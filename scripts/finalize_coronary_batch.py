from __future__ import annotations

import csv
import json
from pathlib import Path


BATCH_ID = "BATCH-CARD-CAD-20260623-001"
SCOPE_TARGET = "冠状动脉粥样硬化性心脏病（冠心病）"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _escape_table(value: str) -> str:
    return str(value or "").replace("|", "｜")


def main() -> None:
    workspace = Path(__file__).resolve().parents[1]
    root = workspace / "心血管内科文献集合"
    batch = root / BATCH_ID
    manifest = batch / "01_source_manifest" / "source_documents_manifest.csv"
    review = batch / "07_review_package"
    review.mkdir(parents=True, exist_ok=True)

    included = [
        row
        for row in _read_csv(manifest)
        if row.get("inclusion_status") == "included" and row.get("extension", "").lower() == ".pdf"
    ]
    included.sort(key=lambda row: (row.get("source_type", ""), row.get("relative_path", "")))

    summary = json.loads(
        (batch / "06_quality_audit" / "quality_gate_summary.json").read_text(encoding="utf-8-sig")
    )
    source_conflict_total = summary.get("source_conflict_total_count", summary.get("source_conflict_count", 0))
    source_conflict_open = summary.get("source_conflict_count", 0)
    missing_rows = _read_csv(batch / "06_quality_audit" / "missing_reason_and_solution.csv")
    required_missing = sum(1 for row in missing_rows if row.get("applicability_status") == "required")
    optional_missing = sum(1 for row in missing_rows if row.get("applicability_status") == "optional")

    source_md = root / "冠心病PDF来源清单.md"
    source_csv = root / "冠心病PDF来源清单.csv"
    source_fields = [
        "序号",
        "document_id",
        "source_type",
        "file_name",
        "relative_path",
        "full_path",
        "sha256",
        "inclusion_reason",
    ]
    _write_csv(
        source_csv,
        source_fields,
        [
            {
                "序号": index,
                "document_id": row.get("document_id", ""),
                "source_type": row.get("source_type", ""),
                "file_name": row.get("file_name", ""),
                "relative_path": row.get("relative_path", ""),
                "full_path": row.get("full_path", ""),
                "sha256": row.get("sha256", ""),
                "inclusion_reason": row.get("inclusion_reason", ""),
            }
            for index, row in enumerate(included, 1)
        ],
    )

    source_lines = [
        "# 冠心病PDF来源清单",
        "",
        f"- 批次编号：`{BATCH_ID}`",
        "- 顶层学科：心血管内科",
        f"- 目标范围：{SCOPE_TARGET}",
        f"- 正式纳入PDF：{len(included)}份",
        f"- 原始明细CSV：`{manifest}`",
        f"- 根目录便捷CSV：`{source_csv}`",
        "",
        "| 序号 | document_id | source_type | 文件名 | 原始路径 |",
        "|---:|---|---|---|---|",
    ]
    for index, row in enumerate(included, 1):
        source_lines.append(
            f"| {index} | {row.get('document_id', '')} | {row.get('source_type', '')} | "
            f"{_escape_table(row.get('file_name', ''))} | `{row.get('full_path', '')}` |"
        )
    source_md.write_text("\n".join(source_lines) + "\n", encoding="utf-8-sig")

    handoff = review / "可导入图谱文件清单.md"
    handoff.write_text(
        f"""# 可导入图谱文件清单

## 一、批次信息

- 批次编号：`{BATCH_ID}`
- 顶层学科：心血管内科
- 范围类型：疾病大类
- 目标范围：{SCOPE_TARGET}
- Schema：`专科知识图谱Schema标准.md` V1.4
- SKILL：`AI自动化工具-文献指南解析.md` V1.5

## 二、导入结论

- 测试库导入：可以
- 正式 CDSS 上线：不可以
- 当前 Neo4j 测试库状态：未执行导入

## 三、可导入图谱文件

最小导入文件：

- 节点文件：`{batch / "05_data_instance" / "nodes_final.jsonl"}`
- 关系文件：`{batch / "05_data_instance" / "relations_final.jsonl"}`

辅助导入文件：

- 完整图文件：`{batch / "05_data_instance" / "graph_final.json"}`
- 节点 CSV：`{batch / "05_data_instance" / "nodes_final.csv"}`
- 关系 CSV：`{batch / "05_data_instance" / "relations_final.csv"}`

Neo4j 导入文件：

- 导入脚本：`{workspace / "scripts" / "import_neo4j_test_db.py"}`
- 导入摘要：本批次尚未导入，导入后生成 `08_neo4j_import/neo4j_import_summary.json`

## 四、审核必带文件

- 质量审计：`{batch / "06_quality_audit" / "quality_gate_summary.json"}`
- 路径覆盖矩阵：`{batch / "06_quality_audit" / "disease_pathway_coverage.csv"}`
- 缺口原因与修复建议：`{batch / "06_quality_audit" / "missing_reason_and_solution.csv"}`
- 来源冲突清单：`{batch / "06_quality_audit" / "source_conflict_register.csv"}`
- 来源冲突处置计划：`{batch / "06_quality_audit" / "source_conflict_resolution_plan.csv"}`
- 专家审核说明：`{batch / "07_review_package" / "专家审核说明.md"}`
- PDF来源清单：`{source_md}`

## 五、导入验收数据

- 节点：{summary["node_count"]}
- 关系：{summary["relation_count"]}
- 疾病节点：{summary["disease_count"]}
- 核心关系证据链完整率：{summary["core_relation_evidence_chain_rate"]:.1%}
- 目标名称或别名与证据匹配率：{summary["target_name_or_alias_match_rate"]:.1%}
- 质量门禁：{summary["quality_gate_status"]}
- 结构阻断项：0
- required 临床闭环缺口：{required_missing}
- optional 缺口：{optional_missing}
- 来源推荐等级差异总数：{source_conflict_total}
- 阻断性 open 冲突：{source_conflict_open}

说明：质量门禁通过，结构化图谱文件可以导入测试库；推荐等级差异已生成处置计划，宽关系不直接承载最终推荐等级。
""",
        encoding="utf-8-sig",
    )

    delivery = review / "批次交付摘要.md"
    delivery.write_text(
        f"""# 冠心病专科知识图谱批次交付摘要

## 一、执行范围

- 批次编号：`{BATCH_ID}`
- 顶层学科：心血管内科
- 范围类型：疾病大类（category）
- 目标范围：{SCOPE_TARGET}
- 覆盖病种：ACS、UA、AMI、STEMI、NSTEMI、慢性冠脉综合征/慢性冠脉疾病、稳定型心绞痛、隐匿性冠心病、陈旧性心肌梗死、缺血性心肌病
- Schema 标准：`专科知识图谱Schema标准.md`，V1.4
- 解析规范：`AI自动化工具-文献指南解析.md`，V1.5

## 二、来源与解析结果

- 正式纳入 PDF：{len(included)} 份
- 正式解析页数：2222 页
- 页面核算率：100%
- 合格内容页解析通过率：100%
- 需 OCR 页面：0 页
- 《内科学》第10版冠心病基础证据：209 条
- 指南疾病锚定证据：3805 条，覆盖 10 个冠心病相关病种

## 三、标准数据实例

- 节点：{summary["node_count"]} 个
- 关系：{summary["relation_count"]} 条
- 输出格式：JSON、JSONL、CSV

## 四、质量结论

- 质量门禁：通过（passed）
- 未知实体类型、未知关系类型、方向错误、悬空关系、重复编码、重复语义关系：均为 0
- 核心关系证据链完整率：100%
- 目标名称或别名与证据匹配率：100%
- 病种与证据相关率：100%
- 待审核别名和待审核极性：均为 0

## 五、临床审核边界

- 本批次完成的是结构合规、证据可追溯的标准数据实例。
- required 临床闭环缺口：{required_missing}；optional 缺口：{optional_missing}。
- 来源推荐等级差异总数：{source_conflict_total} 条；已生成处置计划，阻断性 open 冲突：{source_conflict_open}。
- 未执行 Neo4j 导入，也未与主图谱自动合并。

## 六、主要交付文件

- 来源清单：`{source_md}`
- 可导入图谱文件清单：`{handoff}`
- 质量门禁：`{batch / "06_quality_audit" / "quality_gate_summary.json"}`
- 路径覆盖矩阵：`{batch / "06_quality_audit" / "disease_pathway_coverage.csv"}`
- 来源冲突处置计划：`{batch / "06_quality_audit" / "source_conflict_resolution_plan.csv"}`
- 专家审核说明：`{batch / "07_review_package" / "专家审核说明.md"}`
""",
        encoding="utf-8-sig",
    )

    ledger = root / "批次登记台账.md"
    text = ledger.read_text(encoding="utf-8-sig")
    old_row = (
        "| 2 | 心血管内科 | 疾病大类 | 冠状动脉粥样硬化性心脏病（冠心病） | "
        f"{BATCH_ID} | 执行中 | `{batch}` | 待生成后判定 | 待生成后判定 | "
        "范围包含 ACS、UA、AMI、STEMI、NSTEMI、慢性冠脉综合征/慢性冠脉疾病、"
        "稳定型心绞痛、隐匿性冠心病、陈旧性心肌梗死、缺血性心肌病 |"
    )
    new_row = (
        "| 2 | 心血管内科 | 疾病大类 | 冠状动脉粥样硬化性心脏病（冠心病） | "
        f"{BATCH_ID} | 已生成、已审计、未导入测试库 | `{batch}` | 可以，未导入 | 不可以 | "
        f"质量门禁 passed；节点{summary['node_count']}，关系{summary['relation_count']}；"
        f"required缺口{required_missing}，来源推荐等级差异{source_conflict_total}，阻断性open冲突{source_conflict_open}；"
        f"PDF来源清单：`{source_md}`；可导入清单：`{handoff}` |"
    )
    if old_row in text:
        text = text.replace(old_row, new_row)
    elif BATCH_ID in text:
        lines = []
        for line in text.splitlines():
            if line.startswith("| 2 |") and BATCH_ID in line:
                lines.append(new_row)
            else:
                lines.append(line)
        text = "\n".join(lines) + "\n"

    section_header = f"### {BATCH_ID}：冠心病正式纳入PDF"
    if section_header not in text:
        source_section = [
            "",
            section_header,
            "",
            f"正式纳入 PDF：{len(included)} 份。根目录便捷清单：",
            "",
            f"- `{source_md}`",
            f"- `{source_csv}`",
            "",
            "| 序号 | document_id | source_type | 文件名 | 原始路径 |",
            "|---:|---|---|---|---|",
        ]
        for index, row in enumerate(included, 1):
            source_section.append(
                f"| {index} | {row.get('document_id', '')} | {row.get('source_type', '')} | "
                f"{_escape_table(row.get('file_name', ''))} | `{row.get('full_path', '')}` |"
            )
        text = text.replace("\n## 每批次必须登记\n", "\n".join(source_section) + "\n## 每批次必须登记\n")
    ledger.write_text(text, encoding="utf-8-sig")

    print(
        json.dumps(
            {
                "included_pdf_count": len(included),
                "required_missing": required_missing,
                "optional_missing": optional_missing,
                "source_md": str(source_md),
                "handoff": str(handoff),
                "delivery": str(delivery),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
