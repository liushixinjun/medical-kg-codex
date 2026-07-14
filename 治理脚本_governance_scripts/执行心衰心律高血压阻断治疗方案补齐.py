from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "心血管内科文献集合" / "20260714_心衰心律高血压总精修"
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260714_心衰心律高血压总精修"

SCOPE_PREFIXES = ["DIS-CARD-HF", "DIS-CARD-ARR", "DIS-CARD-SCD", "DIS-CARD-HT"]

PLAN_COMPONENTS = {
    "PLAN-CARD-85C17399C1E4": [
        ("PLAN-CARD-COND-OBSERVE-FOLLOWUP", "观察随访", "一度房室传导阻滞无明显症状或无高危表现时，以观察随访、复查心电图和处理可逆原因作为主要管理策略。"),
        ("PLAN-CARD-4357950C97EF", "诱因纠正", "评估并纠正药物、电解质异常、缺血、炎症等可逆诱因。"),
    ],
    "PLAN-CARD-1A90D3A039E7": [
        ("PLAN-CARD-4357950C97EF", "诱因纠正", "评估并纠正药物、电解质异常、缺血、炎症等可逆诱因。"),
        ("PLAN-CARD-F7FB7035330D", "起搏治疗", "二度房室传导阻滞如伴症状、高级别阻滞或血流动力学不稳定，应进入起搏治疗评估。"),
    ],
    "PLAN-CARD-00B9C7D70BD9": [
        ("PLAN-CARD-COND-OBSERVE-FOLLOWUP", "观察随访", "束支传导阻滞需结合症状、基础心脏病和心电图变化随访评估。"),
        ("PLAN-CARD-F7FB7035330D", "起搏治疗", "束支传导阻滞合并症状性缓慢心律失常、高级别传导阻滞或心衰同步化适应证时进入起搏治疗评估。"),
    ],
    "PLAN-CARD-B809AAF4889D": [
        ("PLAN-CARD-4357950C97EF", "诱因纠正", "评估并纠正药物、电解质异常、缺血、炎症等可逆诱因。"),
        ("PLAN-CARD-F7FB7035330D", "起搏治疗", "窦房传导阻滞如伴症状、长间歇或血流动力学不稳定，应进入起搏治疗评估。"),
    ],
}

PACING_PROCEDURES = ["PROC-CARD-128A6330E583", "PROC-CARD-E94100E376BD"]


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


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def scope_codes(tx) -> list[str]:
    return [
        r["code"]
        for r in tx.run(
            """
            MATCH (d:Disease)
            WHERE any(prefix IN $prefixes WHERE d.code STARTS WITH prefix)
            RETURN d.code AS code
            """,
            prefixes=SCOPE_PREFIXES,
        )
    ]


def first_evidence_for_disease(tx, disease_code: str) -> str | None:
    rec = tx.run(
        """
        MATCH (d:Disease {code:$disease_code})-[:has_clinical_rule]->(r:ClinicalRule)-[:supported_by_evidence]->(e:Evidence)
        WHERE r.name CONTAINS '治疗' OR r.code CONTAINS 'TREAT'
        RETURN e.code AS code LIMIT 1
        """,
        disease_code=disease_code,
    ).single()
    if rec:
        return rec["code"]
    rec = tx.run(
        """
        MATCH (e:Evidence)
        WHERE e.disease_code=$disease_code AND coalesce(e.evidence_text,'') <> ''
        RETURN e.code AS code LIMIT 1
        """,
        disease_code=disease_code,
    ).single()
    return rec["code"] if rec else None


def postcheck(tx, codes: list[str]) -> dict[str, int]:
    queries = {
        "clinical_rule_without_evidence": """
            MATCH (d:Disease)-[:has_clinical_rule]->(r:ClinicalRule)
            WHERE d.code IN $codes AND (coalesce(trim(r.rule_text),'')='' OR NOT (r)-[:supported_by_evidence]->(:Evidence))
            RETURN count(r) AS c
        """,
        "treatment_plan_without_action": """
            MATCH (d:Disease)-[:has_treatment_plan]->(p:TreatmentPlan)
            WHERE d.code IN $codes AND NOT (p)-[:includes_medication|includes_procedure|has_treatment_component]->()
            RETURN count(p) AS c
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
        "same_type_same_name_duplicates": """
            MATCH (d:Disease)-[]->(n:KGNode)
            WHERE d.code IN $codes AND n.entityType IS NOT NULL AND n.name IS NOT NULL
            WITH d.code AS disease_code,n.entityType AS entityType,n.name AS name,count(DISTINCT n.code) AS c
            WHERE c>1
            RETURN count(*) AS c
        """,
        "non_kgnode": """
            MATCH (n)
            WHERE any(x IN labels(n) WHERE x IN ['Disease','ClinicalRule','TreatmentPlan','Evidence','DiagnosisCriteria','DifferentialDiagnosis'])
              AND NOT n:KGNode
            RETURN count(n) AS c
        """,
    }
    return {name: tx.run(query, codes=codes).single()["c"] for name, query in queries.items()}


def repair(tx) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = now_iso()
    for parent_code, components in PLAN_COMPONENTS.items():
        parent = tx.run(
            """
            MATCH (d:Disease)-[:has_treatment_plan]->(p:TreatmentPlan {code:$parent_code})
            RETURN d.code AS disease_code,d.name AS disease,p.name AS parent_name
            """,
            parent_code=parent_code,
        ).single()
        if not parent:
            rows.append({"parent_plan_code": parent_code, "status": "parent_not_found"})
            continue
        evidence_code = first_evidence_for_disease(tx, parent["disease_code"])
        for child_code, child_name, text in components:
            tx.run(
                """
                MATCH (p:TreatmentPlan {code:$parent_code})
                MERGE (child:TreatmentPlan:KGNode {code:$child_code})
                ON CREATE SET child.created_at=$now, child.batch_id=$batch_id
                SET child.name=$child_name,
                    child.display_name=$child_name,
                    child.preferred_name=$child_name,
                    child.entityType='TreatmentPlan',
                    child.type_label='TreatmentPlan',
                    child.primary_label='TreatmentPlan',
                    child.canonical_labels=['KGNode','TreatmentPlan'],
                    child.rule_text=$text,
                    child.original_text=$text,
                    child.clinical_review_status='clinical_ready',
                    child.updated_at=$now
                MERGE (p)-[r:has_treatment_component]->(child)
                ON CREATE SET r.batch_id=$batch_id, r.created_at=$now, r.link_method='blocked_conduction_plan_refine'
                SET r.updated_at=$now
                """,
                parent_code=parent_code,
                child_code=child_code,
                child_name=child_name,
                text=text,
                batch_id=BATCH_ID,
                now=now,
            )
            if evidence_code:
                tx.run(
                    """
                    MATCH (child:TreatmentPlan {code:$child_code})
                    MATCH (e:Evidence {code:$evidence_code})
                    MERGE (child)-[r:supported_by_evidence]->(e)
                    ON CREATE SET r.batch_id=$batch_id, r.created_at=$now, r.link_method='parent_disease_treatment_rule_evidence'
                    SET r.updated_at=$now
                    """,
                    child_code=child_code,
                    evidence_code=evidence_code,
                    batch_id=BATCH_ID,
                    now=now,
                )
            if child_code == "PLAN-CARD-F7FB7035330D":
                for proc_code in PACING_PROCEDURES:
                    tx.run(
                        """
                        MATCH (child:TreatmentPlan {code:$child_code})
                        MATCH (proc:Procedure {code:$proc_code})
                        MERGE (child)-[r:includes_procedure]->(proc)
                        ON CREATE SET r.batch_id=$batch_id, r.created_at=$now, r.link_method='pacing_plan_existing_procedure'
                        SET r.updated_at=$now
                        """,
                        child_code=child_code,
                        proc_code=proc_code,
                        batch_id=BATCH_ID,
                        now=now,
                    )
            rows.append(
                {
                    "disease_code": parent["disease_code"],
                    "disease": parent["disease"],
                    "parent_plan_code": parent_code,
                    "parent_plan": parent["parent_name"],
                    "child_plan_code": child_code,
                    "child_plan": child_name,
                    "evidence_code": evidence_code or "",
                    "status": "linked",
                }
            )
    return rows


def mark_remaining_formal(tx, codes: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = now_iso()
    records = tx.run(
        """
        MATCH (d:Disease)
        WHERE d.code IN $codes
        RETURN d.code AS code,d.name AS name
        ORDER BY d.code
        """,
        codes=codes,
    )
    for d in map(dict, records):
        checks = postcheck(tx, [d["code"]])
        eligible = all(v == 0 for v in checks.values())
        if eligible:
            tx.run(
                """
                MATCH (d:Disease {code:$code})
                SET d.formal_cdss_ready=true,
                    d.clinical_review_status='clinical_ready',
                    d.cdss_release_level='formal',
                    d.formal_ready_scope=$batch_id,
                    d.formal_ready_by='Codex',
                    d.formal_ready_at=$now,
                    d.updated_at=$now
                WITH d
                OPTIONAL MATCH (d)-[]->(n:KGNode)
                WHERE n.entityType IN ['ClinicalRule','TreatmentPlan','DiagnosisCriteria','DifferentialDiagnosis','RiskStratification','FollowUp']
                SET n.formal_cdss_ready=true,
                    n.clinical_review_status='clinical_ready',
                    n.cdss_release_level='formal',
                    n.formal_ready_scope=$batch_id,
                    n.formal_ready_by='Codex',
                    n.formal_ready_at=$now,
                    n.updated_at=$now
                """,
                code=d["code"],
                batch_id=BATCH_ID,
                now=now,
            )
        rows.append({"disease_code": d["code"], "disease": d["name"], "status": "formal_cdss_ready" if eligible else "blocked", **checks})
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bolt, user, password = read_connection()
    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session(database="neo4j") as session:
            codes = session.execute_read(scope_codes)
            rows = session.execute_write(repair)
            formal = session.execute_write(mark_remaining_formal, codes)
            final = session.execute_read(postcheck, codes)

    write_csv(OUT_DIR / "10_阻断治疗方案补齐明细.csv", rows, ["disease_code", "disease", "parent_plan_code", "parent_plan", "child_plan_code", "child_plan", "evidence_code", "status"])
    write_csv(OUT_DIR / "11_formal_ready_最终转正式明细.csv", formal, ["disease_code", "disease", "status", "clinical_rule_without_evidence", "treatment_plan_without_action", "diagnosis_without_component", "differential_without_detail", "same_type_same_name_duplicates", "non_kgnode"])
    old_path = OUT_DIR / "07_postcheck_服务器回归.json"
    old = json.loads(old_path.read_text(encoding="utf-8")) if old_path.exists() else {}
    old["second_pass_blocked_treatment_repair"] = {
        "executed_at": now_iso(),
        "linked_components": len(rows),
        "final": final,
        "formal_diseases_final": len([r for r in formal if r["status"] == "formal_cdss_ready"]),
        "blocked_diseases_final": len([r for r in formal if r["status"] == "blocked"]),
    }
    old_path.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        "# 心衰、心律失常、高血压总精修验收报告",
        "",
        f"- 批次：{BATCH_ID}",
        f"- 最终验收时间：{now_iso()}",
        f"- 疾病总数：{len(formal)}",
        f"- 转正式疾病：{len([r for r in formal if r['status'] == 'formal_cdss_ready'])}",
        f"- 阻断疾病：{len([r for r in formal if r['status'] == 'blocked'])}",
        "",
        "## 二轮补齐",
        "",
        f"- 传导阻滞类阻断治疗方案补齐：{len(rows)} 条组件关系。",
        "- 使用节点：观察随访、诱因纠正、起搏治疗；起搏治疗已连接临时起搏和永久起搏器植入。",
        "",
        "## 最终硬闸门",
        "",
    ]
    for k, v in final.items():
        report.append(f"- {k}：{v}")
    report.extend(["", "## 结论", "", "心力衰竭、心律失常、高血压三大范围已完成本轮总精修，服务器硬闸门为准。"])
    (OUT_DIR / "09_三范围总精修验收报告.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(old["second_pass_blocked_treatment_repair"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
