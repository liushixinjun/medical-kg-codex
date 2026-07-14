# -*- coding: utf-8 -*-
"""生成冠心病检验指标批量精修包。

原则：
- 不新增 LabTestIndicator。
- 优先复用服务器已存在的同名 ExamIndicator，减少重复节点。
- 只补 LabTest -> lab_test_has_indicator -> ExamIndicator 缺失关系。
- 没有明确映射或证据不足的检验项目进入缺口，不硬补。
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "心血管内科文献集合"
OUT_DIR = COLLECTION / "BATCH-CARD-CAD-LABIND-20260713-001_冠心病检验指标批量精修_lab_indicator_refine"
BATCH_ID = "BATCH-CARD-CAD-LABIND-20260713-001"
CREATED_AT = "2026-07-13 00:55:00"
SCHEMA_VERSION = "V1.15"
SKILL_VERSION = "V2.1-CAD-lab-indicator-refine"

SOURCE_NAME = "《内科学（第10版）》与已入库冠心病指南证据"


LAB_TO_INDICATORS = {
    "CK-MB": ["肌酸激酶同工酶升高"],
    "肌酸激酶同工酶": ["肌酸激酶同工酶升高"],
    "肌酸激酶同工酶MB": ["肌酸激酶同工酶升高"],
    "肌酸激酶": ["肌酸激酶升高"],
    "心肌肌钙蛋白": ["心肌肌钙蛋白升高"],
    "肌钙蛋白": ["心肌肌钙蛋白升高"],
    "肌红蛋白": ["肌红蛋白升高"],
    "血常规": ["白细胞计数升高", "中性粒细胞增多", "嗜酸性粒细胞减少或消失"],
    "白细胞计数": ["白细胞计数升高"],
    "红细胞沉降率": ["红细胞沉降率增快"],
    "血沉": ["红细胞沉降率增快"],
    "C反应蛋白": ["C反应蛋白升高"],
    "CRP": ["C反应蛋白升高"],
    "低密度脂蛋白胆固醇": ["低密度脂蛋白胆固醇升高"],
    "血脂检查": ["低密度脂蛋白胆固醇升高"],
    "血脂": ["低密度脂蛋白胆固醇升高"],
    "D-二聚体": ["D-二聚体升高"],
    "游离脂肪酸": ["游离脂肪酸升高"],
}


NEW_INDICATORS = {
    "游离脂肪酸升高": {
        "code": "IND-CARD-LAB-FREE-FATTY-ACID-HIGH",
        "evidence_code": "EVD-CARD-CAD-LABIND-FREE-FATTY-ACID",
        "clinical_use": "AMI起病数小时至2日内可出现的代谢变化，作为辅助线索，不作为AMI核心确诊指标。",
        "evidence_text": "急性心肌梗死起病数小时至2日内血中游离脂肪酸增高。",
        "source_page": "251",
    }
}


def short_hash(text: str, n: int = 20) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest().upper()[:n]


def kg_id(code: str) -> str:
    return "KG_" + code.replace("-", "_")


def rel_id(source: str, relation_type: str, target: str) -> str:
    return "REL-" + short_hash(f"{source}|{relation_type}|{target}", 20)


def parse_conn() -> tuple[str, str, str, str]:
    text = (ROOT / "图谱数据库链接.txt").read_text(encoding="utf-8", errors="ignore")
    http = re.search(r"https?://[^\s]+", text)
    bolt = re.search(r"bolt://[^\s]+", text)
    user = re.search(r"用户名\s*[:：]\s*([^\s]+)", text)
    pwd = re.search(r"密码\s*[:：]\s*([^\s]+)", text)
    if not (http and bolt and user and pwd):
        raise RuntimeError("图谱数据库链接.txt 缺少 http/bolt/用户名/密码字段")
    return http.group(0), bolt.group(0), user.group(1), pwd.group(1)


def base_node(entity_type: str, code: str, name: str, **props: Any) -> dict[str, Any]:
    node = {
        "id": kg_id(code),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": props.pop("entityCategory", ""),
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "scope_type": "disease_category",
        "scope_target": "冠心病",
        "source_type": "authoritative_textbook",
        "source_authority": SOURCE_NAME,
        "source_name": SOURCE_NAME,
        "clinical_review_status": "pending_clinical_use_effect_review",
        "review_status": "ai_prechecked",
        "merge_status": "delta_ready",
        "formal_cdss_ready": False,
        "cdss_release_level": "test_recommendation",
        "created_at": CREATED_AT,
    }
    node.update({k: v for k, v in props.items() if v not in (None, "")})
    return node


def relation(source_code: str, relation_type: str, target_code: str, *, disease_code: str, disease_name: str, evidence_ids: list[str]) -> dict[str, Any]:
    return {
        "id": rel_id(source_code, relation_type, target_code),
        "source_code": source_code,
        "relationType": relation_type,
        "target_code": target_code,
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "source_type": "authoritative_textbook",
        "source_authority": SOURCE_NAME,
        "disease_code": disease_code,
        "disease_name": disease_name,
        "formal_cdss_ready": False,
        "clinical_review_status": "pending_clinical_use_effect_review",
        "created_at": CREATED_AT,
        "evidence_ids": evidence_ids,
        "evidence_count": len(evidence_ids),
    }


def fetch_inputs() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[str]]]:
    _, bolt, user, password = parse_conn()
    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session() as s:
            lab_rows = s.run(
                """
                MATCH (d:KGNode {entityType:'Disease'})-[:requires_lab_test]->(l:KGNode)
                WHERE d.code STARTS WITH 'DIS-CARD-CAD'
                   OR coalesce(d.disease_category,'') CONTAINS '冠'
                   OR coalesce(d.category,'') CONTAINS '冠'
                OPTIONAL MATCH (l)-[:lab_test_has_indicator]->(i:KGNode)
                WITH d,l,count(DISTINCT i) AS indicator_count
                RETURN d.code AS disease_code, d.name AS disease_name, l.code AS lab_code, l.name AS lab_name, indicator_count
                ORDER BY d.code,l.name,l.code
                """
            ).data()
            indicators = {
                row["name"]: row
                for row in s.run(
                    """
                    MATCH (i:KGNode {entityType:'ExamIndicator'})
                    WHERE i.name IN $names
                    RETURN i.name AS name, i.code AS code
                    """,
                    names=list({n for names in LAB_TO_INDICATORS.values() for n in names}),
                ).data()
            }
            indicator_evidence: dict[str, list[str]] = {}
            for row in s.run(
                """
                MATCH (i:KGNode {entityType:'ExamIndicator'})-[:supported_by_evidence]->(e:KGNode {entityType:'Evidence'})
                WHERE i.name IN $names
                RETURN i.name AS name, collect(DISTINCT e.code) AS evidence_codes
                """,
                names=list({n for names in LAB_TO_INDICATORS.values() for n in names}),
            ).data():
                indicator_evidence[row["name"]] = row["evidence_codes"] or []
    return lab_rows, indicators, indicator_evidence


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    lab_rows, existing_indicators, indicator_evidence = fetch_inputs()
    nodes: dict[str, dict[str, Any]] = {}
    rels: dict[tuple[str, str, str], dict[str, Any]] = {}
    adopted: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    for name, spec in NEW_INDICATORS.items():
        if name not in existing_indicators:
            ind = base_node(
                "ExamIndicator",
                spec["code"],
                name,
                entityCategory="检查/检验指标",
                indicator_category="检验指标",
                indicator_domain="lab_test",
                value_direction="升高",
                clinical_use=spec["clinical_use"],
                description=spec["clinical_use"],
            )
            ev = base_node(
                "Evidence",
                spec["evidence_code"],
                f"冠心病-{name}-教材证据",
                entityCategory="证据",
                evidence_role="textbook_lab_indicator_original",
                evidence_slot="exam_lab",
                evidence_text=spec["evidence_text"],
                original_text=spec["evidence_text"],
                evidence_summary=spec["evidence_text"],
                source_page=spec["source_page"],
                source_location=f"《内科学（第10版）》第{spec['source_page']}页",
                recommendation_class="N/A",
                evidence_level="N/A",
                knowledge_strength="high",
                clinical_applicability="general",
            )
            nodes[ind["code"]] = ind
            nodes[ev["code"]] = ev
            rels[(ind["code"], "supported_by_evidence", ev["code"])] = relation(
                ind["code"], "supported_by_evidence", ev["code"],
                disease_code="DIS-CARD-CAD", disease_name="冠心病", evidence_ids=[ev["code"]]
            )
            existing_indicators[name] = {"name": name, "code": ind["code"]}
            indicator_evidence[name] = [ev["code"]]

    for row in lab_rows:
        lab_name = row["lab_name"]
        if row["indicator_count"] and row["indicator_count"] > 0:
            continue
        target_names = LAB_TO_INDICATORS.get(lab_name)
        if not target_names:
            gaps.append({**row, "缺口原因": "未建立安全指标映射或证据不足"})
            continue
        for indicator_name in target_names:
            indicator = existing_indicators.get(indicator_name)
            if not indicator:
                gaps.append({**row, "缺口原因": f"指标节点不存在：{indicator_name}"})
                continue
            evidence_ids = indicator_evidence.get(indicator_name) or []
            rel = relation(
                row["lab_code"],
                "lab_test_has_indicator",
                indicator["code"],
                disease_code=row["disease_code"],
                disease_name=row["disease_name"],
                evidence_ids=evidence_ids,
            )
            rels[(rel["source_code"], rel["relationType"], rel["target_code"])] = rel
            adopted.append(
                {
                    "疾病编码": row["disease_code"],
                    "疾病名称": row["disease_name"],
                    "检验项目编码": row["lab_code"],
                    "检验项目名称": lab_name,
                    "指标编码": indicator["code"],
                    "指标名称": indicator_name,
                    "证据编码": "；".join(evidence_ids),
                }
            )
    return list(nodes.values()), list(rels.values()), adopted, gaps


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
    path.write_text((text + "\n") if text else "", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


def audit(nodes: list[dict[str, Any]], rels: list[dict[str, Any]]) -> dict[str, Any]:
    rel_keys = [(r["source_code"], r["relationType"], r["target_code"]) for r in rels]
    duplicate_rel_keys = sorted({"|".join(k) for k in rel_keys if rel_keys.count(k) > 1})
    evidence_without_text = [n["code"] for n in nodes if n.get("entityType") == "Evidence" and not n.get("evidence_text")]
    missing_required = [n.get("code") for n in nodes if not n.get("code") or not n.get("name") or not n.get("entityType")]
    rel_without_evidence = [
        r["id"] for r in rels
        if r["relationType"] == "lab_test_has_indicator" and not r.get("evidence_ids")
    ]
    return {
        "batch_id": BATCH_ID,
        "node_count": len(nodes),
        "relation_count": len(rels),
        "lab_test_has_indicator_relation_count": sum(1 for r in rels if r["relationType"] == "lab_test_has_indicator"),
        "duplicate_relation_keys": duplicate_rel_keys,
        "missing_required": missing_required,
        "evidence_without_text": evidence_without_text,
        "lab_indicator_relation_without_evidence_count": len(rel_without_evidence),
        "local_hard_gate_pass": not (duplicate_rel_keys or missing_required or evidence_without_text or rel_without_evidence),
    }


def main() -> int:
    for sub in ["00_config", "02_delta", "03_audit", "04_reports"]:
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)
    nodes, rels, adopted, gaps = build()
    summary = audit(nodes, rels)
    write_jsonl(OUT_DIR / "02_delta" / "delta_nodes_upsert.jsonl", nodes)
    write_jsonl(OUT_DIR / "02_delta" / "delta_relations_add.jsonl", rels)
    write_csv(OUT_DIR / "03_audit" / "冠心病检验指标批量精修采纳明细.csv", adopted, ["疾病编码", "疾病名称", "检验项目编码", "检验项目名称", "指标编码", "指标名称", "证据编码"])
    write_csv(OUT_DIR / "03_audit" / "冠心病检验指标缺口.csv", gaps, ["disease_code", "disease_name", "lab_code", "lab_name", "indicator_count", "缺口原因"])
    (OUT_DIR / "03_audit" / "quality_audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "00_config" / "batch_config.json").write_text(json.dumps({"batch_id": BATCH_ID, "scope_target": "冠心病", "purpose": "批量补全冠心病组检验项目到检验指标的下钻关系"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# 冠心病检验指标批量精修报告",
        "",
        f"- 批次：`{BATCH_ID}`",
        f"- 节点：{summary['node_count']}",
        f"- 关系：{summary['relation_count']}",
        f"- lab_test_has_indicator：{summary['lab_test_has_indicator_relation_count']}",
        f"- 本地硬闸门：{'通过' if summary['local_hard_gate_pass'] else '未通过'}",
        f"- 因证据不足或未建立映射暂不硬补：{len(gaps)}",
    ]
    (OUT_DIR / "04_reports" / "冠心病检验指标批量精修报告_20260713.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["local_hard_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
