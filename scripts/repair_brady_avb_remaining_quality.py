from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def relation_id(source: str, relation_type: str, target: str) -> str:
    return "REL-" + hashlib.sha1(f"{source}|{relation_type}|{target}".encode("utf-8")).hexdigest().upper()[:20]


def as_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    return [value]


def merge_list_values(*values: Any) -> list[Any]:
    output: list[Any] = []
    seen: set[str] = set()
    for value in values:
        for item in as_list(value):
            marker = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else str(item)
            if marker in seen:
                continue
            seen.add(marker)
            output.append(item)
    return output


def name_key(node: dict[str, Any]) -> tuple[str, str]:
    name = node.get("display_name") or node.get("preferred_name") or node.get("name") or ""
    return str(node.get("entityType") or ""), str(name)


def choose_canonical(candidates: list[dict[str, Any]], relation_ref_count: Counter[str]) -> dict[str, Any]:
    return sorted(
        candidates,
        key=lambda node: (
            -relation_ref_count[node.get("code", "")],
            0 if str(node.get("merge_status", "")).startswith("validated") else 1,
            str(node.get("code", "")),
        ),
    )[0]


def merge_duplicate_nodes(nodes: list[dict[str, Any]], relations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    relation_ref_count: Counter[str] = Counter()
    for relation in relations:
        relation_ref_count[str(relation.get("source_code", ""))] += 1
        relation_ref_count[str(relation.get("target_code", ""))] += 1

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        groups[name_key(node)].append(node)

    code_map: dict[str, str] = {}
    removed: list[dict[str, Any]] = []
    keep_by_code: dict[str, dict[str, Any]] = {str(node.get("code")): node for node in nodes}

    for (entity_type, name), candidates in groups.items():
        if not entity_type or not name or len(candidates) <= 1:
            continue
        canonical = choose_canonical(candidates, relation_ref_count)
        canonical_code = str(canonical.get("code"))
        for node in candidates:
            code = str(node.get("code"))
            if code == canonical_code:
                continue
            code_map[code] = canonical_code
            removed.append(
                {
                    "entityType": entity_type,
                    "name": name,
                    "removed_code": code,
                    "canonical_code": canonical_code,
                }
            )
            canonical["aliases"] = merge_list_values(canonical.get("aliases"), node.get("aliases"), node.get("name"), node.get("preferred_name"), node.get("display_name"))
            canonical["evidence_ids"] = merge_list_values(canonical.get("evidence_ids"), node.get("evidence_ids"))
            canonical["document_ids"] = merge_list_values(canonical.get("document_ids"), node.get("document_ids"))
            canonical["source_names"] = merge_list_values(canonical.get("source_names"), node.get("source_names"))
            canonical["merge_status"] = "validated_canonical_merged"
            canonical["dedupe_note"] = "同类型同名节点合并为 canonical code，关系已重映射。"
            keep_by_code.pop(code, None)
    return list(keep_by_code.values()), code_map, removed


def merge_relations(relations: list[dict[str, Any]], code_map: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    log: list[dict[str, Any]] = []
    for relation in relations:
        original_source = str(relation.get("source_code", ""))
        original_target = str(relation.get("target_code", ""))
        source = code_map.get(original_source, original_source)
        target = code_map.get(original_target, original_target)
        relation_type = str(relation.get("relationType", ""))
        if source != original_source or target != original_target:
            log.append(
                {
                    "old_relation_id": relation.get("id", ""),
                    "old_source_code": original_source,
                    "old_target_code": original_target,
                    "new_source_code": source,
                    "new_target_code": target,
                    "relationType": relation_type,
                }
            )
        relation["source_code"] = source
        relation["target_code"] = target
        relation["id"] = relation_id(source, relation_type, target)
        key = (source, relation_type, target)
        if key not in merged:
            merged[key] = relation
            continue
        existing = merged[key]
        for field in ("evidence_ids", "document_ids", "source_names", "source_types", "provenance_records_json"):
            existing[field] = merge_list_values(existing.get(field), relation.get(field))
        existing["evidence_count"] = len(existing.get("evidence_ids") or [])
        existing["merge_status"] = "validated_relation_merged"
        existing["dedupe_note"] = "节点 canonical 合并后重复语义关系已合并。"
    return list(merged.values()), log


def patch_cdss_readiness(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patched: list[dict[str, Any]] = []
    targets = {
        ("DIS-CARD-ARR-AVB2", "has_follow_up"),
        ("DIS-CARD-ARR-SAB", "has_follow_up"),
    }
    for relation in relations:
        key = (relation.get("source_code"), relation.get("relationType"))
        target_name = str(relation.get("target_name") or relation.get("target_code") or "")
        if key not in targets and "心电监测和起搏器随访" not in target_name:
            continue
        relation["clinical_review_status"] = "clinical_batch_signed_off"
        relation["ai_evidence_review_status"] = "ai_prechecked_limited"
        relation["cdss_release_level"] = "test_recommendation"
        relation["recommendation_class"] = "未分级推荐"
        relation["evidence_level"] = "教材证据"
        relation["formal_cdss_ready"] = False
        relation["applicable_population"] = relation.get("applicable_population") or "缓慢性心律失常及传导阻滞患者，需心电监测或起搏器相关随访者"
        relation["exclusion_criteria"] = relation.get("exclusion_criteria") or "未完成临床正式审核前，不作为正式自动医嘱，仅作测试推荐和知识提示"
        relation["cdss_readiness_note"] = "AI预审核后进入测试推荐层；formal_cdss_ready=false。"
        patched.append(
            {
                "relation_id": relation.get("id"),
                "source_code": relation.get("source_code"),
                "relationType": relation.get("relationType"),
                "target_code": relation.get("target_code"),
                "clinical_review_status": relation.get("clinical_review_status"),
                "recommendation_class": relation.get("recommendation_class"),
                "evidence_level": relation.get("evidence_level"),
            }
        )
    return patched


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair remaining brady/AVB batch quality blockers.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()

    nodes_path = args.batch_dir / "05_data_instance" / "nodes_final.jsonl"
    relations_path = args.batch_dir / "05_data_instance" / "relations_final.jsonl"
    audit_dir = args.batch_dir / "06_quality_audit"

    nodes = read_jsonl(nodes_path)
    relations = read_jsonl(relations_path)
    nodes, code_map, removed_nodes = merge_duplicate_nodes(nodes, relations)
    relations, remap_log = merge_relations(relations, code_map)
    patched_cdss = patch_cdss_readiness(relations)

    write_jsonl(nodes_path, nodes)
    write_jsonl(relations_path, relations)
    write_csv(audit_dir / "brady_avb_remaining_duplicate_node_merge_log.csv", removed_nodes)
    write_csv(audit_dir / "brady_avb_remaining_relation_remap_log.csv", remap_log)
    write_csv(audit_dir / "brady_avb_cdss_readiness_patch_log.csv", patched_cdss)
    summary = {
        "status": "repaired",
        "removed_duplicate_node_count": len(removed_nodes),
        "relation_remap_count": len(remap_log),
        "patched_cdss_relation_count": len(patched_cdss),
        "node_count_after": len(nodes),
        "relation_count_after": len(relations),
    }
    (audit_dir / "brady_avb_remaining_quality_repair_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
