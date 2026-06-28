import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.probe_required_gap_evidence import probe_required_gaps


class ProbeRequiredGapEvidenceTests(unittest.TestCase):
    def test_matches_required_gap_to_guideline_and_candidate_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            coverage = root / "coverage.csv"
            guideline = root / "guideline.jsonl"
            candidate = root / "candidate.csv"

            with coverage.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "disease_code",
                        "disease_name",
                        "pathway_element",
                        "applicability_status",
                        "coverage_status",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "disease_code": "DIS-1",
                        "disease_name": "测试病",
                        "pathway_element": "exam",
                        "applicability_status": "required",
                        "coverage_status": "missing",
                    }
                )

            guideline.write_text(
                json.dumps(
                    {
                        "disease_code": "DIS-1",
                        "disease_name": "测试病",
                        "pathway_element": "exam",
                        "source_section": "exam",
                        "source_name": "测试指南.pdf",
                        "source_page": 3,
                        "evidence_text": "测试病需要心电图和超声心动图检查。",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            with candidate.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "disease_code",
                        "disease_name",
                        "entityType",
                        "entity_name",
                        "entity_code",
                        "relationType",
                        "evidence_text",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "disease_code": "DIS-1",
                        "disease_name": "测试病",
                        "entityType": "Exam",
                        "entity_name": "心电图",
                        "entity_code": "EXAM-1",
                        "relationType": "requires_exam",
                        "evidence_text": "测试病初诊时需要完善心电图检查，并结合超声心动图判断心脏结构和功能。",
                    }
                )

            result = probe_required_gaps(
                coverage_csv=coverage,
                guideline_jsonl_paths=[guideline],
                textbook_jsonl_paths=[],
                candidate_csv_paths=[candidate],
            )

            self.assertEqual(result["summary"]["missing_required_count"], 1)
            row = result["gaps"][0]
            self.assertEqual(row["exact_evidence_count"], 1)
            self.assertEqual(row["candidate_relation_count"], 1)
            self.assertEqual(row["repair_status"], "LOCAL_BACKFILL_CANDIDATE")

    def test_uses_disease_name_fallback_when_code_drift_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            coverage = root / "coverage.csv"
            guideline = root / "guideline.jsonl"

            with coverage.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "disease_code",
                        "disease_name",
                        "pathway_element",
                        "applicability_status",
                        "coverage_status",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "disease_code": "DIS-A",
                        "disease_name": "缺血性心肌病",
                        "pathway_element": "etiology",
                        "applicability_status": "required",
                        "coverage_status": "missing",
                    }
                )

            guideline.write_text(
                json.dumps(
                    {
                        "disease_code": "DIS-B",
                        "disease_name": "缺血性心肌病",
                        "pathway_element": "etiology",
                        "source_section": "etiology",
                        "source_name": "测试指南.pdf",
                        "source_page": 8,
                        "evidence_text": "缺血性心肌病与冠状动脉粥样硬化和心肌缺血相关。",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            result = probe_required_gaps(
                coverage_csv=coverage,
                guideline_jsonl_paths=[guideline],
                textbook_jsonl_paths=[],
                candidate_csv_paths=[],
            )

            row = result["gaps"][0]
            self.assertEqual(row["name_fallback_evidence_count"], 1)
            self.assertEqual(row["repair_status"], "EVIDENCE_MAPPING_REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
