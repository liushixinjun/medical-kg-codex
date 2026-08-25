from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "AMI与心肌病样板收口.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ami_cm_sample_closure", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scope_contains_ami_three_levels_and_cardiomyopathy_family() -> None:
    module = load_module()
    assert module.AMI_CODES == {
        "DIS-CARD-CAD-AMI",
        "DIS-CARD-CAD-STEMI",
        "DIS-CARD-CAD-NSTEMI",
    }
    assert "DIS-CARD-CM-GENERAL" in module.CM_CODES
    assert "DIS-CARD-CM-HCM" in module.CM_CODES
    assert "DIS-CARD-CM-DCM" in module.CM_CODES
    assert len(module.CM_CODES) == 12


def test_standard_exam_and_lab_paths_are_fixed() -> None:
    module = load_module()
    assert module.STANDARD_PATHS["检查发现"] == (
        "has_exam_plan",
        "includes_exam_item",
        "exam_item_has_observation",
    )
    assert module.STANDARD_PATHS["检验细项"] == (
        "has_exam_plan",
        "includes_lab_item",
        "lab_item_has_subitem",
    )
    assert ("ExamPlan", "includes_lab_item", "LabSubitem") in module.FORBIDDEN_DIRECT_PATHS
    assert ("ExamPlan", "*", "ExamObservation") in module.FORBIDDEN_DIRECT_PATHS


def test_role_requirements_do_not_use_one_coverage_template() -> None:
    module = load_module()
    broad = set(module.ROLE_REQUIRED_SLOTS["broad_diagnosis"])
    subtype = set(module.ROLE_REQUIRED_SLOTS["clinical_subtype"])
    assert {
        "definition",
        "exam_plan",
        "clinical_subtype",
        "standard_diagnosis",
    } == broad
    assert "diagnostic_criteria" not in broad
    assert "treatment_plan" not in broad
    assert "clinical_subtype" not in subtype
    assert {
        "definition",
        "exam_plan",
        "diagnostic_criteria",
        "differential_diagnosis",
        "treatment_plan",
        "standard_diagnosis",
    }.issubset(subtype)


def test_content_repairs_are_evidence_bound_and_not_title_only() -> None:
    module = load_module()
    expected = {
        "DIS-CARD-CM-ABVC",
        "DIS-CARD-CM-ATRIAL",
        "DIS-CARD-CM-FABRY",
        "DIS-CARD-CM-GENERAL",
        "DIS-CARD-CM-NDLVCM",
    }
    assert set(module.DIFFERENTIAL_REPAIR_SPECS) == expected
    for disease_code, spec in module.DIFFERENTIAL_REPAIR_SPECS.items():
        assert disease_code == spec["disease_code"]
        assert spec["evidence_id"]
        assert len(spec["rule_text"]) >= 30
        assert spec["differential_targets"]


def test_direct_lab_subitem_can_only_migrate_with_one_parent() -> None:
    module = load_module()
    assert module.classify_parent_candidates([]) == "blocking_missing_parent"
    assert module.classify_parent_candidates(["LAB-1"]) == "safe_to_migrate"
    assert (
        module.classify_parent_candidates(["LAB-1", "LAB-2"])
        == "blocking_ambiguous_parent"
    )


def test_formal_recommendation_accepts_actions_assessments_and_blocks() -> None:
    module = load_module()
    assert module.FORMAL_RECOMMENDATION_RELATIONS == {
        "recommends_action",
        "recommends_assessment",
        "blocks_action",
    }


def test_audit_score_is_split_into_four_named_results() -> None:
    module = load_module()
    assert module.ACCEPTANCE_DIMENSIONS == (
        "知识内容完整性",
        "标准身份完整性",
        "路径可用性",
        "正式推荐就绪度",
    )


def test_context_resolves_known_ambiguous_lab_parents() -> None:
    module = load_module()
    parents = [
        {"code": "LAB-CARD-CADCD76D40B9", "name": "心肌损伤标志物"},
        {"code": "LAB-CARDIAC-BIOMARKERS", "name": "心脏生物标志物检测"},
    ]
    ami = module.resolve_lab_parent(
        "DIS-CARD-CAD-AMI",
        "CARD-SKELETON-20260709-LABTEST-AD6A34F25F521595",
        parents,
    )
    cm = module.resolve_lab_parent(
        "DIS-CARD-CM-DCM",
        "CARD-SKELETON-20260709-LABTEST-AD6A34F25F521595",
        parents,
    )
    assert ami["classification"] == "safe_context_resolved"
    assert ami["selected_parent_code"] == "LAB-CARD-CADCD76D40B9"
    assert cm["classification"] == "safe_context_resolved"
    assert cm["selected_parent_code"] == "LAB-CARDIAC-BIOMARKERS"


def test_nt_probnp_uses_natriuretic_peptide_parent() -> None:
    module = load_module()
    parents = [
        {"code": "LAB-CARDIAC-BIOMARKERS", "name": "心脏生物标志物检测"},
        {"code": "EXAM-CARD-01C3182D129E", "name": "利钠肽"},
    ]
    resolved = module.resolve_lab_parent(
        "DIS-CARD-CM-HCM",
        "IND-NT-PROBNP",
        parents,
    )
    assert resolved["classification"] == "safe_context_resolved"
    assert resolved["selected_parent_code"] == "EXAM-CARD-01C3182D129E"


def test_missing_parent_policy_uses_confirmed_dictionary_or_review_queue() -> None:
    module = load_module()
    esr = module.resolve_lab_parent(
        "DIS-CARD-CAD-AMI",
        "LAB-CARD-1BE2B3C08B76",
        [],
    )
    crp = module.resolve_lab_parent(
        "DIS-CARD-CAD-AMI",
        "LAB-CARD-BF2619C772EC",
        [],
    )
    assert esr["classification"] == "safe_create_parent"
    assert esr["parent_spec"]["dictionary_validation_status"] == "validated"
    assert esr["parent_spec"]["cdss_dict_id"] == "E5BFABACF8274FC9865D36299A1EC8D6"
    assert crp["classification"] == "safe_create_parent"
    assert crp["parent_spec"]["dictionary_validation_status"] == "pending_registration"
    assert not crp["parent_spec"].get("cdss_dict_id")


def test_lab_result_statements_are_not_lab_subitems() -> None:
    module = load_module()
    assert module.classify_lab_result_statement("心肌肌钙蛋白升高") == "ThresholdRule"
    assert (
        module.classify_lab_result_statement(
            "D-二聚体升高提示肺栓塞鉴别线索但需结合临床"
        )
        == "ClinicalRule"
    )
    assert (
        module.classify_lab_result_statement(
            "D-二聚体＜500μg/L可基本排除低度临床可能性急性PTE"
        )
        == "ClinicalRule"
    )
    assert (
        module.lab_child_repair_strategy(
            ["KGNode", "LabItem"],
            ["KGNode", "LabItem"],
            "肌酸激酶同工酶",
        )
        == "create_subitem_shadow"
    )
    assert (
        module.lab_child_repair_strategy(
            ["KGNode", "LabItem"],
            ["KGNode", "ThresholdRule"],
            "白细胞计数升高",
        )
        == "convert_to_threshold_rule"
    )


def test_standard_diagnosis_mapping_distinguishes_exact_from_fallback() -> None:
    module = load_module()
    exact = module.STANDARD_DIAGNOSIS_MAPPINGS["DIS-CARD-CM-ARVC"]
    fallback = module.STANDARD_DIAGNOSIS_MAPPINGS["DIS-CARD-CM-ABVC"]
    assert exact["mapping_type"] == "exact"
    assert exact["standard_code"] == "I42.800x002"
    assert exact["valid_flag"] == 1
    assert fallback["mapping_type"] == "broader_fallback"
    assert fallback["standard_code"] == "I42.900"
    assert fallback["is_emr_writable"] is False


def test_rollback_plan_covers_path_and_standard_identity_changes() -> None:
    module = load_module()
    audit = {
        "bad_lab_paths": [
            {"classification": "safe_to_migrate", "disease_code": "D1"}
        ],
        "bad_exam_paths": [],
        "invalid_lab_child_relations": [
            {"source_code": "L1", "target_code": "L2"}
        ],
        "standard_diagnosis_gaps": [
            {"disease_code": "DIS-CARD-CM-ARVC"}
        ],
    }
    rollback = module.build_rollback_rows(audit)
    assert {row["rollback_kind"] for row in rollback} == {
        "restore_lab_path",
        "restore_lab_child_relation",
        "remove_standard_diagnosis_mapping",
    }


def test_invalid_lab_child_audit_traverses_full_sample_scope() -> None:
    module = load_module()

    class FakeResult:
        def __iter__(self):
            return iter(())

    class FakeSession:
        def __init__(self) -> None:
            self.query = ""
            self.params = {}

        def run(self, query, **params):
            self.query = query
            self.params = params
            return FakeResult()

    session = FakeSession()
    module.collect_invalid_lab_child_relations(session, {"D1", "D2"})

    assert "MATCH (d:Disease)-[:has_exam_plan]->(:ExamPlan)" in session.query
    assert "[:includes_lab_item]->(source)" in session.query
    assert "d.code IN $scope_codes" in session.query
    assert session.params["scope_codes"] == ["D1", "D2"]
