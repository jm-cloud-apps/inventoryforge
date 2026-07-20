"""EB Games Canada — the primary TCG source (confirmed live).

Flow (no per-product page visit needed):
  1. For each watchlist term, scrape /SearchResult/QuickSearch?q=<term> for product tiles
     (url-id + title + price); keep the ones whose title matches the watchlist.
  2. For each matched product, call the store-availability endpoint from inside the page
     (carries the Cloudflare cookie), using the URL product id directly as the sku:
        GET /api/store/SearchStores?term=<city>&sku=<url-id>&limit=<n>
     -> [{ name, city, availability:{ color }, ... }]

Confirmed live: the URL id works as the sku param (returns the same per-store color as the
product's internal data-skus). Status granularity is a per-store COLOR (red/yellow/green),
not a unit count — that's all EB Games exposes.
"""
from urllib.parse import quote

from ..browser import settle
from ..match import matched_label, search_terms

COLOR_STATUS = {
    "green": "In Stock", "lime": "In Stock",
    "yellow": "Limited Stock", "orange": "Limited Stock", "amber": "Limited Stock",
    "red": "Out of Stock", "grey": "Not Carried", "gray": "Not Carried",
}


def fetch(ctx, cfg, keywords):
    page = ctx.new_page()
    items = []
    try:
        page.goto(cfg["origin"] + "/", wait_until="domcontentloaded", timeout=45000)
        settle(page)

        matched = {}
        for term in search_terms(keywords, cfg.get("searchTerms")):
            page.goto(f'{cfg["origin"]}/SearchResult/QuickSearch?q={quote(term)}',
                      wait_until="domcontentloaded", timeout=45000)
            settle(page)
            products = page.evaluate(r"""() => {
              const seen = {};
              document.querySelectorAll('a[href*="/Games/"]').forEach(a => {
                const href = a.getAttribute('href') || '';
                const m = href.match(/\/Games\/(\d{5,})/);
                if (!m || seen[m[1]]) return;
                const title = (a.getAttribute('title') || a.textContent || '').trim().replace(/\s+/g, ' ');
                if (!title || title.length < 5) return;
                let el = a, price = null;                     // walk up the tile for a price
                for (let i = 0; i < 6 && el; i++) {
                  const pm = (el.innerText || '').match(/\$([0-9]+\.[0-9]{2})/);
                  if (pm) { price = pm[1]; break; }
                  el = el.parentElement;
                }
                seen[m[1]] = { urlId: m[1], title, price,
                               url: href.startsWith('http') ? href : location.origin + href };
              });
              return Object.values(seen);
            }""")
            for p in products:
                label = matched_label(p["title"], keywords)
                if label:
                    matched[p["urlId"]] = {**p, "label": label}

        store_terms = cfg.get("storeTerms", ["Vancouver", "Burnaby"])
        keep = {c.lower().strip() for c in cfg.get("keepCities", store_terms)}
        limit = cfg.get("storeSearchLimit", 10)

        for urlId, p in list(matched.items())[: cfg.get("maxProducts", 20)]:
            store_map = {}
            for term in store_terms:
                stores = page.evaluate(r"""async ([term, sku, limit]) => {
                  const qs = new URLSearchParams({ term, sku: String(sku), limit: String(limit) });
                  const r = await fetch('/api/store/SearchStores?' + qs, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
                  return r.ok ? await r.json() : [];
                }""", [term, urlId, limit])
                for s in stores or []:
                    if keep and (s.get("city") or "").strip().lower() not in keep:
                        continue
                    store_map[s.get("id")] = s

            try:
                price = float(p["price"]) if p.get("price") else None
            except (TypeError, ValueError):
                price = None

            for s in store_map.values():
                color = ((s.get("availability") or {}).get("color") or "").lower()
                items.append({
                    "retailer": cfg["displayName"],
                    "store": f'{(s.get("name") or "EB Games").title()} — {(s.get("city") or "").strip()}',
                    "title": p["title"],
                    "matchedKeyword": p["label"],
                    "status": COLOR_STATUS.get(color, "Unknown"),
                    "price": price,
                    "url": p["url"],
                    "productId": urlId,
                })
        print(f"[ebgames] {len(matched)} matched product(s) -> {len(items)} store rows")
    finally:
        page.close()
    return items
