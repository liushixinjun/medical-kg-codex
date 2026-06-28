import tempfile
import unittest
from pathlib import Path

from scripts.enrich_foundation_full_textbook_backfill import (
    build_counter_evidence_register,
    context_lines_for_disease,
    extract_terms_from_context,
    read_textbook_lines,
)


class FullTextbookBackfillTests(unittest.TestCase):
    def test_full_book_context_includes_cross_chapter_vte_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            foundation_dir = Path(tmp)
            clean_dir = foundation_dir / "03_clean_text"
            clean_dir.mkdir(parents=True)
            text_path = clean_dir / "DOC-CF62B75AEC93F1A6.clean.txt"
            text_path.write_text(
                "\n".join(
                    [
                        "第一篇 呼吸系统疾病",
                        "肺血栓栓塞症常由深静脉血栓形成引起，属于静脉血栓栓塞症（VTE）。",
                        "患者可出现呼吸困难、胸痛、咯血、晕厥，D-二聚体和CT肺动脉造影有助于诊断，应进行抗凝治疗。",
                        "第三篇 循环系统疾病",
                        "其他内容。",
                    ]
                ),
                encoding="utf-8-sig",
            )

            lines = read_textbook_lines(foundation_dir)
            disease = {
                "disease_code": "DIS-CARD-VTE",
                "disease_name": "静脉血栓症",
                "aliases": "静脉血栓栓塞症,VTE,肺血栓栓塞症",
            }

            contexts = context_lines_for_disease(lines, disease, window=1, max_lines=20)
            context_text = "\n".join(text for _, text in contexts)
            mentions = extract_terms_from_context(context_text)

            self.assertIn("肺血栓栓塞症", context_text)
            self.assertIn(("Symptom", "呼吸困难"), mentions)
            self.assertIn(("Symptom", "胸痛"), mentions)
            self.assertIn(("LabTest", "D-二聚体"), mentions)
            self.assertIn(("Exam", "CT肺动脉造影"), mentions)
            self.assertIn(("TreatmentPlan", "抗凝治疗"), mentions)

    def test_counter_evidence_register_marks_source_hits_per_pathway_element(self):
        lines = [
            (1, "肺血栓栓塞症常由深静脉血栓形成引起，属于静脉血栓栓塞症（VTE）。"),
            (2, "患者可出现呼吸困难、胸痛、咯血、晕厥，D-二聚体和CT肺动脉造影有助于诊断，应进行抗凝治疗。"),
        ]
        diseases = [
            {
                "disease_code": "DIS-CARD-VTE",
                "disease_name": "静脉血栓症",
                "aliases": "静脉血栓栓塞症,VTE,肺血栓栓塞症",
            },
            {
                "disease_code": "DIS-CARD-NOT-COVERED",
                "disease_name": "不存在的测试病",
                "aliases": "",
            },
        ]

        rows = build_counter_evidence_register(diseases, lines, window=1, max_lines=20)
        by_key = {(row["disease_code"], row["pathway_element"]): row for row in rows}

        self.assertGreater(int(by_key[("DIS-CARD-VTE", "symptom")]["source_hit_count"]), 0)
        self.assertGreater(int(by_key[("DIS-CARD-VTE", "lab_test")]["source_hit_count"]), 0)
        self.assertGreater(int(by_key[("DIS-CARD-VTE", "exam")]["source_hit_count"]), 0)
        self.assertGreater(int(by_key[("DIS-CARD-VTE", "treatment_plan")]["source_hit_count"]), 0)
        self.assertEqual(
            by_key[("DIS-CARD-NOT-COVERED", "symptom")]["source_hit_status"],
            "SOURCE_DOES_NOT_COVER",
        )


if __name__ == "__main__":
    unittest.main()
