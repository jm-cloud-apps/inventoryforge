"""Keyword matching against the editable watchlist (watchlist.json)."""


def normalize(keywords):
    """Accept ['text', ...] or [{'match','label'}, ...]; return list of dicts."""
    out = []
    for kw in keywords:
        if isinstance(kw, str):
            out.append({"match": kw, "label": kw})
        elif isinstance(kw, dict) and kw.get("match"):
            out.append({"match": kw["match"], "label": kw.get("label") or kw["match"]})
    return out


_EXCLUDES = []


def set_excludes(terms):
    """Titles containing any of these are never matched — filters out accessories
    (binders, portfolios, sticker/poster collections) that match a set name but aren't
    the sealed product you're hunting. Module-level because each retailer calls
    matched_label() directly and the collector is single-threaded; set once per run."""
    global _EXCLUDES
    _EXCLUDES = [t.lower() for t in (terms or []) if t]


def matched_label(title, keywords):
    """Case-insensitive substring match. Returns the label of the first hit, or None.
    Exclusions win over keywords."""
    t = (title or "").lower()
    if any(x in t for x in _EXCLUDES):
        return None
    for kw in keywords:
        if kw["match"].lower() in t:
            return kw["label"]
    return None


def search_terms(keywords, extra=None):
    """Query terms to feed each retailer's search box. We search the watchlist entries
    themselves (e.g. "Prismatic Evolutions") — far better hit rate than a generic "pokemon"
    search, which buries TCG under plush/figures. `extra` appends any config-level terms."""
    out, seen = [], set()
    for t in [k["match"] for k in keywords] + list(extra or []):
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out
