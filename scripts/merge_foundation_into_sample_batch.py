from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


STANDARD_CODE_ALIASES = {
    "EXAM-TTE": ["超声心动图", "经胸超声心动图", "心脏超声", "床旁心脏超声"],
    "EXAM-ECG": ["心电图", "ECG"],
    "EXAM-HOLTER": ["动态心电图", "Holter"],
    "EXAM-CMR": ["心脏磁共振成像", "心脏磁共振", "CMR"],
    "EXAM-CAG": ["冠状动脉造影", "冠脉造影"],
}


def stable_hash(*parts: str, length: int = 12) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest().upper()[:length]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def load_scope_disease_codes(batch_dir: Path, batch_nodes: list[dict[str, Any]]) -> set[str]:
    scope_path = batch_dir / "00_scope_and_config" / "scope_taxonomy.csv"
    if scope_path.is_file():
        with scope_path.open(encoding="utf-8-sig", newline="") as handle:
            codes = {
                row.get("disease_code", "").strip()
                for row in csv.DictReader(handle)
                if row.get("disease_code", "").strip()
            }
        if codes:
            return codes
    return {
        node["code"]
        for node in batch_nodes
        if node.get("entityType") == "Disease" and not str(node.get("batch_id", "")).startswith("FOUNDATION-")
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def merge_aliases(target: dict[str, Any], source: dict[str, Any]) -> None:
    merged: list[str] = []
    for node in (target, source):
        aliases = node.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [item.strip() for item in aliases.replace("，", ",").split(",") if item.strip()]
        for alias in aliases:
            if alias and alias != target.get("name") and alias not in merged:
                merged.append(alias)
    if merged:
        target["aliases"] = merged


def relation_key(rel: dict[str, Any]) -> tuple[str, str, str]:
    return (rel.get("source_code", ""), rel.get("relationType", ""), rel.get("target_code", ""))


def collect_foundation_closure(
    foundation_nodes: list[dict[str, Any]],
    foundation_relations: list[dict[str, Any]],
    disease_codes: set[str],
) -> tuple[set[str], list[dict[str, Any]]]:
    foundation_node_by_code = {node.get("code", ""): node for node in foundation_nodes}
    node_codes = set(foundation_node_by_code)
    selected_codes = set(disease_codes)
    selected_relations: list[dict[str, Any]] = []
    selected_relation_ids: set[str] = set()
    changed = True
    while changed:
        changed = False
        for rel in foundation_relations:
            if rel.get("source_code") not in selected_codes:
                continue
            target_node = foundation_node_by_code.get(rel.get("target_code", ""))
            if target_node and target_node.get("entityType") == "Disease" and target_node.get("code") not in disease_codes:
                continue
            rel_id = rel.get("id", "")
            if rel_id not in selected_relation_ids:
                selected_relations.append(rel)
                selected_relation_ids.add(rel_id)
            target_code = rel.get("target_code", "")
            if target_code in node_codes and target_code not in selected_codes:
                selected_codes.add(target_code)
                changed = True
    return selected_codes, selected_relations


def remove_previous_foundation_merge(
    batch_nodes: list[dict[str, Any]],
    batch_relations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    foundation_node_codes = {
        node.get("code", "")
        for node in batch_nodes
        if str(node.get("batch_id", "")).startswith("FOUNDATION-")
        or str(node.get("code", "")).startswith("EVD-CARD-DEEP-")
        or str(node.get("code", "")).startswith("EVD-CARD-FULLBOOK-")
    }
    cleaned_nodes = [node for node in batch_nodes if node.get("code", "") not in foundation_node_codes]
    cleaned_relations = []
    for rel in batch_relations:
        evidence_ids = rel.get("evidence_ids", []) or []
        if (
            str(rel.get("batch_id", "")).startswith("FOUNDATION-")
            or rel.get("source_code") in foundation_node_codes
            or rel.get("target_code") in foundation_node_codes
            or any(str(eid).startswith("EVD-CARD-DEEP-") or str(eid).startswith("EVD-CARD-FULLBOOK-") for eid in evidence_ids)
        ):
            continue
        cleaned_relations.append(rel)
    return cleaned_nodes, cleaned_relations


def remap_relation(rel: dict[str, Any], code_remap: dict[str, str]) -> dict[str, Any]:
    row = dict(rel)
    row["source_code"] = code_remap.get(row.get("source_code", ""), row.get("source_code", ""))
    row["target_code"] = code_remap.get(row.get("target_code", ""), row.get("target_code", ""))
    row["id"] = f"REL-{stable_hash(row['source_code'], row.get('relationType', ''), row['target_code'])}"
    return row


def merge_foundation_into_batch(foundation_dir: Path, batch_dir: Path) -> dict[str, Any]:
    foundation_dir = Path(foundation_dir).resolve()
    batch_dir = Path(batch_dir).resolve()
    foundation_nodes = load_jsonl(foundation_dir / "05_data_instance" / "nodes_final.jsonl")
    foundation_relations = load_jsonl(foundation_dir / "05_data_instance" / "relations_final.jsonl")
    batch_nodes = load_jsonl(batch_dir / "05_data_instance" / "nodes_final.jsonl")
    batch_relations = load_jsonl(batch_dir / "05_data_instance" / "relations_final.jsonl")
    batch_nodes, batch_relations = remove_previous_foundation_merge(batch_nodes, batch_relations)

    disease_codes = load_scope_disease_codes(batch_dir, batch_nodes)
    selected_codes, selected_relations = collect_foundation_closure(foundation_nodes, foundation_relations, disease_codes)
    foundation_node_by_code = {node["code"]: node for node in foundation_nodes}
    selected_nodes = [foundation_node_by_code[code] for code in selected_codes if code in foundation_node_by_code]

    batch_node_by_code = {node["code"]: node for node in batch_nodes}
    batch_code_by_type_name = {(node.get("entityType"), node.get("name")): node["code"] for node in batch_nodes}
    code_remap: dict[str, str] = {}
    added_nodes = 0
    merged_alias_nodes = 0

    for node in selected_nodes:
        code = node.get("code", "")
        if code in batch_node_by_code:
            merge_aliases(batch_node_by_code[code], node)
            code_remap[code] = code
            continue
        type_name = (node.get("entityType"), node.get("name"))
        existing_code = batch_code_by_type_name.get(type_name)
        if existing_code:
            merge_aliases(batch_node_by_code[existing_code], node)
            code_remap[code] = existing_code
            merged_alias_nodes += 1
            continue
        batch_nodes.append(dict(node))
        batch_node_by_code[code] = batch_nodes[-1]
        batch_code_by_type_name[type_name] = code
        code_remap[code] = code
        added_nodes += 1

    for code, aliases in STANDARD_CODE_ALIASES.items():
        if code in batch_node_by_code:
            merge_aliases(batch_node_by_code[code], {"aliases": aliases})

    relation_semantics = {relation_key(rel) for rel in batch_relations}
    added_relations = 0
    for rel in selected_relations:
        mapped = remap_relation(rel, code_remap)
        if mapped.get("source_code") not in batch_node_by_code or mapped.get("target_code") not in batch_node_by_code:
            continue
        semantic = relation_key(mapped)
        if semantic in relation_semantics:
            continue
        batch_relations.append(mapped)
        relation_semantics.add(semantic)
        added_relations += 1

    write_jsonl(batch_dir / "05_data_instance" / "nodes_final.jsonl", batch_nodes)
    write_jsonl(batch_dir / "05_data_instance" / "relations_final.jsonl", batch_relations)

    summary = {
        "status": "foundation_merged_into_sample_batch",
        "foundation_dir": str(foundation_dir),
        "batch_dir": str(batch_dir),
        "disease_count": len(disease_codes),
        "selected_foundation_node_count": len(selected_nodes),
        "selected_foundation_relation_count": len(selected_relations),
        "added_node_count": added_nodes,
        "merged_alias_node_count": merged_alias_nodes,
        "added_relation_count": added_relations,
        "final_node_count": len(batch_nodes),
        "final_relation_count": len(batch_relations),
    }
    out = batch_dir / "04_evidence_and_extraction" / "foundation_merge_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge cardiology foundation graph into a disease sample batch.")
    parser.add_argument("--foundation-dir", type=Path, required=True)
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(merge_foundation_into_batch(args.foundation_dir, args.batch_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
