import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.apply_source_decisions import apply_decisions


class ApplySourceDecisionsTests(unittest.TestCase):
    def test_updates_manifest_without_deleting_source_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            manifest_dir = batch / "01_source_manifest"
            config_dir = batch / "00_scope_and_config"
            manifest_dir.mkdir(parents=True)
            config_dir.mkdir()
            clean_dir = batch / "03_clean_text"
            clean_dir.mkdir()

            fields = [
                "document_id",
                "inclusion_status",
                "inclusion_reason",
                "keep_or_duplicate",
                "duplicate_reason",
            ]
            with (manifest_dir / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(
                    [
                        {"document_id": "DOC-A", "inclusion_status": "included", "keep_or_duplicate": "keep"},
                        {"document_id": "DOC-B", "inclusion_status": "included", "keep_or_duplicate": "keep"},
                    ]
                )
            (config_dir / "batch_config.json").write_text("{}", encoding="utf-8-sig")
            artifact = clean_dir / "DOC-B.clean.txt"
            artifact.write_text("audit", encoding="utf-8-sig")

            decisions = manifest_dir / "source_review_decisions.csv"
            with decisions.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("document_id", "decision", "reason", "primary_document_id"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "document_id": "DOC-B",
                        "decision": "exclude",
                        "reason": "SAME_SOURCE_COMPANION",
                        "primary_document_id": "DOC-A",
                    }
                )

            result = apply_decisions(batch, decisions)
            self.assertEqual(result["included_file_count"], 1)
            with (manifest_dir / "source_documents_manifest.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            excluded = next(row for row in rows if row["document_id"] == "DOC-B")
            self.assertEqual(excluded["inclusion_status"], "excluded")
            self.assertEqual(excluded["inclusion_reason"], "SAME_SOURCE_COMPANION")
            self.assertTrue(artifact.exists())


if __name__ == "__main__":
    unittest.main()
