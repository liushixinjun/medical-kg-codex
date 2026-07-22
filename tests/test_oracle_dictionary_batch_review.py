from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "Oracle字典批量审核.py"
SPEC = importlib.util.spec_from_file_location("oracle_dictionary_batch_review", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def row(issue_type: str, name: str, target_table: str) -> dict[str, str]:
    return {
        "id": f"id-{name}",
        "entity_type": "ExamItem",
        "kg_node_code": f"code-{name}",
        "kg_node_name": name,
        "target_table": target_table,
        "issue_type": issue_type,
        "reason": "测试",
        "current_value": "",
        "proposed_value": "",
        "source": "",
        "target_id": "",
        "target_code": "",
        "target_name": "",
    }


def test_existing_wrong_type_does_not_need_manual_review() -> None:
    result = MODULE.classify_review_row(
        row("WRONG_TYPE_OR_COMPOSITE", "肥厚型心肌病体征", "K_CLINICAL_SIGN_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "退回并重分类"


def test_alias_candidate_is_kept_as_alias_mapping() -> None:
    result = MODULE.classify_review_row(
        row("ALIAS_TO_TERM_CANDIDATE", "胸痛", "K_SYMPTOM_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "保留为别名映射"


def test_ambiguous_match_needs_individual_decision() -> None:
    result = MODULE.classify_review_row(
        row("AMBIGUOUS_MATCH", "发热", "K_SYMPTOM_DICT")
    )
    assert result["review_layer"] == "逐条人工裁决"
    assert result["recommended_action"] == "选择唯一标准记录"


def test_heading_pollution_is_rejected_before_dictionary_registration() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "一、稳定型心绞痛-症状", "K_SYMPTOM_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "退回并清理污染"


def test_disease_shell_is_rejected_before_dictionary_registration() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "ST段抬高型心肌梗死检查", "K_EXAM_ITEM_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "退回并拆分为原子项"


def test_valve_sign_shell_is_rejected() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "三尖瓣反流体征", "K_CLINICAL_SIGN_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "退回并拆分为原子项"


def test_disease_specific_exam_shell_is_rejected() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "三尖瓣反流检查", "K_EXAM_ITEM_DICT")
    )
    assert result["review_layer"] == "无需人工审核"


def test_non_observation_context_is_not_registered_as_exam_observation() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "发病时间", "K_EXAM_OBSERVATION_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "转入临床规则"


def test_lab_result_state_is_not_registered_as_lab_subitem() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "BNP升高", "K_LAB_SUBITEM_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "拆分为检验细项与结果状态"


def test_real_exam_item_enters_group_review() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "12导联心电图", "K_EXAM_ITEM_DICT")
    )
    assert result["review_layer"] == "分组批量确认"
    assert result["recommended_action"] == "候选注册"


def test_drug_class_is_not_registered_as_concrete_drug() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "P2Y12受体抑制剂", "K_DRUG_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "转为药物类别"


def test_concrete_drug_enters_group_review() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "阿司匹林", "K_DRUG_DICT")
    )
    assert result["review_layer"] == "分组批量确认"
    assert result["recommended_action"] == "候选注册"


def test_package_preserves_every_input_row() -> None:
    rows = [
        row("WRONG_TYPE_OR_COMPOSITE", "肥厚型心肌病体征", "K_CLINICAL_SIGN_DICT"),
        row("ALIAS_TO_TERM_CANDIDATE", "胸痛", "K_SYMPTOM_DICT"),
        row("AMBIGUOUS_MATCH", "发热", "K_SYMPTOM_DICT"),
        row("MISSING_IN_EXISTING_DICTIONARY", "一、稳定型心绞痛-症状", "K_SYMPTOM_DICT"),
        row("MISSING_IN_EXISTING_DICTIONARY", "12导联心电图", "K_EXAM_ITEM_DICT"),
    ]
    package = MODULE.build_review_package(rows)
    output_count = sum(len(package[key]) for key in ("automatic", "group_candidates", "manual"))
    assert output_count == len(rows)
    assert len(package["manual"]) == 1
    assert len(package["groups"]) == 1
