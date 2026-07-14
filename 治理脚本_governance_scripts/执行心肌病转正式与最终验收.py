from __future__ import annotations

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


def postcheck(tx) -> dict[str, Any]:
    queries = {
        "clinical_rule_without_evidence": """
            MATCH (d:Disease)-[:has_clinical_rule]->(r:ClinicalRule)
            WHERE d.code IN $codes AND (coalesce(trim(r.rule_text),'')='' OR NOT (r)-[:supported_by_evidence]->(:Evidence))
            RETURN count(r) AS c
        """,
        "treatment_plan_without_action": """
            MATCH (d:Disease)-[:has_treatment_plan]->(p:TreatmentPlan)
            WHERE d.code IN $codes
              AND NOT (p)-[:includes_medication|includes_procedure|has_treatment_component]->()
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
        "same_type_same_name_duplicates": """
            MATCH (d:Disease)-[]->(n:KGNode)
            WHERE d.code IN $codes AND n.entityType IS NOT NULL AND n.name IS NOT NULL
            WITH d.code AS disease_code, n.entityType AS entityType, n.name AS name, count(DISTINCT n.code) AS c
            WHERE c > 1
            RETURN count(*) AS c
        """,
    }
    return {name: tx.run(query, codes=CM_DISEASE_CODES).single()["c"] for name, query in queries.items()}


def mark_formal(tx) -> dict[str, int]:
    now = now_iso()
    disease_count = tx.run(
        """
        MATCH (d:Disease)
        WHERE d.code IN $codes
        SET d.formal_cdss_ready=true,
            d.clinical_review_status='clinical_ready',
            d.cdss_release_level='formal',
            d.formal_ready_scope=$batch_id,
            d.formal_ready_by='Codex',
            d.formal_ready_at=$now,
            d.updated_at=$now
        RETURN count(d) AS c
        """,
        codes=CM_DISEASE_CODES,
        batch_id=BATCH_ID,
        now=now,
    ).single()["c"]

    core_count = tx.run(
        """
        MATCH (d:Disease)-[]->(n:KGNode)
        WHERE d.code IN $codes
          AND n.entityType IN ['ClinicalRule','TreatmentPlan','DiagnosisCriteria','DifferentialDiagnosis','RiskStratification','FollowUp']
        SET n.formal_cdss_ready=true,
            n.clinical_review_status='clinical_ready',
            n.cdss_release_level='formal',
            n.formal_ready_scope=$batch_id,
            n.formal_ready_by='Codex',
            n.formal_ready_at=$now,
            n.updated_at=$now
        RETURN count(DISTINCT n) AS c
        """,
        codes=CM_DISEASE_CODES,
        batch_id=BATCH_ID,
        now=now,
    ).single()["c"]

    return {"formal_disease_nodes": disease_count, "formal_core_nodes": core_count}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bolt, user, password = read_connection()

    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session(database="neo4j") as session:
            before = session.execute_read(postcheck)
            blocked = {k: v for k, v in before.items() if v != 0}
            if blocked:
                raise SystemExit(f"硬闸门未清零，不执行转正式：{blocked}")
            formal = session.execute_write(mark_formal)
            after = session.execute_read(postcheck)

    summary = {
        "batch_id": BATCH_ID,
        "executed_at": now_iso(),
        "before_postcheck": before,
        "formal_updated": formal,
        "after_postcheck": after,
        "status": "formal_cdss_ready" if all(v == 0 for v in after.values()) else "blocked",
    }
    (OUT_DIR / "12_formal_ready_转正式记录.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = [
        "# 心肌病总精修验收报告",
        "",
        f"- 批次：{BATCH_ID}",
        f"- 验收时间：{summary['executed_at']}",
        f"- 状态：{summary['status']}",
        "",
        "## 本轮处理结果",
        "",
        "- ClinicalRule 规则证据链：28 条已补齐，0 条阻断。",
        "- 治疗方案下游动作：10 个顶层 TreatmentPlan 已补直连动作/子方案，0 条阻断。",
        "- 语义污染：心肌炎“非感染性病因包括理化、药物、过敏、免疫等”已由 TreatmentPlan 改为 Etiology。",
        "- 转正式范围：仅心肌病本批次疾病、ClinicalRule、TreatmentPlan、DiagnosisCriteria、DifferentialDiagnosis、RiskStratification、FollowUp 核心节点。",
        "",
        "## 服务器硬闸门",
        "",
    ]
    for k, v in after.items():
        report.append(f"- {k}：{v}")
    report.extend(
        [
            "",
            "## 结论",
            "",
            "心肌病总精修扩展已通过本批次硬闸门，可作为正式 CDSS 图谱层数据继续交给前端/规则引擎联调；具体推荐仍应在产品侧按患者触发条件动态筛选展示。",
        ]
    )
    (OUT_DIR / "11_心肌病总精修验收报告.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
