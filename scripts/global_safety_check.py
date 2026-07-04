from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient, first_row


BLOCKING_METRICS = [
    "non_kgnode_node_count",
    "relation_touching_non_kgnode_count",
    "technical_display_name_error_count",
    "treatment_plan_actionability_error_count",
    "medication_class_without_specific_count",
    "duplicate_type_name_count",
    "duplicate_semantic_relation_count",
    "semantic_shell_relation_count",
]


COUNT_QUERIES = {
    "kg_node_count": "MATCH (n:KGNode) RETURN count(n) AS value",
    "kg_relation_count": "MATCH (:KGNode)-[r]->(:KGNode) RETURN count(r) AS value",
    "non_kgnode_node_count": "MATCH (n) WHERE NOT n:KGNode RETURN count(n) AS value",
    "relation_touching_non_kgnode_count": "MATCH (a)-[r]->(b) WHERE NOT a:KGNode OR NOT b:KGNode RETURN count(r) AS value",
    "technical_display_name_error_count": """
        MATCH (n:KGNode)
        WHERE NOT n.entityType IN ['Evidence','Guideline']
          AND (
            n.name = n.code OR n.preferred_name = n.code OR n.display_name = n.code
            OR n.name =~ '^[A-Z][A-Z0-9]+(-[A-Z0-9]+)+$'
            OR n.preferred_name =~ '^[A-Z][A-Z0-9]+(-[A-Z0-9]+)+$'
            OR n.display_name =~ '^[A-Z][A-Z0-9]+(-[A-Z0-9]+)+$'
          )
        RETURN count(n) AS value
    """,
    "treatment_plan_actionability_error_count": """
        MATCH (p:KGNode {entityType:'TreatmentPlan'})<-[:has_treatment_plan]-(:KGNode {entityType:'Disease'})
        WHERE NOT (p)-[:includes_medication|includes_procedure|has_timing|has_follow_up|has_clinical_pathway|has_indication|has_contraindication]->(:KGNode)
        RETURN count(DISTINCT p) AS value
    """,
    "medication_class_without_specific_count": """
        MATCH (m:KGNode {entityType:'Medication'})
        WHERE m.name IN [
          '抗凝药物','溶栓药物','抗血小板药物','硝酸酯类药物','醛固酮受体拮抗剂',
          'β受体阻滞剂','β受体拮抗剂','血管紧张素转换酶抑制剂','血管紧张素Ⅱ受体阻滞剂',
          '血管紧张素Ⅱ受体拮抗剂','钙通道阻滞剂','非二氢吡啶类钙通道阻滞剂',
          '他汀类药物','P2Y12受体抑制剂','利尿剂','洋地黄类药物',
          '袢利尿剂','盐皮质激素受体拮抗剂','血管紧张素受体脑啡肽酶抑制剂','钠-葡萄糖协同转运蛋白2抑制剂'
        ]
        AND NOT (m)-[:has_specific_medication]->(:KGNode {entityType:'Medication'})
        RETURN count(DISTINCT m) AS value
    """,
    "duplicate_type_name_count": """
        MATCH (n:KGNode)
        WITH n.entityType AS entity_type, n.name AS name, count(n) AS c
        WHERE entity_type IS NOT NULL AND name IS NOT NULL AND c > 1
        RETURN count(*) AS value
    """,
    "duplicate_semantic_relation_count": """
        MATCH (a:KGNode)-[r]->(b:KGNode)
        WITH a.code AS source_code, type(r) AS relation_type, b.code AS target_code, count(r) AS c
        WHERE c > 1
        RETURN count(*) AS value
    """,
    "semantic_shell_relation_count": """
        MATCH (:KGNode {entityType:'Disease'})-[r]->(n:KGNode)
        WHERE
          (n.entityType='DifferentialDiagnosis' AND n.name IN ['鉴别诊断','鉴别','除外','排除'])
          OR (n.entityType='DiagnosisCriteria' AND n.name IN ['诊断标准','诊断','确诊','诊断依据','临床诊断'])
          OR (n.entityType='TreatmentPlan' AND n.name IN ['治疗','治疗方案','治疗原则','一般治疗','药物治疗','非药物治疗'])
          OR (n.entityType='FollowUp' AND n.name IN ['随访','定期随访','随访方案','长期随访','复查'])
          OR (n.entityType='Prognosis' AND n.name IN ['预后','预后良好','预后不良','预后不佳'])
          OR (n.entityType='RiskStratification' AND n.name IN ['风险分层','危险分层','风险评估','评分','危险因素评估'])
        RETURN count(r) AS value
    """,
}

DETAIL_QUERIES = {
    "02_问题节点清单.csv": """
        MATCH (n)
        WHERE NOT n:KGNode
           OR (n:KGNode AND NOT n.entityType IN ['Evidence','Guideline'] AND (
                n.name = n.code OR n.preferred_name = n.code OR n.display_name = n.code
                OR n.name =~ '^[A-Z][A-Z0-9]+(-[A-Z0-9]+)+$'
                OR n.preferred_name =~ '^[A-Z][A-Z0-9]+(-[A-Z0-9]+)+$'
                OR n.display_name =~ '^[A-Z][A-Z0-9]+(-[A-Z0-9]+)+$'
           ))
        RETURN n.code AS code, n.name AS name, labels(n) AS labels, n.entityType AS entityType
        LIMIT 500
    """,
    "03_问题关系清单.csv": """
        MATCH (a)-[r]->(b)
        WHERE NOT a:KGNode OR NOT b:KGNode
        RETURN a.code AS source_code, type(r) AS relation_type, b.code AS target_code, r.id AS relation_id
        LIMIT 500
    """,
}


def summarize_gate(metrics: dict[str, int]) -> dict[str, Any]:
    blocking_items = [
        {"metric": metric, "count": int(metrics.get(metric, 0) or 0)}
        for metric in BLOCKING_METRICS
        if int(metrics.get(metric, 0) or 0) > 0
    ]
    return {
        **metrics,
        "blocking_issue_count": len(blocking_items),
        "blocking_items": blocking_items,
        "global_safety_gate_status": "passed" if not blocking_items else "failed",
    }


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    http = re.search(r"https?://[^\s，,；;]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s]+)", text, re.I)
    if not http or not password:
        raise ValueError(f"Cannot parse Neo4j HTTP/password from {path}")
    return {
        "uri": http.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    columns = result["results"][0]["columns"]
    return [
        {column: item["row"][index] for index, column in enumerate(columns)}
        for item in result["results"][0]["data"]
    ]


def write_rows(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in data for key in row.keys()}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)


def run_check(client: Neo4jHttpClient, output_dir: Path) -> dict[str, Any]:
    metrics: dict[str, int] = {}
    for name, query in COUNT_QUERIES.items():
        row = first_row(client.run(query))
        metrics[name] = int(row[0] or 0)
    summary = summarize_gate(metrics)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "01_服务器全库硬闸门_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    for filename, query in DETAIL_QUERIES.items():
        write_rows(output_dir / filename, rows(client.run(query)))
    write_rows(output_dir / "04_可自动修复清单.csv", [])
    blocking_rows = [
        {"metric": item["metric"], "count": item["count"], "reason": "全局硬闸门阻断"}
        for item in summary["blocking_items"]
    ]
    write_rows(output_dir / "05_禁止进入正式CDSS清单.csv", blocking_rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run global Neo4j safety gate check.")
    parser.add_argument("--connection-file", type=Path, default=Path("图谱数据库链接.txt"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    conn = parse_connection_file(args.connection_file)
    client = Neo4jHttpClient(conn["uri"], conn["username"], conn["password"], args.database, 5, 1)
    summary = run_check(client, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
