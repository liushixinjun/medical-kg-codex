from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "128_冠心病指南PDF精修层总收口_20260717"
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260717_冠心病推荐动作缺口补齐"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

REPAIRS = [
    {
        "recommendation_code": "REC-CDSS-CAD-ACS-01-01-ECG-TROP",
        "disease_code": "DIS-CARD-CAD-ACS",
        "action_targets": [
            {"label": "Exam", "names": ["心电图", "常规心电图"]},
            {"label": "LabTest", "names": ["心肌肌钙蛋白", "肌钙蛋白"]},
        ],
    },
    {
        "recommendation_code": "REC-35AFFC16987E38D3",
        "disease_code": "DIS-CARD-CAD-AMI",
        "action_targets": [{"label": "Exam", "names": ["超声心动图"]}],
    },
    {
        "recommendation_code": "REC-7025595F385004F3",
        "disease_code": "DIS-CARD-CAD-AMI",
        "action_targets": [{"label": "Exam", "names": ["心电图", "常规心电图"]}],
    },
    {
        "recommendation_code": "REC-73F794FD0A746355",
        "disease_code": "DIS-CARD-CAD-AMI",
        "action_targets": [{"label": "Exam", "names": ["冠状动脉造影", "冠脉造影"]}],
    },
    {
        "recommendation_code": "REC-775B4D172719135D",
        "disease_code": "DIS-CARD-CAD-AMI",
        "action_targets": [{"label": "LabTest", "names": ["心肌肌钙蛋白", "肌钙蛋白"]}],
    },
    {
        "recommendation_code": "REC-CB7A690AA83E529E",
        "disease_code": "DIS-CARD-CAD-AMI",
        "action_targets": [{"label": "Exam", "names": ["冠状动脉CT血管成像", "冠状动脉CTA", "冠脉CTA"]}],
    },
    {
        "recommendation_code": "REC-CDSS-CAD-CCS-01-01-TEST",
        "disease_code": "DIS-CARD-CAD-CCS",
        "action_targets": [
            {"label": "Exam", "names": ["心电图", "常规心电图"]},
            {"label": "Exam", "names": ["运动负荷试验", "负荷试验"]},
            {"label": "Exam", "names": ["冠状动脉CT血管成像", "冠状动脉CTA", "冠脉CTA"]},
            {"label": "Exam", "names": ["冠状动脉造影", "冠脉造影"]},
        ],
    },
    {
        "recommendation_code": "REC-94F5D2BD891A1C5D",
        "disease_code": "DIS-CARD-CAD-STEMI",
        "action_targets": [{"label": "Exam", "names": ["心电图", "常规心电图"]}],
    },
]


def read_connection() -> tuple[str, str, str]:
    text = CONNECTION_FILE.read_text(encoding="utf-8", errors="ignore")
    bolt_match = re.search(r"bolt://[^\s，,;；]+", text)
    if not bolt_match:
        raise RuntimeError("连接文件缺少 bolt 地址")
    username_match = re.search(r"(?:用户名|username|NEO4J_USERNAME)\s*[:：=]\s*([^\s，,;；]+)", text, re.I)
    password_match = re.search(r"(?:密码|password|NEO4J_PASSWORD)\s*[:：=]\s*([^\s，,;；]+)", text, re.I)
    username = username_match.group(1) if username_match else os.environ.get("NEO4J_USERNAME", "neo4j")
    password = password_match.group(1) if password_match else os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        raise RuntimeError("缺少 Neo4j 密码，禁止空密码连接")
    return bolt_match.group(0), username, password


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def candidate_score(row: dict[str, Any], disease_code: str, expected_label: str, names: list[str]) -> int:
    name = row.get("name") or ""
    aliases = row.get("aliases_text") or ""
    score = 0
    if expected_label in (row.get("labels") or []):
        score += 100
    if row.get("disease_code") == disease_code:
        score += 50
    elif row.get("disease_code") in ("", None):
        score += 20
    for target in names:
        if name == target:
            score += 40
        elif target in name or name in target:
            score += 20
        if target and target in aliases:
            score += 15
    return score


def find_action(session, expected_label: str, names: list[str], disease_code: str) -> dict[str, Any] | None:
    label_condition = f"a:{expected_label}"
    rows: list[dict[str, Any]] = []
    for name in names:
        query = f"""
        MATCH (a)
        WHERE {label_condition}
          AND coalesce(a.status,'active') <> 'deprecated'
          AND (
            coalesce(a.name,'') CONTAINS $name
            OR coalesce(a.display_name,'') CONTAINS $name
            OR coalesce(a.preferred_name,'') CONTAINS $name
            OR $name CONTAINS coalesce(a.name,'')
            OR reduce(alias_text = '', alias IN coalesce(a.aliases, []) | alias_text + '|' + alias) CONTAINS $name
          )
        RETURN coalesce(a.code,'') AS code,
               coalesce(a.display_name,a.preferred_name,a.name,'') AS name,
               coalesce(a.disease_code,'') AS disease_code,
               labels(a) AS labels,
               reduce(alias_text = '', alias IN coalesce(a.aliases, []) | alias_text + '|' + alias) AS aliases_text
        LIMIT 50
        """
        rows.extend(dict(r) for r in session.run(query, {"name": name}))
    if not rows:
        return None
    # 去重后按分数排序。
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        dedup[row["code"]] = row
    ranked = sorted(dedup.values(), key=lambda r: candidate_score(r, disease_code, expected_label, names), reverse=True)
    return ranked[0] if ranked else None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bolt, username, password = read_connection()
    driver = GraphDatabase.driver(bolt, auth=(username, password))
    rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    created_or_matched = 0
    try:
        driver.verify_connectivity()
        with driver.session(database="neo4j") as session:
            for item in REPAIRS:
                rec_code = item["recommendation_code"]
                disease_code = item["disease_code"]
                rec_exists = session.run(
                    "MATCH (rs:RecommendationStatement {code:$code}) WHERE coalesce(rs.status,'active') <> 'deprecated' RETURN count(rs) AS c",
                    {"code": rec_code},
                ).single()["c"]
                if not rec_exists:
                    blocked.append({"recommendation_code": rec_code, "target": "", "reason": "推荐陈述不存在或已废弃"})
                    continue
                for target in item["action_targets"]:
                    action = find_action(session, target["label"], target["names"], disease_code)
                    if not action:
                        blocked.append(
                            {
                                "recommendation_code": rec_code,
                                "target": " / ".join(target["names"]),
                                "reason": f"未找到既有{target['label']}动作节点",
                            }
                        )
                        continue
                    result = session.run(
                        """
                        MATCH (rs:RecommendationStatement {code:$rec_code})
                        MATCH (a {code:$action_code})
                        MERGE (rs)-[r:recommends_action]->(a)
                        ON CREATE SET r.created_at=$now,
                                      r.batch_id=$batch_id,
                                      r.source='冠心病指南PDF精修层总收口',
                                      r.relation_status='active'
                        ON MATCH SET r.last_verified_at=$now,
                                     r.last_verified_batch_id=$batch_id
                        RETURN type(r) AS relation_type,
                               coalesce(rs.code,'') AS recommendation_code,
                               coalesce(rs.display_name,rs.name,rs.title,'') AS recommendation_name,
                               coalesce(a.code,'') AS action_code,
                               coalesce(a.display_name,a.preferred_name,a.name,'') AS action_name,
                               labels(a) AS action_labels
                        """,
                        {"rec_code": rec_code, "action_code": action["code"], "now": NOW, "batch_id": BATCH_ID},
                    ).single()
                    if result:
                        created_or_matched += 1
                        rows.append(dict(result))
    finally:
        driver.close()

    summary = {
        "generated_at": NOW,
        "batch_id": BATCH_ID,
        "neo4j_written": True,
        "planned_recommendations": len(REPAIRS),
        "planned_action_links": sum(len(x["action_targets"]) for x in REPAIRS),
        "created_or_matched_recommends_action_relations": created_or_matched,
        "blocked_count": len(blocked),
        "blocked": blocked,
    }
    write_csv(
        OUT_DIR / "06_冠心病推荐动作补齐明细_20260717.csv",
        rows,
        ["relation_type", "recommendation_code", "recommendation_name", "action_code", "action_name", "action_labels"],
    )
    write_csv(
        OUT_DIR / "07_冠心病推荐动作补齐阻断清单_20260717.csv",
        blocked,
        ["recommendation_code", "target", "reason"],
    )
    (OUT_DIR / "08_冠心病推荐动作缺口补齐_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
