import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.extract_guideline_evidence import _pathway_element, extract_guideline_evidence


class ExtractGuidelineEvidenceTests(unittest.TestCase):
    def test_classifies_real_chinese_pathway_terms(self):
        examples = {
            "主动脉瓣狭窄的临床表现包括呼吸困难、胸痛和晕厥。": "symptom_sign",
            "超声心动图是评估主动脉瓣狭窄严重程度的主要检查。": "exam",
            "重度主动脉瓣狭窄出现症状时推荐行瓣膜置换或介入治疗。": "treatment_plan",
            "主动脉瓣狭窄需与肥厚型心肌病进行鉴别诊断。": "diagnosis_criteria",
            "退行性钙化是老年主动脉瓣狭窄的重要病因。": "etiology",
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assertEqual(_pathway_element(text), expected)

    def test_explicit_etiology_heading_wins_over_pathophysiology_terms(self):
        text = (
            "【病因】 主动脉瓣反流主要由主动脉瓣膜本身病变、主动脉根部疾病所致。"
            "主动脉瓣反流使左心室容量负荷过度而扩大，产生相对性二尖瓣关闭不全。"
        )
        self.assertEqual(_pathway_element(text), "etiology")

    def test_extracts_docx_clean_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            (batch / "00_scope_and_config").mkdir(parents=True)
            (batch / "01_source_manifest").mkdir()
            (batch / "03_clean_text").mkdir()
            fields = ("canonical_name", "name_en", "abbr", "aliases", "entityType", "disease_scope", "source")
            with (batch / "00_scope_and_config" / "controlled_vocabulary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "canonical_name": "心力衰竭",
                    "name_en": "Heart failure",
                    "abbr": "HF",
                    "aliases": "心衰",
                    "entityType": "Disease",
                    "disease_scope": "DIS-CARD-HF",
                    "source": "test",
                })
            with (batch / "01_source_manifest" / "source_documents_manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=("batch_id", "document_id", "file_name", "source_type", "extension", "inclusion_status"))
                writer.writeheader()
                writer.writerow({
                    "batch_id": "BATCH-HF",
                    "document_id": "DOC-TEXTBOOK",
                    "file_name": "内科学.docx",
                    "source_type": "authoritative_textbook",
                    "extension": ".docx",
                    "inclusion_status": "included",
                })
            (batch / "03_clean_text" / "DOC-TEXTBOOK.clean.txt").write_text(
                "<<<DOCUMENT document_id=DOC-TEXTBOOK>>>\n"
                "<<<SECTION section_id=SEG-DOC-TEXTBOOK-P00001-00001 title=Body Text>>>\n"
                "心力衰竭是各种心脏疾病导致心功能异常的临床综合征。\n",
                encoding="utf-8-sig",
            )

            summary = extract_guideline_evidence(batch)

            self.assertEqual(summary["document_count"], 1)
            self.assertEqual(summary["document_with_evidence_count"], 1)
            self.assertEqual(summary["evidence_count"], 1)
            rows = [
                json.loads(line)
                for line in (batch / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl")
                .read_text(encoding="utf-8-sig")
                .splitlines()
            ]
            self.assertEqual(rows[0]["source_page"], "N/A")

    def test_extracts_disease_anchors_from_scope_taxonomy(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            (batch / "00_scope_and_config").mkdir(parents=True)
            (batch / "01_source_manifest").mkdir()
            (batch / "03_clean_text").mkdir()

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
                        "canonical_name": "主动脉瓣置换术",
                        "name_en": "Aortic valve replacement",
                        "abbr": "AVR",
                        "aliases": "",
                        "entityType": "Procedure",
                        "disease_scope": "PROC-CARD-VHD-AVR",
                        "source": "test",
                    }
                )

            with (batch / "00_scope_and_config" / "scope_taxonomy.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("disease_code", "name", "name_en", "aliases"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "disease_code": "DIS-CARD-VHD-AS",
                        "name": "主动脉瓣狭窄",
                        "name_en": "Aortic stenosis",
                        "aliases": "AS,主动脉瓣口狭窄",
                    }
                )

            with (batch / "01_source_manifest" / "source_documents_manifest.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("batch_id", "document_id", "file_name", "source_type", "source_version", "extension", "inclusion_status"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "batch_id": "BATCH-VHD",
                        "document_id": "DOC-VHD",
                        "file_name": "主动脉瓣狭窄指南2025.pdf",
                        "source_type": "guideline",
                        "source_version": "2025",
                        "extension": ".pdf",
                        "inclusion_status": "included",
                    }
                )
            (batch / "03_clean_text" / "DOC-VHD.clean.txt").write_text(
                "<<<PAGE page=1 class=body>>>\n"
                "主动脉瓣狭窄患者出现症状或左心室功能下降时，应评估瓣膜介入或外科治疗适应证。\n",
                encoding="utf-8-sig",
            )

            summary = extract_guideline_evidence(batch)

            self.assertEqual(summary["document_count"], 1)
            self.assertEqual(summary["document_with_evidence_count"], 1)
            self.assertEqual(summary["evidence_count"], 1)
            self.assertEqual(summary["evidence_by_disease"], {"DIS-CARD-VHD-AS": 1})

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
