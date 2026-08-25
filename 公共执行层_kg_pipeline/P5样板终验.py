from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]

ROOT_DISEASES = {
    "冠心病-急性心肌梗死样板": ["DIS-CARD-CAD-AMI"],
    "心肌病样板": ["DIS-CARD-CM-GENERAL"],
}

CLINICAL_ENTITY_TYPES = {
    "Definition",
    "Etiology",
    "Pathophysiology",
    "Epidemiology",
    "Symptom",
    "Sign",
    "RiskFactor",
    "Complication",
    "ExamItem",
    "ExamObservation",
    "LabItem",
    "LabSubitem",
    "DiagnosisCriteria",
    "DiagnosisCriteriaComponent",
    "DifferentialDiagnosis",
    "RiskStratification",
    "TreatmentPlan",
    "Medication",
    "Procedure",
    "TreatmentItem",
    "FollowUp",
    "Prognosis",
    "Prevention",
    "ClinicalRule",
    "RecommendationStatement",
}

STANDARD_REQUIRED_TYPES = {
    "StandardDiagnosis",
    "Medication",
    "Procedure",
    "ExamItem",
    "LabItem",
    "LabSubitem",
    "ExamObservation",
    "TreatmentItem",
    "Symptom",
    "Sign",
}

FORMAL_ACTION_STANDARD_TYPES = {
    "Medication",
    "Procedure",
    "StandardProcedure",
    "ExamItem",
    "LabItem",
    "LabSubitem",
    "ExamObservation",
    "TreatmentItem",
}


def read_db_config(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;]+)", text)
    if not (uri and user and password):
        raise RuntimeError("数据库连接文件无法解析 Bolt 地址、用户名或密码。")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def rows(records: list[Any]) -> list[dict[str, Any]]:
    return [dict(record) for record in records]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, data: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def compact(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def list_codes(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    codes: list[str] = []
    for item in value:
        if isinstance(item, dict):
            code = str(item.get("code") or "").strip()
            name = str(item.get("name") or "").strip()
            if code or name:
                codes.append(f"{name}({code})" if code and name else code or name)
        elif item:
            codes.append(str(item))
    return "；".join(codes)


def is_truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and value == 1:
        return True
    return str(value or "").strip() in {"1", "true", "True", "有效", "是", "yes"}


SCOPED_DISEASE_QUERY = """
MATCH (root:KGNode {entityType:'Disease'})
WHERE root.code IN $root_codes
MATCH (root)-[:has_clinical_subtype*0..4]->(d:KGNode {entityType:'Disease'})
WITH DISTINCT d
OPTIONAL MATCH (parent:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->(d)
OPTIONAL MATCH (d)-[:has_clinical_subtype]->(child:KGNode {entityType:'Disease'})
OPTIONAL MATCH (d)-[sd_rel:has_standard_diagnosis]->(sd:KGNode {entityType:'StandardDiagnosis'})
WITH d,
     collect(DISTINCT parent.code) AS parent_codes,
     collect(DISTINCT child.code) AS child_codes,
     [x IN collect(DISTINCT CASE WHEN sd IS NULL THEN NULL ELSE {
        code: sd.code,
        name: sd.name,
        valid_flag: sd.valid_flag,
        status: sd.status,
        diagnostic_system: properties(sd)['diagnostic_system'],
        mapping_type: sd_rel.mapping_type,
        mapping_status: sd_rel.mapping_status,
        mapping_scope: sd_rel.mapping_scope,
        emr_write_allowed: properties(sd_rel)['emr_write_allowed']
      } END) WHERE x IS NOT NULL] AS standard_diagnoses
RETURN d.code AS disease_code,
       d.name AS disease_name,
       d.english_name AS english_name,
       d.diagnostic_role AS diagnostic_role,
       d.clinical_use_status AS clinical_use_status,
       d.cdss_use_status AS cdss_use_status,
       d.formal_cdss_ready AS formal_cdss_ready,
       properties(d)['icd10'] AS icd10,
       d.standard_code AS standard_code,
       d.cdss_dict_id AS cdss_dict_id,
       d.dictionary_validation_status AS dictionary_validation_status,
       parent_codes,
       child_codes,
       standard_diagnoses,
       size(child_codes) AS child_count,
       size(parent_codes) AS parent_count
ORDER BY disease_name
"""


DIMENSION_COUNT_QUERY = """
MATCH (d:KGNode {entityType:'Disease', code:$code})
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode)
  WHERE type(r)='has_definition' OR x.entityType='Definition'
  RETURN count(DISTINCT x) AS definition_nodes
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'Symptom'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS symptom_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'Sign'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS sign_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'RiskFactor'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS risk_factor_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'Complication'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS complication_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'ExamItem'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS exam_item_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'LabItem'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS lab_item_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[:has_exam_plan]->(:KGNode {entityType:'ExamPlan'})
    -[:includes_exam_item]->(:KGNode {entityType:'ExamItem'})
    -[:exam_item_has_observation]->(x:KGNode {entityType:'ExamObservation'})
  RETURN count(DISTINCT x) AS exam_observation_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[:has_exam_plan]->(:KGNode {entityType:'ExamPlan'})
    -[:includes_lab_item]->(:KGNode {entityType:'LabItem'})
    -[:lab_item_has_subitem]->(x:KGNode {entityType:'LabSubitem'})
  RETURN count(DISTINCT x) AS lab_subitem_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'DiagnosisCriteria'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS diagnosis_criteria_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[]->(dc:KGNode {entityType:'DiagnosisCriteria'})
    -[:has_diagnostic_component]->(x:KGNode)
  RETURN count(DISTINCT x) AS diagnostic_component_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'DifferentialDiagnosis'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS differential_diagnosis_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[]->(:KGNode {entityType:'DifferentialDiagnosis'})
    -[:has_differential_rule|has_differential_point|requires_exclusion_exam|may_block_action]->(x:KGNode)
  RETURN count(DISTINCT x) AS differential_rule_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'RiskStratification'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS risk_stratification_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'TreatmentPlan'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS treatment_plan_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[:has_treatment_plan]->(:KGNode {entityType:'TreatmentPlan'})
    -[:includes_medication|treated_by_medication|recommends_action]->(x:KGNode {entityType:'Medication'})
  RETURN count(DISTINCT x) AS medication_action_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[:has_treatment_plan]->(:KGNode {entityType:'TreatmentPlan'})
    -[:includes_procedure|treated_by_procedure|recommends_action]->(x:KGNode)
  WHERE x.entityType IN ['Procedure','StandardProcedure']
  RETURN count(DISTINCT x) AS procedure_action_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[:has_treatment_plan]->(:KGNode {entityType:'TreatmentPlan'})
    -[:includes_treatment_item|has_treatment_component|recommends_action]->(x:KGNode {entityType:'TreatmentItem'})
  RETURN count(DISTINCT x) AS treatment_item_action_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'FollowUp'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS followup_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'Prognosis'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS prognosis_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[r]->(x:KGNode {entityType:'Prevention'})
  WHERE type(r) <> 'supported_by_evidence'
  RETURN count(DISTINCT x) AS prevention_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[:supported_by_evidence|derived_from]->(x:KGNode {entityType:'Evidence'})
  RETURN count(DISTINCT x) AS evidence_count
}
CALL {
  WITH d
  OPTIONAL MATCH (d)-[:based_on_guideline|uses_primary_guideline]->(x:KGNode {entityType:'Guideline'})
  RETURN count(DISTINCT x) AS guideline_count
}
CALL {
  WITH d
  OPTIONAL MATCH (rec:KGNode {entityType:'RecommendationStatement'})
  WHERE rec.disease_code=d.code AND coalesce(rec.formal_cdss_ready,false)=true
    AND coalesce(rec.cdss_use_status,'')='正式推荐'
  RETURN count(DISTINCT rec) AS formal_recommendation_count
}
RETURN d.code AS disease_code,
       d.name AS disease_name,
       CASE WHEN trim(coalesce(d.definition,''))<>'' THEN 1 ELSE definition_nodes END AS definition_count,
       symptom_count,
       sign_count,
       risk_factor_count,
       complication_count,
       exam_item_count,
       lab_item_count,
       exam_observation_count,
       lab_subitem_count,
       diagnosis_criteria_count,
       diagnostic_component_count,
       differential_diagnosis_count,
       differential_rule_count,
       risk_stratification_count,
       treatment_plan_count,
       medication_action_count,
       procedure_action_count,
       treatment_item_action_count,
       followup_count,
       prognosis_count,
       prevention_count,
       evidence_count,
       guideline_count,
       formal_recommendation_count
"""


FORMAL_RECOMMENDATION_QUERY = """
MATCH (rec:KGNode {entityType:'RecommendationStatement'})
WHERE rec.disease_code IN $codes
  AND coalesce(rec.formal_cdss_ready,false)=true
  AND coalesce(rec.cdss_use_status,'')='正式推荐'
OPTIONAL MATCH (rec)-[ar:recommends_action|blocks_action|recommends_assessment]->(action:KGNode)
OPTIONAL MATCH (rec)-[:supported_by_evidence|derived_from]->(ev:KGNode {entityType:'Evidence'})
OPTIONAL MATCH (rec)-[:uses_primary_guideline|based_on_guideline]->(gl:KGNode {entityType:'Guideline'})
WITH rec,
     collect(DISTINCT action.code) AS action_codes,
     collect(DISTINCT action.name) AS action_names,
     collect(DISTINCT action.entityType) AS action_types,
     collect(DISTINCT type(ar)) AS action_relations,
     collect(DISTINCT ev.code) AS evidence_codes,
     collect(DISTINCT gl.code) AS guideline_codes
RETURN rec.disease_code AS disease_code,
       rec.disease_name AS disease_name,
       rec.code AS rec_code,
       rec.name AS rec_name,
       rec.statement_text AS statement_text,
       action_codes,
       action_names,
       action_types,
       action_relations,
       rec.primary_evidence_code AS primary_evidence_code,
       rec.primary_guideline_code AS primary_guideline_code,
       rec.primary_source_name AS primary_source_name,
       rec.primary_source_page AS primary_source_page,
       rec.primary_evidence_summary AS primary_evidence_summary,
       rec.recommendation_class AS recommendation_class,
       rec.evidence_level AS evidence_level,
       rec.conflict_status AS conflict_status,
       rec.adjudication_reason AS adjudication_reason,
       coalesce(rec.adjudication_reason, rec.source_decision_status, rec.primary_evidence_summary, '') AS adjudication_text,
       evidence_codes,
       guideline_codes,
       CASE WHEN size(action_codes)>0
             AND any(x IN action_relations WHERE x IN ['recommends_action','blocks_action','recommends_assessment'])
            THEN true ELSE false END AS has_action,
       CASE WHEN trim(coalesce(rec.primary_evidence_code,''))<>'' AND rec.primary_evidence_code IN evidence_codes
            THEN true ELSE false END AS precise_primary_evidence,
       CASE WHEN trim(coalesce(rec.primary_guideline_code,''))<>'' AND rec.primary_guideline_code IN guideline_codes
            THEN true ELSE false END AS precise_primary_guideline
ORDER BY disease_code, rec_code
"""


INVALID_PATH_QUERY = """
MATCH (d:KGNode {entityType:'Disease'})
WHERE d.code IN $codes
OPTIONAL MATCH (d)-[:has_exam_plan]->(p1:KGNode {entityType:'ExamPlan'})
  -[bad_lab_direct:includes_lab_item]->(direct_sub:KGNode {entityType:'LabSubitem'})
OPTIONAL MATCH (d)-[:has_exam_plan]->(p2:KGNode {entityType:'ExamPlan'})
  -[bad_exam_direct]->(direct_obs:KGNode {entityType:'ExamObservation'})
OPTIONAL MATCH (d)-[:has_exam_plan]->(p3:KGNode {entityType:'ExamPlan'})
  -[:includes_lab_item]->(li:KGNode {entityType:'LabItem'})
  -[old_lab_indicator:lab_test_has_indicator]->(obs:KGNode {entityType:'ExamObservation'})
WITH d,
     collect(DISTINCT CASE WHEN direct_sub IS NULL THEN NULL ELSE {
       disease_code:d.code, disease_name:d.name, problem:'ExamPlan直接连接检验细项',
       source_code:p1.code, source_name:p1.name, relation:type(bad_lab_direct),
       target_code:direct_sub.code, target_name:direct_sub.name, target_type:direct_sub.entityType
     } END) AS a,
     collect(DISTINCT CASE WHEN direct_obs IS NULL THEN NULL ELSE {
       disease_code:d.code, disease_name:d.name, problem:'ExamPlan直接连接检查发现',
       source_code:p2.code, source_name:p2.name, relation:type(bad_exam_direct),
       target_code:direct_obs.code, target_name:direct_obs.name, target_type:direct_obs.entityType
     } END) AS b,
     collect(DISTINCT CASE WHEN obs IS NULL THEN NULL ELSE {
       disease_code:d.code, disease_name:d.name, problem:'LabItem旧关系连接检查发现',
       source_code:li.code, source_name:li.name, relation:type(old_lab_indicator),
       target_code:obs.code, target_name:obs.name, target_type:obs.entityType
     } END) AS c
WITH a+b+c AS all_items
UNWIND all_items AS item
WITH item WHERE item IS NOT NULL
RETURN item.disease_code AS disease_code,
       item.disease_name AS disease_name,
       item.problem AS problem,
       item.source_code AS source_code,
       item.source_name AS source_name,
       item.relation AS relation,
       item.target_code AS target_code,
       item.target_name AS target_name,
       item.target_type AS target_type
ORDER BY disease_name, problem, source_name, target_name
"""


POLLUTION_QUERY = """
MATCH (d:KGNode {entityType:'Disease'})
WHERE d.code IN $codes
MATCH (d)-[*1..2]->(n:KGNode)
WHERE n.entityType IN $clinical_types
  AND coalesce(n.status,'') <> 'deprecated'
  AND (
    (coalesce(n.name,'') CONTAINS '第' AND coalesce(n.name,'') CONTAINS '节')
    OR (n.entityType IN ['Symptom','Sign'] AND (coalesce(n.name,'') CONTAINS '、' OR coalesce(n.name,'') CONTAINS '或'))
    OR coalesce(n.name,'') STARTS WITH 'EXAM-'
    OR coalesce(n.name,'') STARTS WITH 'PLAN-'
    OR coalesce(n.name,'') STARTS WITH 'DXC-'
    OR coalesce(n.name,'') = coalesce(n.code,'')
  )
RETURN DISTINCT d.code AS disease_code,
       d.name AS disease_name,
       n.entityType AS entity_type,
       n.code AS node_code,
       n.name AS node_name,
       CASE
         WHEN coalesce(n.name,'') CONTAINS '第' AND coalesce(n.name,'') CONTAINS '节' THEN '章节标题污染'
         WHEN n.entityType IN ['Symptom','Sign'] AND (coalesce(n.name,'') CONTAINS '、' OR coalesce(n.name,'') CONTAINS '或') THEN '多个症状体征合并成一个实体'
         WHEN coalesce(n.name,'') STARTS WITH 'EXAM-' OR coalesce(n.name,'') STARTS WITH 'PLAN-' OR coalesce(n.name,'') STARTS WITH 'DXC-' OR coalesce(n.name,'') = coalesce(n.code,'') THEN '技术编码名称'
         ELSE '需人工核对'
       END AS problem
ORDER BY disease_name, entity_type, node_name
"""


FORMAL_ACTION_STANDARD_CLOSURE_QUERY = """
MATCH (rec:KGNode {entityType:'RecommendationStatement'})
WHERE rec.disease_code IN $codes
  AND coalesce(rec.formal_cdss_ready,false)=true
  AND coalesce(rec.cdss_use_status,'')='正式推荐'
MATCH (rec)-[:recommends_action|blocks_action|recommends_assessment]->(n:KGNode)
WHERE n.entityType IN $standard_required_types
  AND coalesce(n.status,'') <> 'deprecated'
WITH DISTINCT rec, n
WHERE trim(coalesce(n.cdss_dict_id,'')) = ''
   OR trim(coalesce(n.standard_code, n.code, '')) = ''
RETURN rec.disease_code AS disease_code,
       rec.disease_name AS disease_name,
       rec.code AS recommendation_code,
       rec.name AS recommendation_name,
       n.entityType AS entity_type,
       n.code AS node_code,
       n.name AS node_name,
       coalesce(n.cdss_use_status,'') AS cdss_use_status,
       coalesce(n.clinical_use_status,'') AS clinical_use_status,
       coalesce(n.dictionary_validation_status,'') AS dictionary_validation_status,
       coalesce(n.source_table,'') AS source_table,
       coalesce(n.cdss_order_ready,true) AS cdss_order_ready,
       coalesce(n.cdss_display_ready,false) AS cdss_display_ready,
       coalesce(n.emr_write_allowed,false) AS emr_write_allowed,
       coalesce(n.cdss_dictionary_resolution_status,'') AS cdss_dictionary_resolution_status,
       coalesce(n.cdss_dictionary_resolution_note,'') AS cdss_dictionary_resolution_note,
       coalesce(n.cdss_dictionary_required_action,'') AS cdss_dictionary_required_action
ORDER BY disease_name, entity_type, node_name
"""


KNOWLEDGE_STANDARD_TODO_QUERY = """
MATCH (d:KGNode {entityType:'Disease'})
WHERE d.code IN $codes
MATCH (d)-[*1..3]->(n:KGNode)
WHERE n.entityType IN $standard_required_types
  AND coalesce(n.status,'') <> 'deprecated'
WITH DISTINCT d, n
WHERE trim(coalesce(n.cdss_dict_id,'')) = ''
   OR trim(coalesce(n.standard_code, n.code, '')) = ''
RETURN d.code AS disease_code,
       d.name AS disease_name,
       n.entityType AS entity_type,
       n.code AS node_code,
       n.name AS node_name,
       coalesce(n.dictionary_validation_status,'') AS dictionary_validation_status,
       coalesce(n.source_table,'') AS source_table
ORDER BY disease_name, entity_type, node_name
"""


def classify_standard_status(disease: dict[str, Any]) -> tuple[str, str]:
    standards = disease.get("standard_diagnoses") or []
    if not standards:
        if disease.get("child_count", 0) > 0:
            return "非阻断", "宽口径疑似诊断可无精确出院诊断编码，但必须有分型入口。"
        return "阻断", "具体诊断/分型缺少标准诊断映射，不能回填EMR。"

    exact_items: list[str] = []
    fallback_items: list[str] = []
    disease_name = str(disease.get("disease_name") or "")

    def normalize_diag_name(value: Any) -> str:
        text = re.sub(r"\s+", "", str(value or ""))
        text = text.replace("急性", "")
        text = text.replace("，其他的", "").replace(",其他的", "")
        text = text.replace("，未特指", "").replace(",未特指", "")
        return text

    for item in standards:
        rel = item.get("mapping_type") or item.get("mapping_status") or item.get("mapping_scope") or ""
        rel_text = str(rel)
        valid = is_truthy(item.get("valid_flag")) or str(item.get("status") or "") in {"有效", "active"}
        emr_allowed = item.get("emr_write_allowed")
        standard_name = str(item.get("name") or "")
        name_exact = normalize_diag_name(disease_name) == normalize_diag_name(standard_name)
        if emr_allowed is True or rel_text in {"精确", "exact", "标准诊断", "一对一"} or name_exact:
            exact_items.append(f"{item.get('name')}({item.get('code')})")
        elif valid:
            fallback_items.append(f"{item.get('name')}({item.get('code')})")

    if exact_items:
        return "通过", "存在精确标准诊断：" + "；".join(exact_items)
    if fallback_items:
        return "非阻断", "只有上位/回退标准诊断：" + "；".join(fallback_items) + "；可知识展示，不可自动写出院诊断。"
    return "阻断", "标准诊断节点存在，但不是有效可用映射。"


def count_dimension_gaps(disease: dict[str, Any], counts: dict[str, Any]) -> tuple[list[str], list[str]]:
    hard_gaps: list[str] = []
    warnings: list[str] = []
    has_children = int(disease.get("child_count") or 0) > 0

    if int(counts.get("definition_count") or 0) == 0:
        hard_gaps.append("缺疾病定义")
    if int(counts.get("diagnosis_criteria_count") or 0) > 0 and int(counts.get("diagnostic_component_count") or 0) == 0:
        hard_gaps.append("诊断标准无明细")
    if int(counts.get("differential_diagnosis_count") or 0) > 0 and int(counts.get("differential_rule_count") or 0) == 0:
        hard_gaps.append("鉴别诊断无规则")
    if int(counts.get("treatment_plan_count") or 0) > 0:
        action_total = sum(
            int(counts.get(key) or 0)
            for key in ["medication_action_count", "procedure_action_count", "treatment_item_action_count", "followup_count"]
        )
        if action_total == 0:
            hard_gaps.append("治疗方案无下游动作")

    if not has_children:
        if int(counts.get("symptom_count") or 0) == 0 and int(counts.get("sign_count") or 0) == 0:
            warnings.append("分型缺临床表现")
        if int(counts.get("exam_item_count") or 0) == 0 and int(counts.get("lab_item_count") or 0) == 0:
            warnings.append("分型缺检查/检验项目")
    else:
        if int(counts.get("symptom_count") or 0) == 0 and int(counts.get("sign_count") or 0) == 0:
            warnings.append("疑似诊断节点缺基础临床表现")
        if int(counts.get("child_count") or 0) == 0:
            warnings.append("疑似诊断节点缺分型入口")

    if int(counts.get("formal_recommendation_count") or 0) == 0:
        warnings.append("暂无正式CDSS推荐陈述；可展示知识，不能进入正式推荐区")

    return hard_gaps, warnings


def build_coverage_rows(diseases: list[dict[str, Any]], counts_by_code: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in diseases:
        code = d["disease_code"]
        counts = counts_by_code.get(code, {})
        status, note = classify_standard_status(d)
        hard_gaps, warnings = count_dimension_gaps(d, {**counts, "child_count": d.get("child_count", 0)})
        row = {
            "疾病编码": code,
            "疾病名称": d.get("disease_name", ""),
            "诊断角色": d.get("diagnostic_role", ""),
            "父级疾病": "；".join(str(x) for x in d.get("parent_codes", []) if x),
            "下级分型数": d.get("child_count", 0),
            "标准诊断状态": status,
            "标准诊断说明": note,
            "定义": counts.get("definition_count", 0),
            "症状": counts.get("symptom_count", 0),
            "体征": counts.get("sign_count", 0),
            "危险因素": counts.get("risk_factor_count", 0),
            "并发症": counts.get("complication_count", 0),
            "检查项目": counts.get("exam_item_count", 0),
            "检验项目": counts.get("lab_item_count", 0),
            "检查发现": counts.get("exam_observation_count", 0),
            "检验细项": counts.get("lab_subitem_count", 0),
            "诊断标准": counts.get("diagnosis_criteria_count", 0),
            "诊断明细": counts.get("diagnostic_component_count", 0),
            "鉴别诊断": counts.get("differential_diagnosis_count", 0),
            "鉴别规则": counts.get("differential_rule_count", 0),
            "风险分层": counts.get("risk_stratification_count", 0),
            "治疗方案": counts.get("treatment_plan_count", 0),
            "药物动作": counts.get("medication_action_count", 0),
            "手术/操作动作": counts.get("procedure_action_count", 0),
            "其他治疗动作": counts.get("treatment_item_action_count", 0),
            "随访": counts.get("followup_count", 0),
            "预后": counts.get("prognosis_count", 0),
            "预防": counts.get("prevention_count", 0),
            "证据": counts.get("evidence_count", 0),
            "指南": counts.get("guideline_count", 0),
            "正式推荐": counts.get("formal_recommendation_count", 0),
            "硬缺口": "；".join(hard_gaps),
            "提醒": "；".join(warnings),
        }
        out.append(row)
    return out


def evaluate_formal_rows(rows_: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows_:
        gaps: list[str] = []
        if not r.get("has_action"):
            gaps.append("缺推荐动作/阻断动作/评估目标")
        if not r.get("precise_primary_evidence"):
            gaps.append("缺精确主证据")
        if not r.get("precise_primary_guideline"):
            gaps.append("缺精确主指南")
        for key, label in [
            ("recommendation_class", "缺推荐等级"),
            ("evidence_level", "缺证据等级"),
            ("conflict_status", "缺冲突状态"),
        ]:
            if not str(r.get(key) or "").strip():
                gaps.append(label)
        if not str(r.get("adjudication_text") or "").strip():
            gaps.append("缺裁决理由")
        out.append(
            {
                "疾病编码": r.get("disease_code", ""),
                "疾病名称": r.get("disease_name", ""),
                "推荐编码": r.get("rec_code", ""),
                "推荐名称": r.get("rec_name", ""),
                "动作名称": list_codes(r.get("action_names")),
                "动作类型": "；".join(str(x) for x in (r.get("action_types") or []) if x),
                "主证据编码": r.get("primary_evidence_code", ""),
                "主指南编码": r.get("primary_guideline_code", ""),
                "主来源": r.get("primary_source_name", ""),
                "页码": r.get("primary_source_page", ""),
                "推荐等级": r.get("recommendation_class", ""),
                "证据等级": r.get("evidence_level", ""),
                "冲突状态": r.get("conflict_status", ""),
                "裁决理由": r.get("adjudication_reason", ""),
                "裁决文本": r.get("adjudication_text", ""),
                "链路缺口": "；".join(gaps),
            }
        )
    return out


def build_gap_rows(
    coverage_rows: list[dict[str, Any]],
    formal_rows: list[dict[str, Any]],
    invalid_rows: list[dict[str, Any]],
    pollution_rows: list[dict[str, Any]],
    standard_gap_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for row in coverage_rows:
        if row["标准诊断状态"] == "阻断":
            gaps.append(
                {
                    "问题类别": "标准诊断阻断",
                    "疾病编码": row["疾病编码"],
                    "疾病名称": row["疾病名称"],
                    "对象类型": "Disease",
                    "对象名称": row["疾病名称"],
                    "问题说明": row["标准诊断说明"],
                    "处理建议": "补充CDSS标准诊断映射后才允许回填EMR。",
                }
            )
        if row["硬缺口"]:
            gaps.append(
                {
                    "问题类别": "知识结构阻断",
                    "疾病编码": row["疾病编码"],
                    "疾病名称": row["疾病名称"],
                    "对象类型": "Disease",
                    "对象名称": row["疾病名称"],
                    "问题说明": row["硬缺口"],
                    "处理建议": "回到教材/指南原文补实体和关系，不能用标题凑数。",
                }
            )
    for row in formal_rows:
        if row["链路缺口"]:
            gaps.append(
                {
                    "问题类别": "正式推荐链路阻断",
                    "疾病编码": row["疾病编码"],
                    "疾病名称": row["疾病名称"],
                    "对象类型": "RecommendationStatement",
                    "对象名称": row["推荐名称"],
                    "问题说明": row["链路缺口"],
                    "处理建议": "补推荐动作、主证据、主指南、等级和裁决字段。",
                }
            )
    for row in invalid_rows:
        gaps.append(
            {
                "问题类别": "检查检验路径结构错误",
                "疾病编码": row.get("disease_code", ""),
                "疾病名称": row.get("disease_name", ""),
                "对象类型": row.get("target_type", ""),
                "对象名称": row.get("target_name", ""),
                "问题说明": row.get("problem", ""),
                "处理建议": "改为 检查方案→检查/检验项目→检查发现/检验细项，不保留旧直连。",
            }
        )
    for row in pollution_rows:
        gaps.append(
            {
                "问题类别": "实体命名污染",
                "疾病编码": row.get("disease_code", ""),
                "疾病名称": row.get("disease_name", ""),
                "对象类型": row.get("entity_type", ""),
                "对象名称": row.get("node_name", ""),
                "问题说明": row.get("problem", ""),
                "处理建议": "拆分为标准临床实体；章节标题、组合短语不得作为实体名称。",
            }
        )
    for row in standard_gap_rows:
        gaps.append(
            {
                "问题类别": "正式推荐动作标准字典未闭环",
                "疾病编码": row.get("disease_code", ""),
                "疾病名称": row.get("disease_name", ""),
                "对象类型": row.get("entity_type", ""),
                "对象名称": row.get("node_name", ""),
                "问题说明": f"正式推荐动作缺 cdss_dict_id 或标准编码；当前字典状态：{row.get('dictionary_validation_status','')}",
                "处理建议": "优先匹配CDSS标准字典；缺失时进入待注册清单，不能伪造字典ID。",
            }
        )
    return gaps


def split_standard_action_gap_rows(
    standard_gap_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """把真正阻断的字典缺口，与已分类的“非直接医嘱动作”分开。

    已分类动作的原则：
    - 可用于图谱知识展示；
    - 不允许直接写医嘱/回填EMR；
    - 后续要么下钻到具体标准项目，要么进入新增字典/映射评审。
    """
    blocking_rows: list[dict[str, Any]] = []
    classified_rows: list[dict[str, Any]] = []
    non_blocking_statuses = {
        "non_orderable_category",
        "knowledge_display_only",
        "knowledge_only_non_orderable",
        "not_orderable",
        "needs_specific_exam",
        "needs_lab_subitem_drilldown",
        "medication_class_not_orderable",
        "needs_disease_scenario_split",
        "needs_drug_form_route",
    }
    for row in standard_gap_rows:
        status = str(row.get("cdss_dictionary_resolution_status") or "").strip()
        order_ready = is_truthy(row.get("cdss_order_ready"))
        if status in non_blocking_statuses and not order_ready:
            item = dict(row)
            item["处置结论"] = "已分类为非直接医嘱动作：可展示，不可直接下医嘱/回填EMR"
            classified_rows.append(item)
        else:
            blocking_rows.append(row)
    return blocking_rows, classified_rows


def write_report(
    path: Path,
    summary: dict[str, Any],
    coverage_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
) -> None:
    top_gaps = gap_rows[:20]
    lines = [
        "# P5 AMI与心肌病样板终验报告",
        "",
        f"- 生成时间：{summary['generated_at']}",
        "- 执行方式：只读审计，未写 Neo4j，未写 Oracle。",
        "- 样板范围：急性心肌梗死及分型、心肌病及分型。",
        "",
        "## 1. 总体结论",
        "",
        f"- 疾病节点数：{summary['disease_count']}",
        f"- 正式推荐数：{summary['formal_recommendation_count']}",
        f"- 阻断缺口数：{summary['blocking_gap_count']}",
        f"- 非阻断提醒数：{summary['warning_count']}",
        f"- 标准诊断非阻断回退数：{summary['fallback_standard_diagnosis_count']}",
        "",
        "说明：非阻断回退指“图谱可展示、可辅助分型提示，但不能自动写入电子病历诊断”的现代疾病分型；这类不能伪造 CDSS 标准诊断。",
        "",
        "## 2. 疾病维度摘要",
        "",
        "| 疾病 | 诊断角色 | 分型数 | 标准诊断状态 | 关键缺口 | 提醒 |",
        "|---|---:|---:|---|---|---|",
    ]
    for row in coverage_rows:
        lines.append(
            "| {name} | {role} | {children} | {status} | {gap} | {warn} |".format(
                name=row["疾病名称"],
                role=row["诊断角色"] or "-",
                children=row["下级分型数"],
                status=row["标准诊断状态"],
                gap=row["硬缺口"] or "-",
                warn=row["提醒"] or "-",
            )
        )
    lines.extend(["", "## 3. 当前缺口明细（前20条）", ""])
    if top_gaps:
        lines.extend(["| 类别 | 疾病 | 对象 | 问题 | 建议 |", "|---|---|---|---|---|"])
        for row in top_gaps:
            lines.append(
                "| {cat} | {dis} | {obj} | {problem} | {fix} |".format(
                    cat=row["问题类别"],
                    dis=row["疾病名称"],
                    obj=row["对象名称"],
                    problem=row["问题说明"],
                    fix=row["处理建议"],
                )
            )
    else:
        lines.append("无阻断缺口。")
    lines.extend(
        [
            "",
            "## 4. P5判定口径",
            "",
            "1. 疑似诊断节点可以有自身知识和分型入口，但不能代替具体分型出院诊断。",
        "2. 具体分型诊断必须优先绑定有效 CDSS 标准诊断；没有一对一标准编码时，只允许知识展示和辅助提示。",
            "3. 检查检验必须走标准路径：辅助检查方案连接检查/检验项目，项目再连接检查发现或检验细项。",
            "4. 正式 CDSS 推荐必须走推荐陈述、推荐动作、主证据、主指南、推荐等级、证据等级和裁决理由，不从疾病证据池直接推断。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="P5 AMI与心肌病样板终验，只读审计。")
    parser.add_argument("--connection-file", default=str(ROOT / "图谱数据库链接.txt"))
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "项目管理中心_project_management" / "2026年8月P5样板终验" / "02_当前标准专项终验_20260803"),
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = read_db_config(Path(args.connection_file))
    driver = GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))

    with driver.session() as sess:
        all_diseases: list[dict[str, Any]] = []
        group_index: dict[str, str] = {}
        for group_name, roots in ROOT_DISEASES.items():
            group_rows = rows(sess.run(SCOPED_DISEASE_QUERY, root_codes=roots))
            for item in group_rows:
                item["样板分组"] = group_name
                group_index[item["disease_code"]] = group_name
            all_diseases.extend(group_rows)

        seen: set[str] = set()
        diseases: list[dict[str, Any]] = []
        for item in all_diseases:
            code = str(item.get("disease_code") or "")
            if code and code not in seen:
                seen.add(code)
                diseases.append(item)

        disease_codes = [d["disease_code"] for d in diseases]
        counts_by_code: dict[str, dict[str, Any]] = {}
        for code in disease_codes:
            result = rows(sess.run(DIMENSION_COUNT_QUERY, code=code))
            counts_by_code[code] = result[0] if result else {}

        formal_raw = rows(sess.run(FORMAL_RECOMMENDATION_QUERY, codes=disease_codes))
        invalid_path_rows = rows(sess.run(INVALID_PATH_QUERY, codes=disease_codes))
        pollution_rows = rows(
            sess.run(POLLUTION_QUERY, codes=disease_codes, clinical_types=sorted(CLINICAL_ENTITY_TYPES))
        )
        standard_gap_rows = rows(
            sess.run(
                FORMAL_ACTION_STANDARD_CLOSURE_QUERY,
                codes=disease_codes,
                standard_required_types=sorted(FORMAL_ACTION_STANDARD_TYPES),
            )
        )
        knowledge_standard_todo_rows = rows(
            sess.run(
                KNOWLEDGE_STANDARD_TODO_QUERY,
                codes=disease_codes,
                standard_required_types=sorted(STANDARD_REQUIRED_TYPES),
            )
        )

    driver.close()

    standard_gap_rows, classified_non_orderable_action_rows = split_standard_action_gap_rows(standard_gap_rows)
    coverage_rows = build_coverage_rows(diseases, counts_by_code)
    formal_rows = evaluate_formal_rows(formal_raw)
    gap_rows = build_gap_rows(coverage_rows, formal_rows, invalid_path_rows, pollution_rows, standard_gap_rows)

    blocking_gap_count = sum(1 for row in gap_rows if "非阻断" not in row["问题类别"])
    warning_count = sum(1 for row in coverage_rows if row["提醒"])
    fallback_count = sum(1 for row in coverage_rows if row["标准诊断状态"] == "非阻断")
    classified_non_orderable_action_unique_count = len({
        str(row.get("node_code") or "").strip()
        for row in classified_non_orderable_action_rows
        if str(row.get("node_code") or "").strip()
    })
    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "read_only",
        "scope": ROOT_DISEASES,
        "disease_count": len(coverage_rows),
        "formal_recommendation_count": len(formal_rows),
        "blocking_gap_count": blocking_gap_count,
        "warning_count": warning_count,
        "fallback_standard_diagnosis_count": fallback_count,
        "invalid_path_count": len(invalid_path_rows),
        "pollution_count": len(pollution_rows),
        "standard_dictionary_gap_count": len(standard_gap_rows),
        "classified_non_orderable_action_count": len(classified_non_orderable_action_rows),
        "classified_non_orderable_action_unique_count": classified_non_orderable_action_unique_count,
        "output_dir": str(out_dir),
    }

    write_json(out_dir / "00_P5样板终验_summary.json", summary)
    write_json(out_dir / "00_P5样板终验_raw.json", {
        "diseases": diseases,
        "counts_by_code": counts_by_code,
        "formal_recommendations": formal_raw,
        "invalid_paths": invalid_path_rows,
        "pollution": pollution_rows,
        "formal_action_standard_dictionary_gaps": standard_gap_rows,
        "classified_non_orderable_actions": classified_non_orderable_action_rows,
        "knowledge_standard_dictionary_todo": knowledge_standard_todo_rows,
    })
    write_csv(
        out_dir / "01_疾病维度覆盖明细.csv",
        coverage_rows,
        [
            "疾病编码",
            "疾病名称",
            "诊断角色",
            "父级疾病",
            "下级分型数",
            "标准诊断状态",
            "标准诊断说明",
            "定义",
            "症状",
            "体征",
            "危险因素",
            "并发症",
            "检查项目",
            "检验项目",
            "检查发现",
            "检验细项",
            "诊断标准",
            "诊断明细",
            "鉴别诊断",
            "鉴别规则",
            "风险分层",
            "治疗方案",
            "药物动作",
            "手术/操作动作",
            "其他治疗动作",
            "随访",
            "预后",
            "预防",
            "证据",
            "指南",
            "正式推荐",
            "硬缺口",
            "提醒",
        ],
    )
    write_csv(
        out_dir / "02_正式推荐链路明细.csv",
        formal_rows,
        [
            "疾病编码",
            "疾病名称",
            "推荐编码",
            "推荐名称",
            "动作名称",
            "动作类型",
            "主证据编码",
            "主指南编码",
            "主来源",
            "页码",
            "推荐等级",
            "证据等级",
            "冲突状态",
            "裁决理由",
            "裁决文本",
            "链路缺口",
        ],
    )
    write_csv(
        out_dir / "03_样板缺口清单.csv",
        gap_rows,
        ["问题类别", "疾病编码", "疾病名称", "对象类型", "对象名称", "问题说明", "处理建议"],
    )
    write_csv(
        out_dir / "04_检查检验旧路径明细.csv",
        invalid_path_rows,
        [
            "disease_code",
            "disease_name",
            "problem",
            "source_code",
            "source_name",
            "relation",
            "target_code",
            "target_name",
            "target_type",
        ],
    )
    write_csv(
        out_dir / "05_实体命名污染明细.csv",
        pollution_rows,
        ["disease_code", "disease_name", "entity_type", "node_code", "node_name", "problem"],
    )
    write_csv(
        out_dir / "06_标准字典缺口明细.csv",
        standard_gap_rows,
        [
            "disease_code",
            "disease_name",
            "recommendation_code",
            "recommendation_name",
            "entity_type",
            "node_code",
            "node_name",
            "cdss_use_status",
            "clinical_use_status",
            "dictionary_validation_status",
            "source_table",
            "cdss_order_ready",
            "cdss_display_ready",
            "emr_write_allowed",
            "cdss_dictionary_resolution_status",
            "cdss_dictionary_resolution_note",
            "cdss_dictionary_required_action",
        ],
    )
    write_csv(
        out_dir / "07_知识实体待字典融合明细.csv",
        knowledge_standard_todo_rows,
        [
            "disease_code",
            "disease_name",
            "entity_type",
            "node_code",
            "node_name",
            "dictionary_validation_status",
            "source_table",
        ],
    )
    write_report(out_dir / "P5_AMI与心肌病样板终验报告.md", summary, coverage_rows, gap_rows)

    write_csv(
        out_dir / "08_已分类非直接医嘱动作明细.csv",
        classified_non_orderable_action_rows,
        [
            "disease_code",
            "disease_name",
            "recommendation_code",
            "recommendation_name",
            "entity_type",
            "node_code",
            "node_name",
            "cdss_use_status",
            "clinical_use_status",
            "dictionary_validation_status",
            "source_table",
            "cdss_order_ready",
            "cdss_display_ready",
            "emr_write_allowed",
            "cdss_dictionary_resolution_status",
            "cdss_dictionary_resolution_note",
            "cdss_dictionary_required_action",
            "处置结论",
        ],
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
