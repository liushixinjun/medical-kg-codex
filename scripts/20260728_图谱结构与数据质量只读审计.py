from __future__ import annotations

import json
import re
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
LINK_FILE = ROOT / "图谱数据库链接.txt"


def read_neo4j_config() -> dict:
    text = LINK_FILE.read_text(encoding="utf-8", errors="ignore")
    bolt = re.search(r"(bolt://[^\s，,;]+)", text, re.I)
    user = re.search(r"(?:用户名|user|username)\s*[:：]\s*([^\s，,;]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,;]+)", text, re.I)
    if not (bolt and user and password):
        raise RuntimeError("无法从 图谱数据库链接.txt 解析 Neo4j 连接信息")
    return {"uri": bolt.group(1), "user": user.group(1), "password": password.group(1)}


def q_single(tx, cypher: str, **params) -> dict:
    row = tx.run(cypher, **params).single()
    return dict(row) if row else {}


def q_list(tx, cypher: str, **params) -> list[dict]:
    return [dict(r) for r in tx.run(cypher, **params)]


def audit(tx) -> dict:
    result: dict = {}

    result["疾病主数据"] = q_single(
        tx,
        """
        MATCH (d:Disease)
        WHERE d.status IS NULL OR d.status <> 'deprecated'
        RETURN count(d) AS 疾病总数,
               count(CASE WHEN d.diagnostic_role IS NULL OR d.diagnostic_role = '' THEN 1 END) AS 缺diagnostic_role,
               count(CASE WHEN d.is_diagnosable IS NULL THEN 1 END) AS 缺is_diagnosable,
               count(CASE WHEN d.code IS NULL OR d.code = '' THEN 1 END) AS 缺code,
               count(CASE WHEN d.name IS NULL OR d.name = '' THEN 1 END) AS 缺name
        """,
    )

    result["疾病角色分布"] = q_list(
        tx,
        """
        MATCH (d:Disease)
        WHERE d.status IS NULL OR d.status <> 'deprecated'
        RETURN coalesce(d.diagnostic_role, '未设置') AS 角色, count(*) AS 数量
        ORDER BY 数量 DESC
        """,
    )

    result["标准诊断映射"] = q_single(
        tx,
        """
        MATCH (d:Disease)
        WHERE d.status IS NULL OR d.status <> 'deprecated'
        OPTIONAL MATCH (d)-[:has_standard_diagnosis]->(sd:StandardDiagnosis)
        WITH d, count(sd) AS c
        RETURN count(d) AS 疾病总数,
               count(CASE WHEN c > 0 THEN 1 END) AS 已连标准诊断,
               count(CASE WHEN c = 0 THEN 1 END) AS 未连标准诊断
        """,
    )

    result["疾病层级关系"] = q_single(
        tx,
        """
        MATCH (d:Disease)
        WHERE d.status IS NULL OR d.status <> 'deprecated'
        OPTIONAL MATCH (p:Disease)-[:has_clinical_subtype]->(d)
        WITH d, count(p) AS parent_count
        RETURN count(d) AS 疾病总数,
               count(CASE WHEN d.diagnostic_role = 'clinical_subtype' AND parent_count = 0 THEN 1 END) AS 具体分型无父级,
               count(CASE WHEN d.diagnostic_role = 'broad_diagnosis' AND parent_count > 0 THEN 1 END) AS 宽口径诊断有父级
        """,
    )

    result["治疗方案新旧路径"] = q_single(
        tx,
        """
        MATCH (d:Disease)
        WHERE d.status IS NULL OR d.status <> 'deprecated'
        OPTIONAL MATCH (d)-[old_m:treated_by_medication]->(:Medication)
        WITH d, count(old_m) AS old_m
        OPTIONAL MATCH (d)-[old_p:treated_by_procedure]->(:Procedure)
        WITH d, old_m, count(old_p) AS old_p
        OPTIONAL MATCH (d)-[:has_treatment_plan]->(:TreatmentPlan)-[new_m:includes_medication]->(:Medication)
        WITH d, old_m, old_p, count(new_m) AS new_m
        OPTIONAL MATCH (d)-[:has_treatment_plan]->(:TreatmentPlan)-[new_p:includes_procedure]->(:Procedure)
        WITH d, old_m, old_p, new_m, count(new_p) AS new_p
        RETURN count(d) AS 疾病总数,
               sum(old_m) AS 旧直连药物关系数,
               sum(old_p) AS 旧直连手术关系数,
               count(CASE WHEN new_m > 0 THEN 1 END) AS 新路径有药物疾病数,
               count(CASE WHEN new_p > 0 THEN 1 END) AS 新路径有手术疾病数,
               count(CASE WHEN old_m = 0 AND new_m > 0 THEN 1 END) AS 旧口径会误判药物缺失疾病数,
               count(CASE WHEN old_p = 0 AND new_p > 0 THEN 1 END) AS 旧口径会误判手术缺失疾病数
        """,
    )

    result["治疗方案空壳"] = q_single(
        tx,
        """
        MATCH (tp:TreatmentPlan)
        WHERE tp.status IS NULL OR tp.status <> 'deprecated'
        OPTIONAL MATCH (tp)-[m:includes_medication]->(:Medication)
        WITH tp, count(m) AS med_c
        OPTIONAL MATCH (tp)-[p:includes_procedure]->(:Procedure)
        WITH tp, med_c, count(p) AS proc_c
        OPTIONAL MATCH (tp)-[a:recommends_action]->()
        WITH tp, med_c, proc_c, count(a) AS action_c
        RETURN count(tp) AS 治疗方案总数,
               count(CASE WHEN med_c = 0 AND proc_c = 0 AND action_c = 0 THEN 1 END) AS 无药物无手术无动作方案数
        """,
    )

    result["检查检验路径"] = q_single(
        tx,
        """
        MATCH (d:Disease)
        WHERE d.status IS NULL OR d.status <> 'deprecated'
        OPTIONAL MATCH (d)-[:has_exam_plan]->(:ExamPlan)-[ei:includes_exam_item]->(:ExamItem)
        WITH d, count(ei) AS exam_items
        OPTIONAL MATCH (d)-[:has_exam_plan]->(:ExamPlan)-[li:includes_lab_item]->(:LabItem)
        WITH d, exam_items, count(li) AS lab_items
        OPTIONAL MATCH (d)-[:has_exam_plan]->(:ExamPlan)-[bad1]->(:ExamObservation)
        WITH d, exam_items, lab_items, count(bad1) AS direct_obs
        OPTIONAL MATCH (d)-[:has_exam_plan]->(:ExamPlan)-[bad2]->(:LabSubitem)
        WITH d, exam_items, lab_items, direct_obs, count(bad2) AS direct_subitem
        RETURN count(d) AS 疾病总数,
               count(CASE WHEN exam_items > 0 THEN 1 END) AS 有检查项目疾病数,
               count(CASE WHEN lab_items > 0 THEN 1 END) AS 有检验项目疾病数,
               sum(direct_obs) AS ExamPlan直连检查发现数_应为0,
               sum(direct_subitem) AS ExamPlan直连检验细项数_应为0
        """,
    )

    result["检查检验下钻"] = q_single(
        tx,
        """
        MATCH (ei:ExamItem)
        WHERE ei.status IS NULL OR ei.status <> 'deprecated'
        OPTIONAL MATCH (ei)-[r:exam_item_has_observation]->(:ExamObservation)
        WITH count(DISTINCT ei) AS exam_total,
             count(DISTINCT CASE WHEN r IS NOT NULL THEN ei END) AS exam_with_obs
        MATCH (li:LabItem)
        WHERE li.status IS NULL OR li.status <> 'deprecated'
        OPTIONAL MATCH (li)-[r2:lab_item_has_subitem]->(:LabSubitem)
        RETURN exam_total AS 检查项目总数,
               exam_with_obs AS 有检查发现下钻的检查项目数,
               count(DISTINCT li) AS 检验项目总数,
               count(DISTINCT CASE WHEN r2 IS NOT NULL THEN li END) AS 有检验细项下钻的检验项目数
        """,
    )

    result["手术标准字典映射"] = q_single(
        tx,
        """
        MATCH (p:Procedure)
        WHERE p.status IS NULL OR p.status <> 'deprecated'
        OPTIONAL MATCH (p)-[:has_standard_procedure]->(sp:StandardProcedure)
        WITH p, count(sp) AS c
        RETURN count(p) AS 手术实体总数,
               count(CASE WHEN c > 0 THEN 1 END) AS 已连标准手术,
               count(CASE WHEN c = 0 THEN 1 END) AS 未连标准手术
        """,
    )

    result["孤立标准手术"] = q_single(
        tx,
        """
        MATCH (sp:StandardProcedure)
        WHERE sp.status IS NULL OR sp.status <> 'deprecated'
        OPTIONAL MATCH (p:Procedure)-[:has_standard_procedure]->(sp)
        WITH sp, count(p) AS c
        RETURN count(sp) AS 标准手术总数,
               count(CASE WHEN c = 0 THEN 1 END) AS 未被手术实体引用数
        """,
    )

    result["正式CDSS推荐链路"] = q_single(
        tx,
        """
        MATCH (rs:RecommendationStatement)
        WHERE rs.status IS NULL OR rs.status <> 'deprecated'
        OPTIONAL MATCH (rs)-[:recommends_action]->(a)
        WITH rs, count(a) AS action_c
        OPTIONAL MATCH (rs)-[:blocks_action]->(b)
        WITH rs, action_c, count(b) AS block_c
        OPTIONAL MATCH (rs)-[:supported_by_evidence]->(e)
        WITH rs, action_c, block_c, count(e) AS evidence_c
        OPTIONAL MATCH (rs)-[:based_on_guideline]->(g)
        WITH rs, action_c, block_c, evidence_c, count(g) AS guideline_c
        RETURN count(rs) AS 推荐陈述总数,
               count(CASE WHEN action_c + block_c = 0 THEN 1 END) AS 无推荐或阻断动作,
               count(CASE WHEN evidence_c = 0 THEN 1 END) AS 无证据,
               count(CASE WHEN guideline_c = 0 THEN 1 END) AS 无指南,
               count(CASE WHEN rs.formal_cdss_ready = true THEN 1 END) AS formal_cdss_ready数量
        """,
    )

    result["场景区分字段落库情况"] = q_list(
        tx,
        """
        CALL {
          MATCH ()-[r:includes_exam_item]->()
          RETURN 'includes_exam_item' AS 关系, count(r) AS 总数,
                 count(CASE WHEN r.clinical_stage IS NOT NULL AND r.clinical_stage <> '' THEN 1 END) AS 有诊疗阶段,
                 count(CASE WHEN r.use_purpose IS NOT NULL AND r.use_purpose <> '' THEN 1 END) AS 有用途,
                 count(CASE WHEN r.required_level IS NOT NULL AND r.required_level <> '' THEN 1 END) AS 有必需程度,
                 count(CASE WHEN r.trigger_condition IS NOT NULL AND r.trigger_condition <> '' THEN 1 END) AS 有触发条件
          UNION ALL
          MATCH ()-[r:includes_lab_item]->()
          RETURN 'includes_lab_item' AS 关系, count(r) AS 总数,
                 count(CASE WHEN r.clinical_stage IS NOT NULL AND r.clinical_stage <> '' THEN 1 END) AS 有诊疗阶段,
                 count(CASE WHEN r.use_purpose IS NOT NULL AND r.use_purpose <> '' THEN 1 END) AS 有用途,
                 count(CASE WHEN r.required_level IS NOT NULL AND r.required_level <> '' THEN 1 END) AS 有必需程度,
                 count(CASE WHEN r.trigger_condition IS NOT NULL AND r.trigger_condition <> '' THEN 1 END) AS 有触发条件
          UNION ALL
          MATCH ()-[r:includes_medication]->()
          RETURN 'includes_medication' AS 关系, count(r) AS 总数,
                 count(CASE WHEN r.clinical_stage IS NOT NULL AND r.clinical_stage <> '' THEN 1 END) AS 有诊疗阶段,
                 count(CASE WHEN r.use_purpose IS NOT NULL AND r.use_purpose <> '' THEN 1 END) AS 有用途,
                 count(CASE WHEN r.required_level IS NOT NULL AND r.required_level <> '' THEN 1 END) AS 有必需程度,
                 count(CASE WHEN r.trigger_condition IS NOT NULL AND r.trigger_condition <> '' THEN 1 END) AS 有触发条件
          UNION ALL
          MATCH ()-[r:includes_procedure]->()
          RETURN 'includes_procedure' AS 关系, count(r) AS 总数,
                 count(CASE WHEN r.clinical_stage IS NOT NULL AND r.clinical_stage <> '' THEN 1 END) AS 有诊疗阶段,
                 count(CASE WHEN r.use_purpose IS NOT NULL AND r.use_purpose <> '' THEN 1 END) AS 有用途,
                 count(CASE WHEN r.required_level IS NOT NULL AND r.required_level <> '' THEN 1 END) AS 有必需程度,
                 count(CASE WHEN r.trigger_condition IS NOT NULL AND r.trigger_condition <> '' THEN 1 END) AS 有触发条件
          UNION ALL
          MATCH ()-[r:recommends_action]->()
          RETURN 'recommends_action' AS 关系, count(r) AS 总数,
                 count(CASE WHEN r.clinical_stage IS NOT NULL AND r.clinical_stage <> '' THEN 1 END) AS 有诊疗阶段,
                 count(CASE WHEN r.use_purpose IS NOT NULL AND r.use_purpose <> '' THEN 1 END) AS 有用途,
                 count(CASE WHEN r.required_level IS NOT NULL AND r.required_level <> '' THEN 1 END) AS 有必需程度,
                 count(CASE WHEN r.trigger_condition IS NOT NULL AND r.trigger_condition <> '' THEN 1 END) AS 有触发条件
        }
        RETURN 关系, 总数, 有诊疗阶段, 有用途, 有必需程度, 有触发条件
        ORDER BY 关系
        """,
    )

    result["疑似高风险技术字段展示污染样例"] = q_list(
        tx,
        """
        MATCH (d:Disease)
        WHERE d.status IS NULL OR d.status <> 'deprecated'
        WITH d, keys(d) AS ks
        UNWIND ks AS k
        WITH k, count(*) AS c
        WHERE k IN [
          'batch_id','source_roots','source_batch_id','parser_version','raw_id','legacy_id',
          'merge_key','kg_import_batch','clinical_review_status','source_type',
          'source_section_path','evidence_ids','rule_ids'
        ]
        RETURN k AS 属性名, c AS 疾病节点出现数
        ORDER BY c DESC, k
        """,
    )

    return result


def main() -> None:
    cfg = read_neo4j_config()
    driver = GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))
    try:
        with driver.session() as session:
            result = session.execute_read(audit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
