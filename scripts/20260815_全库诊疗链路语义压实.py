from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


BATCH_ID = "20260815_全库诊疗链路语义压实"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
LINK_FILE = ROOT / "图谱数据库链接.txt"
OUT_DIR = ROOT / "项目管理中心_project_management" / "2026年8月P8全局诊疗链路压实"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_neo4j_link() -> tuple[str, str, str]:
    text = LINK_FILE.read_text(encoding="utf-8", errors="ignore")
    uri_match = re.search(r"bolt://[^\s\u3000，,]+", text)
    user_match = re.search(r"(?:用户名|用户|user|username)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    password_match = re.search(r"(?:密码|password)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    if not uri_match or not password_match:
        raise RuntimeError("未在图谱数据库链接.txt 中解析到 bolt 地址或密码")
    return uri_match.group(0), (user_match.group(1) if user_match else "neo4j"), password_match.group(1)


REL_TYPES = [
    "has_exam_plan",
    "includes_exam_item",
    "includes_lab_item",
    "exam_item_has_observation",
    "lab_item_has_subitem",
    "has_differential_diagnosis",
    "has_differential_rule",
    "requires_exclusion_exam",
    "requires_exclusion_lab",
    "has_treatment_plan",
    "includes_medication",
    "includes_procedure",
    "includes_treatment_item",
    "stage_has_available_action",
    "has_recommendation_statement",
    "recommends_action",
]


def run_count(session, query: str, **params) -> int:
    rec = session.run(query, **params).single()
    return int(rec["n"]) if rec else 0


def relation_missing(session, rel_type: str) -> dict:
    rows = session.run(
        f"""
        MATCH ()-[r:{rel_type}]->()
        RETURN properties(r) AS p
        """
    )
    total = 0
    missing_stage = 0
    missing_purpose = 0
    missing_target = 0
    missing_formal_flag = 0
    for row in rows:
        total += 1
        p = row["p"] or {}
        if not (p.get("clinical_stage") or p.get("care_stage")):
            missing_stage += 1
        if not (p.get("recommendation_purpose") or p.get("purpose")):
            missing_purpose += 1
        if not (p.get("service_target_code") or p.get("service_target_name")):
            missing_target += 1
        if rel_type in {"recommends_action", "stage_has_available_action"}:
            if not p.get("formal_recommendation"):
                missing_formal_flag += 1
    return {
        "total": total,
        "missing_stage": missing_stage,
        "missing_purpose": missing_purpose,
        "missing_target": missing_target,
        "missing_formal_flag": missing_formal_flag,
    }


def audit(session) -> dict:
    rel_missing = {rel: relation_missing(session, rel) for rel in REL_TYPES}
    return {
        "time": NOW,
        "batch_id": BATCH_ID,
        "relation_missing": rel_missing,
        "ddx_rules_without_exclusion_items": run_count(
            session,
            """
            MATCH (d:Disease)-[:has_differential_diagnosis]->(ddx)-[:has_differential_rule]->(rule)
            WHERE coalesce(ddx.status,'active') <> 'deprecated'
              AND NOT (rule)-[:requires_exclusion_exam|requires_exclusion_lab]->()
            RETURN count(DISTINCT rule) AS n
            """,
        ),
        "treatment_plans_without_downstream_action": run_count(
            session,
            """
            MATCH (d:Disease)-[:has_treatment_plan]->(tp:TreatmentPlan)
            WHERE coalesce(tp.status,'active') <> 'deprecated'
              AND NOT (tp)-[:includes_medication|includes_procedure|includes_treatment_item]->()
            RETURN count(DISTINCT tp) AS n
            """,
        ),
        "formal_recommendation_without_action": run_count(
            session,
            """
            MATCH (r:RecommendationStatement)
            WHERE coalesce(r.status,'active') <> 'deprecated'
              AND NOT (r)-[:recommends_action]->()
            RETURN count(r) AS n
            """,
        ),
        "formal_recommendation_without_evidence": run_count(
            session,
            """
            MATCH (r:RecommendationStatement)
            WHERE coalesce(r.status,'active') <> 'deprecated'
              AND NOT (r)-[:supported_by_evidence]->()
            RETURN count(r) AS n
            """,
        ),
        "formal_recommendation_without_primary_guideline": run_count(
            session,
            """
            MATCH (r:RecommendationStatement)
            WHERE coalesce(r.status,'active') <> 'deprecated'
              AND coalesce(r.primary_guideline_id, r.primary_guideline_name, '') = ''
            RETURN count(r) AS n
            """,
        ),
    }


def execute_updates(session) -> dict:
    updates: dict[str, int] = {}

    # 疾病 -> 检查方案：表示某疾病在辅助诊断阶段有一组检查/检验建议。
    updates["has_exam_plan"] = session.run(
        """
        MATCH (d:Disease)-[r:has_exam_plan]->(p:ExamPlan)
        SET r.clinical_stage = coalesce(r.clinical_stage, '辅助诊断'),
            r.purpose = coalesce(r.purpose, '诊断检查'),
            r.service_target_type = coalesce(r.service_target_type, 'Disease'),
            r.service_target_code = coalesce(r.service_target_code, d.code),
            r.service_target_name = coalesce(r.service_target_name, d.name),
            r.formal_recommendation = coalesce(r.formal_recommendation, 'no'),
            r.recommendation_scope = coalesce(r.recommendation_scope, '检查检验方案'),
            r.semantic_review_status = 'auto_confirmed',
            r.semantic_patch_batch = $batch,
            r.semantic_patch_time = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    # 检查方案 -> 检查项目/检验项目：服务于疾病首诊或复核，不直接等于治疗前置。
    for rel_type, target_kind, purpose in [
        ("includes_exam_item", "ExamItem", "辅助检查"),
        ("includes_lab_item", "LabItem", "辅助检验"),
    ]:
        updates[rel_type] = session.run(
            f"""
            MATCH (d:Disease)-[:has_exam_plan]->(p:ExamPlan)-[r:{rel_type}]->(item)
            SET r.clinical_stage = coalesce(r.clinical_stage, '辅助诊断'),
                r.purpose = coalesce(r.purpose, $purpose),
                r.service_target_type = coalesce(r.service_target_type, 'Disease'),
                r.service_target_code = coalesce(r.service_target_code, d.code),
                r.service_target_name = coalesce(r.service_target_name, d.name),
                r.formal_recommendation = 'no',
                r.recommendation_scope = coalesce(r.recommendation_scope, '疾病辅助诊断'),
                r.target_entity_type = coalesce(r.target_entity_type, $target_kind),
                r.semantic_review_status = 'auto_confirmed',
                r.semantic_patch_batch = $batch,
                r.semantic_patch_time = $now
            RETURN count(r) AS n
            """,
            purpose=purpose,
            target_kind=target_kind,
            batch=BATCH_ID,
            now=NOW,
        ).single()["n"]

    # 检查项目/检验项目 -> 观察项/检验细项：这是下钻关系，用于前端解释“为什么推荐这个项目”。
    updates["exam_item_has_observation"] = session.run(
        """
        MATCH (exam:ExamItem)-[r:exam_item_has_observation]->(obs:ExamObservation)
        SET r.clinical_stage = coalesce(r.clinical_stage, '辅助诊断'),
            r.purpose = coalesce(r.purpose, '检查发现下钻'),
            r.service_target_type = coalesce(r.service_target_type, 'ExamItem'),
            r.service_target_code = coalesce(r.service_target_code, exam.code),
            r.service_target_name = coalesce(r.service_target_name, exam.name),
            r.formal_recommendation = coalesce(r.formal_recommendation, 'no'),
            r.recommendation_scope = coalesce(r.recommendation_scope, '解释下钻'),
            r.semantic_review_status = 'auto_confirmed',
            r.semantic_patch_batch = $batch,
            r.semantic_patch_time = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    updates["lab_item_has_subitem"] = session.run(
        """
        MATCH (lab:LabItem)-[r:lab_item_has_subitem]->(sub:LabSubitem)
        SET r.clinical_stage = coalesce(r.clinical_stage, '辅助诊断'),
            r.purpose = coalesce(r.purpose, '检验细项下钻'),
            r.service_target_type = coalesce(r.service_target_type, 'LabItem'),
            r.service_target_code = coalesce(r.service_target_code, lab.code),
            r.service_target_name = coalesce(r.service_target_name, lab.name),
            r.formal_recommendation = coalesce(r.formal_recommendation, 'no'),
            r.recommendation_scope = coalesce(r.recommendation_scope, '解释下钻'),
            r.semantic_review_status = 'auto_confirmed',
            r.semantic_patch_batch = $batch,
            r.semantic_patch_time = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    # 鉴别诊断链路：疾病 -> 鉴别对象 -> 鉴别规则 -> 排除检查/检验。
    updates["has_differential_diagnosis"] = session.run(
        """
        MATCH (d:Disease)-[r:has_differential_diagnosis]->(ddx:DifferentialDiagnosis)
        SET r.clinical_stage = coalesce(r.clinical_stage, '鉴别诊断'),
            r.purpose = coalesce(r.purpose, '鉴别对象'),
            r.service_target_type = coalesce(r.service_target_type, 'Disease'),
            r.service_target_code = coalesce(r.service_target_code, d.code),
            r.service_target_name = coalesce(r.service_target_name, d.name),
            r.formal_recommendation = 'no',
            r.recommendation_scope = coalesce(r.recommendation_scope, '疾病鉴别诊断'),
            r.semantic_review_status = 'auto_confirmed',
            r.semantic_patch_batch = $batch,
            r.semantic_patch_time = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    updates["has_differential_rule"] = session.run(
        """
        MATCH (ddx:DifferentialDiagnosis)-[r:has_differential_rule]->(rule:ClinicalRule)
        SET r.clinical_stage = coalesce(r.clinical_stage, '鉴别诊断'),
            r.purpose = coalesce(r.purpose, '鉴别规则'),
            r.service_target_type = coalesce(r.service_target_type, 'DifferentialDiagnosis'),
            r.service_target_code = coalesce(r.service_target_code, ddx.code),
            r.service_target_name = coalesce(r.service_target_name, ddx.name),
            r.formal_recommendation = 'no',
            r.recommendation_scope = coalesce(r.recommendation_scope, '鉴别诊断规则'),
            r.semantic_review_status = 'auto_confirmed',
            r.semantic_patch_batch = $batch,
            r.semantic_patch_time = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    for rel_type, purpose in [
        ("requires_exclusion_exam", "鉴别排除检查"),
        ("requires_exclusion_lab", "鉴别排除检验"),
    ]:
        updates[rel_type] = session.run(
            f"""
            MATCH (ddx:DifferentialDiagnosis)-[r:{rel_type}]->(item)
            SET r.clinical_stage = coalesce(r.clinical_stage, '鉴别诊断'),
                r.purpose = coalesce(r.purpose, $purpose),
                r.service_target_type = coalesce(r.service_target_type, 'DifferentialDiagnosis'),
                r.service_target_code = coalesce(r.service_target_code, ddx.code),
                r.service_target_name = coalesce(r.service_target_name, ddx.name),
                r.formal_recommendation = 'no',
                r.recommendation_scope = coalesce(r.recommendation_scope, '鉴别排除依据'),
                r.semantic_review_status = 'auto_confirmed',
                r.semantic_patch_batch = $batch,
                r.semantic_patch_time = $now
            RETURN count(r) AS n
            """,
            purpose=purpose,
            batch=BATCH_ID,
            now=NOW,
        ).single()["n"]

    # 把鉴别对象已有排除检查/检验复制到具体鉴别规则，避免前端只知道“要鉴别”，不知道“用什么排除”。
    updates["copy_ddx_exam_to_rule"] = session.run(
        """
        MATCH (ddx:DifferentialDiagnosis)-[:has_differential_rule]->(rule:ClinicalRule)
        MATCH (ddx)-[:requires_exclusion_exam]->(item)
        MERGE (rule)-[r:requires_exclusion_exam]->(item)
        ON CREATE SET r.id = 'REL-' + coalesce(rule.code, elementId(rule)) + '-EXAM-' + coalesce(item.code, elementId(item)),
                      r.created_at = $now
        SET r.clinical_stage = '鉴别诊断',
            r.purpose = '鉴别排除检查',
            r.service_target_type = 'ClinicalRule',
            r.service_target_code = coalesce(rule.code, ddx.code),
            r.service_target_name = coalesce(rule.name, ddx.name),
            r.formal_recommendation = 'no',
            r.recommendation_scope = '鉴别规则排除依据',
            r.semantic_review_status = 'auto_confirmed',
            r.semantic_patch_batch = $batch,
            r.semantic_patch_time = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    updates["copy_ddx_lab_to_rule"] = session.run(
        """
        MATCH (ddx:DifferentialDiagnosis)-[:has_differential_rule]->(rule:ClinicalRule)
        MATCH (ddx)-[:requires_exclusion_lab]->(item)
        MERGE (rule)-[r:requires_exclusion_lab]->(item)
        ON CREATE SET r.id = 'REL-' + coalesce(rule.code, elementId(rule)) + '-LAB-' + coalesce(item.code, elementId(item)),
                      r.created_at = $now
        SET r.clinical_stage = '鉴别诊断',
            r.purpose = '鉴别排除检验',
            r.service_target_type = 'ClinicalRule',
            r.service_target_code = coalesce(rule.code, ddx.code),
            r.service_target_name = coalesce(rule.name, ddx.name),
            r.formal_recommendation = 'no',
            r.recommendation_scope = '鉴别规则排除依据',
            r.semantic_review_status = 'auto_confirmed',
            r.semantic_patch_batch = $batch,
            r.semantic_patch_time = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    # 历史误挂清理：D-二聚体升高是检查/检验指标线索，不是正式鉴别规则。
    updates["cleanup_ddimer_indicator_misclassified_as_rule"] = session.run(
        """
        MATCH (ddx:DifferentialDiagnosis {code:'DDX-AUTO-9BC262364DA5'})
              -[rel:has_differential_rule]->
              (r:ClinicalRule {code:'IND-CARD-LAB-DDIMER-PE-ELEVATED-20260714'})
        DELETE rel
        WITH r
        REMOVE r:ClinicalRule
        SET r:ExamIndicator,
            r.entityType = 'ExamIndicator',
            r.type_label = 'ExamIndicator',
            r.knowledge_role = 'exam_or_lab_indicator',
            r.status = 'knowledge_only',
            r.hidden_from_cdss = true,
            r.cleanup_reason = '历史误挂为鉴别规则，已退出正式鉴别规则链路',
            r.cleanup_batch = $batch,
            r.updated_at = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    # 历史空壳清理：只有“需要考虑以下疾病/其他病因”这类标题、没有鉴别规则和检查检验下游的节点，不能进入前端。
    updates["delete_generic_empty_differential_diagnosis"] = session.run(
        """
        MATCH (d:Disease)-[rel:has_differential_diagnosis]->(ddx:DifferentialDiagnosis)
        WHERE coalesce(ddx.status,'active') <> 'deprecated'
          AND NOT (ddx)-[:has_differential_rule]->(:ClinicalRule)
          AND ddx.name IN ['需要考虑以下疾病', '需其他引起心脏增大和心力衰竭的病因']
          AND COUNT { (ddx)--() } = 1
        DELETE rel, ddx
        RETURN count(ddx) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    # 名称卫生：实体名称和显示名称首尾空格会影响前端去重、搜索和字典匹配，必须入库后自动清理。
    updates["trim_node_name"] = session.run(
        """
        MATCH (n:KGNode)
        WHERE n.name IS NOT NULL AND n.name <> trim(n.name)
        SET n.name = trim(n.name),
            n.updated_at = $now
        RETURN count(n) AS n
        """,
        now=NOW,
    ).single()["n"]

    updates["trim_node_display_name"] = session.run(
        """
        MATCH (n:KGNode)
        WHERE n.display_name IS NOT NULL AND n.display_name <> trim(n.display_name)
        SET n.display_name = trim(n.display_name),
            n.updated_at = $now
        RETURN count(n) AS n
        """,
        now=NOW,
    ).single()["n"]

    # 治疗方案链路：疾病 -> 治疗方案 -> 用药/手术/治疗项目。这里不把方案标题当作正式推荐。
    updates["has_treatment_plan"] = session.run(
        """
        MATCH (d:Disease)-[r:has_treatment_plan]->(p:TreatmentPlan)
        SET r.clinical_stage = coalesce(r.clinical_stage, '治疗决策'),
            r.purpose = coalesce(r.purpose, '治疗方案'),
            r.service_target_type = coalesce(r.service_target_type, 'Disease'),
            r.service_target_code = coalesce(r.service_target_code, d.code),
            r.service_target_name = coalesce(r.service_target_name, d.name),
            r.formal_recommendation = coalesce(r.formal_recommendation, 'no'),
            r.recommendation_scope = coalesce(r.recommendation_scope, '疾病治疗方案'),
            r.semantic_review_status = 'auto_confirmed',
            r.semantic_patch_batch = $batch,
            r.semantic_patch_time = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    for rel_type, target_kind, purpose in [
        ("includes_medication", "Medication", "治疗用药"),
        ("includes_procedure", "Procedure", "治疗操作/手术"),
        ("includes_treatment_item", "TreatmentItem", "治疗处置"),
    ]:
        updates[rel_type] = session.run(
            f"""
            MATCH (d:Disease)-[:has_treatment_plan]->(p:TreatmentPlan)-[r:{rel_type}]->(item)
            SET r.clinical_stage = coalesce(r.clinical_stage, '治疗决策'),
                r.purpose = coalesce(r.purpose, $purpose),
                r.service_target_type = coalesce(r.service_target_type, 'Disease'),
                r.service_target_code = coalesce(r.service_target_code, d.code),
                r.service_target_name = coalesce(r.service_target_name, d.name),
                r.formal_recommendation = 'no',
                r.recommendation_scope = coalesce(r.recommendation_scope, '治疗方案下游动作'),
                r.target_entity_type = coalesce(r.target_entity_type, $target_kind),
                r.semantic_review_status = 'auto_confirmed',
                r.semantic_patch_batch = $batch,
                r.semantic_patch_time = $now
            RETURN count(r) AS n
            """,
            purpose=purpose,
            target_kind=target_kind,
            batch=BATCH_ID,
            now=NOW,
        ).single()["n"]

    # 教材“极化液疗法”不能只保留标题，必须下钻到组成药物；该知识不直接进入正式医嘱回填。
    updates["polarizing_solution_downstream_medications"] = session.run(
        """
        MATCH (p:TreatmentPlan {code:'MED-CARD-STEMI-579132151037'})
        MERGE (k:Medication {name:'氯化钾'})
          ON CREATE SET k.code='MED-CARD-POLAR-KCL',
                        k.entityType='Medication',
                        k.type_label='Medication',
                        k.primary_label='KGNode',
                        k.formal_cdss_ready=false,
                        k.dictionary_validation_status='pending_cdss_dictionary_mapping',
                        k.status='knowledge_only',
                        k.created_at=$now
          SET k.aliases=coalesce(k.aliases, ['potassium chloride','KCl']),
              k.updated_at=$now
        MERGE (i:Medication {code:'MED-CARD-POLAR-INSULIN'})
          ON CREATE SET i.name='胰岛素',
                        i.entityType='Medication',
                        i.type_label='Medication',
                        i.primary_label='KGNode',
                        i.formal_cdss_ready=false,
                        i.dictionary_validation_status='pending_cdss_dictionary_mapping',
                        i.status='knowledge_only',
                        i.aliases=['insulin'],
                        i.created_at=$now
          SET i.updated_at=$now
        MERGE (g:Medication {code:'MED-CARD-POLAR-GLUCOSE'})
          ON CREATE SET g.name='葡萄糖溶液',
                        g.entityType='Medication',
                        g.type_label='Medication',
                        g.primary_label='KGNode',
                        g.formal_cdss_ready=false,
                        g.dictionary_validation_status='pending_cdss_dictionary_mapping',
                        g.status='knowledge_only',
                        g.aliases=['葡萄糖','glucose solution'],
                        g.created_at=$now
          SET g.updated_at=$now
        WITH p, [k,i,g] AS meds
        UNWIND meds AS m
        MERGE (p)-[r:includes_medication]->(m)
        SET r.clinical_stage='治疗决策',
            r.purpose='治疗方案组成药物',
            r.recommendation_scope='治疗方案下游动作',
            r.service_target_type='Disease',
            r.service_target_code='DIS-CARD-CAD-STEMI',
            r.service_target_name='ST段抬高型心肌梗死',
            r.target_entity_type='Medication',
            r.formal_recommendation='no',
            r.semantic_review_status='auto_confirmed',
            r.semantic_patch_batch=$batch,
            r.semantic_patch_time=$now,
            r.source_name='《内科学（第10版）》',
            r.source_section='第三篇 循环系统疾病 / 第四节 急性冠脉综合征 / 二、急性ST段抬高型心肌梗死 / 治疗 / 其他治疗 / 极化液疗法'
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    # 路径阶段候选动作不等于正式推荐，必须明确标识，防止前端误当医嘱推荐。
    updates["stage_has_available_action"] = session.run(
        """
        MATCH (stage:PathwayStage)-[r:stage_has_available_action]->(action)
        SET r.clinical_stage = coalesce(r.clinical_stage, coalesce(stage.name, '专病路径阶段')),
            r.purpose = coalesce(r.purpose, '阶段候选动作'),
            r.service_target_type = coalesce(r.service_target_type, 'PathwayStage'),
            r.service_target_code = coalesce(r.service_target_code, stage.code),
            r.service_target_name = coalesce(r.service_target_name, stage.name),
            r.formal_recommendation = coalesce(r.formal_recommendation, 'no'),
            r.recommendation_scope = coalesce(r.recommendation_scope, '路径阶段候选'),
            r.semantic_review_status = 'auto_confirmed',
            r.semantic_patch_batch = $batch,
            r.semantic_patch_time = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    # 正式推荐陈述 -> 推荐动作：正式推荐展示区只走这条链路。
    updates["recommends_action"] = session.run(
        """
        MATCH (rs:RecommendationStatement)-[r:recommends_action]->(action)
        OPTIONAL MATCH (d:Disease)-[:has_recommendation_statement]->(rs)
        SET r.clinical_stage = coalesce(r.clinical_stage, rs.clinical_stage, '正式推荐'),
            r.purpose = coalesce(r.purpose, rs.recommendation_purpose, '正式推荐动作'),
            r.service_target_type = coalesce(r.service_target_type, CASE WHEN d IS NULL THEN 'RecommendationStatement' ELSE 'Disease' END),
            r.service_target_code = coalesce(r.service_target_code, d.code, rs.code),
            r.service_target_name = coalesce(r.service_target_name, d.name, rs.name),
            r.formal_recommendation = 'yes',
            r.recommendation_scope = coalesce(r.recommendation_scope, '正式CDSS推荐'),
            r.semantic_review_status = 'auto_confirmed',
            r.semantic_patch_batch = $batch,
            r.semantic_patch_time = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).single()["n"]

    return updates


def main() -> None:
    uri, user, password = parse_neo4j_link()
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session() as session:
            before = audit(session)
            updates = execute_updates(session)
            after = audit(session)

    result = {"before": before, "updates": updates, "after": after}
    out_file = OUT_DIR / "全库诊疗链路语义压实_执行结果_20260815.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(str(out_file))


if __name__ == "__main__":
    main()
