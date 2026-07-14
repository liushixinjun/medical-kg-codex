# -*- coding: utf-8 -*-
"""冠心病 V2.1 回归验证。

只读校验并生成本地审计报告；不连接 Neo4j，不写数据库。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "心血管内科文献集合"
    / "BATCH-CARD-CAD-V21-REGRESSION-20260712-001_冠心病_V21回归验证"
)
SOURCE_BATCH = ROOT / "心血管内科文献集合" / "BATCH-CARD-CAD-20260623-001"
EXPECTED_DISEASES = {
    "急性冠脉综合征",
    "急性心肌梗死",
    "ST段抬高型心肌梗死",
    "非ST段抬高型心肌梗死",
    "不稳定型心绞痛",
    "慢性冠脉综合征",
    "稳定型心绞痛",
    "缺血性心肌病",
    "陈旧性心肌梗死",
    "隐匿性冠心病",
}
CURRENT_SCHEMA_VERSION = "V1.15"
CURRENT_SKILL_VERSION = "V2.1 收尾版"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def add_failure(failures: list[dict[str, str]], item: str, detail: str) -> None:
    failures.append({"级别": "阻断", "项目": item, "问题": detail})


def add_warning(warnings: list[dict[str, str]], item: str, detail: str) -> None:
    warnings.append({"级别": "提醒", "项目": item, "问题": detail})


def suspicious_evidence_text(text: str) -> bool:
    if not text:
        return True
    return bool(re.search(r"[�□\u0590-\u05ff\u0600-\u06ff]", text))


def validate(output_dir: Path) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    config_path = output_dir / "00_config" / "batch_config.json"
    quality_path = output_dir / "02_audit" / "quality_audit_summary.json"
    nodes_path = output_dir / "01_delta" / "delta_nodes_upsert.jsonl"
    rels_path = output_dir / "01_delta" / "delta_relations_add.jsonl"
    rec_matrix_path = output_dir / "02_audit" / "cdss_recommendation_statement_matrix.csv"
    action_matrix_path = output_dir / "02_audit" / "cdss_pathway_rule_action_matrix.csv"
    legacy_readiness_path = SOURCE_BATCH / "06_quality_audit" / "cdss_recommendation_readiness_register.csv"
    source_manifest_path = SOURCE_BATCH / "01_source_manifest" / "source_documents_manifest.csv"
    parse_summary_path = SOURCE_BATCH / "02_page_audit" / "pdf_parse_summary.json"

    required_files = [
        config_path,
        quality_path,
        nodes_path,
        rels_path,
        rec_matrix_path,
        action_matrix_path,
        legacy_readiness_path,
        source_manifest_path,
        parse_summary_path,
    ]
    for path in required_files:
        if not path.exists():
            add_failure(failures, "文件存在性", f"缺少文件：{path}")
    if failures:
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "hard_gate_pass": False,
            "failures": failures,
            "warnings": warnings,
        }

    config = read_json(config_path)
    quality = read_json(quality_path)
    nodes = read_jsonl(nodes_path)
    rels = read_jsonl(rels_path)
    rec_rows = read_csv(rec_matrix_path)
    action_rows = read_csv(action_matrix_path)
    legacy_rows = read_csv(legacy_readiness_path)
    source_rows = read_csv(source_manifest_path)
    parse_summary = read_json(parse_summary_path)

    if config.get("schema_version") != CURRENT_SCHEMA_VERSION:
        add_failure(failures, "Schema版本", f"batch_config={config.get('schema_version')}")
    if config.get("skill_version") != CURRENT_SKILL_VERSION:
        add_failure(failures, "SKILL版本", f"batch_config={config.get('skill_version')}")
    if config.get("neo4j_action") != "none":
        add_failure(failures, "写库权限", f"neo4j_action 必须为 none，当前={config.get('neo4j_action')}")
    if not quality.get("hard_gate_pass"):
        add_failure(failures, "原始生成质量门", "quality_audit_summary.hard_gate_pass=false")

    node_counter = Counter(node.get("entityType", "") for node in nodes)
    rel_counter = Counter(rel.get("relationType", "") for rel in rels)
    if node_counter.get("RecommendationStatement", 0) != len(rec_rows):
        add_failure(
            failures,
            "推荐陈述数量",
            f"RecommendationStatement={node_counter.get('RecommendationStatement', 0)}，矩阵={len(rec_rows)}",
        )
    if node_counter.get("ClinicalPathway", 0) != 10:
        add_failure(failures, "路径数量", f"ClinicalPathway 应为10，当前={node_counter.get('ClinicalPathway', 0)}")

    version_bad_nodes = [
        node.get("code", "")
        for node in nodes
        if node.get("schema_version") != CURRENT_SCHEMA_VERSION or node.get("skill_version") != CURRENT_SKILL_VERSION
    ]
    version_bad_rels = [
        rel.get("id", "")
        for rel in rels
        if rel.get("schema_version") != CURRENT_SCHEMA_VERSION or rel.get("skill_version") != CURRENT_SKILL_VERSION
    ]
    if version_bad_nodes:
        add_failure(failures, "节点版本字段", f"异常节点数={len(version_bad_nodes)}")
    if version_bad_rels:
        add_failure(failures, "关系版本字段", f"异常关系数={len(version_bad_rels)}")

    for rel in rels:
        relation_type = rel.get("relationType")
        source = str(rel.get("source_code", ""))
        evidence_count = int(rel.get("evidence_count") or 0)
        if relation_type == "has_recommended_action" and not source.startswith("STAGE-"):
            add_failure(failures, "关系语义", f"has_recommended_action 必须从 PathwayStage 发出：{rel.get('id')}")
        if relation_type in {"recommends_action", "blocks_action"} and not (
            source.startswith("RULE-") or source.startswith("REC-")
        ):
            add_failure(
                failures,
                "关系语义",
                f"{relation_type} 必须从 ClinicalRule 或 RecommendationStatement 发出：{rel.get('id')}",
            )
        if relation_type in {"has_stage_rule", "has_recommended_action", "recommends_action", "blocks_action"} and evidence_count <= 0:
            add_failure(failures, "证据链", f"{relation_type} 缺 evidence_ids：{rel.get('id')}")

    rec_audit_rows: list[dict[str, Any]] = []
    for row in rec_rows:
        row_failures: list[str] = []
        row_warnings: list[str] = []
        if not present(row.get("推荐陈述")):
            row_failures.append("缺推荐陈述")
        if not present(row.get("触发条件")):
            row_failures.append("缺触发条件")
        if not present(row.get("判断逻辑")):
            row_failures.append("缺判断逻辑")
        if not present(row.get("推荐动作")) and not present(row.get("阻断动作")):
            row_failures.append("缺推荐动作/阻断动作")
        if not present(row.get("主证据")):
            row_failures.append("缺主证据")
        if not present(row.get("指南/来源")):
            row_failures.append("缺指南/来源")
        if not present(row.get("页码")):
            row_failures.append("缺页码")
        if not present(row.get("推荐等级")):
            row_failures.append("缺推荐等级")
        if not present(row.get("证据等级")):
            row_failures.append("缺证据等级")
        if not present(row.get("证据摘要")):
            row_failures.append("缺证据摘要")
        elif suspicious_evidence_text(row.get("证据摘要", "")):
            row_warnings.append("证据摘要疑似OCR/编码噪声，建议后续原文复核")

        if row_failures:
            add_failure(failures, "推荐矩阵", f"{row.get('推荐陈述编码')}：" + "；".join(row_failures))
        if row_warnings:
            add_warning(warnings, "推荐矩阵", f"{row.get('推荐陈述编码')}：" + "；".join(row_warnings))
        rec_audit_rows.append(
            {
                "疾病": row.get("疾病", ""),
                "推荐陈述编码": row.get("推荐陈述编码", ""),
                "推荐动作": row.get("推荐动作", ""),
                "阻断动作": row.get("阻断动作", ""),
                "主证据": row.get("主证据", ""),
                "指南/来源": row.get("指南/来源", ""),
                "页码": row.get("页码", ""),
                "推荐等级": row.get("推荐等级", ""),
                "证据等级": row.get("证据等级", ""),
                "审计结论": "阻断" if row_failures else ("提醒" if row_warnings else "通过"),
                "问题": "；".join(row_failures + row_warnings),
            }
        )

    covered_diseases = {row.get("疾病", "") for row in rec_rows}
    missing_diseases = sorted(EXPECTED_DISEASES - covered_diseases)
    if missing_diseases:
        add_failure(failures, "疾病覆盖", "缺少：" + "、".join(missing_diseases))

    legacy_disposition_rows: list[dict[str, Any]] = []
    uncovered_legacy = 0
    for row in legacy_rows:
        disease_name = row.get("source_name", "")
        if disease_name in covered_diseases:
            disposition = "已由V2.1 RecommendationStatement/ClinicalRule路径层承接；旧事实关系不再作为直接CDSS推荐入口"
        else:
            disposition = "疾病未被本轮路径层覆盖，需后续单独复核"
            uncovered_legacy += 1
        legacy_disposition_rows.append(
            {
                "source_code": row.get("source_code", ""),
                "source_name": disease_name,
                "relation_type": row.get("relation_type", ""),
                "target_code": row.get("target_code", ""),
                "target_name": row.get("target_name", ""),
                "missing_fields": row.get("missing_fields", ""),
                "处置结论": disposition,
            }
        )
    if uncovered_legacy:
        add_warning(warnings, "旧readiness缺口", f"仍有{uncovered_legacy}条旧关系未被路径层疾病名覆盖")

    included_pdf_count = sum(
        1
        for row in source_rows
        if row.get("inclusion_status") == "included" and row.get("extension", "").lower() == ".pdf"
    )
    if included_pdf_count <= 0:
        add_failure(failures, "来源清单", "未找到纳入PDF")
    if int(parse_summary.get("ocr_required_page_count") or 0) != 0:
        add_warning(warnings, "OCR", f"ocr_required_page_count={parse_summary.get('ocr_required_page_count')}")

    audit_dir = output_dir / "02_audit"
    report_dir = output_dir / "03_reports"
    write_csv(
        audit_dir / "V21推荐证据链审计.csv",
        rec_audit_rows,
        ["疾病", "推荐陈述编码", "推荐动作", "阻断动作", "主证据", "指南/来源", "页码", "推荐等级", "证据等级", "审计结论", "问题"],
    )
    write_csv(
        audit_dir / "legacy_cdss_readiness_disposition.csv",
        legacy_disposition_rows,
        ["source_code", "source_name", "relation_type", "target_code", "target_name", "missing_fields", "处置结论"],
    )

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "batch_id": config.get("batch_id"),
        "output_dir": str(output_dir),
        "source_batch": str(SOURCE_BATCH),
        "neo4j_written": False,
        "delta_generated": True,
        "hard_gate_pass": not failures,
        "node_count": len(nodes),
        "relation_count": len(rels),
        "node_type_counts": dict(node_counter),
        "relation_type_counts": dict(rel_counter),
        "recommendation_statement_count": len(rec_rows),
        "action_matrix_rows": len(action_rows),
        "covered_disease_count": len(covered_diseases),
        "covered_diseases": sorted(covered_diseases),
        "included_pdf_count": included_pdf_count,
        "legacy_readiness_rows": len(legacy_rows),
        "legacy_readiness_uncovered_rows": uncovered_legacy,
        "warning_count": len(warnings),
        "failure_count": len(failures),
        "failures": failures,
        "warnings": warnings[:50],
    }
    (audit_dir / "V21回归审计_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_dir.mkdir(parents=True, exist_ok=True)
    report_lines = [
        "# 冠心病 V2.1 回归验证报告",
        "",
        f"生成时间：{summary['generated_at']}",
        "",
        "## 1. 结论",
        "",
        f"- G2本地硬闸门：{'通过' if summary['hard_gate_pass'] else '未通过'}",
        "- Neo4j写入：否",
        "- 本轮定位：冠心病 CDSS 决策层回归验证与差量候选准备，不覆盖旧事实层。",
        "",
        "## 2. 核心统计",
        "",
        f"- 新增/待导入节点：{summary['node_count']}",
        f"- 新增/待导入关系：{summary['relation_count']}",
        f"- 推荐陈述：{summary['recommendation_statement_count']}",
        f"- 覆盖疾病：{summary['covered_disease_count']} / 10",
        f"- 纳入PDF来源：{included_pdf_count} 份",
        f"- 旧 readiness 缺口处置：{len(legacy_rows) - uncovered_legacy} / {len(legacy_rows)} 已由路径层承接",
        "",
        "## 3. 阻断项",
        "",
    ]
    if failures:
        report_lines.extend(f"- {item['项目']}：{item['问题']}" for item in failures)
    else:
        report_lines.append("- 无")
    report_lines.extend(["", "## 4. 提醒项", ""])
    if warnings:
        report_lines.extend(f"- {item['项目']}：{item['问题']}" for item in warnings[:20])
    else:
        report_lines.append("- 无")
    report_lines.extend(
        [
            "",
            "## 5. 输出文件",
            "",
            "- `01_delta/delta_nodes_upsert.jsonl`",
            "- `01_delta/delta_relations_add.jsonl`",
            "- `02_audit/V21推荐证据链审计.csv`",
            "- `02_audit/legacy_cdss_readiness_disposition.csv`",
            "- `02_audit/V21回归审计_summary.json`",
            "",
            "## 6. 下一步",
            "",
            "若用户确认进入 G3，则使用本目录下 delta 文件受控导入 Neo4j，并在写库后执行服务器 postcheck。未确认前不得写库。",
        ]
    )
    (report_dir / "冠心病V21回归验证报告_20260712.md").write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CAD V2.1 regression batch without Neo4j writes.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    summary = validate(args.output_dir.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["hard_gate_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
