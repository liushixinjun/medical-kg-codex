from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]


def read_db_config(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;]+)", text)
    if not (uri and user and password):
        raise RuntimeError("数据库连接文件无法解析 Bolt 地址、用户名或密码。")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def rows_to_dicts(records: list[Any]) -> list[dict[str, Any]]:
    return [dict(record) for record in records]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


FORMAL_RECOMMENDATION_DETAIL_QUERY = """
MATCH (rec:KGNode {entityType:'RecommendationStatement'})
WHERE coalesce(rec.formal_cdss_ready,false)=true
  AND coalesce(rec.cdss_use_status,'')='正式推荐'
OPTIONAL MATCH (rec)-[ar:recommends_action|blocks_action|recommends_assessment]->(action:KGNode)
OPTIONAL MATCH (rec)-[:supported_by_evidence|derived_from]->(ev:KGNode {entityType:'Evidence'})
OPTIONAL MATCH (rec)-[:uses_primary_guideline|based_on_guideline]->(gl:KGNode {entityType:'Guideline'})
WITH rec,
     collect(DISTINCT action.code) AS action_codes,
     collect(DISTINCT action.name) AS action_names,
     collect(DISTINCT action.entityType) AS action_types,
     collect(DISTINCT type(ar)) AS action_relations,
     collect(DISTINCT ev.code) AS evidence_codes,
     collect(DISTINCT gl.code) AS guideline_codes,
     collect(DISTINCT {
       code: ev.code,
       name: ev.name,
       source_name: coalesce(properties(ev)['source_name'], properties(ev)['primary_source_name'], properties(ev)['source'], properties(ev)['guideline_name'], properties(ev)['source_file'], ''),
       page: coalesce(toString(properties(ev)['page']), toString(properties(ev)['page_number']), toString(properties(ev)['source_page']), toString(properties(ev)['primary_source_page']), ''),
       section: coalesce(properties(ev)['section'], properties(ev)['source_section'], properties(ev)['primary_source_section'], ''),
       summary: coalesce(properties(ev)['summary'], properties(ev)['evidence_summary'], properties(ev)['primary_evidence_summary'], ev.name, '')
     }) AS evidence_nodes,
     collect(DISTINCT {
       code: gl.code,
       name: gl.name,
       source_name: coalesce(properties(gl)['source_name'], properties(gl)['title'], properties(gl)['file_name'], gl.name, ''),
       page: coalesce(toString(properties(gl)['page']), toString(properties(gl)['page_number']), '')
     }) AS guideline_nodes
RETURN rec.code AS 推荐陈述编码,
       rec.name AS 推荐陈述,
       rec.disease_code AS 疾病编码,
       rec.disease_name AS 疾病名称,
       action_codes AS 动作编码,
       action_names AS 动作名称,
       action_types AS 动作类型,
       action_relations AS 动作关系,
       rec.primary_evidence_code AS 主证据编码,
       rec.primary_guideline_code AS 主指南编码,
       rec.primary_source_name AS 主来源名称,
       rec.primary_source_page AS 主来源页码,
       rec.primary_source_section AS 主来源章节,
       rec.primary_evidence_summary AS 主证据摘要,
       rec.primary_evidence_raw_excerpt AS 主证据原文摘录,
       rec.recommendation_class AS 推荐等级,
       rec.evidence_level AS 证据等级,
       rec.conflict_status AS 冲突状态,
       rec.adjudication_reason AS 裁决理由,
       evidence_codes AS 已连接证据编码,
       guideline_codes AS 已连接指南编码,
       evidence_nodes AS 已连接证据详情,
       guideline_nodes AS 已连接指南详情,
       CASE WHEN size(action_codes)>0
             AND any(x IN action_relations WHERE x IN ['recommends_action','blocks_action','recommends_assessment'])
            THEN true ELSE false END AS 是否有动作,
       CASE WHEN trim(coalesce(rec.primary_evidence_code,''))<>''
             AND rec.primary_evidence_code IN evidence_codes
            THEN true ELSE false END AS 主证据是否精确连接,
       CASE WHEN trim(coalesce(rec.primary_guideline_code,''))<>''
             AND rec.primary_guideline_code IN guideline_codes
            THEN true ELSE false END AS 主指南是否精确连接
ORDER BY 推荐陈述编码
"""


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _candidate_score(candidate: dict[str, Any], row: dict[str, Any], *, kind: str) -> int:
    source_name = _norm(row.get("主来源名称"))
    source_page = _norm(row.get("主来源页码"))
    haystack = _norm(
        " ".join(
            str(candidate.get(key) or "")
            for key in ["name", "source_name", "page", "section", "summary"]
        )
    )
    score = 0
    if source_name and (source_name in haystack or haystack in source_name):
        score += 10
    if source_page and _norm(candidate.get("page")) == source_page:
        score += 6
    if kind == "evidence" and "shared" in _norm(candidate.get("code")):
        score -= 1
    return score


def choose_best_candidate(row: dict[str, Any], *, kind: str) -> dict[str, Any] | None:
    key = "已连接证据详情" if kind == "evidence" else "已连接指南详情"
    candidates = [
        item
        for item in _as_list(row.get(key))
        if isinstance(item, dict) and str(item.get("code") or "").strip()
    ]
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda item: (
            _candidate_score(item, row, kind=kind),
            -1 if kind == "evidence" and "shared" in _norm(item.get("code")) else 0,
            _norm(item.get("code")),
        ),
        reverse=True,
    )
    best = ranked[0]
    return {
        "code": best.get("code"),
        "name": best.get("name"),
        "source_name": best.get("source_name"),
        "page": best.get("page"),
        "score": _candidate_score(best, row, kind=kind),
    }


def build_repair_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repair_rows: list[dict[str, Any]] = []
    for row in rows:
        missing_evidence = not row["主证据是否精确连接"]
        missing_guideline = not row["主指南是否精确连接"]
        if not missing_evidence and not missing_guideline:
            continue
        evidence = choose_best_candidate(row, kind="evidence") if missing_evidence else None
        guideline = choose_best_candidate(row, kind="guideline") if missing_guideline else None
        repair_rows.append(
            {
                "推荐陈述编码": row.get("推荐陈述编码"),
                "疾病名称": row.get("疾病名称"),
                "推荐陈述": row.get("推荐陈述"),
                "主来源名称": row.get("主来源名称"),
                "主来源页码": row.get("主来源页码"),
                "建议主证据编码": evidence.get("code") if evidence else "",
                "建议主证据名称": evidence.get("name") if evidence else "",
                "建议主证据来源": evidence.get("source_name") if evidence else "",
                "建议主证据页码": evidence.get("page") if evidence else "",
                "主证据匹配分": evidence.get("score") if evidence else "",
                "建议主指南编码": guideline.get("code") if guideline else "",
                "建议主指南名称": guideline.get("name") if guideline else "",
                "建议主指南来源": guideline.get("source_name") if guideline else "",
                "主指南匹配分": guideline.get("score") if guideline else "",
                "处理建议": "可补主证据和主指南精确标识"
                if evidence and guideline
                else "候选不足，需回原文复核",
            }
        )
    return repair_rows


def _cypher_string(value: Any) -> str:
    return str(value or "").replace("\\", "\\\\").replace("'", "\\'")


def render_repair_cypher(rows: list[dict[str, Any]]) -> str:
    lines = [
        "// P4 正式推荐主证据补链预览",
        "// 说明：此文件只作为人工审核后的写库脚本草案，生成时未执行。",
    ]
    for row in rows:
        rec_code = _cypher_string(row.get("推荐陈述编码"))
        evidence_code = _cypher_string(row.get("建议主证据编码"))
        guideline_code = _cypher_string(row.get("建议主指南编码"))
        if evidence_code:
            lines.extend(
                [
                    f"MATCH (rec:KGNode {{entityType:'RecommendationStatement', code:'{rec_code}'}})",
                    f"MATCH (ev:KGNode {{entityType:'Evidence', code:'{evidence_code}'}})",
                    "MERGE (rec)-[:supported_by_evidence]->(ev)",
                    f"SET rec.primary_evidence_code = '{evidence_code}';",
                ]
            )
        if guideline_code:
            lines.extend(
                [
                    f"MATCH (rec:KGNode {{entityType:'RecommendationStatement', code:'{rec_code}'}})",
                    f"MATCH (gl:KGNode {{entityType:'Guideline', code:'{guideline_code}'}})",
                    "MERGE (rec)-[:uses_primary_guideline]->(gl)",
                    f"SET rec.primary_guideline_code = '{guideline_code}';",
                ]
            )
    return "\n".join(lines) + "\n"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    missing_action = [row for row in rows if not row["是否有动作"]]
    missing_primary_evidence = [row for row in rows if not row["主证据是否精确连接"]]
    missing_primary_guideline = [row for row in rows if not row["主指南是否精确连接"]]
    missing_grade = [row for row in rows if not str(row.get("推荐等级") or "").strip()]
    missing_level = [row for row in rows if not str(row.get("证据等级") or "").strip()]
    return {
        "审计口径": "正式推荐主体为 RecommendationStatement；Evidence 是证据来源，不直接作为医生端推荐列表主体。",
        "正式推荐总数": total,
        "动作缺口": len(missing_action),
        "主证据精确连接缺口": len(missing_primary_evidence),
        "主指南精确连接缺口": len(missing_primary_guideline),
        "推荐等级缺口": len(missing_grade),
        "证据等级缺口": len(missing_level),
        "正式推荐链路结论": "通过"
        if not (missing_action or missing_primary_evidence or missing_primary_guideline or missing_grade or missing_level)
        else "不通过",
    }


def render_report(summary: dict[str, Any]) -> str:
    return f"""# P4 正式推荐证据链只读审计报告

## 一、结论

本轮只读审计以 `RecommendationStatement` 作为正式推荐主体，不再以旧的 `SourceAdjudication` 作为入口。医生端正式推荐应读取“推荐陈述 → 推荐动作/评估目标 → 主证据 → 主指南”，不应直接展示疾病下的一整池 Evidence。

## 二、统计

| 项目 | 数量 |
|---|---:|
| 正式推荐总数 | {summary['正式推荐总数']} |
| 动作缺口 | {summary['动作缺口']} |
| 主证据精确连接缺口 | {summary['主证据精确连接缺口']} |
| 主指南精确连接缺口 | {summary['主指南精确连接缺口']} |
| 推荐等级缺口 | {summary['推荐等级缺口']} |
| 证据等级缺口 | {summary['证据等级缺口']} |

## 三、当前判断

正式推荐链路结论：{summary['正式推荐链路结论']}。

如果存在主证据或主指南精确连接缺口，处理方式不是让前端过滤，而是补齐推荐陈述到主证据、主指南的关系；Evidence 节点仍保留为证据追溯层。
"""


def run(connection_file: Path, output_dir: Path) -> dict[str, Any]:
    cfg = read_db_config(connection_file)
    output_dir.mkdir(parents=True, exist_ok=True)
    with GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"])) as driver:
        rows = rows_to_dicts(driver.execute_query(FORMAL_RECOMMENDATION_DETAIL_QUERY).records)

    summary = summarize(rows)
    missing_rows = [
        row
        for row in rows
        if not row["是否有动作"]
        or not row["主证据是否精确连接"]
        or not row["主指南是否精确连接"]
        or not str(row.get("推荐等级") or "").strip()
        or not str(row.get("证据等级") or "").strip()
    ]

    fieldnames = [
        "推荐陈述编码",
        "推荐陈述",
        "疾病编码",
        "疾病名称",
        "动作编码",
        "动作名称",
        "动作类型",
        "动作关系",
        "主证据编码",
        "主指南编码",
        "主来源名称",
        "主来源页码",
        "主来源章节",
        "主证据摘要",
        "主证据原文摘录",
        "推荐等级",
        "证据等级",
        "冲突状态",
        "裁决理由",
        "已连接证据编码",
        "已连接指南编码",
        "已连接证据详情",
        "已连接指南详情",
        "是否有动作",
        "主证据是否精确连接",
        "主指南是否精确连接",
    ]
    repair_rows = build_repair_candidates(rows)
    repair_fieldnames = [
        "推荐陈述编码",
        "疾病名称",
        "推荐陈述",
        "主来源名称",
        "主来源页码",
        "建议主证据编码",
        "建议主证据名称",
        "建议主证据来源",
        "建议主证据页码",
        "主证据匹配分",
        "建议主指南编码",
        "建议主指南名称",
        "建议主指南来源",
        "主指南匹配分",
        "处理建议",
    ]
    write_csv(output_dir / "01_正式推荐证据链明细.csv", rows, fieldnames)
    write_csv(output_dir / "02_正式推荐证据链缺口.csv", missing_rows, fieldnames)
    write_csv(output_dir / "04_正式推荐主证据补链建议.csv", repair_rows, repair_fieldnames)
    (output_dir / "05_正式推荐主证据补链_preview.cypher").write_text(
        render_repair_cypher(repair_rows), encoding="utf-8"
    )
    (output_dir / "00_P4正式推荐证据链审计_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (output_dir / "03_P4正式推荐证据链只读审计报告.md").write_text(
        render_report(summary), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P4 正式推荐证据链只读审计")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.connection_file, args.output_dir)
