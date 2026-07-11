from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_textbook_skeleton_curated_delta import parse_connection_file, result_rows  # noqa: E402
from scripts.import_neo4j_test_db import Neo4jHttpClient  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("status,message\nOK,No blockers\n", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_server_nodes(connection_file: Path) -> tuple[set[str], dict[tuple[str, str], list[str]]]:
    uri, username, password = parse_connection_file(connection_file)
    client = Neo4jHttpClient(uri, username, password, "neo4j", 3, 1)
    result = client.run(
        """
        MATCH (n:KGNode)
        RETURN n.code AS code, n.entityType AS entityType, n.name AS name
        """
    )
    codes = set()
    by_type_name: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in result_rows(result):
        code = str(row.get("code") or "").strip()
        entity_type = str(row.get("entityType") or "").strip()
        name = str(row.get("name") or "").strip()
        if code:
            codes.add(code)
        if entity_type and name and code:
            by_type_name[(entity_type, name)].append(code)
    return codes, by_type_name


def main() -> int:
    parser = argparse.ArgumentParser(description="G2 preimport audit for textbook skeleton curated delta.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--connection-file", required=True, type=Path)
    parser.add_argument("--batch-id", default="CARD-SKELETON-20260709")
    args = parser.parse_args()

    nodes = read_jsonl(args.out_dir / "阶段C5_curated_delta_nodes_20260709.jsonl")
    relations = read_jsonl(args.out_dir / "阶段C5_curated_delta_relations_20260709.jsonl")
    evidence_nodes = [n for n in nodes if n.get("entityType") == "Evidence"]
    server_codes, server_by_type_name = load_server_nodes(args.connection_file)

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    node_codes = set()
    delta_by_type_name: dict[tuple[str, str], list[str]] = defaultdict(list)
    for n in nodes:
        code = str(n.get("code") or "").strip()
        entity_type = str(n.get("entityType") or "").strip()
        name = str(n.get("name") or "").strip()
        if not code:
            blockers.append({"level": "blocker", "type": "node_missing_code", "id": n.get("id", ""), "message": "节点缺code"})
            continue
        if code in node_codes:
            blockers.append({"level": "blocker", "type": "duplicate_node_code_in_delta", "id": code, "message": "delta内code重复"})
        node_codes.add(code)
        if not entity_type:
            blockers.append({"level": "blocker", "type": "node_missing_entityType", "id": code, "message": "节点缺entityType"})
        if not name:
            blockers.append({"level": "blocker", "type": "node_missing_name", "id": code, "message": "节点缺name"})
        if n.get("formal_cdss_ready") is True:
            blockers.append({"level": "blocker", "type": "formal_cdss_ready_true", "id": code, "message": "教材骨架delta不得标记formal_cdss_ready=true"})
        if str(n.get("import_status", "")) == "local_candidate_not_imported":
            blockers.append({"level": "blocker", "type": "candidate_status_leaked", "id": code, "message": "curated delta不能带local_candidate_not_imported"})
        if entity_type and name:
            delta_by_type_name[(entity_type, name)].append(code)
        if entity_type == "Evidence" and not str(n.get("text_excerpt", "")).strip():
            blockers.append({"level": "blocker", "type": "evidence_missing_excerpt", "id": code, "message": "Evidence缺原文摘要"})

    for (entity_type, name), codes in delta_by_type_name.items():
        if len(set(codes)) > 1:
            blockers.append(
                {
                    "level": "blocker",
                    "type": "duplicate_type_name_in_delta",
                    "id": "|".join(codes[:5]),
                    "message": f"delta内同类型同名重复：{entity_type}/{name}",
                }
            )
        server_codes_same = [c for c in server_by_type_name.get((entity_type, name), []) if c not in set(codes)]
        if server_codes_same and entity_type != "Evidence":
            blockers.append(
                {
                    "level": "blocker",
                    "type": "would_duplicate_server_type_name",
                    "id": "|".join(codes[:3]),
                    "message": f"服务器已有同类型同名节点但delta仍要新建：{entity_type}/{name} -> {server_codes_same[:3]}",
                }
            )

    relation_keys = set()
    for r in relations:
        rel_id = str(r.get("id") or "").strip()
        source = str(r.get("source_code") or "").strip()
        target = str(r.get("target_code") or "").strip()
        rel_type = str(r.get("relationType") or "").strip()
        if not rel_id or not source or not target or not rel_type:
            blockers.append({"level": "blocker", "type": "relation_missing_key_field", "id": rel_id, "message": "关系缺id/source/target/type"})
            continue
        key = (source, rel_type, target)
        if key in relation_keys:
            blockers.append({"level": "blocker", "type": "duplicate_semantic_relation_in_delta", "id": rel_id, "message": "delta内语义关系重复"})
        relation_keys.add(key)
        if source not in node_codes and source not in server_codes:
            blockers.append({"level": "blocker", "type": "relation_source_missing", "id": rel_id, "message": f"关系source不存在：{source}"})
        if target not in node_codes and target not in server_codes:
            blockers.append({"level": "blocker", "type": "relation_target_missing", "id": rel_id, "message": f"关系target不存在：{target}"})
        if r.get("formal_cdss_ready") is True:
            blockers.append({"level": "blocker", "type": "relation_formal_cdss_ready_true", "id": rel_id, "message": "教材骨架关系不得formal_cdss_ready=true"})
        if rel_type != "HAS_EVIDENCE" and not r.get("evidence_ids"):
            blockers.append({"level": "blocker", "type": "relation_missing_evidence_ids", "id": rel_id, "message": "非HAS_EVIDENCE关系缺evidence_ids"})

    # Warnings: English abbreviations as main names.
    for n in nodes:
        name = str(n.get("name") or "")
        if re.fullmatch(r"[A-Za-z0-9/\\-]+", name) and n.get("entityType") not in {"Evidence"}:
            warnings.append({"level": "warning", "type": "english_abbreviation_primary_name", "id": n.get("code", ""), "message": f"疑似英文缩写主名称：{name}"})

    status = "passed" if not blockers else "blocked"
    summary = {
        "batch_id": args.batch_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "node_count": len(nodes),
        "relation_count": len(relations),
        "evidence_node_count": len(evidence_nodes),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blocker_types": dict(Counter(b["type"] for b in blockers)),
        "warning_types": dict(Counter(w["type"] for w in warnings)),
        "neo4j_import_allowed": not blockers,
    }
    (args.out_dir / "阶段C5_G2入库前审计_summary_20260709.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(args.out_dir / "阶段C5_G2入库前阻断清单_20260709.csv", blockers)
    write_csv(args.out_dir / "阶段C5_G2入库前警告清单_20260709.csv", warnings)

    md = []
    md.append("# 阶段C5-G2入库前审计报告")
    md.append("")
    md.append(f"生成时间：{summary['generated_at']}")
    md.append("")
    md.append(f"结论：{status}")
    md.append("")
    md.append("| 指标 | 数值 |")
    md.append("|---|---:|")
    md.append(f"| 节点 | {len(nodes)} |")
    md.append(f"| 关系 | {len(relations)} |")
    md.append(f"| Evidence节点 | {len(evidence_nodes)} |")
    md.append(f"| 阻断项 | {len(blockers)} |")
    md.append(f"| 警告项 | {len(warnings)} |")
    md.append("")
    if blockers:
        md.append("## 阻断类型")
        md.append("")
        for k, v in Counter(b["type"] for b in blockers).most_common():
            md.append(f"- {k}: {v}")
    else:
        md.append("G2通过，允许进入Neo4j导入步骤。")
    (args.out_dir / "阶段C5_G2入库前审计报告_20260709.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
