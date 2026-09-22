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
        self.assertEqual(rows[0]["交通費区分"], "全額 1件 / 一部（10,000円） 1件 / その他 1件")
        self.assertEqual(rows[0]["全額割合"], "33.3%")
        self.assertEqual(rows[0]["一部割合"], "33.3%")
        self.assertEqual(rows[0]["その他割合"], "33.3%")


if __name__ == "__main__":
    unittest.main()
