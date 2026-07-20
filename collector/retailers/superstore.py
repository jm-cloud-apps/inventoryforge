"""Real Canadian Superstore — LOW VALUE for TCG (kept for completeness).

Live finding: RCSS's online catalog for "pokemon" is snacks, plush, candy, apparel — it
does NOT list Pokémon trading cards (those are in-store impulse items behind the counter).
The old api.pcexpress.ca API is also legacy; the current site is an SSR Chakra-UI SPA
(iceberg-bff). So we DOM-scrape the search page. Card-specific watchlist keywords
(e.g. "Elite Trainer Box") will simply match nothing here — that's expected.

Each tile carries an "Add <title> to cart" button (confirmed), a price, and an optional
"Out of Stock" label. Selectors may need a nudge if the SPA markup shifts.
"""
from urllib.parse import quote

from ..browser import settle
from ..match import matched_label, search_terms


def fetch(ctx, cfg, keywords):
    page = ctx.new_page()
    items = []
    try:
        for term in search_terms(keywords, cfg.get("searchTerms")):
            page.goto(f'{cfg["origin"]}/search?search-bar={quote(term)}',
                      wait_until="domcontentloaded", timeout=45000)
            settle(page)
            store = page.evaluate(
                r"""() => (document.querySelector('[data-testid*="store" i],[class*="store-locator" i]')?.textContent || '').trim().slice(0, 80)"""
            )
            cards = page.evaluate(r"""() => {
              const out = [];
              document.querySelectorAll('button[aria-label^="Add "]').forEach(btn => {
                const title = (btn.getAttribute('aria-label') || '').replace(/^Add /, '').replace(/ to cart$/i, '').trim();
                let el = btn;
                for (let i = 0; i < 6 && el; i++) { if (/\$\d/.test(el.innerText || '')) break; el = el.parentElement; }
                const text = (el && el.innerText) || '';
                const pm = text.match(/\$([0-9]+\.[0-9]{2})/);
                const link = (el && el.querySelector('a[href*="/p/"]')?.getAttribute('href')) || '';
                if (title) out.push({ title, price: pm ? pm[1] : null, oos: /out of stock/i.test(text), url: link });
              });
              return out;
            }""")
            for c in cards:
                label = matched_label(c["title"], keywords)
                if not label:
                    continue
                items.append({
                    "retailer": cfg["displayName"],
                    "store": store or "RCSS (online)",
                    "title": c["title"],
                    "matchedKeyword": label,
                    "status": "Out of Stock" if c["oos"] else "Available online",
                    "price": float(c["price"]) if c["price"] else None,
                    "url": (cfg["origin"] + c["url"]) if c["url"].startswith("/") else (c["url"] or cfg["origin"]),
                    "productId": c["url"] or c["title"],
                })
        print(f"[superstore] {len(items)} matched row(s) — reminder: RCSS online carries no TCG cards")
    finally:
        page.close()
    return items
