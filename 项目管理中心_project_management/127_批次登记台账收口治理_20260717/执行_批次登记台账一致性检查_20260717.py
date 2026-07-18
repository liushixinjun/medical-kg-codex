from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "127_批次登记台账收口治理_20260717"
CSV_LEDGER = ROOT / "项目管理中心_project_management" / "04_批次登记台账_batch_ledger.csv"
MD_LEDGER = ROOT / "心血管内科文献集合" / "批次登记台账.md"

REQUIRED_LATEST_BATCH_IDS = [
    "20260716_内科学心血管骨架V1冻结",
    "20260716_内科学心血管骨架V1.1临床可推理层下钻",
    "20260716_内科学心血管骨架V1.2章节级证据精修",
    "20260717_指南PDF精修层全库总检",
    "20260717_批次登记台账收口治理",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_csv_rows(CSV_LEDGER)
    md_text = MD_LEDGER.read_text(encoding="utf-8")

    diff_rows: list[dict[str, object]] = []
    missing_in_md = 0
    missing_output_path = 0
    empty_output_path = 0
    duplicate_ids: dict[str, int] = {}
    seen: dict[str, int] = {}

    for row in rows:
        batch_id = (row.get("batch_id") or "").strip()
        seen[batch_id] = seen.get(batch_id, 0) + 1
    duplicate_ids = {k: v for k, v in seen.items() if k and v > 1}

    for row in rows:
        batch_id = (row.get("batch_id") or "").strip()
        output_path = (row.get("输出路径") or "").strip()
        present_in_md = "是" if batch_id and batch_id in md_text else "否"
        if present_in_md == "否":
            missing_in_md += 1
        if not output_path:
            empty_output_path += 1
            output_exists = "空"
        else:
            output_exists = "是" if Path(output_path).exists() else "否"
            if output_exists == "否":
                missing_output_path += 1

        diff_rows.append(
            {
                "batch_id": batch_id,
                "学科": row.get("学科", ""),
                "疾病大类": row.get("疾病大类", ""),
                "状态": row.get("状态", ""),
                "是否写Neo4j": row.get("是否写Neo4j", ""),
                "CSV输出路径": output_path,
                "MD是否登记": present_in_md,
                "输出路径是否存在": output_exists,
                "备注": row.get("备注", ""),
            }
        )

    latest_rows = []
    latest_missing_csv = 0
    latest_missing_md = 0
    csv_ids = {str(r.get("batch_id", "")).strip() for r in rows}
    for batch_id in REQUIRED_LATEST_BATCH_IDS:
        in_csv = batch_id in csv_ids
        in_md = batch_id in md_text
        if not in_csv:
            latest_missing_csv += 1
        if not in_md:
            latest_missing_md += 1
        latest_rows.append({"batch_id": batch_id, "CSV是否登记": "是" if in_csv else "否", "MD是否登记": "是" if in_md else "否"})

    write_csv(
        OUT_DIR / "01_MD与CSV台账差异清单_20260717.csv",
        diff_rows,
        ["batch_id", "学科", "疾病大类", "状态", "是否写Neo4j", "CSV输出路径", "MD是否登记", "输出路径是否存在", "备注"],
    )
    write_csv(
        OUT_DIR / "02_最新关键批次登记复核_20260717.csv",
        latest_rows,
        ["batch_id", "CSV是否登记", "MD是否登记"],
    )
    (OUT_DIR / "03_补齐后的批次登记台账快照_20260717.md").write_text(md_text, encoding="utf-8")

    summary = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "csv_ledger": str(CSV_LEDGER),
        "md_ledger": str(MD_LEDGER),
        "csv_batch_count": len(rows),
        "md_heading_count": md_text.count("\n## "),
        "missing_in_md_count": missing_in_md,
        "empty_output_path_count": empty_output_path,
        "missing_output_path_count": missing_output_path,
        "duplicate_batch_id_count": len(duplicate_ids),
        "latest_required_missing_csv_count": latest_missing_csv,
        "latest_required_missing_md_count": latest_missing_md,
        "latest_required_batch_ids": REQUIRED_LATEST_BATCH_IDS,
        "neo4j_written": False,
    }
    (OUT_DIR / "04_台账一致性检查_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_lines = [
        "# 批次登记台账收口治理报告（2026-07-17）",
        "",
        "## 1. 本次检查范围",
        "",
        f"- Markdown 台账：`{MD_LEDGER}`",
        f"- CSV 台账：`{CSV_LEDGER}`",
        "- 本次写 Neo4j：否",
        "",
        "## 2. 检查结果",
        "",
        f"- CSV 登记批次数：{len(rows)}",
        f"- Markdown 二级标题数：{summary['md_heading_count']}",
        f"- CSV 有但 Markdown 未登记：{missing_in_md}",
        f"- CSV 输出路径为空：{empty_output_path}",
        f"- CSV 输出路径不存在：{missing_output_path}",
        f"- 重复 batch_id：{len(duplicate_ids)}",
        f"- 最新关键批次 CSV 缺失：{latest_missing_csv}",
        f"- 最新关键批次 Markdown 缺失：{latest_missing_md}",
        "",
        "## 3. 结论",
        "",
    ]
    if latest_missing_csv == 0 and latest_missing_md == 0:
        report_lines.append("- 最新关键批次已经同时登记到 CSV 与 Markdown。")
    else:
        report_lines.append("- 最新关键批次仍有缺登记，必须先补齐再继续后续批次。")
    if missing_in_md:
        report_lines.append("- 仍存在 CSV 已有但 Markdown 未登记的历史批次，需要补登记索引；不影响当前精修执行，但会影响长期复盘。")
    else:
        report_lines.append("- CSV 与 Markdown 已无 batch_id 级别登记缺口。")
    if missing_output_path:
        report_lines.append("- 仍存在输出路径不存在记录，后续应结合历史迁移或废弃清单处理。")

    report_lines += [
        "",
        "## 4. 输出文件",
        "",
        "- `01_MD与CSV台账差异清单_20260717.csv`",
        "- `02_最新关键批次登记复核_20260717.csv`",
        "- `03_补齐后的批次登记台账快照_20260717.md`",
        "- `04_台账一致性检查_summary.json`",
        "",
        "## 5. 后续硬规则",
        "",
        "每个批次结束时必须同时更新：Markdown 台账、CSV 台账、步骤记录、踩坑日志；不得只在聊天中记录。",
    ]

    (OUT_DIR / "00_批次登记台账收口治理报告_20260717.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
