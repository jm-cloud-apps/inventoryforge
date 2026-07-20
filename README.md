# InventoryForge

A one-page tracker for Pokémon restocks at **EB Games, London Drugs, and Real Canadian
Superstore** in the **Vancouver / Burnaby** area. You keep an editable list of things to
watch for (by title keyword); a collector on your Mac checks the stores on a schedule, the
dashboard shows current status + last-restock, and you get a **Discord/email ping** the
moment a watched item comes back in stock.

> Status: **working end-to-end.** Live runs return real EB Games per-store availability
> (e.g. *Metropolis at Metrotown — Burnaby*, *The Rise — Vancouver*) and London Drugs online
> listings with prices.

## How it works (and why it's split this way)

```
  YOUR MAC (headed browser)                         GITHUB
  ┌───────────────────────────────┐                 ┌────────────────────────┐
  │ collector/ (patchright, HEADED)│   git push      │ GitHub Pages (static)  │
  │  • real browser clears         │   data/*.json   │  index.html reads      │
  │    Cloudflare bot walls        │ ──────────────► │  data/latest.json →    │
  │  • searches your watchlist     │                 │  renders one dashboard │
  │  • writes data/latest.json     │                 └────────────────────────┘
  │  • Discord/email on restock    │
  │  • launchd runs it on a timer  │
  └───────────────────────────────┘
```

**Why local + headed?** Live testing settled it hard: these retailers sit behind Cloudflare,
and **vanilla Playwright — headless *or* headed — gets stuck on "Just a moment…" forever.**
The fix is [`patchright`](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) (a stealth-patched
Playwright) **running headed**. patchright *headless* is still blocked; only a real, headed
browser window passes. GitHub Actions (datacenter IPs, headless) can't do it — so the
collector runs on your Mac and only the display lives on GitHub.

## Data sources (confirmed live)

| Retailer | How we read it | Status granularity | Notes |
|---|---|---|---|
| **EB Games** ✅ | Search page scrape → `GET /api/store/SearchStores?term=<city>&sku=<product-id>&limit=10` | Per-store **traffic-light color** (green=in / yellow=limited / red=out). No unit counts. | **Primary TCG source.** Real per-store Vancouver/Burnaby availability. |
| **London Drugs** ✅ | Search page scrape (Mozu/Kibo storefront) | **Online** availability + price | Carries TCG. Per-store "Check Nearby Availability" is a v2. |
| **Real Canadian Superstore** ⚠️ | Search page scrape | Binary (online) | **Disabled by default.** RCSS online = snacks/plush/apparel; it does **not** list Pokémon cards (they're in-store impulse items). Enable only if you want to track Pokémon *merch*. |

## Setup

```bash
cd inventoryforge
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
patchright install chromium        # one-time browser download (note: patchright, not playwright)

cp .env.example .env               # then paste your Discord webhook URL into .env
```

## Editing your watchlist

Edit **`watchlist.json`** any time. Each entry is matched (case-insensitive substring) against
product titles **and** used as the search query at each retailer:

```json
{ "keywords": [
    { "match": "Prismatic Evolutions", "label": "Prismatic Evolutions" },
    { "match": "Ascended Heroes" },
    { "match": "Moltres" }
] }
```

**Tip:** specific set names (`"Prismatic Evolutions"`) work far better than broad terms like
`"Elite Trainer Box"` (which matches every set at every store and makes runs slower).

## Running

```bash
python -m collector.run                 # full run: scrape, write data, alert  (a browser window WILL appear)
python -m collector.run --dry-run       # scrape + write data, no alerts
python -m collector.run --retailer ebgames   # just one retailer
```

A real Chromium window opens while it runs — that's required to pass Cloudflare. It closes
when the run finishes (~1–2 min). `scripts/run_collector.sh` does one full cycle **and**
commits+pushes `data/` if it changed (that's what redeploys the Pages site).

## Scheduling (macOS launchd)

```bash
cp scripts/com.inventoryforge.collector.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.inventoryforge.collector.plist
tail -f collector.log
```

⚠️ **Heads-up:** because it runs headed, a browser window pops up each cycle (default every
20 min) while you're logged in. If that's annoying, raise `StartInterval` in the plist (e.g.
`1800` = 30 min), or just run it manually when you're at the machine. This is the trade-off
for beating the bot-walls for free.

## Deploying the dashboard (GitHub Pages)

Served from the **`main` branch root** ("Deploy from a branch"); `.nojekyll` tells GitHub to
serve the files as-is. Every collector data push to `main` auto-redeploys the page — no build
step. Enabled under **Settings → Pages → Source: Deploy from a branch → `main` / `/root`**.
(You can switch to a GitHub Actions workflow later if you prefer; it needs a token with
`workflow` scope to push the workflow file.)

## Accuracy — read this

- **As accurate as each retailer's own website**, sampled every ~20 min. It's a strong
  *lead/alert* system — "this flipped to available, go check" — **not** a guarantee the item
  is physically on the shelf, and not a real-time feed.
- **EB Games** shows real per-store status but only as a **color** (in/limited/out), not a
  count, and it's the retailer's own inventory read (can lag reality by hours — call ahead).
- **London Drugs** v1 is **online** availability only (per-store is a v2).
- **"Restock dates" are observed, not predicted** — we log every out→in-stock transition and
  show last-restock + recency; retailers don't publish future delivery dates.
- **Blocked ≠ out of stock:** if a source can't be reached, its rows are kept (flagged
  *stale*) and the source shows "couldn't check" — it never silently reads as out-of-stock.

## Troubleshooting

- **Everything returns 0 / stuck on "Just a moment…"** — the browser profile may be flagged.
  Clear it and re-run: `rm -rf collector/.pw-user-data`. (This happens if you ever run vanilla
  Playwright against these sites; always use the patchright-based collector.)
- **EB Games returns products but 0 store rows** — check `storeTerms`/`keepCities` in
  `config.json` match real city names the store search returns.

## Notes / caveats

Unofficial + fragile: these are internal endpoints/markup that can change without notice;
keep it personal-use and gentle (low frequency, one request at a time). Secrets (`.env`) are
git-ignored and never leave your machine.
