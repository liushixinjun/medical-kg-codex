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
        raise RuntimeError("无法从 图谱数据库链接.txt 解析 bolt/user/password")
    return {"uri": bolt.group(1), "user": user.group(1), "password": password.group(1)}


DISEASE_CODES = {
    "急性心肌梗死": "DIS-CARD-CAD-AMI",
    "急性ST段抬高型心肌梗死": "DIS-CARD-CAD-STEMI",
    "急性非ST段抬高型心肌梗死": "DIS-CARD-CAD-NSTEMI",
}


def query_one(tx, disease_name: str, disease_code: str) -> dict:
    q = """
    MATCH (d:Disease {code:$code})
    OPTIONAL MATCH (d)-[old_m:treated_by_medication]->(old_med:Medication)
    WITH d, collect(DISTINCT old_med.name)[0..10] AS old_meds, count(DISTINCT old_m) AS old_med_rels
    OPTIONAL MATCH (d)-[:has_treatment_plan]->(tp:TreatmentPlan)-[new_m:includes_medication]->(new_med:Medication)
    WITH d, old_meds, old_med_rels, collect(DISTINCT new_med.name)[0..10] AS new_meds, count(DISTINCT new_m) AS new_med_rels
    OPTIONAL MATCH (d)-[old_p:treated_by_procedure]->(old_proc:Procedure)
    WITH d, old_meds, old_med_rels, new_meds, new_med_rels, collect(DISTINCT old_proc.name)[0..10] AS old_procs, count(DISTINCT old_p) AS old_proc_rels
    OPTIONAL MATCH (d)-[:has_treatment_plan]->(tp2:TreatmentPlan)-[new_p:includes_procedure]->(new_proc:Procedure)
    WITH d, old_meds, old_med_rels, new_meds, new_med_rels, old_procs, old_proc_rels,
         collect(DISTINCT new_proc.name)[0..10] AS new_procs, count(DISTINCT new_p) AS new_proc_rels
    OPTIONAL MATCH (d)-[epi_r:has_epidemiology]->(epi:Epidemiology)
    WITH d, old_meds, old_med_rels, new_meds, new_med_rels, old_procs, old_proc_rels, new_procs, new_proc_rels,
         collect(DISTINCT epi.name)[0..10] AS epis, count(DISTINCT epi_r) AS epi_rels
    OPTIONAL MATCH (d)-[r]->(x)
    RETURN d.name AS db_name,
           labels(d) AS labels,
           old_med_rels, old_meds,
           new_med_rels, new_meds,
           old_proc_rels, old_procs,
           new_proc_rels, new_procs,
           epi_rels, epis,
           collect(DISTINCT {rel:type(r), labels:labels(x), cnt:1}) AS outgoing_raw
    """
    row = tx.run(q, code=disease_code).single()
    if row is None:
        return {"疾病": disease_name, "code": disease_code, "exists": False}

    # Separate outgoing relation type summary: Neo4j cannot count inside collected map in the compact query above.
    rel_q = """
    MATCH (d:Disease {code:$code})-[r]->(x)
    RETURN type(r) AS rel, labels(x) AS labels, count(*) AS cnt
    ORDER BY cnt DESC, rel
    """
    rels = [dict(r) for r in tx.run(rel_q, code=disease_code)]

    plan_q = """
    MATCH (d:Disease {code:$code})
    OPTIONAL MATCH (d)-[:has_treatment_plan]->(tp:TreatmentPlan)
    WITH d, count(DISTINCT tp) AS treatment_plan_count
    OPTIONAL MATCH (d)-[:has_treatment_plan]->(:TreatmentPlan)-[ra:recommends_action]->(action)
    WITH d, treatment_plan_count, count(DISTINCT ra) AS recommends_action_count
    OPTIONAL MATCH (d)-[:has_treatment_plan]->(:TreatmentPlan)-[bm:blocks_action]->(blocked)
    RETURN treatment_plan_count, recommends_action_count, count(DISTINCT bm) AS blocks_action_count
    """
    plan = dict(tx.run(plan_q, code=disease_code).single())

    return {
        "疾病": disease_name,
        "code": disease_code,
        "exists": True,
        "db_name": row["db_name"],
        "旧直连_药物关系数": row["old_med_rels"],
        "新路径_治疗方案包含药物关系数": row["new_med_rels"],
        "新路径_药物样例": row["new_meds"],
        "旧直连_手术关系数": row["old_proc_rels"],
        "新路径_治疗方案包含手术关系数": row["new_proc_rels"],
        "新路径_手术样例": row["new_procs"],
        "流行病学关系数": row["epi_rels"],
        "流行病学样例": row["epis"],
        "治疗方案数": plan.get("treatment_plan_count", 0),
        "治疗方案正式推荐动作关系数": plan.get("recommends_action_count", 0),
        "治疗方案禁忌阻断关系数": plan.get("blocks_action_count", 0),
        "疾病直接外出关系类型": rels,
    }


def main() -> None:
    cfg = read_neo4j_config()
    driver = GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))
    try:
        with driver.session() as session:
            result = [
                session.execute_read(query_one, name, code)
                for name, code in DISEASE_CODES.items()
            ]
            global_summary = session.execute_read(query_global_summary)
        print(json.dumps({"重点疾病": result, "全库摘要": global_summary}, ensure_ascii=False, indent=2))
    finally:
        driver.close()


def query_global_summary(tx) -> dict:
    q = """
    MATCH (d:Disease)
    WHERE d.status IS NULL OR d.status <> 'deprecated'
    OPTIONAL MATCH (d)-[old_m:treated_by_medication]->(:Medication)
    WITH d, count(DISTINCT old_m) AS old_med
    OPTIONAL MATCH (d)-[:has_treatment_plan]->(:TreatmentPlan)-[new_m:includes_medication]->(:Medication)
    WITH d, old_med, count(DISTINCT new_m) AS new_med
    OPTIONAL MATCH (d)-[old_p:treated_by_procedure]->(:Procedure)
    WITH d, old_med, new_med, count(DISTINCT old_p) AS old_proc
    OPTIONAL MATCH (d)-[:has_treatment_plan]->(:TreatmentPlan)-[new_p:includes_procedure]->(:Procedure)
    WITH d, old_med, new_med, old_proc, count(DISTINCT new_p) AS new_proc
    RETURN
      count(d) AS disease_count,
      count(CASE WHEN old_med > 0 THEN 1 END) AS old_med_disease_count,
      count(CASE WHEN new_med > 0 THEN 1 END) AS new_med_disease_count,
      count(CASE WHEN old_med = 0 AND new_med > 0 THEN 1 END) AS old_med_missing_but_new_exists,
      count(CASE WHEN old_proc > 0 THEN 1 END) AS old_proc_disease_count,
      count(CASE WHEN new_proc > 0 THEN 1 END) AS new_proc_disease_count,
      count(CASE WHEN old_proc = 0 AND new_proc > 0 THEN 1 END) AS old_proc_missing_but_new_exists
    """
    row = tx.run(q).single()

    sample_q = """
    MATCH (d:Disease)
    WHERE d.status IS NULL OR d.status <> 'deprecated'
    OPTIONAL MATCH (d)-[old_m:treated_by_medication]->(:Medication)
    WITH d, count(DISTINCT old_m) AS old_med
    OPTIONAL MATCH (d)-[:has_treatment_plan]->(:TreatmentPlan)-[new_m:includes_medication]->(:Medication)
    WITH d, old_med, count(DISTINCT new_m) AS new_med
    OPTIONAL MATCH (d)-[old_p:treated_by_procedure]->(:Procedure)
    WITH d, old_med, new_med, count(DISTINCT old_p) AS old_proc
    OPTIONAL MATCH (d)-[:has_treatment_plan]->(:TreatmentPlan)-[new_p:includes_procedure]->(:Procedure)
    WITH d, old_med, new_med, old_proc, count(DISTINCT new_p) AS new_proc
    WHERE (old_med = 0 AND new_med > 0) OR (old_proc = 0 AND new_proc > 0)
    RETURN d.code AS code, d.name AS name, old_med, new_med, old_proc, new_proc
    ORDER BY d.name
    LIMIT 20
    """
    samples = [dict(r) for r in tx.run(sample_q)]

    return {**dict(row), "旧口径误判样例": samples}


if __name__ == "__main__":
    main()
