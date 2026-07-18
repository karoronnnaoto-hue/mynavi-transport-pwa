from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/data/jobs.json"
CATALOG = ROOT / "data/catalog.json"
STATE = ROOT / "data/crawl_state.json"
TARGETS = ROOT / "targets.txt"
JST = timezone(timedelta(hours=9))

# 全体検索の入口。各入口を少しずつ巡回し、毎回全ページを読み直さない。
SEARCH_SEEDS = [
    "https://job.mynavi.jp/28/pc/search/is_it1.html",  # インターンシップ
    "https://job.mynavi.jp/28/pc/search/is_it2.html",  # 仕事体験
    "https://job.mynavi.jp/28/pc/search/is_it3.html",  # オープン・カンパニー等
]
MAX_LIST_PAGES_PER_RUN = 9
MAX_DETAIL_PAGES_PER_RUN = 90
REQUEST_INTERVAL_SECONDS = 2.5
DETAIL_REFRESH_DAYS = 1
URGENT_DEADLINE_DAYS = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PersonalInternshipWatcher/2.0; low-frequency public-page checker)",
    "Accept-Language": "ja,en;q=0.8",
}

YEN_RE = re.compile(r"(?:上限|最大|一律)?\s*([0-9０-９,，]+)\s*(?:円|万円)")
PREFS = "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split()


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_digits(value: str) -> str:
    return value.translate(str.maketrans("０１２３４５６７８９，", "0123456789,"))


def canonical_url(raw_url: str) -> str:
    """追跡用クエリを除き、同じコースURLを一意にする。"""
    p = urlparse(raw_url)
    allowed = []
    for key, value in parse_qsl(p.query, keep_blank_values=True):
        if key.lower() in {"corpid", "optno", "courseid", "id"}:
            allowed.append((key, value))
    allowed.sort(key=lambda x: x[0].lower())
    path = re.sub(r"/+", "/", p.path).rstrip("/")
    return urlunparse(("https", "job.mynavi.jp", path, "", urlencode(allowed), ""))


def course_key(url: str) -> str:
    p = urlparse(url)
    q = {k.lower(): v for k, v in parse_qsl(p.query)}
    corp = q.get("corpid")
    opt = q.get("optno") or q.get("courseid")
    if corp and opt:
        return f"corp:{corp}:course:{opt}"
    return "url:" + hashlib.sha256(canonical_url(url).encode()).hexdigest()[:24]


def classify(text: str):
    t = normalize_digits(text)
    if re.search(r"支給なし|自己負担|各自負担|支給いたしません", t):
        return "none", 0
    if re.search(r"全額|実費.*支給|全額補助", t):
        return "unlimited", None
    m = YEN_RE.search(t)
    if m:
        raw = m.group(0)
        amount = int(m.group(1).replace(",", ""))
        amount *= 10000 if "万円" in raw else 1
        return ("limit" if ("上限" in raw or "最大" in raw) else "fixed"), amount
    if re.search(r"規定|一部|遠方|条件|相談", t):
        return "conditional", None
    if "支給あり" in t or "交通費" in t:
        return "unknown", None
    return "unknown", None


def extract_labeled_text(soup: BeautifulSoup, labels: list[str], width: int = 5) -> str:
    lines = [x.strip() for x in soup.get_text("\n", strip=True).splitlines() if x.strip()]
    for idx, line in enumerate(lines):
        if any(line == label or line.startswith(label) for label in labels):
            return " ".join(lines[idx : idx + width])[:700]
    return ""


def parse_dates(text: str) -> list[str]:
    """明示された2026年の日付をISO形式へ。期間表記は両端を保存する。"""
    t = normalize_digits(text)
    today = datetime.now(JST).date()
    years = re.findall(r"(20\d{2})年", t)
    default_year = int(years[0]) if years else today.year
    found: set[str] = set()

    for y, m, d in re.findall(r"(20\d{2})[年/.-]\s*(\d{1,2})[月/.-]\s*(\d{1,2})日?", t):
        try:
            found.add(date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            pass

    # 年省略の「8月4日」「8/4」
    for m, d in re.findall(r"(?<!\d)(\d{1,2})\s*(?:月|/)\s*(\d{1,2})\s*日?", t):
        try:
            candidate = date(default_year, int(m), int(d))
            # 年末に翌年の日付を拾う場合の軽い補正
            if candidate < today - timedelta(days=120):
                candidate = date(default_year + 1, int(m), int(d))
            found.add(candidate.isoformat())
        except ValueError:
            pass
    return sorted(found)


def extract_detail_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    output = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        p = urlparse(href)
        if p.hostname != "job.mynavi.jp":
            continue
        if "displayInternship" not in p.path:
            continue
        q = {k.lower(): v for k, v in parse_qsl(p.query)}
        if q.get("corpid") and (q.get("optno") or q.get("courseid")):
            output.append(canonical_url(href))
    return list(dict.fromkeys(output))


def find_next_page(base_url: str, html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        aria = a.get("aria-label", "")
        if "次の30社" in text or text in {"次へ", "次のページ"} or "次" in aria:
            candidate = urljoin(base_url, a["href"])
            if urlparse(candidate).hostname == "job.mynavi.jp":
                return candidate
    return None


def parse_detail(url: str, html: str, old_item: dict | None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    company = re.sub(r"のインターンシップ.*$", "", title).strip() or "企業名不明"
    h1 = soup.find("h1")
    course = h1.get_text(" ", strip=True) if h1 else title
    transport = extract_labeled_text(soup, ["交通費", "交通費支給"])
    lodging = extract_labeled_text(soup, ["宿泊費", "宿泊費支給"])
    schedule = extract_labeled_text(soup, ["開催時期", "開催日", "日程"], width=8)
    deadline = extract_labeled_text(soup, ["応募締切", "締切"], width=4)
    alltext = soup.get_text(" ", strip=True)
    status = detect_status(alltext)
    locations = [p for p in PREFS if p in alltext]
    transport_type, amount = classify(transport)
    key = course_key(url)
    now = datetime.now(JST).isoformat(timespec="seconds")
    return {
        "id": key,
        "company": company,
        "course": course[:220],
        "locations": locations[:12],
        "event_dates": parse_dates(schedule),
        "schedule_text": schedule or "開催日の明示なし",
        "deadline_text": deadline or "記載なし",
        "deadline": parse_deadline(deadline),
        "transport_type": transport_type,
        "transport_amount": amount,
        "transport_original": transport or "交通費欄を特定できませんでした。",
        "lodging_provided": bool(lodging and not re.search(r"なし|自己負担|各自負担", lodging)),
        "lodging_text": lodging or "記載なし",
        "first_seen": (old_item or {}).get("first_seen", now),
        "last_checked": now,
        "is_new": old_item is None,
        "status": status,
        "closed_at": now if status in {"closed", "cancelled"} else None,
        "url": canonical_url(url),
    }



def parse_deadline(text: str) -> str | None:
    dates = parse_dates(text)
    return dates[0] if dates else None


def detect_status(text: str) -> str:
    if re.search(r"満席|受付終了|募集終了|応募受付終了|エントリー受付終了|開催終了", text):
        return "closed"
    if re.search(r"中止|開催中止", text):
        return "cancelled"
    return "open"


def is_urgent(item: dict, today: date) -> bool:
    raw = item.get("deadline")
    if not raw:
        return False
    try:
        deadline = date.fromisoformat(raw)
    except ValueError:
        return False
    return today <= deadline <= today + timedelta(days=URGENT_DEADLINE_DAYS)

def item_fingerprint(item: dict) -> str:
    """IDが取れない場合も、内容が同じ募集を重複表示しない。"""
    parts = [
        re.sub(r"\s+", "", item.get("company", "")),
        re.sub(r"\s+", "", item.get("course", "")),
        ",".join(item.get("event_dates", [])),
        ",".join(sorted(item.get("locations", []))),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def dedupe_items(items: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    fingerprints: set[str] = set()
    for item in sorted(items, key=lambda x: x.get("last_checked", ""), reverse=True):
        if item["id"] in by_id:
            continue
        fp = item_fingerprint(item)
        if fp in fingerprints:
            continue
        by_id[item["id"]] = item
        fingerprints.add(fp)
    return list(by_id.values())


def fetch(session: requests.Session, url: str) -> str:
    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text



def discover_courses(session: requests.Session, catalog: dict, crawl_state: dict, now: datetime) -> tuple[int, int]:
    discovered: list[str] = []
    pages_left = MAX_LIST_PAGES_PER_RUN
    for seed in SEARCH_SEEDS:
        page_url = crawl_state.get("next_pages", {}).get(seed) or seed
        while page_url and pages_left > 0:
            try:
                html = fetch(session, page_url)
                discovered.extend(extract_detail_links(page_url, html))
                next_page = find_next_page(page_url, html)
                crawl_state.setdefault("next_pages", {})[seed] = next_page or seed
                page_url = next_page
                pages_left -= 1
                time.sleep(REQUEST_INTERVAL_SECONDS)
            except Exception as exc:
                print("list failed", page_url, exc)
                crawl_state.setdefault("next_pages", {})[seed] = seed
                break
        if pages_left <= 0:
            break

    new_count = 0
    for url in dict.fromkeys(discovered):
        key = course_key(url)
        if key not in catalog.setdefault("urls", {}):
            new_count += 1
        record = catalog["urls"].get(key, {})
        record.update({"url": canonical_url(url), "last_discovered": now.isoformat(timespec="seconds")})
        catalog["urls"][key] = record
    return len(set(discovered)), new_count


def manual_urls() -> list[str]:
    if not TARGETS.exists():
        return []
    return [
        canonical_url(x.strip())
        for x in TARGETS.read_text(encoding="utf-8").splitlines()
        if x.strip() and not x.lstrip().startswith("#")
    ]


def select_candidates(mode: str, catalog: dict, items_by_id: dict, now: datetime) -> list[tuple[int, str, str, str]]:
    today = now.date()
    candidates = []
    manual = set(manual_urls())
    for key, record in catalog.get("urls", {}).items():
        url = record.get("url")
        if not url:
            continue
        old = items_by_id.get(key)
        last = record.get("last_checked") or ""
        last_dt = None
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
            except ValueError:
                pass

        include = False
        priority = 5
        if mode == "discover":
            include = old is None or url in manual
            priority = 0 if old is None else 1
        elif mode == "refresh":
            include = old is not None and (last_dt is None or last_dt < now - timedelta(hours=6))
            priority = 1
        elif mode == "urgent":
            include = old is not None and old.get("status", "open") == "open" and is_urgent(old, today)
            priority = 0
        elif mode == "cleanup":
            include = old is not None and (
                old.get("status", "open") != "open"
                or not old.get("event_dates")
                or any(d < today.isoformat() for d in old.get("event_dates", []))
            )
            priority = 0
        elif mode == "all":
            include = old is None or last_dt is None or last_dt < now - timedelta(days=DETAIL_REFRESH_DAYS)
            priority = 0 if old is None else 1
        if include:
            candidates.append((priority, last, key, url))
    candidates.sort()
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["discover", "refresh", "urgent", "cleanup", "all"], default="all")
    parser.add_argument("--limit", type=int, default=MAX_DETAIL_PAGES_PER_RUN)
    args = parser.parse_args()

    old_payload = load_json(OUT, {"items": []})
    old_by_id = {x.get("id"): x for x in old_payload.get("items", []) if x.get("id")}
    catalog = load_json(CATALOG, {"urls": {}})
    crawl_state = load_json(STATE, {"next_pages": {seed: seed for seed in SEARCH_SEEDS}})
    session = requests.Session()
    now = datetime.now(JST)

    # 手動URLはすべてのモードでカタログへ登録。
    for url in manual_urls():
        key = course_key(url)
        catalog.setdefault("urls", {}).setdefault(key, {})["url"] = url

    discovered_count = 0
    new_count = 0
    if args.mode in {"discover", "all"}:
        discovered_count, new_count = discover_courses(session, catalog, crawl_state, now)

    items_by_id = dict(old_by_id)
    candidates = select_candidates(args.mode, catalog, items_by_id, now)
    checked = 0
    for _, _, key, url in candidates[: max(0, args.limit)]:
        try:
            html = fetch(session, url)
            item = parse_detail(url, html, old_by_id.get(key))
            items_by_id[key] = item
            catalog["urls"][key]["last_checked"] = item["last_checked"]
            catalog["urls"][key]["status"] = item["status"]
            checked += 1
            time.sleep(REQUEST_INTERVAL_SECONDS)
        except Exception as exc:
            print("detail failed", url, exc)

    # 終了整理では終了済みを削除せず履歴として保持し、画面側で非表示にできる状態にする。
    items = dedupe_items(list(items_by_id.values()))
    items.sort(key=lambda x: (
        x.get("status", "open") != "open",
        x.get("event_dates", ["9999-12-31"])[0] if x.get("event_dates") else "9999-12-31",
        x.get("company", ""),
    ))
    generated = now.isoformat(timespec="seconds")
    save_json(OUT, {
        "generated_at": generated,
        "last_mode": args.mode,
        "stats": {
            "catalog_courses": len(catalog.get("urls", {})),
            "displayed_courses": len(items),
            "discovered_links_this_run": discovered_count,
            "new_courses_this_run": new_count,
            "details_checked_this_run": checked,
        },
        "items": items,
    })
    save_json(CATALOG, catalog)
    save_json(STATE, crawl_state)


if __name__ == "__main__":
    main()
