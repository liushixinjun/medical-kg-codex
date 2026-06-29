import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.apply_clinical_review_decisions import apply_decisions
from scripts.build_clinical_review_pack import build_pack


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class ClinicalReviewWorkflowTests(unittest.TestCase):
    def test_builds_review_pack_with_evidence_chain_and_template_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "BATCH-TEST"
            audit = batch / "06_quality_audit"
            audit.mkdir(parents=True)
            with (audit / "cdss_recommendation_readiness_register.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "relation_id",
                        "source_code",
                        "source_name",
                        "relation_type",
                        "target_code",
                        "target_name",
                        "target_type",
                        "missing_fields",
                        "clinical_review_status",
                        "solution",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "relation_id": "REL-1",
                        "source_code": "DIS-1",
                        "source_name": "测试病",
                        "relation_type": "treated_by_medication",
                        "target_code": "MED-1",
                        "target_name": "测试药",
                        "target_type": "Medication",
                        "missing_fields": "applicable_population;clinical_review_status",
                        "clinical_review_status": "pending_clinical_review",
                        "solution": "补齐后审核",
                    }
                )
            write_jsonl(
                batch / "05_data_instance" / "relations_final.jsonl",
                [
                    {
                        "id": "REL-1",
                        "source_code": "DIS-1",
                        "relationType": "treated_by_medication",
                        "target_code": "MED-1",
                        "provenance_records_json": [
                            {
                                "source_name": "测试指南",
                                "source_page": 8,
                                "evidence_id": "EVD-1",
                                "evidence_text": "测试病患者推荐使用测试药。",
                            }
                        ],
                    }
                ],
            )

            out_dir = root / "review"
            summary = build_pack([batch], out_dir)
            rows = read_csv_rows(out_dir / "clinical_review_items.csv")

            self.assertEqual(summary["review_item_count"], 1)
            self.assertEqual(rows[0]["relation_id"], "REL-1")
            self.assertIn("测试指南", rows[0]["evidence_source_chain"])
            self.assertIn("clinical_review_decision", rows[0])
            self.assertIn("reviewer_name", rows[0])

    def test_applies_only_approved_decision_with_required_reviewer_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "BATCH-TEST"
            write_jsonl(
                batch / "05_data_instance" / "nodes_final.jsonl",
                [
                    {"code": "DIS-1", "name": "测试病", "entityType": "Disease"},
                    {"code": "MED-1", "name": "测试药", "entityType": "Medication"},
                ],
            )
            write_jsonl(
                batch / "05_data_instance" / "relations_final.jsonl",
                [
                    {
                        "id": "REL-1",
                        "source_code": "DIS-1",
                        "relationType": "treated_by_medication",
                        "target_code": "MED-1",
                        "clinical_review_status": "pending_clinical_review",
                    }
                ],
            )
            decisions = root / "decisions.csv"
            with decisions.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "batch_id",
                        "relation_id",
                        "clinical_review_decision",
                        "reviewer_name",
                        "reviewer_role",
                        "reviewed_at",
                        "expert_comment",
                        "applicable_population",
                        "recommendation_class",
                        "evidence_level",
                        "medication_dosage",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "batch_id": "BATCH-TEST",
                        "relation_id": "REL-1",
                        "clinical_review_decision": "approve",
                        "reviewer_name": "张医生",
                        "reviewer_role": "心内科主任医师",
                        "reviewed_at": "2026-06-28 21:30:00",
                        "expert_comment": "通过",
                        "applicable_population": "测试病成人患者",
                        "recommendation_class": "I",
                        "evidence_level": "B",
                        "medication_dosage": "遵医嘱",
                    }
                )

            summary = apply_decisions([batch], decisions)
            rel = json.loads((batch / "05_data_instance" / "relations_final.jsonl").read_text(encoding="utf-8-sig").splitlines()[0])
            node_rows = [
                json.loads(line)
                for line in (batch / "05_data_instance" / "nodes_final.jsonl").read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            med = next(row for row in node_rows if row["code"] == "MED-1")

            self.assertEqual(summary["updated_relations"], 1)
            self.assertEqual(rel["clinical_review_status"], "clinical_approved")
            self.assertFalse(rel["formal_cdss_ready"])
            self.assertEqual(rel["applicable_population"], "测试病成人患者")
            self.assertEqual(med["dosage"], "遵医嘱")

    def test_rejects_approved_decision_without_reviewer_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "BATCH-TEST"
            write_jsonl(batch / "05_data_instance" / "nodes_final.jsonl", [])
            write_jsonl(batch / "05_data_instance" / "relations_final.jsonl", [])
            decisions = root / "decisions.csv"
            with decisions.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["batch_id", "relation_id", "clinical_review_decision", "reviewer_name", "reviewer_role", "reviewed_at"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "batch_id": "BATCH-TEST",
                        "relation_id": "REL-1",
                        "clinical_review_decision": "approve",
                        "reviewer_name": "",
                        "reviewer_role": "心内科",
                        "reviewed_at": "2026-06-28 21:30:00",
                    }
                )

            with self.assertRaisesRegex(ValueError, "missing reviewer metadata"):
                apply_decisions([batch], decisions)


if __name__ == "__main__":
    unittest.main()
