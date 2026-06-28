import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_coronary_evidence import build_foundation


class BuildCoronaryEvidenceTests(unittest.TestCase):
    def test_builds_coronary_taxonomy_vocabulary_and_textbook_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            for folder in ("00_scope_and_config", "01_source_manifest", "03_clean_text"):
                (batch / folder).mkdir(parents=True, exist_ok=True)

            config = {
                "batch_id": "BATCH-CAD-TEST",
                "specialty": "心血管内科",
                "scope_type": "category",
                "scope_target": "冠状动脉粥样硬化性心脏病",
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
                "第四章 动脉粥样硬化和冠状动脉粥样硬化性心脏病 . . . . . 227 "
                "第一节 动脉粥样硬化 . . . . . 227 "
                "第四节 急性冠脉综合征 ACS . . . . . 242 "
                "二、急性ST段抬高型心肌梗死 STEMI . . . . . 247\n\n"
                "冠状动脉粥样硬化性心脏病是指冠状动脉粥样硬化导致管腔狭窄或闭塞引起的心脏病。\n"
                "急性冠脉综合征包括不稳定型心绞痛和急性心肌梗死。\n"
                "ST段抬高型心肌梗死患者应尽早行再灌注治疗。\n"
            )
            (batch / "03_clean_text" / "DOC-TB.clean.txt").write_text(clean_text, encoding="utf-8-sig")

            summary = build_foundation(batch)
            self.assertEqual(summary["disease_count"], 10)
            self.assertGreaterEqual(summary["textbook_evidence_count"], 3)

            with (batch / "00_scope_and_config" / "scope_taxonomy.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                taxonomy = list(csv.DictReader(handle))
            disease_names = {row["name"] for row in taxonomy if row.get("disease_code")}
            self.assertIn("急性心肌梗死", disease_names)
            self.assertIn("ST段抬高型心肌梗死", disease_names)

            with (batch / "00_scope_and_config" / "controlled_vocabulary.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                vocabulary = list(csv.DictReader(handle))
            canonical_names = {row["canonical_name"] for row in vocabulary}
            self.assertIn("经皮冠状动脉介入治疗", canonical_names)
            self.assertIn("心肌肌钙蛋白", canonical_names)
            self.assertNotIn("ACEI/ARB", canonical_names)
            self.assertIn("血管紧张素转换酶抑制剂", canonical_names)
            self.assertIn("血管紧张素Ⅱ受体阻滞剂", canonical_names)
            self.assertIn("氯吡格雷", canonical_names)
            self.assertIn("替格瑞洛", canonical_names)
            self.assertIn("阿托伐他汀", canonical_names)
            vocabulary_by_name = {row["canonical_name"]: row for row in vocabulary}
            self.assertEqual(vocabulary_by_name["血管紧张素转换酶抑制剂"]["abbr"], "ACEI")
            self.assertEqual(vocabulary_by_name["血管紧张素Ⅱ受体阻滞剂"]["abbr"], "ARB")
            self.assertNotIn("氯吡格雷", vocabulary_by_name["P2Y12受体抑制剂"]["aliases"])
            self.assertNotIn("美托洛尔", vocabulary_by_name["β受体拮抗剂"]["aliases"])
            self.assertEqual(vocabulary_by_name["吸烟"]["entityType"], "RiskFactor")
            self.assertEqual(vocabulary_by_name["糖尿病"]["entityType"], "RiskFactor")
            self.assertEqual(vocabulary_by_name["冠状动脉痉挛"]["entityType"], "DifferentialDiagnosis")
            for symptom_name in ("放射痛", "恶心呕吐", "濒死感", "乏力", "晕厥"):
                self.assertEqual(vocabulary_by_name[symptom_name]["entityType"], "Symptom")
            for sign_name in ("低血压", "肺部啰音", "心动过速", "心音低钝", "颈静脉怒张"):
                self.assertEqual(vocabulary_by_name[sign_name]["entityType"], "Sign")

            evidence_text = (batch / "03_clean_text" / "textbook_evidence_index.jsonl").read_text(
                encoding="utf-8-sig"
            )
            self.assertNotIn("第四章 动脉粥样硬化", evidence_text)
            self.assertNotIn("STEMI . . . . . 247", evidence_text)


if __name__ == "__main__":
    unittest.main()
