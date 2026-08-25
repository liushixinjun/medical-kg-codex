from __future__ import annotations

import json
import re
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
LINK_FILE = ROOT / "图谱数据库链接.txt"


def read_conn() -> tuple[str, str, str]:
    text = LINK_FILE.read_text(encoding="utf-8", errors="ignore")
    bolt = re.search(r"bolt://[^\s;，,]+", text)
    user = re.search(r"用户名[:：]\s*([^\s]+)", text)
    pwd = re.search(r"密码[:：]\s*([^\s]+)", text)
    if not (bolt and user and pwd):
        raise RuntimeError("无法解析 Neo4j 连接信息")
    return bolt.group(0), user.group(1), pwd.group(1)


def run_list(session, query: str):
    return [dict(record) for record in session.run(query)]


def main() -> None:
    bolt, user, pwd = read_conn()
    driver = GraphDatabase.driver(bolt, auth=(user, pwd))
    queries = {
        "core_relationship_counts": """
        MATCH ()-[r]->()
        WHERE type(r) IN [
          'has_exam_plan','includes_exam_item','includes_lab_item',
          'exam_item_has_observation','lab_item_has_subitem',
          'has_diagnostic_criteria','has_diagnostic_component',
          'has_differential_diagnosis','has_differential_rule',
          'has_treatment_plan','recommends_action','recommends_assessment','blocks_action'
        ]
        RETURN type(r) AS rel, count(r) AS cnt
        ORDER BY rel
        """,
        "scene_property_coverage": """
        MATCH ()-[r]->()
        WHERE type(r) IN [
          'includes_exam_item','includes_lab_item',
          'recommends_action','recommends_assessment','blocks_action'
        ]
        WITH type(r) AS rel, count(r) AS total,
             sum(CASE WHEN 'clinical_stage' IN keys(r) THEN 1 ELSE 0 END) AS clinical_stage,
             sum(CASE WHEN 'use_purpose' IN keys(r) THEN 1 ELSE 0 END) AS use_purpose,
             sum(CASE WHEN 'required_level' IN keys(r) THEN 1 ELSE 0 END) AS required_level,
             sum(CASE WHEN 'trigger_condition' IN keys(r) THEN 1 ELSE 0 END) AS trigger_condition,
             sum(CASE WHEN 'clinical_context' IN keys(r) THEN 1 ELSE 0 END) AS clinical_context,
             sum(CASE WHEN 'usage_note' IN keys(r) THEN 1 ELSE 0 END) AS usage_note,
             sum(CASE WHEN 'recommendation_class' IN keys(r) THEN 1 ELSE 0 END) AS recommendation_class,
             sum(CASE WHEN 'evidence_level' IN keys(r) THEN 1 ELSE 0 END) AS evidence_level,
             sum(CASE WHEN 'evidence_ids' IN keys(r) THEN 1 ELSE 0 END) AS evidence_ids
        RETURN rel,total,clinical_stage,use_purpose,required_level,trigger_condition,
               clinical_context,usage_note,recommendation_class,evidence_level,evidence_ids
        ORDER BY rel
        """,
        "ami_exam_plan_sample": """
        MATCH (d:Disease {code:'DIS-CARD-CAD-AMI'})-[:has_exam_plan]->(p:ExamPlan)-[r]->(x)
        WHERE type(r) IN ['includes_exam_item','includes_lab_item']
        RETURN type(r) AS rel,
               coalesce(x.name,x.display_name,x.preferred_name,x.code) AS item,
               labels(x) AS labels,
               keys(r) AS r_keys
        LIMIT 10
        """,
        "recommendation_relationship_sample": """
        MATCH (rs:RecommendationStatement)-[r]->(x)
        WHERE type(r) IN ['recommends_action','recommends_assessment','blocks_action']
        RETURN coalesce(rs.name,rs.display_name,rs.preferred_name,rs.code) AS rec,
               type(r) AS rel,
               labels(x) AS target_labels,
               coalesce(x.name,x.display_name,x.preferred_name,x.code) AS target,
               keys(r) AS r_keys
        LIMIT 10
        """,
        "stemi_treatment_plan_sample": """
        MATCH (d:Disease {code:'DIS-CARD-CAD-STEMI'})-[:has_treatment_plan]->(p:TreatmentPlan)-[r]->(x)
        RETURN type(r) AS rel,
               coalesce(p.name,p.display_name,p.preferred_name,p.code) AS plan,
               labels(x) AS target_labels,
               coalesce(x.name,x.display_name,x.preferred_name,x.code) AS target,
               keys(r) AS r_keys
        LIMIT 10
        """,
        "treatment_plan_downstream": """
        MATCH (p:TreatmentPlan)-[r]->(x)
        RETURN type(r) AS rel, labels(x) AS target_labels, count(r) AS cnt
        ORDER BY cnt DESC
        LIMIT 30
        """,
        "diagnosis_and_differential_detail": """
        MATCH ()-[r]->()
        WHERE type(r) IN ['has_diagnostic_component','has_differential_rule']
        RETURN type(r) AS rel, count(r) AS cnt,
               sum(CASE WHEN 'evidence_ids' IN keys(r) THEN 1 ELSE 0 END) AS evidence_ids,
               sum(CASE WHEN 'clinical_context' IN keys(r) THEN 1 ELSE 0 END) AS clinical_context,
               sum(CASE WHEN 'use_purpose' IN keys(r) THEN 1 ELSE 0 END) AS use_purpose
        ORDER BY rel
        """,
    }

    result = {}
    with driver.session() as session:
        for name, query in queries.items():
            result[name] = run_list(session, query)
    driver.close()

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
