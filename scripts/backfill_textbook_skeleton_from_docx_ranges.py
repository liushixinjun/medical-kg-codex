from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_textbook_skeleton_structured_candidates import (  # noqa: E402
    REL_TYPE_BY_NODE_TYPE,
    build_term_index,
    extract_definition_components,
    extract_list_like_components,
    is_false_treatment,
    match_terms,
    stable_id,
    write_jsonl,
)


GROUP_TO_NODE_TYPES = {
    "definition": ["Definition", "DefinitionComponent"],
    "etiology_pathogenesis": ["Etiology", "RiskFactor", "Pathophysiology"],
    "clinical_manifestation": ["Symptom", "Sign"],
    "exam_lab": ["Exam", "LabTest"],
    "diagnosis_differential": ["DiagnosisCriteriaComponent", "DifferentialDiagnosis", "Exam", "LabTest"],
    "treatment": ["TreatmentPlan", "Medication", "Procedure"],
    "prognosis_followup": ["Prognosis", "FollowUp", "Complication", "Prevention"],
}


def read_docx_paras(docx_path: Path) -> List[str]:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    paras = []
    for p in root.findall(".//w:body/w:p", ns):
        txt = "".join((t.text or "") for t in p.findall(".//w:t", ns)).strip()
        paras.append("".join(txt.split()))
    return paras


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def clean(text: str, limit: int = 180) -> str:
    return re.sub(r"\s+", "", text or "")[:limit]


def infer_missing_group_candidates(group: str, text: str, subject_name: str) -> list[dict]:
    text = clean(text, 5000)
    out = []
    if group == "definition":
        comps = extract_definition_components(text)
        if comps:
            out.append(
                {
                    "node_type": "Definition",
                    "canonical_name": f"{subject_name}定义",
                    "matched_text": "definition_text",
                    "confidence": "docx_range_definition_backfill",
                    "fragment": clean(text, 220),
                }
            )
        for comp in comps:
            out.append(
                {
                    "node_type": "DefinitionComponent",
                    "canonical_name": comp,
                    "matched_text": comp,
                    "confidence": "docx_range_definition_component",
                    "fragment": comp,
                }
            )
    elif group == "diagnosis_differential":
        for item in extract_list_like_components(text, 30):
            if any(k in item for k in ["诊断", "确诊", "可直接确立", "心电图", "ST段", "造影", "激发试验", "鉴别", "不同", "排除"]):
                node_type = "DifferentialDiagnosis" if any(k in item for k in ["鉴别", "不同", "排除"]) else "DiagnosisCriteriaComponent"
                out.append(
                    {
                        "node_type": node_type,
                        "canonical_name": item[:80],
                        "matched_text": item[:80],
                        "confidence": "docx_range_diagnosis_backfill",
                        "fragment": item[:160],
                    }
                )
    elif group == "treatment":
        if is_false_treatment(text[:160]):
            return out
        for item in extract_list_like_components(text, 30):
            if any(k in item for k in ["治疗", "药物", "手段", "使用", "不能单独用于", "戒烟", "戒酒", "介入", "消融", "起搏", "电复律", "除颤"]):
                out.append(
                    {
                        "node_type": "TreatmentPlan",
                        "canonical_name": item[:80],
                        "matched_text": item[:80],
                        "confidence": "docx_range_treatment_backfill",
                        "fragment": item[:160],
                    }
                )
    elif group in {"etiology_pathogenesis", "prognosis_followup"}:
        node_type = "Pathophysiology" if group == "etiology_pathogenesis" else "Prognosis"
        for item in extract_list_like_components(text, 20):
            if len(item) >= 8:
                out.append(
                    {
                        "node_type": node_type,
                        "canonical_name": item[:80],
                        "matched_text": item[:80],
                        "confidence": f"docx_range_{group}_backfill",
                        "fragment": item[:160],
                    }
                )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill structured candidates from original DOCX ranges.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--docx", required=True, type=Path)
    parser.add_argument("--dict-dir", required=True, type=Path)
    parser.add_argument("--batch-id", default="CARD-SKELETON-20260709")
    args = parser.parse_args()

    paras = read_docx_paras(args.docx)
    backfill_rows = load_csv(args.out_dir / "阶段C2_下一步补槽位优先清单_20260709.csv")
    chapter_rows = load_csv(args.out_dir / "心血管内科教材章节目录_20260709.csv")
    chapter_by_name = {r["名称"]: r for r in chapter_rows}
    terms = build_term_index(args.dict_dir)

    nodes_by_key: Dict[tuple, dict] = {}
    rels_by_key: Dict[tuple, dict] = {}
    links = []
    audit = []

    for row in backfill_rows:
        subject = row["对象"]
        parent = row["父级"]
        chapter = chapter_by_name.get(subject)
        if not chapter:
            audit.append({**row, "backfill_status": "chapter_range_not_found", "candidate_count": 0})
            continue
        start = int(chapter["docx_start_para"])
        end = int(chapter["docx_end_para"])
        text = "".join(paras[start + 1 : min(end + 1, len(paras))])
        subject_id = stable_id(f"{args.batch_id}-SUBJECT", parent, subject)
        missing = [g for g in row["缺失组"].split("；") if g]
        candidates = []
        for group in missing:
            allowed = GROUP_TO_NODE_TYPES.get(group, [])
            # First dictionary-based extraction across the whole original section.
            if allowed:
                candidates.extend(match_terms(text, terms, allowed))
            # Then conservative rule-based candidates for groups dictionaries cannot cover.
            candidates.extend(infer_missing_group_candidates(group, text, subject))

        seen = set()
        cleaned = []
        for cand in candidates:
            node_type = cand["node_type"]
            name = clean(cand["canonical_name"], 120)
            if not name or len(name) < 2:
                continue
            key = (node_type, name, cand.get("standard_code", ""))
            if key in seen:
                continue
            seen.add(key)
            cand["canonical_name"] = name
            cleaned.append(cand)

        for cand in cleaned:
            node_type = cand["node_type"]
            name = cand["canonical_name"]
            node_id = stable_id(f"{args.batch_id}-{node_type.upper()}", node_type, name, cand.get("standard_code", ""))
            node_key = (node_type, name, cand.get("standard_code", ""))
            if node_key not in nodes_by_key:
                nodes_by_key[node_key] = {
                    "node_id": node_id,
                    "node_type": node_type,
                    "name": name,
                    "standard_code": cand.get("standard_code", ""),
                    "source_layer": "textbook_skeleton_docx_range_backfill",
                    "batch_id": args.batch_id,
                    "clinical_use_status": "not_for_formal_cdss_until_reviewed",
                    "import_status": "local_candidate_not_imported",
                }
            rel_type = REL_TYPE_BY_NODE_TYPE.get(node_type, f"HAS_{node_type.upper()}")
            rel_key = (subject_id, node_id, rel_type)
            if rel_key not in rels_by_key:
                rels_by_key[rel_key] = {
                    "rel_id": stable_id(f"{args.batch_id}-REL-BACKFILL", *rel_key),
                    "source_id": subject_id,
                    "source_name": subject,
                    "target_id": node_id,
                    "target_name": name,
                    "target_type": node_type,
                    "rel_type": rel_type,
                    "batch_id": args.batch_id,
                    "evidence_ids": [],
                    "confidence": cand.get("confidence", "docx_range_backfill"),
                    "import_status": "local_candidate_not_imported",
                }
            evidence_id = stable_id(f"{args.batch_id}-EVID-BACKFILL", subject, node_type, name, str(start), str(end))
            rels_by_key[rel_key]["evidence_ids"].append(evidence_id)
            links.append(
                {
                    "evidence_id": evidence_id,
                    "node_id": node_id,
                    "node_type": node_type,
                    "node_name": name,
                    "matched_text": cand.get("matched_text", ""),
                    "fragment": cand.get("fragment") or clean(text, 180),
                    "source_section_path": f"{parent} > {subject}",
                    "docx_para_start": start,
                    "docx_para_end": end,
                    "pdf_page_approx": row.get("页码", ""),
                    "confidence": cand.get("confidence", "docx_range_backfill"),
                }
            )
        audit.append({**row, "backfill_status": "ok" if cleaned else "no_backfill_candidate", "candidate_count": len(cleaned)})

    for rel in rels_by_key.values():
        rel["evidence_ids"] = list(dict.fromkeys(rel["evidence_ids"]))

    nodes = list(nodes_by_key.values())
    rels = list(rels_by_key.values())
    write_jsonl(args.out_dir / "阶段C3_缺口定向补抽_nodes_20260709.jsonl", nodes)
    write_jsonl(args.out_dir / "阶段C3_缺口定向补抽_relations_20260709.jsonl", rels)
    write_jsonl(args.out_dir / "阶段C3_缺口定向补抽_evidence_links_20260709.jsonl", links)
    write_csv(args.out_dir / "阶段C3_缺口定向补抽审计_20260709.csv", audit)

    # Merged C2 + C3 files for re-audit.
    c2_nodes = load_jsonl(args.out_dir / "阶段C2_结构化候选_nodes_20260709.jsonl")
    c2_rels = load_jsonl(args.out_dir / "阶段C2_结构化候选_relations_20260709.jsonl")
    merged_nodes = {n["node_id"]: n for n in c2_nodes}
    for n in nodes:
        merged_nodes.setdefault(n["node_id"], n)
    merged_rels = {r["rel_id"]: r for r in c2_rels}
    for r in rels:
        merged_rels.setdefault(r["rel_id"], r)
    write_jsonl(args.out_dir / "阶段C3_合并结构化候选_nodes_20260709.jsonl", list(merged_nodes.values()))
    write_jsonl(args.out_dir / "阶段C3_合并结构化候选_relations_20260709.jsonl", list(merged_rels.values()))

    summary = {
        "batch_id": args.batch_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "backfill_subject_count": len(backfill_rows),
        "backfill_node_count": len(nodes),
        "backfill_relation_count": len(rels),
        "backfill_evidence_link_count": len(links),
        "merged_node_count": len(merged_nodes),
        "merged_relation_count": len(merged_rels),
        "not_imported_to_neo4j": True,
    }
    (args.out_dir / "阶段C3_缺口定向补抽_summary_20260709.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
