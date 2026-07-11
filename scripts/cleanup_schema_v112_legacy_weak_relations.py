from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from migrate_schema_v112_neo4j import read_connection


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "schema_v112_migration_20260711"
LEGACY_REL_TYPES = ["USES_MEDICATION", "HAS_PROCEDURE", "HAS_CLINICAL_MANIFESTATION"]


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fetch_candidates(session) -> list[dict[str, Any]]:
    query = """
    MATCH (s)-[r]->(t)
    WHERE type(r) IN $types
      AND r.clinical_use_status = 'knowledge_display_only'
      AND r.formal_cdss_ready = false
      AND r.knowledge_layer = 'textbook_skeleton'
    RETURN elementId(r) AS element_id,
           type(r) AS relationType,
           properties(r) AS props,
           labels(s) AS source_labels,
           s.code AS source_code,
           s.name AS source_name,
           s.entityType AS source_entityType,
           labels(t) AS target_labels,
           t.code AS target_code,
           t.name AS target_name,
           t.entityType AS target_entityType
    ORDER BY relationType, source_code, target_code
    """
    return [dict(row) for row in session.run(query, types=LEGACY_REL_TYPES)]


def count_all_legacy(session) -> list[dict[str, Any]]:
    query = """
    MATCH ()-[r]->()
    WHERE type(r) IN $types
    RETURN type(r) AS relationType,
           count(r) AS count,
           collect(DISTINCT coalesce(toString(r.clinical_use_status), 'NULL')) AS clinical_use_status,
           collect(DISTINCT coalesce(toString(r.formal_cdss_ready), 'NULL')) AS formal_cdss_ready,
           collect(DISTINCT coalesce(toString(r.knowledge_layer), 'NULL')) AS knowledge_layer
    ORDER BY relationType
    """
    return [dict(row) for row in session.run(query, types=LEGACY_REL_TYPES)]


def count_by_endpoint(session) -> list[dict[str, Any]]:
    query = """
    MATCH (s)-[r]->(t)
    WHERE type(r) IN $types
    RETURN type(r) AS relationType,
           s.entityType AS source_entityType,
           t.entityType AS target_entityType,
           count(r) AS count
    ORDER BY relationType, count DESC
    """
    return [dict(row) for row in session.run(query, types=LEGACY_REL_TYPES)]


def delete_candidates(session) -> int:
    query = """
    MATCH ()-[r]->()
    WHERE type(r) IN $types
      AND r.clinical_use_status = 'knowledge_display_only'
      AND r.formal_cdss_ready = false
      AND r.knowledge_layer = 'textbook_skeleton'
    WITH collect(r) AS rels
    FOREACH (rel IN rels | DELETE rel)
    RETURN size(rels) AS deleted_count
    """
    return int(session.run(query, types=LEGACY_REL_TYPES).single()["deleted_count"])


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 Schema V1.12 后残留的弱语义旧关系")
    parser.add_argument("--dry-run", action="store_true", help="只导出归档和计划，不删除")
    parser.add_argument("--apply", action="store_true", help="导出归档后删除符合条件的旧关系")
    args = parser.parse_args()
    if args.dry_run == args.apply:
        raise SystemExit("必须且只能指定 --dry-run 或 --apply")

    bolt, user, password = read_connection()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session() as session:
            before_counts = count_all_legacy(session)
            before_endpoint = count_by_endpoint(session)
            candidates = fetch_candidates(session)
            report = {
                "mode": "apply" if args.apply else "dry-run",
                "generated_at": now(),
                "legacy_relation_types": LEGACY_REL_TYPES,
                "before_counts": before_counts,
                "before_endpoint_counts": before_endpoint,
                "candidate_count": len(candidates),
                "candidate_by_type": {},
                "safety_rule": {
                    "clinical_use_status": "knowledge_display_only",
                    "formal_cdss_ready": False,
                    "knowledge_layer": "textbook_skeleton",
                    "meaning": "仅清理教材骨架章节提及/弱语义旧关系，不清理正式CDSS推荐关系",
                },
            }
            for row in candidates:
                report["candidate_by_type"][row["relationType"]] = report["candidate_by_type"].get(row["relationType"], 0) + 1

            archive_path = OUTPUT_DIR / (
                "legacy_weak_relations_archive_20260711_apply.json"
                if args.apply
                else "legacy_weak_relations_archive_20260711_dry_run.json"
            )
            report_path = OUTPUT_DIR / (
                "legacy_weak_relations_cleanup_apply_report.json"
                if args.apply
                else "legacy_weak_relations_cleanup_dry_run_report.json"
            )
            write_json(archive_path, candidates)

            if args.apply:
                deleted_count = delete_candidates(session)
                after_counts = count_all_legacy(session)
                after_endpoint = count_by_endpoint(session)
                report["deleted_count"] = deleted_count
                report["after_counts"] = after_counts
                report["after_endpoint_counts"] = after_endpoint
            else:
                report["deleted_count"] = 0

            write_json(report_path, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
