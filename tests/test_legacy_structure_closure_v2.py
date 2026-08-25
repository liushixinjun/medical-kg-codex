from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "旧结构全库收口V2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("legacy_structure_closure_v2", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_adjudication_cannot_directly_recommend_targets() -> None:
    module = load_module()
    assert "SourceAdjudication" not in module.RECOMMEND_SOURCE_TYPES
    assert "SourceAdjudication" not in module.ASSESSMENT_SOURCE_TYPES
    assert "SourceAdjudication" not in module.BLOCK_SOURCE_TYPES


def test_formal_targets_are_split_into_actions_and_assessments() -> None:
    module = load_module()
    assert set(module.ACTION_TYPES) == {
        "ExamItem",
        "LabItem",
        "Medication",
        "Procedure",
        "TreatmentItem",
        "FollowUp",
    }
    assert {"DiagnosisCriteria", "RiskStratification", "DifferentialDiagnosis"}.issubset(
        set(module.ASSESSMENT_TYPES)
    )
    assert set(module.ACTION_TYPES).isdisjoint(module.ASSESSMENT_TYPES)


def test_known_cross_disease_plan_rules_are_explicit_whitelists() -> None:
    module = load_module()
    for rule in module.PLAN_SCOPE_RULES:
        assert rule["plan_code"]
        assert rule["plan_name"]
        assert rule["allowed_prefixes"] or rule["allowed_codes"]


def test_audit_counts_treatment_items_as_plan_actions() -> None:
    audit_path = ROOT / "公共执行层_kg_pipeline" / "CDSS双口径安全审计.py"
    text = audit_path.read_text(encoding="utf-8")
    assert "includes_treatment_item" in text
    assert "recommends_assessment" in text
