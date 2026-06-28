import json
import tempfile
import unittest
from pathlib import Path

from scripts.merge_foundation_into_sample_batch import merge_foundation_into_batch


class MergeFoundationIntoSampleBatchTests(unittest.TestCase):
    def test_merges_foundation_relations_and_remaps_same_type_name_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            foundation = root / "foundation"
            batch = root / "batch"
            for base in [foundation, batch]:
                (base / "05_data_instance").mkdir(parents=True)
                (base / "04_evidence_and_extraction").mkdir()

            common = {
                "preferred_name": "x",
                "display_name": "x",
                "entityCategory": "临床",
                "schema_version": "V1.4",
                "review_status": "approved",
                "batch_id": "TEST",
            }
            foundation_nodes = [
                {"id": "D1", "code": "DIS-HCM", "name": "肥厚型心肌病", "entityType": "Disease", **common},
                {"id": "S1", "code": "SYM-F", "name": "呼吸困难", "entityType": "Symptom", "aliases": ["气促"], **common},
                {"id": "E1", "code": "EVD-F", "name": "证据", "entityType": "Evidence", "evidence_text": "肥厚型心肌病可出现呼吸困难。", **common},
            ]
            foundation_relations = [
                {"id": "R1", "source_code": "DIS-HCM", "relationType": "has_symptom", "target_code": "SYM-F", "relationCategory": "clinical", "batch_id": "TEST", "schema_version": "V1.4", "review_status": "approved"},
                {"id": "R2", "source_code": "DIS-HCM", "relationType": "supported_by_evidence", "target_code": "EVD-F", "relationCategory": "evidence", "batch_id": "TEST", "schema_version": "V1.4", "review_status": "approved"},
            ]
            batch_nodes = [
                {"id": "D1", "code": "DIS-HCM", "name": "肥厚型心肌病", "entityType": "Disease", **common},
                {"id": "S2", "code": "SYM-BATCH", "name": "呼吸困难", "entityType": "Symptom", "aliases": ["喘憋"], **common},
            ]
            batch_relations = []
            for base, nodes, rels in [
                (foundation, foundation_nodes, foundation_relations),
                (batch, batch_nodes, batch_relations),
            ]:
                (base / "05_data_instance" / "nodes_final.jsonl").write_text(
                    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in nodes),
                    encoding="utf-8-sig",
                )
                (base / "05_data_instance" / "relations_final.jsonl").write_text(
                    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rels),
                    encoding="utf-8-sig",
                )

            summary = merge_foundation_into_batch(foundation, batch)

            self.assertEqual(summary["added_node_count"], 1)
            self.assertEqual(summary["added_relation_count"], 2)
            merged_nodes = [
                json.loads(line)
                for line in (batch / "05_data_instance" / "nodes_final.jsonl").read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            merged_relations = [
                json.loads(line)
                for line in (batch / "05_data_instance" / "relations_final.jsonl").read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            symptom_nodes = [node for node in merged_nodes if node["entityType"] == "Symptom" and node["name"] == "呼吸困难"]
            self.assertEqual(len(symptom_nodes), 1)
            self.assertEqual(symptom_nodes[0]["code"], "SYM-BATCH")
            symptom_rel = next(rel for rel in merged_relations if rel["relationType"] == "has_symptom")
            self.assertEqual(symptom_rel["target_code"], "SYM-BATCH")


if __name__ == "__main__":
    unittest.main()
