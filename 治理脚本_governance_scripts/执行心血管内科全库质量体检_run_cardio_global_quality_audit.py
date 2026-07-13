# -*- coding: utf-8 -*-
"""执行心血管内科全库质量体检。

检查目标：
- 非 KGNode 节点
- 空证据 Evidence
- 已挂疾病的 LabTest 是否缺指标或缺非空证据
- 已挂疾病的 ExamIndicator 是否缺非空证据
- 诊断标准是否无明细
- 鉴别诊断是否无下级说明/规则
- RecommendationStatement 是否缺证据、缺动作、缺指南
- 语义重复关系
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "心血管内科文献集合"
OUT_DIR = COLLECTION / "00_全局质量体检_global_quality_audit" / "20260713_after_lab_evidence_cleanup"

CARDIO_DISEASE_WHERE = """
(
  d.code STARTS WITH 'DIS-CARD'
)
"""


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


def first_row(session: Any, query: str) -> dict[str, Any]:
    rows = session.run(query).data()
    return rows[0] if rows else {}


def run() -> dict[str, Any]:
    bolt, user, password = parse_conn()
    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session() as session:
            checks: dict[str, Any] = {}
            checks["non_kg_nodes"] = first_row(
                session,
                "MATCH (n) WHERE NOT n:KGNode RETURN count(n) AS count, collect(labels(n))[..10] AS sample_labels",
            )
            checks["empty_evidence_nodes"] = first_row(
                session,
                """
                MATCH (e:KGNode {entityType:'Evidence'})
                WHERE trim(coalesce(e.evidence_text,e.original_text,e.evidence_summary,'')) = ''
                RETURN count(e) AS count, collect(e.code)[..30] AS sample_codes
                """,
            )
            checks["required_lab_without_indicator_or_evidence"] = session.run(
                f"""
                MATCH (d:KGNode {{entityType:'Disease'}})-[:requires_lab_test]->(l:KGNode {{entityType:'LabTest'}})
                WHERE {CARDIO_DISEASE_WHERE}
                OPTIONAL MATCH (l)-[:lab_test_has_indicator]->(i:KGNode {{entityType:'ExamIndicator'}})
                OPTIONAL MATCH (l)-[:supported_by_evidence]->(e:KGNode {{entityType:'Evidence'}})
                WITH d,l,collect(DISTINCT i.code) AS indicators,
                     collect(DISTINCT coalesce(e.evidence_text,e.original_text,e.evidence_summary,'')) AS evtexts
                WITH d,l,indicators,[x IN evtexts WHERE trim(x)<>''] AS nonempty_evs
                WHERE size(indicators)=0 OR size(nonempty_evs)=0
                RETURN d.code AS disease_code,d.name AS disease_name,l.code AS lab_code,l.name AS lab_name,
                       size(indicators) AS indicator_count,size(nonempty_evs) AS nonempty_evidence_count
                ORDER BY d.code,l.name
                LIMIT 100
                """
            ).data()
            checks["indicator_without_evidence"] = session.run(
                f"""
                MATCH (d:KGNode {{entityType:'Disease'}})-[:requires_lab_test|requires_exam]->(x:KGNode)-[:lab_test_has_indicator|exam_has_indicator]->(i:KGNode {{entityType:'ExamIndicator'}})
                WHERE {CARDIO_DISEASE_WHERE}
                OPTIONAL MATCH (i)-[:supported_by_evidence]->(e:KGNode {{entityType:'Evidence'}})
                WITH DISTINCT i, collect(DISTINCT coalesce(e.evidence_text,e.original_text,e.evidence_summary,'')) AS evtexts
                WITH i, [x IN evtexts WHERE trim(x)<>''] AS nonempty_evs
                WHERE size(nonempty_evs)=0
                RETURN i.code AS indicator_code,i.name AS indicator_name
                ORDER BY i.code
                LIMIT 100
                """
            ).data()
            checks["diagnosis_criteria_without_component"] = session.run(
                f"""
                MATCH (d:KGNode {{entityType:'Disease'}})-[:has_diagnostic_criteria]->(dc:KGNode {{entityType:'DiagnosisCriteria'}})
                WHERE {CARDIO_DISEASE_WHERE}
                OPTIONAL MATCH (dc)-[:has_diagnostic_component]->(c:KGNode)
                WITH d,dc,count(c) AS component_count
                WHERE component_count=0
                RETURN d.code AS disease_code,d.name AS disease_name,dc.code AS criteria_code,dc.name AS criteria_name
                ORDER BY d.code
                LIMIT 100
                """
            ).data()
            checks["differential_without_detail"] = session.run(
                f"""
                MATCH (d:KGNode {{entityType:'Disease'}})-[:has_differential_diagnosis]->(dd:KGNode {{entityType:'DifferentialDiagnosis'}})
                WHERE {CARDIO_DISEASE_WHERE}
                OPTIONAL MATCH (dd)-[:has_differential_detail|differentiated_by|has_exclusion_rule|has_diagnostic_component]->(x:KGNode)
                WITH d,dd,count(x) AS detail_count
                WHERE detail_count=0
                RETURN d.code AS disease_code,d.name AS disease_name,dd.code AS differential_code,dd.name AS differential_name
                ORDER BY d.code
                LIMIT 100
                """
            ).data()
            checks["recommendation_statement_missing_core"] = session.run(
                """
                MATCH (rs:KGNode {entityType:'RecommendationStatement'})
                OPTIONAL MATCH (rs)-[:supported_by_evidence]->(e:KGNode {entityType:'Evidence'})
                OPTIONAL MATCH (rs)-[:recommends_action]->(a:KGNode)
                OPTIONAL MATCH (rs)-[:based_on_guideline|source_guideline]->(g:KGNode {entityType:'Guideline'})
                WITH rs,
                     count(DISTINCT e) AS evidence_count,
                     count(DISTINCT a) AS action_count,
                     count(DISTINCT g) AS guideline_count
                WHERE evidence_count=0 OR action_count=0 OR guideline_count=0
                RETURN rs.code AS recommendation_code,rs.name AS recommendation_name,
                       evidence_count,action_count,guideline_count
                ORDER BY rs.code
                LIMIT 100
                """
            ).data()
            checks["duplicate_semantic_relationships"] = session.run(
                """
                MATCH ()-[r]->()
                WHERE r.source_code IS NOT NULL AND r.target_code IS NOT NULL
                WITH r.source_code AS source_code, type(r) AS relation_type, r.target_code AS target_code,
                     count(r) AS count, collect(r.id)[..10] AS relation_ids
                WHERE count > 1
                RETURN source_code, relation_type, target_code, count, relation_ids
                ORDER BY count DESC, source_code
                LIMIT 100
                """
            ).data()
            checks["summary_counts"] = first_row(
                session,
                """
                CALL {
                  MATCH (n:KGNode)
                  RETURN count(n) AS node_count
                }
                CALL {
                  MATCH ()-[r]->()
                  RETURN count(r) AS relation_count
                }
                RETURN node_count, relation_count
                """,
            )
    metric_counts = {
        "non_kg_nodes": checks["non_kg_nodes"].get("count", 0),
        "empty_evidence_nodes": checks["empty_evidence_nodes"].get("count", 0),
        "required_lab_without_indicator_or_evidence": len(checks["required_lab_without_indicator_or_evidence"]),
        "indicator_without_evidence": len(checks["indicator_without_evidence"]),
        "diagnosis_criteria_without_component": len(checks["diagnosis_criteria_without_component"]),
        "differential_without_detail": len(checks["differential_without_detail"]),
        "recommendation_statement_missing_core": len(checks["recommendation_statement_missing_core"]),
        "duplicate_semantic_relationships": len(checks["duplicate_semantic_relationships"]),
    }
    checks["metric_counts"] = metric_counts
    checks["hard_gate_pass"] = all(value == 0 for value in metric_counts.values())
    return checks


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks = run()
    (OUT_DIR / "global_quality_audit.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# 心血管内科全库质量体检报告",
        "",
        "时间：2026-07-13 18:00:00",
        "",
        f"硬闸门：{'通过' if checks['hard_gate_pass'] else '未通过'}",
        "",
        "## 指标汇总",
        "",
        "| 指标 | 数量 |",
        "|---|---:|",
    ]
    for key, value in checks["metric_counts"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 本报告面向当前心血管内科 CDSS 图谱使用范围。",
            "- 若某项数量非 0，应先定位是否为历史数据、前端展示数据，还是当前新版流程新生成数据。",
        ]
    )
    (OUT_DIR / "全库质量体检报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "metric_counts": checks["metric_counts"], "hard_gate_pass": checks["hard_gate_pass"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
