#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P6 标准诊断缺口收口。

原则：
1. Oracle 原始 ICD-10 字典只读。
2. 仅当疾病名称与 K_ICD10_DICT 有效记录完全一致且唯一时，自动写入 Neo4j 标准诊断映射。
3. 其他情况只写入 K_KG_DICT_CHANGE_REVIEW 待处理登记表，不伪造编码。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import oracledb
from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAP_CSV = (
    ROOT
    / "项目管理中心_project_management"
    / "2026年8月P6已解析大类终验"
    / "15_标准字典分类口径修正后复核_20260803"
    / "03_样板缺口清单.csv"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "项目管理中心_project_management"
    / "2026年8月P6已解析大类终验"
    / "16_标准诊断缺口收口_20260803"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def parse_neo4j_config(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s，,；;]+", text)
    user = re.search(r"(?:用户名|用户|user)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    if not (uri and user and password):
        raise RuntimeError(f"无法解析 Neo4j 连接文件：{path}")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def oracle_scalar(value: Any) -> Any:
    if hasattr(value, "read"):
        return value.read()
    return value


def fetch_exact_icd10(cursor: oracledb.Cursor, name: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, code, name, valid_flag
          FROM K_ICD10_DICT
         WHERE valid_flag = 1
           AND trim(name) = :name
         ORDER BY code, id
        """,
        name=name.strip(),
    )
    columns = [column[0].lower() for column in cursor.description]
    return [
        {column: oracle_scalar(value) for column, value in zip(columns, row)}
        for row in cursor.fetchall()
    ]


def fetch_like_icd10(cursor: oracledb.Cursor, name: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, code, name, valid_flag
          FROM K_ICD10_DICT
         WHERE valid_flag = 1
           AND name LIKE :kw
         ORDER BY name, code
         FETCH FIRST 20 ROWS ONLY
        """,
        kw=f"%{name.strip()}%",
    )
    columns = [column[0].lower() for column in cursor.description]
    return [
        {column: oracle_scalar(value) for column, value in zip(columns, row)}
        for row in cursor.fetchall()
    ]


def collect_standard_diagnosis_gaps(path: Path) -> list[dict[str, str]]:
    rows = []
    seen = set()
    for row in read_csv(path):
        if row.get("问题类别") != "标准诊断阻断":
            continue
        key = (row.get("疾病编码", "").strip(), row.get("疾病名称", "").strip())
        if not key[0] or key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def classify_candidates(gaps: list[dict[str, str]], cursor: oracledb.Cursor) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exact_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    for gap in gaps:
        disease_code = gap["疾病编码"].strip()
        disease_name = gap["疾病名称"].strip()
        exact = fetch_exact_icd10(cursor, disease_name)
        like_rows = fetch_like_icd10(cursor, disease_name)
        if len(exact) == 1:
            item = exact[0]
            exact_rows.append(
                {
                    "disease_code": disease_code,
                    "disease_name": disease_name,
                    "target_id": str(item.get("id") or ""),
                    "target_code": str(item.get("code") or ""),
                    "target_name": str(item.get("name") or ""),
                    "target_table": "K_ICD10_DICT",
                    "match_type": "完全同名唯一命中",
                }
            )
        else:
            issue_type = "NO_CANDIDATE" if not exact and not like_rows else "MULTI_OR_FUZZY_CANDIDATE"
            review_rows.append(
                {
                    "entity_type": "Disease",
                    "kg_node_code": disease_code,
                    "kg_node_name": disease_name,
                    "target_table": "K_ICD10_DICT",
                    "target_id": "",
                    "target_code": "",
                    "target_name": "；".join(str(x.get("name") or "") for x in like_rows[:8]),
                    "issue_type": issue_type,
                    "current_value": disease_name,
                    "proposed_value": "",
                    "reason": "无完全同名唯一有效 ICD-10 候选，禁止自动写标准诊断映射。",
                    "source": "P6标准诊断缺口收口_20260803",
                    "review_status": "pending",
                    "execution_status": "not_executed",
                    "remark": f"模糊候选数：{len(like_rows)}",
                }
            )
    return exact_rows, review_rows


def write_neo4j_mappings(config: dict[str, str], rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
    try:
        with driver.session() as session:
            result = session.run(
                """
                UNWIND $rows AS row
                MATCH (d:KGNode {entityType:'Disease', code:row.disease_code})
                MERGE (sd:KGNode:StandardDiagnosis {entityType:'StandardDiagnosis', cdss_dict_id:row.target_id})
                SET sd.code = row.target_code,
                    sd.name = row.target_name,
                    sd.display_name = row.target_name,
                    sd.preferred_name = row.target_name,
                    sd.source_table = row.target_table,
                    sd.valid_flag = 1,
                    sd.dictionary_validation_status = 'validated',
                    sd.cdss_standard_ready = true,
                    sd.cdss_order_ready = true,
                    sd.emr_write_allowed = true,
                    sd.cdss_display_ready = true,
                    sd.clinical_use_status = 'clinical_ready',
                    sd.cdss_use_status = 'formal_cdss_ready',
                    sd.updated_at = $now
                MERGE (d)-[r:has_standard_diagnosis]->(sd)
                SET r.relationType = 'has_standard_diagnosis',
                    r.match_type = 'exact',
                    r.match_level = '精确',
                    r.source_table = row.target_table,
                    r.cdss_dict_id = row.target_id,
                    r.cdss_code = row.target_code,
                    r.emr_write_allowed = true,
                    r.updated_at = $now
                RETURN count(r) AS c
                """,
                rows=rows,
                now=now,
            )
            record = result.single()
            return int(record["c"] if record else 0)
    finally:
        driver.close()


def write_review_rows(connection: oracledb.Connection, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
    MERGE INTO K_KG_DICT_CHANGE_REVIEW t
    USING (
        SELECT :entity_type AS entity_type,
               :kg_node_code AS kg_node_code,
               :target_table AS target_table,
               :issue_type AS issue_type
          FROM dual
    ) s
    ON (
        t.entity_type = s.entity_type
        AND t.kg_node_code = s.kg_node_code
        AND t.target_table = s.target_table
        AND t.issue_type = s.issue_type
        AND t.source = 'P6标准诊断缺口收口_20260803'
    )
    WHEN MATCHED THEN UPDATE SET
        t.kg_node_name = :kg_node_name,
        t.target_id = :target_id,
        t.target_code = :target_code,
        t.target_name = :target_name,
        t.current_value = :current_value,
        t.proposed_value = :proposed_value,
        t.reason = :reason,
        t.review_status = :review_status,
        t.execution_status = :execution_status,
        t.valid_flag = 1,
        t.modify_time = SYSDATE,
        t.modify_operator = 0,
        t.remark = :remark
    WHEN NOT MATCHED THEN INSERT (
        id, entity_type, kg_node_code, kg_node_name, target_table, target_id, target_code,
        target_name, issue_type, current_value, proposed_value, reason, source,
        review_status, execution_status, valid_flag, create_time, create_operator, remark
    ) VALUES (
        :id, :entity_type, :kg_node_code, :kg_node_name, :target_table, :target_id, :target_code,
        :target_name, :issue_type, :current_value, :proposed_value, :reason, 'P6标准诊断缺口收口_20260803',
        :review_status, :execution_status, 1, SYSDATE, 0, :remark
    )
    """
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
        "review_status",
        "execution_status",
        "remark",
    }
    bind_rows = []
    for row in rows:
        item = {key: row.get(key) for key in bind_keys}
        item["id"] = uuid.uuid4().hex
        bind_rows.append(item)
    with connection.cursor() as cursor:
        cursor.executemany(sql, bind_rows)
    connection.commit()
    return len(bind_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="P6 标准诊断缺口收口")
    parser.add_argument("--gap-csv", type=Path, default=DEFAULT_GAP_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mode", choices=["dry-run", "write"], default="dry-run")
    parser.add_argument("--neo4j-config", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--oracle-user", default="zycdss")
    parser.add_argument("--oracle-dsn", default="192.168.4.25:1521/ORCL")
    args = parser.parse_args()

    password = os.environ.get("ORACLE_PASSWORD")
    if not password:
        raise RuntimeError("缺少 ORACLE_PASSWORD 环境变量。")

    gaps = collect_standard_diagnosis_gaps(args.gap_csv)
    connection = oracledb.connect(user=args.oracle_user, password=password, dsn=args.oracle_dsn)
    try:
        with connection.cursor() as cursor:
            exact_rows, review_rows = classify_candidates(gaps, cursor)
        neo4j_written = 0
        oracle_review_written = 0
        if args.mode == "write":
            neo4j_written = write_neo4j_mappings(parse_neo4j_config(args.neo4j_config), exact_rows)
            oracle_review_written = write_review_rows(connection, review_rows)
    finally:
        connection.close()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.output_dir / "01_可自动写入标准诊断映射.csv",
        exact_rows,
        ["disease_code", "disease_name", "target_table", "target_id", "target_code", "target_name", "match_type"],
    )
    write_csv(
        args.output_dir / "02_标准诊断待处理登记.csv",
        review_rows,
        [
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
            "review_status",
            "execution_status",
            "remark",
        ],
    )
    summary = {
        "mode": args.mode,
        "gap_count": len(gaps),
        "exact_unique_count": len(exact_rows),
        "review_count": len(review_rows),
        "neo4j_written": neo4j_written,
        "oracle_review_written": oracle_review_written,
        "oracle_original_dictionary_written": False,
        "output_dir": str(args.output_dir),
    }
    write_json(args.output_dir / "00_标准诊断缺口收口_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
