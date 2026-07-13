# -*- coding: utf-8 -*-
"""生成心内科检验指标安全补链包。

目标：
1. 不新增 LabTestIndicator，统一使用 ExamIndicator。
2. 仅处理已入库疾病中缺少 lab_test_has_indicator 的 LabTest。
3. 只采纳“有非空 evidence_text/original_text/evidence_summary”的证据，避免把旧骨架空证据继续扩散。
4. 只补通用、安全的“异常类/升高类”检验指标，不臆造阈值。
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
OUT_DIR = COLLECTION / "BATCH-CARD-LABIND-SAFE-20260713-001_心内科检验指标安全补链_lab_indicator_safe_refine"
BATCH_ID = "BATCH-CARD-LABIND-SAFE-20260713-001"
CREATED_AT = "2026-07-13 14:20:00"
SCHEMA_VERSION = "V1.15"
SKILL_VERSION = "V2.1-lab-indicator-safe-refine"

SCOPE_WHERE = """
(
  d.code STARTS WITH 'DIS-CARD-CAD'
  OR d.code STARTS WITH 'DIS-CARD-CM'
  OR d.code STARTS WITH 'DIS-CARD-HF'
  OR d.code STARTS WITH 'DIS-CARD-ARR'
  OR d.code STARTS WITH 'DIS-CARD-AF'
  OR d.code STARTS WITH 'DIS-CARD-SVT'
  OR d.code STARTS WITH 'DIS-CARD-AFL'
  OR d.code STARTS WITH 'DIS-CARD-VA'
  OR d.code STARTS WITH 'DIS-CARD-SCD'
  OR d.code STARTS WITH 'DIS-CARD-BRADY'
  OR d.code STARTS WITH 'DIS-CARD-AVB'
)
"""

# 检验项目 -> 标准指标名称。这里不写阈值，只补“异常/升高/阳性”的临床可解释指标层。
LAB_TO_INDICATORS: dict[str, list[str]] = {
    "INR": ["INR异常"],
    "凝血功能检查": ["凝血功能异常"],
    "甲状腺功能检查": ["甲状腺功能异常"],
    "电解质检查": ["电解质异常"],
    "肝功能检查": ["肝功能异常"],
    "肾功能检查": ["肾功能异常"],
    "血钾": ["血钾异常"],
    "血镁": ["血镁异常"],
}

INDICATOR_META: dict[str, dict[str, str]] = {
    "INR异常": {"code": "IND-CARD-LAB-INR-ABNORMAL", "value_direction": "异常"},
    "凝血功能异常": {"code": "IND-CARD-LAB-COAGULATION-ABNORMAL", "value_direction": "异常"},
    "甲状腺功能异常": {"code": "IND-CARD-LAB-THYROID-FUNCTION-ABNORMAL", "value_direction": "异常"},
    "电解质异常": {"code": "IND-CARD-LAB-ELECTROLYTE-ABNORMAL", "value_direction": "异常"},
    "肝功能异常": {"code": "IND-CARD-LAB-LIVER-FUNCTION-ABNORMAL", "value_direction": "异常"},
    "肾功能异常": {"code": "IND-CARD-LAB-RENAL-FUNCTION-ABNORMAL", "value_direction": "异常"},
    "血钾异常": {"code": "IND-CARD-LAB-POTASSIUM-ABNORMAL", "value_direction": "异常"},
    "血镁异常": {"code": "IND-CARD-LAB-MAGNESIUM-ABNORMAL", "value_direction": "异常"},
}


def short_hash(text: str, n: int = 20) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest().upper()[:n]


def kg_id(code: str) -> str:
    return "KG_" + code.replace("-", "_")


def rel_id(source_code: str, relation_type: str, target_code: str) -> str:
    return "REL-" + short_hash(f"{source_code}|{relation_type}|{target_code}", 20)


def parse_conn() -> tuple[str, str, str, str]:
    text = (ROOT / "图谱数据库链接.txt").read_text(encoding="utf-8", errors="ignore")
    http = re.search(r"https?://[^\s]+", text)
    bolt = re.search(r"bolt://[^\s]+", text)
    user = re.search(r"用户名\s*[:：]\s*([^\s]+)", text)
    pwd = re.search(r"密码\s*[:：]\s*([^\s]+)", text)
    if not (http and bolt and user and pwd):
        raise RuntimeError("图谱数据库链接.txt 缺少 HTTP/Bolt/用户名/密码字段")
    return http.group(0), bolt.group(0), user.group(1), pwd.group(1)


def base_node(entity_type: str, code: str, name: str, **props: Any) -> dict[str, Any]:
    node = {
        "id": kg_id(code),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "scope_type": "specialty_increment",
        "scope_target": "心血管内科",
        "source_type": "guideline_or_textbook_evidence_reuse",
        "source_authority": "已入库指南/教材原文证据",
        "source_name": "已入库指南/教材原文证据",
        "clinical_review_status": "pending_clinical_use_effect_review",
        "review_status": "ai_prechecked",
        "merge_status": "delta_ready",
        "formal_cdss_ready": False,
        "cdss_release_level": "test_recommendation",
        "created_at": CREATED_AT,
    }
    node.update({k: v for k, v in props.items() if v not in (None, "")})
    return node


def relation(
    source_code: str,
    relation_type: str,
    target_code: str,
    *,
    disease_code: str = "",
    disease_name: str = "",
    evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    evidence_ids = evidence_ids or []
    return {
        "id": rel_id(source_code, relation_type, target_code),
        "source_code": source_code,
        "relationType": relation_type,
        "target_code": target_code,
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "source_type": "guideline_or_textbook_evidence_reuse",
        "source_authority": "已入库指南/教材原文证据",
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
    indicator_names = sorted({name for names in LAB_TO_INDICATORS.values() for name in names})
    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session() as session:
            lab_rows = session.run(
                f"""
                MATCH (d:KGNode {{entityType:'Disease'}})-[:requires_lab_test]->(l:KGNode)
                WHERE {SCOPE_WHERE}
                  AND NOT (l)-[:lab_test_has_indicator]->(:KGNode {{entityType:'ExamIndicator'}})
                OPTIONAL MATCH (l)-[:supported_by_evidence]->(e:KGNode {{entityType:'Evidence'}})
                WITH d,l,collect(DISTINCT {{
                    code:e.code,
                    text:coalesce(e.evidence_text,e.original_text,e.evidence_summary,'')
                }}) AS evs
                RETURN d.code AS disease_code,
                       d.name AS disease_name,
                       l.code AS lab_code,
                       l.name AS lab_name,
                       [x IN evs WHERE x.code IS NOT NULL AND trim(x.text) <> '' | x.code][..5] AS evidence_codes,
                       size([x IN evs WHERE x.code IS NOT NULL]) AS evidence_count,
                       size([x IN evs WHERE x.code IS NOT NULL AND trim(x.text) <> '']) AS nonempty_evidence_count
                ORDER BY d.code,l.name,l.code
                """
            ).data()
            existing_indicators = {
                row["name"]: row
                for row in session.run(
                    """
                    MATCH (i:KGNode {entityType:'ExamIndicator'})
                    WHERE i.name IN $names
                    RETURN i.name AS name, i.code AS code
                    """,
                    names=indicator_names,
                ).data()
            }
            indicator_evidence: dict[str, list[str]] = {
                row["name"]: row["evidence_codes"] or []
                for row in session.run(
                    """
                    MATCH (i:KGNode {entityType:'ExamIndicator'})-[:supported_by_evidence]->(e:KGNode {entityType:'Evidence'})
                    WHERE i.name IN $names
                    RETURN i.name AS name, collect(DISTINCT e.code)[..10] AS evidence_codes
                    """,
                    names=indicator_names,
                ).data()
            }
    return lab_rows, existing_indicators, indicator_evidence


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    lab_rows, existing_indicators, indicator_evidence = fetch_inputs()
    nodes: dict[str, dict[str, Any]] = {}
    rels: dict[tuple[str, str, str], dict[str, Any]] = {}
    adopted: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    for row in lab_rows:
        lab_name = row["lab_name"]
        target_names = LAB_TO_INDICATORS.get(lab_name)
        if not target_names:
            gaps.append({**row, "缺口原因": "未建立安全映射"})
            continue
        evidence_ids = [x for x in (row.get("evidence_codes") or []) if x]
        if not evidence_ids:
            gaps.append({**row, "缺口原因": "缺少非空原文证据，暂不补链"})
            continue

        for indicator_name in target_names:
            indicator = existing_indicators.get(indicator_name)
            if indicator:
                indicator_code = indicator["code"]
            else:
                meta = INDICATOR_META[indicator_name]
                indicator_code = meta["code"]
                nodes[indicator_code] = base_node(
                    "ExamIndicator",
                    indicator_code,
                    indicator_name,
                    entityCategory="检查/检验指标",
                    indicator_category="检验指标",
                    indicator_domain="lab_test",
                    value_direction=meta["value_direction"],
                    clinical_use=f"用于表达检验项目“{lab_name}”在相关心血管疾病场景中的异常结果。",
                    description=f"检验指标：{indicator_name}；来源于已入库 LabTest 的非空原文证据。",
                )
                existing_indicators[indicator_name] = {"name": indicator_name, "code": indicator_code}

            for evidence_code in evidence_ids[:3]:
                rels[(indicator_code, "supported_by_evidence", evidence_code)] = relation(
                    indicator_code,
                    "supported_by_evidence",
                    evidence_code,
                    evidence_ids=[evidence_code],
                )
            rels[(row["lab_code"], "lab_test_has_indicator", indicator_code)] = relation(
                row["lab_code"],
                "lab_test_has_indicator",
                indicator_code,
                evidence_ids=evidence_ids[:5],
            )
            adopted.append(
                {
                    "疾病编码": row["disease_code"],
                    "疾病名称": row["disease_name"],
                    "检验项目编码": row["lab_code"],
                    "检验项目名称": lab_name,
                    "指标编码": indicator_code,
                    "指标名称": indicator_name,
                    "证据编码": "；".join(evidence_ids[:5]),
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
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def audit(nodes: list[dict[str, Any]], rels: list[dict[str, Any]]) -> dict[str, Any]:
    rel_keys = [(r["source_code"], r["relationType"], r["target_code"]) for r in rels]
    duplicate_rel_keys = sorted({"|".join(k) for k in rel_keys if rel_keys.count(k) > 1})
    missing_required_nodes = [n.get("code") for n in nodes if not n.get("code") or not n.get("name") or not n.get("entityType")]
    rel_without_evidence = [
        r["id"]
        for r in rels
        if r["relationType"] in {"lab_test_has_indicator", "supported_by_evidence"} and not r.get("evidence_ids")
    ]
    return {
        "batch_id": BATCH_ID,
        "node_count": len(nodes),
        "relation_count": len(rels),
        "indicator_node_count": sum(1 for n in nodes if n.get("entityType") == "ExamIndicator"),
        "lab_test_has_indicator_relation_count": sum(1 for r in rels if r["relationType"] == "lab_test_has_indicator"),
        "supported_by_evidence_relation_count": sum(1 for r in rels if r["relationType"] == "supported_by_evidence"),
        "duplicate_relation_keys": duplicate_rel_keys,
        "missing_required_nodes": missing_required_nodes,
        "relation_without_evidence_count": len(rel_without_evidence),
        "local_hard_gate_pass": not (duplicate_rel_keys or missing_required_nodes or rel_without_evidence),
    }


def main() -> int:
    for sub in ["00_config", "02_delta", "03_audit", "04_reports"]:
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)

    nodes, rels, adopted, gaps = build()
    summary = audit(nodes, rels)
    write_jsonl(OUT_DIR / "02_delta" / "delta_nodes_upsert.jsonl", nodes)
    write_jsonl(OUT_DIR / "02_delta" / "delta_relations_add.jsonl", rels)
    write_csv(
        OUT_DIR / "03_audit" / "心内科检验指标安全补链采纳明细.csv",
        adopted,
        ["疾病编码", "疾病名称", "检验项目编码", "检验项目名称", "指标编码", "指标名称", "证据编码"],
    )
    write_csv(
        OUT_DIR / "03_audit" / "心内科检验指标安全补链剩余缺口.csv",
        gaps,
        ["disease_code", "disease_name", "lab_code", "lab_name", "evidence_count", "nonempty_evidence_count", "缺口原因"],
    )
    (OUT_DIR / "03_audit" / "quality_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "00_config" / "batch_config.json").write_text(
        json.dumps(
            {
                "batch_id": BATCH_ID,
                "scope_target": "心血管内科已解析疾病大类",
                "purpose": "安全补全 LabTest 到 ExamIndicator 的检验指标下钻关系",
                "accepted_rule": "仅采纳已入库 LabTest 非空原文证据；无证据文本不硬补。",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report = [
        "# 心内科检验指标安全补链报告",
        "",
        f"- 批次：`{BATCH_ID}`",
        f"- 新增/更新指标节点：{summary['node_count']}",
        f"- 新增关系：{summary['relation_count']}",
        f"- 其中 lab_test_has_indicator：{summary['lab_test_has_indicator_relation_count']}",
        f"- 因缺少非空原文证据或未建立安全映射保留缺口：{len(gaps)}",
        f"- 本地硬闸门：{'通过' if summary['local_hard_gate_pass'] else '未通过'}",
    ]
    (OUT_DIR / "04_reports" / "心内科检验指标安全补链报告_20260713.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["local_hard_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
