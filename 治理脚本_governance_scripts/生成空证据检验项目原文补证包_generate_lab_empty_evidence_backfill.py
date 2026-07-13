# -*- coding: utf-8 -*-
"""生成“空证据检验项目”原文补证包。

用途：
1. 从 Neo4j 读取心血管内科已入库疾病的 LabTest 缺口。
2. 从本地心血管/心内科 docx 原文中抽取非空证据片段。
3. 生成 delta nodes / relations，不直接写库。

安全边界：
- 不创建 LabTestIndicator，检验指标统一使用 ExamIndicator。
- 不硬补无直接心内科证据的项目，例如 AMI/HF 下的“血培养”默认阻断。
- 所有 Evidence 节点必须有非空 evidence_text/original_text。
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "心血管内科文献集合"
BATCH_ID = "BATCH-CARD-LAB-EVIDENCE-20260713-001"
OUT_DIR = COLLECTION / f"{BATCH_ID}_空证据检验项目原文补证_lab_empty_evidence_backfill"
SCHEMA_VERSION = "V1.15"
SKILL_VERSION = "V2.1-lab-evidence-backfill"
CREATED_AT = "2026-07-13 17:30:00"

CARDIO_TERMS = ("心血管内科", "心内科")

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


@dataclass(frozen=True)
class IndicatorRule:
    indicator_name: str
    indicator_code: str
    value_direction: str
    keyword: str
    source_hint: str
    note: str = ""


LAB_RULES: dict[str, IndicatorRule] = {
    "肾功能": IndicatorRule("肾功能异常", "IND-CARD-LAB-RENAL-FUNCTION-ABNORMAL", "异常", "肾功能", "心力衰竭（县医院适用版）"),
    "血糖": IndicatorRule("血糖异常", "IND-CARD-LAB-GLUCOSE-ABNORMAL", "异常", "血糖", "心力衰竭（县医院适用版）"),
    "血脂": IndicatorRule("血脂异常", "IND-CARD-LAB-LIPID-ABNORMAL", "异常", "血脂", "心力衰竭（县医院适用版）"),
    "血脂检查": IndicatorRule("血脂异常", "IND-CARD-LAB-LIPID-ABNORMAL", "异常", "血脂", "心力衰竭（县医院适用版）"),
    "电解质": IndicatorRule("电解质异常", "IND-CARD-LAB-ELECTROLYTE-ABNORMAL", "异常", "电解质", "心力衰竭（县医院适用版）"),
    "动脉血气分析": IndicatorRule("动脉血气异常", "IND-CARD-LAB-ABG-ABNORMAL", "异常", "动脉血气分析", "心力衰竭（县医院适用版）"),
    "肌钙蛋白": IndicatorRule("心肌肌钙蛋白升高", "IND-CARD-AMI-LAB-2906F6AE1C62", "升高", "肌钙蛋白", "《内科学（第10版）》"),
    "肌酸激酶": IndicatorRule("肌酸激酶升高", "IND-CARD-AMI-LAB-68AAB9D88BA4", "升高", "肌酸激酶", "《内科学（第10版）》"),
    "肌酸激酶同工酶MB": IndicatorRule("肌酸激酶同工酶升高", "IND-CARD-AMI-LAB-0FC93EB091FE", "升高", "CK-MB", "《内科学（第10版）》"),
    "脑钠肽": IndicatorRule("BNP升高", "IND-CARD-LAB-BNP-ELEVATED", "升高", "BNP", "心力衰竭（县医院适用版）"),
    "B型钠尿肽": IndicatorRule("BNP升高", "IND-CARD-LAB-BNP-ELEVATED", "升高", "BNP", "心力衰竭（县医院适用版）"),
    "B型利钠肽": IndicatorRule("BNP升高", "IND-CARD-LAB-BNP-ELEVATED", "升高", "BNP", "心力衰竭（县医院适用版）"),
    "BNP": IndicatorRule("BNP升高", "IND-CARD-LAB-BNP-ELEVATED", "升高", "BNP", "心力衰竭（县医院适用版）"),
    "N末端B型钠尿肽前体": IndicatorRule("NT-proBNP升高", "IND-CARD-LAB-NTPROBNP-ELEVATED", "升高", "NT-proBNP", "心力衰竭（县医院适用版）"),
    "NT-proBNP": IndicatorRule("NT-proBNP升高", "IND-CARD-LAB-NTPROBNP-ELEVATED", "升高", "NT-proBNP", "心力衰竭（县医院适用版）"),
}

BLOCKED_LABS = {
    "血培养": "当前缺口主要落在 AMI/HF 等场景，未找到支持这些疾病常规需要血培养的直接证据；只在急性心包炎资料中出现，暂不硬补。",
}


def short_hash(text: str, n: int = 16) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest().upper()[:n]


def kg_id(code: str) -> str:
    return "KG_" + code.replace("-", "_")


def rel_id(source_code: str, relation_type: str, target_code: str) -> str:
    return "REL-" + short_hash(f"{source_code}|{relation_type}|{target_code}", 20)


def parse_conn() -> tuple[str, str, str]:
    text = ""
    for path in ROOT.glob("*.txt"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        if "bolt://" in content and "http://" in content:
            text = content
            break
    if not text:
        raise RuntimeError("未找到 Neo4j 链接文件")
    bolt = re.search(r"bolt://[^\s；;]+", text)
    password = re.search(r"([A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+)", text)
    if not (bolt and password):
        raise RuntimeError("Neo4j Bolt 或密码解析失败")
    return bolt.group(0), "neo4j", password.group(1)


def read_docx_paragraphs(path: Path) -> list[str]:
    texts: list[str] = []
    try:
        with ZipFile(path) as zf:
            for name in zf.namelist():
                if not (name.startswith("word/") and name.endswith(".xml")):
                    continue
                if not any(x in name for x in ("document.xml", "footnotes.xml", "endnotes.xml")):
                    continue
                tree = ET.fromstring(zf.read(name))
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for para in tree.findall(".//w:p", ns):
                    text = "".join(t.text or "" for t in para.findall(".//w:t", ns))
                    text = re.sub(r"\s+", " ", text).strip()
                    if text:
                        texts.append(text)
    except Exception:
        return []
    return texts


def collect_cardio_docx() -> list[Path]:
    root = ROOT.parent
    docs: list[Path] = []
    for path in root.rglob("*.docx"):
        path_text = str(path)
        if "AI专科知识图谱生成" in path_text:
            continue
        if any(term in path_text for term in CARDIO_TERMS):
            docs.append(path)
    return docs


def build_evidence_catalog() -> dict[str, dict[str, str]]:
    docs = collect_cardio_docx()
    catalog: dict[str, dict[str, str]] = {}
    needed_rules = {name: rule for name, rule in LAB_RULES.items()}

    # 先按 source_hint 精确匹配，避免拿非心内科或非目标疾病的泛化材料。
    for lab_name, rule in needed_rules.items():
        candidate_docs = sorted(
            docs,
            key=lambda p: (0 if rule.source_hint in str(p) else 1, len(str(p))),
        )
        for path in candidate_docs:
            paras = read_docx_paragraphs(path)
            for i, para in enumerate(paras):
                if rule.keyword not in para:
                    continue
                ctx = " ".join(paras[max(0, i - 1) : min(len(paras), i + 2)])
                ctx = re.sub(r"\s+", " ", ctx).strip()
                if len(ctx) < 12:
                    continue
                catalog[lab_name] = {
                    "source_file_name": path.name,
                    "source_name": path.name,
                    "source_locator": f"docx段落命中：{rule.keyword}",
                    "evidence_text": ctx[:900],
                    "source_hint": rule.source_hint,
                }
                break
            if lab_name in catalog:
                break
    return catalog


def fetch_focus_rows() -> list[dict[str, Any]]:
    bolt, user, password = parse_conn()
    query = f"""
    MATCH (d:KGNode {{entityType:'Disease'}})-[:requires_lab_test]->(l:KGNode)
    WHERE {SCOPE_WHERE}
    OPTIONAL MATCH (l)-[:lab_test_has_indicator]->(i:KGNode {{entityType:'ExamIndicator'}})
    OPTIONAL MATCH (l)-[:supported_by_evidence]->(e:KGNode {{entityType:'Evidence'}})
    WITH d,l,collect(DISTINCT i.name) AS indicators,
         collect(DISTINCT {{code:e.code,text:coalesce(e.evidence_text,e.original_text,e.evidence_summary,'')}}) AS evs
    WITH d,l,indicators,[x IN evs WHERE x.code IS NOT NULL | x] AS evs
    RETURN d.code AS disease_code,
           d.name AS disease_name,
           l.code AS lab_code,
           l.name AS lab_name,
           size(indicators) AS indicator_count,
           size(evs) AS evidence_count,
           size([x IN evs WHERE trim(x.text) <> '']) AS nonempty_evidence_count,
           indicators AS indicators
    ORDER BY d.code,l.name,l.code
    """
    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        rows = driver.session().run(query).data()
    return [row for row in rows if row["indicator_count"] == 0 or row["nonempty_evidence_count"] == 0]


def fetch_existing_codes(codes: set[str]) -> set[str]:
    if not codes:
        return set()
    bolt, user, password = parse_conn()
    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        rows = driver.session().run(
            "MATCH (n:KGNode) WHERE n.code IN $codes RETURN n.code AS code",
            codes=sorted(codes),
        ).data()
    return {row["code"] for row in rows}


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
        "source_type": "textbook_or_clinical_path_original_evidence",
        "clinical_review_status": "pending_clinical_use_effect_review",
        "review_status": "ai_prechecked",
        "merge_status": "delta_ready",
        "formal_cdss_ready": False,
        "cdss_release_level": "test_recommendation",
        "created_at": CREATED_AT,
    }
    node.update({k: v for k, v in props.items() if v not in (None, "")})
    return node


def relation(source_code: str, relation_type: str, target_code: str, **props: Any) -> dict[str, Any]:
    rel = {
        "id": rel_id(source_code, relation_type, target_code),
        "source_code": source_code,
        "relationType": relation_type,
        "target_code": target_code,
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "source_type": "textbook_or_clinical_path_original_evidence",
        "clinical_review_status": "pending_clinical_use_effect_review",
        "formal_cdss_ready": False,
        "created_at": CREATED_AT,
    }
    rel.update({k: v for k, v in props.items() if v not in (None, "")})
    return rel


def build_delta() -> dict[str, Any]:
    focus_rows = fetch_focus_rows()
    catalog = build_evidence_catalog()

    indicator_codes = {rule.indicator_code for rule in LAB_RULES.values()}
    existing_codes = fetch_existing_codes(indicator_codes)

    nodes: dict[str, dict[str, Any]] = {}
    relations: dict[tuple[str, str, str], dict[str, Any]] = {}
    adopted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for row in focus_rows:
        lab_name = row["lab_name"]
        if lab_name in BLOCKED_LABS:
            blocked.append({**row, "blocked_reason": BLOCKED_LABS[lab_name]})
            continue
        rule = LAB_RULES.get(lab_name)
        if not rule:
            blocked.append({**row, "blocked_reason": "未配置安全映射规则，暂不自动补证"})
            continue
        evidence = catalog.get(lab_name)
        if not evidence or not evidence.get("evidence_text", "").strip():
            blocked.append({**row, "blocked_reason": f"未在本地心内科资料中命中非空原文证据：{rule.keyword}"})
            continue

        evidence_code = "EVI-CARD-LABBACKFILL-" + short_hash(
            f"{lab_name}|{evidence['source_file_name']}|{evidence['evidence_text']}", 18
        )
        nodes[evidence_code] = base_node(
            "Evidence",
            evidence_code,
            f"{lab_name}原文证据",
            evidence_text=evidence["evidence_text"],
            original_text=evidence["evidence_text"],
            evidence_summary=f"本证据说明心内科场景中检验项目“{lab_name}”的检查/判断依据。",
            source_name=evidence["source_name"],
            source_file_name=evidence["source_file_name"],
            source_locator=evidence["source_locator"],
            source_authority="本地心内科教材/临床路径原文",
            evidence_category="lab_test_original_evidence",
            evidence_granularity="paragraph",
        )

        if rule.indicator_code not in existing_codes:
            nodes[rule.indicator_code] = base_node(
                "ExamIndicator",
                rule.indicator_code,
                rule.indicator_name,
                entityCategory="检查/检验指标",
                indicator_category="检验指标",
                indicator_domain="lab_test",
                value_direction=rule.value_direction,
                clinical_use=f"用于表达检验项目“{lab_name}”在心血管疾病场景中的{rule.value_direction}结果。",
                description=f"检验指标：{rule.indicator_name}；由本地心内科原文证据补证生成。",
            )

        relations[(row["lab_code"], "supported_by_evidence", evidence_code)] = relation(
            row["lab_code"],
            "supported_by_evidence",
            evidence_code,
            evidence_ids=[evidence_code],
            evidence_count=1,
            evidence_scope="lab_test_node_evidence",
            disease_code=row["disease_code"],
            disease_name=row["disease_name"],
        )
        relations[(rule.indicator_code, "supported_by_evidence", evidence_code)] = relation(
            rule.indicator_code,
            "supported_by_evidence",
            evidence_code,
            evidence_ids=[evidence_code],
            evidence_count=1,
            evidence_scope="indicator_node_evidence",
            disease_code=row["disease_code"],
            disease_name=row["disease_name"],
        )
        relations[(row["lab_code"], "lab_test_has_indicator", rule.indicator_code)] = relation(
            row["lab_code"],
            "lab_test_has_indicator",
            rule.indicator_code,
            evidence_ids=[evidence_code],
            evidence_count=1,
            disease_code=row["disease_code"],
            disease_name=row["disease_name"],
        )
        adopted.append(
            {
                **row,
                "indicator_code": rule.indicator_code,
                "indicator_name": rule.indicator_name,
                "evidence_code": evidence_code,
                "source_file_name": evidence["source_file_name"],
                "evidence_text": evidence["evidence_text"],
            }
        )

    return {
        "focus_rows": focus_rows,
        "catalog": catalog,
        "nodes": list(nodes.values()),
        "relations": list(relations.values()),
        "adopted": adopted,
        "blocked": blocked,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def validate(nodes: list[dict[str, Any]], relations: list[dict[str, Any]]) -> dict[str, Any]:
    node_codes = {node["code"] for node in nodes}
    duplicate_node_codes = len(node_codes) != len(nodes)
    rel_keys = [(rel["source_code"], rel["relationType"], rel["target_code"]) for rel in relations]
    duplicate_relation_keys = len(set(rel_keys)) != len(rel_keys)
    empty_evidence_nodes = [
        node["code"]
        for node in nodes
        if node.get("entityType") == "Evidence" and not str(node.get("evidence_text", "")).strip()
    ]
    rel_without_id = [rel.get("id", "") for rel in relations if not rel.get("id")]
    hard_gate_pass = not (duplicate_node_codes or duplicate_relation_keys or empty_evidence_nodes or rel_without_id)
    return {
        "node_count": len(nodes),
        "relation_count": len(relations),
        "evidence_node_count": sum(1 for n in nodes if n.get("entityType") == "Evidence"),
        "indicator_node_count": sum(1 for n in nodes if n.get("entityType") == "ExamIndicator"),
        "lab_test_has_indicator_relation_count": sum(1 for r in relations if r.get("relationType") == "lab_test_has_indicator"),
        "supported_by_evidence_relation_count": sum(1 for r in relations if r.get("relationType") == "supported_by_evidence"),
        "duplicate_node_codes": duplicate_node_codes,
        "duplicate_relation_keys": duplicate_relation_keys,
        "empty_evidence_nodes": empty_evidence_nodes,
        "relation_without_id": rel_without_id,
        "hard_gate_pass": hard_gate_pass,
    }


def main() -> None:
    result = build_delta()
    nodes = result["nodes"]
    relations = result["relations"]
    audit = validate(nodes, relations)
    audit.update(
        {
            "batch_id": BATCH_ID,
            "focus_row_count": len(result["focus_rows"]),
            "adopted_row_count": len(result["adopted"]),
            "blocked_row_count": len(result["blocked"]),
            "catalog_lab_count": len(result["catalog"]),
            "blocked_labs": sorted({row["lab_name"] for row in result["blocked"]}),
            "adopted_labs": sorted({row["lab_name"] for row in result["adopted"]}),
        }
    )

    out_nodes = OUT_DIR / "03_delta" / "nodes.jsonl"
    out_relations = OUT_DIR / "03_delta" / "relations.jsonl"
    write_jsonl(out_nodes, nodes)
    write_jsonl(out_relations, relations)
    write_csv(OUT_DIR / "01_candidates" / "采纳补证清单.csv", result["adopted"])
    write_csv(OUT_DIR / "01_candidates" / "阻断清单.csv", result["blocked"])
    write_csv(OUT_DIR / "01_candidates" / "原文证据目录.csv", list(result["catalog"].values()))
    (OUT_DIR / "02_audit").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "02_audit" / "audit_summary.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "README.md").write_text(
        "\n".join(
            [
                f"# {BATCH_ID} 空证据检验项目原文补证",
                "",
                "本批次只补有本地心内科教材/临床路径原文证据的检验项目。",
                "血培养等无直接疾病场景证据的项目进入阻断清单，不硬补。",
                "",
                f"- 节点：{audit['node_count']}",
                f"- 关系：{audit['relation_count']}",
                f"- 采纳缺口行：{audit['adopted_row_count']}",
                f"- 阻断缺口行：{audit['blocked_row_count']}",
                f"- 本地硬闸门：{audit['hard_gate_pass']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
