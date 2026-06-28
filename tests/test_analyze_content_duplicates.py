import csv
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_content_duplicates import analyze_duplicates


class AnalyzeContentDuplicatesTests(unittest.TestCase):
    def test_flags_same_content_with_different_document_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            manifest_dir = batch / "01_source_manifest"
            clean_dir = batch / "03_clean_text"
            manifest_dir.mkdir(parents=True)
            clean_dir.mkdir()

            fields = ["document_id", "file_name", "inclusion_status"]
            with (manifest_dir / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(
                    [
                        {"document_id": "DOC-A", "file_name": "指南.pdf", "inclusion_status": "included"},
                        {"document_id": "DOC-B", "file_name": "指南.docx", "inclusion_status": "included"},
                        {"document_id": "DOC-C", "file_name": "其他.pdf", "inclusion_status": "included"},
                    ]
                )

            repeated = "肥厚型心肌病诊断治疗随访建议" * 100
            (clean_dir / "DOC-A.clean.txt").write_text(
                "<<<DOCUMENT document_id=DOC-A>>>\n" + repeated, encoding="utf-8-sig"
            )
            (clean_dir / "DOC-B.clean.txt").write_text(
                "<<<DOCUMENT document_id=DOC-B>>>\n" + repeated, encoding="utf-8-sig"
            )
            (clean_dir / "DOC-C.clean.txt").write_text(
                "完全不同的感染性心内膜炎内容" * 100, encoding="utf-8-sig"
            )

            pairs = analyze_duplicates(batch, threshold=0.8)
            self.assertEqual(len(pairs), 1)
            self.assertEqual({pairs[0]["document_id_a"], pairs[0]["document_id_b"]}, {"DOC-A", "DOC-B"})
            self.assertEqual(pairs[0]["suggested_action"], "REVIEW_AS_SAME_SOURCE")


if __name__ == "__main__":
    unittest.main()
