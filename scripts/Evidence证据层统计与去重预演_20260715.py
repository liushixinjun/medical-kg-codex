from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient  # noqa: E402


OUT_ROOT = ROOT / "项目管理中心_project_management"
DEFAULT_CONNECTION_FILE = ROOT / "图谱数据库链接.txt"


def read_db_config(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    http_match = re.search(r"https?://[^\s，,；;]+", text)
    user_match = re.search(r"用户名\s*[:：]\s*([^\s，,；;]+)", text)
    password_match = re.search(r"密码\s*[:：]\s*([^\s，,；;]+)", text)
    if not (http_match and user_match and password_match):
        raise RuntimeError(f"{path} 缺少 HTTP 地址、用户名或密码。")
    return {
        "http": http_match.group(0).rstrip("/"),
        "username": user_match.group(1),
        "password": password_match.group(1),
        "database": "neo4j",
    }


def rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    columns = result["results"][0]["columns"]
    return [
        {column: item["row"][index] for index, column in enumerate(columns)}
        for item in result["results"][0]["data"]
    ]


def first_row(result: dict[str, Any]) -> dict[str, Any]:
    data = rows(result)
    return data[0] if data else {}


def query_summary(client: Neo4jHttpClient) -> dict[str, Any]:
    summary = first_row(
        client.run(
            """
            MATCH (e:Evidence)
            RETURN
              count(e) AS evidence_count,
              sum(CASE WHEN coalesce(e.evidence_text, '') = '' THEN 1 ELSE 0 END) AS empty_text_count,
              sum(CASE WHEN size(coalesce(e.evidence_text, '')) > 5000 THEN 1 ELSE 0 END) AS long_text_gt_5000,
              sum(CASE WHEN size(coalesce(e.evidence_text, '')) > 10000 THEN 1 ELSE 0 END) AS long_text_gt_10000
            """
        )
    )
    duplicate = first_row(
        client.run(
            """
            MATCH (e:Evidence)
            WITH
              coalesce(e.source_name, '') AS source_name,
              toString(coalesce(e.source_page, '')) AS source_page,
              coalesce(e.evidence_text, '') AS evidence_text,
              count(e) AS node_count
            WHERE node_count > 1
            RETURN
              count(*) AS duplicate_group_count,
              sum(node_count) AS duplicate_node_count,
              sum(node_count - 1) AS reducible_node_count
            """
        )
    )
    active_duplicate = first_row(
        client.run(
            """
            MATCH (e:Evidence)
            WHERE coalesce(e.deprecated, false) <> true
              AND e.duplicate_replaced_by IS NULL
            WITH
              coalesce(e.source_name, '') AS source_name,
              toString(coalesce(e.source_page, '')) AS source_page,
              coalesce(e.evidence_text, '') AS evidence_text,
              count(e) AS node_count
            WHERE node_count > 1
            RETURN
              count(*) AS duplicate_group_count,
              sum(node_count) AS duplicate_node_count,
              sum(node_count - 1) AS reducible_node_count
            """
        )
    )
    orphan = first_row(
        client.run(
            """
            MATCH (e:Evidence)
            WHERE NOT (()-[]->(e)) AND NOT ((e)-[]->())
            RETURN count(e) AS orphan_evidence_count
            """
        )
    )
    relation_counts = rows(
        client.run(
            """
            MATCH ()-[r]->(e:Evidence)
            RETURN type(r) AS relation_type, count(r) AS relation_count
            ORDER BY relation_count DESC
            """
        )
    )
    return {
        "server_counts": summary,
        "server_duplicate_groups": duplicate,
        "server_active_duplicate_groups": active_duplicate,
        "server_orphan": orphan,
        "server_relation_to_evidence": relation_counts,
    }


def query_duplicate_groups(client: Neo4jHttpClient, limit: int) -> list[dict[str, Any]]:
    return rows(
        client.run(
            """
            MATCH (e:Evidence)
            WHERE coalesce(e.deprecated, false) <> true
              AND e.duplicate_replaced_by IS NULL
            WITH
              coalesce(e.source_name, '') AS source_name,
              toString(coalesce(e.source_page, '')) AS source_page,
              coalesce(e.evidence_text, '') AS evidence_text,
              collect(e.code) AS codes,
              count(e) AS node_count
            WHERE node_count > 1
            WITH source_name, source_page, evidence_text, codes, node_count
            ORDER BY node_count DESC, source_name ASC, source_page ASC
            RETURN
              source_name,
              source_page,
              size(evidence_text) AS evidence_text_length,
              node_count,
              codes[0] AS suggested_keep_code,
              codes[1..] AS duplicate_codes,
              codes[..10] AS sample_codes
            LIMIT $limit
            """,
            {"limit": limit},
        )
    )


def write_duplicate_csv(path: Path, groups: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "序号",
        "来源文件",
        "页码",
        "证据文本长度",
        "重复节点数",
        "建议保留证据节点",
        "建议迁移/归并节点数",
        "样例节点",
        "迁移节点清单_JSON",
        "是否写库",
        "备注",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, group in enumerate(groups, start=1):
            duplicate_codes = group.get("duplicate_codes") or []
            writer.writerow(
                {
                    "序号": index,
                    "来源文件": group.get("source_name", ""),
                    "页码": group.get("source_page", ""),
                    "证据文本长度": group.get("evidence_text_length", 0),
                    "重复节点数": group.get("node_count", 0),
                    "建议保留证据节点": group.get("suggested_keep_code", ""),
                    "建议迁移/归并节点数": len(duplicate_codes),
                    "样例节点": "；".join(group.get("sample_codes") or []),
                    "迁移节点清单_JSON": json.dumps(duplicate_codes, ensure_ascii=False),
                    "是否写库": "否，本文件只是预演",
                    "备注": "正式迁移前必须先核对推荐等级、证据等级和关系数量",
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence 证据层服务器统计与去重预演，只读，不写 Neo4j。")
    parser.add_argument("--connection-file", type=Path, default=DEFAULT_CONNECTION_FILE)
    parser.add_argument("--limit", type=int, default=200, help="输出前 N 组重复证据明细")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()

    cfg = read_db_config(args.connection_file)
    client = Neo4jHttpClient(cfg["http"], cfg["username"], cfg["password"], args.database, 5, 1)

    summary = query_summary(client)
    duplicate_groups = query_duplicate_groups(client, max(1, args.limit))

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = OUT_ROOT / "37_Evidence证据层去重预演结果_20260715.json"
    csv_path = OUT_ROOT / "37_Evidence证据层去重预演重复组_20260715.csv"

    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "write_neo4j": False,
        "description": "只读预演：统计 Evidence 规模，列出重复证据组，给出建议保留节点和候选迁移节点。",
        "summary": summary,
        "duplicate_group_limit": args.limit,
        "duplicate_groups": duplicate_groups,
        "next_step": "确认预演结果后，再单独生成可回滚迁移脚本；本脚本不执行迁移。",
    }
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_duplicate_csv(csv_path, duplicate_groups)

    print(json.dumps({"json": str(json_path), "csv": str(csv_path), "groups": len(duplicate_groups)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
