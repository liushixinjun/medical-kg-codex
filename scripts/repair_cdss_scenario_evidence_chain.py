from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_cdss_scenario_evidence_chain import CDSS_SCENARIO_RELATION_TYPES  # noqa: E402
from scripts.audit_graph_instance import EVIDENCE_REQUIRED  # noqa: E402


EVIDENCE_COPY_FIELDS = set(EVIDENCE_REQUIRED) | {
    "evidence_count",
    "provenance_records_json",
    "document_ids",
    "source_names",
    "source_types",
    "source_versions",
    "source_sections",
    "source_pages",
    "guideline_ids",
    "evidence_ids",
    "source_title",
    "source_titles",
    "recommendation_statement",
    "recommendation_context",
    "applicable_population",
    "exclusion_criteria",
    "contraindications",
    "clinical_review_status",
    "cdss_release_level",
    "ai_precheck_status",
    "ai_precheck_note",
    "clinical_effect_review_status",
    "recommendation_grade_source",
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


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def has_required_evidence(rel: dict) -> bool:
    return all(rel.get(field) not in (None, "") for field in EVIDENCE_REQUIRED)


def disease_treatment_plan_name(pathway_name: str) -> str:
    if pathway_name.endswith("治疗路径"):
        return pathway_name[: -len("治疗路径")] + "治疗方案"
    return pathway_name.replace("路径", "方案")


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


def build_reference_indexes(nodes: list[dict], relations: list[dict]) -> dict:
    node_by_code = {node.get("code"): node for node in nodes}
    has_tp_by_disease: dict[str, list[dict]] = {}
    has_tp_by_plan: dict[str, list[dict]] = {}
    therapeutic_by_source: dict[str, list[dict]] = {}
    for rel in relations:
        relation_type = rel.get("relationType")
        source_code = rel.get("source_code")
        target_code = rel.get("target_code")
        if relation_type == "has_treatment_plan":
            source = node_by_code.get(source_code, {})
            target = node_by_code.get(target_code, {})
            if source.get("entityType") == "Disease" and target.get("entityType") == "TreatmentPlan":
                has_tp_by_disease.setdefault(source_code, []).append(rel)
                has_tp_by_plan.setdefault(target_code, []).append(rel)
        if relation_type in {"has_treatment_plan", "treated_by_medication", "treated_by_procedure", "has_follow_up"}:
            if has_required_evidence(rel):
                therapeutic_by_source.setdefault(source_code, []).append(rel)
    return {
        "node_by_code": node_by_code,
        "has_tp_by_disease": has_tp_by_disease,
        "has_tp_by_plan": has_tp_by_plan,
        "therapeutic_by_source": therapeutic_by_source,
    }


def select_reference(rel: dict, indexes: dict) -> dict | None:
    node_by_code = indexes["node_by_code"]
    source = node_by_code.get(rel.get("source_code"), {})
    target = node_by_code.get(rel.get("target_code"), {})
    source_type = source.get("entityType")
    target_type = target.get("entityType")
    relation_type = rel.get("relationType")

    if relation_type == "has_clinical_pathway" and target_type == "ClinicalPathway":
        expected_plan_name = disease_treatment_plan_name(str(target.get("name") or ""))
        if source_type == "Disease":
            candidates = indexes["has_tp_by_disease"].get(rel.get("source_code"), [])
            exact = [
                candidate
                for candidate in candidates
                if str(node_by_code.get(candidate.get("target_code"), {}).get("name") or "") == expected_plan_name
                and has_required_evidence(candidate)
            ]
            if exact:
                return exact[0]
            evidenced = [candidate for candidate in candidates if has_required_evidence(candidate)]
            if evidenced:
                return evidenced[0]
        if source_type == "TreatmentPlan":
            candidates = indexes["has_tp_by_plan"].get(rel.get("source_code"), [])
            evidenced = [candidate for candidate in candidates if has_required_evidence(candidate)]
            if evidenced:
                return evidenced[0]

    if source_type == "TreatmentPlan":
        candidates = indexes["has_tp_by_plan"].get(rel.get("source_code"), [])
        evidenced = [candidate for candidate in candidates if has_required_evidence(candidate)]
        if evidenced:
            return evidenced[0]

    if source_type == "Disease" and relation_type in {"has_treatment_plan", "treated_by_medication", "treated_by_procedure", "has_follow_up"}:
        candidates = indexes["therapeutic_by_source"].get(rel.get("source_code"), [])
        if candidates:
            return candidates[0]
    return None


def copy_evidence(target: dict, reference: dict) -> None:
    for field in EVIDENCE_COPY_FIELDS:
        value = reference.get(field)
        if value not in (None, ""):
            target[field] = copy.deepcopy(value)
    target["evidence_inherited_from_relation_id"] = reference.get("id", "")
    target["evidence_inherited_from_relation_type"] = reference.get("relationType", "")
    target["evidence_copy_reason"] = "repair_cdss_scenario_relation_from_same_batch_source_relation"


def repair_graph_dir(graph_dir: Path, dry_run: bool = False) -> dict:
    data_dir = graph_dir / "05_data_instance"
    audit_dir = graph_dir / "06_quality_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = data_dir / "nodes_final.jsonl"
    relations_path = data_dir / "relations_final.jsonl"
    nodes = read_jsonl(nodes_path)
    relations = read_jsonl(relations_path)
    indexes = build_reference_indexes(nodes, relations)

    repaired_rows: list[dict] = []
    unresolved_rows: list[dict] = []
    for rel in relations:
        if rel.get("relationType") not in CDSS_SCENARIO_RELATION_TYPES:
            continue
        if has_required_evidence(rel):
            continue
        reference = select_reference(rel, indexes)
        source = indexes["node_by_code"].get(rel.get("source_code"), {})
        target = indexes["node_by_code"].get(rel.get("target_code"), {})
        if reference:
            before_missing = sorted(field for field in EVIDENCE_REQUIRED if rel.get(field) in (None, ""))
            copy_evidence(rel, reference)
            if rel.get("relationType") == "has_clinical_pathway":
                rel["relationCategory"] = "therapeutic"
            repaired_rows.append(
                {
                    "relation_id": rel.get("id", ""),
                    "relationType": rel.get("relationType", ""),
                    "source_name": source.get("name", ""),
                    "source_entityType": source.get("entityType", ""),
                    "target_name": target.get("name", ""),
                    "target_entityType": target.get("entityType", ""),
                    "copied_from_relation_id": reference.get("id", ""),
                    "copied_from_relationType": reference.get("relationType", ""),
                    "before_missing_fields": "|".join(before_missing),
                }
            )
        else:
            unresolved_rows.append(
                {
                    "relation_id": rel.get("id", ""),
                    "relationType": rel.get("relationType", ""),
                    "source_name": source.get("name", ""),
                    "source_entityType": source.get("entityType", ""),
                    "target_name": target.get("name", ""),
                    "target_entityType": target.get("entityType", ""),
                    "missing_fields": "|".join(sorted(field for field in EVIDENCE_REQUIRED if rel.get(field) in (None, ""))),
                }
            )

    if repaired_rows and not dry_run:
        write_jsonl(relations_path, relations)

    for path, rows, fields in [
        (
            audit_dir / "cdss_scenario_evidence_repaired.csv",
            repaired_rows,
            [
                "relation_id",
                "relationType",
                "source_name",
                "source_entityType",
                "target_name",
                "target_entityType",
                "copied_from_relation_id",
                "copied_from_relationType",
                "before_missing_fields",
            ],
        ),
        (
            audit_dir / "cdss_scenario_evidence_unresolved.csv",
            unresolved_rows,
            ["relation_id", "relationType", "source_name", "source_entityType", "target_name", "target_entityType", "missing_fields"],
        ),
    ]:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    summary = {
        "graph_dir": graph_dir.name,
        "dry_run": dry_run,
        "repaired_relation_count": len(repaired_rows),
        "unresolved_relation_count": len(unresolved_rows),
    }
    with (audit_dir / "cdss_scenario_evidence_repair_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair missing CDSS scenario evidence by copying from same-batch source relations.")
    parser.add_argument("--collection-root", type=Path)
    parser.add_argument("--graph-dir", type=Path, action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    graph_dirs = args.graph_dir
    if args.collection_root:
        graph_dirs.extend(discover_graph_dirs(args.collection_root))
    if not graph_dirs:
        parser.error("Provide --graph-dir or --collection-root")

    seen = set()
    summaries = []
    for graph_dir in graph_dirs:
        graph_dir = Path(graph_dir)
        if graph_dir in seen:
            continue
        seen.add(graph_dir)
        summary = repair_graph_dir(graph_dir, dry_run=args.dry_run)
        summaries.append(summary)
        print(summary["graph_dir"], "repaired=" + str(summary["repaired_relation_count"]), "unresolved=" + str(summary["unresolved_relation_count"]))
    return 0 if all(item["unresolved_relation_count"] == 0 for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
