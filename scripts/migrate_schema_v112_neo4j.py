from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
OUTPUT_DIR = ROOT / "schema_v112_migration_20260711"


EXACT_RELATION_MAP = {
    "HAS_SYMPTOM": "has_symptom",
    "HAS_SIGN": "has_sign",
    "HAS_PATHOPHYSIOLOGY": "has_pathophysiology",
    "HAS_ETIOLOGY": "has_etiology",
    "HAS_RISK_FACTOR": "has_risk_factor",
    "HAS_DIAGNOSTIC_COMPONENT": "has_diagnostic_component",
    "HAS_TREATMENT_PLAN": "has_treatment_plan",
    "HAS_FOLLOW_UP": "has_follow_up",
    "HAS_PROGNOSIS": "has_prognosis",
    "HAS_EPIDEMIOLOGY": "has_epidemiology",
    "HAS_RISK_STRATIFICATION": "has_risk_stratification",
    "HAS_DEFINITION": "has_definition",
    "HAS_DEFINITION_COMPONENT": "has_definition_component",
    "HAS_PREVENTION": "has_prevention",
    "HAS_CLASSIFICATION": "has_classification",
    "HAS_COMPLICATION": "may_cause_complication",
    "HAS_EXAM": "requires_exam",
    "HAS_LAB_TEST": "requires_lab_test",
    "HAS_DIFFERENTIAL_DIAGNOSIS": "differentiates_from",
    "has_differential_diagnosis": "differentiates_from",
}

LEGACY_RELATION_TYPES = sorted(
    set(EXACT_RELATION_MAP)
    | {
        "HAS_EVIDENCE",
        "USES_MEDICATION",
        "HAS_PROCEDURE",
        "HAS_CLINICAL_MANIFESTATION",
    }
)

ARRAY_MERGE_FIELDS = {
    "evidence_ids",
    "document_ids",
    "source_names",
    "source_types",
    "migrated_from_relation_types",
}


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_connection() -> tuple[str, str, str]:
    text = CONNECTION_FILE.read_text(encoding="utf-8")
    bolt_match = re.search(r"bolt://[^\s；;]+", text)
    user_match = re.search(r"用户名\s*[:：]\s*([^\s；;]+)", text)
    pwd_match = re.search(r"密码\s*[:：]\s*([^\s；;]+)", text)
    if not (bolt_match and user_match and pwd_match):
        raise RuntimeError(f"无法从连接文件解析 bolt/用户名/密码：{CONNECTION_FILE}")
    return bolt_match.group(0), user_match.group(1), pwd_match.group(1)


def normalize_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def stable_union(left: Any, right: Any) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for item in normalize_list(left) + normalize_list(right):
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def merge_provenance(existing: Any, incoming: Any) -> Any:
    existing_list = normalize_list(existing)
    incoming_list = normalize_list(incoming)
    if not existing_list and not incoming_list:
        return None
    return stable_union(existing_list, incoming_list)


def merge_props(existing: dict[str, Any] | None, incoming: dict[str, Any], new_type: str, old_type: str) -> dict[str, Any]:
    merged: dict[str, Any] = dict(existing or {})
    for key, value in incoming.items():
        if key in ARRAY_MERGE_FIELDS:
            merged[key] = stable_union(merged.get(key), value)
        elif key == "provenance_records_json":
            provenance = merge_provenance(merged.get(key), value)
            if provenance is not None:
                merged[key] = provenance
        elif key not in merged or merged.get(key) in (None, "", [], {}):
            merged[key] = value
    merged["relationType"] = new_type
    merged["schema_version"] = "V1.12"
    merged["migrated_at"] = now_str()
    merged["migrated_from_relation_types"] = stable_union(merged.get("migrated_from_relation_types"), old_type)
    if isinstance(merged.get("evidence_ids"), list):
        merged["evidence_count"] = len(merged["evidence_ids"])
    return merged


def target_relation_type(row: dict[str, Any]) -> str | None:
    old = row["relationType"]
    source_type = row.get("source_entity_type")
    target_type = row.get("target_entity_type")
    if old in EXACT_RELATION_MAP:
        return EXACT_RELATION_MAP[old]
    if old == "HAS_EVIDENCE":
        if source_type == "Guideline":
            return "guideline_has_evidence"
        if source_type in {"SourceSection", "TextbookSection"}:
            return "section_has_evidence"
        if source_type == "RecommendationStatement":
            return "derived_from"
        if target_type == "Evidence":
            return "supported_by_evidence"
        return None
    if old == "USES_MEDICATION":
        if source_type == "Disease":
            return "treated_by_medication"
        if source_type == "TreatmentPlan":
            return "includes_medication"
        return None
    if old == "HAS_PROCEDURE":
        if source_type == "Disease":
            return "treated_by_procedure"
        if source_type == "TreatmentPlan":
            return "includes_procedure"
        return None
    if old == "HAS_CLINICAL_MANIFESTATION":
        return None
    return None


def fetch_relation_plan(session) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    query = """
    MATCH (s:KGNode)-[r]->(t:KGNode)
    WHERE type(r) IN $types
    RETURN elementId(r) AS element_id,
           type(r) AS relationType,
           properties(r) AS props,
           s.code AS source_code,
           s.name AS source_name,
           s.entityType AS source_entity_type,
           t.code AS target_code,
           t.name AS target_name,
           t.entityType AS target_entity_type
    ORDER BY type(r), s.code, t.code
    """
    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for record in session.run(query, types=LEGACY_RELATION_TYPES):
        row = dict(record)
        new_type = target_relation_type(row)
        row["new_relationType"] = new_type
        if new_type:
            planned.append(row)
        else:
            skipped.append(row)
    return planned, skipped


def summarize_relation_plan(planned: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> dict[str, Any]:
    by_mapping = Counter((row["relationType"], row["new_relationType"]) for row in planned)
    skipped_by_type = Counter(row["relationType"] for row in skipped)
    semantic_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in planned:
        semantic_groups[(row["source_code"], row["new_relationType"], row["target_code"])].append(row)
    duplicate_target_groups = [
        {
            "source_code": key[0],
            "new_relationType": key[1],
            "target_code": key[2],
            "old_relation_count": len(rows),
            "old_relation_types": sorted({r["relationType"] for r in rows}),
        }
        for key, rows in semantic_groups.items()
        if len(rows) > 1
    ]
    return {
        "planned_relation_count": len(planned),
        "skipped_relation_count": len(skipped),
        "planned_by_mapping": [
            {"old_relationType": old, "new_relationType": new, "count": count}
            for (old, new), count in sorted(by_mapping.items())
        ],
        "skipped_by_type": [
            {"relationType": rel_type, "count": count}
            for rel_type, count in sorted(skipped_by_type.items())
        ],
        "duplicate_target_group_count": len(duplicate_target_groups),
        "duplicate_target_groups_sample": duplicate_target_groups[:50],
    }


def fetch_node_plan(session) -> dict[str, Any]:
    queries = {
        "textbook_section_to_source_section": """
            MATCH (n:KGNode {entityType:'TextbookSection'})
            RETURN count(n) AS count, collect(n.code)[0..20] AS sample_codes
        """,
        "clinical_manifestation_to_source_section": """
            MATCH (n:KGNode {entityType:'ClinicalManifestation'})
            RETURN count(n) AS count, collect(n.code)[0..20] AS sample_codes
        """,
        "knowledge_layer_textbook_skeleton": """
            MATCH (n:KGNode {knowledge_layer:'textbook_skeleton'})
            RETURN count(n) AS count, collect(n.code)[0..20] AS sample_codes
        """,
        "definition_skeleton_slot_to_skeleton_slot": """
            MATCH (n:KGNode)
            WHERE n.definition_skeleton_slot IS NOT NULL AND n.skeleton_slot IS NULL
            RETURN count(n) AS count, collect(n.code)[0..20] AS sample_codes
        """,
    }
    result: dict[str, Any] = {}
    for key, query in queries.items():
        rows = [dict(r) for r in session.run(query)]
        result[key] = rows[0] if rows else {"count": 0, "sample_codes": []}
    return result


def run_baseline_checks(session) -> dict[str, Any]:
    queries = {
        "legacy_relation_count": """
            MATCH (:KGNode)-[r]->(:KGNode)
            WHERE type(r) IN $types
            RETURN type(r) AS relationType, count(r) AS count
            ORDER BY count DESC, relationType
        """,
        "v112_nonstandard_entity_count": """
            MATCH (n:KGNode)
            WHERE n.entityType IN ['TextbookSection','ClinicalManifestation']
            RETURN n.entityType AS entityType, count(n) AS count
            ORDER BY count DESC
        """,
        "knowledge_layer_values": """
            MATCH (n:KGNode)
            WHERE n.knowledge_layer IS NOT NULL
            RETURN n.knowledge_layer AS value, count(n) AS count
            ORDER BY count DESC
        """,
        "total": """
            MATCH (n:KGNode)
            WITH count(n) AS node_count
            MATCH ()-[r]->()
            RETURN node_count, count(r) AS relation_count
        """,
        "recommendation_integrity": """
            MATCH (rec:KGNode {entityType:'RecommendationStatement'})
            RETURN count(rec) AS rec_total,
              sum(CASE WHEN (rec)-[:recommends_action|blocks_action]->(:KGNode) THEN 0 ELSE 1 END) AS rec_without_action,
              sum(CASE WHEN (rec)-[:derived_from|supported_by_evidence]->(:KGNode {entityType:'Evidence'}) THEN 0 ELSE 1 END) AS rec_without_evidence,
              sum(CASE WHEN (rec)-[:based_on_guideline]->(:KGNode {entityType:'Guideline'}) THEN 0 ELSE 1 END) AS rec_without_guideline
        """,
    }
    output: dict[str, Any] = {}
    for key, query in queries.items():
        params = {"types": LEGACY_RELATION_TYPES} if "$types" in query else {}
        output[key] = [dict(r) for r in session.run(query, **params)]
    return output


def apply_node_migrations(session) -> dict[str, Any]:
    timestamp = now_str()
    migrations = {}
    queries = {
        "textbook_section_to_source_section": """
            MATCH (n:KGNode {entityType:'TextbookSection'})
            SET n.entityType='SourceSection',
                n.schema_version='V1.12',
                n.migrated_from_entityType='TextbookSection',
                n.migrated_at=$timestamp,
                n.primary_label='KGNode',
                n.type_label='SourceSection',
                n.canonical_labels=['KGNode','SourceSection']
            SET n:SourceSection
            REMOVE n:TextbookSection
            RETURN count(n) AS count
        """,
        "clinical_manifestation_to_source_section": """
            MATCH (n:KGNode {entityType:'ClinicalManifestation'})
            SET n.entityType='SourceSection',
                n.schema_version='V1.12',
                n.migrated_from_entityType='ClinicalManifestation',
                n.migrated_at=$timestamp,
                n.primary_label='KGNode',
                n.type_label='SourceSection',
                n.canonical_labels=['KGNode','SourceSection']
            SET n:SourceSection
            REMOVE n:ClinicalManifestation
            RETURN count(n) AS count
        """,
        "knowledge_layer_textbook_skeleton": """
            MATCH (n:KGNode {knowledge_layer:'textbook_skeleton'})
            SET n.knowledge_layer='textbook_core',
                n.migrated_knowledge_layer_from='textbook_skeleton',
                n.migrated_at=$timestamp
            RETURN count(n) AS count
        """,
        "definition_skeleton_slot_to_skeleton_slot": """
            MATCH (n:KGNode)
            WHERE n.definition_skeleton_slot IS NOT NULL AND n.skeleton_slot IS NULL
            SET n.skeleton_slot=n.definition_skeleton_slot,
                n.migrated_at=$timestamp
            RETURN count(n) AS count
        """,
    }
    for key, query in queries.items():
        migrations[key] = dict(session.run(query, timestamp=timestamp).single() or {}).get("count", 0)
    return migrations


def get_existing_relation_props(session, source_code: str, target_code: str, rel_type: str) -> dict[str, Any] | None:
    query = f"""
    MATCH (s:KGNode {{code:$source_code}})-[r:`{rel_type}`]->(t:KGNode {{code:$target_code}})
    RETURN properties(r) AS props
    LIMIT 1
    """
    row = session.run(query, source_code=source_code, target_code=target_code).single()
    return dict(row["props"]) if row else None


def upsert_new_relation(session, row: dict[str, Any], merged_props: dict[str, Any]) -> None:
    rel_type = row["new_relationType"]
    query = f"""
    MATCH (s:KGNode {{code:$source_code}}), (t:KGNode {{code:$target_code}})
    MERGE (s)-[nr:`{rel_type}`]->(t)
    SET nr += $props
    """
    session.run(
        query,
        source_code=row["source_code"],
        target_code=row["target_code"],
        props=merged_props,
    ).consume()


def delete_old_relation(session, element_id: str) -> None:
    session.run(
        "MATCH ()-[r]->() WHERE elementId(r)=$element_id DELETE r",
        element_id=element_id,
    ).consume()


def apply_relation_migrations(session, planned: list[dict[str, Any]]) -> dict[str, Any]:
    applied = 0
    by_mapping: Counter[tuple[str, str]] = Counter()
    for row in planned:
        existing = get_existing_relation_props(session, row["source_code"], row["target_code"], row["new_relationType"])
        merged = merge_props(existing, dict(row["props"] or {}), row["new_relationType"], row["relationType"])
        upsert_new_relation(session, row, merged)
        delete_old_relation(session, row["element_id"])
        applied += 1
        by_mapping[(row["relationType"], row["new_relationType"])] += 1
    return {
        "applied_relation_count": applied,
        "applied_by_mapping": [
            {"old_relationType": old, "new_relationType": new, "count": count}
            for (old, new), count in sorted(by_mapping.items())
        ],
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只生成迁移计划，不写 Neo4j")
    parser.add_argument("--apply", action="store_true", help="执行迁移并写 Neo4j")
    args = parser.parse_args()
    if args.dry_run == args.apply:
        raise SystemExit("必须且只能指定 --dry-run 或 --apply")

    bolt, user, password = read_connection()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session() as session:
            before = run_baseline_checks(session)
            planned, skipped = fetch_relation_plan(session)
            relation_summary = summarize_relation_plan(planned, skipped)
            node_plan = fetch_node_plan(session)
            report: dict[str, Any] = {
                "mode": "dry_run" if args.dry_run else "apply",
                "generated_at": now_str(),
                "server": bolt.replace("bolt://", ""),
                "node_plan": node_plan,
                "relation_plan": relation_summary,
                "before_checks": before,
                "decision": {
                    "safe_to_apply": len(planned) > 0 or any(v.get("count", 0) for v in node_plan.values()),
                    "reason": "只迁移可确定映射的实体、字段和关系；跳过无法确定语义的历史关系。",
                },
            }
            if args.apply:
                node_result = apply_node_migrations(session)
                # Re-fetch after node migrations so TextbookSection endpoints become SourceSection.
                planned_after_nodes, skipped_after_nodes = fetch_relation_plan(session)
                relation_result = apply_relation_migrations(session, planned_after_nodes)
                after = run_baseline_checks(session)
                report["applied_node_migrations"] = node_result
                report["applied_relation_migrations"] = relation_result
                report["after_checks"] = after
                report["remaining_relation_plan"] = summarize_relation_plan(*fetch_relation_plan(session))

    output_name = "schema_v112_dry_run_report.json" if args.dry_run else "schema_v112_apply_report.json"
    out = OUTPUT_DIR / output_name
    write_json(out, report)
    print(json.dumps({"ok": True, "mode": report["mode"], "output": str(out), "summary": report.get("relation_plan"), "node_plan": report.get("node_plan")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
