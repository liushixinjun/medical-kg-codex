import json
import tempfile
import unittest
from pathlib import Path

from scripts.apply_curated_required_backfill import apply_backfill_spec


class ApplyCuratedRequiredBackfillTests(unittest.TestCase):
    def test_adds_node_and_relation_once_by_semantic_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-TEST"
            data = batch / "05_data_instance"
            data.mkdir(parents=True)
            (data / "nodes_final.jsonl").write_text(
                json.dumps(
                    {
                        "id": "KG_DIS_1",
                        "code": "DIS-1",
                        "name": "测试病",
                        "preferred_name": "测试病",
                        "display_name": "测试病",
                        "entityType": "Disease",
                        "entityCategory": "临床",
                        "schema_version": "V1.1",
                        "review_status": "approved",
                        "batch_id": "BATCH-TEST",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8-sig",
            )
            (data / "relations_final.jsonl").write_text("", encoding="utf-8-sig")

            spec = {
                "batches": [
                    {
                        "batch_dir": str(batch),
                        "nodes": [
                            {
                                "code": "DXC-1",
                                "name": "测试病诊断标准",
                                "entityType": "DiagnosisCriteria",
                                "entityCategory": "诊断",
                            }
                        ],
                        "relations": [
                            {
                                "source_code": "DIS-1",
                                "relationType": "has_diagnostic_criteria",
                                "target_code": "DXC-1",
                                "applicable_population": "疑似测试病患者",
                                "exclusion_criteria": "排除继发性原因",
                                "clinical_rule_or_clinical_pathway": "测试病诊断路径",
                                "provenance_records_json": [
                                    {
                                        "document_id": "DOC-1",
                                        "segment_id": "SEG-1",
                                        "source_name": "测试教材",
                                        "source_type": "authoritative_textbook",
                                        "source_version": "第1版",
                                        "source_section": "diagnosis_criteria",
                                        "source_page": 1,
                                        "evidence_text": "测试病诊断依据包括症状、检查和排除其他疾病。",
                                        "evidence_id": "EVD-1",
                                        "recommendation_class": "N/A",
                                        "evidence_level": "N/A",
                                        "confidence": 0.86,
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }

            first = apply_backfill_spec(spec)
            second = apply_backfill_spec(spec)

            self.assertEqual(first["added_nodes"], 1)
            self.assertEqual(first["added_relations"], 1)
            self.assertEqual(second["added_nodes"], 0)
            self.assertEqual(second["added_relations"], 0)
            relation = json.loads((data / "relations_final.jsonl").read_text(encoding="utf-8-sig").splitlines()[0])
            self.assertEqual(relation["applicable_population"], "疑似测试病患者")
            self.assertEqual(relation["exclusion_criteria"], "排除继发性原因")
            self.assertEqual(relation["clinical_rule_or_clinical_pathway"], "测试病诊断路径")

    def test_rejects_missing_relation_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-TEST"
            data = batch / "05_data_instance"
            data.mkdir(parents=True)
            (data / "nodes_final.jsonl").write_text("", encoding="utf-8-sig")
            (data / "relations_final.jsonl").write_text("", encoding="utf-8-sig")

            spec = {
                "batches": [
                    {
                        "batch_dir": str(batch),
                        "nodes": [],
                        "relations": [
                            {
                                "source_code": "DIS-MISSING",
                                "relationType": "has_etiology",
                                "target_code": "ETI-MISSING",
                                "provenance_records_json": [],
                            }
                        ],
                    }
                ]
            }

            with self.assertRaisesRegex(ValueError, "Missing endpoint"):
                apply_backfill_spec(spec)


if __name__ == "__main__":
    unittest.main()
