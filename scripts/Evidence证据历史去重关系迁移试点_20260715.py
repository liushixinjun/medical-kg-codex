from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient, cypher_name  # noqa: E402


DEFAULT_CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
OUT_ROOT = ROOT / "项目管理中心_project_management"


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


def first_value(result: dict[str, Any], default: int = 0) -> int:
    data = result["results"][0]["data"]
    if not data:
        return default
    return int(data[0]["row"][0] or default)


def choose_keep_code(nodes: list[dict[str, Any]]) -> str:
    sorted_nodes = sorted(nodes, key=lambda item: (-int(item.get("degree") or 0), str(item.get("code") or "")))
    return str(sorted_nodes[0]["code"])


def fetch_candidate_groups(client: Neo4jHttpClient, *, group_limit: int, max_relations_per_group: int) -> list[dict[str, Any]]:
    return rows(
        client.run(
            """
            MATCH (e:Evidence)
            WHERE coalesce(e.evidence_text, '') <> ''
              AND coalesce(e.deprecated, false) <> true
              AND e.duplicate_replaced_by IS NULL
            WITH
              coalesce(e.source_name, '') AS source_name,
              toString(coalesce(e.source_page, '')) AS source_page,
              coalesce(e.evidence_text, '') AS evidence_text,
              collect(e) AS evs,
              count(e) AS node_count
            WHERE node_count > 1
            UNWIND evs AS e
            OPTIONAL MATCH (e)-[r]-()
            WITH source_name, source_page, evidence_text, node_count, e, count(r) AS degree
            WITH source_name, source_page, evidence_text, node_count,
                 collect({code: e.code, degree: degree}) AS nodes,
                 sum(degree) AS total_relation_count,
                 size(evidence_text) AS evidence_text_length
            WHERE total_relation_count > 0 AND total_relation_count <= $max_relations_per_group
            RETURN
              source_name,
              source_page,
              evidence_text_length,
              node_count,
              total_relation_count,
              nodes
            ORDER BY total_relation_count ASC, node_count ASC, source_name ASC, source_page ASC
            LIMIT $group_limit
            """,
            {"group_limit": group_limit, "max_relations_per_group": max_relations_per_group},
        )
    )


def fetch_relation_rows(client: Neo4jHttpClient, duplicate_code: str, keep_code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    incoming = rows(
        client.run(
            """
            MATCH (s:KGNode)-[r]->(dup:Evidence {code: $duplicate_code})
            RETURN
              s.code AS source_code,
              type(r) AS relation_type,
              properties(r) AS props,
              $duplicate_code AS duplicate_code,
              $keep_code AS keep_code
            """,
            {"duplicate_code": duplicate_code, "keep_code": keep_code},
        )
    )
    outgoing = rows(
        client.run(
            """
            MATCH (dup:Evidence {code: $duplicate_code})-[r]->(t:KGNode)
            RETURN
              t.code AS target_code,
              type(r) AS relation_type,
              properties(r) AS props,
              $duplicate_code AS duplicate_code,
              $keep_code AS keep_code
            """,
            {"duplicate_code": duplicate_code, "keep_code": keep_code},
        )
    )
    return incoming, outgoing


def count_node_relations(client: Neo4jHttpClient, code: str) -> int:
    return first_value(
        client.run(
            """
            MATCH (e:Evidence {code: $code})
            OPTIONAL MATCH (e)-[r]-()
            RETURN count(r) AS relation_count
            """,
            {"code": code},
        )
    )


def group_by_relation_type(relation_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in relation_rows:
        props = dict(row.get("props") or {})
        props["evidence_migration_status"] = "migrated_to_main_evidence"
        props["migrated_from_evidence_code"] = row["duplicate_code"]
        props["evidence_id_before_migration"] = props.get("evidence_id", row["duplicate_code"])
        props["evidence_id"] = row["keep_code"]
        row = dict(row)
        row["props"] = props
        grouped[str(row["relation_type"])].append(row)
    return grouped


def apply_incoming_relations(client: Neo4jHttpClient, relation_rows: list[dict[str, Any]], *, batch_id: str, migrated_at: str) -> int:
    total = 0
    for relation_type, grouped_rows in group_by_relation_type(relation_rows).items():
        statement = f"""
        UNWIND $rows AS row
        MATCH (s:KGNode {{code: row.source_code}})
        MATCH (keep:Evidence {{code: row.keep_code}})
        MERGE (s)-[nr:{cypher_name(relation_type)}]->(keep)
        SET nr += row.props
        SET nr.evidence_migration_batch = $batch_id,
            nr.migrated_at = $migrated_at
        WITH s, row
        MATCH (s)-[old:{cypher_name(relation_type)}]->(dup:Evidence {{code: row.duplicate_code}})
        DELETE old
        RETURN count(*) AS migrated_count
        """
        total += first_value(client.run(statement, {"rows": grouped_rows, "batch_id": batch_id, "migrated_at": migrated_at}))
    return total


def apply_outgoing_relations(client: Neo4jHttpClient, relation_rows: list[dict[str, Any]], *, batch_id: str, migrated_at: str) -> int:
    total = 0
    for relation_type, grouped_rows in group_by_relation_type(relation_rows).items():
        statement = f"""
        UNWIND $rows AS row
        MATCH (keep:Evidence {{code: row.keep_code}})
        MATCH (t:KGNode {{code: row.target_code}})
        MERGE (keep)-[nr:{cypher_name(relation_type)}]->(t)
        SET nr += row.props
        SET nr.evidence_migration_batch = $batch_id,
            nr.migrated_at = $migrated_at
        WITH t, row
        MATCH (dup:Evidence {{code: row.duplicate_code}})-[old:{cypher_name(relation_type)}]->(t)
        DELETE old
        RETURN count(*) AS migrated_count
        """
        total += first_value(client.run(statement, {"rows": grouped_rows, "batch_id": batch_id, "migrated_at": migrated_at}))
    return total


def mark_duplicate(client: Neo4jHttpClient, *, duplicate_code: str, keep_code: str, batch_id: str, migrated_at: str) -> None:
    client.run(
        """
        MATCH (dup:Evidence {code: $duplicate_code})
        MATCH (keep:Evidence {code: $keep_code})
        SET dup.deprecated = true,
            dup.evidence_merge_status = 'relationship_migrated_to_main_evidence',
            dup.duplicate_replaced_by = $keep_code,
            dup.merge_batch_id = $batch_id,
            dup.merged_at = $migrated_at
        SET keep.merged_duplicate_count = coalesce(keep.merged_duplicate_count, 0) + 1,
            keep.evidence_merge_status = 'main_evidence_kept',
            keep.last_merge_batch_id = $batch_id,
            keep.last_merged_at = $migrated_at
        """,
        {"duplicate_code": duplicate_code, "keep_code": keep_code, "batch_id": batch_id, "migrated_at": migrated_at},
    )


def write_csv(path: Path, data_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in data_rows for key in row}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data_rows)


def run_migration(*, client: Neo4jHttpClient, group_limit: int, max_relations_per_group: int, apply: bool, output_dir: Path) -> dict[str, Any]:
    batch_id = "20260715_Evidence证据历史去重关系迁移试点"
    migrated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    candidate_groups = fetch_candidate_groups(client, group_limit=group_limit, max_relations_per_group=max_relations_per_group)
    detail_rows = []
    relation_backup_rows = []

    for group_index, group in enumerate(candidate_groups, start=1):
        nodes = group.get("nodes") or []
        keep_code = choose_keep_code(nodes)
        duplicate_codes = [str(item["code"]) for item in nodes if str(item["code"]) != keep_code]
        for duplicate_code in duplicate_codes:
            before_duplicate_relations = count_node_relations(client, duplicate_code)
            before_keep_relations = count_node_relations(client, keep_code)
            incoming, outgoing = fetch_relation_rows(client, duplicate_code, keep_code)
            for row in incoming:
                relation_backup_rows.append({"direction": "incoming", **row, "props": json.dumps(row.get("props") or {}, ensure_ascii=False)})
            for row in outgoing:
                relation_backup_rows.append({"direction": "outgoing", **row, "props": json.dumps(row.get("props") or {}, ensure_ascii=False)})

            migrated_incoming = 0
            migrated_outgoing = 0
            after_duplicate_relations = before_duplicate_relations
            after_keep_relations = before_keep_relations
            if apply:
                migrated_incoming = apply_incoming_relations(client, incoming, batch_id=batch_id, migrated_at=migrated_at)
                migrated_outgoing = apply_outgoing_relations(client, outgoing, batch_id=batch_id, migrated_at=migrated_at)
                mark_duplicate(client, duplicate_code=duplicate_code, keep_code=keep_code, batch_id=batch_id, migrated_at=migrated_at)
                after_duplicate_relations = count_node_relations(client, duplicate_code)
                after_keep_relations = count_node_relations(client, keep_code)

            detail_rows.append(
                {
                    "group_index": group_index,
                    "apply": str(apply).lower(),
                    "source_name": group.get("source_name", ""),
                    "source_page": group.get("source_page", ""),
                    "evidence_text_length": group.get("evidence_text_length", 0),
                    "group_node_count": group.get("node_count", 0),
                    "group_total_relation_count": group.get("total_relation_count", 0),
                    "keep_code": keep_code,
                    "duplicate_code": duplicate_code,
                    "before_duplicate_relation_count": before_duplicate_relations,
                    "before_keep_relation_count": before_keep_relations,
                    "incoming_relation_count": len(incoming),
                    "outgoing_relation_count": len(outgoing),
                    "migrated_incoming_relation_count": migrated_incoming,
                    "migrated_outgoing_relation_count": migrated_outgoing,
                    "after_duplicate_relation_count": after_duplicate_relations,
                    "after_keep_relation_count": after_keep_relations,
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "Evidence关系迁移试点明细.csv", detail_rows)
    write_csv(output_dir / "Evidence关系迁移试点关系备份.csv", relation_backup_rows)
    summary = {
        "batch_id": batch_id,
        "generated_at": migrated_at,
        "apply": apply,
        "group_limit": group_limit,
        "max_relations_per_group": max_relations_per_group,
        "candidate_group_count": len(candidate_groups),
        "duplicate_node_processed_count": len(detail_rows),
        "migrated_incoming_relation_count": sum(int(row["migrated_incoming_relation_count"]) for row in detail_rows),
        "migrated_outgoing_relation_count": sum(int(row["migrated_outgoing_relation_count"]) for row in detail_rows),
        "detail_csv": str(output_dir / "Evidence关系迁移试点明细.csv"),
        "backup_csv": str(output_dir / "Evidence关系迁移试点关系备份.csv"),
        "physical_delete": False,
    }
    (output_dir / "Evidence关系迁移试点_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="服务器历史 Evidence 去重关系迁移试点。默认只预演；加 --apply 才写 Neo4j。")
    parser.add_argument("--connection-file", type=Path, default=DEFAULT_CONNECTION_FILE)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--group-limit", type=int, default=1)
    parser.add_argument("--max-relations-per-group", type=int, default=20)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUT_ROOT / "38_Evidence证据历史去重关系迁移试点_20260715")
    args = parser.parse_args()

    cfg = read_db_config(args.connection_file)
    client = Neo4jHttpClient(cfg["http"], cfg["username"], cfg["password"], args.database, 5, 1)
    summary = run_migration(
        client=client,
        group_limit=max(1, args.group_limit),
        max_relations_per_group=max(1, args.max_relations_per_group),
        apply=args.apply,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
