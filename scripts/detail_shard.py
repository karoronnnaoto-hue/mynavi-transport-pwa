from __future__ import annotations

import argparse
import hashlib
import time
from datetime import datetime
from pathlib import Path

import requests

from scrape import (
    CATALOG,
    DB,
    JST,
    OUT,
    amount_analysis_status,
    balance_candidates_by_implementation,
    fetch,
    has_transport_support,
    is_kanto_only,
    is_science_only,
    load_json,
    parse_detail,
    save_json,
    select_candidates,
)


def shard_matches(key: str, index: int, total: int) -> bool:
    value = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return value % total == index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-total", type=int, required=True)
    parser.add_argument("--limit", type=int, default=220)
    parser.add_argument("--request-interval", type=float, default=1.8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.shard_total <= 0 or not 0 <= args.shard_index < args.shard_total:
        raise SystemExit("--shard-index must be between 0 and --shard-total - 1")

    old_payload = load_json(DB, load_json(OUT, {"items": []}))
    old_by_id = {x.get("id"): x for x in old_payload.get("items", []) if x.get("id")}
    catalog = load_json(CATALOG, {"urls": {}})
    now = datetime.now(JST)
    session = requests.Session()

    candidates = select_candidates("rebuild", catalog, old_by_id, now)
    candidates = [candidate for candidate in candidates if shard_matches(candidate[2], args.shard_index, args.shard_total)]
    detail_candidates = balance_candidates_by_implementation(candidates, catalog, args.limit)

    items = []
    catalog_updates = {}
    failures = []
    checked = 0
    time.sleep(args.shard_index * 0.9)
    for _, _, key, url in detail_candidates:
        try:
            html = fetch(session, url)
            item = parse_detail(url, html, old_by_id.get(key))
            item["amount_analysis_status"] = amount_analysis_status(item)
            item["implementation_types"] = catalog.get("urls", {}).get(key, {}).get("implementation_types", [])
            items.append(item)
            catalog_updates[key] = {
                "last_checked": item["last_checked"],
                "status": item["status"],
                "transport_available": has_transport_support(item),
                "science_only": is_science_only(item),
                "kanto_only": is_kanto_only(item),
            }
            checked += 1
            time.sleep(args.request_interval)
        except Exception as exc:
            failures.append({"key": key, "url": url, "error": str(exc)})

    save_json(args.output, {
        "generated_at": now.isoformat(timespec="seconds"),
        "shard_index": args.shard_index,
        "shard_total": args.shard_total,
        "checked": checked,
        "failures": failures,
        "items": items,
        "catalog_updates": catalog_updates,
    })
    print(f"shard {args.shard_index}/{args.shard_total}: checked={checked} failures={len(failures)}")


if __name__ == "__main__":
    main()
