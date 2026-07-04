from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_graph_instance import EVIDENCE_REQUIRED


PASS_STATUS = "ai_prechecked_pass"
LIMITED_STATUS = "ai_prechecked_limited"
BLOCKED_STATUS = "ai_prechecked_blocked"
BATCH_SIGNOFF_STATUS = "clinical_batch_signed_off"


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


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def evidence_key(evidence: dict[str, Any]) -> str:
    return str(evidence.get("evidence_id") or evidence.get("code") or "").strip()


def build_evidence_index(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if node.get("entityType") != "Evidence":
            continue
        key = evidence_key(node)
        if key:
            index[key] = node
    return index


def as_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    return [value]


def first_evidence(rel: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for evidence_id in as_list(rel.get("evidence_ids")):
        evidence = evidence_by_id.get(str(evidence_id))
        if evidence:
            return evidence
    for record in as_list(rel.get("provenance_records_json")):
        if isinstance(record, dict):
            key = str(record.get("evidence_id") or "")
            if key and key in evidence_by_id:
                return evidence_by_id[key]
            return record
    return {}


def evidence_chain(rel: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> str:
    parts: list[str] = []
    for evidence_id in as_list(rel.get("evidence_ids")):
        evidence = evidence_by_id.get(str(evidence_id), {})
        if not evidence:
            continue
        source_name = evidence.get("source_name") or evidence.get("document_id") or "UNKNOWN_SOURCE"
        source_page = evidence.get("source_page")
        page_text = f"#p{source_page}" if source_page not in (None, "") else ""
        ev_id = evidence.get("evidence_id") or evidence_id
        parts.append(f"{source_name}{page_text}#{ev_id}")
    if parts:
        return " | ".join(parts)
    return str(rel.get("evidence_source_chain") or "")


def fill_evidence_required_fields(rel: dict[str, Any], evidence: dict[str, Any]) -> int:
    changed = 0
    source_page = evidence.get("source_page")
    if source_page in (None, "") and (evidence.get("source_type") == "authoritative_textbook" or str(evidence.get("source_name", "")).lower().endswith(".docx")):
        source_page = "N/A"
    defaults = {
        "document_id": evidence.get("document_id"),
        "segment_id": evidence.get("segment_id"),
        "source_name": evidence.get("source_name"),
        "source_type": evidence.get("source_type"),
        "source_version": evidence.get("source_version"),
        "source_section": evidence.get("source_section"),
        "source_page": source_page,
        "evidence_text": evidence.get("evidence_text"),
        "guideline_id": evidence.get("guideline_id"),
        "evidence_id": evidence.get("evidence_id") or evidence.get("code"),
        "recommendation_class": rel.get("recommendation_class") or evidence.get("recommendation_class"),
        "evidence_level": rel.get("evidence_level") or evidence.get("evidence_level"),
        "confidence": evidence.get("confidence") if evidence.get("confidence") not in (None, "") else rel.get("confidence"),
    }
    for field in EVIDENCE_REQUIRED:
        value = defaults.get(field)
        if value in (None, ""):
            continue
        if rel.get(field) != value:
            rel[field] = value
            changed += 1
    return changed


def has_clear_grade(rel: dict[str, Any]) -> bool:
    if rel.get("recommendation_grade_source") == "ungraded_limited_signoff":
        return False
    return rel.get("recommendation_class") not in (None, "", "N/A") and rel.get("evidence_level") not in (None, "", "N/A")


def relation_grade_text(rel: dict[str, Any]) -> str:
    rec_class = rel.get("recommendation_class") or "N/A"
    evidence_level = rel.get("evidence_level") or "N/A"
    return f"{rec_class}/{evidence_level}"


def ensure_limited_grade_fields(rel: dict[str, Any]) -> int:
    """Fill audit-required grade fields without pretending there is a formal guideline grade."""
    if rel.get("recommendation_class") not in (None, "", "N/A") and rel.get("evidence_level") not in (None, "", "N/A"):
        return 0
    changed = 0
    if rel.get("recommendation_class") in (None, "", "N/A"):
        rel["recommendation_class"] = "未分级推荐"
        changed += 1
    if rel.get("evidence_level") in (None, "", "N/A"):
        rel["evidence_level"] = "专家共识/教材证据"
        changed += 1
    rel["recommendation_grade_source"] = "ungraded_limited_signoff"
    rel["recommendation_grade_note"] = "来源未提供I/IIa/A/B等正式推荐等级；为满足CDSS候选字段完整性，按未分级推荐记录，不代表正式上线分级。"
    return changed


def medication_safety_complete(target: dict[str, Any]) -> bool:
    return all(
        target.get(field) not in (None, "", [], {})
        for field in ("dosage", "contraindications", "drug_interactions")
    )


def classify_relation(rel: dict[str, Any], target: dict[str, Any]) -> tuple[str, str, list[str]]:
    reasons: list[str] = []
    if not has_clear_grade(rel):
        reasons.append("recommendation_grade_not_explicit")
    if target.get("entityType") == "Medication" and not medication_safety_complete(target):
        reasons.append("medication_safety_fields_missing")
    if "medication_safety_fields_missing" in reasons:
        return BLOCKED_STATUS, "formal_blocked", reasons
    if "recommendation_grade_not_explicit" in reasons:
        return LIMITED_STATUS, "knowledge_display", reasons
    return PASS_STATUS, "test_recommendation", ["evidence_chain_and_grade_complete"]


def relation_ids_from_register(batch_dir: Path) -> set[str]:
    rows = read_csv(batch_dir / "06_quality_audit" / "cdss_recommendation_readiness_register.csv")
    return {str(row.get("relation_id") or "").strip() for row in rows if str(row.get("relation_id") or "").strip()}


def apply_precheck_signoff(
    batch_dir: Path,
    reviewer_name: str,
    reviewer_role: str,
    reviewed_at: str,
    output_dir: Path,
    apply: bool,
) -> dict[str, Any]:
    nodes_path = batch_dir / "05_data_instance" / "nodes_final.jsonl"
    relations_path = batch_dir / "05_data_instance" / "relations_final.jsonl"
    nodes = read_jsonl(nodes_path)
    relations = read_jsonl(relations_path)
    node_by_code = {str(node.get("code") or ""): node for node in nodes}
    evidence_by_id = build_evidence_index(nodes)
    target_relation_ids = relation_ids_from_register(batch_dir)

    review_rows: list[dict[str, Any]] = []
    changed_relations = 0
    evidence_field_updates = 0
    status_counts: Counter[str] = Counter()

    for rel in relations:
        relation_id = str(rel.get("id") or "")
        if relation_id not in target_relation_ids:
            continue
        target = node_by_code.get(str(rel.get("target_code") or ""), {})
        before = json.dumps(rel, ensure_ascii=False, sort_keys=True)
        evidence = first_evidence(rel, evidence_by_id)
        evidence_field_updates += fill_evidence_required_fields(rel, evidence)
        evidence_field_updates += ensure_limited_grade_fields(rel)
        chain = evidence_chain(rel, evidence_by_id)
        if chain:
            rel["evidence_source_chain"] = chain
        rel["recommendation_class_and_evidence_level"] = relation_grade_text(rel)

        ai_status, release_level, reasons = classify_relation(rel, target)
        rel["ai_evidence_review_status"] = ai_status
        rel["cdss_release_level"] = release_level
        rel["ai_precheck_reasons"] = reasons
        rel["clinical_review_status"] = BATCH_SIGNOFF_STATUS
        rel["clinical_reviewer_name"] = reviewer_name
        rel["clinical_reviewer_role"] = reviewer_role
        rel["clinical_reviewed_at"] = reviewed_at
        rel["clinical_expert_comment"] = "专家同意采用批量签收机制；AI 仅完成证据预审核与分级，不替代正式上线责任。"
        rel["clinical_review_decision_source"] = "AI批量预审核+用户确认专家同意批量签收"
        rel["formal_cdss_ready"] = False
        if release_level != "test_recommendation":
            rel["formal_cdss_block_reason"] = ";".join(reasons)
        else:
            rel.pop("formal_cdss_block_reason", None)

        after = json.dumps(rel, ensure_ascii=False, sort_keys=True)
        if after != before:
            changed_relations += 1
        status_counts[ai_status] += 1
        review_rows.append(
            {
                "batch_id": batch_dir.name,
                "relation_id": relation_id,
                "source_code": rel.get("source_code", ""),
                "relation_type": rel.get("relationType", ""),
                "target_code": rel.get("target_code", ""),
                "target_name": target.get("name", ""),
                "target_type": target.get("entityType", ""),
                "recommendation_class_and_evidence_level": rel.get("recommendation_class_and_evidence_level", ""),
                "evidence_source_chain": rel.get("evidence_source_chain", ""),
                "ai_evidence_review_status": ai_status,
                "cdss_release_level": release_level,
                "formal_cdss_block_reason": rel.get("formal_cdss_block_reason", ""),
                "clinical_review_status": rel.get("clinical_review_status", ""),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "06_CDSS推荐AI预审核表.csv",
        review_rows,
        [
            "batch_id",
            "relation_id",
            "source_code",
            "relation_type",
            "target_code",
            "target_name",
            "target_type",
            "recommendation_class_and_evidence_level",
            "evidence_source_chain",
            "ai_evidence_review_status",
            "cdss_release_level",
            "formal_cdss_block_reason",
            "clinical_review_status",
        ],
    )
    write_csv(
        output_dir / "07_测试推荐层可放行清单.csv",
        [row for row in review_rows if row["cdss_release_level"] == "test_recommendation"],
        [
            "batch_id",
            "relation_id",
            "source_code",
            "relation_type",
            "target_code",
            "target_name",
            "target_type",
            "recommendation_class_and_evidence_level",
            "evidence_source_chain",
        ],
    )
    write_csv(
        output_dir / "08_正式CDSS仍阻断清单.csv",
        [row for row in review_rows if row["cdss_release_level"] != "test_recommendation"],
        [
            "batch_id",
            "relation_id",
            "source_code",
            "relation_type",
            "target_code",
            "target_name",
            "target_type",
            "ai_evidence_review_status",
            "cdss_release_level",
            "formal_cdss_block_reason",
        ],
    )

    if apply and changed_relations:
        write_jsonl(relations_path, relations)

    summary = {
        "batch_id": batch_dir.name,
        "target_relation_count": len(target_relation_ids),
        "review_rows": len(review_rows),
        "updated_relations": changed_relations if apply else 0,
        "evidence_field_updates": evidence_field_updates,
        "ai_prechecked_pass": status_counts[PASS_STATUS],
        "ai_prechecked_limited": status_counts[LIMITED_STATUS],
        "ai_prechecked_blocked": status_counts[BLOCKED_STATUS],
        "clinical_review_status_set_to": BATCH_SIGNOFF_STATUS,
        "formal_cdss_ready_set_true": 0,
        "output_dir": str(output_dir),
    }
    (output_dir / "ai_precheck_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply AI evidence precheck and expert batch signoff metadata.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--reviewer-name", required=True)
    parser.add_argument("--reviewer-role", required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    summary = apply_precheck_signoff(
        args.batch_dir,
        args.reviewer_name,
        args.reviewer_role,
        args.reviewed_at,
        args.output_dir,
        args.apply,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
