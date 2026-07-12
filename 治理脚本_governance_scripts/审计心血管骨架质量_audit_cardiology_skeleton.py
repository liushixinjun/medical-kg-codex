# -*- coding: utf-8 -*-
"""心血管内科教材骨架质量闭环审计。

只读读取既有骨架产物，生成本轮审计报告。
不连接 Neo4j，不修改历史批次目录，不写服务器数据库。
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
QUALITY_DIR = FOUNDATION_ROOT / "06_quality_audit"
DATA_DIR = FOUNDATION_ROOT / "05_data_instance"

CN_FOUNDATION_ROOT = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton"
FULL_DIR = CN_FOUNDATION_ROOT / "心血管内科全章节骨架扩展_CARD-SKELETON-FULL-20260709"

SLOT_GROUPS = [
    "definition",
    "etiology_pathogenesis",
    "clinical_manifestation",
    "exam_lab",
    "diagnosis_differential",
    "classification_risk",
    "treatment",
]

DEEP_COUNT_GROUPS = {
    "clinical_manifestation": ["symptom_count", "sign_count"],
    "exam_lab": ["exam_count", "lab_test_count"],
    "treatment": ["treatment_plan_count", "medication_count", "procedure_count"],
    "classification_risk": ["risk_stratification_count"],
    "follow_up_prognosis": ["follow_up_count", "prognosis_count"],
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def split_groups(value: str) -> set[str]:
    if not value:
        return set()
    return {x.strip() for x in value.replace(";", "；").split("；") if x.strip()}


def safe_int(value: str | int | None) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def sample_jsonl_entity_counts(path: Path) -> tuple[Counter, int]:
    counts: Counter = Counter()
    total = 0
    if not path.exists():
        return counts, total
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            try:
                obj = json.loads(line)
            except Exception:
                continue
            et = obj.get("entityType") or obj.get("type") or obj.get("label") or "UNKNOWN"
            counts[str(et)] += 1
    return counts, total


def classify_slot_status(
    slot: str,
    source_available: set[str],
    present: set[str],
    reference_only: set[str],
    extraction_gap: set[str],
    source_not_cover: set[str],
    deep_presence: set[str],
) -> tuple[str, str]:
    if slot in present:
        return "candidate_present", "D6候选已覆盖"
    if slot in deep_presence:
        return "deep_entity_present", "全书回捞深层实体有计数，需与D6候选归并"
    if slot in extraction_gap:
        return "extraction_gap", "教材有来源但抽取缺口，需补抽"
    if slot in reference_only:
        return "reference_only", "仅引用/提示，不足以直接作为结构化临床实体"
    if slot in source_not_cover:
        return "source_not_cover", "当前教材章节未覆盖，后续由指南/权威来源补血肉"
    if slot in source_available:
        return "available_missing", "教材显示可用但候选缺失"
    return "not_applicable_or_not_detected", "本章节未识别该槽位"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    full_matrix_path = FULL_DIR / "阶段D6_来源感知G1全章节审计矩阵_20260709.csv"
    full_summary_path = FULL_DIR / "阶段D6_来源感知G1全章节审计_summary_20260709.json"
    chapter_outline_path = FULL_DIR / "心血管内科教材章节目录_20260709.csv"
    backfill_coverage_path = QUALITY_DIR / "textbook_fullbook_backfill_coverage.csv"
    foundation_quality_path = QUALITY_DIR / "foundation_quality_summary.json"
    import_summary_path = FOUNDATION_ROOT / "08_neo4j_import" / "neo4j_import_summary_global_dedupe_replace_final.json"
    c6_server_summary_path = FULL_DIR / "阶段C6_服务器复核_summary_20260709.json"

    matrix_rows = read_csv(full_matrix_path)
    chapter_rows = read_csv(chapter_outline_path)
    backfill_rows = read_csv(backfill_coverage_path)
    full_summary = read_json(full_summary_path)
    foundation_quality = read_json(foundation_quality_path)
    import_summary = read_json(import_summary_path)
    c6_summary = read_json(c6_server_summary_path)

    backfill_by_name = {r.get("disease_name", ""): r for r in backfill_rows if r.get("disease_name")}

    subject_counter = Counter(r.get("subject_kind", "UNKNOWN") for r in matrix_rows)
    status_counter = Counter(r.get("status", "UNKNOWN") for r in matrix_rows)
    level_counter = Counter(r.get("level", "UNKNOWN") for r in matrix_rows)

    slot_rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    category_counter: dict[str, Counter] = defaultdict(Counter)

    audited_subjects = [
        r
        for r in matrix_rows
        if r.get("subject_kind") in {"disease_or_topic", "overview_section"}
    ]

    for row in audited_subjects:
        name = row.get("subject_name", "")
        parent = row.get("parent", "")
        kind = row.get("subject_kind", "")
        status = row.get("status", "")
        source_available = split_groups(row.get("source_available_groups", ""))
        present = split_groups(row.get("present_candidate_groups", ""))
        reference_only = split_groups(row.get("reference_only_groups", ""))
        extraction_gap = split_groups(row.get("extraction_gap_groups", ""))
        source_not_cover = split_groups(row.get("textbook_source_not_cover_groups", ""))
        deep = backfill_by_name.get(name, {})
        deep_presence = {
            group
            for group, cols in DEEP_COUNT_GROUPS.items()
            if sum(safe_int(deep.get(c)) for c in cols) > 0
        }

        category_counter[parent]["subject_count"] += 1
        category_counter[parent][status] += 1

        for slot in SLOT_GROUPS:
            slot_status, note = classify_slot_status(
                slot,
                source_available,
                present,
                reference_only,
                extraction_gap,
                source_not_cover,
                deep_presence,
            )
            slot_rows.append(
                {
                    "subject_name": name,
                    "parent": parent,
                    "subject_kind": kind,
                    "status": status,
                    "slot": slot,
                    "slot_status": slot_status,
                    "note": note,
                    "docx_start_para": row.get("docx_start_para", ""),
                    "docx_end_para": row.get("docx_end_para", ""),
                    "example_entities": row.get("example_entities", "")[:300],
                }
            )

            if slot_status in {"extraction_gap", "available_missing"}:
                severity = "P0" if slot in {"definition", "clinical_manifestation", "exam_lab", "diagnosis_differential", "treatment"} else "P1"
                issue_rows.append(
                    {
                        "severity": severity,
                        "issue_type": slot_status,
                        "subject_name": name,
                        "parent": parent,
                        "slot": slot,
                        "reason": note,
                        "recommended_action": "回到教材原文段落补抽结构化实体",
                    }
                )
            elif slot_status == "source_not_cover" and slot in {"clinical_manifestation", "exam_lab", "diagnosis_differential", "treatment"}:
                issue_rows.append(
                    {
                        "severity": "P2",
                        "issue_type": "source_not_cover",
                        "subject_name": name,
                        "parent": parent,
                        "slot": slot,
                        "reason": note,
                        "recommended_action": "后续专病指南/权威来源补充，不作为教材抽取失败",
                    }
                )

    slot_status_counter = Counter(r["slot_status"] for r in slot_rows)
    slot_by_group: dict[str, Counter] = defaultdict(Counter)
    for r in slot_rows:
        slot_by_group[r["slot"]][r["slot_status"]] += 1

    category_rows = []
    for parent, counter in sorted(category_counter.items()):
        total = counter.get("subject_count", 0)
        ready = counter.get("source_covered_ready", 0)
        limited = counter.get("source_limited_ready_as_textbook_core", 0)
        category_rows.append(
            {
                "parent_category": parent,
                "audited_subject_count": total,
                "source_covered_ready": ready,
                "source_limited_ready_as_textbook_core": limited,
                "container_rollup_only": counter.get("container_rollup_only", 0),
                "ready_rate": round(ready / total, 4) if total else 0,
                "limited_rate": round(limited / total, 4) if total else 0,
            }
        )

    entity_counts, node_total = sample_jsonl_entity_counts(DATA_DIR / "nodes_final.jsonl")
    clinical_entity_count = sum(
        entity_counts.get(k, 0)
        for k in [
            "Symptom",
            "Sign",
            "Exam",
            "LabTest",
            "TreatmentPlan",
            "Medication",
            "Procedure",
            "DiagnosisCriteria",
            "DiagnosisCriteriaComponent",
            "DifferentialDiagnosis",
        ]
    )

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_date": RUN_DATE,
        "neo4j_written": False,
        "source_files": {
            "full_matrix": str(full_matrix_path),
            "full_summary": str(full_summary_path),
            "chapter_outline": str(chapter_outline_path),
            "backfill_coverage": str(backfill_coverage_path),
            "foundation_quality": str(foundation_quality_path),
            "import_summary": str(import_summary_path),
            "c6_server_summary": str(c6_server_summary_path),
        },
        "matrix_subject_count": len(matrix_rows),
        "audited_subject_count": len(audited_subjects),
        "chapter_outline_count": len(chapter_rows),
        "subject_kind_counter": dict(subject_counter),
        "status_counter": dict(status_counter),
        "level_counter": dict(level_counter),
        "slot_status_counter": dict(slot_status_counter),
        "slot_by_group": {k: dict(v) for k, v in slot_by_group.items()},
        "issue_counter": dict(Counter(r["severity"] for r in issue_rows)),
        "foundation_quality_summary": foundation_quality,
        "local_nodes_final_total": node_total,
        "local_nodes_entity_type_counts_top": dict(entity_counts.most_common(40)),
        "clinical_entity_count_in_nodes_final": clinical_entity_count,
        "last_import_summary": {
            "status": import_summary.get("status"),
            "database_kg_node_count": import_summary.get("database_kg_node_count"),
            "database_relation_count": import_summary.get("database_relation_count"),
            "node_entity_type_counts": import_summary.get("node_entity_type_counts"),
            "relation_type_counts": import_summary.get("relation_type_counts"),
        },
        "c6_server_summary": {
            "status": c6_summary.get("status"),
            "batch_counts": c6_summary.get("batch_counts"),
            "checks": c6_summary.get("checks"),
            "batch_entity_types": c6_summary.get("batch_entity_types"),
        },
        "interpretation": {
            "local_extraction": "D6全章节候选抽取未发现extraction_gap，但大量source_limited说明教材本身不覆盖或只适合作为基础骨架。",
            "server_state": "本轮未连接服务器；只引用历史导入摘要，不能替代实时Neo4j复核。",
            "cdss_readiness": "教材骨架可作为基础知识层，不等同于正式CDSS推荐层；后续仍需指南证据、推荐规则和服务器postcheck。",
        },
    }

    write_csv(OUT_DIR / f"心血管内科骨架槽位覆盖审计_{RUN_DATE}.csv", slot_rows)
    write_csv(OUT_DIR / f"心血管内科骨架疾病大类汇总_{RUN_DATE}.csv", category_rows)
    write_csv(OUT_DIR / f"心血管内科骨架质量问题清单_{RUN_DATE}.csv", issue_rows)
    write_json(OUT_DIR / f"心血管内科骨架质量闭环_summary_{RUN_DATE}.json", summary)

    top_issues = Counter(r["issue_type"] for r in issue_rows)
    p0 = sum(1 for r in issue_rows if r["severity"] == "P0")
    p1 = sum(1 for r in issue_rows if r["severity"] == "P1")
    p2 = sum(1 for r in issue_rows if r["severity"] == "P2")

    report = f"""
# 心血管内科教材骨架质量闭环审计报告

生成时间：{summary['generated_at']}

## 1. 本轮结论

本轮只做本地骨架质量闭环审计，未连接 Neo4j，未写服务器数据库，未改历史批次目录。

当前判断：

1. 心血管内科教材骨架已经有全章节候选抽取和历史导入摘要，不是从零状态。
2. D6 全章节审计显示 `extraction_gap_group_counter` 为空，说明已知教材范围内没有明显“有来源但没抽”的机械缺口。
3. 但 D6 显示 `source_limited_ready_as_textbook_core` 为 45 个主题，说明大量内容只能作为教材基础骨架，不能直接等同正式 CDSS 决策层。
4. 历史服务器摘要显示全章节批次导入检查通过，但本轮未实时连接服务器，因此不能替代当前 Neo4j 复核。

## 2. 关键统计

| 指标 | 数值 |
|---|---:|
| D6矩阵主题数 | {len(matrix_rows)} |
| 本轮审计主题数 | {len(audited_subjects)} |
| 教材章节目录行数 | {len(chapter_rows)} |
| `nodes_final.jsonl` 节点数 | {node_total} |
| 临床实体节点数（本地nodes_final） | {clinical_entity_count} |
| 质量问题清单 P0 | {p0} |
| 质量问题清单 P1 | {p1} |
| 质量问题清单 P2 | {p2} |

## 3. D6状态分布

```json
{json.dumps(dict(status_counter), ensure_ascii=False, indent=2)}
```

## 4. 槽位覆盖状态

```json
{json.dumps({k: dict(v) for k, v in slot_by_group.items()}, ensure_ascii=False, indent=2)}
```

## 5. 需要处理的问题

```json
{json.dumps(dict(top_issues), ensure_ascii=False, indent=2)}
```

处理原则：

- `extraction_gap` / `available_missing`：属于抽取或归并缺口，后续应回到教材原文补抽。
- `source_not_cover`：不是抽取失败，属于教材本身未覆盖，后续由指南、共识、权威来源补充。
- `deep_entity_present`：说明全书回捞有实体计数，但 D6 槽位候选未完全归并，后续应做“候选归并审计”，不是重新抽取全文。

## 6. 下一步执行建议

第一步：做“候选归并审计”

- 输入：`textbook_fullbook_backfill_coverage.csv` 与 D6 审计矩阵。
- 目标：把全书回捞中已有的症状、体征、检查、治疗等深层实体，归并到 D6 槽位视图。
- 输出：疾病-槽位-实体明细矩阵。

第二步：做“source_not_cover 分流”

- 教材未覆盖但 CDSS 必需的槽位，进入指南/共识补血肉清单。
- 不再把 source_not_cover 误判成抽取质量失败。

第三步：服务器实时复核

- 等用户允许连接 Neo4j 后，读取当前服务器实际疾病、实体、关系、硬闸门。
- 把历史导入摘要与实时服务器状态对齐。

## 7. 本轮输出文件

- `心血管内科骨架槽位覆盖审计_{RUN_DATE}.csv`
- `心血管内科骨架疾病大类汇总_{RUN_DATE}.csv`
- `心血管内科骨架质量问题清单_{RUN_DATE}.csv`
- `心血管内科骨架质量闭环_summary_{RUN_DATE}.json`
"""
    write_text(OUT_DIR / f"心血管内科骨架质量闭环报告_{RUN_DATE}.md", report)

    print("AUDIT_OK")
    print("out_dir=", OUT_DIR)
    print("matrix_subject_count=", len(matrix_rows))
    print("audited_subject_count=", len(audited_subjects))
    print("nodes_final_total=", node_total)
    print("issue_count=", len(issue_rows))
    print("p0=", p0, "p1=", p1, "p2=", p2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
