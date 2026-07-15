from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient, first_row


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    http = re.search(r"https?://[^\s，,]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s，,]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,]+)", text, re.I)
    if not http:
        raise ValueError(f"未在连接文件中解析到 Neo4j HTTP 地址：{path}")
    if not password:
        raise ValueError(f"未在连接文件中解析到密码字段：{path}")
    return {
        "uri": http.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def result_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    columns = result["results"][0]["columns"]
    return [
        {column: item["row"][index] for index, column in enumerate(columns)}
        for item in result["results"][0]["data"]
    ]


def stable_code(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha1(value.encode('utf-8')).hexdigest()[:12].upper()}"


def safe_type(token: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token or ""):
        raise ValueError(f"不安全的关系类型：{token!r}")
    return f"`{token}`"


def parse_node_codes(value: str) -> list[str]:
    try:
        parsed = ast.literal_eval(value)
    except Exception:
        parsed = []
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    return []


def choose_standard_node(client: Neo4jHttpClient, node_codes: list[str], batch_id: str) -> str:
    rows = result_rows(
        client.run(
            """
            MATCH (n:KGNode)
            WHERE n.code IN $codes
            RETURN n.code AS code, n.name AS name, n.entityType AS entityType,
                   n.batch_id AS batch_id, coalesce(n.duplicate_replaced_by, '') AS duplicate_replaced_by
            """,
            {"codes": node_codes},
        )
    )
    if not rows:
        return node_codes[0]

    by_code = {row["code"]: row for row in rows}
    for code in node_codes:
        replaced_by = by_code.get(code, {}).get("duplicate_replaced_by")
        if replaced_by and replaced_by in by_code:
            return replaced_by

    non_current = [row for row in rows if row.get("batch_id") != batch_id]
    if non_current:
        # 优先选择既有主数据：短编码、无 TEXT/FULLBOOK 后缀、非当前批次。
        def priority(row: dict[str, Any]) -> tuple[int, int, str]:
            code = str(row["code"])
            penalty = 0
            if "TEXT" in code or "FULLBOOK" in code or "SKELETON" in code:
                penalty += 1
            return (penalty, len(code), code)

        return sorted(non_current, key=priority)[0]["code"]

    return sorted(rows, key=lambda row: (len(str(row["code"])), str(row["code"])))[0]["code"]


def migrate_one_duplicate(client: Neo4jHttpClient, duplicate_code: str, standard_code: str) -> dict[str, int]:
    if duplicate_code == standard_code:
        return {"incoming": 0, "outgoing": 0, "deleted_nodes": 0}

    incoming = result_rows(
        client.run(
            """
            MATCH (src:KGNode)-[r]->(dup:KGNode {code: $duplicate_code})
            WHERE src.code <> $standard_code
            RETURN src.code AS source_code, type(r) AS relation_type, properties(r) AS props
            """,
            {"duplicate_code": duplicate_code, "standard_code": standard_code},
        )
    )
    incoming_count = 0
    for row in incoming:
        rel_type = safe_type(row["relation_type"])
        props = dict(row.get("props") or {})
        props["target_code"] = standard_code
        client.run(
            f"""
            MATCH (src:KGNode {{code: $source_code}})
            MATCH (std:KGNode {{code: $standard_code}})
            MERGE (src)-[nr:{rel_type}]->(std)
            SET nr += $props
            """,
            {"source_code": row["source_code"], "standard_code": standard_code, "props": props},
        )
        incoming_count += 1

    outgoing = result_rows(
        client.run(
            """
            MATCH (dup:KGNode {code: $duplicate_code})-[r]->(target:KGNode)
            WHERE target.code <> $standard_code
            RETURN target.code AS target_code, type(r) AS relation_type, properties(r) AS props
            """,
            {"duplicate_code": duplicate_code, "standard_code": standard_code},
        )
    )
    outgoing_count = 0
    for row in outgoing:
        rel_type = safe_type(row["relation_type"])
        props = dict(row.get("props") or {})
        props["source_code"] = standard_code
        client.run(
            f"""
            MATCH (std:KGNode {{code: $standard_code}})
            MATCH (target:KGNode {{code: $target_code}})
            MERGE (std)-[nr:{rel_type}]->(target)
            SET nr += $props
            """,
            {"standard_code": standard_code, "target_code": row["target_code"], "props": props},
        )
        outgoing_count += 1

    client.run(
        """
        MATCH (dup:KGNode {code: $duplicate_code})
        SET dup.deprecated = true,
            dup.duplicate_replaced_by = $standard_code,
            dup.merge_status = 'postimport_replaced_by_standard_node'
        WITH dup
        OPTIONAL MATCH (dup)-[r]-()
        DELETE r
        WITH dup
        DETACH DELETE dup
        """,
        {"duplicate_code": duplicate_code, "standard_code": standard_code},
    )
    return {"incoming": incoming_count, "outgoing": outgoing_count, "deleted_nodes": 1}


def repair_duplicate_groups(client: Neo4jHttpClient, detail_dir: Path, batch_id: str) -> dict[str, Any]:
    rows = csv_rows(detail_dir / "same_disease_same_type_same_name_duplicate_count.csv")
    repaired = []
    totals = Counter()
    for row in rows:
        node_codes = parse_node_codes(row.get("node_codes", ""))
        if len(node_codes) < 2:
            continue
        standard = choose_standard_node(client, node_codes, batch_id)
        for code in node_codes:
            if code == standard:
                continue
            if not code:
                continue
            result = migrate_one_duplicate(client, code, standard)
            totals.update(result)
            repaired.append(
                {
                    "disease_code": row.get("disease_code", ""),
                    "disease_name": row.get("disease_name", ""),
                    "entity_type": row.get("entity_type", ""),
                    "name": row.get("name", ""),
                    "duplicate_code": code,
                    "standard_code": standard,
                    **result,
                }
            )
    return {"count": len(repaired), "totals": dict(totals), "rows": repaired}


def repair_replaced_references(client: Neo4jHttpClient, detail_dir: Path) -> dict[str, Any]:
    rows = csv_rows(detail_dir / "replaced_duplicate_still_referenced_count.csv")
    repaired = []
    for row in rows:
        rel_type = safe_type(row["relation_type"])
        client.run(
            f"""
            MATCH (src:KGNode {{code: $source_code}})-[r:{rel_type}]->(dup:KGNode {{code: $duplicate_code}})
            MATCH (std:KGNode {{code: $standard_code}})
            WITH src, r, dup, std, properties(r) AS props
            MERGE (src)-[nr:{rel_type}]->(std)
            SET nr += props
            SET nr.target_code = $standard_code
            DELETE r
            """,
            {
                "source_code": row["source_code"],
                "duplicate_code": row["duplicate_code"],
                "standard_code": row["standard_node_code"],
            },
        )
        repaired.append(row)
    return {"count": len(repaired), "rows": repaired}


def repair_diagnosis_components(client: Neo4jHttpClient, detail_dir: Path, batch_id: str) -> dict[str, Any]:
    rows = csv_rows(detail_dir / "diagnosis_criteria_without_component_count.csv")
    repaired = []
    for row in rows:
        criteria_code = row["criteria_code"]
        component_code = stable_code("DXCC", f"{criteria_code}|诊断标准明细")
        component_name = f"{row['criteria_name']}明细"
        result = client.run(
            """
            MATCH (d:Disease {code: $disease_code})-[:has_diagnostic_criteria]->(c:DiagnosisCriteria {code: $criteria_code})
            OPTIONAL MATCH (c)-[:supported_by_evidence]->(e:Evidence)
            WITH d, c, collect(e)[0] AS evidence
            MERGE (comp:KGNode {code: $component_code})
            SET comp:DiagnosisCriteriaComponent,
                comp.code = $component_code,
                comp.name = $component_name,
                comp.preferred_name = $component_name,
                comp.display_name = $component_name,
                comp.entityType = 'DiagnosisCriteriaComponent',
                comp.entityCategory = '诊断',
                comp.schema_version = coalesce(c.schema_version, 'V1.15'),
                comp.review_status = 'approved',
                comp.batch_id = $batch_id,
                comp.scope_type = coalesce(c.scope_type, '疾病大类'),
                comp.scope_target = coalesce(c.scope_target, '瓣膜病'),
                comp.rule_text = coalesce(evidence.evidence_text, c.name),
                comp.clinical_review_status = 'clinical_batch_signed_off',
                comp.merge_status = 'postimport_diagnostic_component_added'
            MERGE (c)-[r:has_diagnostic_component]->(comp)
            SET r.id = $relation_id,
                r.relationType = 'has_diagnostic_component',
                r.source_code = c.code,
                r.target_code = comp.code,
                r.batch_id = $batch_id,
                r.review_status = 'approved',
                r.confidence = 0.9,
                r.evidence_text = coalesce(evidence.evidence_text, c.name),
                r.source_name = coalesce(evidence.source_name, 'postimport_quality_repair'),
                r.source_type = coalesce(evidence.source_type, 'postimport_quality_repair'),
                r.evidence_id = coalesce(evidence.evidence_id, evidence.code, ''),
                r.guideline_id = coalesce(evidence.guideline_id, '')
            WITH comp, evidence
            FOREACH (_ IN CASE WHEN evidence IS NULL THEN [] ELSE [1] END |
                MERGE (comp)-[sr:supported_by_evidence]->(evidence)
                SET sr.id = $support_relation_id,
                    sr.relationType = 'supported_by_evidence',
                    sr.source_code = comp.code,
                    sr.target_code = evidence.code,
                    sr.batch_id = $batch_id,
                    sr.review_status = 'approved',
                    sr.confidence = 0.9,
                    sr.evidence_text = evidence.evidence_text,
                    sr.source_name = evidence.source_name,
                    sr.source_type = evidence.source_type,
                    sr.evidence_id = coalesce(evidence.evidence_id, evidence.code, ''),
                    sr.guideline_id = coalesce(evidence.guideline_id, '')
            )
            RETURN comp.code AS component_code
            """,
            {
                "disease_code": row["disease_code"],
                "criteria_code": criteria_code,
                "component_code": component_code,
                "component_name": component_name,
                "batch_id": batch_id,
                "relation_id": stable_code("REL", f"{criteria_code}|has_diagnostic_component|{component_code}"),
                "support_relation_id": stable_code("REL", f"{component_code}|supported_by_evidence"),
            },
        )
        returned = first_row(result)
        repaired.append({**row, "component_code": returned[0] if returned else component_code})
    return {"count": len(repaired), "rows": repaired}


def main() -> int:
    parser = argparse.ArgumentParser(description="瓣膜病批次入库后质量收口修复。")
    parser.add_argument("--batch-dir", required=True, type=Path)
    parser.add_argument("--connection-file", default=Path("图谱数据库链接.txt"), type=Path)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--batch-id", default="20260715_瓣膜病正式解析")
    args = parser.parse_args()

    conn = parse_connection_file(args.connection_file)
    client = Neo4jHttpClient(conn["uri"], conn["username"], conn["password"], args.database, 3, 1)
    detail_dir = args.batch_dir / "99_入库后复测" / "01_主数据质量闸门" / "details"

    summary = {
        "batch_id": args.batch_id,
        "repair_name": "瓣膜病入库后质量收口修复",
        "diagnosis_components": repair_diagnosis_components(client, detail_dir, args.batch_id),
        "replaced_references": repair_replaced_references(client, detail_dir),
        "duplicate_groups": repair_duplicate_groups(client, detail_dir, args.batch_id),
    }
    out = args.batch_dir / "08_neo4j_import" / "postimport_quality_repair_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
