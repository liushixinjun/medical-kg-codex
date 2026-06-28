import unittest

from scripts.classify_evidence_backfill_candidates import classify_candidate
from scripts.classify_evidence_backfill_candidates import has_strong_disease_anchor


class ClassifyEvidenceBackfillCandidateTests(unittest.TestCase):
    def test_rejects_semantic_shell_candidate_even_with_evidence(self):
        row = {
            "entityType": "DiagnosisCriteria",
            "entity_name": "诊断标准",
            "evidence_text": "本段提到诊断标准但没有给出具体标准。",
        }
        self.assertEqual(classify_candidate(row, already_covered=False), "REJECT_SEMANTIC_SHELL")

    def test_rejects_short_or_noise_evidence(self):
        row = {
            "entityType": "Symptom",
            "entity_name": "胸痛",
            "evidence_text": "胸痛",
        }
        self.assertEqual(classify_candidate(row, already_covered=False), "REJECT_NO_EVIDENCE")

    def test_marks_existing_relation_as_already_covered(self):
        row = {
            "entityType": "Symptom",
            "entity_name": "胸痛",
            "evidence_text": "患者可表现为胸痛、胸闷等症状。",
        }
        self.assertEqual(classify_candidate(row, already_covered=True), "ALREADY_COVERED")

    def test_accepts_specific_clinical_entity_with_evidence(self):
        row = {
            "disease_name": "静脉血栓症",
            "entityType": "Medication",
            "entity_name": "华法林",
            "evidence_text": "静脉血栓症患者可使用华法林进行抗凝治疗。",
        }
        self.assertEqual(classify_candidate(row, already_covered=False), "ACCEPT_CANDIDATE")

    def test_demotes_candidate_when_disease_anchor_is_incidental(self):
        row = {
            "disease_name": "急性心力衰竭",
            "entityType": "Medication",
            "entity_name": "硝酸酯类药物",
            "evidence_text": "心肌梗死患者少数一开始即表现为休克或急性心力衰竭，含用硝酸甘油多不能缓解。",
        }
        self.assertEqual(classify_candidate(row, already_covered=False), "NEEDS_DISEASE_ANCHOR_REVIEW")

    def test_detects_strong_disease_anchor_for_therapeutic_sentence(self):
        self.assertTrue(
            has_strong_disease_anchor(
                "急性心力衰竭",
                "硝酸甘油主要用于高血压急症伴急性心力衰竭或急性冠脉综合征。",
            )
        )

    def test_demotes_medication_when_target_is_not_supported_near_disease_anchor(self):
        row = {
            "disease_name": "心房颤动",
            "entityType": "Medication",
            "entity_name": "溶栓药物",
            "relationType": "treated_by_medication",
            "evidence_text": "除非有禁忌，所有 STEMI 病人无论是否采用溶栓治疗，均应在抗血小板治疗的基础上常规联合抗凝治疗。对于 STEMI 合并心房颤动时，需在抗血小板治疗基础上联合直接口服抗凝药抗凝治疗，但需注意出血风险。",
        }
        self.assertEqual(classify_candidate(row, already_covered=False), "NEEDS_RELATION_SEMANTIC_REVIEW")

    def test_accepts_medication_class_when_specific_drug_supports_relation_near_disease_anchor(self):
        row = {
            "disease_name": "二尖瓣狭窄",
            "entityType": "Medication",
            "entity_name": "抗凝药物",
            "relationType": "treated_by_medication",
            "evidence_text": "合并中重度二尖瓣狭窄或机械瓣置换术后的瓣膜性房颤病人，无需行 CHA2DS2-VASc 评分，直接选择华法林抗凝治疗。",
        }
        self.assertEqual(classify_candidate(row, already_covered=False), "ACCEPT_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
