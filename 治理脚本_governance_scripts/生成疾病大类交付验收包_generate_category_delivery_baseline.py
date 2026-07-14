from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient  # noqa: E402


DIMENSION_ENTITY_TYPES = [
    "Definition",
    "Etiology",
    "Pathophysiology",
    "Epidemiology",
    "Symptom",
    "Sign",
    "Exam",
    "ExamIndicator",
    "LabTest",
    "LabTestIndicator",
    "DiagnosisCriteria",
    "DiagnosisCriteriaComponent",
    "DifferentialDiagnosis",
    "RiskStratification",
    "TreatmentPlan",
    "Medication",
    "Procedure",
    "Contraindication",
    "ClinicalRule",
    "RecommendationStatement",
    "FollowUp",
    "Prognosis",
    "Prevention",
    "Complication",
    "Guideline",
    "Evidence",
]


SCENARIOS = [
    ("疑似疾病识别", ["Symptom", "Sign"]),
    ("诊断建议", ["DiagnosisCriteria", "DiagnosisCriteriaComponent", "ClinicalRule"]),
    ("鉴别诊断", ["DifferentialDiagnosis"]),
    ("推荐检查", ["Exam", "ExamIndicator"]),
    ("推荐检验", ["LabTest", "LabTestIndicator"]),
    ("风险分层", ["RiskStratification"]),
    ("治疗方案", ["TreatmentPlan", "RecommendationStatement"]),
    ("药物推荐", ["Medication"]),
    ("手术/操作推荐", ["Procedure"]),
    ("禁忌与风险预警", ["Contraindication", "ClinicalRule"]),
    ("随访", ["FollowUp"]),
    ("预后/预防", ["Prognosis", "Prevention"]),
    ("并发症管理", ["Complication"]),
]


CAD_KEY_NAMES = [
    "冠状动脉粥样硬化性心脏病",
    "冠心病",
    "急性冠脉综合征",
    "急性冠状动脉综合征",
    "不稳定型心绞痛",
    "急性心肌梗死",
    "ST段抬高型心肌梗死",
    "非ST段抬高型心肌梗死",
    "慢性冠脉疾病",
    "慢性冠脉综合征",
    "稳定型心绞痛",
    "缺血性心肌病",
    "隐匿性冠心病",
    "无症状心肌缺血",
    "陈旧性心肌梗死",
    "冠状动脉痉挛",
    "冠状动脉粥样硬化",
    "动脉粥样硬化",
]


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    http = re.search(r"https?://[^\s；;，,]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s；;，,]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s；;，,]+)", text, re.I)
    if not http:
        raise RuntimeError(f"连接文件缺少 HTTP 地址：{path}")
    if not password:
        raise RuntimeError(f"连接文件缺少密码字段：{path}")
    return {
        "uri": http.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def result_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    columns = result["results"][0]["columns"]
    return [
        {column: item["row"][index] for index, column in enumerate(columns)}
        for item in result["results"][0]["data"]
    ]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row.keys()}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def query(client: Neo4jHttpClient, statement: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return result_rows(client.run(statement, params or {}))


def cad_scope_where(alias: str = "d") -> str:
    return f"""
    (
      {alias}.code STARTS WITH 'DIS-CARD-CAD'
      OR coalesce({alias}.disease_category,'') CONTAINS '冠心'
      OR coalesce({alias}.disease_category,'') CONTAINS '冠状动脉粥样硬化'
      OR any(name IN $key_names WHERE coalesce({alias}.name,'') CONTAINS name)
    )
    """


def fetch_diseases(client: Neo4jHttpClient) -> list[dict[str, Any]]:
    return query(
        client,
        f"""
        MATCH (d:KGNode)
        WHERE d.entityType = 'Disease'
          AND {cad_scope_where("d")}
        OPTIONAL MATCH (d)-[r]-(n:KGNode)
        WITH d,
             count(DISTINCT n) AS related_entity_count,
             count(DISTINCT r) AS relation_count,
             count(DISTINCT CASE WHEN n.entityType = 'Evidence' THEN n END) AS evidence_count,
             count(DISTINCT CASE WHEN n.entityType = 'Guideline' THEN n END) AS guideline_count,
             count(DISTINCT CASE WHEN n.entityType IN ['ClinicalRule','RecommendationStatement','TreatmentPlan'] THEN n END) AS cdss_decision_node_count,
             sum(CASE WHEN coalesce(r.formal_cdss_ready,false) = true THEN 1 ELSE 0 END) AS formal_ready_relation_count
        RETURN
          d.code AS disease_code,
          d.name AS disease_name,
          coalesce(d.disease_category,'') AS disease_category,
          coalesce(d.disease_subcategory,'') AS disease_subcategory,
          coalesce(d.definition,'') AS definition,
          coalesce(d.formal_cdss_ready,false) AS formal_cdss_ready,
          coalesce(d.clinical_review_status,'') AS clinical_review_status,
          related_entity_count,
          relation_count,
          evidence_count,
          guideline_count,
          cdss_decision_node_count,
          formal_ready_relation_count
        ORDER BY disease_category, disease_subcategory, disease_name, disease_code
        """,
        {"key_names": CAD_KEY_NAMES},
    )


def fetch_dimension_counts(client: Neo4jHttpClient, disease_codes: list[str]) -> list[dict[str, Any]]:
    return query(
        client,
        """
        UNWIND $disease_codes AS code
        MATCH (d:KGNode {code: code})
        OPTIONAL MATCH (d)-[r]-(n:KGNode)
        WHERE n.entityType IN $dimension_types
        RETURN d.code AS disease_code,
               d.name AS disease_name,
               n.entityType AS entity_type,
               count(DISTINCT n) AS entity_count,
               count(DISTINCT r) AS relation_count
        ORDER BY disease_code, entity_type
        """,
        {"disease_codes": disease_codes, "dimension_types": DIMENSION_ENTITY_TYPES},
    )


def fetch_quality_issues(client: Neo4jHttpClient, disease_codes: list[str]) -> dict[str, list[dict[str, Any]]]:
    checks = {
        "诊断标准无明细": """
            UNWIND $disease_codes AS code
            MATCH (d:KGNode {code: code})--(c:KGNode)
            WHERE c.entityType = 'DiagnosisCriteria'
              AND NOT EXISTS {
                MATCH (c)--(x:KGNode)
                WHERE x.entityType IN ['DiagnosisCriteriaComponent','ClinicalRule','Exam','LabTest','ExamIndicator','LabTestIndicator','Symptom','Sign','ThresholdRule']
              }
            RETURN DISTINCT d.code AS disease_code, d.name AS disease_name,
                   c.code AS node_code, c.name AS node_name, c.entityType AS entity_type
            ORDER BY disease_code, node_name
        """,
        "鉴别诊断无规则或依据": """
            UNWIND $disease_codes AS code
            MATCH (d:KGNode {code: code})--(c:KGNode)
            WHERE c.entityType = 'DifferentialDiagnosis'
              AND NOT EXISTS {
                MATCH (c)--(x:KGNode)
                WHERE x.entityType IN ['ClinicalRule','Exam','LabTest','ExamIndicator','LabTestIndicator','Symptom','Sign','ThresholdRule','Evidence','Guideline']
              }
            RETURN DISTINCT d.code AS disease_code, d.name AS disease_name,
                   c.code AS node_code, c.name AS node_name, c.entityType AS entity_type
            ORDER BY disease_code, node_name
        """,
        "治疗方案无下游动作": """
            UNWIND $disease_codes AS code
            MATCH (d:KGNode {code: code})--(c:KGNode)
            WHERE c.entityType = 'TreatmentPlan'
              AND NOT EXISTS {
                MATCH (c)--(x:KGNode)
                WHERE x.entityType IN ['Medication','Procedure','ClinicalRule','RecommendationStatement','TreatmentPlan','Contraindication','ClinicalPathway','PathwayStage','Evidence','Guideline']
              }
            RETURN DISTINCT d.code AS disease_code, d.name AS disease_name,
                   c.code AS node_code, c.name AS node_name, c.entityType AS entity_type
            ORDER BY disease_code, node_name
        """,
        "同疾病同类型同名重复直连": """
            UNWIND $disease_codes AS code
            MATCH (d:KGNode {code: code})--(n:KGNode)
            WHERE n.entityType IS NOT NULL
              AND n.name IS NOT NULL
              AND trim(n.name) <> ''
              AND NOT n.entityType IN ['Evidence','Guideline','RecommendationStatement','ClinicalRule','ClinicalPathway','PathwayStage','SourceDocument']
            WITH d, n.entityType AS entity_type, n.name AS node_name,
                 count(DISTINCT n.code) AS duplicate_count,
                 collect(DISTINCT n.code)[0..30] AS node_codes
            WHERE duplicate_count > 1
            RETURN d.code AS disease_code, d.name AS disease_name,
                   entity_type, node_name, duplicate_count, node_codes
            ORDER BY disease_code, entity_type, node_name
        """,
        "CDSS推荐节点缺证据": """
            UNWIND $disease_codes AS code
            MATCH (d:KGNode {code: code})-[dn]-(n:KGNode)
            WHERE n.entityType IN ['ClinicalRule','RecommendationStatement','TreatmentPlan']
              AND coalesce(dn.formal_cdss_ready, coalesce(n.formal_cdss_ready, true)) <> false
              AND NOT EXISTS {
                MATCH (n)-[er]-(e:KGNode)
                WHERE e.entityType IN ['Evidence','Guideline']
                  AND (er.disease_code IS NULL OR er.disease_code = code)
              }
            RETURN DISTINCT d.code AS disease_code, d.name AS disease_name,
                   n.code AS node_code, n.name AS node_name, n.entityType AS entity_type
            ORDER BY disease_code, entity_type, node_name
        """,
    }
    return {name: query(client, statement, {"disease_codes": disease_codes}) for name, statement in checks.items()}


def fetch_evidence_samples(client: Neo4jHttpClient, disease_codes: list[str]) -> list[dict[str, Any]]:
    return query(
        client,
        """
        UNWIND $disease_codes AS code
        MATCH (d:KGNode {code: code})--(n:KGNode)
        WHERE n.entityType IN ['ClinicalRule','RecommendationStatement','TreatmentPlan','Medication','Procedure','DiagnosisCriteria','DifferentialDiagnosis']
        OPTIONAL MATCH (n)--(e:KGNode {entityType:'Evidence'})
        OPTIONAL MATCH (n)--(g:KGNode {entityType:'Guideline'})
        WITH d, n,
             collect(DISTINCT coalesce(g.name, g.source_name, g.title))[0..3] AS guideline_names,
             collect(DISTINCT coalesce(e.evidence_text, e.original_text, e.text, e.name))[0..2] AS evidence_texts,
             collect(DISTINCT coalesce(e.page, e.page_number, e.page_start, e.source_page))[0..3] AS pages,
             collect(DISTINCT coalesce(e.recommendation_class, n.recommendation_class, e.recommendation_level, n.recommendation_level))[0..3] AS recommendation_levels,
             collect(DISTINCT coalesce(e.evidence_level, n.evidence_level))[0..3] AS evidence_levels
        RETURN d.code AS disease_code,
               d.name AS disease_name,
               n.entityType AS entity_type,
               n.code AS node_code,
               n.name AS node_name,
               guideline_names,
               pages,
               recommendation_levels,
               evidence_levels,
               evidence_texts
        ORDER BY disease_code, entity_type, node_name
        LIMIT 300
        """,
        {"disease_codes": disease_codes},
    )


def build_capability_rows(diseases: list[dict[str, Any]], dimension_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_disease_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in dimension_rows:
        if row.get("entity_type"):
            by_disease_type[row["disease_code"]][row["entity_type"]] += int(row.get("entity_count") or 0)

    result: list[dict[str, Any]] = []
    for disease in diseases:
        code = disease["disease_code"]
        counts = by_disease_type[code]
        for scenario, entity_types in SCENARIOS:
            total = sum(counts.get(entity_type, 0) for entity_type in entity_types)
            if total >= 3:
                status = "可用于CDSS展示"
            elif total > 0:
                status = "可展示但需补强"
            else:
                status = "缺口"
            if scenario in {"治疗方案", "诊断建议", "鉴别诊断"} and total > 0 and int(disease.get("evidence_count") or 0) == 0:
                status = "需补证据链"
            result.append(
                {
                    "疾病编码": code,
                    "疾病名称": disease["disease_name"],
                    "疾病大类": disease.get("disease_category", ""),
                    "CDSS场景": scenario,
                    "支撑实体类型": "、".join(entity_types),
                    "支撑实体数量": total,
                    "证据节点数量": disease.get("evidence_count", 0),
                    "正式CDSS关系数": disease.get("formal_ready_relation_count", 0),
                    "能力判断": status,
                }
            )
    return result


def build_dimension_summary_rows(diseases: list[dict[str, Any]], dimension_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_disease_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in dimension_rows:
        if row.get("entity_type"):
            by_disease_type[row["disease_code"]][row["entity_type"]] += int(row.get("entity_count") or 0)

    rows: list[dict[str, Any]] = []
    for disease in diseases:
        counts = by_disease_type[disease["disease_code"]]
        item = {
            "疾病编码": disease["disease_code"],
            "疾病名称": disease["disease_name"],
            "疾病大类": disease.get("disease_category", ""),
            "疾病亚类": disease.get("disease_subcategory", ""),
            "formal_cdss_ready": disease.get("formal_cdss_ready", False),
            "临床审核状态": disease.get("clinical_review_status", ""),
            "关联实体数": disease.get("related_entity_count", 0),
            "关系数": disease.get("relation_count", 0),
            "证据数": disease.get("evidence_count", 0),
            "指南数": disease.get("guideline_count", 0),
            "CDSS决策节点数": disease.get("cdss_decision_node_count", 0),
            "正式CDSS关系数": disease.get("formal_ready_relation_count", 0),
            "定义是否存在": "是" if str(disease.get("definition") or "").strip() else "否",
        }
        for entity_type in DIMENSION_ENTITY_TYPES:
            item[entity_type] = counts.get(entity_type, 0)
        rows.append(item)
    return rows


def build_progress_rows(diseases: list[dict[str, Any]], capability_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    capability_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in capability_rows:
        capability_by_code[row["疾病编码"]].append(row)
    rows: list[dict[str, Any]] = []
    for disease in diseases:
        caps = capability_by_code[disease["disease_code"]]
        ready = sum(1 for row in caps if row["能力判断"] == "可用于CDSS展示")
        partial = sum(1 for row in caps if row["能力判断"] == "可展示但需补强")
        gaps = sum(1 for row in caps if row["能力判断"] in {"缺口", "需补证据链"})
        total = len(caps) or 1
        score = round((ready * 1.0 + partial * 0.5) / total * 100, 1)
        rows.append(
            {
                "疾病编码": disease["disease_code"],
                "疾病名称": disease["disease_name"],
                "疾病大类": disease.get("disease_category", ""),
                "疾病亚类": disease.get("disease_subcategory", ""),
                "关联实体数": disease.get("related_entity_count", 0),
                "证据数": disease.get("evidence_count", 0),
                "指南数": disease.get("guideline_count", 0),
                "CDSS决策节点数": disease.get("cdss_decision_node_count", 0),
                "正式CDSS关系数": disease.get("formal_ready_relation_count", 0),
                "可用场景数": ready,
                "需补强场景数": partial,
                "缺口场景数": gaps,
                "大类基线分": score,
                "交付判断": "可作为样板/测试库" if score >= 80 and gaps <= 2 else ("可参考但需补强" if score >= 60 else "暂不建议作为交付样板"),
            }
        )
    return rows


def write_markdown_report(
    path: Path,
    generated_at: str,
    diseases: list[dict[str, Any]],
    progress_rows: list[dict[str, Any]],
    quality_issues: dict[str, list[dict[str, Any]]],
    evidence_samples: list[dict[str, Any]],
) -> None:
    total_diseases = len(diseases)
    total_relations = sum(int(row.get("relation_count") or 0) for row in diseases)
    total_evidence = sum(int(row.get("evidence_count") or 0) for row in diseases)
    total_guidelines = sum(int(row.get("guideline_count") or 0) for row in diseases)
    issue_count = sum(len(rows) for rows in quality_issues.values())
    high_score = sum(1 for row in progress_rows if row["大类基线分"] >= 80)
    medium_score = sum(1 for row in progress_rows if 60 <= row["大类基线分"] < 80)
    low_score = sum(1 for row in progress_rows if row["大类基线分"] < 60)

    lines = [
        "# 冠心病大类图谱质量验收报告",
        "",
        f"- 生成时间：{generated_at}",
        "- 验收口径：疾病大类，不把 AMI 当成冠心病整体。",
        "- AMI/STEMI 定位：冠心病大类中的技术开发案例和深度样板。",
        "- 数据来源：服务器 Neo4j 只读查询 + 已入库图谱关系。",
        "",
        "## 1. 总览",
        "",
        "| 项目 | 数量 |",
        "|---|---:|",
        f"| 冠心病大类相关疾病/分型 | {total_diseases} |",
        f"| 关联关系总数 | {total_relations} |",
        f"| 证据节点数 | {total_evidence} |",
        f"| 指南节点数 | {total_guidelines} |",
        f"| 质量问题总数 | {issue_count} |",
        f"| 基线分 ≥80 的疾病 | {high_score} |",
        f"| 基线分 60-79 的疾病 | {medium_score} |",
        f"| 基线分 <60 的疾病 | {low_score} |",
        "",
        "## 2. 大类交付判断",
        "",
    ]
    if total_diseases == 0:
        lines.append("未在服务器识别到冠心病大类疾病节点，必须先修复疾病目录层。")
    elif issue_count == 0 and low_score == 0:
        lines.append("冠心病大类可作为 V1.0 第一交付大类进入前端/后端联调；仍需按医生使用场景继续优化展示。")
    elif issue_count == 0:
        lines.append("冠心病大类已通过本轮硬质量验收，可作为大类交付基线；低分疾病代表覆盖深度不足，后续按优先级继续补充，不等同于硬质量失败。")
    else:
        lines.append("冠心病大类仍存在硬质量问题，需按本报告问题清单补齐后再作为完整大类样板。")

    lines.extend(
        [
            "",
            "## 3. 疾病/分型基线分",
            "",
            "| 疾病 | 关联实体 | 证据 | 可用场景 | 缺口场景 | 基线分 | 判断 |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in sorted(progress_rows, key=lambda item: (-item["大类基线分"], item["疾病名称"])):
        lines.append(
            f"| {row['疾病名称']} | {row['关联实体数']} | {row['证据数']} | {row['可用场景数']} | {row['缺口场景数']} | {row['大类基线分']} | {row['交付判断']} |"
        )

    lines.extend(["", "## 4. 质量问题", ""])
    for name, rows in quality_issues.items():
        lines.append(f"### {name}")
        lines.append("")
        if not rows:
            lines.append("- 未发现。")
        else:
            lines.append(f"- 发现 {len(rows)} 条，详见 `04_质量问题明细.json` 和 `冠心病大类前端展示问题清单_20260714.md`。")
        lines.append("")

    lines.extend(
        [
            "## 5. 证据链抽查说明",
            "",
            f"- 本轮抽取推荐/诊断/治疗/鉴别相关证据样本 {len(evidence_samples)} 条。",
            "- 医生端展示时，不应显示疾病全部证据；应显示当前推荐动作绑定的指南、页码/段落、推荐等级、证据等级和原文摘要。",
            "- AMI/STEMI 仍作为技术开发案例，但报告和验收按冠心病大类计算。",
            "",
            "## 6. 交付结论",
            "",
            "冠心病大类进入 V1.0 基线验收流程。下一步不是单独追 AMI，而是按本报告缺口对整个冠心病大类补齐，并把 AMI/STEMI 样板交给技术同事实现动态 CDSS 推理与展示。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_frontend_issues(path: Path, quality_issues: dict[str, list[dict[str, Any]]], evidence_samples: list[dict[str, Any]]) -> None:
    lines = [
        "# 冠心病大类前端展示问题清单",
        "",
        "## 给 Trae/前端的核心要求",
        "",
        "1. 冠心病是疾病大类；AMI/STEMI 是开发案例，不能把 AMI 当成冠心病全部。",
        "2. 诊断标准、鉴别诊断、治疗方案必须继续下钻到规则/条件/证据，不允许只显示标题。",
        "3. 证据与指南不按疾病一股脑展示；医生点到某条推荐时，只展示该推荐绑定的证据。",
        "4. 页面统计应按疾病大类、疾病、实体类型、关系类型分层展示。",
        "",
        "## 数据驱动的前端待处理项",
        "",
    ]
    for name, rows in quality_issues.items():
        if not rows:
            continue
        lines.append(f"### {name}")
        lines.append("")
        for row in rows[:30]:
            lines.append(
                f"- {row.get('disease_name','')}：{row.get('node_name') or row.get('node_name','')}（{row.get('node_code') or row.get('node_codes','')}）"
            )
        if len(rows) > 30:
            lines.append(f"- 其余 {len(rows) - 30} 条见 JSON 明细。")
        lines.append("")

    lines.extend(
        [
            "## 证据展示改造",
            "",
            "前端接口建议返回结构：",
            "",
            "```json",
            json.dumps(
                {
                    "recommendation": "急诊PCI",
                    "disease": "ST段抬高型心肌梗死",
                    "why_triggered": "胸痛 + ST段抬高 + 发病时间窗满足",
                    "evidence": {
                        "guideline": "STEMI CN 2019.pdf",
                        "page": "页码或段落",
                        "recommendation_level": "推荐等级",
                        "evidence_level": "证据等级",
                        "summary": "原文摘要",
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            f"本轮可供抽查的证据样本数量：{len(evidence_samples)}。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成疾病大类交付验收包。当前支持冠心病大类。")
    parser.add_argument("--category", default="冠心病")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "心血管内科文献集合" / "20260714_冠心病大类交付验收")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()

    if args.category != "冠心病":
        raise SystemExit("当前脚本先固化冠心病大类验收；其他大类后续复用本结构扩展。")

    conn = parse_connection_file(args.connection_file)
    client = Neo4jHttpClient(conn["uri"], conn["username"], conn["password"], args.database, 5, 1)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    diseases = fetch_diseases(client)
    disease_codes = [row["disease_code"] for row in diseases if row.get("disease_code")]
    dimension_rows = fetch_dimension_counts(client, disease_codes) if disease_codes else []
    quality_issues = fetch_quality_issues(client, disease_codes) if disease_codes else {}
    evidence_samples = fetch_evidence_samples(client, disease_codes) if disease_codes else []
    capability_rows = build_capability_rows(diseases, dimension_rows)
    dimension_summary_rows = build_dimension_summary_rows(diseases, dimension_rows)
    progress_rows = build_progress_rows(diseases, capability_rows)

    write_csv(
        args.output_dir / "冠心病大类建设进度表_20260714.csv",
        progress_rows,
        [
            "疾病编码",
            "疾病名称",
            "疾病大类",
            "疾病亚类",
            "关联实体数",
            "证据数",
            "指南数",
            "CDSS决策节点数",
            "正式CDSS关系数",
            "可用场景数",
            "需补强场景数",
            "缺口场景数",
            "大类基线分",
            "交付判断",
        ],
    )
    write_csv(args.output_dir / "冠心病大类CDSS推荐能力矩阵_20260714.csv", capability_rows)
    write_csv(args.output_dir / "冠心病大类维度覆盖明细_20260714.csv", dimension_summary_rows)
    write_csv(args.output_dir / "冠心病大类证据链抽查样本_20260714.csv", evidence_samples)

    (args.output_dir / "04_质量问题明细.json").write_text(
        json.dumps(quality_issues, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "05_冠心病大类验收原始数据.json").write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "category": args.category,
                "diseases": diseases,
                "dimension_rows": dimension_rows,
                "progress_rows": progress_rows,
                "capability_rows": capability_rows,
                "evidence_samples": evidence_samples,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    write_markdown_report(
        args.output_dir / "冠心病大类图谱质量验收报告_20260714.md",
        generated_at,
        diseases,
        progress_rows,
        quality_issues,
        evidence_samples,
    )
    write_frontend_issues(
        args.output_dir / "冠心病大类前端展示问题清单_20260714.md",
        quality_issues,
        evidence_samples,
    )

    summary = {
        "generated_at": generated_at,
        "category": args.category,
        "output_dir": str(args.output_dir),
        "disease_count": len(diseases),
        "evidence_sample_count": len(evidence_samples),
        "quality_issue_counts": {name: len(rows) for name, rows in quality_issues.items()},
        "progress_distribution": {
            ">=80": sum(1 for row in progress_rows if row["大类基线分"] >= 80),
            "60-79": sum(1 for row in progress_rows if 60 <= row["大类基线分"] < 80),
            "<60": sum(1 for row in progress_rows if row["大类基线分"] < 60),
        },
    }
    (args.output_dir / "00_冠心病大类交付验收摘要.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
