# 专科CDSS图谱查询接口与 Cypher 示例

版本：V1.0  
日期：2026-07-07 22:10:00  
定位：`专病辅助诊疗建设方案_专科CDSS六级建设.md` 的开发实施附件  
适用对象：后端、Trae 前端、规则引擎、专病诊疗路径编辑器  
适用图谱：Neo4j 专科知识图谱，实体以 `KGNode.code` 唯一识别，类型以 `entityType` 为准

## 1. 文件关系

```text
专病辅助诊疗建设方案_专科CDSS六级建设.md
  = 产品方案、业务链路、架构原则

专科CDSS图谱查询接口与Cypher示例.md
  = 开发实施附件，说明接口怎么设计、Cypher 怎么写、返回结构怎么组织
```

开发同事不要直接拿 Schema 猜查询路径，优先按本文接口实现。

## 2. 总体调用链

```text
患者 EMR 数据
  -> 疑似疾病识别
  -> 查询疾病概览
  -> 查询诊断标准明细
  -> 查询鉴别诊断明细
  -> 进入 ClinicalPathway
  -> 匹配 PathwayStage
  -> 匹配 ClinicalRule
  -> 读取 RecommendationStatement
  -> 展示推荐动作、阻断动作、证据和指南
```

正式 CDSS 推荐必须以 `RecommendationStatement` 为根，不得从疾病证据池或动作证据池反推依据。

## 3. 通用返回规则

### 3.1 节点显示名

```text
display_name > preferred_name > name > code
```

### 3.2 节点去重

```text
按 code 去重，不按 name 去重。
```

### 3.3 类型判断

```text
以 entityType 为准，不依赖 labels(n) 顺序。
```

### 3.4 推荐证据

医生看到某条推荐时，只展示该推荐自己的证据链：

```text
RecommendationStatement
  -> derived_from Evidence
  -> based_on_guideline Guideline
```

## 4. 接口清单

| 接口 | 用途 | 前端页面 |
|---|---|---|
| `GET /api/kg/summary` | 图谱总览统计 | 数据总览 |
| `GET /api/kg/disease/{disease_code}/overview` | 疾病概览 | 图谱探索、专病首页 |
| `GET /api/kg/disease/{disease_code}/diagnostic-criteria` | 诊断标准与下级明细 | 诊断标准卡片 |
| `GET /api/kg/disease/{disease_code}/differentials` | 鉴别诊断与鉴别要点 | 鉴别诊断卡片 |
| `GET /api/kg/disease/{disease_code}/pathways` | 专病路径、阶段、规则、推荐 | 专病诊疗路径 |
| `POST /api/cdss/simulate` | 根据患者数据动态模拟推荐 | 临床诊断模拟 |
| `GET /api/cdss/recommendation/{recommendation_code}` | 单条推荐证据详情 | 推荐卡片详情 |
| `GET /api/kg/schema` | Schema 字典 | Schema 页面 |
| `POST /api/pathway/editor/validate` | 路径编辑器保存前校验 | 路径编辑 |

## 5. 图谱总览

### 5.1 接口

```text
GET /api/kg/summary
```

### 5.2 Cypher

```cypher
MATCH (n:KGNode)
WITH count(n) AS entity_count
MATCH ()-[r]-()
WITH entity_count, count(DISTINCT r) AS relation_count
OPTIONAL MATCH (d:KGNode {entityType:'Disease'})
OPTIONAL MATCH (cat:KGNode {entityType:'DiseaseCategory'})
RETURN
  entity_count,
  relation_count,
  count(DISTINCT d) AS disease_count,
  count(DISTINCT cat) AS disease_category_count
```

### 5.3 返回字段

```json
{
  "disease_category_count": 11,
  "disease_count": 92,
  "entity_count": 35035,
  "relation_count": 104312
}
```

## 6. 疾病概览

### 6.1 接口

```text
GET /api/kg/disease/{disease_code}/overview
```

### 6.2 Cypher

```cypher
MATCH (d:KGNode {entityType:'Disease', code:$disease_code})
OPTIONAL MATCH (d)-[r]->(target:KGNode)
RETURN
  d,
  type(r) AS relation_type,
  target.entityType AS target_type,
  collect(DISTINCT target) AS targets
```

### 6.3 使用说明

这个接口只做知识概览，不用于正式 CDSS 推荐。

正式推荐必须走：

```text
ClinicalRule -> RecommendationStatement
```

## 7. 诊断标准明细

### 7.1 接口

```text
GET /api/kg/disease/{disease_code}/diagnostic-criteria
```

### 7.2 Cypher

```cypher
MATCH (d:KGNode {entityType:'Disease', code:$disease_code})
      -[:has_diagnostic_criteria]->(dx:KGNode {entityType:'DiagnosisCriteria'})
OPTIONAL MATCH (dx)-[:has_diagnostic_component]->(rule:KGNode {entityType:'ClinicalRule'})
OPTIONAL MATCH (rule)-[:has_recommendation_statement]->(rs:KGNode {entityType:'RecommendationStatement'})
OPTIONAL MATCH (rs)-[:derived_from]->(ev:KGNode {entityType:'Evidence'})
OPTIONAL MATCH (rs)-[:based_on_guideline]->(g:KGNode {entityType:'Guideline'})
RETURN
  dx,
  collect(DISTINCT {
    rule_code: rule.code,
    rule_name: coalesce(rule.display_name, rule.preferred_name, rule.name, rule.code),
    rule_logic: rule.rule_logic,
    recommendations: rs.code,
    evidence_count: count(DISTINCT ev),
    guideline_count: count(DISTINCT g)
  }) AS components
```

### 7.3 AMI 示例展示

```text
急性心肌梗死诊断标准
  - 急性缺血症状或等效表现
  - 肌钙蛋白升高及动态变化
  - 缺血性心电图改变
  - 冠状动脉血栓或责任病变
  - 影像学新发室壁运动异常
```

前端不得只展示“急性心肌梗死诊断标准”标题。

## 8. 鉴别诊断明细

### 8.1 接口

```text
GET /api/kg/disease/{disease_code}/differentials
```

### 8.2 Cypher

```cypher
MATCH (d:KGNode {entityType:'Disease', code:$disease_code})
      -[:has_differential_diagnosis]->(ddx:KGNode {entityType:'DifferentialDiagnosis'})
OPTIONAL MATCH (ddx)-[:has_differential_point]->(rule:KGNode {entityType:'ClinicalRule'})
OPTIONAL MATCH (rule)-[:has_recommendation_statement]->(rs:KGNode {entityType:'RecommendationStatement'})
OPTIONAL MATCH (rs)-[:blocks_action|recommends_action]->(action:KGNode)
OPTIONAL MATCH (rs)-[:derived_from]->(ev:KGNode {entityType:'Evidence'})
RETURN
  ddx,
  collect(DISTINCT {
    rule_code: rule.code,
    point_name: coalesce(rule.display_name, rule.preferred_name, rule.name, rule.code),
    point_logic: rule.rule_logic,
    recommendation_code: rs.code,
    action_code: action.code,
    action_name: coalesce(action.display_name, action.preferred_name, action.name, action.code),
    evidence_count: count(DISTINCT ev)
  }) AS differential_points
```

### 8.3 展示要求

```text
主动脉夹层
  鉴别要点：撕裂样胸背痛、双上肢血压差、主动脉影像异常
  建议排除检查：主动脉 CTA、床旁超声
  治疗影响：未排除前阻断溶栓
```

前端不得只列“主动脉夹层、肺栓塞、心包炎”名称。

## 9. 专病诊疗路径

### 9.1 接口

```text
GET /api/kg/disease/{disease_code}/pathways
```

### 9.2 Cypher

```cypher
MATCH (d:KGNode {entityType:'Disease', code:$disease_code})
      -[:has_clinical_pathway]->(p:KGNode {entityType:'ClinicalPathway'})
OPTIONAL MATCH (p)-[:has_pathway_stage]->(s:KGNode {entityType:'PathwayStage'})
OPTIONAL MATCH (s)-[:has_stage_rule]->(rule:KGNode {entityType:'ClinicalRule'})
OPTIONAL MATCH (rule)-[:has_recommendation_statement]->(rs:KGNode {entityType:'RecommendationStatement'})
OPTIONAL MATCH (rs)-[:recommends_action|blocks_action]->(action:KGNode)
RETURN
  p,
  s,
  collect(DISTINCT rule) AS rules,
  collect(DISTINCT rs) AS recommendations,
  collect(DISTINCT action) AS actions
ORDER BY s.stage_order
```

### 9.3 阶段展示

```text
阶段名称
阶段目标
进入条件
退出条件
需要的患者数据
已触发规则
推荐动作
阻断动作
证据摘要
```

## 10. CDSS 动态模拟

### 10.1 接口

```text
POST /api/cdss/simulate
```

### 10.2 请求体

```json
{
  "disease_code": "DIS-CARD-CAD-STEMI",
  "patient_facts": {
    "chief_complaint": "胸痛2小时",
    "ecg_st_elevation": true,
    "troponin_dynamic_change": true,
    "onset_hours": 2,
    "pci_available_minutes": 90,
    "suspected_aortic_dissection": false,
    "active_bleeding": false
  }
}
```

### 10.3 后端处理逻辑

```text
1. 读取 disease_code 对应 ClinicalPathway
2. 按 PathwayStage.stage_order 排序
3. 用 patient_facts 匹配 ClinicalRule.trigger_condition / rule_logic
4. 命中规则后读取 RecommendationStatement
5. 输出推荐动作、阻断动作、缺失数据、证据摘要
```

### 10.4 返回结构

```json
{
  "disease_code": "DIS-CARD-CAD-STEMI",
  "current_stage": {
    "code": "STAGE-CARD-CAD-STEMI-03-REPERFUSION-DECISION",
    "name": "STEMI再灌注决策阶段"
  },
  "recommendations": [
    {
      "recommendation_code": "REC-xxxx",
      "title": "STEMI再灌注策略选择规则｜急诊PCI（操作/手术）推荐",
      "type": "recommend",
      "action_name": "急诊PCI",
      "recommendation_class": "I",
      "evidence_level": "A",
      "primary_guideline_name": "指南名称",
      "primary_evidence_code": "EVD-xxxx"
    }
  ],
  "blocked_actions": [],
  "missing_data": []
}
```

## 11. 单条推荐证据详情

### 11.1 接口

```text
GET /api/cdss/recommendation/{recommendation_code}
```

### 11.2 Cypher

```cypher
MATCH (rs:KGNode {entityType:'RecommendationStatement', code:$recommendation_code})
OPTIONAL MATCH (rs)-[:recommends_action|blocks_action]->(action:KGNode)
OPTIONAL MATCH (rs)-[:derived_from]->(ev:KGNode {entityType:'Evidence'})
OPTIONAL MATCH (rs)-[:based_on_guideline]->(g:KGNode {entityType:'Guideline'})
RETURN
  rs,
  action,
  collect(DISTINCT {
    evidence_code: ev.code,
    source_name: ev.source_name,
    source_section: ev.source_section,
    recommendation_class: ev.recommendation_class,
    evidence_level: ev.evidence_level,
    evidence_text: ev.evidence_text
  }) AS evidences,
  collect(DISTINCT {
    guideline_code: g.code,
    guideline_name: coalesce(g.display_name, g.preferred_name, g.name, g.code),
    document_id: g.document_id,
    publication_year: g.publication_year
  }) AS guidelines
```

### 11.3 医生界面只默认展示

```text
指南名称
页码/段落
推荐等级
证据等级
原文摘要
```

完整原文折叠展示，不要默认铺满页面。

## 12. 路径编辑器保存前校验

### 12.1 接口

```text
POST /api/pathway/editor/validate
```

### 12.2 必查规则

```text
RecommendationStatement 必须连接至少 1 个 Action
RecommendationStatement 必须连接至少 1 个 Evidence
正式 CDSS 推荐必须有 recommendation_class、evidence_level
ClinicalRule 必须有 rule_logic 或 trigger_condition
阻断推荐必须有 contraindication_conditions 或明确阻断说明
PathwayStage.name 不得等于 TreatmentPlan.name
同一列表按 code 去重
```

## 13. 前端验收清单

```text
1. AMI 诊断标准能看到 5 个诊断明细组件
2. 鉴别诊断能看到鉴别要点、排除检查、治疗影响
3. 推荐卡片来自 RecommendationStatement
4. 急诊PCI、溶栓、抗凝等推荐只显示自身证据
5. 页面不出现 AMI诊断明细、AMI鉴别、EXAM-TTE 等技术前缀
6. 相同动作在不同规则下不被错误合并
7. entityType 不依赖 Neo4j 标签顺序
8. 所有节点按 code 去重
9. 路径编辑器保存前能拦截无证据推荐
10. 前端不要用“查疾病全部邻居节点”作为 CDSS 推荐逻辑
```

## 14. 和 Oracle/EMR 的关系

Oracle/EMR 提供患者事实字段，例如：

```text
主诉
现病史
诊断
检验结果
检查结果
用药
生命体征
禁忌证
手术/操作记录
```

图谱不直接替代 Oracle 表。后端需要把 Oracle/EMR 字段转换为 `patient_facts`，再交给 CDSS 路径引擎匹配 `ClinicalRule`。

最小映射示例：

| EMR/Oracle字段 | patient_facts | 图谱使用点 |
|---|---|---|
| 主诉/现病史 | `chief_complaint`、`symptoms` | 疑似疾病、诊断标准 |
| 心电图结论 | `ecg_st_elevation`、`arrhythmia_type` | 诊断规则、路径阶段 |
| 肌钙蛋白 | `troponin_dynamic_change` | AMI 诊断标准 |
| 发病时间 | `onset_hours` | 再灌注决策 |
| 禁忌证 | `contraindications` | 阻断推荐 |
| 当前用药 | `current_medications` | 药物推荐/相互作用 |

## 15. 开发结论

前端和后端真正需要掌握的是这条主链：

```text
Disease
  -> ClinicalPathway
  -> PathwayStage
  -> ClinicalRule
  -> RecommendationStatement
  -> Action
  -> Evidence / Guideline
```

诊断标准和鉴别诊断必须下钻到规则/明细；正式推荐必须下钻到 `RecommendationStatement`。
