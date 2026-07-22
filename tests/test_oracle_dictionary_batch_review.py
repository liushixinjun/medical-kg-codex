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


def test_reversed_dosage_form_phrase_is_alias_not_new_drug() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "肠溶阿司匹林", "K_DRUG_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "保留为别名并匹配规范制剂"
    assert result["normalized_name"] == "阿司匹林肠溶片"
    assert result["term_relation"] == "alias_of"


def test_drug_class_without_drug_suffix_is_not_registered() -> None:
    for name in ("低分子量肝素", "洋地黄制剂", "组织型纤溶酶原激活物"):
        result = MODULE.classify_review_row(
            row("MISSING_IN_EXISTING_DICTIONARY", name, "K_DRUG_DICT")
        )
        assert result["review_layer"] == "无需人工审核"
        assert result["recommended_action"] == "转为药物类别"
        assert result["term_relation"] == "member_of"


def test_compounded_treatment_is_not_registered_as_drug() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "极化液", "K_DRUG_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "转为治疗项目"
    assert result["term_relation"] == "reclassified_as"
    assert result["resolved_target_table"] == "K_TREATMENT_DICT"


def test_known_exam_alias_is_normalized_without_new_registration() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "胸部X线", "K_EXAM_ITEM_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "保留为别名并匹配规范检查"
    assert result["normalized_name"] == "胸部X线检查"
    assert result["term_relation"] == "alias_of"


def test_history_taking_is_not_an_exam_item() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "病史采集", "K_EXAM_ITEM_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "转入临床评估"
    assert result["resolved_target_table"] == ""


def test_atomic_lab_analyte_is_reclassified_as_lab_subitem() -> None:
    for name in ("白细胞计数", "肌钙蛋白", "D-二聚体", "血肌酐", "血钾"):
        result = MODULE.classify_review_row(
            row("MISSING_IN_EXISTING_DICTIONARY", name, "K_LAB_ITEM_DICT")
        )
        assert result["review_layer"] == "无需人工审核"
        assert result["recommended_action"] == "转为检验细项"
        assert result["resolved_target_table"] == "K_LAB_SUBITEM_DICT"
        assert result["term_relation"] == "reclassified_as"


def test_lab_panel_remains_a_lab_item_candidate() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "甲状腺功能", "K_LAB_ITEM_DICT")
    )
    assert result["review_layer"] == "分组批量确认"
    assert result["recommended_action"] == "候选注册"


def test_composite_lab_assessment_is_not_registered_as_lab_item() -> None:
    result = MODULE.classify_review_row(
        row(
            "MISSING_IN_EXISTING_DICTIONARY",
            "CKD高血压肾功能和尿蛋白评估",
            "K_LAB_ITEM_DICT",
        )
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "转入临床评估"


def test_lab_result_container_is_not_registered_as_subitem() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "血培养结果", "K_LAB_SUBITEM_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "转入检验结果规则"


def test_broad_treatment_knowledge_is_not_registered_as_order_item() -> None:
    for name in ("最佳药物治疗", "病因治疗", "支持治疗", "危险因素管理", "溶栓治疗"):
        result = MODULE.classify_review_row(
            row("MISSING_IN_EXISTING_DICTIONARY", name, "K_TREATMENT_DICT")
        )
        assert result["review_layer"] == "无需人工审核"
        assert result["recommended_action"] == "保留为治疗方案知识"
        assert result["resolved_target_table"] == ""


def test_treatment_alias_is_normalized_without_duplicate_registration() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "吸氧治疗", "K_TREATMENT_DICT")
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "保留为别名并匹配规范治疗"
    assert result["normalized_name"] == "氧疗"
    assert result["term_relation"] == "alias_of"


def test_composite_procedure_is_split_before_dictionary_registration() -> None:
    result = MODULE.classify_review_row(
        row(
            "MISSING_IN_EXISTING_DICTIONARY",
            "肺移植同时修补心脏缺损",
            "K_TREATMENT_DICT",
        )
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "拆分为具体手术与组合方案"


def test_known_drug_variant_is_alias_not_a_second_master_record() -> None:
    expected = {
        "地尔硫䓬": "地尔硫卓",
        "达比加群": "达比加群酯",
        "长效青霉素": "苄星青霉素",
    }
    for name, normalized in expected.items():
        result = MODULE.classify_review_row(
            row("MISSING_IN_EXISTING_DICTIONARY", name, "K_DRUG_DICT")
        )
        assert result["review_layer"] == "无需人工审核"
        assert result["recommended_action"] == "保留为别名并匹配规范制剂"
        assert result["normalized_name"] == normalized
        assert result["term_relation"] == "alias_of"


def test_ambiguous_drug_short_name_requires_authoritative_verification() -> None:
    result = MODULE.classify_review_row(
        row("MISSING_IN_EXISTING_DICTIONARY", "肝素", "K_DRUG_DICT")
    )
    assert result["review_layer"] == "逐条人工裁决"
    assert result["recommended_action"] == "核对具体制剂或药品通用名"


def test_contextual_symptom_phrase_keeps_context_out_of_master_name() -> None:
    expected = {
        "安静时持续性胸痛": "胸痛",
        "活动时心悸": "心悸",
        "静息性呼吸困难": "呼吸困难",
    }
    for name, normalized in expected.items():
        result = MODULE.classify_review_row(
            row("MISSING_IN_EXISTING_DICTIONARY", name, "K_SYMPTOM_DICT")
        )
        assert result["review_layer"] == "无需人工审核"
        assert result["recommended_action"] == "归一症状主名并保留情境"
        assert result["normalized_name"] == normalized
        assert result["term_relation"] == "contextual_variant_of"


def test_composite_symptom_with_conjunction_is_split() -> None:
    result = MODULE.classify_review_row(
        row(
            "MISSING_IN_EXISTING_DICTIONARY",
            "间歇性跛行和活动相关下肢症状",
            "K_SYMPTOM_DICT",
        )
    )
    assert result["review_layer"] == "无需人工审核"
    assert result["recommended_action"] == "退回并拆分为原子项"


def test_myocarditis_exam_shell_is_rejected() -> None:
    for name in ("心肌炎检查", "暴发性心肌炎检查"):
        result = MODULE.classify_review_row(
            row("MISSING_IN_EXISTING_DICTIONARY", name, "K_EXAM_ITEM_DICT")
        )
        assert result["review_layer"] == "无需人工审核"
        assert result["recommended_action"] == "退回并拆分为原子项"


def test_duplicate_group_candidate_is_automatically_consolidated() -> None:
    first = row("MISSING_IN_EXISTING_DICTIONARY", "超声心动图", "K_EXAM_ITEM_DICT")
    second = dict(first)
    second["id"] = "another-id"
    second["kg_node_code"] = "another-code"
    package = MODULE.build_review_package([first, second])
    assert package["summary"]["group_candidate_count"] == 1
    assert package["summary"]["automatic_count"] == 1
    assert package["automatic"][0]["recommended_action"] == "合并重复候选"


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
