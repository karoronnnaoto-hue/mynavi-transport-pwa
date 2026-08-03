from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))
TARGETS = [
    ROOT / "docs/data/jobs.json",
    ROOT / "data/items.json",
]


def touch(path: Path, timestamp: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["generated_at"] = timestamp
    payload["last_mode"] = "display_refresh"
    stats = payload.setdefault("stats", {})
    stats["discovered_links_this_run"] = 0
    stats["new_courses_this_run"] = 0
    stats["details_checked_this_run"] = 0
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    timestamp = datetime.now(JST).isoformat(timespec="seconds")
    for path in TARGETS:
        touch(path, timestamp)
    print(f"display refresh timestamp: {timestamp}")


if __name__ == "__main__":
    main()
