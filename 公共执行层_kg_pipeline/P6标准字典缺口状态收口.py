#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
P6 标准字典缺口状态收口。

只做三件事：
1. 唯一候选：写入 Neo4j 标准字典映射。
2. 多候选/无候选：写入 K_KG_DICT_CHANGE_REVIEW 审核表。
3. 多候选/无候选：在 Neo4j 标记为不可直接回填医嘱。

不修改 Oracle 原标准字典表。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import oracledb
from neo4j import GraphDatabase


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def stable_id(*parts: str) -> str:
    text = "|".join(parts)
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def build_plan(unique_rows: list[dict[str, str]], candidate_rows: list[dict[str, str]]) -> dict[str, Any]:
    candidates_by_node: dict[str, list[dict[str, str]]] = {}
    for row in candidate_rows:
        candidates_by_node.setdefault(row["node_code"], []).append(row)

    validated: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for row in unique_rows:
        node_code = row["node_code"]
        candidates = candidates_by_node.get(node_code, [])
        status = row.get("candidate_status", "")
        if len(candidates) == 1 and "唯一候选" in status:
            c = candidates[0]
            validated.append(
                {
                    "node_code": node_code,
                    "node_name": row["node_name"],
                    "entity_type": row["entity_type"],
                    "target_table": row["target_table"],
                    "target_id": c["candidate_id"],
                    "target_code": c["candidate_code"],
                    "target_name": c["candidate_name"],
                    "reason": "Oracle有效标准字典唯一候选，图谱实体可映射为该标准项目。",
                }
            )
            continue

        issue_type = "MULTI_CANDIDATE" if candidates else "NO_CANDIDATE"
        proposed = {
            "node": row,
            "candidates": candidates[:30],
            "required_action": (
                "需要确定具体字典项或新增标准字典项；未确认前不得下医嘱或回填EMR。"
                if issue_type == "MULTI_CANDIDATE"
                else "CDSS有效标准字典无候选，需要新增或维护标准字典；未确认前不得下医嘱或回填EMR。"
            ),
        }
        review.append(
            {
                "id": stable_id("P6_STD_DICT_GAP", row["entity_type"], node_code, row["node_name"]),
                "entity_type": row["entity_type"],
                "kg_node_code": node_code,
                "kg_node_name": row["node_name"],
                "target_table": row["target_table"],
                "target_id": "",
                "target_code": "",
                "target_name": "",
                "issue_type": issue_type,
                "current_value": json.dumps(row, ensure_ascii=False),
                "proposed_value": json.dumps(proposed, ensure_ascii=False),
                "reason": proposed["required_action"],
                "source": "P6已解析疾病大类终验_标准字典候选分析_20260803",
                "neo4j_status": "candidate_conflict" if issue_type == "MULTI_CANDIDATE" else "pending_dictionary_registration",
            }
        )
    return {"validated": validated, "review": review}


def write_review_rows(conn: oracledb.Connection, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
MERGE INTO K_KG_DICT_CHANGE_REVIEW t
USING (
  SELECT :id AS id FROM dual
) s
ON (t.ID = s.id)
WHEN MATCHED THEN UPDATE SET
  ENTITY_TYPE = :entity_type,
  KG_NODE_CODE = :kg_node_code,
  KG_NODE_NAME = :kg_node_name,
  TARGET_TABLE = :target_table,
  TARGET_ID = :target_id,
  TARGET_CODE = :target_code,
  TARGET_NAME = :target_name,
  ISSUE_TYPE = :issue_type,
  CURRENT_VALUE = :current_value,
  PROPOSED_VALUE = :proposed_value,
  REASON = :reason,
  SOURCE = :source,
  REVIEW_STATUS = 'PENDING',
  EXECUTION_STATUS = 'NOT_EXECUTED',
  VALID_FLAG = 1,
  MODIFY_TIME = SYSDATE,
  MODIFY_OPERATOR = -1
WHEN NOT MATCHED THEN INSERT (
  ID, ENTITY_TYPE, KG_NODE_CODE, KG_NODE_NAME, TARGET_TABLE,
  TARGET_ID, TARGET_CODE, TARGET_NAME, ISSUE_TYPE, CURRENT_VALUE,
  PROPOSED_VALUE, REASON, SOURCE, REVIEW_STATUS, EXECUTION_STATUS,
  VALID_FLAG, CREATE_TIME, CREATE_OPERATOR
) VALUES (
  :id, :entity_type, :kg_node_code, :kg_node_name, :target_table,
  :target_id, :target_code, :target_name, :issue_type, :current_value,
  :proposed_value, :reason, :source, 'PENDING', 'NOT_EXECUTED',
  1, SYSDATE, -1
)
    """
    cursor = conn.cursor()
    bind_keys = {
        "id",
        "entity_type",
        "kg_node_code",
        "kg_node_name",
        "target_table",
        "target_id",
        "target_code",
        "target_name",
        "issue_type",
        "current_value",
        "proposed_value",
        "reason",
        "source",
    }
    for row in rows:
        cursor.execute(sql, {key: row.get(key, "") for key in bind_keys})
    conn.commit()
    return len(rows)


def write_neo4j(driver: GraphDatabase.driver, plan: dict[str, Any]) -> dict[str, int]:
    result = {"validated_mapped": 0, "review_marked": 0}
    with driver.session() as session:
        if plan["validated"]:
            cypher = """
UNWIND $rows AS row
MATCH (n:KGNode {code: row.node_code})
SET n.cdss_dict_id = row.target_id,
    n.standard_code = row.target_code,
    n.standard_name = row.target_name,
    n.source_table = row.target_table,
    n.valid_flag = 1,
    n.dictionary_validation_status = 'validated',
    n.cdss_dictionary_resolution_status = 'standard_dict_validated',
    n.cdss_dictionary_resolution_note = row.reason,
    n.cdss_order_ready = true,
    n.cdss_display_ready = true,
    n.emr_write_allowed = true,
    n.standard_mapping_batch = 'P6_STANDARD_DICT_STATUS_CLOSE_20260803',
    n.updated_at = datetime()
RETURN count(n) AS c
"""
            result["validated_mapped"] = int(session.run(cypher, rows=plan["validated"]).single()["c"])
        if plan["review"]:
            cypher = """
UNWIND $rows AS row
MATCH (n:KGNode {code: row.kg_node_code})
SET n.dictionary_validation_status = row.neo4j_status,
    n.cdss_dictionary_resolution_status = row.neo4j_status,
    n.cdss_dictionary_resolution_note = row.reason,
    n.cdss_dictionary_required_action = row.reason,
    n.cdss_order_ready = false,
    n.cdss_display_ready = true,
    n.emr_write_allowed = false,
    n.source_table = row.target_table,
    n.standard_mapping_batch = 'P6_STANDARD_DICT_STATUS_CLOSE_20260803',
    n.updated_at = datetime()
RETURN count(n) AS c
"""
            result["review_marked"] = int(session.run(cypher, rows=plan["review"]).single()["c"])
    return result


def backup_nodes(driver: GraphDatabase.driver, codes: list[str]) -> list[dict[str, Any]]:
    with driver.session() as session:
        return session.run(
            """
MATCH (n:KGNode)
WHERE n.code IN $codes
RETURN n.code AS code, labels(n) AS labels, properties(n) AS props
ORDER BY n.code
""",
            codes=codes,
        ).data()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--oracle-user", default="zycdss")
    parser.add_argument("--oracle-dsn", default="192.168.4.25:1521/ORCL")
    args = parser.parse_args()

    unique_rows = read_csv(args.candidate_dir / "01_唯一缺口实体.csv")
    candidate_rows = read_csv(args.candidate_dir / "02_Oracle候选明细.csv")
    plan = build_plan(unique_rows, candidate_rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "01_状态收口计划.json", plan)

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "write" if args.write else "dry_run",
        "validated_mapping_count": len(plan["validated"]),
        "review_count": len(plan["review"]),
        "neo4j_written": False,
        "oracle_original_dictionary_written": False,
        "oracle_review_table_written": False,
        "write_result": {"validated_mapped": 0, "review_marked": 0, "review_rows_written": 0},
    }

    if args.write:
        neo4j_uri = os.environ["NEO4J_URI"]
        neo4j_user = os.environ["NEO4J_USERNAME"]
        neo4j_password = os.environ["NEO4J_PASSWORD"]
        oracle_password = os.environ["ORACLE_PASSWORD"]

        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        try:
            codes = [x["node_code"] for x in plan["validated"]] + [x["kg_node_code"] for x in plan["review"]]
            write_json(args.output_dir / "02_写库前Neo4j备份.json", backup_nodes(driver, codes))
            neo4j_result = write_neo4j(driver, plan)
        finally:
            driver.close()

        conn = oracledb.connect(user=args.oracle_user, password=oracle_password, dsn=args.oracle_dsn)
        try:
            review_count = write_review_rows(conn, plan["review"])
        finally:
            conn.close()

        summary["neo4j_written"] = True
        summary["oracle_review_table_written"] = True
        summary["write_result"] = {
            "validated_mapped": neo4j_result["validated_mapped"],
            "review_marked": neo4j_result["review_marked"],
            "review_rows_written": review_count,
        }

    write_json(args.output_dir / "00_状态收口摘要.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
