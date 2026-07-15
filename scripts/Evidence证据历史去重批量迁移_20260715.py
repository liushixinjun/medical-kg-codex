from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.Evidence证据历史去重关系迁移试点_20260715 import (  # noqa: E402
    DEFAULT_CONNECTION_FILE,
    OUT_ROOT,
    choose_keep_code,
    fetch_candidate_groups,
    read_db_config,
    rows,
)
from scripts.import_neo4j_test_db import Neo4jHttpClient, cypher_name  # noqa: E402


def write_csv(path: Path, data_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in data_rows for key in row}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data_rows)


def first_value(result: dict[str, Any], default: int = 0) -> int:
    data = result["results"][0]["data"]
    if not data:
        return default
    return int(data[0]["row"][0] or default)


def build_pairs(candidate_groups: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    pairs: list[dict[str, Any]] = []
    degree_by_code: dict[str, int] = {}
    for group_index, group in enumerate(candidate_groups, start=1):
        nodes = group.get("nodes") or []
        keep_code = choose_keep_code(nodes)
        for item in nodes:
            degree_by_code[str(item.get("code") or "")] = int(item.get("degree") or 0)
        for item in nodes:
            duplicate_code = str(item.get("code") or "")
            if duplicate_code == keep_code:
                continue
            pairs.append(
                {
                    "group_index": group_index,
                    "source_name": group.get("source_name", ""),
                    "source_page": group.get("source_page", ""),
                    "evidence_text_length": group.get("evidence_text_length", 0),
                    "group_node_count": group.get("node_count", 0),
                    "group_total_relation_count": group.get("total_relation_count", 0),
                    "keep_code": keep_code,
                    "duplicate_code": duplicate_code,
                }
            )
    return pairs, degree_by_code


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def fetch_evidence_status(client: Neo4jHttpClient, codes: list[str]) -> dict[str, dict[str, Any]]:
    status: dict[str, dict[str, Any]] = {}
    for part in chunked(sorted(set(codes)), 800):
        for row in rows(
            client.run(
                """
                UNWIND $codes AS code
                MATCH (e:Evidence {code: code})
                OPTIONAL MATCH (e)-[r]-()
                RETURN
                  e.code AS code,
                  coalesce(e.deprecated, false) AS deprecated,
                  e.duplicate_replaced_by AS duplicate_replaced_by,
                  count(r) AS relation_count
                """,
                {"codes": part},
            )
        ):
            status[str(row["code"])] = row
    return status


def build_pairs_from_candidate_csv(
    *,
    client: Neo4jHttpClient,
    candidate_csv: Path,
    duplicate_node_limit: int,
    max_relations_per_duplicate: int,
    min_evidence_text_length: int,
) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    raw_pairs: list[dict[str, Any]] = []
    with candidate_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for group_index, row in enumerate(reader, start=1):
            text_length = int(row.get("证据文本长度") or 0)
            if text_length < min_evidence_text_length:
                continue
            keep_code = str(row.get("建议保留证据节点") or "")
            try:
                duplicate_codes = json.loads(row.get("迁移节点清单_JSON") or "[]")
            except json.JSONDecodeError:
                continue
            for duplicate_code in duplicate_codes:
                raw_pairs.append(
                    {
                        "group_index": group_index,
                        "source_name": row.get("来源文件", ""),
                        "source_page": row.get("页码", ""),
                        "evidence_text_length": text_length,
                        "group_node_count": int(row.get("重复节点数") or 0),
                        "group_total_relation_count": "",
                        "keep_code": keep_code,
                        "duplicate_code": str(duplicate_code),
                    }
                )
            if len(raw_pairs) >= duplicate_node_limit * 10:
                break

    status = fetch_evidence_status(
        client,
        [row["keep_code"] for row in raw_pairs] + [row["duplicate_code"] for row in raw_pairs],
    )
    pairs: list[dict[str, Any]] = []
    degree_by_code: dict[str, int] = {}
    seen_duplicates: set[str] = set()
    for row in raw_pairs:
        keep_status = status.get(row["keep_code"])
        duplicate_status = status.get(row["duplicate_code"])
        if not keep_status or not duplicate_status:
            continue
        if keep_status.get("deprecated") or keep_status.get("duplicate_replaced_by"):
            continue
        if duplicate_status.get("deprecated") or duplicate_status.get("duplicate_replaced_by"):
            continue
        duplicate_relation_count = int(duplicate_status.get("relation_count") or 0)
        if duplicate_relation_count <= 0 or duplicate_relation_count > max_relations_per_duplicate:
            continue
        if row["duplicate_code"] in seen_duplicates:
            continue
        seen_duplicates.add(row["duplicate_code"])
        degree_by_code[row["keep_code"]] = int(keep_status.get("relation_count") or 0)
        degree_by_code[row["duplicate_code"]] = duplicate_relation_count
        pairs.append(row)
        if len(pairs) >= duplicate_node_limit:
            break
    return pairs, degree_by_code, len({row["group_index"] for row in pairs})


def fetch_relations_batch(client: Neo4jHttpClient, pairs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    incoming = rows(
        client.run(
            """
            UNWIND $pairs AS pair
            MATCH (s:KGNode)-[r]->(dup:Evidence {code: pair.duplicate_code})
            RETURN
              pair.duplicate_code AS duplicate_code,
              pair.keep_code AS keep_code,
              s.code AS source_code,
              type(r) AS relation_type,
              properties(r) AS props
            """,
            {"pairs": pairs},
        )
    )
    outgoing = rows(
        client.run(
            """
            UNWIND $pairs AS pair
            MATCH (dup:Evidence {code: pair.duplicate_code})-[r]->(t:KGNode)
            RETURN
              pair.duplicate_code AS duplicate_code,
              pair.keep_code AS keep_code,
              t.code AS target_code,
              type(r) AS relation_type,
              properties(r) AS props
            """,
            {"pairs": pairs},
        )
    )
    return incoming, outgoing


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


def apply_incoming_batch(client: Neo4jHttpClient, relation_rows: list[dict[str, Any]], *, batch_id: str, migrated_at: str) -> int:
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


def apply_outgoing_batch(client: Neo4jHttpClient, relation_rows: list[dict[str, Any]], *, batch_id: str, migrated_at: str) -> int:
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


def mark_duplicates_batch(client: Neo4jHttpClient, pairs: list[dict[str, Any]], *, batch_id: str, migrated_at: str) -> int:
    return first_value(
        client.run(
            """
            UNWIND $pairs AS row
            MATCH (dup:Evidence {code: row.duplicate_code})
            MATCH (keep:Evidence {code: row.keep_code})
            SET dup.deprecated = true,
                dup.evidence_merge_status = 'relationship_migrated_to_main_evidence',
                dup.duplicate_replaced_by = row.keep_code,
                dup.merge_batch_id = $batch_id,
                dup.merged_at = $migrated_at
            WITH keep, count(row) AS duplicate_count
            SET keep.merged_duplicate_count = coalesce(keep.merged_duplicate_count, 0) + duplicate_count,
                keep.evidence_merge_status = 'main_evidence_kept',
                keep.last_merge_batch_id = $batch_id,
                keep.last_merged_at = $migrated_at
            RETURN sum(duplicate_count) AS marked_count
            """,
            {"pairs": pairs, "batch_id": batch_id, "migrated_at": migrated_at},
        )
    )


def count_relations_batch(client: Neo4jHttpClient, codes: list[str]) -> dict[str, int]:
    if not codes:
        return {}
    return {
        str(row["code"]): int(row["relation_count"] or 0)
        for row in rows(
            client.run(
                """
                UNWIND $codes AS code
                MATCH (e:Evidence {code: code})
                OPTIONAL MATCH (e)-[r]-()
                RETURN e.code AS code, count(r) AS relation_count
                """,
                {"codes": sorted(set(codes))},
            )
        )
    }


def run_batch_migration(
    *,
    client: Neo4jHttpClient,
    group_limit: int,
    max_relations_per_group: int,
    apply: bool,
    output_dir: Path,
    candidate_csv: Path | None = None,
    duplicate_node_limit: int | None = None,
    min_evidence_text_length: int = 1,
) -> dict[str, Any]:
    batch_id = "20260715_Evidence证据历史去重批量迁移"
    migrated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if candidate_csv:
        pairs, degree_by_code, candidate_group_count = build_pairs_from_candidate_csv(
            client=client,
            candidate_csv=candidate_csv,
            duplicate_node_limit=duplicate_node_limit or group_limit,
            max_relations_per_duplicate=max_relations_per_group,
            min_evidence_text_length=min_evidence_text_length,
        )
    else:
        candidate_groups = fetch_candidate_groups(client, group_limit=group_limit, max_relations_per_group=max_relations_per_group)
        pairs, degree_by_code = build_pairs(candidate_groups)
        candidate_group_count = len(candidate_groups)
    incoming, outgoing = fetch_relations_batch(client, pairs)
    incoming_count_by_duplicate = defaultdict(int)
    outgoing_count_by_duplicate = defaultdict(int)
    for row in incoming:
        incoming_count_by_duplicate[str(row["duplicate_code"])] += 1
    for row in outgoing:
        outgoing_count_by_duplicate[str(row["duplicate_code"])] += 1

    relation_backup_rows = [
        {"direction": "incoming", **row, "props": json.dumps(row.get("props") or {}, ensure_ascii=False)}
        for row in incoming
    ] + [
        {"direction": "outgoing", **row, "props": json.dumps(row.get("props") or {}, ensure_ascii=False)}
        for row in outgoing
    ]

    migrated_incoming = 0
    migrated_outgoing = 0
    marked_count = 0
    after_counts: dict[str, int] = {}
    if apply and pairs:
        migrated_incoming = apply_incoming_batch(client, incoming, batch_id=batch_id, migrated_at=migrated_at)
        migrated_outgoing = apply_outgoing_batch(client, outgoing, batch_id=batch_id, migrated_at=migrated_at)
        marked_count = mark_duplicates_batch(client, pairs, batch_id=batch_id, migrated_at=migrated_at)
        after_counts = count_relations_batch(client, [row["duplicate_code"] for row in pairs] + [row["keep_code"] for row in pairs])

    detail_rows = []
    for pair in pairs:
        duplicate_code = pair["duplicate_code"]
        keep_code = pair["keep_code"]
        detail_rows.append(
            {
                **pair,
                "apply": str(apply).lower(),
                "before_duplicate_relation_count": degree_by_code.get(duplicate_code, 0),
                "before_keep_relation_count": degree_by_code.get(keep_code, 0),
                "incoming_relation_count": incoming_count_by_duplicate.get(duplicate_code, 0),
                "outgoing_relation_count": outgoing_count_by_duplicate.get(duplicate_code, 0),
                "after_duplicate_relation_count": after_counts.get(duplicate_code, degree_by_code.get(duplicate_code, 0)),
                "after_keep_relation_count": after_counts.get(keep_code, degree_by_code.get(keep_code, 0)),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "Evidence批量迁移明细.csv", detail_rows)
    write_csv(output_dir / "Evidence批量迁移关系备份.csv", relation_backup_rows)
    summary = {
        "batch_id": batch_id,
        "generated_at": migrated_at,
        "apply": apply,
        "group_limit": group_limit,
        "max_relations_per_group": max_relations_per_group,
        "candidate_csv": str(candidate_csv) if candidate_csv else "",
        "candidate_group_count": candidate_group_count,
        "duplicate_node_processed_count": len(pairs),
        "incoming_relation_count": len(incoming),
        "outgoing_relation_count": len(outgoing),
        "migrated_incoming_relation_count": migrated_incoming,
        "migrated_outgoing_relation_count": migrated_outgoing,
        "marked_duplicate_count": marked_count,
        "duplicate_node_remaining_relation_count_after_apply": sum(
            after_counts.get(row["duplicate_code"], 0) for row in pairs
        ) if apply else None,
        "detail_csv": str(output_dir / "Evidence批量迁移明细.csv"),
        "backup_csv": str(output_dir / "Evidence批量迁移关系备份.csv"),
        "physical_delete": False,
    }
    (output_dir / "Evidence批量迁移_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="服务器历史 Evidence 去重关系批量迁移。默认只预演；加 --apply 才写 Neo4j。")
    parser.add_argument("--connection-file", type=Path, default=DEFAULT_CONNECTION_FILE)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--group-limit", type=int, default=500)
    parser.add_argument("--max-relations-per-group", type=int, default=50)
    parser.add_argument("--candidate-csv", type=Path, default=None)
    parser.add_argument("--duplicate-node-limit", type=int, default=None)
    parser.add_argument("--min-evidence-text-length", type=int, default=1)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUT_ROOT / "44_Evidence历史去重批量迁移_20260715")
    args = parser.parse_args()

    cfg = read_db_config(args.connection_file)
    client = Neo4jHttpClient(cfg["http"], cfg["username"], cfg["password"], args.database, 5, 1)
    summary = run_batch_migration(
        client=client,
        group_limit=max(1, args.group_limit),
        max_relations_per_group=max(1, args.max_relations_per_group),
        apply=args.apply,
        output_dir=args.output_dir,
        candidate_csv=args.candidate_csv,
        duplicate_node_limit=args.duplicate_node_limit,
        min_evidence_text_length=max(1, args.min_evidence_text_length),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
