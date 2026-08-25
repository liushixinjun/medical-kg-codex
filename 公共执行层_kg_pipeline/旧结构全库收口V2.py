#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧实体、旧关系和错误方案结构的全库收口。

执行模式：
1. plan：只读盘点并生成迁移计划；
2. apply：校验全库备份后，在单一事务内迁移并执行硬闸门；
3. postcheck：只读执行入库后复核。

本脚本不从模型猜测临床事实。只有明确等价的新旧结构才自动迁移；错误类型
关系只删除关系并保留实体、原文证据和指南来源。事务内任一硬闸门失败时，
Neo4j 自动回滚本轮全部写操作。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from neo4j import GraphDatabase, READ_ACCESS


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    ROOT / "项目管理中心_project_management" / "145_旧结构全库收口_20260719"
)
BATCH_ID = "20260719_旧结构全库收口V2"
SCHEMA_VERSION = "V2.4"

LEGACY_ENTITY_TYPES = ["Exam", "LabTest", "ExamIndicator", "DiseaseClassification"]
LEGACY_RELATION_TYPES = [
    "requires_exam",
    "requires_lab_test",
    "treated_by_medication",
    "treated_by_procedure",
    "exam_has_indicator",
    "lab_test_has_indicator",
    "has_recommended_action",
    "has_treatment_component",
]
ACTION_TYPES = ["ExamItem", "LabItem", "Medication", "Procedure", "TreatmentItem", "FollowUp"]
ASSESSMENT_TYPES = [
    "DiagnosisCriteria",
    "RiskStratification",
    "DifferentialDiagnosis",
    "RiskFactor",
    "Complication",
    "ExamObservation",
    "LabSubitem",
    "Etiology",
]
RECOMMEND_SOURCE_TYPES = ["ClinicalRule", "RecommendationStatement"]
ASSESSMENT_SOURCE_TYPES = ["ClinicalRule", "RecommendationStatement"]
BLOCK_SOURCE_TYPES = [
    "ClinicalRule",
    "RecommendationStatement",
    "Contraindication",
]

# 只处理能够从疾病归属和临床语义明确判定的历史跨病种污染。
PLAN_SCOPE_RULES = [
    {
        "plan_code": "PLAN-CARD-TEXT-7CC38FBA6F",
        "plan_name": "复律治疗",
        "allowed_prefixes": ["DIS-CARD-ARR-", "DIS-CARD-SCD-"],
        "allowed_codes": [],
    },
    {
        "plan_code": "PLAN-CARD-TEXT-EEF9C97B59",
        "plan_name": "血运重建",
        "allowed_prefixes": ["DIS-CARD-CAD-"],
        "allowed_codes": ["DIS-CARD-HT-RENOVASCULAR"],
    },
    {
        "plan_code": "PLAN-CARD-FULLBOOK-B87D3F557B",
        "plan_name": "溶栓治疗",
        "allowed_prefixes": [],
        "allowed_codes": ["DIS-CARD-CAD-STEMI", "DIS-CARD-VTE"],
    },
    {
        "plan_code": "PLAN-CARD-BDE62A3BE028",
        "plan_name": "降压治疗",
        "allowed_prefixes": ["DIS-CARD-HT-", "DIS-CARD-HTN-"],
        "allowed_codes": ["DIS-CARD-HT"],
    },
    {
        "plan_code": "PLAN-CARD-A1C4E6332D38",
        "plan_name": "抗凝治疗",
        "allowed_prefixes": [],
        "allowed_codes": [
            "DIS-CARD-ARR-AF",
            "DIS-CARD-ARR-AFL",
            "DIS-CARD-VTE",
            "DIS-CARD-CAD-ACS",
            "DIS-CARD-CAD-UA",
            "DIS-CARD-CAD-AMI",
            "DIS-CARD-CAD-STEMI",
            "DIS-CARD-CAD-NSTEMI",
        ],
    },
    {
        "plan_code": "PLAN-CARD-3972CBC8228B",
        "plan_name": "再灌注治疗",
        "allowed_prefixes": [],
        "allowed_codes": ["DIS-CARD-CAD-STEMI"],
    },
]

CATEGORY_DISEASE_MAP = [
    {"category_code": "CAT-CARD-NEUROSIS", "disease_code": "DIS-CARD-NEUROSIS"},
    {"category_code": "CAT-CARD-IE", "disease_code": "DIS-CARD-INFECTIVE-ENDOCARDITIS"},
]


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    bolt = re.search(r"(?:bolt|neo4j)(?:\+ssc|\+s)?://[^\s，,；;]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    if not bolt or not password:
        raise ValueError(f"无法从连接文件解析 Bolt 地址或密码：{path}")
    return {
        "uri": bolt.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    iso_format = getattr(value, "iso_format", None)
    if callable(iso_format):
        return iso_format()
    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row)) or ["说明"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows or [{"说明": "无"}])


def query_rows(runner: Any, cypher: str, **parameters: Any) -> list[dict[str, Any]]:
    return [dict(record) for record in runner.run(cypher, **parameters)]


def query_count(runner: Any, cypher: str, **parameters: Any) -> int:
    record = runner.run(cypher, **parameters).single(strict=True)
    return int(record["amount"])


def run_write(tx: Any, name: str, cypher: str, **parameters: Any) -> dict[str, Any]:
    result = tx.run(cypher, **parameters)
    rows = [dict(record) for record in result]
    summary = result.consume()
    counters = summary.counters
    return {
        "步骤": name,
        "返回": rows,
        "新增节点": counters.nodes_created,
        "删除节点": counters.nodes_deleted,
        "新增关系": counters.relationships_created,
        "删除关系": counters.relationships_deleted,
        "属性更新": counters.properties_set,
        "新增标签": counters.labels_added,
        "删除标签": counters.labels_removed,
    }


def inventory(runner: Any) -> dict[str, Any]:
    return {
        "节点总数": query_count(runner, "MATCH (n) RETURN count(n) AS amount"),
        "关系总数": query_count(runner, "MATCH ()-[r]->() RETURN count(r) AS amount"),
        "旧实体": query_rows(
            runner,
            """
            MATCH (n)
            WHERE n.entityType IN $types OR
                  (n:Exam AND n.entityType IS NULL) OR
                  (n:LabTest AND n.entityType IS NULL) OR
                  (n:ExamIndicator AND n.entityType IS NULL)
            RETURN coalesce(n.entityType, head([x IN labels(n) WHERE x <> 'KGNode'])) AS 类型,
                   count(*) AS 数量
            ORDER BY 类型
            """,
            types=LEGACY_ENTITY_TYPES,
        ),
        "旧关系": query_rows(
            runner,
            """
            MATCH ()-[r]->()
            WHERE type(r) IN $types
            RETURN type(r) AS 关系, count(*) AS 数量
            ORDER BY 数量 DESC
            """,
            types=LEGACY_RELATION_TYPES,
        ),
        "错误正式推荐终点": query_rows(
            runner,
            """
            MATCH (s)-[r:recommends_action|blocks_action|recommends_assessment]->(t)
            WHERE (type(r) IN ['recommends_action','blocks_action'] AND
                   NOT t.entityType IN $action_types) OR
                  (type(r)='recommends_assessment' AND
                   NOT t.entityType IN $assessment_types) OR
                  (type(r)='recommends_action' AND NOT s.entityType IN $recommend_sources) OR
                  (type(r)='recommends_assessment' AND NOT s.entityType IN $assessment_sources) OR
                  (type(r)='blocks_action' AND NOT s.entityType IN $block_sources)
            RETURN s.entityType AS 起点类型, type(r) AS 关系,
                   t.entityType AS 终点类型, count(*) AS 数量
            ORDER BY 数量 DESC
            """,
            action_types=ACTION_TYPES,
            assessment_types=ASSESSMENT_TYPES,
            recommend_sources=RECOMMEND_SOURCE_TYPES,
            assessment_sources=ASSESSMENT_SOURCE_TYPES,
            block_sources=BLOCK_SOURCE_TYPES,
        ),
        "目录层错误挂载": query_rows(
            runner,
            """
            MATCH (c)-[r]->(x)
            WHERE c.entityType IN ['DiseaseCategory','DiseaseSubcategory'] AND
                  type(r) IN ['has_exam_plan','has_treatment_plan','requires_exam',
                              'requires_lab_test','treated_by_medication',
                              'treated_by_procedure','has_recommended_action',
                              'recommends_action','recommends_assessment','blocks_action']
            RETURN c.entityType AS 起点类型, type(r) AS 关系,
                   x.entityType AS 终点类型, count(*) AS 数量
            ORDER BY 数量 DESC
            """,
        ),
        "方案套方案": query_count(
            runner,
            "MATCH (:TreatmentPlan)-[r:has_treatment_component]->(:TreatmentPlan) "
            "RETURN count(r) AS amount",
        ),
        "空辅助检查方案": query_count(
            runner,
            """
            MATCH (p:ExamPlan)
            WHERE NOT (p)-[:includes_exam_item|includes_lab_item]->()
            RETURN count(p) AS amount
            """,
        ),
        "空治疗方案": query_count(
            runner,
            """
            MATCH (p:TreatmentPlan)
            WHERE NOT (p)-[:includes_medication|includes_procedure|includes_treatment_item]->()
            RETURN count(p) AS amount
            """,
        ),
        "待删除跨病种错误方案关系": query_rows(
            runner,
            """
            UNWIND $rules AS rule
            MATCH (d:Disease)-[:has_treatment_plan]->(p:TreatmentPlan {code: rule.plan_code})
            WHERE NOT d.code IN rule.allowed_codes AND
                  NOT any(prefix IN rule.allowed_prefixes WHERE d.code STARTS WITH prefix)
            RETURN p.code AS 方案编码, p.name AS 方案名称,
                   d.code AS 疾病编码, d.name AS 疾病名称
            ORDER BY 方案名称, 疾病名称
            """,
            rules=PLAN_SCOPE_RULES,
        ),
        "待物理删除失效孤立节点": query_rows(
            runner,
            """
            MATCH (n)
            WHERE n.status='deprecated' AND NOT (n)--()
            RETURN n.entityType AS 实体类型, n.code AS 编码, n.name AS 名称
            ORDER BY 实体类型, 名称
            """,
        ),
    }


def verify_backup(output_dir: Path, expected: dict[str, Any]) -> dict[str, Any]:
    path = output_dir / "00_升级前全库备份" / "备份清单_manifest.json"
    if not path.exists():
        raise RuntimeError(f"缺少完整全库备份清单：{path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not manifest.get("count_consistent"):
        raise RuntimeError("全库备份前后数量不一致，禁止写库")
    exported = manifest.get("exported", {})
    if int(exported.get("nodes", -1)) != int(expected["节点总数"]):
        raise RuntimeError("备份节点数与当前写库前基线不一致，禁止写库")
    if int(exported.get("relationships", -1)) != int(expected["关系总数"]):
        raise RuntimeError("备份关系数与当前写库前基线不一致，禁止写库")
    return manifest


def _migration_plan_code(disease_code: str) -> str:
    digest = hashlib.sha256(disease_code.encode("utf-8")).hexdigest()[:12].upper()
    return f"PLAN-MIG-{digest}"


def build_direct_action_assignments(runner: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = query_rows(
        runner,
        """
        MATCH (d:Disease)-[old:treated_by_medication|treated_by_procedure]->(a)
        WHERE NOT EXISTS {
          MATCH (d)-[:has_treatment_plan]->(:TreatmentPlan)
                -[:includes_medication|includes_procedure]->(a)
        }
        OPTIONAL MATCH (d)-[:has_treatment_plan]->(p:TreatmentPlan)
        OPTIONAL MATCH (other:Disease)-[:has_treatment_plan]->(p)
        OPTIONAL MATCH (p)-[inc:includes_medication|includes_procedure]->()
        WITH d, a, type(old) AS old_relation, p,
             count(DISTINCT other) AS disease_count,
             count(DISTINCT inc) AS action_count
        ORDER BY CASE WHEN p.name = d.name + '治疗方案' THEN 3
                      WHEN disease_count = 1 AND p.name CONTAINS d.name THEN 2
                      WHEN disease_count = 1 THEN 1 ELSE 0 END DESC,
                 action_count DESC, p.code
        WITH d, a, old_relation,
             collect(CASE WHEN p IS NULL THEN null ELSE {
               code:p.code, name:p.name, disease_count:disease_count
             } END) AS candidates
        RETURN d.code AS disease_code, d.name AS disease_name,
               a.code AS action_code, a.entityType AS action_type,
               old_relation, candidates
        ORDER BY disease_code, action_type, action_code
        """,
    )
    plans: dict[str, dict[str, Any]] = {}
    assignments: list[dict[str, Any]] = []
    for row in rows:
        candidates = [item for item in (row.get("candidates") or []) if item]
        selected = next(
            (
                item
                for item in candidates
                if item.get("name") == f"{row['disease_name']}治疗方案"
            ),
            None,
        )
        if selected is None:
            selected = next(
                (
                    item
                    for item in candidates
                    if int(item.get("disease_count") or 0) == 1
                    and row["disease_name"] in str(item.get("name") or "")
                ),
                None,
            )
        if selected is None:
            selected = next(
                (item for item in candidates if int(item.get("disease_count") or 0) == 1),
                None,
            )
        if selected is None:
            code = _migration_plan_code(str(row["disease_code"]))
            selected = {"code": code, "name": f"{row['disease_name']}治疗方案"}
            plans[code] = {
                "disease_code": row["disease_code"],
                "plan_code": code,
                "plan_name": selected["name"],
            }
        assignments.append(
            {
                "disease_code": row["disease_code"],
                "plan_code": selected["code"],
                "action_code": row["action_code"],
                "action_type": row["action_type"],
                "old_relation": row["old_relation"],
            }
        )
    return list(plans.values()), assignments


def execute_migration(tx: Any, new_plans: list[dict[str, Any]], assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    common = {"batch_id": BATCH_ID, "schema_version": SCHEMA_VERSION, "now": now}

    results.append(run_write(tx, "目录层检查/检验关系转移到对应疾病", """
        UNWIND $mappings AS item
        MATCH (c:DiseaseCategory {code:item.category_code})
        MATCH (d:Disease {code:item.disease_code})
        MATCH (c)-[r:requires_exam|requires_lab_test]->(x)
        CALL {
          WITH d, r, x
          WITH d, r, x WHERE type(r)='requires_exam'
          MERGE (d)-[nr:requires_exam]->(x)
          SET nr += properties(r), nr.migration_batch=$batch_id
          RETURN count(*) AS moved
          UNION
          WITH d, r, x
          WITH d, r, x WHERE type(r)='requires_lab_test'
          MERGE (d)-[nr:requires_lab_test]->(x)
          SET nr += properties(r), nr.migration_batch=$batch_id
          RETURN count(*) AS moved
        }
        DELETE r
        RETURN sum(moved) AS 数量
    """, mappings=CATEGORY_DISEASE_MAP, **common))

    results.append(run_write(tx, "感染性心内膜炎错误方案片段转回疾病证据", """
        MATCH (:DiseaseCategory {code:'CAT-CARD-IE'})-[:has_treatment_plan]->(bad:TreatmentPlan)
        MATCH (d:Disease {code:'DIS-CARD-INFECTIVE-ENDOCARDITIS'})
        OPTIONAL MATCH (bad)-[:supported_by_evidence]->(e:Evidence)
        FOREACH (_ IN CASE WHEN e IS NULL THEN [] ELSE [1] END |
          MERGE (d)-[:supported_by_evidence]->(e)
        )
        WITH DISTINCT bad
        DETACH DELETE bad
        RETURN count(*) AS 数量
    """, **common))

    results.append(run_write(tx, "心血管神经症句子片段归并为一项方案", """
        MATCH (d:Disease {code:'DIS-CARD-NEUROSIS'})
        MERGE (plan:KGNode:TreatmentPlan {code:'PLAN-CARD-NEUROSIS-COMPREHENSIVE'})
        SET plan.entityType='TreatmentPlan', plan.name='心血管神经症综合治疗方案',
            plan.description='以心理与行为干预为主，必要时结合药物治疗；具体推荐须由患者场景规则触发。',
            plan.formal_cdss_ready=false, plan.schema_version=$schema_version,
            plan.migration_batch=$batch_id, plan.updated_at=$now
        MERGE (action:KGNode:TreatmentItem {code:'TRT-CARD-NEUROSIS-PSYCHOTHERAPY'})
        SET action.entityType='TreatmentItem', action.name='心理与行为干预',
            action.orderable=false, action.formal_cdss_ready=false,
            action.schema_version=$schema_version, action.migration_batch=$batch_id,
            action.updated_at=$now
        MERGE (d)-[:has_treatment_plan]->(plan)
        MERGE (plan)-[:includes_treatment_item]->(action)
        WITH d,plan,action
        OPTIONAL MATCH (:DiseaseCategory {code:'CAT-CARD-NEUROSIS'})
                       -[:has_treatment_plan]->(bad:TreatmentPlan)
        OPTIONAL MATCH (bad)-[:supported_by_evidence]->(e:Evidence)
        FOREACH (_ IN CASE WHEN e IS NULL THEN [] ELSE [1] END |
          MERGE (plan)-[:supported_by_evidence]->(e)
        )
        WITH plan,action,collect(DISTINCT bad) AS bad_nodes
        FOREACH (bad IN bad_nodes | DETACH DELETE bad)
        RETURN size(bad_nodes) AS 数量
    """, **common))

    results.append(run_write(tx, "检查实体迁移为检查项目", """
        MATCH (n)
        WHERE n.entityType='Exam' OR (n:Exam AND n.entityType IS NULL)
        SET n:KGNode:ExamItem, n.entityType='ExamItem', n.schema_version=$schema_version,
            n.migration_batch=$batch_id, n.updated_at=$now
        REMOVE n:Exam
        RETURN count(n) AS 数量
    """, **common))
    results.append(run_write(tx, "检验实体迁移为检验项目", """
        MATCH (n)
        WHERE n.entityType='LabTest' OR (n:LabTest AND n.entityType IS NULL)
        SET n:KGNode:LabItem, n.entityType='LabItem', n.schema_version=$schema_version,
            n.migration_batch=$batch_id, n.updated_at=$now
        REMOVE n:LabTest
        RETURN count(n) AS 数量
    """, **common))
    results.append(run_write(tx, "检验指标迁移为检验细项", """
        MATCH (i)
        WHERE (i.entityType='ExamIndicator' OR (i:ExamIndicator AND i.entityType IS NULL))
          AND ()-[:lab_test_has_indicator]->(i)
          AND NOT ()-[:exam_has_indicator]->(i)
        SET i:KGNode:LabSubitem, i.entityType='LabSubitem', i.schema_version=$schema_version,
            i.migration_batch=$batch_id, i.updated_at=$now
        REMOVE i:ExamIndicator
        RETURN count(i) AS 数量
    """, **common))
    results.append(run_write(tx, "其余检查指标迁移为检查发现", """
        MATCH (i)
        WHERE i.entityType='ExamIndicator' OR (i:ExamIndicator AND i.entityType IS NULL)
        SET i:KGNode:ExamObservation, i.entityType='ExamObservation',
            i.schema_version=$schema_version, i.migration_batch=$batch_id,
            i.updated_at=$now
        REMOVE i:ExamIndicator
        RETURN count(i) AS 数量
    """, **common))

    results.append(run_write(tx, "检查项目与检查发现关系迁移", """
        MATCH (item)-[r:exam_has_indicator]->(observation)
        MERGE (item)-[nr:exam_item_has_observation]->(observation)
        SET nr += properties(r), nr.migration_batch=$batch_id
        DELETE r
        RETURN count(*) AS 数量
    """, **common))
    results.append(run_write(tx, "检验项目与检验细项关系迁移", """
        MATCH (item)-[r:lab_test_has_indicator]->(subitem)
        MERGE (item)-[nr:lab_item_has_subitem]->(subitem)
        SET nr += properties(r), nr.migration_batch=$batch_id
        DELETE r
        RETURN count(*) AS 数量
    """, **common))

    for target_type, old_relation, new_relation in [
        ("ExamItem", "requires_exam", "includes_exam_item"),
        ("LabItem", "requires_exam", "includes_lab_item"),
        ("LabItem", "requires_lab_test", "includes_lab_item"),
    ]:
        results.append(run_write(tx, f"疾病{old_relation}迁移到辅助检查方案/{target_type}", f"""
            MATCH (d:Disease)-[old:{old_relation}]->(item)
            WHERE item.entityType=$target_type
            MERGE (plan:KGNode:ExamPlan {{code:'EXAMPLAN-MIG-' + d.code}})
            ON CREATE SET plan.entityType='ExamPlan', plan.name=d.name + '辅助检查方案',
                          plan.formal_cdss_ready=false, plan.created_at=$now
            SET plan.schema_version=$schema_version, plan.migration_batch=$batch_id,
                plan.updated_at=$now
            MERGE (d)-[:has_exam_plan]->(plan)
            MERGE (plan)-[nr:{new_relation}]->(item)
            SET nr += properties(old), nr.migration_batch=$batch_id
            DELETE old
            RETURN count(*) AS 数量
        """, target_type=target_type, **common))

    results.append(run_write(tx, "疾病直连检查发现/检验细项回溯到所属项目", """
        MATCH (d:Disease)-[old:requires_exam]->(detail)
        WHERE detail.entityType IN ['ExamObservation','LabSubitem']
        MATCH (item)-[:exam_item_has_observation|lab_item_has_subitem]->(detail)
        MERGE (plan:KGNode:ExamPlan {code:'EXAMPLAN-MIG-' + d.code})
        ON CREATE SET plan.entityType='ExamPlan', plan.name=d.name + '辅助检查方案',
                      plan.formal_cdss_ready=false, plan.created_at=$now
        SET plan.schema_version=$schema_version, plan.migration_batch=$batch_id,
            plan.updated_at=$now
        MERGE (d)-[:has_exam_plan]->(plan)
        FOREACH (_ IN CASE WHEN item.entityType='ExamItem' THEN [1] ELSE [] END |
          MERGE (plan)-[:includes_exam_item]->(item)
        )
        FOREACH (_ IN CASE WHEN item.entityType='LabItem' THEN [1] ELSE [] END |
          MERGE (plan)-[:includes_lab_item]->(item)
        )
        DELETE old
        RETURN count(*) AS 数量
    """, **common))

    results.append(run_write(tx, "来源章节旧检查/检验直连关系清除", """
        MATCH (:SourceSection)-[r:requires_exam|requires_lab_test]->()
        DELETE r
        RETURN count(*) AS 数量
    """, **common))
    results.append(run_write(tx, "其余无法形成合法方案的旧检查关系清除", """
        MATCH ()-[r:requires_exam|requires_lab_test]->()
        DELETE r
        RETURN count(*) AS 数量
    """, **common))

    results.append(run_write(tx, "可执行子方案直接挂到疾病", """
        MATCH (d:Disease)-[:has_treatment_plan]->(parent:TreatmentPlan)
              -[:has_treatment_component]->(child:TreatmentPlan)
        WHERE (child)-[:includes_medication|includes_procedure]->()
        MERGE (d)-[:has_treatment_plan]->(child)
        RETURN count(*) AS 数量
    """, **common))
    for relation in ["includes_medication", "includes_procedure"]:
        results.append(run_write(tx, f"总方案展开子方案动作/{relation}", f"""
            MATCH (parent:TreatmentPlan)-[:has_treatment_component]->(child:TreatmentPlan)
                  -[:{relation}]->(action)
            MERGE (parent)-[:{relation}]->(action)
            RETURN count(*) AS 数量
        """, **common))

    results.append(run_write(tx, "诱因纠正子方案转换为治疗项目", """
        MATCH (parent:TreatmentPlan)-[:has_treatment_component]->(child:TreatmentPlan {name:'诱因纠正'})
        MERGE (action:KGNode:TreatmentItem {code:'TRT-CARD-CORRECT-REVERSIBLE-CAUSES'})
        SET action.entityType='TreatmentItem', action.name='纠正可逆诱因',
            action.orderable=false, action.formal_cdss_ready=false,
            action.schema_version=$schema_version, action.migration_batch=$batch_id,
            action.updated_at=$now
        MERGE (parent)-[:includes_treatment_item]->(action)
        WITH DISTINCT parent,child,action
        OPTIONAL MATCH (child)-[:supported_by_evidence]->(e:Evidence)
        FOREACH (_ IN CASE WHEN e IS NULL THEN [] ELSE [1] END |
          MERGE (parent)-[:supported_by_evidence]->(e)
          MERGE (action)-[:supported_by_evidence]->(e)
        )
        WITH collect(DISTINCT child) AS children
        FOREACH (child IN children | DETACH DELETE child)
        RETURN size(children) AS 数量
    """, **common))

    results.append(run_write(tx, "观察随访子方案转换为随访实体", """
        MATCH (d:Disease)-[:has_treatment_plan]->(parent:TreatmentPlan)
              -[:has_treatment_component]->(child:TreatmentPlan {name:'观察随访'})
        MERGE (followup:KGNode:FollowUp {code:'FOLLOWUP-CARD-OBSERVATION'})
        SET followup.entityType='FollowUp', followup.name='观察随访',
            followup.formal_cdss_ready=false, followup.schema_version=$schema_version,
            followup.migration_batch=$batch_id, followup.updated_at=$now
        MERGE (d)-[:has_follow_up]->(followup)
        WITH DISTINCT child,followup
        OPTIONAL MATCH (child)-[:supported_by_evidence]->(e:Evidence)
        FOREACH (_ IN CASE WHEN e IS NULL THEN [] ELSE [1] END |
          MERGE (followup)-[:supported_by_evidence]->(e)
        )
        WITH collect(DISTINCT child) AS children
        FOREACH (child IN children | DETACH DELETE child)
        RETURN size(children) AS 数量
    """, **common))

    results.append(run_write(tx, "残余方案套方案关系清除", """
        MATCH (:TreatmentPlan)-[r:has_treatment_component]->(:TreatmentPlan)
        DELETE r
        RETURN count(*) AS 数量
    """, **common))

    results.append(run_write(tx, "创建历史直连动作承接方案", """
        UNWIND $plans AS item
        MATCH (d:Disease {code:item.disease_code})
        MERGE (plan:KGNode:TreatmentPlan {code:item.plan_code})
        ON CREATE SET plan.entityType='TreatmentPlan', plan.name=item.plan_name,
                      plan.formal_cdss_ready=false, plan.created_at=$now
        SET plan.schema_version=$schema_version, plan.migration_batch=$batch_id,
            plan.updated_at=$now
        MERGE (d)-[:has_treatment_plan]->(plan)
        RETURN count(*) AS 数量
    """, plans=new_plans, **common))
    for action_type, relation in [("Medication", "includes_medication"), ("Procedure", "includes_procedure")]:
        results.append(run_write(tx, f"历史直连动作纳入方案/{action_type}", f"""
            UNWIND $assignments AS item
            WITH item WHERE item.action_type=$action_type
            MATCH (plan:TreatmentPlan {{code:item.plan_code}})
            MATCH (action {{code:item.action_code, entityType:$action_type}})
            MERGE (plan)-[r:{relation}]->(action)
            SET r.migration_batch=$batch_id, r.legacy_relation=item.old_relation,
                r.formal_cdss_ready=false
            RETURN count(*) AS 数量
        """, assignments=assignments, action_type=action_type, **common))

    results.append(run_write(tx, "疾病直连药品/手术旧关系清除", """
        MATCH (:Disease)-[r:treated_by_medication|treated_by_procedure]->()
        DELETE r
        RETURN count(*) AS 数量
    """, **common))

    results.append(run_write(tx, "阶段旧候选动作关系迁移", """
        MATCH (stage:PathwayStage)-[old:has_recommended_action]->(action)
        WHERE action.entityType IN $action_types
        MERGE (stage)-[nr:stage_has_available_action]->(action)
        SET nr += properties(old), nr.migration_batch=$batch_id
        DELETE old
        RETURN count(*) AS 数量
    """, action_types=ACTION_TYPES, **common))
    results.append(run_write(tx, "阶段旧方案候选展开为具体动作", """
        MATCH (stage:PathwayStage)-[old:has_recommended_action]->(plan:TreatmentPlan)
              -[:includes_medication|includes_procedure|includes_treatment_item]->(action)
        WHERE action.entityType IN $action_types
        MERGE (stage)-[nr:stage_has_available_action]->(action)
        SET nr += properties(old), nr.migration_batch=$batch_id
        WITH DISTINCT old
        DELETE old
        RETURN count(*) AS 数量
    """, action_types=ACTION_TYPES, **common))
    results.append(run_write(tx, "规则旧候选动作迁移为规则动作", """
        MATCH (rule:ClinicalRule)-[old:has_recommended_action]->(action)
        WHERE action.entityType IN $action_types
        MERGE (rule)-[nr:recommends_action]->(action)
        SET nr += properties(old), nr.migration_batch=$batch_id,
            nr.legacy_unverified=true
        DELETE old
        RETURN count(*) AS 数量
    """, action_types=ACTION_TYPES, **common))
    results.append(run_write(tx, "规则旧方案推荐展开为具体动作", """
        MATCH (rule:ClinicalRule)-[old:has_recommended_action]->(plan:TreatmentPlan)
              -[:includes_medication|includes_procedure|includes_treatment_item]->(action)
        WHERE action.entityType IN $action_types
        MERGE (rule)-[nr:recommends_action]->(action)
        SET nr += properties(old), nr.migration_batch=$batch_id,
            nr.legacy_unverified=true
        WITH DISTINCT old
        DELETE old
        RETURN count(*) AS 数量
    """, action_types=ACTION_TYPES, **common))
    results.append(run_write(tx, "非动作旧推荐关系清除", """
        MATCH ()-[r:has_recommended_action]->()
        DELETE r
        RETURN count(*) AS 数量
    """, **common))

    results.append(run_write(tx, "路径阶段不得直接形成正式推荐", """
        MATCH (stage:PathwayStage)-[old:recommends_action]->(action)
        WHERE action.entityType IN $action_types
        MERGE (stage)-[nr:stage_has_available_action]->(action)
        SET nr += properties(old), nr.migration_batch=$batch_id
        DELETE old
        RETURN count(*) AS 数量
    """, action_types=ACTION_TYPES, **common))
    for relation, source_types in [
        ("recommends_action", RECOMMEND_SOURCE_TYPES),
        ("blocks_action", BLOCK_SOURCE_TYPES),
    ]:
        for source_type in source_types:
            results.append(run_write(tx, f"{source_type}方案终点展开/{relation}", f"""
                MATCH (source:{source_type})-[old:{relation}]->(plan:TreatmentPlan)
                      -[:includes_medication|includes_procedure|includes_treatment_item]->(action)
                WHERE action.entityType IN $action_types
                MERGE (source)-[nr:{relation}]->(action)
                SET nr += properties(old), nr.migration_batch=$batch_id
                WITH DISTINCT old
                DELETE old
                RETURN count(*) AS 数量
            """, action_types=ACTION_TYPES, **common))

    results.append(run_write(tx, "错误正式推荐终点关系清除", """
        MATCH (source)-[r:recommends_action|blocks_action]->(target)
        WHERE NOT target.entityType IN $action_types OR
              (type(r)='recommends_action' AND NOT source.entityType IN $recommend_sources) OR
              (type(r)='blocks_action' AND NOT source.entityType IN $block_sources)
        DELETE r
        RETURN count(*) AS 数量
    """, action_types=ACTION_TYPES, recommend_sources=RECOMMEND_SOURCE_TYPES,
         block_sources=BLOCK_SOURCE_TYPES, **common))

    results.append(run_write(tx, "跨病种错误治疗方案关系清除", """
        UNWIND $rules AS rule
        MATCH (d:Disease)-[r:has_treatment_plan]->(p:TreatmentPlan {code:rule.plan_code})
        WHERE NOT d.code IN rule.allowed_codes AND
              NOT any(prefix IN rule.allowed_prefixes WHERE d.code STARTS WITH prefix)
        DELETE r
        RETURN count(*) AS 数量
    """, rules=PLAN_SCOPE_RULES, **common))

    results.append(run_write(tx, "空治疗方案证据回收到上游知识实体", """
        MATCH (source)-[]->(plan:TreatmentPlan)-[:supported_by_evidence]->(e:Evidence)
        WHERE NOT (plan)-[:includes_medication|includes_procedure|includes_treatment_item]->()
          AND source.entityType <> 'Evidence'
        MERGE (source)-[:supported_by_evidence]->(e)
        RETURN count(*) AS 数量
    """, **common))
    results.append(run_write(tx, "空治疗方案物理删除", """
        MATCH (plan:TreatmentPlan)
        WHERE NOT (plan)-[:includes_medication|includes_procedure|includes_treatment_item]->()
        DETACH DELETE plan
        RETURN count(*) AS 数量
    """, **common))
    results.append(run_write(tx, "空辅助检查方案物理删除", """
        MATCH (plan:ExamPlan)
        WHERE NOT (plan)-[:includes_exam_item|includes_lab_item]->()
        DETACH DELETE plan
        RETURN count(*) AS 数量
    """, **common))
    results.append(run_write(tx, "失效且孤立节点物理删除", """
        MATCH (n)
        WHERE n.status='deprecated' AND NOT (n)--()
        DELETE n
        RETURN count(*) AS 数量
    """, **common))

    # 旧关系或旧“方案终点”只能迁移为阶段候选菜单，不能批量制造正式推荐。
    # 前面的展开用于保持事务内可追踪映射，此处立即收敛并删除误展开边。
    results.extend(compact_generated_recommendations(tx))

    # 事务提交前硬闸门；任一指标不为 0 即抛错并回滚。
    post = inventory(tx)
    blockers = {
        "旧实体": sum(int(row["数量"]) for row in post["旧实体"]),
        "旧关系": sum(int(row["数量"]) for row in post["旧关系"]),
        "错误正式推荐终点": sum(int(row["数量"]) for row in post["错误正式推荐终点"]),
        "目录层错误挂载": sum(int(row["数量"]) for row in post["目录层错误挂载"]),
        "方案套方案": int(post["方案套方案"]),
        "空辅助检查方案": int(post["空辅助检查方案"]),
        "空治疗方案": int(post["空治疗方案"]),
        "待删除跨病种错误方案关系": len(post["待删除跨病种错误方案关系"]),
    }
    failed = {key: value for key, value in blockers.items() if value != 0}
    if failed:
        raise RuntimeError(f"事务内硬闸门未通过，已触发回滚：{failed}")
    results.append({"步骤": "事务内硬闸门", "结果": "通过", "指标": blockers})
    return results


def compact_generated_recommendations(tx: Any) -> list[dict[str, Any]]:
    """回收本批次从旧方案批量展开的关系，防止推荐关系爆炸。"""
    results: list[dict[str, Any]] = []
    results.append(run_write(tx, "旧规则动作收敛为阶段可选动作", """
        MATCH (stage:PathwayStage)-[:has_stage_rule|has_clinical_rule]->(rule:ClinicalRule)
              -[r:recommends_action]->(action)
        WHERE r.migration_batch=$batch_id
        MERGE (stage)-[candidate:stage_has_available_action]->(action)
        SET candidate.migration_batch=$batch_id,
            candidate.source_kind='legacy_rule_candidate',
            candidate.formal_cdss_ready=false
        RETURN count(DISTINCT [elementId(stage),elementId(action)]) AS 数量
    """, batch_id=BATCH_ID))
    results.append(run_write(tx, "旧推荐陈述动作收敛为阶段可选动作", """
        MATCH (stage:PathwayStage)-[:has_stage_rule|has_clinical_rule]->(rule:ClinicalRule)
              -[:has_recommendation_statement]->(statement:RecommendationStatement)
              -[r:recommends_action]->(action)
        WHERE r.migration_batch=$batch_id
        MERGE (stage)-[candidate:stage_has_available_action]->(action)
        SET candidate.migration_batch=$batch_id,
            candidate.source_kind='legacy_statement_candidate',
            candidate.formal_cdss_ready=false
        RETURN count(DISTINCT [elementId(stage),elementId(action)]) AS 数量
    """, batch_id=BATCH_ID))
    results.append(run_write(tx, "旧方案展开来源标记为不可正式推荐", """
        MATCH (source)-[r:recommends_action|blocks_action]->()
        WHERE r.migration_batch=$batch_id
        SET source.formal_cdss_ready=false,
            source.clinical_review_status='blocked',
            source.migration_block_reason='旧方案关系不能自动展开为正式推荐，需回到原文抽取具体动作',
            source.updated_at=$now
        RETURN count(DISTINCT source) AS 数量
    """, batch_id=BATCH_ID, now=datetime.now(timezone.utc).isoformat()))
    results.append(run_write(tx, "回收批量误展开的正式推荐/阻断关系", """
        MATCH ()-[r:recommends_action|blocks_action]->()
        WHERE r.migration_batch=$batch_id
        DELETE r
        RETURN count(*) AS 数量
    """, batch_id=BATCH_ID))
    remaining = query_count(
        tx,
        """
        MATCH ()-[r:recommends_action|blocks_action]->()
        WHERE r.migration_batch=$batch_id
        RETURN count(r) AS amount
        """,
        batch_id=BATCH_ID,
    )
    if remaining:
        raise RuntimeError(f"仍有 {remaining} 条批量误展开关系，触发事务回滚")
    return results


def normalize_formal_recommendation_chain(tx: Any) -> list[dict[str, Any]]:
    """统一正式推荐链路：来源裁决只裁决来源，推荐陈述承接推荐目标。"""
    now = datetime.now(timezone.utc).isoformat()
    common = {"batch_id": BATCH_ID, "schema_version": SCHEMA_VERSION, "now": now}
    results: list[dict[str, Any]] = []

    results.append(run_write(tx, "来源裁决直连推荐动作迁移到推荐陈述", """
        MATCH (adj:SourceAdjudication)-[:decides_recommendation]->
              (rec:RecommendationStatement),
              (adj)-[old:recommends_action]->(action)
        MERGE (rec)-[nr:recommends_action]->(action)
        SET nr += properties(old), nr.normalized_batch=$batch_id,
            nr.schema_version=$schema_version, nr.updated_at=$now
        DELETE old
        RETURN count(*) AS 数量
    """, **common))
    results.append(run_write(tx, "来源裁决直连阻断动作迁移到推荐陈述", """
        MATCH (adj:SourceAdjudication)-[:decides_recommendation]->
              (rec:RecommendationStatement),
              (adj)-[old:blocks_action]->(action)
        MERGE (rec)-[nr:blocks_action]->(action)
        SET nr += properties(old), nr.normalized_batch=$batch_id,
            nr.schema_version=$schema_version, nr.updated_at=$now
        DELETE old
        RETURN count(*) AS 数量
    """, **common))

    results.append(run_write(tx, "推荐陈述动作编码回连具体执行项目", """
        MATCH (adj:SourceAdjudication)-[:decides_recommendation]->
              (rec:RecommendationStatement)
        WHERE coalesce(adj.formal_cdss_ready,false)=true
          AND coalesce(adj.cdss_use_status,'')='正式推荐'
          AND NOT (rec)-[:recommends_action|blocks_action|recommends_assessment]->()
        WITH adj,rec,coalesce(rec.action_code,adj.action_code,'') AS wanted
        MATCH (action:KGNode {code:wanted})
        WHERE action.entityType IN $action_types
          AND coalesce(rec.recommendation_type,'recommend') <> 'block'
          AND coalesce(adj.action_relation,'recommends_action') <> 'blocks_action'
        MERGE (rec)-[nr:recommends_action]->(action)
        SET nr.normalized_batch=$batch_id, nr.schema_version=$schema_version,
            nr.updated_at=$now
        RETURN count(*) AS 数量
    """, action_types=ACTION_TYPES, **common))
    results.append(run_write(tx, "推荐陈述动作编码回连具体阻断项目", """
        MATCH (adj:SourceAdjudication)-[:decides_recommendation]->
              (rec:RecommendationStatement)
        WHERE coalesce(adj.formal_cdss_ready,false)=true
          AND coalesce(adj.cdss_use_status,'')='正式推荐'
          AND NOT (rec)-[:recommends_action|blocks_action|recommends_assessment]->()
        WITH adj,rec,coalesce(rec.action_code,adj.action_code,'') AS wanted
        MATCH (action:KGNode {code:wanted})
        WHERE action.entityType IN $action_types
          AND (coalesce(rec.recommendation_type,'')='block' OR
               coalesce(adj.action_relation,'')='blocks_action')
        MERGE (rec)-[nr:blocks_action]->(action)
        SET nr.normalized_batch=$batch_id, nr.schema_version=$schema_version,
            nr.updated_at=$now
        RETURN count(*) AS 数量
    """, action_types=ACTION_TYPES, **common))
    results.append(run_write(tx, "推荐陈述动作编码回连临床评估目标", """
        MATCH (adj:SourceAdjudication)-[:decides_recommendation]->
              (rec:RecommendationStatement)
        WHERE coalesce(adj.formal_cdss_ready,false)=true
          AND coalesce(adj.cdss_use_status,'')='正式推荐'
          AND NOT (rec)-[:recommends_action|blocks_action|recommends_assessment]->()
        WITH adj,rec,coalesce(rec.action_code,adj.action_code,'') AS wanted
        MATCH (target:KGNode {code:wanted})
        WHERE target.entityType IN $assessment_types
        MERGE (rec)-[nr:recommends_assessment]->(target)
        SET nr.normalized_batch=$batch_id, nr.schema_version=$schema_version,
            nr.updated_at=$now
        RETURN count(*) AS 数量
    """, assessment_types=ASSESSMENT_TYPES, **common))

    results.append(run_write(tx, "无推荐目标的来源裁决退出正式推荐", """
        MATCH (adj:SourceAdjudication)-[:decides_recommendation]->
              (rec:RecommendationStatement)
        WHERE coalesce(adj.formal_cdss_ready,false)=true
          AND coalesce(adj.cdss_use_status,'')='正式推荐'
          AND NOT (rec)-[:recommends_action|blocks_action|recommends_assessment]->()
        SET adj.formal_cdss_ready=false,
            adj.cdss_use_status='阻断',
            adj.clinical_review_status='blocked',
            adj.migration_block_reason='推荐陈述未连接具体执行项目或临床评估目标',
            adj.updated_at=$now,
            rec.formal_cdss_ready=false,
            rec.cdss_use_status='阻断',
            rec.clinical_review_status='blocked',
            rec.updated_at=$now
        RETURN count(DISTINCT adj) AS 数量
    """, **common))

    invalid_direct = query_count(
        tx,
        """
        MATCH (:SourceAdjudication)-[r:recommends_action|blocks_action|recommends_assessment]->()
        RETURN count(r) AS amount
        """,
    )
    unresolved_formal = query_count(
        tx,
        """
        MATCH (adj:SourceAdjudication)-[:decides_recommendation]->
              (rec:RecommendationStatement)
        WHERE coalesce(adj.formal_cdss_ready,false)=true
          AND coalesce(adj.cdss_use_status,'')='正式推荐'
          AND NOT (rec)-[:recommends_action|blocks_action|recommends_assessment]->()
        RETURN count(DISTINCT adj) AS amount
        """,
    )
    if invalid_direct or unresolved_formal:
        raise RuntimeError(
            "正式推荐链路统一失败，已触发事务回滚："
            f"来源裁决直连目标={invalid_direct}，正式推荐无目标={unresolved_formal}"
        )
    results.append(
        {
            "步骤": "正式推荐链路事务内硬闸门",
            "结果": "通过",
            "指标": {
                "来源裁决直连推荐目标": invalid_direct,
                "正式推荐无具体目标": unresolved_formal,
            },
        }
    )
    return results


def render_report(path: Path, before: dict[str, Any], after: dict[str, Any] | None, status: str) -> None:
    def total(rows: Iterable[dict[str, Any]]) -> int:
        return sum(int(row.get("数量", 0)) for row in rows)

    lines = [
        "# 旧实体、旧关系和错误方案结构全库收口报告",
        "",
        f"- 批次：`{BATCH_ID}`",
        f"- 状态：**{status}**",
        f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "## 收口基线",
        "",
        f"- 节点总数：{before['节点总数']}",
        f"- 关系总数：{before['关系总数']}",
        f"- 旧实体：{total(before['旧实体'])}",
        f"- 旧关系：{total(before['旧关系'])}",
        f"- 错误正式推荐终点：{total(before['错误正式推荐终点'])}",
        f"- 目录层错误挂载：{total(before['目录层错误挂载'])}",
        f"- 方案套方案：{before['方案套方案']}",
        f"- 空治疗方案：{before['空治疗方案']}",
        f"- 明确跨病种污染关系：{len(before['待删除跨病种错误方案关系'])}",
    ]
    if after is not None:
        lines.extend(
            [
                "",
                "## 收口后硬闸门",
                "",
                f"- 旧实体：{total(after['旧实体'])}",
                f"- 旧关系：{total(after['旧关系'])}",
                f"- 错误正式推荐终点：{total(after['错误正式推荐终点'])}",
                f"- 目录层错误挂载：{total(after['目录层错误挂载'])}",
                f"- 方案套方案：{after['方案套方案']}",
                f"- 空辅助检查方案：{after['空辅助检查方案']}",
                f"- 空治疗方案：{after['空治疗方案']}",
                f"- 明确跨病种污染关系：{len(after['待删除跨病种错误方案关系'])}",
            ]
        )
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 检查、检验及指标实体原节点原地升级，业务编码、别名和证据不丢失。",
            "- 疾病直连检查/检验迁移为疾病—辅助检查方案—具体项目。",
            "- 疾病直连药品/手术迁移为疾病—治疗方案—具体动作。",
            "- 方案套方案展开为疾病直连方案和方案直连具体动作。",
            "- 非动作类型不再伪装为正式推荐；节点和证据保留。",
            "- 仅对可客观判定的跨病种错误方案关系执行清除。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="旧结构全库收口 V2")
    parser.add_argument(
        "--mode",
        choices=["plan", "apply", "compact", "normalize-formal", "postcheck"],
        required=True,
    )
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = parse_connection_file(args.connection_file.resolve())
    driver = GraphDatabase.driver(conn["uri"], auth=(conn["username"], conn["password"]))
    try:
        driver.verify_connectivity()
        with driver.session(database=args.database, default_access_mode=READ_ACCESS) as session:
            before = inventory(session)
            new_plans, assignments = build_direct_action_assignments(session)
        baseline_path = output_dir / "01_收口前结构盘点.json"
        if args.mode in {"plan", "apply"} or not baseline_path.exists():
            write_json(baseline_path, before)
            write_csv(
                output_dir / "02_跨病种错误方案关系清单.csv",
                before["待删除跨病种错误方案关系"],
            )
            write_json(
                output_dir / "03_疾病直连治疗动作迁移计划.json",
                {"新增承接方案": new_plans, "动作分配": assignments},
            )

        if args.mode == "plan":
            render_report(output_dir / "旧结构全库收口报告.md", before, None, "只读预演完成，未写库")
            print(json.dumps({"mode": "plan", "before": before}, ensure_ascii=False))
            return 0

        if args.mode == "postcheck":
            render_report(output_dir / "旧结构全库收口报告.md", before, before, "入库后复核")
            print(json.dumps({"mode": "postcheck", "inventory": before}, ensure_ascii=False))
            return 0

        if args.mode == "compact":
            manifest_path = output_dir / "00_升级前全库备份" / "备份清单_manifest.json"
            if not manifest_path.exists():
                raise RuntimeError("缺少升级前完整全库备份，禁止执行关系收敛")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not manifest.get("count_consistent"):
                raise RuntimeError("升级前全库备份不完整，禁止执行关系收敛")
            with driver.session(database=args.database) as session:
                compact_operations = session.execute_write(compact_generated_recommendations)
            write_json(output_dir / "04b_推荐关系膨胀回收记录.json", compact_operations)
            with driver.session(database=args.database, default_access_mode=READ_ACCESS) as session:
                after_compact = inventory(session)
            write_json(output_dir / "05_收口后结构复核.json", after_compact)
            render_report(
                output_dir / "旧结构全库收口报告.md",
                before,
                after_compact,
                "旧结构归零且推荐关系膨胀已回收",
            )
            print(json.dumps({"mode": "compact", "after": after_compact}, ensure_ascii=False))
            return 0

        if args.mode == "normalize-formal":
            manifest_path = output_dir / "00_升级前全库备份" / "备份清单_manifest.json"
            if not manifest_path.exists():
                raise RuntimeError("缺少升级前完整全库备份，禁止统一正式推荐链路")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not manifest.get("count_consistent"):
                raise RuntimeError("升级前全库备份不完整，禁止统一正式推荐链路")
            with driver.session(database=args.database) as session:
                normalized = session.execute_write(normalize_formal_recommendation_chain)
            write_json(output_dir / "04c_正式推荐链路统一记录.json", normalized)
            with driver.session(database=args.database, default_access_mode=READ_ACCESS) as session:
                after_normalize = inventory(session)
            write_json(output_dir / "05_收口后结构复核.json", after_normalize)
            render_report(
                output_dir / "旧结构全库收口报告.md",
                before,
                after_normalize,
                "旧结构归零且正式推荐链路已统一",
            )
            print(
                json.dumps(
                    {"mode": "normalize-formal", "operations": normalized,
                     "after": after_normalize},
                    ensure_ascii=False,
                )
            )
            return 0

        verify_backup(output_dir, before)
        with driver.session(database=args.database) as session:
            operations = session.execute_write(execute_migration, new_plans, assignments)
        write_json(output_dir / "04_事务执行记录.json", operations)
        with driver.session(database=args.database, default_access_mode=READ_ACCESS) as session:
            after = inventory(session)
        write_json(output_dir / "05_收口后结构复核.json", after)
        render_report(output_dir / "旧结构全库收口报告.md", before, after, "写库与硬闸门通过")
        print(json.dumps({"mode": "apply", "before": before, "after": after}, ensure_ascii=False))
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
