from __future__ import annotations

import csv
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "130_未解析PDF病种启动池_20260717"
OUTPUT_ROOT = ROOT / "心血管内科文献集合"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

BATCH_IDS = [
    "20260717_冠心病ACS2025补充解析",
    "20260717_瓣膜病指南补充解析",
    "20260717_心律失常指南补充解析",
    "20260717_心肌病ESC2023补充解析",
    "20260717_结构性先心病介入补充解析",
    "20260717_心衰LVAD右心衰补充解析",
    "20260717_高血压LVAD补充解析",
]

sys.path.insert(0, str(ROOT))
from scripts.audit_graph_instance import audit_graph  # noqa: E402
from scripts.build_graph_instance import build_graph_instance  # noqa: E402
from scripts.extract_guideline_evidence import extract_guideline_evidence  # noqa: E402


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for line in f if line.strip())


def run_one(batch_id: str) -> dict[str, Any]:
    batch_dir = OUTPUT_ROOT / batch_id
    row: dict[str, Any] = {
        "batch_id": batch_id,
        "batch_dir": str(batch_dir),
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "neo4j_written": "否",
        "extract_status": "not_started",
        "build_status": "not_started",
        "audit_status": "not_started",
        "evidence_count": 0,
        "node_count": 0,
        "relation_count": 0,
        "blocking_count": "",
        "warning_count": "",
        "error": "",
    }
    try:
        if not batch_dir.is_dir():
            raise FileNotFoundError(f"批次目录不存在：{batch_dir}")
        extract_result = extract_guideline_evidence(batch_dir)
        row["extract_status"] = extract_result.get("status", "completed")
        row["evidence_count"] = extract_result.get("evidence_count", count_jsonl(batch_dir / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl"))

        build_result = build_graph_instance(batch_dir)
        row["build_status"] = build_result.get("status", "completed")
        row["node_count"] = build_result.get("node_count", count_jsonl(batch_dir / "05_data_instance" / "nodes_final.jsonl"))
        row["relation_count"] = build_result.get("relation_count", count_jsonl(batch_dir / "05_data_instance" / "relations_final.jsonl"))

        audit_result = audit_graph(batch_dir)
        row["audit_status"] = audit_result.get("status", "completed")
        row["blocking_count"] = audit_result.get("blocking_count", audit_result.get("error_count", ""))
        row["warning_count"] = audit_result.get("warning_count", "")
    except Exception as exc:  # noqa: BLE001
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["traceback"] = traceback.format_exc(limit=5)
    finally:
        row["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return row


def main() -> int:
    rows = [run_one(batch_id) for batch_id in BATCH_IDS]
    write_csv(OUT_DIR / "05_补充批次证据抽取与本地审计结果_20260717.csv", rows)
    summary = {
        "generated_at": NOW,
        "neo4j_written": False,
        "batch_count": len(rows),
        "extract_completed_count": sum(1 for r in rows if not r.get("error") and r.get("extract_status") != "not_started"),
        "build_completed_count": sum(1 for r in rows if not r.get("error") and r.get("build_status") != "not_started"),
        "audit_completed_count": sum(1 for r in rows if not r.get("error") and r.get("audit_status") != "not_started"),
        "error_count": sum(1 for r in rows if r.get("error")),
        "total_evidence_count": sum(int(r.get("evidence_count") or 0) for r in rows),
        "total_node_count": sum(int(r.get("node_count") or 0) for r in rows),
        "total_relation_count": sum(int(r.get("relation_count") or 0) for r in rows),
    }
    (OUT_DIR / "06_补充批次证据抽取与本地审计_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 补充批次证据抽取与本地审计报告（2026-07-17）",
        "",
        f"- 生成时间：{NOW}",
        "- 本次写 Neo4j：否。",
        f"- 批次数：{summary['batch_count']}",
        f"- 证据抽取完成批次：{summary['extract_completed_count']}",
        f"- 图谱实例生成完成批次：{summary['build_completed_count']}",
        f"- 本地审计完成批次：{summary['audit_completed_count']}",
        f"- 错误批次：{summary['error_count']}",
        f"- 证据总数：{summary['total_evidence_count']}",
        f"- 节点总数：{summary['total_node_count']}",
        f"- 关系总数：{summary['total_relation_count']}",
        "",
        "## 明细文件",
        "",
        "- `05_补充批次证据抽取与本地审计结果_20260717.csv`",
        "- `06_补充批次证据抽取与本地审计_summary.json`",
    ]
    (OUT_DIR / "07_补充批次证据抽取与本地审计报告_20260717.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
