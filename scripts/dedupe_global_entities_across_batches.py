from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_BATCH_DIRS = [
    Path("心血管内科文献集合/00_foundation_skeleton"),
    Path("心血管内科文献集合/BATCH-CARD-CAD-20260623-001"),
    Path("心血管内科文献集合/BATCH-CARD-CM-20260622-001"),
]

EXCLUDED_ENTITY_TYPES = {"Evidence", "Guideline", "Specialty", "DiseaseCategory", "DiseaseSubcategory"}
PREFERRED_CANONICAL_CODES = {
    ("Disease", "缺血性心肌病"): "DIS-CARD-CAD-ICM",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def normalize_aliases(value) -> list[str]:
    if value is None:
        values = []
    elif isinstance(value, list):
        values = value
    elif isinstance(value, str):
        values = [item.strip() for item in value.split(",") if item.strip()]
    else:
        values = [value]
    out = []
    seen = set()
    for item in values:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def choose_canonical(records: list[tuple[int, dict]]) -> dict:
    key = (records[0][1].get("entityType"), records[0][1].get("name"))
    preferred = PREFERRED_CANONICAL_CODES.get(key)
    if preferred:
        for _, node in records:
            if node.get("code") == preferred:
                return node
    return sorted(records, key=lambda item: (item[0], str(item[1].get("code", ""))))[0][1]


def merge_node_fields(canonical: dict, duplicate: dict) -> dict:
    canonical["aliases"] = normalize_aliases(normalize_aliases(canonical.get("aliases")) + normalize_aliases(duplicate.get("aliases")))
    for field in ("description", "name_en", "abbr", "clinical_review_status", "formal_cdss_ready"):
        if canonical.get(field) in (None, "", []) and duplicate.get(field) not in (None, "", []):
            canonical[field] = duplicate[field]
    return canonical


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize same entityType+name nodes to one canonical code across multiple batch JSONL files.")
    parser.add_argument("--batch-dir", action="append", type=Path, default=[])
    args = parser.parse_args()
    batch_dirs = args.batch_dir or DEFAULT_BATCH_DIRS

    batches = []
    groups = defaultdict(list)
    node_by_code = {}
    for batch_index, batch_dir in enumerate(batch_dirs):
        nodes_path = batch_dir / "05_data_instance" / "nodes_final.jsonl"
        relations_path = batch_dir / "05_data_instance" / "relations_final.jsonl"
        nodes = read_jsonl(nodes_path)
        relations = read_jsonl(relations_path)
        batches.append((batch_dir, nodes_path, relations_path, nodes, relations))
        for node in nodes:
            node_by_code[node["code"]] = node
            if node.get("entityType") in EXCLUDED_ENTITY_TYPES:
                continue
            groups[(node.get("entityType"), node.get("name"))].append((batch_index, node))

    code_map = {}
    canonical_updates = {}
    for key, records in groups.items():
        codes = {node["code"] for _, node in records}
        if len(codes) <= 1:
            continue
        canonical = choose_canonical(records)
        canonical_code = canonical["code"]
        canonical_updates[canonical_code] = canonical
        for _, node in records:
            if node["code"] == canonical_code:
                canonical_updates[canonical_code] = merge_node_fields(canonical_updates[canonical_code], node)
            else:
                code_map[node["code"]] = canonical_code
                canonical_updates[canonical_code] = merge_node_fields(canonical_updates[canonical_code], node)

    summaries = []
    for batch_dir, nodes_path, relations_path, nodes, relations in batches:
        changed_nodes = 0
        removed_duplicate_nodes = 0
        seen_codes = set()
        rewritten_nodes = []
        for node in nodes:
            old_code = node["code"]
            if old_code in code_map:
                node = {**node, "code": code_map[old_code]}
                canonical = canonical_updates.get(node["code"])
                if canonical:
                    node["id"] = canonical.get("id", node.get("id"))
                    node["aliases"] = canonical.get("aliases", node.get("aliases", []))
                changed_nodes += 1
            if node["code"] in seen_codes:
                removed_duplicate_nodes += 1
                continue
            seen_codes.add(node["code"])
            rewritten_nodes.append(node)

        changed_relations = 0
        deduped_relations = []
        seen_relation_semantics = set()
        for rel in relations:
            new_rel = dict(rel)
            if new_rel.get("source_code") in code_map:
                new_rel["source_code"] = code_map[new_rel["source_code"]]
                changed_relations += 1
            if new_rel.get("target_code") in code_map:
                new_rel["target_code"] = code_map[new_rel["target_code"]]
                changed_relations += 1
            semantic_key = (new_rel.get("source_code"), new_rel.get("relationType"), new_rel.get("target_code"), new_rel.get("id"))
            if semantic_key in seen_relation_semantics:
                continue
            seen_relation_semantics.add(semantic_key)
            deduped_relations.append(new_rel)

        write_jsonl(nodes_path, rewritten_nodes)
        write_jsonl(relations_path, deduped_relations)
        summaries.append(
            {
                "batch_dir": str(batch_dir),
                "changed_nodes": changed_nodes,
                "removed_duplicate_nodes_within_batch": removed_duplicate_nodes,
                "changed_relation_endpoints": changed_relations,
                "node_count": len(rewritten_nodes),
                "relation_count": len(deduped_relations),
            }
        )

    summary = {
        "canonical_code_count": len(set(code_map.values())),
        "rewritten_code_count": len(code_map),
        "code_map": code_map,
        "batches": summaries,
    }
    Path("心血管内科文献集合/global_entity_dedupe_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
