import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_graph_instance import build_graph_instance


class BuildGraphInstanceTests(unittest.TestCase):
    def test_builds_schema_nodes_relations_and_thresholds_with_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            for folder in (
                "00_scope_and_config",
                "01_source_manifest",
                "03_clean_text",
                "04_evidence_and_extraction",
                "05_data_instance",
                "06_quality_audit",
            ):
                (batch / folder).mkdir(parents=True, exist_ok=True)

            taxonomy_fields = (
                "specialty_code",
                "category_code",
                "subcategory_code",
                "disease_code",
                "name",
                "name_en",
                "aliases",
                "inclusion_status",
                "inclusion_reason",
            )
            taxonomy = [
                {"specialty_code": "SPEC-CARD", "name": "心血管内科", "inclusion_status": "included"},
                {"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CM", "name": "心肌病", "inclusion_status": "included"},
                {"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CM", "subcategory_code": "SUB-CARD-CM-PHENOTYPE", "name": "心室表型心肌病", "inclusion_status": "included"},
                {"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CM", "subcategory_code": "SUB-CARD-CM-PHENOTYPE", "disease_code": "DIS-CARD-CM-HCM", "name": "肥厚型心肌病", "name_en": "Hypertrophic cardiomyopathy", "aliases": "HCM", "inclusion_status": "included"},
            ]
            with (batch / "00_scope_and_config" / "scope_taxonomy.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=taxonomy_fields)
                writer.writeheader()
                writer.writerows(taxonomy)

            vocabulary_fields = (
                "canonical_name",
                "name_en",
                "abbr",
                "aliases",
                "entityType",
                "disease_scope",
                "source",
            )
            vocabulary = [
                {"canonical_name": "肥厚型心肌病", "name_en": "Hypertrophic cardiomyopathy", "abbr": "HCM", "entityType": "Disease", "disease_scope": "DIS-CARD-CM-HCM"},
                {"canonical_name": "左心室射血分数", "abbr": "LVEF", "entityType": "ExamIndicator", "disease_scope": "ALL"},
                {"canonical_name": "超声心动图", "abbr": "TTE", "aliases": "经胸超声心动图", "entityType": "Exam", "disease_scope": "ALL"},
                {"canonical_name": "β受体拮抗剂", "aliases": "β受体阻滞剂", "entityType": "Medication", "disease_scope": "ALL"},
                {"canonical_name": "静息性呼吸困难", "aliases": "静息呼吸困难", "entityType": "Symptom", "disease_scope": "ALL"},
                {"canonical_name": "第三心音", "aliases": "S3", "entityType": "Sign", "disease_scope": "ALL"},
                {"canonical_name": "家族史", "aliases": "家族性发病", "entityType": "RiskFactor", "disease_scope": "ALL"},
                {"canonical_name": "高血压性心脏病", "aliases": "高血压心脏病", "entityType": "DifferentialDiagnosis", "disease_scope": "ALL"},
            ]
            with (batch / "00_scope_and_config" / "controlled_vocabulary.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=vocabulary_fields)
                writer.writeheader()
                writer.writerows(vocabulary)

            manifest_fields = (
                "batch_id",
                "document_id",
                "file_name",
                "source_type",
                "sha256",
                "inclusion_status",
            )
            with (batch / "01_source_manifest" / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=manifest_fields)
                writer.writeheader()
                writer.writerow(
                    {"batch_id": "BATCH-TEST", "document_id": "DOC-1", "file_name": "HCM指南2025.pdf", "source_type": "guideline", "sha256": "ABC", "inclusion_status": "included"}
                )

            evidence = [
                {
                    "evidence_id": "EVD-EN",
                    "document_id": "DOC-1",
                    "segment_id": "SEG-EN",
                    "source_name": "HCM ESC 2023.pdf",
                    "source_type": "guideline",
                    "source_version": "2023",
                    "source_section": "definition",
                    "source_page": 1,
                    "disease_code": "DIS-CARD-CM-HCM",
                    "disease_name": "肥厚型心肌病",
                    "pathway_element": "definition",
                    "evidence_text": "Hypertrophic cardiomyopathy is defined as increased ventricular wall thickness not explained by loading conditions.",
                    "content_hash": "HASH-EN",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "review_status": "approved",
                },
                {
                    "evidence_id": "EVD-0",
                    "document_id": "DOC-1",
                    "segment_id": "SEG-0",
                    "source_name": "HCM指南2025.pdf",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "pathophysiology",
                    "source_page": 1,
                    "disease_code": "DIS-CARD-CM-HCM",
                    "disease_name": "肥厚型心肌病",
                    "pathway_element": "pathophysiology",
                    "evidence_text": "肥厚型心肌病（hypertrophic cardiomyopathy，HCM）是一类以左心室和/或右心室肥厚，伴舒张功能障碍为特征的心肌病。发病机制与遗传有关。",
                    "content_hash": "HASH0",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "review_status": "approved",
                },
                {
                    "evidence_id": "EVD-1",
                    "document_id": "DOC-1",
                    "segment_id": "SEG-1",
                    "source_name": "HCM指南2025.pdf",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "exam",
                    "source_page": 1,
                    "disease_code": "DIS-CARD-CM-HCM",
                    "disease_name": "肥厚型心肌病",
                    "pathway_element": "exam",
                    "evidence_text": "肥厚型心肌病患者应行超声心动图，LVEF≤35%。",
                    "content_hash": "HASH1",
                    "recommendation_class": "Ⅰ",
                    "evidence_level": "B",
                    "review_status": "approved",
                },
                {
                    "evidence_id": "EVD-2",
                    "document_id": "DOC-1",
                    "segment_id": "SEG-2",
                    "source_name": "HCM指南2025.pdf",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "treatment_plan",
                    "source_page": 1,
                    "disease_code": "DIS-CARD-CM-HCM",
                    "disease_name": "肥厚型心肌病",
                    "pathway_element": "treatment_plan",
                    "evidence_text": "β受体拮抗剂可用于肥厚型心肌病的症状治疗。",
                    "content_hash": "HASH2",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "review_status": "approved",
                },
                {
                    "evidence_id": "EVD-RF",
                    "document_id": "DOC-1",
                    "segment_id": "SEG-RF",
                    "source_name": "HCM指南2025.pdf",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "etiology",
                    "source_page": 2,
                    "disease_code": "DIS-CARD-CM-HCM",
                    "disease_name": "肥厚型心肌病",
                    "pathway_element": "etiology",
                    "evidence_text": "肥厚型心肌病常有家族史，需注意遗传因素。",
                    "content_hash": "HASH-RF",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "review_status": "approved",
                },
                {
                    "evidence_id": "EVD-DDX",
                    "document_id": "DOC-1",
                    "segment_id": "SEG-DDX",
                    "source_name": "HCM指南2025.pdf",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "diagnosis_criteria",
                    "source_page": 3,
                    "disease_code": "DIS-CARD-CM-HCM",
                    "disease_name": "肥厚型心肌病",
                    "pathway_element": "diagnosis_criteria",
                    "evidence_text": "肥厚型心肌病诊断时需与高血压性心脏病鉴别。",
                    "content_hash": "HASH-DDX",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "review_status": "approved",
                },
            ]
            with (batch / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl").open(
                "w", encoding="utf-8-sig"
            ) as handle:
                for row in evidence:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            (batch / "03_clean_text" / "textbook_evidence_index.jsonl").write_text(
                json.dumps(
                    {
                        "document_id": "DOC-1",
                        "segment_id": "SEG-TB-UNANCHORED",
                        "source_name": "《内科学》第10版",
                        "source_type": "authoritative_textbook",
                        "source_section": "心肌病章节",
                        "source_page": 10,
                        "disease_code": "DIS-CARD-CM-HCM",
                        "disease_name": "肥厚型心肌病",
                        "pathway_element": "symptom_sign",
                        "evidence_text": "症状可有静息性呼吸困难。体征可闻及第三心音。",
                        "content_hash": "HASH-TB",
                        "recommendation_class": "N/A",
                        "evidence_level": "N/A",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8-sig",
            )

            summary = build_graph_instance(batch)
            self.assertGreater(summary["node_count"], 0)
            self.assertGreater(summary["relation_count"], 0)
            nodes = [json.loads(line) for line in (batch / "05_data_instance" / "nodes_final.jsonl").read_text(encoding="utf-8-sig").splitlines()]
            relations = [json.loads(line) for line in (batch / "05_data_instance" / "relations_final.jsonl").read_text(encoding="utf-8-sig").splitlines()]
            hcm = next(node for node in nodes if node["code"] == "DIS-CARD-CM-HCM")
            self.assertEqual(
                hcm["description"],
                "肥厚型心肌病（hypertrophic cardiomyopathy，HCM）是一类以左心室和/或右心室肥厚，伴舒张功能障碍为特征的心肌病。",
            )
            self.assertEqual(hcm["definition_evidence_text"], hcm["description"])
            self.assertTrue(any(node["entityType"] == "ThresholdRule" and node["value"] == 35 for node in nodes))
            self.assertTrue(any(rel["relationType"] == "requires_exam" for rel in relations))
            self.assertTrue(any(rel["relationType"] == "treated_by_medication" for rel in relations))
            self.assertTrue(all(rel.get("evidence_text") for rel in relations if rel["relationCategory"] in {"clinical", "diagnostic", "therapeutic", "risk", "rule"}))
            self.assertFalse(any(node["name"].replace("%", "").replace(".", "").isdigit() for node in nodes))
            evidence_names = [node["name"] for node in nodes if node["entityType"] == "Evidence"]
            self.assertEqual(len(evidence_names), len(set(evidence_names)))
            tte = next(node for node in nodes if node["code"] == "EXAM-TTE")
            self.assertEqual(tte["name"], "超声心动图")
            self.assertIn("经胸超声心动图", tte["aliases"])
            treatment = next(node for node in nodes if node["entityType"] == "TreatmentPlan")
            self.assertIn("植入", treatment["aliases"])
            self.assertTrue(
                any(
                    node["entityType"] == "Evidence"
                    and node.get("segment_id") == "SEG-TB-UNANCHORED"
                    for node in nodes
                )
            )
            self.assertTrue(any(node["entityType"] == "Symptom" and node["name"] == "静息性呼吸困难" for node in nodes))
            self.assertTrue(any(node["entityType"] == "Sign" and node["name"] == "第三心音" for node in nodes))
            symptom_code = next(node["code"] for node in nodes if node["entityType"] == "Symptom" and node["name"] == "静息性呼吸困难")
            sign_code = next(node["code"] for node in nodes if node["entityType"] == "Sign" and node["name"] == "第三心音")
            self.assertTrue(any(rel["relationType"] == "has_symptom" and rel["target_code"] == symptom_code for rel in relations))
            self.assertTrue(any(rel["relationType"] == "has_sign" and rel["target_code"] == sign_code for rel in relations))
            self.assertTrue(any(node["entityType"] == "RiskFactor" and node["name"] == "家族史" for node in nodes))
            self.assertTrue(any(node["entityType"] == "DifferentialDiagnosis" and node["name"] == "高血压性心脏病" for node in nodes))
            risk_factor_code = next(node["code"] for node in nodes if node["entityType"] == "RiskFactor" and node["name"] == "家族史")
            ddx_code = next(node["code"] for node in nodes if node["entityType"] == "DifferentialDiagnosis" and node["name"] == "高血压性心脏病")
            self.assertTrue(any(rel["relationType"] == "has_risk_factor" and rel["target_code"] == risk_factor_code for rel in relations))
            self.assertTrue(any(rel["relationType"] == "differentiates_from" and rel["target_code"] == ddx_code for rel in relations))

    def test_builds_coronary_graph_with_config_scope_lab_and_risk_relations(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            for folder in (
                "00_scope_and_config",
                "01_source_manifest",
                "03_clean_text",
                "04_evidence_and_extraction",
                "05_data_instance",
                "06_quality_audit",
            ):
                (batch / folder).mkdir(parents=True, exist_ok=True)

            (batch / "00_scope_and_config" / "batch_config.json").write_text(
                json.dumps(
                    {
                        "batch_id": "BATCH-CAD-TEST",
                        "scope_type": "category",
                        "scope_target": "冠状动脉粥样硬化性心脏病",
                        "schema_version": "V1.7",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )
            taxonomy_fields = (
                "specialty_code",
                "category_code",
                "subcategory_code",
                "disease_code",
                "name",
                "name_en",
                "aliases",
                "inclusion_status",
                "inclusion_reason",
            )
            taxonomy = [
                {"specialty_code": "SPEC-CARD", "name": "心血管内科", "inclusion_status": "included"},
                {"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CAD", "name": "冠心病", "inclusion_status": "included"},
                {"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CAD", "subcategory_code": "SUB-CARD-CAD-ACS", "name": "ACS谱系", "inclusion_status": "included"},
                {"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CAD", "subcategory_code": "SUB-CARD-CAD-ACS", "disease_code": "DIS-CARD-CAD-STEMI", "name": "ST段抬高型心肌梗死", "name_en": "ST-segment elevation myocardial infarction", "aliases": "STEMI", "inclusion_status": "included"},
            ]
            with (batch / "00_scope_and_config" / "scope_taxonomy.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=taxonomy_fields)
                writer.writeheader()
                writer.writerows(taxonomy)

            vocabulary_fields = (
                "canonical_name",
                "name_en",
                "abbr",
                "aliases",
                "entityType",
                "disease_scope",
                "source",
            )
            vocabulary = [
                {"canonical_name": "ST段抬高型心肌梗死", "abbr": "STEMI", "entityType": "Disease", "disease_scope": "DIS-CARD-CAD-STEMI"},
                {"canonical_name": "心肌肌钙蛋白", "abbr": "cTn", "aliases": "肌钙蛋白", "entityType": "LabTest", "disease_scope": "ALL"},
                {"canonical_name": "GRACE评分", "abbr": "GRACE", "entityType": "RiskStratification", "disease_scope": "ALL"},
                {"canonical_name": "ST段抬高", "aliases": "ST抬高", "entityType": "ExamIndicator", "disease_scope": "ALL"},
            ]
            with (batch / "00_scope_and_config" / "controlled_vocabulary.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=vocabulary_fields)
                writer.writeheader()
                writer.writerows(vocabulary)

            with (batch / "01_source_manifest" / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("document_id", "file_name", "source_type", "sha256", "inclusion_status"),
                )
                writer.writeheader()
                writer.writerow({"document_id": "DOC-STEMI", "file_name": "STEMI指南.pdf", "source_type": "guideline", "sha256": "ABC", "inclusion_status": "included"})

            evidence = [
                {
                    "evidence_id": "EVD-CAD-1",
                    "document_id": "DOC-STEMI",
                    "segment_id": "SEG-CAD-1",
                    "source_name": "STEMI指南.pdf",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "exam",
                    "source_page": 1,
                    "disease_code": "DIS-CARD-CAD-STEMI",
                    "disease_name": "ST段抬高型心肌梗死",
                    "pathway_element": "exam",
                    "evidence_text": "STEMI患者应检测心肌肌钙蛋白，心电图可见相邻导联ST段抬高≥1mm。",
                    "content_hash": "CAD1",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "review_status": "approved",
                },
                {
                    "evidence_id": "EVD-CAD-2",
                    "document_id": "DOC-STEMI",
                    "segment_id": "SEG-CAD-2",
                    "source_name": "STEMI指南.pdf",
                    "source_type": "guideline",
                    "source_version": "2025",
                    "source_section": "risk_stratification",
                    "source_page": 2,
                    "disease_code": "DIS-CARD-CAD-STEMI",
                    "disease_name": "ST段抬高型心肌梗死",
                    "pathway_element": "risk_stratification",
                    "evidence_text": "STEMI患者可采用GRACE评分进行危险分层。",
                    "content_hash": "CAD2",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "review_status": "approved",
                },
            ]
            with (batch / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl").open(
                "w", encoding="utf-8-sig"
            ) as handle:
                for row in evidence:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")

            build_graph_instance(batch)
            nodes = [json.loads(line) for line in (batch / "05_data_instance" / "nodes_final.jsonl").read_text(encoding="utf-8-sig").splitlines()]
            relations = [json.loads(line) for line in (batch / "05_data_instance" / "relations_final.jsonl").read_text(encoding="utf-8-sig").splitlines()]
            self.assertTrue(all(node["scope_target"] == "冠状动脉粥样硬化性心脏病" for node in nodes))
            self.assertTrue(all(rel["scope_target"] == "冠状动脉粥样硬化性心脏病" for rel in relations))
            self.assertTrue(all(node["schema_version"] == "V1.7" for node in nodes))
            self.assertTrue(all(rel["schema_version"] == "V1.7" for rel in relations))
            graph = json.loads((batch / "05_data_instance" / "graph_final.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(graph["schema_version"], "V1.7")
            self.assertTrue(any(rel["relationType"] == "requires_lab_test" for rel in relations))
            self.assertTrue(any(rel["relationType"] == "has_risk_stratification" and rel["target_code"].startswith("RISK-") for rel in relations))
            self.assertTrue(any(node["entityType"] == "ThresholdRule" and node["value"] == 1 for node in nodes))

    def test_fills_missing_disease_definition_from_terminology_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            for folder in (
                "00_scope_and_config",
                "01_source_manifest",
                "03_clean_text",
                "04_evidence_and_extraction",
                "06_quality_audit",
            ):
                (batch / folder).mkdir(parents=True, exist_ok=True)

            (batch / "00_scope_and_config" / "batch_config.json").write_text(
                json.dumps(
                    {
                        "batch_id": "BATCH-CAD-TEST",
                        "scope_type": "category",
                        "scope_target": "冠状动脉粥样硬化性心脏病",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )
            taxonomy_fields = (
                "specialty_code",
                "category_code",
                "subcategory_code",
                "disease_code",
                "name",
                "name_en",
                "aliases",
                "inclusion_status",
                "inclusion_reason",
            )
            taxonomy = [
                {"specialty_code": "SPEC-CARD", "name": "心血管内科", "inclusion_status": "included"},
                {"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CAD", "name": "冠心病", "inclusion_status": "included"},
                {"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CAD", "subcategory_code": "SUB-CARD-CAD-ACS", "name": "ACS谱系", "inclusion_status": "included"},
                {
                    "specialty_code": "SPEC-CARD",
                    "category_code": "CAT-CARD-CAD",
                    "subcategory_code": "SUB-CARD-CAD-ACS",
                    "disease_code": "DIS-CARD-CAD-NSTEMI",
                    "name": "非ST段抬高型心肌梗死",
                    "name_en": "Non-ST-segment elevation myocardial infarction",
                    "aliases": "NSTEMI,NSTE-ACS",
                    "inclusion_status": "included",
                },
            ]
            with (batch / "00_scope_and_config" / "scope_taxonomy.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=taxonomy_fields)
                writer.writeheader()
                writer.writerows(taxonomy)

            with (batch / "00_scope_and_config" / "controlled_vocabulary.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("canonical_name", "name_en", "abbr", "aliases", "entityType", "disease_scope", "source"),
                )
                writer.writeheader()

            with (batch / "01_source_manifest" / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("document_id", "file_name", "source_type", "sha256", "inclusion_status"),
                )
                writer.writeheader()

            (batch / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl").write_text(
                "", encoding="utf-8-sig"
            )
            (batch / "03_clean_text" / "textbook_evidence_index.jsonl").write_text(
                "", encoding="utf-8-sig"
            )

            build_graph_instance(batch)
            nodes = [
                json.loads(line)
                for line in (batch / "05_data_instance" / "nodes_final.jsonl")
                .read_text(encoding="utf-8-sig")
                .splitlines()
            ]
            nstemi = next(node for node in nodes if node["code"] == "DIS-CARD-CAD-NSTEMI")
            self.assertIn("非ST段抬高型心肌梗死", nstemi["description"])
            self.assertIn("Non-ST-segment elevation myocardial infarction", nstemi["description"])
            self.assertEqual(nstemi["definition_source_type"], "controlled_vocabulary")


if __name__ == "__main__":
    unittest.main()
