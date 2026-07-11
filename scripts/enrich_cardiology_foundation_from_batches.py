from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


SCHEMA_VERSION = "V1.8"
STRUCTURAL_RELATIONS = {
    "has_category",
    "has_subcategory",
    "has_disease",
    "belongs_to_subcategory",
    "belongs_to_category",
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def relation_id(source: str, relation_type: str, target: str) -> str:
    import hashlib

    digest = hashlib.sha1(f"{source}|{relation_type}|{target}".encode("utf-8")).hexdigest().upper()[:12]
    return f"REL-{digest}"


def remap_relation(rel: dict, code_map: dict[str, str]) -> dict:
    row = dict(rel)
    row["source_code"] = code_map.get(row.get("source_code"), row.get("source_code"))
    row["target_code"] = code_map.get(row.get("target_code"), row.get("target_code"))
    row["id"] = relation_id(row["source_code"], row["relationType"], row["target_code"])
    row["schema_version"] = row.get("schema_version") or SCHEMA_VERSION
    row["review_status"] = row.get("review_status") or "approved"
    return row


def add_structural_for_new_disease(relations: list[dict], relation_semantics: set[tuple[str, str, str]], disease_code: str) -> None:
    if disease_code.startswith("DIS-CARD-CM-"):
        category_code = "CAT-CARD-CM"
        subcategory_code = "SUB-CARD-CM-GENERAL"
    elif disease_code.startswith("DIS-CARD-CAD-"):
        category_code = "CAT-CARD-CAD"
        subcategory_code = "SUB-CARD-CAD-GENERAL"
    elif disease_code.startswith("DIS-CARD-HF"):
        category_code = "CAT-CARD-HF"
        subcategory_code = "SUB-CARD-HF-GENERAL"
    elif disease_code.startswith("DIS-CARD-ARR"):
        category_code = "CAT-CARD-ARR"
        subcategory_code = "SUB-CARD-ARR-GENERAL"
    else:
        return
    for source, relation_type, target in (
        (subcategory_code, "has_disease", disease_code),
        (disease_code, "belongs_to_subcategory", subcategory_code),
        (disease_code, "belongs_to_category", category_code),
    ):
        semantic = (source, relation_type, target)
        if semantic in relation_semantics:
            continue
        relations.append(
            {
                "id": relation_id(source, relation_type, target),
                "source_code": source,
                "relationType": relation_type,
                "target_code": target,
                "relationCategory": "structural",
                "batch_id": "FOUNDATION-CARD-20260624-001",
                "schema_version": SCHEMA_VERSION,
                "review_status": "approved",
            }
        )
        relation_semantics.add(semantic)


def enrich(foundation_dir: Path, batch_dirs: list[Path]) -> dict:
    foundation_dir = foundation_dir.resolve()
    current_nodes_path = foundation_dir / "05_data_instance" / "nodes_final.jsonl"
    current_relations_path = foundation_dir / "05_data_instance" / "relations_final.jsonl"
    nodes = load_jsonl(current_nodes_path) or load_jsonl(foundation_dir / "foundation_nodes.jsonl")
    relations = load_jsonl(current_relations_path) or load_jsonl(foundation_dir / "foundation_relations.jsonl")

    by_code = {node["code"]: node for node in nodes}
    by_type_name = {(node.get("entityType"), node.get("name")): node["code"] for node in nodes}
    relation_semantics = {(rel["source_code"], rel["relationType"], rel["target_code"]) for rel in relations}

    code_map: dict[str, str] = {}
    conflict_rows: list[dict] = []
    added_node_codes: set[str] = set()

    for batch_dir in batch_dirs:
        batch_nodes = load_jsonl(batch_dir / "05_data_instance" / "nodes_final.jsonl")
        for node in batch_nodes:
            code = node.get("code")
            entity_type = node.get("entityType")
            name = node.get("name")
            if not code or not entity_type or not name:
                continue
            if code in by_code:
                code_map[code] = code
                continue
            same_type_name_code = by_type_name.get((entity_type, name))
            if same_type_name_code:
                code_map[code] = same_type_name_code
                conflict_rows.append(
                    {
                        "source_batch": batch_dir.name,
                        "incoming_code": code,
                        "incoming_name": name,
                        "entityType": entity_type,
                        "mapped_to_code": same_type_name_code,
                        "decision": "same_entity_same_type_name_reused_foundation_node",
                    }
                )
                continue
            row = dict(node)
            row["schema_version"] = row.get("schema_version") or SCHEMA_VERSION
            row["merge_status"] = "validated"
            row["foundation_import_source"] = batch_dir.name
            by_code[code] = row
            by_type_name[(entity_type, name)] = code
            code_map[code] = code
            nodes.append(row)
            added_node_codes.add(code)
            if entity_type == "Disease":
                add_structural_for_new_disease(relations, relation_semantics, code)

    for rel in relations:
        relation_semantics.add((rel["source_code"], rel["relationType"], rel["target_code"]))

    dangling_skipped = 0
    for batch_dir in batch_dirs:
        batch_relations = load_jsonl(batch_dir / "05_data_instance" / "relations_final.jsonl")
        for rel in batch_relations:
            if rel.get("relationType") in STRUCTURAL_RELATIONS:
                continue
            row = remap_relation(rel, code_map)
            if row.get("source_code") not in by_code or row.get("target_code") not in by_code:
                dangling_skipped += 1
                continue
            semantic = (row["source_code"], row["relationType"], row["target_code"])
            if semantic in relation_semantics:
                continue
            relations.append(row)
            relation_semantics.add(semantic)

    write_jsonl(foundation_dir / "foundation_nodes_enriched.jsonl", nodes)
    write_jsonl(foundation_dir / "foundation_relations_enriched.jsonl", relations)
    write_jsonl(foundation_dir / "05_data_instance" / "nodes_final.jsonl", nodes)
    write_jsonl(foundation_dir / "05_data_instance" / "relations_final.jsonl", relations)
    write_csv(
        foundation_dir / "06_quality_audit" / "foundation_merge_conflict_register.csv",
        ["source_batch", "incoming_code", "incoming_name", "entityType", "mapped_to_code", "decision"],
        conflict_rows,
    )

    summary = {
        "status": "foundation_enriched_from_validated_batches",
        "schema_version": SCHEMA_VERSION,
        "batch_dirs": [str(path.resolve()) for path in batch_dirs],
        "node_count": len(nodes),
        "relation_count": len(relations),
        "added_node_count": len(added_node_codes),
        "same_type_name_reuse_count": len(conflict_rows),
        "dangling_relation_skipped_count": dangling_skipped,
        "entity_type_counts": dict(Counter(node.get("entityType", "") for node in nodes)),
        "relation_type_counts": dict(Counter(rel.get("relationType", "") for rel in relations)),
    }
    (foundation_dir / "06_quality_audit" / "foundation_enrichment_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich cardiology foundation skeleton from validated disease batches.")
    parser.add_argument("--foundation-dir", type=Path, required=True)
    parser.add_argument("--batch-dir", type=Path, action="append", required=True)
    args = parser.parse_args()
    print(json.dumps(enrich(args.foundation_dir, args.batch_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
