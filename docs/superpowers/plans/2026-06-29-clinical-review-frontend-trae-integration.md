# Clinical Review Frontend and Trae Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 CAD/CM 图谱的 pending 临床审核从“逐条图谱边审核”转换为可由 Trae 前端展示、专家按疾病/场景/药师专项审核、Codex 回写和验收的闭环流程。

**Architecture:** Trae 前端只读取 `clinical_review_frontend_data.json` 并导出审核结果文件；不得直接写 Neo4j、不得修改 `nodes_final.jsonl` 或 `relations_final.jsonl`。Codex 负责校验导出文件、转换为 detail 级回写 CSV、执行 `apply_clinical_review_decisions.py`、重跑审计并导入测试库。

**Tech Stack:** 静态 HTML/JS Trae 图谱系统、JSON/CSV 审核包、Python 回写脚本、Neo4j HTTP delta 导入、unittest。

---

## 已分析的 Trae 图谱系统现状

访问地址：`http://192.168.3.27:4001/index.html`

现有页面：

- `index.html`：专病总览、KPI、疾病大类、知识维度成熟度。
- `explore.html`：疾病维度浏览、实体视角，调用 `/api/kg/diseases/summary`。
- `network.html`：交互式图谱网络、疾病中心展开、实体详情、路径分析、导出。
- `heatmap.html`：77 种疾病 × 17 维度覆盖分析。
- `diagnosis.html`：病例文本输入与候选疾病匹配模拟。
- `schema.html`：实体类型、关系类型、疾病分类等数据字典。
- `standard.html`：Schema 标准展示。
- `terminology.html`：医学术语知识库。
- `config.html`：Neo4j 连接配置。

现有数据接口：

- `/api/kg/stats`
- `/api/kg/diseases`
- `/api/kg/diseases/summary`
- `/api/kg/disease/{code}`
- `./assets/kg_full_data.json`

当前缺口：

- 没有 `clinical_review` / `pending` 专家审核工作流。
- 没有疾病级、场景级、药师专项三层审核页面。
- 没有审核结果导出契约。
- 没有把前端审核结果交给 Codex 回写的边界控制。

## 本轮已生成的前端审核包

目录：

`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\99_临床审核_clinical_review\20260629_Trae前端审核包_frontend_review_package`

文件：

- `clinical_review_frontend_manifest.json`
- `clinical_review_frontend_data.json`
- `clinical_review_decision_export_template.csv`

数据量：

- disease_review_count = 22
- scenario_card_count = 103
- pharmacist_item_count = 187
- detail_item_count = 303

## Task 1: Trae 增加审核入口

**Files:**

- Modify in Trae project: `index.html`
- Modify in Trae project: `_shared/js/app.js`
- Create in Trae project: `review.html`

- [ ] **Step 1: 在导航中增加“临床审核”入口**

在 Trae 的导航配置中增加：

```js
{
  id: 'review',
  title: '临床审核',
  href: 'review.html',
  icon: '✅',
  desc: '疾病级、场景级、药师专项审核'
}
```

- [ ] **Step 2: 新增 `review.html` 页面骨架**

页面必须包含 4 个 Tab：

```text
1. 疾病级审核
2. 场景级推荐审核
3. 药师专项审核
4. 边级证据追溯
```

页面顶部显示：

```text
待审核疾病数
待审核场景数
药师专项数
边级追溯数
当前允许状态：测试库工作版本，不得正式 CDSS 上线
```

- [ ] **Step 3: 读取前端审核 JSON**

Trae 前端只读取：

```js
fetch('./assets/clinical_review_frontend_data.json')
```

若文件放在服务器其他路径，必须由 Trae 配置为静态资源路径，不得从 Codex 本地目录直接读取。

Expected JSON top-level keys:

```json
{
  "schema_version": "clinical-review-frontend-v1",
  "decision_options": {},
  "summary": {},
  "disease_reviews": [],
  "scenario_cards": [],
  "pharmacist_items": [],
  "detail_items": [],
  "rules": []
}
```

## Task 2: 疾病级审核页

**Files:**

- Modify in Trae project: `review.html`
- Modify in Trae project: `_shared/js/review.js`

- [ ] **Step 1: 渲染疾病级表格**

字段：

```text
disease_name
pending_recommendation_count
scenario_card_count
clinical_use_question
clinical_use_decision
overall_risk_level
reviewer_name
reviewer_role
reviewed_at
expert_comment
```

- [ ] **Step 2: 决策枚举**

`clinical_use_decision` 只允许：

```text
可试用
仅参考
需修改
禁用
```

- [ ] **Step 3: 交互规则**

用户选择 `需修改` 或 `禁用` 时，`expert_comment` 必填。

## Task 3: 场景级推荐审核页

**Files:**

- Modify in Trae project: `review.html`
- Modify in Trae project: `_shared/js/review.js`

- [ ] **Step 1: 渲染场景卡**

字段：

```text
disease_name
scenario_type
relation_type
target_type
pending_item_count
sample_targets
missing_field_summary
review_focus
clinical_use_decision
expert_comment
```

- [ ] **Step 2: 筛选器**

必须支持：

```text
按疾病筛选
按场景类型筛选
按 target_type 筛选
按 decision 状态筛选
关键词搜索 sample_targets
```

- [ ] **Step 3: 证据追溯入口**

每张场景卡提供“查看边级证据”按钮，只展开相关 `detail_items`，不得让专家默认面对全部 303 条边。

## Task 4: 药师专项审核页

**Files:**

- Modify in Trae project: `review.html`
- Modify in Trae project: `_shared/js/review.js`

- [ ] **Step 1: 渲染药师清单**

字段：

```text
disease_name
target_name
missing_fields
review_focus
pharmacist_decision
pharmacist_comment
```

- [ ] **Step 2: 决策枚举**

`pharmacist_decision` 只允许：

```text
通过
需修改
禁用
```

- [ ] **Step 3: 强制备注**

药师选择 `需修改` 或 `禁用` 时，`pharmacist_comment` 必填。

## Task 5: 审核结果导出

**Files:**

- Modify in Trae project: `review.html`
- Modify in Trae project: `_shared/js/review.js`

- [ ] **Step 1: 导出 CSV**

导出文件名：

```text
clinical_review_decisions_export_YYYYMMDD_HHMMSS.csv
```

导出列必须完全匹配：

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

- [ ] **Step 2: 导出 JSON**

同时导出 JSON：

```json
{
  "schema_version": "clinical-review-decision-export-v1",
  "exported_at": "YYYY-MM-DD HH:mm:ss",
  "exported_by": "前端填写或登录用户",
  "items": []
}
```

- [ ] **Step 3: 禁止直接回写**

页面不得提供“写入 Neo4j”“正式上线”“修改 JSONL”按钮。

## Task 6: Codex 回写机制

**Files:**

- Existing: `scripts/apply_clinical_review_decisions.py`
- Existing: `scripts/build_clinical_review_frontend_package.py`
- Future test: `tests/test_convert_frontend_review_decisions.py`
- Future script: `scripts/convert_frontend_review_decisions.py`

- [ ] **Step 1: Trae 交付审核结果文件**

Trae 只交付：

```text
clinical_review_decisions_export_YYYYMMDD_HHMMSS.csv
clinical_review_decisions_export_YYYYMMDD_HHMMSS.json
```

- [ ] **Step 2: Codex 校验导出文件**

Codex 校验：

```text
review_id 是否存在于 clinical_review_frontend_data.json
需修改/禁用是否填写备注
reviewer_name/reviewer_role/reviewed_at 是否完整
是否含未知 batch_id / relation_id
```

- [ ] **Step 3: Codex 转换 detail approve**

只有 `review_level=detail` 且 `review_decision=approve` 的行，才转换为 `apply_clinical_review_decisions.py` 可用的 detail 回写 CSV。

疾病级和场景级决策只作为使用效果审核记录，不直接把所有边标为 `clinical_approved`。

- [ ] **Step 4: Codex 执行回写**

命令模板：

```powershell
python scripts/apply_clinical_review_decisions.py `
  --batch-dir "心血管内科文献集合\BATCH-CARD-CAD-20260623-001" `
  --batch-dir "心血管内科文献集合\BATCH-CARD-CM-20260622-001" `
  --decisions-csv "心血管内科文献集合\99_临床审核_clinical_review\回写输入\detail_decisions_for_apply.csv" `
  --summary-json "心血管内科文献集合\99_临床审核_clinical_review\回写输入\apply_summary.json"
```

## Task 7: 验收规则

**Files:**

- Existing: `scripts/audit_graph_instance.py`
- Existing: `scripts/import_neo4j_delta.py`
- Existing: `scripts/verify_server_global_repair.py`

- [ ] **Step 1: 本地审计**

回写后必须运行：

```powershell
python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 2: 测试库同步**

只能导入测试库工作版本，不得标记正式 CDSS 上线。

- [ ] **Step 3: 服务器硬闸门**

服务器必须满足：

```text
non_kgnode_node_count = 0
semantic_shell_relation_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
duplicate_type_name_count = 0
```

## Trae 交付边界

Trae 可以做：

- 审核页面 UI。
- 表格筛选、搜索、导出。
- 读取 `clinical_review_frontend_data.json`。
- 导出审核结果 CSV/JSON。

Trae 不可以做：

- 直接写 Neo4j。
- 直接改 `nodes_final.jsonl` / `relations_final.jsonl`。
- 自动把 `pending_clinical_review` 改成 `clinical_approved`。
- 设置 `formal_cdss_ready=true`。

## 下一批心力衰竭启动前置

审核页面可以与心力衰竭批次并行推进。心力衰竭正式开工前必须确认：

```text
顶层学科：心血管内科
执行范围类型：疾病大类
目标疾病范围：心力衰竭
PDF/指南来源路径：E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南
教材/基础骨架路径：E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\书籍教材
输出路径：E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合
```
