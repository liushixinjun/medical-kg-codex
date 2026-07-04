from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SAFE_TOKEN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def cypher_name(token: str) -> str:
    if not SAFE_TOKEN_RE.fullmatch(token or ""):
        raise ValueError(f"Unsafe Cypher token: {token!r}")
    return f"`{token}`"


def to_property_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        if all(item is None or isinstance(item, (str, int, float, bool)) for item in value):
            return [item for item in value if item is not None]
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def cleaned_props(row: dict[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for key, value in row.items():
        converted = to_property_value(value)
        if converted is not None:
            props[key] = converted
    return props


def canonical_node_labels(entity_type: str) -> list[str]:
    if not entity_type:
        raise ValueError("Node without entityType")
    cypher_name(entity_type)
    return ["KGNode", entity_type]


def cleaned_node_props(node: dict[str, Any]) -> dict[str, Any]:
    entity_type = node.get("entityType")
    labels = canonical_node_labels(entity_type)
    props = cleaned_props(node)
    props["primary_label"] = labels[0]
    props["type_label"] = labels[1]
    props["canonical_labels"] = labels
    return props


def type_label_set_clause(entity_type: str) -> str:
    return f"SET n:{cypher_name(entity_type)}"


class Neo4jHttpClient:
    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str,
        max_retries: int = 3,
        retry_delay_seconds: float = 2.0,
    ) -> None:
        uri = uri.rstrip("/")
        if "/db/" not in uri:
            uri = f"{uri}/db/{database}/tx/commit"
        self.uri = uri
        self.max_retries = max(0, max_retries)
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)
        auth = f"{username}:{password}".encode("utf-8")
        import base64

        self.headers = {
            "Authorization": "Basic " + base64.b64encode(auth).decode("ascii"),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def run(self, statement: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = json.dumps(
            {"statements": [{"statement": statement, "parameters": parameters or {}}]},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(self.uri, data=payload, headers=self.headers, method="POST")
        last_error: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    result = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Neo4j HTTP error {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.retry_delay_seconds)
        else:
            raise RuntimeError(f"Neo4j request failed: {last_error}")
        if result.get("errors"):
            raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False))
        return result


def chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def first_row(result: dict[str, Any]) -> list[Any]:
    data = result["results"][0]["data"]
    if not data:
        return []
    return data[0]["row"]


def count_kg_subgraph(client: Neo4jHttpClient) -> dict[str, int]:
    result = client.run(
        """
        MATCH (n:KGNode)
        WITH collect(n) AS nodes, count(n) AS node_count
        UNWIND CASE WHEN nodes = [] THEN [null] ELSE nodes END AS n
        OPTIONAL MATCH (n)-[r]-()
        RETURN node_count, count(DISTINCT r) AS relation_count
        """
    )
    row = first_row(result)
    return {"node_count": int(row[0] or 0), "relation_count": int(row[1] or 0)}


def audit_label_metadata(client: Neo4jHttpClient) -> dict[str, int]:
    result = client.run(
        """
        MATCH (n:KGNode)
        RETURN
          count(n) AS total_kg_node_count,
          sum(
            CASE
              WHEN n.primary_label = 'KGNode'
               AND n.type_label = n.entityType
               AND n.canonical_labels = ['KGNode', n.entityType]
              THEN 0 ELSE 1
            END
          ) AS canonical_label_metadata_mismatch_count,
          sum(
            CASE
              WHEN labels(n) = ['KGNode', n.entityType]
              THEN 0 ELSE 1
            END
          ) AS raw_label_order_differs_count
        """
    )
    row = first_row(result)
    return {
        "total_kg_node_count": int(row[0] or 0),
        "canonical_label_metadata_mismatch_count": int(row[1] or 0),
        "raw_label_order_differs_count": int(row[2] or 0),
    }


def replace_kg_subgraph(client: Neo4jHttpClient, batch_size: int) -> int:
    deleted_total = 0
    while True:
        result = client.run(
            """
            MATCH (n:KGNode)
            WITH n LIMIT $batch_size
            DETACH DELETE n
            RETURN count(n) AS deleted_node_count
            """,
            {"batch_size": batch_size},
        )
        row = first_row(result)
        deleted_count = int(row[0] or 0)
        deleted_total += deleted_count
        if deleted_count == 0:
            return deleted_total


def import_nodes(client: Neo4jHttpClient, nodes: list[dict[str, Any]], batch_size: int) -> int:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        entity_type = node.get("entityType")
        if not entity_type:
            raise ValueError(f"Node without entityType: {node.get('code')}")
        grouped[entity_type].append({"code": node["code"], "props": cleaned_node_props(node)})

    imported = 0
    for entity_type, rows in sorted(grouped.items()):
        type_label_clause = type_label_set_clause(entity_type)
        statement = f"""
        UNWIND $rows AS row
        MERGE (n:KGNode {{code: row.code}})
        SET n += row.props
        {type_label_clause}
        """
        for batch in chunks(rows, batch_size):
            client.run(statement, {"rows": batch})
            imported += len(batch)
    return imported


def import_relations(client: Neo4jHttpClient, relations: list[dict[str, Any]], batch_size: int) -> int:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rel in relations:
        relation_type = rel.get("relationType")
        if not relation_type:
            raise ValueError(f"Relation without relationType: {rel.get('id')}")
        grouped[relation_type].append(
            {
                "id": rel["id"],
                "source_code": rel["source_code"],
                "target_code": rel["target_code"],
                "props": cleaned_props(rel),
            }
        )

    imported = 0
    for relation_type, rows in sorted(grouped.items()):
        rel_type = cypher_name(relation_type)
        statement = f"""
        UNWIND $rows AS row
        MATCH (s:KGNode {{code: row.source_code}})
        MATCH (t:KGNode {{code: row.target_code}})
        MERGE (s)-[r:{rel_type}]->(t)
        SET r += row.props
        """
        for batch in chunks(rows, batch_size):
            client.run(statement, {"rows": batch})
            imported += len(batch)
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a generated medical KG batch into a Neo4j test database.")
    parser.add_argument("--batch-dir", required=True, type=Path)
    parser.add_argument("--uri", required=True, help="Neo4j HTTP URI, e.g. http://host:7474")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=float, default=2.0)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument(
        "--replace-kg-subgraph",
        action="store_true",
        help="Delete the existing KGNode subgraph before import so the database exactly matches this batch.",
    )
    args = parser.parse_args()
    if not args.password:
        parser.error("Neo4j password must be provided via --password or NEO4J_PASSWORD.")

    batch_dir = args.batch_dir.resolve()
    nodes_path = batch_dir / "05_data_instance" / "nodes_final.jsonl"
    relations_path = batch_dir / "05_data_instance" / "relations_final.jsonl"
    nodes = load_jsonl(nodes_path)
    relations = load_jsonl(relations_path)

    client = Neo4jHttpClient(
        args.uri,
        args.username,
        args.password,
        args.database,
        max_retries=args.max_retries,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    start = time.time()
    client.run("RETURN 1 AS ok")
    pre_replace_counts = count_kg_subgraph(client)
    deleted_kg_node_count = 0
    if args.replace_kg_subgraph:
        deleted_kg_node_count = replace_kg_subgraph(client, args.batch_size)
    client.run("CREATE CONSTRAINT kg_node_code IF NOT EXISTS FOR (n:KGNode) REQUIRE n.code IS UNIQUE")
    node_imported = import_nodes(client, nodes, args.batch_size)
    relation_imported = import_relations(client, relations, args.batch_size)

    count_result = client.run(
        """
        MATCH (n:KGNode)
        WITH count(n) AS node_count
        MATCH ()-[r]->()
        RETURN node_count, count(r) AS relation_count
        """
    )
    row = count_result["results"][0]["data"][0]["row"]
    label_metadata_audit = audit_label_metadata(client)
    summary = {
        "status": "imported",
        "batch_dir": str(batch_dir),
        "input_node_count": len(nodes),
        "input_relation_count": len(relations),
        "pre_replace_kg_node_count": pre_replace_counts["node_count"],
        "pre_replace_kg_relation_count": pre_replace_counts["relation_count"],
        "replace_kg_subgraph": args.replace_kg_subgraph,
        "deleted_kg_node_count": deleted_kg_node_count,
        "imported_node_rows": node_imported,
        "imported_relation_rows": relation_imported,
        "database_kg_node_count": row[0],
        "database_relation_count": row[1],
        "node_entity_type_counts": dict(Counter(node.get("entityType", "") for node in nodes)),
        "relation_type_counts": dict(Counter(rel.get("relationType", "") for rel in relations)),
        "label_metadata_audit": label_metadata_audit,
        "label_order_note": "Neo4j labels are unordered. Use canonical_labels/primary_label/type_label for review; raw labels(n) order is diagnostic only.",
        "elapsed_seconds": round(time.time() - start, 3),
        "import_mode": "replace_kg_subgraph" if args.replace_kg_subgraph else "idempotent_merge_no_delete",
    }
    summary_out = args.summary_out or batch_dir / "08_neo4j_import" / "neo4j_import_summary.json"
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
