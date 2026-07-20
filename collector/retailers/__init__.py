"""Registry of retailer collectors. Each exposes fetch(ctx, cfg, keywords) -> [item dict]."""
from . import ebgames, londondrugs, superstore

REGISTRY = {
    "superstore": superstore.fetch,
    "ebgames": ebgames.fetch,
    "londondrugs": londondrugs.fetch,
}
