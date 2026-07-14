# -*- coding: utf-8 -*-
"""冠心病剩余病种教材骨架精修批次服务器复核。

只读查询 Neo4j，不修改服务器数据。
环境变量：
- NEO4J_URI
- NEO4J_USERNAME
- NEO4J_PASSWORD
- CAD_REMAINING_BATCH_ID
- CAD_REMAINING_POSTCHECK_OUT
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient  # noqa: E402


DEFAULT_BATCH_ID = "BATCH-CARD-CAD-REMAINING-20260712-001"
DISEASE_CODES = [
    "DIS-CARD-CAD-ACS",
    "DIS-CARD-CAD-AMI",
    "DIS-CARD-CAD-UA",
    "DIS-CARD-CAD-NSTEMI",
    "DIS-CARD-CAD-CCS",
    "DIS-CARD-CAD-STABLE-ANGINA",
    "DIS-CARD-CAD-ICM",
    "DIS-CARD-CAD-SILENT-ISCHEMIA",
    "DIS-CARD-CAD-OLD-MI",
]


def rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    columns = result["results"][0]["columns"]
    return [{col: item["row"][idx] for idx, col in enumerate(columns)} for item in result["results"][0]["data"]]


def scalar(client: Neo4jHttpClient, statement: str, params: dict[str, Any] | None = None) -> Any:
    data = rows(client.run(statement, params or {}))
    if not data:
        return None
    return next(iter(data[0].values()))


def main() -> int:
    uri = os.environ.get("NEO4J_URI", "http://192.168.3.27:7474")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    batch_id = os.environ.get("CAD_REMAINING_BATCH_ID", DEFAULT_BATCH_ID)
    out_path = Path(os.environ.get("CAD_REMAINING_POSTCHECK_OUT", "cad_remaining_postcheck_summary.json"))
    if not password:
        raise SystemExit("NEO4J_PASSWORD is required")

    client = Neo4jHttpClient(uri, username, password, "neo4j", 5, 1)
    summary: dict[str, Any] = {
        "batch_id": batch_id,
        "batch_node_count": scalar(client, "MATCH (n:KGNode {batch_id:$batch_id}) RETURN count(n)", {"batch_id": batch_id}),
        "batch_relation_count": scalar(client, "MATCH ()-[r {batch_id:$batch_id}]->() RETURN count(r)", {"batch_id": batch_id}),
    }
    summary["node_entity_type_counts"] = rows(
        client.run(
            """
            MATCH (n:KGNode {batch_id:$batch_id})
            RETURN n.entityType AS entityType, count(n) AS count
            ORDER BY entityType
            """,
            {"batch_id": batch_id},
        )
    )
    summary["relation_type_counts"] = rows(
        client.run(
            """
            MATCH ()-[r {batch_id:$batch_id}]->()
            RETURN type(r) AS relationType, count(r) AS count
            ORDER BY relationType
            """,
            {"batch_id": batch_id},
        )
    )
    summary["disease_relation_coverage"] = rows(
        client.run(
            """
            UNWIND $codes AS code
            MATCH (d:KGNode {code:code})
            OPTIONAL MATCH (d)-[r {batch_id:$batch_id}]->(t:KGNode)
            WITH d, type(r) AS relationType, count(r) AS count
            RETURN d.code AS disease_code, d.name AS disease_name, relationType, count
            ORDER BY disease_code, relationType
            """,
            {"batch_id": batch_id, "codes": DISEASE_CODES},
        )
    )
    summary["diagnostic_component_coverage"] = rows(
        client.run(
            """
            UNWIND $codes AS code
            MATCH (d:KGNode {code:code})
            OPTIONAL MATCH (d)-[:has_diagnostic_criteria {batch_id:$batch_id}]->(dx:KGNode)
            OPTIONAL MATCH (dx)-[:has_diagnostic_component {batch_id:$batch_id}]->(c:KGNode)
            RETURN d.code AS disease_code, d.name AS disease_name, count(DISTINCT dx) AS diagnostic_criteria_count, count(DISTINCT c) AS diagnostic_component_count
            ORDER BY disease_code
            """,
            {"batch_id": batch_id, "codes": DISEASE_CODES},
        )
    )

    hard_gates = {
        "non_kg_node_batch_count": scalar(
            client,
            "MATCH (n {batch_id:$batch_id}) WHERE NOT n:KGNode RETURN count(n)",
            {"batch_id": batch_id},
        ),
        "generic_has_related_entity_count": scalar(
            client,
            "MATCH ()-[r:has_related_entity {batch_id:$batch_id}]->() RETURN count(r)",
            {"batch_id": batch_id},
        ),
        "duplicate_semantic_relation_count": scalar(
            client,
            """
            MATCH (s:KGNode)-[r {batch_id:$batch_id}]->(t:KGNode)
            WITH s.code AS s, type(r) AS rt, t.code AS t, count(r) AS c
            WHERE c > 1
            RETURN count(*)
            """,
            {"batch_id": batch_id},
        ),
        "diagnosis_criteria_without_component_count": scalar(
            client,
            """
            MATCH (dx:KGNode {batch_id:$batch_id, entityType:'DiagnosisCriteria'})
            WHERE NOT (dx)-[:has_diagnostic_component]->(:KGNode)
            RETURN count(dx)
            """,
            {"batch_id": batch_id},
        ),
        "evidence_without_text_count": scalar(
            client,
            """
            MATCH (e:KGNode {batch_id:$batch_id, entityType:'Evidence'})
            WHERE e.evidence_text IS NULL OR trim(toString(e.evidence_text)) = ''
            RETURN count(e)
            """,
            {"batch_id": batch_id},
        ),
        "short_entity_too_long_count": scalar(
            client,
            """
            MATCH (n:KGNode {batch_id:$batch_id})
            WHERE n.entityType IN ['Symptom','Sign','Exam','LabTest','Medication','Procedure','RiskFactor','Complication']
              AND size(toString(n.name)) > 32
            RETURN count(n)
            """,
            {"batch_id": batch_id},
        ),
    }
    summary["hard_gates"] = hard_gates
    summary["hard_gate_pass"] = all(int(v or 0) == 0 for v in hard_gates.values())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["hard_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
