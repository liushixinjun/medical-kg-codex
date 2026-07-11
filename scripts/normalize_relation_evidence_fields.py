from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


TOP_LEVEL_EVIDENCE_FIELDS = {
    "document_id",
    "segment_id",
    "source_name",
    "source_type",
    "source_version",
    "source_section",
    "source_page",
    "evidence_text",
    "recommendation_class",
    "evidence_level",
}


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def parse_provenance(value: object) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    return []


def is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def score_provenance(record: dict) -> tuple[int, int, int, int]:
    source_type = str(record.get("source_type") or "")
    source_name = str(record.get("source_name") or "")
    return (
        1 if is_present(record.get("source_page")) else 0,
        1 if source_type in {"guideline", "authoritative_guideline", "expert_consensus", "authoritative_textbook"} else 0,
        1 if source_name.lower().endswith(".pdf") else 0,
        len(str(record.get("evidence_text") or "")),
    )


def best_provenance(records: list[dict]) -> dict | None:
    if not records:
        return None
    return max(records, key=score_provenance)


def normalize_relation(rel: dict) -> tuple[bool, str]:
    changed = False
    reasons: list[str] = []
    records = parse_provenance(rel.get("provenance_records_json"))
    best = best_provenance(records)
    if best:
        should_promote_best = not is_present(rel.get("source_page")) and is_present(best.get("source_page"))
        for field in TOP_LEVEL_EVIDENCE_FIELDS:
            best_value = best.get(field)
            if not is_present(best_value):
                continue
            if should_promote_best or not is_present(rel.get(field)):
                if rel.get(field) != best_value:
                    rel[field] = best_value
                    changed = True
                    reasons.append(f"promote_{field}_from_provenance")
        if not is_present(rel.get("guideline_id")) and is_present(rel.get("document_id")):
            rel["guideline_id"] = f"SRC-{rel['document_id']}"
            changed = True
            reasons.append("derive_guideline_id_from_document_id")
        if not is_present(rel.get("evidence_id")) and is_present(rel.get("segment_id")):
            rel["evidence_id"] = "EVD-" + hashlib.sha1(str(rel["segment_id"]).encode("utf-8")).hexdigest().upper()[:20]
            changed = True
            reasons.append("derive_evidence_id_from_segment_id")
    else:
        if not is_present(rel.get("guideline_id")) and is_present(rel.get("document_id")):
            rel["guideline_id"] = f"SRC-{rel['document_id']}"
            changed = True
            reasons.append("derive_guideline_id_from_document_id")
    if not is_present(rel.get("source_page")) and is_present(rel.get("source_name")):
        source_name = str(rel.get("source_name") or "").lower()
        if not source_name.endswith(".pdf"):
            rel["source_page"] = "N/A-非分页来源"
            changed = True
            reasons.append("mark_source_page_not_applicable_for_non_paginated_source")
    return changed, "|".join(sorted(set(reasons)))


def discover_graph_dirs(collection_root: Path) -> list[Path]:
    graph_dirs = []
    foundation = collection_root / "00_foundation_skeleton"
    if (foundation / "05_data_instance" / "relations_final.jsonl").exists():
        graph_dirs.append(foundation)
    graph_dirs.extend(
        graph_dir
        for graph_dir in sorted(collection_root.glob("BATCH-*"))
        if (graph_dir / "05_data_instance" / "relations_final.jsonl").exists()
    )
    return graph_dirs


def normalize_graph_dir(graph_dir: Path, dry_run: bool = False) -> dict:
    data_dir = graph_dir / "05_data_instance"
    audit_dir = graph_dir / "06_quality_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    relations_path = data_dir / "relations_final.jsonl"
    relations = read_jsonl(relations_path)
    rows: list[dict] = []
    for rel in relations:
        changed, reason = normalize_relation(rel)
        if changed:
            rows.append(
                {
                    "relation_id": rel.get("id", ""),
                    "relationType": rel.get("relationType", ""),
                    "source_code": rel.get("source_code", ""),
                    "target_code": rel.get("target_code", ""),
                    "document_id": rel.get("document_id", ""),
                    "source_name": rel.get("source_name", ""),
                    "source_page": rel.get("source_page", ""),
                    "guideline_id": rel.get("guideline_id", ""),
                    "reason": reason,
                }
            )
    if rows and not dry_run:
        write_jsonl(relations_path, relations)
    with (audit_dir / "relation_evidence_field_normalization.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "relation_id",
                "relationType",
                "source_code",
                "target_code",
                "document_id",
                "source_name",
                "source_page",
                "guideline_id",
                "reason",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    summary = {"graph_dir": graph_dir.name, "dry_run": dry_run, "normalized_relation_count": len(rows)}
    with (audit_dir / "relation_evidence_field_normalization_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize top-level relation evidence fields from provenance records.")
    parser.add_argument("--collection-root", type=Path)
    parser.add_argument("--graph-dir", type=Path, action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    graph_dirs = list(args.graph_dir)
    if args.collection_root:
        graph_dirs.extend(discover_graph_dirs(args.collection_root))
    if not graph_dirs:
        parser.error("Provide --graph-dir or --collection-root")

    seen: set[Path] = set()
    for graph_dir in graph_dirs:
        graph_dir = Path(graph_dir)
        if graph_dir in seen:
            continue
        seen.add(graph_dir)
        summary = normalize_graph_dir(graph_dir, dry_run=args.dry_run)
        print(summary["graph_dir"], "normalized=" + str(summary["normalized_relation_count"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
