from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


REVIEW_COLUMNS = [
    "batch_id",
    "relation_id",
    "source_code",
    "source_name",
    "relation_type",
    "target_code",
    "target_name",
    "target_type",
    "missing_fields",
    "clinical_review_status",
    "evidence_source_chain",
    "evidence_text_sample",
    "required_action",
    "clinical_review_decision",
    "reviewer_name",
    "reviewer_role",
    "reviewed_at",
    "expert_comment",
    "applicable_population",
    "exclusion_or_contraindication",
    "clinical_rule_or_clinical_pathway",
    "recommendation_class",
    "evidence_level",
    "medication_dosage",
    "medication_contraindication",
    "medication_interaction",
    "medication_aliases",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] = REVIEW_COLUMNS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def evidence_chain(rel: dict[str, Any]) -> str:
    records = rel.get("provenance_records_json") or []
    if isinstance(records, str):
        try:
            records = json.loads(records)
        except json.JSONDecodeError:
            records = []
    if records:
        chains = []
        for record in records[:3]:
            source_name = record.get("source_name") or rel.get("source_name") or ""
            source_page = record.get("source_page") or rel.get("source_page") or ""
            evidence_id = record.get("evidence_id") or rel.get("evidence_id") or ""
            chains.append(f"{source_name}#p{source_page}#{evidence_id}".strip("#"))
        return " | ".join(chains)
    source_name = rel.get("source_name") or ",".join(rel.get("source_names") or [])
    source_page = rel.get("source_page") or ""
    evidence_id = rel.get("evidence_id") or ",".join(rel.get("evidence_ids") or [])
    return f"{source_name}#p{source_page}#{evidence_id}".strip("#")


def evidence_sample(rel: dict[str, Any], limit: int = 260) -> str:
    text = str(rel.get("evidence_text") or "")
    if not text:
        records = rel.get("provenance_records_json") or []
        if isinstance(records, str):
            try:
                records = json.loads(records)
            except json.JSONDecodeError:
                records = []
        if records:
            text = str(records[0].get("evidence_text") or "")
    return " ".join(text.split())[:limit]


def build_pack(batch_dirs: list[Path], out_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing_field_counter: Counter[str] = Counter()
    batch_counter: Counter[str] = Counter()

    for batch_dir in batch_dirs:
        batch_id = batch_dir.name
        audit_csv = batch_dir / "06_quality_audit" / "cdss_recommendation_readiness_register.csv"
        readiness_rows = read_csv(audit_csv)
        rels = read_jsonl(batch_dir / "05_data_instance" / "relations_final.jsonl")
        rel_by_id = {str(rel.get("id", "")): rel for rel in rels}
        for item in readiness_rows:
            rel = rel_by_id.get(item.get("relation_id", ""), {})
            missing_fields = item.get("missing_fields", "")
            for field in [part.strip() for part in missing_fields.replace("|", ";").split(";") if part.strip()]:
                missing_field_counter[field] += 1
            batch_counter[batch_id] += 1
            rows.append(
                {
                    "batch_id": batch_id,
                    "relation_id": item.get("relation_id", ""),
                    "source_code": item.get("source_code", ""),
                    "source_name": item.get("source_name", ""),
                    "relation_type": item.get("relation_type", ""),
                    "target_code": item.get("target_code", ""),
                    "target_name": item.get("target_name", ""),
                    "target_type": item.get("target_type", ""),
                    "missing_fields": missing_fields,
                    "clinical_review_status": item.get("clinical_review_status", ""),
                    "evidence_source_chain": evidence_chain(rel),
                    "evidence_text_sample": evidence_sample(rel),
                    "required_action": "补齐缺失字段；临床专家审核后填写 approve/reject/revise；未审核不得进入正式 CDSS。",
                }
            )

    out_dir.mkdir(parents=True, exist_ok=True)
    review_csv = out_dir / "clinical_review_items.csv"
    write_csv(review_csv, rows)
    summary = {
        "review_item_count": len(rows),
        "batch_counts": dict(batch_counter),
        "missing_field_counts": dict(missing_field_counter),
        "review_csv": str(review_csv),
        "decision_rule": "只有 clinical_review_decision=approve 且 reviewer_name/reviewer_role/reviewed_at 完整的行可回写为 clinical_approved。",
    }
    (out_dir / "clinical_review_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build clinical review package from CDSS readiness audit registers.")
    parser.add_argument("--batch-dir", action="append", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = build_pack(args.batch_dir, args.out_dir)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
