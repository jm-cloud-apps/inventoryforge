"""InventoryForge collector — run from the repo root:

    python -m collector.run                 # normal run: scrape, write data, alert
    python -m collector.run --dry-run        # scrape + write data, but no alerts
    python -m collector.run --retailer ebgames             # debug just one retailer

Reads config.json + watchlist.json, scrapes each enabled retailer via one shared browser,
detects out->in-stock transitions vs the previous run, writes data/latest.json (+ appends
data/history.jsonl), then fires alerts for anything that just came back in stock.

Reliability: if a retailer errors or gets bot-blocked, its rows are NOT dropped and are NOT
treated as out-of-stock. We carry forward its last-known rows (flagged "stale") and record
the source as "unreachable" so the dashboard can say "couldn't check" instead of lying.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from . import alerts, state
from .browser import browser_context
from .match import matched_label, normalize  # noqa: F401 (matched_label used by retailers)
from .retailers import REGISTRY

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(name):
    return json.loads((ROOT / name).read_text())


def load_prev_latest():
    p = DATA / "latest.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def is_in_stock(status):
    s = (status or "").lower()
    return any(w in s for w in ("in stock", "available", "in-store", "limited")) \
        and "not available" not in s and "unavailable" not in s


def collect(args):
    load_dotenv(ROOT / ".env")
    config = load_json("config.json")
    keywords = normalize(load_json("watchlist.json").get("keywords", []))
    if not keywords:
        print("watchlist.json has no keywords — nothing to match. Add some and re-run.")
        return

    prev_latest = load_prev_latest()
    prev_by_retailer, prev_sources = {}, prev_latest.get("sources", {})
    for it in prev_latest.get("items", []):
        prev_by_retailer.setdefault(it.get("retailer"), []).append(it)

    which = args.retailer
    prev_state = state.load()
    ts = now_iso()
    items, sources = [], {}

    def carry_forward(disp, status):
        """Reuse a retailer's last-known rows when we didn't freshly fetch it."""
        carried = prev_by_retailer.get(disp, [])
        for it in carried:
            items.append({**it, "stale": True})
        last_ok = (prev_sources.get(disp) or {}).get("lastOkAt") or (prev_sources.get(disp) or {}).get("at")
        sources[disp] = {"status": status, "count": len(carried), "at": ts, "lastOkAt": last_ok}

    with browser_context() as ctx:
        for name, rcfg in config["retailers"].items():
            if not rcfg.get("enabled", True):
                continue
            disp = rcfg.get("displayName", name)
            if which and name != which:
                carry_forward(disp, "skipped")   # debug run: don't wipe the other retailers
                continue
            try:
                got = REGISTRY[name](ctx, rcfg, keywords)
                prev_count = len(prev_by_retailer.get(disp, []))
                if not got and prev_count:
                    # Returned nothing but had rows last time -> almost certainly a transient
                    # bot-block/hiccup, not a real empty. Keep last-known instead of wiping it.
                    print(f"[{name}] 0 rows but had {prev_count} last run — treating as unreachable")
                    carry_forward(disp, "unreachable")
                else:
                    items.extend(got)            # fresh rows
                    sources[disp] = {"status": "ok", "count": len(got), "at": ts, "lastOkAt": ts}
            except Exception as e:
                print(f"[{name}] ERROR: {e}")
                carry_forward(disp, "unreachable")

    # Diff ONLY fresh rows -> detect out->in transitions. Carried (stale) rows keep their
    # previous status/lastRestock and never trigger a restock alert.
    restocks = []
    new_state = dict(prev_state)                 # persist state for carried/skipped retailers
    for it in items:
        if it.get("stale"):
            continue
        key = state.item_key(it)
        prior = prev_state.get(key, {})
        in_now = is_in_stock(it.get("status"))
        it["lastSeen"] = ts
        it["lastRestock"] = prior.get("lastRestock")
        if in_now and not prior.get("inStock"):
            it["lastRestock"] = ts
            restocks.append(it)
        new_state[key] = {"inStock": in_now, "lastRestock": it["lastRestock"], "status": it.get("status")}

    state.save(new_state)  # runtime diff state (git-ignored) — always persist
    fresh = len([i for i in items if not i.get("stale")])
    unreachable = [d for d, s in sources.items() if s["status"] == "unreachable"]

    # Material-change gate: only rewrite latest.json (=> only commit + push + redeploy) when
    # item statuses or source reachability actually changed vs the published snapshot. A run
    # that finds nothing new leaves latest.json untouched, so the git history stays quiet and
    # "Updated" on the page reflects the last real change, not the last check.
    def signature(items_list, sources_map):
        isig = sorted((f"{i['retailer']}|{i['store']}|{i.get('productId') or i.get('title')}",
                       i.get("status")) for i in items_list)
        ssig = sorted((k, (v or {}).get("status")) for k, v in sources_map.items())
        return [isig, ssig]

    if signature(items, sources) == signature(prev_latest.get("items", []), prev_latest.get("sources", {})):
        print(f"[run] no material change ({fresh} rows) — latest.json untouched, nothing to push @ {ts}")
        return

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "latest.json").write_text(json.dumps({
        "updatedAt": ts,
        "region": config.get("region", ""),
        "watchlist": [k["label"] for k in keywords],
        "sources": sources,
        "items": sorted(items, key=lambda i: (not is_in_stock(i.get("status")),
                                              i.get("retailer", ""), i.get("title", ""))),
    }, indent=2))

    if restocks:
        with (DATA / "history.jsonl").open("a") as f:
            for it in restocks:
                f.write(json.dumps({"at": ts, **{k: it.get(k) for k in
                        ("retailer", "store", "title", "price", "url")}}) + "\n")

    print(f"[run] CHANGED — {fresh} rows, {len(restocks)} restock(s), "
          f"unreachable: {unreachable or 'none'} @ {ts}; wrote latest.json")

    if restocks and not args.dry_run:
        alerts.notify(restocks)
    elif restocks:
        print("[run] --dry-run: skipping alerts")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="scrape + write data but don't send alerts")
    ap.add_argument("--retailer", help="run only one retailer (ebgames|londondrugs|superstore)")
    ap.add_argument("--headless", action="store_true",
                    help="run headless (WILL be Cloudflare-blocked; debug on non-protected pages only)")
    args = ap.parse_args()
    if args.headless:
        os.environ["HEADLESS"] = "1"
    collect(args)


if __name__ == "__main__":
    main()
