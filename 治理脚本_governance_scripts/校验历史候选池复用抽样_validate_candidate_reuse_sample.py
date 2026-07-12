# -*- coding: utf-8 -*-
"""校验历史候选池复用抽样核查产物。

只读本地文件，不连接 Neo4j。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = "20260712"
OUT_DIR = ROOT / "骨架质量闭环_skeleton_quality_loop" / f"{RUN_DATE}_历史候选池复用抽样核查"

SUMMARY = OUT_DIR / f"历史候选池复用抽样核查_summary_{RUN_DATE}.json"
PRECHECK = OUT_DIR / f"历史候选池可复用性机器预审明细_{RUN_DATE}.csv"
SAMPLE = OUT_DIR / f"历史候选池可复用性分层抽样_{RUN_DATE}.csv"
RISK_DIST = OUT_DIR / f"历史候选池复用风险分布_{RUN_DATE}.csv"
REPORT = OUT_DIR / f"历史候选池复用抽样核查报告_{RUN_DATE}.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fail(message: str) -> int:
    print(f"VALIDATION_FAILED: {message}")
    return 1


def main() -> int:
    required = [SUMMARY, PRECHECK, SAMPLE, RISK_DIST, REPORT]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        return fail("missing files: " + "；".join(missing))

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if summary.get("neo4j_written") is not False:
        return fail("neo4j_written must be false")
    if summary.get("delta_generated") is not False:
        return fail("delta_generated must be false")

    decision = summary.get("decision", {})
    if decision.get("direct_batch_reuse_allowed") is not False:
        return fail("direct_batch_reuse_allowed must be false")

    counts = summary.get("counts", {})
    if int(counts.get("mergeable_input_rows", 0)) <= 0:
        return fail("mergeable_input_rows must be positive")
    if int(counts.get("sample_rows", 0)) < 100:
        return fail("sample_rows must be at least 100")

    precheck_rows = read_csv(PRECHECK)
    sample_rows = read_csv(SAMPLE)
    risk_rows = read_csv(RISK_DIST)

    if len(precheck_rows) != int(counts.get("mergeable_input_rows", -1)):
        return fail("precheck row count mismatch")
    if len(sample_rows) != int(counts.get("sample_rows", -1)):
        return fail("sample row count mismatch")
    if not risk_rows:
        return fail("risk distribution is empty")

    forbidden_direct = [
        r for r in precheck_rows if r.get("machine_precheck_decision") in {"可直接入库", "可直接生成delta"}
    ]
    if forbidden_direct:
        return fail("precheck contains direct import decision")

    if not any(r.get("machine_precheck_decision") == "仅作重抽取线索" for r in precheck_rows):
        return fail("precheck should contain clue-only rows")
    if not any(r.get("machine_precheck_decision") == "不建议复用" for r in precheck_rows):
        return fail("precheck should contain reject rows")

    print("VALIDATION_OK")
    print("precheck_rows=", len(precheck_rows))
    print("sample_rows=", len(sample_rows))
    print("direct_batch_reuse_allowed=false")
    print("neo4j_written=false")
    print("delta_generated=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
