from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "公共执行层_kg_pipeline" / "AMI与心肌病样板收口.py"
OUTPUT = Path(__file__).with_name("样板缺口只读核查结果.json")

spec = importlib.util.spec_from_file_location("sample_closure", MODULE)
assert spec and spec.loader
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)

config = closure.read_connection_file(ROOT / "图谱数据库链接.txt")

QUERIES = {
    "invalid_lab_relations_in_scope": """
        MATCH (d:Disease)-[:has_exam_plan]->(p:ExamPlan)
        WHERE d.code IN $codes
        MATCH path=(p)-[:includes_lab_item|lab_item_has_subitem*1..3]->(n)
        UNWIND relationships(path) AS r
        WITH DISTINCT d,startNode(r) AS source,r,endNode(r) AS target
        WHERE type(r)='lab_item_has_subitem'
          AND (NOT source:LabItem OR NOT target:LabSubitem)
        RETURN d.code AS disease_code,
               labels(source) AS source_labels, source.code AS source_code,
               source.name AS source_name, type(r) AS relation_type,
               labels(target) AS target_labels, target.code AS target_code,
               target.name AS target_name, properties(r) AS relation_properties
        ORDER BY disease_code,source_code,target_code
    """,
    "orphan_parent_subitems": """
        MATCH (s:LabSubitem)
        WHERE s.code IN $subitem_codes
        OPTIONAL MATCH (li:LabItem)-[:lab_item_has_subitem]->(s)
        OPTIONAL MATCH (s)-[r]->(target)
        RETURN s.code AS subitem_code, s.name AS subitem_name,
               labels(s) AS labels, properties(s) AS properties,
               collect(DISTINCT {
                 parent_code:li.code,parent_name:li.name
               }) AS parents,
               collect(DISTINCT {
                 relation:type(r),target_labels:labels(target),
                 target_code:target.code,target_name:target.name,
                 target_properties:properties(target)
               }) AS outgoing
        ORDER BY subitem_code
    """,
    "missing_content_evidence": """
        MATCH (e:Evidence)
        WHERE e.disease_code IN $missing_content_codes
          AND coalesce(e.status,'') <> 'deprecated'
          AND (
            toLower(coalesce(e.source_section,'')) IN [
              'clinical_manifestation','diagnostic_criteria',
              'differential_diagnosis','treatment_plan','definition'
            ]
            OR e.evidence_text CONTAINS '鉴别'
            OR e.evidence_text CONTAINS '诊断'
            OR e.evidence_text CONTAINS '治疗'
            OR e.evidence_text CONTAINS '临床表现'
          )
        RETURN e.disease_code AS disease_code, e.code AS evidence_code,
               e.source_name AS source_name, e.source_type AS source_type,
               e.source_page AS source_page, e.source_section AS source_section,
               left(coalesce(e.evidence_text,''),1500) AS evidence_text
        ORDER BY disease_code,source_name,source_page
    """,
    "existing_standard_diagnoses": """
        MATCH (sd:StandardDiagnosis)
        WHERE coalesce(sd.status,'active') <> 'deprecated'
          AND (
            sd.code STARTS WITH 'I42'
            OR sd.code STARTS WITH 'E75.2'
            OR sd.code STARTS WITH 'E85'
            OR sd.name CONTAINS '心肌病'
            OR sd.name CONTAINS '淀粉样'
            OR sd.name CONTAINS '法布'
          )
        RETURN sd.code AS code, sd.name AS name,
               coalesce(sd.cdss_dict_id,sd.standard_dict_id) AS cdss_dict_id,
               coalesce(sd.valid_flag,sd.validFlag) AS valid_flag,
               sd.source_table AS source_table, sd.status AS status,
               properties(sd) AS properties
        ORDER BY code,name
    """,
    "scope_outgoing_summary": """
        MATCH (d:Disease)
        WHERE d.code IN $codes AND coalesce(d.status,'') <> 'deprecated'
        OPTIONAL MATCH (d)-[r]->(target)
        WHERE coalesce(target.status,'') <> 'deprecated'
        RETURN d.code AS disease_code,d.name AS disease_name,
               type(r) AS relation_type,labels(target) AS target_labels,
               count(DISTINCT target) AS target_count
        ORDER BY disease_code,relation_type
    """,
    "lab_analyte_direct_usage": """
        MATCH (p:ExamPlan)-[r:includes_lab_item]->(n)
        WHERE n.code IN $analyte_codes
        OPTIONAL MATCH (d:Disease)-[:has_exam_plan]->(p)
        RETURN n.code AS code,n.name AS name,
               count(DISTINCT r) AS incoming_plan_count,
               collect(DISTINCT d.code) AS disease_codes
        ORDER BY code
    """,
}


def main() -> None:
    payload: dict[str, object] = {}
    with GraphDatabase.driver(
        config["uri"], auth=(config["username"], config["password"])
    ) as driver:
        with driver.session() as session:
            common = {
                "codes": sorted(closure.SCOPE_CODES),
                "subitem_codes": [
                    "CARD-SKELETON-20260709-LABTEST-AD6A34F25F521595",
                    "LAB-CARD-1BE2B3C08B76",
                    "LAB-CARD-2E1F4EC42626",
                    "LAB-CARD-BF2619C772EC",
                    "IND-NT-PROBNP",
                ],
                "missing_content_codes": [
                    "DIS-CARD-CM-ABVC",
                    "DIS-CARD-CM-ATRIAL",
                    "DIS-CARD-CM-FABRY",
                    "DIS-CARD-CM-GENERAL",
                    "DIS-CARD-CM-NDLVCM",
                ],
                "analyte_codes": [
                    "CARD-SKELETON-20260709-LABTEST-70C17E9844CB4791",
                    "LAB-CARD-960C7CE8E22B",
                    "LAB-CARD-STEMI-4BA28B772105",
                ],
            }
            for name, query in QUERIES.items():
                parameters = {
                    key: value
                    for key, value in common.items()
                    if f"${key}" in query
                }
                payload[name] = [
                    dict(record) for record in session.run(query, **parameters)
                ]
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: len(value) if isinstance(value, list) else None
                for key, value in payload.items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
