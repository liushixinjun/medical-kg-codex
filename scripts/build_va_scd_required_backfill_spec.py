from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ENTITY_META = {
    "DiagnosisCriteria": ("诊断", "has_diagnostic_criteria", "DXC"),
    "FollowUp": ("治疗", "has_follow_up", "FU"),
    "Sign": ("临床", "has_sign", "SIGN"),
    "Prognosis": ("临床", "has_prognosis", "PROG"),
}


BACKFILL_RULES = {
    "diagnosis_criteria": {
        "entityType": "DiagnosisCriteria",
        "suffix": "诊断标准",
        "aliases": ["诊断", "诊断标准", "诊断依据", "diagnosis", "diagnostic"],
        "desired_pathways": {"diagnosis_criteria", "exam", "clinical_knowledge", "definition"},
        "keywords": [
            "诊断",
            "诊断标准",
            "心电图",
            "ecg",
            "diagnos",
            "qt",
            "qrs",
            "brugada",
            "nsvt",
            "sqts",
            "lqts",
            "cpvt",
            "ventricular fibrillation",
            "non-sustained",
        ],
    },
    "follow_up": {
        "entityType": "FollowUp",
        "suffix": "随访与复查方案",
        "aliases": ["随访", "复查", "监测", "管理", "评估", "follow-up", "monitoring", "evaluation"],
        "desired_pathways": {"follow_up", "exam", "risk_stratification", "clinical_knowledge"},
        "keywords": ["随访", "复查", "监测", "管理", "评估", "follow-up", "monitor", "evaluation", "evaluat"],
    },
    "sign": {
        "entityType": "Sign",
        "suffix": "相关临床体征",
        "aliases": ["体征", "临床表现", "恶性心律失常", "心律失常", "cardiac arrest", "arrhythmia"],
        "desired_pathways": {"symptom_sign", "clinical_knowledge", "prognosis"},
        "keywords": ["体征", "临床表现", "恶性心律失常", "心律失常", "cardiac arrest", "syncope", "arrhythmia", "vt/vf"],
    },
    "prognosis": {
        "entityType": "Prognosis",
        "suffix": "预后与猝死风险",
        "aliases": ["预后", "死亡", "猝死", "风险", "sudden death", "SCD", "mortality", "survival"],
        "desired_pathways": {"prognosis", "risk_stratification", "clinical_knowledge", "treatment_plan"},
        "keywords": ["预后", "死亡", "猝死", "风险", "sudden death", "scd", "mortality", "survival", "cardiac arrest", "vt/vf"],
    },
}


CURATED_EVIDENCE_RULES = {
    ("DIS-CARD-ARR-BRUGADA", "diagnosis_criteria"): {
        "source_contains": ["室性心律失常中国专家共识基层版.pdf"],
        "include_all": ["Brugada", "可诊断为", "ST"],
        "include_any": ["Ⅰ型", "I型", "钠通道阻滞剂"],
    },
    ("DIS-CARD-ARR-CPVT", "diagnosis_criteria"): {
        "source_contains": ["室性心律失常中国专家共识基层版.pdf"],
        "include_all": ["可诊断为CPVT", "年龄<40", "双向性室速"],
        "include_any": ["多形性室速", "RYR2", "CASQ2"],
    },
    ("DIS-CARD-ARR-LQTS", "diagnosis_criteria"): {
        "source_contains": ["内科学"],
        "include_all": ["长QT", "QT"],
        "include_any": ["QTc", "QT 间期延长", "QT间期延长", "晕厥"],
    },
    ("DIS-CARD-ARR-LQTS", "follow_up"): {
        "source_contains": ["室性心律失常中国专家共识基层版.pdf", "内科学"],
        "include_all": ["LQTS", "QT"],
        "include_any": ["避免使用延长QT", "纠正低钾血症", "低镁血症", "严密监测"],
    },
    ("DIS-CARD-ARR-NSVT", "diagnosis_criteria"): {
        "source_contains": ["室性心律失常中国专家共识基层版.pdf"],
        "include_all": ["非持续性室速", "<30 s"],
        "include_any": ["自行终止", "NSVT"],
    },
    ("DIS-CARD-ARR-NSVT", "follow_up"): {
        "source_contains": ["室性心律失常中国专家共识基层版.pdf"],
        "include_all": ["NSVT"],
        "include_any": ["超声心动图", "磁共振", "运动试验", "评价有无结构性心脏病"],
    },
    ("DIS-CARD-ARR-SQTS", "diagnosis_criteria"): {
        "source_contains": ["室性心律失常中国专家共识基层版.pdf", "ESC指南"],
        "include_all": ["SQTS", "QTc"],
        "include_any": ["诊断标准", "diagnosed", "≤340", "≤360"],
    },
    ("DIS-CARD-ARR-SQTS", "sign"): {
        "source_contains": ["室性心律失常中国专家共识基层版.pdf", "内科学"],
        "include_all": ["SQTS"],
        "include_any": ["临床表现", "SCD", "心悸", "心房颤动", "晕厥"],
    },
    ("DIS-CARD-ARR-SQTS", "prognosis"): {
        "source_contains": ["室性心律失常中国专家共识基层版.pdf", "ESC指南"],
        "include_all": ["SQTS"],
        "include_any": ["SCD", "室颤", "猝死", "ICD", "risk"],
    },
    ("DIS-CARD-ARR-TDP", "diagnosis_criteria"): {
        "source_contains": ["内科学", "室性心律失常中国专家共识基层版.pdf"],
        "include_all": ["尖端扭转"],
        "include_any": ["QT间期", "QT 间期", "torsades", "QRS波"],
    },
    ("DIS-CARD-ARR-VA", "diagnosis_criteria"): {
        "source_contains": ["室性心律失常中国专家共识基层版.pdf"],
        "include_all": ["室性心律失常"],
        "include_any": ["临床表现与诊断", "诊断主要依据", "心电图", "动态心电图"],
    },
    ("DIS-CARD-ARR-VF", "diagnosis_criteria"): {
        "source_contains": ["内科学"],
        "include_all": ["室扑", "室颤", "心电图特征"],
        "include_any": ["频率", "QRS", "波形"],
    },
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")


def stable_code(prefix: str, disease_code: str, pathway: str) -> str:
    digest = hashlib.sha1(f"{disease_code}|{pathway}".encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-CARD-REQ-{digest}"


def load_disease_aliases(batch_dir: Path) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for row in read_csv(batch_dir / "00_scope_and_config" / "controlled_vocabulary.csv"):
        if row.get("entityType") != "Disease":
            continue
        code = row.get("disease_scope", "")
        names = [row.get("canonical_name", ""), row.get("name_en", ""), row.get("abbr", "")]
        names.extend(item.strip() for item in row.get("aliases", "").split(","))
        aliases[code] = [item for item in names if item]
    return aliases


def evidence_score(row: dict[str, Any], rule: dict[str, Any], aliases: list[str]) -> int:
    text = str(row.get("evidence_text") or "")
    lower = text.lower()
    score = 0
    source_name = str(row.get("source_name") or "")
    if "内科学" in source_name:
        score -= 120
    if "专家共识" in source_name:
        score += 80
    if "ESC" in source_name.upper():
        score += 65
    page = row.get("source_page")
    try:
        page_number = int(page)
    except Exception:
        page_number = 999
    if page_number <= 7:
        score -= 80
    if row.get("pathway_element") in rule["desired_pathways"]:
        score += 60
    for keyword in rule["keywords"]:
        if keyword.lower() in lower:
            score += 25
    for alias in aliases:
        if not alias:
            continue
        if alias.isascii() and len(alias) <= 12:
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, re.IGNORECASE):
                score += 18
        elif alias.lower() in lower:
            score += 18
    if row.get("recommendation_class") not in (None, "", "N/A"):
        score += 10
    if len(text) < 20:
        score -= 40
    if re.search(r"AAD, anti-arrhythmic drug|ACE-Is, angiotensin|Abbreviations and acronyms", text, re.I):
        score -= 260
    return score


def curated_rule_score(row: dict[str, Any], rule: dict[str, Any]) -> int:
    text = str(row.get("evidence_text") or "")
    source_name = str(row.get("source_name") or "")
    normalized_text = re.sub(r"\s+", "", text).lower()
    source_ok = any(item in source_name for item in rule.get("source_contains", []))
    if not source_ok:
        return -10_000
    if re.search(r"AAD, anti-arrhythmic drug|ACE-Is, angiotensin|Abbreviations and acronyms", text, re.I):
        return -10_000
    score = 100
    for item in rule.get("include_all", []):
        item_norm = re.sub(r"\s+", "", str(item)).lower()
        if item_norm not in normalized_text:
            return -10_000
        score += 40
    any_hits = 0
    for item in rule.get("include_any", []):
        item_norm = re.sub(r"\s+", "", str(item)).lower()
        if item_norm in normalized_text:
            any_hits += 1
            score += 30
    if rule.get("include_any") and any_hits == 0:
        return -10_000
    if "专家共识" in source_name:
        score += 35
    if "ESC" in source_name.upper():
        score += 25
    if "内科学" in source_name:
        score += 10
    if row.get("pathway_element") in {"diagnosis_criteria", "follow_up", "prognosis", "symptom_sign"}:
        score += 20
    page = row.get("source_page")
    try:
        page_number = int(page)
    except Exception:
        page_number = 999
    if page_number <= 7:
        score -= 25
    return score


def best_curated_evidence(
    evidence_rows: list[dict[str, Any]],
    disease_code: str,
    pathway: str,
) -> dict[str, Any] | None:
    rule = CURATED_EVIDENCE_RULES.get((disease_code, pathway))
    if not rule:
        return None
    candidates = [row for row in evidence_rows if row.get("disease_code") == disease_code]
    ranked = sorted(
        ((curated_rule_score(row, rule), row) for row in candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] <= 0:
        return None
    return ranked[0][1]


def best_evidence(
    evidence_rows: list[dict[str, Any]],
    disease_code: str,
    pathway: str,
    rule: dict[str, Any],
    aliases: list[str],
) -> dict[str, Any]:
    curated = best_curated_evidence(evidence_rows, disease_code, pathway)
    if curated:
        return curated
    candidates = [row for row in evidence_rows if row.get("disease_code") == disease_code]
    ranked = sorted(
        ((evidence_score(row, rule, aliases), row) for row in candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] <= 0:
        raise ValueError(f"No usable evidence for {disease_code} / {pathway} / {rule['entityType']}")
    return ranked[0][1]


def provenance_from_evidence(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": row.get("document_id"),
        "segment_id": row.get("segment_id"),
        "source_name": row.get("source_name"),
        "source_type": row.get("source_type"),
        "source_version": row.get("source_version", "N/A"),
        "source_section": row.get("source_section", "N/A"),
        "source_page": row.get("source_page", "N/A"),
        "disease_code": row.get("disease_code", ""),
        "disease_name": row.get("disease_name", ""),
        "evidence_text": row.get("evidence_text"),
        "recommendation_class": row.get("recommendation_class", "N/A"),
        "evidence_level": row.get("evidence_level", "N/A"),
        "evidence_id": row.get("evidence_id"),
    }


def build_spec(batch_dir: Path) -> dict[str, Any]:
    batch_dir = Path(batch_dir).resolve()
    config = json.loads((batch_dir / "00_scope_and_config" / "batch_config.json").read_text(encoding="utf-8-sig"))
    missing = [
        row
        for row in read_csv(batch_dir / "06_quality_audit" / "missing_reason_and_solution.csv")
        if row.get("applicability_status") == "required"
    ]
    evidence_rows = read_jsonl(batch_dir / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl")
    disease_aliases = load_disease_aliases(batch_dir)

    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for row in missing:
        pathway = row["pathway_element"]
        if pathway not in BACKFILL_RULES:
            continue
        rule = BACKFILL_RULES[pathway]
        disease_code = row["disease_code"]
        disease_name = row["disease_name"]
        entity_type = rule["entityType"]
        entity_category, relation_type, prefix = ENTITY_META[entity_type]
        aliases = sorted(set(rule["aliases"] + disease_aliases.get(disease_code, [])))
        node_code = stable_code(prefix, disease_code, pathway)
        node_name = f"{disease_name}{rule['suffix']}"
        evidence = best_evidence(evidence_rows, disease_code, pathway, rule, disease_aliases.get(disease_code, []))
        provenance = provenance_from_evidence(evidence)
        nodes.append(
            {
                "code": node_code,
                "name": node_name,
                "entityType": entity_type,
                "entityCategory": entity_category,
                "aliases": aliases,
                "description": f"{node_name}，由本批次教材/指南/共识证据定向回填，用于补齐required临床闭环路径。",
                "backfill_reason": f"required_pathway_missing:{pathway}",
                "curation_note": "优先使用本批次指南/共识证据；仅在教材证据更具体时使用教材专病段落，禁止使用教材泛命中段落。",
            }
        )
        relations.append(
            {
                "source_code": disease_code,
                "relationType": relation_type,
                "target_code": node_code,
                "provenance_records_json": [provenance],
                "document_id": provenance.get("document_id"),
                "segment_id": provenance.get("segment_id"),
                "source_name": provenance.get("source_name"),
                "source_type": provenance.get("source_type"),
                "source_version": provenance.get("source_version"),
                "source_section": provenance.get("source_section"),
                "source_page": provenance.get("source_page"),
                "evidence_text": provenance.get("evidence_text"),
                "guideline_id": f"SRC-{provenance.get('document_id')}",
                "evidence_id": provenance.get("evidence_id"),
                "recommendation_class": provenance.get("recommendation_class") or "N/A",
                "evidence_level": provenance.get("evidence_level") or "N/A",
                "confidence": 0.88,
                "clinical_rule_or_clinical_pathway": node_name,
                "applicable_population": f"{disease_name}相关患者，具体适用条件以证据原文和临床判断为准。",
                "exclusion_criteria": "急性血流动力学不稳定、需立即复苏/电复律/除颤等抢救场景，或证据原文明确不适用/禁忌的患者，不按该常规路径处理。",
                "backfill_reason": f"required_pathway_missing:{pathway}",
            }
        )
        selected.append(
            {
                "disease_code": disease_code,
                "disease_name": disease_name,
                "pathway_element": pathway,
                "target_node": node_name,
                "source_name": evidence.get("source_name"),
                "source_page": evidence.get("source_page"),
                "pathway_detected": evidence.get("pathway_element"),
                "evidence_text": evidence.get("evidence_text"),
            }
        )

    spec = {
        "id": "VA_SCD_REQUIRED_BACKFILL_20260704",
        "batches": [
            {
                "batch_dir": str(batch_dir),
                "batch_id": config.get("batch_id", batch_dir.name),
                "schema_version": config.get("schema_version", "V1.7"),
                "scope_type": config.get("scope_type", "disease"),
                "scope_target": config.get("scope_target", "室性心律失常及心脏性猝死"),
                "nodes": nodes,
                "relations": relations,
            }
        ],
        "selected_evidence": selected,
    }
    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Build required-pathway backfill spec for VA/SCD batch.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    args = parser.parse_args()
    spec = build_spec(args.batch_dir)
    write_json(args.out_json, spec)
    print(json.dumps({"spec": str(args.out_json), "nodes": len(spec["batches"][0]["nodes"]), "relations": len(spec["batches"][0]["relations"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
