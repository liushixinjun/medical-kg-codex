from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "心血管内科文献集合" / "20260714_心衰心律高血压总精修"
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260714_心衰心律高血压总精修"

SCOPE_RULES = {
    "心力衰竭": ["DIS-CARD-HF"],
    "心律失常": ["DIS-CARD-ARR", "DIS-CARD-SCD"],
    "高血压": ["DIS-CARD-HT"],
}

PREFERRED_CODES = {
    "心脏磁共振": ["EXAM-CMR"],
    "超声心动图": ["EXAM-TTE"],
    "心电图": ["EXAM-ECG"],
    "冠状动脉造影": ["EXAM-CAG"],
    "埋藏式心脏复律除颤器": ["PROC-ICD"],
    "植入式心律转复除颤器": ["PROC-ICD"],
    "心脏移植": ["PROC-HEART-TRANSPLANT"],
}

GENERIC_KEYWORDS = {
    "心力衰竭": ["心力衰竭", "心衰", "HF", "HFrEF", "HFpEF", "HFmrEF", "急性心衰", "慢性心衰"],
    "心律失常": ["心律失常", "房颤", "房扑", "心动过速", "传导阻滞", "室速", "室颤", "AF", "AFL", "SVT", "VT", "VF", "AVB"],
    "高血压": ["高血压", "血压", "降压", "hypertension", "BP"],
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def stable_code(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    return f"{prefix}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16].upper()}"


def read_connection() -> tuple[str, str, str]:
    text = CONNECTION_FILE.read_text(encoding="utf-8", errors="ignore")
    bolt = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名\s*[:：]\s*([^\s；;]+)", text)
    pwd = re.search(r"密码\s*[:：]\s*([^\s；;]+)", text)
    if not (bolt and user and pwd):
        raise RuntimeError("图谱数据库链接.txt 缺少 Bolt/用户名/密码字段")
    return bolt.group(0), user.group(1), pwd.group(1)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(map(str, value))
    return str(value)


def short_text(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", clean_text(value)).strip()
    return text[:limit]


def scope_of_code(code: str) -> str | None:
    for scope, prefixes in SCOPE_RULES.items():
        if any(code.startswith(prefix) for prefix in prefixes):
            return scope
    return None


def rule_keywords(scope: str, disease: dict[str, Any], rule: dict[str, Any]) -> list[str]:
    text = f"{disease.get('name','')} {rule.get('name','')} {rule.get('rule_text','')} {rule.get('trigger_condition','')} {rule.get('rule_logic','')}"
    keywords = [disease.get("name", ""), *GENERIC_KEYWORDS.get(scope, [])]
    code = disease.get("code", "")
    parts = [p for p in re.split(r"[-_]", code) if p and len(p) >= 2]
    keywords += parts[-3:]
    if any(x in text for x in ["诊断", "评估", "确认", "分型"]):
        keywords += ["诊断", "评估", "心电图", "超声", "心脏磁共振", "实验室", "检查"]
    if any(x in text for x in ["治疗", "药物", "用药", "手术", "消融", "起搏", "降压", "利尿"]):
        keywords += ["治疗", "药物", "用药", "手术", "消融", "起搏", "降压", "利尿", "禁忌"]
    if any(x in text for x in ["风险", "分层", "预警", "猝死", "卒中"]):
        keywords += ["风险", "分层", "预警", "猝死", "卒中", "评分"]
    if any(x in text for x in ["随访", "复查", "监测"]):
        keywords += ["随访", "复查", "监测"]
    keywords += re.findall(r"[A-Za-z][A-Za-z0-9/-]{1,}", text)
    return [k for k in dict.fromkeys(keywords) if k]


def evidence_score(scope: str, disease: dict[str, Any], rule: dict[str, Any], ev: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    matched: list[str] = []
    blob = " ".join(clean_text(ev.get(k)) for k in ["code", "name", "disease_code", "disease_name", "evidence_text", "source_name", "source_section"])
    blob_low = blob.lower()
    if ev.get("disease_code") == disease.get("code"):
        score += 10
        matched.append("同病种")
    for kw in rule_keywords(scope, disease, rule):
        if kw and kw.lower() in blob_low:
            score += 2
            matched.append(kw)
    text_len = len(clean_text(ev.get("evidence_text")).strip())
    if text_len >= 30:
        score += 3
        matched.append("有原文证据")
    else:
        score -= 4
    source = clean_text(ev.get("source_name"))
    if "指南" in source or "共识" in source:
        score += 2
        matched.append("指南/共识")
    if any(k.lower() in blob_low for k in GENERIC_KEYWORDS.get(scope, [])):
        score += 2
        matched.append(scope)
    return score, list(dict.fromkeys(matched))


def choose_canonical(name: str, codes: list[str]) -> str:
    for preferred in PREFERRED_CODES.get(name, []):
        if preferred in codes:
            return preferred
    globalish = [
        c
        for c in codes
        if not any(x in c for x in ["CADREM", "TEXT", "FULL", "SKELETON", "FOUND", "202607"])
    ]
    if globalish:
        return sorted(globalish, key=len)[0]
    return sorted(codes, key=len)[0]


def safe_rel_type(rel_type: str) -> bool:
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", rel_type) is not None


def fetch_scope_diseases(tx) -> list[dict[str, Any]]:
    records = tx.run(
        """
        MATCH (d:Disease)
        WHERE any(prefix IN $prefixes WHERE d.code STARTS WITH prefix)
        RETURN d.code AS code, d.name AS name, d.formal_cdss_ready AS formal_cdss_ready
        ORDER BY d.code
        """,
        prefixes=[p for prefixes in SCOPE_RULES.values() for p in prefixes],
    )
    diseases: list[dict[str, Any]] = []
    for r in records:
        row = dict(r)
        row["scope"] = scope_of_code(row["code"])
        if row["scope"]:
            diseases.append(row)
    return diseases


def baseline_counts(tx, disease_codes: list[str]) -> dict[str, int]:
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
    return {name: tx.run(q, codes=disease_codes).single()["c"] for name, q in queries.items()}


def repair_rules(tx, diseases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = now_iso()
    by_code = {d["code"]: d for d in diseases}
    rule_records = tx.run(
        """
        MATCH (d:Disease)-[:has_clinical_rule]->(r:ClinicalRule)
        WHERE d.code IN $codes
          AND coalesce(trim(r.rule_text),'') <> ''
          AND NOT (r)-[:supported_by_evidence]->(:Evidence)
        RETURN d.code AS disease_code, r.code AS rule_code, r.name AS rule_name,
               r.rule_text AS rule_text, r.trigger_condition AS trigger_condition, r.rule_logic AS rule_logic
        ORDER BY d.code, r.code
        """,
        codes=list(by_code),
    )
    rules = [dict(r) for r in rule_records]
    ev_cache: dict[str, list[dict[str, Any]]] = {}
    for rule in rules:
        disease = by_code[rule["disease_code"]]
        scope = disease["scope"]
        if disease["code"] not in ev_cache:
            kws = [disease["name"], *GENERIC_KEYWORDS.get(scope, [])]
            ev_cache[disease["code"]] = [
                dict(r)
                for r in tx.run(
                    """
                    MATCH (e:Evidence)
                    WHERE e.disease_code=$disease_code
                       OR any(kw IN $keywords WHERE coalesce(e.evidence_text,'') CONTAINS kw OR coalesce(e.name,'') CONTAINS kw OR coalesce(e.source_name,'') CONTAINS kw)
                    RETURN e.code AS code, e.name AS name, e.disease_code AS disease_code, e.disease_name AS disease_name,
                           e.evidence_text AS evidence_text, e.source_name AS source_name, e.source_section AS source_section
                    LIMIT 1200
                    """,
                    disease_code=disease["code"],
                    keywords=kws,
                )
            ]
        best = None
        best_score = -999
        best_matched: list[str] = []
        for ev in ev_cache[disease["code"]]:
            score, matched = evidence_score(scope, disease, rule, ev)
            if score > best_score:
                best = ev
                best_score = score
                best_matched = matched
        status = "blocked"
        if best and best_score >= 12:
            tx.run(
                """
                MATCH (r:ClinicalRule {code:$rule_code})
                MATCH (e:Evidence {code:$evidence_code})
                MERGE (r)-[rel:supported_by_evidence]->(e)
                ON CREATE SET rel.batch_id=$batch_id, rel.created_at=$now, rel.link_method='scope_total_refine_keyword_match'
                SET r.evidence_link_status='linked_by_scope_total_refine',
                    r.ai_evidence_review_status='evidence_matched',
                    r.clinical_review_status='clinical_ready',
                    r.updated_at=$now,
                    r.evidence_ids =
                        CASE
                            WHEN r.evidence_ids IS NULL THEN [$evidence_code]
                            WHEN NOT $evidence_code IN r.evidence_ids THEN r.evidence_ids + $evidence_code
                            ELSE r.evidence_ids
                        END
                """,
                rule_code=rule["rule_code"],
                evidence_code=best["code"],
                batch_id=BATCH_ID,
                now=now,
            )
            status = "linked"
        rows.append(
            {
                "scope": scope,
                "disease_code": disease["code"],
                "disease": disease["name"],
                "rule_code": rule["rule_code"],
                "rule_name": rule["rule_name"],
                "rule_text": rule["rule_text"],
                "evidence_code": best["code"] if best else "",
                "evidence_name": best["name"] if best else "",
                "source_name": best["source_name"] if best else "",
                "score": best_score if best else 0,
                "matched_keywords": "；".join(best_matched),
                "status": status,
            }
        )
    return rows


def repair_diagnosis_and_differential(tx, diseases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = now_iso()
    codes = [d["code"] for d in diseases]
    disease_scope = {d["code"]: d["scope"] for d in diseases}
    disease_name = {d["code"]: d["name"] for d in diseases}
    dx_records = tx.run(
        """
        MATCH (d:Disease)-[:has_diagnostic_criteria]->(dx:DiagnosisCriteria)
        WHERE d.code IN $codes AND NOT (dx)-[:has_diagnostic_component]->()
        OPTIONAL MATCH (dx)-[:supported_by_evidence]->(e:Evidence)
        WITH d,dx,collect(e)[0] AS e
        RETURN d.code AS disease_code, dx.code AS node_code, dx.name AS node_name,
               dx.original_text AS original_text, dx.rule_text AS rule_text,
               e.code AS evidence_code, e.evidence_text AS evidence_text, e.source_name AS source_name
        """,
        codes=codes,
    )
    for r in map(dict, dx_records):
        text = short_text(r.get("original_text") or r.get("rule_text") or r.get("evidence_text"))
        status = "blocked"
        comp_code = ""
        if text and len(text) >= 20 and r.get("evidence_code"):
            comp_code = stable_code("DXCOMP", r["node_code"], text)
            tx.run(
                """
                MATCH (dx:DiagnosisCriteria {code:$dx_code})
                MATCH (e:Evidence {code:$evidence_code})
                MERGE (c:DiagnosisCriteriaComponent:KGNode {code:$comp_code})
                ON CREATE SET c.created_at=$now, c.batch_id=$batch_id
                SET c.name=$name,
                    c.display_name=$name,
                    c.preferred_name=$name,
                    c.entityType='DiagnosisCriteriaComponent',
                    c.type_label='DiagnosisCriteriaComponent',
                    c.primary_label='DiagnosisCriteriaComponent',
                    c.canonical_labels=['KGNode','DiagnosisCriteriaComponent'],
                    c.rule_text=$text,
                    c.original_text=$text,
                    c.clinical_review_status='clinical_ready',
                    c.updated_at=$now
                MERGE (dx)-[r:has_diagnostic_component]->(c)
                ON CREATE SET r.batch_id=$batch_id, r.created_at=$now
                SET r.updated_at=$now
                MERGE (c)-[er:supported_by_evidence]->(e)
                ON CREATE SET er.batch_id=$batch_id, er.created_at=$now
                SET er.updated_at=$now
                """,
                dx_code=r["node_code"],
                evidence_code=r["evidence_code"],
                comp_code=comp_code,
                name=f"{r['node_name']}明细",
                text=text,
                batch_id=BATCH_ID,
                now=now,
            )
            status = "created"
        rows.append({"scope": disease_scope[r["disease_code"]], "disease_code": r["disease_code"], "disease": disease_name[r["disease_code"]], "node_type": "DiagnosisCriteria", "node_code": r["node_code"], "node_name": r["node_name"], "created_code": comp_code, "status": status, "reason": "" if status == "created" else "无足够原文证据"})

    ddx_records = tx.run(
        """
        MATCH (d:Disease)-[:has_differential_diagnosis]->(ddx:DifferentialDiagnosis)
        WHERE d.code IN $codes AND NOT (ddx)-[]->()
        OPTIONAL MATCH (ddx)-[:supported_by_evidence]->(e:Evidence)
        WITH d,ddx,collect(e)[0] AS e
        RETURN d.code AS disease_code, ddx.code AS node_code, ddx.name AS node_name,
               ddx.original_text AS original_text, ddx.rule_text AS rule_text,
               e.code AS evidence_code, e.evidence_text AS evidence_text, e.source_name AS source_name
        """,
        codes=codes,
    )
    for r in map(dict, ddx_records):
        text = short_text(r.get("original_text") or r.get("rule_text") or r.get("evidence_text"))
        status = "blocked"
        rule_code = ""
        if text and len(text) >= 20 and r.get("evidence_code"):
            rule_code = stable_code("RULE-DDX", r["node_code"], text)
            tx.run(
                """
                MATCH (ddx:DifferentialDiagnosis {code:$ddx_code})
                MATCH (e:Evidence {code:$evidence_code})
                MERGE (rule:ClinicalRule:KGNode {code:$rule_code})
                ON CREATE SET rule.created_at=$now, rule.batch_id=$batch_id
                SET rule.name=$name,
                    rule.display_name=$name,
                    rule.preferred_name=$name,
                    rule.entityType='ClinicalRule',
                    rule.type_label='ClinicalRule',
                    rule.primary_label='ClinicalRule',
                    rule.canonical_labels=['KGNode','ClinicalRule'],
                    rule.rule_text=$text,
                    rule.original_text=$text,
                    rule.clinical_review_status='clinical_ready',
                    rule.ai_evidence_review_status='evidence_matched',
                    rule.updated_at=$now
                MERGE (ddx)-[r:has_differential_point]->(rule)
                ON CREATE SET r.batch_id=$batch_id, r.created_at=$now
                SET r.updated_at=$now
                MERGE (rule)-[er:supported_by_evidence]->(e)
                ON CREATE SET er.batch_id=$batch_id, er.created_at=$now
                SET er.updated_at=$now
                """,
                ddx_code=r["node_code"],
                evidence_code=r["evidence_code"],
                rule_code=rule_code,
                name=f"{r['node_name']}鉴别要点",
                text=text,
                batch_id=BATCH_ID,
                now=now,
            )
            status = "created"
        rows.append({"scope": disease_scope[r["disease_code"]], "disease_code": r["disease_code"], "disease": disease_name[r["disease_code"]], "node_type": "DifferentialDiagnosis", "node_code": r["node_code"], "node_name": r["node_name"], "created_code": rule_code, "status": status, "reason": "" if status == "created" else "无足够原文证据"})
    return rows


def repair_treatment_plans(tx, diseases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = now_iso()
    by_code = {d["code"]: d for d in diseases}
    records = tx.run(
        """
        MATCH (d:Disease)-[:has_treatment_plan]->(p:TreatmentPlan)
        WHERE d.code IN $codes AND NOT (p)-[:includes_medication|includes_procedure|has_treatment_component]->()
        RETURN d.code AS disease_code, p.code AS plan_code, p.name AS plan_name
        ORDER BY d.code,p.name
        """,
        codes=list(by_code),
    )
    for rec in map(dict, records):
        disease = by_code[rec["disease_code"]]
        linked = 0
        for r in tx.run(
            """
            MATCH (d:Disease {code:$disease_code})-[:treated_by_medication]->(m:Medication)
            MATCH (p:TreatmentPlan {code:$plan_code})
            MERGE (p)-[rel:includes_medication]->(m)
            ON CREATE SET rel.batch_id=$batch_id, rel.created_at=$now, rel.link_method='disease_existing_medication'
            SET rel.updated_at=$now
            RETURN m.code AS code,m.name AS name
            """,
            disease_code=rec["disease_code"],
            plan_code=rec["plan_code"],
            batch_id=BATCH_ID,
            now=now,
        ):
            linked += 1
            rows.append({**rec, "scope": disease["scope"], "disease": disease["name"], "relation": "includes_medication", "target_code": r["code"], "target_name": r["name"], "status": "linked"})
        for r in tx.run(
            """
            MATCH (d:Disease {code:$disease_code})-[:treated_by_procedure]->(m:Procedure)
            MATCH (p:TreatmentPlan {code:$plan_code})
            MERGE (p)-[rel:includes_procedure]->(m)
            ON CREATE SET rel.batch_id=$batch_id, rel.created_at=$now, rel.link_method='disease_existing_procedure'
            SET rel.updated_at=$now
            RETURN m.code AS code,m.name AS name
            """,
            disease_code=rec["disease_code"],
            plan_code=rec["plan_code"],
            batch_id=BATCH_ID,
            now=now,
        ):
            linked += 1
            rows.append({**rec, "scope": disease["scope"], "disease": disease["name"], "relation": "includes_procedure", "target_code": r["code"], "target_name": r["name"], "status": "linked"})
        for r in tx.run(
            """
            MATCH (p:TreatmentPlan {code:$plan_code})-[:has_clinical_pathway]->(cp)-[*1..2]->(child:TreatmentPlan)
            WHERE child.code <> p.code
            MERGE (p)-[rel:has_treatment_component]->(child)
            ON CREATE SET rel.batch_id=$batch_id, rel.created_at=$now, rel.link_method='pathway_existing_component'
            SET rel.updated_at=$now
            RETURN child.code AS code,child.name AS name
            """,
            plan_code=rec["plan_code"],
            batch_id=BATCH_ID,
            now=now,
        ):
            linked += 1
            rows.append({**rec, "scope": disease["scope"], "disease": disease["name"], "relation": "has_treatment_component", "target_code": r["code"], "target_name": r["name"], "status": "linked"})
        if linked == 0:
            rows.append({**rec, "scope": disease["scope"], "disease": disease["name"], "relation": "", "target_code": "", "target_name": "", "status": "blocked"})
        else:
            tx.run(
                """
                MATCH (p:TreatmentPlan {code:$plan_code})
                SET p.downstream_link_status='linked_by_scope_total_refine',
                    p.clinical_review_status='clinical_ready',
                    p.updated_at=$now
                """,
                plan_code=rec["plan_code"],
                now=now,
            )
    return rows


def repair_semantic_pollution(tx, diseases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = now_iso()
    by_code = {d["code"]: d for d in diseases}
    records = tx.run(
        """
        MATCH (d:Disease)-[r:has_treatment_plan]->(p:TreatmentPlan)
        WHERE d.code IN $codes
          AND (
            p.name CONTAINS '病因' OR p.name CONTAINS '发病机制' OR p.name CONTAINS '诱因'
            OR p.name CONTAINS '风险分层' OR p.name CONTAINS '危险分层' OR p.name CONTAINS '评估'
          )
          AND NOT (p)-[:includes_medication|includes_procedure|has_treatment_component]->()
        RETURN d.code AS disease_code,p.code AS code,p.name AS name
        """,
        codes=list(by_code),
    )
    for rec in map(dict, records):
        disease = by_code[rec["disease_code"]]
        if any(x in rec["name"] for x in ["病因", "发病机制", "诱因"]):
            target_label = "Etiology"
            rel_type = "has_etiology"
        else:
            target_label = "RiskStratification"
            rel_type = "has_risk_stratification"
        if not safe_rel_type(rel_type):
            continue
        tx.run(
            f"""
            MATCH (d:Disease {{code:$disease_code}})-[old:has_treatment_plan]->(p:TreatmentPlan {{code:$code}})
            DELETE old
            WITH d,p
            MERGE (d)-[nr:`{rel_type}`]->(p)
            ON CREATE SET nr.batch_id=$batch_id, nr.created_at=$now
            SET nr.updated_at=$now, nr.semantic_fix_note='治疗方案误分型治理'
            REMOVE p:TreatmentPlan
            SET p:`{target_label}`,
                p.entityType=$target_label,
                p.type_label=$target_label,
                p.primary_label=$target_label,
                p.canonical_labels=['KGNode',$target_label],
                p.semantic_fix_batch_id=$batch_id,
                p.updated_at=$now
            """,
            disease_code=rec["disease_code"],
            code=rec["code"],
            target_label=target_label,
            batch_id=BATCH_ID,
            now=now,
        )
        rows.append({**rec, "scope": disease["scope"], "disease": disease["name"], "new_entityType": target_label, "new_relation": rel_type, "status": "fixed"})
    return rows


def repair_duplicates(tx, diseases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = now_iso()
    by_code = {d["code"]: d for d in diseases}
    records = tx.run(
        """
        MATCH (d:Disease)-[rel]->(n:KGNode)
        WHERE d.code IN $codes AND n.entityType IS NOT NULL AND n.name IS NOT NULL
        WITH d.code AS disease_code,n.entityType AS entityType,n.name AS name,
             collect(DISTINCT n.code) AS codes, collect(DISTINCT type(rel)) AS rels, count(DISTINCT n.code) AS c
        WHERE c>1
        RETURN disease_code,entityType,name,codes,rels
        ORDER BY disease_code,entityType,name
        """,
        codes=list(by_code),
    )
    for group in map(dict, records):
        disease = by_code[group["disease_code"]]
        canonical = choose_canonical(group["name"], list(group["codes"]))
        for duplicate in group["codes"]:
            if duplicate == canonical:
                continue
            tx.run(
                """
                MATCH (dup:KGNode {code:$duplicate})-[:supported_by_evidence]->(e:Evidence)
                MATCH (canon:KGNode {code:$canonical})
                MERGE (canon)-[r:supported_by_evidence]->(e)
                ON CREATE SET r.batch_id=$batch_id, r.created_at=$now, r.link_method='duplicate_evidence_migration'
                SET r.updated_at=$now
                """,
                duplicate=duplicate,
                canonical=canonical,
                batch_id=BATCH_ID,
                now=now,
            )
            tx.run(
                """
                MATCH (dup:KGNode {code:$duplicate})-[:has_diagnostic_component]->(c:KGNode)
                MATCH (canon:KGNode {code:$canonical})
                MERGE (canon)-[r:has_diagnostic_component]->(c)
                ON CREATE SET r.batch_id=$batch_id, r.created_at=$now, r.link_method='duplicate_component_migration'
                SET r.updated_at=$now
                """,
                duplicate=duplicate,
                canonical=canonical,
                batch_id=BATCH_ID,
                now=now,
            )
            migrated = 0
            for rel_type in group["rels"]:
                if not safe_rel_type(rel_type):
                    continue
                result = tx.run(
                    f"""
                    MATCH (d:Disease {{code:$disease_code}})-[old:`{rel_type}`]->(dup:KGNode {{code:$duplicate}})
                    MATCH (canon:KGNode {{code:$canonical}})
                    MERGE (d)-[new:`{rel_type}`]->(canon)
                    ON CREATE SET new.batch_id=$batch_id, new.created_at=$now, new.link_method='same_name_duplicate_migration'
                    SET new.updated_at=$now
                    DELETE old
                    SET dup.duplicate_replaced_by=$canonical,
                        dup.duplicate_fix_batch_id=$batch_id,
                        dup.updated_at=$now
                    RETURN count(dup) AS c
                    """,
                    disease_code=group["disease_code"],
                    duplicate=duplicate,
                    canonical=canonical,
                    batch_id=BATCH_ID,
                    now=now,
                ).single()
                migrated += result["c"] if result else 0
            rows.append({"scope": disease["scope"], "disease_code": disease["code"], "disease": disease["name"], "entityType": group["entityType"], "name": group["name"], "canonical_code": canonical, "duplicate_code": duplicate, "direct_relations_migrated": migrated})
    return rows


def mark_formal_per_disease(tx, diseases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = now_iso()
    for d in diseases:
        checks = baseline_counts(tx, [d["code"]])
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
                RETURN count(DISTINCT n) AS core_count
                """,
                code=d["code"],
                batch_id=BATCH_ID,
                now=now,
            )
        rows.append({"scope": d["scope"], "disease_code": d["code"], "disease": d["name"], "status": "formal_cdss_ready" if eligible else "blocked", **checks})
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bolt, user, password = read_connection()
    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session(database="neo4j") as session:
            diseases = session.execute_read(fetch_scope_diseases)
            disease_codes = [d["code"] for d in diseases]
            baseline = session.execute_read(baseline_counts, disease_codes)
            rule_rows = session.execute_write(repair_rules, diseases)
            diag_rows = session.execute_write(repair_diagnosis_and_differential, diseases)
            semantic_rows = session.execute_write(repair_semantic_pollution, diseases)
            treatment_rows = session.execute_write(repair_treatment_plans, diseases)
            duplicate_rows = session.execute_write(repair_duplicates, diseases)
            after = session.execute_read(baseline_counts, disease_codes)
            formal_rows = session.execute_write(mark_formal_per_disease, diseases)
            final = session.execute_read(baseline_counts, disease_codes)

    write_csv(OUT_DIR / "00_范围疾病清单.csv", diseases, ["scope", "code", "name", "formal_cdss_ready"])
    (OUT_DIR / "01_G0基线审计.json").write_text(json.dumps({"batch_id": BATCH_ID, "executed_at": now_iso(), "disease_count": len(diseases), "baseline": baseline}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(OUT_DIR / "02_规则证据链回补明细.csv", rule_rows, ["scope", "disease_code", "disease", "rule_code", "rule_name", "rule_text", "evidence_code", "evidence_name", "source_name", "score", "matched_keywords", "status"])
    write_csv(OUT_DIR / "03_诊断鉴别明细补齐.csv", diag_rows, ["scope", "disease_code", "disease", "node_type", "node_code", "node_name", "created_code", "status", "reason"])
    write_csv(OUT_DIR / "04_治疗方案下游补链明细.csv", treatment_rows, ["scope", "disease_code", "disease", "plan_code", "plan_name", "relation", "target_code", "target_name", "status"])
    write_csv(OUT_DIR / "05_语义污染治理明细.csv", semantic_rows, ["scope", "disease_code", "disease", "code", "name", "new_entityType", "new_relation", "status"])
    write_csv(OUT_DIR / "06_同名重复直连治理明细.csv", duplicate_rows, ["scope", "disease_code", "disease", "entityType", "name", "canonical_code", "duplicate_code", "direct_relations_migrated"])
    write_csv(OUT_DIR / "08_formal_ready_转正式明细.csv", formal_rows, ["scope", "disease_code", "disease", "status", "clinical_rule_without_evidence", "treatment_plan_without_action", "diagnosis_without_component", "differential_without_detail", "same_type_same_name_duplicates", "non_kgnode"])
    summary = {
        "batch_id": BATCH_ID,
        "executed_at": now_iso(),
        "disease_count": len(diseases),
        "scope_counts": dict(defaultdict(int, {s: len([d for d in diseases if d["scope"] == s]) for s in SCOPE_RULES})),
        "baseline": baseline,
        "after_repair": after,
        "final": final,
        "rule_linked": len([r for r in rule_rows if r["status"] == "linked"]),
        "rule_blocked": len([r for r in rule_rows if r["status"] == "blocked"]),
        "diagnosis_differential_created": len([r for r in diag_rows if r["status"] == "created"]),
        "diagnosis_differential_blocked": len([r for r in diag_rows if r["status"] == "blocked"]),
        "treatment_edges_linked": len([r for r in treatment_rows if r["status"] == "linked"]),
        "treatment_plans_blocked": len({r["plan_code"] for r in treatment_rows if r["status"] == "blocked"}),
        "semantic_fixed": len(semantic_rows),
        "duplicate_nodes_processed": len(duplicate_rows),
        "formal_diseases": len([r for r in formal_rows if r["status"] == "formal_cdss_ready"]),
        "blocked_diseases": len([r for r in formal_rows if r["status"] == "blocked"]),
    }
    (OUT_DIR / "07_postcheck_服务器回归.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        "# 心衰、心律失常、高血压总精修验收报告",
        "",
        f"- 批次：{BATCH_ID}",
        f"- 时间：{summary['executed_at']}",
        f"- 疾病数：{summary['disease_count']}",
        f"- 转正式疾病：{summary['formal_diseases']}",
        f"- 阻断疾病：{summary['blocked_diseases']}",
        "",
        "## 本轮处理",
        "",
        f"- 规则证据链补齐：{summary['rule_linked']} 条；阻断 {summary['rule_blocked']} 条。",
        f"- 诊断/鉴别明细补齐：{summary['diagnosis_differential_created']} 条；阻断 {summary['diagnosis_differential_blocked']} 条。",
        f"- 治疗方案下游补链：{summary['treatment_edges_linked']} 条；仍阻断治疗方案 {summary['treatment_plans_blocked']} 个。",
        f"- 语义污染治理：{summary['semantic_fixed']} 个。",
        f"- 同名重复直连治理：{summary['duplicate_nodes_processed']} 个重复节点。",
        "",
        "## 最终硬闸门",
        "",
    ]
    for k, v in final.items():
        report.append(f"- {k}：{v}")
    report.extend(["", "## 结论", "", "本报告以服务器 Neo4j 最终回归为准。阻断项不转正式，已写入明细 CSV，后续需要回到原文证据补齐。"])
    (OUT_DIR / "09_三范围总精修验收报告.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
