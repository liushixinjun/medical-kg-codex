import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_graph_instance import audit_graph
from scripts.build_graph_instance import build_graph_instance
from scripts.repair_graph_semantic_quality import repair_batch


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


class HeartFailureGraphRepairTests(unittest.TestCase):
    def test_build_graph_canonicalizes_clinical_problem_to_allowed_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-CARD-HF-TEST"
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
                        "batch_id": "BATCH-CARD-HF-TEST",
                        "scope_type": "category",
                        "scope_target": "心力衰竭",
                        "schema_version": "V1.7",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )
            with (batch / "00_scope_and_config" / "scope_taxonomy.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=(
                        "specialty_code",
                        "category_code",
                        "subcategory_code",
                        "disease_code",
                        "name",
                        "name_en",
                        "aliases",
                        "inclusion_status",
                    ),
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {"specialty_code": "SPEC-CARD", "name": "心血管内科", "inclusion_status": "included"},
                        {
                            "specialty_code": "SPEC-CARD",
                            "category_code": "CAT-CARD-HF",
                            "name": "心力衰竭",
                            "inclusion_status": "included",
                        },
                        {
                            "specialty_code": "SPEC-CARD",
                            "category_code": "CAT-CARD-HF",
                            "subcategory_code": "SUB-CARD-HF",
                            "name": "心力衰竭谱系",
                            "inclusion_status": "included",
                        },
                        {
                            "specialty_code": "SPEC-CARD",
                            "category_code": "CAT-CARD-HF",
                            "subcategory_code": "SUB-CARD-HF",
                            "disease_code": "DIS-CARD-HF",
                            "name": "心力衰竭",
                            "aliases": "HF",
                            "inclusion_status": "included",
                        },
                    ]
                )

            with (batch / "00_scope_and_config" / "controlled_vocabulary.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("canonical_name", "name_en", "abbr", "aliases", "entityType", "disease_scope", "source"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "canonical_name": "利尿剂抵抗",
                        "name_en": "Diuretic resistance",
                        "abbr": "DR",
                        "aliases": "利尿剂反应不佳",
                        "entityType": "ClinicalProblem",
                        "disease_scope": "ALL",
                        "source": "test",
                    }
                )

            with (batch / "01_source_manifest" / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("document_id", "file_name", "source_type", "sha256", "inclusion_status"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "document_id": "DOC-HF",
                        "file_name": "心力衰竭指南.pdf",
                        "source_type": "guideline",
                        "sha256": "abc",
                        "inclusion_status": "included",
                    }
                )

            write_jsonl(
                batch / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl",
                [
                    {
                        "evidence_id": "EVD-HF-1",
                        "document_id": "DOC-HF",
                        "segment_id": "SEG-HF-1",
                        "source_name": "心力衰竭指南.pdf",
                        "source_type": "guideline",
                        "source_version": "2024",
                        "source_section": "治疗",
                        "source_page": 1,
                        "disease_code": "DIS-CARD-HF",
                        "disease_name": "心力衰竭",
                        "pathway_element": "treatment_plan",
                        "evidence_text": "心力衰竭患者可发生利尿剂抵抗，应识别利尿剂反应不佳。",
                        "content_hash": "HASH-HF-1",
                        "recommendation_class": "N/A",
                        "evidence_level": "N/A",
                        "review_status": "approved",
                    }
                ],
            )
            (batch / "03_clean_text" / "textbook_evidence_index.jsonl").write_text("", encoding="utf-8-sig")

            build_graph_instance(batch)
            nodes = [
                json.loads(line)
                for line in (batch / "05_data_instance" / "nodes_final.jsonl")
                .read_text(encoding="utf-8-sig")
                .splitlines()
                if line.strip()
            ]

            self.assertFalse(any(node["entityType"] == "ClinicalProblem" for node in nodes))
            self.assertTrue(any(node["entityType"] == "Complication" and node["name"] == "利尿剂抵抗" for node in nodes))

    def test_repair_adds_hf_specific_drugs_pathway_and_review_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-CARD-HF-TEST"
            data_dir = batch / "05_data_instance"
            (batch / "06_quality_audit").mkdir(parents=True)
            data_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "治疗",
                "schema_version": "V1.7",
                "review_status": "approved",
                "batch_id": "BATCH-CARD-HF-TEST",
            }
            nodes = [
                {"id": "N-DIS", "code": "DIS-CARD-HF-HFrEF", "name": "射血分数降低的心力衰竭", "entityType": "Disease", **common},
                {"id": "N-PLAN", "code": "PLAN-HFrEF", "name": "射血分数降低的心力衰竭治疗方案", "entityType": "TreatmentPlan", **common},
                {"id": "N-LOOP", "code": "MED-LOOP", "name": "袢利尿剂", "aliases": ["呋塞米", "托拉塞米", "布美他尼"], "entityType": "Medication", **common},
                {"id": "N-ARNI", "code": "MED-ARNI", "name": "血管紧张素受体脑啡肽酶抑制剂", "aliases": ["沙库巴曲缬沙坦"], "abbr": "ARNI", "entityType": "Medication", **common},
                {"id": "N-SGLT2", "code": "MED-SGLT2", "name": "钠-葡萄糖协同转运蛋白2抑制剂", "aliases": ["达格列净", "恩格列净"], "abbr": "SGLT2i", "entityType": "Medication", **common},
            ]
            relations = [
                {
                    "id": "R-PLAN",
                    "source_code": "DIS-CARD-HF-HFrEF",
                    "relationType": "has_treatment_plan",
                    "target_code": "PLAN-HFrEF",
                    "relationCategory": "therapeutic",
                    "batch_id": "BATCH-CARD-HF-TEST",
                    "schema_version": "V1.7",
                    "review_status": "approved",
                    "evidence_text": "射血分数降低的心力衰竭应给予指南指导的治疗方案。",
                    "document_id": "DOC-HF",
                    "segment_id": "SEG-HF-1",
                    "source_name": "心力衰竭指南.pdf",
                    "source_type": "guideline",
                    "source_version": "2024",
                    "source_section": "治疗",
                    "source_page": 1,
                    "guideline_id": "SRC-DOC-HF",
                    "evidence_id": "EVD-HF-1",
                    "recommendation_class": "Ⅰ",
                    "evidence_level": "A",
                    "confidence": 1.0,
                    "provenance_records_json": [],
                },
                {
                    "id": "R-LOOP",
                    "source_code": "DIS-CARD-HF-HFrEF",
                    "relationType": "treated_by_medication",
                    "target_code": "MED-LOOP",
                    "relationCategory": "therapeutic",
                    "batch_id": "BATCH-CARD-HF-TEST",
                    "schema_version": "V1.7",
                    "review_status": "approved",
                    "evidence_text": "有容量负荷过重时可用袢利尿剂。",
                    "document_id": "DOC-HF",
                    "segment_id": "SEG-HF-2",
                    "source_name": "心力衰竭指南.pdf",
                    "source_type": "guideline",
                    "source_version": "2024",
                    "source_section": "治疗",
                    "source_page": 2,
                    "guideline_id": "SRC-DOC-HF",
                    "evidence_id": "EVD-HF-2",
                    "recommendation_class": "Ⅰ",
                    "evidence_level": "C",
                    "confidence": 1.0,
                    "provenance_records_json": [],
                },
            ]
            write_jsonl(data_dir / "nodes_final.jsonl", nodes)
            write_jsonl(data_dir / "relations_final.jsonl", relations)

            summary = repair_batch(batch)
            repaired_nodes = [
                json.loads(line)
                for line in (data_dir / "nodes_final.jsonl").read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            repaired_relations = [
                json.loads(line)
                for line in (data_dir / "relations_final.jsonl").read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            names = {node["name"] for node in repaired_nodes}
            relation_keys = {(rel["source_code"], rel["relationType"], rel["target_code"]) for rel in repaired_relations}
            loop_node = next(node for node in repaired_nodes if node["code"] == "MED-LOOP")
            treated = next(rel for rel in repaired_relations if rel["id"] == "R-LOOP")

            self.assertGreaterEqual(summary["added_specific_medication_nodes"], 5)
            self.assertIn("呋塞米", names)
            self.assertIn("沙库巴曲缬沙坦", names)
            self.assertIn("达格列净", names)
            self.assertNotIn("呋塞米", loop_node["aliases"])
            self.assertTrue(any(rel[1] == "has_specific_medication" for rel in relation_keys))
            self.assertTrue(any(rel[1] == "has_clinical_pathway" and rel[0] == "PLAN-HFrEF" for rel in relation_keys))
            self.assertTrue(any(rel[1] == "has_clinical_pathway" and rel[0] == "DIS-CARD-HF-HFrEF" for rel in relation_keys))
            self.assertIn("applicable_population", treated)
            self.assertIn("exclusion_criteria", treated)
            self.assertIn("dosage", loop_node)
            self.assertIn("drug_interactions", loop_node)

            audit_summary = audit_graph(batch)
            self.assertEqual(audit_summary["treatment_plan_actionability_error_count"], 0)
            self.assertEqual(audit_summary["medication_class_without_specific_count"], 0)
            self.assertEqual(audit_summary["medication_alias_instance_gap_count"], 0)

    def test_audit_does_not_treat_taxonomy_actionability_edge_as_cdss_recommendation(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "治疗",
                "schema_version": "V1.7",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            nodes = [
                {"id": "N1", "code": "PLAN-HF", "name": "心力衰竭治疗方案", "entityType": "TreatmentPlan", **common},
                {"id": "N2", "code": "MED-ARNI", "name": "血管紧张素受体脑啡肽酶抑制剂", "entityType": "Medication", **common},
            ]
            relations = [
                {
                    "id": "R1",
                    "source_code": "PLAN-HF",
                    "relationType": "includes_medication",
                    "target_code": "MED-ARNI",
                    "relationCategory": "taxonomy",
                    "batch_id": "BATCH-TEST",
                    "schema_version": "V1.7",
                    "review_status": "approved",
                    "clinical_review_status": "not_applicable",
                }
            ]
            write_jsonl(data_dir / "nodes_final.jsonl", nodes)
            write_jsonl(data_dir / "relations_final.jsonl", relations)

            audit_summary = audit_graph(batch)

            self.assertEqual(audit_summary["cdss_recommendation_readiness_error_count"], 0)

    def test_repair_disambiguates_duplicate_guideline_display_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-CARD-HF-TEST"
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            common = {
                "preferred_name": "心力衰竭患者利尿剂抵抗诊断及管理中国专家共识.pdf",
                "display_name": "心力衰竭患者利尿剂抵抗诊断及管理中国专家共识.pdf",
                "entityCategory": "证据",
                "schema_version": "V1.7",
                "review_status": "approved",
                "batch_id": "BATCH-CARD-HF-TEST",
                "entityType": "Guideline",
            }
            nodes = [
                {
                    "id": "N1",
                    "code": "SRC-DOC-A",
                    "name": "心力衰竭患者利尿剂抵抗诊断及管理中国专家共识.pdf",
                    "document_id": "DOC-A",
                    "sha256": "AAAA1111",
                    **common,
                },
                {
                    "id": "N2",
                    "code": "SRC-DOC-B",
                    "name": "心力衰竭患者利尿剂抵抗诊断及管理中国专家共识.pdf",
                    "document_id": "DOC-B",
                    "sha256": "BBBB2222",
                    **common,
                },
            ]
            write_jsonl(data_dir / "nodes_final.jsonl", nodes)
            write_jsonl(data_dir / "relations_final.jsonl", [])

            repair_batch(batch)
            repaired_nodes = [
                json.loads(line)
                for line in (data_dir / "nodes_final.jsonl").read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            names = [node["name"] for node in repaired_nodes]

            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(any("DOC-A" in name or "AAAA1111" in name for name in names))
            self.assertTrue(any("DOC-B" in name or "BBBB2222" in name for name in names))

    def test_repair_inherits_required_hf_pathway_from_root_disease_with_source_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-CARD-HF-TEST"
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "临床",
                "schema_version": "V1.7",
                "review_status": "approved",
                "batch_id": "BATCH-CARD-HF-TEST",
            }
            nodes = [
                {"id": "N1", "code": "DIS-CARD-HF", "name": "心力衰竭", "entityType": "Disease", **common},
                {"id": "N2", "code": "DIS-CARD-HF-HFrEF", "name": "射血分数降低的心力衰竭", "entityType": "Disease", **common},
                {"id": "N3", "code": "ETI-HF", "name": "心力衰竭病因", "entityType": "Etiology", **common},
            ]
            relations = [
                {
                    "id": "R1",
                    "source_code": "DIS-CARD-HF",
                    "relationType": "has_etiology",
                    "target_code": "ETI-HF",
                    "relationCategory": "clinical",
                    "batch_id": "BATCH-CARD-HF-TEST",
                    "schema_version": "V1.7",
                    "review_status": "approved",
                    "document_id": "DOC-HF",
                    "segment_id": "SEG-HF",
                    "source_name": "心力衰竭指南.pdf",
                    "source_type": "guideline",
                    "source_version": "2024",
                    "source_section": "病因",
                    "source_page": 1,
                    "evidence_text": "心力衰竭可由多种心血管疾病导致。",
                    "guideline_id": "SRC-DOC-HF",
                    "evidence_id": "EVD-HF",
                    "recommendation_class": "N/A",
                    "evidence_level": "N/A",
                    "confidence": 1.0,
                    "provenance_records_json": [],
                }
            ]
            write_jsonl(data_dir / "nodes_final.jsonl", nodes)
            write_jsonl(data_dir / "relations_final.jsonl", relations)

            summary = repair_batch(batch)
            repaired_relations = [
                json.loads(line)
                for line in (data_dir / "relations_final.jsonl").read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            inherited = [
                rel
                for rel in repaired_relations
                if rel["source_code"] == "DIS-CARD-HF-HFrEF" and rel["relationType"] == "has_etiology"
            ]

            self.assertGreaterEqual(summary["inherited_required_pathway_relations"], 1)
            self.assertEqual(len(inherited), 1)
            self.assertEqual(inherited[0]["target_code"], "ETI-HF")
            self.assertEqual(inherited[0]["source_quality"], "inherited_from_root_heart_failure_with_source_trace")
            self.assertEqual(inherited[0]["evidence_id"], "EVD-HF")


if __name__ == "__main__":
    unittest.main()
