from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient, cleaned_props, cypher_name, import_nodes


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {col: item["row"][idx] for idx, col in enumerate(result["results"][0]["columns"])}
        for item in result["results"][0]["data"]
    ]


def semantic_key(relation: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(relation.get("source_code", "")).strip(),
        str(relation.get("relationType", "")).strip(),
        str(relation.get("target_code", "")).strip(),
    )


def validate_delta_relations(relations: list[dict[str, Any]]) -> None:
    seen: set[tuple[str, str, str]] = set()
    for relation in relations:
        key = semantic_key(relation)
        if not all(key):
            raise ValueError(f"Delta relation missing semantic key fields: {relation.get('id')}")
        if key in seen:
            raise ValueError(f"Duplicate semantic key in delta input: {key}")
        seen.add(key)
        if relation.get("formal_cdss_ready") is True:
            raise ValueError(f"Delta relation must not be marked formal_cdss_ready=true: {relation.get('id')}")


def validate_delta_nodes(nodes: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for node in nodes:
        code = str(node.get("code", "")).strip()
        if not code:
            raise ValueError("Delta node missing code")
        if not str(node.get("entityType", "")).strip():
            raise ValueError(f"Delta node missing entityType: {code}")
        if code in seen:
            raise ValueError(f"Duplicate node code in delta input: {code}")
        seen.add(code)
        if node.get("formal_cdss_ready") is True:
            raise ValueError(f"Delta node must not be marked formal_cdss_ready=true: {code}")


def plan_delta_relation_actions(relations: list[dict[str, Any]], server_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    server_by_key = {
        (str(row.get("source_code")), str(row.get("relationType")), str(row.get("target_code"))): row
        for row in server_rows
    }
    actions: list[dict[str, Any]] = []
    for relation in relations:
        key = semantic_key(relation)
        row = server_by_key.get(key, {})
        existing_count = int(row.get("existing_count") or 0)
        existing_ids = [value for value in (row.get("existing_relation_ids") or []) if value]
        missing_id_count = int(row.get("missing_id_count") or 0)
        relation_id = str(relation.get("id", "")).strip()
        if existing_count == 0:
            action = "create"
        elif existing_ids == [relation_id] and existing_count == 1 and missing_id_count == 0:
            action = "update"
        else:
            action = "replace_semantic_edge"
        actions.append(
            {
                "id": relation_id,
                "source_code": key[0],
                "relationType": key[1],
                "target_code": key[2],
                "existing_count": existing_count,
                "existing_relation_ids": existing_ids,
                "missing_id_count": missing_id_count,
                "action": action,
            }
        )
    return actions


def relation_rows_for_query(relations: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "id": str(relation.get("id", "")).strip(),
            "source_code": str(relation.get("source_code", "")).strip(),
            "relationType": str(relation.get("relationType", "")).strip(),
            "target_code": str(relation.get("target_code", "")).strip(),
        }
        for relation in relations
    ]


def precheck_by_relation_type(client: Neo4jHttpClient, relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in relation_rows_for_query(relations):
        grouped[row["relationType"]].append(row)
    output: list[dict[str, Any]] = []
    for relation_type, group_rows in sorted(grouped.items()):
        rel_type = cypher_name(relation_type)
        result = client.run(
            f"""
            UNWIND $rows AS row
            OPTIONAL MATCH (s:KGNode {{code: row.source_code}})
            OPTIONAL MATCH (t:KGNode {{code: row.target_code}})
            OPTIONAL MATCH (s)-[r:{rel_type}]->(t)
            RETURN
              row.source_code AS source_code,
              row.relationType AS relationType,
              row.target_code AS target_code,
              s.code AS source_found,
              t.code AS target_found,
              count(r) AS existing_count,
              collect(r.id) AS existing_relation_ids,
              sum(CASE WHEN r.id IS NULL THEN 1 ELSE 0 END) AS missing_id_count
            """,
            {"rows": group_rows},
        )
        output.extend(rows(result))
    return output


def import_delta_relations(
    client: Neo4jHttpClient,
    relations: list[dict[str, Any]],
    *,
    replace_semantic_edges: bool,
) -> dict[str, Any]:
    validate_delta_relations(relations)
    precheck_rows = precheck_by_relation_type(client, relations)
    missing_endpoints = [row for row in precheck_rows if not row.get("source_found") or not row.get("target_found")]
    if missing_endpoints:
        raise RuntimeError(f"Missing endpoint nodes for delta relations: {missing_endpoints}")
    actions = plan_delta_relation_actions(relations, precheck_rows)
    if any(action["action"] == "replace_semantic_edge" for action in actions) and not replace_semantic_edges:
        raise RuntimeError("Delta import would replace existing semantic edges; rerun with --replace-semantic-edges after review.")

    action_by_key = {
        (action["source_code"], action["relationType"], action["target_code"]): action
        for action in actions
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relation in relations:
        key = semantic_key(relation)
        grouped[key[1]].append(
            {
                "id": relation["id"],
                "source_code": key[0],
                "target_code": key[2],
                "props": cleaned_props(relation),
                "replace_existing": action_by_key[key]["action"] == "replace_semantic_edge",
            }
        )

    imported = 0
    deleted_legacy = 0
    for relation_type, group_rows in sorted(grouped.items()):
        rel_type = cypher_name(relation_type)
        if any(row["replace_existing"] for row in group_rows):
            result = client.run(
                f"""
                UNWIND $rows AS row
                MATCH (s:KGNode {{code: row.source_code}})-[r:{rel_type}]->(t:KGNode {{code: row.target_code}})
                WHERE row.replace_existing = true AND (r.id IS NULL OR r.id <> row.id)
                WITH collect(r) AS rels
                FOREACH (rel IN rels | DELETE rel)
                RETURN size(rels) AS deleted_count
                """,
                {"rows": group_rows},
            )
            deleted_legacy += int(rows(result)[0].get("deleted_count") or 0)
        result = client.run(
            f"""
            UNWIND $rows AS row
            MATCH (s:KGNode {{code: row.source_code}})
            MATCH (t:KGNode {{code: row.target_code}})
            MERGE (s)-[r:{rel_type} {{id: row.id}}]->(t)
            SET r += row.props
            RETURN count(r) AS merged_count
            """,
            {"rows": group_rows},
        )
        imported += int(rows(result)[0].get("merged_count") or 0)

    postcheck_rows = precheck_by_relation_type(client, relations)
    post_actions = plan_delta_relation_actions(relations, postcheck_rows)
    bad_postcheck = [row for row in postcheck_rows if int(row.get("existing_count") or 0) != 1]
    if bad_postcheck:
        raise RuntimeError(f"Postcheck failed; semantic key not unique: {bad_postcheck}")
    return {
        "input_relation_count": len(relations),
        "merged_relation_count": imported,
        "deleted_legacy_relationship_count": deleted_legacy,
        "precheck": precheck_rows,
        "actions": actions,
        "postcheck": postcheck_rows,
        "post_actions": post_actions,
    }


def import_delta_nodes(client: Neo4jHttpClient, nodes: list[dict[str, Any]], *, batch_size: int) -> dict[str, Any]:
    validate_delta_nodes(nodes)
    imported = import_nodes(client, nodes, batch_size)
    return {
        "input_node_count": len(nodes),
        "merged_node_count": imported,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Neo4j delta relationship JSONL with semantic-key de-duplication.")
    parser.add_argument("--delta-nodes-upsert", type=Path)
    parser.add_argument("--delta-relations-add", type=Path)
    parser.add_argument("--uri", default="http://192.168.3.27:7474")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--replace-semantic-edges", action="store_true")
    parser.add_argument("--summary-out", type=Path)
    args = parser.parse_args()
    if not args.password:
        parser.error("Neo4j password must be provided via --password or NEO4J_PASSWORD.")
    if not args.delta_nodes_upsert and not args.delta_relations_add:
        parser.error("At least one of --delta-nodes-upsert or --delta-relations-add is required.")

    client = Neo4jHttpClient(args.uri, args.username, args.password, args.database, 5, 1)
    summary: dict[str, Any] = {}
    if args.delta_nodes_upsert:
        nodes = read_jsonl(args.delta_nodes_upsert)
        summary["nodes"] = import_delta_nodes(client, nodes, batch_size=500)
    if args.delta_relations_add:
        relations = read_jsonl(args.delta_relations_add)
        summary["relations"] = import_delta_relations(client, relations, replace_semantic_edges=args.replace_semantic_edges)
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
