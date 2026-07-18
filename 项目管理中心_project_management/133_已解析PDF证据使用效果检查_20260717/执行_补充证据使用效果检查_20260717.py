#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
补充证据入库后的“使用效果”只读检查。

检查目标：
1. 新增 Evidence 是否能被指南追溯。
2. 新增 Evidence 是否能被疾病页面按疾病维度查到。
3. 新增 Evidence 是否能进入 CDSS 推荐链路：疾病 -> 临床规则 -> 推荐动作 -> 证据。
4. 输出给前端/后端可直接参考的查询口径。

本脚本只读 Neo4j，不写库。
"""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any


WORKDIR = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = WORKDIR / "项目管理中心_project_management" / "133_已解析PDF证据使用效果检查_20260717"
DB_LINK_FILE = WORKDIR / "图谱数据库链接.txt"
PACKAGE_ID = "SUPP-EVIDENCE-MERGE-20260717-001"

BATCHES = [
    "20260717_冠心病ACS2025补充解析",
    "20260717_瓣膜病指南补充解析",
    "20260717_心律失常指南补充解析",
    "20260717_心肌病ESC2023补充解析",
    "20260717_结构性先心病介入补充解析",
    "20260717_心衰LVAD右心衰补充解析",
    "20260717_高血压LVAD补充解析",
]

def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_db_link() -> tuple[str, str, str]:
    text = DB_LINK_FILE.read_text(encoding="utf-8")
    bolt_match = re.search(r"bolt://[^\s，,;；]+", text, re.I)
    if not bolt_match:
        raise RuntimeError("图谱数据库链接.txt 未解析到 bolt 地址")
    username_match = re.search(r"(?:用户名|username|NEO4J_USERNAME)\s*[:：=]\s*([^\s，,;；]+)", text, re.I)
    password_match = re.search(r"(?:密码|password|NEO4J_PASSWORD)\s*[:：=]\s*([^\s，,;；]+)", text, re.I)
    username = username_match.group(1) if username_match else os.environ.get("NEO4J_USERNAME", "neo4j")
    password = password_match.group(1) if password_match else os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        raise RuntimeError("未解析到 Neo4j 密码")
    return bolt_match.group(0), username, password


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def pct(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0%"
    return f"{numerator / denominator * 100:.1f}%"


def run_batch_checks(session: Any, batch_id: str) -> dict[str, Any]:
    params = {
        "package_id": PACKAGE_ID,
        "batch_id": batch_id,
    }

    evidence_summary = session.run(
        """
        MATCH (e:KGNode)
        WHERE e.entityType = 'Evidence'
          AND e.last_merge_package_id = $package_id
          AND ($batch_id IN coalesce(e.source_batch_ids, []) OR e.batch_id = $batch_id)
        WITH collect(e) AS evidences
        UNWIND evidences AS e
        OPTIONAL MATCH (:KGNode)-[:guideline_has_evidence]->(e)
        WITH evidences, e, count(*) AS guideline_links
        WITH evidences,
             count(e) AS evidence_count,
             sum(CASE WHEN guideline_links > 0 THEN 1 ELSE 0 END) AS evidence_with_guideline
        UNWIND evidences AS e2
        OPTIONAL MATCH (:KGNode)-[:supported_by_evidence]->(e2)
        WITH evidence_count, evidence_with_guideline, e2, count(*) AS support_links
        RETURN evidence_count,
               evidence_with_guideline,
               sum(CASE WHEN support_links > 0 THEN 1 ELSE 0 END) AS evidence_used_by_clinical_entity
        """,
        **params,
    ).single().data()

    disease_rows_rule = session.run(
        """
        MATCH (e:KGNode)<-[:supported_by_evidence]-(:KGNode)<-[:has_clinical_rule]-(d:KGNode {entityType:'Disease'})
        WHERE e.entityType = 'Evidence'
          AND e.last_merge_package_id = $package_id
          AND ($batch_id IN coalesce(e.source_batch_ids, []) OR e.batch_id = $batch_id)
        RETURN DISTINCT e.code AS evidence_code, d.code AS disease_code
        """,
        **params,
    ).data()

    disease_rows_guideline = session.run(
        """
        MATCH (e:KGNode)<-[:guideline_has_evidence]-(:KGNode)<-[:based_on_guideline]-(d:KGNode {entityType:'Disease'})
        WHERE e.entityType = 'Evidence'
          AND e.last_merge_package_id = $package_id
          AND ($batch_id IN coalesce(e.source_batch_ids, []) OR e.batch_id = $batch_id)
        RETURN DISTINCT e.code AS evidence_code, d.code AS disease_code
        """,
        **params,
    ).data()

    # 不在全库层面扫描“疾病 -> 任意普通实体 -> Evidence”宽路径；
    # 该路径适合单病种详情页按需查询，不适合全量服务器审计。
    all_disease_rows = disease_rows_rule + disease_rows_guideline
    disease_reachable_evidence_codes = {r["evidence_code"] for r in all_disease_rows if r.get("evidence_code")}
    reached_disease_codes = {r["disease_code"] for r in all_disease_rows if r.get("disease_code")}

    cdss_chain = session.run(
        """
        MATCH (rule:KGNode)
        WHERE rule.entityType = 'ClinicalRule'
          AND rule.last_merge_package_id = $package_id
          AND ($batch_id IN coalesce(rule.source_batch_ids, []) OR rule.batch_id = $batch_id)
        OPTIONAL MATCH (rule)-[:has_recommended_action]->(action:KGNode)
        WITH rule, count(DISTINCT action) AS action_count
        OPTIONAL MATCH (rule)-[:supported_by_evidence]->(e:KGNode)
        WITH rule, action_count, count(DISTINCT e) AS evidence_count
        RETURN count(rule) AS clinical_rule_count,
               sum(CASE WHEN action_count > 0 THEN 1 ELSE 0 END) AS rules_with_action,
               sum(CASE WHEN evidence_count > 0 THEN 1 ELSE 0 END) AS rules_with_evidence,
               sum(CASE WHEN action_count > 0 AND evidence_count > 0 THEN 1 ELSE 0 END) AS rules_with_action_and_evidence
        """,
        **params,
    ).single().data()

    action_disease_chain = session.run(
        """
        MATCH (e:KGNode)<-[:supported_by_evidence]-(rule:KGNode)<-[:has_clinical_rule]-(d:KGNode {entityType:'Disease'})
        MATCH (rule)-[:has_recommended_action]->(action:KGNode)
        WHERE e.last_merge_package_id = $package_id
          AND ($batch_id IN coalesce(e.source_batch_ids, []) OR e.batch_id = $batch_id)
        RETURN count(DISTINCT rule) AS disease_rule_action_evidence_chains,
               count(DISTINCT action) AS action_count,
               count(DISTINCT d) AS disease_count
        """,
        **params,
    ).single().data()

    top_diseases = session.run(
        """
        MATCH (e:KGNode)<-[:supported_by_evidence]-(rule:KGNode)<-[:has_clinical_rule]-(d:KGNode {entityType:'Disease'})
        WHERE e.last_merge_package_id = $package_id
          AND ($batch_id IN coalesce(e.source_batch_ids, []) OR e.batch_id = $batch_id)
        RETURN d.code AS disease_code,
               coalesce(d.display_name, d.preferred_name, d.name) AS disease_name,
               count(DISTINCT e) AS evidence_count,
               count(DISTINCT rule) AS rule_count
        ORDER BY evidence_count DESC, rule_count DESC
        LIMIT 12
        """,
        **params,
    ).data()

    total_evidence = int(evidence_summary.get("evidence_count") or 0)
    used_by_entity = int(evidence_summary.get("evidence_used_by_clinical_entity") or 0)
    with_guideline = int(evidence_summary.get("evidence_with_guideline") or 0)
    disease_reachable = len(disease_reachable_evidence_codes)
    clinical_rules = int(cdss_chain.get("clinical_rule_count") or 0)
    rules_with_both = int(cdss_chain.get("rules_with_action_and_evidence") or 0)

    formal_chain_rate = (rules_with_both / clinical_rules) if clinical_rules else 0
    disease_reachable_rate = (disease_reachable / total_evidence) if total_evidence else 0

    if total_evidence == 0:
        judgement = "无新增证据"
    elif disease_reachable_rate < 0.8 or used_by_entity < total_evidence or with_guideline < total_evidence:
        judgement = "需修复查询链或数据关系"
    elif formal_chain_rate >= 0.75:
        judgement = "可进入正式CDSS推荐链路"
    elif formal_chain_rate >= 0.4:
        judgement = "部分可进入正式CDSS推荐链路，需补动作链"
    elif rules_with_both > 0:
        judgement = "知识浏览可用，正式CDSS动作链明显不足"
    elif used_by_entity == total_evidence and with_guideline == total_evidence:
        judgement = "可作为知识浏览和证据追溯，CDSS动作链需补强"
    else:
        judgement = "需修复查询链或数据关系"

    return {
        "batch_id": batch_id,
        "evidence_count": total_evidence,
        "evidence_with_guideline": with_guideline,
        "evidence_with_guideline_rate": pct(with_guideline, total_evidence),
        "evidence_used_by_clinical_entity": used_by_entity,
        "evidence_used_by_clinical_entity_rate": pct(used_by_entity, total_evidence),
        "disease_reachable_evidence": disease_reachable,
        "disease_reachable_evidence_rate": pct(disease_reachable, total_evidence),
        "reached_disease_count": len(reached_disease_codes),
        "clinical_rule_count": clinical_rules,
        "rules_with_action": int(cdss_chain.get("rules_with_action") or 0),
        "rules_with_evidence": int(cdss_chain.get("rules_with_evidence") or 0),
        "rules_with_action_and_evidence": rules_with_both,
        "formal_cdss_chain_rate": pct(rules_with_both, clinical_rules),
        "disease_rule_action_evidence_chains": int(action_disease_chain.get("disease_rule_action_evidence_chains") or 0),
        "action_count": int(action_disease_chain.get("action_count") or 0),
        "action_disease_count": int(action_disease_chain.get("disease_count") or 0),
        "judgement": judgement,
        "top_diseases": top_diseases,
    }


def write_markdown(rows: list[dict[str, Any]], global_summary: dict[str, Any]) -> None:
    lines = [
        "# 已解析 PDF 补充证据使用效果检查报告",
        "",
        f"- 生成时间：{now_text()}",
        f"- 检查范围：7 个补充证据批次",
        f"- 合并包编号：`{PACKAGE_ID}`",
        f"- 本轮是否写库：否，只读服务器复核",
        "",
        "## 总体结论",
        "",
        f"- 新增 Evidence：{global_summary['evidence_count']} 条",
        f"- 已挂指南追溯：{global_summary['evidence_with_guideline']} 条（{pct(global_summary['evidence_with_guideline'], global_summary['evidence_count'])}）",
        f"- 已被临床实体使用：{global_summary['evidence_used_by_clinical_entity']} 条（{pct(global_summary['evidence_used_by_clinical_entity'], global_summary['evidence_count'])}）",
        f"- 可从疾病页面查到：{global_summary['disease_reachable_evidence']} 条（{pct(global_summary['disease_reachable_evidence'], global_summary['evidence_count'])}）",
        f"- 临床规则数：{global_summary['clinical_rule_count']} 条",
        f"- 同时具备推荐动作和证据的规则：{global_summary['rules_with_action_and_evidence']} 条（{pct(global_summary['rules_with_action_and_evidence'], global_summary['clinical_rule_count'])}）",
        "",
        "解释：医生端/CDSS 不能只展示某疾病下全部 Evidence；正式推荐区应按“疾病 → 临床规则 → 推荐动作 → 证据”查询。",
        "",
        "## 分批次结果",
        "",
        "| 批次 | Evidence | 指南追溯 | 临床实体使用 | 疾病可查 | 规则 | 动作+证据规则 | 判断 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['batch_id']} | {row['evidence_count']} | "
            f"{row['evidence_with_guideline']} ({row['evidence_with_guideline_rate']}) | "
            f"{row['evidence_used_by_clinical_entity']} ({row['evidence_used_by_clinical_entity_rate']}) | "
            f"{row['disease_reachable_evidence']} ({row['disease_reachable_evidence_rate']}) | "
            f"{row['clinical_rule_count']} | {row['rules_with_action_and_evidence']} ({row['formal_cdss_chain_rate']}) | "
            f"{row['judgement']} |"
        )

    lines.extend(
        [
            "",
            "## 前端/CDSS 查询口径",
            "",
            "### 1. 疾病知识页",
            "",
            "用于展示该疾病相关的检查、治疗、风险分层、随访等知识卡片。证据作为卡片详情的依据，不要把全量证据直接铺出来。",
            "",
            "```cypher",
            "MATCH (d:KGNode {code:$disease_code})-[r]->(x:KGNode)",
            "WHERE type(r) IN ['has_treatment_plan','requires_exam','requires_lab_test','has_diagnostic_criteria','has_risk_stratification','has_follow_up']",
            "OPTIONAL MATCH (x)-[:supported_by_evidence]->(e:KGNode {entityType:'Evidence'})",
            "RETURN type(r) AS 维度, x.code AS 实体编码, coalesce(x.display_name,x.name) AS 实体名称, count(DISTINCT e) AS 证据数",
            "ORDER BY 维度, 实体名称",
            "```",
            "",
            "### 2. 正式 CDSS 推荐区",
            "",
            "用于医生真正可执行的推荐，不走疾病直连治疗方案，而走规则和动作链。",
            "",
            "```cypher",
            "MATCH (d:KGNode {code:$disease_code})-[:has_clinical_rule]->(rule:KGNode)-[:has_recommended_action]->(action:KGNode)",
            "MATCH (rule)-[:supported_by_evidence]->(e:KGNode {entityType:'Evidence'})",
            "RETURN coalesce(rule.display_name,rule.name) AS 规则名称,",
            "       coalesce(action.display_name,action.name) AS 推荐动作,",
            "       e.source_name AS 指南名称, e.source_page AS 页码,",
            "       e.recommendation_class AS 推荐等级, e.evidence_level AS 证据等级,",
            "       left(e.evidence_text, 300) AS 原文摘要",
            "ORDER BY 推荐动作",
            "```",
            "",
            "### 3. 指南证据追溯页",
            "",
            "用于查某指南被拆成哪些证据，不应用作正式推荐列表。",
            "",
            "```cypher",
            "MATCH (g:KGNode {entityType:'Guideline'})-[:guideline_has_evidence]->(e:KGNode {entityType:'Evidence'})",
            "WHERE g.code=$guideline_code",
            "RETURN coalesce(g.display_name,g.name) AS 指南名称, e.source_page AS 页码, left(e.evidence_text, 300) AS 原文摘要",
            "ORDER BY e.source_page",
            "```",
            "",
            "## 需关注点",
            "",
            "1. 如果某批次“指南追溯”和“临床实体使用”都是 100%，但“动作+证据规则”不足，说明这批更适合知识浏览或证据补强，不应直接进入正式推荐区。",
            "2. 前端疾病详情页应展示实体卡片与每个卡片的证据数；医生点击某个治疗/检查/规则时，再展开该条证据。",
            "3. 正式推荐区必须有推荐动作和证据，不允许只因为疾病下有 Evidence 就显示推荐。",
        ]
    )
    (OUT_DIR / "已解析PDF补充证据使用效果检查报告_20260717.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bolt, username, password = parse_db_link()
    from neo4j import GraphDatabase

    rows: list[dict[str, Any]] = []
    with GraphDatabase.driver(bolt, auth=(username, password)) as driver:
        with driver.session(database="neo4j") as session:
            for batch in BATCHES:
                rows.append(run_batch_checks(session, batch))

    global_summary = {
        "evidence_count": sum(r["evidence_count"] for r in rows),
        "evidence_with_guideline": sum(r["evidence_with_guideline"] for r in rows),
        "evidence_used_by_clinical_entity": sum(r["evidence_used_by_clinical_entity"] for r in rows),
        "disease_reachable_evidence": sum(r["disease_reachable_evidence"] for r in rows),
        "clinical_rule_count": sum(r["clinical_rule_count"] for r in rows),
        "rules_with_action_and_evidence": sum(r["rules_with_action_and_evidence"] for r in rows),
    }
    output = {
        "generated_at": now_text(),
        "neo4j_written": False,
        "package_id": PACKAGE_ID,
        "global_summary": global_summary,
        "batches": rows,
    }
    (OUT_DIR / "证据使用效果检查结果_20260717.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(
        OUT_DIR / "证据使用效果检查结果_20260717.csv",
        rows,
        [
            "batch_id",
            "evidence_count",
            "evidence_with_guideline",
            "evidence_with_guideline_rate",
            "evidence_used_by_clinical_entity",
            "evidence_used_by_clinical_entity_rate",
            "disease_reachable_evidence",
            "disease_reachable_evidence_rate",
            "reached_disease_count",
            "clinical_rule_count",
            "rules_with_action",
            "rules_with_evidence",
            "rules_with_action_and_evidence",
            "formal_cdss_chain_rate",
            "disease_rule_action_evidence_chains",
            "action_count",
            "action_disease_count",
            "judgement",
        ],
    )
    top_rows: list[dict[str, Any]] = []
    for row in rows:
        for item in row["top_diseases"]:
            top_rows.append({"batch_id": row["batch_id"], **item})
    write_csv(
        OUT_DIR / "疾病可达证据Top清单_20260717.csv",
        top_rows,
        ["batch_id", "disease_code", "disease_name", "evidence_count", "rule_count"],
    )
    write_markdown(rows, global_summary)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
