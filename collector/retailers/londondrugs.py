"""London Drugs — per-store availability for specific Vancouver/Burnaby stores.

For each matched product: open its PDP, open the store picker, search a postal code, and
scrape the per-store cards. Each card carries the store's address/postal + a stock badge
("Available for pickup today" / "Not In Stock") for THAT product. We keep only the stores
listed in config (matched by postal code) and emit an in/out row per (product x store).

LD is Next.js RSC (the store list arrives via a server action — no clean JSON API), so this
is a DOM-scrape of the picker: slower than EB Games (one PDP + picker per product), but it
gives true per-store shelf/pickup stock at exactly the stores you care about.
"""
import re
from urllib.parse import quote

from ..browser import settle
from ..match import matched_label, search_terms


def _norm_postal(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _status(card_text):
    """LD uses several badge wordings: 'In Stock', 'Available for pickup today',
    'Not In Stock'. Check the negatives FIRST — 'Not In Stock' contains 'in stock',
    so order is what keeps a plain 'in stock' match from misreading an out-of-stock card.
    ('In-Store Pickup' is a label on every card and must not count as in-stock.)"""
    t = card_text.lower()
    if "not in stock" in t or "out of stock" in t or "unavailable" in t or "not available" in t:
        return "Out of Stock"
    if "in stock" in t or "available for pickup" in t or "pickup today" in t or "available today" in t:
        return "In Stock"
    return "Unknown"


def _search_cards(page, origin, term):
    """Navigate to the search page and scrape product cards, waiting for the SPA to render.
    LD is a Next.js SPA whose results appear AFTER networkidle, so we wait for a product
    link and retry once — otherwise the scrape intermittently sees an empty page."""
    for _ in range(2):
        page.goto(f'{origin}/search?q={quote(term)}', wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_selector('a[href*="/p/"]', timeout=15000)
        except Exception:
            pass
        settle(page, timeout=4000)
        cards = page.evaluate(r"""() => {
          const byCode = {};
          document.querySelectorAll('a[href*="/p/"]').forEach(a => {
            const href = a.getAttribute('href') || '';
            const m = href.match(/\/p\/([A-Za-z0-9]+)/);
            if (!m || byCode[m[1]]) return;
            let title = a.querySelector('img')?.getAttribute('alt') || a.getAttribute('aria-label') || '';
            let el = a;
            for (let i = 0; i < 6 && el; i++) { if (/\$\d/.test(el.innerText || '')) break; el = el.parentElement; }
            const text = (el && el.innerText) || '';
            if (!title) title = (text.split('\n')[0] || '').trim();
            const pm = text.match(/\$([0-9]+\.[0-9]{2})/);
            if (title) byCode[m[1]] = { code: m[1], title: title.trim(), price: pm ? pm[1] : null,
                         url: href.startsWith('http') ? href : location.origin + href };
          });
          return Object.values(byCode);
        }""")
        if cards:
            return cards
    return cards


def _find_products(page, cfg, keywords):
    matched = {}
    for term in search_terms(keywords, cfg.get("searchTerms")):
        for c in _search_cards(page, cfg["origin"], term):
            label = matched_label(c["title"], keywords)
            if label:
                matched[c["code"]] = {**c, "label": label}
    return matched


def fetch(ctx, cfg, keywords):
    page = ctx.new_page()
    items = []
    targets = {_norm_postal(s["postal"]): s["name"] for s in cfg.get("targetStores", [])}
    postal = cfg.get("storeSearchPostal", "V5H 2E2")
    if not targets:
        print("[londondrugs] no targetStores in config — nothing to report per-store")
        page.close()
        return items
    try:
        matched = _find_products(page, cfg, keywords)

        for code, p in list(matched.items())[: cfg.get("maxProducts", 12)]:
            page.goto(p["url"], wait_until="domcontentloaded", timeout=45000)
            settle(page, timeout=10000)
            opener = (page.query_selector("text=/set your store/i")
                      or page.query_selector("text=/select your store/i")
                      or page.query_selector("text=/change store/i"))
            if not opener:
                print(f"[londondrugs] no store picker on '{p['title'][:40]}'")
                continue
            try:
                opener.click()
                page.wait_for_timeout(1800)
                inp = page.query_selector('input[name="searchTerm"], input[placeholder*="postal" i]')
                if not inp:
                    continue
                inp.fill(postal)
                page.wait_for_timeout(1000)
                page.keyboard.press("Enter")
                page.wait_for_timeout(3500)
            except Exception as e:
                print(f"[londondrugs] picker error on '{p['title'][:40]}': {e}")
                continue

            cards = page.evaluate(r"""() => {
              const out = [];
              document.querySelectorAll('*').forEach(el => {
                const t = el.innerText || '';
                if (/[\d.]+\s*km/.test(t) && /[A-Z]\d[A-Z]\s?\d[A-Z]\d/.test(t)
                    && t.length < 300 && el.children.length < 16)
                  out.push(t.replace(/[ \t]+/g, ' ').trim());
              });
              return [...new Set(out)].sort((a, b) => a.length - b.length);
            }""")

            try:
                price = float(p["price"]) if p.get("price") else None
            except (TypeError, ValueError):
                price = None

            seen = set()
            for card in cards:
                mp = re.search(r"[A-Z]\d[A-Z]\s?\d[A-Z]\d", card)
                if not mp:
                    continue
                pc = _norm_postal(mp.group())
                if pc not in targets or pc in seen:
                    continue
                seen.add(pc)
                items.append({
                    "retailer": cfg["displayName"],
                    "store": f"London Drugs — {targets[pc]}",
                    "title": p["title"],
                    "matchedKeyword": p["label"],
                    "status": _status(card),
                    "price": price,
                    "url": p["url"],
                    "productId": f"{code}|{pc}",
                })
        print(f"[londondrugs] {len(matched)} product(s) -> {len(items)} store rows "
              f"({len(targets)} target stores)")
    finally:
        page.close()
    return items
