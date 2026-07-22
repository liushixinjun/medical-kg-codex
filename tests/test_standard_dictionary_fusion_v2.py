from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "标准字典融合与诊断推理V2.py"
SPEC = importlib.util.spec_from_file_location("standard_dictionary_fusion_v2", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_composite_sign_is_not_registered_as_atomic_sign() -> None:
    rejected, reason = MODULE.is_composite_sign("肥厚型心肌病体征")
    assert rejected is True
    assert "不是原子体征" in reason


def test_atomic_sign_is_accepted() -> None:
    rejected, reason = MODULE.is_composite_sign("心包摩擦音")
    assert rejected is False
    assert reason == ""


def test_inference_sentence_is_not_registered_as_exam_observation() -> None:
    rejected, reason = MODULE.is_rule_observation("ST段持续抬高提示室壁瘤")
    assert rejected is True
    assert "临床规则" in reason


def test_diagnostic_effect_requires_explicit_finding_context() -> None:
    result = MODULE.classify_diagnostic_effect(
        {
            "evidence_text": "患者常可出现胸痛，但本段没有目标词。",
            "review_status": "approved",
            "conflict_status": "none",
        },
        "心包摩擦音",
    )
    assert result["effect_code"] == "UNSET"
    assert result["score_enabled"] == 0


def test_strong_diagnostic_effect_is_enabled_only_after_review() -> None:
    approved = MODULE.classify_diagnostic_effect(
        {
            "evidence_text": "心包摩擦音是该病具有鉴别价值的特征性体征。",
            "review_status": "approved",
            "conflict_status": "none",
        },
        "心包摩擦音",
    )
    pending = MODULE.classify_diagnostic_effect(
        {
            "evidence_text": "心包摩擦音是该病具有鉴别价值的特征性体征。",
            "review_status": "pending",
            "conflict_status": "none",
        },
        "心包摩擦音",
    )
    assert approved["effect_code"] == "STRONG_SUPPORT"
    assert approved["score_enabled"] == 1
    assert pending["score_enabled"] == 0


def test_duplicate_dictionary_target_prefers_high_degree_node() -> None:
    rows = [
        {"entity_type": "ExamItem", "dict_id": "D1", "dict_code": "E1", "dict_name": "心电图", "element_id": "a", "degree": 2, "kg_name": "ECG", "kg_code": "OLD1"},
        {"entity_type": "ExamItem", "dict_id": "D1", "dict_code": "E1", "dict_name": "心电图", "element_id": "b", "degree": 8, "kg_name": "心电图", "kg_code": "OLD2"},
    ]
    groups = MODULE.build_collision_groups(rows)
    assert len(groups) == 1
    assert groups[0]["canonical_element_id"] == "b"
    assert groups[0]["duplicate_element_ids"] == ["a"]
