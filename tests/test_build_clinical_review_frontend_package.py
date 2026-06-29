import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_clinical_review_frontend_package import build_frontend_package


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class BuildClinicalReviewFrontendPackageTests(unittest.TestCase):
    def test_builds_frontend_json_and_decision_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            effect_dir = root / "effect"
            detail_dir = root / "detail"
            out_dir = root / "frontend"
            write_csv(
                effect_dir / "01_疾病级使用效果审核表.csv",
                [
                    {
                        "batch_id": "BATCH-1",
                        "disease_code": "DIS-1",
                        "disease_name": "测试病",
                        "pending_recommendation_count": "2",
                        "scenario_card_count": "1",
                        "clinical_use_question": "是否可用？",
                    }
                ],
                [
                    "batch_id",
                    "disease_code",
                    "disease_name",
                    "pending_recommendation_count",
                    "scenario_card_count",
                    "clinical_use_question",
                ],
            )
            write_csv(
                effect_dir / "02_场景级推荐审核卡.csv",
                [
                    {
                        "batch_id": "BATCH-1",
                        "disease_code": "DIS-1",
                        "disease_name": "测试病",
                        "scenario_type": "药物治疗",
                        "relation_type": "includes_medication",
                        "target_type": "Medication",
                        "pending_item_count": "2",
                        "sample_targets": "测试药",
                        "missing_field_summary": "药物剂量×2",
                        "review_focus": "重点确认：药物剂量",
                    }
                ],
                [
                    "batch_id",
                    "disease_code",
                    "disease_name",
                    "scenario_type",
                    "relation_type",
                    "target_type",
                    "pending_item_count",
                    "sample_targets",
                    "missing_field_summary",
                    "review_focus",
                ],
            )
            write_csv(
                effect_dir / "03_药师专项审核清单.csv",
                [
                    {
                        "batch_id": "BATCH-1",
                        "disease_code": "DIS-1",
                        "disease_name": "测试病",
                        "relation_id": "REL-1",
                        "relation_type": "includes_medication",
                        "target_code": "MED-1",
                        "target_name": "测试药",
                        "missing_fields": "medication_dosage",
                        "review_focus": "重点确认：药物剂量",
                    }
                ],
                [
                    "batch_id",
                    "disease_code",
                    "disease_name",
                    "relation_id",
                    "relation_type",
                    "target_code",
                    "target_name",
                    "missing_fields",
                    "review_focus",
                ],
            )
            (effect_dir / "clinical_effect_review_summary.json").write_text(
                json.dumps({"disease_review_count": 1, "scenario_card_count": 1, "pharmacist_item_count": 1}, ensure_ascii=False),
                encoding="utf-8-sig",
            )
            write_csv(
                detail_dir / "clinical_review_items.csv",
                [
                    {
                        "batch_id": "BATCH-1",
                        "relation_id": "REL-1",
                        "source_code": "PLAN-1",
                        "source_name": "治疗方案",
                        "relation_type": "includes_medication",
                        "target_code": "MED-1",
                        "target_name": "测试药",
                        "target_type": "Medication",
                        "missing_fields": "medication_dosage",
                        "clinical_review_status": "pending_clinical_review",
                        "evidence_source_chain": "测试指南#p1#EVD-1",
                        "evidence_text_sample": "测试药用于测试病。",
                    }
                ],
                [
                    "batch_id",
                    "relation_id",
                    "source_code",
                    "source_name",
                    "relation_type",
                    "target_code",
                    "target_name",
                    "target_type",
                    "missing_fields",
                    "clinical_review_status",
                    "evidence_source_chain",
                    "evidence_text_sample",
                ],
            )
            (detail_dir / "clinical_review_summary.json").write_text(
                json.dumps({"review_item_count": 1}, ensure_ascii=False),
                encoding="utf-8-sig",
            )

            summary = build_frontend_package(effect_dir, detail_dir, out_dir)
            data = json.loads((out_dir / "clinical_review_frontend_data.json").read_text(encoding="utf-8-sig"))
            template_rows = read_csv_rows(out_dir / "clinical_review_decision_export_template.csv")

            self.assertEqual(summary["disease_review_count"], 1)
            self.assertEqual(summary["scenario_card_count"], 1)
            self.assertEqual(summary["pharmacist_item_count"], 1)
            self.assertEqual(summary["detail_item_count"], 1)
            self.assertEqual(data["schema_version"], "clinical-review-frontend-v1")
            self.assertEqual(data["disease_reviews"][0]["review_id"], "DISEASE-BATCH-1-DIS-1")
            self.assertEqual(data["scenario_cards"][0]["review_id"], "SCENARIO-BATCH-1-DIS-1-includes_medication-Medication")
            self.assertEqual(data["detail_items"][0]["scenario_review_id"], "SCENARIO-BATCH-1-DIS-1-includes_medication-Medication")
            self.assertIn("可试用", data["decision_options"]["clinical_use_decision"])
            self.assertEqual(template_rows[0]["review_level"], "disease")
            self.assertIn("review_decision", template_rows[0])


if __name__ == "__main__":
    unittest.main()
