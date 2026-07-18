from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "项目管理中心_project_management" / "137_正式推荐接口契约与前端联调_20260718"
OUT.mkdir(parents=True, exist_ok=True)

RUN_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

SAMPLE_DISEASES = [
    ("DIS-CARD-CAD-STEMI", "ST段抬高型心肌梗死"),
    ("DIS-CARD-CAD-AMI", "急性心肌梗死"),
    ("DIS-CARD-CM-HCM", "肥厚型心肌病"),
    ("DIS-CARD-HF", "心力衰竭"),
    ("DIS-CARD-ARR-AF", "心房颤动"),
    ("DIS-CARD-HT", "高血压"),
]


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


def fetch_recommendations(driver, disease_code: str) -> List[Dict[str, Any]]:
    query = """
    MATCH (d:KGNode {code:$disease_code})
    MATCH (d)-[:has_source_adjudication]->(adj:KGNode {entityType:'SourceAdjudication'})
    MATCH (adj)-[:decides_recommendation]->(rec:KGNode {entityType:'RecommendationStatement'})
    MATCH (adj)-[ar:recommends_action|blocks_action]->(action:KGNode)
    MATCH (adj)-[:derived_from]->(ev:KGNode {entityType:'Evidence'})
    MATCH (adj)-[:uses_primary_guideline]->(gl:KGNode {entityType:'Guideline'})
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
      coalesce(adj.conflict_status,'') AS conflict_status,
      coalesce(properties(ev)['source_page'], properties(ev)['page'], properties(ev)['page_number']) AS evidence_page,
      substring(coalesce(ev.evidence_text, ev.original_text, ev.name, ''), 0, 500) AS evidence_text
    ORDER BY
      CASE type(ar) WHEN 'blocks_action' THEN 0 ELSE 1 END,
      adj.code
    """
    return [dict(row) for row in driver.execute_query(query, disease_code=disease_code).records]


def build_response(disease_code: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    first = rows[0] if rows else {}
    recommendations = []
    for row in rows:
        recommendations.append(
            {
                "source_adjudication_code": row["source_adjudication_code"],
                "recommendation_code": row["recommendation_code"],
                "clinical_question": row["clinical_question"],
                "clinical_scenario": row["clinical_scenario"],
                "recommendation_text": row["recommendation_text"],
                "action": {
                    "code": row["action_code"],
                    "name": row["action_name"],
                    "type": row["action_type"],
                    "relation": row["action_relation"],
                    "relation_cn": "禁忌/阻断" if row["action_relation"] == "blocks_action" else "建议执行",
                },
                "primary_guideline": {
                    "code": row["primary_guideline_code"],
                    "name": row["primary_guideline_name"],
                },
                "primary_evidence": {
                    "code": row["primary_evidence_code"],
                    "page": row["evidence_page"],
                    "text": row["evidence_text"],
                },
                "recommendation_class": row["recommendation_class"],
                "evidence_level": row["evidence_level"],
                "conflict_status": row["conflict_status"],
            }
        )
    return {
        "success": True,
        "disease": {
            "code": disease_code,
            "name": first.get("disease_name", ""),
            "category": first.get("category", ""),
        },
        "summary": {
            "total": len(recommendations),
            "recommend_count": sum(1 for x in recommendations if x["action"]["relation"] == "recommends_action"),
            "block_count": sum(1 for x in recommendations if x["action"]["relation"] == "blocks_action"),
        },
        "recommendations": recommendations,
    }


def run() -> Dict[str, Any]:
    cfg = read_db_config()
    samples: Dict[str, Any] = {}
    test_rows: List[Dict[str, Any]] = []
    with GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"])) as driver:
        for disease_code, disease_name in SAMPLE_DISEASES:
            rows = fetch_recommendations(driver, disease_code)
            response = build_response(disease_code, rows)
            samples[disease_code] = response
            test_rows.append(
                {
                    "用例编号": f"TC-{len(test_rows)+1:02d}",
                    "疾病编码": disease_code,
                    "疾病名称": disease_name,
                    "预期正式推荐数": response["summary"]["total"],
                    "预期建议执行数": response["summary"]["recommend_count"],
                    "预期禁忌阻断数": response["summary"]["block_count"],
                    "验收重点": "每条推荐必须展示动作、动作性质、主指南、推荐等级、证据等级、原文证据摘要",
                }
            )

    (OUT / "正式推荐接口样例_20260718.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(OUT / "正式推荐接口验收用例_20260718.csv", test_rows)

    endpoint_md = f"""# 正式推荐接口契约（2026-07-18）

## 1. 接口定位

本接口只服务正式 CDSS 推荐区。知识浏览页可以继续展示疾病相关症状、检查、治疗方案和证据池，但医生端主动推荐必须只读取本接口。

## 2. 推荐接口

```text
GET /api/kg/formal-recommendations?disease_code=DIS-CARD-CAD-STEMI
```

参数：

| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| `disease_code` | 是 | 疾病编码 | `DIS-CARD-CAD-STEMI` |

## 3. 返回结构

```json
{{
  "success": true,
  "disease": {{
    "code": "DIS-CARD-CAD-STEMI",
    "name": "ST段抬高型心肌梗死",
    "category": "冠心病"
  }},
  "summary": {{
    "total": 35,
    "recommend_count": 32,
    "block_count": 3
  }},
  "recommendations": [
    {{
      "source_adjudication_code": "推荐来源裁决编码",
      "recommendation_code": "推荐陈述编码",
      "clinical_question": "临床问题",
      "clinical_scenario": "适用场景",
      "recommendation_text": "推荐内容",
      "action": {{
        "code": "动作编码",
        "name": "动作中文名",
        "type": "动作实体类型",
        "relation": "recommends_action",
        "relation_cn": "建议执行"
      }},
      "primary_guideline": {{
        "code": "主指南编码",
        "name": "主指南名称"
      }},
      "primary_evidence": {{
        "code": "主证据编码",
        "page": "页码",
        "text": "原文证据摘要"
      }},
      "recommendation_class": "推荐等级",
      "evidence_level": "证据等级",
      "conflict_status": "冲突状态"
    }}
  ]
}}
```

## 4. 前端展示要求

| 返回字段 | 中文展示 | 要求 |
|---|---|---|
| `recommendation_text` | 推荐内容 | 作为卡片主体 |
| `action.name` | 推荐动作 | 必须显示中文标准名 |
| `action.relation_cn` | 动作性质 | “建议执行”和“禁忌/阻断”必须分区展示 |
| `primary_guideline.name` | 主依据指南 | 每条推荐显示自己的主指南 |
| `recommendation_class` | 推荐等级 | 不允许为空 |
| `evidence_level` | 证据等级 | 不允许为空 |
| `primary_evidence.text` | 原文证据摘要 | 展示当前推荐对应证据，不展示疾病全部证据 |

## 5. 后端查询 Cypher

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
  coalesce(adj.conflict_status,'') AS conflict_status,
  coalesce(properties(ev)['source_page'], properties(ev)['page'], properties(ev)['page_number']) AS evidence_page,
  coalesce(ev.evidence_text, ev.original_text, ev.name) AS evidence_text
ORDER BY CASE type(ar) WHEN 'blocks_action' THEN 0 ELSE 1 END, adj.code
```

## 6. 当前样例覆盖

本包已生成 6 个疾病样例：STEMI、AMI、肥厚型心肌病、心力衰竭、心房颤动、高血压。样例文件见 `正式推荐接口样例_20260718.json`。

生成时间：{RUN_AT}
"""
    (OUT / "正式推荐接口契约_20260718.md").write_text(endpoint_md, encoding="utf-8")

    trae_md = f"""# Trae/后端正式推荐联调任务说明（2026-07-18）

## 1. 本次要改什么

正式推荐区不要再从“疾病 -> 治疗方案/药物/检查/证据池”直接拿数据。统一改为调用正式推荐接口，后端按“疾病 -> 推荐来源裁决 -> 推荐陈述 -> 推荐动作 -> 主证据 -> 主指南”查询。

## 2. 前端页面怎么展示

每条推荐卡片至少显示：

1. 推荐内容。
2. 推荐动作。
3. 动作性质：建议执行或禁忌/阻断。
4. 主依据指南。
5. 推荐等级。
6. 证据等级。
7. 原文证据摘要。

## 3. 禁止做法

- 不要把疾病证据池全部展示到某条推荐下面。
- 不要把疾病直连的治疗方案当正式推荐。
- 不要把 `blocks_action` 显示成建议执行。
- 不要只展示动作名称而不展示主指南和证据摘要。

## 4. 验收用例

使用 `正式推荐接口验收用例_20260718.csv`。其中 STEMI 必须能看到禁忌/阻断类推荐；房颤也应能看到阻断类推荐。

## 5. 输入文件

- `正式推荐接口契约_20260718.md`
- `正式推荐接口样例_20260718.json`
- `正式推荐接口验收用例_20260718.csv`
"""
    (OUT / "Trae后端正式推荐联调任务说明_20260718.md").write_text(trae_md, encoding="utf-8")

    result = {
        "run_at": RUN_AT,
        "output_dir": str(OUT),
        "sample_disease_count": len(SAMPLE_DISEASES),
        "sample_total_recommendations": sum(item["summary"]["total"] for item in samples.values()),
        "files": [
            "正式推荐接口契约_20260718.md",
            "正式推荐接口样例_20260718.json",
            "正式推荐接口验收用例_20260718.csv",
            "Trae后端正式推荐联调任务说明_20260718.md",
        ],
    }
    (OUT / "正式推荐接口联调包生成结果_20260718.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()
