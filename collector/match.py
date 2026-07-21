"""Keyword matching against the editable watchlist (watchlist.json)."""
import unicodedata


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
_REQUIRE = []


def fold(s):
    """Lowercase + strip accents so 'Pokémon' and 'Pokemon' compare equal."""
    return "".join(c for c in unicodedata.normalize("NFKD", (s or "").lower())
                   if not unicodedata.combining(c))


def set_excludes(terms):
    """Titles containing any of these are never matched — filters out accessories
    (binders, portfolios, sticker/poster collections) that match a set name but aren't
    the sealed product you're hunting. Module-level because each retailer calls
    matched_label() directly and the collector is single-threaded; set once per run."""
    global _EXCLUDES
    _EXCLUDES = [fold(t) for t in (terms or []) if t]


def set_require(terms):
    """A title must contain at least one of these to match at all. Defaults to 'Pokemon',
    which stops generic keywords pulling in unrelated products — e.g. '30th Anniversary'
    was matching 'U2 - The Joshua Tree: 30th Anniversary - 2 LP Vinyl'."""
    global _REQUIRE
    _REQUIRE = [fold(t) for t in (terms or []) if t]


def matched_label(title, keywords):
    """Case-insensitive, accent-insensitive substring match. Returns the label of the first
    hit, or None. Order: required terms, then exclusions, then keywords."""
    t = fold(title)
    if _REQUIRE and not any(r in t for r in _REQUIRE):
        return None
    if any(x in t for x in _EXCLUDES):
        return None
    for kw in keywords:
        if fold(kw["match"]) in t:
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
