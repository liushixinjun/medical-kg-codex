# -*- coding: utf-8 -*-
"""生成冠心病剩余病种教材骨架批量精修包。

只生成本地 delta、审计矩阵和报告；不连接 Neo4j，不修改旧批次。

输入：
- 心血管内科全章节骨架扩展 D6 候选节点/关系
- 心血管内科全章节骨架扩展 D1 原文证据锚点
- 旧冠心病批次疾病编码索引

目标：
- 复用旧 CAD 疾病主节点编码
- 对 UA/NSTEMI 合并章节、隐匿型/隐匿性名称差异做映射
- 过滤明显泛化的“鉴别诊断/因此需要鉴别诊断”等空壳候选
- 形成可审计、可导入、可服务器 postcheck 的增量包
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "心血管内科文献集合"
SKELETON_DIR = (
    COLLECTION
    / "00_教材骨架库_foundation_skeleton"
    / "心血管内科全章节骨架扩展_CARD-SKELETON-FULL-20260709"
)
OLD_CAD_BATCH = COLLECTION / "BATCH-CARD-CAD-20260623-001"
OUT_DIR = COLLECTION / "BATCH-CARD-CAD-REMAINING-20260712-001_冠心病剩余病种教材骨架精修_textbook_refine"
BATCH_ID = "BATCH-CARD-CAD-REMAINING-20260712-001"
CREATED_AT = "2026-07-12 21:45:00"
SCHEMA_VERSION = "V1.15"
SKILL_VERSION = "V2.1-CAD-remaining-textbook-refine"


RELATION_MAP = {
    "HAS_DEFINITION": "has_definition",
    "HAS_DEFINITION_COMPONENT": "has_definition_component",
    "HAS_ETIOLOGY": "has_etiology",
    "HAS_PATHOPHYSIOLOGY": "has_pathophysiology",
    "HAS_EPIDEMIOLOGY": "has_epidemiology",
    "HAS_SYMPTOM": "has_symptom",
    "HAS_SIGN": "has_sign",
    "HAS_RISK_FACTOR": "has_risk_factor",
    "HAS_COMPLICATION": "may_cause_complication",
    "HAS_EXAM": "requires_exam",
    "HAS_LAB_TEST": "requires_lab_test",
    "HAS_DIAGNOSTIC_COMPONENT": "has_diagnostic_component",
    "HAS_DIFFERENTIAL_DIAGNOSIS": "differentiates_from",
    "HAS_RISK_STRATIFICATION": "has_risk_stratification",
    "HAS_TREATMENT_PLAN": "has_treatment_plan",
    "USES_MEDICATION": "treated_by_medication",
    "HAS_PROCEDURE": "treated_by_procedure",
    "HAS_FOLLOW_UP": "has_follow_up",
    "HAS_PROGNOSIS": "has_prognosis",
    "HAS_PREVENTION": "has_prevention",
    "HAS_CLASSIFICATION": "has_classification",
}

ENTITY_PREFIX = {
    "Definition": "DEF",
    "DefinitionComponent": "DEF-COMP",
    "Etiology": "ETI",
    "Pathophysiology": "PATH",
    "Epidemiology": "EPI",
    "Symptom": "SYM",
    "Sign": "SIGN",
    "RiskFactor": "RF",
    "Complication": "COMP",
    "Exam": "EXAM",
    "LabTest": "LAB",
    "DiagnosisCriteria": "DXC",
    "DiagnosisCriteriaComponent": "DXC-COMP",
    "DifferentialDiagnosis": "DDX",
    "RiskStratification": "RISK",
    "TreatmentPlan": "PLAN",
    "Medication": "MED",
    "Procedure": "PROC",
    "FollowUp": "FU",
    "Prognosis": "PROG",
    "Prevention": "PREV",
    "DiseaseClassification": "CLASS",
    "ClinicalRule": "RULE",
    "Evidence": "EVD",
}

SOURCE_NAME = "《内科学（第10版）》"
SOURCE_TYPE = "authoritative_textbook"


DISEASE_SPECS = [
    {
        "code": "DIS-CARD-CAD-ACS",
        "name": "急性冠脉综合征",
        "category": "冠心病",
        "sources": ["急性冠脉综合征"],
        "shared_sources": ["冠状动脉粥样硬化性心脏病概述"],
        "allow_types": {"Definition", "DefinitionComponent", "DiseaseClassification", "Pathophysiology"},
    },
    {
        "code": "DIS-CARD-CAD-AMI",
        "name": "急性心肌梗死",
        "category": "冠心病",
        "sources": ["急性 ST 段抬高型心肌梗死"],
        "allow_types": {
            "Definition",
            "DefinitionComponent",
            "Etiology",
            "Pathophysiology",
            "Symptom",
            "Sign",
            "Exam",
            "LabTest",
            "DiagnosisCriteriaComponent",
            "DifferentialDiagnosis",
            "RiskFactor",
            "Complication",
            "TreatmentPlan",
            "Medication",
            "Procedure",
            "FollowUp",
            "Prognosis",
            "Prevention",
        },
    },
    {
        "code": "DIS-CARD-CAD-UA",
        "name": "不稳定型心绞痛",
        "category": "冠心病",
        "sources": ["不稳定型心绞痛和非 ST 段抬高型心肌梗死"],
        "allow_types": {
            "Definition",
            "DefinitionComponent",
            "Etiology",
            "Symptom",
            "Sign",
            "Exam",
            "LabTest",
            "DiagnosisCriteriaComponent",
            "DifferentialDiagnosis",
            "RiskFactor",
            "RiskStratification",
            "DiseaseClassification",
            "Medication",
            "Procedure",
        },
    },
    {
        "code": "DIS-CARD-CAD-NSTEMI",
        "name": "非ST段抬高型心肌梗死",
        "category": "冠心病",
        "sources": ["不稳定型心绞痛和非 ST 段抬高型心肌梗死"],
        "allow_types": {
            "Definition",
            "DefinitionComponent",
            "Etiology",
            "Symptom",
            "Sign",
            "Exam",
            "LabTest",
            "DiagnosisCriteriaComponent",
            "DifferentialDiagnosis",
            "RiskFactor",
            "RiskStratification",
            "DiseaseClassification",
            "Medication",
            "Procedure",
        },
    },
    {
        "code": "DIS-CARD-CAD-CCS",
        "name": "慢性冠脉综合征",
        "category": "冠心病",
        "sources": ["冠状动脉粥样硬化性心脏病概述"],
        "shared_sources": ["稳定型心绞痛", "隐匿型冠心病"],
        "allow_types": {"Definition", "DefinitionComponent", "DiseaseClassification", "Pathophysiology", "RiskFactor"},
    },
    {
        "code": "DIS-CARD-CAD-STABLE-ANGINA",
        "name": "稳定型心绞痛",
        "category": "冠心病",
        "sources": ["稳定型心绞痛"],
        "allow_types": {
            "Definition",
            "Pathophysiology",
            "Symptom",
            "Sign",
            "Exam",
            "LabTest",
            "DiagnosisCriteriaComponent",
            "DifferentialDiagnosis",
            "Medication",
            "FollowUp",
            "Prognosis",
            "Prevention",
        },
    },
    {
        "code": "DIS-CARD-CAD-ICM",
        "name": "缺血性心肌病",
        "category": "冠心病",
        "sources": ["缺血性心肌病"],
        "allow_types": {
            "Definition",
            "DefinitionComponent",
            "Symptom",
            "Sign",
            "Exam",
            "DiagnosisCriteriaComponent",
            "DifferentialDiagnosis",
            "Procedure",
        },
    },
    {
        "code": "DIS-CARD-CAD-SILENT-ISCHEMIA",
        "name": "隐匿性冠心病",
        "category": "冠心病",
        "sources": ["隐匿型冠心病"],
        "allow_types": {"Definition", "DefinitionComponent", "Symptom", "Exam", "DifferentialDiagnosis", "Medication", "Procedure"},
    },
    {
        "code": "DIS-CARD-CAD-OLD-MI",
        "name": "陈旧性心肌梗死",
        "category": "冠心病",
        "sources": [],
        "allow_types": set(),
    },
]


SHORT_ENTITY_TYPES = {"Symptom", "Sign", "Exam", "LabTest", "Medication", "Procedure", "RiskFactor", "Complication"}
STATEMENT_ENTITY_TYPES = {
    "DefinitionComponent",
    "Etiology",
    "Pathophysiology",
    "DiagnosisCriteriaComponent",
    "DifferentialDiagnosis",
    "Prognosis",
    "FollowUp",
    "Prevention",
    "DiseaseClassification",
}
GENERIC_BAD_PATTERNS = [
    "因此需要鉴别诊断",
    "与其他疾病的鉴别诊断参见",
    "结合年龄和存在冠心病危险因素",
    "诊断未明确的症状不典型但病情稳定者",
    "在出院前可作",
]


def short_hash(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest().upper()[:n]


def kg_id(code: str) -> str:
    return "KG_" + re.sub(r"[^0-9A-Za-z_一-龥]", "_", code)


def rel_id(source: str, rel_type: str, target: str) -> str:
    return "REL-" + short_hash(f"{source}|{rel_type}|{target}", 20)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")


def csv_write(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def clean_name(text: str) -> str:
    text = re.sub(r"\s+", "", str(text or ""))
    text = text.replace("（", "(").replace("）", ")")
    return text.strip("；。,.，、 ")


def display_name_for(entity_type: str, disease_name: str, raw_name: str, seq: int) -> str:
    raw = raw_name.strip()
    if entity_type in SHORT_ENTITY_TYPES and len(raw) <= 32:
        return raw
    if entity_type == "Definition":
        return f"{disease_name}定义"
    if entity_type == "DiagnosisCriteriaComponent":
        return raw if len(raw) <= 36 else f"{disease_name}诊断要点{seq}"
    if entity_type == "DifferentialDiagnosis":
        return raw if len(raw) <= 24 else f"{disease_name}鉴别诊断要点{seq}"
    label = {
        "DefinitionComponent": "定义要点",
        "Etiology": "病因机制要点",
        "Pathophysiology": "病理生理要点",
        "Prognosis": "预后要点",
        "FollowUp": "随访要点",
        "Prevention": "预防要点",
        "DiseaseClassification": "分类要点",
    }.get(entity_type, "知识要点")
    return raw if len(raw) <= 32 else f"{disease_name}{label}{seq}"


def node_code(entity_type: str, name: str, disease_code: str) -> str:
    prefix = ENTITY_PREFIX.get(entity_type, "NODE")
    disease_suffix = disease_code.replace("DIS-CARD-CAD-", "")
    return f"{prefix}-CARD-CADREM-{disease_suffix}-{short_hash(entity_type + '|' + name, 10)}"


def evidence_code(evidence_id: str) -> str:
    if evidence_id:
        return f"EVD-CARD-TEXTBOOK-{short_hash(evidence_id, 16)}"
    return f"EVD-CARD-TEXTBOOK-{short_hash('missing', 16)}"


def source_section_from_evidence(evidence: dict[str, Any]) -> str:
    return str(evidence.get("source_section_path") or "")


def include_candidate(spec: dict[str, Any], row: dict[str, Any]) -> bool:
    entity_type = str(row.get("target_type") or "")
    if entity_type not in spec["allow_types"]:
        return False
    name = clean_name(row.get("target_name") or "")
    if not name:
        return False
    if entity_type in SHORT_ENTITY_TYPES and len(name) > 32:
        return False
    if entity_type in {"DifferentialDiagnosis", "DiagnosisCriteriaComponent"}:
        if any(pattern in name for pattern in GENERIC_BAD_PATTERNS):
            return False
    if entity_type == "DifferentialDiagnosis" and len(name) > 36:
        return False
    if "表3-" in name and entity_type not in {"DiseaseClassification", "RiskStratification"}:
        return False
    return True


def node_base(entity_type: str, name: str, code: str, spec: dict[str, Any], **props: Any) -> dict[str, Any]:
    return {
        "id": kg_id(code),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "scope_type": "disease_category_batch_refine",
        "scope_target": "冠心病剩余病种",
        "top_specialty": "心血管内科",
        "disease_category": spec["category"],
        "disease_code": spec["code"],
        "disease_name": spec["name"],
        "source_type": SOURCE_TYPE,
        "source_authority": SOURCE_NAME,
        "clinical_review_status": "pending_clinical_use_effect_review",
        "review_status": "ai_prechecked",
        "merge_status": "delta_ready",
        "formal_cdss_ready": False,
        "cdss_release_level": "test_recommendation",
        "created_at": CREATED_AT,
        **props,
    }


def relation_base(source_code: str, relation_type: str, target_code: str, spec: dict[str, Any], **props: Any) -> dict[str, Any]:
    return {
        "id": rel_id(source_code, relation_type, target_code),
        "source_code": source_code,
        "target_code": target_code,
        "relationType": relation_type,
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "scope_type": "disease_category_batch_refine",
        "scope_target": "冠心病剩余病种",
        "top_specialty": "心血管内科",
        "disease_category": spec["category"],
        "disease_code": spec["code"],
        "disease_name": spec["name"],
        "source_type": SOURCE_TYPE,
        "clinical_review_status": "pending_clinical_use_effect_review",
        "review_status": "ai_prechecked",
        "formal_cdss_ready": False,
        "created_at": CREATED_AT,
        **props,
    }


def load_old_disease_codes() -> set[str]:
    codes = set()
    for node in read_jsonl(OLD_CAD_BATCH / "05_data_instance" / "nodes_final.jsonl"):
        if node.get("entityType") == "Disease" and str(node.get("code") or "").startswith("DIS-CARD-CAD"):
            codes.add(str(node["code"]))
    return codes


def main() -> int:
    relations_raw = read_jsonl(SKELETON_DIR / "阶段D6_合并结构化候选_relations_20260709.jsonl")
    evidences_raw = {
        str(row.get("evidence_id")): row
        for row in read_jsonl(SKELETON_DIR / "阶段D1_全章节教材骨架原文锚点_evidence_20260709.jsonl")
    }
    old_disease_codes = load_old_disease_codes()

    relations_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in relations_raw:
        relations_by_source[str(row.get("source_name") or "")].append(row)

    nodes_by_code: dict[str, dict[str, Any]] = {}
    relations_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    audit_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    candidate_seq: Counter[tuple[str, str]] = Counter()

    def add_node(node: dict[str, Any]) -> None:
        nodes_by_code[node["code"]] = node

    def add_relation(rel: dict[str, Any]) -> None:
        key = (rel["source_code"], rel["relationType"], rel["target_code"])
        relations_by_key[key] = rel

    for spec in DISEASE_SPECS:
        if spec["code"] not in old_disease_codes:
            gap_rows.append(
                {
                    "疾病编码": spec["code"],
                    "疾病名称": spec["name"],
                    "缺口类型": "disease_code_missing_in_old_cad",
                    "说明": "旧冠心病批次未找到该疾病主节点编码，本轮未新造疾病主节点。",
                }
            )
            continue

        source_names = list(spec.get("sources") or [])
        if not source_names:
            gap_rows.append(
                {
                    "疾病编码": spec["code"],
                    "疾病名称": spec["name"],
                    "缺口类型": "textbook_source_not_found",
                    "说明": "D6教材骨架未抽到独立章节来源，暂不硬补。",
                }
            )
        source_names.extend(spec.get("shared_sources") or [])

        accepted_count = Counter()
        rejected_count = Counter()
        source_count = 0
        for source_name in source_names:
            for row in relations_by_source.get(source_name, []):
                source_count += 1
                entity_type = str(row.get("target_type") or "")
                raw_name = clean_name(row.get("target_name") or "")
                if not include_candidate(spec, row):
                    rejected_count[entity_type or "UNKNOWN"] += 1
                    continue

                candidate_seq[(spec["code"], entity_type)] += 1
                seq = candidate_seq[(spec["code"], entity_type)]
                display_name = display_name_for(entity_type, spec["name"], raw_name, seq)
                code = node_code(entity_type, display_name, spec["code"])
                evidence_ids = [str(v) for v in (row.get("evidence_ids") or []) if str(v)]
                primary_evidence = evidences_raw.get(evidence_ids[0], {}) if evidence_ids else {}

                if entity_type == "Definition":
                    text_for_node = next(
                        (
                            clean_name(r.get("target_name") or "")
                            for r in relations_by_source.get(source_name, [])
                            if r.get("target_type") == "DefinitionComponent" and include_candidate(spec, r)
                        ),
                        "",
                    )
                    add_node(
                        node_base(
                            "Definition",
                            f"{spec['name']}定义",
                            node_code("Definition", f"{spec['name']}定义", spec["code"]),
                            spec,
                            definition_text=text_for_node,
                            description=text_for_node,
                            source_section=source_section_from_evidence(primary_evidence),
                        )
                    )
                    rel_type = "has_definition"
                    add_relation(
                        relation_base(
                            spec["code"],
                            rel_type,
                            node_code("Definition", f"{spec['name']}定义", spec["code"]),
                            spec,
                            source_name=SOURCE_NAME,
                            evidence_ids=evidence_ids,
                            extraction_basis="textbook_skeleton_d6",
                        )
                    )
                    accepted_count[entity_type] += 1
                    continue

                add_node(
                    node_base(
                        entity_type,
                        display_name,
                        code,
                        spec,
                        original_text=raw_name if entity_type in STATEMENT_ENTITY_TYPES else "",
                        description=raw_name if display_name != raw_name else "",
                        source_subject_name=source_name,
                        source_section=source_section_from_evidence(primary_evidence),
                        evidence_ids=evidence_ids,
                    )
                )

                rel_type = RELATION_MAP.get(str(row.get("rel_type") or ""))
                if not rel_type:
                    rejected_count[f"{entity_type}_no_relation_map"] += 1
                    continue
                if entity_type == "DiagnosisCriteriaComponent":
                    dxc_name = f"{spec['name']}诊断标准"
                    dxc_code = node_code("DiagnosisCriteria", dxc_name, spec["code"])
                    add_node(
                        node_base(
                            "DiagnosisCriteria",
                            dxc_name,
                            dxc_code,
                            spec,
                            description=f"{spec['name']}教材诊断标准汇总，明细见 has_diagnostic_component。",
                        )
                    )
                    add_relation(relation_base(spec["code"], "has_diagnostic_criteria", dxc_code, spec))
                    add_relation(
                        relation_base(
                            dxc_code,
                            "has_diagnostic_component",
                            code,
                            spec,
                            source_name=SOURCE_NAME,
                            evidence_ids=evidence_ids,
                            extraction_basis="textbook_skeleton_d6",
                        )
                    )
                elif entity_type == "DefinitionComponent":
                    definition_code = node_code("Definition", f"{spec['name']}定义", spec["code"])
                    add_node(
                        node_base(
                            "Definition",
                            f"{spec['name']}定义",
                            definition_code,
                            spec,
                            definition_text=raw_name,
                            description=raw_name,
                        )
                    )
                    add_relation(relation_base(spec["code"], "has_definition", definition_code, spec))
                    add_relation(
                        relation_base(
                            definition_code,
                            "has_definition_component",
                            code,
                            spec,
                            source_name=SOURCE_NAME,
                            evidence_ids=evidence_ids,
                            extraction_basis="textbook_skeleton_d6",
                        )
                    )
                else:
                    add_relation(
                        relation_base(
                            spec["code"],
                            rel_type,
                            code,
                            spec,
                            source_name=SOURCE_NAME,
                            evidence_ids=evidence_ids,
                            extraction_basis="textbook_skeleton_d6",
                        )
                    )

                for evidence_id in evidence_ids[:3]:
                    evidence = evidences_raw.get(evidence_id)
                    if not evidence:
                        continue
                    ev_code = evidence_code(evidence_id)
                    text = str(evidence.get("text_excerpt") or "")
                    add_node(
                        node_base(
                            "Evidence",
                            f"{spec['name']}-{entity_type}-{seq}-教材原文证据",
                            ev_code,
                            spec,
                            evidence_id=evidence_id,
                            evidence_text=text,
                            original_text=text,
                            evidence_summary=text[:180],
                            source_id=evidence.get("source_id"),
                            source_file=evidence.get("source_file"),
                            source_section=evidence.get("source_section_path"),
                            source_page=evidence.get("pdf_page_approx") or "",
                            source_location=f"{SOURCE_NAME}; {evidence.get('source_section_path') or ''}; 段落{evidence.get('docx_para_start') or ''}-{evidence.get('docx_para_end') or ''}",
                            recommendation_class="N/A",
                            evidence_level="N/A",
                            knowledge_strength="high",
                            clinical_applicability="general",
                        )
                    )
                    add_relation(
                        relation_base(
                            code,
                            "supported_by_evidence",
                            ev_code,
                            spec,
                            evidence_id=evidence_id,
                            source_name=SOURCE_NAME,
                        )
                    )

                audit_rows.append(
                    {
                        "疾病编码": spec["code"],
                        "疾病名称": spec["name"],
                        "教材来源名": source_name,
                        "实体类型": entity_type,
                        "实体名称": display_name,
                        "原始候选文本": raw_name,
                        "证据ID": ";".join(evidence_ids),
                        "处理结果": "accepted",
                    }
                )
                accepted_count[entity_type] += 1

        needed = {
            "definition": bool(accepted_count["Definition"] or accepted_count["DefinitionComponent"]),
            "diagnosis": bool(accepted_count["DiagnosisCriteriaComponent"]),
            "manifestation": bool(accepted_count["Symptom"] or accepted_count["Sign"]),
            "exam_or_lab": bool(accepted_count["Exam"] or accepted_count["LabTest"]),
            "treatment": bool(accepted_count["Medication"] or accepted_count["Procedure"] or accepted_count["TreatmentPlan"]),
        }
        for slot, ok in needed.items():
            if not ok and spec["sources"]:
                gap_rows.append(
                    {
                        "疾病编码": spec["code"],
                        "疾病名称": spec["name"],
                        "缺口类型": f"slot_gap_{slot}",
                        "说明": "本轮D6教材候选未覆盖该槽位，后续需指南PDF或人工金标准补充。",
                    }
                )

        coverage_rows.append(
            {
                "疾病编码": spec["code"],
                "疾病名称": spec["name"],
                "来源候选数": source_count,
                "采纳实体数": sum(accepted_count.values()),
                "过滤实体数": sum(rejected_count.values()),
                "采纳类型分布": json.dumps(dict(accepted_count), ensure_ascii=False),
                "过滤类型分布": json.dumps(dict(rejected_count), ensure_ascii=False),
                "定义": "是" if needed["definition"] else "否",
                "诊断": "是" if needed["diagnosis"] else "否",
                "症状体征": "是" if needed["manifestation"] else "否",
                "检查检验": "是" if needed["exam_or_lab"] else "否",
                "治疗": "是" if needed["treatment"] else "否",
            }
        )

    nodes = sorted(nodes_by_code.values(), key=lambda x: (x["entityType"], x["code"]))
    relations = sorted(relations_by_key.values(), key=lambda x: (x["source_code"], x["relationType"], x["target_code"]))

    failures: list[str] = []
    relation_keys = set()
    for node in nodes:
        if not node.get("code") or not node.get("entityType"):
            failures.append(f"node_missing_key:{node}")
        if node.get("entityType") in SHORT_ENTITY_TYPES and len(str(node.get("name") or "")) > 32:
            failures.append(f"short_entity_too_long:{node['code']}:{node['name']}")
    node_codes = {node["code"] for node in nodes} | {spec["code"] for spec in DISEASE_SPECS}
    for rel in relations:
        key = (rel["source_code"], rel["relationType"], rel["target_code"])
        if key in relation_keys:
            failures.append(f"duplicate_relation_key:{key}")
        relation_keys.add(key)
        if rel["relationType"] == "has_related_entity":
            failures.append(f"generic_relation:{rel['id']}")
        if rel["source_code"] not in node_codes:
            failures.append(f"missing_source_in_local_or_disease:{rel['source_code']}->{rel['target_code']}")
        if rel["target_code"] not in node_codes:
            failures.append(f"missing_target_in_local_or_disease:{rel['source_code']}->{rel['target_code']}")

    summary = {
        "batch_id": BATCH_ID,
        "created_at": CREATED_AT,
        "source": "D6 textbook skeleton candidates + old CAD disease code index",
        "node_count": len(nodes),
        "relation_count": len(relations),
        "node_entity_type_counts": dict(Counter(node["entityType"] for node in nodes)),
        "relation_type_counts": dict(Counter(rel["relationType"] for rel in relations)),
        "disease_coverage": coverage_rows,
        "gap_count": len(gap_rows),
        "failure_count": len(failures),
        "failures": failures[:100],
        "local_hard_gate_pass": len(failures) == 0,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "00_config").mkdir(exist_ok=True)
    (OUT_DIR / "01_gold_standard").mkdir(exist_ok=True)
    (OUT_DIR / "02_delta").mkdir(exist_ok=True)
    (OUT_DIR / "03_audit").mkdir(exist_ok=True)
    (OUT_DIR / "04_reports").mkdir(exist_ok=True)

    serializable_specs = []
    for spec in DISEASE_SPECS:
        item = dict(spec)
        item["allow_types"] = sorted(item.get("allow_types") or [])
        serializable_specs.append(item)

    (OUT_DIR / "00_config" / "batch_config.json").write_text(
        json.dumps(
            {
                "batch_id": BATCH_ID,
                "created_at": CREATED_AT,
                "top_specialty": "心血管内科",
                "disease_category": "冠心病",
                "scope": "冠心病剩余病种教材骨架精修扩展",
                "source_batch": str(SKELETON_DIR),
                "old_cad_batch": str(OLD_CAD_BATCH),
                "disease_specs": serializable_specs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_jsonl(OUT_DIR / "02_delta" / "delta_nodes_upsert.jsonl", nodes)
    write_jsonl(OUT_DIR / "02_delta" / "delta_relations_add.jsonl", relations)
    csv_write(
        OUT_DIR / "01_gold_standard" / "冠心病剩余病种教材槽位覆盖矩阵.csv",
        [
            "疾病编码",
            "疾病名称",
            "来源候选数",
            "采纳实体数",
            "过滤实体数",
            "采纳类型分布",
            "过滤类型分布",
            "定义",
            "诊断",
            "症状体征",
            "检查检验",
            "治疗",
        ],
        coverage_rows,
    )
    csv_write(
        OUT_DIR / "03_audit" / "冠心病剩余病种精修采纳明细.csv",
        ["疾病编码", "疾病名称", "教材来源名", "实体类型", "实体名称", "原始候选文本", "证据ID", "处理结果"],
        audit_rows,
    )
    csv_write(
        OUT_DIR / "03_audit" / "冠心病剩余病种缺口矩阵.csv",
        ["疾病编码", "疾病名称", "缺口类型", "说明"],
        gap_rows,
    )
    (OUT_DIR / "03_audit" / "quality_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = [
        "# 冠心病剩余病种教材骨架精修报告",
        "",
        f"- 批次：`{BATCH_ID}`",
        f"- 生成时间：{CREATED_AT}",
        f"- 节点数：{len(nodes)}",
        f"- 关系数：{len(relations)}",
        f"- 本地硬闸门：{'通过' if summary['local_hard_gate_pass'] else '未通过'}",
        f"- 缺口数：{len(gap_rows)}",
        "",
        "## 病种覆盖",
        "",
        "| 疾病 | 采纳实体数 | 定义 | 诊断 | 症状体征 | 检查检验 | 治疗 |",
        "|---|---:|---|---|---|---|---|",
    ]
    for row in coverage_rows:
        report.append(
            f"| {row['疾病名称']} | {row['采纳实体数']} | {row['定义']} | {row['诊断']} | {row['症状体征']} | {row['检查检验']} | {row['治疗']} |"
        )
    report.extend(
        [
            "",
            "## 处理原则",
            "",
            "- 复用旧 CAD 疾病主节点编码，不新造疾病主节点。",
            "- UA/NSTEMI 合并教材章节映射到 UA 与 NSTEMI 两个疾病节点。",
            "- 隐匿型冠心病映射到图谱中的隐匿性冠心病。",
            "- 明显泛化、空壳、跳转式候选不入库，只进入缺口或过滤统计。",
            "- 所有采纳实体均保留教材证据链，`RecommendationClass/EvidenceLevel` 对教材来源固定为 `N/A`。",
        ]
    )
    if gap_rows:
        report.extend(["", "## 未补齐缺口", ""])
        for row in gap_rows:
            report.append(f"- {row['疾病名称']}：{row['缺口类型']}；{row['说明']}")
    (OUT_DIR / "04_reports" / "冠心病剩余病种教材骨架精修报告_20260712.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["local_hard_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
