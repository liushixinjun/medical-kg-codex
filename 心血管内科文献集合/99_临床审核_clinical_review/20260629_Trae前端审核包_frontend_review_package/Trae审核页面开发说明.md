# Trae 临床审核页面开发说明

## 结论

当前 Trae 图谱系统已有总览、探索、网络、覆盖、诊断模拟、数据字典、Schema、术语库、配置页面，但还没有 pending 临床审核工作流。

本目录已生成 Trae 可直接读取的前端审核包：

- `clinical_review_frontend_manifest.json`
- `clinical_review_frontend_data.json`
- `clinical_review_decision_export_template.csv`

Trae 只负责前端展示和导出审核结果，不允许直接写 Neo4j，不允许直接修改图谱 JSONL。

## 页面建议

新增页面：`review.html`

导航名称：`临床审核`

页面分 4 个 Tab：

1. 疾病级审核
2. 场景级推荐审核
3. 药师专项审核
4. 边级证据追溯

## 数据源

前端读取：

```js
fetch('./assets/clinical_review_frontend_data.json')
```

如果部署目录不同，请把本目录的 `clinical_review_frontend_data.json` 复制到 Trae 静态资源目录。

## 数据量

```text
disease_review_count = 22
scenario_card_count = 103
pharmacist_item_count = 187
detail_item_count = 303
```

## 决策枚举

疾病级/场景级：

```text
可试用
仅参考
需修改
禁用
```

药师专项：

```text
通过
需修改
禁用
```

边级明细：

```text
approve
revise
reject
```

## 导出要求

导出 CSV 文件名：

```text
clinical_review_decisions_export_YYYYMMDD_HHMMSS.csv
```

导出列：

```text
review_level
review_id
batch_id
disease_code
disease_name
scenario_type
relation_type
target_type
relation_id
target_code
target_name
review_decision
overall_risk_level
reviewer_name
reviewer_role
reviewed_at
expert_comment
```

同时导出 JSON：

```json
{
  "schema_version": "clinical-review-decision-export-v1",
  "exported_at": "YYYY-MM-DD HH:mm:ss",
  "exported_by": "审核人",
  "items": []
}
```

## 禁止动作

Trae 页面不得提供以下按钮或行为：

- 写入 Neo4j
- 正式 CDSS 上线
- 修改 `nodes_final.jsonl`
- 修改 `relations_final.jsonl`
- 自动把所有 pending 改成 approved

## Codex 回写规则

Trae 导出的审核结果交给 Codex。Codex 校验后，只允许 detail 级 `approve` 行进入 `apply_clinical_review_decisions.py` 回写。

疾病级和场景级审核只代表“临床使用效果可接受”，不直接等同于所有边级推荐已完成正式审核。
