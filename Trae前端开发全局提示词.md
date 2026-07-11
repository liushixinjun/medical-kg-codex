# Trae前端开发全局提示词

版本：V1.4
更新时间：2026-07-11 17:34:47
适用范围：专科知识图谱、专病辅助诊疗、图谱探索、临床诊断模拟、路径编辑、临床审核、Schema 标准、CDSS 前后端集成。
依据文件：

- `专科知识图谱Schema标准.md` V1.15
- `专病辅助诊疗建设方案_专科CDSS六级建设.md`
- `专科CDSS图谱查询接口与Cypher示例.md`
- `schema_v112_migration_20260711/schema_v112_postcheck_keyfix_20260711.json`

## 0. 版本修改记录

| 版本 | 时间 | 变更内容 | Trae影响 |
|---|---:|---|---|
| V1.4 | 2026-07-11 17:34:47 | Schema V1.15 所有表格已统一增加 AMI 示例列，并补具体值格式要求 | Trae 阅读 Schema 时按“格式或使用要求 + AMI示例”理解接口字段、展示字段和查询关系 |
| V1.4 | 2026-07-11 17:18:30 | Schema V1.15 §5 已补充字段格式要求和节点/关系 JSON 示例 | 前端/后端接口入参、返回字段和审核页面要按 `code/id/aliases/status/schema_version` 规范校验；别名必须按数组处理 |
| V1.4 | 2026-07-11 17:06:21 | Schema V1.15 已把实体、关系改成中文优先说明，并补充诊断标准明细、Evidence、阶段候选动作/正式推荐动作案例 | 前端页面展示优先使用中文业务含义；英文 relationType/entityType 只作为查询字段；Evidence 区域不得一次性展示疾病证据池，只展示当前推荐直连证据 |
| V1.3 | 2026-07-11 09:08:00 | Schema 主文档瘦身为 V1.14，详细历史、字段和案例迁入 `schema_docs/` | Trae 以主Schema看当前标准，以 `schema_docs/Schema关系兼容与禁用清单.md` 看兼容和禁用关系 |
| V1.3 | 2026-07-11 09:08:00 | `has_recommended_action` 仅保留为路径阶段候选动作旧命名，后续建议迁移为 `stage_has_available_action` | 前端不能把 `has_recommended_action` 展示成“当前患者正式推荐” |
| V1.2 | 2026-07-11 08:58:00 | Schema V1.13 已清理 `USES_MEDICATION`、`HAS_PROCEDURE`、`HAS_CLINICAL_MANIFESTATION` 三类旧弱语义关系 | 前端不再需要兼容这三类旧关系；如查询到应视为异常 |
| V1.2 | 2026-07-11 08:58:00 | 明确 `has_recommended_action` 与 `recommends_action` 的区别 | 阶段快捷动作和患者触发推荐必须分开展示 |
| V1.1 | 2026-07-11 22:40:00 | 更新为 Schema V1.12 关系口径，前端查询统一使用小写 snake_case 标准关系 | 旧的 `HAS_*` 大写关系不再作为正式临床事实入口 |
| V1.1 | 2026-07-11 22:40:00 | 明确 `entityType` 是节点类型字段，不能使用 `entity_type` | 查询、筛选、图例、统计全部按 `entityType` |
| V1.1 | 2026-07-11 22:40:00 | 明确诊断标准、鉴别诊断、推荐证据必须下钻到明细组件和 RecommendationStatement | 不能只展示标题节点；医生必须看到“为什么推荐/为什么排除” |
| V1.1 | 2026-07-11 22:40:00 | 增加遗留关系处理规则：`USES_MEDICATION`、`HAS_PROCEDURE`、`HAS_CLINICAL_MANIFESTATION` 仅作为章节提及，不作为 CDSS 推荐 | 防止把教材章节提到的药物/手术误当作可直接推荐 |
| V1.0 | 2026-07-07 21:50:00 | 从局部 AMI 页面提示词升级为全局提示词 | 后续统一读取本文件 |

## 1. 总原则

前端不能再做“选择一个疾病后，把检查、检验、药物、手术、治疗方案、鉴别诊断一次性无脑圈出来”的旧 CDSS 展示。

新的专科 CDSS 应按下面链路工作：

```text
患者数据 / EMR
  -> 疑似疾病识别
  -> 进入专病诊疗路径 ClinicalPathway
  -> 定位当前诊疗阶段 PathwayStage
  -> 匹配临床规则 ClinicalRule
  -> 输出推荐陈述 RecommendationStatement
  -> 推荐或阻断具体动作
  -> 展示该推荐自己的证据链 Evidence / Guideline
```

图谱负责提供医学知识、实体关系和证据链；规则引擎/路径引擎负责根据患者当前数据动态触发。

## 2. 节点字段与显示规则

1. 节点类型字段统一使用 `entityType`，不是 `entity_type`。
2. 节点去重优先使用 `code`，不要用 `name` 去重。
3. 医生界面显示名称优先级：

```text
display_name > preferred_name > name > code
```

4. 不得向医生展示技术前缀，例如：

```text
AMI诊断明细：
AMI鉴别：
EXAM-TTE
RULE-xxx
DXC-xxx
```

如果数据库返回名称仍带技术前缀，前端可兜底清理，但必须反馈给图谱数据侧修正。

## 3. Schema V1.12 正式关系口径

前端正式查询优先使用以下关系：

| 业务含义 | 标准关系 |
|---|---|
| 疾病-症状 | `has_symptom` |
| 疾病-体征 | `has_sign` |
| 疾病-病因 | `has_etiology` |
| 疾病-病理生理 | `has_pathophysiology` |
| 疾病-危险因素 | `has_risk_factor` |
| 疾病-诊断标准 | `has_diagnostic_criteria` |
| 诊断标准-明细组件 | `has_diagnostic_component` |
| 疾病-鉴别诊断 | `differentiates_from` |
| 疾病-治疗方案 | `has_treatment_plan` |
| 治疗方案-药物 | `includes_medication` |
| 治疗方案-操作/手术 | `includes_procedure` |
| 疾病-直接用药事实 | `treated_by_medication` |
| 疾病-直接操作/手术事实 | `treated_by_procedure` |
| 疾病-随访 | `has_follow_up` |
| 疾病-预后 | `has_prognosis` |
| 疾病-定义 | `has_definition` |
| 定义-定义明细 | `has_definition_component` |
| 疾病-预防 | `has_prevention` |
| 疾病-分类 | `has_classification` |
| 疾病-并发症 | `may_cause_complication` |
| 推荐-动作 | `recommends_action` / `blocks_action` |
| 推荐-证据 | `derived_from` 或 `supported_by_evidence` |
| 推荐-指南 | `based_on_guideline` |

以下旧关系已在 Schema V1.13 清理为 0，不得继续查询；如果接口返回，视为后端或图谱异常：

```text
USES_MEDICATION
HAS_PROCEDURE
HAS_CLINICAL_MANIFESTATION
```

## 4. 路径阶段动作与正式推荐动作必须区分

```text
PathwayStage -> has_recommended_action -> Action
```

含义：某诊疗阶段可展示的候选动作/快捷入口，不代表当前患者已经满足推荐条件。

```text
ClinicalRule / RecommendationStatement -> recommends_action -> Action
ClinicalRule / RecommendationStatement -> blocks_action -> Action
```

含义：患者满足规则后正式推荐或阻断的动作。医生推荐卡片必须以这条链路为准。

前端页面必须分开展示：

- 阶段候选动作：放在路径阶段或编辑器中。
- 患者触发推荐：放在 CDSS 推荐卡片中。

## 5. 推荐卡片必须从 RecommendationStatement 查询

正式 CDSS 推荐卡片不能直接从疾病、治疗方案、药物、检查节点拿证据。必须查询：

```text
ClinicalRule
  -> has_recommendation_statement
RecommendationStatement
  -> recommends_action / blocks_action
  -> derived_from / supported_by_evidence -> Evidence
  -> based_on_guideline -> Guideline
```

医生看到“急诊 PCI”“溶栓治疗”“抗凝治疗”等推荐时，只展示支持这一条推荐的主证据：

- 指南名称
- 页码/段落
- 推荐等级
- 证据等级
- 原文摘要

不要把疾病级或治疗方案级挂着的一箩筐指南全部展示给医生。

## 6. 推荐卡片后端查询示例

```cypher
MATCH (rule:KGNode {entityType:'ClinicalRule'})
      -[:has_recommendation_statement]->(rs:KGNode {entityType:'RecommendationStatement'})
OPTIONAL MATCH (rs)-[:recommends_action|blocks_action]->(action:KGNode)
OPTIONAL MATCH (rs)-[:derived_from|supported_by_evidence]->(ev:KGNode {entityType:'Evidence'})
OPTIONAL MATCH (rs)-[:based_on_guideline]->(gl:KGNode {entityType:'Guideline'})
WHERE rule.disease_code = $disease_code
RETURN rule, rs, collect(DISTINCT action) AS actions,
       collect(DISTINCT ev) AS evidence,
       collect(DISTINCT gl) AS guidelines
ORDER BY coalesce(rs.priority, 999), rs.name
```

前端展示时，推荐卡片字段建议：

```text
推荐标题
适用疾病
适用阶段
触发条件
排除/禁忌条件
推荐动作
推荐等级
证据等级
主证据摘要
采用 / 暂不采用 / 查看证据 / 查看禁忌
```

## 7. 诊断标准必须显示明细组件

错误展示：

```text
诊断标准
  急性心肌梗死诊断标准
```

正确展示：

```text
诊断标准：急性心肌梗死诊断标准
  明细组件：
    - 急性缺血症状或等效表现
    - 肌钙蛋白升高及动态变化
    - 缺血性心电图改变
    - 冠状动脉血栓或责任病变
    - 影像学新发室壁运动异常
```

查询示例：

```cypher
MATCH (d:KGNode {entityType:'Disease', code:$disease_code})
      -[:has_diagnostic_criteria]->(dx:KGNode {entityType:'DiagnosisCriteria'})
OPTIONAL MATCH (dx)-[:has_diagnostic_component]->(component:KGNode)
OPTIONAL MATCH (component)-[:derived_from|supported_by_evidence]->(ev:KGNode {entityType:'Evidence'})
RETURN d, dx,
       collect(DISTINCT component) AS components,
       collect(DISTINCT ev) AS evidence
```

注意：截至 2026-07-11 服务器仍有 31 条 `DiagnosisCriteria` 暂无 `has_diagnostic_component` 明细。前端遇到这种节点时显示“待补明细”，不要伪造明细。

## 8. 鉴别诊断必须显示鉴别要点

错误展示：

```text
鉴别诊断
  主动脉夹层
  肺栓塞
```

正确展示：

```text
主动脉夹层
  鉴别要点：撕裂样胸背痛、双上肢血压差、主动脉影像异常
  排除检查：主动脉 CTA、床旁超声
  治疗影响：未排除前阻断溶栓
  证据来源：对应 Evidence / Guideline
```

查询示例：

```cypher
MATCH (d:KGNode {entityType:'Disease', code:$disease_code})
      -[:differentiates_from]->(ddx:KGNode)
OPTIONAL MATCH (ddx)-[:has_differential_point]->(point:KGNode)
OPTIONAL MATCH (point)-[:derived_from|supported_by_evidence]->(ev:KGNode {entityType:'Evidence'})
RETURN d, ddx,
       collect(DISTINCT point) AS differential_points,
       collect(DISTINCT ev) AS evidence
```

## 9. 图谱探索页面改造要求

图谱探索页可分两层：

1. 知识浏览层：疾病下有哪些症状、体征、检查、治疗方案、定义、诊断标准、鉴别诊断。
2. CDSS 使用层：当前患者条件触发了哪些规则、推荐了什么动作、为什么推荐、为什么不能推荐。

不要把两层混在一个列表里。
知识浏览可以展示“这个疾病有哪些治疗方案”；CDSS 使用必须展示“当前患者为什么适用这个治疗方案”。

## 10. 路径编辑器改造要求

路径编辑器不是维护“治疗方案节点”的地方，而是维护专病诊疗流程：

```text
PathwayStage 阶段
  -> ClinicalRule 触发规则
  -> RecommendationStatement 推荐陈述
  -> Action 推荐动作
  -> Evidence/Guideline 证据链
```

阶段名称可以是“疑似识别、确诊评估、危险分层、急性处理、长期管理、随访复评”等；治疗方案节点是被阶段调用的动作对象，不要和阶段节点混为一类。

## 11. 后端接口建议

至少提供 4 个接口：

```text
GET /api/kg/disease/{code}/overview
GET /api/kg/disease/{code}/diagnosis
GET /api/kg/disease/{code}/recommendations?stage=xxx
GET /api/kg/disease/{code}/evidence?recommendation_code=xxx
```

返回结构必须区分：

```json
{
  "disease": {},
  "knowledge_overview": {},
  "pathway_stage": {},
  "triggered_rules": [],
  "recommendations": [],
  "evidence": [],
  "warnings": []
}
```

`warnings` 用于提示“该诊断标准暂无明细”“该节点是章节提及，不是正式推荐”等数据状态。

## 12. 当前服务器状态，供 Trae 核对

2026-07-11 Schema V1.12 迁移后：

- 总节点：43020
- 总关系：139512
- `TextbookSection`、`ClinicalManifestation` 节点残留：0
- `SourceSection`：75
- `knowledge_layer=textbook_core`：1860
- 新标准关系重复三元组：0
- 仍残留旧关系：0
- 推荐陈述：560
  - 缺证据：0
  - 缺指南：0
  - 缺推荐动作：3
- 诊断标准：81
  - 有明细组件：50
  - 暂无明细组件：31

前端不要再查询 `USES_MEDICATION`、`HAS_PROCEDURE`、`HAS_CLINICAL_MANIFESTATION`。如发现返回非 0，说明后端查询或图谱数据回退。

## 13. 本轮必须修正的页面问题

1. AMI 诊断标准必须下钻 `has_diagnostic_component`，不能只显示“急性心肌梗死诊断标准”标题。
2. AMI 鉴别诊断不要显示“AMI鉴别：”前缀，直接显示临床名称和鉴别要点。
3. 证据与指南不要疾病级一箩筐展示，推荐卡片只展示该推荐自己的主证据。
4. 所有查询统一使用 `entityType` 和小写标准关系。
5. 旧大写关系只放“遗留数据提示”，不得进入正式 CDSS 推荐。
