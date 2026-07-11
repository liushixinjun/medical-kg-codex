from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_anchor_matrix" / "textbook_skeleton_matrix_priority_four_20260708.csv"
DEFAULT_OUT = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_definition_delta"


REQUIRED_STATUS = "ready_for_import_after_sampling"


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"N\s*O\s*T\s*E\s*S", "", text, flags=re.IGNORECASE).strip()
    return text


def looks_header_only(text: str) -> bool:
    text = clean_text(text)
    if len(text) < 16:
        return True
    if re.match(r"^第[一二三四五六七八九十百]+[章节]\s*\|?\s*", text) and not any(x in text for x in ["是", "指", "称为", "特点"]):
        return True
    return False


def read_matrix(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate_row(row: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if row.get("match_status") != REQUIRED_STATUS:
        errors.append("status_not_ready_for_import")
    if not row.get("disease_code"):
        errors.append("missing_disease_code")
    if not row.get("disease_name"):
        errors.append("missing_disease_name")
    definition = clean_text(row.get("definition_candidate", ""))
    if not definition:
        errors.append("missing_definition")
    if looks_header_only(definition):
        errors.append("header_only_definition")
    if any(bad in definition for bad in ["本章数字资源", "N O T E S", "NOTE S"]):
        errors.append("definition_noise_text")
    if len(definition) > 650:
        errors.append("definition_too_long")
    if not row.get("source_section_path"):
        errors.append("missing_source_section_path")
    if row.get("skeleton_slot") != "overview":
        errors.append("skeleton_slot_not_overview")
    if row.get("knowledge_layer") != "textbook_core":
        errors.append("knowledge_layer_not_textbook_core")
    for field in ["docx_paragraph_start", "docx_paragraph_end", "pdf_page_start", "pdf_page_end"]:
        value = str(row.get(field, "")).strip()
        if not value.isdigit():
            errors.append(f"missing_or_invalid_{field}")
    if row.get("match_type") == "body_mention":
        errors.append("body_mention_not_allowed")
    if row.get("match_type") == "combined_title":
        errors.append("combined_title_not_allowed")
    return errors


def build_delta(row: dict[str, str], generated_at: str) -> dict[str, object]:
    return {
        "op": "update_disease_textbook_definition",
        "match": {
            "label": "Disease",
            "property": "code",
            "value": row["disease_code"],
        },
        "set": {
            "definition": clean_text(row["definition_candidate"]),
            "description": clean_text(row["description_candidate"]),
            "definition_source_type": "authoritative_textbook",
            "definition_source_name": "《内科学（第10版）》",
            "definition_source_section_path": row["source_section_path"],
            "definition_docx_paragraph_start": int(row["docx_paragraph_start"]),
            "definition_docx_paragraph_end": int(row["docx_paragraph_end"]),
            "definition_pdf_page_start": int(row["pdf_page_start"]),
            "definition_pdf_page_end": int(row["pdf_page_end"]),
            "definition_skeleton_slot": "overview",
            "definition_knowledge_layer": "textbook_core",
            "textbook_anchor_status": "ready_for_import_after_sampling",
            "textbook_anchor_generated_at": generated_at,
        },
        "source_matrix": {
            "match_type": row["match_type"],
            "match_score": row["match_score"],
            "hit_text": row["hit_text"],
            "source_section_path": row["source_section_path"],
        },
    }


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build strict Neo4j delta for textbook-core disease definitions.")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = read_matrix(args.matrix)
    selected = [r for r in rows if r.get("match_status") == REQUIRED_STATUS]

    detail_rows: list[dict[str, object]] = []
    deltas: list[dict[str, object]] = []
    seen: set[str] = set()
    duplicate_codes: set[str] = set()
    blocking_errors: list[dict[str, object]] = []

    for row in selected:
        code = row["disease_code"]
        errors = validate_row(row)
        if code in seen:
            errors.append("duplicate_disease_code")
            duplicate_codes.add(code)
        seen.add(code)
        detail = {
            "disease_code": code,
            "disease_name": row["disease_name"],
            "match_status": row["match_status"],
            "match_type": row["match_type"],
            "source_section_path": row["source_section_path"],
            "definition_preview": clean_text(row["definition_candidate"])[:220],
            "errors": "|".join(errors),
            "validation_status": "failed" if errors else "passed",
        }
        detail_rows.append(detail)
        if errors:
            blocking_errors.append(detail)
        else:
            deltas.append(build_delta(row, generated_at))

    args.out.mkdir(parents=True, exist_ok=True)
    delta_path = args.out / "delta_disease_definition_update_ready25_20260708.jsonl"
    with delta_path.open("w", encoding="utf-8") as f:
        for item in deltas:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    write_csv(
        args.out / "preimport_validation_detail_ready25_20260708.csv",
        detail_rows,
        ["disease_code", "disease_name", "match_status", "match_type", "source_section_path", "definition_preview", "errors", "validation_status"],
    )

    cypher = """// 教材骨架 Disease.definition 更新脚本
// 用法：读取 delta_disease_definition_update_ready25_20260708.jsonl 中每行 set 对象为 rows 参数。
// 本脚本只更新既有 Disease 节点，不创建新疾病。
UNWIND $rows AS row
MATCH (d:Disease {code: row.disease_code})
SET d.definition = row.definition,
    d.description = CASE WHEN row.description IS NOT NULL AND trim(row.description) <> '' THEN row.description ELSE d.description END,
    d.definition_source_type = row.definition_source_type,
    d.definition_source_name = row.definition_source_name,
    d.definition_source_section_path = row.definition_source_section_path,
    d.definition_docx_paragraph_start = row.definition_docx_paragraph_start,
    d.definition_docx_paragraph_end = row.definition_docx_paragraph_end,
    d.definition_pdf_page_start = row.definition_pdf_page_start,
    d.definition_pdf_page_end = row.definition_pdf_page_end,
    d.definition_skeleton_slot = row.definition_skeleton_slot,
    d.definition_knowledge_layer = row.definition_knowledge_layer,
    d.textbook_anchor_status = row.textbook_anchor_status,
    d.textbook_anchor_generated_at = row.textbook_anchor_generated_at
RETURN count(d) AS updated_count;
"""
    (args.out / "neo4j_update_disease_definition_ready25_20260708.cypher").write_text(cypher, encoding="utf-8")

    summary = {
        "generated_at": generated_at,
        "matrix": str(args.matrix),
        "selected_status": REQUIRED_STATUS,
        "selected_count": len(selected),
        "delta_count": len(deltas),
        "blocking_error_count": len(blocking_errors),
        "duplicate_code_count": len(duplicate_codes),
        "preimport_gate_status": "passed" if not blocking_errors and len(deltas) == len(selected) else "failed",
        "outputs": {
            "delta_jsonl": str(delta_path),
            "validation_detail_csv": str(args.out / "preimport_validation_detail_ready25_20260708.csv"),
            "cypher": str(args.out / "neo4j_update_disease_definition_ready25_20260708.cypher"),
        },
        "blocking_errors": blocking_errors[:50],
    }
    (args.out / "preimport_validation_summary_ready25_20260708.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    readme = f"""# 教材 definition 修复 delta 包

生成时间：{generated_at}

本目录只包含 `textbook_skeleton_matrix_priority_four_20260708.csv` 中状态为 `{REQUIRED_STATUS}` 的疾病 definition 修复项。

## 校验结果

```text
候选数：{len(selected)}
delta 数：{len(deltas)}
阻断错误数：{len(blocking_errors)}
导入前硬闸门：{summary['preimport_gate_status']}
```

## 文件

| 文件 | 用途 |
|---|---|
| `delta_disease_definition_update_ready25_20260708.jsonl` | Neo4j 更新输入，只包含通过导入前校验的疾病 definition。 |
| `preimport_validation_detail_ready25_20260708.csv` | 每条候选的导入前校验明细。 |
| `preimport_validation_summary_ready25_20260708.json` | 汇总结果。 |
| `neo4j_update_disease_definition_ready25_20260708.cypher` | 参数化 Cypher 模板；当前未执行。 |

## 当前策略

本轮只生成 delta 和校验，不直接写服务器。待确认后，再把 JSONL 转换为参数 rows 写入 Neo4j 测试库，并运行 definition 空值、来源错配、章节锚点、`skeleton_slot`、`knowledge_layer` 等硬闸门。
"""
    (args.out / "README_delta说明.md").write_text(readme, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["preimport_gate_status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
