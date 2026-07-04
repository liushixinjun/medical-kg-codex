import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.ocr_pdf_pages import apply_ocr_text_to_batch


class OcrPdfPagesTests(unittest.TestCase):
    def test_applies_ocr_text_to_unreadable_page_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            (batch / "02_page_audit").mkdir(parents=True)
            (batch / "03_clean_text").mkdir()
            page_rows = [
                {
                    "batch_id": "BATCH-HF",
                    "document_id": "DOC-OCR",
                    "page_number": "1",
                    "page_class": "unreadable",
                    "parse_method": "fitz",
                    "char_count": "4",
                    "engine_b_char_count": "4",
                    "chinese_ratio": "1.0",
                    "replacement_char_count": "0",
                    "mojibake_score": "0",
                    "image_count": "1",
                    "ocr_used": "False",
                    "table_detected": "False",
                    "clinical_keyword_hits": "0",
                    "status": "ocr_required",
                    "failure_reason": "IMAGE_ONLY_OR_LOW_TEXT",
                }
            ]
            fields = tuple(page_rows[0].keys())
            with (batch / "02_page_audit" / "page_audit.jsonl").open("w", encoding="utf-8-sig") as handle:
                for row in page_rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            with (batch / "03_clean_text" / "segment_index.jsonl").open("w", encoding="utf-8-sig") as handle:
                handle.write(json.dumps({
                    "document_id": "DOC-OCR",
                    "segment_id": "SEG-DOC-OCR-1-PAGE-0-4",
                    "page_number": 1,
                    "page_class": "unreadable",
                    "start_offset": 0,
                    "end_offset": 4,
                    "content_hash": "OLD",
                    "status": "ocr_required",
                }, ensure_ascii=False) + "\n")
            (batch / "03_clean_text" / "DOC-OCR.clean.txt").write_text(
                "<<<DOCUMENT document_id=DOC-OCR>>>\n"
                "<<<PAGE page=1 class=unreadable>>>\n"
                "<<<SECTION section_id=SEG-DOC-OCR-1-PAGE-0-4 title=PAGE_1>>>\n"
                "万方数据\n",
                encoding="utf-8-sig",
            )
            ocr_text = {("DOC-OCR", 1): "心力衰竭患者需要规范诊断和治疗。"}

            summary = apply_ocr_text_to_batch(batch, ocr_text)

            self.assertEqual(summary["updated_page_count"], 1)
            clean = (batch / "03_clean_text" / "DOC-OCR.clean.txt").read_text(encoding="utf-8-sig")
            self.assertIn("class=body", clean)
            self.assertIn("心力衰竭患者需要规范诊断和治疗。", clean)
            updated = [json.loads(line) for line in (batch / "02_page_audit" / "page_audit.jsonl").read_text(encoding="utf-8-sig").splitlines()][0]
            self.assertEqual(updated["status"], "parsed")
            self.assertTrue(updated["ocr_used"])


if __name__ == "__main__":
    unittest.main()
