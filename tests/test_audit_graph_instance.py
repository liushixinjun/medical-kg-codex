import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_graph_instance import audit_graph


class AuditGraphInstanceTests(unittest.TestCase):
    def test_missing_reason_uses_counter_evidence_and_blocks_quality_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            audit_dir = batch / "06_quality_audit"
            data_dir.mkdir(parents=True)
            audit_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "临床",
                "schema_version": "V1.4",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {
                    "id": "N1",
                    "code": "DIS-CARD-VTE",
                    "name": "静脉血栓症",
                    "entityType": "Disease",
                    "description": "静脉血栓症定义。",
                    **common,
                }
            ]
            relations = []
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text("", encoding="utf-8-sig")
            with (audit_dir / "反证检索登记表.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "disease_code",
                        "disease_name",
                        "pathway_element",
                        "source_hit_status",
                        "source_hit_count",
                        "source_hit_lines",
                        "sample_evidence_text",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "disease_code": "DIS-CARD-VTE",
                        "disease_name": "静脉血栓症",
                        "pathway_element": "symptom",
                        "source_hit_status": "SOURCE_HAS_RELEVANT_TEXT",
                        "source_hit_count": "2",
                        "source_hit_lines": "1;2",
                        "sample_evidence_text": "患者可出现呼吸困难、胸痛、咯血、晕厥。",
                    }
                )

            summary = audit_graph(batch)

            self.assertEqual(summary["quality_gate_status"], "failed")
            self.assertEqual(summary["extraction_miss_review_required_count"], 1)
            with (audit_dir / "missing_reason_and_solution.csv").open(encoding="utf-8-sig", newline="") as handle:
                missing_rows = list(csv.DictReader(handle))
            symptom_missing = next(
                row
                for row in missing_rows
                if row["disease_code"] == "DIS-CARD-VTE" and row["pathway_element"] == "symptom"
            )
            self.assertEqual(symptom_missing["missing_reason"], "EXTRACTION_MISS_REVIEW_REQUIRED")
            self.assertIn("反证检索", symptom_missing["solution"])

    def test_source_conflicts_are_resolved_with_statement_level_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            audit_dir = batch / "06_quality_audit"
            data_dir.mkdir(parents=True)
            audit_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "临床",
                "schema_version": "V1.1",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {"id": "N1", "code": "DIS-ACS", "name": "急性冠脉综合征", "entityType": "Disease", "description": "急性冠脉综合征定义。", **common},
                {"id": "N2", "code": "SRC-1", "name": "ACS CN 2024.pdf", "entityType": "Guideline", **common},
                {"id": "N3", "code": "PLAN-ACS", "name": "急性冠脉综合征治疗方案", "aliases": ["治疗"], "entityType": "TreatmentPlan", **common},
            ]
            provenance = [
                {
                    "document_id": "DOC-CN",
                    "segment_id": "SEG-CN",
                    "source_name": "ACS CN 2024.pdf",
                    "source_type": "guideline",
                    "source_version": "2024",
                    "source_section": "治疗",
                    "source_page": 1,
                    "evidence_text": "急性冠脉综合征治疗推荐使用抗血小板治疗。",
                    "recommendation_class": "Ⅰ",
                    "evidence_level": "A",
                },
                {
                    "document_id": "DOC-ESC",
                    "segment_id": "SEG-ESC",
                    "source_name": "ACS ESC 2023.pdf",
                    "source_type": "guideline",
                    "source_version": "2023",
                    "source_section": "治疗",
                    "source_page": 2,
                    "evidence_text": "急性冠脉综合征治疗可考虑早期侵入策略。",
                    "recommendation_class": "Ⅱa",
                    "evidence_level": "B",
                },
            ]
            relations = [
                {
                    "id": "R1",
                    "source_code": "DIS-ACS",
                    "relationType": "based_on_guideline",
                    "target_code": "SRC-1",
                    "relationCategory": "evidence",
                    "batch_id": "BATCH-TEST",
                    "schema_version": "V1.1",
                    "review_status": "approved",
                    "polarity": "positive",
                    "provenance_records_json": provenance,
                    "evidence_ids": ["E1", "E2"],
                    "document_ids": ["DOC-CN", "DOC-ESC"],
                    "source_names": ["ACS CN 2024.pdf", "ACS ESC 2023.pdf"],
                    "source_types": ["guideline"],
                    "evidence_count": 2,
                },
                {
                    "id": "R2",
                    "source_code": "DIS-ACS",
                    "relationType": "has_treatment_plan",
                    "target_code": "PLAN-ACS",
                    "relationCategory": "therapeutic",
                    "batch_id": "BATCH-TEST",
                    "schema_version": "V1.1",
                    "review_status": "approved",
                    "polarity": "positive",
                    "document_id": "DOC-CN",
                    "segment_id": "SEG-CN",
                    "source_name": "ACS CN 2024.pdf",
                    "source_type": "guideline",
                    "source_version": "2024",
                    "source_section": "治疗",
                    "source_page": 1,
                    "evidence_text": "急性冠脉综合征治疗推荐使用抗血小板治疗。",
                    "guideline_id": "SRC-1",
                    "evidence_id": "E1",
                    "recommendation_class": "Ⅰ",
                    "evidence_level": "A",
                    "confidence": 1.0,
                    "provenance_records_json": provenance,
                    "evidence_ids": ["E1", "E2"],
                    "document_ids": ["DOC-CN", "DOC-ESC"],
                    "source_names": ["ACS CN 2024.pdf", "ACS ESC 2023.pdf"],
                    "source_types": ["guideline"],
                    "evidence_count": 2,
                },
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relations),
                encoding="utf-8-sig",
            )

            summary = audit_graph(batch)
            self.assertEqual(summary["source_conflict_count"], 0)
            self.assertEqual(summary["source_conflict_total_count"], 2)
            with (audit_dir / "source_conflict_resolution_plan.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                plan = list(csv.DictReader(handle))
            self.assertEqual({row["conflict_status"] for row in plan}, {"resolved"})
            self.assertIn("statement", plan[1]["resolution_action"])
            self.assertEqual(plan[1]["primary_source"], "ACS CN 2024.pdf")

    def test_accepts_target_match_from_any_provenance_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            config_dir = batch / "00_scope_and_config"
            (batch / "06_quality_audit").mkdir(parents=True)
            config_dir.mkdir(parents=True)
            data_dir.mkdir(parents=True)
            (config_dir / "batch_config.json").write_text(
                json.dumps({"scope_target": "急性心肌梗死"}, ensure_ascii=False),
                encoding="utf-8-sig",
            )

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "临床",
                "schema_version": "V1.1",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {"id": "N1", "code": "DIS-AMI", "name": "急性心肌梗死", "entityType": "Disease", **common},
                {
                    "id": "N2",
                    "code": "DXC-AMI",
                    "name": "急性心肌梗死诊断标准",
                    "entityType": "DiagnosisCriteria",
                    "aliases": ["诊断", "诊断标准", "诊断依据"],
                    **common,
                },
            ]
            provenance = [
                {
                    "document_id": "DOC-1",
                    "segment_id": "SEG-1",
                    "source_name": "指南1",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "诊断",
                    "source_page": 1,
                    "evidence_text": "急性心肌梗死患者应结合胸痛和心电图改变综合判断。",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                },
                {
                    "document_id": "DOC-2",
                    "segment_id": "SEG-2",
                    "source_name": "指南2",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "诊断",
                    "source_page": 2,
                    "evidence_text": "急性心肌梗死诊断标准包括症状、心电图和心肌标志物。",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                },
            ]
            relations = [
                {
                    "id": "R1",
                    "source_code": "DIS-AMI",
                    "relationType": "has_diagnostic_criteria",
                    "target_code": "DXC-AMI",
                    "relationCategory": "diagnostic",
                    "batch_id": "BATCH-TEST",
                    "schema_version": "V1.1",
                    "review_status": "approved",
                    "polarity": "positive",
                    "document_id": "DOC-1",
                    "segment_id": "SEG-1",
                    "source_name": "指南1",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "诊断",
                    "source_page": 1,
                    "evidence_text": "急性心肌梗死患者应结合胸痛和心电图改变综合判断。",
                    "guideline_id": "SRC-DOC-1",
                    "evidence_id": "EVD-1",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "confidence": 1.0,
                    "provenance_records_json": provenance,
                    "evidence_ids": ["EVD-1", "EVD-2"],
                    "document_ids": ["DOC-1", "DOC-2"],
                    "source_names": ["指南1", "指南2"],
                    "source_types": ["guideline"],
                    "evidence_count": 2,
                }
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relations),
                encoding="utf-8-sig",
            )

            summary = audit_graph(batch)
            self.assertEqual(summary["target_match_failure_count"], 0)
            self.assertEqual(summary["quality_gate_status"], "failed")
            self.assertGreater(summary["required_pathway_missing_count"], 0)
            review_text = (batch / "07_review_package" / "专家审核说明.md").read_text(
                encoding="utf-8-sig"
            )
            self.assertIn("# 急性心肌梗死知识图谱专家审核说明", review_text)

    def test_textbook_contextual_disease_evidence_does_not_fail_relevance_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            audit_dir = batch / "06_quality_audit"
            data_dir.mkdir(parents=True)
            audit_dir.mkdir()

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "临床",
                "schema_version": "V1.1",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {
                    "id": "N1",
                    "code": "DIS-HCM",
                    "name": "肥厚型心肌病",
                    "entityType": "Disease",
                    "description": "肥厚型心肌病定义。",
                    **common,
                },
                {
                    "id": "N2",
                    "code": "EVD-TB",
                    "name": "教材证据",
                    "entityType": "Evidence",
                    "evidence_text": "症状可有静息性呼吸困难。体征可闻及第三心音。",
                    "source_type": "authoritative_textbook",
                    "disease_code": "DIS-HCM",
                    "disease_name": "肥厚型心肌病",
                    **common,
                },
            ]
            relations = [
                {
                    "id": "R1",
                    "source_code": "DIS-HCM",
                    "relationType": "supported_by_evidence",
                    "target_code": "EVD-TB",
                    "relationCategory": "evidence",
                    "batch_id": "BATCH-TEST",
                    "schema_version": "V1.1",
                    "review_status": "approved",
                    "polarity": "positive",
                    "provenance_records_json": [
                        {
                            "source_type": "authoritative_textbook",
                            "disease_code": "DIS-HCM",
                            "disease_name": "肥厚型心肌病",
                            "evidence_text": "症状可有静息性呼吸困难。体征可闻及第三心音。",
                            "recommendation_class": "N/A",
                            "evidence_level": "N/A",
                        }
                    ],
                }
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relations),
                encoding="utf-8-sig",
            )

            summary = audit_graph(batch)
            self.assertEqual(summary["disease_relevance_failure_count"], 0)
            self.assertEqual(summary["definition_disease_relevance_rate"], 1.0)

    def test_passes_structurally_valid_evidence_backed_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            audit_dir = batch / "06_quality_audit"
            config_dir = batch / "00_scope_and_config"
            data_dir.mkdir(parents=True)
            audit_dir.mkdir()
            config_dir.mkdir()

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "临床",
                "schema_version": "V1.1",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {"id": "N1", "code": "DIS-HCM", "name": "肥厚型心肌病", "entityType": "Disease", "aliases": ["HCM"], **common},
                {"id": "N2", "code": "EXAM-TTE", "name": "超声心动图", "entityType": "Exam", **common},
                {"id": "N3", "code": "EVD-1", "name": "证据", "entityType": "Evidence", "evidence_text": "肥厚型心肌病应进行超声心动图。", **common},
                {"id": "N4", "code": "EVD-DEF", "name": "定义证据", "entityType": "Evidence", "evidence_text": "肥厚型心肌病是一类以左心室和/或右心室肥厚为特征的心肌病。", **common},
            ]
            provenance = [{"document_id": "DOC-1", "segment_id": "SEG-1", "source_name": "指南", "source_type": "guideline", "source_version": "2025", "source_section": "检查", "source_page": 1, "evidence_text": "肥厚型心肌病应进行超声心动图。", "recommendation_class": "N/A", "evidence_level": "N/A"}]
            definition_provenance = [{"document_id": "DOC-1", "segment_id": "SEG-DEF", "source_name": "指南", "source_type": "guideline", "source_version": "2025", "source_section": "定义", "source_page": 1, "evidence_text": "肥厚型心肌病是一类以左心室和/或右心室肥厚为特征的心肌病。", "recommendation_class": "N/A", "evidence_level": "N/A"}]
            relations = [
                {"id": "R1", "source_code": "DIS-HCM", "relationType": "requires_exam", "target_code": "EXAM-TTE", "relationCategory": "diagnostic", "batch_id": "BATCH-TEST", "schema_version": "V1.1", "review_status": "approved", "polarity": "positive", "document_id": "DOC-1", "segment_id": "SEG-1", "source_name": "指南", "source_type": "guideline", "source_version": "2025", "source_section": "检查", "source_page": 1, "evidence_text": "肥厚型心肌病应进行超声心动图。", "guideline_id": "SRC-DOC-1", "evidence_id": "EVD-1", "recommendation_class": "N/A", "evidence_level": "N/A", "confidence": 1.0, "provenance_records_json": provenance, "evidence_ids": ["EVD-1"], "document_ids": ["DOC-1"], "source_names": ["指南"], "source_types": ["guideline"], "evidence_count": 1},
                {"id": "R2", "source_code": "DIS-HCM", "relationType": "supported_by_evidence", "target_code": "EVD-1", "relationCategory": "evidence", "batch_id": "BATCH-TEST", "schema_version": "V1.1", "review_status": "approved", "polarity": "positive", "provenance_records_json": provenance, "evidence_ids": ["EVD-1"], "document_ids": ["DOC-1"], "source_names": ["指南"], "source_types": ["guideline"], "evidence_count": 1},
                {"id": "R3", "source_code": "DIS-HCM", "relationType": "supported_by_evidence", "target_code": "EVD-DEF", "relationCategory": "evidence", "batch_id": "BATCH-TEST", "schema_version": "V1.1", "review_status": "approved", "polarity": "positive", "provenance_records_json": definition_provenance, "evidence_ids": ["EVD-DEF"], "document_ids": ["DOC-1"], "source_names": ["指南"], "source_types": ["guideline"], "evidence_count": 1},
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relations),
                encoding="utf-8-sig",
            )

            summary = audit_graph(batch)
            self.assertEqual(summary["quality_gate_status"], "failed")
            self.assertGreater(summary["required_pathway_missing_count"], 0)
            self.assertEqual(summary["unknown_entity_type_count"], 0)
            self.assertEqual(summary["dangling_relation_count"], 0)
            self.assertEqual(summary["core_relation_evidence_chain_rate"], 1.0)
            self.assertTrue((audit_dir / "disease_pathway_coverage.csv").is_file())
            self.assertTrue((batch / "07_review_package" / "专家审核说明.md").is_file())
            with (audit_dir / "missing_reason_and_solution.csv").open(encoding="utf-8-sig", newline="") as handle:
                missing_rows = list(csv.DictReader(handle))
            definition_missing = next(
                row
                for row in missing_rows
                if row["disease_code"] == "DIS-HCM" and row["pathway_element"] == "definition"
            )
            self.assertEqual(definition_missing["missing_reason"], "EXTRACTION_MAPPING_GAP")
            with (audit_dir / "disease_pathway_coverage.csv").open(encoding="utf-8-sig", newline="") as handle:
                coverage_rows = list(csv.DictReader(handle))
            self.assertTrue(any(row["pathway_element"] == "risk_factor" for row in coverage_rows))

    def test_rejects_abbreviated_or_combined_medication_standard_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            audit_dir = batch / "06_quality_audit"
            data_dir.mkdir(parents=True)
            audit_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "治疗",
                "schema_version": "V1.1",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {"id": "N1", "code": "DIS-CAD", "name": "冠心病", "entityType": "Disease", "description": "冠心病定义。", **common},
                {"id": "N2", "code": "MED-BAD", "name": "ACEI/ARB", "aliases": ["血管紧张素转换酶抑制剂", "血管紧张素Ⅱ受体阻滞剂"], "entityType": "Medication", **common},
                {"id": "N3", "code": "EVD-1", "name": "证据", "entityType": "Evidence", **common},
            ]
            provenance = [
                {
                    "document_id": "DOC-1",
                    "segment_id": "SEG-1",
                    "source_name": "指南",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "治疗",
                    "source_page": 1,
                    "evidence_text": "冠心病治疗可使用ACEI/ARB。",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                }
            ]
            relations = [
                {"id": "R1", "source_code": "DIS-CAD", "relationType": "treated_by_medication", "target_code": "MED-BAD", "relationCategory": "therapeutic", "batch_id": "BATCH-TEST", "schema_version": "V1.1", "review_status": "approved", "polarity": "positive", "document_id": "DOC-1", "segment_id": "SEG-1", "source_name": "指南", "source_type": "guideline", "source_version": "2025", "source_section": "治疗", "source_page": 1, "evidence_text": "冠心病治疗可使用ACEI/ARB。", "guideline_id": "SRC-DOC-1", "evidence_id": "EVD-1", "recommendation_class": "N/A", "evidence_level": "N/A", "confidence": 1.0, "provenance_records_json": provenance, "evidence_ids": ["EVD-1"], "document_ids": ["DOC-1"], "source_names": ["指南"], "source_types": ["guideline"], "evidence_count": 1},
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relations),
                encoding="utf-8-sig",
            )

            summary = audit_graph(batch)
            self.assertEqual(summary["quality_gate_status"], "failed")
            self.assertEqual(summary["medication_name_error_count"], 1)

    def test_rejects_generic_semantic_shell_nodes_linked_from_disease(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "clinical",
                "schema_version": "V1.1",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {"id": "N1", "code": "DIS-VTE", "name": "\u9759\u8109\u8840\u6813\u75c7", "entityType": "Disease", "description": "\u9759\u8109\u8840\u6813\u75c7\u5b9a\u4e49", **common},
                {"id": "N2", "code": "DDX-GENERIC", "name": "\u9274\u522b\u8bca\u65ad", "entityType": "DifferentialDiagnosis", **common},
                {"id": "N3", "code": "PLAN-GENERIC", "name": "\u836f\u7269\u6cbb\u7597", "entityType": "TreatmentPlan", **common},
            ]
            provenance = [
                {
                    "document_id": "DOC-1",
                    "segment_id": "SEG-1",
                    "source_name": "\u6559\u6750",
                    "source_type": "authoritative_textbook",
                    "source_version": "2026",
                    "source_section": "\u6cbb\u7597",
                    "source_page": 1,
                    "evidence_text": "\u9759\u8109\u8840\u6813\u75c7\u9700\u8981\u8fdb\u884c\u9274\u522b\u8bca\u65ad\u548c\u836f\u7269\u6cbb\u7597\u3002",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                }
            ]
            base_rel = {
                "relationCategory": "therapeutic",
                "batch_id": "BATCH-TEST",
                "schema_version": "V1.1",
                "review_status": "approved",
                "polarity": "positive",
                "document_id": "DOC-1",
                "segment_id": "SEG-1",
                "source_name": "\u6559\u6750",
                "source_type": "authoritative_textbook",
                "source_version": "2026",
                "source_section": "\u6cbb\u7597",
                "source_page": 1,
                "evidence_text": "\u9759\u8109\u8840\u6813\u75c7\u9700\u8981\u8fdb\u884c\u9274\u522b\u8bca\u65ad\u548c\u836f\u7269\u6cbb\u7597\u3002",
                "guideline_id": "SRC-1",
                "evidence_id": "EVD-1",
                "recommendation_class": "N/A",
                "evidence_level": "N/A",
                "confidence": 1.0,
                "provenance_records_json": provenance,
                "evidence_ids": ["EVD-1"],
                "document_ids": ["DOC-1"],
                "source_names": ["\u6559\u6750"],
                "source_types": ["authoritative_textbook"],
                "evidence_count": 1,
            }
            relations = [
                {"id": "R1", "source_code": "DIS-VTE", "relationType": "differentiates_from", "target_code": "DDX-GENERIC", **base_rel},
                {"id": "R2", "source_code": "DIS-VTE", "relationType": "has_treatment_plan", "target_code": "PLAN-GENERIC", **base_rel},
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relations),
                encoding="utf-8-sig",
            )

            summary = audit_graph(batch)

            self.assertEqual(summary["quality_gate_status"], "failed")
            self.assertEqual(summary.get("semantic_shell_node_relation_count"), 2)
            self.assertTrue((batch / "06_quality_audit" / "semantic_shell_node_register.csv").is_file())

    def test_rejects_concrete_medications_only_stored_as_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "therapeutic",
                "schema_version": "V1.1",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {"id": "N1", "code": "MED-CLASS", "name": "\u6297\u51dd\u836f\u7269", "aliases": ["\u534e\u6cd5\u6797", "\u809d\u7d20"], "entityType": "Medication", **common},
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text("", encoding="utf-8-sig")

            summary = audit_graph(batch)

            self.assertEqual(summary["quality_gate_status"], "failed")
            self.assertEqual(summary.get("medication_alias_instance_gap_count"), 2)
            self.assertTrue((batch / "06_quality_audit" / "medication_alias_instance_gap_register.csv").is_file())

    def test_rejects_cdss_recommendation_without_clinical_review_and_closed_loop_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "therapeutic",
                "schema_version": "V1.1",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {"id": "N1", "code": "DIS-VTE", "name": "\u9759\u8109\u8840\u6813\u75c7", "entityType": "Disease", "description": "\u9759\u8109\u8840\u6813\u75c7\u5b9a\u4e49", **common},
                {"id": "N2", "code": "MED-WARFARIN", "name": "\u534e\u6cd5\u6797", "entityType": "Medication", **common},
            ]
            provenance = [
                {
                    "document_id": "DOC-1",
                    "segment_id": "SEG-1",
                    "source_name": "\u6307\u5357",
                    "source_type": "guideline",
                    "source_version": "2026",
                    "source_section": "\u6cbb\u7597",
                    "source_page": 1,
                    "evidence_text": "\u9759\u8109\u8840\u6813\u75c7\u53ef\u4f7f\u7528\u534e\u6cd5\u6797\u6297\u51dd\u6cbb\u7597\u3002",
                    "recommendation_class": "\u2160",
                    "evidence_level": "A",
                }
            ]
            relations = [
                {
                    "id": "R1",
                    "source_code": "DIS-VTE",
                    "relationType": "treated_by_medication",
                    "target_code": "MED-WARFARIN",
                    "relationCategory": "therapeutic",
                    "batch_id": "BATCH-TEST",
                    "schema_version": "V1.1",
                    "review_status": "approved",
                    "polarity": "positive",
                    "document_id": "DOC-1",
                    "segment_id": "SEG-1",
                    "source_name": "\u6307\u5357",
                    "source_type": "guideline",
                    "source_version": "2026",
                    "source_section": "\u6cbb\u7597",
                    "source_page": 1,
                    "evidence_text": "\u9759\u8109\u8840\u6813\u75c7\u53ef\u4f7f\u7528\u534e\u6cd5\u6797\u6297\u51dd\u6cbb\u7597\u3002",
                    "guideline_id": "SRC-1",
                    "evidence_id": "EVD-1",
                    "recommendation_class": "\u2160",
                    "evidence_level": "A",
                    "confidence": 1.0,
                    "provenance_records_json": provenance,
                    "evidence_ids": ["EVD-1"],
                    "document_ids": ["DOC-1"],
                    "source_names": ["\u6307\u5357"],
                    "source_types": ["guideline"],
                    "evidence_count": 1,
                }
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relations),
                encoding="utf-8-sig",
            )

            summary = audit_graph(batch)

            self.assertEqual(summary["quality_gate_status"], "failed")
            self.assertEqual(summary.get("cdss_recommendation_readiness_error_count"), 1)
            self.assertTrue((batch / "06_quality_audit" / "cdss_recommendation_readiness_register.csv").is_file())

    def test_rejects_technical_code_used_as_clinical_display_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            common = {
                "entityCategory": "diagnostic",
                "schema_version": "V1.5",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {
                    "id": "N1",
                    "code": "EXAM-TTE",
                    "name": "EXAM-TTE",
                    "preferred_name": "EXAM-TTE",
                    "display_name": "EXAM-TTE",
                    "aliases": ["\u8d85\u58f0\u5fc3\u52a8\u56fe", "\u7ecf\u80f8\u8d85\u58f0\u5fc3\u52a8\u56fe"],
                    "entityType": "Exam",
                    **common,
                }
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text("", encoding="utf-8-sig")

            summary = audit_graph(batch)

            self.assertEqual(summary["quality_gate_status"], "failed")
            self.assertEqual(summary.get("technical_display_name_error_count"), 1)
            self.assertTrue((batch / "06_quality_audit" / "technical_display_name_error_register.csv").is_file())

    def test_rejects_executable_treatment_plan_without_downstream_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "therapeutic",
                "schema_version": "V1.5",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {"id": "N1", "code": "DIS-VTE", "name": "\u9759\u8109\u8840\u6813\u75c7", "entityType": "Disease", "description": "\u9759\u8109\u8840\u6813\u75c7\u5b9a\u4e49", **common},
                {"id": "N2", "code": "PLAN-THROMBOLYSIS", "name": "\u6eb6\u6813\u6cbb\u7597", "entityType": "TreatmentPlan", **common},
            ]
            provenance = [
                {
                    "document_id": "DOC-1",
                    "segment_id": "SEG-1",
                    "source_name": "\u6559\u6750",
                    "source_type": "authoritative_textbook",
                    "source_version": "2026",
                    "source_section": "\u6cbb\u7597",
                    "source_page": 1,
                    "evidence_text": "\u9759\u8109\u8840\u6813\u75c7\u53ef\u8003\u8651\u6eb6\u6813\u6cbb\u7597\u3002",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                }
            ]
            relations = [
                {
                    "id": "R1",
                    "source_code": "DIS-VTE",
                    "relationType": "has_treatment_plan",
                    "target_code": "PLAN-THROMBOLYSIS",
                    "relationCategory": "therapeutic",
                    "batch_id": "BATCH-TEST",
                    "schema_version": "V1.5",
                    "review_status": "approved",
                    "polarity": "positive",
                    "document_id": "DOC-1",
                    "segment_id": "SEG-1",
                    "source_name": "\u6559\u6750",
                    "source_type": "authoritative_textbook",
                    "source_version": "2026",
                    "source_section": "\u6cbb\u7597",
                    "source_page": 1,
                    "evidence_text": "\u9759\u8109\u8840\u6813\u75c7\u53ef\u8003\u8651\u6eb6\u6813\u6cbb\u7597\u3002",
                    "guideline_id": "SRC-1",
                    "evidence_id": "EVD-1",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "confidence": 1.0,
                    "provenance_records_json": provenance,
                    "evidence_ids": ["EVD-1"],
                    "document_ids": ["DOC-1"],
                    "source_names": ["\u6559\u6750"],
                    "source_types": ["authoritative_textbook"],
                    "evidence_count": 1,
                }
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relations),
                encoding="utf-8-sig",
            )

            summary = audit_graph(batch)

            self.assertEqual(summary["quality_gate_status"], "failed")
            self.assertEqual(summary.get("treatment_plan_actionability_error_count"), 1)
            self.assertTrue((batch / "06_quality_audit" / "treatment_plan_actionability_register.csv").is_file())

    def test_rejects_medication_class_without_specific_medication(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            node = {
                "id": "N1",
                "code": "MED-STATIN-CLASS",
                "name": "\u4ed6\u6c40\u7c7b\u836f\u7269",
                "preferred_name": "\u4ed6\u6c40\u7c7b\u836f\u7269",
                "display_name": "\u4ed6\u6c40\u7c7b\u836f\u7269",
                "aliases": ["\u4ed6\u6c40"],
                "entityType": "Medication",
                "entityCategory": "therapeutic",
                "schema_version": "V1.5",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            (data_dir / "nodes_final.jsonl").write_text(
                json.dumps(node, ensure_ascii=False) + "\n",
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text("", encoding="utf-8-sig")

            summary = audit_graph(batch)

            self.assertEqual(summary["quality_gate_status"], "failed")
            self.assertEqual(summary.get("medication_class_without_specific_count"), 1)
            self.assertTrue((batch / "06_quality_audit" / "medication_class_specific_gap_register.csv").is_file())

    def test_accepts_medication_class_target_when_evidence_mentions_specific_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "therapeutic",
                "schema_version": "V1.5",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {"id": "N1", "code": "DIS-HF", "name": "\u5fc3\u529b\u8870\u7aed", "entityType": "Disease", "description": "\u5fc3\u529b\u8870\u7aed", **common},
                {"id": "N2", "code": "MED-DIGITALIS", "name": "\u6d0b\u5730\u9ec4\u7c7b\u836f\u7269", "entityType": "Medication", **common},
                {"id": "N3", "code": "MED-DIGOXIN", "name": "\u5730\u9ad8\u8f9b", "entityType": "Medication", **common},
            ]
            relations = [
                {
                    "id": "R1",
                    "source_code": "MED-DIGITALIS",
                    "relationType": "has_specific_medication",
                    "target_code": "MED-DIGOXIN",
                    "relationCategory": "taxonomy",
                    "batch_id": "BATCH-TEST",
                    "schema_version": "V1.5",
                    "review_status": "approved",
                },
                {
                    "id": "R2",
                    "source_code": "DIS-HF",
                    "relationType": "treated_by_medication",
                    "target_code": "MED-DIGITALIS",
                    "relationCategory": "therapeutic",
                    "batch_id": "BATCH-TEST",
                    "schema_version": "V1.5",
                    "review_status": "approved",
                    "document_id": "DOC-1",
                    "segment_id": "SEG-1",
                    "source_name": "\u6559\u6750",
                    "source_type": "authoritative_textbook",
                    "source_version": "2026",
                    "source_section": "\u6cbb\u7597",
                    "source_page": 1,
                    "evidence_text": "\u5fc3\u529b\u8870\u7aed\u53ef\u6839\u636e\u60c5\u51b5\u4f7f\u7528\u5730\u9ad8\u8f9b\u3002",
                    "guideline_id": "SRC-1",
                    "evidence_id": "EVD-1",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "confidence": 1.0,
                    "provenance_records_json": [{"evidence_text": "\u5fc3\u529b\u8870\u7aed\u53ef\u6839\u636e\u60c5\u51b5\u4f7f\u7528\u5730\u9ad8\u8f9b\u3002"}],
                    "evidence_ids": ["EVD-1"],
                    "document_ids": ["DOC-1"],
                    "source_names": ["\u6559\u6750"],
                    "source_types": ["authoritative_textbook"],
                    "evidence_count": 1,
                },
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relations),
                encoding="utf-8-sig",
            )

            summary = audit_graph(batch)

            self.assertEqual(summary["target_match_failure_count"], 0)


if __name__ == "__main__":
    unittest.main()
