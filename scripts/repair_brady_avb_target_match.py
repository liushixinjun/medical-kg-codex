from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def as_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def merge_aliases(*values: Any) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in as_list(value):
            item = item.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            output.append(item)
    return output


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def provenance(ev: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": ev.get("document_id", ""),
        "segment_id": ev.get("segment_id", ""),
        "source_name": ev.get("source_name", ""),
        "source_type": ev.get("source_type", ""),
        "source_version": ev.get("source_version", "N/A"),
        "source_section": ev.get("source_section", "N/A"),
        "source_page": ev.get("source_page", "N/A"),
        "disease_code": ev.get("disease_code", ""),
        "disease_name": ev.get("disease_name", ""),
        "evidence_text": ev.get("evidence_text", ""),
        "recommendation_class": ev.get("recommendation_class", "N/A"),
        "evidence_level": ev.get("evidence_level", "N/A"),
    }


GENERIC_ALIASES = {"治疗", "路径", "治疗路径", "症状", "随访", "并发症", "检查", "诊断"}


def score_evidence(ev: dict[str, Any], failure: dict[str, str], aliases: list[str]) -> int:
    text = ev.get("evidence_text", "")
    score = 0
    for alias in aliases:
        if not alias or alias in GENERIC_ALIASES:
            continue
        if alias in text:
            score += 3 if len(alias) >= 4 else 1
    if failure.get("source_name") and failure["source_name"] in text:
        score += 3
    if ev.get("disease_code") == failure.get("source_code"):
        score += 5
    if failure.get("source_name", "").replace("治疗方案", "") in text:
        score += 2
    if ev.get("source_name", "").endswith(".pdf"):
        score += 1
    if "指南" in ev.get("source_name", "") or "共识" in ev.get("source_name", ""):
        score += 1
    return score


def choose_evidence(evidences: list[dict[str, Any]], failure: dict[str, str]) -> dict[str, Any] | None:
    aliases = [failure.get("target_name", "")]
    aliases.extend([item for item in failure.get("aliases", "").split(";") if item])
    ranked = [
        (score_evidence(ev, failure, aliases), len(ev.get("evidence_text", "")), ev)
        for ev in evidences
    ]
    ranked = [item for item in ranked if item[0] > 0]
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return ranked[0][2]


def patch_relation_with_evidence(relation: dict[str, Any], ev: dict[str, Any]) -> None:
    prov = provenance(ev)
    relation["provenance_records_json"] = [prov]
    relation["evidence_ids"] = [ev.get("evidence_id", "")]
    relation["document_ids"] = [ev.get("document_id", "")]
    relation["source_names"] = [ev.get("source_name", "")]
    relation["source_types"] = [ev.get("source_type", "")]
    relation["evidence_count"] = 1
    relation["document_id"] = ev.get("document_id", "")
    relation["segment_id"] = ev.get("segment_id", "")
    relation["source_name"] = ev.get("source_name", "")
    relation["source_type"] = ev.get("source_type", "")
    relation["source_section"] = ev.get("source_section", "N/A")
    relation["source_page"] = ev.get("source_page", "N/A")
    relation["evidence_text"] = ev.get("evidence_text", "")
    relation["recommendation_class"] = ev.get("recommendation_class", relation.get("recommendation_class", "N/A"))
    relation["evidence_level"] = ev.get("evidence_level", relation.get("evidence_level", "N/A"))
    relation["target_match_repair"] = "evidence_reselected_by_target_alias"


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair brady/AVB target alias evidence matching failures.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()

    data_dir = args.batch_dir / "05_data_instance"
    audit_dir = args.batch_dir / "06_quality_audit"
    failure_path = audit_dir / "target_match_failure_register.csv"
    if not failure_path.is_file():
        raise FileNotFoundError(f"Run target failure register first: {failure_path}")

    nodes = read_jsonl(data_dir / "nodes_final.jsonl")
    relations = read_jsonl(data_dir / "relations_final.jsonl")
    evidences = read_jsonl(args.batch_dir / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl")
    node_by_code = {node["code"]: node for node in nodes}
    relation_by_id = {relation["id"]: relation for relation in relations}
    failures = load_csv(failure_path)

    patch_log: list[dict[str, Any]] = []
    for failure in failures:
        relation = relation_by_id.get(failure["relation_id"])
        target = node_by_code.get(failure["target_code"])
        if not relation or not target:
            continue
        if failure["target_type"] == "ClinicalPathway":
            clinical_alias = failure["target_name"].replace("治疗路径", "").strip()
            source_alias = failure["source_name"].replace("治疗方案", "").strip()
            target["aliases"] = merge_aliases(target.get("aliases"), clinical_alias, source_alias, failure["source_name"])
            target["target_match_repair"] = "pathway_alias_added_from_scope_context"
            patch_log.append(
                {
                    "relation_id": failure["relation_id"],
                    "repair_type": "pathway_alias",
                    "target_code": failure["target_code"],
                    "added_alias": ";".join([clinical_alias, source_alias, failure["source_name"]]),
                }
            )
            continue
        ev = choose_evidence(evidences, failure)
        if ev:
            patch_relation_with_evidence(relation, ev)
            patch_log.append(
                {
                    "relation_id": failure["relation_id"],
                    "repair_type": "evidence_reselected",
                    "target_code": failure["target_code"],
                    "evidence_id": ev.get("evidence_id", ""),
                    "source_name": ev.get("source_name", ""),
                    "source_page": ev.get("source_page", ""),
                    "evidence_disease_code": ev.get("disease_code", ""),
                }
            )

    write_jsonl(data_dir / "nodes_final.jsonl", nodes)
    write_jsonl(data_dir / "relations_final.jsonl", relations)
    write_csv(audit_dir / "target_match_repair_log.csv", patch_log)
    summary = {
        "status": "target_match_repaired",
        "failure_count_before": len(failures),
        "patched_count": len(patch_log),
    }
    (audit_dir / "target_match_repair_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
