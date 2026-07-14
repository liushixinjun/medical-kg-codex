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

实施时不要直接拿 Schema 猜查询路径，优先按本文接口实现。

## 2. 总体调用链

```text
患者 EMR 数据
  -> 疑似疾病识别
  -> 查询疾病概览
  -> 查询诊断标准明细
  -> 查询鉴别诊断明细
  -> 定位推荐阶段 stage_code
  -> 匹配规则 rule_code
  -> 读取 RecommendationStatement
  -> 展示推荐动作、需补充判断的信息、证据和指南
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
      -[rel:differentiates_from]->(ddx:KGNode {entityType:'DifferentialDiagnosis'})
RETURN
  ddx.code AS differential_code,
  coalesce(ddx.display_name, ddx.preferred_name, ddx.name) AS differential_name,
  rel.evidence_text AS evidence_text,
  rel.source_name AS source_name,
  rel.source_page AS source_page
```

### 8.3 展示要求

```text
主动脉夹层
  图谱关系：Disease -differentiates_from-> DifferentialDiagnosis
  展示内容：鉴别名称、证据摘要、来源文件、来源页码
  业务影响：未排除前应提示医生关注，不直接进入溶栓类处理
```

前端不得只列“主动脉夹层、肺栓塞、心包炎”名称。

## 9. 专病诊疗路径

### 9.1 接口

```text
GET /api/kg/disease/{disease_code}/pathways
```

### 9.2 Cypher

```cypher
MATCH (rs:KGNode {entityType:'RecommendationStatement'})
WHERE rs.stage_code IS NOT NULL
  AND (
    rs.code CONTAINS replace($disease_code, 'DIS-', '')
    OR rs.stage_code CONTAINS replace($disease_code, 'DIS-', '')
    OR rs.code STARTS WITH 'REC-CDSS-CAD-AMI'
  )
OPTIONAL MATCH (rs)-[:recommends_action]->(action:KGNode)
RETURN
  rs.stage_code AS stage_code,
  rs.rule_code AS rule_code,
  collect(DISTINCT rs{.code, .name, .statement_text, .recommendation_class, .evidence_level}) AS recommendations,
  collect(DISTINCT action{.code, .name, .entityType}) AS actions
ORDER BY stage_code, rule_code
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
需补充判断的信息
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
1. 从 patient_facts 分拣症状、体征、危险因素
2. 先做疑似疾病识别，胸痛急症场景按症状、体征、诊断标准和检查检验闭环评分
3. 医生关注或确认疾病后，读取 RecommendationStatement.stage_code / rule_code
4. 用 patient_facts 匹配 RecommendationStatement 对应规则条件
5. 输出推荐动作、需补充判断的信息、证据摘要
```

### 10.4 返回结构

```json
{
  "disease_code": "DIS-CARD-CAD-AMI",
  "current_stage": {
    "code": "STAGE-CDSS-CAD-AMI-02-REPERFUSION",
    "name": "AMI再灌注评估阶段"
  },
  "recommendations": [
    {
      "recommendation_code": "REC-CDSS-CAD-AMI-02-01-REPERFUSION",
      "title": "AMI患者应结合分型、时间窗和PCI可及性评估急诊PCI、溶栓或冠脉造影。",
      "type": "recommend",
      "action_code": "PROC-CARD-E9ADC25A25E3",
      "action_name": "经皮冠状动脉介入治疗",
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

### 10.5 疑似疾病排序规则

截图类输入：

```json
{
  "chief_complaint": "胸痛2小时",
  "history": "胸痛、出汗、恶心呕吐",
  "past_history": "高血压、糖尿病"
}
```

应先按当前阳性症状、体征、检查检验异常召回 `Disease`，再用诊断标准、检查检验闭环和危险因素做评分。`高血压`、`糖尿病`在该场景中只能作为 `RiskFactor` 命中依据，不单独召回为推荐诊断。

```cypher
MATCH (d:KGNode {entityType:'Disease'})
OPTIONAL MATCH (d)-[:has_symptom]->(s:KGNode {entityType:'Symptom'})
  WHERE s.name IN $symptom_names
OPTIONAL MATCH (d)-[:has_sign]->(sg:KGNode {entityType:'Sign'})
  WHERE sg.name IN $sign_names
OPTIONAL MATCH (d)-[:has_risk_factor]->(rf:KGNode {entityType:'RiskFactor'})
  WHERE rf.name IN $risk_factor_names
OPTIONAL MATCH (d)-[:requires_exam]->(exam:KGNode {entityType:'Exam'})
OPTIONAL MATCH (d)-[:requires_lab_test]->(lab:KGNode {entityType:'LabTest'})
OPTIONAL MATCH (d)-[:has_diagnostic_criteria]->(dx:KGNode {entityType:'DiagnosisCriteria'})
OPTIONAL MATCH (d)-[:differentiates_from]->(ddx:KGNode {entityType:'DifferentialDiagnosis'})
WITH d,
     collect(DISTINCT s.name) AS hit_symptoms,
     collect(DISTINCT sg.name) AS hit_signs,
     collect(DISTINCT rf.name) AS hit_risk_factors,
     count(DISTINCT exam) AS exam_count,
     count(DISTINCT lab) AS lab_count,
     count(DISTINCT dx) AS diagnostic_criteria_count,
     count(DISTINCT ddx) AS differential_count
WITH d, hit_symptoms, hit_signs, hit_risk_factors,
     size(hit_symptoms) * 5
       + size(hit_signs) * 5
       + size(hit_risk_factors) * 1
       + CASE WHEN diagnostic_criteria_count > 0 THEN 2 ELSE 0 END
       + CASE WHEN exam_count + lab_count > 0 THEN 2 ELSE 0 END
       + CASE WHEN differential_count > 0 THEN 1 ELSE 0 END AS score
WHERE size(hit_symptoms) + size(hit_signs) > 0
RETURN d.code AS disease_code,
       coalesce(d.display_name, d.name) AS disease_name,
       score,
       hit_symptoms,
       hit_signs,
       hit_risk_factors,
       CASE
         WHEN size(hit_symptoms) + size(hit_signs) > 0 THEN 'suspected_diagnosis'
         ELSE 'risk_context'
       END AS recommendation_role
ORDER BY score DESC, disease_name
LIMIT 10
```

该输入下，首屏不要求靠手写名单固定排序，但应满足以下原则：

```text
1. 命中当前症状/体征的疾病进入 suspected_diagnosis。
2. 只命中高血压、糖尿病等危险因素的疾病进入 risk_context，不进入推荐诊断。
3. 同分或接近同分时，具备诊断标准、推荐检查检验、鉴别诊断关系的疾病优先。
4. 检查检验结果返回后，再用诊断标准明细和 RecommendationStatement 继续收敛。
```

因此，`高血压`不应仅因既往史中出现而作为推荐诊断。`不稳定型心绞痛`、`心肌炎`是否进入前列，取决于它们与当前阳性症状、体征、诊断标准和检查检验闭环的综合得分，而不是人工写死优先级。

### 10.6 AMI 完整模拟用例

第一步只输入一诉五史和体征，接口应返回疑似诊断、命中依据和下一步检查检验。

后端处理一诉五史时，先把原始病历文字拆成系统能用的小项。简单说：主诉和现病史拆成“这次有什么症状”，既往史、个人史、家族史拆成“风险高不高”，过敏史拆成“后面用药安不安全”。技术上建议生成标准化 `patient_facts`，不要直接把原始文本拿去拼查询。

| 原始字段 | 标准化 facts | 用途 |
|---|---|---|
| `chief_complaint` | `symptoms` | 疑似疾病召回主入口 |
| `present_illness` | `symptoms`、`duration`、`severity`、`associated_symptoms` | 疑似疾病加权、鉴别诊断、紧急程度判断 |
| `past_history` | `risk_factors`、`past_diseases` | 风险背景和加分，不单独生成推荐诊断 |
| `personal_history` | `risk_factors` | 风险背景、宣教和随访管理 |
| `family_history` | `risk_factors` | 风险分层 |
| `allergy_history` | `allergies` | 用药、造影和介入安全提醒 |
| `physical_exam` | `signs`、`vital_signs` | 疑似疾病加权、重症风险和治疗安全评估 |

示例标准化结果：

```json
{
  "patient_facts": {
    "symptoms": ["胸痛", "出汗", "恶心呕吐"],
    "signs": ["低血压", "心动过速", "皮肤湿冷"],
    "risk_factors": ["高血压", "糖尿病", "吸烟"],
    "duration": {
      "chest_pain_hours": 2
    },
    "allergies": [],
    "negative_facts": ["否认药物过敏史"]
  }
}
```

```json
{
  "patient_context": {
    "name": "张某",
    "sex": "男",
    "age": 58,
    "department": "心血管内科"
  },
  "chief_complaint": "胸痛2小时",
  "present_illness": "胸骨后压榨样疼痛，持续不缓解，伴出汗、恶心呕吐",
  "past_history": "高血压10年，糖尿病5年",
  "personal_history": "吸烟30年",
  "family_history": "父亲有冠心病史",
  "allergy_history": "否认药物过敏史",
  "physical_exam": "血压95/60mmHg，心率110次/分，皮肤湿冷"
}
```

第一步预期返回：

```json
{
  "stage": "initial_suspected_diagnosis",
  "recommendations": [
    {
      "disease_code": "DIS-CARD-CAD-ACS",
      "disease_name": "急性冠脉综合征",
      "recommendation_role": "suspected_diagnosis",
      "hit_symptoms": ["胸痛", "出汗", "恶心呕吐"],
      "hit_risk_factors": ["高血压", "糖尿病", "吸烟"],
      "next_step": ["EXAM-ECG", "LAB-CARD-A9EC1D4DA037"]
    },
    {
      "disease_code": "DIS-CARD-CAD-AMI",
      "disease_name": "急性心肌梗死",
      "recommendation_role": "suspected_diagnosis",
      "hit_symptoms": ["胸痛", "出汗", "恶心呕吐"],
      "hit_risk_factors": ["高血压", "糖尿病", "吸烟"],
      "next_step": ["EXAM-ECG", "LAB-CARD-A9EC1D4DA037"]
    }
  ],
  "risk_context": ["高血压", "糖尿病", "吸烟"],
  "differentials": ["主动脉夹层", "肺栓塞", "急性心包炎", "冠状动脉痉挛"]
}
```

第二步回填检查检验报告后，再收敛诊断和治疗建议。

```json
{
  "focused_disease_code": "DIS-CARD-CAD-AMI",
  "exam_results": {
    "EXAM-ECG": "II、III、aVF导联ST段抬高",
    "EXAM-TTE": "下壁节段性室壁运动异常",
    "aortic_dissection_excluded": true
  },
  "lab_results": {
    "LAB-CARD-A9EC1D4DA037": "心肌肌钙蛋白0h升高，1h复查继续升高",
    "LAB-CARD-960C7CE8E22B": "肌酸激酶同工酶升高"
  },
  "clinical_facts": {
    "onset_hours": 2,
    "pci_available_minutes": 90,
    "active_bleeding": false
  }
}
```

第二步预期返回：

```json
{
  "diagnosis": {
    "disease_code": "DIS-CARD-CAD-AMI",
    "disease_name": "急性心肌梗死",
    "subtype_code": "DIS-CARD-CAD-STEMI",
    "subtype_name": "ST段抬高型心肌梗死",
    "supporting_evidence": ["胸痛持续不缓解", "ST段抬高", "心肌肌钙蛋白动态升高", "节段性室壁运动异常"]
  },
  "treatment_suggest": {
    "stage_code": "STAGE-CDSS-CAD-AMI-02-REPERFUSION",
    "recommendation_code": "REC-CDSS-CAD-AMI-02-01-REPERFUSION",
    "recommended_actions": [
      {
        "action_code": "PROC-CARD-E9ADC25A25E3",
        "action_name": "经皮冠状动脉介入治疗"
      }
    ],
    "missing_or_attention": ["确认PCI可及性", "评估出血风险", "持续关注肺栓塞等鉴别诊断"]
  }
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
OPTIONAL MATCH (rs)-[:recommends_action]->(action:KGNode)
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
  -> 疑似疾病识别
  -> DiagnosisCriteria / DifferentialDiagnosis
  -> RecommendationStatement(stage_code, rule_code)
  -> recommends_action
  -> Evidence / Guideline
```

诊断标准和鉴别诊断必须下钻到规则/明细；正式推荐必须下钻到 `RecommendationStatement`。
