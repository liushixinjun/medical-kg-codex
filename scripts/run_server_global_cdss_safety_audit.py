from __future__ import annotations

import base64
import csv
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "心血管内科文献集合" / "00_全局质量体检_global_quality_audit"
TODAY = "20260709"


def post(statement: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    http_root = os.environ.get("NEO4J_HTTP", "http://192.168.3.27:7474").rstrip("/")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("缺少 NEO4J_PASSWORD 环境变量，禁止在脚本中硬编码数据库密码。")
    url = f"{http_root}/db/neo4j/tx/commit"
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    payload = json.dumps(
        {"statements": [{"statement": statement, "parameters": parameters or {}}]},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Basic " + token},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False))
    return result


def rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    res = result["results"][0]
    cols = res["columns"]
    return [dict(zip(cols, item["row"])) for item in res["data"]]


def one_value(statement: str) -> int:
    r = rows(post(statement))
    if not r:
        return 0
    return int(next(iter(r[0].values())) or 0)


QUERIES: dict[str, str] = {
    "overview": """
        MATCH (n)
        WITH count(n) AS all_node_count
        MATCH ()-[r]->()
        WITH all_node_count, count(r) AS all_relation_count
        MATCH (k:KGNode)
        WITH all_node_count, all_relation_count, count(k) AS kg_node_count
        MATCH (:KGNode)-[kr]->(:KGNode)
        RETURN all_node_count, all_relation_count, kg_node_count, count(kr) AS kg_relation_count
    """,
    "entity_type_distribution": """
        MATCH (n:KGNode)
        RETURN n.entityType AS entityType, count(n) AS count
        ORDER BY count DESC, entityType
    """,
    "non_kgnode_nodes": """
        MATCH (n)
        WHERE NOT n:KGNode
        OPTIONAL MATCH (a)-[rin]->(n)
        OPTIONAL MATCH (n)-[rout]->(b)
        RETURN labels(n) AS labels, n.code AS code, n.name AS name, n.entityType AS entityType,
               count(DISTINCT rin) AS in_degree, count(DISTINCT rout) AS out_degree
        ORDER BY in_degree + out_degree DESC, name
        LIMIT 200
    """,
    "relations_touching_non_kgnode": """
        MATCH (a)-[r]->(b)
        WHERE NOT a:KGNode OR NOT b:KGNode
        RETURN type(r) AS relType, count(r) AS count
        ORDER BY count DESC
    """,
    "label_metadata_mismatch": """
        MATCH (n:KGNode)
        WHERE n.primary_label IS NULL OR n.type_label IS NULL OR n.canonical_labels IS NULL
           OR n.primary_label <> 'KGNode' OR n.type_label <> n.entityType
        RETURN n.entityType AS entityType, count(n) AS count
        ORDER BY count DESC
    """,
    "raw_label_order_differs": """
        MATCH (n:KGNode)
        WHERE labels(n) <> ['KGNode', n.entityType]
        RETURN labels(n) AS labels, n.entityType AS entityType, count(n) AS count
        ORDER BY count DESC
    """,
    "duplicate_type_name": """
        MATCH (n:KGNode)
        WITH n.entityType AS entityType, n.name AS name, count(n) AS count, collect(n.code)[0..20] AS codes
        WHERE name IS NOT NULL AND trim(name) <> '' AND count > 1
        RETURN entityType, name, count, codes
        ORDER BY count DESC, entityType, name
        LIMIT 300
    """,
    "disease_definition_empty": """
        MATCH (d:KGNode {entityType:'Disease'})
        WHERE coalesce(d.definition,'') = ''
        RETURN d.code AS code, d.name AS name, d.disease_category AS disease_category
        ORDER BY d.code
    """,
    "conditional_definition_diseases": """
        MATCH (d:KGNode {entityType:'Disease'})
        WHERE d.definition_confidence = 'conditional'
        OPTIONAL MATCH (d)-[r]-(:KGNode)
        WITH d, sum(CASE WHEN coalesce(r.formal_cdss_ready,false)=true THEN 1 ELSE 0 END) AS formal_ready_rel_count
        RETURN d.code AS code, d.name AS name, d.definition_source_name AS source_name,
               d.external_authority_review_status AS review_status,
               formal_ready_rel_count
        ORDER BY d.code
    """,
    "conditional_definition_used_in_formal_ready_edges": """
        MATCH (d:KGNode {entityType:'Disease'})-[r]-(:KGNode)
        WHERE d.definition_confidence = 'conditional' AND coalesce(r.formal_cdss_ready,false)=true
        RETURN d.code AS code, d.name AS name, type(r) AS relType, count(r) AS count
        ORDER BY count DESC, code
    """,
    "diagnosis_criteria_without_components": """
        MATCH (d:KGNode {entityType:'Disease'})-[:has_diagnostic_criteria]->(c:KGNode {entityType:'DiagnosisCriteria'})
        WHERE NOT (c)-[:has_diagnostic_component]->(:KGNode)
        RETURN d.code AS disease_code, d.name AS disease_name, c.code AS criteria_code, c.name AS criteria_name
        ORDER BY d.code, c.name
        LIMIT 500
    """,
    "differential_diagnosis_without_details": """
        MATCH (d:KGNode {entityType:'Disease'})-[:has_differential_diagnosis]->(x:KGNode {entityType:'DifferentialDiagnosis'})
        WHERE NOT (x)-[:has_differential_point|requires_exclusion_exam]->(:KGNode)
        RETURN d.code AS disease_code, d.name AS disease_name, x.code AS differential_code, x.name AS differential_name
        ORDER BY d.code, x.name
        LIMIT 500
    """,
    "treatment_plan_without_downstream_action": """
        MATCH (d:KGNode {entityType:'Disease'})-[:has_treatment_plan]->(p:KGNode {entityType:'TreatmentPlan'})
        WHERE NOT (p)-[:includes_medication|includes_procedure|has_recommended_action|recommends_action|treated_by_medication|treated_by_procedure]->(:KGNode)
        RETURN d.code AS disease_code, d.name AS disease_name, p.code AS plan_code, p.name AS plan_name
        ORDER BY d.code, p.name
        LIMIT 500
    """,
    "medication_class_without_specific": """
        MATCH (m:KGNode {entityType:'Medication'})
        WHERE (
          m.name CONTAINS '药物' OR m.name CONTAINS '制剂' OR m.name CONTAINS '抑制剂' OR
          m.name CONTAINS '阻滞剂' OR m.name CONTAINS '拮抗剂' OR m.name CONTAINS '类'
        )
        AND NOT (m)-[:has_specific_medication]->(:KGNode {entityType:'Medication'})
        RETURN m.code AS code, m.name AS name, m.aliases AS aliases
        ORDER BY m.name
        LIMIT 500
    """,
    "recommendation_like_nodes_without_evidence": """
        MATCH (n:KGNode)
        WHERE n.entityType IN ['RecommendationStatement','ClinicalRule','ThresholdRule','TreatmentPlan','ClinicalPathway','PathwayStage']
          AND NOT (n)-[:supported_by_evidence]->(:KGNode {entityType:'Evidence'})
          AND NOT (n)<-[:supported_by_evidence]-(:KGNode {entityType:'Evidence'})
          AND NOT (n)-[:based_on_guideline]->(:KGNode {entityType:'Guideline'})
          AND NOT (n)<-[:based_on_guideline]-(:KGNode {entityType:'Guideline'})
        RETURN n.entityType AS entityType, n.code AS code, n.name AS name
        ORDER BY entityType, name
        LIMIT 1000
    """,
    "recommendation_relationships_missing_core_fields": """
        MATCH (s:KGNode)-[r]->(t:KGNode)
        WHERE type(r) IN ['recommends_action','has_recommended_action','treated_by_medication','treated_by_procedure','includes_medication','includes_procedure']
          AND (
            coalesce(r.recommendation_strength,'') = '' AND
            coalesce(r.recommendation_class,'') = '' AND
            coalesce(r.recommendation_grade,'') = '' AND
            coalesce(r.evidence_level,'') = '' AND
            coalesce(r.source_evidence_id,'') = ''
          )
        RETURN type(r) AS relType, s.code AS source_code, s.name AS source_name,
               t.code AS target_code, t.name AS target_name
        ORDER BY relType, source_code
        LIMIT 1000
    """,
    "evidence_without_guideline": """
        MATCH (e:KGNode {entityType:'Evidence'})
        WHERE NOT (:KGNode {entityType:'Guideline'})-[:guideline_has_evidence]->(e)
          AND coalesce(e.guideline_id,'') = ''
          AND coalesce(e.source_guideline,'') = ''
          AND coalesce(e.source_name,'') = ''
        RETURN e.code AS code, e.name AS name
        LIMIT 1000
    """,
    "technical_name_nodes": """
        MATCH (n:KGNode)
        WHERE n.entityType <> 'Evidence'
          AND (
            n.name = n.code OR n.display_name = n.code OR n.preferred_name = n.code
            OR n.name STARTS WITH 'EXAM-' OR n.name STARTS WITH 'PLAN-' OR n.name STARTS WITH 'DXC-'
          )
        RETURN n.entityType AS entityType, n.code AS code, n.name AS name, n.display_name AS display_name
        ORDER BY entityType, code
        LIMIT 500
    """,
}


COUNT_QUERIES: dict[str, str] = {
    "entity_type_distribution_count": "MATCH (n:KGNode) RETURN count(DISTINCT n.entityType) AS count",
    "non_kgnode_nodes_count": "MATCH (n) WHERE NOT n:KGNode RETURN count(n) AS count",
    "relations_touching_non_kgnode_count": "MATCH (a)-[r]->(b) WHERE NOT a:KGNode OR NOT b:KGNode RETURN count(r) AS count",
    "label_metadata_mismatch_count": """
        MATCH (n:KGNode)
        WHERE n.primary_label IS NULL OR n.type_label IS NULL OR n.canonical_labels IS NULL
           OR n.primary_label <> 'KGNode' OR n.type_label <> n.entityType
        RETURN count(n) AS count
    """,
    "raw_label_order_differs_count": "MATCH (n:KGNode) WHERE labels(n) <> ['KGNode', n.entityType] RETURN count(n) AS count",
    "duplicate_type_name_count": """
        MATCH (n:KGNode)
        WITH n.entityType AS entityType, n.name AS name, count(n) AS c
        WHERE name IS NOT NULL AND trim(name) <> '' AND c > 1
        RETURN count(*) AS count
    """,
    "disease_definition_empty_count": "MATCH (d:KGNode {entityType:'Disease'}) WHERE coalesce(d.definition,'') = '' RETURN count(d) AS count",
    "conditional_definition_diseases_count": "MATCH (d:KGNode {entityType:'Disease'}) WHERE d.definition_confidence = 'conditional' RETURN count(d) AS count",
    "conditional_definition_used_in_formal_ready_edges_count": """
        MATCH (d:KGNode {entityType:'Disease'})-[r]-(:KGNode)
        WHERE d.definition_confidence = 'conditional' AND coalesce(r.formal_cdss_ready,false)=true
        RETURN count(r) AS count
    """,
    "diagnosis_criteria_without_components_count": """
        MATCH (d:KGNode {entityType:'Disease'})-[:has_diagnostic_criteria]->(c:KGNode {entityType:'DiagnosisCriteria'})
        WHERE NOT (c)-[:has_diagnostic_component]->(:KGNode)
        RETURN count(DISTINCT c) AS count
    """,
    "differential_diagnosis_without_details_count": """
        MATCH (d:KGNode {entityType:'Disease'})-[:has_differential_diagnosis]->(x:KGNode {entityType:'DifferentialDiagnosis'})
        WHERE NOT (x)-[:has_differential_point|requires_exclusion_exam]->(:KGNode)
        RETURN count(DISTINCT x) AS count
    """,
    "treatment_plan_without_downstream_action_count": """
        MATCH (d:KGNode {entityType:'Disease'})-[:has_treatment_plan]->(p:KGNode {entityType:'TreatmentPlan'})
        WHERE NOT (p)-[:includes_medication|includes_procedure|has_recommended_action|recommends_action|treated_by_medication|treated_by_procedure]->(:KGNode)
        RETURN count(DISTINCT p) AS count
    """,
    "medication_class_without_specific_count": """
        MATCH (m:KGNode {entityType:'Medication'})
        WHERE (
          m.name CONTAINS '药物' OR m.name CONTAINS '制剂' OR m.name CONTAINS '抑制剂' OR
          m.name CONTAINS '阻滞剂' OR m.name CONTAINS '拮抗剂' OR m.name CONTAINS '类'
        )
        AND NOT (m)-[:has_specific_medication]->(:KGNode {entityType:'Medication'})
        RETURN count(DISTINCT m) AS count
    """,
    "recommendation_like_nodes_without_evidence_count": """
        MATCH (n:KGNode)
        WHERE n.entityType IN ['RecommendationStatement','ClinicalRule','ThresholdRule','TreatmentPlan','ClinicalPathway','PathwayStage']
          AND NOT (n)-[:supported_by_evidence]->(:KGNode {entityType:'Evidence'})
          AND NOT (n)<-[:supported_by_evidence]-(:KGNode {entityType:'Evidence'})
          AND NOT (n)-[:based_on_guideline]->(:KGNode {entityType:'Guideline'})
          AND NOT (n)<-[:based_on_guideline]-(:KGNode {entityType:'Guideline'})
        RETURN count(n) AS count
    """,
    "recommendation_relationships_missing_core_fields_count": """
        MATCH (s:KGNode)-[r]->(t:KGNode)
        WHERE type(r) IN ['recommends_action','has_recommended_action','treated_by_medication','treated_by_procedure','includes_medication','includes_procedure']
          AND (
            coalesce(r.recommendation_strength,'') = '' AND
            coalesce(r.recommendation_class,'') = '' AND
            coalesce(r.recommendation_grade,'') = '' AND
            coalesce(r.evidence_level,'') = '' AND
            coalesce(r.source_evidence_id,'') = ''
          )
        RETURN count(r) AS count
    """,
    "evidence_without_guideline_count": """
        MATCH (e:KGNode {entityType:'Evidence'})
        WHERE NOT (:KGNode {entityType:'Guideline'})-[:guideline_has_evidence]->(e)
          AND coalesce(e.guideline_id,'') = ''
          AND coalesce(e.source_guideline,'') = ''
          AND coalesce(e.source_name,'') = ''
        RETURN count(e) AS count
    """,
    "technical_name_nodes_count": """
        MATCH (n:KGNode)
        WHERE n.entityType <> 'Evidence'
          AND (
            n.name = n.code OR n.display_name = n.code OR n.preferred_name = n.code
            OR n.name STARTS WITH 'EXAM-' OR n.name STARTS WITH 'PLAN-' OR n.name STARTS WITH 'DXC-'
          )
        RETURN count(n) AS count
    """,
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_rows: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}

    for name, query in QUERIES.items():
        qrows = rows(post(query))
        all_rows[name] = qrows
    for name, query in COUNT_QUERIES.items():
        counts[name] = int(rows(post(query))[0].get("count") or 0)

    overview = all_rows["overview"][0] if all_rows["overview"] else {}
    blocking_keys = [
        "non_kgnode_nodes_count",
        "relations_touching_non_kgnode_count",
        "duplicate_type_name_count",
        "disease_definition_empty_count",
        "conditional_definition_used_in_formal_ready_edges_count",
        "diagnosis_criteria_without_components_count",
        "differential_diagnosis_without_details_count",
        "treatment_plan_without_downstream_action_count",
        "medication_class_without_specific_count",
        "recommendation_relationships_missing_core_fields_count",
        "technical_name_nodes_count",
    ]
    warning_keys = [
        "raw_label_order_differs_count",
        "recommendation_like_nodes_without_evidence_count",
        "evidence_without_guideline_count",
        "label_metadata_mismatch_count",
    ]
    blocking_total = sum(int(counts.get(k, 0)) for k in blocking_keys)
    warning_total = sum(int(counts.get(k, 0)) for k in warning_keys)

    conclusion = {
        "knowledge_display": "可用" if counts.get("non_kgnode_nodes_count", 0) == 0 and counts.get("technical_name_nodes_count", 0) == 0 else "受限",
        "specialty_pathway_engine": "可继续样板验证" if blocking_total == 0 else "需先修复阻断项",
        "formal_cdss_recommendation": "不可直接上线" if blocking_total > 0 or warning_total > 0 else "可进入临床灰度验证",
    }
    summary = {
        "generated_at": generated_at,
        "overview": overview,
        "counts": counts,
        "blocking_keys": {k: counts.get(k, 0) for k in blocking_keys},
        "warning_keys": {k: counts.get(k, 0) for k in warning_keys},
        "blocking_total": blocking_total,
        "warning_total": warning_total,
        "conclusion": conclusion,
    }

    summary_path = OUT / f"server_global_cdss_safety_audit_summary_{TODAY}.json"
    detail_path = OUT / f"server_global_cdss_safety_audit_detail_{TODAY}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    detail_path.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # CSV summary for nontechnical review.
    csv_path = OUT / f"server_global_cdss_safety_audit_summary_{TODAY}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["检查项", "数量", "性质", "说明"])
        descriptions = {
            "non_kgnode_nodes_count": "不带 KGNode 标签的节点，前端/查询接口可能漏查。",
            "relations_touching_non_kgnode_count": "关系连接到非 KGNode 节点，图谱主查询可能漏掉。",
            "duplicate_type_name_count": "同一实体类型同名重复，会影响医生看到的实体唯一性。",
            "disease_definition_empty_count": "疾病定义为空，不能支撑疾病基本解释。",
            "conditional_definition_used_in_formal_ready_edges_count": "条件性定义参与正式推荐关系，属于 CDSS 风险。",
            "diagnosis_criteria_without_components_count": "诊断标准只有标题，没有明细条件。",
            "differential_diagnosis_without_details_count": "鉴别诊断只有疾病名，没有鉴别点/排除检查。",
            "treatment_plan_without_downstream_action_count": "治疗方案没有药物/手术/动作下游，医生无法执行。",
            "medication_class_without_specific_count": "药物类别没有具体药品，医生无法落地用药。",
            "recommendation_relationships_missing_core_fields_count": "推荐关系缺推荐等级、证据等级或来源证据。",
            "technical_name_nodes_count": "节点名是技术编码，前端展示不可读。",
        }
        for k in blocking_keys:
            w.writerow([k, counts.get(k, 0), "阻断", descriptions.get(k, "")])
        for k in warning_keys:
            w.writerow([k, counts.get(k, 0), "警告", "需要治理，但不一定阻断知识展示。"])

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
