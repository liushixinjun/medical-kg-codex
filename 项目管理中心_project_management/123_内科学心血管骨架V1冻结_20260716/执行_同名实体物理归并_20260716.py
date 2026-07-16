from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent
CONN_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260716_内科学骨架同名实体归并"
EXCLUDED_TYPES = {"Disease", "DiseaseCategory", "DiseaseSubcategory", "Evidence", "Guideline", "SourceSection"}


def parse_conn() -> tuple[str, str, str]:
    text = CONN_FILE.read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text).group(0)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text).group(1)
    pwd = re.search(r"密码[:：]\s*([^\s；;]+)", text).group(1)
    return uri, user, pwd


def listify(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x is not None and str(x).strip()]
    if isinstance(v, str):
        if not v.strip():
            return []
        return [v.strip()]
    return [str(v)]


def canonical_score(n: dict[str, Any]) -> tuple[int, int, str]:
    code = n.get("code") or ""
    status = n.get("status") or ""
    source_type = n.get("source_type") or ""
    knowledge_layer = n.get("knowledge_layer") or ""
    degree = int(n.get("degree") or 0)

    score = 0
    if status == "deprecated":
        score -= 200
    if "-CADREM-" in code or "-CM-" in code or "-HF-" in code or "-ARR-" in code:
        score -= 40
    if code.startswith("CARD-SKELETON"):
        score += 10
    if "-STD-" in code:
        score += 90
    if re.match(r"^(MED|EXAM|LAB|SYM|SIGN|PROC|RF)-CARD-[0-9A-F]", code):
        score += 70
    if re.match(r"^(EXAM|LAB|MED|PROC)-[A-Z0-9-]+$", code) and "-CADREM-" not in code:
        score += 60
    if source_type == "authoritative_textbook":
        score += 20
    if knowledge_layer == "textbook_core":
        score += 10
    score += min(degree, 50)
    return (score, degree, code)


def run() -> dict[str, Any]:
    uri, user, pwd = parse_conn()
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result: dict[str, Any] = {"batch_id": BATCH_ID, "executed_at": now}
    merged_groups = []
    skipped_groups = []

    with driver.session() as s:
        groups = [
            dict(r)
            for r in s.run(
                """
                MATCH (n:KGNode)
                WHERE n.entityType IS NOT NULL
                  AND n.name IS NOT NULL
                  AND NOT n.entityType IN $excluded
                  AND coalesce(n.status,'active') <> 'deleted'
                WITH n.entityType AS type, n.name AS name, collect(n) AS nodes, count(*) AS c
                WHERE c > 1
                RETURN type, name,
                       [x IN nodes | {
                         dbid:id(x),
                         code:x.code,
                         aliases:x.aliases,
                         status:x.status,
                         source_type:x.source_type,
                         knowledge_layer:x.knowledge_layer,
                         degree: count { (x)--() }
                       }] AS nodes
                ORDER BY type, name
                """,
                excluded=list(EXCLUDED_TYPES),
            )
        ]

        for g in groups:
            nodes = g["nodes"]
            if len(nodes) <= 1:
                continue
            nodes_sorted = sorted(nodes, key=canonical_score, reverse=True)
            keep = nodes_sorted[0]
            dups = nodes_sorted[1:]
            # ClinicalRule 如规则正文不同，先跳过，避免不同临床规则被误并。
            if g["type"] == "ClinicalRule":
                skipped_groups.append(
                    {
                        "type": g["type"],
                        "name": g["name"],
                        "reason": "ClinicalRule需逐条校验rule_text，暂不自动物理合并",
                        "codes": [n.get("code") for n in nodes],
                    }
                )
                continue

            aliases = []
            merged_from_codes = []
            for n in nodes:
                aliases.extend(listify(n.get("aliases")))
                aliases.append(g["name"])
                if n.get("code") != keep.get("code"):
                    merged_from_codes.append(n.get("code"))
            aliases = sorted({x for x in aliases if x and x != keep.get("code")})
            merged_from_codes = sorted({x for x in merged_from_codes if x})

            try:
                rec = s.run(
                    """
                    MATCH (keep:KGNode) WHERE id(keep)=$keep_id
                    MATCH (dup:KGNode) WHERE id(dup) IN $dup_ids
                    SET keep.aliases=$aliases,
                        keep.merged_from_codes=coalesce(keep.merged_from_codes,[]) + $merged_from_codes,
                        keep.master_data_merge_status='merged_duplicate_same_type_name',
                        keep.master_data_merged_at=$now,
                        keep.master_data_merge_batch=$batch_id,
                        keep.updated_at=$now,
                        keep.updated_by=$batch_id
                    WITH keep, collect(dup) AS dups
                    CALL apoc.refactor.mergeNodes([keep] + dups, {
                        properties:'discard',
                        mergeRels:true,
                        produceSelfRel:false,
                        preserveExistingSelfRels:false
                    }) YIELD node
                    RETURN node.code AS code, size(dups) AS merged_count
                    """,
                    keep_id=keep["dbid"],
                    dup_ids=[n["dbid"] for n in dups],
                    aliases=aliases,
                    merged_from_codes=merged_from_codes,
                    now=now,
                    batch_id=BATCH_ID,
                ).single()
                merged_groups.append(
                    {
                        "type": g["type"],
                        "name": g["name"],
                        "kept_code": rec["code"],
                        "merged_count": rec["merged_count"],
                        "merged_codes": merged_from_codes,
                    }
                )
            except Exception as exc:
                skipped_groups.append(
                    {
                        "type": g["type"],
                        "name": g["name"],
                        "reason": f"merge_failed: {type(exc).__name__}: {str(exc)[:300]}",
                        "codes": [n.get("code") for n in nodes],
                    }
                )

        remaining = [
            dict(r)
            for r in s.run(
                """
                MATCH (n:KGNode)
                WHERE n.entityType IS NOT NULL
                  AND n.name IS NOT NULL
                  AND NOT n.entityType IN $excluded
                  AND coalesce(n.status,'active') <> 'deleted'
                WITH n.entityType AS type, n.name AS name, count(*) AS c
                WHERE c > 1
                RETURN type, count(*) AS groups, sum(c) AS nodes
                ORDER BY groups DESC
                """,
                excluded=list(EXCLUDED_TYPES),
            )
        ]

    driver.close()
    result["merged_group_count"] = len(merged_groups)
    result["merged_node_count"] = sum(x["merged_count"] for x in merged_groups)
    result["skipped_group_count"] = len(skipped_groups)
    result["merged_groups"] = merged_groups
    result["skipped_groups"] = skipped_groups
    result["remaining_duplicates_by_type"] = remaining
    (OUT_DIR / "08_同名实体物理归并执行结果.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
