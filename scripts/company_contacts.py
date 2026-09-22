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
    return "other", "その他"


def _percentage(count: int, total: int) -> str:
    return f"{count / total:.1%}" if total else "0.0%"


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
        "全額割合",
        "一部割合",
        "その他割合",
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
        for item in items:
            broad, detail = _transport_label(item)
            broad_counts[broad] += 1
            detail_counts[detail] += 1
        total = len(items)
        breakdown = " / ".join(
            f"{label} {count}件"
            for label, count in sorted(
                detail_counts.items(),
                key=lambda pair: ({"全額": 0, "その他": 2}.get(pair[0], 1), pair[0]),
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
                "全額割合": _percentage(broad_counts["full"], total),
                "一部割合": _percentage(broad_counts["partial"], total),
                "その他割合": _percentage(broad_counts["other"], total),
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
