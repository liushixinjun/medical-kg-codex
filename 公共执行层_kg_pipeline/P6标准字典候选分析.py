#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
P6 标准字典缺口候选分析。

用途：
- 读取 P6 入库后复核产生的“标准字典缺口明细.csv”。
- 只读 Oracle 标准字典，给每个图谱实体找 CDSS 字典候选。
- 不写 Neo4j，不写 Oracle。

输出：
- 01_唯一缺口实体.csv
- 02_Oracle候选明细.csv
- 03_候选分析摘要.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import oracledb


ROOT = Path(__file__).resolve().parents[1]

TABLE_BY_ENTITY_TYPE = {
    "ExamItem": "K_EXAM_ITEM_DICT",
    "LabItem": "K_LAB_ITEM_DICT",
    "LabSubitem": "K_LAB_SUBITEM_DICT",
    "Medication": "K_DRUG_DICT",
    "Procedure": "K_OPERATION_HANDLE_DICT",
    "TreatmentItem": "K_TREATMENT_DICT",
}

STOP_WORDS = {
    "检查",
    "测定",
    "治疗",
    "手术",
    "药物",
    "项目",
    "评估",
}


def normalize_text(text: str) -> str:
    text = (text or "").strip()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", "", text)
    return text


def split_terms(name: str) -> list[str]:
    clean = normalize_text(name)
    parts = re.split(r"[/、,，+＋\s]+", clean)
    terms: list[str] = []
    for part in parts:
        part = re.sub(r"\([^)]*\)", "", part)
        part = part.strip()
        if len(part) >= 2 and part not in STOP_WORDS:
            terms.append(part)
    if clean and clean not in terms:
        terms.insert(0, clean)
    return terms[:6]


def oracle_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "read"):
        return value.read()
    return value


def read_unique_gap_nodes(path: Path) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            entity_type = (row.get("entity_type") or "").strip()
            node_code = (row.get("node_code") or "").strip()
            node_name = (row.get("node_name") or "").strip()
            if not entity_type or not node_code:
                continue
            key = (entity_type, node_code)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "entity_type": entity_type,
                    "node_code": node_code,
                    "node_name": node_name,
                    "target_table": TABLE_BY_ENTITY_TYPE.get(entity_type, ""),
                }
            )
    return rows


def fetch_candidates(cursor: oracledb.Cursor, table: str, name: str) -> list[dict[str, str]]:
    if not table:
        return []

    terms = split_terms(name)
    candidates: dict[str, dict[str, str]] = {}

    # 先完全同名，再关键词组合。只取 valid_flag=1 的有效字典。
    sql_exact = f"""
        SELECT id, code, name, valid_flag
          FROM {table}
         WHERE valid_flag = 1
           AND trim(name) = :name
         FETCH FIRST 30 ROWS ONLY
    """
    try:
        cursor.execute(sql_exact, name=normalize_text(name))
        columns = [column[0].lower() for column in cursor.description]
        for record in cursor.fetchall():
            data = {column: str(oracle_value(value) or "") for column, value in zip(columns, record)}
            data["match_type"] = "完全同名"
            candidates[data.get("id", data.get("code", ""))] = data
    except Exception:
        pass

    sql_like = f"""
        SELECT id, code, name, valid_flag
          FROM {table}
         WHERE valid_flag = 1
           AND name LIKE :pattern
         FETCH FIRST 30 ROWS ONLY
    """
    for term in terms:
        try:
            cursor.execute(sql_like, pattern=f"%{term}%")
            columns = [column[0].lower() for column in cursor.description]
            for record in cursor.fetchall():
                data = {column: str(oracle_value(value) or "") for column, value in zip(columns, record)}
                data["match_type"] = f"包含关键词:{term}"
                candidates.setdefault(data.get("id", data.get("code", "")), data)
        except Exception:
            continue

    return list(candidates.values())


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gap-csv",
        type=Path,
        required=True,
        help="P6 标准字典缺口明细.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="输出目录",
    )
    parser.add_argument("--oracle-user", default="zycdss")
    parser.add_argument("--oracle-dsn", default="192.168.4.25:1521/ORCL")
    args = parser.parse_args()

    password = os.environ.get("ORACLE_PASSWORD")
    if not password:
        raise RuntimeError("缺少 ORACLE_PASSWORD 环境变量")

    unique_nodes = read_unique_gap_nodes(args.gap_csv)
    candidate_rows: list[dict[str, Any]] = []

    conn = oracledb.connect(user=args.oracle_user, password=password, dsn=args.oracle_dsn)
    try:
        cursor = conn.cursor()
        for node in unique_nodes:
            candidates = fetch_candidates(cursor, node["target_table"], node["node_name"])
            node["candidate_count"] = str(len(candidates))
            if len(candidates) == 1:
                node["candidate_status"] = "唯一候选，需二次语义确认"
            elif len(candidates) > 1:
                node["candidate_status"] = "多个候选，禁止自动写库"
            else:
                node["candidate_status"] = "无候选，需补充字典或作为知识项保留"
            for item in candidates:
                candidate_rows.append(
                    {
                        "entity_type": node["entity_type"],
                        "node_code": node["node_code"],
                        "node_name": node["node_name"],
                        "target_table": node["target_table"],
                        "candidate_id": item.get("id", ""),
                        "candidate_code": item.get("code", ""),
                        "candidate_name": item.get("name", ""),
                        "candidate_valid_flag": item.get("valid_flag", ""),
                        "match_type": item.get("match_type", ""),
                    }
                )
    finally:
        conn.close()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.output_dir / "01_唯一缺口实体.csv",
        unique_nodes,
        ["entity_type", "node_code", "node_name", "target_table", "candidate_count", "candidate_status"],
    )
    write_csv(
        args.output_dir / "02_Oracle候选明细.csv",
        candidate_rows,
        [
            "entity_type",
            "node_code",
            "node_name",
            "target_table",
            "candidate_id",
            "candidate_code",
            "candidate_name",
            "candidate_valid_flag",
            "match_type",
        ],
    )
    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "unique_gap_node_count": len(unique_nodes),
        "candidate_row_count": len(candidate_rows),
        "by_entity_type": dict(Counter(row["entity_type"] for row in unique_nodes)),
        "by_candidate_status": dict(Counter(row["candidate_status"] for row in unique_nodes)),
        "oracle_written": False,
        "neo4j_written": False,
    }
    (args.output_dir / "03_候选分析摘要.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
