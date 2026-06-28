from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _as_paths(values: list[str | Path]) -> list[Path]:
    return [Path(value) for value in values if str(value).strip()]


def build_preflight_report(
    *,
    specialty: str,
    scope_type: str,
    scope_target: str,
    source_roots: list[Path],
    textbook_roots: list[Path],
    output_root: Path,
    schema_path: Path | None = None,
    skill_path: Path | None = None,
) -> dict[str, Any]:
    missing_required_fields: list[str] = []
    for field_name, value in (
        ("specialty", specialty),
        ("scope_type", scope_type),
        ("scope_target", scope_target),
        ("source_roots", source_roots),
        ("output_root", output_root),
    ):
        if value in (None, "", []):
            missing_required_fields.append(field_name)

    checked_paths = list(source_roots) + list(textbook_roots)
    if output_root:
        checked_paths.append(output_root)
    if schema_path:
        checked_paths.append(schema_path)
    if skill_path:
        checked_paths.append(skill_path)

    missing_paths = [str(path) for path in checked_paths if not path.exists()]
    warnings: list[str] = []
    if not textbook_roots:
        warnings.append("未提供教材/基础骨架来源路径；如果是从0开始的新专科，应先完成基础骨架。")
    if schema_path and schema_path.name != "专科知识图谱Schema标准.md":
        warnings.append("Schema主文件名不是“专科知识图谱Schema标准.md”，请确认不是历史版本。")
    if skill_path and skill_path.name != "AI自动化工具-文献指南解析.md":
        warnings.append("SKILL主文件名不是“AI自动化工具-文献指南解析.md”，请确认不是历史版本。")

    status = "pass" if not missing_required_fields and not missing_paths else "fail"
    return {
        "status": status,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "specialty": specialty,
        "scope_type": scope_type,
        "scope_target": scope_target,
        "source_roots": [str(path) for path in source_roots],
        "textbook_roots": [str(path) for path in textbook_roots],
        "output_root": str(output_root) if output_root else "",
        "schema_path": str(schema_path) if schema_path else "",
        "skill_path": str(skill_path) if skill_path else "",
        "missing_required_fields": missing_required_fields,
        "missing_paths": missing_paths,
        "warnings": warnings,
        "required_next_outputs": [
            "source_manifest/使用PDF清单",
            "local_graph_jsonl/nodes_final.jsonl",
            "local_graph_jsonl/relations_final.jsonl",
            "quality_audit/quality_gate_summary.json",
            "delta_import_package/delta_manifest.json",
            "delta_import_package/delta_nodes_upsert.jsonl",
            "delta_import_package/delta_relations_add.jsonl",
            "claude_review_pack/审核包",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight checklist before starting a new specialty KG disease batch.")
    parser.add_argument("--specialty", required=True, help="顶层学科，例如：心血管内科")
    parser.add_argument("--scope-type", required=True, help="执行范围类型，例如：疾病大类 / 单病种")
    parser.add_argument("--scope-target", required=True, help="目标疾病范围，例如：冠心病")
    parser.add_argument("--source-root", action="append", default=[], help="PDF/指南来源路径，可重复")
    parser.add_argument("--textbook-root", action="append", default=[], help="教材/基础骨架来源路径，可重复")
    parser.add_argument("--output-root", required=True, type=Path, help="本批次输出路径")
    parser.add_argument("--schema-path", type=Path)
    parser.add_argument("--skill-path", type=Path)
    parser.add_argument("--out-json", type=Path, required=True)
    args = parser.parse_args()

    report = build_preflight_report(
        specialty=args.specialty,
        scope_type=args.scope_type,
        scope_target=args.scope_target,
        source_roots=_as_paths(args.source_root),
        textbook_roots=_as_paths(args.textbook_root),
        output_root=args.output_root,
        schema_path=args.schema_path,
        skill_path=args.skill_path,
    )
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
