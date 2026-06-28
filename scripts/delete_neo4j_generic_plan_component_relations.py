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


QUERY = """
MATCH (p:KGNode {entityType:'TreatmentPlan'})-[r]->(t:KGNode)
WHERE p.name ENDS WITH '治疗方案'
  AND type(r) IN ['includes_medication', 'includes_procedure']
WITH collect(r) AS rels
FOREACH (rel IN rels | DELETE rel)
RETURN size(rels) AS deleted_count
"""


def rows(result: dict) -> list[dict]:
    return [
        {col: item["row"][idx] for idx, col in enumerate(result["results"][0]["columns"])}
        for item in result["results"][0]["data"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete executable component relations copied under generic disease-level treatment plans.")
    parser.add_argument("--uri", default="http://192.168.3.27:7474")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    if not args.password:
        parser.error("Neo4j password must be provided via --password or NEO4J_PASSWORD.")
    client = Neo4jHttpClient(args.uri, args.username, args.password, args.database, 5, 1)
    print(json.dumps(rows(client.run(QUERY)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
