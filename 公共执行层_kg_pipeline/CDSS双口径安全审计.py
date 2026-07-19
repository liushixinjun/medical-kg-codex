from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]

KNOWLEDGE_BLOCKING_KEYS = (
    "非标准图谱节点",
    "技术编码名称节点",
    "同编码重复实体",
    "疾病定义缺口",
    "诊断标准无明细",
    "鉴别诊断无规则",
    "治疗方案无可执行动作",
    "在用药物类别无具体药品",
)

FORMAL_BLOCKING_KEYS = (
    "正式推荐缺疾病",
    "正式推荐缺推荐陈述",
    "正式推荐缺动作",
    "正式推荐缺主证据",
    "正式推荐缺主指南",
    "正式推荐缺推荐等级",
    "正式推荐缺证据等级",
    "正式推荐缺冲突状态",
    "正式推荐缺裁决理由",
)

KNOWLEDGE_DESCRIPTIONS = {
    "非标准图谱节点": "节点缺少 KGNode 主标签，公共查询可能漏查。",
    "技术编码名称节点": "实体名称仍是内部编码，医生无法理解。",
    "同编码重复实体": "同一实体类型和业务编码出现多个有效节点。",
    "疾病定义缺口": "可诊断疾病既无疾病定义文本，也无带正文的定义实体。",
    "诊断标准无明细": "诊断标准只有标题，没有可判断的组成条件。",
    "鉴别诊断无规则": "鉴别诊断只有对象名称，没有鉴别要点或排除检查。",
    "治疗方案无可执行动作": "治疗方案无法沿受控路径到达药品、操作、检查、检验、治疗或随访动作。",
    "在用药物类别无具体药品": "临床链路使用了药物类别，但没有连接任何具体药品。",
    "证据原文重复": "同一来源、同一页码、同一原文存在多个证据节点；按内容指纹识别，不按显示名称识别。",
}

FORMAL_DESCRIPTIONS = {
    "正式推荐缺疾病": "来源裁决没有关联疾病。",
    "正式推荐缺推荐陈述": "来源裁决没有形成医生可读的推荐陈述。",
    "正式推荐缺动作": "来源裁决没有推荐或阻断具体动作。",
    "正式推荐缺主证据": "来源裁决没有主证据，或主证据编码与关系不一致。",
    "正式推荐缺主指南": "来源裁决没有主指南，或主指南编码与关系不一致。",
    "正式推荐缺推荐等级": "正式推荐缺推荐等级。",
    "正式推荐缺证据等级": "正式推荐缺证据等级。",
    "正式推荐缺冲突状态": "正式推荐未说明指南之间是否存在冲突。",
    "正式推荐缺裁决理由": "正式推荐没有可复核的来源采用理由。",
}


def is_formal_recommendation_edge(
    source_entity_type: str,
    relation_type: str,
    source_properties: dict[str, Any],
) -> bool:
    """正式推荐只认来源裁决动作边，普通知识边不得进入此口径。"""
    return (
        source_entity_type == "SourceAdjudication"
        and relation_type in {"recommends_action", "blocks_action"}
        and source_properties.get("formal_cdss_ready") is True
        and source_properties.get("cdss_use_status") == "正式推荐"
    )


def build_evidence_fingerprint(source_name: Any, source_page: Any, evidence_text: Any) -> str:
    normalized = "|".join(
        re.sub(r"\s+", " ", str(value or "")).strip()
        for value in (source_name, source_page, evidence_text)
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def evaluate_dual_scope(
    knowledge_counts: dict[str, int], formal_counts: dict[str, int]
) -> dict[str, dict[str, Any]]:
    knowledge_blockers = {
        key: int(knowledge_counts.get(key, 0))
        for key in KNOWLEDGE_BLOCKING_KEYS
        if int(knowledge_counts.get(key, 0)) > 0
    }
    formal_blockers = {
        key: int(formal_counts.get(key, 0))
        for key in FORMAL_BLOCKING_KEYS
        if int(formal_counts.get(key, 0)) > 0
    }
    return {
        "知识内容完整性": {
            "结论": "通过" if not knowledge_blockers else "不通过",
            "阻断项": knowledge_blockers,
            "阻断总数": sum(knowledge_blockers.values()),
        },
        "正式推荐链路": {
            "结论": "通过" if not formal_blockers else "不通过",
            "阻断项": formal_blockers,
            "阻断总数": sum(formal_blockers.values()),
        },
    }


KNOWLEDGE_DETAIL_QUERIES: dict[str, str] = {
    "非标准图谱节点": """
        MATCH (n)
        WHERE NOT n:KGNode
        RETURN elementId(n) AS element_id, labels(n) AS labels,
               coalesce(n.code,'') AS code, coalesce(n.name,'') AS name
        ORDER BY code, name
    """,
    "技术编码名称节点": """
        MATCH (n:KGNode)
        WHERE n.entityType <> 'Evidence'
          AND (
            n.name = n.code OR n.display_name = n.code OR n.preferred_name = n.code
            OR n.name STARTS WITH 'EXAM-' OR n.name STARTS WITH 'PLAN-'
            OR n.name STARTS WITH 'DXC-' OR n.name STARTS WITH 'RULE-'
          )
        RETURN n.entityType AS entity_type, n.code AS code, n.name AS name
        ORDER BY entity_type, code
    """,
    "同编码重复实体": """
        MATCH (n:KGNode)
        WHERE trim(coalesce(n.code,'')) <> '' AND coalesce(n.status,'') <> 'deprecated'
        WITH n.entityType AS entity_type, n.code AS code, count(n) AS duplicate_count,
             collect(coalesce(n.name,'')) AS names
        WHERE duplicate_count > 1
        RETURN entity_type, code, duplicate_count, names
        ORDER BY duplicate_count DESC, entity_type, code
    """,
    "疾病定义缺口": """
        MATCH (d:KGNode {entityType:'Disease'})
        WHERE coalesce(d.status,'') <> 'deprecated'
          AND coalesce(d.is_diagnosable,true)=true
          AND coalesce(d.diagnostic_role,'independent_disease') IN
              ['broad_diagnosis','clinical_subtype','independent_disease']
        OPTIONAL MATCH (d)-[:has_definition]->(df:KGNode {entityType:'Definition'})
        WITH d, collect(df) AS definitions
        WHERE trim(coalesce(d.definition,''))=''
          AND none(x IN definitions WHERE trim(coalesce(
                x.definition_text, x.description, x.original_text, ''
              ))<>'')
        RETURN d.code AS disease_code, d.name AS disease_name,
               d.diagnostic_role AS diagnostic_role,
               size(definitions) AS definition_node_count
        ORDER BY diagnostic_role, disease_code
    """,
    "诊断标准无明细": """
        MATCH (d:KGNode {entityType:'Disease'})-[:has_diagnostic_criteria]->
              (c:KGNode {entityType:'DiagnosisCriteria'})
        WHERE coalesce(d.status,'') <> 'deprecated'
          AND coalesce(c.status,'') <> 'deprecated'
          AND NOT (c)-[:has_diagnostic_component]->(:KGNode)
        RETURN d.code AS disease_code, d.name AS disease_name,
               c.code AS criteria_code, c.name AS criteria_name
        ORDER BY disease_code, criteria_code
    """,
    "鉴别诊断无规则": """
        MATCH (d:KGNode {entityType:'Disease'})-[:has_differential_diagnosis|differentiates_from]->
              (x:KGNode {entityType:'DifferentialDiagnosis'})
        WHERE coalesce(d.status,'') <> 'deprecated'
          AND coalesce(x.status,'') <> 'deprecated'
          AND NOT (x)-[:has_differential_point|requires_exclusion_exam]->(:KGNode)
        RETURN d.code AS disease_code, d.name AS disease_name,
               x.code AS differential_code, x.name AS differential_name
        ORDER BY disease_code, differential_code
    """,
    "治疗方案无可执行动作": """
        MATCH (d:KGNode {entityType:'Disease'})-[:has_treatment_plan]->
              (p:KGNode {entityType:'TreatmentPlan'})
        WHERE coalesce(d.status,'') <> 'deprecated'
          AND coalesce(p.status,'') <> 'deprecated'
        OPTIONAL MATCH path=(p)-[:has_clinical_pathway|has_pathway_stage|next_pathway_stage|
          has_stage_rule|has_treatment_component|includes_medication|includes_procedure|
          has_recommended_action|recommends_action|
          treated_by_medication|treated_by_procedure*1..5]->(a:KGNode)
        WHERE a.entityType IN ['Medication','Procedure','ExamItem','LabItem','TreatmentItem',
                               'FollowUp','Exam','LabTest']
        WITH d, p, collect(DISTINCT a.code) AS action_codes
        WHERE size(action_codes)=0
        RETURN d.code AS disease_code, d.name AS disease_name,
               p.code AS plan_code, p.name AS plan_name,
               p.description AS description, p.source_name AS source_name
        ORDER BY disease_code, plan_code
    """,
    "在用药物类别无具体药品": """
        MATCH (m:KGNode {entityType:'Medication'})
        WHERE coalesce(m.status,'') <> 'deprecated'
          AND (
            m.name ENDS WITH '类药物' OR m.name ENDS WITH '类制剂'
            OR m.name ENDS WITH '抑制剂' OR m.name ENDS WITH '阻滞剂'
            OR m.name ENDS WITH '拮抗剂'
          )
        OPTIONAL MATCH (source:KGNode)-[use_rel]->(m)
        WHERE type(use_rel) IN ['includes_medication','treated_by_medication',
                                'recommends_action','has_recommended_action']
        WITH m, collect(DISTINCT source.code) AS used_by_codes
        WHERE size(used_by_codes)>0
          AND NOT (m)-[:has_specific_medication]->(:KGNode {entityType:'Medication'})
        RETURN m.code AS medication_class_code, m.name AS medication_class_name,
               m.aliases AS aliases, used_by_codes
        ORDER BY medication_class_name
    """,
    "证据原文重复": """
        MATCH (e:KGNode {entityType:'Evidence'})
        WITH coalesce(properties(e)['source_name'],properties(e)['source_guideline'],'') AS source_name,
             coalesce(toString(properties(e)['source_page']),toString(properties(e)['page']),
                      toString(properties(e)['page_number']),'') AS source_page,
             coalesce(e.evidence_text,e.original_text,'') AS evidence_text,
             count(e) AS duplicate_count, collect(e.code)[0..20] AS codes
        WHERE trim(evidence_text)<>'' AND duplicate_count>1
        RETURN source_name, source_page, substring(evidence_text,0,180) AS evidence_excerpt,
               duplicate_count, codes
        ORDER BY duplicate_count DESC, source_name, source_page
    """,
}


FORMAL_RECOMMENDATION_ROWS_QUERY = """
    MATCH (adj:KGNode {entityType:'SourceAdjudication'})
    WHERE coalesce(adj.formal_cdss_ready,false)=true
      AND coalesce(adj.cdss_use_status,'')='正式推荐'
    OPTIONAL MATCH (d:KGNode)-[:has_source_adjudication]->(adj)
    OPTIONAL MATCH (adj)-[:decides_recommendation]->
                   (rec:KGNode {entityType:'RecommendationStatement'})
    OPTIONAL MATCH (adj)-[ar:recommends_action|blocks_action]->(action:KGNode)
    OPTIONAL MATCH (adj)-[:derived_from]->(ev:KGNode {entityType:'Evidence'})
    OPTIONAL MATCH (adj)-[:uses_primary_guideline]->(gl:KGNode {entityType:'Guideline'})
    WITH adj,
         collect(DISTINCT d.code) AS disease_codes,
         collect(DISTINCT rec.code) AS recommendation_codes,
         collect(DISTINCT action.code) AS action_codes,
         collect(DISTINCT action.entityType) AS action_types,
         collect(DISTINCT type(ar)) AS action_relations,
         collect(DISTINCT ev.code) AS evidence_codes,
         collect(DISTINCT gl.code) AS guideline_codes
    RETURN adj.code AS source_adjudication_code,
           coalesce(adj.name,adj.clinical_question,adj.code) AS source_adjudication_name,
           disease_codes, recommendation_codes, action_codes, action_types, action_relations,
           evidence_codes, guideline_codes,
           adj.action_code AS action_code_property,
           adj.primary_evidence_code AS primary_evidence_code,
           adj.primary_guideline_code AS primary_guideline_code,
           adj.recommendation_class AS recommendation_class,
           adj.evidence_level AS evidence_level,
           adj.conflict_status AS conflict_status,
           adj.adjudication_reason AS adjudication_reason
    ORDER BY source_adjudication_code
"""


def read_db_config(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;]+)", text)
    if not (uri and user and password):
        raise RuntimeError("数据库连接文件无法解析 Bolt 地址、用户名或密码。")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def rows_to_dicts(records: Iterable[Any]) -> list[dict[str, Any]]:
    return [dict(record) for record in records]


def audit_formal_rows(rows: list[dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts = Counter({key: 0 for key in FORMAL_BLOCKING_KEYS})
    details: list[dict[str, Any]] = []
    for row in rows:
        issues: list[str] = []
        disease_codes = [x for x in row.get("disease_codes", []) if x]
        recommendation_codes = [x for x in row.get("recommendation_codes", []) if x]
        action_codes = [x for x in row.get("action_codes", []) if x]
        action_relations = {x for x in row.get("action_relations", []) if x}
        evidence_codes = {x for x in row.get("evidence_codes", []) if x}
        guideline_codes = {x for x in row.get("guideline_codes", []) if x}
        primary_evidence_code = str(row.get("primary_evidence_code") or "").strip()
        primary_guideline_code = str(row.get("primary_guideline_code") or "").strip()

        if not disease_codes:
            issues.append("正式推荐缺疾病")
        if not recommendation_codes:
            issues.append("正式推荐缺推荐陈述")
        if (
            not action_codes
            or not action_relations.intersection({"recommends_action", "blocks_action"})
        ):
            issues.append("正式推荐缺动作")
        if not primary_evidence_code or primary_evidence_code not in evidence_codes:
            issues.append("正式推荐缺主证据")
        if not primary_guideline_code or primary_guideline_code not in guideline_codes:
            issues.append("正式推荐缺主指南")
        if not str(row.get("recommendation_class") or "").strip():
            issues.append("正式推荐缺推荐等级")
        if not str(row.get("evidence_level") or "").strip():
            issues.append("正式推荐缺证据等级")
        if not str(row.get("conflict_status") or "").strip():
            issues.append("正式推荐缺冲突状态")
        if not str(row.get("adjudication_reason") or "").strip():
            issues.append("正式推荐缺裁决理由")

        for issue in issues:
            counts[issue] += 1
            details.append(
                {
                    "检查项": issue,
                    "来源裁决编码": row.get("source_adjudication_code"),
                    "来源裁决名称": row.get("source_adjudication_name"),
                    "疾病编码": "；".join(disease_codes),
                    "推荐陈述编码": "；".join(recommendation_codes),
                    "动作编码": "；".join(action_codes),
                    "说明": FORMAL_DESCRIPTIONS[issue],
                }
            )
    return dict(counts), details


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def flatten_knowledge_details(details: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for check_name, items in details.items():
        for item in items:
            rows.append(
                {
                    "检查项": check_name,
                    "性质": "阻断" if check_name in KNOWLEDGE_BLOCKING_KEYS else "提示",
                    "业务编码": item.get("disease_code") or item.get("plan_code")
                    or item.get("medication_class_code") or item.get("code") or "",
                    "业务名称": item.get("disease_name") or item.get("plan_name")
                    or item.get("medication_class_name") or item.get("name") or "",
                    "说明": KNOWLEDGE_DESCRIPTIONS.get(check_name, ""),
                    "原始数据": json.dumps(item, ensure_ascii=False, default=str),
                }
            )
    return rows


def render_report(
    generated_at: str,
    overview: dict[str, Any],
    knowledge_counts: dict[str, int],
    formal_counts: dict[str, int],
    conclusions: dict[str, dict[str, Any]],
    formal_total: int,
    mode: str,
) -> str:
    knowledge_lines = "\n".join(
        f"| {name} | {knowledge_counts.get(name, 0)} | {'阻断' if name in KNOWLEDGE_BLOCKING_KEYS else '提示'} | {KNOWLEDGE_DESCRIPTIONS.get(name,'')} |"
        for name in KNOWLEDGE_DETAIL_QUERIES
    )
    formal_lines = "\n".join(
        f"| {name} | {formal_counts.get(name, 0)} | {FORMAL_DESCRIPTIONS[name]} |"
        for name in FORMAL_BLOCKING_KEYS
    )
    return f"""# 正式 CDSS 安全审计 V2.0（双口径）

- 审计时间：{generated_at}
- 审计阶段：{'治理前基线' if mode == 'baseline' else '治理后复核'}
- 服务器节点：{overview.get('node_count', 0)}
- 服务器关系：{overview.get('relation_count', 0)}

## 一、结论

| 审计口径 | 结论 | 阻断总数 | 解释 |
|---|---:|---:|---|
| 知识内容完整性 | {conclusions['知识内容完整性']['结论']} | {conclusions['知识内容完整性']['阻断总数']} | 检查疾病知识是否完整、可解释、可下钻。 |
| 正式推荐链路 | {conclusions['正式推荐链路']['结论']} | {conclusions['正式推荐链路']['阻断总数']} | 只检查进入医生正式推荐区的 {formal_total} 条来源裁决。 |

两套结论独立：知识内容存在缺口，不再被误报成正式推荐字段缺失；正式推荐通过，也不代表所有疾病知识已经完整。

## 二、知识内容完整性

| 检查项 | 数量 | 性质 | 讲人话说明 |
|---|---:|---|---|
{knowledge_lines}

## 三、正式推荐链路

标准链路：疾病—推荐来源裁决—推荐陈述—推荐/阻断动作—主证据—主指南。

| 检查项 | 数量 | 讲人话说明 |
|---|---:|---|
{formal_lines}

普通知识关系（疾病有治疗方案、治疗方案包含药品、疾病接受手术等）不属于正式推荐口径，不能再要求它们逐条具备推荐等级和证据等级。
"""


def run_audit(connection_file: Path, output_dir: Path, mode: str) -> dict[str, Any]:
    cfg = read_db_config(connection_file)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    with GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"])) as driver:
        overview_record = driver.execute_query(
            "MATCH (n) WITH count(n) AS node_count MATCH ()-[r]->() RETURN node_count, count(r) AS relation_count"
        ).records[0]
        overview = dict(overview_record)
        knowledge_details = {
            name: rows_to_dicts(driver.execute_query(query).records)
            for name, query in KNOWLEDGE_DETAIL_QUERIES.items()
        }
        formal_rows = rows_to_dicts(driver.execute_query(FORMAL_RECOMMENDATION_ROWS_QUERY).records)

    knowledge_counts = {name: len(items) for name, items in knowledge_details.items()}
    formal_counts, formal_details = audit_formal_rows(formal_rows)
    conclusions = evaluate_dual_scope(knowledge_counts, formal_counts)
    result = {
        "审计版本": "V2.0",
        "生成时间": generated_at,
        "审计阶段": mode,
        "服务器概况": overview,
        "知识内容完整性": {
            "统计": knowledge_counts,
            **conclusions["知识内容完整性"],
        },
        "正式推荐链路": {
            "正式来源裁决数": len(formal_rows),
            "统计": formal_counts,
            **conclusions["正式推荐链路"],
        },
    }

    (output_dir / "双口径安全审计汇总.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (output_dir / "知识内容完整性明细.json").write_text(
        json.dumps(knowledge_details, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (output_dir / "正式推荐链路明细.json").write_text(
        json.dumps(formal_details, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    write_csv(
        output_dir / "知识内容完整性问题清单.csv",
        flatten_knowledge_details(knowledge_details),
        ["检查项", "性质", "业务编码", "业务名称", "说明", "原始数据"],
    )
    write_csv(
        output_dir / "正式推荐链路问题清单.csv",
        formal_details,
        ["检查项", "来源裁决编码", "来源裁决名称", "疾病编码", "推荐陈述编码", "动作编码", "说明"],
    )
    report = render_report(
        generated_at, overview, knowledge_counts, formal_counts, conclusions, len(formal_rows), mode
    )
    (output_dir / "正式CDSS安全审计V2.0报告.md").write_text(report, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式 CDSS 安全审计 V2.0（知识内容与正式推荐双口径）")
    parser.add_argument(
        "--connection-file",
        type=Path,
        default=ROOT / "图谱数据库链接.txt",
        help="图谱数据库连接文件",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="审计输出目录")
    parser.add_argument("--mode", choices=("baseline", "postcheck"), default="baseline")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_audit(args.connection_file, args.output_dir, args.mode)
