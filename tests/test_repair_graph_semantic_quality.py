import json
import tempfile
import unittest
from pathlib import Path

from scripts.repair_graph_semantic_quality import repair_batch


class RepairGraphSemanticQualityTests(unittest.TestCase):
    def test_repairs_semantic_shell_and_medication_class_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-TEST"
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
                {"id": "N1", "code": "DIS-VTE", "name": "\u9759\u8109\u8840\u6813\u75c7", "entityType": "Disease", **common},
                {"id": "N2", "code": "DDX-GENERIC", "name": "\u9274\u522b\u8bca\u65ad", "entityType": "DifferentialDiagnosis", **common},
                {"id": "N3", "code": "MED-CLASS", "name": "\u6297\u51dd\u836f\u7269", "aliases": ["\u534e\u6cd5\u6797", "\u809d\u7d20"], "entityType": "Medication", **common},
            ]
            relations = [
                {"id": "R1", "source_code": "DIS-VTE", "relationType": "differentiates_from", "target_code": "DDX-GENERIC", "relationCategory": "diagnostic", "batch_id": "BATCH-TEST", "schema_version": "V1.1", "review_status": "approved"},
                {"id": "R2", "source_code": "DDX-GENERIC", "relationType": "supported_by_evidence", "target_code": "EVD-1", "relationCategory": "evidence", "batch_id": "BATCH-TEST", "schema_version": "V1.1", "review_status": "approved"},
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in relations),
                encoding="utf-8-sig",
            )

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
            relation_types = {rel["relationType"] for rel in repaired_relations}
            class_node = next(node for node in repaired_nodes if node["name"] == "\u6297\u51dd\u836f\u7269")

            self.assertEqual(summary["removed_semantic_shell_relations"], 1)
            self.assertNotIn("\u9274\u522b\u8bca\u65ad", names)
            self.assertIn("\u534e\u6cd5\u6797", names)
            self.assertIn("\u809d\u7d20", names)
            self.assertNotIn("\u534e\u6cd5\u6797", class_node["aliases"])
            self.assertIn("has_specific_medication", relation_types)
            self.assertTrue(all("clinical_review_status" in node for node in repaired_nodes))

    def test_repairs_technical_code_used_as_display_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-TEST"
            data_dir = batch / "05_data_instance"
            data_dir.mkdir(parents=True)

            node = {
                "id": "N1",
                "code": "EXAM-TTE",
                "name": "EXAM-TTE",
                "preferred_name": "EXAM-TTE",
                "display_name": "EXAM-TTE",
                "aliases": ["\u7ecf\u80f8\u8d85\u58f0\u5fc3\u52a8\u56fe", "\u8d85\u58f0\u5fc3\u52a8\u56fe"],
                "entityType": "Exam",
                "entityCategory": "diagnostic",
                "schema_version": "V1.5",
                "review_status": "approved",
                "batch_id": "BATCH-TEST",
            }
            (data_dir / "nodes_final.jsonl").write_text(
                json.dumps(node, ensure_ascii=False) + "\n",
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text("", encoding="utf-8-sig")

            summary = repair_batch(batch)

            repaired = json.loads((data_dir / "nodes_final.jsonl").read_text(encoding="utf-8-sig").strip())
            self.assertEqual(summary["repaired_technical_display_name_fields"], 3)
            self.assertEqual(repaired["name"], "\u8d85\u58f0\u5fc3\u52a8\u56fe")
            self.assertEqual(repaired["preferred_name"], "\u8d85\u58f0\u5fc3\u52a8\u56fe")
            self.assertEqual(repaired["display_name"], "\u8d85\u58f0\u5fc3\u52a8\u56fe")
            self.assertIn("TTE", repaired["abbr"])

    def test_adds_treatment_plan_execution_relation(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-TEST"
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
                {"id": "N1", "code": "DIS-VTE", "name": "\u9759\u8109\u8840\u6813\u75c7", "entityType": "Disease", **common},
                {"id": "N2", "code": "PLAN-THROMBOLYSIS", "name": "\u6eb6\u6813\u6cbb\u7597", "entityType": "TreatmentPlan", **common},
                {"id": "N3", "code": "MED-THROMBOLYTIC", "name": "\u6eb6\u6813\u836f\u7269", "entityType": "Medication", **common},
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
                    "evidence_text": "\u9759\u8109\u8840\u6813\u75c7\u91c7\u7528\u6eb6\u6813\u6cbb\u7597\u65f6\uff0c\u53ef\u4f7f\u7528\u5177\u4f53\u6eb6\u6813\u836f\u7269\u3002",
                    "provenance_records_json": [
                        {"evidence_text": "\u9759\u8109\u8840\u6813\u75c7\u91c7\u7528\u6eb6\u6813\u6cbb\u7597\u65f6\uff0c\u53ef\u4f7f\u7528\u5177\u4f53\u6eb6\u6813\u836f\u7269\u3002"}
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

            summary = repair_batch(batch)

            repaired_relations = [
                json.loads(line)
                for line in (data_dir / "relations_final.jsonl").read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            self.assertEqual(summary["added_treatment_plan_execution_relations"], 1)
            self.assertIn(
                ("PLAN-THROMBOLYSIS", "includes_medication", "MED-THROMBOLYTIC"),
                {(rel["source_code"], rel["relationType"], rel["target_code"]) for rel in repaired_relations},
            )

    def test_adds_specific_medications_for_class_without_alias_pollution(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "BATCH-TEST"
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
                {"id": "N1", "code": "MED-STATIN", "name": "\u4ed6\u6c40\u7c7b\u836f\u7269", "aliases": ["\u4ed6\u6c40"], "entityType": "Medication", **common},
            ]
            (data_dir / "nodes_final.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                encoding="utf-8-sig",
            )
            (data_dir / "relations_final.jsonl").write_text("", encoding="utf-8-sig")

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
            self.assertGreaterEqual(summary["added_specific_medication_nodes"], 2)
            self.assertIn("\u963f\u6258\u4f10\u4ed6\u6c40", names)
            self.assertIn("\u745e\u8212\u4f10\u4ed6\u6c40", names)
            self.assertTrue(any(rel["relationType"] == "has_specific_medication" for rel in repaired_relations))


if __name__ == "__main__":
    unittest.main()
