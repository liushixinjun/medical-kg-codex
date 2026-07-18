#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读盘点 V2.0 疾病层级迁移所需的服务器现状。"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
BACKUP_MODULE = ROOT / "公共执行层_kg_pipeline" / "Neo4j全量逻辑备份.py"


def load_connection_parser() -> Any:
    spec = importlib.util.spec_from_file_location("neo4j_backup", BACKUP_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载连接解析模块：{BACKUP_MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_connection_file


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else ["无数据"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def rows(session: Any, cypher: str) -> list[dict[str, Any]]:
    return [dict(record) for record in session.run(cypher)]


def main() -> int:
    parser = argparse.ArgumentParser(description="只读盘点 V2.0 疾病层级迁移现状")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "10_迁移前全量疾病盘点")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    parse_connection_file = load_connection_parser()
    connection = parse_connection_file(args.connection_file.resolve())

    driver = GraphDatabase.driver(
        connection["uri"], auth=(connection["username"], connection["password"])
    )
    try:
        driver.verify_connectivity()
        with driver.session(database="neo4j", default_access_mode="READ") as session:
            entity_counts = rows(
                session,
                """
                MATCH (n:KGNode)
                WHERE n.entityType IN [
                  'Specialty','DiseaseCategory','DiseaseSubcategory',
                  'DiseaseClassification','Disease','StandardDiagnosis'
                ]
                RETURN n.entityType AS entity_type, count(*) AS count
                ORDER BY entity_type
                """,
            )
            structural_relation_counts = rows(
                session,
                """
                MATCH (source)-[r]->(target)
                WHERE source.entityType IN [
                  'Specialty','DiseaseCategory','DiseaseSubcategory',
                  'DiseaseClassification','Disease'
                ]
                  AND target.entityType IN [
                  'Specialty','DiseaseCategory','DiseaseSubcategory',
                  'DiseaseClassification','Disease','StandardDiagnosis'
                ]
                RETURN type(r) AS relation_type, count(*) AS count
                ORDER BY count DESC, relation_type
                """,
            )
            structural_endpoint_counts = rows(
                session,
                """
                MATCH (source)-[r]->(target)
                WHERE source.entityType IN [
                  'Specialty','DiseaseCategory','DiseaseSubcategory',
                  'DiseaseClassification','Disease'
                ]
                  AND target.entityType IN [
                  'Specialty','DiseaseCategory','DiseaseSubcategory',
                  'DiseaseClassification','Disease','StandardDiagnosis'
                ]
                RETURN source.entityType AS source_type, type(r) AS relation_type,
                       target.entityType AS target_type, count(*) AS count
                ORDER BY count DESC, source_type, relation_type, target_type
                """,
            )
            hierarchy_nodes = rows(
                session,
                """
                MATCH (n:KGNode)
                WHERE n.entityType IN [
                  'Specialty','DiseaseCategory','DiseaseSubcategory',
                  'DiseaseClassification','Disease'
                ]
                RETURN n.code AS code, n.entityType AS entity_type, n.name AS name,
                       n.status AS status, n.deprecated AS deprecated,
                       n.duplicate_replaced_by AS duplicate_replaced_by,
                       n.schema_version AS schema_version,
                       n.diagnostic_role AS diagnostic_role,
                       n.is_diagnosable AS is_diagnosable,
                       n.is_emr_writable AS is_emr_writable,
                       n.aliases AS aliases
                ORDER BY entity_type, name, code
                """,
            )
            hierarchy_relations = rows(
                session,
                """
                MATCH (source)-[r]->(target)
                WHERE source.entityType IN [
                  'Specialty','DiseaseCategory','DiseaseSubcategory',
                  'DiseaseClassification','Disease'
                ]
                  AND target.entityType IN [
                  'Specialty','DiseaseCategory','DiseaseSubcategory',
                  'DiseaseClassification','Disease','StandardDiagnosis'
                ]
                RETURN source.code AS source_code, source.entityType AS source_type,
                       type(r) AS relation_type,
                       target.code AS target_code, target.entityType AS target_type,
                       properties(r) AS properties
                ORDER BY source_code, relation_type, target_code
                """,
            )
            duplicate_disease_names = rows(
                session,
                """
                MATCH (d:KGNode {entityType:'Disease'})
                WHERE coalesce(d.status,'active') <> 'deprecated'
                  AND coalesce(d.deprecated,false) = false
                  AND d.duplicate_replaced_by IS NULL
                  AND d.name IS NOT NULL AND trim(d.name) <> ''
                WITH d.name AS name, collect(DISTINCT d.code) AS codes
                WHERE size(codes) > 1
                RETURN name, codes, size(codes) AS count
                ORDER BY count DESC, name
                """,
            )
            sample_detail = rows(
                session,
                """
                MATCH (n:KGNode)
                WHERE n.code IN [
                  'CARD','SPEC-CARD','CAT-CARD-CAD','CAT-CARD-CM',
                  'DIS-CARD-CAD-AMI','DIS-CARD-CAD-STEMI','DIS-CARD-CAD-NSTEMI',
                  'DIS-CARD-CM-GENERAL','DIS-CARD-CM-HCM','DIS-CARD-CM-DCM',
                  'CLASS-CARD-CAD-AMI-STEMI','CLASS-CARD-CAD-AMI-NSTEMI'
                ]
                OPTIONAL MATCH (n)-[r]-(other)
                WHERE other.entityType IN [
                  'Specialty','DiseaseCategory','DiseaseSubcategory',
                  'DiseaseClassification','Disease','StandardDiagnosis'
                ]
                RETURN n.code AS code, n.entityType AS entity_type, n.name AS name,
                       type(r) AS relation_type,
                       CASE WHEN startNode(r)=n THEN 'outgoing' ELSE 'incoming' END AS direction,
                       other.code AS other_code, other.entityType AS other_type,
                       other.name AS other_name
                ORDER BY code, relation_type, other_code
                """,
            )
            sample_classifications = rows(
                session,
                """
                MATCH (d:KGNode {entityType:'Disease'})-[:has_classification]->(cl:KGNode)
                WHERE d.code IN [
                  'DIS-CARD-CAD-AMI','DIS-CARD-CAD-STEMI','DIS-CARD-CAD-NSTEMI',
                  'DIS-CARD-CM-GENERAL','DIS-CARD-CM-HCM','DIS-CARD-CM-DCM'
                ]
                OPTIONAL MATCH (cl)-[r]-(other)
                RETURN d.code AS parent_disease_code,
                       cl.code AS classification_code, cl.name AS classification_name,
                       cl.entityType AS classification_type,
                       type(r) AS relation_type,
                       CASE WHEN startNode(r)=cl THEN 'outgoing' ELSE 'incoming' END AS direction,
                       other.code AS other_code, other.entityType AS other_type,
                       other.name AS other_name
                ORDER BY parent_disease_code, classification_code, relation_type, other_code
                """,
            )
    finally:
        driver.close()

    write_json(output_dir / "01_实体类型统计.json", entity_counts)
    write_json(output_dir / "02_结构关系统计.json", structural_relation_counts)
    write_json(output_dir / "02A_结构关系端点统计.json", structural_endpoint_counts)
    write_csv(output_dir / "03_层级节点.csv", hierarchy_nodes)
    write_json(output_dir / "04_层级关系.json", hierarchy_relations)
    write_json(output_dir / "05_同名疾病重复.json", duplicate_disease_names)
    write_json(output_dir / "06_AMI与心肌病现状.json", sample_detail)
    write_json(output_dir / "07_AMI与心肌病旧分型明细.json", sample_classifications)
    summary = {
        "read_only": True,
        "entity_counts": entity_counts,
        "structural_relation_counts": structural_relation_counts,
        "structural_endpoint_counts": structural_endpoint_counts,
        "hierarchy_node_count": len(hierarchy_nodes),
        "hierarchy_relation_count": len(hierarchy_relations),
        "duplicate_disease_name_group_count": len(duplicate_disease_names),
        "sample_detail_row_count": len(sample_detail),
        "sample_classification_detail_row_count": len(sample_classifications),
    }
    write_json(output_dir / "00_盘点摘要.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
