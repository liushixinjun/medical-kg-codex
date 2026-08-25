from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "2026年8月真实性来源核验"
LINK_FILE = ROOT / "图谱数据库链接.txt"


def parse_neo4j_link() -> tuple[str, str, str]:
    text = LINK_FILE.read_text(encoding="utf-8", errors="ignore")
    uri_match = re.search(r"bolt://[^\s\u3000，,]+", text)
    user_match = re.search(r"(?:用户名|用户|user|username)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    password_match = re.search(r"(?:密码|password)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    if not uri_match or not password_match:
        raise RuntimeError("未在图谱数据库链接.txt 中解析到 bolt 地址或密码")
    return uri_match.group(0), (user_match.group(1) if user_match else "neo4j"), password_match.group(1)


CHECKS = [
    {
        "name": "检查检验方案无下钻项目",
        "severity": "阻断",
        "query": """
            MATCH (d:Disease)-[:has_exam_plan]->(p:ExamPlan)
            WHERE NOT (p)-[:includes_exam_item|includes_lab_item]->()
            RETURN d.code AS disease_code, d.name AS disease_name,
                   p.code AS object_code, p.name AS object_name,
                   'has_exam_plan' AS relation_type,
                   'ExamPlan 没有 includes_exam_item/includes_lab_item' AS reason
            ORDER BY d.code, p.name
        """,
    },
    {
        "name": "检查检验下钻关系缺用途阶段来源",
        "severity": "阻断",
        "query": """
            MATCH (d:Disease)-[:has_exam_plan]->(:ExamPlan)-[r:includes_exam_item|includes_lab_item]->(item)
            WHERE r.purpose IS NULL
               OR r.clinical_stage IS NULL
               OR r.service_target_code IS NULL
               OR (
                    r.evidence_id IS NULL AND r.evidence_ids IS NULL
                    AND r.evidence_text IS NULL AND r.source_name IS NULL
                    AND r.source_names IS NULL
                  )
            RETURN d.code AS disease_code, d.name AS disease_name,
                   item.code AS object_code, item.name AS object_name,
                   type(r) AS relation_type,
                   '缺 purpose/clinical_stage/service_target_code/来源证据字段' AS reason
            ORDER BY d.code, item.name
        """,
    },
    {
        "name": "鉴别诊断对象无鉴别规则",
        "severity": "阻断",
        "query": """
            MATCH (d:Disease)-[:has_differential_diagnosis]->(ddx:DifferentialDiagnosis)
            WHERE NOT (ddx)-[:has_differential_rule]->(:ClinicalRule)
            RETURN d.code AS disease_code, d.name AS disease_name,
                   ddx.code AS object_code, ddx.name AS object_name,
                   'has_differential_diagnosis' AS relation_type,
                   '鉴别对象缺少 has_differential_rule' AS reason
            ORDER BY d.code, ddx.name
        """,
    },
    {
        "name": "鉴别规则无排除检查检验",
        "severity": "阻断",
        "query": """
            MATCH (d:Disease)-[:has_differential_diagnosis]->(:DifferentialDiagnosis)-[:has_differential_rule]->(rule:ClinicalRule)
            WHERE NOT (rule)-[:requires_exclusion_exam|requires_exclusion_lab]->()
            RETURN d.code AS disease_code, d.name AS disease_name,
                   rule.code AS object_code, rule.name AS object_name,
                   'has_differential_rule' AS relation_type,
                   '鉴别规则缺少 requires_exclusion_exam/requires_exclusion_lab' AS reason
            ORDER BY d.code, rule.name
        """,
    },
    {
        "name": "治疗方案无具体动作",
        "severity": "阻断",
        "query": """
            MATCH (d:Disease)-[:has_treatment_plan]->(p:TreatmentPlan)
            WHERE NOT (p)-[:includes_medication|includes_procedure|includes_treatment_item]->()
            RETURN d.code AS disease_code, d.name AS disease_name,
                   p.code AS object_code, p.name AS object_name,
                   'has_treatment_plan' AS relation_type,
                   '治疗方案缺少具体用药/手术/治疗项目' AS reason
            ORDER BY d.code, p.name
        """,
    },
    {
        "name": "治疗动作关系缺用途阶段来源",
        "severity": "阻断",
        "query": """
            MATCH (d:Disease)-[:has_treatment_plan]->(:TreatmentPlan)-[r:includes_medication|includes_procedure|includes_treatment_item]->(item)
            WHERE r.purpose IS NULL
               OR r.clinical_stage IS NULL
               OR r.service_target_code IS NULL
               OR (
                    r.evidence_id IS NULL AND r.evidence_ids IS NULL
                    AND r.evidence_text IS NULL AND r.source_name IS NULL
                    AND r.source_names IS NULL
                  )
            RETURN d.code AS disease_code, d.name AS disease_name,
                   item.code AS object_code, item.name AS object_name,
                   type(r) AS relation_type,
                   '缺 purpose/clinical_stage/service_target_code/来源证据字段' AS reason
            ORDER BY d.code, item.name
        """,
    },
    {
        "name": "正式推荐缺动作证据主指南",
        "severity": "阻断",
        "query": """
            MATCH (r:RecommendationStatement)
            OPTIONAL MATCH (r)-[:recommends_action]->(a)
            OPTIONAL MATCH (r)-[:derived_from|supported_by_evidence]->(e:Evidence)
            OPTIONAL MATCH (r)-[:based_on_guideline]->(g:Guideline)
            WITH r, count(DISTINCT a) AS action_count, count(DISTINCT e) AS evidence_count, count(DISTINCT g) AS guideline_count
            WHERE action_count = 0 OR evidence_count = 0 OR guideline_count = 0
            RETURN coalesce(r.disease_code, r.scope_disease_code, '') AS disease_code,
                   coalesce(r.disease_name, r.scope_disease_name, '') AS disease_name,
                   r.code AS object_code, r.name AS object_name,
                   'RecommendationStatement' AS relation_type,
                   '正式推荐缺动作/证据/主指南' AS reason
            ORDER BY disease_code, object_code
        """,
    },
    {
        "name": "证据节点缺原文或来源",
        "severity": "阻断",
        "query": """
            MATCH (e:Evidence)
            WHERE e.evidence_text IS NULL OR trim(toString(e.evidence_text)) = ''
               OR e.source_name IS NULL OR trim(toString(e.source_name)) = ''
            RETURN coalesce(e.disease_code, '') AS disease_code,
                   coalesce(e.disease_name, '') AS disease_name,
                   e.code AS object_code, e.name AS object_name,
                   'Evidence' AS relation_type,
                   'Evidence 缺 evidence_text/source_name' AS reason
            ORDER BY object_code
        """,
    },
]


SAMPLE_DISEASE_CODES = [
    "DIS-CARD-CAD-AMI",
    "DIS-CARD-CAD-STEMI",
    "DIS-CARD-CAD-NSTEMI",
    "DIS-CARD-CM-GENERAL",
    "DIS-CARD-CM-HCM",
    "DIS-CARD-CM-DCM",
]


def rows(session, query: str, **params):
    return [r.data() for r in session.run(query, **params)]


def count_rows(session, query: str) -> int:
    return session.run(f"CALL {{ {query} }} RETURN count(*) AS c").single()["c"]


def sample_rows(session, query: str, limit: int = 300) -> list[dict]:
    return rows(session, f"{query}\nLIMIT {limit}")


def scalar_count(session, query: str, **params) -> int:
    return session.run(query, **params).single()["c"]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    uri, user, password = parse_neo4j_link()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    defects: list[dict] = []
    summary: list[dict] = []
    sample: dict[str, object] = {}

    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session() as session:
            db_stats = rows(
                session,
                """
                MATCH (n) WITH count(n) AS node_count
                MATCH ()-[r]->() WITH node_count, count(r) AS rel_count
                MATCH (d:Disease) WITH node_count, rel_count, count(d) AS disease_count
                MATCH (rs:RecommendationStatement) RETURN node_count, rel_count, disease_count, count(rs) AS recommendation_count
                """,
            )[0]

            for check in CHECKS:
                total = count_rows(session, check["query"])
                result = sample_rows(session, check["query"], 300)
                summary.append(
                    {
                        "检查项": check["name"],
                        "级别": check["severity"],
                        "缺口数": total,
                    }
                )
                for item in result:
                    item["检查项"] = check["name"]
                    item["级别"] = check["severity"]
                    defects.append(item)

            sample_stats = []
            for code in SAMPLE_DISEASE_CODES:
                disease = rows(session, "MATCH (d:Disease {code:$code}) RETURN d.code AS code, d.name AS name, d.diagnostic_role AS diagnostic_role", code=code)
                if not disease:
                    continue
                base = disease[0]
                count_queries = {
                    "definition_count": "MATCH (d:Disease {code:$code})-[:has_definition]->(x:Definition) RETURN count(DISTINCT x) AS c",
                    "exam_item_count": "MATCH (d:Disease {code:$code})-[:has_exam_plan]->(:ExamPlan)-[:includes_exam_item]->(x) RETURN count(DISTINCT x) AS c",
                    "lab_item_count": "MATCH (d:Disease {code:$code})-[:has_exam_plan]->(:ExamPlan)-[:includes_lab_item]->(x) RETURN count(DISTINCT x) AS c",
                    "ddx_count": "MATCH (d:Disease {code:$code})-[:has_differential_diagnosis]->(x) RETURN count(DISTINCT x) AS c",
                    "ddx_rule_count": "MATCH (d:Disease {code:$code})-[:has_differential_diagnosis]->(:DifferentialDiagnosis)-[:has_differential_rule]->(x) RETURN count(DISTINCT x) AS c",
                    "medication_count": "MATCH (d:Disease {code:$code})-[:has_treatment_plan]->(:TreatmentPlan)-[:includes_medication]->(x) RETURN count(DISTINCT x) AS c",
                    "procedure_count": "MATCH (d:Disease {code:$code})-[:has_treatment_plan]->(:TreatmentPlan)-[:includes_procedure]->(x) RETURN count(DISTINCT x) AS c",
                    "recommendation_count": "MATCH (x:RecommendationStatement) WHERE x.disease_code=$code OR x.scope_disease_code=$code RETURN count(DISTINCT x) AS c",
                }
                for key, q in count_queries.items():
                    base[key] = scalar_count(session, q, code=code)
                sample_stats.append(base)
            sample["样板疾病链路统计"] = sample_stats

            sample["AMI核心链路样例"] = rows(
                session,
                """
                MATCH (d:Disease {code:'DIS-CARD-CAD-AMI'})
                OPTIONAL MATCH (d)-[:has_exam_plan]->(:ExamPlan)-[er:includes_exam_item|includes_lab_item]->(item)
                WITH d, collect(DISTINCT {rel:type(er), item:item.name, purpose:er.purpose, stage:er.clinical_stage, source:coalesce(er.source_name, er.source_names[0]), evidence:substring(coalesce(er.evidence_text,''),0,120)})[0..12] AS exam_chain
                OPTIONAL MATCH (d)-[:has_differential_diagnosis]->(ddx)-[:has_differential_rule]->(rule)-[rr:requires_exclusion_exam|requires_exclusion_lab]->(x)
                WITH d, exam_chain, collect(DISTINCT {ddx:ddx.name, rule:rule.name, item:x.name, rel:type(rr), purpose:rr.purpose})[0..12] AS ddx_chain
                OPTIONAL MATCH (rs:RecommendationStatement)
                WHERE rs.disease_code='DIS-CARD-CAD-AMI' OR rs.scope_disease_code='DIS-CARD-CAD-AMI'
                OPTIONAL MATCH (rs)-[:recommends_action]->(a)
                OPTIONAL MATCH (rs)-[:derived_from|supported_by_evidence]->(e:Evidence)
                OPTIONAL MATCH (rs)-[:based_on_guideline]->(g:Guideline)
                RETURN d.code AS code, d.name AS name, exam_chain, ddx_chain,
                       collect(DISTINCT {recommendation:rs.name, action:a.name, guideline:g.name, evidence_id:e.code, evidence_text:substring(coalesce(e.evidence_text,''),0,120)})[0..12] AS recommendation_chain
                """,
            )

    csv_path = OUT_DIR / "真实性来源一致性缺口明细_20260817.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["检查项", "级别", "disease_code", "disease_name", "object_code", "object_name", "relation_type", "reason"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(defects)

    sample_path = OUT_DIR / "样板链路实例_20260817.json"
    sample_path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = OUT_DIR / "真实性来源一致性核验报告_20260817.md"
    lines = [
        "# 真实性与来源一致性核验报告",
        "",
        f"- 生成时间：{now}",
        f"- 数据库：{uri}",
        f"- 节点数：{db_stats['node_count']}",
        f"- 关系数：{db_stats['rel_count']}",
        f"- 疾病数：{db_stats['disease_count']}",
        f"- 正式推荐数：{db_stats['recommendation_count']}",
        "",
        "## 1. 结论",
        "",
    ]
    blocker_count = sum(item["缺口数"] for item in summary if item["级别"] == "阻断")
    if blocker_count == 0:
        lines.append("本轮硬闸门通过：检查检验、鉴别诊断、治疗动作、正式推荐和证据来源未发现结构性阻断。")
    else:
        lines.append(f"本轮发现阻断缺口 {blocker_count} 条，不能直接判定全库已达到正式 CDSS 可用标准。")
    lines += [
        "",
        "## 2. 缺口汇总",
        "",
        "| 检查项 | 级别 | 缺口数 |",
        "|---|---:|---:|",
    ]
    for item in summary:
        lines.append(f"| {item['检查项']} | {item['级别']} | {item['缺口数']} |")
    lines += [
        "",
        "## 3. AMI/心肌病样板统计",
        "",
        "| 疾病编码 | 疾病名称 | 诊断角色 | 定义 | 检查项目 | 检验项目 | 鉴别对象 | 鉴别规则 | 药物 | 手术 | 正式推荐 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sample["样板疾病链路统计"]:
        lines.append(
            f"| {row['code']} | {row['name']} | {row.get('diagnostic_role') or ''} | "
            f"{row['definition_count']} | {row['exam_item_count']} | {row['lab_item_count']} | "
            f"{row['ddx_count']} | {row['ddx_rule_count']} | {row['medication_count']} | "
            f"{row['procedure_count']} | {row['recommendation_count']} |"
        )
    lines += [
        "",
        "## 4. 输出文件",
        "",
        f"- 缺口明细：`{csv_path.name}`",
        f"- 样板链路实例：`{sample_path.name}`",
        "",
        "## 5. 执行边界",
        "",
        "- 本脚本只读 Neo4j，不写库。",
        "- 发现缺口时，后续只能基于教材、指南或已存在证据补齐，不允许模型补造证据。",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(str(md_path))
    print(json.dumps({"blocker_count": blocker_count, "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
