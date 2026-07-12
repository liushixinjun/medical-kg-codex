# -*- coding: utf-8 -*-
"""校验疾病名称与章节坐标对齐审计输出。

本校验只读本地文件，不连接 Neo4j。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = "20260712"
OUT_DIR = ROOT / "骨架质量闭环_skeleton_quality_loop" / f"{RUN_DATE}_心血管内科疾病名称与证据坐标对齐"

REQUIRED_FILES = [
    OUT_DIR / f"疾病名称标准化映射表_{RUN_DATE}.csv",
    OUT_DIR / f"需人工确认疾病映射_{RUN_DATE}.csv",
    OUT_DIR / f"证据文本质量与坐标审计_{RUN_DATE}.csv",
    OUT_DIR / f"可归并候选摘要_{RUN_DATE}.csv",
    OUT_DIR / f"阻断候选原因清单_{RUN_DATE}.csv",
    OUT_DIR / f"疾病名称与章节坐标对齐_summary_{RUN_DATE}.json",
    OUT_DIR / f"疾病名称与章节坐标对齐报告_{RUN_DATE}.md",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fail(message: str) -> int:
    print(f"VALIDATION_FAILED: {message}")
    return 1


def main() -> int:
    missing = [str(p) for p in REQUIRED_FILES if not p.exists()]
    if missing:
        return fail("missing files: " + "；".join(missing))

    summary = json.loads((OUT_DIR / f"疾病名称与章节坐标对齐_summary_{RUN_DATE}.json").read_text(encoding="utf-8"))
    if summary.get("neo4j_written") is not False:
        return fail("summary.neo4j_written must be false")

    counts = summary.get("counts", {})
    input_meta = summary.get("input", {})
    if input_meta.get("backfill_index_scope") != "历史候选池/旧实例产物":
        return fail("backfill_index_scope must be historical candidate pool")
    if input_meta.get("d6_matrix_scope") != "当前骨架基线产物":
        return fail("d6_matrix_scope must be current baseline")

    if int(counts.get("backfill_row_count", 0)) <= 0:
        return fail("backfill_row_count must be positive")
    if int(counts.get("mergeable_slot_summary_rows", 0)) <= 0:
        return fail("mergeable_slot_summary_rows must be positive")

    name_rows = read_csv(OUT_DIR / f"疾病名称标准化映射表_{RUN_DATE}.csv")
    evidence_rows = read_csv(OUT_DIR / f"证据文本质量与坐标审计_{RUN_DATE}.csv")
    mergeable_rows = read_csv(OUT_DIR / f"可归并候选摘要_{RUN_DATE}.csv")

    if any(r.get("issue_scope") != "历史候选池归并风险，不作为当前骨架缺陷" for r in evidence_rows):
        return fail("evidence audit rows must be marked as historical candidate merge risk")

    bad_ami = [
        r
        for r in name_rows
        if r.get("source_disease_name") == "急性心肌梗死" and r.get("target_subject_name") == "心肌疾病"
    ]
    if bad_ami:
        return fail("急性心肌梗死 was mapped to 心肌疾病")

    non_review_ami = [
        r
        for r in name_rows
        if r.get("source_disease_name") == "急性心肌梗死" and r.get("mapping_status") != "需人工确认"
    ]
    if non_review_ami:
        return fail("急性心肌梗死 must remain review-required before STEMI/NSTEMI split")

    if any(r.get("merge_decision") == "可进入抽样复核后归并" and r.get("mapping_status") != "可自动采用" for r in evidence_rows):
        return fail("mergeable evidence must come from auto-accepted disease mapping")

    if not any(r.get("slot") == "clinical_manifestation" for r in mergeable_rows):
        return fail("mergeable summary should include clinical_manifestation candidates")

    print("VALIDATION_OK")
    print("name_mapping_rows=", len(name_rows))
    print("evidence_audit_rows=", len(evidence_rows))
    print("mergeable_summary_rows=", len(mergeable_rows))
    print("neo4j_written=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
