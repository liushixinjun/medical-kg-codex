from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "128_冠心病指南PDF精修层总收口_20260717"
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260717_冠心病缺失标准检查动作补齐"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

STANDARD_EXAMS = [
    {
        "code": "EXAM-CARD-ECHOCARDIOGRAPHY",
        "name": "超声心动图",
        "aliases": ["心脏超声", "经胸超声心动图", "TTE", "UCG", "Echocardiography"],
        "english_name": "Echocardiography",
    },
    {
        "code": "EXAM-CARD-CORONARY-ANGIOGRAPHY",
        "name": "冠状动脉造影",
        "aliases": ["冠脉造影", "CAG", "冠状动脉造影检查", "Coronary angiography"],
        "english_name": "Coronary angiography",
    },
]

RELATIONS = [
    {"rec": "REC-35AFFC16987E38D3", "exam": "EXAM-CARD-ECHOCARDIOGRAPHY"},
    {"rec": "REC-73F794FD0A746355", "exam": "EXAM-CARD-CORONARY-ANGIOGRAPHY"},
    {"rec": "REC-CDSS-CAD-CCS-01-01-TEST", "exam": "EXAM-CARD-CORONARY-ANGIOGRAPHY"},
]


def read_connection() -> tuple[str, str, str]:
    text = CONNECTION_FILE.read_text(encoding="utf-8", errors="ignore")
    bolt_match = re.search(r"bolt://[^\s，,;；]+", text)
    if not bolt_match:
        raise RuntimeError("连接文件缺少 bolt 地址")
    username_match = re.search(r"(?:用户名|username|NEO4J_USERNAME)\s*[:：=]\s*([^\s，,;；]+)", text, re.I)
    password_match = re.search(r"(?:密码|password|NEO4J_PASSWORD)\s*[:：=]\s*([^\s，,;；]+)", text, re.I)
    username = username_match.group(1) if username_match else os.environ.get("NEO4J_USERNAME", "neo4j")
    password = password_match.group(1) if password_match else os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        raise RuntimeError("缺少 Neo4j 密码，禁止空密码连接")
    return bolt_match.group(0), username, password


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bolt, username, password = read_connection()
    summary = {
        "generated_at": NOW,
        "batch_id": BATCH_ID,
        "neo4j_written": True,
        "standard_exam_upserts": 0,
        "recommendation_action_relation_upserts": 0,
        "blocked": [],
    }
    driver = GraphDatabase.driver(bolt, auth=(username, password))
    try:
        driver.verify_connectivity()
        with driver.session(database="neo4j") as session:
            for exam in STANDARD_EXAMS:
                row = session.run(
                    """
                    MERGE (e:KGNode:Exam {code:$code})
                    ON CREATE SET e.created_at=$now,
                                  e.created_by_batch=$batch_id,
                                  e.status='active',
                                  e.source_type='standard_exam_action'
                    SET e.name=$name,
                        e.display_name=$name,
                        e.preferred_name=$name,
                        e.aliases=$aliases,
                        e.english_name=$english_name,
                        e.last_verified_at=$now,
                        e.last_verified_batch_id=$batch_id
                    RETURN e.code AS code
                    """,
                    {**exam, "now": NOW, "batch_id": BATCH_ID},
                ).single()
                if row:
                    summary["standard_exam_upserts"] += 1

            for rel in RELATIONS:
                row = session.run(
                    """
                    MATCH (rs:RecommendationStatement {code:$rec})
                    MATCH (e:Exam {code:$exam})
                    WHERE coalesce(rs.status,'active') <> 'deprecated'
                    MERGE (rs)-[r:recommends_action]->(e)
                    ON CREATE SET r.created_at=$now,
                                  r.batch_id=$batch_id,
                                  r.source='冠心病指南PDF精修层总收口',
                                  r.relation_status='active'
                    ON MATCH SET r.last_verified_at=$now,
                                 r.last_verified_batch_id=$batch_id
                    RETURN rs.code AS rec, e.code AS exam
                    """,
                    {"rec": rel["rec"], "exam": rel["exam"], "now": NOW, "batch_id": BATCH_ID},
                ).single()
                if row:
                    summary["recommendation_action_relation_upserts"] += 1
                else:
                    summary["blocked"].append(rel)
    finally:
        driver.close()

    (OUT_DIR / "09_冠心病缺失标准检查动作补齐_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
