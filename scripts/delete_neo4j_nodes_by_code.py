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


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete KGNode nodes by code from Neo4j test database.")
    parser.add_argument("--uri", default="http://192.168.3.27:7474")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--code", action="append", required=True)
    args = parser.parse_args()
    if not args.password:
        parser.error("Neo4j password must be provided via --password or NEO4J_PASSWORD.")

    client = Neo4jHttpClient(args.uri, args.username, args.password, args.database, 5, 1)
    query = """
    MATCH (n:KGNode)
    WHERE n.code IN $codes
    WITH collect(n.code) AS codes, collect(n) AS nodes
    FOREACH (node IN nodes | DETACH DELETE node)
    RETURN codes AS deleted_codes, size(codes) AS deleted_count
    """
    result = client.run(query, {"codes": args.code})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
