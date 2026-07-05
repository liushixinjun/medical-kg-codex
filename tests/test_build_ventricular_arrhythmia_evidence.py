import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_ventricular_arrhythmia_evidence import build_foundation


class BuildVentricularArrhythmiaEvidenceTests(unittest.TestCase):
    def test_builds_taxonomy_vocabulary_and_textbook_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            for folder in ("00_scope_and_config", "01_source_manifest", "03_clean_text"):
                (batch / folder).mkdir(parents=True, exist_ok=True)

            config = {
                "batch_id": "BATCH-VA-SCD-TEST",
                "specialty": "心血管内科",
                "scope_type": "disease",
                "scope_target": "室性心律失常及心脏性猝死",
            }
            (batch / "00_scope_and_config" / "batch_config.json").write_text(
                json.dumps(config, ensure_ascii=False), encoding="utf-8-sig"
            )
            with (batch / "01_source_manifest" / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=(
                        "document_id",
                        "file_name",
                        "source_type",
                        "inclusion_status",
                        "extension",
                    ),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "document_id": "DOC-TB",
                        "file_name": "《内科学（第10版）》.pdf",
                        "source_type": "authoritative_textbook",
                        "inclusion_status": "included",
                        "extension": ".pdf",
                    }
                )
            clean_text = (
                "<<<PAGE page=1 class=body>>>\n"
                "第六节 室性心律失常 . . . . . 102 心脏性猝死 . . . . . 110\n\n"
                "室性心律失常包括室性早搏、非持续性室性心动过速、持续性室性心动过速和心室颤动。\n"
                "长QT间期综合征患者可发生尖端扭转型室性心动过速和晕厥。\n"
                "心脏性猝死的抢救应尽早心肺复苏和电除颤，部分高危患者需要ICD治疗。\n"
            )
            (batch / "03_clean_text" / "DOC-TB.clean.txt").write_text(clean_text, encoding="utf-8-sig")

            summary = build_foundation(batch)
            self.assertEqual(summary["disease_count"], 12)
            self.assertGreaterEqual(summary["textbook_evidence_count"], 3)

            with (batch / "00_scope_and_config" / "scope_taxonomy.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                taxonomy = list(csv.DictReader(handle))
            disease_names = {row["name"] for row in taxonomy if row.get("disease_code")}
            self.assertIn("持续性室性心动过速", disease_names)
            self.assertIn("心室扑动与心室颤动", disease_names)
            self.assertIn("心脏性猝死", disease_names)
            self.assertIn("Brugada综合征", disease_names)

            with (batch / "00_scope_and_config" / "controlled_vocabulary.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                vocabulary = list(csv.DictReader(handle))
            by_name = {row["canonical_name"]: row for row in vocabulary}
            self.assertEqual(by_name["抗心律失常药物"]["entityType"], "Medication")
            self.assertNotIn("胺碘酮", by_name["抗心律失常药物"]["aliases"])
            self.assertEqual(by_name["胺碘酮"]["entityType"], "Medication")
            self.assertEqual(by_name["利多卡因"]["entityType"], "Medication")
            self.assertEqual(by_name["钾剂"]["entityType"], "Medication")
            self.assertEqual(by_name["氯化钾"]["entityType"], "Medication")
            self.assertEqual(by_name["电除颤"]["entityType"], "Procedure")
            self.assertEqual(by_name["宽QRS波心动过速"]["entityType"], "ExamIndicator")
            self.assertEqual(by_name["晕厥"]["entityType"], "Symptom")
            self.assertEqual(by_name["无脉搏"]["entityType"], "Sign")

            evidence_text = (batch / "03_clean_text" / "textbook_evidence_index.jsonl").read_text(
                encoding="utf-8-sig"
            )
            self.assertNotIn("第六节 室性心律失常", evidence_text)
            self.assertIn("心脏性猝死的抢救", evidence_text)


if __name__ == "__main__":
    unittest.main()
