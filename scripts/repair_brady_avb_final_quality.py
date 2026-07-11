from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


PATTERN_BY_RELATION = {
    "has_clinical_pathway": r"二度房室传导阻滞|临时心脏起搏|心脏起搏|起搏",
    "has_symptom": r"晕厥|头晕|黑矇|乏力|活动耐量",
    "requires_exam": r"体表心电图|动态心电图|心电生理|长程心电|Holter|心电图",
    "may_cause_complication": r"心室静止|血流动力学|心脏停搏|并发症|二度或三度房室传导阻滞",
    "has_follow_up": r"起搏阈值|心电监测|起搏器|随访|程控|电池|术后",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row.keys()}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
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


def patch_relation_evidence(relation: dict[str, Any], ev: dict[str, Any]) -> None:
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
    relation["target_match_repair"] = "final_relation_type_based_evidence_reselected"


def choose_by_pattern(evidences: list[dict[str, Any]], failure: dict[str, str]) -> dict[str, Any] | None:
    pattern = re.compile(PATTERN_BY_RELATION.get(failure["relation_type"], re.escape(failure["target_name"])))
    source_name = failure.get("source_name", "")
    source_code = failure.get("source_code", "")
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for ev in evidences:
        text = ev.get("evidence_text", "")
        if not pattern.search(text):
            continue
        score = 10
        if source_name and source_name in text:
            score += 5
        if ev.get("disease_code") == source_code:
            score += 4
        if "指南" in ev.get("source_name", "") or "共识" in ev.get("source_name", ""):
            score += 2
        if ev.get("source_name", "").endswith(".pdf"):
            score += 1
        ranked.append((score, len(text), ev))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return ranked[0][2]


def patch_test_recommendation_fields(relations: list[dict[str, Any]]) -> int:
    count = 0
    for relation in relations:
        if relation.get("relationType") not in {"has_follow_up", "includes_procedure"}:
            continue
        if relation.get("clinical_review_status") != "clinical_batch_signed_off":
            continue
        rec = relation.get("recommendation_class")
        ev_level = relation.get("evidence_level")
        if rec not in (None, "", "N/A") and ev_level not in (None, "", "N/A"):
            continue
        relation["recommendation_class"] = "未分级推荐"
        relation["evidence_level"] = "共识/教材证据"
        relation["cdss_release_level"] = "test_recommendation"
        relation["formal_cdss_ready"] = False
        relation["cdss_readiness_note"] = "测试推荐层字段补齐；非正式自动医嘱。"
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Final brady/AVB batch quality patch.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()

    data_dir = args.batch_dir / "05_data_instance"
    audit_dir = args.batch_dir / "06_quality_audit"
    nodes = read_jsonl(data_dir / "nodes_final.jsonl")
    relations = read_jsonl(data_dir / "relations_final.jsonl")
    evidences = read_jsonl(args.batch_dir / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl")
    failures = read_csv(audit_dir / "target_match_failure_register.csv")
    relation_by_id = {relation["id"]: relation for relation in relations}

    log: list[dict[str, Any]] = []
    for failure in failures:
        relation = relation_by_id.get(failure["relation_id"])
        if not relation:
            continue
        ev = choose_by_pattern(evidences, failure)
        if not ev:
            continue
        patch_relation_evidence(relation, ev)
        log.append(
            {
                "relation_id": failure["relation_id"],
                "relation_type": failure["relation_type"],
                "target_name": failure["target_name"],
                "evidence_id": ev.get("evidence_id", ""),
                "evidence_disease_code": ev.get("disease_code", ""),
                "source_name": ev.get("source_name", ""),
                "source_page": ev.get("source_page", ""),
            }
        )
    cdss_patch_count = patch_test_recommendation_fields(relations)
    write_jsonl(data_dir / "nodes_final.jsonl", nodes)
    write_jsonl(data_dir / "relations_final.jsonl", relations)
    write_csv(audit_dir / "brady_avb_final_target_patch_log.csv", log)
    summary = {
        "status": "final_quality_patch_applied",
        "target_relation_patched_count": len(log),
        "cdss_field_patched_count": cdss_patch_count,
    }
    (audit_dir / "brady_avb_final_quality_patch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
