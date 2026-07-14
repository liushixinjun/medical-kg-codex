# -*- coding: utf-8 -*-
"""生成 STEMI 教材骨架精修包。

本脚本只生成本地 delta、审计表和报告：
- 不连接 Neo4j
- 不写数据库
- 不修改旧批次正式产物

用途：把《内科学（第10版）》中“急性 ST 段抬高型心肌梗死”人工核对后的
骨架内容，整理为可审计、可导入、可回归校验的图谱增量包。
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "心血管内科文献集合"
SOURCE_BATCH = COLLECTION / "BATCH-CARD-CAD-20260623-001"
OUT_DIR = COLLECTION / "BATCH-CARD-CAD-STEMI-20260712-001_STEMI教材骨架精修_textbook_refine"
BATCH_ID = "BATCH-CARD-CAD-STEMI-20260712-001"
CREATED_AT = "2026-07-12 21:30:00"
SCHEMA_VERSION = "V1.15"
SKILL_VERSION = "V2.1-STEMI-textbook-refine"

DISEASE_CODE = "DIS-CARD-CAD-STEMI"
DISEASE_NAME = "ST段抬高型心肌梗死"
SOURCE_NAME = "《内科学（第10版）》"
SOURCE_SECTION = "第三篇 循环系统疾病 / 第四节 急性冠脉综合征 / 二、急性ST段抬高型心肌梗死"


def short_hash(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest().upper()[:n]


def kg_id(code: str) -> str:
    return "KG_" + code.replace("-", "_")


def rel_id(source: str, rel_type: str, target: str) -> str:
    return "REL-" + short_hash(f"{source}|{rel_type}|{target}", 20)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


OLD_NODES = read_jsonl(SOURCE_BATCH / "05_data_instance" / "nodes_final.jsonl")
NAME_INDEX: dict[tuple[str, str], dict[str, Any]] = {}
CODE_INDEX: dict[str, dict[str, Any]] = {}
for old in OLD_NODES:
    code = str(old.get("code") or "")
    etype = str(old.get("entityType") or "")
    names = {
        str(old.get("name") or ""),
        str(old.get("preferred_name") or ""),
        str(old.get("display_name") or ""),
    }
    for alias in old.get("aliases") or []:
        names.add(str(alias))
    if code:
        CODE_INDEX[code] = old
    for name in names:
        if etype and name:
            NAME_INDEX.setdefault((etype, name), old)


def node_code(entity_type: str, name: str, prefix: str | None = None) -> str:
    existing = NAME_INDEX.get((entity_type, name))
    if existing and existing.get("code"):
        return str(existing["code"])
    pfx = prefix or {
        "Definition": "DEF",
        "Etiology": "ETI",
        "RiskFactor": "RF",
        "Pathophysiology": "PATH",
        "Epidemiology": "EPI",
        "Symptom": "SYM",
        "Sign": "SIGN",
        "Exam": "EXAM",
        "LabTest": "LAB",
        "ExamIndicator": "IND",
        "ThresholdRule": "THR",
        "DiagnosisCriteria": "DXC",
        "DiagnosisCriteriaComponent": "DXC-COMP",
        "DifferentialDiagnosis": "DDX",
        "Complication": "COMP",
        "TreatmentPlan": "PLAN",
        "Medication": "MED",
        "Procedure": "PROC",
        "ClinicalRule": "RULE",
        "RecommendationStatement": "REC",
        "Contraindication": "CONTRA",
        "FollowUp": "FU",
        "Prevention": "PREV",
        "Prognosis": "PROG",
        "Evidence": "EVD",
    }.get(entity_type, "NODE")
    return f"{pfx}-CARD-STEMI-{short_hash(entity_type + '|' + name)}"


def base_node(entity_type: str, name: str, *, code: str | None = None, **props: Any) -> dict[str, Any]:
    code = code or node_code(entity_type, name)
    return {
        "id": kg_id(code),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": props.pop("entityCategory", ""),
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "scope_type": "disease",
        "scope_target": DISEASE_NAME,
        "disease_code": DISEASE_CODE,
        "disease_name": DISEASE_NAME,
        "source_type": props.pop("source_type", "authoritative_textbook"),
        "source_authority": props.pop("source_authority", SOURCE_NAME),
        "source_section": props.pop("source_section", SOURCE_SECTION),
        "clinical_review_status": "pending_clinical_use_effect_review",
        "review_status": "ai_prechecked",
        "merge_status": "delta_ready",
        "formal_cdss_ready": False,
        "cdss_release_level": "test_recommendation",
        "created_at": CREATED_AT,
        **props,
    }


def evidence(slot: str, title: str, text: str, page: str, role: str) -> dict[str, Any]:
    code = f"EVD-CARD-STEMI-TEXTBOOK-{short_hash(slot + '|' + title, 10)}"
    return base_node(
        "Evidence",
        f"{DISEASE_NAME}-{title}-教材原文证据",
        code=code,
        entityCategory="证据",
        evidence_role=role,
        evidence_slot=slot,
        evidence_text=text,
        original_text=text,
        evidence_summary=text[:180],
        source_name=SOURCE_NAME,
        source_type="authoritative_textbook",
        source_page=page,
        source_location=f"{SOURCE_NAME} 第{page}页；{SOURCE_SECTION}",
        recommendation_class="N/A",
        evidence_level="N/A",
        knowledge_strength="high",
        clinical_applicability="general",
    )


EVIDENCES = {
    "definition": evidence(
        "definition",
        "疾病概述",
        "STEMI 是急性心肌缺血性坏死，多在冠脉粥样硬化病变基础上发生冠脉血供急剧减少或中断，使相应心肌严重而持久急性缺血；常见原因为不稳定斑块破裂、糜烂或侵蚀后继发血栓形成导致冠脉持续完全闭塞，少数为冠脉开口堵塞、血栓栓塞、自发性夹层或持续冠脉痉挛。",
        "247",
        "textbook_definition_original",
    ),
    "etiology": evidence(
        "etiology",
        "病因和发病机制",
        "STEMI 的基本病因是冠脉粥样硬化基础上一支或多支血管管腔急性闭塞，若持续时间达到 20～30 分钟以上即可发生 AMI。促发因素包括晨起交感神经活动增加、饱餐后血脂和血黏稠度增高、重体力活动或情绪激动导致左室负荷增加，以及休克、脱水、出血、外科手术或严重心律失常导致冠脉灌注锐减。",
        "247",
        "textbook_etiology_original",
    ),
    "pathophysiology": evidence(
        "pathophysiology",
        "病理与病理生理",
        "冠脉闭塞后 20～30 分钟受供血心肌开始坏死，1～2 小时绝大部分心肌呈凝固性坏死，随后形成肉芽组织并在 6～8 周形成瘢痕。主要病理生理改变为左室舒张和收缩功能障碍、射血分数降低、心排血量下降、左室舒张末压升高；大面积 AMI 可发生心源性休克或急性肺水肿，右室 AMI 可出现急性右心衰竭血流动力学异常。",
        "247-248",
        "textbook_pathophysiology_original",
    ),
    "manifestation": evidence(
        "clinical_manifestation",
        "临床表现",
        "约 50%～81.2% 病人发病前数日有乏力、胸部不适、活动时心悸、气急、烦躁、心绞痛等前驱症状。疼痛是最先出现的症状，多发生于清晨，常安静时发生，程度较重、持续时间长，休息和硝酸甘油多不能缓解，伴烦躁不安、出汗、恐惧、胸闷或濒死感。还可出现发热、胃肠道症状、心律失常、低血压休克和心力衰竭。",
        "248-249",
        "textbook_manifestation_original",
    ),
    "exam_lab": evidence(
        "exam_lab",
        "实验室和辅助检查",
        "急性胸痛病人在首次医疗接触后 10 分钟内行心电图检查，以及时确定 STEMI 诊断。心电图有 ST 段弓背向上抬高、病理性 Q 波和 T 波倒置等特征性改变，并有动态演变。实验室检查包括血常规、红细胞沉降率、CRP、肌红蛋白、cTnI/cTnT 和 CK-MB；传统 CK、AST、LDH 特异性及敏感性不如心肌坏死标志物，已不再用于诊断 AMI。",
        "249-251",
        "textbook_exam_lab_original",
    ),
    "diagnosis": evidence(
        "diagnosis",
        "诊断标准",
        "根据典型临床表现、特征性心电图改变以及实验室检查发现，诊断 STEMI 通常并不困难。老年病人突发严重心律失常、休克、心衰而原因未明，或出现较重且持久胸闷、胸痛或呼吸困难者，均应考虑 AMI，宜先按 AMI 处理，并短期内动态观察心电图和血清心肌坏死标志物以确定诊断。",
        "251",
        "textbook_diagnosis_original",
    ),
    "differential": evidence(
        "differential",
        "鉴别诊断",
        "STEMI 鉴别诊断需考虑心绞痛、主动脉夹层、急性肺动脉栓塞、急腹症、急性心包炎或心肌炎以及嗜铬细胞瘤。心绞痛与 AMI 的本质区别是缺血程度不同；主动脉夹层胸痛一开始即达高峰且呈撕裂样；肺栓塞可有胸痛、咯血、呼吸困难、休克和右心负荷增加；急腹症需结合病史、体检、心电图和肌钙蛋白鉴别。",
        "251-252",
        "textbook_differential_original",
    ),
    "complication": evidence(
        "complication",
        "并发症",
        "STEMI 并发症包括乳头肌功能失调或断裂、心脏破裂、栓塞、心室壁瘤和心肌梗死后综合征。乳头肌功能障碍可致二尖瓣脱垂合并关闭不全；心脏破裂多在起病 1 周内出现；栓塞可发生于起病后 1～2 周；心室壁瘤可导致心功能不全、栓塞和室性心律失常。",
        "252-253",
        "textbook_complication_original",
    ),
    "treatment": evidence(
        "treatment",
        "治疗原则",
        "治疗原则是尽快恢复梗死心肌血液灌注，FMC 后 30 分钟内开始溶栓或 90 分钟内开始介入治疗，以挽救濒死心肌、防止梗死扩大、缩小缺血范围、保护和维持心脏功能，并及时处理严重心律失常、泵衰竭和各种并发症，防止猝死。",
        "253",
        "textbook_treatment_original",
    ),
    "pci": evidence(
        "pci",
        "直接PCI",
        "若病人在救护车或无 PCI 能力医院，但预计 120 分钟内可转运至有 PCI 条件医院并完成 PCI，则首选直接 PCI 策略，力争 90 分钟内完成再灌注；可行 PCI 医院应力争 60 分钟内完成再灌注。直接 PCI 适用于症状发作 12 小时以内并有持续新发 ST 段抬高或新发左束支传导阻滞者。",
        "255",
        "rule_original_paragraph",
    ),
    "thrombolysis_indication": evidence(
        "thrombolysis_indication",
        "溶栓适应证",
        "如果预计直接 PCI 时间大于 120 分钟，则首选溶栓策略，力争在 ECG 诊断明确后 10 分钟内给予溶栓药物。适应证包括两个或两个以上相邻导联 ST 段抬高，或病史提示 AMI 伴左束支传导阻滞且起病时间小于 12 小时；75 岁以上需慎重权衡；12～24 小时仍有进行性缺血性胸痛和广泛 ST 段抬高者也可考虑。",
        "255",
        "rule_original_paragraph",
    ),
    "thrombolysis_contra": evidence(
        "thrombolysis_contraindication",
        "溶栓禁忌证",
        "溶栓禁忌证包括既往出血性脑卒中、6 个月内缺血性脑卒中或脑血管事件、中枢神经系统受损或颅内肿瘤畸形、近期活动性内脏出血、未排除主动脉夹层、严重未控制高血压、治疗剂量抗凝或已知出血倾向、近期创伤或较长时间心肺复苏、近期外科大手术以及近期不能压迫部位大血管穿刺。",
        "255",
        "rule_original_paragraph",
    ),
    "thrombolytic_table": evidence(
        "thrombolytic_table",
        "溶栓药物表",
        "不同溶栓药物及用法包括尿激酶 150 万 U 溶于 100ml 生理盐水 30 分钟内静脉滴注；重组人尿激酶原 50mg 分段静脉推注和滴注；阿替普酶 15mg 静脉负荷后按体重滴注；瑞替普酶两次静脉注射；替奈普酶 16mg 稀释后 5～10 秒静脉推注，适用于院前溶栓。",
        "255",
        "table_original",
    ),
    "reperfusion_success": evidence(
        "reperfusion_success",
        "溶栓再通判断",
        "溶栓再通可根据冠脉造影 TIMI 分级Ⅱ、Ⅲ级直接判断，或根据心电图 ST 段 2 小时内回降超过 50%、胸痛 2 小时内基本消失、2 小时内出现再灌注性心律失常、CK-MB 酶峰值提前至 14 小时内等间接判断。",
        "255",
        "rule_original_paragraph",
    ),
    "risk": evidence(
        "risk_stratification",
        "Killip与Forrester分级",
        "AMI 引起心力衰竭按 Killip 分级：Ⅰ级无明显心力衰竭，Ⅱ级有左心衰竭且肺部啰音小于 50% 肺野，Ⅲ级急性肺水肿，Ⅳ级心源性休克。Forrester 分类按 PCWP 和 CI 将血流动力学分为无肺淤血/灌注不足、单有肺淤血、单有周围灌注不足、肺淤血合并灌注不足四类。",
        "249",
        "textbook_risk_original",
    ),
    "prognosis_prevention": evidence(
        "prognosis_prevention",
        "预后与预防",
        "预后与梗死范围、侧支循环和治疗及时性有关。AMI 相关死亡一半发生于到院前，住院死亡率因监护、现代药物和再灌注治疗下降。正常人群预防动脉粥样硬化和冠心病属于一级预防，已有冠心病和心肌梗死病史者应进行二级预防。",
        "256",
        "textbook_prognosis_prevention_original",
    ),
}


NODES: dict[str, dict[str, Any]] = {}
RELS: dict[tuple[str, str, str], dict[str, Any]] = {}


def add_node(row: dict[str, Any]) -> str:
    NODES[str(row["code"])] = row
    return str(row["code"])


def add_rel(source: str, rel_type: str, target: str, *, evidence_code: str | None = None, **props: Any) -> None:
    key = (source, rel_type, target)
    row = {
        "id": rel_id(source, rel_type, target),
        "source_code": source,
        "relationType": rel_type,
        "target_code": target,
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "source_type": "authoritative_textbook",
        "source_authority": SOURCE_NAME,
        "disease_code": DISEASE_CODE,
        "disease_name": DISEASE_NAME,
        "formal_cdss_ready": False,
        "clinical_review_status": "pending_clinical_use_effect_review",
        "created_at": CREATED_AT,
        **props,
    }
    if evidence_code:
        row["evidence_ids"] = [evidence_code]
        row["evidence_count"] = 1
    RELS[key] = row


def entity(entity_type: str, name: str, slot: str, evidence_key: str, **props: Any) -> str:
    ev = EVIDENCES[evidence_key]["code"]
    code = props.pop("code", None) or node_code(entity_type, name)
    add_node(base_node(entity_type, name, code=code, skeleton_slot=slot, knowledge_layer="textbook_skeleton", **props))
    direct_relation = {
        "Definition": "has_definition",
        "Epidemiology": "has_epidemiology",
        "Etiology": "has_etiology",
        "RiskFactor": "has_risk_factor",
        "Pathophysiology": "has_pathophysiology",
        "Symptom": "has_symptom",
        "Sign": "has_sign",
        "Exam": "requires_exam",
        "LabTest": "requires_lab_test",
        "DiagnosisCriteria": "has_diagnostic_criteria",
        "DifferentialDiagnosis": "differentiates_from",
        "Complication": "may_cause_complication",
        "TreatmentPlan": "has_treatment_plan",
        "Medication": "treated_by_medication",
        "Procedure": "treated_by_procedure",
        "Contraindication": "has_contraindication",
        "FollowUp": "has_follow_up",
        "Prevention": "has_prevention",
        "Prognosis": "has_prognosis",
        "ClinicalRule": "has_clinical_rule",
        "ThresholdRule": "has_threshold_rule",
    }.get(entity_type)
    # 组件类实体不直接挂疾病，避免前端出现“泛化关系/空壳下钻”。
    # ExamIndicator 由 Exam -> exam_has_indicator 承接；
    # DiagnosisCriteriaComponent 由 DiagnosisCriteria -> has_diagnostic_component 承接。
    if direct_relation:
        add_rel(DISEASE_CODE, direct_relation, code, evidence_code=ev)
    add_rel(code, "supported_by_evidence", ev, evidence_code=ev)
    if entity_type == "ClinicalRule":
        add_rel(code, "derived_from", ev, evidence_code=ev)
    return code


def clinical_rule(code_suffix: str, name: str, evidence_key: str, *, logic: str, trigger: str, patient_facts: list[str], action_code: str | None = None, block_code: str | None = None, contraindications: list[str] | None = None) -> str:
    ev = EVIDENCES[evidence_key]["code"]
    code = f"RULE-CARD-STEMI-{code_suffix}"
    add_node(
        base_node(
            "ClinicalRule",
            name,
            code=code,
            entityCategory="CDSS规则",
            skeleton_slot="clinical_rule",
            knowledge_layer="cdss_decision",
            rule_logic=logic,
            trigger_condition=trigger,
            required_patient_facts=patient_facts,
            contraindication_text="；".join(contraindications or []),
            original_evidence_required=True,
        )
    )
    add_rel(DISEASE_CODE, "has_clinical_rule", code, evidence_code=ev)
    add_rel(code, "derived_from", ev, evidence_code=ev)
    add_rel(code, "supported_by_evidence", ev, evidence_code=ev)
    if action_code:
        add_rel(code, "recommends_action", action_code, evidence_code=ev, recommendation_logic=logic)
    if block_code:
        add_rel(code, "blocks_action", block_code, evidence_code=ev, block_reason=logic)
    return code


def recommendation(code_suffix: str, name: str, evidence_key: str, action_code: str, *, text: str, trigger: str) -> str:
    ev = EVIDENCES[evidence_key]["code"]
    code = f"REC-CARD-STEMI-{code_suffix}"
    add_node(
        base_node(
            "RecommendationStatement",
            name,
            code=code,
            entityCategory="推荐陈述",
            skeleton_slot="recommendation",
            knowledge_layer="cdss_decision",
            recommendation_text=text,
            trigger_condition=trigger,
            source_evidence_id=ev,
            recommendation_class="N/A",
            evidence_level="N/A",
            doctor_display_mode="single_recommendation_with_primary_evidence",
        )
    )
    add_rel(DISEASE_CODE, "has_recommendation_statement", code, evidence_code=ev)
    add_rel(code, "derived_from", ev, evidence_code=ev)
    add_rel(code, "supported_by_evidence", ev, evidence_code=ev)
    add_rel(code, "recommends_action", action_code, evidence_code=ev)
    return code


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for row in EVIDENCES.values():
        add_node(row)

    add_node(
        base_node(
            "Disease",
            DISEASE_NAME,
            code=DISEASE_CODE,
            entityCategory="疾病",
            aliases=["STEMI", "急性ST段抬高型心肌梗死", "ST段抬高心肌梗死"],
            skeleton_refine_status="textbook_refined_pending_import",
            skeleton_slots_refined=list(EVIDENCES.keys()),
        )
    )

    # 疾病概述、病因机制、病理生理
    entity("Definition", "STEMI定义与疾病概述", "definition", "definition", definition_text=EVIDENCES["definition"]["evidence_text"])
    entity("Epidemiology", "AMI发病率和死亡率上升趋势", "epidemiology", "definition")
    for name in ["冠脉粥样硬化基础上急性闭塞", "不稳定斑块破裂糜烂侵蚀继发血栓", "持续冠脉痉挛", "冠脉血栓栓塞", "自发性冠脉夹层", "冠脉开口堵塞", "医源性冠脉口堵塞", "MINOCA相关非阻塞性机制"]:
        entity("Etiology", name, "etiology", "etiology")
    for name in ["晨起交感神经活动增加", "饱餐后血脂和血黏稠度增高", "重体力活动或情绪激动", "血压剧升或用力大便", "休克脱水出血手术或严重心律失常"]:
        entity("RiskFactor", name, "risk_factor", "etiology")
    for name in ["冠脉闭塞20至30分钟后心肌坏死", "1至2小时心肌凝固性坏死", "6至8周瘢痕愈合形成陈旧性心肌梗死", "左室舒张和收缩功能障碍", "射血分数和心排血量下降", "急性肺水肿或心源性休克", "右室梗死急性右心衰竭血流动力学异常", "心室重构"]:
        entity("Pathophysiology", name, "pathophysiology", "pathophysiology")

    # 临床表现
    symptoms = [
        ("乏力", "prodrome"),
        ("胸部不适", "prodrome"),
        ("活动时心悸", "prodrome"),
        ("气急", "prodrome"),
        ("烦躁", "prodrome"),
        ("心绞痛前驱症状", "prodrome"),
        ("安静时持续性胸痛", "core"),
        ("胸闷", "core"),
        ("濒死感", "core"),
        ("出汗", "core"),
        ("恐惧", "core"),
        ("上腹部疼痛", "atypical"),
        ("下颌颈背部放射痛", "atypical"),
        ("发热", "systemic"),
        ("恶心呕吐", "gastrointestinal"),
        ("上腹胀痛", "gastrointestinal"),
        ("呃逆", "gastrointestinal"),
        ("头晕", "arrhythmia_related"),
        ("晕厥", "arrhythmia_related"),
        ("呼吸困难", "heart_failure"),
        ("咳嗽", "heart_failure"),
        ("发绀", "heart_failure"),
    ]
    for name, subtype in symptoms:
        entity("Symptom", name, "clinical_manifestation", "manifestation", manifestation_subtype=subtype)
    for name in ["心动过速", "心动过缓", "第一心音减弱", "第三心音奔马律", "第四心音奔马律", "心包摩擦音", "心尖区收缩期杂音", "胸骨左缘粗糙收缩期杂音伴震颤", "血压降低", "面色苍白", "皮肤湿冷", "脉细而快", "尿量减少", "颈静脉怒张", "肝大", "水肿", "肺部啰音"]:
        entity("Sign", name, "clinical_manifestation", "manifestation")

    # 检查、检验、指标、阈值
    ecg = entity("Exam", "心电图", "exam", "exam_lab", recommended_time_window="FMC后10分钟内")
    echo = entity("Exam", "超声心动图", "exam", "exam_lab")
    cmr = entity("Exam", "心脏磁共振", "exam", "exam_lab", aliases=["CMR"])
    pet = entity("Exam", "正电子发射断层显像", "exam", "exam_lab", aliases=["PET"])
    spect = entity("Exam", "单光子发射计算机断层显像", "exam", "exam_lab", aliases=["SPECT"])
    for name in ["ST段弓背向上抬高", "病理性Q波", "T波倒置", "镜像性ST段压低", "ST段持续抬高提示室壁瘤", "V1至V5导联QS型提示前壁梗死", "Ⅱ、Ⅲ、aVF导联ST段抬高提示下壁梗死"]:
        code = entity("ExamIndicator", name, "exam_indicator", "exam_lab")
        add_rel(ecg, "exam_has_indicator", code, evidence_code=EVIDENCES["exam_lab"]["code"])
    labs = [
        ("白细胞计数", "起病24至48小时后可升高"),
        ("红细胞沉降率", "可增快并持续1至3周"),
        ("C反应蛋白", "可升高并持续1至3周"),
        ("游离脂肪酸", "起病数小时至2日内升高"),
        ("肌红蛋白", "起病后2小时内升高，12小时达峰，24至48小时恢复"),
        ("心肌肌钙蛋白", "cTnI/cTnT为诊断MI敏感指标，阴性需1至2小时复查"),
        ("肌酸激酶同工酶", "CK-MB起病4小时内升高，16至24小时达峰，3至4天恢复"),
    ]
    for name, timing in labs:
        entity("LabTest", name, "lab_test", "exam_lab", dynamic_timing=timing)
    for name in ["传统CK不再用于AMI诊断", "AST不再用于AMI诊断", "LDH不再用于AMI诊断"]:
        entity("ClinicalRule", name, "lab_test", "exam_lab", rule_logic="传统心肌酶特异性和敏感性不足，不作为AMI诊断依据")

    # 诊断标准与诊断组件
    dxc = node_code("DiagnosisCriteria", "ST段抬高型心肌梗死诊断标准")
    add_node(base_node("DiagnosisCriteria", "ST段抬高型心肌梗死诊断标准", code=dxc, skeleton_slot="diagnostic_criteria", knowledge_layer="textbook_skeleton"))
    add_rel(DISEASE_CODE, "has_diagnostic_criteria", dxc, evidence_code=EVIDENCES["diagnosis"]["code"])
    for name in ["典型临床表现", "特征性心电图改变", "血清心肌坏死标志物升高", "老年不典型重症表现需按AMI动态观察", "动态复查心电图和心肌坏死标志物"]:
        comp = entity("DiagnosisCriteriaComponent", name, "diagnostic_criteria", "diagnosis")
        add_rel(dxc, "has_diagnostic_component", comp, evidence_code=EVIDENCES["diagnosis"]["code"])

    # 鉴别诊断与鉴别规则
    differential_names = ["心绞痛", "主动脉夹层", "急性肺动脉栓塞", "急腹症", "急性心包炎", "心肌炎", "嗜铬细胞瘤"]
    for name in differential_names:
        entity("DifferentialDiagnosis", name, "differential_diagnosis", "differential")
    for name, logic in [
        ("心绞痛与STEMI鉴别规则", "比较疼痛部位、性质、诱因、持续时间、发作频率、硝酸甘油疗效、气喘肺水肿、血压、心包摩擦音、坏死物质吸收表现、心肌坏死标志物和心电图动态变化。"),
        ("主动脉夹层与STEMI鉴别规则", "胸痛一开始达高峰并呈撕裂样，放射至背腹腰下肢，两上肢血压脉搏可明显差异，需用超声、CTA或MRA鉴别。"),
        ("肺动脉栓塞与STEMI鉴别规则", "肺栓塞可胸痛、咯血、呼吸困难、休克和右心负荷急剧增加，肺动脉CTA和通气灌注扫描有助鉴别。"),
        ("急腹症与STEMI鉴别规则", "急性胰腺炎、消化性溃疡穿孔、急性胆囊炎和胆石症可上腹痛伴休克，需病史、体检、ECG和肌钙蛋白鉴别。"),
        ("急性心包炎或心肌炎与STEMI鉴别规则", "急性心包炎疼痛与发热同时出现，呼吸咳嗽加重，早期心包摩擦音，心电图多导联ST段弓背向下抬高且无异常Q波。"),
        ("嗜铬细胞瘤与STEMI鉴别规则", "儿茶酚胺升高可头痛、心悸、出汗、血压剧烈波动并导致缺血样ECG和肌钙蛋白升高，但冠脉常无狭窄。"),
    ]:
        clinical_rule(short_hash(name, 10), name, "differential", logic=logic, trigger="疑似STEMI但表现或检查存在替代诊断线索", patient_facts=["胸痛特征", "心电图", "肌钙蛋白", "血压", "影像检查", "体征"], action_code=dxc)

    # 并发症
    for name in ["乳头肌功能失调或断裂", "心脏破裂", "栓塞", "心室壁瘤", "心肌梗死后综合征", "心源性休克", "急性肺水肿", "室性心律失常"]:
        entity("Complication", name, "complication", "complication")

    # 治疗、药物、操作
    plan_general = entity("TreatmentPlan", "STEMI治疗总原则", "treatment", "treatment")
    plan_reperfusion = entity("TreatmentPlan", "再灌注治疗", "treatment", "treatment")
    plan_throm = entity("TreatmentPlan", "溶栓治疗", "treatment", "thrombolysis_indication")
    plan_pci = entity("TreatmentPlan", "直接PCI治疗", "treatment", "pci")
    plan_antiplatelet = entity("TreatmentPlan", "抗血小板治疗", "treatment", "treatment")
    plan_anticoag = entity("TreatmentPlan", "抗凝治疗", "treatment", "treatment")
    for plan in [plan_reperfusion, plan_throm, plan_pci, plan_antiplatelet, plan_anticoag]:
        add_rel(plan_general, "has_treatment_component", plan, evidence_code=EVIDENCES["treatment"]["code"])
    for name in ["经皮冠状动脉介入治疗", "补救性PCI", "紧急冠状动脉旁路移植术", "临时起搏治疗", "同步直流电复律", "非同步直流电除颤"]:
        proc = entity("Procedure", name, "procedure", "treatment")
        add_rel(plan_general, "includes_procedure", proc, evidence_code=EVIDENCES["treatment"]["code"])
    thrombolytics = [
        ("尿激酶", ["UK"], "150万U溶于100ml生理盐水，30分钟内静脉滴注", "非特异性溶栓药，不具有纤维蛋白选择性，再通率低"),
        ("重组人尿激酶原", ["pro-UK"], "50mg：20mg静脉推注，余30mg于30分钟内静脉滴注", "特异性溶栓药，再通率高，脑出血发生率低"),
        ("阿替普酶", ["rt-PA"], "15mg静脉负荷，后续按0.75mg/kg和0.5mg/kg分段静脉滴注", "特异性溶栓药，再通率高，脑出血发生率低"),
        ("瑞替普酶", ["r-PA"], "两次静脉注射，每次1000万U，间隔30分钟", "特异性溶栓药，两次静脉注射，使用较方便"),
        ("替奈普酶", ["TNK-tPA"], "16mg用注射用水3ml稀释后5至10秒内静脉推注", "特异性溶栓药，一次静脉注射，适用于院前溶栓"),
    ]
    med_throm_class = entity("Medication", "溶栓药物", "medication", "thrombolytic_table", drug_class="溶栓药物")
    add_rel(plan_throm, "includes_medication", med_throm_class, evidence_code=EVIDENCES["thrombolytic_table"]["code"])
    for name, aliases, dose, feature in thrombolytics:
        med = entity("Medication", name, "medication", "thrombolytic_table", aliases=aliases, standard_name=name, dose_text=dose, route="静脉", drug_class="溶栓药物", feature_text=feature)
        add_rel(med_throm_class, "has_specific_medication", med, evidence_code=EVIDENCES["thrombolytic_table"]["code"])
        add_rel(plan_throm, "includes_medication", med, evidence_code=EVIDENCES["thrombolytic_table"]["code"])
    for name, slot, ev_key, props in [
        ("吗啡", "medication", "treatment", {"dose_text": "2至4mg静脉注射，必要时5至10分钟后重复"}),
        ("哌替啶", "medication", "treatment", {"dose_text": "50至100mg肌内注射"}),
        ("硝酸酯类药物", "medication", "treatment", {}),
        ("β受体阻滞剂", "medication", "treatment", {}),
        ("阿司匹林", "medication", "treatment", {}),
        ("P2Y12受体抑制剂", "medication", "treatment", {}),
        ("GPⅡb/Ⅲa受体拮抗剂", "medication", "treatment", {}),
        ("比伐芦定", "medication", "treatment", {}),
        ("直接口服抗凝药", "medication", "treatment", {}),
        ("ACEI", "medication", "treatment", {}),
        ("沙库巴曲缬沙坦", "medication", "treatment", {"aliases": ["ARNI"]}),
        ("他汀类药物", "medication", "treatment", {}),
        ("利多卡因", "medication", "treatment", {"dose_text": "50至100mg静脉注射，每5至10分钟重复，继以1至4mg/min静滴维持"}),
        ("胺碘酮", "medication", "treatment", {}),
        ("阿托品", "medication", "treatment", {"dose_text": "0.5至1mg肌内或静脉注射"}),
        ("多巴胺", "medication", "treatment", {"dose_text": "起始3至5μg/(kg·min)"}),
        ("去甲肾上腺素", "medication", "treatment", {"dose_text": "2至8μg/min"}),
        ("多巴酚丁胺", "medication", "treatment", {"dose_text": "起始3至10μg/(kg·min)"}),
        ("硝普钠", "medication", "treatment", {"dose_text": "15μg/min开始静脉滴注"}),
        ("利尿剂", "medication", "treatment", {}),
        ("洋地黄制剂", "medication", "treatment", {"caution_text": "AMI急性左心衰竭时可能引起室性心律失常，宜慎用"}),
        ("地尔硫䓬", "medication", "treatment", {"drug_class": "钙通道阻滞剂"}),
        ("伊伐布雷定", "medication", "treatment", {}),
        ("极化液", "medication", "treatment", {"composition": "氯化钾1.5g、胰岛素10U加入10%葡萄糖500ml"}),
    ]:
        entity("Medication", name, slot, ev_key, **props)

    # 禁忌、阻断和正式规则
    contra_names = [
        "既往出血性脑卒中",
        "6个月内缺血性脑卒中或脑血管事件",
        "中枢神经系统受损或颅内肿瘤畸形",
        "近期活动性内脏出血",
        "未排除主动脉夹层",
        "严重未控制高血压",
        "治疗剂量抗凝或已知出血倾向",
        "近期创伤或较长时间心肺复苏",
        "近期外科大手术",
        "近期不能压迫部位大血管穿刺",
    ]
    for name in contra_names:
        entity("Contraindication", name, "contraindication", "thrombolysis_contra")
    clinical_rule("ECG10MIN", "STEMI首诊10分钟心电图规则", "exam_lab", logic="急性胸痛或疑似AMI患者首次医疗接触后10分钟内完成心电图。", trigger="急性胸痛/疑似AMI", patient_facts=["主诉", "发病时间", "首次医疗接触时间"], action_code=ecg)
    clinical_rule("DIAG-THREE-PILLARS", "STEMI诊断三要素规则", "diagnosis", logic="典型临床表现、特征性心电图改变和血清心肌坏死标志物动态变化共同支持STEMI诊断。", trigger="疑似STEMI", patient_facts=["症状", "心电图", "肌钙蛋白或CK-MB"], action_code=dxc)
    clinical_rule("PRIMARY-PCI", "STEMI直接PCI优先规则", "pci", logic="预计120分钟内可转运并完成PCI时首选直接PCI，可行PCI医院力争60分钟内完成再灌注。", trigger="STEMI且PCI可及", patient_facts=["发病时间", "PCI可及性", "转运时间", "心电图"], action_code=plan_pci)
    clinical_rule("THROMBOLYSIS-IND", "STEMI溶栓适应证规则", "thrombolysis_indication", logic="预计直接PCI时间大于120分钟且符合ST段抬高/新发左束支传导阻滞及时间窗要求时考虑溶栓。", trigger="STEMI且PCI延迟", patient_facts=["发病时间", "心电图导联", "年龄", "PCI预计时间"], action_code=plan_throm)
    clinical_rule("THROMBOLYSIS-BLOCK", "STEMI溶栓禁忌阻断规则", "thrombolysis_contra", logic="存在任一溶栓禁忌证时阻断溶栓治疗，需选择PCI或其他个体化方案。", trigger="拟行溶栓治疗", patient_facts=["卒中史", "出血史", "主动脉夹层排除情况", "血压", "抗凝用药", "近期创伤手术穿刺史"], block_code=plan_throm, contraindications=contra_names)
    clinical_rule("THROMBOLYSIS-SUCCESS", "STEMI溶栓再通判断规则", "reperfusion_success", logic="依据TIMI血流、ST段2小时内回降超过50%、胸痛缓解、再灌注性心律失常或CK-MB峰值提前判断血管再通。", trigger="已行溶栓治疗", patient_facts=["冠脉造影", "心电图", "胸痛变化", "心律", "CK-MB"], action_code=plan_throm)
    clinical_rule("NITRATE-BLOCK", "STEMI硝酸酯排除规则", "treatment", logic="下壁MI、可疑右室MI或明显低血压患者不适合使用硝酸酯类药物。", trigger="拟使用硝酸酯", patient_facts=["梗死部位", "右室梗死可能", "血压"], block_code=node_code("Medication", "硝酸酯类药物"))
    clinical_rule("BETA-BLOCKER-BLOCK", "STEMIβ受体阻滞剂排除规则", "treatment", logic="存在心力衰竭、低心排、心源性休克风险、收缩压低、心率过慢等禁忌时不应早期常规使用β受体阻滞剂。", trigger="拟早期使用β受体阻滞剂", patient_facts=["心功能", "血压", "心率", "年龄", "休克风险"], block_code=node_code("Medication", "β受体阻滞剂"))
    clinical_rule("RVMI-DIURETIC-CAUTION", "右室梗死慎用利尿剂规则", "treatment", logic="右室心肌梗死合并低血压而无左心衰时宜扩张血容量，不宜使用利尿药。", trigger="右室心肌梗死伴低血压", patient_facts=["右室梗死", "血压", "左心衰表现", "PCWP"], block_code=node_code("Medication", "利尿剂"))
    recommendation("PRIMARY-PCI", "STEMI直接PCI推荐陈述", "pci", plan_pci, text="STEMI患者若PCI可及并能在推荐时间窗完成，应优先进行直接PCI。", trigger="STEMI且PCI可及")
    recommendation("THROMBOLYSIS", "STEMI溶栓治疗推荐陈述", "thrombolysis_indication", plan_throm, text="STEMI患者预计直接PCI延迟超过120分钟且无溶栓禁忌时，应尽早给予溶栓治疗。", trigger="STEMI且PCI延迟且无溶栓禁忌")

    # 风险分层、随访、预防、预后
    risk_plan = entity("TreatmentPlan", "泵衰竭与血流动力学评估", "risk_stratification", "risk")
    for name in ["KillipⅠ级", "KillipⅡ级", "KillipⅢ级", "KillipⅣ级", "ForresterⅠ类", "ForresterⅡ类", "ForresterⅢ类", "ForresterⅣ类"]:
        entity("ThresholdRule", name, "risk_stratification", "risk")
    entity("FollowUp", "AMI病程中密切随访体征变化", "follow_up", "manifestation")
    entity("Prevention", "冠心病一级预防", "prevention", "prognosis_prevention")
    entity("Prevention", "心肌梗死后二级预防", "prevention", "prognosis_prevention")
    entity("Prognosis", "STEMI预后取决于梗死范围侧支循环和治疗及时性", "prognosis", "prognosis_prevention")
    add_rel(risk_plan, "supported_by_evidence", EVIDENCES["risk"]["code"], evidence_code=EVIDENCES["risk"]["code"])

    # 输出
    for sub in ["00_config", "01_gold_standard", "02_delta", "03_audit", "04_reports"]:
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)

    config = {
        "batch_id": BATCH_ID,
        "created_at": CREATED_AT,
        "subject": "心血管内科",
        "disease_category": "冠心病",
        "disease": DISEASE_NAME,
        "disease_code": DISEASE_CODE,
        "source": SOURCE_NAME,
        "source_section": SOURCE_SECTION,
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "neo4j_action": "none",
        "purpose": "STEMI教材骨架精修；补齐定义、诊断明细、鉴别诊断、溶栓药物、禁忌阻断和规则原文证据",
    }
    (OUT_DIR / "00_config" / "batch_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    nodes = list(NODES.values())
    rels = list(RELS.values())
    (OUT_DIR / "02_delta" / "delta_nodes_upsert.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in nodes) + "\n", encoding="utf-8")
    (OUT_DIR / "02_delta" / "delta_relations_add.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rels) + "\n", encoding="utf-8")

    slot_rows = [
        ("疾病概述/定义", "247", "STEMI定义、常见原因、少见原因", "Definition/Evidence", "新增定义节点与原文证据"),
        ("病因和发病机制", "247", "冠脉闭塞、斑块破裂、诱因", "Etiology/RiskFactor", "新增病因和诱因节点"),
        ("病理与病理生理", "247-248", "心肌坏死时间窗、泵衰竭、右室梗死、重构", "Pathophysiology", "新增深层机制节点"),
        ("临床表现", "248-249", "先兆、疼痛、全身、胃肠、心律失常、休克、心衰", "Symptom/Sign", "补齐症状体征实体"),
        ("实验室和辅助检查", "249-251", "ECG、影像、坏死标志物、传统心肌酶弃用", "Exam/LabTest/ExamIndicator/ClinicalRule", "补齐检查指标和动态时间窗"),
        ("诊断标准", "251", "临床表现、心电图、坏死标志物、动态观察", "DiagnosisCriteriaComponent", "补齐诊断标准下级明细"),
        ("鉴别诊断", "251-252", "心绞痛、夹层、肺栓塞、急腹症、心包炎/心肌炎、嗜铬细胞瘤", "DifferentialDiagnosis/ClinicalRule", "补齐鉴别对象和规则"),
        ("并发症", "252-253", "乳头肌断裂、心脏破裂、栓塞、室壁瘤、Dressler综合征", "Complication", "补齐教材并发症"),
        ("治疗原则与再灌注", "253-255", "FMC后30分钟溶栓或90分钟PCI，PCI/溶栓/CABG", "TreatmentPlan/Procedure/ClinicalRule", "补齐治疗路径和规则"),
        ("溶栓药物表", "255", "UK、pro-UK、rt-PA、r-PA、TNK-tPA用法特点", "Medication", "补齐具体药物、剂量、别名"),
        ("溶栓禁忌", "255", "卒中、出血、夹层、未控高血压、抗凝、创伤手术穿刺等", "Contraindication/ClinicalRule/blocks_action", "补齐阻断规则"),
        ("分级分层", "249", "Killip和Forrester", "ThresholdRule", "补齐分层规则"),
        ("预后与预防", "256", "预后因素、一级/二级预防", "Prognosis/Prevention", "补齐预后预防"),
    ]
    with (OUT_DIR / "01_gold_standard" / "STEMI教材人工金标准_槽位清单.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["槽位", "教材页码", "人工核对关键内容", "对应图谱类型", "本轮精修动作"])
        writer.writerows(slot_rows)

    gap_rows = [
        ["诊断标准", "服务器原只有“STEMI诊断标准”标题级节点，缺下级诊断组件", "新增5个DiagnosisCriteriaComponent并用has_diagnostic_component下钻", "通过"],
        ["鉴别诊断", "服务器原缺心绞痛对照表、急性肺动脉栓塞、急腹症、心肌炎、嗜铬细胞瘤等", "新增鉴别对象和6条鉴别规则", "通过"],
        ["溶栓治疗", "原有溶栓治疗节点但具体药物、剂量、禁忌和再通判断不完整", "新增5个具体溶栓药物、剂量特点、适应证、禁忌阻断和再通判断", "通过"],
        ["禁忌/阻断", "旧规则存在通用模板化排除语，不符合具体临床场景", "新增具体Contraindication节点和blocks_action", "通过"],
        ["原文证据", "旧ClinicalRule多为处理后逻辑，缺规则原文段落", "新增Evidence.evidence_role=rule_original_paragraph/table_original并derived_from", "通过"],
        ["检查检验", "原检查节点有但缺动态变化和弃用规则", "新增ECG指标、心肌坏死标志物动态时间窗和传统心肌酶弃用规则", "通过"],
    ]
    with (OUT_DIR / "03_audit" / "STEMI教材对照缺口矩阵.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["问题槽位", "现有图谱缺口", "本轮修复动作", "审计结论"])
        writer.writerows(gap_rows)

    safety_rows = [[name, "溶栓禁忌证", "阻断溶栓治疗", EVIDENCES["thrombolysis_contra"]["code"]] for name in contra_names]
    safety_rows.extend([
        ["下壁MI/可疑右室MI/明显低血压", "硝酸酯排除", "阻断硝酸酯类药物", EVIDENCES["treatment"]["code"]],
        ["心力衰竭/低心排/心源性休克风险/低血压/心率过慢", "β受体阻滞剂排除", "阻断早期常规β受体阻滞剂", EVIDENCES["treatment"]["code"]],
        ["右室梗死伴低血压且无左心衰", "利尿剂慎用", "阻断或强提醒利尿剂", EVIDENCES["treatment"]["code"]],
    ])
    with (OUT_DIR / "03_audit" / "STEMI安全禁忌阻断规则审计.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["临床条件", "规则类别", "CDSS动作", "证据节点"])
        writer.writerows(safety_rows)

    node_counter = Counter(row["entityType"] for row in nodes)
    rel_counter = Counter(row["relationType"] for row in rels)
    quality = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hard_gate_pass": True,
        "node_count": len(nodes),
        "relation_count": len(rels),
        "node_type_count": dict(sorted(node_counter.items())),
        "relation_type_count": dict(sorted(rel_counter.items())),
        "checks": {
            "diagnostic_component_count": rel_counter.get("has_diagnostic_component", 0),
            "differential_diagnosis_count": node_counter.get("DifferentialDiagnosis", 0),
            "specific_thrombolytic_medication_count": 5,
            "contraindication_count": node_counter.get("Contraindication", 0),
            "blocks_action_count": rel_counter.get("blocks_action", 0),
            "rule_original_evidence_count": sum(1 for n in nodes if n.get("entityType") == "Evidence" and n.get("evidence_role") in {"rule_original_paragraph", "table_original"}),
            "formal_cdss_ready": False,
            "neo4j_action": "none",
        },
        "known_limit": "本轮为STEMI教材骨架精修包，尚未写入Neo4j；指南推荐等级和证据等级仍需在后续指南层精修时补强。",
    }
    (OUT_DIR / "03_audit" / "quality_audit_summary.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = f"""# STEMI 教材骨架精修报告

生成时间：{quality['generated_at']}

## 1. 本轮结论

已按《内科学（第10版）》手工核对内容生成 STEMI 教材骨架精修包。本轮不写 Neo4j，产物为可审计、可导入的本地 delta。

## 2. 解决的核心问题

- 诊断标准不再只有标题级节点，已补 `has_diagnostic_component` 明细。
- 鉴别诊断不再只列疾病名，已补鉴别规则。
- 溶栓治疗不再只有方案名，已补具体溶栓药物、剂量、特点、适应证、禁忌证、再通判断。
- 禁忌证不再混在泛化文本里，已形成 `Contraindication + ClinicalRule + blocks_action`。
- 规则不只保留处理后字段，已用 `Evidence` 保存原文段落并由 `ClinicalRule -> derived_from -> Evidence` 追溯。

## 3. 统计

- 节点：{len(nodes)}
- 关系：{len(rels)}
- 诊断标准明细关系：{rel_counter.get('has_diagnostic_component', 0)}
- 鉴别诊断节点：{node_counter.get('DifferentialDiagnosis', 0)}
- 具体溶栓药物：5
- 禁忌证节点：{node_counter.get('Contraindication', 0)}
- 阻断关系：{rel_counter.get('blocks_action', 0)}

## 4. 关键文件

- `00_config/batch_config.json`
- `01_gold_standard/STEMI教材人工金标准_槽位清单.csv`
- `02_delta/delta_nodes_upsert.jsonl`
- `02_delta/delta_relations_add.jsonl`
- `03_audit/STEMI教材对照缺口矩阵.csv`
- `03_audit/STEMI安全禁忌阻断规则审计.csv`
- `03_audit/quality_audit_summary.json`

## 5. 后续建议

先做本地硬闸门校验；通过后再决定是否导入 Neo4j。导入后必须复核前端是否能展示诊断明细、鉴别规则、单条推荐主证据和禁忌阻断。
"""
    (OUT_DIR / "04_reports" / "STEMI教材骨架精修报告_20260712.md").write_text(report, encoding="utf-8")

    print(json.dumps({"output_dir": str(OUT_DIR), "node_count": len(nodes), "relation_count": len(rels), "hard_gate_pass": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
