import unittest

from scripts.repair_cad_cm_clinical_safety import repair_rows


def node(code, name, entity_type):
    return {
        "id": f"N-{code}",
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": "临床",
        "schema_version": "V1.7",
        "review_status": "approved",
        "batch_id": "BATCH-TEST",
        "clinical_review_status": "pending_clinical_review",
        "formal_cdss_ready": False,
    }


def rel(rel_id, source, relation_type, target):
    return {
        "id": rel_id,
        "source_code": source,
        "relationType": relation_type,
        "target_code": target,
        "relationCategory": "therapeutic",
        "batch_id": "BATCH-TEST",
        "schema_version": "V1.7",
        "review_status": "approved",
        "clinical_review_status": "pending_clinical_review",
        "formal_cdss_ready": False,
    }


class RepairCadCmClinicalSafetyTests(unittest.TestCase):
    def test_replaces_polluted_cardiomyopathy_definitions(self):
        nodes = [
            {
                **node("DIS-CARD-CM-ACM", "致心律失常性心肌病", "Disease"),
                "description": "在成年遗传性RCM 患者中，心力衰竭是主 ACM 是一类以心室心肌被纤维脂肪组织进行要死亡原因。",
                "definition_evidence_text": "在成年遗传性RCM 患者中，心力衰竭是主 ACM 是一类以心室心肌被纤维脂肪组织进行要死亡原因。",
            },
            {
                **node("DIS-CARD-CM-ATRIAL", "心房心肌病", "Disease"),
                "description": "酒精可能诱发或加重HCM 患者流出道梗阻，心房心肌病是指心房发生组织结构和功能异常。",
                "definition_evidence_text": "酒精可能诱发或加重HCM 患者流出道梗阻，心房心肌病是指心房发生组织结构和功能异常。",
            },
        ]

        summary = repair_rows(nodes, [], "BATCH-TEST")

        acm = next(row for row in nodes if row["code"] == "DIS-CARD-CM-ACM")
        atrial = next(row for row in nodes if row["code"] == "DIS-CARD-CM-ATRIAL")
        self.assertEqual(summary["updated_polluted_definition_nodes"], 2)
        self.assertNotIn("RCM", acm["description"])
        self.assertIn("纤维脂肪", acm["description"])
        self.assertNotIn("HCM", atrial["description"])
        self.assertIn("心房结构", atrial["description"])

    def test_removes_invalid_thrombolysis_paths_but_keeps_stemi(self):
        nodes = [
            node("DIS-CARD-CAD-STABLE-ANGINA", "稳定型心绞痛", "Disease"),
            node("DIS-CARD-CAD-NSTEMI", "非ST段抬高型心肌梗死", "Disease"),
            node("DIS-CARD-CAD-STEMI", "ST段抬高型心肌梗死", "Disease"),
            node("PLAN-REPERFUSION", "再灌注治疗", "TreatmentPlan"),
            node("PROC-THROMBOLYSIS", "溶栓治疗", "Procedure"),
        ]
        relations = [
            rel("R-STABLE-PLAN", "DIS-CARD-CAD-STABLE-ANGINA", "has_treatment_plan", "PLAN-REPERFUSION"),
            rel("R-NSTEMI-PROC", "DIS-CARD-CAD-NSTEMI", "treated_by_procedure", "PROC-THROMBOLYSIS"),
            rel("R-STEMI-PLAN", "DIS-CARD-CAD-STEMI", "has_treatment_plan", "PLAN-REPERFUSION"),
            rel("R-STEMI-PROC", "DIS-CARD-CAD-STEMI", "treated_by_procedure", "PROC-THROMBOLYSIS"),
        ]

        summary = repair_rows(nodes, relations, "BATCH-TEST")

        remaining_ids = {row["id"] for row in relations}
        self.assertEqual(summary["deleted_invalid_thrombolysis_relations"], 2)
        self.assertNotIn("R-STABLE-PLAN", remaining_ids)
        self.assertNotIn("R-NSTEMI-PROC", remaining_ids)
        self.assertIn("R-STEMI-PLAN", remaining_ids)
        self.assertIn("R-STEMI-PROC", remaining_ids)

    def test_repairs_hcm_pci_and_ccb_relation(self):
        nodes = [
            node("DIS-CARD-CM-HCM", "肥厚型心肌病", "Disease"),
            node("PROC-PCI", "经皮冠状动脉介入治疗", "Procedure"),
            node("MED-CCB", "钙通道阻滞剂", "Medication"),
            node("MED-NDHP-CCB", "非二氢吡啶类钙通道阻滞剂", "Medication"),
        ]
        relations = [
            rel("R-HCM-PCI", "DIS-CARD-CM-HCM", "treated_by_procedure", "PROC-PCI"),
            rel("R-HCM-CCB", "DIS-CARD-CM-HCM", "treated_by_medication", "MED-CCB"),
        ]

        summary = repair_rows(nodes, relations, "BATCH-TEST")

        remaining = {(row["source_code"], row["relationType"], row["target_code"]): row for row in relations}
        self.assertEqual(summary["deleted_hcm_pci_relations"], 1)
        self.assertEqual(summary["retargeted_hcm_ccb_relations"], 1)
        self.assertNotIn(("DIS-CARD-CM-HCM", "treated_by_procedure", "PROC-PCI"), remaining)
        ccb = remaining[("DIS-CARD-CM-HCM", "treated_by_medication", "MED-NDHP-CCB")]
        self.assertIn("非梗阻", ccb["applicable_population"])
        self.assertIn("梗阻", ccb["exclusion_criteria"])

    def test_merges_beta_blocker_and_arb_synonym_targets(self):
        nodes = [
            node("DIS-CARD-CM-DCM", "扩张型心肌病", "Disease"),
            node("MED-BETA-BLOCKER", "β受体拮抗剂", "Medication"),
            node("MED-CARD-36D5B18BD8D3", "β受体阻滞剂", "Medication"),
            node("MED-CARD-C015B7A5655A", "血管紧张素Ⅱ受体阻滞剂", "Medication"),
            node("MED-CARD-TEXT-B905AF3E59", "血管紧张素Ⅱ受体拮抗剂", "Medication"),
        ]
        relations = [
            rel("R-DCM-BETA-OLD", "DIS-CARD-CM-DCM", "treated_by_medication", "MED-BETA-BLOCKER"),
            rel("R-DCM-BETA-CANON", "DIS-CARD-CM-DCM", "treated_by_medication", "MED-CARD-36D5B18BD8D3"),
            rel("R-DCM-ARB-OLD", "DIS-CARD-CM-DCM", "treated_by_medication", "MED-CARD-C015B7A5655A"),
        ]

        summary = repair_rows(nodes, relations, "BATCH-TEST")

        targets = [row["target_code"] for row in relations if row["source_code"] == "DIS-CARD-CM-DCM"]
        beta = next(row for row in nodes if row["code"] == "MED-BETA-BLOCKER")
        arb = next(row for row in nodes if row["code"] == "MED-CARD-TEXT-B905AF3E59")
        self.assertEqual(summary["retargeted_synonym_medication_relations"], 2)
        self.assertGreaterEqual(summary["removed_duplicate_semantic_relations"], 1)
        self.assertEqual(summary["removed_orphan_synonym_nodes"], 2)
        self.assertEqual(targets.count("MED-BETA-BLOCKER"), 1)
        self.assertNotIn("MED-CARD-36D5B18BD8D3", {row["code"] for row in nodes})
        self.assertNotIn("MED-CARD-C015B7A5655A", {row["code"] for row in nodes})
        self.assertEqual("β受体阻滞剂", beta["name"])
        self.assertIn("β受体拮抗剂", beta["aliases"])
        self.assertIn("血管紧张素Ⅱ受体阻滞剂", arb["aliases"])


if __name__ == "__main__":
    unittest.main()
