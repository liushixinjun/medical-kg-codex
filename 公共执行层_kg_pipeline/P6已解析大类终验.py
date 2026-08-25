from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
P5_SCRIPT = ROOT / "公共执行层_kg_pipeline" / "P5样板终验.py"


# 只纳入台账明确已经做过教材/指南解析并写入 Neo4j 的大类。
# 仅有骨架、但没有正式解析收口记录的大类暂不混入本轮终验。
TARGET_CATEGORY_CODES = [
    "CAT-CARD-CAD",          # 冠心病
    "CAT-CARD-CM",           # 心肌病
    "CAT-CARD-HF",           # 心力衰竭
    "CAT-CARD-ARR",          # 心律失常
    "CAT-CARD-SCD",          # 心脏骤停与心脏性猝死
    "CAT-CARD-HTN",          # 高血压
    "CAT-CARD-VHD",          # 心脏瓣膜病
    "CAT-CARD-PH",           # 肺动脉高压
    "CAT-CARD-PACING",       # 起搏治疗相关疾病
    "CAT-CARD-CHD",          # 先天性心血管病/结构性心脏病
    "CAT-CARD-AORTA-PAD",    # 主动脉和周围血管病
    "CAT-CARD-PERICARD",     # 心包疾病
    "CAT-CARD-IE",           # 感染性心内膜炎
    "CAT-CARD-LIPID-ASCVD",  # 血脂异常与动脉粥样硬化防治
]


def load_p5_module() -> Any:
    spec = importlib.util.spec_from_file_location("p5_sample_final_check", P5_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 P5 脚本：{P5_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fetch_category_scope(p5: Any, connection_file: Path) -> tuple[dict[str, list[str]], list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = p5.read_db_config(connection_file)
    driver = GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))
    query = """
MATCH (cat:KGNode {entityType:'DiseaseCategory'})
OPTIONAL MATCH (cat)-[:has_disease|has_subcategory|groups_disease*1..3]->(d:KGNode {entityType:'Disease'})
WITH cat, collect(DISTINCT d) AS diseases
RETURN cat.code AS category_code,
       cat.name AS category_name,
       [x IN diseases WHERE x IS NOT NULL | {code:x.code, name:x.name, diagnostic_role:coalesce(x.diagnostic_role,'')}] AS diseases
ORDER BY cat.name
"""
    try:
        with driver.session() as sess:
            rows = [dict(r) for r in sess.run(query)]
    finally:
        driver.close()

    scope: dict[str, list[str]] = {}
    included_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    for row in rows:
        code = str(row.get("category_code") or "")
        name = str(row.get("category_name") or "")
        diseases = row.get("diseases") or []
        disease_codes = sorted({
            str(item.get("code") or "").strip()
            for item in diseases
            if isinstance(item, dict) and str(item.get("code") or "").strip()
        })
        if code in TARGET_CATEGORY_CODES:
            scope[name] = disease_codes
            included_rows.append({
                "疾病大类编码": code,
                "疾病大类名称": name,
                "纳入状态": "纳入",
                "疾病数": len(disease_codes),
                "纳入依据": "批次台账已有教材/指南解析并写入Neo4j或补充解析入库记录",
                "疾病样例": "；".join(f"{d.get('name')}({d.get('code')})" for d in diseases[:12] if isinstance(d, dict)),
            })
        else:
            excluded_rows.append({
                "疾病大类编码": code,
                "疾病大类名称": name,
                "纳入状态": "暂不纳入",
                "疾病数": len(disease_codes),
                "原因": "本轮按已解析大类终验；台账未见该大类正式指南解析收口记录",
                "疾病样例": "；".join(f"{d.get('name')}({d.get('code')})" for d in diseases[:12] if isinstance(d, dict)),
            })

    return scope, included_rows, excluded_rows


def run_p5_with_scope(p5: Any, scope: dict[str, list[str]], connection_file: Path, out_dir: Path) -> int:
    old_scope = p5.ROOT_DISEASES
    old_argv = sys.argv[:]
    p5.ROOT_DISEASES = scope
    sys.argv = [
        str(P5_SCRIPT),
        "--connection-file",
        str(connection_file),
        "--output-dir",
        str(out_dir),
    ]
    try:
        return int(p5.main())
    finally:
        p5.ROOT_DISEASES = old_scope
        sys.argv = old_argv


def rename_p5_outputs(out_dir: Path) -> None:
    rename_map = {
        "00_P5样板终验_summary.json": "00_P6已解析大类终验_summary.json",
        "00_P5样板终验_raw.json": "00_P6已解析大类终验_raw.json",
        "P5_AMI与心肌病样板终验报告_收口版.md": "P6_已解析大类终验报告.md",
    }
    for src_name, dst_name in rename_map.items():
        src = out_dir / src_name
        dst = out_dir / dst_name
        if src.exists():
            if dst.exists():
                dst.unlink()
            src.rename(dst)


def enrich_and_summarize(out_dir: Path, included_rows: list[dict[str, Any]], excluded_rows: list[dict[str, Any]]) -> None:
    raw_path = out_dir / "00_P6已解析大类终验_raw.json"
    summary_path = out_dir / "00_P6已解析大类终验_summary.json"
    coverage_path = out_dir / "01_疾病维度覆盖明细.csv"
    formal_path = out_dir / "02_正式推荐链路明细.csv"
    gap_path = out_dir / "03_样板缺口清单.csv"
    classified_path = out_dir / "08_已分类非直接医嘱动作明细.csv"

    raw = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else {}
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    category_by_disease: dict[str, str] = {}
    for item in raw.get("diseases", []):
        if isinstance(item, dict):
            code = str(item.get("disease_code") or "").strip()
            group = str(item.get("样板分组") or "").strip()
            if code and group:
                category_by_disease.setdefault(code, group)

    coverage_rows = read_csv(coverage_path)
    if coverage_rows:
        original_fields = list(coverage_rows[0].keys())
        fields = ["疾病大类"] + [x for x in original_fields if x != "疾病大类"]
        for row in coverage_rows:
            row["疾病大类"] = category_by_disease.get(str(row.get("疾病编码") or ""), "")
        write_csv(coverage_path, coverage_rows, fields)

    formal_rows = read_csv(formal_path)
    gap_rows = read_csv(gap_path)
    classified_rows = read_csv(classified_path)

    formal_counter = Counter(category_by_disease.get(str(r.get("疾病编码") or r.get("disease_code") or ""), "未归类") for r in formal_rows)
    gap_counter = Counter(category_by_disease.get(str(r.get("疾病编码") or r.get("disease_code") or ""), "未归类") for r in gap_rows)
    classified_counter = Counter(category_by_disease.get(str(r.get("disease_code") or r.get("疾病编码") or ""), "未归类") for r in classified_rows)

    disease_rows_by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in coverage_rows:
        disease_rows_by_category[row.get("疾病大类", "")].append(row)

    category_summary: list[dict[str, Any]] = []
    for item in included_rows:
        name = str(item["疾病大类名称"])
        disease_rows = disease_rows_by_category.get(name, [])
        scope_disease_count = int(item.get("疾病数") or len(disease_rows) or 0)
        hard_gap_count = sum(1 for r in disease_rows if str(r.get("硬缺口") or "").strip())
        warning_count = sum(1 for r in disease_rows if str(r.get("提醒") or "").strip())
        if not disease_rows and scope_disease_count > 0:
            current_judgement = "共享疾病，已在主大类复核"
            summary_note = "该大类疾病节点与其他疾病大类共用，P5明细按疾病主归属统计，避免重复计算。"
        else:
            current_judgement = "通过" if hard_gap_count == 0 and gap_counter.get(name, 0) == 0 else "需治理"
            summary_note = ""
        category_summary.append({
            "疾病大类编码": item["疾病大类编码"],
            "疾病大类名称": name,
            "纳入疾病数": scope_disease_count,
            "独立统计疾病数": len(disease_rows),
            "正式推荐数": formal_counter.get(name, 0),
            "硬缺口疾病数": hard_gap_count,
            "阻断缺口行数": gap_counter.get(name, 0),
            "提醒疾病数": warning_count,
            "已分类非直接医嘱动作行数": classified_counter.get(name, 0),
            "当前判断": current_judgement,
            "统计说明": summary_note,
        })

    write_csv(
        out_dir / "09_疾病大类终验汇总.csv",
        category_summary,
        ["疾病大类编码", "疾病大类名称", "纳入疾病数", "独立统计疾病数", "正式推荐数", "硬缺口疾病数", "阻断缺口行数", "提醒疾病数", "已分类非直接医嘱动作行数", "当前判断", "统计说明"],
    )
    write_csv(
        out_dir / "10_本轮纳入大类说明.csv",
        included_rows,
        ["疾病大类编码", "疾病大类名称", "纳入状态", "疾病数", "纳入依据", "疾病样例"],
    )
    write_csv(
        out_dir / "11_本轮未纳入大类说明.csv",
        excluded_rows,
        ["疾病大类编码", "疾病大类名称", "纳入状态", "疾病数", "原因", "疾病样例"],
    )

    summary["p6_scope_note"] = "P6按批次台账已解析并入库的大类扩展P5终验口径；不纳入仅有骨架但无正式解析收口记录的大类。"
    summary["included_category_count"] = len(included_rows)
    summary["excluded_category_count"] = len(excluded_rows)
    summary["category_summary"] = category_summary
    write_json(summary_path, summary)

    report_lines = [
        "# P6 已解析疾病大类终验报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 执行模式：只读审计，不写 Oracle，不写 Neo4j。",
        f"- 纳入疾病大类：{len(included_rows)} 个。",
        f"- 纳入疾病：{summary.get('disease_count', 0)} 个。",
        f"- 正式推荐：{summary.get('formal_recommendation_count', 0)} 条。",
        f"- 阻断缺口：{summary.get('blocking_gap_count', 0)} 条。",
        f"- 标准字典真实缺口：{summary.get('standard_dictionary_gap_count', 0)} 条。",
        f"- 已分类非直接医嘱动作：{summary.get('classified_non_orderable_action_unique_count', 0)} 个节点。",
        "",
        "## 疾病大类结果",
        "",
        "| 疾病大类 | 纳入疾病数 | 独立统计疾病数 | 正式推荐数 | 硬缺口疾病数 | 阻断缺口行数 | 当前判断 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in category_summary:
        report_lines.append(
            f"| {row['疾病大类名称']} | {row['纳入疾病数']} | {row['独立统计疾病数']} | {row['正式推荐数']} | {row['硬缺口疾病数']} | {row['阻断缺口行数']} | {row['当前判断']} |"
        )
    report_lines.extend([
        "",
        "## 文件说明",
        "",
        "- `01_疾病维度覆盖明细.csv`：疾病级知识覆盖、诊断角色、标准诊断状态。",
        "- `02_正式推荐链路明细.csv`：正式 CDSS 推荐链路是否有动作、主证据、主指南、推荐等级、证据等级。",
        "- `03_样板缺口清单.csv`：真正阻断本轮终验的问题。",
        "- `08_已分类非直接医嘱动作明细.csv`：可展示但不能直接回填医嘱的动作，已从真实字典缺口中剥离。",
        "- `09_疾病大类终验汇总.csv`：面向交接的疾病大类总览。",
    ])
    (out_dir / "P6_已解析大类终验报告.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="P6 已解析疾病大类终验：复用 P5 最新口径扩展到已解析大类。")
    parser.add_argument("--connection-file", default=str(ROOT / "图谱数据库链接.txt"))
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "项目管理中心_project_management" / "2026年8月P6已解析大类终验" / "01_全大类只读审计_20260803"),
    )
    args = parser.parse_args()

    p5 = load_p5_module()
    connection_file = Path(args.connection_file)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scope, included_rows, excluded_rows = fetch_category_scope(p5, connection_file)
    if not scope:
        raise RuntimeError("未能从服务器识别可纳入 P6 的已解析疾病大类。")

    scope_file = out_dir / "00_P6纳入范围.json"
    write_json(scope_file, {"scope": scope, "included": included_rows, "excluded": excluded_rows})

    exit_code = run_p5_with_scope(p5, scope, connection_file, out_dir)
    rename_p5_outputs(out_dir)
    enrich_and_summarize(out_dir, included_rows, excluded_rows)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
