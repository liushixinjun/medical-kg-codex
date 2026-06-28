import csv
import json
import tempfile
import unittest
from pathlib import Path

import fitz

from scripts.parse_pdf_batch import parse_included_pdfs


class ParsePdfBatchTests(unittest.TestCase):
    def test_accounts_for_every_page_and_writes_clean_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch"
            manifest_dir = batch / "01_source_manifest"
            manifest_dir.mkdir(parents=True)
            pdf_path = root / "中国心肌病指南.pdf"

            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Cardiomyopathy diagnosis and treatment recommendation")
            document.new_page()
            document.save(pdf_path)
            document.close()

            fields = [
                "document_id",
                "file_name",
                "full_path",
                "extension",
                "inclusion_status",
                "source_type",
            ]
            with (manifest_dir / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "document_id": "DOC-TEST",
                        "file_name": pdf_path.name,
                        "full_path": str(pdf_path),
                        "extension": ".pdf",
                        "inclusion_status": "included",
                        "source_type": "guideline",
                    }
                )

            summary = parse_included_pdfs(batch)
            self.assertEqual(summary["document_count"], 1)
            self.assertEqual(summary["page_count"], 2)
            self.assertEqual(summary["page_accounting_rate"], 1.0)

            audit_path = batch / "02_page_audit" / "page_audit.jsonl"
            rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8-sig").splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["status"], "parsed")
            self.assertEqual(rows[1]["page_class"], "blank")

            clean_text = (batch / "03_clean_text" / "DOC-TEST.clean.txt").read_text(
                encoding="utf-8-sig"
            )
            self.assertIn("<<<DOCUMENT document_id=DOC-TEST>>>", clean_text)
            self.assertIn("<<<PAGE page=1", clean_text)
            self.assertIn("Cardiomyopathy", clean_text)

            renders = list((batch / "02_page_audit" / "render_samples" / "DOC-TEST").glob("*.png"))
            self.assertGreaterEqual(len(renders), 1)

    def test_does_not_request_ocr_for_cover_and_section_divider_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch"
            manifest_dir = batch / "01_source_manifest"
            manifest_dir.mkdir(parents=True)
            pdf_path = root / "内科学.pdf"

            pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), False)
            pixmap.clear_with(0xFFFFFF)
            image_bytes = pixmap.tobytes("png")

            document = fitz.open()
            cover = document.new_page()
            cover.insert_image(fitz.Rect(0, 0, 100, 100), stream=image_bytes)
            divider = document.new_page()
            divider.insert_text((72, 72), "PART I\nCARDIOVASCULAR SYSTEM")
            back_cover = document.new_page()
            back_cover.insert_image(fitz.Rect(0, 0, 100, 100), stream=image_bytes)
            document.save(pdf_path)
            document.close()

            fields = [
                "document_id",
                "file_name",
                "full_path",
                "extension",
                "inclusion_status",
                "source_type",
            ]
            with (manifest_dir / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "document_id": "DOC-BOOK",
                        "file_name": pdf_path.name,
                        "full_path": str(pdf_path),
                        "extension": ".pdf",
                        "inclusion_status": "included",
                        "source_type": "authoritative_textbook",
                    }
                )

            summary = parse_included_pdfs(batch)
            self.assertEqual(summary["ocr_required_page_count"], 0)
            rows = [
                json.loads(line)
                for line in (batch / "02_page_audit" / "page_audit.jsonl")
                .read_text(encoding="utf-8-sig")
                .splitlines()
            ]
            self.assertEqual(rows[0]["page_class"], "cover")
            self.assertEqual(rows[1]["page_class"], "section_divider")
            self.assertEqual(rows[2]["page_class"], "cover")


if __name__ == "__main__":
    unittest.main()
