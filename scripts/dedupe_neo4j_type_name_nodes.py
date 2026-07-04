from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient, cypher_name, first_row


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    http = re.search(r"http://[^\s；;]+", text)
    username = re.search(r"(?:用户名|username)\s*[:：]\s*([^\s；;]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s；;]+)", text, re.I)
    if not http or not password:
        raise ValueError(f"Connection file missing HTTP URI or password: {path}")
    return {
        "uri": http.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def rows(result: dict[str, Any]) -> list[list[Any]]:
    return [item["row"] for item in result["results"][0]["data"]]


def find_duplicate_groups(client: Neo4jHttpClient) -> list[dict[str, Any]]:
    result = client.run(
        """
        MATCH (n:KGNode)
        WHERE n.entityType IS NOT NULL AND n.name IS NOT NULL
        WITH n.entityType AS entity_type, n.name AS name,
             collect({
               code:n.code,
               batch_id:n.batch_id,
               entityType:n.entityType,
               name:n.name,
               source_type:n.source_type,
               source_name:n.source_name,
               created_time:n.created_time
             }) AS nodes,
             count(n) AS c
        WHERE c > 1
        RETURN entity_type, name, c, nodes
        ORDER BY entity_type, name
        """
    )
    groups = []
    for entity_type, name, count, nodes in rows(result):
        groups.append({"entityType": entity_type, "name": name, "count": count, "nodes": nodes})
    return groups


def choose_canonical(nodes: list[dict[str, Any]], prefer_existing_over_batch: str | None) -> dict[str, Any]:
    def score(node: dict[str, Any]) -> tuple[int, int, str]:
        batch_id = str(node.get("batch_id") or "")
        prefer_existing = 0 if prefer_existing_over_batch and batch_id != prefer_existing_over_batch else 1
        code = str(node.get("code") or "")
        stable_code = 0 if not code.startswith(("MED-CARD-", "PROC-CARD-", "PLAN-CARD-")) else 1
        return (prefer_existing, stable_code, code)

    return sorted(nodes, key=score)[0]


def get_node_props(client: Neo4jHttpClient, code: str) -> dict[str, Any]:
    result = client.run("MATCH (n:KGNode {code:$code}) RETURN properties(n)", {"code": code})
    row = first_row(result)
    return dict(row[0] or {}) if row else {}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def merge_canonical_properties(client: Neo4jHttpClient, canonical_code: str, duplicate_code: str) -> None:
    canonical = get_node_props(client, canonical_code)
    duplicate = get_node_props(client, duplicate_code)
    aliases = []
    for value in (
        canonical.get("aliases"),
        duplicate.get("aliases"),
        duplicate.get("name"),
        duplicate.get("preferred_name"),
        duplicate.get("display_name"),
        duplicate.get("abbr"),
    ):
        aliases.extend(as_list(value))
    seen = set()
    merged_aliases = []
    for alias in aliases:
        text = str(alias).strip()
        if text and text != canonical.get("name") and text not in seen:
            seen.add(text)
            merged_aliases.append(text)

    merged_codes = as_list(canonical.get("merged_duplicate_codes")) + [duplicate_code]
    merged_batches = as_list(canonical.get("merged_duplicate_batch_ids")) + as_list(duplicate.get("batch_id"))
    client.run(
        """
        MATCH (n:KGNode {code:$code})
        SET n.aliases = $aliases,
            n.merged_duplicate_codes = $merged_codes,
            n.merged_duplicate_batch_ids = $merged_batches,
            n.merge_status = 'validated',
            n.last_dedupe_at = $dedupe_at
        """,
        {
            "code": canonical_code,
            "aliases": sorted(set(merged_aliases)),
            "merged_codes": sorted(set(str(item) for item in merged_codes if item)),
            "merged_batches": sorted(set(str(item) for item in merged_batches if item)),
            "dedupe_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


def relationship_rows(client: Neo4jHttpClient, duplicate_code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    outgoing = client.run(
        """
        MATCH (d:KGNode {code:$code})-[r]->(t:KGNode)
        RETURN type(r), properties(r), t.code
        """,
        {"code": duplicate_code},
    )
    incoming = client.run(
        """
        MATCH (s:KGNode)-[r]->(d:KGNode {code:$code})
        RETURN type(r), properties(r), s.code
        """,
        {"code": duplicate_code},
    )
    out_rows = [
        {"type": row[0], "props": row[1] or {}, "target_code": row[2]} for row in rows(outgoing)
    ]
    in_rows = [
        {"type": row[0], "props": row[1] or {}, "source_code": row[2]} for row in rows(incoming)
    ]
    return out_rows, in_rows


def merge_duplicate_node(client: Neo4jHttpClient, canonical_code: str, duplicate_code: str) -> dict[str, int]:
    outgoing, incoming = relationship_rows(client, duplicate_code)
    created_outgoing = 0
    created_incoming = 0
    for rel in outgoing:
        target_code = rel["target_code"]
        if target_code == canonical_code:
            continue
        rel_type = cypher_name(rel["type"])
        client.run(
            f"""
            MATCH (c:KGNode {{code:$canonical_code}})
            MATCH (t:KGNode {{code:$target_code}})
            MERGE (c)-[r:{rel_type}]->(t)
            SET r += $props
            """,
            {"canonical_code": canonical_code, "target_code": target_code, "props": rel["props"]},
        )
        created_outgoing += 1
    for rel in incoming:
        source_code = rel["source_code"]
        if source_code == canonical_code:
            continue
        rel_type = cypher_name(rel["type"])
        client.run(
            f"""
            MATCH (s:KGNode {{code:$source_code}})
            MATCH (c:KGNode {{code:$canonical_code}})
            MERGE (s)-[r:{rel_type}]->(c)
            SET r += $props
            """,
            {"canonical_code": canonical_code, "source_code": source_code, "props": rel["props"]},
        )
        created_incoming += 1
    merge_canonical_properties(client, canonical_code, duplicate_code)
    client.run("MATCH (d:KGNode {code:$code}) DETACH DELETE d", {"code": duplicate_code})
    return {
        "outgoing_transferred": created_outgoing,
        "incoming_transferred": created_incoming,
        "deleted_nodes": 1,
    }


def dedupe_type_name_nodes(
    client: Neo4jHttpClient,
    *,
    apply: bool,
    prefer_existing_over_batch: str | None,
) -> dict[str, Any]:
    groups = find_duplicate_groups(client)
    operations = []
    totals = {"outgoing_transferred": 0, "incoming_transferred": 0, "deleted_nodes": 0}
    for group in groups:
        canonical = choose_canonical(group["nodes"], prefer_existing_over_batch)
        canonical_code = canonical["code"]
        duplicate_codes = [node["code"] for node in group["nodes"] if node["code"] != canonical_code]
        op = {
            "entityType": group["entityType"],
            "name": group["name"],
            "canonical_code": canonical_code,
            "duplicate_codes": duplicate_codes,
            "applied": apply,
        }
        if apply:
            merge_counts = {"outgoing_transferred": 0, "incoming_transferred": 0, "deleted_nodes": 0}
            for duplicate_code in duplicate_codes:
                counts = merge_duplicate_node(client, canonical_code, duplicate_code)
                for key, value in counts.items():
                    merge_counts[key] += value
                    totals[key] += value
            op.update(merge_counts)
        operations.append(op)
    return {
        "duplicate_group_count": len(groups),
        "operation_count": sum(len(item["duplicate_codes"]) for item in operations),
        "applied": apply,
        **totals,
        "operations": operations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dedupe Neo4j KGNode entities by entityType + name.")
    parser.add_argument("--connection-file", type=Path, required=True)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prefer-existing-over-batch")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = parse_connection_file(args.connection_file)
    client = Neo4jHttpClient(conn["uri"], conn["username"], conn["password"], args.database)
    summary = dedupe_type_name_nodes(
        client,
        apply=args.apply,
        prefer_existing_over_batch=args.prefer_existing_over_batch,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "neo4j_type_name_dedupe_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "operations"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
