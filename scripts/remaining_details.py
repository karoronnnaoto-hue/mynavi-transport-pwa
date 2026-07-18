from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/catalog.json"
DB = ROOT / "data/items.json"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def main() -> None:
    catalog = load_json(CATALOG, {"urls": {}})
    db = load_json(DB, {"items": []})
    collected = {item.get("id") for item in db.get("items", []) if item.get("id")}
    catalog_keys = {key for key, record in catalog.get("urls", {}).items() if record.get("url")}
    print(len(catalog_keys - collected))


if __name__ == "__main__":
    main()
