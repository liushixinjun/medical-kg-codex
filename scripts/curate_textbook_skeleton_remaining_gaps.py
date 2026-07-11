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

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_textbook_skeleton_structured_candidates import REL_TYPE_BY_NODE_TYPE, stable_id, write_jsonl  # noqa: E402


CURATED = {
    "第一节动脉粥样硬化": [
        ("TreatmentPlan", "动脉粥样硬化防治", 4926, 4942, "docx_curated_treatment"),
        ("TreatmentPlan", "积极控制危险因素", 4928, 4928, "docx_curated_treatment"),
        ("TreatmentPlan", "合理膳食", 4929, 4929, "docx_curated_treatment"),
        ("TreatmentPlan", "适当体力活动和运动", 4930, 4930, "docx_curated_treatment"),
        ("TreatmentPlan", "调整血脂治疗", 4933, 4934, "docx_curated_treatment"),
        ("TreatmentPlan", "抗血小板治疗", 4935, 4935, "docx_curated_treatment"),
        ("TreatmentPlan", "溶栓和抗凝治疗", 4936, 4941, "docx_curated_treatment"),
        ("Procedure", "血运重建", 4942, 4942, "docx_curated_procedure"),
    ],
    "四、心房颤动": [
        ("DiagnosisCriteriaComponent", "P波消失，代之以小而不规则的f波", 4424, 4424, "docx_curated_diagnostic_component"),
        ("DiagnosisCriteriaComponent", "心室率极不规则", 4424, 4424, "docx_curated_diagnostic_component"),
        ("DiagnosisCriteriaComponent", "QRS波形态通常正常，心室率过快时可增宽变形", 4424, 4424, "docx_curated_diagnostic_component"),
        ("Exam", "心电图", 4423, 4424, "docx_curated_exam"),
    ],
    "一、窦性心动过速": [
        ("DiagnosisCriteriaComponent", "成人窦性心律频率超过100次/分", 4322, 4322, "docx_curated_diagnostic_component"),
        ("Exam", "心电图", 4324, 4325, "docx_curated_exam"),
        ("DiagnosisCriteriaComponent", "Ⅱ导联P波正向，PR间期0.13秒，心率115次/分", 4325, 4325, "docx_curated_diagnostic_component"),
    ],
    "二、窦性心动过缓": [
        ("Exam", "心电图", 4330, 4331, "docx_curated_exam"),
        ("DiagnosisCriteriaComponent", "Ⅱ导联P波正向，PR间期0.18秒，心率48次/分", 4331, 4331, "docx_curated_diagnostic_component"),
    ],
    "四、窦房传导阻滞": [
        ("Sign", "逸搏心律", 4343, 4343, "docx_curated_clinical_manifestation"),
        ("Exam", "心电图", 4343, 4346, "docx_curated_exam"),
        ("DiagnosisCriteriaComponent", "二度Ⅰ型窦房传导阻滞表现为PP间期进行性缩短直至出现一次长PP间期", 4343, 4346, "docx_curated_diagnostic_component"),
        ("DiagnosisCriteriaComponent", "二度Ⅱ型窦房传导阻滞长PP间期为基本PP间期整倍数", 4343, 4343, "docx_curated_diagnostic_component"),
    ],
    "一、房室交界性期前收缩": [
        ("Exam", "心电图", 4456, 4459, "docx_curated_exam"),
        ("DiagnosisCriteriaComponent", "提前发生的QRS波与逆行P波", 4456, 4456, "docx_curated_diagnostic_component"),
        ("DiagnosisCriteriaComponent", "逆行P波可位于QRS波之前、之中或之后", 4456, 4456, "docx_curated_diagnostic_component"),
        ("DiagnosisCriteriaComponent", "QRS波形态通常正常，室内差异性传导时可变化", 4456, 4456, "docx_curated_diagnostic_component"),
    ],
    "三、非阵发性房室交界性心动过速": [
        ("Exam", "心电图", 4474, 4474, "docx_curated_exam"),
        ("DiagnosisCriteriaComponent", "心率70～150次/分或更快，心律通常规则，QRS波群正常", 4474, 4474, "docx_curated_diagnostic_component"),
        ("DiagnosisCriteriaComponent", "发作起始与终止时心率逐渐变化，有别于突发突止的阵发性折返性心动过速", 4474, 4474, "docx_curated_diagnostic_component"),
        ("DiagnosisCriteriaComponent", "可发生房室分离", 4474, 4474, "docx_curated_diagnostic_component"),
    ],
}


def read_docx_paras(docx_path: Path) -> list[str]:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    return [
        "".join((t.text or "") for t in p.findall(".//w:t", ns)).strip()
        for p in root.findall(".//w:body/w:p", ns)
    ]


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def compact(text: str, limit: int = 260) -> str:
    return re.sub(r"\s+", "", text or "")[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Curate remaining textbook skeleton gaps with explicit textbook evidence.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--docx", required=True, type=Path)
    parser.add_argument("--batch-id", default="CARD-SKELETON-20260709")
    args = parser.parse_args()

    paras = read_docx_paras(args.docx)
    c1 = read_csv(args.out_dir / "阶段C1_教材骨架原文锚点审计_20260709.csv")
    c1_by_subject = {r["subject_name"]: r for r in c1}

    nodes = []
    rels = []
    links = []
    audit = []

    for subject, items in CURATED.items():
        meta = c1_by_subject.get(subject)
        if not meta:
            audit.append({"subject_name": subject, "status": "source_subject_not_found", "candidate_count": 0})
            continue
        parent = meta["parent"]
        subject_id = stable_id(f"{args.batch_id}-SUBJECT", parent, subject)
        count = 0
        for node_type, name, start, end, confidence in items:
            fragment = compact("".join(paras[start : end + 1]), 360)
            node_id = stable_id(f"{args.batch_id}-{node_type.upper()}", node_type, name, "")
            evidence_id = stable_id(f"{args.batch_id}-EVID-C4", subject, node_type, name, str(start), str(end))
            rel_type = REL_TYPE_BY_NODE_TYPE.get(node_type, f"HAS_{node_type.upper()}")
            nodes.append(
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "name": name,
                    "standard_code": "",
                    "source_layer": "textbook_skeleton_c4_curated",
                    "batch_id": args.batch_id,
                    "clinical_use_status": "not_for_formal_cdss_until_reviewed",
                    "import_status": "local_candidate_not_imported",
                }
            )
            rels.append(
                {
                    "rel_id": stable_id(f"{args.batch_id}-REL-C4", subject_id, node_id, rel_type),
                    "source_id": subject_id,
                    "source_name": subject,
                    "target_id": node_id,
                    "target_name": name,
                    "target_type": node_type,
                    "rel_type": rel_type,
                    "batch_id": args.batch_id,
                    "evidence_ids": [evidence_id],
                    "confidence": confidence,
                    "import_status": "local_candidate_not_imported",
                }
            )
            links.append(
                {
                    "evidence_id": evidence_id,
                    "node_id": node_id,
                    "node_type": node_type,
                    "node_name": name,
                    "matched_text": name,
                    "fragment": fragment,
                    "source_section_path": f"{parent} > {subject}",
                    "docx_para_start": start,
                    "docx_para_end": end,
                    "pdf_page_approx": meta.get("pdf_page_approx", ""),
                    "confidence": confidence,
                }
            )
            count += 1
        audit.append({"subject_name": subject, "status": "ok_curated_from_textbook", "candidate_count": count})

    # Deduplicate and merge.
    def by_id(rows: list[dict], key: str) -> dict:
        out = {}
        for row in rows:
            out.setdefault(row[key], row)
        return out

    c3_nodes = load_jsonl(args.out_dir / "阶段C3_合并结构化候选_nodes_20260709.jsonl")
    c3_rels = load_jsonl(args.out_dir / "阶段C3_合并结构化候选_relations_20260709.jsonl")
    merged_nodes = by_id(c3_nodes, "node_id")
    merged_nodes.update(by_id(nodes, "node_id"))
    merged_rels = by_id(c3_rels, "rel_id")
    merged_rels.update(by_id(rels, "rel_id"))

    write_jsonl(args.out_dir / "阶段C4_剩余缺口精修_nodes_20260709.jsonl", list(by_id(nodes, "node_id").values()))
    write_jsonl(args.out_dir / "阶段C4_剩余缺口精修_relations_20260709.jsonl", list(by_id(rels, "rel_id").values()))
    write_jsonl(args.out_dir / "阶段C4_剩余缺口精修_evidence_links_20260709.jsonl", links)
    write_jsonl(args.out_dir / "阶段C4_合并结构化候选_nodes_20260709.jsonl", list(merged_nodes.values()))
    write_jsonl(args.out_dir / "阶段C4_合并结构化候选_relations_20260709.jsonl", list(merged_rels.values()))
    write_csv(args.out_dir / "阶段C4_剩余缺口精修审计_20260709.csv", audit)

    summary = {
        "batch_id": args.batch_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "curated_subject_count": len(CURATED),
        "curated_node_count": len(by_id(nodes, "node_id")),
        "curated_relation_count": len(by_id(rels, "rel_id")),
        "curated_evidence_link_count": len(links),
        "merged_node_count": len(merged_nodes),
        "merged_relation_count": len(merged_rels),
        "not_imported_to_neo4j": True,
        "note": "C4 is local curated candidate layer; still requires final G1/G2 audit and stable-id delta generation.",
    }
    (args.out_dir / "阶段C4_剩余缺口精修_summary_20260709.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
