from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ALIAS_FIELDS = (
    "aliases",
    "alias",
    "name_en",
    "english_name",
    "abbr",
    "abbreviation",
    "short_name",
    "中文简称",
    "英文简称",
)


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


def normalize_alias(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def split_alias_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(split_alias_value(item))
        return out
    if isinstance(value, dict):
        return [str(item).strip() for item in value.values() if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"[;；,，|/、]+", text)
    return [part.strip() for part in parts if part.strip()]


def discover_graph_dirs(root: Path) -> list[Path]:
    graph_dirs = []
    foundation = root / "00_foundation_skeleton"
    if (foundation / "05_data_instance" / "nodes_final.jsonl").exists():
        graph_dirs.append(foundation)
    graph_dirs.extend(
        graph_dir
        for graph_dir in sorted(root.glob("BATCH-*"))
        if (graph_dir / "05_data_instance" / "nodes_final.jsonl").exists()
    )
    return graph_dirs


def add_alias_row(rows: list[dict], *, alias: str, canonical: str, node: dict, graph_dir: Path, source_field: str) -> None:
    alias = alias.strip()
    canonical = canonical.strip()
    if not alias or not canonical:
        return
    if normalize_alias(alias) == normalize_alias(canonical):
        return
    rows.append(
        {
            "alias": alias,
            "alias_norm": normalize_alias(alias),
            "canonical_name": canonical,
            "entityType": node.get("entityType", ""),
            "code": node.get("code", ""),
            "source_batch": graph_dir.name,
            "source_file": str(graph_dir / "05_data_instance" / "nodes_final.jsonl"),
            "source_field": source_field,
        }
    )


def collect_alias_rows(graph_dirs: list[Path]) -> list[dict]:
    rows: list[dict] = []
    seen = set()
    for graph_dir in graph_dirs:
        nodes = read_jsonl(graph_dir / "05_data_instance" / "nodes_final.jsonl")
        for node in nodes:
            canonical = str(node.get("preferred_name") or node.get("name") or node.get("display_name") or "").strip()
            if not canonical:
                continue
            for field in ALIAS_FIELDS:
                for alias in split_alias_value(node.get(field)):
                    key = (normalize_alias(alias), canonical, node.get("entityType", ""), node.get("code", ""), graph_dir.name, field)
                    if key in seen:
                        continue
                    add_alias_row(rows, alias=alias, canonical=canonical, node=node, graph_dir=graph_dir, source_field=field)
                    seen.add(key)
            for field in ("name", "display_name", "preferred_name"):
                value = str(node.get(field) or "").strip()
                if not value:
                    continue
                key = (normalize_alias(value), canonical, node.get("entityType", ""), node.get("code", ""), graph_dir.name, field)
                if key in seen:
                    continue
                add_alias_row(rows, alias=value, canonical=canonical, node=node, graph_dir=graph_dir, source_field=field)
                seen.add(key)
    return rows


def build_conflicts(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["alias_norm"]].append(row)

    conflicts: list[dict] = []
    for alias_norm, items in grouped.items():
        canonical_targets = sorted({(item["entityType"], item["canonical_name"], item["code"]) for item in items})
        if len(canonical_targets) <= 1:
            continue
        aliases = sorted({item["alias"] for item in items})
        conflicts.append(
            {
                "alias_norm": alias_norm,
                "alias_examples": " | ".join(aliases[:8]),
                "target_count": len(canonical_targets),
                "targets": " || ".join(f"{entity_type}:{name}:{code}" for entity_type, name, code in canonical_targets[:20]),
                "source_batches": " | ".join(sorted({item["source_batch"] for item in items})),
            }
        )
    return conflicts


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a cross-batch terminology alias ledger.")
    parser.add_argument("--collection-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    graph_dirs = discover_graph_dirs(args.collection_root)
    rows = collect_alias_rows(graph_dirs)
    rows.sort(key=lambda item: (item["entityType"], item["canonical_name"], item["alias_norm"], item["source_batch"]))
    conflicts = build_conflicts(rows)
    conflicts.sort(key=lambda item: (-item["target_count"], item["alias_norm"]))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.output_dir / "terminology_alias_ledger.csv",
        rows,
        ["alias", "alias_norm", "canonical_name", "entityType", "code", "source_batch", "source_file", "source_field"],
    )
    write_csv(
        args.output_dir / "terminology_alias_conflict_register.csv",
        conflicts,
        ["alias_norm", "alias_examples", "target_count", "targets", "source_batches"],
    )
    counts_by_type = Counter(row["entityType"] for row in rows)
    with (args.output_dir / "terminology_alias_summary.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "audited_graph_count": len(graph_dirs),
                "alias_row_count": len(rows),
                "unique_alias_count": len({row["alias_norm"] for row in rows}),
                "conflict_alias_count": len(conflicts),
                "counts_by_entityType": dict(sorted(counts_by_type.items())),
                "source_graph_dirs": [graph_dir.name for graph_dir in graph_dirs],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("alias_rows", len(rows))
    print("unique_aliases", len({row["alias_norm"] for row in rows}))
    print("conflicts", len(conflicts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
