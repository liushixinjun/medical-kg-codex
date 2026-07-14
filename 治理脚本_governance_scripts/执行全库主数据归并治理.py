from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "心血管内科文献集合" / "20260714_全库主数据归并治理"
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260714_全库主数据归并治理"

EXCLUDED_ENTITY_TYPES = {
    "Evidence",
    "Guideline",
    "RecommendationStatement",
    "ClinicalRule",
    "ClinicalPathway",
    "SourceDocument",
}

SAFE_OUTGOING_REL_TYPES = [
    "supported_by_evidence",
    "has_diagnostic_component",
    "has_differential_point",
    "includes_medication",
    "includes_procedure",
    "has_treatment_component",
    "has_threshold_rule",
    "has_exam_indicator",
    "exam_has_indicator",
    "lab_test_has_indicator",
    "requires_exclusion_exam",
    "may_block_action",
    "derived_from",
    "based_on_guideline",
]

SAFE_INCOMING_REL_TYPES = [
    "has_symptom",
    "has_sign",
    "has_risk_factor",
    "has_complication",
    "has_exam",
    "has_lab_test",
    "has_exam_indicator",
    "has_diagnostic_criteria",
    "has_differential_diagnosis",
    "has_treatment_plan",
    "has_medication",
    "has_procedure",
    "has_follow_up",
    "has_prognosis",
    "has_prevention",
    "has_etiology",
    "has_pathophysiology",
    "has_epidemiology",
    "has_risk_stratification",
    "includes_medication",
    "includes_procedure",
    "has_treatment_component",
    "recommends_action",
    "requires_exclusion_exam",
    "may_block_action",
    "has_diagnostic_component",
    "has_differential_point",
    "supported_by_evidence",
]

PREFERRED_CODES = {
    "心电图": ["EXAM-ECG"],
    "超声心动图": ["EXAM-TTE"],
    "心脏磁共振": ["EXAM-CMR"],
    "冠状动脉造影": ["EXAM-CAG"],
    "冠状动脉CT血管成像": ["EXAM-CCTA"],
    "植入式心律转复除颤器": ["PROC-ICD"],
    "心脏移植": ["PROC-HEART-TRANSPLANT"],
    "临时起搏": ["PROC-CARD-128A6330E583"],
    "永久起搏器植入": ["PROC-CARD-E94100E376BD"],
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_connection() -> tuple[str, str, str]:
    text = CONNECTION_FILE.read_text(encoding="utf-8", errors="ignore")
    bolt = re.search(r"bolt://[^\s，,]+", text)
    user = re.search(r"用户名\s*[:：]\s*([^\s，,]+)", text)
    pwd = re.search(r"密码\s*[:：]\s*([^\s，,]+)", text)
    if not (bolt and user and pwd):
        raise RuntimeError("图谱数据库链接.txt 缺少 Bolt/用户名/密码字段")
    return bolt.group(0), user.group(1), pwd.group(1)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({k for row in rows for k in row})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def relationship_type_is_safe(rel_type: str) -> bool:
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", rel_type) is not None


def stable_list(*values: Any) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for value in values:
        if value in (None, "", [], {}):
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item in (None, "", [], {}):
                continue
            key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
            if key not in seen:
                seen.add(key)
                out.append(item)
    return out


def fetch_duplicate_groups(tx) -> list[dict[str, Any]]:
    records = tx.run(
        """
        MATCH (d:Disease)-[rel]->(n:KGNode)
        WHERE n.entityType IS NOT NULL
          AND n.name IS NOT NULL
          AND NOT n.entityType IN $excluded
        WITH d.code AS disease_code,
             d.name AS disease,
             n.entityType AS entityType,
             n.name AS name,
             collect(DISTINCT n.code) AS codes,
             collect(DISTINCT type(rel)) AS direct_rel_types,
             count(DISTINCT n.code) AS c
        WHERE c > 1
        RETURN disease_code, disease, entityType, name, codes, direct_rel_types
        ORDER BY disease_code, entityType, name
        """,
        excluded=sorted(EXCLUDED_ENTITY_TYPES),
    )
    return [dict(r) for r in records]


def fetch_node_stats(tx, codes: list[str]) -> dict[str, dict[str, Any]]:
    records = tx.run(
        """
        MATCH (n:KGNode)
        WHERE n.code IN $codes
        OPTIONAL MATCH (n)-[out]->()
        WITH n, count(out) AS out_degree
        OPTIONAL MATCH ()-[inc]->(n)
        WITH n, out_degree, count(inc) AS in_degree
        RETURN n.code AS code,
               labels(n) AS labels,
               properties(n) AS props,
               out_degree,
               in_degree
        """,
        codes=codes,
    )
    return {r["code"]: dict(r) for r in records}


def code_penalty(code: str) -> int:
    markers = ["CADREM", "SKELETON", "FULLBOOK", "FULL", "TEXT", "BACKFILL", "CURATED"]
    return sum(1 for marker in markers if marker in code)


def choose_canonical(group: dict[str, Any], stats: dict[str, dict[str, Any]]) -> tuple[str, str]:
    codes = list(group["codes"])
    name = str(group["name"])
    for preferred in PREFERRED_CODES.get(name, []):
        if preferred in codes:
            return preferred, "preferred_code"

    def score(code: str) -> tuple[int, int, int, int, str]:
        node = stats.get(code) or {}
        props = node.get("props") or {}
        formal = 1 if props.get("formal_cdss_ready") is True else 0
        degree = int(node.get("in_degree") or 0) + int(node.get("out_degree") or 0)
        penalty = code_penalty(code)
        return (formal, -penalty, degree, -len(code), code)

    best = sorted(codes, key=score, reverse=True)[0]
    reason = "formal_or_low_penalty_high_degree"
    return best, reason


def build_candidates(tx) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    groups = fetch_duplicate_groups(tx)
    for group in groups:
        codes = list(group["codes"])
        if len(codes) < 2:
            continue
        entity_type = str(group["entityType"])
        stats = fetch_node_stats(tx, codes)
        if entity_type in EXCLUDED_ENTITY_TYPES:
            blockers.append({**group, "block_reason": "excluded_entity_type"})
            continue
        if any(code not in stats for code in codes):
            blockers.append({**group, "block_reason": "missing_node_stats"})
            continue
        canonical, reason = choose_canonical(group, stats)
        for duplicate_code in codes:
            if duplicate_code == canonical:
                continue
            dup_stats = stats[duplicate_code]
            can_stats = stats[canonical]
            candidates.append(
                {
                    "disease_code": group["disease_code"],
                    "disease": group["disease"],
                    "entityType": entity_type,
                    "name": group["name"],
                    "canonical_code": canonical,
                    "duplicate_code": duplicate_code,
                    "canonical_reason": reason,
                    "direct_rel_types": "|".join(sorted(group["direct_rel_types"] or [])),
                    "duplicate_in_degree": dup_stats.get("in_degree", 0),
                    "duplicate_out_degree": dup_stats.get("out_degree", 0),
                    "canonical_in_degree": can_stats.get("in_degree", 0),
                    "canonical_out_degree": can_stats.get("out_degree", 0),
                    "action": "apply_safe_relation_migration",
                }
            )
    summary = {
        "batch_id": BATCH_ID,
        "generated_at": now_iso(),
        "duplicate_group_count": len(groups),
        "candidate_duplicate_node_count": len(candidates),
        "blocked_group_count": len(blockers),
        "candidate_entity_type_counts": dict(Counter(row["entityType"] for row in candidates)),
    }
    return candidates, blockers, summary


def merge_node_properties(tx, duplicate_code: str, canonical_code: str) -> None:
    now = now_iso()
    rec = tx.run(
        """
        MATCH (dup:KGNode {code:$duplicate_code})
        MATCH (can:KGNode {code:$canonical_code})
        RETURN properties(dup) AS dup_props, properties(can) AS can_props
        """,
        duplicate_code=duplicate_code,
        canonical_code=canonical_code,
    ).single()
    if not rec:
        return
    dup_props = dict(rec["dup_props"] or {})
    can_props = dict(rec["can_props"] or {})
    aliases = stable_list(can_props.get("aliases"), dup_props.get("aliases"), dup_props.get("name"), dup_props.get("preferred_name"), dup_props.get("display_name"))
    source_codes = stable_list(can_props.get("merged_duplicate_codes"), dup_props.get("merged_duplicate_codes"), duplicate_code)
    source_batches = stable_list(can_props.get("merged_from_batches"), dup_props.get("batch_id"), dup_props.get("source_batch"), BATCH_ID)
    tx.run(
        """
        MATCH (dup:KGNode {code:$duplicate_code})
        MATCH (can:KGNode {code:$canonical_code})
        SET can.aliases=$aliases,
            can.merged_duplicate_codes=$source_codes,
            can.merged_from_batches=$source_batches,
            can.master_data_merge_batch_id=$batch_id,
            can.updated_at=$now,
            dup.duplicate_replaced_by=$canonical_code,
            dup.duplicate_fix_batch_id=$batch_id,
            dup.duplicate_direct_link_removed_at=$now,
            dup.updated_at=$now
        """,
        duplicate_code=duplicate_code,
        canonical_code=canonical_code,
        aliases=aliases,
        source_codes=source_codes,
        source_batches=source_batches,
        batch_id=BATCH_ID,
        now=now,
    )


def migrate_incoming_relationship(tx, duplicate_code: str, canonical_code: str, rel_type: str) -> int:
    if not relationship_type_is_safe(rel_type):
        raise ValueError(f"非法关系类型：{rel_type}")
    now = now_iso()
    rec = tx.run(
        f"""
        MATCH (src)-[old:`{rel_type}`]->(dup:KGNode {{code:$duplicate_code}})
        MATCH (can:KGNode {{code:$canonical_code}})
        WHERE src <> can
        WITH src, old, dup, can, properties(old) AS old_props
        MERGE (src)-[new:`{rel_type}`]->(can)
        SET new += old_props,
            new.updated_at=$now,
            new.master_data_merge_batch_id=$batch_id,
            new.link_method=coalesce(new.link_method, 'master_data_duplicate_relation_migration')
        DELETE old
        RETURN count(*) AS c
        """,
        duplicate_code=duplicate_code,
        canonical_code=canonical_code,
        now=now,
        batch_id=BATCH_ID,
    ).single()
    return int(rec["c"] or 0) if rec else 0


def migrate_outgoing_relationship(tx, duplicate_code: str, canonical_code: str, rel_type: str) -> int:
    if not relationship_type_is_safe(rel_type):
        raise ValueError(f"非法关系类型：{rel_type}")
    now = now_iso()
    rec = tx.run(
        f"""
        MATCH (dup:KGNode {{code:$duplicate_code}})-[old:`{rel_type}`]->(dst)
        MATCH (can:KGNode {{code:$canonical_code}})
        WHERE dst <> can
        WITH dup, old, dst, can, properties(old) AS old_props
        MERGE (can)-[new:`{rel_type}`]->(dst)
        SET new += old_props,
            new.updated_at=$now,
            new.master_data_merge_batch_id=$batch_id,
            new.link_method=coalesce(new.link_method, 'master_data_duplicate_relation_migration')
        DELETE old
        RETURN count(*) AS c
        """,
        duplicate_code=duplicate_code,
        canonical_code=canonical_code,
        now=now,
        batch_id=BATCH_ID,
    ).single()
    return int(rec["c"] or 0) if rec else 0


def apply_candidate(tx, row: dict[str, Any]) -> dict[str, Any]:
    duplicate_code = row["duplicate_code"]
    canonical_code = row["canonical_code"]
    merge_node_properties(tx, duplicate_code, canonical_code)

    incoming_counts: dict[str, int] = {}
    outgoing_counts: dict[str, int] = {}
    direct_rel_types = [x for x in str(row.get("direct_rel_types") or "").split("|") if x]
    incoming_types = sorted(set(SAFE_INCOMING_REL_TYPES + direct_rel_types))
    for rel_type in incoming_types:
        count = migrate_incoming_relationship(tx, duplicate_code, canonical_code, rel_type)
        if count:
            incoming_counts[rel_type] = count
    for rel_type in SAFE_OUTGOING_REL_TYPES:
        count = migrate_outgoing_relationship(tx, duplicate_code, canonical_code, rel_type)
        if count:
            outgoing_counts[rel_type] = count
    return {
        **row,
        "incoming_relations_migrated": sum(incoming_counts.values()),
        "outgoing_relations_migrated": sum(outgoing_counts.values()),
        "incoming_detail": json.dumps(incoming_counts, ensure_ascii=False, sort_keys=True),
        "outgoing_detail": json.dumps(outgoing_counts, ensure_ascii=False, sort_keys=True),
        "status": "applied",
    }


def postcheck(tx) -> dict[str, Any]:
    same_disease_duplicates = tx.run(
        """
        MATCH (d:Disease)-[]->(n:KGNode)
        WHERE n.entityType IS NOT NULL
          AND n.name IS NOT NULL
          AND NOT n.entityType IN $excluded
        WITH d.code AS disease_code, n.entityType AS entityType, n.name AS name, count(DISTINCT n.code) AS c
        WHERE c > 1
        RETURN count(*) AS c
        """,
        excluded=sorted(EXCLUDED_ENTITY_TYPES),
    ).single()["c"]
    remaining_by_type = tx.run(
        """
        MATCH (d:Disease)-[]->(n:KGNode)
        WHERE n.entityType IS NOT NULL
          AND n.name IS NOT NULL
          AND NOT n.entityType IN $excluded
        WITH d.code AS disease_code, n.entityType AS entityType, n.name AS name, count(DISTINCT n.code) AS c
        WHERE c > 1
        RETURN entityType, count(*) AS groups
        ORDER BY groups DESC, entityType
        """,
        excluded=sorted(EXCLUDED_ENTITY_TYPES),
    )
    non_kgnode = tx.run("MATCH (n) WHERE NOT n:KGNode RETURN count(n) AS c").single()["c"]
    label_mismatch = tx.run(
        """
        MATCH (n:KGNode)
        WHERE n.entityType IS NOT NULL AND NOT n.entityType IN labels(n)
        RETURN count(n) AS c
        """
    ).single()["c"]
    return {
        "same_disease_same_type_same_name_duplicates": int(same_disease_duplicates or 0),
        "remaining_by_type": [dict(r) for r in remaining_by_type],
        "non_kgnode": int(non_kgnode or 0),
        "label_mismatch": int(label_mismatch or 0),
    }


def write_report(summary: dict[str, Any], post: dict[str, Any] | None = None) -> None:
    lines = [
        "# 全库主数据归并治理报告",
        "",
        f"- 批次：{BATCH_ID}",
        f"- 时间：{now_iso()}",
        f"- 模式：{summary.get('mode')}",
        "",
        "## 范围",
        "",
        "- 处理对象：同一疾病下、同一实体类型、同名的主数据重复直连。",
        "- 自动排除：Evidence、Guideline、RecommendationStatement、ClinicalRule、ClinicalPathway。",
        "- 执行策略：迁移关系到 canonical 节点，duplicate 节点保留并打标，不做粗暴删除。",
        "",
        "## dry-run / apply 统计",
        "",
        f"- 重复组：{summary.get('duplicate_group_count', 0)}",
        f"- 候选重复节点：{summary.get('candidate_duplicate_node_count', 0)}",
        f"- 阻断组：{summary.get('blocked_group_count', 0)}",
    ]
    if "applied_duplicate_node_count" in summary:
        lines.append(f"- 已执行重复节点：{summary.get('applied_duplicate_node_count', 0)}")
        lines.append(f"- 迁移入边：{summary.get('incoming_relations_migrated', 0)}")
        lines.append(f"- 迁移出边：{summary.get('outgoing_relations_migrated', 0)}")
    lines.extend(["", "## 候选类型分布", ""])
    for entity_type, count in sorted((summary.get("candidate_entity_type_counts") or {}).items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- {entity_type}：{count}")
    if post:
        lines.extend(["", "## 服务器复核", ""])
        for key, value in post.items():
            if key == "remaining_by_type":
                continue
            lines.append(f"- {key}：{value}")
        if post.get("remaining_by_type"):
            lines.append("")
            lines.append("剩余重复类型：")
            for row in post["remaining_by_type"]:
                lines.append(f"- {row['entityType']}：{row['groups']}")
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "本轮只治理高置信主数据重复直连，不合并证据与推荐陈述；低置信或需临床语义判断的内容保留为后续治理候选。",
        ]
    )
    (OUT_DIR / "05_全库主数据归并治理报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="全库主数据同病种同类型同名重复直连治理")
    parser.add_argument("--apply", action="store_true", help="执行写库；默认只生成 dry-run")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bolt, user, password = read_connection()
    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session(database="neo4j") as session:
            candidates, blockers, summary = session.execute_read(build_candidates)
            summary["mode"] = "apply" if args.apply else "dry-run"
            write_csv(
                OUT_DIR / "01_主数据归并候选清单.csv",
                candidates,
                [
                    "disease_code",
                    "disease",
                    "entityType",
                    "name",
                    "canonical_code",
                    "duplicate_code",
                    "canonical_reason",
                    "direct_rel_types",
                    "duplicate_in_degree",
                    "duplicate_out_degree",
                    "canonical_in_degree",
                    "canonical_out_degree",
                    "action",
                ],
            )
            write_csv(OUT_DIR / "02_主数据归并阻断清单.csv", blockers)
            write_json(OUT_DIR / "03_dryrun_summary.json", summary)

            applied_rows: list[dict[str, Any]] = []
            post: dict[str, Any] | None = None
            if args.apply:
                for row in candidates:
                    applied_rows.append(session.execute_write(apply_candidate, row))
                summary["applied_duplicate_node_count"] = len(applied_rows)
                summary["incoming_relations_migrated"] = sum(int(r.get("incoming_relations_migrated") or 0) for r in applied_rows)
                summary["outgoing_relations_migrated"] = sum(int(r.get("outgoing_relations_migrated") or 0) for r in applied_rows)
                post = session.execute_read(postcheck)
                write_csv(
                    OUT_DIR / "04_主数据归并执行明细.csv",
                    applied_rows,
                    [
                        "disease_code",
                        "disease",
                        "entityType",
                        "name",
                        "canonical_code",
                        "duplicate_code",
                        "incoming_relations_migrated",
                        "outgoing_relations_migrated",
                        "incoming_detail",
                        "outgoing_detail",
                        "status",
                    ],
                )
                write_json(OUT_DIR / "06_postcheck_服务器复核.json", {"summary": summary, "postcheck": post})
            write_report(summary, post)
            print(json.dumps({"summary": summary, "postcheck": post}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
