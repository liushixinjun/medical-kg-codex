#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
P6 语义等价标准字典收口。

只处理已经人工规则确认、且 Oracle 候选唯一可解释为同一临床概念的少量映射：
1. 不写 Oracle。
2. 不处理多候选、宽泛候选、非等价候选。
3. 写 Neo4j 前先备份被修改节点和已有关系。
"""

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
CANDIDATE_CSV = (
    ROOT
    / "项目管理中心_project_management"
    / "2026年8月P6已解析大类终验"
    / "06_剩余缺口Oracle候选_20260803"
    / "01_剩余缺口Oracle宽松候选.csv"
)
OUT_DIR = (
    ROOT
    / "项目管理中心_project_management"
    / "2026年8月P6已解析大类终验"
    / "07_语义等价标准字典收口_20260803"
)
CONFIG_PATH = ROOT / "图谱数据库链接.txt"


CURATED_MAPPINGS = [
    {
        "kind": "diagnosis",
        "node_code": "DIS-CARD-PH-CTEPH",
        "graph_name": "慢性血栓栓塞性肺动脉高压",
        "target_table": "K_ICD10_DICT",
        "target_name": "慢性血栓栓塞性肺动脉高压症",
        "mapping_reason": "语义等价：是否带“症”不改变诊断含义",
    },
    {
        "kind": "diagnosis",
        "node_code": "DIS-CARD-PH-HPAH",
        "graph_name": "遗传性肺动脉高压",
        "target_table": "K_ICD10_DICT",
        "target_name": "可遗传性肺动脉高压",
        "mapping_reason": "语义等价：临床分类中 HPAH 对应可遗传性肺动脉高压",
    },
    {
        "kind": "diagnosis",
        "node_code": "DIS-CARD-ARR-VF",
        "graph_name": "心室扑动与心室颤动",
        "target_table": "K_ICD10_DICT",
        "target_name": "心室颤动和扑动",
        "mapping_reason": "语义等价：同一组 ICD-10 诊断，仅中文顺序不同",
    },
    {
        "kind": "action",
        "node_code": "EXAM-CARD-241B4B0218DF",
        "graph_name": "运动负荷试验",
        "target_table": "K_EXAM_ITEM_DICT",
        "target_name": "心电图运动负荷试验",
        "mapping_reason": "语义等价：心血管语境下运动负荷试验指心电图运动负荷试验",
    },
]


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_neo4j_config(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    uri_match = re.search(r"bolt://[^\s，,；;]+", text)
    user_match = re.search(r"(?:用户名|用户|user|username)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    password_match = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    if not (uri_match and user_match and password_match):
        raise RuntimeError("无法解析图谱数据库链接.txt，请检查 Bolt、用户名、密码字段。")
    return {"uri": uri_match.group(0), "user": user_match.group(1), "password": password_match.group(1)}


def load_candidates(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def resolve_mappings(candidates: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolved: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in CURATED_MAPPINGS:
        matches = [
            row
            for row in candidates
            if row.get("疾病编码") == item["node_code"] or row.get("对象名称") == item["graph_name"]
            if row.get("查询表") == item["target_table"] and row.get("候选名称") == item["target_name"]
        ]
        unique_matches = {
            (row.get("候选ID", ""), row.get("候选编码", ""), row.get("候选名称", "")): row
            for row in matches
        }
        if len(unique_matches) != 1:
            rejected.append({**item, "status": "未写入", "reason": f"唯一候选数={len(unique_matches)}，不是唯一候选"})
            continue
        row = next(iter(unique_matches.values()))
        resolved.append(
            {
                **item,
                "target_id": row.get("候选ID", ""),
                "target_code": row.get("候选编码", ""),
                "target_name": row.get("候选名称", ""),
                "status": "待写入",
            }
        )
    return resolved, rejected


def backup_nodes(driver, mappings: list[dict[str, Any]]) -> dict[str, Any]:
    codes = [row["node_code"] for row in mappings]
    cypher = """
    MATCH (n:KGNode)
    WHERE n.code IN $codes
    OPTIONAL MATCH (n)-[r]->(m:KGNode)
    RETURN n.code AS code,
           labels(n) AS labels,
           properties(n) AS props,
           collect({type:type(r), rel:properties(r), end_code:m.code, end_type:m.entityType, end_name:m.name}) AS out_relations
    ORDER BY code
    """
    with driver.session() as session:
        return {"backup_time": now_text(), "nodes": session.run(cypher, codes=codes).data()}


def write_mappings(driver, mappings: list[dict[str, Any]], dry_run: bool) -> dict[str, int]:
    counts = {"diagnosis": 0, "action": 0}
    if dry_run:
        return counts

    diagnosis_rows = [row for row in mappings if row["kind"] == "diagnosis"]
    action_rows = [row for row in mappings if row["kind"] == "action"]

    if diagnosis_rows:
        cypher = """
        UNWIND $rows AS row
        MATCH (d:KGNode {entityType:'Disease', code: row.node_code})
        MERGE (sd:KGNode:StandardDiagnosis {entityType:'StandardDiagnosis', cdss_dict_id: row.target_id})
        ON CREATE SET sd.code = 'STDDX-' + row.target_id,
                      sd.created_at = datetime()
        SET sd.name = row.target_name,
            sd.display_name = row.target_name,
            sd.preferred_name = row.target_name,
            sd.standard_code = row.target_code,
            sd.icd10 = row.target_code,
            sd.coding_system = 'ICD-10（诊断）',
            sd.source_type = 'cdss_standard_dict',
            sd.source_table = row.target_table,
            sd.valid_flag = 1,
            sd.dictionary_validation_status = 'validated',
            sd.clinical_use_status = 'clinical_ready',
            sd.updated_at = datetime()
        MERGE (d)-[r:has_standard_diagnosis]->(sd)
        SET r.mapping_type = '语义等价',
            r.mapping_status = 'validated',
            r.mapping_scope = 'clinical_diagnosis',
            r.emr_write_allowed = true,
            r.source_table = row.target_table,
            r.mapping_reason = row.mapping_reason,
            r.updated_at = datetime()
        SET d.cdss_dict_id = row.target_id,
            d.standard_code = row.target_code,
            d.icd10 = row.target_code,
            d.dictionary_validation_status = 'validated',
            d.dictionary_mapping_status = 'validated_semantic_equivalent',
            d.emr_write_allowed = true,
            d.updated_at = datetime()
        RETURN count(*) AS changed
        """
        with driver.session() as session:
            counts["diagnosis"] = session.run(cypher, rows=diagnosis_rows).single()["changed"]

    if action_rows:
        cypher = """
        UNWIND $rows AS row
        MATCH (a:KGNode {code: row.node_code})
        WITH a, row, coalesce(a.aliases, []) AS old_aliases
        SET a.aliases = CASE
              WHEN a.name IS NOT NULL AND NOT a.name IN old_aliases AND a.name <> row.target_name
              THEN old_aliases + a.name
              ELSE old_aliases
            END
        SET a.name = row.target_name,
            a.display_name = row.target_name,
            a.preferred_name = row.target_name,
            a.cdss_dict_id = row.target_id,
            a.standard_code = row.target_code,
            a.standard_name = row.target_name,
            a.source_table = row.target_table,
            a.valid_flag = 1,
            a.dictionary_validation_status = 'validated',
            a.dictionary_mapping_status = 'validated_semantic_equivalent',
            a.cdss_dictionary_resolution_status = 'standard_dict_validated_semantic_equivalent',
            a.cdss_order_ready = true,
            a.cdss_display_ready = true,
            a.emr_write_allowed = true,
            a.mapping_reason = row.mapping_reason,
            a.updated_at = datetime()
        RETURN count(*) AS changed
        """
        with driver.session() as session:
            counts["action"] = session.run(cypher, rows=action_rows).single()["changed"]

    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="写入 Neo4j；默认只生成预览")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = load_candidates(CANDIDATE_CSV)
    resolved, rejected = resolve_mappings(candidates)

    write_csv(
        OUT_DIR / "01_语义等价映射预览.csv",
        resolved + rejected,
        [
            "kind",
            "node_code",
            "graph_name",
            "target_table",
            "target_id",
            "target_code",
            "target_name",
            "mapping_reason",
            "status",
            "reason",
        ],
    )

    config = parse_neo4j_config(CONFIG_PATH)
    driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
    try:
        backup = backup_nodes(driver, resolved)
        write_json(OUT_DIR / "02_写入前Neo4j备份.json", backup)
        counts = write_mappings(driver, resolved, dry_run=not args.write)
    finally:
        driver.close()

    summary = {
        "generated_at": now_text(),
        "mode": "write" if args.write else "dry_run",
        "resolved_count": len(resolved),
        "rejected_count": len(rejected),
        "write_counts": counts,
        "oracle_written": False,
        "neo4j_written": bool(args.write),
        "output_dir": str(OUT_DIR),
    }
    write_json(OUT_DIR / "00_语义等价标准字典收口摘要.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
