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


def read_db_config(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;]+)", text)
    if not (uri and user and password):
        raise RuntimeError("数据库连接文件无法解析 Bolt 地址、用户名或密码。")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def read_repair_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    clean_rows: list[dict[str, str]] = []
    for row in rows:
        rec_code = (row.get("推荐陈述编码") or "").strip()
        evidence_code = (row.get("建议主证据编码") or "").strip()
        guideline_code = (row.get("建议主指南编码") or "").strip()
        if rec_code and evidence_code and guideline_code:
            clean_rows.append(row)
    return clean_rows


BACKUP_QUERY = """
MATCH (rec:KGNode {entityType:'RecommendationStatement'})
WHERE rec.code IN $codes
OPTIONAL MATCH (rec)-[er:supported_by_evidence|derived_from]->(ev:KGNode {entityType:'Evidence'})
OPTIONAL MATCH (rec)-[gr:uses_primary_guideline|based_on_guideline]->(gl:KGNode {entityType:'Guideline'})
OPTIONAL MATCH (rec)-[ar:recommends_action|blocks_action|recommends_assessment]->(action:KGNode)
RETURN rec.code AS recommendation_code,
       properties(rec) AS recommendation_properties,
       collect(DISTINCT {relation:type(er), code:ev.code, name:ev.name}) AS evidence_links,
       collect(DISTINCT {relation:type(gr), code:gl.code, name:gl.name}) AS guideline_links,
       collect(DISTINCT {relation:type(ar), code:action.code, name:action.name, entityType:action.entityType}) AS action_links
ORDER BY recommendation_code
"""


VERIFY_NODE_QUERY = """
MATCH (rec:KGNode {entityType:'RecommendationStatement', code:$rec_code})
MATCH (ev:KGNode {entityType:'Evidence', code:$evidence_code})
MATCH (gl:KGNode {entityType:'Guideline', code:$guideline_code})
RETURN rec.code AS recommendation_code, ev.code AS evidence_code, gl.code AS guideline_code
"""


WRITE_QUERY = """
MATCH (rec:KGNode {entityType:'RecommendationStatement', code:$rec_code})
MATCH (ev:KGNode {entityType:'Evidence', code:$evidence_code})
MATCH (gl:KGNode {entityType:'Guideline', code:$guideline_code})
MERGE (rec)-[:supported_by_evidence]->(ev)
MERGE (rec)-[:uses_primary_guideline]->(gl)
SET rec.primary_evidence_code = $evidence_code,
    rec.primary_guideline_code = $guideline_code
RETURN rec.code AS recommendation_code,
       rec.primary_evidence_code AS primary_evidence_code,
       rec.primary_guideline_code AS primary_guideline_code
"""


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run(connection_file: Path, repair_file: Path, output_dir: Path, execute: bool) -> dict[str, Any]:
    rows = read_repair_rows(repair_file)
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = read_db_config(connection_file)
    codes = [row["推荐陈述编码"].strip() for row in rows]
    result_rows: list[dict[str, Any]] = []
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"])) as driver:
        backup_records = driver.execute_query(BACKUP_QUERY, codes=codes).records
        backup = [dict(record) for record in backup_records]
        (output_dir / "06_写库前推荐证据链快照.json").write_text(
            json.dumps(
                {
                    "生成时间": started_at,
                    "说明": "P4 主证据补链写库前快照，用于必要时回滚核对。",
                    "记录数": len(backup),
                    "records": backup,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        for row in rows:
            rec_code = row["推荐陈述编码"].strip()
            evidence_code = row["建议主证据编码"].strip()
            guideline_code = row["建议主指南编码"].strip()
            params = {
                "rec_code": rec_code,
                "evidence_code": evidence_code,
                "guideline_code": guideline_code,
            }
            verify_records = driver.execute_query(VERIFY_NODE_QUERY, **params).records
            if not verify_records:
                result_rows.append(
                    {
                        "推荐陈述编码": rec_code,
                        "建议主证据编码": evidence_code,
                        "建议主指南编码": guideline_code,
                        "执行状态": "阻断",
                        "说明": "推荐陈述、证据或指南节点不存在，未写入。",
                    }
                )
                continue
            if execute:
                write_records = driver.execute_query(WRITE_QUERY, **params).records
                status = "已写入" if write_records else "阻断"
                message = "已补齐主证据和主指南精确标识。" if write_records else "写入后未返回结果。"
            else:
                status = "预演通过"
                message = "节点存在；未执行写库。"
            result_rows.append(
                {
                    "推荐陈述编码": rec_code,
                    "建议主证据编码": evidence_code,
                    "建议主指南编码": guideline_code,
                    "执行状态": status,
                    "说明": message,
                }
            )

    summary = {
        "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "执行模式": "写库" if execute else "只读预演",
        "输入记录数": len(rows),
        "已写入": sum(1 for row in result_rows if row["执行状态"] == "已写入"),
        "预演通过": sum(1 for row in result_rows if row["执行状态"] == "预演通过"),
        "阻断": sum(1 for row in result_rows if row["执行状态"] == "阻断"),
    }
    write_csv(
        output_dir / "07_主证据补链执行结果.csv",
        result_rows,
        ["推荐陈述编码", "建议主证据编码", "建议主指南编码", "执行状态", "说明"],
    )
    (output_dir / "07_主证据补链执行_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P4 正式推荐主证据补链执行")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--repair-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="实际写 Neo4j；未提供时只做预演。")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.connection_file, args.repair_file, args.output_dir, args.execute)
