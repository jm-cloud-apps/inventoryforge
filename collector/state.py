"""Prior-run state, so we can detect 0 -> in-stock transitions (restocks)."""
import json
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "state.json"


def item_key(item):
    pid = item.get("productId") or item.get("title")
    return f"{item['retailer']}|{item['store']}|{pid}"


def load():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            return {}
    return {}


def save(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))
