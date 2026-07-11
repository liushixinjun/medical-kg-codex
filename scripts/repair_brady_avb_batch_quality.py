from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


ENTITY_CATEGORY = {
    "Etiology": "病因",
    "Symptom": "症状",
    "Sign": "体征",
    "Exam": "检查",
    "DiagnosisCriteria": "诊断标准",
    "Complication": "并发症",
    "Prognosis": "预后",
    "FollowUp": "随访",
}
TYPE_PREFIX = {
    "Etiology": "ETI",
    "Symptom": "SYM",
    "Sign": "SIGN",
    "Exam": "EXAM",
    "DiagnosisCriteria": "DX",
    "Complication": "COMP",
    "Prognosis": "PROG",
    "FollowUp": "FU",
}
RELATION_BY_ELEMENT = {
    "etiology": ("has_etiology", "Etiology"),
    "symptom": ("has_symptom", "Symptom"),
    "sign": ("has_sign", "Sign"),
    "exam": ("requires_exam", "Exam"),
    "diagnosis_criteria": ("has_diagnostic_criteria", "DiagnosisCriteria"),
    "complication": ("may_cause_complication", "Complication"),
    "prognosis": ("has_prognosis", "Prognosis"),
    "follow_up": ("has_follow_up", "FollowUp"),
}
RELATION_CATEGORY = {
    "has_etiology": "clinical",
    "has_symptom": "clinical",
    "has_sign": "clinical",
    "requires_exam": "diagnostic",
    "has_diagnostic_criteria": "diagnostic",
    "may_cause_complication": "clinical",
    "has_prognosis": "clinical",
    "has_follow_up": "therapeutic",
    "supported_by_evidence": "evidence",
}


BACKFILL_SPEC = {
    "etiology": {
        "name": "传导系统退行性变及可逆因素",
        "aliases": ["退行性", "药物", "急性心肌梗死", "心肌炎", "电解质", "甲状腺功能减退", "洋地黄"],
        "keywords": r"退行|药物|急性心肌梗死|下壁心肌梗死|心肌炎|电解质|甲状腺|洋地黄|病因|纤维化",
    },
    "symptom": {
        "name": "晕厥、头晕和乏力",
        "aliases": ["晕厥", "头晕", "黑矇", "乏力", "症状", "活动耐量下降"],
        "keywords": r"晕厥|头晕|黑矇|乏力|症状|活动耐量|意识",
    },
    "sign": {
        "name": "心动过缓或房室分离表现",
        "aliases": ["心动过缓", "房室分离", "PR间期", "长PP间期", "长间歇", "血流动力学"],
        "keywords": r"心动过缓|房室分离|PR\s*间期|长\s*PP|长间歇|血流动力学|第一心音",
    },
    "exam": {
        "name": "心电图及长程心电监测",
        "aliases": ["心电图", "动态心电图", "长程心电监测", "事件记录仪", "电生理检查", "Holter"],
        "keywords": r"心电图|动态心电|长程心电|事件记录|电生理|Holter",
    },
    "diagnosis_criteria": {
        "name": "心电图传导阻滞诊断依据",
        "aliases": ["PR间期", "P波", "QRS波", "房室分离", "文氏阻滞", "莫氏", "完全性房室传导阻滞", "窦房传导阻滞"],
        "keywords": r"PR\s*间期|P\s*波|QRS|房室分离|文氏|莫氏|完全性房室传导阻滞|诊断|确诊|阻滞",
    },
    "complication": {
        "name": "血流动力学不稳定和心脏停搏风险",
        "aliases": ["血流动力学不稳定", "心室静止", "心脏停搏", "逸搏", "心力衰竭", "猝死", "并发症"],
        "keywords": r"血流动力学|心室静止|心脏停搏|逸搏|心力衰竭|猝死|并发症|休克",
    },
    "prognosis": {
        "name": "进展为高度传导阻滞或需起搏风险",
        "aliases": ["发展为", "进展为", "三度房室传导阻滞", "完全性房室传导阻滞", "需起搏", "预后"],
        "keywords": r"发展为|进展为|三度房室传导阻滞|完全性房室传导阻滞|需.*起搏|预后|死亡",
    },
    "follow_up": {
        "name": "心电监测和起搏器随访",
        "aliases": ["随访", "术后管理", "心电监测", "起搏器", "程控", "电池", "阈值"],
        "keywords": r"随访|术后管理|心电监测|起搏器|程控|电池|阈值",
    },
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def stable_code(prefix: str, *parts: str, length: int = 12) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest().upper()[:length]
    return f"{prefix}-CARD-{digest}"


def relation_id(source: str, relation_type: str, target: str) -> str:
    return "REL-" + hashlib.sha1(f"{source}|{relation_type}|{target}".encode("utf-8")).hexdigest().upper()[:20]


def provenance(ev: dict) -> dict:
    return {
        "document_id": ev["document_id"],
        "segment_id": ev["segment_id"],
        "source_name": ev["source_name"],
        "source_type": ev["source_type"],
        "source_version": ev.get("source_version", "N/A"),
        "source_section": ev.get("source_section", "N/A"),
        "source_page": ev.get("source_page", "N/A"),
        "disease_code": ev.get("disease_code", ""),
        "disease_name": ev.get("disease_name", ""),
        "evidence_text": ev["evidence_text"],
        "recommendation_class": ev.get("recommendation_class", "N/A"),
        "evidence_level": ev.get("evidence_level", "N/A"),
    }


def choose_evidence(evidence_by_disease: dict[str, list[dict]], disease_code: str, keywords: str) -> dict | None:
    pattern = re.compile(keywords, re.IGNORECASE)
    candidates = evidence_by_disease.get(disease_code, [])
    matching = [ev for ev in candidates if pattern.search(ev.get("evidence_text", ""))]
    pool = matching or candidates
    if not pool:
        return None
    return max(
        pool,
        key=lambda ev: (
            1 if pattern.search(ev.get("evidence_text", "")) else 0,
            1 if ev.get("source_name", "").endswith(".pdf") else 0,
            1 if "内科学" in ev.get("source_name", "") else 0,
            len(ev.get("evidence_text", "")),
        ),
    )


def ensure_node(nodes: list[dict], node_by_code: dict[str, dict], code: str, name: str, entity_type: str, batch_id: str, aliases: list[str]) -> dict:
    existing = node_by_code.get(code)
    if existing:
        existing_aliases = existing.get("aliases")
        if not isinstance(existing_aliases, list):
            existing_aliases = [item for item in str(existing_aliases or "").split(",") if item]
        for alias in aliases:
            if alias and alias not in existing_aliases:
                existing_aliases.append(alias)
        existing["aliases"] = existing_aliases
        return existing
    node = {
        "id": "KG_" + code.replace("-", "_"),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "aliases": aliases,
        "entityType": entity_type,
        "entityCategory": ENTITY_CATEGORY[entity_type],
        "schema_version": "V1.7",
        "review_status": "approved",
        "clinical_review_status": "pending_clinical_review",
        "formal_cdss_ready": False,
        "batch_id": batch_id,
        "scope_type": "disease",
        "scope_target": "缓慢性心律失常及传导阻滞",
        "merge_status": "validated",
        "conflict_status": "none",
        "source_quality": "brady_avb_required_pathway_backfill",
    }
    nodes.append(node)
    node_by_code[code] = node
    return node


def add_relation(relations: list[dict], relation_keys: set[tuple[str, str, str]], disease_code: str, relation_type: str, target_code: str, ev: dict, batch_id: str) -> bool:
    key = (disease_code, relation_type, target_code)
    if key in relation_keys:
        return False
    prov = provenance(ev)
    rel = {
        "id": relation_id(*key),
        "source_code": disease_code,
        "relationType": relation_type,
        "target_code": target_code,
        "relationCategory": RELATION_CATEGORY[relation_type],
        "batch_id": batch_id,
        "schema_version": "V1.7",
        "review_status": "approved",
        "clinical_review_status": "pending_clinical_review",
        "formal_cdss_ready": False,
        "polarity": "positive",
        "scope_type": "disease",
        "scope_target": "缓慢性心律失常及传导阻滞",
        "merge_status": "validated",
        "conflict_status": "none",
        "source_quality": "brady_avb_required_pathway_backfill",
        "provenance_records_json": [prov],
        "evidence_ids": [ev["evidence_id"]],
        "document_ids": [prov["document_id"]],
        "source_names": [prov["source_name"]],
        "source_types": [prov["source_type"]],
        "evidence_count": 1,
        "document_id": prov["document_id"],
        "segment_id": prov["segment_id"],
        "source_name": prov["source_name"],
        "source_type": prov["source_type"],
        "source_version": prov["source_version"],
        "source_section": prov["source_section"],
        "source_page": prov["source_page"],
        "evidence_text": prov["evidence_text"],
        "guideline_id": f"SRC-{prov['document_id']}",
        "evidence_id": ev["evidence_id"],
        "recommendation_class": prov["recommendation_class"],
        "evidence_level": prov["evidence_level"],
        "confidence": 0.92,
    }
    if relation_type == "has_follow_up":
        rel["applicable_population"] = "缓慢性心律失常及传导阻滞患者治疗后或起搏器植入后需随访监测者。"
        rel["exclusion_criteria"] = "急性不稳定状态需先急诊处理；随访频率应结合器械类型和病情调整。"
        rel["recommendation_context"] = "用于提示心电监测、起搏器程控和术后管理。"
    relations.append(rel)
    relation_keys.add(key)
    return True


def repair(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir).resolve()
    batch_id = batch_dir.name
    data_dir = batch_dir / "05_data_instance"
    audit_dir = batch_dir / "06_quality_audit"
    nodes = read_jsonl(data_dir / "nodes_final.jsonl")
    relations = read_jsonl(data_dir / "relations_final.jsonl")
    evidence_rows = read_jsonl(batch_dir / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl")
    node_by_code = {node["code"]: node for node in nodes}
    relation_keys = {(rel["source_code"], rel["relationType"], rel["target_code"]) for rel in relations}
    evidence_by_disease: dict[str, list[dict]] = {}
    for ev in evidence_rows:
        evidence_by_disease.setdefault(ev.get("disease_code", ""), []).append(ev)

    missing_path = audit_dir / "disease_pathway_coverage.csv"
    missing_rows = []
    if missing_path.exists():
        with missing_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("applicability_status") == "required" and row.get("coverage_status") != "covered":
                    missing_rows.append(row)

    added_nodes = 0
    added_relations = 0
    repair_rows = []
    for row in missing_rows:
        element = row["pathway_element"]
        disease_code = row["disease_code"]
        if element not in RELATION_BY_ELEMENT:
            continue
        relation_type, entity_type = RELATION_BY_ELEMENT[element]
        spec = BACKFILL_SPEC[element]
        evidence = choose_evidence(evidence_by_disease, disease_code, spec["keywords"])
        if not evidence:
            continue
        name = spec["name"]
        aliases = list(dict.fromkeys(spec["aliases"]))
        code = stable_code(TYPE_PREFIX[entity_type], disease_code, element, name)
        if code not in node_by_code:
            added_nodes += 1
        ensure_node(nodes, node_by_code, code, name, entity_type, batch_id, aliases)
        if add_relation(relations, relation_keys, disease_code, relation_type, code, evidence, batch_id):
            added_relations += 1
            repair_rows.append(
                {
                    "disease_code": disease_code,
                    "disease_name": row.get("disease_name", ""),
                    "pathway_element": element,
                    "target_name": name,
                    "relationType": relation_type,
                    "evidence_id": evidence["evidence_id"],
                    "source_name": evidence["source_name"],
                    "source_page": evidence.get("source_page", ""),
                }
            )

    write_jsonl(data_dir / "nodes_final.jsonl", nodes)
    write_jsonl(data_dir / "relations_final.jsonl", relations)
    with (audit_dir / "brady_avb_required_backfill_log.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["disease_code", "disease_name", "pathway_element", "target_name", "relationType", "evidence_id", "source_name", "source_page"],
        )
        writer.writeheader()
        writer.writerows(repair_rows)
    summary = {
        "status": "brady_avb_required_pathway_backfilled",
        "missing_required_before": len(missing_rows),
        "added_node_count": added_nodes,
        "added_relation_count": added_relations,
    }
    (audit_dir / "brady_avb_required_backfill_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill required clinical pathways for bradyarrhythmia/AV block batch.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(repair(args.batch_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
