from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "心血管内科文献集合"
SCHEMA_VERSION = "V1.9"
CREATED_AT = "2026-07-07 00:00:00"


def kg_id(code: str) -> str:
    return "KG_" + code.replace("-", "_")


def rel_id(source: str, rel_type: str, target: str) -> str:
    digest = hashlib.sha1(f"{source}|{rel_type}|{target}".encode("utf-8")).hexdigest().upper()
    return "REL-" + digest[:20]


def common_props(batch_id: str, scope_target: str, *, clinical_review_status: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved_for_sample",
        "batch_id": batch_id,
        "scope_type": "disease",
        "scope_target": scope_target,
        "merge_status": "delta_sample_not_imported",
        "conflict_status": "none",
        "clinical_review_status": clinical_review_status or "pending_clinical_use_effect_review",
        "formal_cdss_ready": False,
        "ai_evidence_review_status": "ai_prechecked_limited",
        "cdss_release_level": "test_recommendation",
        "created_at": CREATED_AT,
    }


def node(
    nodes: dict[str, dict[str, Any]],
    *,
    code: str,
    name: str,
    entity_type: str,
    entity_category: str,
    batch_id: str,
    scope_target: str,
    disease_code: str,
    aliases: list[str] | None = None,
    **extra: Any,
) -> None:
    payload = {
        "id": kg_id(code),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": entity_category,
        **common_props(batch_id, scope_target),
        "aliases": aliases or [],
        "disease_code": disease_code,
        **extra,
    }
    if code in nodes and nodes[code] != payload:
        raise ValueError(f"Duplicate node code with different payload: {code}")
    nodes[code] = payload


def rel(
    rels: dict[tuple[str, str, str], dict[str, Any]],
    *,
    source: str,
    rel_type: str,
    target: str,
    category: str,
    batch_id: str,
    scope_target: str,
    evidence_ids: list[str] | None = None,
    confidence: float = 0.88,
    polarity: str = "positive",
    clinical_review_status: str | None = None,
    cdss_release_level: str | None = None,
) -> None:
    evidence_ids = list(dict.fromkeys(evidence_ids or []))
    payload = {
        "id": rel_id(source, rel_type, target),
        "source_code": source,
        "relationType": rel_type,
        "target_code": target,
        "relationCategory": category,
        **common_props(batch_id, scope_target, clinical_review_status=clinical_review_status),
        "polarity": polarity,
        "confidence": confidence,
        "evidence_ids": evidence_ids,
        "evidence_count": len(evidence_ids),
    }
    if cdss_release_level:
        payload["cdss_release_level"] = cdss_release_level
    key = (source, rel_type, target)
    if key in rels and rels[key] != payload:
        raise ValueError(f"Duplicate relation key with different payload: {key}")
    rels[key] = payload


def support_evidence(
    rels: dict[tuple[str, str, str], dict[str, Any]],
    *,
    source: str,
    evidence_ids: list[str],
    batch_id: str,
    scope_target: str,
) -> None:
    for evidence_id in dict.fromkeys(evidence_ids):
        rel(
            rels,
            source=source,
            rel_type="supported_by_evidence",
            target=evidence_id,
            category="evidence",
            batch_id=batch_id,
            scope_target=scope_target,
            evidence_ids=[evidence_id],
            clinical_review_status="not_applicable",
            cdss_release_level="knowledge_display",
        )


def clinical_pathway(
    nodes: dict[str, dict[str, Any]],
    rels: dict[tuple[str, str, str], dict[str, Any]],
    *,
    batch_id: str,
    scope_target: str,
    disease_code: str,
    disease_name: str,
    pathway_code: str,
    pathway_name: str,
    aliases: list[str],
    goal: str,
    evidence_ids: list[str],
) -> None:
    node(
        nodes,
        code=pathway_code,
        name=pathway_name,
        entity_type="ClinicalPathway",
        entity_category="临床流程",
        batch_id=batch_id,
        scope_target=scope_target,
        disease_code=disease_code,
        aliases=aliases,
        disease_name=disease_name,
        pathway_goal=goal,
        execution_boundary="图谱维护医学规则、触发条件、证据链；专病流程引擎根据EMR事件和患者状态触发。",
    )
    rel(
        rels,
        source=disease_code,
        rel_type="has_clinical_pathway",
        target=pathway_code,
        category="pathway",
        batch_id=batch_id,
        scope_target=scope_target,
        evidence_ids=evidence_ids,
    )


def add_stages(
    nodes: dict[str, dict[str, Any]],
    rels: dict[tuple[str, str, str], dict[str, Any]],
    *,
    batch_id: str,
    scope_target: str,
    disease_code: str,
    pathway_code: str,
    stages: list[dict[str, Any]],
) -> None:
    previous: str | None = None
    for index, stage in enumerate(stages, start=1):
        code = stage["code"]
        node(
            nodes,
            code=code,
            name=stage["name"],
            entity_type="PathwayStage",
            entity_category="临床流程",
            batch_id=batch_id,
            scope_target=scope_target,
            disease_code=disease_code,
            pathway_code=pathway_code,
            stage_order=index,
            stage_goal=stage["goal"],
            trigger_condition=stage["trigger"],
            exit_condition=stage["exit"],
        )
        rel(
            rels,
            source=pathway_code,
            rel_type="has_pathway_stage",
            target=code,
            category="pathway",
            batch_id=batch_id,
            scope_target=scope_target,
        )
        if previous:
            rel(
                rels,
                source=previous,
                rel_type="next_pathway_stage",
                target=code,
                category="pathway",
                batch_id=batch_id,
                scope_target=scope_target,
            )
        previous = code


def clinical_rule(
    nodes: dict[str, dict[str, Any]],
    rels: dict[tuple[str, str, str], dict[str, Any]],
    *,
    batch_id: str,
    scope_target: str,
    disease_code: str,
    code: str,
    name: str,
    rule_logic: str,
    evidence_ids: list[str],
    rule_type: str = "pathway_stage_rule",
) -> None:
    node(
        nodes,
        code=code,
        name=name,
        entity_type="ClinicalRule",
        entity_category="临床规则",
        batch_id=batch_id,
        scope_target=scope_target,
        disease_code=disease_code,
        rule_type=rule_type,
        rule_logic=rule_logic,
        evidence_ids=evidence_ids,
    )
    support_evidence(rels, source=code, evidence_ids=evidence_ids, batch_id=batch_id, scope_target=scope_target)


def add_stage_rule(
    rels: dict[tuple[str, str, str], dict[str, Any]],
    *,
    batch_id: str,
    scope_target: str,
    stage: str,
    rule_code: str,
    evidence_ids: list[str],
) -> None:
    rel(
        rels,
        source=stage,
        rel_type="has_stage_rule",
        target=rule_code,
        category="pathway",
        batch_id=batch_id,
        scope_target=scope_target,
        evidence_ids=evidence_ids,
    )


def add_actions(
    rels: dict[tuple[str, str, str], dict[str, Any]],
    *,
    batch_id: str,
    scope_target: str,
    source: str,
    targets: list[str],
    rel_type: str,
    category: str,
    evidence_ids: list[str] | None = None,
) -> None:
    for target in targets:
        rel(
            rels,
            source=source,
            rel_type=rel_type,
            target=target,
            category=category,
            batch_id=batch_id,
            scope_target=scope_target,
            evidence_ids=evidence_ids or [],
        )


def add_exam_node(
    nodes: dict[str, dict[str, Any]],
    *,
    batch_id: str,
    scope_target: str,
    disease_code: str,
    code: str,
    name: str,
    purpose: str,
    aliases: list[str] | None = None,
    exam_category: str = "辅助检查",
) -> None:
    node(
        nodes,
        code=code,
        name=name,
        entity_type="Exam",
        entity_category="检查/检验",
        batch_id=batch_id,
        scope_target=scope_target,
        disease_code=disease_code,
        aliases=aliases or [],
        exam_category=exam_category,
        purpose=purpose,
    )


def add_diagnostic_component(
    rels: dict[tuple[str, str, str], dict[str, Any]],
    *,
    batch_id: str,
    scope_target: str,
    dx_code: str,
    component_rule: str,
    evidence_ids: list[str],
) -> None:
    rel(
        rels,
        source=dx_code,
        rel_type="has_diagnostic_component",
        target=component_rule,
        category="diagnostic",
        batch_id=batch_id,
        scope_target=scope_target,
        evidence_ids=evidence_ids,
    )


def add_ddx(
    nodes: dict[str, dict[str, Any]],
    rels: dict[tuple[str, str, str], dict[str, Any]],
    *,
    batch_id: str,
    scope_target: str,
    disease_code: str,
    ddx_code: str,
    ddx_name: str,
    point_rule: str,
    point_name: str,
    point_logic: str,
    evidence_ids: list[str],
    exclusion_exams: list[str],
    may_block_actions: list[str] | None = None,
    create_ddx_node: bool = True,
) -> None:
    if create_ddx_node and ddx_code.startswith("DDX-CARD-") and ddx_code not in nodes:
        node(
            nodes,
            code=ddx_code,
            name=ddx_name,
            entity_type="DifferentialDiagnosis",
            entity_category="鉴别诊断",
            batch_id=batch_id,
            scope_target=scope_target,
            disease_code=disease_code,
            aliases=[],
        )
    clinical_rule(
        nodes,
        rels,
        batch_id=batch_id,
        scope_target=scope_target,
        disease_code=disease_code,
        code=point_rule,
        name=point_name,
        rule_logic=point_logic,
        evidence_ids=evidence_ids,
        rule_type="differential_point",
    )
    rel(
        rels,
        source=disease_code,
        rel_type="has_differential_diagnosis",
        target=ddx_code,
        category="differential",
        batch_id=batch_id,
        scope_target=scope_target,
        evidence_ids=evidence_ids,
    )
    rel(
        rels,
        source=ddx_code,
        rel_type="has_differential_point",
        target=point_rule,
        category="differential",
        batch_id=batch_id,
        scope_target=scope_target,
        evidence_ids=evidence_ids,
    )
    for exam in exclusion_exams:
        rel(
            rels,
            source=ddx_code,
            rel_type="requires_exclusion_exam",
            target=exam,
            category="differential",
            batch_id=batch_id,
            scope_target=scope_target,
            evidence_ids=evidence_ids,
        )
    for action in may_block_actions or []:
        rel(
            rels,
            source=ddx_code,
            rel_type="may_block_action",
            target=action,
            category="differential",
            batch_id=batch_id,
            scope_target=scope_target,
            evidence_ids=evidence_ids,
            polarity="negative",
        )


def build_hf() -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    batch_id = "BATCH-CARD-HF-20260629-001"
    scope = "心力衰竭"
    disease = "DIS-CARD-HF"
    out = COLLECTION / batch_id / "09_专病CDSS动态路径样板_dynamic_cdss_pathway" / "HF_20260707"
    nodes: dict[str, dict[str, Any]] = {}
    rels: dict[tuple[str, str, str], dict[str, Any]] = {}
    evidence = {
        "diagnosis": ["EVD-C3D617211B596CF0E5CE-HF", "EVD-BAC1C48FDED5FA1DEB2D-AHF"],
        "hfpef": ["EVD-7DFE0F3278CE8851A238-HFpEF", "EVD-1740A4027F163FB2BFA3-HFpEF"],
        "therapy": ["EVD-6C40984E352072D805F6-HF", "EVD-6C22AF8E99424C13D50E-HF"],
        "acute": ["EVD-BAC1C48FDED5FA1DEB2D-AHF", "EVD-3D73B3265AA9A0357CBB-AHF"],
        "follow": ["EVD-D33B79AC036793E90BBD-HF"],
    }
    pathway = "PATHWAY-CARD-HF-DYNAMIC-CDSS"
    clinical_pathway(
        nodes,
        rels,
        batch_id=batch_id,
        scope_target=scope,
        disease_code=disease,
        disease_name="心力衰竭",
        pathway_code=pathway,
        pathway_name="心力衰竭专病动态CDSS路径",
        aliases=["HF动态诊疗路径", "心衰动态诊疗流程"],
        goal="疑诊、确诊、分型、急性失代偿处理、长期药物管理和随访的动态推荐路径",
        evidence_ids=evidence["diagnosis"],
    )
    stages = [
        {"code": "STAGE-CARD-HF-01-SUSPECTED-ASSESSMENT", "name": "心衰疑诊评估阶段", "goal": "识别呼吸困难、水肿、乏力等心衰线索并补基础检查。", "trigger": "症状/体征提示心衰或既往心脏病基础上出现容量负荷异常", "exit": "完成利钠肽、心电图、超声心动图等初筛"},
        {"code": "STAGE-CARD-HF-02-DIAGNOSIS-CONFIRMATION", "name": "心衰诊断确认阶段", "goal": "结合临床表现、利钠肽和心脏结构/功能证据确认诊断。", "trigger": "初筛结果支持心衰可能", "exit": "诊断标准明细满足或转入鉴别诊断"},
        {"code": "STAGE-CARD-HF-03-PHENOTYPE-ETIOLOGY", "name": "心衰分型与病因评估阶段", "goal": "按LVEF分型并识别急慢性、左右心及病因线索。", "trigger": "心衰诊断成立", "exit": "完成HFrEF/HFmrEF/HFpEF等分型与主要病因判断"},
        {"code": "STAGE-CARD-HF-04-ACUTE-DECOMPENSATION", "name": "心衰急性失代偿处理阶段", "goal": "根据淤血、低灌注和容量状态触发急性处理建议。", "trigger": "存在急性加重、明显淤血或低灌注", "exit": "急性风险稳定并进入长期管理"},
        {"code": "STAGE-CARD-HF-05-LONGTERM-MEDICATION", "name": "心衰长期药物管理阶段", "goal": "按分型触发利尿剂、ARNI/ACEI/ARB、β受体阻滞剂、MRA、SGLT2抑制剂等方案。", "trigger": "血流动力学稳定且需长期治疗", "exit": "形成长期治疗与监测计划"},
        {"code": "STAGE-CARD-HF-06-FOLLOWUP-PREVENTION", "name": "心衰随访与再入院预防阶段", "goal": "安排随访、监测肾功能电解质、利钠肽和用药安全。", "trigger": "出院、门诊稳定管理或治疗调整后", "exit": "完成随访闭环"},
    ]
    add_stages(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, pathway_code=pathway, stages=stages)
    add_exam_node(nodes, batch_id=batch_id, scope_target=scope, disease_code=disease, code="EXAM-CARD-CHEST-IMAGING-CDSS", name="胸部影像学检查", aliases=["胸片", "胸部X线", "胸部CT"], purpose="用于评估肺淤血、肺炎、COPD相关改变和其他呼吸系统鉴别诊断。")
    add_exam_node(nodes, batch_id=batch_id, scope_target=scope, disease_code=disease, code="LAB-CARD-RENAL-ELECTROLYTE-CDSS", name="肾功能与电解质", aliases=["肌酐", "eGFR", "血钾", "电解质"], purpose="用于心衰利尿剂、RAAS抑制剂、MRA、SGLT2抑制剂治疗前后安全监测。", exam_category="检验")
    add_exam_node(nodes, batch_id=batch_id, scope_target=scope, disease_code=disease, code="LAB-CARD-CBC-HB-CDSS", name="血常规与血红蛋白", aliases=["血红蛋白", "Hb", "血常规"], purpose="用于贫血、感染等心衰症状类似疾病的鉴别。", exam_category="检验")

    rules = [
        ("RULE-CARD-HF-01-INITIAL-NP-ECHO", "心衰疑诊利钠肽与超声评估规则", "疑似心衰时优先补齐利钠肽、心电图、超声心动图和LVEF，用于确认心衰及分型。", evidence["diagnosis"], stages[0]["code"], ["EXAM-CARD-01C3182D129E", "EXAM-ECG", "EXAM-TTE", "IND-LVEF"]),
        ("RULE-CARD-HF-02-DIAGNOSIS-TRIAD", "心衰诊断三要素规则", "心衰诊断应同时考虑症状体征、利钠肽升高以及心脏结构或功能异常证据。", evidence["diagnosis"], stages[1]["code"], ["DXC-CARD-C9F14771A730"]),
        ("RULE-CARD-HF-03-EF-PHENOTYPE", "心衰LVEF分型规则", "根据LVEF将心衰分为HFrEF、HFmrEF和HFpEF，并结合结构/舒张功能异常和利钠肽判断。", evidence["hfpef"], stages[2]["code"], ["IND-LVEF", "DXC-CARD-221AA46B58A3", "DXC-CARD-28280DD401C8", "DXC-CARD-2456E1DC2365"]),
        ("RULE-CARD-HF-04-ACUTE-CONGESTION", "急性心衰淤血处理规则", "急性心衰伴容量负荷或淤血时，应评估利尿剂治疗、肾功能电解质和血流动力学状态。", evidence["acute"], stages[3]["code"], ["PLAN-CARD-8DE84AB1F5CB", "MED-CARD-072B93AB8BC2", "LAB-CARD-RENAL-ELECTROLYTE-CDSS"]),
        ("RULE-CARD-HF-05-HFREF-GDMT", "HFrEF长期规范药物治疗规则", "HFrEF长期治疗优先形成包含ARNI/ACEI/ARB、β受体阻滞剂、MRA、SGLT2抑制剂等的规范治疗组合，并监测禁忌和耐受。", evidence["therapy"], stages[4]["code"], ["PLAN-CARD-4C0507593DD1", "MED-CARD-5C774D10CF46", "MED-CARD-E40082221530", "MED-CARD-C015B7A5655A", "MED-BETA-BLOCKER", "MED-CARD-E2FE14E667D7", "MED-CARD-3B504DD7AA33"]),
        ("RULE-CARD-HF-06-HFPEF-MANAGEMENT", "HFpEF综合管理规则", "HFpEF应重视利钠肽/结构功能证据、容量管理、合并症管理和SGLT2抑制剂等治疗选择。", evidence["hfpef"] + evidence["therapy"], stages[4]["code"], ["PLAN-CARD-71EEE6F12EA8", "MED-CARD-3B504DD7AA33", "MED-CARD-3B4D860E5C07"]),
        ("RULE-CARD-HF-07-FOLLOWUP-SAFETY", "心衰随访与用药安全监测规则", "治疗调整后需随访症状、体重、血压、肾功能、电解质及药物相关高钾血症风险。", evidence["follow"], stages[5]["code"], ["FU-CARD-8BCE7C3349BC", "LAB-CARD-RENAL-ELECTROLYTE-CDSS", "RISK-CARD-FDA995103C36"]),
    ]
    for code, name, logic, ev, stage, actions in rules:
        clinical_rule(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, code=code, name=name, rule_logic=logic, evidence_ids=ev)
        add_stage_rule(rels, batch_id=batch_id, scope_target=scope, stage=stage, rule_code=code, evidence_ids=ev)
        add_actions(rels, batch_id=batch_id, scope_target=scope, source=stage, targets=actions, rel_type="has_recommended_action", category="pathway")
        add_actions(rels, batch_id=batch_id, scope_target=scope, source=code, targets=actions, rel_type="recommends_action", category="cdss_rule", evidence_ids=ev)

    dx_components = {
        "DXC-CARD-C9F14771A730": ["RULE-CARD-HF-DX-COMP-CLINICAL-CONGESTION", "RULE-CARD-HF-DX-COMP-NP", "RULE-CARD-HF-DX-COMP-ECHO"],
        "DXC-CARD-F8A3379B0E95": ["RULE-CARD-HF-DX-COMP-ACUTE-ONSET", "RULE-CARD-HF-DX-COMP-CONGESTION-HYPOPERFUSION", "RULE-CARD-HF-DX-COMP-NP"],
        "DXC-CARD-ED581915E839": ["RULE-CARD-HF-DX-COMP-CHRONIC-SYMPTOM", "RULE-CARD-HF-DX-COMP-ECHO", "RULE-CARD-HF-DX-COMP-NP"],
        "DXC-CARD-221AA46B58A3": ["RULE-CARD-HF-DX-COMP-HFREF-LVEF"],
        "DXC-CARD-28280DD401C8": ["RULE-CARD-HF-DX-COMP-HFMREF-LVEF"],
        "DXC-CARD-2456E1DC2365": ["RULE-CARD-HF-DX-COMP-HFPEF-LVEF", "RULE-CARD-HF-DX-COMP-HFPEF-STRUCTURE"],
        "DXC-CARD-CE6F1213B83D": ["RULE-CARD-HF-DX-COMP-DIALYSIS-VOLUME", "RULE-CARD-HF-DX-COMP-ECHO"],
        "DXC-CARD-5A4BCEDA1085": ["RULE-CARD-HF-DX-COMP-POSTMI-HISTORY", "RULE-CARD-HF-DX-COMP-ECHO"],
        "DXC-CARD-25510C02A8C8": ["RULE-CARD-HF-DX-COMP-LEFT-PULMONARY", "RULE-CARD-HF-DX-COMP-ECHO"],
        "DXC-CARD-FB1FD85809E5": ["RULE-CARD-HF-DX-COMP-RIGHT-SYSTEMIC", "RULE-CARD-HF-DX-COMP-ECHO"],
    }
    component_defs = {
        "RULE-CARD-HF-DX-COMP-CLINICAL-CONGESTION": ("心衰症状体征组成规则", "呼吸困难、乏力、水肿、肺部啰音、颈静脉怒张等提示心衰的症状体征需作为诊断组成。", evidence["diagnosis"]),
        "RULE-CARD-HF-DX-COMP-NP": ("利钠肽诊断组成规则", "BNP或NT-proBNP升高支持心衰诊断，并可用于严重程度和预后判断。", evidence["diagnosis"]),
        "RULE-CARD-HF-DX-COMP-ECHO": ("超声心动图结构功能组成规则", "超声心动图用于确认心脏结构或功能异常，并提供LVEF等分型依据。", evidence["diagnosis"]),
        "RULE-CARD-HF-DX-COMP-ACUTE-ONSET": ("急性心衰起病组成规则", "急性新发或慢性心衰急性加重，伴快速出现或加重的症状体征，构成急性心衰判断要点。", evidence["acute"]),
        "RULE-CARD-HF-DX-COMP-CONGESTION-HYPOPERFUSION": ("急性心衰淤血低灌注组成规则", "急性心衰需评估肺/体循环淤血、低灌注、血压和容量状态。", evidence["acute"]),
        "RULE-CARD-HF-DX-COMP-CHRONIC-SYMPTOM": ("慢性心衰长期症状组成规则", "慢性呼吸困难、运动耐量下降、水肿等长期表现与结构功能异常共同支持慢性心衰。", evidence["diagnosis"]),
        "RULE-CARD-HF-DX-COMP-HFREF-LVEF": ("HFrEF射血分数组成规则", "LVEF降低支持HFrEF分型，需结合心衰症状体征和超声结果。", evidence["hfpef"]),
        "RULE-CARD-HF-DX-COMP-HFMREF-LVEF": ("HFmrEF射血分数组成规则", "LVEF轻度降低时需结合心衰表现、利钠肽和结构/舒张功能异常判断HFmrEF。", evidence["hfpef"]),
        "RULE-CARD-HF-DX-COMP-HFPEF-LVEF": ("HFpEF射血分数组成规则", "LVEF保留不排除心衰，需结合心衰表现、利钠肽和结构/舒张功能异常。", evidence["hfpef"]),
        "RULE-CARD-HF-DX-COMP-HFPEF-STRUCTURE": ("HFpEF结构舒张异常组成规则", "左房扩大、左室肥厚或舒张功能异常等支持HFpEF诊断。", evidence["hfpef"]),
        "RULE-CARD-HF-DX-COMP-DIALYSIS-VOLUME": ("透析患者容量状态组成规则", "透析患者需结合容量状态、利钠肽趋势和心脏结构功能异常判断慢性心衰。", evidence["diagnosis"]),
        "RULE-CARD-HF-DX-COMP-POSTMI-HISTORY": ("心梗后心衰病史组成规则", "明确心肌梗死病史后出现心衰表现及结构功能异常，支持心梗后心衰。", evidence["diagnosis"]),
        "RULE-CARD-HF-DX-COMP-LEFT-PULMONARY": ("左心衰肺淤血组成规则", "肺淤血、呼吸困难、端坐呼吸等以肺循环淤血为主的表现支持左心衰。", evidence["diagnosis"]),
        "RULE-CARD-HF-DX-COMP-RIGHT-SYSTEMIC": ("右心衰体循环淤血组成规则", "颈静脉怒张、肝大、下肢水肿等体循环淤血表现支持右心衰。", evidence["diagnosis"]),
    }
    for rule_code, (name, logic, ev) in component_defs.items():
        clinical_rule(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, code=rule_code, name=name, rule_logic=logic, evidence_ids=ev, rule_type="diagnostic_component")
    for dx_code, comps in dx_components.items():
        for comp in comps:
            ev = component_defs[comp][2]
            add_diagnostic_component(rels, batch_id=batch_id, scope_target=scope, dx_code=dx_code, component_rule=comp, evidence_ids=ev)

    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-HF-COPD-ASTHMA", ddx_name="慢阻肺或支气管哮喘", point_rule="RULE-CARD-HF-DDX-COPD-ASTHMA", point_name="心衰与慢阻肺/哮喘鉴别规则", point_logic="以喘息、慢性咳痰、肺功能或胸部影像提示气道疾病为主时，应与心衰呼吸困难鉴别。", evidence_ids=evidence["diagnosis"], exclusion_exams=["EXAM-CARD-CHEST-IMAGING-CDSS", "EXAM-CARD-01C3182D129E", "EXAM-TTE"])
    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-HF-PNEUMONIA", ddx_name="肺炎", point_rule="RULE-CARD-HF-DDX-PNEUMONIA", point_name="心衰与肺炎鉴别规则", point_logic="发热、感染指标升高、局灶肺部影像异常时，应与心衰肺淤血鉴别。", evidence_ids=evidence["diagnosis"], exclusion_exams=["EXAM-CARD-CHEST-IMAGING-CDSS", "LAB-CARD-CBC-HB-CDSS"])
    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-HF-RENAL-VOLUME", ddx_name="肾功能不全或容量负荷过多", point_rule="RULE-CARD-HF-DDX-RENAL-VOLUME", point_name="心衰与肾性容量负荷鉴别规则", point_logic="水肿或呼吸困难合并肾功能异常时，应结合超声心动图、利钠肽和容量状态区分心衰与肾性容量负荷。", evidence_ids=evidence["diagnosis"], exclusion_exams=["LAB-CARD-RENAL-ELECTROLYTE-CDSS", "EXAM-CARD-01C3182D129E", "EXAM-TTE"])
    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-HF-ANEMIA", ddx_name="贫血", point_rule="RULE-CARD-HF-DDX-ANEMIA", point_name="心衰与贫血相关乏力气促鉴别规则", point_logic="乏力、气促伴血红蛋白降低时，应鉴别贫血导致的症状加重或与心衰并存。", evidence_ids=evidence["diagnosis"], exclusion_exams=["LAB-CARD-CBC-HB-CDSS"])
    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-881C77E90E42", ddx_name="肺栓塞", point_rule="RULE-CARD-HF-DDX-PE", point_name="心衰与肺栓塞鉴别规则", point_logic="突发呼吸困难、低氧、胸痛或栓塞风险较高时，应与肺栓塞鉴别。", evidence_ids=evidence["diagnosis"], exclusion_exams=["EXAM-CARD-CHEST-IMAGING-CDSS", "EXAM-TTE"])
    return out, list(nodes.values()), list(rels.values()), make_matrices(nodes, rels)


def build_af() -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    batch_id = "BATCH-CARD-AF-20260701-001"
    scope = "心房颤动"
    disease = "DIS-CARD-ARR-AF"
    out = COLLECTION / "BATCH-CARD-AF-20260701-001_房颤_AtrialFibrillation" / "09_专病CDSS动态路径样板_dynamic_cdss_pathway" / "AF_20260707"
    nodes: dict[str, dict[str, Any]] = {}
    rels: dict[tuple[str, str, str], dict[str, Any]] = {}
    ev = {
        "diagnosis": ["EVD-028A2F2BA76DE48E34B3-AF", "EVD-D4005792C9B076BFC7E1-AF"],
        "risk": ["EVD-1BDBEB039CDD54E3D3A7-AF"],
        "therapy": ["EVD-00CF88A508BB4F312338-AF", "EVD-8A9E9D41F2BC962BEB8B-AF"],
        "ablation": ["EVD-01226DDDBF2566E8F84E-AF", "EVD-72EB22EEF00323FB3AD9-AF"],
    }
    pathway = "PATHWAY-CARD-ARR-AF-DYNAMIC-CDSS"
    clinical_pathway(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, disease_name=scope, pathway_code=pathway, pathway_name="心房颤动专病动态CDSS路径", aliases=["AF动态诊疗路径", "房颤动态诊疗流程"], goal="心电图确认、卒中/出血风险评估、抗凝、急性复律/心率控制、节律控制和随访的动态路径", evidence_ids=ev["diagnosis"])
    stages = [
        {"code": "STAGE-CARD-ARR-AF-01-ECG-CONFIRMATION", "name": "房颤心电图确认阶段", "goal": "对心悸、脉搏不齐或疑似房颤患者补心电图/动态心电图并确认诊断。", "trigger": "脉搏不齐、心悸、卒中风险评估或设备提示房颤", "exit": "心电证据确认或排除房颤"},
        {"code": "STAGE-CARD-ARR-AF-02-STROKE-BLEEDING-RISK", "name": "房颤卒中出血风险评估阶段", "goal": "计算CHA2DS2-VASc和HAS-BLED，识别抗凝获益与出血风险。", "trigger": "房颤诊断成立", "exit": "形成抗凝风险分层"},
        {"code": "STAGE-CARD-ARR-AF-03-ANTICOAGULATION-DECISION", "name": "房颤抗凝策略决策阶段", "goal": "根据卒中风险、出血风险、肾功能和禁忌推荐抗凝方案。", "trigger": "卒中风险达到抗凝评估阈值", "exit": "明确抗凝药物或禁忌/延迟原因"},
        {"code": "STAGE-CARD-ARR-AF-04-ACUTE-CONTROL", "name": "房颤急性控制阶段", "goal": "根据血流动力学稳定性触发复律、心率控制或急诊处理。", "trigger": "房颤伴快速心室率、症状明显或血流动力学不稳定", "exit": "急性风险稳定"},
        {"code": "STAGE-CARD-ARR-AF-05-RHYTHM-ABLATION", "name": "房颤节律控制与消融评估阶段", "goal": "评估节律控制、复律、导管消融适应证和随访策略。", "trigger": "症状性房颤、复发、药物控制不佳或适合节律控制", "exit": "形成节律控制/消融计划"},
        {"code": "STAGE-CARD-ARR-AF-06-FOLLOWUP", "name": "房颤随访综合管理阶段", "goal": "监测复发、抗凝安全、危险因素和生活方式管理。", "trigger": "治疗后或长期管理", "exit": "随访闭环"},
    ]
    add_stages(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, pathway_code=pathway, stages=stages)
    rules = [
        ("RULE-CARD-ARR-AF-01-ECG-DIAGNOSIS", "房颤心电图诊断规则", "房颤诊断需心电证据支持，重点识别RR间期绝对不规则和P波缺如等特征，必要时使用动态心电图。", ev["diagnosis"], stages[0]["code"], ["EXAM-ECG", "EXAM-HOLTER", "DXC-CARD-5996B55AA97D"]),
        ("RULE-CARD-ARR-AF-02-RISK-SCORES", "房颤卒中出血评分规则", "房颤确诊后应评估CHA2DS2-VASc卒中风险和HAS-BLED出血风险，用于抗凝决策。", ev["risk"], stages[1]["code"], ["RISK-CARD-BD6FBD0D2712", "RISK-CARD-E21D88A4688D", "RISK-CARD-7371F77D04B5"]),
        ("RULE-CARD-ARR-AF-03-ANTICOAGULATION", "房颤抗凝治疗规则", "需抗凝者结合肾功能、出血风险和禁忌选择抗凝治疗，药物类别必须关联到具体药物。", ev["risk"] + ev["therapy"], stages[2]["code"], ["PLAN-CARD-A1C4E6332D38", "MED-CARD-TEXT-EE219280A7", "MED-CARD-68E5765B76ED", "MED-CARD-C3B888F489B9", "MED-CARD-38524B4E5194", "MED-CARD-FC4A5B5D6C12", "MED-CARD-81B5F958C0F3"]),
        ("RULE-CARD-ARR-AF-04-ACUTE-CONTROL", "房颤急性复律/心率控制规则", "房颤急性发作时先判断血流动力学稳定性；不稳定者考虑同步电复律，稳定者根据情况选择心率或节律控制。", ev["therapy"], stages[3]["code"], ["PLAN-CARD-TEXT-7CC38FBA6F", "PLAN-CARD-108E680ADD4F", "MED-BETA-BLOCKER", "MED-CARD-0401DB9741D8", "MED-CARD-C685CE7163F5", "MED-AMIODARONE"]),
        ("RULE-CARD-ARR-AF-05-RHYTHM-ABLATION", "房颤节律控制与导管消融规则", "症状性或反复发作房颤可评估节律控制、复律和导管消融，同时保留抗凝风险管理。", ev["ablation"], stages[4]["code"], ["PLAN-CARD-40AB27F53C05", "PLAN-CARD-5C9E41087192", "PROC-CARD-A89DB5C678D2"]),
        ("RULE-CARD-ARR-AF-06-FOLLOWUP", "房颤随访规则", "房颤长期管理需随访心律、症状、抗凝安全、卒中/出血风险和危险因素控制。", ev["ablation"], stages[5]["code"], ["FU-CARD-CE0CF6305FAF", "RISK-CARD-BD6FBD0D2712", "RISK-CARD-E21D88A4688D"]),
    ]
    for code, name, logic, evid, stage, actions in rules:
        clinical_rule(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, code=code, name=name, rule_logic=logic, evidence_ids=evid)
        add_stage_rule(rels, batch_id=batch_id, scope_target=scope, stage=stage, rule_code=code, evidence_ids=evid)
        add_actions(rels, batch_id=batch_id, scope_target=scope, source=stage, targets=actions, rel_type="has_recommended_action", category="pathway")
        add_actions(rels, batch_id=batch_id, scope_target=scope, source=code, targets=actions, rel_type="recommends_action", category="cdss_rule", evidence_ids=evid)
    # 服务器已存在“抗凝药物 -> 具体药物”语义关系。本回补包只在推荐规则中引用
    # 抗凝类别和具体药物，不替换既有 has_specific_medication 关系 ID。

    comp_defs = {
        "RULE-CARD-ARR-AF-DX-COMP-ECG-RR": ("房颤RR不规则心电组成规则", "房颤诊断需识别RR间期绝对不规则等心电特征。", ev["diagnosis"]),
        "RULE-CARD-ARR-AF-DX-COMP-NO-P": ("房颤P波缺如组成规则", "心电图P波缺如或房颤波等表现支持房颤诊断。", ev["diagnosis"]),
        "RULE-CARD-ARR-AF-DX-COMP-DOCUMENTATION": ("房颤记录证据组成规则", "12导联心电图或动态心电图记录到房颤发作可作为诊断证据。", ev["diagnosis"]),
    }
    for code, (name, logic, evid) in comp_defs.items():
        clinical_rule(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, code=code, name=name, rule_logic=logic, evidence_ids=evid, rule_type="diagnostic_component")
        add_diagnostic_component(rels, batch_id=batch_id, scope_target=scope, dx_code="DXC-CARD-5996B55AA97D", component_rule=code, evidence_ids=evid)
    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-ARR-AFL", ddx_name="心房扑动", point_rule="RULE-CARD-ARR-AF-DDX-AFL", point_name="房颤与心房扑动鉴别规则", point_logic="规则性房扑波、固定或规律房室传导提示房扑，应与RR绝对不规则的房颤鉴别。", evidence_ids=ev["diagnosis"], exclusion_exams=["EXAM-ECG", "EXAM-HOLTER"])
    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-AF-SVT", ddx_name="室上性心动过速", point_rule="RULE-CARD-ARR-AF-DDX-SVT", point_name="房颤与室上性心动过速鉴别规则", point_logic="规则性窄QRS心动过速更支持SVT，需与房颤伴快速心室率鉴别。", evidence_ids=ev["diagnosis"], exclusion_exams=["EXAM-ECG", "EXAM-HOLTER"])
    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-AF-AT", ddx_name="房性心动过速", point_rule="RULE-CARD-ARR-AF-DDX-AT", point_name="房颤与房性心动过速鉴别规则", point_logic="可辨认异位P波和较规则房性节律时需与房颤鉴别。", evidence_ids=ev["diagnosis"], exclusion_exams=["EXAM-ECG", "EXAM-HOLTER"])
    return out, list(nodes.values()), list(rels.values()), make_matrices(nodes, rels)


def build_svt_afl() -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    batch_id = "BATCH-CARD-SVT-AFL-20260703-001"
    scope = "室上性心动过速及心房扑动"
    disease = "DIS-CARD-ARR-SVT"
    out = COLLECTION / "BATCH-CARD-SVT-AFL-20260703-001_室上速房扑_SVT_AtrialFlutter" / "09_专病CDSS动态路径样板_dynamic_cdss_pathway" / "SVT_AFL_20260707"
    nodes: dict[str, dict[str, Any]] = {}
    rels: dict[tuple[str, str, str], dict[str, Any]] = {}
    ev = {
        "diagnosis": ["EVD-011B40A3FEC8FE56CB5D-SVT", "EVD-C9950FFDF14F096EA0B8-SVT"],
        "acute": ["EVD-09B1E465B34B6085BFBF-SVT", "EVD-008C3C73C794EC14A074-SVT", "EVD-8E8277EACCB8AF52483A-SVT"],
        "variant": ["EVD-E481A267ED3BA48B080C-SVT", "EVD-091DCA6C247FAD9B4430-AFL", "EVD-52F92D38A1E6498A4D09-WPW"],
        "ablation": ["EVD-01226DDDBF2566E8F84E-SVT"],
    }
    pathway = "PATHWAY-CARD-ARR-SVT-AFL-DYNAMIC-CDSS"
    clinical_pathway(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, disease_name=scope, pathway_code=pathway, pathway_name="室上速/房扑专病动态CDSS路径", aliases=["SVT/AFL动态诊疗路径", "室上速房扑动态诊疗流程"], goal="血流动力学评估、心电诊断、急性终止、机制分型、消融/抗凝和随访的动态路径", evidence_ids=ev["diagnosis"])
    stages = [
        {"code": "STAGE-CARD-ARR-SVT-AFL-01-HEMODYNAMIC", "name": "室上速/房扑血流动力学评估阶段", "goal": "先判断血流动力学稳定性和需急诊处理的风险。", "trigger": "突发心悸、心动过速、窄QRS或疑似室上速/房扑", "exit": "稳定性判断完成"},
        {"code": "STAGE-CARD-ARR-SVT-AFL-02-ECG-DIAGNOSIS", "name": "室上速/房扑心电诊断阶段", "goal": "记录12导联心电图，区分窄/宽QRS、规则/不规则及房扑、AVNRT、AVRT、AT、WPW。", "trigger": "心动过速发作中或有发作证据", "exit": "完成机制初步分型或进入鉴别诊断"},
        {"code": "STAGE-CARD-ARR-SVT-AFL-03-ACUTE-TERMINATION", "name": "室上速急性终止阶段", "goal": "稳定患者优先迷走神经刺激和腺苷；不稳定者同步电复律。", "trigger": "明确或高度怀疑规则窄QRS SVT", "exit": "心律转复或进入进一步处理"},
        {"code": "STAGE-CARD-ARR-SVT-AFL-04-MECHANISM-ABLATION", "name": "机制分型与消融评估阶段", "goal": "按AVNRT、AVRT、WPW、AT等机制评估电生理和消融。", "trigger": "复发、症状明显或需根治策略", "exit": "形成消融或长期管理计划"},
        {"code": "STAGE-CARD-ARR-SVT-AFL-05-AFL-ANTICOAGULATION", "name": "房扑抗凝与复律评估阶段", "goal": "房扑按卒中风险、发作持续时间和复律/消融计划评估抗凝。", "trigger": "诊断或疑似心房扑动", "exit": "明确抗凝/复律/消融策略"},
        {"code": "STAGE-CARD-ARR-SVT-AFL-06-FOLLOWUP", "name": "室上速/房扑随访阶段", "goal": "随访复发、药物安全、消融后管理和危险信号。", "trigger": "急性处理后、消融后或长期管理", "exit": "随访闭环"},
    ]
    add_stages(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, pathway_code=pathway, stages=stages)
    rules = [
        ("RULE-CARD-ARR-SVT-AFL-01-STABILITY", "室上速/房扑血流动力学稳定性规则", "心动过速患者先判断低血压、休克、胸痛、心衰等不稳定表现；不稳定者优先同步电复律。", ev["acute"], stages[0]["code"], ["PROC-CARD-7FD747D740F0", "PLAN-CARD-108E680ADD4F"]),
        ("RULE-CARD-ARR-SVT-AFL-02-ECG-MECHANISM", "室上速/房扑心电机制分型规则", "记录12导联心电图，结合QRS宽度、节律规则性、P波/扑动波和预激表现区分SVT、AFL、AVNRT、AVRT、AT、WPW。", ev["diagnosis"], stages[1]["code"], ["EXAM-ECG", "EXAM-HOLTER", "DXC-CARD-FD25F5A6CB2C", "DXC-CARD-04B9595EC8CA"]),
        ("RULE-CARD-ARR-SVT-AFL-03-ACUTE-VAGAL-ADENOSINE", "稳定窄QRS SVT急性终止规则", "稳定规则窄QRS SVT可先行迷走神经刺激，未终止时考虑腺苷。", ev["acute"], stages[2]["code"], ["PLAN-CARD-741F70867FDD", "PROC-CARD-7FE0AC763703", "PROC-CARD-B13C58DD2614", "MED-CARD-33087B86B32A"]),
        ("RULE-CARD-ARR-SVT-AFL-04-ABLATION", "复发性SVT消融评估规则", "复发、症状明显或药物控制不佳的SVT可评估导管/射频消融。", ev["ablation"], stages[3]["code"], ["PLAN-CARD-5C9E41087192", "PROC-CARD-4777F9B8D8F3"]),
        ("RULE-CARD-ARR-SVT-AFL-05-AFL-ANTICOAG", "房扑抗凝复律规则", "心房扑动需结合卒中风险、发作持续时间、复律或消融计划评估抗凝。", ev["variant"], stages[4]["code"], ["PLAN-CARD-85C337BCB2D5", "PLAN-CARD-A1C4E6332D38", "MED-CARD-TEXT-EE219280A7"]),
        ("RULE-CARD-ARR-SVT-AFL-06-FOLLOWUP", "室上速/房扑随访规则", "治疗后需随访复发、症状、药物不良反应和消融后恢复。", ev["variant"], stages[5]["code"], ["FU-CARD-00103E0E5112", "FU-CARD-39BD08E82048"]),
    ]
    for code, name, logic, evid, stage, actions in rules:
        clinical_rule(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, code=code, name=name, rule_logic=logic, evidence_ids=evid)
        add_stage_rule(rels, batch_id=batch_id, scope_target=scope, stage=stage, rule_code=code, evidence_ids=evid)
        add_actions(rels, batch_id=batch_id, scope_target=scope, source=stage, targets=actions, rel_type="has_recommended_action", category="pathway")
        add_actions(rels, batch_id=batch_id, scope_target=scope, source=code, targets=actions, rel_type="recommends_action", category="cdss_rule", evidence_ids=evid)

    component_defs = {
        "RULE-CARD-ARR-SVT-DX-COMP-ECG-DOCUMENT": ("SVT心电记录组成规则", "SVT诊断需心电图记录到心动过速发作，并结合QRS宽度和节律特征判断。", ev["diagnosis"]),
        "RULE-CARD-ARR-SVT-DX-COMP-NARROW-REGULAR": ("规则窄QRS心动过速组成规则", "规则窄QRS心动过速支持常见SVT机制，但需结合P波和反应鉴别。", ev["diagnosis"]),
        "RULE-CARD-ARR-AFL-DX-COMP-FLUTTER-WAVE": ("房扑扑动波组成规则", "锯齿样扑动波及相对规律房室传导支持心房扑动诊断。", ev["variant"]),
        "RULE-CARD-ARR-AVNRT-DX-COMP-SHORT-RP": ("AVNRT短RP组成规则", "短RP或逆行P波等心电表现支持AVNRT机制判断。", ev["diagnosis"]),
        "RULE-CARD-ARR-AVRT-DX-COMP-ACCESSORY": ("AVRT旁路参与组成规则", "旁路参与和预激相关表现支持AVRT机制判断。", ev["variant"]),
        "RULE-CARD-ARR-WPW-DX-COMP-PREEXCITATION": ("WPW预激心电组成规则", "短PR间期、δ波和QRS增宽等预激表现支持WPW诊断。", ev["variant"]),
        "RULE-CARD-ARR-AT-DX-COMP-ATRIAL-P": ("房速异位P波组成规则", "规则房性心动过速伴异位P波或房性激动序列支持房性心动过速。", ev["diagnosis"]),
    }
    for code, (name, logic, evid) in component_defs.items():
        clinical_rule(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, code=code, name=name, rule_logic=logic, evidence_ids=evid, rule_type="diagnostic_component")
    for dx, comps in {
        "DXC-CARD-FD25F5A6CB2C": ["RULE-CARD-ARR-SVT-DX-COMP-ECG-DOCUMENT", "RULE-CARD-ARR-SVT-DX-COMP-NARROW-REGULAR"],
        "DXC-CARD-04B9595EC8CA": ["RULE-CARD-ARR-AFL-DX-COMP-FLUTTER-WAVE"],
        "DXC-CARD-9A428C9E2C3C": ["RULE-CARD-ARR-AVNRT-DX-COMP-SHORT-RP"],
        "DXC-CARD-96EF831225B2": ["RULE-CARD-ARR-AVRT-DX-COMP-ACCESSORY"],
        "DXC-CARD-C4C1DC3E0CB5": ["RULE-CARD-ARR-WPW-DX-COMP-PREEXCITATION"],
        "DXC-CARD-204766CBAB68": ["RULE-CARD-ARR-AT-DX-COMP-ATRIAL-P"],
    }.items():
        for comp in comps:
            add_diagnostic_component(rels, batch_id=batch_id, scope_target=scope, dx_code=dx, component_rule=comp, evidence_ids=component_defs[comp][2])
    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-95D3594A06C8", ddx_name="室性心动过速", point_rule="RULE-CARD-ARR-SVT-DDX-VT", point_name="SVT与室性心动过速鉴别规则", point_logic="宽QRS或血流动力学不稳定心动过速需优先排除室性心动过速，避免按普通SVT路径误处理。", evidence_ids=ev["diagnosis"], exclusion_exams=["EXAM-ECG"], may_block_actions=["MED-CARD-33087B86B32A"])
    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-SVT-AF", ddx_name="心房颤动伴快速心室率", point_rule="RULE-CARD-ARR-SVT-DDX-AF-RVR", point_name="SVT与房颤伴快速心室率鉴别规则", point_logic="RR间期绝对不规则提示房颤伴快速心室率，应与规则SVT鉴别。", evidence_ids=ev["diagnosis"], exclusion_exams=["EXAM-ECG", "EXAM-HOLTER"])
    add_ddx(nodes, rels, batch_id=batch_id, scope_target=scope, disease_code=disease, ddx_code="DDX-CARD-ARR-AFL", ddx_name="心房扑动", point_rule="RULE-CARD-ARR-SVT-DDX-AFL", point_name="SVT与心房扑动鉴别规则", point_logic="扑动波和固定或规律房室传导提示房扑，应与其他窄QRS SVT鉴别。", evidence_ids=ev["variant"], exclusion_exams=["EXAM-ECG", "EXAM-HOLTER"], create_ddx_node=False)
    return out, list(nodes.values()), list(rels.values()), make_matrices(nodes, rels)


def make_matrices(nodes: dict[str, dict[str, Any]], rels: dict[tuple[str, str, str], dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    node_name = {code: item.get("name", "") for code, item in nodes.items()}
    for item in rels.values():
        rows.append(
            {
                "source_code": item["source_code"],
                "relationType": item["relationType"],
                "target_code": item["target_code"],
                "source_name_if_delta": node_name.get(item["source_code"], ""),
                "target_name_if_delta": node_name.get(item["target_code"], ""),
                "evidence_ids": "|".join(item.get("evidence_ids") or []),
                "clinical_review_status": item.get("clinical_review_status", ""),
                "cdss_release_level": item.get("cdss_release_level", ""),
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_package(out: Path, nodes: list[dict[str, Any]], rels: list[dict[str, Any]], matrix: list[dict[str, str]]) -> dict[str, Any]:
    nodes = sorted(nodes, key=lambda item: item["code"])
    rels = sorted(rels, key=lambda item: (item["source_code"], item["relationType"], item["target_code"]))
    write_jsonl(out / "delta_nodes_upsert.jsonl", nodes)
    write_jsonl(out / "delta_relations_add.jsonl", rels)
    write_csv(out / "cdss_executable_pathway.csv", [row for row in matrix if row["relationType"] in {"has_clinical_pathway", "has_pathway_stage", "next_pathway_stage", "has_stage_rule", "has_recommended_action", "recommends_action"}])
    write_csv(out / "cdss_rule_action_matrix.csv", [row for row in matrix if row["relationType"] in {"has_stage_rule", "recommends_action", "blocks_action", "may_block_action"}])
    write_csv(out / "cdss_diagnosis_criteria_detail_matrix.csv", [row for row in matrix if row["relationType"] == "has_diagnostic_component"])
    write_csv(out / "cdss_differential_diagnosis_matrix.csv", [row for row in matrix if row["relationType"] in {"has_differential_diagnosis", "has_differential_point", "requires_exclusion_exam", "may_block_action"}])
    summary = {
        "output_dir": str(out),
        "node_count": len(nodes),
        "relation_count": len(rels),
        "node_entity_counts": dict(Counter(row["entityType"] for row in nodes)),
        "relation_type_counts": dict(Counter(row["relationType"] for row in rels)),
        "hard_rule_notes": [
            "PathwayStage名称不得与TreatmentPlan名称重名。",
            "DiagnosisCriteria必须通过has_diagnostic_component连接到ClinicalRule。",
            "DifferentialDiagnosis必须通过has_differential_point/requires_exclusion_exam/may_block_action形成下级内容。",
            "Medication类别节点必须通过has_specific_medication连接到具体药物。",
            "formal_cdss_ready保持false，等待临床使用效果审核闭环。",
        ],
    }
    (out / "dynamic_cdss_backfill_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "README_开发交接.md").write_text(
        f"""# 动态CDSS路径回补包

本目录用于把已有静态知识图谱补成可按患者状态触发的专病诊疗流程。

## 可导入文件

- `delta_nodes_upsert.jsonl`：新增/更新 ClinicalPathway、PathwayStage、ClinicalRule、必要的检查/鉴别诊断节点。
- `delta_relations_add.jsonl`：新增流程、规则、诊断标准明细、鉴别诊断明细、证据链关系。

## 给前端/流程引擎的使用方式

1. 先查疾病节点 `has_clinical_pathway` 得到 ClinicalPathway。
2. 通过 `has_pathway_stage` 和 `next_pathway_stage` 取得阶段顺序。
3. 每个 PathwayStage 读取 `trigger_condition`、`exit_condition` 判断是否进入/退出阶段。
4. 阶段通过 `has_stage_rule` 找 ClinicalRule。
5. ClinicalRule 通过 `recommends_action`、`blocks_action`、`may_block_action` 触发检查、检验、药物、手术、治疗方案等动作。
6. 诊断标准不要只显示标题；必须继续查 `DiagnosisCriteria -[:has_diagnostic_component]-> ClinicalRule`。
7. 鉴别诊断不要只显示标题；必须继续查 `DifferentialDiagnosis -[:has_differential_point|requires_exclusion_exam|may_block_action]-> ...`。

## 本包统计

- 节点：{len(nodes)}
- 关系：{len(rels)}
- 关系类型：{json.dumps(summary["relation_type_counts"], ensure_ascii=False)}
""",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    outputs = []
    for builder in (build_hf, build_af, build_svt_afl):
        out, nodes, rels, matrix = builder()
        outputs.append(write_package(out, nodes, rels, matrix))
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
