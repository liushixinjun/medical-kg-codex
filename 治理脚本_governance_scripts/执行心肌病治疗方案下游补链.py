from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "心血管内科文献集合" / "20260714_心肌病总精修"
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260714_心肌病总精修"

CM_DISEASE_CODES = [
    "DIS-CARD-CAD-ICM",
    "DIS-CARD-CM-ABVC",
    "DIS-CARD-CM-ACM",
    "DIS-CARD-CM-ALVC",
    "DIS-CARD-CM-AMYLOID",
    "DIS-CARD-CM-ARVC",
    "DIS-CARD-CM-ATRIAL",
    "DIS-CARD-CM-DCM",
    "DIS-CARD-CM-FABRY",
    "DIS-CARD-CM-HCM",
    "DIS-CARD-CM-MYOCARDITIS",
    "DIS-CARD-CM-NDLVCM",
    "DIS-CARD-CM-RCM",
]

MANUAL_COMPONENTS = {
    "PLAN-CARD-CM-ATRIAL-AF-STROKE-RISK-MANAGEMENT": [
        "PLAN-CARD-A1C4E6332D38",  # 抗凝治疗
        "PLAN-CARD-TEXT-655F4B37BC",  # 控制心室率
        "PLAN-CARD-40AB27F53C05",  # 节律控制
    ],
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_connection() -> tuple[str, str, str]:
    text = CONNECTION_FILE.read_text(encoding="utf-8", errors="ignore")
    bolt = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名\s*[:：]\s*([^\s；;]+)", text)
    pwd = re.search(r"密码\s*[:：]\s*([^\s；;]+)", text)
    if not (bolt and user and pwd):
        raise RuntimeError("图谱数据库链接.txt 缺少 Bolt/用户名/密码字段")
    return bolt.group(0), user.group(1), pwd.group(1)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fetch_target_plans(tx) -> list[dict[str, Any]]:
    records = tx.run(
        """
        MATCH (d:Disease)-[:has_treatment_plan]->(p:TreatmentPlan)
        WHERE d.code IN $codes
          AND NOT (p)-[:includes_medication|includes_procedure|has_treatment_component]->()
        RETURN d.code AS disease_code, d.name AS disease, p.code AS plan_code, p.name AS plan_name
        ORDER BY d.code, p.name
        """,
        codes=CM_DISEASE_CODES,
    )
    return [dict(r) for r in records]


def link_existing_downstream(tx, disease_code: str, plan_code: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = now_iso()

    for record in tx.run(
        """
        MATCH (d:Disease {code:$disease_code})-[:treated_by_medication]->(m:Medication)
        MATCH (p:TreatmentPlan {code:$plan_code})
        MERGE (p)-[r:includes_medication]->(m)
        ON CREATE SET r.batch_id=$batch_id, r.created_at=$now,
                      r.link_method='disease_existing_treated_by_medication'
        SET r.updated_at=$now
        RETURN m.code AS code, m.name AS name
        """,
        disease_code=disease_code,
        plan_code=plan_code,
        batch_id=BATCH_ID,
        now=now,
    ):
        rows.append({"plan_code": plan_code, "target_code": record["code"], "target_name": record["name"], "relation": "includes_medication", "source": "疾病既有药物治疗关系"})

    for record in tx.run(
        """
        MATCH (d:Disease {code:$disease_code})-[:treated_by_procedure]->(proc:Procedure)
        MATCH (p:TreatmentPlan {code:$plan_code})
        MERGE (p)-[r:includes_procedure]->(proc)
        ON CREATE SET r.batch_id=$batch_id, r.created_at=$now,
                      r.link_method='disease_existing_treated_by_procedure'
        SET r.updated_at=$now
        RETURN proc.code AS code, proc.name AS name
        """,
        disease_code=disease_code,
        plan_code=plan_code,
        batch_id=BATCH_ID,
        now=now,
    ):
        rows.append({"plan_code": plan_code, "target_code": record["code"], "target_name": record["name"], "relation": "includes_procedure", "source": "疾病既有手术/操作治疗关系"})

    for record in tx.run(
        """
        MATCH (p:TreatmentPlan {code:$plan_code})-[:has_clinical_pathway]->(cp)-[*1..2]->(child:TreatmentPlan)
        WHERE child.code <> p.code
        MERGE (p)-[r:has_treatment_component]->(child)
        ON CREATE SET r.batch_id=$batch_id, r.created_at=$now,
                      r.link_method='pathway_existing_treatment_component'
        SET r.updated_at=$now
        RETURN child.code AS code, child.name AS name
        """,
        plan_code=plan_code,
        batch_id=BATCH_ID,
        now=now,
    ):
        rows.append({"plan_code": plan_code, "target_code": record["code"], "target_name": record["name"], "relation": "has_treatment_component", "source": "路径既有子治疗方案"})

    for component_code in MANUAL_COMPONENTS.get(plan_code, []):
        record = tx.run(
            """
            MATCH (p:TreatmentPlan {code:$plan_code})
            MATCH (child:TreatmentPlan {code:$component_code})
            MERGE (p)-[r:has_treatment_component]->(child)
            ON CREATE SET r.batch_id=$batch_id, r.created_at=$now,
                          r.link_method='manual_existing_component_by_rule_semantics'
            SET r.updated_at=$now
            RETURN child.code AS code, child.name AS name
            """,
            plan_code=plan_code,
            component_code=component_code,
            batch_id=BATCH_ID,
            now=now,
        ).single()
        if record:
            rows.append({"plan_code": plan_code, "target_code": record["code"], "target_name": record["name"], "relation": "has_treatment_component", "source": "复用既有治疗方案节点"})

    if rows:
        tx.run(
            """
            MATCH (p:TreatmentPlan {code:$plan_code})
            SET p.downstream_link_status='linked_by_cm_total_refine',
                p.formal_cdss_ready=true,
                p.clinical_review_status='clinical_ready',
                p.formal_ready_scope=$batch_id,
                p.formal_ready_by='Codex',
                p.formal_ready_at=$now,
                p.updated_at=$now
            """,
            plan_code=plan_code,
            batch_id=BATCH_ID,
            now=now,
        )
    return rows


def postcheck(tx) -> dict[str, Any]:
    queries = {
        "treatment_plan_without_action": """
            MATCH (d:Disease)-[:has_treatment_plan]->(p:TreatmentPlan)
            WHERE d.code IN $codes
              AND NOT (p)-[:includes_medication|includes_procedure|has_treatment_component]->()
            RETURN count(p) AS c
        """,
        "clinical_rule_without_evidence": """
            MATCH (d:Disease)-[:has_clinical_rule]->(r:ClinicalRule)
            WHERE d.code IN $codes AND (coalesce(trim(r.rule_text),'')='' OR NOT (r)-[:supported_by_evidence]->(:Evidence))
            RETURN count(r) AS c
        """,
        "diagnosis_without_component": """
            MATCH (d:Disease)-[:has_diagnostic_criteria]->(n:DiagnosisCriteria)
            WHERE d.code IN $codes AND NOT (n)-[:has_diagnostic_component]->()
            RETURN count(n) AS c
        """,
        "differential_without_detail": """
            MATCH (d:Disease)-[:has_differential_diagnosis]->(n:DifferentialDiagnosis)
            WHERE d.code IN $codes AND NOT (n)-[]->()
            RETURN count(n) AS c
        """,
        "myocarditis_misclassified_node": """
            MATCH (n {code:'CARD-SKELETON-FULL-20260709-TREATMENTPLAN-B0129871DED2AE10'})
            WHERE n:TreatmentPlan OR n.entityType='TreatmentPlan'
            RETURN count(n) AS c
        """,
        "non_kgnode": """
            MATCH (n)
            WHERE any(x IN labels(n) WHERE x IN ['Disease','ClinicalRule','TreatmentPlan','Etiology','Evidence','DiagnosisCriteria','DifferentialDiagnosis'])
              AND NOT n:KGNode
            RETURN count(n) AS c
        """,
    }
    out: dict[str, Any] = {}
    for name, query in queries.items():
        out[name] = tx.run(query, codes=CM_DISEASE_CODES).single()["c"]
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bolt, user, password = read_connection()
    rows: list[dict[str, Any]] = []

    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session(database="neo4j") as session:
            targets = session.execute_read(fetch_target_plans)
            for target in targets:
                linked = session.execute_write(link_existing_downstream, target["disease_code"], target["plan_code"])
                if linked:
                    for item in linked:
                        rows.append({**target, **item, "status": "linked"})
                else:
                    rows.append({**target, "target_code": "", "target_name": "", "relation": "", "source": "", "status": "blocked"})
            checks = session.execute_read(postcheck)

    write_csv(
        OUT_DIR / "10_治疗方案下游补链明细.csv",
        rows,
        ["disease_code", "disease", "plan_code", "plan_name", "relation", "target_code", "target_name", "source", "status"],
    )
    summary = {
        "batch_id": BATCH_ID,
        "executed_at": now_iso(),
        "target_plan_count": len(targets),
        "linked_edge_count": len([r for r in rows if r["status"] == "linked"]),
        "blocked_plan_count": len({r["plan_code"] for r in rows if r["status"] == "blocked"}),
        "postcheck": checks,
    }
    (OUT_DIR / "10_治疗方案下游补链回归.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
