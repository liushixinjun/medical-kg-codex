import unittest

from scripts.deep_extract_cardiology_textbook import (
    build_evidence_backed_relation,
    extract_mentions,
    merge_aliases,
    relation_id,
)


class DeepExtractCardiologyTextbookTests(unittest.TestCase):
    def test_extracts_clinical_terms_from_textbook_context(self):
        text = "心力衰竭患者可出现劳力性呼吸困难、端坐呼吸，心电图和超声心动图有助于评估，可使用利尿剂治疗。"

        mentions = extract_mentions(text)

        self.assertIn(("Symptom", "劳力性呼吸困难"), mentions)
        self.assertIn(("Symptom", "端坐呼吸"), mentions)
        self.assertIn(("Exam", "心电图"), mentions)
        self.assertIn(("Exam", "超声心动图"), mentions)
        self.assertIn(("Medication", "利尿剂"), mentions)

    def test_normalizes_medication_abbreviation_to_chinese_standard_name(self):
        text = "慢性心力衰竭治疗包括 ACEI、ARB、β受体阻滞剂和利尿剂。"

        mentions = extract_mentions(text)

        self.assertIn(("Medication", "血管紧张素转换酶抑制剂"), mentions)
        self.assertIn(("Medication", "血管紧张素Ⅱ受体拮抗剂"), mentions)
        self.assertNotIn(("Medication", "ACEI"), mentions)
        self.assertNotIn(("Medication", "ARB"), mentions)

    def test_merges_aliases_without_overwriting_existing_aliases(self):
        node = {"aliases": ["硝酸酯"]}

        merge_aliases(node, ["硝酸甘油", "硝酸酯", "nitrates"])

        self.assertEqual(node["aliases"], ["硝酸酯", "硝酸甘油", "nitrates"])

    def test_builds_core_relation_with_required_textbook_evidence_fields(self):
        rel = build_evidence_backed_relation(
            disease_code="DIS-CARD-HF",
            disease_name="心力衰竭",
            target_code="SYM-CARD-DYSPNEA",
            target_name="呼吸困难",
            relation_type="has_symptom",
            relation_category="clinical",
            evidence_code="EVD-CARD-TEXTBOOK-000001",
            line_number=100,
            evidence_text="心力衰竭患者可出现呼吸困难。",
        )

        self.assertEqual(rel["id"], relation_id("DIS-CARD-HF", "has_symptom", "SYM-CARD-DYSPNEA"))
        self.assertEqual(rel["recommendation_class"], "N/A")
        self.assertEqual(rel["evidence_level"], "N/A")
        self.assertEqual(rel["source_type"], "authoritative_textbook")
        self.assertNotEqual(rel["guideline_id"], "")
        self.assertEqual(rel["evidence_count"], 1)
        self.assertEqual(len(rel["provenance_records_json"]), 1)
        self.assertEqual(rel["provenance_records_json"][0]["disease_name"], "心力衰竭")


if __name__ == "__main__":
    unittest.main()
