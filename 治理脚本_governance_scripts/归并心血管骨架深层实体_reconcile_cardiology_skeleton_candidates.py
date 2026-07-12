# -*- coding: utf-8 -*-
"""心血管教材骨架深层实体候选归并审计。

只读读取全书回捞索引和D6槽位审计矩阵，生成疾病-槽位-实体候选矩阵。
不连接 Neo4j，不修改历史批次目录。
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = "20260712"
OUT_DIR = ROOT / "骨架质量闭环_skeleton_quality_loop" / f"{RUN_DATE}_心血管内科教材骨架审计"
FOUNDATION_ROOT = ROOT / "心血管内科文献集合" / "00_foundation_skeleton"
FULL_DIR = (
    ROOT
    / "心血管内科文献集合"
    / "00_教材骨架库_foundation_skeleton"
    / "心血管内科全章节骨架扩展_CARD-SKELETON-FULL-20260709"
)

BACKFILL_INDEX = FOUNDATION_ROOT / "04_evidence_and_extraction" / "textbook_fullbook_backfill_index.csv"
D6_MATRIX = FULL_DIR / "阶段D6_来源感知G1全章节审计矩阵_20260709.csv"
SLOT_AUDIT = OUT_DIR / f"心血管内科骨架槽位覆盖审计_{RUN_DATE}.csv"

ENTITY_SLOT = {
    "Symptom": "clinical_manifestation",
    "Sign": "clinical_manifestation",
    "ClinicalManifestation": "clinical_manifestation",
    "Exam": "exam_lab",
    "LabTest": "exam_lab",
    "ExamIndicator": "exam_lab",
    "TreatmentPlan": "treatment",
    "Medication": "treatment",
    "Procedure": "treatment",
    "DiagnosisCriteria": "diagnosis_differential",
    "DiagnosisCriteriaComponent": "diagnosis_differential",
    "DifferentialDiagnosis": "diagnosis_differential",
    "RiskStratification": "classification_risk",
    "DiseaseClassification": "classification_risk",
    "Etiology": "etiology_pathogenesis",
    "Pathophysiology": "etiology_pathogenesis",
    "RiskFactor": "etiology_pathogenesis",
    "Complication": "follow_up_prognosis",
    "Prognosis": "follow_up_prognosis",
    "FollowUp": "follow_up_prognosis",
    "Prevention": "follow_up_prognosis",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        seen = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_int(value: str | None) -> int | None:
    try:
        return int(value or "")
    except Exception:
        return None


def load_d6_ranges() -> dict[str, dict[str, Any]]:
    ranges: dict[str, dict[str, Any]] = {}
    for row in read_csv(D6_MATRIX):
        name = row.get("subject_name", "")
        if row.get("subject_kind") not in {"disease_or_topic", "overview_section"}:
            continue
        start = safe_int(row.get("docx_start_para"))
        end = safe_int(row.get("docx_end_para"))
        ranges[name] = {
            "parent": row.get("parent", ""),
            "subject_kind": row.get("subject_kind", ""),
            "status": row.get("status", ""),
            "start": start,
            "end": end,
        }
    return ranges


def load_slot_status() -> dict[tuple[str, str], str]:
    status: dict[tuple[str, str], str] = {}
    for row in read_csv(SLOT_AUDIT):
        status[(row.get("subject_name", ""), row.get("slot", ""))] = row.get("slot_status", "")
    return status


def main() -> int:
    ranges = load_d6_ranges()
    slot_status = load_slot_status()

    aggregation: dict[tuple[str, str], dict[str, Any]] = {}
    entity_type_counter: Counter = Counter()
    slot_counter: Counter = Counter()
    backfill_disease_counter: Counter = Counter()
    total_rows = 0
    mapped_rows = 0
    section_aligned_rows = 0
    out_of_section_rows = 0

    with BACKFILL_INDEX.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            etype = row.get("entityType", "")
            slot = ENTITY_SLOT.get(etype)
            if not slot:
                continue
            mapped_rows += 1
            disease = row.get("disease_name", "")
            backfill_disease_counter[disease] += 1
            entity = row.get("entity_name", "")
            line = safe_int(row.get("line_number"))
            info = ranges.get(disease, {})
            start = info.get("start")
            end = info.get("end")
            aligned = bool(line is not None and start is not None and end is not None and start <= line <= end)
            if aligned:
                section_aligned_rows += 1
            else:
                out_of_section_rows += 1

            key = (disease, slot)
            bucket = aggregation.setdefault(
                key,
                {
                    "subject_name": disease,
                    "parent": info.get("parent", ""),
                    "subject_kind": info.get("subject_kind", ""),
                    "d6_status": info.get("status", ""),
                    "slot": slot,
                    "entity_mentions": 0,
                    "section_aligned_mentions": 0,
                    "out_of_section_mentions": 0,
                    "unique_entities": set(),
                    "section_aligned_entities": set(),
                    "entity_type_counter": Counter(),
                    "sample_evidence": [],
                },
            )
            bucket["entity_mentions"] += 1
            bucket["unique_entities"].add(entity)
            bucket["entity_type_counter"][etype] += 1
            if aligned:
                bucket["section_aligned_mentions"] += 1
                bucket["section_aligned_entities"].add(entity)
                if len(bucket["sample_evidence"]) < 3:
                    bucket["sample_evidence"].append(
                        f"{entity}｜行{line}｜{row.get('evidence_text','')[:80]}"
                    )
            else:
                bucket["out_of_section_mentions"] += 1

            entity_type_counter[etype] += 1
            slot_counter[slot] += 1

    detail_rows: list[dict[str, Any]] = []
    action_counter: Counter = Counter()
    for (disease, slot), bucket in sorted(aggregation.items()):
        d6_slot_status = slot_status.get((disease, slot), "not_in_d6_slot_audit")
        aligned_entities = sorted(x for x in bucket["section_aligned_entities"] if x)
        all_entities = sorted(x for x in bucket["unique_entities"] if x)
        if bucket["section_aligned_mentions"] > 0 and d6_slot_status in {
            "not_applicable_or_not_detected",
            "source_not_cover",
            "reference_only",
            "available_missing",
        }:
            action = "需要归并到D6槽位"
        elif bucket["section_aligned_mentions"] > 0 and d6_slot_status in {
            "candidate_present",
            "deep_entity_present",
        }:
            action = "已可作为槽位候选复核"
        elif bucket["section_aligned_mentions"] == 0 and bucket["entity_mentions"] > 0:
            action = "疑似跨章节噪声，需人工抽样确认"
        else:
            action = "无需处理"
        action_counter[action] += 1
        detail_rows.append(
            {
                "subject_name": disease,
                "parent": bucket["parent"],
                "subject_kind": bucket["subject_kind"],
                "d6_status": bucket["d6_status"],
                "slot": slot,
                "d6_slot_status": d6_slot_status,
                "entity_mentions": bucket["entity_mentions"],
                "section_aligned_mentions": bucket["section_aligned_mentions"],
                "out_of_section_mentions": bucket["out_of_section_mentions"],
                "unique_entity_count": len(all_entities),
                "section_aligned_unique_entity_count": len(aligned_entities),
                "entity_type_counts": json.dumps(dict(bucket["entity_type_counter"]), ensure_ascii=False),
                "sample_section_aligned_entities": "；".join(aligned_entities[:20]),
                "sample_all_entities": "；".join(all_entities[:20]),
                "sample_evidence": " || ".join(bucket["sample_evidence"]),
                "recommended_action": action,
            }
        )

    priority_rows = [
        r
        for r in detail_rows
        if r["recommended_action"] in {"需要归并到D6槽位", "疑似跨章节噪声，需人工抽样确认"}
    ]
    priority_rows.sort(
        key=lambda r: (
            0 if r["recommended_action"] == "需要归并到D6槽位" else 1,
            -int(r["section_aligned_mentions"]),
            r["subject_name"],
            r["slot"],
        )
    )

    name_alignment_rows: list[dict[str, Any]] = []
    for disease, count in sorted(backfill_disease_counter.items()):
        info = ranges.get(disease)
        name_alignment_rows.append(
            {
                "disease_name": disease,
                "backfill_mentions": count,
                "exists_in_d6_matrix": "yes" if info else "no",
                "d6_parent": info.get("parent", "") if info else "",
                "d6_subject_kind": info.get("subject_kind", "") if info else "",
                "d6_status": info.get("status", "") if info else "",
                "recommended_action": "可按D6章节范围归并审计" if info else "需先做疾病别名/层级映射，不能直接归并",
            }
        )
    unmatched_name_count = sum(1 for row in name_alignment_rows if row["exists_in_d6_matrix"] == "no")

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "neo4j_written": False,
        "backfill_index": str(BACKFILL_INDEX),
        "d6_matrix": str(D6_MATRIX),
        "backfill_total_rows": total_rows,
        "mapped_rows": mapped_rows,
        "section_aligned_rows": section_aligned_rows,
        "out_of_section_rows": out_of_section_rows,
        "disease_slot_pair_count": len(detail_rows),
        "priority_pair_count": len(priority_rows),
        "backfill_disease_name_count": len(name_alignment_rows),
        "backfill_disease_names_not_in_d6": unmatched_name_count,
        "action_counter": dict(action_counter),
        "slot_counter": dict(slot_counter),
        "entity_type_counter": dict(entity_type_counter),
        "interpretation": {
            "section_aligned": "候选实体行号落在D6疾病/专题章节段落范围内，可优先归并。",
            "out_of_section": "全书回捞命中但不在对应章节范围内，可能是跨章节噪声或全书关联事实，不能直接入槽位。",
            "next_step": "先处理需要归并到D6槽位的条目，再抽样核查跨章节噪声。",
        },
    }

    write_csv(OUT_DIR / f"心血管内科骨架深层实体归并明细_{RUN_DATE}.csv", detail_rows)
    write_csv(OUT_DIR / f"心血管内科骨架深层实体归并优先清单_{RUN_DATE}.csv", priority_rows)
    write_csv(OUT_DIR / f"心血管内科骨架疾病名称对齐审计_{RUN_DATE}.csv", name_alignment_rows)
    write_json(OUT_DIR / f"心血管内科骨架深层实体归并_summary_{RUN_DATE}.json", summary)

    report = f"""
# 心血管内科骨架深层实体归并审计报告

生成时间：{summary['generated_at']}

## 1. 本轮目的

把全书回捞索引中的症状、体征、检查、治疗、诊断、鉴别等深层实体，与 D6 全章节槽位审计矩阵对齐。

本轮只生成审计与归并建议，不写 Neo4j，不改历史批次目录。

## 2. 关键统计

| 指标 | 数值 |
|---|---:|
| 全书回捞索引总行数 | {total_rows} |
| 可映射到骨架槽位的行数 | {mapped_rows} |
| 章节内对齐行数 | {section_aligned_rows} |
| 跨章节/疑似噪声行数 | {out_of_section_rows} |
| 疾病-槽位组合数 | {len(detail_rows)} |
| 需优先处理组合数 | {len(priority_rows)} |
| 全书回捞疾病名数 | {len(name_alignment_rows)} |
| 未在D6矩阵命中的疾病名数 | {unmatched_name_count} |

## 3. 动作分布

```json
{json.dumps(dict(action_counter), ensure_ascii=False, indent=2)}
```

## 4. 结论

1. 全书回捞中已有大量深层实体，但不能直接全部并入疾病槽位。
2. 全书回捞疾病名与D6教材章节名存在差异；未命中D6的疾病名必须先做别名/层级映射。
3. 章节内对齐的实体可优先进入 D6 候选归并流程。
4. 跨章节命中的实体必须先抽样确认，否则容易把前言、总论或其他疾病内容误归到当前疾病。

## 5. 下一步

1. 先处理 `心血管内科骨架疾病名称对齐审计_{RUN_DATE}.csv` 中未命中D6矩阵的疾病名。
2. 对 `需要归并到D6槽位` 的组合生成 delta 候选，但仍需 G1/G2 审计。
3. 对 `疑似跨章节噪声` 抽样核查，不能直接写库。
4. 与服务器实时复核对齐后，再决定是否执行入库。
"""
    write_text(OUT_DIR / f"心血管内科骨架深层实体归并报告_{RUN_DATE}.md", report)

    print("RECONCILE_OK")
    print("mapped_rows=", mapped_rows)
    print("section_aligned_rows=", section_aligned_rows)
    print("out_of_section_rows=", out_of_section_rows)
    print("priority_pair_count=", len(priority_rows))
    print("backfill_disease_name_count=", len(name_alignment_rows))
    print("backfill_disease_names_not_in_d6=", unmatched_name_count)
    print("out_dir=", OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
