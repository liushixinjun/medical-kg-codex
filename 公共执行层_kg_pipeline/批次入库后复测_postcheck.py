from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MASTER_DATA_GATE_PATH = ROOT / "公共执行层_kg_pipeline" / "主数据质量闸门_master_data_gate.py"


@dataclass(frozen=True)
class PostcheckPaths:
    root: Path
    master_data_gate_dir: Path
    summary_path: Path
    report_path: Path


def load_master_data_gate_module():
    spec = importlib.util.spec_from_file_location("master_data_gate_for_postcheck", MASTER_DATA_GATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载主数据质量闸门脚本：{MASTER_DATA_GATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_postcheck_paths(batch_output_dir: Path) -> PostcheckPaths:
    root = batch_output_dir / "99_入库后复测"
    return PostcheckPaths(
        root=root,
        master_data_gate_dir=root / "01_主数据质量闸门",
        summary_path=root / "00_入库后复测总览.json",
        report_path=root / "00_入库后复测报告.md",
    )


def summarize_postcheck(batch_id: str, master_data_summary: dict[str, Any]) -> dict[str, Any]:
    master_status = master_data_summary.get("gate_status")
    master_blocking_count = int(master_data_summary.get("blocking_issue_count") or 0)
    blocking_gates = []
    if master_status != "passed" or master_blocking_count > 0:
        blocking_gates.append("主数据质量闸门")

    status = "passed" if not blocking_gates else "failed"
    return {
        "batch_id": batch_id,
        "postcheck_name": "批次入库后复测",
        "postcheck_status": status,
        "postcheck_status_cn": "通过" if status == "passed" else "未通过",
        "blocking_issue_count": master_blocking_count,
        "blocking_gates": blocking_gates,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "checks": {
            "主数据质量闸门": {
                "status": master_status,
                "status_cn": master_data_summary.get("gate_status_cn", master_status),
                "blocking_issue_count": master_blocking_count,
                "counts": master_data_summary.get("counts", {}),
            }
        },
    }


def write_postcheck_report(path: Path, summary: dict[str, Any], paths: PostcheckPaths) -> None:
    lines = [
        "# 批次入库后复测报告",
        "",
        f"- 批次编号：{summary['batch_id']}",
        f"- 生成时间：{summary['generated_at']}",
        f"- 复测状态：{summary.get('postcheck_status_cn', summary['postcheck_status'])}",
        f"- 阻断项数量：{summary['blocking_issue_count']}",
        "",
        "## 本轮固定复测项",
        "",
        "| 复测项 | 状态 | 阻断项 | 输出目录 |",
        "|---|---|---:|---|",
    ]
    master = summary["checks"]["主数据质量闸门"]
    lines.append(
        f"| 主数据质量闸门 | {master.get('status_cn', master['status'])} | {master['blocking_issue_count']} | `{paths.master_data_gate_dir}` |"
    )
    lines.extend(["", "## 结论", ""])
    if summary["postcheck_status"] == "passed":
        lines.append("本批次入库后复测通过，可以进入批次验收报告或下一批次准备。")
    else:
        lines.append("本批次入库后复测未通过，必须先修复阻断项，不得转正式 CDSS 或继续叠加新数据。")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_postcheck(
    *,
    batch_id: str,
    batch_output_dir: Path,
    connection_file: Path,
    database: str = "neo4j",
) -> dict[str, Any]:
    paths = build_postcheck_paths(batch_output_dir)
    paths.root.mkdir(parents=True, exist_ok=True)

    master_gate = load_master_data_gate_module()
    master_summary = master_gate.run_gate(connection_file, paths.master_data_gate_dir, database)

    summary = summarize_postcheck(batch_id, master_summary)
    summary["output_dir"] = str(paths.root)
    summary["master_data_gate_output_dir"] = str(paths.master_data_gate_dir)
    paths.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_postcheck_report(paths.report_path, summary, paths)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="批次入库后复测：统一执行服务器入库后的质量闸门。")
    parser.add_argument("--batch-id", required=True, help="批次编号，例如 BATCH-CARD-CAD-20260714-001。")
    parser.add_argument("--batch-output-dir", type=Path, required=True, help="本批次输出目录。")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--database", default="neo4j")
    parser.add_argument(
        "--allow-blocking-exit-zero",
        action="store_true",
        help="发现阻断项时仍返回 0，仅用于人工排查；正式流程不要使用。",
    )
    args = parser.parse_args()

    summary = run_postcheck(
        batch_id=args.batch_id,
        batch_output_dir=args.batch_output_dir,
        connection_file=args.connection_file,
        database=args.database,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["postcheck_status"] != "passed" and not args.allow_blocking_exit_zero:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
