from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "CDSS双口径安全审计.py"
REPAIR_MODULE_PATH = (
    ROOT
    / "项目管理中心_project_management"
    / "141_CDSS双口径审计与缺口治理_20260719"
    / "02_修复包"
    / "执行双口径缺口治理.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("cdss_dual_scope_audit", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_repair_module():
    spec = importlib.util.spec_from_file_location("cdss_dual_scope_repair", REPAIR_MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generic_knowledge_relation_is_not_a_formal_recommendation() -> None:
    module = load_module()
    assert not module.is_formal_recommendation_edge(
        "TreatmentPlan",
        "treated_by_medication",
        {"formal_cdss_ready": True, "cdss_use_status": "正式推荐"},
    )


def test_only_formal_source_adjudication_action_is_in_formal_scope() -> None:
    module = load_module()
    assert module.is_formal_recommendation_edge(
        "SourceAdjudication",
        "recommends_action",
        {"formal_cdss_ready": True, "cdss_use_status": "正式推荐"},
    )
    assert module.is_formal_recommendation_edge(
        "SourceAdjudication",
        "blocks_action",
        {"formal_cdss_ready": True, "cdss_use_status": "正式推荐"},
    )
    assert not module.is_formal_recommendation_edge(
        "SourceAdjudication",
        "recommends_action",
        {"formal_cdss_ready": False, "cdss_use_status": "仅知识展示"},
    )


def test_evidence_fingerprint_is_not_based_on_display_name_only() -> None:
    module = load_module()
    first = module.build_evidence_fingerprint("《内科学（第10版）》", "275", "肥厚型心肌病定义原文")
    second = module.build_evidence_fingerprint("《内科学（第10版）》", "276", "肥厚型心肌病治疗原文")
    same = module.build_evidence_fingerprint("《内科学（第10版）》", "275", "肥厚型心肌病定义原文")
    assert first != second
    assert first == same


def test_dual_scope_conclusions_are_independent() -> None:
    module = load_module()
    result = module.evaluate_dual_scope(
        {
            "非标准图谱节点": 0,
            "技术编码名称节点": 0,
            "同编码重复实体": 0,
            "疾病定义缺口": 2,
            "诊断标准无明细": 0,
            "鉴别诊断无规则": 0,
            "治疗方案无可执行动作": 0,
            "在用药物类别无具体药品": 0,
        },
        {
            "正式推荐缺疾病": 0,
            "正式推荐缺推荐陈述": 0,
            "正式推荐缺动作": 0,
            "正式推荐缺主证据": 0,
            "正式推荐缺主指南": 0,
            "正式推荐缺推荐等级": 0,
            "正式推荐缺证据等级": 0,
            "正式推荐缺冲突状态": 0,
            "正式推荐缺裁决理由": 0,
        },
    )
    assert result["知识内容完整性"]["结论"] == "不通过"
    assert result["正式推荐链路"]["结论"] == "通过"


def test_query_contract_does_not_treat_generic_relations_as_formal_scope() -> None:
    module = load_module()
    query = module.FORMAL_RECOMMENDATION_ROWS_QUERY
    assert "SourceAdjudication" in query
    assert "formal_cdss_ready" in query
    assert "cdss_use_status" in query
    assert "treated_by_medication" not in query
    assert "includes_medication" not in query


def test_repair_definition_manifest_is_complete_and_unique() -> None:
    module = load_repair_module()
    rows = module.normalized_definition_rows()
    assert len(rows) == 36
    assert len({row["disease_code"] for row in rows}) == 36
    assert all(row["definition_text"].strip() for row in rows)
    assert all(row["evidence_code"].startswith("EVD-") for row in rows)


def test_repair_scope_contains_only_verified_cleanup_targets() -> None:
    module = load_repair_module()
    assert len(module.BAD_PLAN_PAIRS) == 4
    assert len(module.POLLUTED_DIFFERENTIAL_CODES) == 2
    assert len(module.ORPHAN_MEDICATION_CODES) == 2
    assert module.FORMAL_OLD_EVIDENCE_CODE != module.FORMAL_CANONICAL_EVIDENCE_CODE
