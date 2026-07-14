# -*- coding: utf-8 -*-
"""服务器复核 STEMI 教材骨架精修结果。

读取环境变量：
- NEO4J_URI
- NEO4J_USERNAME
- NEO4J_PASSWORD
- STEMI_BATCH_ID
- STEMI_POSTCHECK_OUT

只读查询 Neo4j，不写数据库。
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

from scripts.import_neo4j_test_db import Neo4jHttpClient


def rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {col: item["row"][idx] for idx, col in enumerate(result["results"][0]["columns"])}
        for item in result["results"][0]["data"]
    ]


def main() -> int:
    batch_id = os.environ["STEMI_BATCH_ID"]
    client = Neo4jHttpClient(
        os.environ["NEO4J_URI"],
        os.environ["NEO4J_USERNAME"],
        os.environ["NEO4J_PASSWORD"],
        "neo4j",
        3,
        1,
    )

    def one(query: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return rows(client.run(query, params or {}))[0]

    summary: dict[str, Any] = {}
    summary["batch_node_count"] = one(
        "MATCH (n:KGNode {batch_id:$batch_id}) RETURN count(n) AS c",
        {"batch_id": batch_id},
    )["c"]
    summary["batch_relation_count"] = one(
        "MATCH ()-[r {batch_id:$batch_id}]->() RETURN count(r) AS c",
        {"batch_id": batch_id},
    )["c"]
    summary["node_type_count"] = rows(
        client.run(
            "MATCH (n:KGNode {batch_id:$batch_id}) "
            "RETURN n.entityType AS entityType, count(n) AS c ORDER BY entityType",
            {"batch_id": batch_id},
        )
    )
    summary["diagnostic_component_count"] = one(
        "MATCH (:KGNode {code:'DIS-CARD-CAD-STEMI'})-[:has_diagnostic_criteria]->"
        "(dx:KGNode)-[:has_diagnostic_component]->(c:KGNode) "
        "RETURN count(DISTINCT c) AS c"
    )["c"]
    summary["diagnostic_components"] = rows(
        client.run(
            "MATCH (:KGNode {code:'DIS-CARD-CAD-STEMI'})-[:has_diagnostic_criteria]->"
            "(dx:KGNode)-[:has_diagnostic_component]->(c:KGNode) "
            "RETURN c.name AS name ORDER BY name"
        )
    )
    summary["differential_count"] = one(
        "MATCH (:KGNode {code:'DIS-CARD-CAD-STEMI'})-[:differentiates_from]->(d:KGNode) "
        "RETURN count(DISTINCT d) AS c"
    )["c"]
    summary["differentials"] = rows(
        client.run(
            "MATCH (:KGNode {code:'DIS-CARD-CAD-STEMI'})-[:differentiates_from]->(d:KGNode) "
            "RETURN d.name AS name ORDER BY name"
        )
    )
    summary["specific_thrombolytic_medication_count"] = one(
        "MATCH (m:KGNode {name:'溶栓药物', batch_id:$batch_id})-[:has_specific_medication]->(x:KGNode) "
        "RETURN count(DISTINCT x) AS c",
        {"batch_id": batch_id},
    )["c"]
    summary["specific_thrombolytic_medications"] = rows(
        client.run(
            "MATCH (m:KGNode {name:'溶栓药物', batch_id:$batch_id})-[:has_specific_medication]->(x:KGNode) "
            "RETURN x.name AS name, x.dose_text AS dose_text, x.aliases AS aliases ORDER BY x.name",
            {"batch_id": batch_id},
        )
    )
    summary["contraindication_count"] = one(
        "MATCH (n:KGNode {batch_id:$batch_id, entityType:'Contraindication'}) RETURN count(n) AS c",
        {"batch_id": batch_id},
    )["c"]
    summary["blocks_action_count"] = one(
        "MATCH ()-[r:blocks_action {batch_id:$batch_id}]->() RETURN count(r) AS c",
        {"batch_id": batch_id},
    )["c"]
    summary["clinical_rule_count"] = one(
        "MATCH (n:KGNode {batch_id:$batch_id, entityType:'ClinicalRule'}) RETURN count(n) AS c",
        {"batch_id": batch_id},
    )["c"]
    summary["clinical_rule_with_derived_from_count"] = one(
        "MATCH (n:KGNode {batch_id:$batch_id, entityType:'ClinicalRule'})-[:derived_from]->"
        "(:KGNode {entityType:'Evidence'}) RETURN count(DISTINCT n) AS c",
        {"batch_id": batch_id},
    )["c"]
    summary["generic_has_related_entity_count"] = one(
        "MATCH ()-[r:has_related_entity {batch_id:$batch_id}]->() RETURN count(r) AS c",
        {"batch_id": batch_id},
    )["c"]
    summary["template_exclusion_phrase_count"] = one(
        "MATCH (n:KGNode {batch_id:$batch_id}) "
        "WHERE coalesce(n.exclusion_criteria,'') CONTAINS '禁忌证、出血风险或关键患者数据缺失时' "
        "   OR coalesce(n.contraindication_text,'') CONTAINS '禁忌证、出血风险或关键患者数据缺失时' "
        "   OR coalesce(n.rule_logic,'') CONTAINS '禁忌证、出血风险或关键患者数据缺失时' "
        "   OR coalesce(n.recommendation_text,'') CONTAINS '禁忌证、出血风险或关键患者数据缺失时' "
        "RETURN count(n) AS c",
        {"batch_id": batch_id},
    )["c"]

    summary["hard_gate_pass"] = all(
        [
            summary["batch_node_count"] >= 203,
            summary["batch_relation_count"] >= 430,
            summary["diagnostic_component_count"] >= 5,
            summary["differential_count"] >= 7,
            summary["specific_thrombolytic_medication_count"] >= 5,
            summary["contraindication_count"] >= 10,
            summary["blocks_action_count"] >= 4,
            summary["clinical_rule_count"] == summary["clinical_rule_with_derived_from_count"],
            summary["generic_has_related_entity_count"] == 0,
            summary["template_exclusion_phrase_count"] == 0,
        ]
    )

    out = Path(os.environ["STEMI_POSTCHECK_OUT"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["hard_gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
