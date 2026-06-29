from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


RELATION_UPDATE_FIELDS = {
    "applicable_population": "applicable_population",
    "exclusion_or_contraindication": "exclusion_criteria",
    "clinical_rule_or_clinical_pathway": "clinical_rule_or_clinical_pathway",
    "recommendation_class": "recommendation_class",
    "evidence_level": "evidence_level",
    "medication_contraindication": "medication_contraindication",
}
TARGET_UPDATE_FIELDS = {
    "medication_dosage": "dosage",
    "medication_interaction": "drug_interactions",
    "medication_aliases": "aliases",
}
REQUIRED_REVIEW_FIELDS = ("reviewer_name", "reviewer_role", "reviewed_at")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )
    tmp_path.replace(path)


def read_decisions(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def split_aliases(value: str) -> list[str]:
    return [item.strip() for item in value.replace("|", ";").replace(",", ";").split(";") if item.strip()]


def apply_value(target: dict[str, Any], field: str, value: str) -> bool:
    value = str(value or "").strip()
    if not value:
        return False
    if field == "aliases":
        incoming = split_aliases(value)
        current = target.get("aliases") or []
        if isinstance(current, str):
            current = [current]
        changed = False
        for alias in incoming:
            if alias not in current:
                current.append(alias)
                changed = True
        if changed:
            target["aliases"] = current
        return changed
    if target.get(field) == value:
        return False
    target[field] = value
    return True


def validate_approval(row: dict[str, str]) -> None:
    missing = [field for field in REQUIRED_REVIEW_FIELDS if not str(row.get(field) or "").strip()]
    if missing:
        raise ValueError(f"Approved row missing reviewer metadata for relation {row.get('relation_id')}: {','.join(missing)}")


def apply_decisions(batch_dirs: list[Path], decisions_csv: Path) -> dict[str, Any]:
    batch_by_id = {batch_dir.name: batch_dir for batch_dir in batch_dirs}
    decisions = read_decisions(decisions_csv)
    approved_rows = [row for row in decisions if str(row.get("clinical_review_decision", "")).strip().lower() == "approve"]
    rejected_rows = [row for row in decisions if str(row.get("clinical_review_decision", "")).strip().lower() == "reject"]
    revised_rows = [row for row in decisions if str(row.get("clinical_review_decision", "")).strip().lower() == "revise"]

    updated_relations = 0
    updated_nodes = 0
    updated_relation_ids: list[str] = []
    touched_batches: set[str] = set()

    rows_by_batch: dict[str, list[dict[str, str]]] = {}
    for row in approved_rows:
        validate_approval(row)
        rows_by_batch.setdefault(str(row.get("batch_id", "")).strip(), []).append(row)

    for batch_id, rows in rows_by_batch.items():
        batch_dir = batch_by_id.get(batch_id)
        if not batch_dir:
            raise ValueError(f"Unknown batch_id in decisions CSV: {batch_id}")
        nodes_path = batch_dir / "05_data_instance" / "nodes_final.jsonl"
        rels_path = batch_dir / "05_data_instance" / "relations_final.jsonl"
        nodes = read_jsonl(nodes_path)
        rels = read_jsonl(rels_path)
        node_by_code = {str(node.get("code", "")): node for node in nodes}
        rel_by_id = {str(rel.get("id", "")): rel for rel in rels}
        batch_rel_updates = 0
        batch_node_updates = 0

        for row in rows:
            relation_id = str(row.get("relation_id", "")).strip()
            rel = rel_by_id.get(relation_id)
            if rel is None:
                raise ValueError(f"Unknown relation_id in decisions CSV: {relation_id}")
            target = node_by_code.get(str(rel.get("target_code", "")), {})

            changed_rel = False
            changed_node = False
            for csv_field, rel_field in RELATION_UPDATE_FIELDS.items():
                changed_rel = apply_value(rel, rel_field, row.get(csv_field, "")) or changed_rel
            for csv_field, node_field in TARGET_UPDATE_FIELDS.items():
                changed_node = apply_value(target, node_field, row.get(csv_field, "")) or changed_node

            for field in ("reviewer_name", "reviewer_role", "reviewed_at", "expert_comment"):
                value = str(row.get(field, "") or "").strip()
                if value:
                    rel[f"clinical_{field}"] = value
            rel["clinical_review_status"] = "clinical_approved"
            rel["formal_cdss_ready"] = False
            rel["clinical_review_decision_source"] = str(decisions_csv)
            changed_rel = True

            if changed_rel:
                batch_rel_updates += 1
                updated_relation_ids.append(relation_id)
            if changed_node:
                batch_node_updates += 1

        if batch_rel_updates:
            write_jsonl(rels_path, rels)
        if batch_node_updates:
            write_jsonl(nodes_path, nodes)
        updated_relations += batch_rel_updates
        updated_nodes += batch_node_updates
        if batch_rel_updates or batch_node_updates:
            touched_batches.add(batch_id)

    return {
        "decision_csv": str(decisions_csv),
        "approved_input_rows": len(approved_rows),
        "rejected_input_rows": len(rejected_rows),
        "revise_input_rows": len(revised_rows),
        "updated_relations": updated_relations,
        "updated_nodes": updated_nodes,
        "updated_relation_ids": updated_relation_ids,
        "touched_batches": sorted(touched_batches),
        "formal_cdss_ready_set_true": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply approved clinical review decisions to local JSONL graph data.")
    parser.add_argument("--batch-dir", action="append", type=Path, required=True)
    parser.add_argument("--decisions-csv", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    args = parser.parse_args()
    summary = apply_decisions(args.batch_dir, args.decisions_csv)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
