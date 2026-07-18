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
NO_TRANSPORT_TEXT = "交通費欄を特定できませんでした。"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PersonalInternshipWatcher/2.0; low-frequency public-page checker)",
    "Accept-Language": "ja,en;q=0.8",
}

YEN_RE = re.compile(r"([0-9０-９,，]+)\s*(円|万円)")
PREFS = "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split()
KANTO_PREFS = {"茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県"}
PREF_ALIASES = {
    "北海道": "北海道", "青森": "青森県", "岩手": "岩手県", "宮城": "宮城県", "秋田": "秋田県", "山形": "山形県", "福島": "福島県",
    "茨城": "茨城県", "栃木": "栃木県", "群馬": "群馬県", "埼玉": "埼玉県", "千葉": "千葉県", "東京": "東京都", "神奈川": "神奈川県",
    "新潟": "新潟県", "富山": "富山県", "石川": "石川県", "福井": "福井県", "山梨": "山梨県", "長野": "長野県",
    "岐阜": "岐阜県", "静岡": "静岡県", "愛知": "愛知県", "三重": "三重県", "滋賀": "滋賀県", "京都": "京都府",
    "大阪": "大阪府", "兵庫": "兵庫県", "奈良": "奈良県", "和歌山": "和歌山県", "鳥取": "鳥取県", "島根": "島根県",
    "岡山": "岡山県", "広島": "広島県", "山口": "山口県", "徳島": "徳島県", "香川": "香川県", "愛媛": "愛媛県",
    "高知": "高知県", "福岡": "福岡県", "佐賀": "佐賀県", "長崎": "長崎県", "熊本": "熊本県", "大分": "大分県",
    "宮崎": "宮崎県", "鹿児島": "鹿児島県", "沖縄": "沖縄県",
}


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
    amounts = [
        int(number.replace(",", "")) * (10000 if unit == "万円" else 1)
        for number, unit in YEN_RE.findall(t)
    ]
    if amounts:
        is_limit = bool(re.search(r"上限|最大|まで|以内|範囲|以上.*(?:以内|以下|未満)", t))
        amount = max(amounts) if is_limit else amounts[0]
        return ("limit" if is_limit else "fixed"), amount
    if re.search(r"規定|一部|遠方|条件|相談", t):
        return "conditional", None
    if "支給あり" in t or "交通費" in t:
        return "unknown", None
    return "unknown", None


def has_transport_support(item: dict) -> bool:
    """交通費ありの母集団だけを画面と金額分析の対象にする。"""
    if item.get("transport_available") is False:
        return False
    if item.get("transport_type") == "none":
        return False
    return bool(item.get("transport_original") and item.get("transport_original") != NO_TRANSPORT_TEXT)


def amount_analysis_status(item: dict) -> str:
    if not has_transport_support(item):
        return "no_transport"
    if item.get("transport_type") == "unlimited":
        return "unlimited"
    if isinstance(item.get("transport_amount"), int) and item["transport_amount"] > 0:
        return "amount_known"
    return "amount_unknown"


def is_science_only(item: dict) -> bool:
    """参加条件が理系限定の募集だけを除外する。文理不問は残す。"""
    text = normalize_text(item.get("eligibility_text", ""))
    if not text or text == "記載なし":
        return False
    if re.search(r"文理不問|文理問わず|文理問いません|全学部|全学科|学部学科不問|学部不問|文系", text):
        return False
    return bool(re.search(r"理系|理工|工学部|工学系|理学部|土木|建築|機械|電気|電子|情報|化学|物理|数学|農学|薬学|技術系", text))


def is_kanto_only(item: dict) -> bool:
    """開催地が関東だけの募集を、収集後の分析母集団から外す。"""
    physical_locations = [location for location in item.get("locations", []) if location in PREFS]
    return bool(physical_locations) and all(location in KANTO_PREFS for location in physical_locations)


def extract_labeled_text(soup: BeautifulSoup, labels: list[str], width: int = 5) -> str:
    lines = [x.strip() for x in soup.get_text("\n", strip=True).splitlines() if x.strip()]
    for idx, line in enumerate(lines):
        if any(line == label or line.startswith(label) for label in labels):
            return " ".join(lines[idx : idx + width])[:700]
    return ""


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_table_fields(soup: BeautifulSoup) -> dict[str, str]:
    """マイナビ詳細ページの dataTable02 を heading セル単位で読む。"""
    fields: dict[str, str] = {}
    for table in soup.select("table.dataTable02"):
        for row in table.find_all("tr"):
            heading = row.find("td", class_=lambda c: c and "heading" in c.split())
            if not heading:
                continue
            label = normalize_text(heading.get_text(" ", strip=True))
            values = []
            for cell in row.find_all("td", recursive=False):
                if cell is heading:
                    continue
                values.append(cell.get_text(" ", strip=True))
            value = normalize_text(" ".join(values))
            if label and value and label not in fields:
                fields[label] = value
    return fields


def parse_locations(text: str) -> list[str]:
    found: list[str] = []
    for pref in PREFS:
        if pref in text and pref not in found:
            found.append(pref)
    for short, pref in PREF_ALIASES.items():
        if re.search(rf"(?<![一-龥ぁ-んァ-ン]){re.escape(short)}(?![一-龥ぁ-んァ-ン])", text) and pref not in found:
            found.append(pref)
    if "WEB" in text and "WEB" not in found:
        found.append("WEB")
    return found


def extract_industries(soup: BeautifulSoup) -> list[str]:
    industries: list[str] = []
    for category in soup.select("div.category"):
        heading = category.find(["h2", "h3"])
        if not heading or normalize_text(heading.get_text(" ", strip=True)) != "業種":
            continue
        for node in category.select("li span, li a"):
            value = normalize_text(node.get_text(" ", strip=True))
            if value and value not in industries:
                industries.append(value)
        if industries:
            return industries
    return industries


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


def extract_detail_links(base_url: str, html: str) -> list[tuple[str, str]]:
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
            output.append((canonical_url(href), normalize_text(a.get_text(" ", strip=True))))
    return list(dict.fromkeys(output))


def form_data(form) -> list[tuple[str, str]]:
    data: list[tuple[str, str]] = []
    for control in form.find_all(["input", "select", "textarea"]):
        name = control.get("name")
        if not name or control.has_attr("disabled"):
            continue
        tag = control.name
        typ = (control.get("type") or "").lower()
        if tag == "input":
            if typ in {"submit", "button", "image", "file", "reset"}:
                continue
            if typ in {"checkbox", "radio"} and not control.has_attr("checked"):
                continue
            data.append((name, control.get("value", "")))
        elif tag == "select":
            options = control.find_all("option")
            selected = [opt for opt in options if opt.has_attr("selected")]
            for opt in selected or options[:1]:
                data.append((name, opt.get("value", opt.get_text(" ", strip=True))))
        elif tag == "textarea":
            data.append((name, control.get_text()))
    return data


def with_form_value(data: list[tuple[str, str]], name: str, value: str) -> list[tuple[str, str]]:
    changed = False
    output = []
    for key, old_value in data:
        if key == name:
            output.append((key, value))
            changed = True
        else:
            output.append((key, old_value))
    if not changed:
        output.append((name, value))
    return output


def find_next_page_request(base_url: str, html: str) -> tuple[str, list[tuple[str, str]]] | None:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        aria = a.get("aria-label", "")
        if "次の30社" in text or text in {"次へ", "次のページ"} or "次" in aria:
            onclick = a.get("onclick") or a.get("onClick") or ""
            m = re.search(r"toNextPage\('([^']+)'\s*,\s*'([^']+)'\)", onclick)
            if not m:
                continue
            form = soup.find("form", id="searchCorpListByIsForm")
            if not form:
                continue
            action = urljoin(base_url, m.group(1))
            data = with_form_value(form_data(form), "pageNo", m.group(2))
            return action, data
    return None


def parse_detail(url: str, html: str, old_item: dict | None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    company_h1 = soup.find("h1")
    company = normalize_text(company_h1.get_text(" ", strip=True)) if company_h1 else ""
    if not company:
        company = re.sub(r"のインターンシップ.*$", "", title).strip() or "企業名不明"
    course_node = soup.find(id="courseName")
    if not course_node:
        head = soup.select_one("div.dtHead2 h2.txt")
        course_node = head or soup.find("h2")
    course = normalize_text(course_node.get_text(" ", strip=True)) if course_node else title
    fields = extract_table_fields(soup)
    transport = fields.get("交通費") or extract_labeled_text(soup, ["交通費", "交通費支給"])
    lodging = fields.get("宿泊費") or extract_labeled_text(soup, ["宿泊費", "宿泊費支給"])
    schedule = fields.get("開催時期と実施日数") or fields.get("開催時期") or extract_labeled_text(soup, ["開催時期", "開催日", "日程"], width=8)
    deadline = fields.get("応募締切日") or fields.get("応募締切") or extract_labeled_text(soup, ["応募締切", "締切"], width=4)
    eligibility = fields.get("参加条件") or fields.get("応募資格") or fields.get("募集対象") or ""
    region = fields.get("開催地域", "")
    alltext = soup.get_text(" ", strip=True)
    status = detect_status(alltext)
    locations = parse_locations(region or alltext)
    industries = extract_industries(soup)
    transport_type, amount = classify(transport)
    key = course_key(url)
    now = datetime.now(JST).isoformat(timespec="seconds")
    return {
        "id": key,
        "company": company,
        "course": course[:220],
        "industries": industries,
        "locations": locations[:12],
        "event_dates": parse_dates(schedule),
        "schedule_text": schedule or "開催日の明示なし",
        "deadline_text": deadline or "記載なし",
        "deadline": parse_deadline(deadline),
        "transport_type": transport_type,
        "transport_amount": amount,
        "transport_available": bool(transport and transport_type != "none"),
        "transport_original": transport or NO_TRANSPORT_TEXT,
        "amount_analysis_status": "pending",
        "lodging_provided": bool(lodging and not re.search(r"なし|自己負担|各自負担", lodging)),
        "lodging_text": lodging or "記載なし",
        "eligibility_text": eligibility or "記載なし",
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


def submit_form(session: requests.Session, url: str, data: list[tuple[str, str]]) -> str:
    headers = dict(HEADERS)
    headers["Referer"] = "https://job.mynavi.jp/28/pc/search/is_it1.html"
    response = session.post(url, headers=headers, data=data, timeout=30)
    response.raise_for_status()
    return response.text


def discover_courses(
    session: requests.Session,
    catalog: dict,
    crawl_state: dict,
    now: datetime,
    list_limit: int | None,
    request_interval: float,
) -> tuple[int, int]:
    discovered: list[str] = []
    hints: dict[str, str] = {}
    pages_left = list_limit
    for seed in SEARCH_SEEDS:
        page_url = seed
        html: str | None = None
        while page_url and (pages_left is None or pages_left > 0):
            try:
                if html is None:
                    html = fetch(session, page_url)
                for url, hint in extract_detail_links(page_url, html):
                    discovered.append(url)
                    if hint:
                        hints[url] = hint
                next_request = find_next_page_request(page_url, html)
                crawl_state.setdefault("next_pages", {})[seed] = bool(next_request)
                if next_request:
                    next_url, data = next_request
                    html = submit_form(session, next_url, data)
                    page_url = next_url
                else:
                    html = None
                    page_url = None
                if pages_left is not None:
                    pages_left -= 1
                time.sleep(request_interval)
            except Exception as exc:
                print("list failed", page_url, exc)
                crawl_state.setdefault("next_pages", {})[seed] = True
                break
        if pages_left is not None and pages_left <= 0:
            break

    new_count = 0
    for url in dict.fromkeys(discovered):
        key = course_key(url)
        if key not in catalog.setdefault("urls", {}):
            new_count += 1
        record = catalog["urls"].get(key, {})
        record.update({"url": canonical_url(url), "last_discovered": now.isoformat(timespec="seconds")})
        if hints.get(url):
            record["course_title_hint"] = hints[url]
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
        elif mode == "rebuild":
            include = True
            priority = 0
        if include:
            candidates.append((priority, last, key, url))
    candidates.sort()
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["discover", "refresh", "urgent", "cleanup", "all", "rebuild"], default="all")
    parser.add_argument("--limit", type=int, default=MAX_DETAIL_PAGES_PER_RUN, help="詳細取得件数。0以下で無制限。")
    parser.add_argument("--list-pages", type=int, default=MAX_LIST_PAGES_PER_RUN, help="一覧巡回ページ数。0以下で次ページが尽きるまで。")
    parser.add_argument("--request-interval", type=float, default=REQUEST_INTERVAL_SECONDS)
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
    list_limit = None if args.list_pages <= 0 else args.list_pages
    if args.mode in {"discover", "all"}:
        discovered_count, new_count = discover_courses(session, catalog, crawl_state, now, list_limit, args.request_interval)

    items_by_id = dict(old_by_id)
    candidates = select_candidates(args.mode, catalog, items_by_id, now)
    checked = 0
    detail_candidates = candidates if args.limit <= 0 else candidates[:args.limit]
    for _, _, key, url in detail_candidates:
        try:
            html = fetch(session, url)
            item = parse_detail(url, html, old_by_id.get(key))
            item["amount_analysis_status"] = amount_analysis_status(item)
            items_by_id[key] = item
            catalog["urls"][key]["last_checked"] = item["last_checked"]
            catalog["urls"][key]["status"] = item["status"]
            catalog["urls"][key]["transport_available"] = has_transport_support(item)
            catalog["urls"][key]["science_only"] = is_science_only(item)
            catalog["urls"][key]["kanto_only"] = is_kanto_only(item)
            checked += 1
            time.sleep(args.request_interval)
        except Exception as exc:
            print("detail failed", url, exc)

    # 終了整理では終了済みを削除せず履歴として保持し、画面側で非表示にできる状態にする。
    collected_items = dedupe_items(list(items_by_id.values()))
    transport_items = [item for item in collected_items if has_transport_support(item)]
    non_kanto_transport_items = [item for item in transport_items if not is_kanto_only(item)]
    items = [item for item in non_kanto_transport_items if not is_science_only(item)]
    for item in items:
        item["amount_analysis_status"] = amount_analysis_status(item)
        item["science_only"] = False
        item["kanto_only"] = False
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
            "collected_courses": len(collected_items),
            "displayed_courses": len(items),
            "transport_supported_courses": len(transport_items),
            "excluded_kanto_only_courses": len(transport_items) - len(non_kanto_transport_items),
            "excluded_science_only_courses": len(non_kanto_transport_items) - len(items),
            "amount_known_courses": sum(amount_analysis_status(x) == "amount_known" for x in items),
            "amount_unlimited_courses": sum(amount_analysis_status(x) == "unlimited" for x in items),
            "amount_unknown_courses": sum(amount_analysis_status(x) == "amount_unknown" for x in items),
            "excluded_no_transport_courses": len(collected_items) - len(transport_items),
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
