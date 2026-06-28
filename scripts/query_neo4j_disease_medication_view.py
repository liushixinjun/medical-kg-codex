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
MATCH (d:KGNode {entityType:'Disease', name:$disease_name})
OPTIONAL MATCH direct=(d)-[r1:treated_by_medication]->(m1:KGNode {entityType:'Medication'})
WITH d, collect({path:'direct', relation:type(r1), medication:m1.name, code:m1.code}) AS direct_rows
OPTIONAL MATCH via_plan=(d)-[:has_treatment_plan]->(p:KGNode {entityType:'TreatmentPlan'})-[r2:includes_medication]->(m2:KGNode {entityType:'Medication'})
WITH d, direct_rows, collect({path:'via_plan', relation:type(r2), plan:p.name, medication:m2.name, code:m2.code}) AS plan_rows
WITH d, [row IN direct_rows + plan_rows WHERE row.medication IS NOT NULL] AS rows
UNWIND rows AS row
WITH row.medication AS medication, row.code AS code, collect(row) AS appearances, count(*) AS path_count
RETURN medication, collect(DISTINCT code) AS codes, path_count, appearances
ORDER BY path_count DESC, medication
"""


def rows(result: dict) -> list[dict]:
    return [
        {col: item["row"][idx] for idx, col in enumerate(result["results"][0]["columns"])}
        for item in result["results"][0]["data"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Query disease medication paths and duplicate appearances from Neo4j.")
    parser.add_argument("--disease-name", required=True)
    parser.add_argument("--uri", default="http://192.168.3.27:7474")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    if not args.password:
        parser.error("Neo4j password must be provided via --password or NEO4J_PASSWORD.")

    client = Neo4jHttpClient(args.uri, args.username, args.password, args.database, 5, 1)
    result = rows(client.run(QUERY, {"disease_name": args.disease_name}))
    summary = {
        "disease_name": args.disease_name,
        "unique_medication_name_count": len(result),
        "duplicated_medication_name_count": sum(1 for row in result if row["path_count"] > 1),
        "total_medication_path_count": sum(row["path_count"] for row in result),
        "rows": result,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
