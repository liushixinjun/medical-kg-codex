from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient


COUNT_QUERY = """
MATCH (s:KGNode)-[r]->(t:KGNode)
WITH s.code AS source_code, type(r) AS relation_type, t.code AS target_code, count(r) AS c
WHERE c > 1
RETURN count(*) AS duplicate_semantic_keys, sum(c - 1) AS redundant_relationship_count
"""


SAMPLE_QUERY = """
MATCH (s:KGNode)-[r]->(t:KGNode)
WITH s.code AS source_code, s.name AS source_name, type(r) AS relation_type, t.code AS target_code, t.name AS target_name, count(r) AS c
WHERE c > 1
RETURN source_code, source_name, relation_type, target_code, target_name, c
ORDER BY c DESC, relation_type, source_name, target_name
LIMIT 50
"""


DEDUPE_QUERY = """
MATCH (s:KGNode)-[r]->(t:KGNode)
WITH s, t, type(r) AS relation_type, collect(r) AS rels
WHERE size(rels) > 1
FOREACH (rel IN tail(rels) | DELETE rel)
RETURN count(*) AS deduped_semantic_keys, sum(size(rels) - 1) AS deleted_relationship_count
"""


def rows(result: dict) -> list[dict]:
    return [
        {col: item["row"][idx] for idx, col in enumerate(result["results"][0]["columns"])}
        for item in result["results"][0]["data"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Dedupe Neo4j relationships by source code + relation type + target code.")
    parser.add_argument("--uri", default="http://192.168.3.27:7474")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("Neo4j password must be provided via --password or NEO4J_PASSWORD.")

    client = Neo4jHttpClient(args.uri, args.username, args.password, args.database, 5, 1)
    output = {
        "before": rows(client.run(COUNT_QUERY)),
        "sample": rows(client.run(SAMPLE_QUERY)),
    }
    if args.apply:
        output["dedupe"] = rows(client.run(DEDUPE_QUERY))
        output["after"] = rows(client.run(COUNT_QUERY))
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
