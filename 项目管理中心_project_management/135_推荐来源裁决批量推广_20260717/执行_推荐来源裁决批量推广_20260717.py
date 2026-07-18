from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "项目管理中心_project_management" / "135_推荐来源裁决批量推广_20260717"
OUT.mkdir(parents=True, exist_ok=True)

BATCH_ID = "推荐来源裁决批量推广_20260717"
SCHEMA_VERSION = "V1.17"
RUN_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

TARGET_CATEGORIES = [
    "冠心病",
    "心肌病",
    "心力衰竭",
    "心律失常",
    "高血压",
    "瓣膜病",
    "肺动脉高压",
    "起搏治疗相关疾病",
]


def read_db_config() -> Dict[str, str]:
    text = (ROOT / "图谱数据库链接.txt").read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;]+)", text)
    if not (uri and user and password):
        raise RuntimeError("图谱数据库链接.txt 无法解析 Bolt、用户名或密码")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def flat(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return " ".join(flat(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def as_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    if str(v).strip():
        return [str(v)]
    return []


def first_nonempty(*values: Any) -> str:
    for v in values:
        if isinstance(v, list):
            if v:
                return str(v[0])
        elif v is not None and str(v).strip():
            return str(v)
    return ""


def category_from_code_or_text(code: str, text: str = "", action_name: str = "") -> str:
    code = code or ""
    text = text or ""
    action_name = action_name or ""
    if code.startswith("DIS-CARD-CAD"):
        return "冠心病"
    if code.startswith("DIS-CARD-CM"):
        return "心肌病"
    if code.startswith("DIS-CARD-HF"):
        return "心力衰竭"
    if code.startswith("DIS-CARD-ARR"):
        return "心律失常"
    if code.startswith("DIS-CARD-HT") or code.startswith("DIS-CARD-HTN"):
        return "高血压"
    if code.startswith("DIS-CARD-VHD") or code.startswith("DIS-CARD-VALVE"):
        return "瓣膜病"
    if code.startswith("DIS-CARD-PH"):
        return "肺动脉高压"
    if "起搏" in text or "起搏" in action_name:
        return "起搏治疗相关疾病"
    return "其他"


def sha_code(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha1(value.encode('utf-8')).hexdigest()[:16].upper()}"


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def rel_query(rel_type: str) -> str:
    allowed = {
        "has_source_adjudication",
        "uses_primary_guideline",
        "decides_recommendation",
        "derived_from",
        "recommends_action",
        "blocks_action",
        "based_on_guideline",
    }
    if rel_type not in allowed:
        raise ValueError(f"不允许的关系类型: {rel_type}")
    return (
        f"MATCH (s) WHERE elementId(s)=$sid "
        f"MATCH (t) WHERE elementId(t)=$tid "
        f"MERGE (s)-[r:`{rel_type}`]->(t) "
        f"SET r += $props "
        f"RETURN elementId(r) AS rid"
    )


def resolve_by_code(tx, code: str, entity_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not code:
        return None
    row = tx.run(
        """
        MATCH (n:KGNode)
        WHERE n.code = $code
          AND ($entity_type IS NULL OR n.entityType=$entity_type)
        RETURN elementId(n) AS id, n.code AS code, n.name AS name, n.entityType AS entityType
        LIMIT 1
        """,
        code=code,
        entity_type=entity_type,
    ).single()
    return dict(row) if row else None


def resolve_guideline_by_name(tx, name: str) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    row = tx.run(
        """
        MATCH (g:KGNode {entityType:'Guideline'})
        WHERE g.name = $name OR g.display_name = $name OR g.name CONTAINS $name OR $name CONTAINS g.name
        RETURN elementId(g) AS id, g.code AS code, g.name AS name, g.entityType AS entityType
        ORDER BY size(g.name) DESC
        LIMIT 1
        """,
        name=name,
    ).single()
    return dict(row) if row else None


def merge_source_adjudication(tx, props: Dict[str, Any]) -> str:
    return tx.run(
        """
        MERGE (n:KGNode:SourceAdjudication {code:$code})
        SET n += $props
        RETURN elementId(n) AS id
        """,
        code=props["code"],
        props=props,
    ).single()["id"]


def update_rec_formal_fields(tx, rec_id: str, props: Dict[str, Any]) -> None:
    tx.run(
        """
        MATCH (rs) WHERE elementId(rs)=$rec_id
        SET rs += $props
        """,
        rec_id=rec_id,
        props=props,
    )


def merge_relation(tx, sid: str, rel_type: str, tid: str, props: Dict[str, Any]) -> str:
    return tx.run(rel_query(rel_type), sid=sid, tid=tid, props=props).single()["rid"]


def fetch_recommendations(tx) -> List[Dict[str, Any]]:
    rows = tx.run(
        """
        MATCH (rs:KGNode {entityType:'RecommendationStatement'})
        OPTIONAL MATCH (existing:KGNode {entityType:'SourceAdjudication'})-[:decides_recommendation]->(rs)
        OPTIONAL MATCH (rs)-[act_rel:recommends_action|blocks_action]->(act:KGNode)
        OPTIONAL MATCH (rs)-[:derived_from|supported_by_evidence]->(ev:KGNode {entityType:'Evidence'})
        OPTIONAL MATCH (rs)-[:based_on_guideline]->(gl:KGNode {entityType:'Guideline'})
        RETURN
          elementId(rs) AS rec_id,
          rs.code AS rec_code,
          rs.name AS rec_name,
          rs.display_name AS rec_display_name,
          rs.statement_text AS statement_text,
          rs.statement_summary AS statement_summary,
          rs.disease_code AS disease_code,
          rs.scope_disease_code AS scope_disease_code,
          rs.disease_name AS disease_name,
          rs.scope_target AS scope_target,
          rs.formal_cdss_ready AS formal_cdss_ready,
          rs.cdss_use_status AS cdss_use_status,
          rs.recommendation_class AS recommendation_class,
          rs.evidence_level AS evidence_level,
          rs.primary_evidence_code AS primary_evidence_code,
          rs.primary_guideline_code AS primary_guideline_code,
          rs.primary_guideline_name AS primary_guideline_name,
          rs.action_code AS action_code,
          rs.action_name AS action_name,
          rs.action_entity_type AS action_entity_type,
          rs.recommended_action_codes AS recommended_action_codes,
          rs.recommended_action_names AS recommended_action_names,
          rs.conflict_status AS conflict_status,
          rs.clinical_review_status AS clinical_review_status,
          rs.review_status AS review_status,
          rs.applicable_population AS applicable_population,
          rs.indication_conditions AS indication_conditions,
          rs.exclusion_criteria AS exclusion_criteria,
          collect(DISTINCT existing.code) AS existing_source_adjudications,
          collect(DISTINCT {id:elementId(act), code:act.code, name:act.name, entityType:act.entityType, rel:type(act_rel)}) AS actions,
          collect(DISTINCT {id:elementId(ev), code:ev.code, name:ev.name, source_name:ev.source_name, page:ev.source_page}) AS evidences,
          collect(DISTINCT {id:elementId(gl), code:gl.code, name:gl.name}) AS guidelines
        """
    ).data()
    return rows


def normalize_candidate(tx, row: Dict[str, Any]) -> Dict[str, Any]:
    disease_code = first_nonempty(row.get("disease_code"), row.get("scope_disease_code"))
    disease_name = first_nonempty(row.get("disease_name"), row.get("scope_target"))
    text = " ".join(
        [
            flat(row.get("rec_name")),
            flat(row.get("statement_text")),
            flat(row.get("statement_summary")),
            disease_name,
        ]
    )
    actions = [a for a in row.get("actions", []) if a.get("code")]
    evidences = [e for e in row.get("evidences", []) if e.get("code")]
    guidelines = [g for g in row.get("guidelines", []) if g.get("code")]

    action_code = first_nonempty(row.get("action_code"), as_list(row.get("recommended_action_codes")))
    action_name = first_nonempty(row.get("action_name"), as_list(row.get("recommended_action_names")))
    action_entity_type = first_nonempty(row.get("action_entity_type"))
    action_rel = "recommends_action"

    if not action_code and actions:
        action_code = actions[0]["code"]
        action_name = actions[0].get("name") or ""
        action_entity_type = actions[0].get("entityType") or ""
        action_rel = actions[0].get("rel") or "recommends_action"
    elif actions:
        found = next((a for a in actions if a.get("code") == action_code), actions[0])
        action_name = action_name or found.get("name") or ""
        action_entity_type = action_entity_type or found.get("entityType") or ""
        action_rel = found.get("rel") or "recommends_action"

    if "禁忌" in text or "阻断" in text or "不推荐" in text:
        action_rel = "blocks_action" if action_rel != "recommends_action" else action_rel

    primary_evidence_code = first_nonempty(row.get("primary_evidence_code"))
    evidence = None
    if primary_evidence_code:
        evidence = resolve_by_code(tx, primary_evidence_code, "Evidence")
    if not evidence and evidences:
        primary_evidence_code = evidences[0]["code"]
        evidence = {"id": evidences[0]["id"], "code": evidences[0]["code"], "name": evidences[0].get("name"), "entityType": "Evidence"}

    primary_guideline_code = first_nonempty(row.get("primary_guideline_code"))
    primary_guideline_name = first_nonempty(row.get("primary_guideline_name"))
    guideline = None
    if primary_guideline_code:
        guideline = resolve_by_code(tx, primary_guideline_code, "Guideline")
    if not guideline and guidelines:
        primary_guideline_code = guidelines[0]["code"]
        primary_guideline_name = guidelines[0].get("name") or primary_guideline_name
        guideline = {"id": guidelines[0]["id"], "code": guidelines[0]["code"], "name": guidelines[0].get("name"), "entityType": "Guideline"}
    if not guideline and primary_guideline_name:
        guideline = resolve_guideline_by_name(tx, primary_guideline_name)
        if guideline:
            primary_guideline_code = guideline["code"]
            primary_guideline_name = guideline["name"]
    if not guideline and evidences:
        source_name = first_nonempty(evidences[0].get("source_name"))
        guideline = resolve_guideline_by_name(tx, source_name)
        if guideline:
            primary_guideline_code = guideline["code"]
            primary_guideline_name = guideline["name"]

    disease = resolve_by_code(tx, disease_code, "Disease")
    action = resolve_by_code(tx, action_code, action_entity_type or None)
    if not action:
        action = resolve_by_code(tx, action_code, None)

    category = category_from_code_or_text(disease_code, text, action_name)

    missing = []
    if category not in TARGET_CATEGORIES or category == "其他":
        missing.append("不在本次目标大类")
    if row.get("existing_source_adjudications"):
        missing.append("已有推荐来源裁决")
    if row.get("formal_cdss_ready") is not True:
        missing.append("formal_cdss_ready不是true")
    if not disease:
        missing.append("缺疾病节点")
    if not action:
        missing.append("缺动作节点")
    if not evidence:
        missing.append("缺主证据节点")
    if not guideline:
        missing.append("缺主指南节点")
    if not first_nonempty(row.get("recommendation_class")):
        missing.append("缺推荐等级")
    if not first_nonempty(row.get("evidence_level")):
        missing.append("缺证据等级")
    if first_nonempty(row.get("conflict_status")) in {"待裁决", "冲突待裁决"}:
        missing.append("冲突待裁决")

    adj_code = sha_code("SRCADJ-CARD-BULK", row["rec_code"])
    adj_name = f"{category}推荐来源裁决｜{first_nonempty(row.get('rec_display_name'), row.get('rec_name'))[:80]}"
    statement_text = first_nonempty(row.get("statement_text"), row.get("statement_summary"), row.get("rec_name"))

    return {
        "raw": row,
        "category": category,
        "missing": missing,
        "disease": disease,
        "action": action,
        "evidence": evidence,
        "guideline": guideline,
        "adj_code": adj_code,
        "adj_name": adj_name,
        "disease_code": disease_code,
        "disease_name": disease_name,
        "action_code": action_code,
        "action_name": action_name,
        "action_entity_type": action_entity_type or (action or {}).get("entityType") or "",
        "action_rel": action_rel,
        "primary_evidence_code": primary_evidence_code,
        "primary_guideline_code": primary_guideline_code,
        "primary_guideline_name": primary_guideline_name or (guideline or {}).get("name") or "",
        "recommendation_class": first_nonempty(row.get("recommendation_class")),
        "evidence_level": first_nonempty(row.get("evidence_level")),
        "statement_text": statement_text,
    }


def import_candidate(tx, c: Dict[str, Any]) -> Dict[str, Any]:
    row = c["raw"]
    rec_id = row["rec_id"]
    props = {
        "code": c["adj_code"],
        "name": c["adj_name"],
        "display_name": c["adj_name"],
        "preferred_name": c["adj_name"],
        "entityType": "SourceAdjudication",
        "中文名称": "推荐来源裁决",
        "category": c["category"],
        "disease_code": c["disease_code"],
        "disease_name": c["disease_name"],
        "clinical_question": first_nonempty(row.get("statement_summary"), row.get("rec_name"))[:120],
        "clinical_scenario": first_nonempty(row.get("applicable_population"), row.get("indication_conditions"), "适用于满足该推荐触发条件的患者"),
        "final_recommendation": c["statement_text"],
        "action_code": c["action_code"],
        "action_name": c["action_name"],
        "action_type": c["action_entity_type"],
        "action_relation": c["action_rel"],
        "primary_guideline_code": c["primary_guideline_code"],
        "primary_guideline_name": c["primary_guideline_name"],
        "primary_evidence_code": c["primary_evidence_code"],
        "recommendation_class": c["recommendation_class"],
        "evidence_level": c["evidence_level"],
        "supporting_guidelines": [],
        "conflict_status": first_nonempty(row.get("conflict_status"), "无冲突"),
        "adjudication_reason": "批量推广：该推荐已具备正式准入、动作、主证据、主指南和等级字段，按现有RecommendationStatement生成推荐来源裁决。",
        "cdss_use_status": "正式推荐",
        "clinical_use_status": "clinical_ready",
        "clinical_review_status": "clinical_ready",
        "review_status": "passed",
        "formal_cdss_ready": True,
        "schema_version": SCHEMA_VERSION,
        "batch_id": BATCH_ID,
        "created_at": RUN_AT,
        "updated_at": RUN_AT,
    }
    adj_id = merge_source_adjudication(tx, props)
    rec_update = {
        "cdss_use_status": "正式推荐",
        "clinical_use_status": "clinical_ready",
        "clinical_review_status": "clinical_ready",
        "formal_cdss_ready": True,
        "primary_evidence_code": c["primary_evidence_code"],
        "primary_guideline_code": c["primary_guideline_code"],
        "primary_guideline_name": c["primary_guideline_name"],
        "action_code": c["action_code"],
        "action_name": c["action_name"],
        "source_adjudication_code": c["adj_code"],
        "updated_at": RUN_AT,
    }
    update_rec_formal_fields(tx, rec_id, rec_update)
    rel_base = {
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "created_at": RUN_AT,
        "updated_at": RUN_AT,
        "clinical_use_status": "clinical_ready",
        "clinical_review_status": "clinical_ready",
        "cdss_use_status": "正式推荐",
        "formal_cdss_ready": True,
        "recommendation_class": c["recommendation_class"],
        "evidence_level": c["evidence_level"],
        "primary_evidence_code": c["primary_evidence_code"],
        "primary_guideline_code": c["primary_guideline_code"],
        "source_adjudication_code": c["adj_code"],
        "recommendation_statement_code": row["rec_code"],
    }
    rels = [
        (c["disease"]["id"], "has_source_adjudication", adj_id),
        (adj_id, "uses_primary_guideline", c["guideline"]["id"]),
        (adj_id, "decides_recommendation", rec_id),
        (adj_id, "derived_from", c["evidence"]["id"]),
        (adj_id, c["action_rel"], c["action"]["id"]),
        (rec_id, "based_on_guideline", c["guideline"]["id"]),
        (rec_id, "derived_from", c["evidence"]["id"]),
        (rec_id, c["action_rel"], c["action"]["id"]),
    ]
    rel_ids = []
    for sid, rel_type, tid in rels:
        rel_ids.append(merge_relation(tx, sid, rel_type, tid, rel_base))
    return {"adj_code": c["adj_code"], "rec_code": row["rec_code"], "category": c["category"], "rel_count": len(rel_ids)}


def run() -> Dict[str, Any]:
    cfg = read_db_config()
    candidates: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    imported: List[Dict[str, Any]] = []
    node_delta: List[Dict[str, Any]] = []
    relation_delta: List[Dict[str, Any]] = []

    with GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"])) as driver:
        with driver.session() as session:
            rows = session.execute_read(fetch_recommendations)
            for row in rows:
                c = session.execute_read(normalize_candidate, row)
                if c["category"] not in TARGET_CATEGORIES:
                    continue
                simple = {
                    "大类": c["category"],
                    "推荐编码": row["rec_code"],
                    "推荐名称": first_nonempty(row.get("rec_display_name"), row.get("rec_name")),
                    "疾病编码": c["disease_code"],
                    "疾病名称": c["disease_name"],
                    "动作编码": c["action_code"],
                    "动作名称": c["action_name"],
                    "动作关系": c["action_rel"],
                    "主证据编码": c["primary_evidence_code"],
                    "主指南编码": c["primary_guideline_code"],
                    "主指南名称": c["primary_guideline_name"],
                    "推荐等级": c["recommendation_class"],
                    "证据等级": c["evidence_level"],
                    "阻断原因": "；".join(c["missing"]),
                }
                if c["missing"]:
                    blocked.append(simple)
                else:
                    candidates.append(simple)
                    node_delta.append(
                        {
                            "code": c["adj_code"],
                            "entityType": "SourceAdjudication",
                            "name": c["adj_name"],
                            "category": c["category"],
                            "recommendation_statement_code": row["rec_code"],
                            "primary_evidence_code": c["primary_evidence_code"],
                            "primary_guideline_code": c["primary_guideline_code"],
                            "action_code": c["action_code"],
                        }
                    )
                    result = session.execute_write(import_candidate, c)
                    imported.append(result)
                    relation_delta.append({"source_adjudication_code": result["adj_code"], "recommendation_statement_code": result["rec_code"], "relation_count": result["rel_count"]})

            verify = session.run(
                """
                MATCH (adj:KGNode {entityType:'SourceAdjudication'})
                WHERE adj.batch_id=$batch_id
                RETURN
                  count(adj) AS source_adjudication_count,
                  count { (adj) WHERE adj.primary_evidence_code IS NULL OR adj.primary_evidence_code='' } AS missing_primary_evidence,
                  count { (adj) WHERE adj.primary_guideline_code IS NULL OR adj.primary_guideline_code='' } AS missing_primary_guideline,
                  count { (adj) WHERE adj.recommendation_class IS NULL OR adj.recommendation_class='' } AS missing_recommendation_class,
                  count { (adj) WHERE adj.evidence_level IS NULL OR adj.evidence_level='' } AS missing_evidence_level,
                  count { (adj) WHERE adj.action_code IS NULL OR adj.action_code='' } AS missing_action_code,
                  count { (adj) WHERE adj.cdss_use_status <> '正式推荐' } AS non_formal
                """,
                batch_id=BATCH_ID,
            ).single().data()
            category_verify = session.run(
                """
                MATCH (adj:KGNode {entityType:'SourceAdjudication'})
                WHERE adj.batch_id=$batch_id
                RETURN adj.category AS category, count(adj) AS count
                ORDER BY category
                """,
                batch_id=BATCH_ID,
            ).data()
            rel_verify = session.run(
                """
                MATCH ()-[r]->()
                WHERE r.batch_id=$batch_id
                RETURN type(r) AS relationship, count(r) AS count
                ORDER BY relationship
                """,
                batch_id=BATCH_ID,
            ).data()

    write_csv(OUT / "推荐来源裁决批量推广_候选入库清单_20260717.csv", candidates)
    write_csv(OUT / "推荐来源裁决批量推广_阻断清单_20260717.csv", blocked)
    write_csv(OUT / "推荐来源裁决批量推广_已入库清单_20260717.csv", imported)
    write_jsonl(OUT / "nodes_delta_final.jsonl", node_delta)
    write_jsonl(OUT / "relations_delta_final.jsonl", relation_delta)

    summary_by_category: Dict[str, Dict[str, int]] = {}
    for item in candidates:
        summary_by_category.setdefault(item["大类"], {"入库候选": 0, "阻断": 0})
        summary_by_category[item["大类"]]["入库候选"] += 1
    for item in blocked:
        summary_by_category.setdefault(item["大类"], {"入库候选": 0, "阻断": 0})
        summary_by_category[item["大类"]]["阻断"] += 1

    result = {
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "run_at": RUN_AT,
        "target_categories": TARGET_CATEGORIES,
        "candidate_count": len(candidates),
        "blocked_count": len(blocked),
        "imported_count": len(imported),
        "summary_by_category": summary_by_category,
        "verify": verify,
        "category_verify": category_verify,
        "relationship_verify": rel_verify,
    }
    (OUT / "推荐来源裁决批量推广_入库结果_20260717.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        "# 推荐来源裁决批量推广报告（2026-07-17）",
        "",
        f"- 批次：{BATCH_ID}",
        f"- Schema：{SCHEMA_VERSION}",
        f"- 执行时间：{RUN_AT}",
        f"- 入库候选：{len(candidates)}",
        f"- 已入库：{len(imported)}",
        f"- 阻断：{len(blocked)}",
        "",
        "## 大类结果",
        "",
        "| 大类 | 已入库 | 阻断 |",
        "|---|---:|---:|",
    ]
    for cat in TARGET_CATEGORIES:
        s = summary_by_category.get(cat, {"入库候选": 0, "阻断": 0})
        report.append(f"| {cat} | {s['入库候选']} | {s['阻断']} |")
    report.extend(
        [
            "",
            "## 服务器硬闸门",
            "",
            f"- 来源裁决节点：{verify.get('source_adjudication_count')}",
            f"- 缺主证据：{verify.get('missing_primary_evidence')}",
            f"- 缺主指南：{verify.get('missing_primary_guideline')}",
            f"- 缺推荐等级：{verify.get('missing_recommendation_class')}",
            f"- 缺证据等级：{verify.get('missing_evidence_level')}",
            f"- 缺动作编码：{verify.get('missing_action_code')}",
            f"- 非正式CDSS状态：{verify.get('non_formal')}",
            "",
            "## 输出文件",
            "",
            "- `推荐来源裁决批量推广_候选入库清单_20260717.csv`",
            "- `推荐来源裁决批量推广_阻断清单_20260717.csv`",
            "- `推荐来源裁决批量推广_已入库清单_20260717.csv`",
            "- `nodes_delta_final.jsonl`",
            "- `relations_delta_final.jsonl`",
        ]
    )
    (OUT / "推荐来源裁决批量推广报告_20260717.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
