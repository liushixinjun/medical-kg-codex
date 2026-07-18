# 专科知识图谱 Schema 标准

版本：V2.0（CDSS 标准主数据融合与疾病分型升级版）
状态：正式执行标准
更新时间：2026-07-19 00:19:13
适用范围：所有专科、疾病大类、单病种知识图谱，以及专科 CDSS 诊断、检查、检验、用药、手术、治疗和随访场景。

## 0. 版本说明

| 时间 | 版本 | 变更类型 | 说明 | AMI 示例 |
|---|---|---|---|---|
| 2026-07-19 00:19:13 | V2.0 | 大版本升级 | 统一疾病三层诊断结构；新增 CDSS 标准诊断、标准手术主数据层；拆分检查项目/检查发现、检验项目/检验细项；固化年龄、性别、妊娠、哺乳基础过滤；停用 `DiseaseClassification`、`Exam`、`LabTest`、`ExamIndicator` 新增写入。 | 冠心病 → 急性心肌梗死 → STEMI/NSTEMI → CDSS 标准诊断 |
| 2026-07-17 17:10:00 | V1.17 | 推荐来源裁决 | 正式推荐增加主依据、支持依据、冲突状态和裁决理由。 | STEMI 再灌注推荐来源裁决 |

升级前基线：Git 标签 `baseline-schema-v1.17-skill-v2.5-20260718`。历史字段细则和旧版本记录保存在 `schema_docs/`，本文件只保留当前正式标准。

## 1. 核心原则

1. 基础权威教材、专科专著搭建疾病骨架，诊疗指南、专家共识和临床路径补充可执行决策。
2. CDSS 已有标准字典是诊断、症状、体征、检查、检验、检验细项、检验标本、药品、手术、治疗、生命体征和医学术语的主数据来源；匹配成功时直接使用其标准名称、编码和 UUID，不再另建同义实体。
3. 疾病目录、临床疾病和标准诊断是三个不同概念：目录负责组织，疾病负责医学知识，标准诊断负责 CDSS/EMR 编码落地。
4. 症状和体征分开；检查和检验分开；检查项目和检查发现分开；检验项目和检验细项分开。
5. 简单人群限制使用标准主数据属性预过滤；肾功能、肝功能、过敏、相互作用、出血风险、时间窗等复杂条件由临床规则表达。
6. 图谱中的知识浏览关系不等于患者正式推荐。正式推荐必须经过路径阶段、临床规则、推荐陈述、标准动作、证据和指南来源裁决。
7. 所有新增关系使用小写下划线命名；中文业务名必须与技术编码同时提供，不允许只写英文编码。
8. 标准字典未命中的实体进入注册队列；注册前可用于知识整理，但不得作为正式医嘱、诊断回填或 CDSS 推荐动作。
9. 写库前本地审计，写库后服务器复核；两次硬闸门均通过才算正式完成。

## 2. 总体架构

### 2.1 疾病三层核心结构

| 层级 | 中文名称 | 实体类型编码 | 业务含义 | 是否可作为诊断 | AMI 示例 |
|---:|---|---|---|---|---|
| 1 | 顶层学科 | `Specialty` | 多学科根目录，必须保留。 | 否 | 心血管内科 |
| 2 | 疾病大类 | `DiseaseCategory` | 组织一组相关疾病，只用于目录和展示。 | 否 | 冠心病 |
| 3 | 临床疾病 | `Disease` | 可表示待分型/初步诊断，也可表示确诊分型；具体层级由疾病关系决定。 | 是 | 急性心肌梗死、STEMI、NSTEMI |

标准关系：

```text
心血管内科(Specialty)
  -> has_disease_category -> 冠心病(DiseaseCategory)
    -> has_disease -> 急性心肌梗死(Disease，待分型/初步诊断)
      -> has_clinical_subtype -> ST段抬高型心肌梗死(Disease，具体分型)
      -> has_clinical_subtype -> 非ST段抬高型心肌梗死(Disease，具体分型)
```

硬规则：

- `DiseaseCategory` 不是诊断，不保存 ICD 编码，不回填 EMR。
- 宽口径 `Disease` 可作为疑似/初步诊断；其具体分型仍使用 `Disease`，不再新建第四层实体类型。
- `DiseaseSubcategory` 只作为可选展示分组，不计入核心三层，不得替代诊断。
- `DiseaseClassification` 自 V2.0 起停止新增。

### 2.2 疾病亚类的可选用途

| 中文名称 | 实体类型编码 | 用途 | 禁止用途 | AMI 示例 |
|---|---|---|---|---|
| 疾病亚类/展示分组 | `DiseaseSubcategory` | 在一个疾病大类下组织临床谱系、表型组或页面分组。 | 不作为疑似诊断、不保存诊断编码、不回填 EMR、不统计为疾病。 | 急性冠脉综合征展示分组 |

一次性标签优先放入 `classification_tags` 属性；只有多个疾病需要长期共享同一分组时才建立 `DiseaseSubcategory`。

### 2.3 知识、主数据和决策层

| 层 | 解决的问题 | 主要实体 | AMI 示例 |
|---|---|---|---|
| 疾病知识层 | 这个病是什么、有哪些表现、如何检查和治疗。 | `Disease`、`Definition`、`Symptom`、`Sign`、`ExamItem`、`LabItem`、`TreatmentPlan` | AMI 定义、胸痛、心电图、肌钙蛋白、再灌注方案 |
| CDSS 标准主数据层 | 如何对应系统标准字典和医嘱/诊断编码。 | `StandardDiagnosis`、`StandardProcedure`，以及来自 CDSS 字典的症状、体征、检查、检验、药品、治疗实体 | I21.900 急性心肌梗死、经皮冠状动脉介入治疗 |
| 临床决策层 | 当前患者何时触发、推荐什么、为什么。 | `ClinicalPathway`、`PathwayStage`、`ClinicalRule`、`RecommendationStatement`、`Evidence`、`Guideline` | STEMI 且 PCI 可及 → 推荐急诊 PCI |

## 3. 标准实体类型

> “实体类型编码”供 Neo4j、接口和脚本使用；医生端展示中文名称。所有示例统一使用 AMI。

### 3.1 目录、疾病和标准诊断

| 中文名称 | 实体类型编码 | 使用要求 | AMI 示例 |
|---|---|---|---|
| 顶层学科 | `Specialty` | 多学科根节点；`code` 全局唯一。 | 心血管内科 |
| 疾病大类 | `DiseaseCategory` | 目录实体，不保存诊断编码。 | 冠心病 |
| 疾病亚类/展示分组 | `DiseaseSubcategory` | 可选；`display_only=true`。 | 急性冠脉综合征 |
| 临床疾病 | `Disease` | 待分型疾病和具体分型统一使用该类型。 | 急性心肌梗死、STEMI、NSTEMI |
| CDSS 标准诊断 | `StandardDiagnosis` | 一条实体对应 Oracle 标准诊断字典的一条有效记录，名称、编码和 UUID 原样使用。 | I21.900 急性心肌梗死 |

### 3.2 疾病医学事实

| 中文名称 | 实体类型编码 | 使用要求 | AMI 示例 |
|---|---|---|---|
| 疾病定义 | `Definition` | 疾病概述原文或忠实摘要；不得只写标题。 | 急性心肌梗死定义 |
| 定义明细 | `DefinitionComponent` | 定义中的独立要点，可单独追溯。 | 急性心肌缺血导致心肌坏死 |
| 病因 | `Etiology` | 标准化短语。 | 斑块破裂继发血栓形成 |
| 病理生理 | `Pathophysiology` | 机制和病理过程。 | 冠脉闭塞导致持续心肌缺血 |
| 流行病学 | `Epidemiology` | 数值必须带时间、人群、单位和来源。 | AMI 发病率变化 |
| 症状 | `Symptom` | 患者主观感受；与体征分开。 | 持续胸痛 |
| 体征 | `Sign` | 医生客观观察结果；与症状分开。 | 心包摩擦音、低血压 |
| 危险因素 | `RiskFactor` | 增加患病或不良结局风险的因素。 | 吸烟、高血压、糖尿病 |
| 并发症 | `Complication` | 疾病导致的并发问题。 | 心力衰竭、心源性休克 |
| 阈值规则 | `ThresholdRule` | 数值、单位、方向和时间窗必须齐全。 | 肌钙蛋白超过第 99 百分位并动态变化 |
| 诊断标准 | `DiagnosisCriteria` | 诊断标准总标题，必须继续下钻明细。 | 急性心肌梗死诊断标准 |
| 诊断标准明细 | `DiagnosisCriteriaComponent` | 可判断的独立条件。 | 缺血症状、心电图改变、肌钙蛋白动态升高 |
| 鉴别诊断 | `DifferentialDiagnosis` | 鉴别对象必须连接鉴别要点、排除检查或规则。 | 主动脉夹层、肺栓塞 |
| 风险分层 | `RiskStratification` | 评分或分层工具。 | GRACE 评分 |
| 治疗方案 | `TreatmentPlan` | 疾病治疗策略；必须下钻到场景、规则、动作和证据。 | STEMI 再灌注方案 |
| 随访 | `FollowUp` | 说明频率、时点或触发条件。 | 出院后复诊和心功能随访 |
| 预后 | `Prognosis` | 结局、复发和死亡风险。 | 再梗死风险 |
| 预防 | `Prevention` | 一级/二级预防和患者教育。 | 戒烟和血脂管理 |
| 禁忌/排除条件 | `Contraindication` | 阻断推荐的临床原因；必须有证据。 | 活动性出血阻断溶栓 |

### 3.3 CDSS 标准临床主数据

以下 14 类必须明确，不使用“其他”“等”代替：

| 序号 | 中文名称 | 实体类型编码 | 标准来源或建设要求 | AMI 示例 |
|---:|---|---|---|---|
| 1 | 标准诊断 | `StandardDiagnosis` | CDSS 标准诊断字典，仅使用有效记录。 | I21.900 急性心肌梗死 |
| 2 | 症状 | `Symptom` | 优先 CDSS 症状字典。 | 胸痛 |
| 3 | 体征 | `Sign` | 症状和体征必须分开；缺少标准表时进入体征字典建设队列。 | 心包摩擦音 |
| 4 | 检查项目 | `ExamItem` | 影像、心电、超声、功能检查项目。 | 常规心电图 |
| 5 | 检查发现/观察指标 | `ExamObservation` | 检查报告中的结构化发现，不是检查项目。 | ST 段抬高、病理性 Q 波 |
| 6 | 检验项目 | `LabItem` | 一组检验或可开立检验项目。 | 心肌损伤标志物检测 |
| 7 | 检验细项 | `LabSubitem` | 检验项目包含的具体可报告指标。 | 心肌肌钙蛋白 I、肌酸激酶同工酶 |
| 8 | 检验标本 | `LabSpecimen` | 使用 CDSS 检验标本字典。 | 血清、血浆 |
| 9 | 药品 | `Medication` | 使用 CDSS 药品通用字典；标准全称为主名，缩写放别名。 | 阿司匹林 |
| 10 | 操作/手术 | `Procedure` | 临床知识动作；必须可映射到 CDSS 标准手术。 | 经皮冠状动脉介入治疗 |
| 11 | CDSS 标准手术 | `StandardProcedure` | Oracle 手术字典的一条有效记录。 | ICD-9-CM-3 对应的 PCI 标准项目 |
| 12 | 治疗项目 | `TreatmentItem` | 非药品、非手术的标准治疗项目。 | 氧疗 |
| 13 | 生命体征项目 | `VitalSignItem` | 使用 CDSS 生命体征标准表。 | 心率、收缩压 |
| 14 | 医学术语与别名 | `MedicalTerm`、`MedicalTermAlias` | 标准术语、缩写、旧称、中文简称统一管理。 | 急性心肌梗死；别名 AMI、急性心梗 |

### 3.4 来源、证据和 CDSS 决策实体

| 中文名称 | 实体类型编码 | 使用要求 | AMI 示例 |
|---|---|---|---|
| 指南/教材/共识 | `Guideline` | 名称、年份、版本、来源类型必须齐全。 | 2023 ESC 急性冠脉综合征指南 |
| 来源章节 | `SourceSection` | 保存章节、小标题、页码范围。 | STEMI 再灌注章节 |
| 证据片段 | `Evidence` | 保留原文、页码/段落和来源；同一原文不按疾病重复建。 | PCI 推荐原文 |
| 专病诊疗路径 | `ClinicalPathway` | CDSS 业务入口，不是治疗方案。 | AMI 急诊诊疗路径 |
| 路径阶段 | `PathwayStage` | 疑似、确诊、分型、治疗、随访阶段。 | STEMI 再灌注决策阶段 |
| 临床规则 | `ClinicalRule` | 触发、适用、排除、禁忌和阈值逻辑。 | 发病 12 小时内且 PCI 可及 |
| 推荐陈述 | `RecommendationStatement` | 医生推荐卡根实体，必须连接动作和证据。 | 推荐急诊 PCI |
| 推荐来源裁决 | `SourceAdjudication` | 记录主依据、支持依据、冲突和采用理由。 | STEMI 再灌注来源裁决 |
| 患者状态 | `PatientState` | 复杂条件或路径状态。 | 急性期、出血高风险 |
| 临床事件 | `ClinicalEvent` | 路径流转、结局或复发事件。 | 再梗死、心源性休克 |

## 4. 标准关系

### 4.1 疾病目录、分型和标准诊断

| 起点 | 中文关系 | 关系类型编码 | 终点 | 使用要求 | AMI 示例 |
|---|---|---|---|---|---|
| 顶层学科 | 包含疾病大类 | `has_disease_category` | 疾病大类 | 目录关系。 | 心血管内科 → 冠心病 |
| 疾病大类 | 包含临床疾病 | `has_disease` | 临床疾病 | 终点可作为初步/疑似诊断。 | 冠心病 → 急性心肌梗死 |
| 临床疾病 | 包含临床分型 | `has_clinical_subtype` | 临床疾病 | 父子均为 `Disease`；不得形成环。 | 急性心肌梗死 → STEMI |
| 疾病大类 | 有展示分组 | `has_display_group` | 疾病亚类 | 可选，仅用于展示。 | 冠心病 → 急性冠脉综合征 |
| 疾病亚类 | 展示分组包含疾病 | `groups_disease` | 临床疾病 | 只负责页面分组，不表示诊断父子层级。 | 急性冠脉综合征 → 急性心肌梗死 |
| 临床疾病 | 归入展示分组 | `classified_as` | 疾病亚类 | 不改变诊断层级。 | 急性心肌梗死 → 急性冠脉综合征 |
| 临床疾病 | 对应标准诊断 | `has_standard_diagnosis` | CDSS 标准诊断 | 可一对多；仅连接有效字典记录。 | AMI → I21.900 急性心肌梗死 |

### 4.2 检查、检验和标准动作

| 起点 | 中文关系 | 关系类型编码 | 终点 | 使用要求 | AMI 示例 |
|---|---|---|---|---|---|
| 临床疾病 | 需要检查 | `requires_exam_item` | 检查项目 | 项目必须来自标准字典或待注册队列。 | AMI → 常规心电图 |
| 检查项目 | 包含检查发现 | `exam_item_has_observation` | 检查发现 | 发现不能直接伪装成检查项目。 | 常规心电图 → ST 段抬高 |
| 临床疾病 | 需要检验 | `requires_lab_item` | 检验项目 | 项目必须来自标准字典或待注册队列。 | AMI → 心肌损伤标志物检测 |
| 检验项目 | 包含检验细项 | `lab_item_has_subitem` | 检验细项 | 必须维护项目与细项归属。 | 心肌损伤标志物检测 → 心肌肌钙蛋白 I |
| 检验项目/细项 | 使用标本 | `lab_item_uses_specimen` | 检验标本 | 标本来自标准字典。 | 肌钙蛋白检测 → 血清 |
| 操作/手术 | 对应标准手术 | `has_standard_procedure` | CDSS 标准手术 | 可一对多；只连接有效字典记录。 | 经皮冠状动脉介入治疗 → 标准 PCI 项目 |
| 医学术语 | 有别名 | `term_has_alias` | 医学术语别名 | 别名不得另建成同类型正式实体。 | 急性心肌梗死 → AMI |

### 4.3 疾病医学事实

| 起点 | 中文关系 | 关系类型编码 | 终点 | 使用要求 | AMI 示例 |
|---|---|---|---|---|---|
| 临床疾病 | 有定义 | `has_definition` | 疾病定义 | 核心疾病必须有定义。 | AMI → AMI 定义 |
| 疾病定义 | 有定义明细 | `has_definition_component` | 定义明细 | 明细可独立追溯。 | AMI 定义 → 心肌坏死 |
| 临床疾病 | 有病因 | `has_etiology` | 病因 | 短语标准化。 | AMI → 斑块破裂 |
| 临床疾病 | 有病理生理 | `has_pathophysiology` | 病理生理 | 机制可拆分。 | AMI → 冠脉急性闭塞 |
| 临床疾病 | 有流行病学 | `has_epidemiology` | 流行病学 | 数值带来源。 | AMI → 发病率变化 |
| 临床疾病 | 有症状 | `has_symptom` | 症状 | 主观感受。 | AMI → 胸痛 |
| 临床疾病 | 有体征 | `has_sign` | 体征 | 客观发现。 | AMI → 心包摩擦音 |
| 临床疾病 | 有危险因素 | `has_risk_factor` | 危险因素 | 不得误建疾病。 | AMI → 吸烟 |
| 临床疾病 | 可导致并发症 | `may_cause_complication` | 并发症 | 表示可能发生。 | AMI → 心源性休克 |
| 临床疾病 | 有诊断标准 | `has_diagnostic_criteria` | 诊断标准 | 必须继续下钻明细。 | AMI → AMI 诊断标准 |
| 诊断标准 | 有诊断明细 | `has_diagnostic_component` | 诊断明细/症状/体征/检查/检验/阈值/规则 | 终点必须是可判断条件。 | AMI 诊断标准 → 肌钙蛋白动态升高 |
| 临床疾病 | 需要鉴别 | `differentiates_from` | 鉴别诊断 | 必须补鉴别要点或排除规则。 | AMI → 主动脉夹层 |
| 临床疾病 | 有风险分层 | `has_risk_stratification` | 风险分层 | 评分项另行结构化。 | AMI → GRACE 评分 |

### 4.4 治疗和正式 CDSS 推荐

| 起点 | 中文关系 | 关系类型编码 | 终点 | 使用要求 | AMI 示例 |
|---|---|---|---|---|---|
| 临床疾病 | 有治疗方案 | `has_treatment_plan` | 治疗方案 | 仅表示知识方案，不等于当前推荐。 | AMI → 再灌注方案 |
| 治疗方案 | 包含药品 | `includes_medication` | 药品 | 类别必须继续连接具体药品。 | 抗血小板方案 → 阿司匹林 |
| 治疗方案 | 包含操作/手术 | `includes_procedure` | 操作/手术 | 动作应可映射标准手术。 | 再灌注方案 → 经皮冠状动脉介入治疗 |
| 治疗方案 | 包含治疗项目 | `includes_treatment_item` | 治疗项目 | 非药品、非手术动作。 | 一般治疗 → 氧疗 |
| 临床疾病 | 有随访 | `has_follow_up` | 随访 | 说明时点或频率。 | AMI → 出院后随访 |
| 临床疾病 | 有预后 | `has_prognosis` | 预后 | 不能替代风险分层。 | AMI → 再梗死风险 |
| 临床疾病 | 有预防 | `has_prevention` | 预防 | 可执行建议。 | AMI → 戒烟 |
| 临床疾病 | 有专病路径 | `has_clinical_pathway` | 专病诊疗路径 | 正式 CDSS 入口。 | AMI → 急诊诊疗路径 |
| 专病诊疗路径 | 包含阶段 | `has_pathway_stage` | 路径阶段 | 阶段顺序由路径维护。 | AMI 路径 → 再灌注决策阶段 |
| 路径阶段 | 有阶段规则 | `has_stage_rule` | 临床规则 | 结构化触发条件。 | 再灌注阶段 → PCI 可及规则 |
| 路径阶段 | 有可选动作 | `stage_has_available_action` | 标准动作 | 只表示该阶段可能使用的动作菜单。 | 再灌注阶段 → PCI、溶栓 |
| 临床规则/推荐陈述 | 正式推荐动作 | `recommends_action` | 药品/操作/检查/检验/治疗/随访 | 当前患者满足条件后才展示。 | 推荐急诊 PCI → 经皮冠状动脉介入治疗 |
| 临床规则/推荐陈述 | 阻断动作 | `blocks_action` | 药品/操作/检查/检验/治疗/随访 | 有禁忌或排除条件时。 | 活动性出血 → 阻断溶栓 |
| 路径阶段 | 下一阶段 | `next_pathway_stage` | 路径阶段 | 不得跳过必需判断。 | 疑似阶段 → 确诊分型阶段 |

### 4.5 来源、证据和推荐裁决

| 起点 | 中文关系 | 关系类型编码 | 终点 | 使用要求 | AMI 示例 |
|---|---|---|---|---|---|
| 指南/教材/共识 | 有来源章节 | `has_source_section` | 来源章节 | 章节需可定位。 | ESC 指南 → 再灌注章节 |
| 来源章节 | 包含证据 | `section_has_evidence` | 证据片段 | 保存原文。 | 再灌注章节 → PCI 原文 |
| 指南/教材/共识 | 包含证据 | `guideline_has_evidence` | 证据片段 | 全局追溯。 | ESC 指南 → PCI 原文 |
| 临床知识或规则实体 | 由证据支持 | `supported_by_evidence` | 证据片段 | “临床知识或规则实体”指疾病、定义、症状、体征、检查发现、检验细项、诊断标准、鉴别规则、治疗方案、临床规则和推荐陈述。 | AMI 定义 → 教材原文 |
| 推荐陈述 | 基于指南 | `based_on_guideline` | 指南/教材/共识 | 明确推荐来源。 | 推荐急诊 PCI → ESC 指南 |
| 推荐陈述/来源裁决 | 来自证据 | `derived_from` | 证据片段 | 医生端默认展示当前推荐直连主证据。 | 推荐急诊 PCI → PCI 原文 |
| 临床疾病 | 有推荐来源裁决 | `has_source_adjudication` | 推荐来源裁决 | 按临床问题建。 | AMI → 再灌注来源裁决 |
| 推荐来源裁决 | 使用主依据 | `uses_primary_guideline` | 指南/教材/共识 | 当前只能有一个主依据。 | 来源裁决 → 中国 STEMI 指南 |
| 推荐来源裁决 | 形成正式推荐 | `decides_recommendation` | 推荐陈述 | 裁决结果落到推荐卡。 | 来源裁决 → 推荐急诊 PCI |

## 5. 字段标准

### 5.1 所有节点必填字段

| 字段 | 中文名称 | 类型 | 格式要求 | AMI 示例 |
|---|---|---|---|---|
| `code` | 图谱实体编码 | 字符串 | 全局唯一且稳定，只允许单值字符串；历史合并编码写入 `merged_from_codes`，禁止把编码数组写入本字段。标准主数据节点可由实体类型前缀和 CDSS UUID 稳定生成。 | `DIS-CARD-CAD-AMI` |
| `entityType` | 实体类型 | 字符串 | 必须来自本标准实体类型表。 | `Disease` |
| `name` | 标准名称 | 字符串 | 医生可读中文全称；缩写不得作为主名。 | 急性心肌梗死 |
| `aliases` | 别名 | 字符串数组 | 没有别名时为 `[]`；中文简称、英文缩写、旧称放入数组。 | `["AMI","急性心梗"]` |
| `source_type` | 来源类型 | 字符串 | 只允许：`authoritative_textbook` 权威教材、`guideline` 指南、`consensus` 专家共识、`clinical_pathway` 临床路径、`cdss_standard_dict` CDSS 标准字典、`external_authority` 外部权威、`governed_composite` 受控合并。 | `cdss_standard_dict`（CDSS 标准字典） |
| `batch_id` | 批次编号 | 字符串 | 能追溯到批次台账和目录。 | `BATCH-CARD-CAD-20260719-001` |
| `schema_version` | Schema 版本 | 字符串 | 使用 `V主版本.次版本`。 | `V2.0` |
| `clinical_use_status` | 临床使用状态 | 字符串 | `draft` 草稿、`review_ready` 待审核、`clinical_ready` 可临床使用、`blocked` 阻断。 | `clinical_ready` |

### 5.2 关系必填字段

| 字段 | 中文名称 | 类型 | 格式要求 | AMI 示例 |
|---|---|---|---|---|
| `id` | 关系编号 | 字符串 | 全局唯一且可稳定重算。 | `REL-CARD-8F31A2C9` |
| `source_code` | 起点实体编码 | 字符串 | 必须引用真实节点 `code`。 | `DIS-CARD-CAD-AMI` |
| `relationType` | 关系类型 | 字符串 | 必须来自本标准关系表。 | `has_clinical_subtype` |
| `target_code` | 终点实体编码 | 字符串 | 必须引用真实节点 `code`。 | `DIS-CARD-CAD-STEMI` |
| `batch_id` | 批次编号 | 字符串 | 与产生该关系的批次一致。 | `BATCH-CARD-CAD-20260719-001` |
| `schema_version` | Schema 版本 | 字符串 | 固定为当前生成版本。 | `V2.0` |
| `review_status` | 自动审核状态 | 字符串 | `pending` 待审、`passed` 通过、`failed` 失败。 | `passed` |
| `clinical_review_status` | 临床使用状态 | 字符串 | `pending` 待临床确认、`clinical_ready` 可临床使用、`blocked` 阻断、`not_required` 不需要临床审核。 | `not_required` |

### 5.3 临床疾病字段

| 字段 | 中文名称 | 类型 | 格式要求 | AMI 示例 |
|---|---|---|---|---|
| `diagnostic_role` | 诊断层级角色 | 字符串 | `broad_diagnosis` 待分型/宽口径诊断，`clinical_subtype` 具体分型，`independent_disease` 独立疾病。 | `broad_diagnosis` |
| `is_diagnosable` | 是否可作为诊断 | 布尔 | `Disease` 通常为 `true`。 | `true` |
| `is_emr_writable` | 是否允许回填 EMR | 布尔 | 只有连接有效 `StandardDiagnosis` 且通过审核时为 `true`。 | `true` |
| `classification_tags` | 临床分类标签 | 字符串数组 | 仅用于轻量展示或检索，不替代疾病分型关系。 | `["急性冠脉综合征"]` |

### 5.4 CDSS 标准诊断和标准手术字段

| 字段 | 中文名称 | 类型 | 格式要求 | AMI 示例 |
|---|---|---|---|---|
| `cdss_dict_id` | CDSS 字典 UUID | 字符串 | 原样保存 Oracle UUID，是与 CDSS 主数据同步的唯一标识。 | `7f...uuid` |
| `standard_code` | 标准业务编码 | 字符串 | 原样保存字典中的诊断编码或手术编码；不与图谱 `code` 混用。 | `I21.900` |
| `name` | 标准项目名称 | 字符串 | 原样使用有效字典记录名称。 | 急性心肌梗死 |
| `coding_system` | 编码体系 | 字符串 | 带中文解释保存，如 `ICD-10（诊断）`、`ICD-9-CM-3（手术操作）`；未来可用 `ICD-11（诊断）`。 | `ICD-10（诊断）` |
| `coding_system_version` | 编码版本 | 字符串 | 字典有版本则原样保存；未知时为空，不猜测。 | 国家临床版 2.0 |
| `valid_flag` | 有效标志 | 整数/字符串 | 只允许字典中表示“有效”的值；当前业务规则为 `1=有效`。 | `1` |
| `effective_start` | 生效时间 | 日期时间 | 使用字典原值。 | `2025-01-01 00:00:00` |
| `effective_end` | 失效时间 | 日期时间/空 | 长期有效可为空。 | 空 |
| `source_table` | 来源表 | 字符串 | 保存实际 Oracle 物理表名。 | `K_ICD10_DICT` |
| `source_version` | 来源快照版本 | 字符串 | 每次同步产生稳定版本。 | `CDSS-DICT-20260719` |
| `last_sync_time` | 最近同步时间 | 日期时间 | `YYYY-MM-DD HH:mm:ss`。 | `2026-07-19 00:19:13` |

说明：标准诊断/标准手术实体的 `name` 就是 CDSS 字典标准名称；`aliases` 保存简称和缩写；`standard_code` 保存 ICD 或手术业务编码；`cdss_dict_id` 保存 Oracle UUID；四者不能互相替代。

### 5.5 基础人群与有效性限制

以下字段适用于 `StandardDiagnosis`、`StandardProcedure`、`Medication`、`ExamItem`、`LabItem`、`TreatmentItem`。字段值优先直接复制 CDSS 标准字典，不得由大模型猜测。

| 字段 | 中文名称 | 类型 | 格式要求 | AMI 示例 |
|---|---|---|---|---|
| `sex_limit_code` | 性别限制编码 | 字符串/整数 | 使用 CDSS 字典原值。 | 不限制对应编码 |
| `sex_limit_name` | 性别限制名称 | 字符串 | 不限制、男性、女性。 | 不限制 |
| `age_min` | 最小年龄 | 数值/空 | 与 `age_unit` 配套。 | `18` |
| `age_max` | 最大年龄 | 数值/空 | 与 `age_unit` 配套。 | 空 |
| `age_unit` | 年龄单位 | 字符串 | 天、月、岁。 | 岁 |
| `pregnancy_limit_code` | 妊娠限制编码 | 字符串/整数/空 | 使用 CDSS 字典原值；没有标准值时不得猜测。 | 空 |
| `pregnancy_limit_name` | 妊娠限制名称 | 字符串/空 | 不限制、慎用、禁用或字典原名称。 | 空 |
| `lactation_limit_code` | 哺乳限制编码 | 字符串/整数/空 | 使用 CDSS 字典原值。 | 空 |
| `lactation_limit_name` | 哺乳限制名称 | 字符串/空 | 使用 CDSS 字典原名称。 | 空 |

基础过滤顺序：有效期 → 性别 → 年龄 → 妊娠 → 哺乳。通过基础过滤后，再由规则引擎判断肾功能、肝功能、过敏史、出血风险、药物相互作用、生命体征、检验结果、急性/稳定期、就诊场景、时间窗、既往手术/卒中和并发症。

## 6. CDSS 标准字典来源规则

### 6.1 已确认的标准来源

| 标准对象 | 首选来源 | 使用规则 | AMI 示例 |
|---|---|---|---|
| 标准诊断 | `K_ICD10_DICT` / 实际生产配置的诊断标准表 | 只读取有效标志为 1 的记录。 | I21.900 急性心肌梗死 |
| 症状 | `K_SYMPTOM_DICT` | 标准名称直用，口语名称进入别名。 | 胸痛 |
| 检查项目 | `K_EXAM_ITEM_DICT` | 项目和检查发现分开。 | 常规心电图 |
| 检验项目 | `K_LAB_ITEM_DICT` | 项目和细项分开。 | 心肌损伤标志物检测 |
| 检验细项 | `K_LAB_SUBITEM_DICT` | 必须维护所属检验项目。 | 心肌肌钙蛋白 I |
| 药品 | `K_DRUG_DICT` | 标准全称为主名。 | 阿司匹林 |
| 标准手术 | `K_OPERATION_HANDLE_DICT` | 只读取有效记录。 | 经皮冠状动脉介入治疗 |
| 治疗项目 | `K_TREATMENT_DICT` | 非药品、非手术治疗。 | 氧疗 |

### 6.2 需配置确认或补建的标准来源

| 标准对象 | 处理要求 | 不允许 | AMI 示例 |
|---|---|---|---|
| 体征 | 独立于症状；优先确认现有表，缺失时建设 `K_SIGN_DICT`。 | 把体征全部塞入症状表。 | 心包摩擦音 |
| 检查发现 | 建设或确认 `K_EXAM_OBSERVATION_DICT`。 | 将 ST 段抬高当作检查项目。 | ST 段抬高 |
| 检查项目与发现关系 | 建设或确认 `K_EXAM_ITEM_OBSERVATION_REL`。 | 只靠名称猜归属。 | 心电图 → ST 段抬高 |
| 检验标本 | 使用现有检验标本字典，物理表名写入批次配置。 | 在脚本中写死未核实表名。 | 血清 |
| 生命体征 | 使用现有生命体征表，物理表名写入批次配置。 | 重复建设“心率”“血压”字典。 | 心率 |
| 医学术语和别名 | 使用现有医学术语表并补别名管理；物理表名写入配置。 | 把同义词建成重复正式节点。 | AMI、急性心梗 |

医院自定义诊断和院内映射表用于 CDSS 上线后的院内回填，不属于文献抽取主数据源，不写入本 Schema 的标准知识抽取流程。

## 7. 正式 CDSS 推荐链

```text
患者数据/EMR
  -> 基础人群与有效性过滤
  -> 疑似/初步诊断 Disease
  -> 进入 ClinicalPathway
  -> 定位 PathwayStage
  -> 匹配 ClinicalRule
  -> 生成 RecommendationStatement
  -> recommends_action / blocks_action
  -> 标准诊断、标准手术、药品、检查、检验、治疗或随访动作
  -> SourceAdjudication
  -> 主依据 Guideline + 主 Evidence
```

正式推荐动作只能是：`Medication`、`Procedure`、`ExamItem`、`LabItem`、`TreatmentItem`、`FollowUp`。疾病直连治疗方案、阶段可选动作和疾病级证据池不得直接显示为当前患者推荐。

## 8. 推荐来源裁决字段

| 字段 | 中文名称 | 格式要求 | AMI 示例 |
|---|---|---|---|
| `clinical_question` | 临床问题 | 按具体场景建立。 | STEMI 是否需要再灌注 |
| `clinical_scenario` | 适用场景 | 分型、阶段、患者条件。 | 发病 12 小时内、ST 段抬高 |
| `final_recommendation` | 最终推荐 | 医生可读简明结论。 | 优先直接 PCI；延误明显时考虑溶栓 |
| `primary_guideline_code` | 主依据指南 | 当前只能有一个。 | 中国 STEMI 指南编码 |
| `supporting_guideline_codes` | 支持指南 | 字符串数组。 | `["ESC-ACS-2023"]` |
| `conflict_guideline_codes` | 冲突指南 | 无冲突时为 `[]`。 | `[]` |
| `adjudication_score` | 裁决得分 | 来自可复核权重表，范围 0—100。 | `90` |
| `adjudication_reason` | 裁决理由 | 写明专病、本土、有效期、推荐等级和证据等级。 | 本土专病指南、当前有效、推荐等级高 |
| `conflict_status` | 冲突状态 | 无冲突、有冲突已处理、冲突待裁决。 | 无冲突 |
| `cdss_use_status` | CDSS 使用状态 | 正式推荐、仅知识展示、冲突待裁决、证据不足、已过时保留。 | 正式推荐 |

大模型只能抽取候选和证据，不得黑箱决定主依据。裁决必须保留输入来源、权重、分数和理由。新指南发布时只更新受影响的推荐、证据和裁决，不重建稳定疾病骨架。

## 9. V1.x 到 V2.0 兼容迁移

| 旧实体/关系 | V2.0 处理 | 判定规则 | AMI 示例 |
|---|---|---|---|
| `DiseaseClassification` | 迁移为 `Disease` 或 `DiseaseSubcategory`/标签 | 可诊断分型迁为 `Disease`；纯展示分组迁为 `DiseaseSubcategory`；临时分类迁为属性。 | STEMI 迁为 `Disease` |
| `Exam` | 迁移为 `ExamItem` | 能开立/执行的检查项目。 | 心电图 |
| `LabTest` | 迁移为 `LabItem` | 能开立的检验项目。 | 心肌损伤标志物检测 |
| `ExamIndicator` | 按父关系拆分 | 检查结果迁为 `ExamObservation`；检验结果迁为 `LabSubitem`。 | ST 段抬高 / 肌钙蛋白 I |
| `DiagnosisCode`、旧 ICD 节点 | 迁移为 `StandardDiagnosis` | 必须能对应有效 CDSS 诊断字典。 | I21.900 急性心肌梗死 |
| 旧 ICD-9 手术节点 | 迁移为 `StandardProcedure` | 必须能对应有效 CDSS 手术字典。 | PCI 标准手术项目 |
| `has_classification` | 改为 `has_clinical_subtype` 或 `classified_as` | 诊断分型与展示分组必须区分。 | AMI → STEMI |
| `has_category` | 改为 `has_disease_category` | 统一使用“顶层学科包含疾病大类”的单向关系。 | 心血管内科 → 冠心病 |
| `belongs_to_category` | 反向关系删除；由疾病大类建立 `has_disease` | 同一层级只保留一个方向，避免双向重复。 | 冠心病 → 急性心肌梗死 |
| `has_subcategory` | 改为 `has_display_group` | 亚类只作为可选展示分组。 | 冠心病 → 急性冠脉综合征 |
| `belongs_to_subcategory` | 反向关系删除；由展示分组建立 `groups_disease` | 不得把展示分组误当诊断父级。 | 急性冠脉综合征 → 急性心肌梗死 |
| `requires_exam` | 改为 `requires_exam_item` | 终点为检查项目。 | AMI → 心电图 |
| `requires_lab_test` | 改为 `requires_lab_item` | 终点为检验项目。 | AMI → 心肌损伤标志物检测 |
| `exam_has_indicator` | 改为 `exam_item_has_observation` | 终点为检查发现。 | 心电图 → ST 段抬高 |
| `lab_test_has_indicator` | 改为 `lab_item_has_subitem` | 终点为检验细项。 | 心肌损伤标志物检测 → 肌钙蛋白 I |
| `has_recommended_action` | 改为 `stage_has_available_action` | 只表示阶段菜单，不是正式推荐。 | 再灌注阶段 → PCI |

迁移期允许旧数据只读查询；V2.0 新批次不得继续生成旧实体或旧关系。迁移必须先备份、生成映射表和回滚文件，再小批量写库并执行服务器复核。

## 10. 数据质量硬闸门

以下任一项不通过，批次不得标记“正式 CDSS 可用”：

1. 节点缺少 `KGNode`、`code`、`entityType`、`name`、`schema_version`。
2. 疾病大类被错误标记为可诊断或保存 ICD 编码。
3. 宽口径疾病没有疾病大类；具体分型没有父疾病；疾病分型形成环；同名疾病重复。
4. 新增 `DiseaseClassification`、`Exam`、`LabTest`、`ExamIndicator` 或 V1.x 旧关系。
5. 可回填疾病没有有效 `StandardDiagnosis`；可下医嘱手术没有有效 `StandardProcedure`。
6. 标准主数据不是来自有效标志为 1 的 CDSS 字典记录，或 UUID、标准编码、标准名称与 Oracle 不一致。
7. 症状与体征混用；检查项目与检查发现混用；检验项目与检验细项混用。
8. 检验细项没有所属检验项目；检查发现没有所属检查项目。
9. 标准名称使用英文缩写，或别名没有进入 `aliases`/医学术语别名管理。
10. 诊断标准没有 `has_diagnostic_component` 明细，或明细没有原文证据。
11. 鉴别诊断只有对象名称，没有鉴别要点、排除检查或临床规则。
12. 治疗方案没有适用场景、触发条件、具体动作、禁忌/排除条件或证据。
13. 正式推荐没有 `RecommendationStatement -> recommends_action/blocks_action -> Evidence -> Guideline` 完整链。
14. 正式推荐没有来源裁决、主依据、冲突状态和可复核裁决理由。
15. 基础人群限制缺失时未标记数据来源状态，或由大模型猜测年龄、性别、妊娠、哺乳限制。
16. 关系端点不存在、关系类型不合法、同一语义关系重复。
17. 写库前无回滚清单，或写库后服务器复核阻断项不为 0。
18. 前端把目录、展示分组、阶段可选动作或疾病级证据池当作正式诊断/推荐展示。

## 11. Neo4j 导入与复核标准

1. 普通知识节点使用 `code` 作为图谱唯一键；标准主数据同时以 `(entityType, cdss_dict_id)` 复核唯一性。
2. 关系以 `(source_code, relationType, target_code)` 作为语义唯一键。
3. 导入前必须生成节点/关系增量包、字典映射表、未命中注册队列、审计报告和回滚清单。
4. 导入后必须复核节点数、关系数、疾病层级、标准字典映射、重复实体、检查/检验归属、诊断标准明细、治疗动作链和推荐证据链。
5. 外部模型、前端和人工修复不得直接写正式 Neo4j；必须回到本地受控数据包和审计流程。

## 12. 每批次必交付文件

```text
batch_config.yaml                         批次配置
source_documents_manifest.csv             来源资料清单
standard_dictionary_snapshot.csv          本批次使用的有效标准字典快照
standard_dictionary_mapping.csv           抽取实体与 CDSS 标准字典映射
dictionary_registration_queue.csv          标准字典未命中注册队列
disease_hierarchy.csv                      疾病大类、宽口径疾病和临床分型层级
nodes_final.jsonl                          正式节点数据
relations_final.jsonl                      正式关系数据
audit_report.json                          本地质量审计
rollback_manifest.json                     写库回滚清单
server_validation_summary.json             服务器入库后复核
source_folder_summary.md                   来源与批次说明
```

## 13. 当前禁止新增项

```text
DiseaseClassification
Exam
LabTest
ExamIndicator
DiagnosisCode
has_category
belongs_to_category
has_subcategory 作为核心必经层
belongs_to_subcategory
has_classification
requires_exam
requires_lab_test
exam_has_indicator
lab_test_has_indicator
has_recommended_action
USES_MEDICATION
HAS_PROCEDURE
HAS_CLINICAL_MANIFESTATION
所有大写 HAS_* 历史关系
```

`Specialty` 是未来多学科扩展根节点，必须保留，不得因当前只有心血管内科而删除。
