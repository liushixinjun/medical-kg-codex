from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
LINK_FILE = ROOT / "图谱数据库链接.txt"
OUT_DIR = ROOT / "项目管理中心_project_management" / "20260727_检查检验路径收口"
REPORT_JSON = OUT_DIR / "检查检验路径收口_审计与修复结果.json"
REPORT_MD = OUT_DIR / "检查检验路径收口_审计与修复结果.md"


def read_conn() -> tuple[str, str, str]:
    text = LINK_FILE.read_text(encoding="utf-8", errors="ignore")
    bolt = re.search(r"bolt://[^\s;，,]+", text)
    user = re.search(r"用户名[:：]\s*([^\s]+)", text)
    pwd = re.search(r"密码[:：]\s*([^\s]+)", text)
    if not (bolt and user and pwd):
        raise RuntimeError(f"无法从 {LINK_FILE} 解析 Bolt/用户名/密码")
    return bolt.group(0), user.group(1), pwd.group(1)


def run_list(sess, query: str, **params):
    return [dict(r) for r in sess.run(query, **params)]


def main() -> None:
    parser = argparse.ArgumentParser(description="全库检查/检验路径收口：疾病->辅助检查方案->项目->发现/细项")
    parser.add_argument("--apply", action="store_true", help="实际写入低风险修复关系")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    batch = "20260727-检查检验路径收口"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    bolt, user, pwd = read_conn()
    driver = GraphDatabase.driver(bolt, auth=(user, pwd))

    with driver.session() as sess:
        before = {
            "disease_count": run_list(sess, "MATCH (d:Disease) RETURN count(d) AS cnt")[0]["cnt"],
            "exam_observation_count": run_list(sess, "MATCH (n:ExamObservation) RETURN count(n) AS cnt")[0]["cnt"],
            "lab_subitem_count": run_list(sess, "MATCH (n:LabSubitem) RETURN count(n) AS cnt")[0]["cnt"],
            "exam_item_has_observation": run_list(
                sess, "MATCH (:ExamItem)-[r:exam_item_has_observation]->(:ExamObservation) RETURN count(r) AS cnt"
            )[0]["cnt"],
            "lab_item_has_subitem": run_list(
                sess, "MATCH (:LabItem)-[r:lab_item_has_subitem]->(:LabSubitem) RETURN count(r) AS cnt"
            )[0]["cnt"],
            "plan_direct_to_labsubitem": run_list(
                sess,
                "MATCH (:ExamPlan)-[r:includes_lab_item]->(:LabSubitem) RETURN count(r) AS cnt",
            )[0]["cnt"],
            "plan_direct_to_examobservation": run_list(
                sess,
                "MATCH (:ExamPlan)-[r]->(:ExamObservation) RETURN count(r) AS cnt",
            )[0]["cnt"],
        }

        # 低风险修复 1：辅助检查方案直接连到检验细项时，如果该细项已有标准父级检验项目，则补方案->检验项目。
        lab_candidates = run_list(
            sess,
            """
            MATCH (p:ExamPlan)-[:includes_lab_item]->(s:LabSubitem)
            MATCH (li:LabItem)-[:lab_item_has_subitem]->(s)
            WHERE NOT (p)-[:includes_lab_item]->(li)
            RETURN DISTINCT p.code AS plan_code, coalesce(p.name,p.display_name,p.preferred_name,p.code) AS plan_name,
                            li.code AS item_code, coalesce(li.name,li.display_name,li.preferred_name,li.code) AS item_name,
                            count(DISTINCT s) AS subitem_count,
                            collect(DISTINCT coalesce(s.name,s.display_name,s.preferred_name,s.code))[0..10] AS subitems
            ORDER BY plan_name, item_name
            """,
        )

        # 低风险修复 2：辅助检查方案直接连到检查发现时，如果该发现已有标准父级检查项目，则补方案->检查项目。
        exam_candidates = run_list(
            sess,
            """
            MATCH (p:ExamPlan)-[oldrel]->(o:ExamObservation)
            MATCH (ei:ExamItem)-[:exam_item_has_observation]->(o)
            WHERE NOT (p)-[:includes_exam_item]->(ei)
            RETURN DISTINCT p.code AS plan_code, coalesce(p.name,p.display_name,p.preferred_name,p.code) AS plan_name,
                            type(oldrel) AS old_rel,
                            ei.code AS item_code, coalesce(ei.name,ei.display_name,ei.preferred_name,ei.code) AS item_name,
                            count(DISTINCT o) AS observation_count,
                            collect(DISTINCT coalesce(o.name,o.display_name,o.preferred_name,o.code))[0..10] AS observations
            ORDER BY plan_name, item_name
            """,
        )

        repaired = {"plan_to_labitem": 0, "plan_to_examitem": 0}
        if args.apply:
            repaired["plan_to_labitem"] = run_list(
                sess,
                """
                MATCH (p:ExamPlan)-[:includes_lab_item]->(s:LabSubitem)
                MATCH (li:LabItem)-[:lab_item_has_subitem]->(s)
                WHERE NOT (p)-[:includes_lab_item]->(li)
                WITH DISTINCT p, li
                MERGE (p)-[r:includes_lab_item]->(li)
                ON CREATE SET r.created_at=$now,
                              r.repair_batch=$batch,
                              r.repair_reason='由辅助检查方案直接连接检验细项，按既有 LabItem->LabSubitem 归属补齐方案到检验项目标准路径',
                              r.status='active'
                RETURN count(r) AS cnt
                """,
                now=now,
                batch=batch,
            )[0]["cnt"]
            repaired["plan_to_examitem"] = run_list(
                sess,
                """
                MATCH (p:ExamPlan)-[oldrel]->(o:ExamObservation)
                MATCH (ei:ExamItem)-[:exam_item_has_observation]->(o)
                WHERE NOT (p)-[:includes_exam_item]->(ei)
                WITH DISTINCT p, ei
                MERGE (p)-[r:includes_exam_item]->(ei)
                ON CREATE SET r.created_at=$now,
                              r.repair_batch=$batch,
                              r.repair_reason='由辅助检查方案直接连接检查发现，按既有 ExamItem->ExamObservation 归属补齐方案到检查项目标准路径',
                              r.status='active'
                RETURN count(r) AS cnt
                """,
                now=now,
                batch=batch,
            )[0]["cnt"]

        after = {
            "plan_direct_to_labsubitem": run_list(
                sess,
                "MATCH (:ExamPlan)-[r:includes_lab_item]->(:LabSubitem) RETURN count(r) AS cnt",
            )[0]["cnt"],
            "plan_to_labitem": run_list(
                sess,
                "MATCH (:ExamPlan)-[r:includes_lab_item]->(:LabItem) RETURN count(r) AS cnt",
            )[0]["cnt"],
            "plan_direct_to_examobservation": run_list(
                sess,
                "MATCH (:ExamPlan)-[r]->(:ExamObservation) RETURN count(r) AS cnt",
            )[0]["cnt"],
            "plan_to_examitem": run_list(
                sess,
                "MATCH (:ExamPlan)-[r:includes_exam_item]->(:ExamItem) RETURN count(r) AS cnt",
            )[0]["cnt"],
        }

        # 全库疾病路径覆盖，不再只看 AMI。
        disease_path = run_list(
            sess,
            """
            MATCH (d:Disease)
            OPTIONAL MATCH (d)-[:has_exam_plan]->(p:ExamPlan)
            OPTIONAL MATCH (p)-[:includes_exam_item]->(ei:ExamItem)
            OPTIONAL MATCH (ei)-[:exam_item_has_observation]->(eo:ExamObservation)
            OPTIONAL MATCH (p)-[:includes_lab_item]->(li:LabItem)
            OPTIONAL MATCH (li)-[:lab_item_has_subitem]->(ls:LabSubitem)
            RETURN d.code AS disease_code,
                   coalesce(d.name,d.display_name,d.preferred_name,d.code) AS disease_name,
                   d.diagnostic_role AS diagnostic_role,
                   count(DISTINCT p) AS exam_plan_count,
                   count(DISTINCT ei) AS exam_item_count,
                   count(DISTINCT eo) AS exam_observation_count,
                   count(DISTINCT li) AS lab_item_count,
                   count(DISTINCT ls) AS lab_subitem_count
            ORDER BY disease_name
            """,
        )

    driver.close()

    result = {
        "run_time": now,
        "apply": args.apply,
        "batch": batch,
        "before": before,
        "candidate_count": {
            "plan_to_labitem": len(lab_candidates),
            "plan_to_examitem": len(exam_candidates),
        },
        "repaired": repaired,
        "after": after,
        "lab_candidates_sample": lab_candidates[:50],
        "exam_candidates_sample": exam_candidates[:50],
        "disease_path": disease_path,
        "key_diseases": [
            r
            for r in disease_path
            if r.get("disease_code")
            in {"DIS-CARD-CAD-AMI", "DIS-CARD-CAD-STEMI", "DIS-CARD-CAD-NSTEMI"}
        ],
    }

    REPORT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    blocking = [
        r
        for r in disease_path
        if r.get("exam_plan_count", 0) > 0
        and (r.get("exam_item_count", 0) == 0 or r.get("lab_item_count", 0) == 0)
    ]
    md = [
        f"# 检查检验路径收口审计与修复结果",
        "",
        f"- 执行时间：{now}",
        f"- 是否写库：{'是' if args.apply else '否，仅审计'}",
        f"- 批次：{batch}",
        "",
        "## 1. 修复范围",
        "",
        "全库 `Disease`，重点检查两条标准路径：",
        "",
        "1. 疾病 → 辅助检查方案 → 检查项目 → 检查发现",
        "2. 疾病 → 辅助检查方案 → 检验项目 → 检验细项",
        "",
        "## 2. 自动修复原则",
        "",
        "- 不新增临床结论。",
        "- 只在已有 `LabItem -> LabSubitem` 或 `ExamItem -> ExamObservation` 标准归属关系时，补齐 `ExamPlan -> LabItem/ExamItem`。",
        "- 不物理删除旧关系，旧关系后续进入冗余清理闭环。",
        "",
        "## 3. 结果摘要",
        "",
        f"- 候选补齐方案→检验项目：{len(lab_candidates)}",
        f"- 候选补齐方案→检查项目：{len(exam_candidates)}",
        f"- 实际新增方案→检验项目：{repaired['plan_to_labitem']}",
        f"- 实际新增方案→检查项目：{repaired['plan_to_examitem']}",
        f"- 有辅助检查方案但缺检查/检验项目的疾病数：{len(blocking)}",
        "",
        "## 4. 关键疾病复测",
        "",
        "| 疾病 | 角色 | 辅助检查方案 | 检查项目 | 检查发现 | 检验项目 | 检验细项 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in result["key_diseases"]:
        md.append(
            f"| {r['disease_name']} | {r.get('diagnostic_role') or ''} | {r['exam_plan_count']} | {r['exam_item_count']} | {r['exam_observation_count']} | {r['lab_item_count']} | {r['lab_subitem_count']} |"
        )
    md.extend(
        [
            "",
            "## 5. 后续说明",
            "",
            "若页面仍显示 0，优先检查前端接口是否仍使用旧关系：`requires_exam`、`requires_lab_test`、`exam_has_indicator`、`lab_test_has_indicator`。",
        ]
    )
    REPORT_MD.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({
        "apply": args.apply,
        "report": str(REPORT_MD),
        "repaired": repaired,
        "candidate_count": result["candidate_count"],
        "key_diseases": result["key_diseases"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
