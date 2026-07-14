from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "心血管内科文献集合" / "20260714_心肌病总精修"
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260714_心肌病总精修"

CM_DISEASE_CODES = [
    "DIS-CARD-CAD-ICM",
    "DIS-CARD-CM-ABVC",
    "DIS-CARD-CM-ACM",
    "DIS-CARD-CM-ALVC",
    "DIS-CARD-CM-AMYLOID",
    "DIS-CARD-CM-ARVC",
    "DIS-CARD-CM-ATRIAL",
    "DIS-CARD-CM-DCM",
    "DIS-CARD-CM-FABRY",
    "DIS-CARD-CM-HCM",
    "DIS-CARD-CM-MYOCARDITIS",
    "DIS-CARD-CM-NDLVCM",
    "DIS-CARD-CM-RCM",
]

PREFERRED_CODES = {
    "冠状动脉造影": ["EXAM-CAG"],
    "超声心动图": ["EXAM-TTE"],
    "心脏磁共振": ["EXAM-CMR"],
    "心脏移植": ["PROC-HEART-TRANSPLANT"],
    "缺血性心肌病诊断标准": ["DXC-CARD-097806EACD3F"],
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_connection() -> tuple[str, str, str]:
    text = CONNECTION_FILE.read_text(encoding="utf-8", errors="ignore")
    bolt = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名\s*[:：]\s*([^\s；;]+)", text)
    pwd = re.search(r"密码\s*[:：]\s*([^\s；;]+)", text)
    if not (bolt and user and pwd):
        raise RuntimeError("图谱数据库链接.txt 缺少 Bolt/用户名/密码字段")
    return bolt.group(0), user.group(1), pwd.group(1)


def choose_canonical(name: str, codes: list[str]) -> str:
    for preferred in PREFERRED_CODES.get(name, []):
        if preferred in codes:
            return preferred
    non_batch = [c for c in codes if "-CADREM-" not in c and "-TEXT-" not in c]
    if non_batch:
        return sorted(non_batch, key=len)[0]
    return sorted(codes, key=len)[0]


def fetch_duplicates(tx) -> list[dict[str, Any]]:
    records = tx.run(
        """
        MATCH (d:Disease)-[rel]->(n:KGNode)
        WHERE d.code IN $codes AND n.entityType IS NOT NULL AND n.name IS NOT NULL
        WITH d.code AS disease_code, d.name AS disease, n.entityType AS entityType, n.name AS name,
             collect(DISTINCT n.code) AS codes, collect(DISTINCT type(rel)) AS rels, count(DISTINCT n.code) AS c
        WHERE c > 1
        RETURN disease_code, disease, entityType, name, codes, rels
        ORDER BY disease_code, entityType, name
        """,
        codes=CM_DISEASE_CODES,
    )
    return [dict(r) for r in records]


def relationship_type_is_safe(rel_type: str) -> bool:
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", rel_type) is not None


def migrate_duplicate_direct_relation(tx, disease_code: str, duplicate_code: str, canonical_code: str, rel_type: str) -> int:
    if not relationship_type_is_safe(rel_type):
        raise ValueError(f"非法关系类型：{rel_type}")
    now = now_iso()
    result = tx.run(
        f"""
        MATCH (d:Disease {{code:$disease_code}})-[old:`{rel_type}`]->(dup:KGNode {{code:$duplicate_code}})
        MATCH (canon:KGNode {{code:$canonical_code}})
        MERGE (d)-[new:`{rel_type}`]->(canon)
        ON CREATE SET new.batch_id=$batch_id, new.created_at=$now,
                      new.link_method='same_name_duplicate_direct_relation_migration'
        SET new.updated_at=$now
        DELETE old
        SET dup.duplicate_replaced_by=$canonical_code,
            dup.duplicate_direct_link_removed_at=$now,
            dup.duplicate_fix_batch_id=$batch_id,
            dup.updated_at=$now
        RETURN count(dup) AS c
        """,
        disease_code=disease_code,
        duplicate_code=duplicate_code,
        canonical_code=canonical_code,
        batch_id=BATCH_ID,
        now=now,
    ).single()
    return result["c"] if result else 0


def copy_selected_outgoing(tx, duplicate_code: str, canonical_code: str) -> dict[str, int]:
    now = now_iso()
    evidence_count = tx.run(
        """
        MATCH (dup:KGNode {code:$duplicate_code})-[:supported_by_evidence]->(e:Evidence)
        MATCH (canon:KGNode {code:$canonical_code})
        MERGE (canon)-[r:supported_by_evidence]->(e)
        ON CREATE SET r.batch_id=$batch_id, r.created_at=$now,
                      r.link_method='duplicate_evidence_relation_migration'
        SET r.updated_at=$now
        RETURN count(e) AS c
        """,
        duplicate_code=duplicate_code,
        canonical_code=canonical_code,
        batch_id=BATCH_ID,
        now=now,
    ).single()["c"]
    component_count = tx.run(
        """
        MATCH (dup:KGNode {code:$duplicate_code})-[:has_diagnostic_component]->(c:KGNode)
        MATCH (canon:KGNode {code:$canonical_code})
        MERGE (canon)-[r:has_diagnostic_component]->(c)
        ON CREATE SET r.batch_id=$batch_id, r.created_at=$now,
                      r.link_method='duplicate_diagnostic_component_migration'
        SET r.updated_at=$now
        RETURN count(c) AS c
        """,
        duplicate_code=duplicate_code,
        canonical_code=canonical_code,
        batch_id=BATCH_ID,
        now=now,
    ).single()["c"]
    return {"copied_evidence": evidence_count, "copied_components": component_count}


def postcheck(tx) -> int:
    return tx.run(
        """
        MATCH (d:Disease)-[]->(n:KGNode)
        WHERE d.code IN $codes AND n.entityType IS NOT NULL AND n.name IS NOT NULL
        WITH d.code AS disease_code, n.entityType AS entityType, n.name AS name, count(DISTINCT n.code) AS c
        WHERE c > 1
        RETURN count(*) AS c
        """,
        codes=CM_DISEASE_CODES,
    ).single()["c"]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bolt, user, password = read_connection()
    rows: list[dict[str, Any]] = []

    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session(database="neo4j") as session:
            duplicates = session.execute_read(fetch_duplicates)
            for group in duplicates:
                canonical = choose_canonical(group["name"], list(group["codes"]))
                for duplicate_code in group["codes"]:
                    if duplicate_code == canonical:
                        continue
                    copied = session.execute_write(copy_selected_outgoing, duplicate_code, canonical)
                    migrated_total = 0
                    for rel_type in group["rels"]:
                        migrated_total += session.execute_write(
                            migrate_duplicate_direct_relation,
                            group["disease_code"],
                            duplicate_code,
                            canonical,
                            rel_type,
                        )
                    rows.append(
                        {
                            "disease_code": group["disease_code"],
                            "disease": group["disease"],
                            "entityType": group["entityType"],
                            "name": group["name"],
                            "canonical_code": canonical,
                            "duplicate_code": duplicate_code,
                            "direct_relations_migrated": migrated_total,
                            **copied,
                        }
                    )
            remaining = session.execute_read(postcheck)

    with (OUT_DIR / "13_同名重复直连治理明细.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "disease_code",
            "disease",
            "entityType",
            "name",
            "canonical_code",
            "duplicate_code",
            "direct_relations_migrated",
            "copied_evidence",
            "copied_components",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "batch_id": BATCH_ID,
        "executed_at": now_iso(),
        "duplicate_groups_before": len(duplicates),
        "duplicate_nodes_processed": len(rows),
        "duplicate_groups_remaining": remaining,
    }
    (OUT_DIR / "13_同名重复直连治理回归.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
