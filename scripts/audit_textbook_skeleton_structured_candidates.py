from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


GROUPS = {
    "definition": {"Definition", "DefinitionComponent"},
    "etiology_pathogenesis": {"Etiology", "RiskFactor", "Pathophysiology"},
    "clinical_manifestation": {"Symptom", "Sign", "ClinicalManifestation"},
    "exam_lab": {"Exam", "LabTest"},
    "diagnosis_differential": {"DiagnosisCriteriaComponent", "DifferentialDiagnosis"},
    "treatment": {"TreatmentPlan", "Medication", "Procedure"},
    "prognosis_followup": {"Prognosis", "FollowUp", "Complication", "Prevention"},
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def subject_kind(name: str, parent: str, has_children: bool = False) -> str:
    text = parent + name
    if has_children:
        return "category_container"
    if any(k in text for k in ["抗心律失常药物", "介入治疗", "手术治疗", "电复律", "电除颤", "导管消融", "起搏", "治疗"]):
        return "therapy_or_management_section"
    if any(k in name for k in ["概述", "总论"]):
        return "overview_section"
    if name.startswith("第") and "章" in name:
        return "chapter"
    if any(k in text for k in ["心律失常", "窦性", "房室交界", "传导阻滞"]) and any(
        k in name for k in ["心动过速", "心动过缓", "停搏", "传导阻滞", "期前收缩", "逸搏", "心律"]
    ):
        return "ecg_defined_arrhythmia"
    return "disease_or_subtype"


def expected_groups(kind: str) -> set[str]:
    if kind == "category_container":
        return set()
    if kind == "ecg_defined_arrhythmia":
        return {"definition", "exam_lab", "diagnosis_differential", "treatment"}
    if kind == "therapy_or_management_section":
        return {"treatment"}
    if kind == "overview_section":
        return {"definition", "etiology_pathogenesis"}
    if kind == "chapter":
        return {"definition"}
    return {"definition", "clinical_manifestation", "exam_lab", "diagnosis_differential", "treatment"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit structured textbook skeleton candidates.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--batch-id", default="CARD-SKELETON-20260709")
    parser.add_argument("--chapter-csv", type=Path, default=None)
    parser.add_argument("--nodes-file", default="阶段C2_结构化候选_nodes_20260709.jsonl")
    parser.add_argument("--relations-file", default="阶段C2_结构化候选_relations_20260709.jsonl")
    parser.add_argument("--prefix", default="阶段C2_G1深审计")
    args = parser.parse_args()

    nodes = load_jsonl(args.out_dir / args.nodes_file)
    rels = load_jsonl(args.out_dir / args.relations_file)
    with (args.out_dir / "阶段C1_教材骨架原文锚点审计_20260709.csv").open("r", encoding="utf-8-sig", newline="") as f:
        c1_subjects = list(csv.DictReader(f))

    chapter_csv = args.chapter_csv or (args.out_dir / "心血管内科教材章节目录_20260709.csv")
    child_parent_names = set()
    if chapter_csv.exists():
        with chapter_csv.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                parent = row.get("父级", "")
                if parent:
                    child_parent_names.add(parent)

    subject_meta = {}
    for row in c1_subjects:
        subject_meta.setdefault(
            row["subject_name"],
            {
                "subject_name": row["subject_name"],
                "parent": row["parent"],
                "level": row["level"],
                "pdf_page_approx": row["pdf_page_approx"],
                "docx_start_para": row["docx_start_para"],
                "docx_end_para": row["docx_end_para"],
            },
        )

    # Node id -> type/name
    node_map = {n["node_id"]: n for n in nodes}
    by_subject: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    entity_examples: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for rel in rels:
        subject = rel["source_name"]
        target = node_map.get(rel["target_id"], {})
        node_type = rel.get("target_type") or target.get("node_type", "")
        node_name = rel.get("target_name") or target.get("name", "")
        for group, types in GROUPS.items():
            if node_type in types:
                by_subject[subject][group][node_type] += 1
                if len(entity_examples[subject][group]) < 8:
                    entity_examples[subject][group].append(node_name)

    rows = []
    for subject, meta in sorted(subject_meta.items(), key=lambda x: (x[1]["parent"], x[0])):
        kind = subject_kind(subject, meta["parent"], has_children=subject in child_parent_names)
        required = expected_groups(kind)
        present = {group for group, counter in by_subject.get(subject, {}).items() if sum(counter.values()) > 0}
        missing = sorted(required - present)
        if kind == "category_container":
            status = "g1_container_rollup_only"
        elif not missing:
            status = "g1_structured_candidate_ready"
        elif present:
            status = "g1_needs_backfill"
        else:
            status = "g1_no_structured_candidate"
        row = {
            **meta,
            "subject_kind": kind,
            "expected_groups": "；".join(sorted(required)),
            "present_groups": "；".join(sorted(present)),
            "missing_groups": "；".join(missing),
            "definition_count": sum(by_subject[subject]["definition"].values()),
            "etiology_pathogenesis_count": sum(by_subject[subject]["etiology_pathogenesis"].values()),
            "clinical_manifestation_count": sum(by_subject[subject]["clinical_manifestation"].values()),
            "exam_lab_count": sum(by_subject[subject]["exam_lab"].values()),
            "diagnosis_differential_count": sum(by_subject[subject]["diagnosis_differential"].values()),
            "treatment_count": sum(by_subject[subject]["treatment"].values()),
            "prognosis_followup_count": sum(by_subject[subject]["prognosis_followup"].values()),
            "example_entities": "；".join(
                f"{group}: {', '.join(names[:5])}" for group, names in entity_examples[subject].items()
            ),
            "g1_status": status,
            "neo4j_import_allowed": "否",
            "note": "C2结构化候选仍需人工/规则深审计后才能进入curated delta",
        }
        rows.append(row)

    audit_path = args.out_dir / f"{args.prefix}矩阵_20260709.csv"
    with audit_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    status_counter = Counter(r["g1_status"] for r in rows)
    kind_counter = Counter(r["subject_kind"] for r in rows)
    missing_counter = Counter()
    for row in rows:
        for group in row["missing_groups"].split("；"):
            if group:
                missing_counter[group] += 1

    summary = {
        "batch_id": args.batch_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "subject_count": len(rows),
        "status_counter": dict(status_counter),
        "subject_kind_counter": dict(kind_counter),
        "missing_group_counter": dict(missing_counter),
        "neo4j_import_allowed": False,
        "next_required": "backfill_missing_groups_or_curate_ready_candidates",
    }
    (args.out_dir / f"{args.prefix}_summary_20260709.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = []
    md.append("# 阶段C2-G1深审计报告")
    md.append("")
    md.append(f"生成时间：{summary['generated_at']}")
    md.append("")
    md.append("## 1. 结论")
    md.append("")
    md.append("- C2 已形成结构化候选，但当前仍不允许直接导入 Neo4j。")
    md.append("- G1 审计用于判断哪些对象可以进入 curated delta，哪些需要补槽位。")
    md.append("")
    md.append("## 2. 状态统计")
    md.append("")
    md.append("| 状态 | 数量 |")
    md.append("|---|---:|")
    for status, count in status_counter.most_common():
        md.append(f"| {status} | {count} |")
    md.append("")
    md.append("## 3. 缺失组统计")
    md.append("")
    md.append("| 缺失组 | 数量 |")
    md.append("|---|---:|")
    for group, count in missing_counter.most_common():
        md.append(f"| {group} | {count} |")
    md.append("")
    md.append("## 4. 下一步")
    md.append("")
    md.append("优先处理 `g1_needs_backfill` 和 `g1_no_structured_candidate`，补齐后再生成 curated delta。")
    (args.out_dir / f"{args.prefix}报告_20260709.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
