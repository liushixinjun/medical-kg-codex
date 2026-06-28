import json
import csv
import tempfile
import unittest
from pathlib import Path

from scripts.build_cardiomyopathy_evidence import build_foundation


class BuildCardiomyopathyEvidenceTests(unittest.TestCase):
    def test_indexes_textbook_sections_and_stops_before_myocarditis(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            clean_dir = batch / "03_clean_text"
            config_dir = batch / "00_scope_and_config"
            clean_dir.mkdir(parents=True)
            config_dir.mkdir()
            source = clean_dir / "DOC-BOOK.clean.txt"
            source.write_text(
                "<<<DOCUMENT document_id=DOC-BOOK>>>\n"
                "<<<PAGE page=10 class=body>>>\n"
                "<<<SECTION section_id=PAGE10 title=PAGE_10>>>\n"
                "第一节 | 肥厚型心肌病\n肥厚型心肌病定义。\n【诊断】超声心动图。\n"
                "<<<PAGE page=11 class=body>>>\n"
                "<<<SECTION section_id=PAGE11 title=PAGE_11>>>\n"
                "第二节 | 扩张型心肌病\n扩张型心肌病定义。\n"
                "第六节 | 心肌炎\n心肌炎内容。\n",
                encoding="utf-8-sig",
            )

            summary = build_foundation(
                batch_dir=batch,
                textbook_document_id="DOC-BOOK",
                textbook_start_page=10,
                textbook_end_page=11,
            )
            self.assertEqual(summary["textbook_disease_count"], 2)
            rows = [
                json.loads(line)
                for line in (clean_dir / "textbook_evidence_index.jsonl")
                .read_text(encoding="utf-8-sig")
                .splitlines()
            ]
            self.assertEqual({row["disease_code"] for row in rows}, {"DIS-CARD-CM-HCM", "DIS-CARD-CM-DCM"})
            self.assertFalse(any("心肌炎内容" in row["evidence_text"] for row in rows))
            self.assertTrue((config_dir / "scope_taxonomy.csv").is_file())
            self.assertTrue((config_dir / "controlled_vocabulary.csv").is_file())
            with (config_dir / "controlled_vocabulary.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                vocabulary = list(csv.DictReader(handle))
            acm = next(row for row in vocabulary if row["canonical_name"] == "致心律失常性心肌病")
            amyloid = next(row for row in vocabulary if row["canonical_name"] == "淀粉样变心肌病")
            self.assertEqual(acm["abbr"], "ACM")
            self.assertEqual(amyloid["abbr"], "")
            vocabulary_by_name = {row["canonical_name"]: row for row in vocabulary}
            for symptom_name in ("静息性呼吸困难", "夜间阵发性呼吸困难", "端坐呼吸", "耐力下降", "胸闷", "头晕", "黑矇"):
                self.assertEqual(vocabulary_by_name[symptom_name]["entityType"], "Symptom")
            for sign_name in ("第三心音", "第四心音", "奔马律", "心音减弱", "肺水肿", "胸腔积液"):
                self.assertEqual(vocabulary_by_name[sign_name]["entityType"], "Sign")
            self.assertEqual(vocabulary_by_name["家族史"]["entityType"], "RiskFactor")
            self.assertEqual(vocabulary_by_name["基因突变"]["entityType"], "RiskFactor")
            self.assertEqual(vocabulary_by_name["高血压性心脏病"]["entityType"], "DifferentialDiagnosis")
            self.assertEqual(vocabulary_by_name["冠心病"]["entityType"], "DifferentialDiagnosis")


if __name__ == "__main__":
    unittest.main()
