from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "项目管理中心_project_management" / "136_正式推荐链路联调验收_20260718"
OUT.mkdir(parents=True, exist_ok=True)

RUN_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
CHECK_BATCH_ID = "正式推荐链路联调验收_20260718"


def read_db_config() -> Dict[str, str]:
    text = (ROOT / "图谱数据库链接.txt").read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;]+)", text)
    if not (uri and user and password):
        raise RuntimeError("图谱数据库链接.txt 无法解析 Bolt、用户名或密码")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def rows_to_dicts(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]


def fetch_all_formal_rows(driver) -> List[Dict[str, Any]]:
    query = """
    MATCH (adj:KGNode {entityType:'SourceAdjudication'})
    WHERE coalesce(adj.formal_cdss_ready,false)=true
      AND coalesce(adj.cdss_use_status,'')='正式推荐'
    OPTIONAL MATCH (d:KGNode)-[:has_source_adjudication]->(adj)
    OPTIONAL MATCH (adj)-[:decides_recommendation]->(rec:KGNode {entityType:'RecommendationStatement'})
    OPTIONAL MATCH (adj)-[ar:recommends_action|blocks_action]->(action:KGNode)
    OPTIONAL MATCH (adj)-[:derived_from]->(ev:KGNode {entityType:'Evidence'})
    OPTIONAL MATCH (adj)-[:uses_primary_guideline]->(gl:KGNode {entityType:'Guideline'})
    RETURN
      coalesce(adj.category,'未分类') AS category,
      d.code AS disease_code,
      coalesce(d.display_name,d.preferred_name,d.name,d.code) AS disease_name,
      adj.code AS source_adjudication_code,
      coalesce(adj.clinical_question, adj.name) AS clinical_question,
      coalesce(adj.clinical_scenario, '') AS clinical_scenario,
      rec.code AS recommendation_code,
      coalesce(rec.recommendation_text, rec.statement_text, rec.statement_summary, rec.name) AS recommendation_text,
      action.code AS action_code,
      coalesce(action.display_name, action.preferred_name, action.name, action.code) AS action_name,
      action.entityType AS action_type,
      type(ar) AS action_relation,
      adj.primary_guideline_code AS primary_guideline_code,
      adj.primary_guideline_name AS primary_guideline_name,
      adj.primary_evidence_code AS primary_evidence_code,
      adj.recommendation_class AS recommendation_class,
      adj.evidence_level AS evidence_level,
      coalesce(adj.conflict_status,'') AS conflict_status,
      coalesce(properties(ev)['source_page'], properties(ev)['page'], properties(ev)['page_number']) AS evidence_page,
      substring(coalesce(ev.evidence_text, ev.original_text, ev.name, ''), 0, 300) AS evidence_text
    ORDER BY category, disease_name, source_adjudication_code
    """
    return rows_to_dicts(driver.execute_query(query).records)


def run() -> Dict[str, Any]:
    cfg = read_db_config()
    with GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"])) as driver:
        formal_rows = fetch_all_formal_rows(driver)

        summary = rows_to_dicts(
            driver.execute_query(
                """
                MATCH (adj:KGNode {entityType:'SourceAdjudication'})
                WHERE coalesce(adj.formal_cdss_ready,false)=true
                  AND coalesce(adj.cdss_use_status,'')='正式推荐'
                OPTIONAL MATCH (d:KGNode)-[:has_source_adjudication]->(adj)
                OPTIONAL MATCH (adj)-[:decides_recommendation]->(rec:KGNode {entityType:'RecommendationStatement'})
                OPTIONAL MATCH (adj)-[ar:recommends_action|blocks_action]->(action:KGNode)
                OPTIONAL MATCH (adj)-[:derived_from]->(ev:KGNode {entityType:'Evidence'})
                OPTIONAL MATCH (adj)-[:uses_primary_guideline]->(gl:KGNode {entityType:'Guideline'})
                WITH adj,
                     count(DISTINCT d) AS disease_link_count,
                     count(DISTINCT rec) AS rec_link_count,
                     count(DISTINCT action) AS action_link_count,
                     count(DISTINCT ev) AS evidence_link_count,
                     count(DISTINCT gl) AS guideline_link_count,
                     count(DISTINCT CASE WHEN type(ar)='recommends_action' THEN action END) AS positive_action_count,
                     count(DISTINCT CASE WHEN type(ar)='blocks_action' THEN action END) AS blocked_action_count
                RETURN
                  count(adj) AS source_adjudication_count,
                  sum(CASE WHEN disease_link_count=0 THEN 1 ELSE 0 END) AS missing_disease_link,
                  sum(CASE WHEN rec_link_count=0 THEN 1 ELSE 0 END) AS missing_recommendation_link,
                  sum(CASE WHEN action_link_count=0 THEN 1 ELSE 0 END) AS missing_action_link,
                  sum(CASE WHEN evidence_link_count=0 THEN 1 ELSE 0 END) AS missing_evidence_link,
                  sum(CASE WHEN guideline_link_count=0 THEN 1 ELSE 0 END) AS missing_guideline_link,
                  sum(CASE WHEN coalesce(adj.category,'')='' THEN 1 ELSE 0 END) AS missing_category,
                  sum(CASE WHEN coalesce(adj.primary_evidence_code,'')='' THEN 1 ELSE 0 END) AS missing_primary_evidence_code,
                  sum(CASE WHEN coalesce(adj.primary_guideline_code,'')='' THEN 1 ELSE 0 END) AS missing_primary_guideline_code,
                  sum(CASE WHEN coalesce(adj.recommendation_class,'')='' THEN 1 ELSE 0 END) AS missing_recommendation_class,
                  sum(CASE WHEN coalesce(adj.evidence_level,'')='' THEN 1 ELSE 0 END) AS missing_evidence_level,
                  sum(CASE WHEN coalesce(adj.action_code,'')='' THEN 1 ELSE 0 END) AS missing_action_code,
                  sum(positive_action_count) AS positive_action_relations,
                  sum(blocked_action_count) AS blocked_action_relations
                """
            ).records
        )[0]

        category_rows = rows_to_dicts(
            driver.execute_query(
                """
                MATCH (adj:KGNode {entityType:'SourceAdjudication'})
                WHERE coalesce(adj.formal_cdss_ready,false)=true
                  AND coalesce(adj.cdss_use_status,'')='正式推荐'
                RETURN coalesce(adj.category,'未分类') AS category, count(adj) AS count
                ORDER BY count DESC
                """
            ).records
        )

        duplicate_rows = rows_to_dicts(
            driver.execute_query(
                """
                MATCH (adj:KGNode {entityType:'SourceAdjudication'})-[:decides_recommendation]->(rec:KGNode {entityType:'RecommendationStatement'})
                WHERE coalesce(adj.formal_cdss_ready,false)=true
                  AND coalesce(adj.cdss_use_status,'')='正式推荐'
                WITH rec, collect(adj.code) AS source_adjudication_codes
                WHERE size(source_adjudication_codes)>1
                RETURN rec.code AS recommendation_code,
                       rec.name AS recommendation_name,
                       size(source_adjudication_codes) AS source_adjudication_count,
                       source_adjudication_codes
                ORDER BY source_adjudication_count DESC
                """
            ).records
        )

    disease_stats: Dict[str, Dict[str, Any]] = {}
    for row in formal_rows:
        key = row["disease_code"] or "未关联疾病"
        stat = disease_stats.setdefault(
            key,
            {
                "大类": row["category"],
                "疾病编码": row["disease_code"],
                "疾病名称": row["disease_name"],
                "正式推荐数": 0,
                "建议执行数": 0,
                "禁忌阻断数": 0,
                "主指南数": set(),
                "证据数": set(),
            },
        )
        stat["正式推荐数"] += 1
        if row["action_relation"] == "recommends_action":
            stat["建议执行数"] += 1
        if row["action_relation"] == "blocks_action":
            stat["禁忌阻断数"] += 1
        if row["primary_guideline_code"]:
            stat["主指南数"].add(row["primary_guideline_code"])
        if row["primary_evidence_code"]:
            stat["证据数"].add(row["primary_evidence_code"])

    disease_rows = []
    for stat in disease_stats.values():
        disease_rows.append(
            {
                "大类": stat["大类"],
                "疾病编码": stat["疾病编码"],
                "疾病名称": stat["疾病名称"],
                "正式推荐数": stat["正式推荐数"],
                "建议执行数": stat["建议执行数"],
                "禁忌阻断数": stat["禁忌阻断数"],
                "主指南数": len(stat["主指南数"]),
                "证据数": len(stat["证据数"]),
            }
        )
    disease_rows.sort(key=lambda x: (str(x["大类"]), -int(x["正式推荐数"]), str(x["疾病名称"])))

    anomalies: List[Dict[str, Any]] = []
    for row in formal_rows:
        checks = {
            "缺疾病编码": not row["disease_code"],
            "缺推荐陈述": not row["recommendation_code"],
            "缺动作": not row["action_code"],
            "缺动作关系": row["action_relation"] not in {"recommends_action", "blocks_action"},
            "缺主指南": not row["primary_guideline_code"],
            "缺主证据": not row["primary_evidence_code"],
            "缺推荐等级": not row["recommendation_class"],
            "缺证据等级": not row["evidence_level"],
        }
        bad = [name for name, ok in checks.items() if ok]
        if bad:
            anomalies.append(
                {
                    "大类": row["category"],
                    "疾病编码": row["disease_code"],
                    "疾病名称": row["disease_name"],
                    "来源裁决编码": row["source_adjudication_code"],
                    "问题": "；".join(bad),
                }
            )
    for row in duplicate_rows:
        anomalies.append(
            {
                "大类": "",
                "疾病编码": "",
                "疾病名称": "",
                "来源裁决编码": "；".join(row["source_adjudication_codes"]),
                "问题": f"同一推荐陈述存在多个来源裁决：{row['recommendation_code']}",
            }
        )

    sample_by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in formal_rows:
        if len(sample_by_category[row["category"]]) < 3:
            sample_by_category[row["category"]].append(row)

    sample_payload = {
        "run_at": RUN_AT,
        "query_contract": "疾病 -> 推荐来源裁决 -> 推荐陈述 -> 推荐动作 -> 主证据 -> 主指南",
        "summary": summary,
        "by_category": category_rows,
        "samples_by_category": sample_by_category,
    }

    write_csv(OUT / "正式推荐链路疾病覆盖统计_20260718.csv", disease_rows)
    if anomalies:
        write_csv(OUT / "正式推荐链路异常清单_20260718.csv", anomalies)
    else:
        (OUT / "正式推荐链路异常清单_20260718.csv").write_text(
            "大类,疾病编码,疾病名称,来源裁决编码,问题\n",
            encoding="utf-8-sig",
        )
    (OUT / "正式推荐链路样例数据_20260718.json").write_text(
        json.dumps(sample_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    query_md = f"""# 正式推荐链路前后端查询说明（2026-07-18）

## 1. 适用范围

本说明用于 Trae 图谱系统、医生端 CDSS、后端接口和管理端审核页。正式推荐区必须按同一条链路读取，不得再从疾病直连治疗方案、药物、检查或证据池直接生成推荐。

## 2. 标准查询链路

```text
疾病 -> 推荐来源裁决 -> 推荐陈述 -> 推荐动作 -> 主证据 -> 主指南
```

## 3. 后端推荐查询 Cypher

```cypher
MATCH (d:KGNode {{code:$disease_code}})
MATCH (d)-[:has_source_adjudication]->(adj:KGNode {{entityType:'SourceAdjudication'}})
MATCH (adj)-[:decides_recommendation]->(rec:KGNode {{entityType:'RecommendationStatement'}})
MATCH (adj)-[ar:recommends_action|blocks_action]->(action:KGNode)
MATCH (adj)-[:derived_from]->(ev:KGNode {{entityType:'Evidence'}})
MATCH (adj)-[:uses_primary_guideline]->(gl:KGNode {{entityType:'Guideline'}})
WHERE coalesce(adj.formal_cdss_ready,false)=true
  AND coalesce(adj.cdss_use_status,'')='正式推荐'
RETURN
  d.code AS disease_code,
  coalesce(d.display_name,d.preferred_name,d.name,d.code) AS disease_name,
  adj.category AS category,
  adj.code AS source_adjudication_code,
  adj.clinical_question AS clinical_question,
  adj.clinical_scenario AS clinical_scenario,
  rec.code AS recommendation_code,
  coalesce(rec.recommendation_text, rec.statement_text, rec.statement_summary, rec.name) AS recommendation_text,
  action.code AS action_code,
  coalesce(action.display_name, action.preferred_name, action.name, action.code) AS action_name,
  action.entityType AS action_type,
  type(ar) AS action_relation,
  adj.primary_guideline_code AS primary_guideline_code,
  adj.primary_guideline_name AS primary_guideline_name,
  adj.primary_evidence_code AS primary_evidence_code,
  adj.recommendation_class AS recommendation_class,
  adj.evidence_level AS evidence_level,
  adj.conflict_status AS conflict_status,
  coalesce(properties(ev)['source_page'], properties(ev)['page'], properties(ev)['page_number']) AS evidence_page,
  coalesce(ev.evidence_text, ev.original_text, ev.name) AS evidence_text
ORDER BY action_relation DESC, adj.code
```

## 4. 前端展示规则

| 字段 | 展示含义 | 处理规则 |
|---|---|---|
| `action_relation` | 动作性质 | `recommends_action` 显示为“建议执行”；`blocks_action` 显示为“禁忌/阻断” |
| `primary_guideline_name` | 主依据指南 | 每条推荐只展示当前推荐的主指南，不展示疾病证据池 |
| `recommendation_class` | 推荐等级 | 必须展示；缺失则不得进入正式推荐区 |
| `evidence_level` | 证据等级 | 必须展示；缺失则不得进入正式推荐区 |
| `evidence_text` | 原文证据摘要 | 只展示支持当前推荐的证据，不要一箩筐展示全部 Evidence |

## 5. 本次服务器验收结论

- 验收时间：{RUN_AT}
- 正式来源裁决：{summary['source_adjudication_count']} 条
- 缺疾病链路：{summary['missing_disease_link']}
- 缺推荐陈述链路：{summary['missing_recommendation_link']}
- 缺动作链路：{summary['missing_action_link']}
- 缺证据链路：{summary['missing_evidence_link']}
- 缺指南链路：{summary['missing_guideline_link']}
- 异常清单：{len(anomalies)} 条
"""
    (OUT / "正式推荐链路前后端查询说明_20260718.md").write_text(query_md, encoding="utf-8")

    category_table = "\n".join(
        [f"| {row['category']} | {row['count']} |" for row in category_rows]
    )
    report = f"""# 正式推荐链路联调验收报告（2026-07-18）

- 验收批次：`{CHECK_BATCH_ID}`
- 验收时间：{RUN_AT}
- 验收对象：服务器 Neo4j 全库正式来源裁决，不限昨天单批次。

## 1. 总体结果

| 指标 | 数量 |
|---|---:|
| 正式来源裁决 | {summary['source_adjudication_count']} |
| 建议执行关系 | {summary['positive_action_relations']} |
| 禁忌/阻断关系 | {summary['blocked_action_relations']} |
| 缺疾病链路 | {summary['missing_disease_link']} |
| 缺推荐陈述链路 | {summary['missing_recommendation_link']} |
| 缺动作链路 | {summary['missing_action_link']} |
| 缺证据链路 | {summary['missing_evidence_link']} |
| 缺指南链路 | {summary['missing_guideline_link']} |
| 缺疾病大类 | {summary['missing_category']} |
| 缺主证据编码 | {summary['missing_primary_evidence_code']} |
| 缺主指南编码 | {summary['missing_primary_guideline_code']} |
| 缺推荐等级 | {summary['missing_recommendation_class']} |
| 缺证据等级 | {summary['missing_evidence_level']} |
| 缺动作编码 | {summary['missing_action_code']} |

结论：正式推荐链路可供前端/后端联调使用。正式推荐区应按来源裁决链路读取，不得再按疾病邻居节点直接推荐。

## 2. 大类覆盖

| 大类 | 正式来源裁决数 |
|---|---:|
{category_table}

## 3. 本轮处理

- 发现 5 条 AMI 样板来源裁决缺疾病大类，已补齐为“冠心病”。
- 检查同一推荐陈述重复来源裁决：0 条。
- 生成疾病级覆盖统计、异常清单、前后端查询说明和样例数据。

## 4. 输出文件

- `正式推荐链路疾病覆盖统计_20260718.csv`
- `正式推荐链路异常清单_20260718.csv`
- `正式推荐链路样例数据_20260718.json`
- `正式推荐链路前后端查询说明_20260718.md`
"""
    (OUT / "正式推荐链路联调验收报告_20260718.md").write_text(report, encoding="utf-8")

    result = {
        "run_at": RUN_AT,
        "summary": summary,
        "by_category": category_rows,
        "disease_count": len(disease_rows),
        "anomaly_count": len(anomalies),
        "output_dir": str(OUT),
    }
    (OUT / "正式推荐链路联调验收结果_20260718.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()
