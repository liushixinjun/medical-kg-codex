import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_graph_instance import CDSS_CLINICAL_APPROVED_STATUSES
from scripts.apply_cdss_ai_precheck_signoff import apply_precheck_signoff


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def write_readiness_register(path: Path, relation_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
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
        for relation_id in relation_ids:
            writer.writerow(
                {
                    "relation_id": relation_id,
                    "source_code": "DIS-HF",
                    "source_name": "心力衰竭",
                    "relation_type": "has_follow_up",
                    "target_code": "FU-HF",
                    "target_name": "随访方案",
                    "target_type": "FollowUp",
                    "missing_fields": "clinical_review_status;evidence_source_chain",
                    "clinical_review_status": "pending_clinical_review",
                    "solution": "补齐后审核",
                }
            )


class CdssAiPrecheckSignoffTests(unittest.TestCase):
    def test_signoff_fills_evidence_chain_and_marks_clear_non_medication_as_test_recommendation(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-HF"
            write_jsonl(
                batch / "05_data_instance" / "nodes_final.jsonl",
                [
                    {"code": "DIS-HF", "name": "心力衰竭", "entityType": "Disease"},
                    {"code": "FU-HF", "name": "心力衰竭随访方案", "entityType": "FollowUp"},
                    {
                        "code": "EVD-1",
                        "entityType": "Evidence",
                        "evidence_id": "EVD-1",
                        "document_id": "DOC-1",
                        "segment_id": "SEG-1",
                        "source_name": "测试指南",
                        "source_type": "guideline",
                        "source_version": "2026",
                        "source_section": "随访",
                        "source_page": 8,
                        "evidence_text": "心力衰竭患者出院后应随访。",
                        "guideline_id": "GL-1",
                        "recommendation_class": "Ⅰ",
                        "evidence_level": "A",
                        "confidence": 0.91,
                    },
                ],
            )
            write_jsonl(
                batch / "05_data_instance" / "relations_final.jsonl",
                [
                    {
                        "id": "REL-1",
                        "source_code": "DIS-HF",
                        "relationType": "has_follow_up",
                        "target_code": "FU-HF",
                        "recommendation_class": "Ⅰ",
                        "evidence_level": "A",
                        "evidence_ids": ["EVD-1"],
                        "clinical_review_status": "pending_clinical_review",
                        "formal_cdss_ready": False,
                    }
                ],
            )
            write_readiness_register(batch / "06_quality_audit" / "cdss_recommendation_readiness_register.csv", ["REL-1"])

            summary = apply_precheck_signoff(
                batch,
                reviewer_name="临床专家组批量签收",
                reviewer_role="心血管内科专家组",
                reviewed_at="2026-06-30 12:00:00",
                output_dir=batch / "07_review_package" / "ai_precheck",
                apply=True,
            )
            rel = read_jsonl(batch / "05_data_instance" / "relations_final.jsonl")[0]

            self.assertEqual(summary["updated_relations"], 1)
            self.assertEqual(summary["ai_prechecked_pass"], 1)
            self.assertEqual(rel["clinical_review_status"], "clinical_batch_signed_off")
            self.assertEqual(rel["recommendation_class_and_evidence_level"], "Ⅰ/A")
            self.assertIn("测试指南#p8#EVD-1", rel["evidence_source_chain"])
            self.assertEqual(rel["document_id"], "DOC-1")
            self.assertEqual(rel["ai_evidence_review_status"], "ai_prechecked_pass")
            self.assertEqual(rel["cdss_release_level"], "test_recommendation")
            self.assertFalse(rel["formal_cdss_ready"])

    def test_medication_without_safety_fields_is_blocked_even_when_signed_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-HF"
            write_jsonl(
                batch / "05_data_instance" / "nodes_final.jsonl",
                [
                    {"code": "DIS-HF", "name": "心力衰竭", "entityType": "Disease"},
                    {"code": "MED-1", "name": "β受体阻滞剂", "entityType": "Medication"},
                    {"code": "EVD-1", "entityType": "Evidence", "evidence_id": "EVD-1", "source_name": "测试指南", "source_page": 9},
                ],
            )
            write_jsonl(
                batch / "05_data_instance" / "relations_final.jsonl",
                [
                    {
                        "id": "REL-MED",
                        "source_code": "DIS-HF",
                        "relationType": "treated_by_medication",
                        "target_code": "MED-1",
                        "recommendation_class": "Ⅰ",
                        "evidence_level": "A",
                        "evidence_ids": ["EVD-1"],
                    }
                ],
            )
            write_readiness_register(batch / "06_quality_audit" / "cdss_recommendation_readiness_register.csv", ["REL-MED"])

            summary = apply_precheck_signoff(
                batch,
                reviewer_name="临床专家组批量签收",
                reviewer_role="心血管内科专家组",
                reviewed_at="2026-06-30 12:00:00",
                output_dir=batch / "07_review_package" / "ai_precheck",
                apply=True,
            )
            rel = read_jsonl(batch / "05_data_instance" / "relations_final.jsonl")[0]

            self.assertEqual(summary["ai_prechecked_blocked"], 1)
            self.assertEqual(rel["clinical_review_status"], "clinical_batch_signed_off")
            self.assertEqual(rel["ai_evidence_review_status"], "ai_prechecked_blocked")
            self.assertEqual(rel["cdss_release_level"], "formal_blocked")
            self.assertIn("medication_safety_fields_missing", rel["formal_cdss_block_reason"])

    def test_na_grade_is_limited_to_knowledge_display(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-HF"
            write_jsonl(
                batch / "05_data_instance" / "nodes_final.jsonl",
                [
                    {"code": "DIS-HF", "name": "心力衰竭", "entityType": "Disease"},
                    {"code": "PLAN-1", "name": "心力衰竭治疗方案", "entityType": "TreatmentPlan"},
                    {"code": "EVD-1", "entityType": "Evidence", "evidence_id": "EVD-1", "source_name": "测试指南", "source_page": 10},
                ],
            )
            write_jsonl(
                batch / "05_data_instance" / "relations_final.jsonl",
                [
                    {
                        "id": "REL-NA",
                        "source_code": "DIS-HF",
                        "relationType": "has_treatment_plan",
                        "target_code": "PLAN-1",
                        "recommendation_class": "N/A",
                        "evidence_level": "N/A",
                        "evidence_ids": ["EVD-1"],
                    }
                ],
            )
            write_readiness_register(batch / "06_quality_audit" / "cdss_recommendation_readiness_register.csv", ["REL-NA"])

            summary = apply_precheck_signoff(
                batch,
                reviewer_name="临床专家组批量签收",
                reviewer_role="心血管内科专家组",
                reviewed_at="2026-06-30 12:00:00",
                output_dir=batch / "07_review_package" / "ai_precheck",
                apply=True,
            )
            rel = read_jsonl(batch / "05_data_instance" / "relations_final.jsonl")[0]

            self.assertEqual(summary["ai_prechecked_limited"], 1)
            self.assertEqual(rel["ai_evidence_review_status"], "ai_prechecked_limited")
            self.assertEqual(rel["cdss_release_level"], "knowledge_display")
            self.assertIn("recommendation_grade_not_explicit", rel["formal_cdss_block_reason"])

    def test_batch_signed_off_status_is_a_clinical_review_approved_status(self):
        self.assertIn("clinical_batch_signed_off", CDSS_CLINICAL_APPROVED_STATUSES)


if __name__ == "__main__":
    unittest.main()
