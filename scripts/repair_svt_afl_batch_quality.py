from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.repair_graph_semantic_quality import stable_code, write_jsonl


SVT_CONSENSUS_SOURCE = {
    "document_id": "DOC-04A6231207D5F4D6",
    "source_name": "室上性心动过速诊断及治疗中国专家共识(2021).pdf",
    "source_type": "consensus",
    "source_version": "2021",
}


REQUIRED_ETIOLOGY_REPAIRS = {
    "DIS-CARD-ARR-SVT": {
        "disease_name": "室上性心动过速",
        "node_name": "室上性心动过速发病机制",
        "aliases": ["室上速发病机制", "室上速机制", "希氏束或以上组织参与", "希氏束以上组织参与"],
        "segment_id": "SEG-DOC-04A6231207D5F4D6-1-PAGE-0-2398",
        "source_page": 1,
        "evidence_text": (
            "室上速定义为于静息状态下，由希氏束或以上组织参与，除外心房颤动，"
            "引起心房率和/或心室率>100次/min的心动过速；室上速主要包括窦性心动过速、"
            "局灶性房性心动过速、大折返性房速、房室结折返性心动过速和房室折返性心动过速等。"
        ),
    },
    "DIS-CARD-ARR-AVNRT": {
        "disease_name": "房室结折返性心动过速",
        "node_name": "房室结双径路折返机制",
        "aliases": ["房室交界区不同径路间折返", "AVNRT折返机制", "慢径路", "快径路"],
        "segment_id": "SEG-DOC-04A6231207D5F4D6-2-PAGE-0-2671",
        "source_page": 2,
        "evidence_text": (
            "AVNRT是一种涉及房室交界区不同径路间的折返性心动过速；典型性折返径路"
            "前传支为慢径路、逆传支为快径路，不典型性折返径路前传支为快径路或慢径路、逆传支为慢径路。"
        ),
    },
    "DIS-CARD-ARR-AVRT": {
        "disease_name": "房室折返性心动过速",
        "node_name": "房室旁路介导折返机制",
        "aliases": ["房室旁路介导的折返性心动过速", "房室旁路介导", "顺向型AVRT", "逆向型AVRT"],
        "segment_id": "SEG-DOC-04A6231207D5F4D6-2-PAGE-0-2671",
        "source_page": 2,
        "evidence_text": (
            "AVRT由房室旁路介导的折返性心动过速；顺向型折返径路的前传支为"
            "房室结/希氏-浦肯野系统、逆传支为房室旁路，逆向型折返径路的前传支为房室或房束旁路。"
        ),
    },
    "DIS-CARD-ARR-AT": {
        "disease_name": "房性心动过速",
        "node_name": "心房局灶或局限区域折返机制",
        "aliases": ["局限区域折返性房性心动过速", "起源于心房某一局部区域", "局灶性房性心动过速", "房速机制"],
        "segment_id": "SEG-DOC-04A6231207D5F4D6-2-PAGE-0-2671",
        "source_page": 2,
        "evidence_text": (
            "房性心动过速属于室上速分类；局限区域折返性房性心动过速为起源于"
            "心房某一局部区域的折返性心律失常，局灶性房性心动过速亦属于室上速主要类型。"
        ),
    },
}


FALSE_AT_PATTERNS = re.compile(r"α1[-\s]*AT|alpha-?1|抗胰蛋白|抗凝血酶|APC-R|蛋白\s*C|蛋白\s*S", re.I)
FALSE_WPW_PATTERNS = re.compile(r"G-?6-?PD|葡萄糖\s*-?\s*6\s*-?\s*磷酸脱氢酶|红细胞酶病", re.I)


FALSE_CORE_RELATION_IDS = {
    # 短缩写或跨疾病段落造成的误配：这些关系不应挂到本批次疾病下。
    "REL-549B97F3B0A4C89F5754",  # WPW -> 窦性心动过速，来源为药物表格上下文
    "REL-087EE4993D6641CAC12A",  # AT -> RAAS/ATⅡ 心衰机制误命中
    "REL-9D1BAA6A3A9D308AE9D2",  # WPW -> 补体旁路误命中
    "REL-4F3A7F1934C563A717BC",  # WPW -> 甲亢，实为房颤病因段落
    "REL-CE5C443BF028207DA599",  # WPW -> 饮酒，实为房颤病因段落
    "REL-59164B1211A9B54DE78E",  # AT -> 心衰A期分期误命中
    "REL-A0EAAD6B996B94202331",  # SVT -> HCM猝死危险分层误命中
    "REL-1BCBB7BF1FA986435B42",  # WPW -> 普通心电图原则误作风险分层
    "REL-1AADFB2319B1A156050D",  # AFL -> 肺栓塞体征段落误作房扑体征
    "REL-95848FF94B98DFBFF178",  # SVT -> 肺栓塞体征段落误作室上速体征
    "REL-AE33FA7A08221C85A8AC",  # AFL -> 腺苷不良反应胸闷误作疾病症状
    "REL-0E771E3CF5E0DFBBECC7",  # WPW -> 腺苷不良反应胸闷误作疾病症状
    "REL-4D761846DE7A47DAE37D",  # WPW -> 房颤/甲亢段落误作WPW检验
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def kg_id_from_code(code: str) -> str:
    return "KG_" + code.replace("-", "_")


def evidence_node(record: dict, batch_id: str) -> dict:
    code = record["evidence_id"]
    name = f"{record['source_name']} 第{record['source_page']}页{record['disease_name']}证据（{record['segment_id']}）"
    return {
        "id": kg_id_from_code(code),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": "Evidence",
        "entityCategory": "证据",
        "schema_version": "V1.7",
        "review_status": "approved",
        "batch_id": batch_id,
        "scope_type": "disease",
        "scope_target": "室上性心动过速及心房扑动",
        "merge_status": "validated",
        "conflict_status": "none",
        "evidence_id": code,
        "document_id": record["document_id"],
        "segment_id": record["segment_id"],
        "source_name": record["source_name"],
        "source_type": record["source_type"],
        "source_section": record["source_section"],
        "source_page": record["source_page"],
        "disease_code": record["disease_code"],
        "disease_name": record["disease_name"],
        "evidence_text": record["evidence_text"],
        "language": "zh",
        "content_hash": stable_code("HASH", record["evidence_text"], record["disease_code"]),
        "clinical_review_status": "not_applicable",
        "formal_cdss_ready": False,
    }


def etiology_node(code: str, name: str, batch_id: str, aliases: list[str] | None = None) -> dict:
    return {
        "id": kg_id_from_code(code),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": "Etiology",
        "entityCategory": "临床",
        "schema_version": "V1.7",
        "review_status": "approved",
        "batch_id": batch_id,
        "scope_type": "disease",
        "scope_target": "室上性心动过速及心房扑动",
        "merge_status": "validated",
        "conflict_status": "none",
        "clinical_review_status": "pending_clinical_review",
        "formal_cdss_ready": False,
        "aliases": aliases or [],
        "source_quality": "manual_repair_from_included_consensus_after_audit",
        "description": f"{name}，来源于室上性心动过速诊断及治疗中国专家共识(2021)的分类和定义表。",
    }


def relation_to_evidence(source_code: str, evidence_code: str, batch_id: str) -> dict:
    return {
        "id": stable_code("REL-EVID", source_code, evidence_code, batch_id),
        "source_code": source_code,
        "relationType": "supported_by_evidence",
        "target_code": evidence_code,
        "relationCategory": "evidence",
        "batch_id": batch_id,
        "schema_version": "V1.7",
        "review_status": "approved",
        "polarity": "positive",
        "scope_type": "disease",
        "scope_target": "室上性心动过速及心房扑动",
        "merge_status": "validated",
        "conflict_status": "none",
        "clinical_review_status": "not_applicable",
        "formal_cdss_ready": False,
    }


def has_etiology_relation(disease_code: str, etiology_code: str, record: dict, batch_id: str) -> dict:
    return {
        "id": stable_code("REL-ETIOLOGY", disease_code, etiology_code, record["evidence_id"], batch_id),
        "source_code": disease_code,
        "relationType": "has_etiology",
        "target_code": etiology_code,
        "relationCategory": "clinical",
        "batch_id": batch_id,
        "schema_version": "V1.7",
        "review_status": "approved",
        "polarity": "positive",
        "scope_type": "disease",
        "scope_target": "室上性心动过速及心房扑动",
        "merge_status": "validated",
        "conflict_status": "none",
        "provenance_records_json": [record],
        "evidence_ids": [record["evidence_id"]],
        "document_ids": [record["document_id"]],
        "source_names": [record["source_name"]],
        "source_types": [record["source_type"]],
        "evidence_count": 1,
        "document_id": record["document_id"],
        "segment_id": record["segment_id"],
        "source_name": record["source_name"],
        "source_type": record["source_type"],
        "source_version": record["source_version"],
        "source_section": record["source_section"],
        "source_page": record["source_page"],
        "evidence_text": record["evidence_text"],
        "recommendation_class": "N/A",
        "evidence_level": "N/A",
        "guideline_id": "SRC-DOC-04A6231207D5F4D6",
        "evidence_id": record["evidence_id"],
        "confidence": 1.0,
        "clinical_review_status": "pending_clinical_review",
        "formal_cdss_ready": False,
    }


def is_false_at_record(text: str) -> bool:
    if re.search(r"房性心动过速|房速|atrial tachycardia|局灶性房性", text, re.I):
        return False
    return bool(FALSE_AT_PATTERNS.search(text))


def is_false_wpw_record(text: str) -> bool:
    if re.search(r"预激|WPW|Wolff", text, re.I):
        return False
    return bool(FALSE_WPW_PATTERNS.search(text))


def compact_relation_provenance(rel: dict) -> bool:
    records = rel.get("provenance_records_json")
    if not isinstance(records, list) or not records:
        return False
    disease_code = rel.get("source_code") or (records[0].get("disease_code") if isinstance(records[0], dict) else "")
    if disease_code not in {"DIS-CARD-ARR-AT", "DIS-CARD-ARR-WPW"}:
        return False
    kept = []
    removed = []
    for record in records:
        if not isinstance(record, dict):
            kept.append(record)
            continue
        text = str(record.get("evidence_text", ""))
        bad = is_false_at_record(text) if disease_code == "DIS-CARD-ARR-AT" else is_false_wpw_record(text)
        (removed if bad else kept).append(record)
    if not removed:
        return False
    rel["provenance_records_json"] = kept
    rel["evidence_ids"] = [r.get("evidence_id") for r in kept if isinstance(r, dict) and r.get("evidence_id")]
    rel["document_ids"] = sorted({r.get("document_id") for r in kept if isinstance(r, dict) and r.get("document_id")})
    rel["source_names"] = sorted({r.get("source_name") for r in kept if isinstance(r, dict) and r.get("source_name")})
    rel["source_types"] = sorted({r.get("source_type") for r in kept if isinstance(r, dict) and r.get("source_type")})
    rel["evidence_count"] = len(kept)
    if kept and isinstance(kept[0], dict):
        first = kept[0]
        for field in [
            "document_id",
            "segment_id",
            "source_name",
            "source_type",
            "source_version",
            "source_section",
            "source_page",
            "evidence_text",
            "recommendation_class",
            "evidence_level",
            "evidence_id",
        ]:
            rel[field] = first.get(field, rel.get(field))
    return True


def repair(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir)
    batch_id = batch_dir.name
    data_dir = batch_dir / "05_data_instance"
    audit_dir = batch_dir / "06_quality_audit"
    nodes_path = data_dir / "nodes_final.jsonl"
    relations_path = data_dir / "relations_final.jsonl"
    nodes = read_jsonl(nodes_path)
    relations = read_jsonl(relations_path)

    false_evidence_codes: set[str] = set()
    removed_relation_ids: set[str] = set()
    compacted_provenance = 0
    for rel in relations:
        if compact_relation_provenance(rel):
            compacted_provenance += 1
        if rel.get("source_code") == "DIS-CARD-ARR-AT":
            text = str(rel.get("evidence_text", ""))
            records = rel.get("provenance_records_json") or []
            texts = [text] + [str(r.get("evidence_text", "")) for r in records if isinstance(r, dict)]
            if any(is_false_at_record(t) for t in texts) and not any(
                re.search(r"房性心动过速|房速|atrial tachycardia|局灶性房性", t, re.I) for t in texts
            ):
                removed_relation_ids.add(rel.get("id"))
                false_evidence_codes.update(rel.get("evidence_ids") or [])
    for rel in relations:
        if rel.get("source_code") == "ETI-CARD-88303088C902":
            text = str(rel.get("evidence_text", ""))
            if is_false_at_record(text):
                removed_relation_ids.add(rel.get("id"))
                if rel.get("target_code"):
                    false_evidence_codes.add(rel["target_code"])
        if rel.get("source_code") == "ETI-CARD-D20FC6DDACD5":
            text = str(rel.get("evidence_text", ""))
            if is_false_wpw_record(text):
                removed_relation_ids.add(rel.get("id"))
                if rel.get("target_code"):
                    false_evidence_codes.add(rel["target_code"])

    removed_relation_ids.update(FALSE_CORE_RELATION_IDS)

    relations = [rel for rel in relations if rel.get("id") not in removed_relation_ids]

    normalized_docx_source_page = 0
    for rel in relations:
        if rel.get("source_page") in (None, "") and (
            str(rel.get("source_name", "")).lower().endswith(".docx")
            or rel.get("source_type") == "authoritative_textbook"
        ):
            rel["source_page"] = "N/A"
            normalized_docx_source_page += 1

    node_by_code = {node.get("code"): node for node in nodes}
    relation_keys = {(rel.get("source_code"), rel.get("relationType"), rel.get("target_code")) for rel in relations}
    added_nodes = 0
    added_relations = 0
    added_evidence_nodes = 0
    for disease_code, item in REQUIRED_ETIOLOGY_REPAIRS.items():
        evidence_code = stable_code("EVD", item["evidence_text"], disease_code)
        if disease_code.endswith("-SVT"):
            evidence_code = f"{evidence_code}-SVT"
        elif disease_code.endswith("-AVNRT"):
            evidence_code = f"{evidence_code}-AVNRT"
        elif disease_code.endswith("-AVRT"):
            evidence_code = f"{evidence_code}-AVRT"
        elif disease_code.endswith("-AT"):
            evidence_code = f"{evidence_code}-AT"
        record = {
            **SVT_CONSENSUS_SOURCE,
            "segment_id": item["segment_id"],
            "source_section": "etiology",
            "source_page": item["source_page"],
            "disease_code": disease_code,
            "disease_name": item["disease_name"],
            "evidence_text": item["evidence_text"],
            "recommendation_class": "N/A",
            "evidence_level": "N/A",
            "evidence_id": evidence_code,
        }
        etiology_code = stable_code("ETI-CARD", disease_code, item["node_name"])
        if etiology_code not in node_by_code:
            node = etiology_node(etiology_code, item["node_name"], batch_id, item.get("aliases") or [])
            nodes.append(node)
            node_by_code[etiology_code] = node
            added_nodes += 1
        else:
            existing_aliases = list(node_by_code[etiology_code].get("aliases") or [])
            for alias in item.get("aliases") or []:
                if alias not in existing_aliases:
                    existing_aliases.append(alias)
            node_by_code[etiology_code]["aliases"] = existing_aliases
        if evidence_code not in node_by_code:
            node = evidence_node(record, batch_id)
            nodes.append(node)
            node_by_code[evidence_code] = node
            added_evidence_nodes += 1
        else:
            display_name = f"{record['source_name']} 第{record['source_page']}页{record['disease_name']}证据（{record['segment_id']}）"
            for field in ("name", "preferred_name", "display_name"):
                node_by_code[evidence_code][field] = display_name
        key = (disease_code, "has_etiology", etiology_code)
        if key not in relation_keys:
            rel = has_etiology_relation(disease_code, etiology_code, record, batch_id)
            relations.append(rel)
            relation_keys.add(key)
            added_relations += 1
        key = (etiology_code, "supported_by_evidence", evidence_code)
        if key not in relation_keys:
            rel = relation_to_evidence(etiology_code, evidence_code, batch_id)
            relations.append(rel)
            relation_keys.add(key)
            added_relations += 1

    referenced_codes = {rel.get("source_code") for rel in relations} | {rel.get("target_code") for rel in relations}
    before_nodes = len(nodes)
    nodes = [
        node
        for node in nodes
        if not (
            node.get("code") in false_evidence_codes
            and node.get("entityType") == "Evidence"
            and node.get("code") not in referenced_codes
        )
    ]
    removed_evidence_nodes = before_nodes - len(nodes)
    before_nodes = len(nodes)
    nodes = [
        node
        for node in nodes
        if not (
            node.get("code") == "ETI-CARD-88303088C902"
            and node.get("entityType") == "Etiology"
            and node.get("code") not in referenced_codes
        )
    ]
    removed_orphan_false_etiology_nodes = before_nodes - len(nodes)

    write_jsonl(nodes_path, nodes)
    write_jsonl(relations_path, relations)
    summary = {
        "batch_dir": str(batch_dir),
        "compacted_false_provenance_relations": compacted_provenance,
        "removed_false_relation_count": len(removed_relation_ids),
        "normalized_docx_source_page_count": normalized_docx_source_page,
        "removed_false_evidence_node_count": removed_evidence_nodes,
        "removed_orphan_false_etiology_node_count": removed_orphan_false_etiology_nodes,
        "added_etiology_nodes": added_nodes,
        "added_evidence_nodes": added_evidence_nodes,
        "added_relations": added_relations,
    }
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "svt_afl_required_etiology_repair_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair SVT/AFL batch-specific etiology gaps and acronym false positives.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    repair(args.batch_dir)


if __name__ == "__main__":
    main()
