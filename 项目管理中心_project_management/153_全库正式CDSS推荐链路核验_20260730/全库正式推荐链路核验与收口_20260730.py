from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "全库正式CDSS推荐链路核验与收口_20260730"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
OUT_DIR = Path(__file__).resolve().parent / "02_正式推荐链路核验与收口"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_conn(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    uri = re.search(r"bolt://[^\s；;,]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;,]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;,]+)", text)
    if not uri or not user or not password:
        raise RuntimeError("无法从图谱数据库链接.txt 解析 Bolt 地址、用户名、密码。")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def rows(records) -> list[dict[str, Any]]:
    return [dict(r) for r in records]


def scalar(session, query: str, **params) -> Any:
    return session.run(query, **params).single().value()


def fix_hypertension_lifestyle_plan(session) -> dict[str, Any]:
    """补齐高血压生活方式干预方案的非药物治疗动作链。

    这些动作不是医嘱项目，不写 Oracle，也不标记为正式医嘱回填。
    目的是避免“治疗方案只有标题、没有可执行内容”的知识图谱空壳。
    """
    plan_code = "PLAN-CARD-2081B78ED14D"
    action_items = [
        {
            "code": "TREAT-CARD-HT-LIFESTYLE-SALT",
            "name": "限制钠盐摄入",
            "description": "高血压生活方式干预组成项，用于提示减少钠盐摄入；不作为医嘱回填项目。",
        },
        {
            "code": "TREAT-CARD-HT-LIFESTYLE-DIET",
            "name": "合理膳食",
            "description": "高血压生活方式干预组成项，用于提示合理膳食结构；不作为医嘱回填项目。",
        },
        {
            "code": "TREAT-CARD-HT-LIFESTYLE-WEIGHT",
            "name": "控制体重",
            "description": "高血压生活方式干预组成项，用于提示控制体重和腹型肥胖；不作为医嘱回填项目。",
        },
        {
            "code": "TREAT-CARD-HT-LIFESTYLE-EXERCISE",
            "name": "规律运动",
            "description": "高血压生活方式干预组成项，用于提示规律体力活动；不作为医嘱回填项目。",
        },
        {
            "code": "TREAT-CARD-HT-LIFESTYLE-SMOKE-ALCOHOL",
            "name": "戒烟限酒",
            "description": "高血压生活方式干预组成项，用于提示戒烟和限制饮酒；不作为医嘱回填项目。",
        },
        {
            "code": "TREAT-CARD-HT-LIFESTYLE-STRESS",
            "name": "心理平衡",
            "description": "高血压生活方式干预组成项，用于提示减轻精神压力、保持心理平衡；不作为医嘱回填项目。",
        },
    ]
    result = session.execute_write(_write_hypertension_lifestyle_plan, plan_code, action_items)
    return result


def _write_hypertension_lifestyle_plan(tx, plan_code: str, action_items: list[dict[str, str]]) -> dict[str, Any]:
    plan = tx.run(
        """
        MATCH (p:KGNode {code:$plan_code})
        SET p.description = coalesce(
              p.description,
              '生活方式干预是高血压管理基础，包括限制钠盐摄入、合理膳食、控制体重、规律运动、戒烟限酒和心理平衡。'
            ),
            p.source_name = coalesce(p.source_name, '《内科学（第10版）》'),
            p.source_type = coalesce(p.source_type, 'authoritative_textbook'),
            p.orderable = false,
            p.formal_cdss_ready = false,
            p.cdss_use_status = coalesce(p.cdss_use_status, '知识展示'),
            p.updated_at = $now,
            p.last_fix_run_id = $run_id
        RETURN p.code AS code, p.name AS name
        """,
        plan_code=plan_code,
        now=NOW,
        run_id=RUN_ID,
    ).single()
    if not plan:
        raise RuntimeError(f"未找到治疗方案节点：{plan_code}")

    created = 0
    linked = 0
    for item in action_items:
        rec = tx.run(
            """
            MERGE (a:KGNode:TreatmentItem {code:$code})
            ON CREATE SET
              a.name=$name,
              a.display_name=$name,
              a.preferred_name=$name,
              a.entityType='TreatmentItem',
              a.type_label='治疗项目',
              a.status='active',
              a.orderable=false,
              a.formal_cdss_ready=false,
              a.cdss_use_status='知识展示',
              a.dictionary_validation_status='knowledge_only',
              a.source_name='《内科学（第10版）》',
              a.source_type='authoritative_textbook',
              a.created_at=$now,
              a.created_by=$run_id
            SET
              a.name=$name,
              a.display_name=$name,
              a.preferred_name=$name,
              a.entityType='TreatmentItem',
              a.type_label='治疗项目',
              a.status='active',
              a.orderable=false,
              a.formal_cdss_ready=false,
              a.cdss_use_status='知识展示',
              a.dictionary_validation_status='knowledge_only',
              a.description=$description,
              a.updated_at=$now,
              a.last_fix_run_id=$run_id
            WITH a
            MATCH (p:KGNode {code:$plan_code})
            MERGE (p)-[r:has_treatment_component]->(a)
            ON CREATE SET r.created_at=$now
            SET r.source_name='《内科学（第10版）》',
                r.source_type='authoritative_textbook',
                r.relation_scope='高血压生活方式干预组成',
                r.orderable=false,
                r.formal_cdss_ready=false,
                r.cdss_use_status='知识展示',
                r.updated_at=$now,
                r.last_fix_run_id=$run_id
            RETURN a.code AS code, count(r) AS rel_count
            """,
            plan_code=plan_code,
            now=NOW,
            run_id=RUN_ID,
            **item,
        ).single()
        if rec:
            created += 1
            linked += int(rec["rel_count"])

    return {
        "plan_code": plan_code,
        "plan_name": plan["name"],
        "component_count": created,
        "linked_count": linked,
        "components": [x["name"] for x in action_items],
    }


def recommendation_rows(session) -> list[dict[str, Any]]:
    return rows(
        session.run(
            """
            MATCH (r:KGNode {entityType:'RecommendationStatement'})
            OPTIONAL MATCH (r)-[ar:recommends_action|blocks_action|recommends_assessment]->(a:KGNode)
            OPTIONAL MATCH (r)-[er:supported_by_evidence|derived_from]->(e:KGNode {entityType:'Evidence'})
            OPTIONAL MATCH (r)-[gr:uses_primary_guideline|based_on_guideline]->(g:KGNode {entityType:'Guideline'})
            OPTIONAL MATCH (d1:KGNode {entityType:'Disease'})-[:has_recommendation_statement]->(r)
            OPTIONAL MATCH (d2:KGNode {entityType:'Disease'})-[:has_clinical_pathway]->(:KGNode)-[:has_recommendation_statement]->(r)
            OPTIONAL MATCH (d3:KGNode {entityType:'Disease'})-[:has_clinical_pathway]->(:KGNode)-[:has_pathway_stage]->(:KGNode)-[:has_recommendation_statement]->(r)
            OPTIONAL MATCH (d4:KGNode {entityType:'Disease'})-[:has_clinical_pathway]->(:KGNode)-[:has_pathway_stage]->(:KGNode)-[:has_stage_rule]->(:KGNode)-[:has_recommendation_statement]->(r)
            OPTIONAL MATCH (d5:KGNode {entityType:'Disease'})-[:has_clinical_rule]->(:KGNode)-[:has_recommendation_statement]->(r)
            WITH r,
                 collect(DISTINCT a.code) AS action_codes,
                 collect(DISTINCT a.name) AS action_names,
                 collect(DISTINCT a.entityType) AS action_types,
                 collect(DISTINCT e.code) AS evidence_codes,
                 collect(DISTINCT g.code) AS guideline_codes,
                 collect(DISTINCT g.name)[0..5] AS guideline_names,
                 [x IN collect(DISTINCT d1.code) + collect(DISTINCT d2.code) + collect(DISTINCT d3.code) + collect(DISTINCT d4.code) + collect(DISTINCT d5.code) WHERE x IS NOT NULL] AS disease_codes
            RETURN
                 elementId(r) AS element_id,
                 r.code AS code,
                 r.name AS name,
                 coalesce(r.formal_cdss_ready,false) AS formal_cdss_ready,
                 coalesce(r.cdss_use_status,'') AS cdss_use_status,
                 coalesce(r.recommendation_class,'') AS recommendation_class,
                 coalesce(r.evidence_level,'') AS evidence_level,
                 coalesce(r.conflict_status,'') AS conflict_status,
                 coalesce(r.adjudication_reason,'') AS adjudication_reason,
                 action_codes,
                 action_names,
                 action_types,
                 evidence_codes,
                 guideline_codes,
                 guideline_names,
                 disease_codes
            ORDER BY r.code
            """
        )
    )


def is_non_empty_standard_value(value: str) -> bool:
    v = (value or "").strip()
    return bool(v) and v not in {"未结构化", "N/A", "NA", "无"}


def classify_recommendation(row: dict[str, Any]) -> dict[str, Any]:
    has_action = bool([x for x in row.get("action_codes", []) if x])
    has_evidence = bool([x for x in row.get("evidence_codes", []) if x])
    has_guideline = bool([x for x in row.get("guideline_codes", []) if x])
    has_disease = bool([x for x in row.get("disease_codes", []) if x])
    has_rec_class = is_non_empty_standard_value(row.get("recommendation_class", ""))
    has_evidence_level = is_non_empty_standard_value(row.get("evidence_level", ""))
    issues = []
    if not has_disease:
        issues.append("缺少所属疾病路径")
    if not has_action:
        issues.append("缺少推荐动作或评估目标")
    if not has_evidence:
        issues.append("缺少证据")
    if not has_guideline:
        issues.append("缺少指南或教材来源")
    if not has_rec_class:
        issues.append("缺少推荐等级/推荐来源强度")
    if not has_evidence_level:
        issues.append("缺少证据等级/证据来源强度")
    complete = not issues
    return {
        "complete": complete,
        "issues": issues,
        "is_declared_formal": row.get("cdss_use_status") == "正式推荐" or row.get("formal_cdss_ready") is True,
    }


def normalize_formal_recommendation_status(session, recs: list[dict[str, Any]]) -> dict[str, Any]:
    to_promote = []
    to_demote = []
    untouched = 0
    for row in recs:
        cls = classify_recommendation(row)
        is_formal_status = row.get("cdss_use_status") == "正式推荐"
        is_ready = row.get("formal_cdss_ready") is True
        if cls["complete"] and (is_formal_status or is_ready) and not (is_formal_status and is_ready):
            to_promote.append(row)
        elif (is_formal_status or is_ready) and not cls["complete"]:
            to_demote.append({**row, "issues": cls["issues"]})
        else:
            untouched += 1

    session.execute_write(_write_recommendation_status, to_promote, to_demote)
    return {
        "promoted_or_completed_formal": len(to_promote),
        "demoted_to_knowledge_display": len(to_demote),
        "untouched": untouched,
        "demoted_examples": [
            {"code": x["code"], "name": x["name"], "issues": x["issues"]} for x in to_demote[:20]
        ],
    }


def _write_recommendation_status(tx, to_promote: list[dict[str, Any]], to_demote: list[dict[str, Any]]) -> None:
    for row in to_promote:
        tx.run(
            """
            MATCH (r:KGNode {code:$code})
            SET r.formal_cdss_ready=true,
                r.cdss_use_status='正式推荐',
                r.conflict_status=CASE
                  WHEN trim(coalesce(r.conflict_status,''))='' THEN '未发现冲突'
                  ELSE r.conflict_status
                END,
                r.adjudication_reason=CASE
                  WHEN trim(coalesce(r.adjudication_reason,''))='' THEN '已具备推荐动作、证据和指南来源，按结构化链路进入正式推荐。'
                  ELSE r.adjudication_reason
                END,
                r.updated_at=$now,
                r.last_fix_run_id=$run_id
            """,
            code=row["code"],
            now=NOW,
            run_id=RUN_ID,
        )
    for row in to_demote:
        tx.run(
            """
            MATCH (r:KGNode {code:$code})
            SET r.formal_cdss_ready=false,
                r.cdss_use_status='知识展示',
                r.formal_block_reason=$reason,
                r.updated_at=$now,
                r.last_fix_run_id=$run_id
            """,
            code=row["code"],
            reason="；".join(row.get("issues", [])),
            now=NOW,
            run_id=RUN_ID,
        )


def treatment_plan_action_blockers(session) -> list[dict[str, Any]]:
    return rows(
        session.run(
            """
            MATCH (d:KGNode {entityType:'Disease'})-[:has_treatment_plan]->(p:KGNode {entityType:'TreatmentPlan'})
            WHERE coalesce(d.status,'') <> 'deprecated'
              AND coalesce(p.status,'') <> 'deprecated'
            OPTIONAL MATCH path=(p)-[:has_clinical_pathway|has_pathway_stage|next_pathway_stage|
              has_stage_rule|has_treatment_component|includes_medication|includes_procedure|
              includes_treatment_item|has_recommended_action|recommends_action|
              treated_by_medication|treated_by_procedure*1..5]->(a:KGNode)
            WHERE a.entityType IN ['Medication','Procedure','ExamItem','LabItem','TreatmentItem',
                                   'FollowUp','Exam','LabTest']
            WITH d, p, collect(DISTINCT a.code) AS action_codes
            WHERE size(action_codes)=0
            RETURN d.code AS disease_code, d.name AS disease_name,
                   p.code AS plan_code, p.name AS plan_name
            ORDER BY disease_code, plan_code
            """
        )
    )


def standard_dictionary_gate_summary(session) -> dict[str, Any]:
    # 只查本轮必须关注的几类，不替代独立标准字典硬闸门脚本。
    rows_ = rows(
        session.run(
            """
            MATCH (n:KGNode)
            WHERE n.entityType IN ['StandardDiagnosis','StandardProcedure','Medication',
                                   'ExamItem','LabItem','LabSubitem','Symptom','Sign',
                                   'ExamObservation','TreatmentItem']
            RETURN n.entityType AS entity_type,
                   count(*) AS total,
                   sum(CASE WHEN coalesce(n.formal_cdss_ready,false)=true THEN 1 ELSE 0 END) AS formal_ready,
                   sum(CASE WHEN coalesce(n.formal_cdss_ready,false)=true AND trim(coalesce(n.cdss_dict_id,''))='' THEN 1 ELSE 0 END) AS formal_missing_dict_id,
                   sum(CASE WHEN coalesce(n.formal_cdss_ready,false)=true AND coalesce(n.dictionary_validation_status,'') IN ['pending','候选注册','待注册'] THEN 1 ELSE 0 END) AS formal_pending
            ORDER BY entity_type
            """
        )
    )
    return {"by_entity_type": rows_}


def write_csv(path: Path, rows_: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows_:
            writer.writerow({k: r.get(k, "") for k in fields})


def main() -> None:
    conn = parse_conn(ROOT / "图谱数据库链接.txt")
    driver = GraphDatabase.driver(conn["uri"], auth=(conn["user"], conn["password"]))
    try:
        with driver.session() as session:
            before_recs = recommendation_rows(session)
            before_formal = sum(1 for r in before_recs if r["cdss_use_status"] == "正式推荐" or r["formal_cdss_ready"])
            before_invalid = [r for r in before_recs if (r["cdss_use_status"] == "正式推荐" or r["formal_cdss_ready"]) and not classify_recommendation(r)["complete"]]
            before_plan_blockers = treatment_plan_action_blockers(session)

            lifestyle_fix = fix_hypertension_lifestyle_plan(session)
            status_fix = normalize_formal_recommendation_status(session, before_recs)

            after_recs = recommendation_rows(session)
            after_formal_rows = [r for r in after_recs if r["cdss_use_status"] == "正式推荐" or r["formal_cdss_ready"]]
            after_invalid = []
            issue_counts = Counter()
            for r in after_formal_rows:
                cls = classify_recommendation(r)
                if not cls["complete"]:
                    item = {**r, "issues": "；".join(cls["issues"])}
                    after_invalid.append(item)
                    issue_counts.update(cls["issues"])
            after_plan_blockers = treatment_plan_action_blockers(session)
            dict_gate = standard_dictionary_gate_summary(session)

        summary = {
            "run_id": RUN_ID,
            "executed_at": NOW,
            "neo4j_written": True,
            "oracle_written": False,
            "before": {
                "recommendation_statement_total": len(before_recs),
                "declared_formal_recommendation_count": before_formal,
                "invalid_declared_formal_recommendation_count": len(before_invalid),
                "treatment_plan_no_action_blocker_count": len(before_plan_blockers),
            },
            "fixes": {
                "hypertension_lifestyle_plan": lifestyle_fix,
                "recommendation_status_normalization": status_fix,
            },
            "after": {
                "recommendation_statement_total": len(after_recs),
                "declared_formal_recommendation_count": len(after_formal_rows),
                "invalid_declared_formal_recommendation_count": len(after_invalid),
                "invalid_declared_formal_issue_counts": dict(issue_counts),
                "treatment_plan_no_action_blocker_count": len(after_plan_blockers),
                "standard_dictionary_formal_blocker_summary": dict_gate,
            },
            "remaining_plan_blockers": after_plan_blockers[:50],
            "remaining_invalid_formal_examples": [
                {
                    "code": r["code"],
                    "name": r["name"],
                    "issues": r["issues"],
                    "status": r["cdss_use_status"],
                    "formal_cdss_ready": r["formal_cdss_ready"],
                }
                for r in after_invalid[:50]
            ],
        }

        (OUT_DIR / "全库正式推荐链路核验与收口汇总_20260730.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_csv(
            OUT_DIR / "剩余正式推荐链路问题清单_20260730.csv",
            [
                {
                    "推荐编码": r["code"],
                    "推荐名称": r["name"],
                    "问题": r["issues"],
                    "状态": r["cdss_use_status"],
                    "formal_cdss_ready": r["formal_cdss_ready"],
                    "动作数": len([x for x in r.get("action_codes", []) if x]),
                    "证据数": len([x for x in r.get("evidence_codes", []) if x]),
                    "指南数": len([x for x in r.get("guideline_codes", []) if x]),
                    "疾病路径数": len([x for x in r.get("disease_codes", []) if x]),
                }
                for r in after_invalid
            ],
            ["推荐编码", "推荐名称", "问题", "状态", "formal_cdss_ready", "动作数", "证据数", "指南数", "疾病路径数"],
        )
        write_csv(
            OUT_DIR / "剩余治疗方案空动作链清单_20260730.csv",
            after_plan_blockers,
            ["disease_code", "disease_name", "plan_code", "plan_name"],
        )
        print(json.dumps(
            {
                "run_id": RUN_ID,
                "neo4j_written": True,
                "oracle_written": False,
                "before_invalid_declared_formal": len(before_invalid),
                "after_invalid_declared_formal": len(after_invalid),
                "before_treatment_plan_no_action": len(before_plan_blockers),
                "after_treatment_plan_no_action": len(after_plan_blockers),
                "promoted_or_completed_formal": status_fix["promoted_or_completed_formal"],
                "demoted_to_knowledge_display": status_fix["demoted_to_knowledge_display"],
                "output_dir": str(OUT_DIR),
            },
            ensure_ascii=False,
            indent=2,
        ))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
