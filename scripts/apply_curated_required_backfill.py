from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


RELATION_CATEGORY = {
    "has_etiology": "clinical",
    "has_symptom": "clinical",
    "has_sign": "clinical",
    "requires_exam": "diagnostic",
    "requires_lab_test": "diagnostic",
    "has_diagnostic_criteria": "diagnostic",
    "has_treatment_plan": "therapeutic",
    "may_cause_complication": "clinical",
    "has_prognosis": "clinical",
    "has_follow_up": "therapeutic",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )
    tmp_path.replace(path)


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def kg_id_from_code(code: str) -> str:
    return f"KG_{code.replace('-', '_')}"


def relation_id(source_code: str, relation_type: str, target_code: str) -> str:
    return stable_id("REL", source_code, relation_type, target_code)


def normalize_node(node: dict[str, Any], batch_defaults: dict[str, Any]) -> dict[str, Any]:
    code = str(node["code"]).strip()
    name = str(node["name"]).strip()
    normalized = {
        "id": node.get("id") or kg_id_from_code(code),
        "code": code,
        "name": name,
        "preferred_name": node.get("preferred_name") or name,
        "display_name": node.get("display_name") or name,
        "entityType": node["entityType"],
        "entityCategory": node["entityCategory"],
        "schema_version": node.get("schema_version") or batch_defaults.get("schema_version") or "V1.1",
        "review_status": node.get("review_status") or "approved",
        "batch_id": node.get("batch_id") or batch_defaults.get("batch_id"),
        "scope_type": node.get("scope_type") or batch_defaults.get("scope_type"),
        "scope_target": node.get("scope_target") or batch_defaults.get("scope_target"),
        "merge_status": node.get("merge_status") or "validated",
        "conflict_status": node.get("conflict_status") or "none",
        "aliases": node.get("aliases") or [],
        "clinical_review_status": node.get("clinical_review_status") or "pending_clinical_review",
        "formal_cdss_ready": bool(node.get("formal_cdss_ready") or False),
        "source_quality": node.get("source_quality") or "curated_required_gap_backfill",
    }
    for optional in ("description", "name_en", "abbr", "backfill_reason", "curation_note"):
        if optional in node:
            normalized[optional] = node[optional]
    return normalized


def merge_aliases(existing: dict[str, Any], incoming_aliases: Any) -> bool:
    if not incoming_aliases:
        return False
    if isinstance(incoming_aliases, str):
        incoming = [incoming_aliases]
    else:
        incoming = list(incoming_aliases)
    current = existing.get("aliases")
    if current is None:
        current_list: list[str] = []
    elif isinstance(current, str):
        current_list = [current]
    else:
        current_list = list(current)
    changed = False
    for alias in incoming:
        alias = str(alias).strip()
        if alias and alias not in current_list:
            current_list.append(alias)
            changed = True
    if changed:
        existing["aliases"] = current_list
    return changed


def normalize_relation(relation: dict[str, Any], source: dict[str, Any], target: dict[str, Any], batch_defaults: dict[str, Any]) -> dict[str, Any]:
    source_code = str(relation["source_code"]).strip()
    target_code = str(relation["target_code"]).strip()
    relation_type = str(relation["relationType"]).strip()
    records = relation.get("provenance_records_json") or []
    first = records[0] if records else {}
    normalized = {
        "id": relation.get("id") or relation_id(source_code, relation_type, target_code),
        "source_code": source_code,
        "relationType": relation_type,
        "target_code": target_code,
        "relationCategory": relation.get("relationCategory") or RELATION_CATEGORY.get(relation_type, "clinical"),
        "batch_id": relation.get("batch_id") or batch_defaults.get("batch_id") or source.get("batch_id"),
        "schema_version": relation.get("schema_version") or batch_defaults.get("schema_version") or "V1.1",
        "review_status": relation.get("review_status") or "approved",
        "polarity": relation.get("polarity") or "positive",
        "scope_type": relation.get("scope_type") or batch_defaults.get("scope_type") or source.get("scope_type"),
        "scope_target": relation.get("scope_target") or batch_defaults.get("scope_target") or source.get("scope_target"),
        "merge_status": relation.get("merge_status") or "validated",
        "conflict_status": relation.get("conflict_status") or "none",
        "source_quality": relation.get("source_quality") or "curated_required_gap_backfill",
        "provenance_records_json": records,
        "evidence_ids": [record.get("evidence_id") for record in records if record.get("evidence_id")],
        "document_ids": sorted({record.get("document_id") for record in records if record.get("document_id")}),
        "source_names": sorted({record.get("source_name") for record in records if record.get("source_name")}),
        "source_types": sorted({record.get("source_type") for record in records if record.get("source_type")}),
        "evidence_count": len(records),
        "clinical_review_status": relation.get("clinical_review_status") or "pending_clinical_review",
        "formal_cdss_ready": bool(relation.get("formal_cdss_ready") or False),
        "backfill_reason": relation.get("backfill_reason") or "required_pathway_gap_with_textbook_or_guideline_evidence",
    }
    for field in (
        "document_id",
        "segment_id",
        "source_name",
        "source_type",
        "source_version",
        "source_section",
        "source_page",
        "evidence_text",
        "guideline_id",
        "evidence_id",
        "recommendation_class",
        "evidence_level",
        "confidence",
    ):
        normalized[field] = relation.get(field, first.get(field))
    normalized.setdefault("recommendation_class", "N/A")
    normalized.setdefault("evidence_level", "N/A")
    normalized.setdefault("confidence", 0.86)
    return normalized


def batch_defaults(batch_spec: dict[str, Any], batch_dir: Path) -> dict[str, Any]:
    return {
        "batch_id": batch_spec.get("batch_id") or batch_dir.name,
        "schema_version": batch_spec.get("schema_version") or "V1.1",
        "scope_type": batch_spec.get("scope_type") or "category",
        "scope_target": batch_spec.get("scope_target") or "",
    }


def apply_batch_spec(batch_spec: dict[str, Any]) -> dict[str, Any]:
    batch_dir = Path(batch_spec["batch_dir"])
    data_dir = batch_dir / "05_data_instance"
    nodes_path = data_dir / "nodes_final.jsonl"
    relations_path = data_dir / "relations_final.jsonl"
    nodes = read_jsonl(nodes_path)
    relations = read_jsonl(relations_path)
    node_by_code = {str(node.get("code", "")): node for node in nodes}
    relation_keys = {
        (str(rel.get("source_code", "")), str(rel.get("relationType", "")), str(rel.get("target_code", "")))
        for rel in relations
    }
    defaults = batch_defaults(batch_spec, batch_dir)

    added_nodes = []
    updated_nodes = []
    for node_spec in batch_spec.get("nodes", []):
        code = str(node_spec["code"]).strip()
        if code in node_by_code:
            if merge_aliases(node_by_code[code], node_spec.get("aliases")):
                updated_nodes.append(node_by_code[code])
            continue
        node = normalize_node(node_spec, defaults)
        nodes.append(node)
        node_by_code[node["code"]] = node
        added_nodes.append(node)

    added_relations = []
    for rel_spec in batch_spec.get("relations", []):
        source_code = str(rel_spec.get("source_code", "")).strip()
        target_code = str(rel_spec.get("target_code", "")).strip()
        relation_type = str(rel_spec.get("relationType", "")).strip()
        if source_code not in node_by_code or target_code not in node_by_code:
            raise ValueError(f"Missing endpoint for relation: {source_code} -[{relation_type}]-> {target_code}")
        key = (source_code, relation_type, target_code)
        if key in relation_keys:
            continue
        relation = normalize_relation(rel_spec, node_by_code[source_code], node_by_code[target_code], defaults)
        relations.append(relation)
        relation_keys.add(key)
        added_relations.append(relation)

    if added_nodes or updated_nodes:
        write_jsonl(nodes_path, nodes)
    if added_relations:
        write_jsonl(relations_path, relations)
    return {
        "batch_dir": str(batch_dir),
        "added_nodes": len(added_nodes),
        "updated_nodes": len(updated_nodes),
        "added_relations": len(added_relations),
        "added_node_codes": [node["code"] for node in added_nodes],
        "updated_node_codes": [node["code"] for node in updated_nodes],
        "added_relation_ids": [rel["id"] for rel in added_relations],
    }


def apply_backfill_spec(spec: dict[str, Any]) -> dict[str, Any]:
    batch_summaries = [apply_batch_spec(batch_spec) for batch_spec in spec.get("batches", [])]
    return {
        "spec_id": spec.get("id", ""),
        "batch_count": len(batch_summaries),
        "added_nodes": sum(item["added_nodes"] for item in batch_summaries),
        "updated_nodes": sum(item["updated_nodes"] for item in batch_summaries),
        "added_relations": sum(item["added_relations"] for item in batch_summaries),
        "batches": batch_summaries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply curated required-pathway backfill to local JSONL graph data.")
    parser.add_argument("--spec-json", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec_json.read_text(encoding="utf-8-sig"))
    summary = apply_backfill_spec(spec)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
