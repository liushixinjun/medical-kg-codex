from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent
CONN_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260716_临床规则同名同正文归并"


def parse_conn() -> tuple[str, str, str]:
    text = CONN_FILE.read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text).group(0)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text).group(1)
    pwd = re.search(r"密码[:：]\s*([^\s；;]+)", text).group(1)
    return uri, user, pwd


def run() -> dict:
    uri, user, pwd = parse_conn()
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = {"batch_id": BATCH_ID, "executed_at": now, "merged": []}
    with driver.session() as s:
        groups = [
            dict(r)
            for r in s.run(
                """
                MATCH (n:KGNode {entityType:'ClinicalRule'})
                WHERE n.name IS NOT NULL AND coalesce(n.status,'active') <> 'deleted'
                WITH n.name AS name, coalesce(n.rule_text,n.original_text,n.description,n.name) AS text, collect(n) AS nodes, count(*) AS c
                WHERE c > 1
                RETURN name, text,
                       [x IN nodes | {dbid:id(x), code:x.code, layer:x.knowledge_layer, source_type:x.source_type, degree: count { (x)--() }}] AS nodes
                """
            )
        ]
        for g in groups:
            nodes = sorted(
                g["nodes"],
                key=lambda x: (
                    1 if x.get("layer") == "textbook_core" else 0,
                    1 if x.get("source_type") == "authoritative_textbook" else 0,
                    int(x.get("degree") or 0),
                    x.get("code") or "",
                ),
                reverse=True,
            )
            keep = nodes[0]
            dup_ids = [n["dbid"] for n in nodes[1:]]
            merged_codes = [n["code"] for n in nodes[1:]]
            rec = s.run(
                """
                MATCH (keep:KGNode) WHERE id(keep)=$keep_id
                MATCH (dup:KGNode) WHERE id(dup) IN $dup_ids
                SET keep.merged_from_codes=coalesce(keep.merged_from_codes,[]) + $merged_codes,
                    keep.master_data_merge_status='merged_duplicate_clinical_rule_same_text',
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
                RETURN node.code AS kept_code, size(dups) AS merged_count
                """,
                keep_id=keep["dbid"],
                dup_ids=dup_ids,
                merged_codes=merged_codes,
                now=now,
                batch_id=BATCH_ID,
            ).single()
            result["merged"].append(
                {
                    "name": g["name"],
                    "text": g["text"],
                    "kept_code": rec["kept_code"],
                    "merged_count": rec["merged_count"],
                    "merged_codes": merged_codes,
                }
            )
        remaining = [
            dict(r)
            for r in s.run(
                """
                MATCH (n:KGNode)
                WHERE n.entityType IS NOT NULL AND n.name IS NOT NULL
                WITH n.entityType AS type, n.name AS name, count(*) AS c
                WHERE c > 1
                RETURN type, count(*) AS groups, sum(c) AS nodes
                ORDER BY groups DESC
                """
            )
        ]
        result["remaining_duplicates_by_type"] = remaining
    driver.close()
    (OUT_DIR / "09_临床规则重复归并执行结果.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
