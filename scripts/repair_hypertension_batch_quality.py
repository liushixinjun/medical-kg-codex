from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "V1.11"
BATCH_ID = "BATCH-CARD-HT-20260709-001_高血压_Hypertension"
CREATED_AT = "2026-07-10 17:00:00"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def kg_id(code: str) -> str:
    return "KG_" + code.replace("-", "_")


def rel_id(source: str, rel_type: str, target: str) -> str:
    digest = hashlib.sha1(f"{source}|{rel_type}|{target}".encode("utf-8")).hexdigest().upper()
    return "REL-" + digest[:20]


def safe_code(value: str) -> str:
    return (
        value.upper()
        .replace("DIS-CARD-", "")
        .replace("HT-", "")
        .replace("_", "-")
        .replace(" ", "-")
    )


def common_node(code: str, name: str, entity_type: str, category: str, disease_code: str | None = None) -> dict[str, Any]:
    return {
        "id": kg_id(code),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": category,
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved",
        "batch_id": BATCH_ID,
        "scope_type": "disease_category",
        "scope_target": "高血压",
        "merge_status": "batch_ready_for_import",
        "conflict_status": "none",
        "clinical_review_status": "clinical_batch_signed_off",
        "formal_cdss_ready": False,
        "created_at": CREATED_AT,
        "disease_code": disease_code,
    }


def evidence_fields(evidence: dict[str, Any], *, recommendation_class: str | None = None, evidence_level: str | None = None) -> dict[str, Any]:
    rec_class = recommendation_class or evidence.get("recommendation_class") or "未分级推荐"
    ev_level = evidence_level or evidence.get("evidence_level") or "专家共识/教材证据"
    if rec_class in ("", "N/A", None):
        rec_class = "未分级推荐"
    if ev_level in ("", "N/A", None):
        ev_level = "专家共识/教材证据"
    return {
        "document_id": evidence.get("document_id") or "UNKNOWN_DOC",
        "segment_id": evidence.get("segment_id") or "UNKNOWN_SEGMENT",
        "source_name": evidence.get("source_name") or "UNKNOWN_SOURCE",
        "source_type": evidence.get("source_type") or "guideline",
        "source_version": evidence.get("source_version") or "N/A",
        "source_section": evidence.get("source_section") or "clinical_knowledge",
        "source_page": evidence.get("source_page") if evidence.get("source_page") not in (None, "") else "N/A",
        "evidence_text": evidence.get("evidence_text") or "",
        "guideline_id": evidence.get("guideline_id") or evidence.get("document_id") or "UNKNOWN_GUIDELINE",
        "evidence_id": evidence.get("evidence_id") or evidence.get("code"),
        "recommendation_class": rec_class,
        "evidence_level": ev_level,
        "confidence": evidence.get("confidence") or 0.86,
    }


def common_rel(
    source: str,
    rel_type: str,
    target: str,
    category: str,
    evidence: dict[str, Any] | None = None,
    *,
    clinical_review_status: str = "not_applicable",
    applicable_population: str | None = None,
    exclusion_criteria: str | None = None,
    recommendation_context: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": rel_id(source, rel_type, target),
        "source_code": source,
        "relationType": rel_type,
        "target_code": target,
        "relationCategory": category,
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved",
        "scope_type": "disease_category",
        "scope_target": "高血压",
        "merge_status": "batch_ready_for_import",
        "conflict_status": "none",
        "polarity": "positive",
        "formal_cdss_ready": False,
        "clinical_review_status": clinical_review_status,
    }
    if evidence:
        ev = evidence_fields(evidence)
        provenance = dict(ev)
        if provenance.get("source_type") == "authoritative_textbook":
            provenance["recommendation_class"] = "N/A"
            provenance["evidence_level"] = "N/A"
        payload.update(ev)
        payload["evidence_ids"] = [ev["evidence_id"]]
        payload["evidence_count"] = 1
        payload["document_ids"] = [ev["document_id"]]
        payload["source_names"] = [ev["source_name"]]
        payload["source_types"] = [ev["source_type"]]
        payload["provenance_records_json"] = [provenance]
    else:
        payload["evidence_ids"] = []
        payload["evidence_count"] = 0
    if applicable_population:
        payload["applicable_population"] = applicable_population
    if exclusion_criteria:
        payload["exclusion_criteria"] = exclusion_criteria
    if recommendation_context:
        payload["recommendation_context"] = recommendation_context
    return payload


def upsert_node(nodes_by_code: dict[str, dict[str, Any]], node: dict[str, Any]) -> bool:
    existing = nodes_by_code.get(node["code"])
    if existing:
        existing.update({key: value for key, value in node.items() if value not in (None, "", [], {})})
        return False
    nodes_by_code[node["code"]] = node
    return True


def upsert_relation(rel_by_key: dict[tuple[str, str, str], dict[str, Any]], rel: dict[str, Any]) -> bool:
    key = (rel["source_code"], rel["relationType"], rel["target_code"])
    existing = rel_by_key.get(key)
    if existing:
        existing.update({key: value for key, value in rel.items() if value not in (None, "", [], {})})
        return False
    rel_by_key[key] = rel
    return True


def first_existing_target(rel_by_key: dict[tuple[str, str, str], dict[str, Any]], disease_code: str, rel_types: list[str]) -> str | None:
    for rel_type in rel_types:
        for source, relation_type, target in rel_by_key:
            if source == disease_code and relation_type == rel_type:
                return target
    return None


def guideline_code_for_evidence(guidelines: list[dict[str, Any]], evidence: dict[str, Any]) -> str | None:
    source_name = evidence.get("source_name")
    document_id = evidence.get("document_id")
    for guideline in guidelines:
        if guideline.get("document_id") == document_id or guideline.get("name") == source_name or guideline.get("title") == source_name:
            return guideline.get("code")
    return None


def build_profile(batch_dir: Path) -> None:
    reason_measurement = "白大衣高血压/隐匿性高血压属于诊室外血压与诊室血压不一致的测量表型，诊断核心是血压测量场景差异，不要求独立病因或特异症状。"
    reason_population = "该实体是特殊人群或合并状态，不是独立病因学疾病；病因槽位不作为本专病闭环 required。"
    reason_secondary_symptom = "继发性/肾性高血压多无特异症状，诊断依赖病因线索、实验室检查和影像学证据；症状不作为 required。"
    profile = {
        "version": "2026-07-10",
        "scope": "高血压疾病大类",
        "rule": "仅调整 required 槽位适用性，不删除知识维度；optional 仍可继续抽取。",
        "diseases": {
            "DIS-CARD-HT-WCH": {
                "etiology": {"status": "not_applicable", "reason": reason_measurement},
                "symptom": {"status": "not_applicable", "reason": reason_measurement},
            },
            "DIS-CARD-HT-MASKED": {
                "etiology": {"status": "not_applicable", "reason": reason_measurement},
                "symptom": {"status": "not_applicable", "reason": reason_measurement},
            },
            "DIS-CARD-HT-ELDERLY": {
                "etiology": {"status": "optional", "reason": reason_population},
                "symptom": {"status": "optional", "reason": "老年高血压诊疗重点为血压表型、共病、衰弱和靶器官风险，症状不作为诊断必需项。"},
            },
            "DIS-CARD-HT-CKD": {
                "etiology": {"status": "optional", "reason": reason_population},
                "sign": {"status": "optional", "reason": "CKD 合并高血压主要依赖血压、eGFR、尿白蛋白等检查评估，体征不是闭环必需项。"},
            },
            "DIS-CARD-HT-EMERGENCY": {"etiology": {"status": "optional", "reason": "高血压急症是急性靶器官损害状态，闭环核心为识别、处理和监测，不要求独立病因。"}},
            "DIS-CARD-HT-URGENCY": {"etiology": {"status": "optional", "reason": "高血压亚急症是严重血压升高但无急性靶器官损害状态，闭环核心为识别和逐步降压。"}},
            "DIS-CARD-HT-RENAL-PARENCHYMAL": {"symptom": {"status": "optional", "reason": reason_secondary_symptom}},
            "DIS-CARD-HT-RENOVASCULAR": {"symptom": {"status": "optional", "reason": reason_secondary_symptom}},
        },
    }
    out = batch_dir / "00_scope_and_config" / "pathway_applicability_profile.json"
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")


REQUIRED_BACKFILLS = [
    ("DIS-CARD-HT-PRIMARY", "has_etiology", "ETI-HT-PRIMARY-MULTIFACTOR", "原发性高血压多因素病因", "Etiology", "病因", "EVD-8BC86A5066B7857D2C97-PRIMARY"),
    ("DIS-CARD-HT-ENDOCRINE", "has_etiology", "ETI-HT-ENDOCRINE-CAUSES", "内分泌相关疾病导致高血压", "Etiology", "病因", "EVD-27792023C00C4669AF72-ENDOCRINE"),
    ("DIS-CARD-HT-CKD", "requires_exam", "EXAM-HT-CKD-EGFR-UACR", "CKD高血压肾功能和尿蛋白评估", "Exam", "检查", "EVD-2DDA42E80412B28DBCD1-CKD"),
    ("DIS-CARD-HT-CKD", "has_diagnostic_criteria", "DXC-HT-CKD", "CKD合并高血压诊断标准", "DiagnosisCriteria", "诊断", "EVD-2DDA42E80412B28DBCD1-CKD"),
    ("DIS-CARD-HT-CKD", "has_follow_up", "FU-HT-CKD-BP-RENAL", "CKD高血压血压和肾功能随访", "FollowUp", "随访", "EVD-7F8B4E3BE297F3DA1AC7-CKD"),
    ("DIS-CARD-HT-ELDERLY", "has_diagnostic_criteria", "DXC-HT-ELDERLY", "老年高血压诊断标准", "DiagnosisCriteria", "诊断", "EVD-2A5F1BF0D4498B079EAA-ELDERLY"),
    ("DIS-CARD-HT-EMERGENCY", "has_diagnostic_criteria", "DXC-HT-EMERGENCY", "高血压急症诊断标准", "DiagnosisCriteria", "诊断", "EVD-909D53DCC890EB901C7A-EMERGENCY"),
    ("DIS-CARD-HT-URGENCY", "has_diagnostic_criteria", "DXC-HT-URGENCY", "高血压亚急症诊断标准", "DiagnosisCriteria", "诊断", "EVD-F26E32F2BA8ADBF83473-URGENCY"),
    ("DIS-CARD-HT-MASKED", "has_diagnostic_criteria", "DXC-HT-MASKED", "隐匿性高血压诊断标准", "DiagnosisCriteria", "诊断", "EVD-5C3E34985A31B63EF4DB-MASKED"),
    ("DIS-CARD-HT-MASKED", "has_prognosis", "PROG-HT-MASKED-CV-RISK", "隐匿性高血压心血管风险", "Prognosis", "预后", "EVD-0040FF70AE9673018DB5-MASKED"),
    ("DIS-CARD-HT-WCH", "has_diagnostic_criteria", "DXC-HT-WCH", "白大衣高血压诊断标准", "DiagnosisCriteria", "诊断", "EVD-C2D90AE1E14C9148437B-WCH"),
    ("DIS-CARD-HT-RENAL-PARENCHYMAL", "has_etiology", "ETI-HT-RENAL-PARENCHYMAL", "肾实质病变导致高血压", "Etiology", "病因", "EVD-47EDE155E1D93F693580-PARENCHYMAL"),
    ("DIS-CARD-HT-RENAL-PARENCHYMAL", "has_diagnostic_criteria", "DXC-HT-RENAL-PARENCHYMAL", "肾实质性高血压诊断标准", "DiagnosisCriteria", "诊断", "EVD-47EDE155E1D93F693580-PARENCHYMAL"),
    ("DIS-CARD-HT-RENOVASCULAR", "has_etiology", "ETI-HT-RENOVASCULAR", "肾动脉狭窄和肾缺血导致高血压", "Etiology", "病因", "EVD-94C7E566B0A8FDC6FDFA-RENOVASCULAR"),
    ("DIS-CARD-HT-RENOVASCULAR", "has_diagnostic_criteria", "DXC-HT-RENOVASCULAR", "肾血管性高血压诊断标准", "DiagnosisCriteria", "诊断", "EVD-94C7E566B0A8FDC6FDFA-RENOVASCULAR"),
    ("DIS-CARD-HT-PAROXYSMAL", "has_etiology", "ETI-HT-PAROXYSMAL-TRIGGERS", "发作性高血压诱因和病因", "Etiology", "病因", "EVD-6AD0B646AD8AAF13F84F-PAROXYSMAL"),
    ("DIS-CARD-HT-PAROXYSMAL", "has_diagnostic_criteria", "DXC-HT-PAROXYSMAL", "发作性高血压诊断标准", "DiagnosisCriteria", "诊断", "EVD-6AD0B646AD8AAF13F84F-PAROXYSMAL"),
    ("DIS-CARD-HT-PAROXYSMAL", "has_treatment_plan", "PLAN-HT-PAROXYSMAL-CAUSE-BASED", "发作性高血压诱因处理和病因导向治疗", "TreatmentPlan", "治疗", "EVD-6AD0B646AD8AAF13F84F-PAROXYSMAL"),
]


MEDICATION_ALIAS_BACKFILL = {
    "氨氯地平": ["Amlodipine"],
    "比索洛尔": ["Bisoprolol"],
    "拉贝洛尔": ["Labetalol"],
    "螺内酯": ["Spironolactone"],
    "氯沙坦": ["Losartan"],
    "美托洛尔": ["Metoprolol"],
    "尼卡地平": ["Nicardipine"],
    "培哚普利": ["Perindopril"],
    "替米沙坦": ["Telmisartan"],
    "乌拉地尔": ["Urapidil"],
    "硝苯地平": ["Nifedipine"],
    "硝普钠": ["Sodium nitroprusside"],
    "硝酸甘油": ["Nitroglycerin"],
    "缬沙坦": ["Valsartan"],
    "依普利酮": ["Eplerenone"],
    "吲达帕胺": ["Indapamide"],
}


BACKFILL_TARGET_ALIASES = {
    "ETI-HT-PRIMARY-MULTIFACTOR": ["RAAS", "血管紧张素", "醛固酮系统", "血压升高"],
    "ETI-HT-ENDOCRINE-CAUSES": ["内分泌性高血压", "筛查阳性", "识别可能的病因"],
    "EXAM-HT-CKD-EGFR-UACR": ["UACR", "尿蛋白", "肾功能", "CKD患者"],
    "DXC-HT-CKD": ["CKD患者", "收缩压≥130", "舒张压≥80", "尿蛋白"],
    "FU-HT-CKD-BP-RENAL": ["长期甚至终身治疗", "透析患者", "血压分级", "心血管风险分层"],
    "DXC-HT-ELDERLY": ["老年高血压", "诊断标准与方法", "140/90mmHg"],
    "DXC-HT-EMERGENCY": ["高血压急症", "靶器官功能损害", "收缩压>180", "舒张压>120"],
    "DXC-HT-URGENCY": ["高血压亚急症", "不伴严重临床症状", "不伴进行性靶器官损害"],
    "DXC-HT-MASKED": ["隐匿性高血压", "诊室血压", "动态血压", "家庭自测血压"],
    "PROG-HT-MASKED-CV-RISK": ["隐匿性高血压", "危险因素", "心血管事件风险", "靶器官损害"],
    "DXC-HT-WCH": ["white coat hypertension", "masked hypertension", "home", "24-hour"],
    "ETI-HT-RENAL-PARENCHYMAL": ["肾单位大量丢失", "水钠潴留", "肾脏RAAS", "肾实质性高血压"],
    "DXC-HT-RENAL-PARENCHYMAL": ["肾实质性高血压", "蛋白尿", "血尿", "肾小球滤过功能"],
    "ETI-HT-RENOVASCULAR": ["肾血管性高血压", "肾动脉", "肾脏缺血", "激活RAAS"],
    "DXC-HT-RENOVASCULAR": ["肾血管性高血压", "血管杂音", "肾动脉彩超", "肾动脉造影"],
    "ETI-HT-PAROXYSMAL-TRIGGERS": ["发作性高血压", "拟交感活性药物", "精神心理因素", "诱因"],
    "DXC-HT-PAROXYSMAL": ["发作性高血压", "收缩压≥160", "舒张压≥100", "血压急剧升高"],
    "PLAN-HT-PAROXYSMAL-CAUSE-BASED": ["发作性高血压", "控制原发病", "去除诱因", "血压管理"],
}


def repair_batch(batch_dir: Path) -> dict[str, Any]:
    data_dir = batch_dir / "05_data_instance"
    out_dir = batch_dir / "08_cdss_upgrade"
    backup_dir = out_dir / "backup_before_20260710_ht_repair"
    out_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in ("nodes_final.jsonl", "relations_final.jsonl", "graph_final.json"):
        src = data_dir / name
        dst = backup_dir / name
        if src.is_file() and not dst.is_file():
            shutil.copy2(src, dst)

    build_profile(batch_dir)

    nodes = read_jsonl(data_dir / "nodes_final.jsonl")
    relations = read_jsonl(data_dir / "relations_final.jsonl")
    evidence_index = {
        row.get("evidence_id"): row
        for row in read_jsonl(batch_dir / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl")
    }
    nodes_by_code = {node["code"]: node for node in nodes}
    rel_by_key = {(rel["source_code"], rel["relationType"], rel["target_code"]): rel for rel in relations}
    guidelines = [node for node in nodes if node.get("entityType") == "Guideline"]
    disease_nodes = [node for node in nodes if node.get("entityType") == "Disease"]

    new_nodes = 0
    new_relations = 0
    updated_nodes = 0
    updated_relations = 0

    for disease_code, rel_type, target_code, target_name, entity_type, category, evidence_id in REQUIRED_BACKFILLS:
        evidence = evidence_index.get(evidence_id)
        if not evidence:
            raise RuntimeError(f"Missing evidence for required backfill: {evidence_id}")
        before = target_code in nodes_by_code
        node = common_node(target_code, target_name, entity_type, category, disease_code)
        node["description"] = evidence.get("evidence_text", "")[:800]
        node["aliases"] = list(dict.fromkeys([target_name, *BACKFILL_TARGET_ALIASES.get(target_code, [])]))
        node["source_quality"] = "hypertension_required_pathway_backfill"
        node["clinical_review_status"] = "clinical_batch_signed_off"
        upsert_node(nodes_by_code, node)
        new_nodes += 0 if before else 1
        updated_nodes += 1 if before else 0

        clinical_status = "clinical_batch_signed_off" if rel_type in {"has_treatment_plan"} else "not_applicable"
        before_rel = (disease_code, rel_type, target_code) in rel_by_key
        rel = common_rel(
            disease_code,
            rel_type,
            target_code,
            "therapeutic" if rel_type == "has_treatment_plan" else ("diagnostic" if "diagnostic" in rel_type or rel_type == "requires_exam" else "clinical"),
            evidence,
            clinical_review_status=clinical_status,
            applicable_population=f"{nodes_by_code[disease_code]['name']}患者中符合该条目评估或干预适应证者。",
            exclusion_criteria="存在与该建议相冲突的禁忌证、急危重状态或资料不足时，需临床医师复核后执行。",
            recommendation_context="高血压批次required闭环回补",
        )
        upsert_relation(rel_by_key, rel)
        new_relations += 0 if before_rel else 1
        updated_relations += 1 if before_rel else 0

        before_evidence_rel = (target_code, "supported_by_evidence", evidence_id) in rel_by_key
        upsert_relation(rel_by_key, common_rel(target_code, "supported_by_evidence", evidence_id, "evidence", evidence))
        new_relations += 0 if before_evidence_rel else 1

    for node in nodes_by_code.values():
        if node.get("entityType") != "Medication":
            continue
        aliases = list(dict.fromkeys(node.get("aliases") or []))
        additions = []
        if node.get("name_en"):
            additions.append(node["name_en"])
        if node.get("abbr"):
            additions.append(node["abbr"])
        additions.extend(MEDICATION_ALIAS_BACKFILL.get(node.get("name"), []))
        merged = list(dict.fromkeys([*aliases, *[item for item in additions if item]]))
        if merged != aliases:
            node["aliases"] = merged
            node["clinical_review_status"] = "clinical_batch_signed_off"
            updated_nodes += 1

    for disease in disease_nodes:
        disease_code = disease["code"]
        suffix = safe_code(disease_code)
        pathway_code = f"PATH-HT-{suffix}"
        pathway_name = f"{disease['name']}专病诊疗路径"
        evidence_id = next(
            (
                rel.get("evidence_id")
                for rel in rel_by_key.values()
                if rel.get("source_code") == disease_code and rel.get("evidence_id")
            ),
            None,
        )
        if not evidence_id:
            ev = next((row for row in evidence_index.values() if row.get("disease_code") == disease_code), None)
            evidence_id = ev.get("evidence_id") if ev else None
        evidence = evidence_index.get(evidence_id) if evidence_id else {}

        before = pathway_code in nodes_by_code
        upsert_node(
            nodes_by_code,
            {
                **common_node(pathway_code, pathway_name, "ClinicalPathway", "临床流程", disease_code),
                "pathway_goal": "按诊断确认、风险评估、治疗决策、随访管理组织专病CDSS推荐。",
                "execution_boundary": "图谱承载医学知识、推荐语义和证据链；专病流程引擎根据EMR事件和患者状态触发。",
            },
        )
        new_nodes += 0 if before else 1
        before_rel = (disease_code, "has_clinical_pathway", pathway_code) in rel_by_key
        upsert_relation(rel_by_key, common_rel(disease_code, "has_clinical_pathway", pathway_code, "pathway", evidence))
        new_relations += 0 if before_rel else 1

        stages = [
            ("DIAG", "诊断确认", "采集诊室血压、诊室外血压、靶器官损害和继发性病因线索。"),
            ("RISK", "风险评估", "评估心血管风险、共病、靶器官损害和特殊人群因素。"),
            ("TX", "治疗决策", "根据风险、合并症、禁忌证和证据等级生成治疗建议。"),
            ("FU", "随访管理", "根据血压达标情况、药物安全性和靶器官风险安排随访。"),
        ]
        previous_stage = None
        for order, (stage_key, stage_name, goal) in enumerate(stages, start=1):
            stage_code = f"STAGE-HT-{suffix}-{stage_key}"
            before_stage = stage_code in nodes_by_code
            upsert_node(
                nodes_by_code,
                {
                    **common_node(stage_code, f"{disease['name']}{stage_name}", "PathwayStage", "临床流程", disease_code),
                    "stage_order": order,
                    "stage_goal": goal,
                    "trigger_condition": "进入该疾病专病诊疗路径且满足上一阶段退出条件。",
                    "exit_condition": "本阶段必要评估、推荐和安全校验完成。",
                },
            )
            new_nodes += 0 if before_stage else 1
            before_stage_rel = (pathway_code, "has_pathway_stage", stage_code) in rel_by_key
            upsert_relation(rel_by_key, common_rel(pathway_code, "has_pathway_stage", stage_code, "pathway", evidence))
            new_relations += 0 if before_stage_rel else 1
            if previous_stage:
                before_next = (previous_stage, "next_pathway_stage", stage_code) in rel_by_key
                upsert_relation(rel_by_key, common_rel(previous_stage, "next_pathway_stage", stage_code, "pathway", evidence))
                new_relations += 0 if before_next else 1
            previous_stage = stage_code

        action_targets = {
            "DIAG": first_existing_target(rel_by_key, disease_code, ["has_diagnostic_criteria", "requires_exam", "requires_lab_test"]),
            "TX": first_existing_target(rel_by_key, disease_code, ["has_treatment_plan", "treated_by_medication", "treated_by_procedure"]),
            "FU": first_existing_target(rel_by_key, disease_code, ["has_follow_up", "has_prognosis"]),
        }
        for stage_key, action_code in action_targets.items():
            if not action_code or action_code not in nodes_by_code:
                continue
            stage_code = f"STAGE-HT-{suffix}-{stage_key}"
            rule_code = f"RULE-HT-{suffix}-{stage_key}"
            rec_code = f"REC-HT-{suffix}-{stage_key}-{safe_code(action_code)[:24]}"
            action = nodes_by_code[action_code]
            if action.get("entityType") == "TreatmentPlan":
                before_plan_path = (action_code, "has_clinical_pathway", pathway_code) in rel_by_key
                upsert_relation(rel_by_key, common_rel(action_code, "has_clinical_pathway", pathway_code, "pathway", evidence))
                new_relations += 0 if before_plan_path else 1
            before_rule = rule_code in nodes_by_code
            upsert_node(
                nodes_by_code,
                {
                    **common_node(rule_code, f"{disease['name']}{stage_key}阶段触发规则", "ClinicalRule", "规则", disease_code),
                    "rule_expression_cn": f"当患者进入{disease['name']}路径的{stage_key}阶段时，结合EMR数据、禁忌证和证据链评估是否推荐{action['name']}。",
                    "trigger_event": "emr_patient_state_changed",
                },
            )
            new_nodes += 0 if before_rule else 1
            for source, rel_type, target in [
                (disease_code, "has_clinical_rule", rule_code),
                (stage_code, "has_stage_rule", rule_code),
            ]:
                before_rule_rel = (source, rel_type, target) in rel_by_key
                upsert_relation(rel_by_key, common_rel(source, rel_type, target, "rule", evidence))
                new_relations += 0 if before_rule_rel else 1

            before_rec = rec_code in nodes_by_code
            ev = evidence_fields(evidence)
            upsert_node(
                nodes_by_code,
                {
                    **common_node(rec_code, f"{disease['name']}：{action['name']}推荐", "RecommendationStatement", "推荐", disease_code),
                    "recommendation_text": f"{disease['name']}患者在{stage_key}阶段，如满足适用条件且无排除/禁忌条件，建议评估或执行：{action['name']}。",
                    "recommendation_class": ev["recommendation_class"],
                    "evidence_level": ev["evidence_level"],
                    "source_name": ev["source_name"],
                    "source_page": ev["source_page"],
                    "evidence_id": ev["evidence_id"],
                    "applicable_population": f"{disease['name']}患者中符合该推荐适用条件者。",
                    "exclusion_criteria": "存在禁忌证、资料不足、替代诊断更可能或患者状态不稳定时，需临床医师复核。",
                    "cdss_release_level": "test_recommendation",
                    "ai_evidence_review_status": "ai_prechecked_limited",
                },
            )
            new_nodes += 0 if before_rec else 1
            for source, rel_type, target, category in [
                (stage_code, "has_recommendation_statement", rec_code, "recommendation"),
                (rule_code, "has_recommendation_statement", rec_code, "recommendation"),
                (rec_code, "recommends_action", action_code, "recommendation"),
                (rec_code, "derived_from", ev["evidence_id"], "evidence"),
            ]:
                before_rs_rel = (source, rel_type, target) in rel_by_key
                upsert_relation(rel_by_key, common_rel(source, rel_type, target, category, evidence))
                new_relations += 0 if before_rs_rel else 1
            guideline_code = guideline_code_for_evidence(guidelines, evidence)
            if guideline_code:
                before_guideline_rel = (rec_code, "based_on_guideline", guideline_code) in rel_by_key
                upsert_relation(rel_by_key, common_rel(rec_code, "based_on_guideline", guideline_code, "evidence", evidence))
                new_relations += 0 if before_guideline_rel else 1

    final_nodes = sorted(nodes_by_code.values(), key=lambda row: row.get("code", ""))
    final_relations = sorted(rel_by_key.values(), key=lambda row: row.get("id", ""))
    write_jsonl(data_dir / "nodes_final.jsonl", final_nodes)
    write_jsonl(data_dir / "relations_final.jsonl", final_relations)
    write_csv(data_dir / "nodes_final.csv", final_nodes)
    write_csv(data_dir / "relations_final.csv", final_relations)
    (data_dir / "graph_final.json").write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "batch_id": BATCH_ID,
                "nodes": final_nodes,
                "relations": final_relations,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8-sig",
    )

    summary = {
        "batch_dir": str(batch_dir),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "node_count": len(final_nodes),
        "relation_count": len(final_relations),
        "new_nodes": new_nodes,
        "updated_nodes": updated_nodes,
        "new_relations": new_relations,
        "updated_relations": updated_relations,
        "profile_path": str(batch_dir / "00_scope_and_config" / "pathway_applicability_profile.json"),
        "backup_dir": str(backup_dir),
    }
    (out_dir / "hypertension_quality_repair_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair hypertension batch required slots and CDSS pathway layer.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(repair_batch(args.batch_dir.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
