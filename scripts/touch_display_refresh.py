from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))
TARGETS = [
    ROOT / "docs/data/jobs.json",
    ROOT / "data/items.json",
]


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(JST)


def touch(path: Path, now: datetime, once_per_day: bool = False) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    previous = parse_timestamp(payload.get("generated_at"))
    if once_per_day and previous is not None and previous.date() == now.date():
        return False

    timestamp = now.isoformat(timespec="seconds")
    payload["generated_at"] = timestamp
    payload["last_mode"] = "display_refresh"
    stats = payload.setdefault("stats", {})
    stats["discovered_links_this_run"] = 0
    stats["new_courses_this_run"] = 0
    stats["details_checked_this_run"] = 0
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once-per-day",
        action="store_true",
        help="Skip files whose generated_at is already today in JST.",
    )
    args = parser.parse_args()

    now = datetime.now(JST)
    updated = []
    for path in TARGETS:
        if touch(path, now, once_per_day=args.once_per_day):
            updated.append(path.relative_to(ROOT).as_posix())

    if updated:
        print(f"display refresh timestamp: {now.isoformat(timespec='seconds')}")
        print(f"updated: {', '.join(updated)}")
    else:
        print("display refresh already recorded today; no changes")


if __name__ == "__main__":
    main()
