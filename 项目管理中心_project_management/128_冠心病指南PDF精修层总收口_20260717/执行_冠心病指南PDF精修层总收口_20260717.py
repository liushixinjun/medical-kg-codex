from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "128_冠心病指南PDF精修层总收口_20260717"
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
LEDGER_CSV = ROOT / "项目管理中心_project_management" / "04_批次登记台账_batch_ledger.csv"
PDF_STATUS_CSV = ROOT / "项目管理中心_project_management" / "126_指南PDF精修层全库总检_20260717" / "01_PDF使用状态总表_20260717.csv"

CAD_PREFIX = "DIS-CARD-CAD"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_query(session, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [dict(r) for r in session.run(cypher, params or {})]


def read_pdf_and_batch_context() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pdf_rows = [r for r in read_csv(PDF_STATUS_CSV) if r.get("建议疾病大类") == "冠心病"]
    ledger_rows = [r for r in read_csv(LEDGER_CSV) if r.get("疾病大类") == "冠心病" or "CAD" in (r.get("batch_id") or "")]
    return pdf_rows, ledger_rows


def query_server(driver) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    with driver.session(database="neo4j") as session:
        disease_rows = run_query(
            session,
            """
            MATCH (d)
            WHERE d:Disease
              AND coalesce(d.status,'active') <> 'deprecated'
              AND coalesce(d.code,'') STARTS WITH $prefix
            RETURN coalesce(d.code,'') AS code,
                   coalesce(d.display_name,d.preferred_name,d.name,'') AS name,
                   '' AS disease_subcategory,
                   coalesce(d.formal_cdss_ready,'') AS cdss_ready,
                   coalesce(d.clinical_review_status,'') AS clinical_review_status
            ORDER BY code
            """,
            {"prefix": CAD_PREFIX},
        )
        label_rows = run_query(
            session,
            """
            MATCH (n)
            WHERE coalesce(n.status,'active') <> 'deprecated'
              AND coalesce(n.disease_code,'') STARTS WITH $prefix
            WITH head([x IN labels(n) WHERE x <> 'KGNode']) AS entity_type, count(n) AS count
            RETURN entity_type, count
            ORDER BY count DESC, entity_type
            """,
            {"prefix": CAD_PREFIX},
        )
        relation_rows = run_query(
            session,
            """
            MATCH (n)-[r]->(m)
            WHERE coalesce(n.status,'active') <> 'deprecated'
              AND coalesce(n.disease_code,'') STARTS WITH $prefix
            WITH type(r) AS relation_type, count(r) AS count
            RETURN relation_type, count
            ORDER BY count DESC, relation_type
            LIMIT 80
            """,
            {"prefix": CAD_PREFIX},
        )
        chain_summary = run_query(
            session,
            """
            MATCH (rs)
            WHERE rs:RecommendationStatement
              AND coalesce(rs.status,'active') <> 'deprecated'
              AND coalesce(rs.disease_code,'') STARTS WITH $prefix
            OPTIONAL MATCH (rs)-[ra]->(a)
              WHERE toLower(type(ra)) IN ['recommends_action','recommends','has_recommended_action']
                AND coalesce(a.status,'active') <> 'deprecated'
            OPTIONAL MATCH (rs)-[se]->(e)
              WHERE toLower(type(se)) IN ['supported_by_evidence','has_evidence','based_on_evidence']
                AND coalesce(e.status,'active') <> 'deprecated'
            OPTIONAL MATCH (rule:ClinicalRule)-[tr]->(rs)
              WHERE toLower(type(tr)) IN ['triggers_recommendation','supports_recommendation','has_recommendation','has_recommendation_statement']
                AND coalesce(rule.status,'active') <> 'deprecated'
            RETURN count(DISTINCT rs) AS recommendation_statement_count,
                   count(DISTINCT CASE WHEN a IS NOT NULL THEN rs END) AS statement_with_action_count,
                   count(DISTINCT CASE WHEN e IS NOT NULL THEN rs END) AS statement_with_evidence_count,
                   count(DISTINCT CASE WHEN rule IS NOT NULL THEN rs END) AS statement_with_rule_count
            """,
            {"prefix": CAD_PREFIX},
        )[0]
        gaps = run_query(
            session,
            """
            MATCH (rs)
            WHERE rs:RecommendationStatement
              AND coalesce(rs.status,'active') <> 'deprecated'
              AND coalesce(rs.disease_code,'') STARTS WITH $prefix
            OPTIONAL MATCH (rs)-[ra]->(a)
              WHERE toLower(type(ra)) IN ['recommends_action','recommends','has_recommended_action']
                AND coalesce(a.status,'active') <> 'deprecated'
            OPTIONAL MATCH (rs)-[se]->(e)
              WHERE toLower(type(se)) IN ['supported_by_evidence','has_evidence','based_on_evidence']
                AND coalesce(e.status,'active') <> 'deprecated'
            OPTIONAL MATCH (rule:ClinicalRule)-[tr]->(rs)
              WHERE toLower(type(tr)) IN ['triggers_recommendation','supports_recommendation','has_recommendation','has_recommendation_statement']
                AND coalesce(rule.status,'active') <> 'deprecated'
            WITH rs, count(DISTINCT a) AS action_count, count(DISTINCT e) AS evidence_count, count(DISTINCT rule) AS rule_count
            WHERE action_count = 0 OR evidence_count = 0 OR rule_count = 0
            RETURN coalesce(rs.code,'') AS code,
                   coalesce(rs.display_name,rs.name,rs.title,'') AS name,
                   coalesce(rs.disease_code,'') AS disease_code,
                   action_count,
                   evidence_count,
                   rule_count,
                   CASE
                     WHEN action_count = 0 THEN '缺推荐动作'
                     WHEN evidence_count = 0 THEN '缺证据'
                     WHEN rule_count = 0 THEN '缺触发规则'
                     ELSE '待复核'
                   END AS gap_type
            ORDER BY gap_type, disease_code, code
            LIMIT 500
            """,
            {"prefix": CAD_PREFIX},
        )
        treatment_plan_gaps = run_query(
            session,
            """
            MATCH (tp)
            WHERE tp:TreatmentPlan
              AND coalesce(tp.status,'active') <> 'deprecated'
              AND coalesce(tp.disease_code,'') STARTS WITH $prefix
            OPTIONAL MATCH (tp)-[r]->(m)
              WHERE coalesce(m.status,'active') <> 'deprecated'
                AND (
                  m:Medication OR m:Procedure OR m:RecommendationStatement OR m:ClinicalRule
                )
            WITH tp, count(DISTINCT m) AS downstream_action_count
            WHERE downstream_action_count = 0
            RETURN coalesce(tp.code,'') AS code,
                   coalesce(tp.display_name,tp.name,'') AS name,
                   coalesce(tp.disease_code,'') AS disease_code,
                   downstream_action_count,
                   '治疗方案缺下游动作' AS gap_type
            ORDER BY disease_code, name
            LIMIT 500
            """,
            {"prefix": CAD_PREFIX},
        )
        diagnosis_component_gaps = run_query(
            session,
            """
            MATCH (dx)
            WHERE dx:DiagnosisCriteria
              AND coalesce(dx.status,'active') <> 'deprecated'
              AND coalesce(dx.disease_code,'') STARTS WITH $prefix
            OPTIONAL MATCH (dx)-[r]->(c)
              WHERE coalesce(c.status,'active') <> 'deprecated'
                AND (
                  c:DiagnosisCriteriaComponent OR c:ClinicalRule OR c:Exam OR c:LabTest
                  OR c:ExamIndicator OR c:ThresholdRule OR c:Symptom OR c:Sign
                  OR toLower(type(r)) CONTAINS 'component'
                )
            WITH dx, count(DISTINCT c) AS component_count
            WHERE component_count = 0
            RETURN coalesce(dx.code,'') AS code,
                   coalesce(dx.display_name,dx.name,'') AS name,
                   coalesce(dx.disease_code,'') AS disease_code,
                   component_count,
                   '诊断标准缺明细组件' AS gap_type
            ORDER BY disease_code, name
            LIMIT 500
            """,
            {"prefix": CAD_PREFIX},
        )

    summary = {
        "disease_count": len(disease_rows),
        "entity_counts": {r["entity_type"] or "未标类型": r["count"] for r in label_rows},
        "relation_counts_top": relation_rows,
        "recommendation_statement_count": chain_summary["recommendation_statement_count"],
        "statement_with_action_count": chain_summary["statement_with_action_count"],
        "statement_with_evidence_count": chain_summary["statement_with_evidence_count"],
        "statement_with_rule_count": chain_summary["statement_with_rule_count"],
        "statement_gap_count": len(gaps),
        "treatment_plan_downstream_gap_count": len(treatment_plan_gaps),
        "diagnosis_component_gap_count": len(diagnosis_component_gaps),
    }
    return summary, disease_rows, gaps, treatment_plan_gaps, diagnosis_component_gaps


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_rows, ledger_rows = read_pdf_and_batch_context()

    bolt, username, password = read_connection()
    driver = GraphDatabase.driver(bolt, auth=(username, password))
    try:
        driver.verify_connectivity()
        server_summary, disease_rows, statement_gaps, treatment_plan_gaps, diagnosis_component_gaps = query_server(driver)
    finally:
        driver.close()

    pdf_summary = {
        "冠心病PDF总数": len(pdf_rows),
        "冠心病已解析登记PDF数": sum(1 for r in pdf_rows if r.get("是否已解析登记") == "是"),
        "冠心病未解析PDF数": sum(1 for r in pdf_rows if r.get("是否已解析登记") != "是"),
        "冠心病台账批次数": len(ledger_rows),
        "冠心病写库批次数": sum(1 for r in ledger_rows if r.get("是否写Neo4j") == "是"),
    }
    all_gaps = statement_gaps + treatment_plan_gaps + diagnosis_component_gaps
    summary = {
        "generated_at": NOW,
        "neo4j_written": False,
        "server": bolt.replace("bolt://", ""),
        **pdf_summary,
        **server_summary,
        "total_blocking_gap_count": len(all_gaps),
    }

    write_csv(OUT_DIR / "01_冠心病PDF使用清单_20260717.csv", pdf_rows)
    write_csv(OUT_DIR / "02_冠心病相关台账批次_20260717.csv", ledger_rows)
    write_csv(OUT_DIR / "03_冠心病疾病节点清单_20260717.csv", disease_rows)
    write_csv(OUT_DIR / "04_冠心病推荐链路缺口清单_20260717.csv", all_gaps)
    (OUT_DIR / "05_冠心病指南PDF精修层总收口_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# 冠心病指南 PDF 精修层总收口报告（2026-07-17）",
        "",
        f"- 生成时间：{NOW}",
        "- 本次写 Neo4j：否，只读复核服务器图谱与本地 PDF/台账。",
        "- 收口口径：PDF 是否已登记、台账是否存在、服务器是否形成正式 CDSS 可用链路。",
        "",
        "## 1. PDF 与台账",
        "",
        f"- 冠心病 PDF 总数：{pdf_summary['冠心病PDF总数']}",
        f"- 已解析登记 PDF：{pdf_summary['冠心病已解析登记PDF数']}",
        f"- 未解析 PDF：{pdf_summary['冠心病未解析PDF数']}",
        f"- 冠心病相关台账批次：{pdf_summary['冠心病台账批次数']}",
        f"- 已写 Neo4j 批次：{pdf_summary['冠心病写库批次数']}",
        "",
        "## 2. 服务器图谱结构",
        "",
        f"- 冠心病疾病节点数：{server_summary['disease_count']}",
        f"- 推荐陈述数：{server_summary['recommendation_statement_count']}",
        f"- 已连接具体推荐动作的推荐陈述：{server_summary['statement_with_action_count']}",
        f"- 已连接证据的推荐陈述：{server_summary['statement_with_evidence_count']}",
        f"- 已连接触发规则的推荐陈述：{server_summary['statement_with_rule_count']}",
        f"- 推荐链路缺口：{server_summary['statement_gap_count']}",
        f"- 治疗方案缺下游动作：{server_summary['treatment_plan_downstream_gap_count']}",
        f"- 诊断标准缺明细组件：{server_summary['diagnosis_component_gap_count']}",
        "",
        "## 3. 实体类型数量",
        "",
        "| 实体类型 | 数量 |",
        "|---|---:|",
    ]
    for entity_type, count in sorted(server_summary["entity_counts"].items(), key=lambda x: (-int(x[1]), x[0])):
        lines.append(f"| {entity_type} | {count} |")
    lines += [
        "",
        "## 4. 结论",
        "",
    ]
    if summary["total_blocking_gap_count"] == 0 and pdf_summary["冠心病未解析PDF数"] == 0:
        lines.append("- 冠心病 PDF 精修层当前满足总收口口径：PDF 已登记齐、服务器正式 CDSS 链路无阻断缺口。")
    else:
        lines.append("- 冠心病仍存在需处理项，详见 `04_冠心病推荐链路缺口清单_20260717.csv`。")
    lines += [
        "",
        "## 5. 输出文件",
        "",
        "- `01_冠心病PDF使用清单_20260717.csv`",
        "- `02_冠心病相关台账批次_20260717.csv`",
        "- `03_冠心病疾病节点清单_20260717.csv`",
        "- `04_冠心病推荐链路缺口清单_20260717.csv`",
        "- `05_冠心病指南PDF精修层总收口_summary.json`",
    ]
    (OUT_DIR / "00_冠心病指南PDF精修层总收口报告_20260717.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
