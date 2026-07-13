# -*- coding: utf-8 -*-
"""清理 AMI/HF 下误归属的“血培养”检验关系。

背景：
全局检验指标缺口补证后仅剩 2 条血培养：
- 急性心肌梗死 -> 血培养
- 心力衰竭 -> 血培养

复核发现：
AMI 的证据文本实际来自感染性心内膜炎“血培养阴性”段落；
HF 的证据文本是“感染性心内膜炎/风湿性心脏病时”的条件性检查。
两者都不应作为 AMI/HF 常规检验项目在前端展示。

处理：
仅删除这两条 Disease -[:requires_lab_test]-> LabTest 关系；
不删除 LabTest 节点，不删除 Evidence 节点。
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "心血管内科文献集合"
BATCH_ID = "BATCH-CARD-LAB-CLEANUP-20260713-001"
OUT_DIR = COLLECTION / f"{BATCH_ID}_血培养误归属检验关系清理_blood_culture_cleanup"
TARGETS = [
    {"disease_code": "DIS-CARD-CAD-AMI", "lab_code": "LAB-CARD-TEXT-48E9A64933"},
    {"disease_code": "DIS-CARD-HF", "lab_code": "LAB-CARD-TEXT-48E9A64933"},
]


def parse_conn() -> tuple[str, str, str]:
    text = ""
    for path in ROOT.glob("*.txt"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        if "bolt://" in content and "http://" in content:
            text = content
            break
    if not text:
        raise RuntimeError("未找到 Neo4j 链接文件")
    bolt = re.search(r"bolt://[^\s；;]+", text)
    password = re.search(r"([A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+)", text)
    if not (bolt and password):
        raise RuntimeError("Neo4j Bolt 或密码解析失败")
    return bolt.group(0), "neo4j", password.group(1)


def rows_to_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    bolt, user, password = parse_conn()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session() as session:
            before = session.run(
                """
                UNWIND $targets AS row
                MATCH (d:KGNode {code: row.disease_code})-[r:requires_lab_test]->(l:KGNode {code: row.lab_code})
                RETURN d.code AS disease_code,
                       d.name AS disease_name,
                       l.code AS lab_code,
                       l.name AS lab_name,
                       r.id AS relation_id,
                       r.evidence_text AS evidence_text,
                       r.evidence_ids AS evidence_ids,
                       r.batch_id AS old_batch_id,
                       r.source_name AS source_name,
                       r.segment_id AS segment_id
                ORDER BY d.code
                """,
                targets=TARGETS,
            ).data()
            session.run(
                """
                UNWIND $targets AS row
                MATCH (:KGNode {code: row.disease_code})-[r:requires_lab_test]->(:KGNode {code: row.lab_code})
                DELETE r
                """,
                targets=TARGETS,
            ).consume()
            after = session.run(
                """
                UNWIND $targets AS row
                OPTIONAL MATCH (d:KGNode {code: row.disease_code})-[r:requires_lab_test]->(l:KGNode {code: row.lab_code})
                RETURN row.disease_code AS disease_code,
                       row.lab_code AS lab_code,
                       count(r) AS remaining_relation_count
                ORDER BY row.disease_code
                """,
                targets=TARGETS,
            ).data()

    blocked = []
    for row in before:
        reason = (
            "原文证据不是该疾病常规检验项目依据；"
            "AMI 证据实际来自感染性心内膜炎血培养阴性段落，"
            "HF 证据为感染性心内膜炎/风湿性心脏病条件性检查。"
        )
        blocked.append({**row, "cleanup_reason": reason, "cleanup_action": "deleted_requires_lab_test_relation"})

    summary = {
        "batch_id": BATCH_ID,
        "target_count": len(TARGETS),
        "matched_before_count": len(before),
        "deleted_relation_count": len(before),
        "after": after,
        "hard_gate_pass": all(row["remaining_relation_count"] == 0 for row in after),
    }
    rows_to_csv(OUT_DIR / "01_audit" / "血培养误归属关系清理前记录.csv", blocked)
    (OUT_DIR / "01_audit" / "cleanup_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "README.md").write_text(
        "\n".join(
            [
                f"# {BATCH_ID} 血培养误归属检验关系清理",
                "",
                "本批次仅删除 AMI/HF 到“血培养”的误归属 requires_lab_test 关系。",
                "不删除 LabTest 节点，不删除 Evidence 节点。",
                "",
                f"- 删除关系数：{summary['deleted_relation_count']}",
                f"- 硬闸门：{summary['hard_gate_pass']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
