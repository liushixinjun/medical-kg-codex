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
OUT_DIR = ROOT / "项目管理中心_project_management" / "129_已解析PDF疾病精修收口总检_20260717"
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
PRIORITY_CSV = ROOT / "项目管理中心_project_management" / "126_指南PDF精修层全库总检_20260717" / "03_指南精修优先级总表_20260717.csv"
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


def classify_disease(code: str, name: str) -> str:
    text = f"{code} {name}"
    if code.startswith("DIS-CARD-CAD"):
        return "冠心病"
    if "肺动脉高压" in text or "肺高压" in text or "PAH" in code or "CTEPH" in code:
        return "肺动脉高压"
    if "瓣" in name or code.startswith("DIS-CARD-VHD"):
        return "瓣膜病"
    if "高血压" in name or code.startswith("DIS-CARD-HT"):
        return "高血压"
    if "起搏" in text or "PACING" in code:
        return "起搏治疗相关疾病"
    if "心力衰竭" in text or "心衰" in text or code.startswith("DIS-CARD-HF"):
        return "心力衰竭"
    if any(k in text for k in ["心律失常", "心房颤动", "房颤", "房扑", "心动过速", "传导阻滞", "室性", "室上"]) or code.startswith("DIS-CARD-ARR"):
        return "心律失常"
    if any(k in text for k in ["心肌炎", "心包炎", "心内膜炎"]):
        return "心肌炎/心包炎/感染性心内膜炎"
    if any(k in text for k in ["主动脉", "外周动脉", "夹层", "动脉瘤"]) or code.startswith("DIS-CARD-AORTA"):
        return "主动脉与外周动脉疾病"
    if any(k in text for k in ["先天性", "房间隔", "室间隔", "卵圆孔", "动脉导管", "结构性"]):
        return "结构性心脏病/先天性心脏病"
    if any(k in text for k in ["血脂", "胆固醇", "动脉粥样硬化"]):
        return "血脂异常/动脉粥样硬化"
    if "心肌病" in text or code.startswith("DIS-CARD-CM"):
        return "心肌病"
    return "其他"


def fetch_disease_category_map(session) -> dict[str, list[dict[str, str]]]:
    rows = session.run(
        """
        MATCH (d:Disease)
        WHERE coalesce(d.status,'active') <> 'deprecated'
        RETURN coalesce(d.code,'') AS code,
               coalesce(d.display_name,d.preferred_name,d.name,'') AS name
        ORDER BY code
        """
    )
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        row = dict(r)
        grouped[classify_disease(row["code"], row["name"])].append(row)
    return grouped


def query_category(session, category: str, codes: list[str]) -> dict[str, Any]:
    if not codes:
        return {
            "疾病大类": category,
            "服务器疾病数": 0,
            "推荐陈述数": 0,
            "推荐动作缺口": 0,
            "证据缺口": 0,
            "触发规则缺口": 0,
            "治疗方案动作缺口": 0,
            "诊断标准明细缺口": 0,
            "总阻断缺口": 0,
        }
    params = {"codes": codes}
    rs = session.run(
        """
        MATCH (rs:RecommendationStatement)
        WHERE coalesce(rs.status,'active') <> 'deprecated'
          AND rs.disease_code IN $codes
        OPTIONAL MATCH (rs)-[ra]->(a)
          WHERE toLower(type(ra)) = 'recommends_action'
            AND coalesce(a.status,'active') <> 'deprecated'
        OPTIONAL MATCH (rs)-[se]->(e)
          WHERE toLower(type(se)) IN ['supported_by_evidence','has_evidence','based_on_evidence']
            AND coalesce(e.status,'active') <> 'deprecated'
        OPTIONAL MATCH (rule:ClinicalRule)-[tr]->(rs)
          WHERE toLower(type(tr)) IN ['triggers_recommendation','supports_recommendation','has_recommendation','has_recommendation_statement']
            AND coalesce(rule.status,'active') <> 'deprecated'
        WITH rs, count(DISTINCT a) AS action_count, count(DISTINCT e) AS evidence_count, count(DISTINCT rule) AS rule_count
        RETURN count(rs) AS recommendation_statement_count,
               sum(CASE WHEN action_count = 0 THEN 1 ELSE 0 END) AS missing_action,
               sum(CASE WHEN evidence_count = 0 THEN 1 ELSE 0 END) AS missing_evidence,
               sum(CASE WHEN rule_count = 0 THEN 1 ELSE 0 END) AS missing_rule
        """,
        params,
    ).single()
    tp = session.run(
        """
        MATCH (tp:TreatmentPlan)
        WHERE coalesce(tp.status,'active') <> 'deprecated'
          AND tp.disease_code IN $codes
        OPTIONAL MATCH (tp)-[r]->(m)
          WHERE coalesce(m.status,'active') <> 'deprecated'
            AND (m:Medication OR m:Procedure OR m:RecommendationStatement OR m:ClinicalRule OR m:Exam OR m:LabTest)
        WITH tp, count(DISTINCT m) AS downstream_count
        RETURN sum(CASE WHEN downstream_count = 0 THEN 1 ELSE 0 END) AS gap_count
        """,
        params,
    ).single()
    dx = session.run(
        """
        MATCH (dx:DiagnosisCriteria)
        WHERE coalesce(dx.status,'active') <> 'deprecated'
          AND dx.disease_code IN $codes
        OPTIONAL MATCH (dx)-[r]->(c)
          WHERE coalesce(c.status,'active') <> 'deprecated'
            AND (
              c:DiagnosisCriteriaComponent OR c:ClinicalRule OR c:Exam OR c:LabTest
              OR c:ExamIndicator OR c:ThresholdRule OR c:Symptom OR c:Sign
              OR toLower(type(r)) CONTAINS 'component'
            )
        WITH dx, count(DISTINCT c) AS component_count
        RETURN sum(CASE WHEN component_count = 0 THEN 1 ELSE 0 END) AS gap_count
        """,
        params,
    ).single()
    missing_action = int(rs["missing_action"] or 0)
    missing_evidence = int(rs["missing_evidence"] or 0)
    missing_rule = int(rs["missing_rule"] or 0)
    tp_gap = int(tp["gap_count"] or 0)
    dx_gap = int(dx["gap_count"] or 0)
    total = missing_action + missing_evidence + missing_rule + tp_gap + dx_gap
    return {
        "疾病大类": category,
        "服务器疾病数": len(codes),
        "推荐陈述数": int(rs["recommendation_statement_count"] or 0),
        "推荐动作缺口": missing_action,
        "证据缺口": missing_evidence,
        "触发规则缺口": missing_rule,
        "治疗方案动作缺口": tp_gap,
        "诊断标准明细缺口": dx_gap,
        "总阻断缺口": total,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    priority_rows = read_csv(PRIORITY_CSV)
    parsed_categories = {
        r["疾病大类"]: r
        for r in priority_rows
        if int(r.get("已解析登记PDF数") or 0) > 0 and r["疾病大类"] != "待人工归类"
    }
    bolt, username, password = read_connection()
    driver = GraphDatabase.driver(bolt, auth=(username, password))
    try:
        driver.verify_connectivity()
        with driver.session(database="neo4j") as session:
            grouped = fetch_disease_category_map(session)
            rows = []
            disease_rows = []
            for category, pdf_info in sorted(parsed_categories.items()):
                codes = [x["code"] for x in grouped.get(category, [])]
                result = query_category(session, category, codes)
                result.update(
                    {
                        "PDF总数": int(pdf_info.get("PDF总数") or 0),
                        "已解析登记PDF数": int(pdf_info.get("已解析登记PDF数") or 0),
                        "未解析PDF数": int(pdf_info.get("未解析PDF数") or 0),
                        "建议动作": pdf_info.get("建议动作", ""),
                    }
                )
                rows.append(result)
                for item in grouped.get(category, []):
                    disease_rows.append({"疾病大类": category, **item})
    finally:
        driver.close()

    rows.sort(key=lambda r: (-int(r["总阻断缺口"]), r["疾病大类"]))
    write_csv(OUT_DIR / "01_已解析PDF疾病精修缺口总表_20260717.csv", rows)
    write_csv(OUT_DIR / "02_服务器疾病归类清单_20260717.csv", disease_rows)
    summary = {
        "generated_at": NOW,
        "neo4j_written": False,
        "checked_category_count": len(rows),
        "category_with_blocking_gap_count": sum(1 for r in rows if int(r["总阻断缺口"]) > 0),
        "total_blocking_gap_count": sum(int(r["总阻断缺口"]) for r in rows),
        "rows": rows,
    }
    (OUT_DIR / "03_已解析PDF疾病精修收口总检_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# 已解析 PDF 疾病精修收口总检报告（2026-07-17）",
        "",
        f"- 生成时间：{NOW}",
        "- 本次写 Neo4j：否，只读总检。",
        "- 检查口径：推荐陈述必须有触发规则、正式推荐动作和证据；治疗方案必须有下游动作；诊断标准必须有明细组件。",
        "",
        "## 1. 总览",
        "",
        f"- 检查疾病大类数：{summary['checked_category_count']}",
        f"- 存在阻断缺口的大类数：{summary['category_with_blocking_gap_count']}",
        f"- 阻断缺口总数：{summary['total_blocking_gap_count']}",
        "",
        "## 2. 各疾病大类结果",
        "",
        "| 疾病大类 | PDF总数 | 已解析PDF | 未解析PDF | 服务器疾病数 | 推荐陈述 | 推荐动作缺口 | 证据缺口 | 触发规则缺口 | 治疗方案动作缺口 | 诊断标准明细缺口 | 总阻断缺口 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['疾病大类']} | {r['PDF总数']} | {r['已解析登记PDF数']} | {r['未解析PDF数']} | {r['服务器疾病数']} | {r['推荐陈述数']} | {r['推荐动作缺口']} | {r['证据缺口']} | {r['触发规则缺口']} | {r['治疗方案动作缺口']} | {r['诊断标准明细缺口']} | {r['总阻断缺口']} |"
        )
    lines += [
        "",
        "## 3. 输出文件",
        "",
        "- `01_已解析PDF疾病精修缺口总表_20260717.csv`",
        "- `02_服务器疾病归类清单_20260717.csv`",
        "- `03_已解析PDF疾病精修收口总检_summary.json`",
    ]
    (OUT_DIR / "00_已解析PDF疾病精修收口总检报告_20260717.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
