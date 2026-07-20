"""London Drugs — secondary TCG source (confirmed live; Mozu/Kibo storefront).

v1: scrape the search page for online listing + price. Cards are `a[href*="/p/<CODE>"]`
with the title in the image alt/aria-label; the price + any out-of-stock text live on the
enclosing tile. Status is ONLINE availability (Available online / Out of Stock).

v2 (not built): per-store stock is behind each card's "Check Nearby Availability" control,
which calls the Mozu/Kibo location-inventory API. Add that to get Vancouver/Burnaby shelf
status the way EB Games already does.
"""
from urllib.parse import quote

from ..browser import settle
from ..match import matched_label, search_terms


def fetch(ctx, cfg, keywords):
    page = ctx.new_page()
    items = []
    try:
        for term in search_terms(keywords, cfg.get("searchTerms")):
            page.goto(f'{cfg["origin"]}/search?q={quote(term)}',
                      wait_until="domcontentloaded", timeout=45000)
            settle(page)
            cards = page.evaluate(r"""() => {
              const byCode = {};
              document.querySelectorAll('a[href*="/p/"]').forEach(a => {
                const href = a.getAttribute('href') || '';
                const m = href.match(/\/p\/([A-Za-z0-9]+)/);
                if (!m) return;
                const code = m[1];
                let title = a.querySelector('img')?.getAttribute('alt') || a.getAttribute('aria-label') || '';
                let el = a;                                   // walk up to the tile with a price
                for (let i = 0; i < 6 && el; i++) { if (/\$\d/.test(el.innerText || '')) break; el = el.parentElement; }
                const text = (el && el.innerText) || '';
                if (!title) title = (text.split('\n')[0] || '').trim();
                const pm = text.match(/\$([0-9]+\.[0-9]{2})/);
                const oos = /out of stock|unavailable|temporarily/i.test(text);
                if (title && !byCode[code])
                  byCode[code] = { code, title: title.trim(), price: pm ? pm[1] : null, oos,
                                   url: href.startsWith('http') ? href : location.origin + href };
              });
              return Object.values(byCode);
            }""")
            for c in cards:
                label = matched_label(c["title"], keywords)
                if not label:
                    continue
                items.append({
                    "retailer": cfg["displayName"],
                    "store": "London Drugs (online)",
                    "title": c["title"],
                    "matchedKeyword": label,
                    "status": "Out of Stock" if c["oos"] else "Available online",
                    "price": float(c["price"]) if c["price"] else None,
                    "url": c["url"],
                    "productId": c["code"],
                })
        print(f"[londondrugs] {len(items)} matched row(s)")
    finally:
        page.close()
    return items
