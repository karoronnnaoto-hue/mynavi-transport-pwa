from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from scrape import CATALOG, DB, JST, OUT, STATE, load_json, write_outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fragments", type=Path, default=Path("work/fragments"))
    parser.add_argument("--mode", default="detail_batch")
    args = parser.parse_args()

    old_payload = load_json(DB, load_json(OUT, {"items": []}))
    items_by_id = {x.get("id"): x for x in old_payload.get("items", []) if x.get("id")}
    catalog = load_json(CATALOG, {"urls": {}})
    crawl_state = load_json(STATE, {})

    checked = 0
    failures = 0
    for path in sorted(args.fragments.glob("*.json")):
        fragment = load_json(path, {})
        for item in fragment.get("items", []):
            if item.get("id"):
                items_by_id[item["id"]] = item
        for key, update in fragment.get("catalog_updates", {}).items():
            catalog.setdefault("urls", {}).setdefault(key, {}).update(update)
        checked += fragment.get("checked", 0)
        failures += len(fragment.get("failures", []))

    now = datetime.now(JST)
    crawl_state.setdefault("detail_batch", {})
    crawl_state["detail_batch"].update({
        "last_merged_at": now.isoformat(timespec="seconds"),
        "last_parallel_checked": checked,
        "last_parallel_failures": failures,
    })
    write_outputs(catalog, crawl_state, items_by_id, args.mode, now, checked=checked)
    print(f"merged fragments: checked={checked} failures={failures}")


if __name__ == "__main__":
    main()
