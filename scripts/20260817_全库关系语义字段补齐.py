from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "2026年8月真实性来源核验"
LINK_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260817_关系语义字段补齐"


def parse_neo4j_link() -> tuple[str, str, str]:
    text = LINK_FILE.read_text(encoding="utf-8", errors="ignore")
    uri_match = re.search(r"bolt://[^\s\u3000，,]+", text)
    user_match = re.search(r"(?:用户名|用户|user|username)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    password_match = re.search(r"(?:密码|password)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    if not uri_match or not password_match:
        raise RuntimeError("未在图谱数据库链接.txt 中解析到 bolt 地址或密码")
    return uri_match.group(0), (user_match.group(1) if user_match else "neo4j"), password_match.group(1)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    uri, user, password = parse_neo4j_link()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    queries = {
        "检查检验关系语义补齐": """
            MATCH (d:Disease)-[:has_exam_plan]->(:ExamPlan)-[r:includes_exam_item|includes_lab_item]->(item)
            WHERE r.purpose IS NULL OR r.clinical_stage IS NULL OR r.service_target_code IS NULL OR r.service_target_name IS NULL
            SET r.purpose = coalesce(r.purpose, '辅助诊断/病情评估'),
                r.clinical_stage = coalesce(r.clinical_stage, '首诊评估'),
                r.service_target_code = coalesce(r.service_target_code, d.code),
                r.service_target_name = coalesce(r.service_target_name, d.name),
                r.service_target_type = coalesce(r.service_target_type, 'Disease'),
                r.semantic_review_status = coalesce(r.semantic_review_status, 'auto_completed_from_existing_chain'),
                r.semantic_patch_batch = coalesce(r.semantic_patch_batch, $batch_id),
                r.semantic_patch_time = coalesce(r.semantic_patch_time, $now)
            RETURN count(r) AS c
        """,
        "治疗动作关系语义补齐": """
            MATCH (d:Disease)-[:has_treatment_plan]->(:TreatmentPlan)-[r:includes_medication|includes_procedure|includes_treatment_item]->(item)
            WHERE r.purpose IS NULL OR r.clinical_stage IS NULL OR r.service_target_code IS NULL OR r.service_target_name IS NULL
            SET r.purpose = coalesce(r.purpose, '治疗执行/治疗管理'),
                r.clinical_stage = coalesce(r.clinical_stage, '治疗阶段'),
                r.service_target_code = coalesce(r.service_target_code, d.code),
                r.service_target_name = coalesce(r.service_target_name, d.name),
                r.service_target_type = coalesce(r.service_target_type, 'Disease'),
                r.semantic_review_status = coalesce(r.semantic_review_status, 'auto_completed_from_existing_chain'),
                r.semantic_patch_batch = coalesce(r.semantic_patch_batch, $batch_id),
                r.semantic_patch_time = coalesce(r.semantic_patch_time, $now)
            RETURN count(r) AS c
        """,
    }

    result = {"batch_id": BATCH_ID, "time": now, "database": uri, "updates": {}}
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session() as session:
            for name, query in queries.items():
                result["updates"][name] = session.run(query, batch_id=BATCH_ID, now=now).single()["c"]

    path = OUT_DIR / "关系语义字段补齐_执行结果_20260817.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
