import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.extract_guideline_evidence import extract_guideline_evidence


class ExtractGuidelineEvidenceTests(unittest.TestCase):
    def test_extracts_only_explicitly_disease_anchored_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            (batch / "00_scope_and_config").mkdir(parents=True)
            (batch / "01_source_manifest").mkdir()
            (batch / "03_clean_text").mkdir()
            vocabulary_fields = (
                "canonical_name",
                "name_en",
                "abbr",
                "aliases",
                "entityType",
                "disease_scope",
                "source",
            )
            with (batch / "00_scope_and_config" / "controlled_vocabulary.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=vocabulary_fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "canonical_name": "肥厚型心肌病",
                        "name_en": "Hypertrophic cardiomyopathy",
                        "abbr": "HCM",
                        "aliases": "肥厚性心肌病",
                        "entityType": "Disease",
                        "disease_scope": "DIS-CARD-CM-HCM",
                        "source": "test",
                    }
                )

            manifest_fields = (
                "batch_id",
                "document_id",
                "file_name",
                "source_type",
                "source_version",
                "extension",
                "inclusion_status",
            )
            with (batch / "01_source_manifest" / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=manifest_fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "batch_id": "BATCH-TEST",
                        "document_id": "DOC-GUIDE",
                        "file_name": "HCM指南2025.pdf",
                        "source_type": "guideline",
                        "source_version": "2025",
                        "extension": ".pdf",
                        "inclusion_status": "included",
                    }
                )

            (batch / "03_clean_text" / "DOC-GUIDE.clean.txt").write_text(
                "<<<DOCUMENT document_id=DOC-GUIDE>>>\n"
                "<<<PAGE page=1 class=body>>>\n"
                "<<<SECTION section_id=PAGE1 title=PAGE_1>>>\n"
                "肥厚型心肌病是一类心肌肥厚性疾病。\n\n"
                "第四章　动脉粥样硬化和冠状动脉粥样硬化性心脏病 . . . . . . . . . . . 227 第三节　慢性冠状动脉综合征 . . . . . . . . . . . 232 ACS . . . . . . . . . e816\n\n"
                "推荐肥厚型心肌病患者进行超声心动图检查（Ⅰ，B）。\n\n"
                "参考文献 Smith J, et al. Hypertrophic cardiomyopathy. Journal 2020. doi:10.1/test.\n\n"
                "23. Maron BJ, et al. Hypertrophic cardiomyopathy. Circulation 2021;143:1-20. doi:10.1/example.\n\n"
                "普通心力衰竭患者可使用利尿剂。\n",
                encoding="utf-8-sig",
            )

            summary = extract_guideline_evidence(batch)
            self.assertEqual(summary["evidence_count"], 2)
            rows = [
                json.loads(line)
                for line in (batch / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl")
                .read_text(encoding="utf-8-sig")
                .splitlines()
            ]
            self.assertTrue(all(row["disease_code"] == "DIS-CARD-CM-HCM" for row in rows))
            recommendation = next(row for row in rows if "推荐" in row["evidence_text"])
            self.assertEqual(recommendation["recommendation_class"], "Ⅰ")
            self.assertEqual(recommendation["evidence_level"], "B")

    def test_classifies_coronary_pathway_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            (batch / "00_scope_and_config").mkdir(parents=True)
            (batch / "01_source_manifest").mkdir()
            (batch / "03_clean_text").mkdir()
            vocabulary_fields = (
                "canonical_name",
                "name_en",
                "abbr",
                "aliases",
                "entityType",
                "disease_scope",
                "source",
            )
            with (batch / "00_scope_and_config" / "controlled_vocabulary.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=vocabulary_fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "canonical_name": "ST段抬高型心肌梗死",
                        "name_en": "ST-segment elevation myocardial infarction",
                        "abbr": "STEMI",
                        "aliases": "ST抬高心梗",
                        "entityType": "Disease",
                        "disease_scope": "DIS-CARD-CAD-STEMI",
                        "source": "test",
                    }
                )

            with (batch / "01_source_manifest" / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=(
                        "batch_id",
                        "document_id",
                        "file_name",
                        "source_type",
                        "source_version",
                        "extension",
                        "inclusion_status",
                    ),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "batch_id": "BATCH-TEST",
                        "document_id": "DOC-STEMI",
                        "file_name": "STEMI指南.pdf",
                        "source_type": "guideline",
                        "source_version": "2025",
                        "extension": ".pdf",
                        "inclusion_status": "included",
                    }
                )
            (batch / "03_clean_text" / "DOC-STEMI.clean.txt").write_text(
                "<<<PAGE page=1 class=body>>>\n"
                "STEMI患者出现持续胸痛时应尽快评估。\n\n"
                "STEMI患者应检测心肌肌钙蛋白并行心电图检查。\n\n"
                "STEMI患者GRACE评分>140属于高危。\n\n"
                "STEMI患者发病12 h内应优先行PCI再灌注治疗（Ⅰ，A）。\n",
                encoding="utf-8-sig",
            )

            extract_guideline_evidence(batch)
            rows = [
                json.loads(line)
                for line in (batch / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl")
                .read_text(encoding="utf-8-sig")
                .splitlines()
            ]
            by_text = {row["evidence_text"]: row["pathway_element"] for row in rows}
            self.assertEqual(by_text["STEMI患者出现持续胸痛时应尽快评估。"], "symptom_sign")
            self.assertEqual(by_text["STEMI患者应检测心肌肌钙蛋白并行心电图检查。"], "exam")
            self.assertEqual(by_text["STEMI患者GRACE评分>140属于高危。"], "risk_stratification")
            self.assertEqual(by_text["STEMI患者发病12 h内应优先行PCI再灌注治疗（Ⅰ，A）。"], "treatment_plan")


if __name__ == "__main__":
    unittest.main()
