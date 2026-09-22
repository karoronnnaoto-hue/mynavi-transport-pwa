from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from company_contacts import extract_contact_details, write_contacts_csv


class CompanyContactsTest(unittest.TestCase):
    def test_extracts_public_contact_fields(self) -> None:
        soup = BeautifulSoup(
            "<h2>問合せ先</h2><p>採用担当 TEL：03-1234-5678 "
            "E-mail: recruit@example.jp https://example.jp/recruit</p>",
            "html.parser",
        )

        self.assertEqual(
            extract_contact_details(soup),
            {
                "emails": ["recruit@example.jp"],
                "phones": ["03-1234-5678"],
                "homepages": ["https://example.jp/recruit"],
            },
        )

    def test_writes_transport_breakdown_and_percentages(self) -> None:
        items = [
            {
                "id": "corp:1:course:a",
                "company": "Example",
                "url": "https://job.mynavi.jp/28/pc/corpinfo/displayInternship/index?corpId=1&optNo=a",
                "transport_type": "unlimited",
                "transport_amount": None,
            },
            {
                "id": "corp:1:course:b",
                "company": "Example",
                "url": "https://job.mynavi.jp/28/pc/corpinfo/displayInternship/index?corpId=1&optNo=b",
                "transport_type": "limit",
                "transport_amount": 10000,
            },
            {
                "id": "corp:1:course:c",
                "company": "Example",
                "url": "https://job.mynavi.jp/28/pc/corpinfo/displayInternship/index?corpId=1&optNo=c",
                "transport_type": "conditional",
                "transport_amount": None,
            },
            {
                "id": "corp:1:course:d",
                "company": "Example",
                "url": "https://job.mynavi.jp/28/pc/corpinfo/displayInternship/index?corpId=1&optNo=d",
                "transport_type": "unknown",
                "transport_amount": None,
            },
        ]
        store = {
            "companies": {
                "1": {
                    "company": "Example",
                    "emails": ["recruit@example.jp"],
                    "phones": [],
                    "homepages": [],
                    "source_urls": [],
                    "last_checked": "2026-09-22T12:00:00+09:00",
                }
            }
        }

        output = ROOT / "tests" / "_company_contacts_output.csv"
        try:
            write_contacts_csv(items, store, output)
            with output.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        finally:
            output.unlink(missing_ok=True)

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["交通費区分"],
            "全額 1件 / 一部（10,000円） 1件 / 条件付き（規定等） 1件 / 金額不明 1件",
        )
        self.assertEqual(rows[0]["全額割合"], "25.0%")
        self.assertEqual(rows[0]["一部割合"], "25.0%")
        self.assertEqual(rows[0]["条件付き割合"], "25.0%")
        self.assertEqual(rows[0]["金額不明割合"], "25.0%")

    def test_writes_detailed_transport_conditions(self) -> None:
        items = [
            {
                "company": "Example",
                "url": "https://job.mynavi.jp/28/pc/corpinfo/displayInternship/index?corpId=1&optNo=a",
                "transport_type": "limit",
                "transport_amount": 10000,
                "transport_original": "支給あり 公共交通機関のみ実費支給（1日あたり上限1万円）。領収書と印鑑が必要。県外の方は要相談。",
            },
            {
                "company": "Example",
                "url": "https://job.mynavi.jp/28/pc/corpinfo/displayInternship/index?corpId=1&optNo=b",
                "transport_type": "unknown",
                "transport_amount": None,
                "transport_original": "ジョブカフェしまねの助成金をご利用ください。駅から送迎あり。",
            },
        ]
        store = {"companies": {"1": {"company": "Example"}}}

        output = ROOT / "tests" / "_company_contacts_conditions.csv"
        try:
            write_contacts_csv(items, store, output)
            with output.open(encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
        finally:
            output.unlink(missing_ok=True)

        self.assertEqual(row["支給額詳細"], "上限 10,000円")
        self.assertEqual(row["支給単位"], "1日あたり")
        self.assertEqual(row["対象者・地域条件"], "県外者; 個別相談")
        self.assertEqual(row["対象交通手段"], "公共交通機関のみ")
        self.assertEqual(row["精算・申請条件"], "実費精算; 領収書必須; 印鑑必須")
        self.assertEqual(row["外部助成制度"], "ジョブカフェしまね助成金")
        self.assertEqual(row["送迎"], "あり")
        self.assertIn("公共交通機関のみ実費支給", row["交通費原文"])


if __name__ == "__main__":
    unittest.main()
