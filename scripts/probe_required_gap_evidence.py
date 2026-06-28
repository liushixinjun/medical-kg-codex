from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PATHWAY_TO_RELATION = {
    "etiology": "has_etiology",
    "symptom": "has_symptom",
    "sign": "has_sign",
    "exam": "requires_exam",
    "lab_test": "requires_lab_test",
    "diagnosis_criteria": "has_diagnostic_criteria",
    "treatment_plan": "has_treatment_plan",
    "complication": "may_cause_complication",
    "prognosis": "has_prognosis",
    "follow_up": "has_follow_up",
}

NOISE_PHRASES = {
    "作者简介",
    "主编简介",
    "从事教学工作至今",
    "版权所有",
    "目录",
}

GENERIC_ENTITY_NAMES = {
    "诊断",
    "诊断标准",
    "鉴别诊断",
    "治疗",
    "治疗方案",
    "药物治疗",
    "检查",
    "随访",
    "预后",
    "症状",
    "体征",
    "病因",
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def missing_required_rows(coverage_csv: Path) -> list[dict[str, str]]:
    rows = []
    for row in read_csv_rows(coverage_csv):
        if row.get("applicability_status") == "required" and row.get("coverage_status") == "missing":
            rows.append(row)
    return rows


def clean_text(text: Any, limit: int = 260) -> str:
    value = " ".join(str(text or "").split())
    return value[:limit]


def is_noise(text: str) -> bool:
    return len(text.strip()) < 20 or any(phrase in text for phrase in NOISE_PHRASES)


def evidence_matches(gap: dict[str, str], row: dict[str, Any]) -> bool:
    return str(row.get("disease_code", "")).strip() == str(gap.get("disease_code", "")).strip()


def evidence_name_fallback_matches(gap: dict[str, str], row: dict[str, Any]) -> bool:
    return (
        str(row.get("disease_name", "")).strip()
        and str(row.get("disease_name", "")).strip() == str(gap.get("disease_name", "")).strip()
        and not evidence_matches(gap, row)
    )


def evidence_pathway_matches(gap: dict[str, str], row: dict[str, Any]) -> bool:
    element = str(gap.get("pathway_element", "")).strip()
    return str(row.get("pathway_element", "")).strip() == element or str(row.get("source_section", "")).strip() == element


def candidate_matches(gap: dict[str, str], row: dict[str, str]) -> bool:
    relation = PATHWAY_TO_RELATION.get(str(gap.get("pathway_element", "")).strip())
    if not relation:
        return False
    code_match = str(row.get("disease_code", "")).strip() == str(gap.get("disease_code", "")).strip()
    name_match = str(row.get("disease_name", "")).strip() == str(gap.get("disease_name", "")).strip()
    if not (code_match or name_match):
        return False
    if str(row.get("relationType", "")).strip() != relation:
        return False
    text = str(row.get("evidence_text", "")).strip()
    entity_name = str(row.get("entity_name", "")).strip()
    if is_noise(text):
        return False
    if entity_name in GENERIC_ENTITY_NAMES:
        return False
    return True


def sample_evidence(rows: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        text = clean_text(row.get("evidence_text"))
        if is_noise(text):
            continue
        key = (str(row.get("source_name", "")), str(row.get("source_page", "")), text[:80])
        if key in seen:
            continue
        seen.add(key)
        output.append(
            {
                "source_name": row.get("source_name", ""),
                "source_page": row.get("source_page", ""),
                "pathway_element": row.get("pathway_element", row.get("source_section", "")),
                "evidence_text": text,
            }
        )
        if len(output) >= limit:
            break
    return output


def sample_candidates(rows: list[dict[str, str]], limit: int = 5) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("relationType", "")),
            str(row.get("entity_code", "")),
            str(row.get("entity_name", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(
            {
                "relationType": str(row.get("relationType", "")),
                "entityType": str(row.get("entityType", "")),
                "entity_code": str(row.get("entity_code", "")),
                "entity_name": str(row.get("entity_name", "")),
                "evidence_text": clean_text(row.get("evidence_text"), 220),
            }
        )
        if len(output) >= limit:
            break
    return output


def repair_status_for(exact_count: int, name_fallback_count: int, candidate_count: int) -> str:
    if candidate_count > 0:
        return "LOCAL_BACKFILL_CANDIDATE"
    if exact_count > 0 or name_fallback_count > 0:
        return "EVIDENCE_MAPPING_REVIEW_REQUIRED"
    return "SOURCE_NOT_FOUND_IN_CURRENT_INDEX"


def probe_required_gaps(
    *,
    coverage_csv: Path,
    guideline_jsonl_paths: list[Path],
    textbook_jsonl_paths: list[Path],
    candidate_csv_paths: list[Path],
) -> dict[str, Any]:
    gaps = missing_required_rows(coverage_csv)
    evidence_rows: list[dict[str, Any]] = []
    for path in guideline_jsonl_paths + textbook_jsonl_paths:
        evidence_rows.extend(read_jsonl_rows(path))
    candidate_rows: list[dict[str, str]] = []
    for path in candidate_csv_paths:
        candidate_rows.extend(read_csv_rows(path))

    output_gaps: list[dict[str, Any]] = []
    status_counter: Counter[str] = Counter()
    for gap in gaps:
        disease_code = str(gap.get("disease_code", "")).strip()
        disease_name = str(gap.get("disease_name", "")).strip()
        pathway_element = str(gap.get("pathway_element", "")).strip()
        same_code = [row for row in evidence_rows if evidence_matches(gap, row)]
        same_name_drift = [row for row in evidence_rows if evidence_name_fallback_matches(gap, row)]
        exact = [row for row in same_code if evidence_pathway_matches(gap, row)]
        name_fallback = [row for row in same_name_drift if evidence_pathway_matches(gap, row)]
        candidates = [row for row in candidate_rows if candidate_matches(gap, row)]
        status = repair_status_for(len(exact), len(name_fallback), len(candidates))
        status_counter[status] += 1
        output_gaps.append(
            {
                "disease_code": disease_code,
                "disease_name": disease_name,
                "pathway_element": pathway_element,
                "required_relation": PATHWAY_TO_RELATION.get(pathway_element, ""),
                "exact_evidence_count": len(exact),
                "name_fallback_evidence_count": len(name_fallback),
                "same_disease_any_pathway_evidence_count": len(same_code),
                "candidate_relation_count": len(candidates),
                "repair_status": status,
                "evidence_samples": sample_evidence(exact or name_fallback or same_code),
                "candidate_samples": sample_candidates(candidates),
            }
        )

    return {
        "coverage_csv": str(coverage_csv),
        "summary": {
            "missing_required_count": len(gaps),
            "repair_status_counts": dict(status_counter),
            "guideline_index_count": len(guideline_jsonl_paths),
            "textbook_index_count": len(textbook_jsonl_paths),
            "candidate_index_count": len(candidate_csv_paths),
            "evidence_row_count": len(evidence_rows),
            "candidate_row_count": len(candidate_rows),
        },
        "gaps": output_gaps,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "disease_code",
        "disease_name",
        "pathway_element",
        "required_relation",
        "repair_status",
        "exact_evidence_count",
        "name_fallback_evidence_count",
        "same_disease_any_pathway_evidence_count",
        "candidate_relation_count",
        "evidence_sample_text",
        "candidate_sample_names",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["evidence_sample_text"] = " | ".join(
                str(sample.get("evidence_text", "")) for sample in row.get("evidence_samples", [])
            )
            flat["candidate_sample_names"] = " | ".join(
                str(sample.get("entity_name", "")) for sample in row.get("candidate_samples", [])
            )
            writer.writerow({field: flat.get(field, "") for field in fieldnames})


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe required pathway gaps against guideline/textbook evidence indexes.")
    parser.add_argument("--coverage-csv", type=Path, required=True)
    parser.add_argument("--guideline-jsonl", action="append", type=Path, default=[])
    parser.add_argument("--textbook-jsonl", action="append", type=Path, default=[])
    parser.add_argument("--candidate-csv", action="append", type=Path, default=[])
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    args = parser.parse_args()

    result = probe_required_gaps(
        coverage_csv=args.coverage_csv,
        guideline_jsonl_paths=args.guideline_jsonl,
        textbook_jsonl_paths=args.textbook_jsonl,
        candidate_csv_paths=args.candidate_csv,
    )
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    write_csv(args.out_csv, result["gaps"])
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
