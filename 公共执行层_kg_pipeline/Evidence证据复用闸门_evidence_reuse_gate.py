from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def evidence_key(row: dict[str, Any]) -> str:
    raw = "|".join(
        [
            normalize_text(row.get("source_name", "")).lower(),
            str(row.get("source_page", "N/A") or "N/A").strip(),
            normalize_text(row.get("evidence_text", "")),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()


def shared_code(key: str) -> str:
    return f"EVD-SHARED-{key[:24]}"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_gate(batch_output_dir: Path, output_dir: Path) -> dict[str, Any]:
    nodes_path = batch_output_dir / "05_data_instance" / "nodes_final.jsonl"
    nodes = load_jsonl(nodes_path)
    evidence_nodes = [row for row in nodes if row.get("entityType") == "Evidence"]

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_key_rows = []
    non_shared_code_rows = []
    wrong_shared_code_rows = []

    for row in evidence_nodes:
        key = str(row.get("evidence_key") or evidence_key(row))
        groups[key].append(row)
        expected_code = shared_code(key)
        if not row.get("evidence_key"):
            missing_key_rows.append({"code": row.get("code", ""), "source_name": row.get("source_name", ""), "source_page": row.get("source_page", "")})
        if not str(row.get("code", "")).startswith("EVD-SHARED-"):
            non_shared_code_rows.append({"code": row.get("code", ""), "expected_code": expected_code, "source_name": row.get("source_name", ""), "source_page": row.get("source_page", "")})
        if str(row.get("code", "")) != expected_code:
            wrong_shared_code_rows.append({"code": row.get("code", ""), "expected_code": expected_code, "source_name": row.get("source_name", ""), "source_page": row.get("source_page", "")})

    duplicate_groups = []
    for key, items in groups.items():
        codes = sorted({str(item.get("code", "")) for item in items})
        if len(codes) > 1:
            duplicate_groups.append(
                {
                    "evidence_key": key,
                    "expected_code": shared_code(key),
                    "node_count": len(items),
                    "distinct_code_count": len(codes),
                    "codes": "；".join(codes),
                    "source_name": items[0].get("source_name", ""),
                    "source_page": items[0].get("source_page", ""),
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "Evidence重复证据组明细.csv", duplicate_groups)
    write_csv(output_dir / "Evidence缺少唯一键明细.csv", missing_key_rows)
    write_csv(output_dir / "Evidence非共享编号明细.csv", non_shared_code_rows)
    write_csv(output_dir / "Evidence共享编号不一致明细.csv", wrong_shared_code_rows)

    summary = {
        "gate_name": "Evidence证据复用闸门",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nodes_path": str(nodes_path),
        "evidence_node_count": len(evidence_nodes),
        "duplicate_evidence_key_group_count": len(duplicate_groups),
        "missing_evidence_key_count": len(missing_key_rows),
        "non_shared_evidence_code_count": len(non_shared_code_rows),
        "wrong_shared_evidence_code_count": len(wrong_shared_code_rows),
    }
    blocking_count = (
        summary["duplicate_evidence_key_group_count"]
        + summary["missing_evidence_key_count"]
        + summary["non_shared_evidence_code_count"]
        + summary["wrong_shared_evidence_code_count"]
    )
    summary["gate_status"] = "passed" if blocking_count == 0 else "failed"
    summary["blocking_issue_count"] = blocking_count
    (output_dir / "Evidence证据复用闸门_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="检查本地批次 Evidence 是否按主证据唯一键复用。")
    parser.add_argument("--batch-output-dir", type=Path, required=True, help="本批次输出目录")
    parser.add_argument("--output-dir", type=Path, required=True, help="闸门输出目录")
    parser.add_argument("--fail-on-blocking", action="store_true")
    args = parser.parse_args()
    summary = run_gate(args.batch_output_dir, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.fail_on_blocking and summary["gate_status"] != "passed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
