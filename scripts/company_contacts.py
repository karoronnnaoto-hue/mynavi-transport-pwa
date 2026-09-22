from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
CONTACT_DB = ROOT / "data/company_contacts.json"
CONTACT_CSV = ROOT / "docs/data/company_contacts.csv"

EMAIL_RE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?:TEL|電話|本社電話番号)?\s*[:：]?\s*((?:0\d{1,4}[-ー−]\d{1,4}[-ー−]\d{3,4})|(?:0\d{9,10}))"
)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def corp_id_from_url(url: str) -> str:
    query = {key.lower(): value for key, value in parse_qs(urlparse(url).query).items()}
    return (query.get("corpid") or [""])[0]


def _best_contact_fragment(text: str) -> str:
    text = normalize_text(text)
    markers = ["問合せ先", "問い合わせ先", "お問合せ先"]
    starts = [text.find(marker) for marker in markers if text.find(marker) >= 0]
    if starts:
        text = text[min(starts) :]
    stops = [
        "の実施する他のコース",
        "この企業のコース情報一覧へ戻る",
        "会社概要 インターンシップ",
        "画像からAIがピックアップ",
    ]
    ends = [text.find(stop) for stop in stops if text.find(stop) > 0]
    if ends:
        text = text[: min(ends)]
    return text[:1200]


def _contact_text(soup: BeautifulSoup) -> str:
    chunks: list[str] = []
    for marker in soup.find_all(
        string=lambda value: value
        and ("問合せ先" in value or "問い合わせ先" in value or "お問合せ" in value)
    ):
        parent = marker.parent
        for node in [
            parent,
            parent.find_next_sibling() if parent else None,
            parent.parent if parent else None,
            parent.parent.parent if parent and parent.parent else None,
        ]:
            if not node:
                continue
            value = _best_contact_fragment(node.get_text(" ", strip=True))
            if value and value not in chunks:
                chunks.append(value)

    full_text = normalize_text(soup.get_text(" ", strip=True))
    for match in re.finditer(r"(?:問合せ先|問い合わせ先|お問合せ先)", full_text):
        value = _best_contact_fragment(full_text[match.start() : match.end() + 500])
        if value and value not in chunks:
            chunks.append(value)
    return " / ".join(chunks)


def extract_contact_details(soup: BeautifulSoup) -> dict[str, list[str]]:
    contact_text = _contact_text(soup)
    search_text = contact_text or normalize_text(soup.get_text(" ", strip=True))
    emails = sorted(set(EMAIL_RE.findall(search_text)))
    phones = sorted(
        set(
            match.group(1).replace("ー", "-").replace("−", "-")
            for match in PHONE_RE.finditer(search_text)
        )
    )
    homepages = []
    for url in re.findall(r"https?://[^\s<>'\"]+", contact_text):
        url = url.rstrip("。、),）]")
        if "job.mynavi.jp" not in url and url not in homepages:
            homepages.append(url)
    return {"emails": emails, "phones": phones, "homepages": homepages}


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def seed_contacts_from_csv(path: Path, generated_at: str) -> dict:
    companies: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            corp_id = row.get("corp_id", "").strip()
            if not corp_id:
                continue
            companies[corp_id] = {
                "company": row.get("company", "").strip(),
                "emails": [value for value in row.get("emails", "").split("; ") if value],
                "phones": [value for value in row.get("phones", "").split("; ") if value],
                "homepages": [value for value in row.get("homepages", "").split("; ") if value],
                "source_urls": [value for value in row.get("source_urls", "").split("; ") if value][:10],
                "last_checked": generated_at,
            }
    return {"generated_at": generated_at, "companies": companies}


def merge_item_contacts(store: dict, items: list[dict], generated_at: str) -> dict:
    companies = store.setdefault("companies", {})
    for item in items:
        checked_at = item.get("contact_checked_at")
        if not checked_at:
            continue
        corp_id = corp_id_from_url(item.get("url", ""))
        if not corp_id:
            continue
        record = companies.setdefault(
            corp_id,
            {"company": item.get("company", ""), "emails": [], "phones": [], "homepages": [], "source_urls": []},
        )
        record["company"] = item.get("company") or record.get("company", "")
        for field in ["emails", "phones", "homepages"]:
            current = set(record.get(field, []))
            current.update(item.get(f"contact_{field}", []))
            record[field] = sorted(current)
        urls = list(dict.fromkeys([*record.get("source_urls", []), item.get("url", "")]))
        record["source_urls"] = [url for url in urls if url][:10]
        record["last_checked"] = max(record.get("last_checked", ""), checked_at)
    store["generated_at"] = generated_at
    return store


def _transport_label(item: dict) -> tuple[str, str]:
    kind = item.get("transport_type")
    amount = item.get("transport_amount")
    if kind == "unlimited":
        return "full", "全額"
    if kind in {"fixed", "limit"}:
        if isinstance(amount, int) and amount > 0:
            return "partial", f"一部（{amount:,}円）"
        return "partial", "一部"
    if kind == "conditional":
        return "conditional", "条件付き（規定等）"
    return "unknown", "金額不明"


def _percentage(count: int, total: int) -> str:
    return f"{count / total:.1%}" if total else "0.0%"


def _unique_join(values: list[str], separator: str = " / ") -> str:
    return separator.join(dict.fromkeys(value for value in values if value))


def _transport_conditions(item: dict) -> dict[str, str]:
    text = normalize_text(item.get("transport_original", ""))
    if not text:
        return {
            "unit": "",
            "targets": "",
            "modes": "",
            "settlement": "",
            "subsidy": "",
            "pickup": "",
            "original": "",
        }

    normalized = text.translate(str.maketrans("０１２３４５６７８９，", "0123456789,"))
    units: list[str] = []
    if re.search(r"1日|一日|日あたり|日当たり|日額|/日", normalized):
        units.append("1日あたり")
    if "往復" in normalized:
        units.append("往復")
    if "片道" in normalized:
        units.append("片道")
    if re.search(r"1回|一回|回あたり|回当たり", normalized):
        units.append("1回あたり")

    targets: list[str] = []
    target_patterns = [
        (r"現住所", "現住所に応じる"),
        (r"遠方", "遠方者"),
        (r"県外", "県外者"),
        (r"県内", "県内者"),
        (r"市外", "市外者"),
        (r"市内", "市内者"),
        (r"地域|エリア", "地域別"),
        (r"当社規定|弊社規定|会社規定|規定に基づ", "会社規定"),
        (r"要相談|個別に.*相談|応相談", "個別相談"),
    ]
    for pattern, label in target_patterns:
        if re.search(pattern, normalized):
            targets.append(label)

    modes: list[str] = []
    mode_patterns = [
        (r"公共交通機関のみ", "公共交通機関のみ"),
        (r"公共交通機関", "公共交通機関"),
        (r"新幹線", "新幹線"),
        (r"電車|鉄道|切符", "鉄道"),
        (r"飛行機|航空", "飛行機"),
        (r"高速バス|バス", "バス"),
        (r"高速道路|高速代", "高速道路"),
        (r"自家用車|自動車|車で|車利用|ガソリン", "自家用車"),
        (r"タクシー", "タクシー"),
    ]
    for pattern, label in mode_patterns:
        if re.search(pattern, normalized) and label not in modes:
            if label == "公共交通機関" and "公共交通機関のみ" in modes:
                continue
            modes.append(label)

    settlement: list[str] = []
    settlement_patterns = [
        (r"実費", "実費精算"),
        (r"領収書|領収証", "領収書必須"),
        (r"印鑑", "印鑑必須"),
        (r"事前申請|事前に申請|事前の申請", "事前申請"),
        (r"ご自身で.*申請|自身で.*申請|本人.*申請", "本人申請"),
        (r"後日.*精算|後払い", "後日精算"),
    ]
    for pattern, label in settlement_patterns:
        if re.search(pattern, normalized):
            settlement.append(label)

    subsidy = ""
    if "ジョブカフェしまね" in normalized:
        subsidy = "ジョブカフェしまね助成金"
    elif re.search(r"助成金|補助金", normalized):
        subsidy = "外部助成・補助制度あり"

    pickup = ""
    if re.search(r"送迎あり|送迎を.*(?:実施|行)", normalized):
        pickup = "あり"
    elif "送迎" in normalized:
        pickup = "記載あり（原文参照）"

    return {
        "unit": _unique_join(units, "; "),
        "targets": _unique_join(targets, "; "),
        "modes": _unique_join(modes, "; "),
        "settlement": _unique_join(settlement, "; "),
        "subsidy": subsidy,
        "pickup": pickup,
        "original": text,
    }


def _transport_amount_value(items: list[dict]) -> str | int:
    if any(item.get("transport_type") == "unlimited" for item in items):
        return "全額"

    amounts: list[int] = []
    for item in items:
        amount = item.get("transport_amount")
        if isinstance(amount, int) and amount > 0:
            amounts.append(amount)
        text = normalize_text(item.get("transport_original", "")).translate(
            str.maketrans("０１２３４５６７８９，", "0123456789,")
        )
        for number, unit in re.findall(r"([0-9,]+)\s*(円|万円)", text):
            value = int(number.replace(",", "")) * (10000 if unit == "万円" else 1)
            if value > 0:
                amounts.append(value)
    return max(amounts) if amounts else ""


def _prefectures(items: list[dict]) -> str:
    values = []
    for item in items:
        for location in item.get("locations", []):
            if location and location != "WEB" and location.endswith(("都", "道", "府", "県")):
                values.append(location)
    return _unique_join(values, "; ")


def write_contacts_csv(active_items: list[dict], store: dict, path: Path = CONTACT_CSV) -> None:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in active_items:
        corp_id = corp_id_from_url(item.get("url", ""))
        if corp_id:
            grouped[corp_id].append(item)

    headers = [
        "企業名",
        "メールアドレス",
        "電話番号",
        "ホームページ",
        "交通費区分",
        "交通費金額",
        "開催都道府県",
        "支給単位",
        "対象者・地域条件",
        "対象交通手段",
        "精算・申請条件",
        "外部助成制度",
        "送迎",
        "交通費原文",
        "全額割合",
        "一部割合",
        "条件付き割合",
        "金額不明割合",
        "掲載コース数",
        "マイナビ企業ID",
        "連絡先最終確認",
        "参照URL",
    ]
    rows = []
    companies = store.get("companies", {})
    for corp_id, items in grouped.items():
        contact = companies.get(corp_id, {})
        broad_counts: Counter[str] = Counter()
        detail_counts: Counter[str] = Counter()
        conditions = defaultdict(list)
        for item in items:
            broad, detail = _transport_label(item)
            broad_counts[broad] += 1
            detail_counts[detail] += 1
            for field, value in _transport_conditions(item).items():
                if value:
                    conditions[field].append(value)
        total = len(items)
        breakdown = " / ".join(
            f"{label} {count}件"
            for label, count in sorted(
                detail_counts.items(),
                key=lambda pair: (
                    {"全額": 0, "条件付き（規定等）": 2, "金額不明": 3}.get(pair[0], 1),
                    pair[0],
                ),
            )
        )
        source_url = (contact.get("source_urls") or [items[0].get("url", "")])[0]
        rows.append(
            {
                "企業名": contact.get("company") or items[0].get("company", ""),
                "メールアドレス": "; ".join(contact.get("emails", [])),
                "電話番号": "; ".join(contact.get("phones", [])),
                "ホームページ": "; ".join(contact.get("homepages", [])),
                "交通費区分": breakdown,
                "交通費金額": _transport_amount_value(items),
                "開催都道府県": _prefectures(items),
                "支給単位": _unique_join(conditions["unit"]),
                "対象者・地域条件": _unique_join(conditions["targets"]),
                "対象交通手段": _unique_join(conditions["modes"]),
                "精算・申請条件": _unique_join(conditions["settlement"]),
                "外部助成制度": _unique_join(conditions["subsidy"]),
                "送迎": _unique_join(conditions["pickup"]),
                "交通費原文": _unique_join(conditions["original"], " | "),
                "全額割合": _percentage(broad_counts["full"], total),
                "一部割合": _percentage(broad_counts["partial"], total),
                "条件付き割合": _percentage(broad_counts["conditional"], total),
                "金額不明割合": _percentage(broad_counts["unknown"], total),
                "掲載コース数": total,
                "マイナビ企業ID": corp_id,
                "連絡先最終確認": contact.get("last_checked", ""),
                "参照URL": source_url,
            }
        )

    rows.sort(key=lambda row: (not row["メールアドレス"], row["企業名"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def update_contact_artifacts(all_items: list[dict], active_items: list[dict], generated_at: str) -> None:
    store = _load_json(CONTACT_DB, {"generated_at": generated_at, "companies": {}})
    store = merge_item_contacts(store, all_items, generated_at)
    _save_json(CONTACT_DB, store)
    write_contacts_csv(active_items, store)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-csv", type=Path)
    parser.add_argument("--active-json", type=Path, default=ROOT / "docs/data/jobs.json")
    parser.add_argument("--generated-at", default="")
    args = parser.parse_args()

    active_payload = _load_json(args.active_json, {"items": []})
    generated_at = args.generated_at or active_payload.get("generated_at", "")
    if args.seed_csv:
        store = seed_contacts_from_csv(args.seed_csv, generated_at)
        _save_json(CONTACT_DB, store)
    else:
        store = _load_json(CONTACT_DB, {"generated_at": generated_at, "companies": {}})
    write_contacts_csv(active_payload.get("items", []), store)
    print(f"companies={len(store.get('companies', {}))} csv={CONTACT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
