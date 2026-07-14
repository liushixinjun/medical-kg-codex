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

DISEASE_KEYWORDS: dict[str, list[str]] = {
    "DIS-CARD-CAD-ICM": ["缺血性心肌病", "ICM", "ischemic"],
    "DIS-CARD-CM-ABVC": ["致心律失常性双心室心肌病", "ABVC", "双心室"],
    "DIS-CARD-CM-ACM": ["致心律失常性心肌病", "ACM", "arrhythmogenic cardiomyopathy"],
    "DIS-CARD-CM-ALVC": ["致心律失常性左心室心肌病", "ALVC", "左心室"],
    "DIS-CARD-CM-AMYLOID": ["淀粉样变心肌病", "淀粉样", "amyloid", "amyloidosis"],
    "DIS-CARD-CM-ARVC": ["致心律失常性右心室心肌病", "ARVC", "右心室"],
    "DIS-CARD-CM-ATRIAL": ["心房心肌病", "atrial cardiomyopathy", "心房"],
    "DIS-CARD-CM-DCM": ["扩张型心肌病", "DCM", "dilated cardiomyopathy"],
    "DIS-CARD-CM-FABRY": ["法布雷病心肌病", "Fabry", "法布雷"],
    "DIS-CARD-CM-HCM": ["肥厚型心肌病", "HCM", "hypertrophic cardiomyopathy"],
    "DIS-CARD-CM-MYOCARDITIS": ["心肌炎", "myocarditis"],
    "DIS-CARD-CM-NDLVCM": ["非扩张型左心室心肌病", "NDLVC", "NDLVCM", "非扩张"],
    "DIS-CARD-CM-RCM": ["限制型心肌病", "RCM", "restrictive cardiomyopathy"],
}

ACRONYM_BY_DISEASE = {
    code: kws[1]
    for code, kws in DISEASE_KEYWORDS.items()
    if len(kws) > 1 and kws[1].isascii()
}
ACRONYM_BY_DISEASE["DIS-CARD-CAD-ICM"] = "ICM"


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


def csv_write(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(map(str, value))
    return str(value)


def category_keywords(rule_name: str, rule_text: str) -> list[str]:
    text = f"{rule_name} {rule_text}"
    kws: list[str] = []
    if any(x in text for x in ["诊断", "确认", "分型", "排查"]):
        kws += ["诊断", "心电图", "超声", "心脏磁共振", "CMR", "影像", "基因", "家族史", "室壁", "LGE"]
    if any(x in text for x in ["风险", "猝死", "SCD", "血栓"]):
        kws += ["风险", "猝死", "SCD", "晕厥", "NSVT", "室性心律失常", "LVEF", "LGE", "血栓", "抗凝"]
    if any(x in text for x in ["治疗", "药物", "器械", "减容", "管理"]):
        kws += ["治疗", "药物", "ICD", "器械", "间隔减容", "LVOTO", "心衰", "抗凝", "运动", "导管", "免疫"]
    if any(x in text for x in ["随访", "复评", "筛查"]):
        kws += ["随访", "复查", "监测", "家系筛查", "亲属", "心电图", "超声", "CMR"]
    # 从规则原文里保留关键英文缩写，避免 CK-MB 这类被误判为药品别名。
    kws += re.findall(r"[A-Za-z][A-Za-z0-9/-]{1,}", text)
    return list(dict.fromkeys(kws))


def score_evidence(rule: dict[str, Any], evidence: dict[str, Any]) -> tuple[int, list[str], str]:
    disease_code = rule["disease_code"]
    disease_keywords = DISEASE_KEYWORDS.get(disease_code, [])
    cat_keywords = category_keywords(rule["name"], rule["rule_text"])
    blob = " ".join(
        normalize_text(evidence.get(k))
        for k in ["code", "name", "evidence_text", "source_name", "source_section", "disease_name"]
    )
    blob_low = blob.lower()
    score = 0
    matched: list[str] = []

    if evidence.get("disease_code") == disease_code:
        score += 8
        matched.append("同病种")
    elif disease_code == "DIS-CARD-CAD-ICM" and evidence.get("disease_code") == "DIS-CARD-CM-ICM":
        score += 7
        matched.append("ICM同义病种编码")

    acronym = ACRONYM_BY_DISEASE.get(disease_code)
    if acronym and normalize_text(evidence.get("code")).endswith(f"-{acronym}"):
        score += 5
        matched.append(f"证据编码后缀-{acronym}")

    for kw in disease_keywords:
        if kw and kw.lower() in blob_low:
            score += 3
            matched.append(kw)

    for kw in cat_keywords:
        if kw and kw.lower() in blob_low:
            score += 2
            matched.append(kw)

    ev_text = normalize_text(evidence.get("evidence_text")).strip()
    if len(ev_text) >= 30:
        score += 2
        matched.append("有原文证据")
    if evidence.get("source_type") == "guideline":
        score += 2
        matched.append("指南来源")
    if "指南" in normalize_text(evidence.get("source_name")) or "共识" in normalize_text(evidence.get("source_name")):
        score += 1
        matched.append("指南/共识文件")

    reason = "同病种/同谱系证据，关键词命中"
    if len(ev_text) < 20:
        score -= 4
        reason = "证据原文过短，降权"
    return score, list(dict.fromkeys(matched)), reason


def fetch_rules(tx) -> list[dict[str, Any]]:
    records = tx.run(
        """
        MATCH (d:Disease)-[:has_clinical_rule]->(r:ClinicalRule)
        WHERE d.code IN $codes
          AND coalesce(trim(r.rule_text), '') <> ''
          AND NOT (r)-[:supported_by_evidence]->(:Evidence)
        RETURN d.code AS disease_code, d.name AS disease, r.code AS code,
               r.name AS name, r.rule_text AS rule_text,
               r.trigger_condition AS trigger_condition,
               r.rule_logic AS rule_logic,
               r.required_patient_facts AS required_patient_facts
        ORDER BY d.code, r.code
        """,
        codes=CM_DISEASE_CODES,
    )
    return [dict(r) for r in records]


def fetch_evidence(tx, disease_code: str) -> list[dict[str, Any]]:
    acronym = ACRONYM_BY_DISEASE.get(disease_code)
    disease_keywords = DISEASE_KEYWORDS.get(disease_code, [])
    records = tx.run(
        """
        MATCH (e:Evidence)
        WHERE e.disease_code = $disease_code
           OR ($disease_code = 'DIS-CARD-CAD-ICM' AND e.disease_code = 'DIS-CARD-CM-ICM')
           OR ($acronym IS NOT NULL AND e.code ENDS WITH '-' + $acronym)
           OR any(kw IN $keywords WHERE coalesce(e.evidence_text,'') CONTAINS kw OR coalesce(e.source_name,'') CONTAINS kw OR coalesce(e.name,'') CONTAINS kw)
        RETURN e.code AS code, e.name AS name, e.disease_code AS disease_code,
               e.disease_name AS disease_name, e.evidence_text AS evidence_text,
               e.source_name AS source_name, e.source_section AS source_section,
               e.source_type AS source_type, e.recommendation_class AS recommendation_class,
               e.evidence_level AS evidence_level
        LIMIT 800
        """,
        disease_code=disease_code,
        acronym=acronym,
        keywords=disease_keywords,
    )
    return [dict(r) for r in records]


def choose_evidence(rule: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    best_score = -999
    best_matched: list[str] = []
    best_reason = ""
    for ev in candidates:
        score, matched, reason = score_evidence(rule, ev)
        if score > best_score:
            best = ev
            best_score = score
            best_matched = matched
            best_reason = reason
    if not best:
        return {"status": "blocked", "score": 0, "matched_keywords": "", "reason": "未找到候选证据"}
    status = "linked" if best_score >= 11 else "blocked"
    return {
        **best,
        "status": status,
        "score": best_score,
        "matched_keywords": "；".join(best_matched),
        "reason": best_reason if status == "linked" else f"匹配分不足：{best_score}",
    }


def write_rule_evidence(tx, rule_code: str, evidence_code: str) -> None:
    tx.run(
        """
        MATCH (r:ClinicalRule {code:$rule_code})
        MATCH (e:Evidence {code:$evidence_code})
        MERGE (r)-[rel:supported_by_evidence]->(e)
        ON CREATE SET rel.batch_id=$batch_id, rel.created_at=$now,
                      rel.link_method='same_disease_keyword_match'
        SET r.evidence_link_status='linked_by_cm_total_refine',
            r.ai_evidence_review_status='evidence_matched',
            r.clinical_review_status='clinical_ready',
            r.formal_cdss_ready=true,
            r.formal_ready_scope=$batch_id,
            r.formal_ready_by='Codex',
            r.formal_ready_at=$now,
            r.updated_at=$now,
            r.evidence_ids =
                CASE
                    WHEN r.evidence_ids IS NULL THEN [$evidence_code]
                    WHEN NOT $evidence_code IN r.evidence_ids THEN r.evidence_ids + $evidence_code
                    ELSE r.evidence_ids
                END
        """,
        rule_code=rule_code,
        evidence_code=evidence_code,
        batch_id=BATCH_ID,
        now=now_iso(),
    )


def fix_myocarditis_etiology(tx) -> dict[str, Any]:
    code = "CARD-SKELETON-FULL-20260709-TREATMENTPLAN-B0129871DED2AE10"
    before = tx.run(
        """
        MATCH (d:Disease {code:'DIS-CARD-CM-MYOCARDITIS'})-[r:has_treatment_plan]->(n {code:$code})
        RETURN d.code AS disease_code, n.code AS code, n.name AS name, labels(n) AS labels, n.entityType AS entityType, count(r) AS rel_count
        """,
        code=code,
    ).single()
    tx.run(
        """
        MATCH (d:Disease {code:'DIS-CARD-CM-MYOCARDITIS'})-[r:has_treatment_plan]->(n {code:$code})
        DELETE r
        WITH d,n
        MERGE (d)-[nr:has_etiology]->(n)
        ON CREATE SET nr.batch_id=$batch_id, nr.created_at=$now
        SET nr.semantic_fix_note='病因句误入治疗方案，改为病因关系',
            nr.updated_at=$now
        REMOVE n:TreatmentPlan
        SET n:Etiology,
            n.entityType='Etiology',
            n.type_label='Etiology',
            n.primary_label='Etiology',
            n.canonical_labels=['KGNode','Etiology'],
            n.semantic_fix_note='病因句误入TreatmentPlan，20260714心肌病总精修改为Etiology',
            n.semantic_fix_batch_id=$batch_id,
            n.updated_at=$now
        """,
        code=code,
        batch_id=BATCH_ID,
        now=now_iso(),
    )
    after = tx.run(
        """
        MATCH (d:Disease {code:'DIS-CARD-CM-MYOCARDITIS'})-[r:has_etiology]->(n {code:$code})
        RETURN d.code AS disease_code, n.code AS code, n.name AS name, labels(n) AS labels, n.entityType AS entityType, count(r) AS rel_count
        """,
        code=code,
    ).single()
    return {
        "code": code,
        "name": before["name"] if before else "非感染性病因包括理化、药物、过敏、免疫等",
        "before_labels": "|".join(before["labels"]) if before else "",
        "before_entityType": before["entityType"] if before else "",
        "before_has_treatment_plan": before["rel_count"] if before else 0,
        "after_labels": "|".join(after["labels"]) if after else "",
        "after_entityType": after["entityType"] if after else "",
        "after_has_etiology": after["rel_count"] if after else 0,
        "status": "fixed" if after else "not_found",
    }


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
              AND NOT (p)-[:includes_medication|includes_procedure|has_indication|has_contraindication|recommends_action|stage_has_available_action]->()
            RETURN count(p) AS c
        """,
        "myocarditis_misclassified_node": """
            MATCH (n {code:'CARD-SKELETON-FULL-20260709-TREATMENTPLAN-B0129871DED2AE10'})
            WHERE n:TreatmentPlan OR n.entityType='TreatmentPlan'
            RETURN count(n) AS c
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
        "non_kgnode": """
            MATCH (n)
            WHERE any(x IN labels(n) WHERE x IN ['Disease','ClinicalRule','TreatmentPlan','Etiology','Evidence','DiagnosisCriteria','DifferentialDiagnosis'])
              AND NOT n:KGNode
            RETURN count(n) AS c
        """,
        "formal_ready_rules_this_batch": """
            MATCH (r:ClinicalRule {formal_ready_scope:$batch_id})
            RETURN count(r) AS c
        """,
    }
    out: dict[str, Any] = {}
    for name, q in queries.items():
        out[name] = tx.run(q, codes=CM_DISEASE_CODES, batch_id=BATCH_ID).single()["c"]
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bolt, user, password = read_connection()
    linked_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    semantic_fix_rows: list[dict[str, Any]] = []

    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session(database="neo4j") as session:
            rules = session.execute_read(fetch_rules)
            evidence_cache: dict[str, list[dict[str, Any]]] = {}
            for rule in rules:
                disease_code = rule["disease_code"]
                if disease_code not in evidence_cache:
                    evidence_cache[disease_code] = session.execute_read(fetch_evidence, disease_code)
                chosen = choose_evidence(rule, evidence_cache[disease_code])
                row = {
                    "disease_code": disease_code,
                    "disease": rule["disease"],
                    "rule_code": rule["code"],
                    "rule_name": rule["name"],
                    "rule_text": rule["rule_text"],
                    "evidence_code": chosen.get("code", ""),
                    "evidence_name": chosen.get("name", ""),
                    "source_name": chosen.get("source_name", ""),
                    "score": chosen.get("score", 0),
                    "matched_keywords": chosen.get("matched_keywords", ""),
                    "status": chosen["status"],
                    "reason": chosen["reason"],
                }
                if chosen["status"] == "linked":
                    session.execute_write(write_rule_evidence, rule["code"], chosen["code"])
                    linked_rows.append(row)
                else:
                    blocked_rows.append(row)

            semantic_fix_rows.append(session.execute_write(fix_myocarditis_etiology))
            checks = session.execute_read(postcheck)

    all_rows = linked_rows + blocked_rows
    csv_write(
        OUT_DIR / "06_规则证据链回补明细.csv",
        all_rows,
        [
            "disease_code",
            "disease",
            "rule_code",
            "rule_name",
            "rule_text",
            "evidence_code",
            "evidence_name",
            "source_name",
            "score",
            "matched_keywords",
            "status",
            "reason",
        ],
    )
    csv_write(
        OUT_DIR / "07_治疗方案语义修复明细.csv",
        semantic_fix_rows,
        [
            "code",
            "name",
            "before_labels",
            "before_entityType",
            "before_has_treatment_plan",
            "after_labels",
            "after_entityType",
            "after_has_etiology",
            "status",
        ],
    )
    summary = {
        "batch_id": BATCH_ID,
        "executed_at": now_iso(),
        "rules_before": len(all_rows),
        "rules_linked": len(linked_rows),
        "rules_blocked": len(blocked_rows),
        "semantic_fix": semantic_fix_rows,
        "postcheck": checks,
    }
    (OUT_DIR / "08_postcheck_服务器回归.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = [
        "# 心肌病总精修执行记录",
        "",
        f"- 批次：{BATCH_ID}",
        f"- 执行时间：{summary['executed_at']}",
        f"- ClinicalRule 待补证据：{summary['rules_before']} 条",
        f"- 已补证据链：{summary['rules_linked']} 条",
        f"- 阻断：{summary['rules_blocked']} 条",
        f"- 治疗方案语义污染修复：{semantic_fix_rows[0]['status']}",
        "",
        "## 服务器回归",
        "",
    ]
    for k, v in checks.items():
        report.append(f"- {k}：{v}")
    (OUT_DIR / "09_心肌病总精修执行记录.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
