# -*- coding: utf-8 -*-
"""骨架质量闭环输出校验。

只读校验本轮审计产物是否齐全，不连接Neo4j，不写业务数据。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = "20260712"
OUT_DIR = ROOT / "骨架质量闭环_skeleton_quality_loop" / f"{RUN_DATE}_心血管内科教材骨架审计"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def count_csv(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def main() -> int:
    required = [
        OUT_DIR / f"心血管内科骨架槽位覆盖审计_{RUN_DATE}.csv",
        OUT_DIR / f"心血管内科骨架疾病大类汇总_{RUN_DATE}.csv",
        OUT_DIR / f"心血管内科骨架质量问题清单_{RUN_DATE}.csv",
        OUT_DIR / f"心血管内科骨架质量闭环_summary_{RUN_DATE}.json",
        OUT_DIR / f"心血管内科骨架质量闭环报告_{RUN_DATE}.md",
        OUT_DIR / f"心血管内科骨架深层实体归并明细_{RUN_DATE}.csv",
        OUT_DIR / f"心血管内科骨架深层实体归并优先清单_{RUN_DATE}.csv",
        OUT_DIR / f"心血管内科骨架疾病名称对齐审计_{RUN_DATE}.csv",
        OUT_DIR / f"心血管内科骨架深层实体归并_summary_{RUN_DATE}.json",
        OUT_DIR / f"心血管内科骨架深层实体归并报告_{RUN_DATE}.md",
        OUT_DIR / f"心血管内科教材骨架质量闭环总报告_{RUN_DATE}.md",
    ]
    failures: list[str] = []
    for path in required:
        if not path.exists():
            failures.append(f"缺少文件：{path}")

    if failures:
        print("VALIDATION_FAILED")
        for item in failures:
            print("-", item)
        return 1

    quality = load_json(OUT_DIR / f"心血管内科骨架质量闭环_summary_{RUN_DATE}.json")
    reconcile = load_json(OUT_DIR / f"心血管内科骨架深层实体归并_summary_{RUN_DATE}.json")
    issue_count = count_csv(OUT_DIR / f"心血管内科骨架质量问题清单_{RUN_DATE}.csv")
    priority_count = count_csv(OUT_DIR / f"心血管内科骨架深层实体归并优先清单_{RUN_DATE}.csv")
    name_count = count_csv(OUT_DIR / f"心血管内科骨架疾病名称对齐审计_{RUN_DATE}.csv")

    if quality.get("neo4j_written") is not False:
        failures.append("质量审计summary未标记neo4j_written=false")
    if reconcile.get("neo4j_written") is not False:
        failures.append("归并审计summary未标记neo4j_written=false")
    if quality.get("issue_counter", {}).get("P0", 0):
        failures.append("存在P0骨架质量问题")
    if quality.get("issue_counter", {}).get("P1", 0):
        failures.append("存在P1骨架质量问题")
    if reconcile.get("backfill_disease_names_not_in_d6", 0) <= 0:
        failures.append("未识别到疾病名称对齐问题，需复核审计算法")

    if failures:
        print("VALIDATION_FAILED")
        for item in failures:
            print("-", item)
        return 1

    print("VALIDATION_OK")
    print("audited_subject_count=", quality.get("audited_subject_count"))
    print("quality_issue_rows=", issue_count)
    print("reconcile_priority_rows=", priority_count)
    print("name_alignment_rows=", name_count)
    print("names_not_in_d6=", reconcile.get("backfill_disease_names_not_in_d6"))
    print("neo4j_written=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
