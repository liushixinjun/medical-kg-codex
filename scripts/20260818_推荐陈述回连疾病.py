from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "项目管理中心_project_management" / "2026年8月真实性来源核验"
BATCH_ID = "20260818_推荐陈述回连疾病"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_conn() -> tuple[str, str, str]:
    text = (BASE_DIR / "图谱数据库链接.txt").read_text(encoding="utf-8", errors="ignore")
    uri = re.search(r"bolt://[^\s；;，,]+", text)
    user = re.search(r"(?:用户名|user|username)\s*[:：]\s*([^\s；;，,]+)", text, re.I)
    pwd = re.search(r"(?:密码|password)\s*[:：]\s*([^\s；;，,]+)", text, re.I)
    if not uri or not user or not pwd:
        raise RuntimeError("图谱数据库链接.txt 缺少 bolt、用户名或密码字段")
    return uri.group(0), user.group(1), pwd.group(1)


def run_one(session, cypher: str, **params) -> int:
    rec = session.run(cypher, **params).single()
    return int(rec["n"]) if rec else 0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    uri, user, password = read_conn()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session(database="neo4j") as session:
        before = session.run(
            """
            MATCH (rs:RecommendationStatement)
            WHERE NOT (:Disease)-[:has_recommendation_statement]->(rs)
            RETURN count(rs) AS n
            """
        ).single()["n"]
        by_disease_code = run_one(
            session,
            """
            MATCH (rs:RecommendationStatement)
            WHERE coalesce(rs.disease_code,'') <> ''
            MATCH (d:Disease {code: rs.disease_code})
            MERGE (d)-[r:has_recommendation_statement]->(rs)
            ON CREATE SET r.id = 'REL-' + d.code + '-HAS-REC-' + rs.code,
                          r.created_at = $now
            SET r.clinical_stage = coalesce(rs.stage_name, rs.clinical_stage, 'CDSS推荐'),
                r.purpose = '疾病拥有正式推荐陈述',
                r.formal_recommendation = 'no',
                r.cdss_usage = '正式推荐入口索引',
                r.service_target_type = 'Disease',
                r.service_target_code = d.code,
                r.service_target_name = d.name,
                r.governance_batch = $batch,
                r.updated_at = $now
            RETURN count(r) AS n
            """,
            batch=BATCH_ID,
            now=NOW,
        )
        by_scope_code = run_one(
            session,
            """
            MATCH (rs:RecommendationStatement)
            WHERE coalesce(rs.scope_disease_code,'') <> ''
            MATCH (d:Disease {code: rs.scope_disease_code})
            MERGE (d)-[r:has_recommendation_statement]->(rs)
            ON CREATE SET r.id = 'REL-' + d.code + '-HAS-REC-' + rs.code,
                          r.created_at = $now
            SET r.clinical_stage = coalesce(rs.stage_name, rs.clinical_stage, 'CDSS推荐'),
                r.purpose = '疾病拥有正式推荐陈述',
                r.formal_recommendation = 'no',
                r.cdss_usage = '正式推荐入口索引',
                r.service_target_type = 'Disease',
                r.service_target_code = d.code,
                r.service_target_name = d.name,
                r.governance_batch = $batch,
                r.updated_at = $now
            RETURN count(r) AS n
            """,
            batch=BATCH_ID,
            now=NOW,
        )
        by_disease_codes = run_one(
            session,
            """
            MATCH (rs:RecommendationStatement)
            WHERE rs.disease_codes IS NOT NULL
            UNWIND rs.disease_codes AS disease_code
            MATCH (d:Disease {code: disease_code})
            MERGE (d)-[r:has_recommendation_statement]->(rs)
            ON CREATE SET r.id = 'REL-' + d.code + '-HAS-REC-' + rs.code,
                          r.created_at = $now
            SET r.clinical_stage = coalesce(rs.stage_name, rs.clinical_stage, 'CDSS推荐'),
                r.purpose = '疾病拥有正式推荐陈述',
                r.formal_recommendation = 'no',
                r.cdss_usage = '正式推荐入口索引',
                r.service_target_type = 'Disease',
                r.service_target_code = d.code,
                r.service_target_name = d.name,
                r.governance_batch = $batch,
                r.updated_at = $now
            RETURN count(r) AS n
            """,
            batch=BATCH_ID,
            now=NOW,
        )
        by_applicable_codes = run_one(
            session,
            """
            MATCH (rs:RecommendationStatement)
            WHERE rs.applicable_disease_codes IS NOT NULL
            UNWIND rs.applicable_disease_codes AS disease_code
            MATCH (d:Disease {code: disease_code})
            MERGE (d)-[r:has_recommendation_statement]->(rs)
            ON CREATE SET r.id = 'REL-' + d.code + '-HAS-REC-' + rs.code,
                          r.created_at = $now
            SET r.clinical_stage = coalesce(rs.stage_name, rs.clinical_stage, 'CDSS推荐'),
                r.purpose = '疾病拥有正式推荐陈述',
                r.formal_recommendation = 'no',
                r.cdss_usage = '正式推荐入口索引',
                r.service_target_type = 'Disease',
                r.service_target_code = d.code,
                r.service_target_name = d.name,
                r.governance_batch = $batch,
                r.updated_at = $now
            RETURN count(r) AS n
            """,
            batch=BATCH_ID,
            now=NOW,
        )
        by_scope_target = run_one(
            session,
            """
            MATCH (rs:RecommendationStatement)
            WHERE NOT (:Disease)-[:has_recommendation_statement]->(rs)
            WITH rs, coalesce(rs.scope_target, rs.disease_name, '') AS target
            WHERE target <> ''
            MATCH (d:Disease)
            WHERE d.name = target OR d.display_name = target OR target IN coalesce(d.aliases, [])
            MERGE (d)-[r:has_recommendation_statement]->(rs)
            ON CREATE SET r.id = 'REL-' + d.code + '-HAS-REC-' + rs.code,
                          r.created_at = $now
            SET r.clinical_stage = coalesce(rs.stage_name, rs.clinical_stage, 'CDSS推荐'),
                r.purpose = '疾病拥有正式推荐陈述',
                r.formal_recommendation = 'no',
                r.cdss_usage = '正式推荐入口索引',
                r.service_target_type = 'Disease',
                r.service_target_code = d.code,
                r.service_target_name = d.name,
                r.governance_batch = $batch,
                r.updated_at = $now
            RETURN count(r) AS n
            """,
            batch=BATCH_ID,
            now=NOW,
        )
        after = session.run(
            """
            MATCH (rs:RecommendationStatement)
            WHERE NOT (:Disease)-[:has_recommendation_statement]->(rs)
            RETURN count(rs) AS n
            """
        ).single()["n"]
        sample = [
            dict(r)
            for r in session.run(
                """
                MATCH (d:Disease)-[:has_recommendation_statement]->(rs:RecommendationStatement)-[:recommends_action {formal_recommendation:'yes'}]->(a)
                WHERE d.code IN ['DIS-CARD-CAD-AMI','DIS-CARD-CAD-STEMI','DIS-CARD-CAD-NSTEMI','DIS-CARD-CM-GENERAL','DIS-CARD-CM-HCM','DIS-CARD-CM-DCM']
                OPTIONAL MATCH (rs)-[:supported_by_evidence]->(ev:Evidence)
                OPTIONAL MATCH (rs)-[:uses_primary_guideline|based_on_guideline]->(g:Guideline)
                RETURN d.code AS disease_code,
                       d.name AS disease_name,
                       count(DISTINCT rs) AS recommendation_count,
                       count(DISTINCT a) AS action_count,
                       count(DISTINCT ev) AS evidence_count,
                       count(DISTINCT g) AS guideline_count
                ORDER BY d.code
                """
            )
        ]
    driver.close()
    payload = {
        "time": NOW,
        "batch": BATCH_ID,
        "unlinked_recommendation_before": before,
        "linked_by_disease_code": by_disease_code,
        "linked_by_scope_disease_code": by_scope_code,
        "linked_by_disease_codes": by_disease_codes,
        "linked_by_applicable_disease_codes": by_applicable_codes,
        "linked_by_scope_target": by_scope_target,
        "unlinked_recommendation_after": after,
        "sample": sample,
    }
    out = OUT_DIR / "推荐陈述回连疾病_20260818.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
