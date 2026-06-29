import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_clinical_effect_review_pack import build_effect_review_pack


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class BuildClinicalEffectReviewPackTests(unittest.TestCase):
    def test_groups_pending_items_into_disease_and_scenario_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "BATCH-TEST"
            write_jsonl(
                batch / "05_data_instance" / "nodes_final.jsonl",
                [
                    {"code": "DIS-1", "name": "测试病", "entityType": "Disease"},
                    {"code": "PLAN-1", "name": "测试治疗方案", "entityType": "TreatmentPlan"},
                    {"code": "MED-1", "name": "测试药物", "entityType": "Medication"},
                ],
            )
            write_jsonl(
                batch / "05_data_instance" / "relations_final.jsonl",
                [
                    {
                        "id": "REL-DIS-PLAN",
                        "source_code": "DIS-1",
                        "relationType": "has_treatment_plan",
                        "target_code": "PLAN-1",
                        "relationCategory": "therapeutic",
                    },
                    {
                        "id": "REL-PLAN-MED",
                        "source_code": "PLAN-1",
                        "relationType": "includes_medication",
                        "target_code": "MED-1",
                        "relationCategory": "therapeutic",
                        "evidence_text": "测试治疗方案包括测试药物。",
                    },
                ],
            )
            audit_dir = batch / "06_quality_audit"
            audit_dir.mkdir(parents=True)
            with (audit_dir / "cdss_recommendation_readiness_register.csv").open("w", encoding="utf-8-sig", newline="") as handle:
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
                        "relation_id": "REL-PLAN-MED",
                        "source_code": "PLAN-1",
                        "source_name": "测试治疗方案",
                        "relation_type": "includes_medication",
                        "target_code": "MED-1",
                        "target_name": "测试药物",
                        "target_type": "Medication",
                        "missing_fields": "clinical_review_status;medication_dosage;medication_interaction",
                        "clinical_review_status": "pending_clinical_review",
                        "solution": "补齐后审核",
                    }
                )

            summary = build_effect_review_pack([batch], root / "review")
            disease_rows = read_csv_rows(root / "review" / "01_疾病级使用效果审核表.csv")
            scenario_rows = read_csv_rows(root / "review" / "02_场景级推荐审核卡.csv")
            pharmacist_rows = read_csv_rows(root / "review" / "03_药师专项审核清单.csv")

            self.assertEqual(summary["disease_review_count"], 1)
            self.assertEqual(summary["scenario_card_count"], 1)
            self.assertEqual(disease_rows[0]["disease_code"], "DIS-1")
            self.assertEqual(disease_rows[0]["pending_recommendation_count"], "1")
            self.assertEqual(scenario_rows[0]["scenario_type"], "药物治疗")
            self.assertEqual(scenario_rows[0]["sample_targets"], "测试药物")
            self.assertIn("剂量", scenario_rows[0]["review_focus"])
            self.assertEqual(pharmacist_rows[0]["target_name"], "测试药物")


if __name__ == "__main__":
    unittest.main()
