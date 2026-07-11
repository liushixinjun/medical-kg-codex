from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


EVIDENCE_REQUIRED = {
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
}


# 这些关系会被 CDSS 用于临床场景展示/推理，不限于治疗推荐。
CDSS_SCENARIO_RELATION_TYPES = {
    "has_etiology",
    "has_pathophysiology",
    "has_epidemiology",
    "has_risk_factor",
    "has_symptom",
    "has_sign",
    "may_cause_complication",
    "has_prognosis",
    "requires_exam",
    "requires_lab_test",
    "has_threshold_rule",
    "has_diagnostic_criteria",
    "differentiates_from",
    "has_risk_stratification",
    "uses_scoring_scale",
    "has_clinical_rule",
    "has_classification_stage",
    "has_treatment_plan",
    "treated_by_medication",
    "treated_by_procedure",
    "includes_medication",
    "includes_procedure",
    "has_indication",
    "has_contraindication",
    "has_timing",
    "has_time_window",
    "has_follow_up",
    "has_clinical_pathway",
    "interacts_with",
}


ACTIONABLE_SOURCE_TYPES = {
    "Disease",
    "TreatmentPlan",
    "Medication",
    "Procedure",
    "Exam",
    "LabTest",
    "ExamIndicator",
    "TreatmentTiming",
}


def read_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    if not path.exists():
        return items
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def discover_graph_dirs(root: Path) -> list[Path]:
    candidates = []
    for graph_dir in sorted(root.glob("BATCH-*")) + [root / "00_foundation_skeleton"]:
        if (graph_dir / "05_data_instance" / "nodes_final.jsonl").exists() and (
            graph_dir / "05_data_instance" / "relations_final.jsonl"
        ).exists():
            candidates.append(graph_dir)
    return candidates


def audit_graph_dir(graph_dir: Path) -> tuple[list[dict], dict]:
    data_dir = graph_dir / "05_data_instance"
    nodes = read_jsonl(data_dir / "nodes_final.jsonl")
    relations = read_jsonl(data_dir / "relations_final.jsonl")
    node_by_code = {node.get("code"): node for node in nodes}

    rows: list[dict] = []
    counts = Counter()
    missing_by_relation_type = Counter()
    missing_field_counter = Counter()

    for rel in relations:
        relation_type = rel.get("relationType")
        if relation_type not in CDSS_SCENARIO_RELATION_TYPES:
            continue
        source = node_by_code.get(rel.get("source_code"), {})
        target = node_by_code.get(rel.get("target_code"), {})
        source_type = source.get("entityType", "")
        target_type = target.get("entityType", "")
        counts["scenario_relation_count"] += 1
        missing_fields = sorted(field for field in EVIDENCE_REQUIRED if not is_present(rel.get(field)))
        provenance = rel.get("provenance_records_json")
        if isinstance(provenance, str):
            try:
                provenance = json.loads(provenance)
            except json.JSONDecodeError:
                provenance = []
        has_provenance = isinstance(provenance, list) and len(provenance) > 0
        has_trace_text = is_present(rel.get("evidence_text")) or has_provenance
        is_actionable_source = source_type in ACTIONABLE_SOURCE_TYPES
        if missing_fields or not has_trace_text:
            severity = "blocking_for_cdss_scenario" if is_actionable_source else "warning"
            counts["scenario_issue_count"] += 1
            if severity == "blocking_for_cdss_scenario":
                counts["blocking_issue_count"] += 1
            missing_by_relation_type[relation_type] += 1
            for field in missing_fields:
                missing_field_counter[field] += 1
            rows.append(
                {
                    "batch_dir": graph_dir.name,
                    "relation_id": rel.get("id", ""),
                    "severity": severity,
                    "relationType": relation_type,
                    "relationCategory": rel.get("relationCategory", ""),
                    "source_code": rel.get("source_code", ""),
                    "source_name": source.get("name", ""),
                    "source_entityType": source_type,
                    "target_code": rel.get("target_code", ""),
                    "target_name": target.get("name", ""),
                    "target_entityType": target_type,
                    "missing_fields": "|".join(missing_fields),
                    "has_provenance_records": str(has_provenance).lower(),
                    "has_evidence_text_or_provenance": str(has_trace_text).lower(),
                    "source_note": rel.get("source_note", ""),
                    "source_quality": rel.get("source_quality", ""),
                }
            )

    summary = {
        "graph_dir": graph_dir.name,
        "scenario_relation_count": counts["scenario_relation_count"],
        "scenario_issue_count": counts["scenario_issue_count"],
        "blocking_issue_count": counts["blocking_issue_count"],
        "missing_by_relation_type": dict(sorted(missing_by_relation_type.items())),
        "missing_field_counter": dict(sorted(missing_field_counter.items())),
        "gate": "passed" if counts["blocking_issue_count"] == 0 else "failed",
    }
    return rows, summary


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit CDSS scenario relations for full evidence-chain coverage.")
    parser.add_argument("--collection-root", type=Path, required=True)
    parser.add_argument("--graph-dir", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    graph_dirs = args.graph_dir or discover_graph_dirs(args.collection_root)
    all_rows: list[dict] = []
    summaries: list[dict] = []
    for graph_dir in graph_dirs:
        rows, summary = audit_graph_dir(Path(graph_dir))
        all_rows.extend(rows)
        summaries.append(summary)

    issue_fields = [
        "batch_dir",
        "relation_id",
        "severity",
        "relationType",
        "relationCategory",
        "source_code",
        "source_name",
        "source_entityType",
        "target_code",
        "target_name",
        "target_entityType",
        "missing_fields",
        "has_provenance_records",
        "has_evidence_text_or_provenance",
        "source_note",
        "source_quality",
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "cdss_scenario_evidence_issues.csv", all_rows, issue_fields)
    with (args.output_dir / "cdss_scenario_evidence_summary.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "audited_graph_count": len(summaries),
                "total_scenario_relation_count": sum(item["scenario_relation_count"] for item in summaries),
                "total_scenario_issue_count": sum(item["scenario_issue_count"] for item in summaries),
                "total_blocking_issue_count": sum(item["blocking_issue_count"] for item in summaries),
                "gate": "passed" if all(item["gate"] == "passed" for item in summaries) else "failed",
                "graphs": summaries,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    for summary in summaries:
        print(
            summary["graph_dir"],
            "gate=" + summary["gate"],
            "scenario=" + str(summary["scenario_relation_count"]),
            "blocking=" + str(summary["blocking_issue_count"]),
        )
    return 0 if all(item["gate"] == "passed" for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
