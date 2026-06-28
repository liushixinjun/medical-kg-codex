import json
import tempfile
import unittest
from pathlib import Path

from scripts.apply_evidence_backfill_candidates import apply_candidate_rows_to_batch


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8-sig")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


class ApplyEvidenceBackfillCandidatesTests(unittest.TestCase):
    def test_groups_duplicate_accepted_rows_into_one_relation_with_unique_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_dir = Path(temp_dir)
            data_dir = batch_dir / "05_data_instance"
            write_jsonl(
                data_dir / "nodes_final.jsonl",
                [
                    {"code": "DIS-1", "name": "二尖瓣狭窄", "entityType": "Disease", "schema_version": "V1.4", "batch_id": "BATCH-1", "scope_type": "specialty", "scope_target": "心血管内科"},
                    {"code": "MED-1", "name": "抗凝药物", "entityType": "Medication", "schema_version": "V1.4"},
                ],
            )
            write_jsonl(data_dir / "relations_final.jsonl", [])

            rows = [
                {
                    "classification": "ACCEPT_CANDIDATE",
                    "disease_code": "DIS-1",
                    "disease_name": "二尖瓣狭窄",
                    "entity_code": "MED-1",
                    "entity_name": "抗凝药物",
                    "entityType": "Medication",
                    "relationType": "treated_by_medication",
                    "evidence_code": "EVD-1",
                    "evidence_text": "合并中重度二尖瓣狭窄时可选择华法林抗凝治疗。",
                    "line_number": "100",
                },
                {
                    "classification": "ACCEPT_CANDIDATE",
                    "disease_code": "DIS-1",
                    "disease_name": "二尖瓣狭窄",
                    "entity_code": "MED-1",
                    "entity_name": "抗凝药物",
                    "entityType": "Medication",
                    "relationType": "treated_by_medication",
                    "evidence_code": "EVD-1",
                    "evidence_text": "合并中重度二尖瓣狭窄时可选择华法林抗凝治疗。",
                    "line_number": "100",
                },
            ]

            summary = apply_candidate_rows_to_batch(batch_dir, rows)
            relations = read_jsonl(data_dir / "relations_final.jsonl")

            self.assertEqual(summary["added_relations"], 1)
            self.assertEqual(summary["skipped_existing_relations"], 0)
            self.assertEqual(len(relations), 1)
            self.assertEqual(relations[0]["source_code"], "DIS-1")
            self.assertEqual(relations[0]["target_code"], "MED-1")
            self.assertEqual(relations[0]["evidence_count"], 1)
            self.assertEqual(relations[0]["clinical_review_status"], "pending_clinical_review")
            self.assertFalse(relations[0]["formal_cdss_ready"])

    def test_skips_existing_relation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_dir = Path(temp_dir)
            data_dir = batch_dir / "05_data_instance"
            write_jsonl(
                data_dir / "nodes_final.jsonl",
                [
                    {"code": "DIS-1", "name": "急性心力衰竭", "entityType": "Disease", "schema_version": "V1.4"},
                    {"code": "MED-1", "name": "硝酸酯类药物", "entityType": "Medication", "schema_version": "V1.4"},
                ],
            )
            write_jsonl(
                data_dir / "relations_final.jsonl",
                [{"id": "REL-OLD", "source_code": "DIS-1", "relationType": "treated_by_medication", "target_code": "MED-1"}],
            )

            rows = [
                {
                    "classification": "ACCEPT_CANDIDATE",
                    "disease_code": "DIS-1",
                    "entity_code": "MED-1",
                    "relationType": "treated_by_medication",
                    "evidence_code": "EVD-2",
                    "evidence_text": "硝酸甘油主要用于高血压急症伴急性心力衰竭。",
                }
            ]

            summary = apply_candidate_rows_to_batch(batch_dir, rows)

            self.assertEqual(summary["added_relations"], 0)
            self.assertEqual(summary["skipped_existing_relations"], 1)
            self.assertEqual(len(read_jsonl(data_dir / "relations_final.jsonl")), 1)


if __name__ == "__main__":
    unittest.main()
