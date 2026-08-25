from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "项目管理中心_project_management" / "146_疾病目录层级收口_20260719"

CATEGORY_RECODE = {
    "CARD-PH": "CAT-CARD-PH",
    "CARD-PACING": "CAT-CARD-PACING",
    "CARD-LIPID-ASCVD": "CAT-CARD-LIPID-ASCVD",
}

CATEGORY_MERGE = {
    "CARD-AORTA-PAD": "CAT-CARD-AORTA-PAD",
    "CARD-SHD-CHD": "CAT-CARD-CHD",
    "CARD-VHD": "CAT-CARD-VHD",
    "CAT-CARD-HT": "CAT-CARD-HTN",
}

CM_SUBTYPE_CODES = [
    "DIS-CARD-CM-ATRIAL",
    "DIS-CARD-CM-FABRY",
    "DIS-CARD-CM-AMYLOID",
    "DIS-CARD-CM-ABVC",
    "DIS-CARD-CM-ARVC",
    "DIS-CARD-CM-ALVC",
    "DIS-CARD-CM-ACM",
    "DIS-CARD-CM-RCM",
    "DIS-CARD-CM-NDLVCM",
]


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    bolt = re.search(r"(?:bolt|neo4j)(?:\+ssc|\+s)?://[^\s，,；;]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    if not bolt or not password:
        raise ValueError(f"无法从连接文件读取图谱数据库地址或密码：{path}")
    return {
        "uri": bolt.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    iso_format = getattr(value, "iso_format", None)
    return iso_format() if callable(iso_format) else str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def snapshot(session) -> dict[str, Any]:
    nodes = [
        row.data()
        for row in session.run(
            """
            MATCH (n:KGNode)
            WHERE n.entityType IN ['DiseaseCategory','DiseaseSubcategory','Disease']
            RETURN labels(n) AS labels, properties(n) AS properties
            ORDER BY n.entityType, n.code
            """
        )
    ]
    relations = [
        row.data()
        for row in session.run(
            """
            MATCH (a:KGNode)-[r]->(b:KGNode)
            WHERE a.entityType IN ['Specialty','DiseaseCategory','DiseaseSubcategory','Disease']
              AND b.entityType IN ['DiseaseCategory','DiseaseSubcategory','Disease']
              AND type(r) IN ['has_disease_category','has_disease','has_display_group','groups_disease','has_clinical_subtype']
            RETURN a.entityType AS source_type, a.code AS source_code,
                   type(r) AS relation_type, properties(r) AS relation_properties,
                   b.entityType AS target_type, b.code AS target_code
            ORDER BY source_type, source_code, relation_type, target_code
            """
        )
    ]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nodes": nodes,
        "relations": relations,
    }


def inventory(session) -> dict[str, Any]:
    counts = session.run(
        """
        MATCH (n:KGNode)
        WITH count(n) AS node_count,
             count(CASE WHEN n.entityType='DiseaseCategory' THEN 1 END) AS category_count,
             count(CASE WHEN n.entityType='Disease' THEN 1 END) AS disease_count,
             count(CASE WHEN n.entityType='Evidence' THEN 1 END) AS evidence_count
        MATCH ()-[r]->()
        RETURN node_count, category_count, disease_count, evidence_count,
               node_count-evidence_count AS visual_entity_count, count(r) AS relationship_count
        """
    ).single().data()
    categories = [
        row.data()
        for row in session.run(
            """
            MATCH (c:KGNode {entityType:'DiseaseCategory'})
            OPTIONAL MATCH (c)-[:has_disease]->(d:KGNode {entityType:'Disease'})
            RETURN c.code AS code, c.name AS name, count(DISTINCT d) AS direct_disease_count
            ORDER BY c.code
            """
        )
    ]
    roles = [
        row.data()
        for row in session.run(
            """
            MATCH (d:KGNode {entityType:'Disease'})
            RETURN coalesce(d.diagnostic_role,'未标注') AS diagnostic_role, count(*) AS count
            ORDER BY count DESC
            """
        )
    ]
    return {"counts": counts, "categories": categories, "disease_roles": roles}


def migrate_category(tx, old_code: str, new_code: str) -> None:
    row = tx.run(
        """
        MATCH (old:KGNode {entityType:'DiseaseCategory',code:$old_code})
        MATCH (new:KGNode {entityType:'DiseaseCategory',code:$new_code})
        OPTIONAL MATCH (sp:KGNode {entityType:'Specialty'})-[sr:has_disease_category]->(old)
        FOREACH (_ IN CASE WHEN sp IS NULL THEN [] ELSE [1] END |
          MERGE (sp)-[nsr:has_disease_category]->(new)
          SET nsr += properties(sr))
        WITH old,new
        OPTIONAL MATCH (old)-[dr:has_disease]->(d:KGNode {entityType:'Disease'})
        FOREACH (_ IN CASE WHEN d IS NULL THEN [] ELSE [1] END |
          MERGE (new)-[ndr:has_disease]->(d)
          SET ndr += properties(dr))
        WITH old,new
        OPTIONAL MATCH (old)-[gr:has_display_group]->(g:KGNode {entityType:'DiseaseSubcategory'})
        FOREACH (_ IN CASE WHEN g IS NULL THEN [] ELSE [1] END |
          MERGE (new)-[ngr:has_display_group]->(g)
          SET ngr += properties(gr)
          SET g.parentCode=$new_code)
        WITH DISTINCT old,new
        SET new.schema_version='V2.4', new.updated_at=$updated_at
        DETACH DELETE old
        RETURN count(*) AS migrated
        """,
        old_code=old_code,
        new_code=new_code,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ).single()
    if not row or row["migrated"] != 1:
        raise RuntimeError(f"疾病大类合并失败：{old_code} -> {new_code}")
    tx.run(
        "MATCH (n:KGNode {parentCode:$old_code}) SET n.parentCode=$new_code",
        old_code=old_code,
        new_code=new_code,
    ).consume()


def apply_closure(tx) -> dict[str, Any]:
    target_conflicts = tx.run(
        """
        UNWIND $pairs AS pair
        OPTIONAL MATCH (old:KGNode {entityType:'DiseaseCategory',code:pair.old})
        WITH pair, count(old) AS old_count
        OPTIONAL MATCH (new:KGNode {entityType:'DiseaseCategory',code:pair.new})
        WITH pair, old_count, count(new) AS new_count
        RETURN collect({old:pair.old,new:pair.new,old_count:old_count,new_count:new_count}) AS checks
        """,
        pairs=[{"old": old, "new": new} for old, new in CATEGORY_RECODE.items()],
    ).single()["checks"]
    bad = [item for item in target_conflicts if item["old_count"] != 1 or item["new_count"] != 0]
    if bad:
        raise RuntimeError(f"疾病大类编码标准化前置检查失败：{bad}")

    for old_code, new_code in CATEGORY_RECODE.items():
        tx.run(
            """
            MATCH (c:KGNode {entityType:'DiseaseCategory',code:$old_code})
            SET c.code=$new_code, c.schema_version='V2.4', c.updated_at=$updated_at
            """,
            old_code=old_code,
            new_code=new_code,
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ).consume()
        tx.run(
            "MATCH (n:KGNode {parentCode:$old_code}) SET n.parentCode=$new_code",
            old_code=old_code,
            new_code=new_code,
        ).consume()

    for old_code, new_code in CATEGORY_MERGE.items():
        migrate_category(tx, old_code, new_code)

    # 旧复合目录拆回心肌炎、心包疾病、感染性心内膜炎三个正式目录。
    tx.run(
        """
        MATCH (pericard:KGNode {entityType:'DiseaseCategory',code:'CAT-CARD-PERICARD'})
        MATCH (d:KGNode {entityType:'Disease',code:'DIS-CARD-PERICARDITIS'})
        MERGE (pericard)-[:has_disease]->(d)
        SET d.parentCode='CAT-CARD-PERICARD'
        WITH pericard
        MATCH (old:KGNode {entityType:'DiseaseCategory',code:'CARD-MPIE'})
        DETACH DELETE old
        WITH pericard
        MATCH (g:KGNode {entityType:'DiseaseSubcategory',code:'SUB-CARD-MPIE-GENERAL'})
        DETACH DELETE g
        """
    ).consume()
    tx.run(
        """
        MATCH (d:KGNode {entityType:'Disease',code:'DIS-CARD-MYOCARDITIS'})
        SET d.parentCode='CAT-CARD-CM'
        WITH d
        MATCH (ie:KGNode {entityType:'Disease',code:'DIS-CARD-INFECTIVE-ENDOCARDITIS'})
        SET ie.parentCode='CAT-CARD-IE'
        WITH ie
        MATCH (f:KGNode {entityType:'Disease',code:'DIS-CARD-FULMINANT-MYOCARDITIS'})
        SET f.parentCode='DIS-CARD-MYOCARDITIS'
        """
    ).consume()

    # 心肌病统一为“心肌病待分型诊断 -> 具体心肌病分型”。
    tx.run(
        """
        MATCH (cat:KGNode {entityType:'DiseaseCategory',code:'CAT-CARD-CM'})
        MATCH (parent:KGNode {entityType:'Disease',code:'DIS-CARD-CM-GENERAL'})
        UNWIND $codes AS code
        MATCH (d:KGNode {entityType:'Disease',code:code})
        OPTIONAL MATCH (cat)-[old:has_disease]->(d)
        DELETE old
        MERGE (parent)-[:has_clinical_subtype]->(d)
        SET d.diagnostic_role='clinical_subtype', d.is_diagnosable=true,
            d.parentCode=parent.code, d.schema_version='V2.4', d.updated_at=$updated_at
        """,
        codes=CM_SUBTYPE_CODES,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ).consume()

    # 缺血性心肌病只归慢性冠脉综合征，不属于急性冠脉综合征分型。
    tx.run(
        """
        MATCH (:KGNode {entityType:'Disease',code:'DIS-CARD-CAD-ACS'})
              -[r:has_clinical_subtype]->
              (:KGNode {entityType:'Disease',code:'DIS-CARD-CAD-ICM'})
        DELETE r
        """
    ).consume()
    tx.run(
        """
        MATCH (ccs:KGNode {entityType:'Disease',code:'DIS-CARD-CAD-CCS'})
        MATCH (icm:KGNode {entityType:'Disease',code:'DIS-CARD-CAD-ICM'})
        MERGE (ccs)-[:has_clinical_subtype]->(icm)
        SET icm.diagnostic_role='clinical_subtype', icm.parentCode=ccs.code,
            icm.schema_version='V2.4', icm.updated_at=$updated_at
        """,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ).consume()

    # 有明确下级临床分型的父疾病统一标记为“待分型诊断”。
    # 心力衰竭历史上仍标记为独立诊断，会导致 8 个下级分型的角色闸门失败。
    tx.run(
        """
        MATCH (d:KGNode {entityType:'Disease'})
        WHERE d.code IN ['DIS-CARD-HF-GENERAL','DIS-CARD-CM-GENERAL']
        SET d.diagnostic_role='broad_diagnosis', d.is_diagnosable=true,
            d.schema_version='V2.4', d.updated_at=$updated_at
        """,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ).consume()

    gates = tx.run(
        """
        CALL {
          MATCH (c:KGNode {entityType:'DiseaseCategory'})
          RETURN count(c) AS category_count,
                 count(CASE WHEN NOT c.code STARTS WITH 'CAT-' THEN 1 END) AS noncanonical_category_count
        }
        CALL {
          MATCH (d:KGNode {entityType:'Disease'})
          WHERE NOT EXISTS {
            MATCH (:KGNode {entityType:'Specialty'})-[:has_disease_category]->
                  (c:KGNode {entityType:'DiseaseCategory'})-[:has_disease]->
                  (:KGNode {entityType:'Disease'})-[:has_clinical_subtype*0..3]->(d)
            WHERE c.code STARTS WITH 'CAT-'
          }
          RETURN count(d) AS unreachable_disease_count
        }
        CALL {
          MATCH (d:KGNode {entityType:'Disease',diagnostic_role:'clinical_subtype'})
          OPTIONAL MATCH (p:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->(d)
          WITH d, count(DISTINCT p) AS parent_count,
               count(DISTINCT CASE WHEN p.diagnostic_role='broad_diagnosis' THEN p END) AS broad_parent_count
          RETURN count(CASE WHEN parent_count<>1 THEN 1 END) AS subtype_parent_count_error,
                 count(CASE WHEN broad_parent_count<>1 THEN 1 END) AS subtype_parent_role_error
        }
        CALL {
          MATCH (s:KGNode {entityType:'DiseaseSubcategory'})
          WHERE NOT (:KGNode {entityType:'DiseaseCategory'})-[:has_display_group]->(s)
          RETURN count(s) AS orphan_display_group_count
        }
        CALL {
          OPTIONAL MATCH (:KGNode {entityType:'Disease',code:'DIS-CARD-CAD-ACS'})
                         -[r:has_clinical_subtype]->
                         (:KGNode {entityType:'Disease',code:'DIS-CARD-CAD-ICM'})
          RETURN count(r) AS invalid_acs_icm_count
        }
        CALL {
          MATCH (d:KGNode)
          WHERE d.parentCode IN ['CARD-PH','CARD-PACING','CARD-LIPID-ASCVD','CARD-AORTA-PAD',
                                 'CARD-SHD-CHD','CARD-VHD','CARD-MPIE','CAT-CARD-HT']
          RETURN count(d) AS stale_parent_code_count
        }
        RETURN category_count, noncanonical_category_count, unreachable_disease_count,
               subtype_parent_count_error, subtype_parent_role_error,
               orphan_display_group_count, invalid_acs_icm_count, stale_parent_code_count
        """
    ).single().data()
    expected = {
        "category_count": 15,
        "noncanonical_category_count": 0,
        "unreachable_disease_count": 0,
        "subtype_parent_count_error": 0,
        "subtype_parent_role_error": 0,
        "orphan_display_group_count": 0,
        "invalid_acs_icm_count": 0,
        "stale_parent_code_count": 0,
    }
    failures = {key: {"actual": gates[key], "expected": value} for key, value in expected.items() if gates[key] != value}
    if failures:
        raise RuntimeError(f"事务内疾病目录层级闸门未通过：{failures}")
    return gates


def main() -> int:
    parser = argparse.ArgumentParser(description="疾病目录与诊断分型全库收口")
    parser.add_argument("--mode", choices=["plan", "apply", "postcheck"], required=True)
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = parse_connection_file(args.connection_file.resolve())
    driver = GraphDatabase.driver(conn["uri"], auth=(conn["username"], conn["password"]))
    try:
        driver.verify_connectivity()
        with driver.session(database="neo4j") as session:
            before = inventory(session)
            if args.mode in {"plan", "apply"}:
                write_json(output_dir / "00_写库前目录层回滚快照.json", snapshot(session))
                write_json(output_dir / "01_治理前目录盘点.json", before)
            if args.mode == "plan":
                print(json.dumps({"mode": "plan", "before": before}, ensure_ascii=False, indent=2))
                return 0
            if args.mode == "apply":
                gates = session.execute_write(apply_closure)
                write_json(output_dir / "02_事务内闸门结果.json", gates)
            after = inventory(session)
            write_json(output_dir / "03_治理后目录复核.json", after)
            print(json.dumps({"mode": args.mode, "before": before, "after": after}, ensure_ascii=False, indent=2))
            return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
