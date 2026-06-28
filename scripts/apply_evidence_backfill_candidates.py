from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


RELATION_CATEGORY = {
    "has_etiology": "clinical",
    "has_pathophysiology": "clinical",
    "has_epidemiology": "clinical",
    "has_risk_factor": "clinical",
    "has_symptom": "clinical",
    "has_sign": "clinical",
    "may_cause_complication": "clinical",
    "has_prognosis": "clinical",
    "requires_exam": "diagnostic",
    "requires_lab_test": "diagnostic",
    "has_diagnostic_criteria": "diagnostic",
    "differentiates_from": "diagnostic",
    "has_risk_stratification": "risk",
    "has_treatment_plan": "therapeutic",
    "treated_by_medication": "therapeutic",
    "treated_by_procedure": "therapeutic",
    "has_follow_up": "therapeutic",
}


TEXTBOOK_DOCUMENT_ID = "DOC-CARD-INTERNAL-MEDICINE-TEXTBOOK-10"
TEXTBOOK_SOURCE_NAME = "内科学教材第10版"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )
    tmp_path.replace(path)


def read_csv_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def stable_relation_id(source_code: str, relation_type: str, target_code: str) -> str:
    digest = hashlib.sha1(f"{source_code}|{relation_type}|{target_code}".encode("utf-8")).hexdigest()[:12].upper()
    return f"REL-{digest}"


def stable_fallback_evidence_id(row: dict) -> str:
    raw = "|".join(
        [
            str(row.get("disease_code", "")),
            str(row.get("relationType", "")),
            str(row.get("entity_code", "")),
            str(row.get("evidence_text", "")),
        ]
    )
    return f"EVD-BACKFILL-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:14].upper()}"


def candidate_relation_key(row: dict) -> tuple[str, str, str]:
    return (
        str(row.get("disease_code", "")).strip(),
        str(row.get("relationType", "")).strip(),
        str(row.get("entity_code", "")).strip(),
    )


def evidence_record(row: dict) -> dict:
    evidence_id = str(row.get("evidence_code") or stable_fallback_evidence_id(row)).strip()
    return {
        "document_id": TEXTBOOK_DOCUMENT_ID,
        "segment_id": evidence_id,
        "source_name": TEXTBOOK_SOURCE_NAME,
        "source_type": "textbook",
        "source_version": "第10版",
        "source_section": "textbook_evidence_backfill",
        "source_page": None,
        "line_number": str(row.get("line_number", "")).strip() or None,
        "disease_code": str(row.get("disease_code", "")).strip(),
        "disease_name": str(row.get("disease_name", "")).strip(),
        "target_code": str(row.get("entity_code", "")).strip(),
        "target_name": str(row.get("entity_name", "")).strip(),
        "target_type": str(row.get("entityType", "")).strip(),
        "relationType": str(row.get("relationType", "")).strip(),
        "evidence_text": str(row.get("evidence_text", "")).strip(),
        "evidence_id": evidence_id,
        "recommendation_class": None,
        "evidence_level": None,
        "confidence": 0.82,
        "source_index_file": str(row.get("source_index_file", "")).strip(),
    }


def unique_evidence_records(rows: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    records: list[dict] = []
    for row in rows:
        record = evidence_record(row)
        key = (str(record.get("evidence_id", "")), str(record.get("evidence_text", "")))
        if key in seen:
            continue
        seen.add(key)
        records.append(record)
    return records


def relation_from_candidate_group(source: dict, target: dict, relation_type: str, candidate_rows: list[dict], batch_dir: Path) -> dict:
    records = unique_evidence_records(candidate_rows)
    first_record = records[0] if records else {}
    source_code = str(source.get("code", ""))
    target_code = str(target.get("code", ""))
    document_ids = sorted({str(record["document_id"]) for record in records if record.get("document_id")})
    evidence_ids = [str(record["evidence_id"]) for record in records if record.get("evidence_id")]
    source_names = sorted({str(record["source_name"]) for record in records if record.get("source_name")})
    source_types = sorted({str(record["source_type"]) for record in records if record.get("source_type")})
    return {
        "id": stable_relation_id(source_code, relation_type, target_code),
        "source_code": source_code,
        "relationType": relation_type,
        "target_code": target_code,
        "relationCategory": RELATION_CATEGORY.get(relation_type, "clinical"),
        "batch_id": str(source.get("batch_id") or batch_dir.name),
        "schema_version": str(source.get("schema_version") or target.get("schema_version") or "V1.4"),
        "review_status": "approved",
        "polarity": "positive",
        "scope_type": str(source.get("scope_type") or "specialty"),
        "scope_target": str(source.get("scope_target") or "心血管内科"),
        "merge_status": "validated",
        "conflict_status": "none",
        "source_quality": "textbook_evidence_backfill_candidate",
        "provenance_records_json": records,
        "evidence_ids": evidence_ids,
        "document_ids": document_ids,
        "source_names": source_names,
        "source_types": source_types,
        "evidence_count": len(records),
        "document_id": first_record.get("document_id"),
        "segment_id": first_record.get("segment_id"),
        "source_name": first_record.get("source_name"),
        "source_type": first_record.get("source_type"),
        "source_version": first_record.get("source_version"),
        "source_section": first_record.get("source_section"),
        "source_page": first_record.get("source_page"),
        "line_number": first_record.get("line_number"),
        "evidence_text": first_record.get("evidence_text"),
        "recommendation_class": None,
        "evidence_level": None,
        "guideline_id": None,
        "evidence_id": first_record.get("evidence_id"),
        "confidence": first_record.get("confidence", 0.82),
        "clinical_review_status": "pending_clinical_review",
        "formal_cdss_ready": False,
    }


def apply_candidate_rows_to_batch(batch_dir: Path, rows: list[dict]) -> dict:
    batch_dir = Path(batch_dir)
    data_dir = batch_dir / "05_data_instance"
    nodes_path = data_dir / "nodes_final.jsonl"
    relations_path = data_dir / "relations_final.jsonl"
    nodes = read_jsonl(nodes_path)
    relations = read_jsonl(relations_path)
    node_by_code = {str(node.get("code", "")): node for node in nodes}
    existing_keys = {
        (str(rel.get("source_code", "")), str(rel.get("relationType", "")), str(rel.get("target_code", "")))
        for rel in relations
    }
    accepted_rows = [row for row in rows if str(row.get("classification", "")).strip() == "ACCEPT_CANDIDATE"]
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    skipped_existing = 0
    skipped_missing_node = 0
    for row in accepted_rows:
        key = candidate_relation_key(row)
        source_code, relation_type, target_code = key
        if not source_code or not relation_type or not target_code:
            skipped_missing_node += 1
            continue
        if key in existing_keys:
            skipped_existing += 1
            continue
        if source_code not in node_by_code or target_code not in node_by_code:
            skipped_missing_node += 1
            continue
        grouped.setdefault(key, []).append(row)

    added_relations: list[dict] = []
    for (source_code, relation_type, target_code), candidate_rows in grouped.items():
        relation = relation_from_candidate_group(
            node_by_code[source_code],
            node_by_code[target_code],
            relation_type,
            candidate_rows,
            batch_dir,
        )
        relations.append(relation)
        added_relations.append(relation)
        existing_keys.add((source_code, relation_type, target_code))

    if added_relations:
        write_jsonl(relations_path, relations)

    return {
        "batch_dir": str(batch_dir),
        "input_rows": len(rows),
        "accepted_rows": len(accepted_rows),
        "unique_candidate_relations": len(grouped),
        "added_relations": len(added_relations),
        "added_evidence_records": sum(int(rel.get("evidence_count", 0)) for rel in added_relations),
        "skipped_existing_relations": skipped_existing,
        "skipped_missing_node": skipped_missing_node,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply accepted evidence-backfill candidates to local JSONL graph data only.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    args = parser.parse_args()
    summary = apply_candidate_rows_to_batch(args.batch_dir, read_csv_rows(args.candidate_csv))
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
