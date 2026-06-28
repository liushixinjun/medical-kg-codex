import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_medical_kg_batch import prepare_batch


class PrepareMedicalKgBatchTests(unittest.TestCase):
    def test_builds_scope_manifest_and_exact_duplicate_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guide = root / "指南"
            books = root / "教材"
            output = root / "输出"
            (guide / "心肌病").mkdir(parents=True)
            (guide / "心律失常").mkdir(parents=True)
            books.mkdir()
            output.mkdir()

            payload = b"same guideline bytes"
            (guide / "心肌病" / "中国心肌病指南.pdf").write_bytes(payload)
            (guide / "心肌病" / "中国心肌病指南-副本.pdf").write_bytes(payload)
            (guide / "心律失常" / "房颤指南.pdf").write_bytes(b"other")
            (guide / "心肌病" / "病理图片.jpg").write_bytes(b"image")
            (books / "内科学第10版.pdf").write_bytes(b"textbook")

            batch_dir = prepare_batch(
                specialty="心血管内科",
                scope_type="category",
                scope_target="心肌病",
                guide_root=guide,
                textbook_root=books,
                output_root=output,
                batch_id="BATCH-TEST-001",
            )

            config = json.loads(
                (batch_dir / "00_scope_and_config" / "batch_config.json").read_text(
                    encoding="utf-8-sig"
                )
            )
            self.assertEqual(config["specialty"], "心血管内科")
            self.assertEqual(config["scope_target"], "心肌病")

            with (batch_dir / "01_source_manifest" / "source_documents_manifest.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 5)
            duplicate_rows = [row for row in rows if row["keep_or_duplicate"] == "duplicate"]
            self.assertEqual(len(duplicate_rows), 1)
            self.assertEqual(duplicate_rows[0]["duplicate_reason"], "EXACT_SHA256_DUPLICATE")

            image_row = next(row for row in rows if row["extension"] == ".jpg")
            self.assertEqual(image_row["inclusion_status"], "excluded")
            self.assertEqual(image_row["inclusion_reason"], "UNSUPPORTED_EXTENSION")

            unrelated = next(row for row in rows if row["file_name"] == "房颤指南.pdf")
            self.assertEqual(unrelated["inclusion_status"], "excluded")
            self.assertEqual(unrelated["inclusion_reason"], "OUT_OF_SCOPE_PATH_AND_NAME")

    def test_refuses_to_overwrite_existing_nonempty_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guide = root / "指南"
            books = root / "教材"
            output = root / "输出"
            guide.mkdir()
            books.mkdir()
            existing = output / "BATCH-TEST-001"
            existing.mkdir(parents=True)
            (existing / "existing.txt").write_text("keep", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                prepare_batch(
                    specialty="心血管内科",
                    scope_type="category",
                    scope_target="心肌病",
                    guide_root=guide,
                    textbook_root=books,
                    output_root=output,
                    batch_id="BATCH-TEST-001",
                )

    def test_includes_coronary_heart_disease_scope_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guide = root / "指南"
            books = root / "教材"
            output = root / "输出"
            (guide / "CAD").mkdir(parents=True)
            (guide / "ACS").mkdir(parents=True)
            (guide / "其他").mkdir(parents=True)
            books.mkdir()
            output.mkdir()

            (guide / "CAD" / "中国慢性冠脉综合征指南.pdf").write_bytes(b"ccs")
            (guide / "ACS" / "STEMI NSTEMI 指南.pdf").write_bytes(b"acs")
            (guide / "其他" / "房颤指南.pdf").write_bytes(b"af")
            (books / "内科学第10版.pdf").write_bytes(b"textbook")

            batch_dir = prepare_batch(
                specialty="心血管内科",
                scope_type="category",
                scope_target="冠状动脉粥样硬化性心脏病",
                guide_root=guide,
                textbook_root=books,
                output_root=output,
                batch_id="BATCH-CAD-TEST",
            )

            config = json.loads(
                (batch_dir / "00_scope_and_config" / "batch_config.json").read_text(
                    encoding="utf-8-sig"
                )
            )
            self.assertEqual(config["skill_version"], "V1.4")

            with (batch_dir / "01_source_manifest" / "source_documents_manifest.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

            included_names = {
                row["file_name"]
                for row in rows
                if row["inclusion_status"] == "included"
            }
            self.assertIn("中国慢性冠脉综合征指南.pdf", included_names)
            self.assertIn("STEMI NSTEMI 指南.pdf", included_names)
            self.assertIn("内科学第10版.pdf", included_names)
            unrelated = next(row for row in rows if row["file_name"] == "房颤指南.pdf")
            self.assertEqual(unrelated["inclusion_reason"], "OUT_OF_SCOPE_PATH_AND_NAME")


if __name__ == "__main__":
    unittest.main()
