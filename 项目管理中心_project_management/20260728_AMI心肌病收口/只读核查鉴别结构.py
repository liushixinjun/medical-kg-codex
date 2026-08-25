from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "AMI与心肌病样板收口.py"
spec = importlib.util.spec_from_file_location("sample_closure", MODULE_PATH)
assert spec and spec.loader
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)

config = closure.read_connection_file(ROOT / "图谱数据库链接.txt")
driver = GraphDatabase.driver(
    config["uri"], auth=(config["username"], config["password"])
)
try:
    with driver.session() as session:
        rows = [
            dict(record)
            for record in session.run(
                """
                MATCH (d:Disease)-[r:differentiates_from|has_differential_diagnosis]->(x)
                WHERE d.code STARTS WITH 'DIS-CARD-CM-'
                  AND coalesce(d.status,'') <> 'deprecated'
                  AND coalesce(x.status,'') <> 'deprecated'
                OPTIONAL MATCH (x)-[:has_differential_rule]->(rule)
                OPTIONAL MATCH (x)-[:supported_by_evidence]->(e:Evidence)
                RETURN d.code AS disease_code,d.name AS disease_name,
                       type(r) AS relation_type,labels(x) AS target_labels,
                       x.code AS target_code,x.name AS target_name,
                       properties(x) AS target_properties,
                       collect(DISTINCT {
                         code:rule.code,name:rule.name,
                         description:coalesce(rule.description,rule.rule_text)
                       }) AS rules,
                       collect(DISTINCT {
                         evidence_id:coalesce(e.evidence_id,e.code),
                         source_name:e.source_name,source_page:e.source_page
                       }) AS evidence
                ORDER BY disease_code,target_name
                """
            )
        ]
        evidence_candidates = [
            dict(record)
            for record in session.run(
                """
                MATCH (e:Evidence)
                WHERE e.disease_code IN $codes
                  AND coalesce(e.status,'') <> 'deprecated'
                  AND any(term IN ['鉴别','排除','区别','误诊','相似','诊断']
                          WHERE coalesce(e.evidence_text,e.text_excerpt,'') CONTAINS term)
                RETURN DISTINCT e.disease_code AS disease_code,
                       e.disease_name AS disease_name,
                       coalesce(e.evidence_id,e.code) AS evidence_id,
                       e.source_name AS source_name,e.source_page AS source_page,
                       e.source_section AS source_section,
                       coalesce(e.evidence_text,e.text_excerpt,'') AS evidence_text
                ORDER BY disease_code,source_name,source_page
                """,
                codes=[
                    "DIS-CARD-CM-ABVC",
                    "DIS-CARD-CM-ATRIAL",
                    "DIS-CARD-CM-FABRY",
                    "DIS-CARD-CM-GENERAL",
                    "DIS-CARD-CM-NDLVCM",
                ],
            )
        ]
finally:
    driver.close()

out = Path(__file__).with_name("鉴别诊断结构样例.json")
out.write_text(
    json.dumps(
        {"existing_structures": rows, "evidence_candidates": evidence_candidates},
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(
    json.dumps(
        {
            "existing_structures": len(rows),
            "evidence_candidates": len(evidence_candidates),
            "output": str(out),
        },
        ensure_ascii=False,
    )
)
