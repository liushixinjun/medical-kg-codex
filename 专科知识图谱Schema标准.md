# 专科知识图谱 Schema 标准

版本：V2.7（术语语义分层与归一约束版）
状态：正式执行标准
更新时间：2026-07-22 15:02:13
适用范围：所有专科、疾病大类、单病种知识图谱，以及专科 CDSS 诊断、检查、检验、用药、手术、治疗和随访场景。

## 0. 版本说明

| 时间 | 版本 | 变更类型 | 说明 | AMI 示例 |
|---|---|---|---|---|
| 2026-07-22 15:02:13 | V2.7 | 术语语义分层与归一约束 | 不增加实体类型；明确同义词、类别成员、活性成分、具体剂型、商品名和口语输入的边界，禁止把上下位关系伪装成别名关系。 | 阿司匹林肠溶片为规范剂型名；肠溶阿司匹林为口语输入；拜阿司匹林为品牌名；阿司匹林为活性成分 |
| 2026-07-22 08:35:12 | V2.6 | 标准字典融合与疑似诊断规则 | 新增体征、检查发现、生命体征、术语映射、字典待审、疑似诊断规则及版本日志表；图谱实体直接保存 CDSS 字典 UUID/编码/名称；诊断作用只按原文显式措辞分级，未绑定标准诊断或缺证据时禁止自动排序。 | AMI → 胸痛；胸痛映射 CDSS 症状字典，关系保存诊断作用等级和证据编码 |
| 2026-07-20 12:30:59 | V2.5 | 标准手术主数据收口 | 临床手术与 CDSS 有效标准手术完成分层；统一二次校验字段；复合治疗策略不得伪装成手术；禁止空壳节点向多个方案扩散证据；正式手术推荐必须可回填标准手术。 | 经皮冠状动脉介入治疗（临床动作）→ 00.6600 等 CDSS 标准手术项目；`PCI` 仅作别名 |
| 2026-07-19 22:57:46 | V2.4 | 正式推荐链路收口 | 推荐来源裁决只负责主依据与冲突裁决，不再直连推荐目标；推荐陈述分别连接具体执行项目或临床评估目标；新增 `recommends_assessment`，支持诊断、鉴别和风险场景，避免把诊断标准伪装成药品/手术动作。 | AMI 来源裁决 → AMI 诊断推荐陈述 → 推荐评估 AMI 诊断标准 |
| 2026-07-19 22:02:11 | V2.3 | 结构边界定型 | 明确目录、诊断、方案和具体项目四层边界；新增辅助检查方案；疾病大类和展示分组禁止挂载临床方案；宽口径疾病与具体分型仅使用显式方案关系，不允许自动继承；正式推荐只能落到具体动作。 | 冠心病只作目录；AMI 可挂首诊通用方案；STEMI 挂再灌注方案；方案下钻心电图、肌钙蛋白、PCI 等具体动作 |
| 2026-07-19 21:03:07 | V2.2 | 主数据可信度治理 | Oracle/CDSS 既有字典调整为“业务候选主数据”，有效标志为 1 仅代表可进入校验池；名称、编码、别名和适用限制必须经过规则校验，并与教材、指南、官方标准或监管资料交叉验证后才能正式使用。 | I21.900 先核对编码、名称和适用范围，再关联 AMI |
| 2026-07-19 20:52:54 | V2.1 | 多来源限制治理 | CDSS 字典负责标准身份和已有基础限制，但不是唯一医学来源；教材、指南、共识、药品说明书和外部权威资料可补充缺失限制。所有补充值必须有原文证据，模型只生成候选。 | CDSS 字典确定项目 UUID，指南补充特定患者适用条件 |
| 2026-07-19 00:19:13 | V2.0 | 大版本升级 | 统一疾病三层诊断结构；新增 CDSS 标准诊断、标准手术主数据层；拆分检查项目/检查发现、检验项目/检验细项；固化年龄、性别、妊娠、哺乳基础过滤；停用 `DiseaseClassification`、`Exam`、`LabTest`、`ExamIndicator` 新增写入。 | 冠心病 → 急性心肌梗死 → STEMI/NSTEMI → CDSS 标准诊断 |
| 2026-07-17 17:10:00 | V1.17 | 推荐来源裁决 | 正式推荐增加主依据、支持依据、冲突状态和裁决理由。 | STEMI 再灌注推荐来源裁决 |

升级前基线：Git 标签 `baseline-schema-v1.17-skill-v2.5-20260718`。历史字段细则和旧版本记录保存在 `schema_docs/`，本文件只保留当前正式标准。

## 1. 核心原则

1. 基础权威教材、专科专著搭建疾病骨架，诊疗指南、专家共识和临床路径补充可执行决策。
2. CDSS 已有字典是诊断、症状、体征、检查、检验、检验细项、检验标本、药品、手术、治疗、生命体征和医学术语的业务候选主数据来源，不天然等同于权威标准。有效记录必须通过名称、编码、UUID、重复项、别名和来源一致性校验，并与教材、指南、官方分类标准、专家共识、药品说明书或外部权威资料交叉验证后，才可作为正式主数据；校验失败或无法确认的记录进入待治理队列。
3. 疾病目录、临床疾病和标准诊断是三个不同概念：目录负责组织，疾病负责医学知识，标准诊断负责 CDSS/EMR 编码落地。
4. 症状和体征分开；检查和检验分开；检查项目和检查发现分开；检验项目和检验细项分开。
5. 简单且全局成立的人群限制使用标准主数据属性预过滤；来源缺失时按权威资料补充并保留证据。仅在特定疾病、阶段或场景成立的限制，以及肾功能、肝功能、过敏、相互作用、出血风险、时间窗等复杂条件，由临床规则表达。
6. 图谱中的知识浏览关系不等于患者正式推荐。正式推荐必须经过路径阶段、临床规则、推荐陈述、具体执行项目或临床评估目标、证据和指南来源裁决。
7. 所有新增关系使用小写下划线命名；中文业务名必须与技术编码同时提供，不允许只写英文编码。
8. 标准字典未命中的实体进入注册队列；注册前可用于知识整理，但不得作为正式医嘱、诊断回填或 CDSS 推荐动作。
9. 写库前本地审计，写库后服务器复核；两次硬闸门均通过才算正式完成。
10. 疾病大类只负责目录，临床疾病承载医学知识，方案组织一组临床策略，具体项目才是可执行动作；四者不得混用。

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
| CDSS 标准主数据层 | 如何对接经过二次校验的系统字典和医嘱/诊断编码。 | `StandardDiagnosis`、`StandardProcedure`，以及经校验的症状、体征、检查、检验、药品、治疗实体 | I21.900 急性心肌梗死、经皮冠状动脉介入治疗 |
| 临床决策层 | 当前患者何时触发、推荐什么、为什么。 | `ClinicalPathway`、`PathwayStage`、`ClinicalRule`、`RecommendationStatement`、`Evidence`、`Guideline` | STEMI 且 PCI 可及 → 推荐急诊 PCI |

### 2.4 疾病、方案和具体项目的唯一边界

| 层次 | 回答的问题 | 允许的实体 | 是否可诊断/开医嘱 | AMI 示例 |
|---|---|---|---|---|
| 目录层 | 属于哪个学科和疾病大类。 | `Specialty`、`DiseaseCategory`、可选 `DiseaseSubcategory` | 否 | 心血管内科、冠心病、急性冠脉综合征展示分组 |
| 诊断层 | 患者可能或确定患什么病。 | `Disease`、`StandardDiagnosis` | `Disease` 可诊断；通过 `StandardDiagnosis` 回填编码 | 急性心肌梗死、STEMI、NSTEMI |
| 方案层 | 对这类患者总体需要做哪些检查或治疗。 | `ExamPlan`、`TreatmentPlan` | 否；只是策略容器 | AMI 首诊辅助检查方案、STEMI 再灌注方案 |
| 具体项目层 | 实际检查、检验、用药、手术或治疗动作是什么。 | `ExamItem`、`LabItem`、`Medication`、`Procedure`、`TreatmentItem` | 经标准主数据校验后可作为推荐动作或医嘱候选 | 常规心电图、肌钙蛋白检测、阿司匹林、经皮冠状动脉介入治疗、氧疗 |

硬规则：

- `DiseaseCategory` 和 `DiseaseSubcategory` 均不得连接辅助检查方案、治疗方案、药品、手术或治疗项目。
- 宽口径 `Disease` 只挂分型前共同适用的方案；具体分型 `Disease` 只挂本分型适用的方案。
- 父疾病的方案不得被子分型自动继承。共同方案需要复用同一方案实体，并由每个适用疾病分别建立显式关系。
- 方案不是医嘱项目，不保存 CDSS 字典 UUID，也不得作为正式推荐动作。
- 正式推荐必须落到具体项目；操作/手术临床动作再通过 `has_standard_procedure` 对应一个或多个 CDSS 标准手术项目。

AMI 正确示例：

```text
冠心病(DiseaseCategory)                         只作目录，不挂方案
  -> 急性心肌梗死(Disease，待分型)
       -> AMI首诊辅助检查方案(ExamPlan)
            -> 常规心电图(ExamItem)
            -> 心肌损伤标志物检测(LabItem)
       -> ST段抬高型心肌梗死(Disease，具体分型)
            -> STEMI再灌注方案(TreatmentPlan)
                 -> 经皮冠状动脉介入治疗(Procedure，临床动作)
                      -> 00.6600 经皮冠状动脉腔内血管成形术(StandardProcedure，CDSS标准项目)
       -> 非ST段抬高型心肌梗死(Disease，具体分型)
            -> NSTE-ACS侵入策略(TreatmentPlan)
```

禁止示例：`冠心病 -> 溶栓方案`、`AMI -> 自动继承 STEMI 溶栓方案`、`治疗方案 -> 直接作为当前患者正式推荐`。

### 2.5 教材、指南和 CDSS 字典的职责边界

| 数据来源 | 主要职责 | 可以形成的内容 | 禁止替代的职责 | AMI 示例 |
|---|---|---|---|---|
| 权威教材/专科专著 | 建立稳定疾病骨架。 | 定义、病因、机制、症状、体征、检查检验概况、诊断鉴别、治疗原则、并发症、随访、预后和预防。 | 不负责 CDSS UUID；不得把教材建议直接写成指南推荐等级。 | 《内科学》提供 AMI 定义、临床表现和治疗总原则 |
| 诊疗指南/专家共识/临床路径 | 建立可执行决策。 | 适用场景、触发条件、排除/禁忌、具体动作、时机剂量、推荐等级、证据等级、随访要求。 | 不按每份指南复制疾病、症状、药品和手术实体。 | STEMI 发病时间窗内的 PCI/溶栓决策 |
| CDSS 业务字典 | 提供系统对接身份和已有基础限制候选。 | UUID、标准编码、标准名称、有效状态、年龄/性别等已有基础字段；均需二次校验。 | 不是医学证据，不生成疾病定义、治疗方案或临床推荐。 | I21.900 急性心肌梗死、00.6600 标准手术项目 |
| 外部权威资料 | 补齐教材、指南或字典未覆盖的缺口。 | 官方编码说明、监管批准说明书、专业学会资料和经审核健康资料。 | 不得覆盖更高等级来源且不留冲突记录。 | 核对术语、编码含义或全局安全限制 |

同一医学概念只建立一个正式实体。不同教材、指南和共识通过各自的 `Evidence` 连接同一事实、规则或推荐，不得因来源不同复制一套疾病、症状、药品、手术或方案节点。

### 2.6 建实体还是存属性/证据的判定标准

满足下列任一条件，才允许建立独立实体：

1. 有稳定医学身份，需要跨文档或跨疾病复用；
2. 需要独立属性、别名、标准编码或 CDSS 字典映射；
3. 需要成为关系起点/终点参与查询、推理或正式推荐；
4. 需要独立审核、版本管理和证据追溯。

不满足上述条件时：短值存属性，完整原文存 `Evidence`，可判断的定义/诊断明细才建立组件。禁止把教材或指南中的每个句子、半句话、小标题都建成 `TreatmentPlan`、`ClinicalRule` 或其他实体。

证据关系遵循“就近一次连接”：`Evidence` 优先连接最精确的事实、规则或推荐，并连接来源文档；疾病页面需要汇总证据时通过查询聚合，不再把同一证据重复连接疾病、方案、规则和推荐四层。

## 3. 标准实体类型

> “实体类型编码”供 Neo4j、接口和脚本使用；医生端展示中文名称。所有示例统一使用 AMI。

### 3.1 目录、疾病和标准诊断

| 中文名称 | 实体类型编码 | 使用要求 | AMI 示例 |
|---|---|---|---|
| 顶层学科 | `Specialty` | 多学科根节点；`code` 全局唯一。 | 心血管内科 |
| 疾病大类 | `DiseaseCategory` | 目录实体，不保存诊断编码。 | 冠心病 |
| 疾病亚类/展示分组 | `DiseaseSubcategory` | 可选；`display_only=true`。 | 急性冠脉综合征 |
| 临床疾病 | `Disease` | 待分型疾病和具体分型统一使用该类型。 | 急性心肌梗死、STEMI、NSTEMI |
| CDSS 标准诊断 | `StandardDiagnosis` | 一条实体对应一条经二次校验通过的 CDSS 诊断记录；保留 Oracle UUID，同时记录编码/名称的外部校验状态。 | I21.900 急性心肌梗死 |

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
| 辅助检查方案 | `ExamPlan` | 组织一组检查和检验策略；不是检查项目，不可直接开医嘱。 | AMI 首诊辅助检查方案 |
| 治疗方案 | `TreatmentPlan` | 疾病治疗策略；必须下钻到场景、规则、动作和证据。 | STEMI 再灌注方案 |
| 随访 | `FollowUp` | 说明频率、时点或触发条件。 | 出院后复诊和心功能随访 |
| 预后 | `Prognosis` | 结局、复发和死亡风险。 | 再梗死风险 |
| 预防 | `Prevention` | 一级/二级预防和患者教育。 | 戒烟和血脂管理 |
| 禁忌/排除条件 | `Contraindication` | 阻断推荐的临床原因；必须有证据。 | 活动性出血阻断溶栓 |

### 3.3 CDSS 标准临床主数据

以下 14 类必须明确，不使用“其他”“等”代替：

| 序号 | 中文名称 | 实体类型编码 | 标准来源或建设要求 | AMI 示例 |
|---:|---|---|---|---|
| 1 | 标准诊断 | `StandardDiagnosis` | CDSS 有效诊断记录进入候选池，经编码、名称和权威来源二次校验后使用。 | I21.900 急性心肌梗死 |
| 2 | 症状 | `Symptom` | 优先 CDSS 症状字典。 | 胸痛 |
| 3 | 体征 | `Sign` | 症状和体征必须分开；缺少标准表时进入体征字典建设队列。 | 心包摩擦音 |
| 4 | 检查项目 | `ExamItem` | 影像、心电、超声、功能检查项目。 | 常规心电图 |
| 5 | 检查发现/观察指标 | `ExamObservation` | 检查报告中的结构化发现，不是检查项目。 | ST 段抬高、病理性 Q 波 |
| 6 | 检验项目 | `LabItem` | 一组检验或可开立检验项目。 | 心肌损伤标志物检测 |
| 7 | 检验细项 | `LabSubitem` | 检验项目包含的具体可报告指标。 | 心肌肌钙蛋白 I、肌酸激酶同工酶 |
| 8 | 检验标本 | `LabSpecimen` | 使用 CDSS 检验标本字典。 | 血清、血浆 |
| 9 | 药品 | `Medication` | 使用 CDSS 药品通用字典；标准全称为主名，缩写放别名。 | 阿司匹林 |
| 10 | 操作/手术 | `Procedure` | 临床知识动作；必须可映射到 CDSS 标准手术。 | 经皮冠状动脉介入治疗 |
| 11 | CDSS 标准手术 | `StandardProcedure` | Oracle 有效手术记录经编码、名称和临床含义二次校验后使用。 | ICD-9-CM-3 对应的 PCI 标准项目 |
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

### 4.2 辅助检查方案、检查、检验和标准动作

| 起点 | 中文关系 | 关系类型编码 | 终点 | 使用要求 | AMI 示例 |
|---|---|---|---|---|---|
| 临床疾病 | 有辅助检查方案 | `has_exam_plan` | 辅助检查方案 | 只能从临床疾病发出；目录和展示分组禁止使用。 | AMI → AMI 首诊辅助检查方案 |
| 辅助检查方案 | 包含检查项目 | `includes_exam_item` | 检查项目 | 项目必须来自标准字典或待注册队列。 | AMI 首诊辅助检查方案 → 常规心电图 |
| 检查项目 | 包含检查发现 | `exam_item_has_observation` | 检查发现 | 发现不能直接伪装成检查项目。 | 常规心电图 → ST 段抬高 |
| 辅助检查方案 | 包含检验项目 | `includes_lab_item` | 检验项目 | 项目必须来自标准字典或待注册队列。 | AMI 首诊辅助检查方案 → 心肌损伤标志物检测 |
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
| 推荐陈述 | 正式推荐具体项目 | `recommends_action` | 药品/操作/检查/检验/治疗/随访 | 当前患者满足条件后，推荐可执行或可开立项目。 | 推荐急诊 PCI → 经皮冠状动脉介入治疗 |
| 推荐陈述 | 推荐临床评估 | `recommends_assessment` | 诊断标准/鉴别诊断/风险分层/危险因素/并发症/检查发现/检验细项/病因 | 用于诊断确认、鉴别、风险与病因评估；不是医嘱项目。 | AMI 诊断推荐 → AMI 诊断标准 |
| 推荐陈述/禁忌条件/临床规则 | 阻断具体项目 | `blocks_action` | 药品/操作/检查/检验/治疗/随访 | 有禁忌、排除条件或阻断规则时。 | 活动性出血 → 阻断溶栓 |
| 路径阶段 | 下一阶段 | `next_pathway_stage` | 路径阶段 | 不得跳过必需判断。 | 疑似阶段 → 确诊分型阶段 |

方案挂载规则：

1. 疾病大类和疾病亚类不得使用 `has_exam_plan` 或 `has_treatment_plan`。
2. 宽口径疾病只连接分型前共同适用的方案；具体分型连接本分型方案。
3. 同一共同方案可被多个 `Disease` 显式连接，但不得复制成多个同名方案节点。
4. 前端查看具体分型时，只读取该分型显式连接的方案；不得仅因父疾病存在方案就自动继承。
5. `TreatmentPlan` 只能包含 `Medication`、`Procedure`、`TreatmentItem`；`ExamPlan` 只能包含 `ExamItem`、`LabItem`。
6. `RecommendationStatement` 不能推荐 `ExamPlan` 或 `TreatmentPlan`，只能推荐方案下的具体动作。

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
| `schema_version` | Schema 版本 | 字符串 | 使用 `V主版本.次版本`。 | `V2.4` |
| `clinical_use_status` | 临床使用状态 | 字符串 | `draft` 草稿、`review_ready` 待审核、`clinical_ready` 可临床使用、`blocked` 阻断。 | `clinical_ready` |

### 5.2 关系必填字段

| 字段 | 中文名称 | 类型 | 格式要求 | AMI 示例 |
|---|---|---|---|---|
| `id` | 关系编号 | 字符串 | 全局唯一且可稳定重算。 | `REL-CARD-8F31A2C9` |
| `source_code` | 起点实体编码 | 字符串 | 必须引用真实节点 `code`。 | `DIS-CARD-CAD-AMI` |
| `relationType` | 关系类型 | 字符串 | 必须来自本标准关系表。 | `has_clinical_subtype` |
| `target_code` | 终点实体编码 | 字符串 | 必须引用真实节点 `code`。 | `DIS-CARD-CAD-STEMI` |
| `batch_id` | 批次编号 | 字符串 | 与产生该关系的批次一致。 | `BATCH-CARD-CAD-20260719-001` |
| `schema_version` | Schema 版本 | 字符串 | 固定为当前生成版本。 | `V2.4` |
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
| `dictionary_validation_status` | 字典二次校验状态 | 字符串 | `unverified` 未校验、`validated` 已通过、`conflict` 存在冲突、`rejected` 拒绝使用。只有 `validated` 可进入正式主数据。 | `validated` |
| `dictionary_validation_sources` | 二次校验来源 | 字符串数组 | 记录实际核验来源类型或来源编码；不得填写“大模型”。 | `["official_code_standard","authoritative_textbook"]` |
| `dictionary_validation_note` | 二次校验说明 | 字符串 | 记录名称、编码、别名或限制的核验结论和冲突理由。 | ICD 编码与名称一致，Oracle UUID 保留用于业务对接 |

说明：标准诊断/标准手术实体的 `name` 就是 CDSS 字典标准名称；`aliases` 保存简称和缩写；`standard_code` 保存 ICD 或手术业务编码；`cdss_dict_id` 保存 Oracle UUID；四者不能互相替代。

直接复用 CDSS 字典身份的症状、体征、检查项目、检查发现、检验项目、检验细项、药品和治疗项目同时使用以下兼容字段：`source_dict_id` 与 `cdss_dict_id` 保存同一个 Oracle UUID，`dictionary_code` 与 `standard_code` 保存同一个字典编码，`dictionary_source_table` 与 `source_table` 保存同一个物理表名。新接口优先读取前一组通用字段，旧接口可继续读取后一组兼容字段；两组值必须同步，禁止各自维护。

标准手术补充规则：

1. `Procedure` 表示临床上明确的手术或操作动作，`StandardProcedure` 表示 CDSS 可回填的标准手术字典项目；两者通过 `has_standard_procedure` 连接，一项临床动作可对应多个需要业务端继续选择的标准项目。
2. 只有 `valid_flag=1` 且 `dictionary_validation_status=validated` 的 `StandardProcedure` 可供正式 CDSS 使用；字段名不得简写为 `validation_status`。
3. 主名称必须是完整中文名称，`PCI`、`TAVR`、`TEVAR`、`BPA`、`PEA` 等缩写只进入 `aliases`。
4. “手术治疗”“介入治疗”“肺移植同时修补心脏缺损”等无法唯一对应一个标准手术编码的宽泛或复合策略，应建为 `TreatmentItem` 或拆成多个有原文依据的具体动作，不得强行建立标准手术映射。
5. 图谱中保留的 `Procedure` 必须映射有效标准手术；尚无有效字典项时进入注册队列并禁止进入正式推荐区。

### 5.5 基础人群与有效性限制

以下字段适用于 `StandardDiagnosis`、`StandardProcedure`、`Medication`、`ExamItem`、`LabItem`、`TreatmentItem`。CDSS 有效字典记录先进入候选池；通过二次校验后保留其 UUID、编码和名称。基础限制不得无脑复制字典值，必须结合权威教材、指南、共识、监管机构批准的药品说明书和外部权威白名单资料核实、补充或纠错。模型只能抽取、归一、发现冲突和生成候选，不能作为医学证据来源。

| 字段 | 中文名称 | 类型 | 格式要求 | AMI 示例 |
|---|---|---|---|---|
| `sex_limit_code` | 性别限制编码 | 字符串/整数/空 | 保留 Oracle 候选原值；必须取得代码含义并完成二次校验后才可用于过滤。 | 不限制对应编码 |
| `sex_limit_name` | 性别限制名称 | 字符串/空 | 二次校验后的中文含义，只允许不限制、男性、女性或已确认的业务字典名称。 | 不限制 |
| `age_min` | 最小年龄 | 数值/空 | 与 `age_unit` 配套。 | `18` |
| `age_max` | 最大年龄 | 数值/空 | 与 `age_unit` 配套。 | 空 |
| `age_unit` | 年龄单位 | 字符串 | 天、月、岁。 | 岁 |
| `pregnancy_limit_code` | 妊娠限制编码 | 字符串/整数/空 | 仅在来源表真实存在该字段或有权威证据时写入；没有标准值时不得生成默认值。 | 空 |
| `pregnancy_limit_name` | 妊娠限制名称 | 字符串/空 | 不限制、慎用、禁用或字典原名称。 | 空 |
| `lactation_limit_code` | 哺乳限制编码 | 字符串/整数/空 | 使用 CDSS 字典原值。 | 空 |
| `lactation_limit_name` | 哺乳限制名称 | 字符串/空 | 使用 CDSS 字典原名称。 | 空 |
| `population_limit_source_types` | 人群限制来源类型 | 字符串数组 | 使用受控来源类型；至少包含实际采用来源。 | `["cdss_standard_dict","guideline"]` |
| `population_limit_evidence_codes` | 人群限制证据编码 | 字符串数组 | 非字典补充值必须关联现行 Evidence 编码；纯字典值可为空。 | `["EVD-CARD-AMI-001"]` |
| `population_limit_review_status` | 人群限制审核状态 | 字符串 | `dictionary_unverified` 字典未核验、`dictionary_verified` 字典值已交叉验证、`evidence_confirmed` 权威证据确认、`governed_composite` 多来源裁决、`source_conflict` 来源冲突、`not_covered` 来源未覆盖。只有 `dictionary_verified`、`evidence_confirmed`、`governed_composite` 可进入正式预过滤。 | `governed_composite` |

基础过滤顺序：有效期 → 性别 → 年龄 → 妊娠 → 哺乳。通过基础过滤后，再由规则引擎判断肾功能、肝功能、过敏史、出血风险、药物相互作用、生命体征、检验结果、急性/稳定期、就诊场景、时间窗、既往手术/卒中和并发症。

空值表示“来源未覆盖或尚未核验”，不等于“不限制”。`age_unit` 只有在 `age_min` 或 `age_max` 至少一个有值时才能保存；来源表没有妊娠/哺乳字段时，禁止迁移脚本自动填默认编码。限制代码无法解释为中文含义时，状态必须为 `dictionary_unverified`，不得执行患者过滤。

来源裁决顺序：CDSS 有效字典提供业务 UUID 和现有业务值，但名称与编码必须对照官方分类标准、教材/指南或监管资料完成二次校验；药品全局禁忌优先采用监管机构批准说明书；临床场景限制优先采用现行权威指南/共识；疾病基础知识采用权威教材/专著；仍缺失时检索外部权威白名单并下载原文归档。来源冲突不得直接覆盖，必须标记 `source_conflict` 并进入裁决；模型自身知识不得写成来源。

## 6. CDSS 标准字典来源规则

### 6.1 已确认的业务候选来源

| 标准对象 | 首选来源 | 使用规则 | AMI 示例 |
|---|---|---|---|
| 标准诊断 | `K_ICD10_DICT` / 实际生产配置的诊断字典表 | 有效标志为 1 的记录进入候选池；对照官方编码标准和临床语义后使用。 | I21.900 急性心肌梗死 |
| 症状 | `K_SYMPTOM_DICT` | 候选主名与教材/术语标准核验；口语名称进入别名。 | 胸痛 |
| 检查项目 | `K_EXAM_ITEM_DICT` | 先核验项目语义，并与检查发现分开。 | 常规心电图 |
| 检验项目 | `K_LAB_ITEM_DICT` | 先核验项目语义，并与检验细项分开。 | 心肌损伤标志物检测 |
| 检验细项 | `K_LAB_SUBITEM_DICT` | 核验名称、编码、单位及所属检验项目。 | 心肌肌钙蛋白 I |
| 药品 | `K_DRUG_DICT` | 对照监管批准说明书核验标准全称，简称和缩写放别名。 | 阿司匹林 |
| 标准手术 | `K_OPERATION_HANDLE_DICT` | 有效记录进入候选池；对照手术编码标准和临床语义后使用。 | 经皮冠状动脉介入治疗 |
| 治疗项目 | `K_TREATMENT_DICT` | 核验为非药品、非手术治疗后使用。 | 氧疗 |

### 6.2 V2.6 已落地的新增标准来源

| 标准对象 | 处理要求 | 不允许 | AMI 示例 |
|---|---|---|---|
| 体征 | 使用 `K_CLINICAL_SIGN_DICT`；只注册原子体征，疾病体征总称和复合句进入待审队列。 | 把体征全部塞入症状表。 | 心包摩擦音 |
| 检查发现 | 建设或确认 `K_EXAM_OBSERVATION_DICT`。 | 将 ST 段抬高当作检查项目。 | ST 段抬高 |
| 检查项目与发现关系 | 使用 `K_EXAM_OBSERVATION_REL`；仅保存图谱中有明确项目归属的关系。 | 只靠名称猜归属。 | 心电图 → ST 段抬高 |
| 检验标本 | 使用现有检验标本字典，物理表名写入批次配置。 | 在脚本中写死未核实表名。 | 血清 |
| 生命体征 | 使用 `K_VITAL_SIGN_ITEM_DICT`；保存项目名称、单位和值类型，患者阈值由规则配置。 | 把“低血压”等判断结果当生命体征项目。 | 心率、收缩压 |
| 医学术语和别名 | `K_TERM`/`K_TERM_SYNONYM` 负责文本识别，`K_TERM_DICT_MAPPING` 负责术语与正式字典身份映射。 | 把同义词建成重复正式节点。 | AMI、急性心梗 → 急性心肌梗死 |

医院自定义诊断和院内映射表用于 CDSS 上线后的院内回填，不属于文献抽取主数据源，不写入本 Schema 的标准知识抽取流程。

### 6.2.1 药品术语归一边界

药品继续使用统一的 `Medication` 实体类型，不因归一规则新增实体类型，但必须区分以下语义层级：

| 输入性质 | 处理方式 | 禁止做法 | 示例 |
|---|---|---|---|
| 药物类别 | 建为类别知识，并用上下位关系连接具体药品。 | 把具体药品放进类别的 `aliases`。 | P2Y12 受体抑制剂 → 氯吡格雷 |
| 活性成分/通用名 | 作为药品主概念；同一成分的等价名称可进 `aliases`。 | 与品牌名或具体剂型直接合并。 | 阿司匹林；别名乙酰水杨酸 |
| 具体剂型 | 优先采用经 CDSS 字典和监管资料核验的规范制剂名。 | 使用倒装口语名称作正式主名。 | 阿司匹林肠溶片 |
| 商品名 | 作为品牌信息关联规范药品。 | 把商品名当通用名。 | 拜阿司匹林 |
| 口语、倒装或不规范输入 | 保留原词及来源，映射到已核验主名。 | 覆盖原词、凭模型记忆自动注册。 | 肠溶阿司匹林 → 阿司匹林肠溶片 |

`aliases` 只保存同一概念可互换的等价名称。类别成员、剂型和品牌不属于普通同义词，必须保留各自语义关系。未唯一命中有效字典或未完成权威核验的名称只能进入待审队列。

### 6.3 V2.6 新增表及职责

| 物理表 | 中文职责 | 可否自动写入 | 关键约束 | AMI 示例 |
|---|---|---|---|---|
| `K_CLINICAL_SIGN_DICT` | 体征标准字典 | 可 | 只允许原子、客观体征。 | 心包摩擦音 |
| `K_EXAM_OBSERVATION_DICT` | 检查发现标准字典 | 可 | 只保存观察结果，不保存“提示某病”的推理句。 | ST 段抬高 |
| `K_VITAL_SIGN_ITEM_DICT` | 生命体征项目字典 | 可 | 项目与阈值分开。 | 收缩压、mmHg |
| `K_EXAM_OBSERVATION_REL` | 检查项目—检查发现归属 | 可 | 必须有明确原关系，不靠名称猜测。 | 心电图 → ST 段抬高 |
| `K_TERM_DICT_MAPPING` | 医学术语—标准字典映射 | 可 | 仅唯一确定匹配自动写入。 | 急性心梗 → 急性心肌梗死 |
| `K_KG_DICT_CHANGE_REVIEW` | 既有字典变更待审队列 | 可 | 只记录建议，不直接改原字典。 | 未命中症状待注册 |
| `K_DIAGNOSIS_RULE` | 疑似诊断规则头 | 可 | 未绑定标准诊断时仅知识展示。 | AMI 疑似诊断初筛规则 |
| `K_DIAGNOSIS_RULE_ITEM` | 疑似诊断规则项 | 可 | 必须保存发现、作用等级、证据和初始化方式。 | 胸痛为一般支持 |
| `K_DIAGNOSIS_RULE_VERSION` | 诊断作用矩阵版本 | 可 | 解释分值的版本必须可追溯。 | V2.0 作用等级矩阵 |
| `K_DIAGNOSIS_RULE_LOG` | 规则变更日志 | 可 | 自动初始化和人工覆盖均留痕。 | AMI 规则批量初始化 |

既有 Oracle 字典表第一批只读；缺失、歧义、重复、别名或名称冲突写入 `K_KG_DICT_CHANGE_REVIEW` 并生成评审页面。只有新增表允许流程直接写入。既有表的新增、改名、合并、失效或删除必须进入第二批评审，不能由解析脚本直接执行。

## 7. 正式 CDSS 推荐链

```text
患者数据/EMR
  -> 基础人群与有效性过滤
  -> 疑似/初步诊断 Disease
  -> 进入 ClinicalPathway
  -> 定位 PathwayStage
  -> 匹配 ClinicalRule
  -> 生成 RecommendationStatement
  -> recommends_action / recommends_assessment / blocks_action
  -> 具体执行项目或临床评估目标
疾病 -> SourceAdjudication -> RecommendationStatement
SourceAdjudication -> 主依据 Guideline + 主 Evidence
```

具体执行项目只能是：`Medication`、`Procedure`、`ExamItem`、`LabItem`、`TreatmentItem`、`FollowUp`。临床评估目标只能是：`DiagnosisCriteria`、`DifferentialDiagnosis`、`RiskStratification`、`RiskFactor`、`Complication`、`ExamObservation`、`LabSubitem`、`Etiology`。来源裁决不得直连推荐目标；疾病直连治疗方案、阶段可选动作和疾病级证据池不得直接显示为当前患者推荐。

### 7.1 疑似疾病排序规则

疑似疾病排序使用“疾病规则头 + 症状/体征规则项 + 版本化作用矩阵”，不把抽取置信度当诊断权重，也不由大模型生成疾病概率。规则项只有在标准字典唯一命中、疾病已绑定有效标准诊断、原文明确提到该症状/体征、存在证据编码、无未解决冲突且审核状态允许时，才可参与自动排序。

| 字段 | 中文名称 | 格式要求 | AMI 示例 |
|---|---|---|---|
| `diagnostic_effect_code` | 诊断作用 | `REQUIRED` 必要、`STRONG_SUPPORT` 强支持、`SUPPORT` 一般支持、`WEAK_SUPPORT` 弱支持、`AGAINST` 反对、`EXCLUDE` 排除、`UNSET` 未确定。 | `SUPPORT` |
| `diagnostic_weight_level` | 作用等级 | 0—3 的有序等级；不直接表示概率，实际分值由版本表解释。 | `2` |
| `diagnostic_score_enabled` | 是否参与自动排序 | 只允许 `0/1`；缺字典、缺证据、缺标准诊断或作用未确定时必须为 0。 | `1` |
| `diagnostic_rule_item_id` | 规则项ID | 对应 `K_DIAGNOSIS_RULE_ITEM.ID`。 | 32位UUID |
| `diagnostic_model_version` | 作用矩阵版本 | 对应 `K_DIAGNOSIS_RULE_VERSION.MODEL_VERSION`。 | `DIAG-EFFECT-V2.0-20260721` |
| `source_evidence_id` | 来源证据编码 | 必须能回到教材或指南原文。 | `EVD-CARD-AMI-001` |
| `diagnostic_initialization_method` | 初始化方式 | 当前只允许“原文显式措辞”或“仅有关联不计分”等受控值。 | `EXPLICIT_TEXT_WINDOW` |
| `diagnostic_review_status` | 规则项状态 | `AUTO_ENABLED` 自动启用、`AUTO_UNSCORED` 保留但不计分；人工调整写入日志。 | `AUTO_ENABLED` |

人工维护只覆盖具体规则项，不直接改全局算法；每次修改保存修改前值、修改后值、操作人、时间和原因。修改作用矩阵时必须新建版本，历史病例仍按原版本解释。

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
| 来源裁决直连 `recommends_action`/`blocks_action` | 迁移到对应推荐陈述 | 来源裁决只负责主依据和冲突裁决；具体推荐目标统一由推荐陈述连接。 | AMI 来源裁决 → AMI 推荐陈述 → AMI 诊断标准 |

自 V2.3 起，`requires_exam_item`、`requires_lab_item` 仅用于读取历史数据，不得新增。迁移时按疾病和临床场景建立 `ExamPlan`，再分别改为 `includes_exam_item`、`includes_lab_item`。不得为了迁移机械生成一个同名空方案。

迁移期允许旧数据只读查询；V2.0 新批次不得继续生成旧实体或旧关系。迁移必须先备份、生成映射表和回滚文件，再小批量写库并执行服务器复核。

## 10. 数据质量硬闸门

以下任一项不通过，批次不得标记“正式 CDSS 可用”：

1. 节点缺少 `KGNode`、`code`、`entityType`、`name`、`schema_version`。
2. 疾病大类被错误标记为可诊断或保存 ICD 编码。
3. 宽口径疾病没有疾病大类；具体分型没有父疾病；疾病分型形成环；同名疾病重复。
4. 新增 `DiseaseClassification`、`Exam`、`LabTest`、`ExamIndicator` 或 V1.x 旧关系。
5. 可回填疾病没有有效 `StandardDiagnosis`；可下医嘱手术没有有效 `StandardProcedure`。
6. 标准主数据没有对应有效标志为 1 的 CDSS 候选记录，或虽有候选记录但未完成名称、编码、UUID、重复项和权威来源二次校验。
7. 症状与体征混用；检查项目与检查发现混用；检验项目与检验细项混用。
8. 检验细项没有所属检验项目；检查发现没有所属检查项目。
9. 标准名称使用英文缩写，或别名没有进入 `aliases`/医学术语别名管理。
10. 诊断标准没有 `has_diagnostic_component` 明细，或明细没有原文证据。
11. 鉴别诊断只有对象名称，没有鉴别要点、排除检查或临床规则。
12. 治疗方案没有适用场景、触发条件、具体动作、禁忌/排除条件或证据。
13. 正式推荐没有“来源裁决 → 推荐陈述 → 具体执行项目或临床评估目标”完整链，或推荐陈述未通过 `recommends_action`、`recommends_assessment`、`blocks_action` 连接目标。
14. 正式推荐没有来源裁决、主依据、冲突状态和可复核裁决理由。
15. 基础人群限制缺失时未标记来源状态，非字典补充值没有原文证据，或把模型自身知识当成年龄、性别、妊娠、哺乳限制来源。
16. 人群限制代码没有已确认中文含义、空值被解释成“不限制”、年龄单位没有年龄范围，或来源表没有相应字段却生成默认妊娠/哺乳限制。
17. 关系端点不存在、关系类型不合法、同一语义关系重复。
18. 写库前无回滚清单，或写库后服务器复核阻断项不为 0。
19. 前端把目录、展示分组、阶段可选动作或疾病级证据池当作正式诊断/推荐展示。
20. 疾病大类/展示分组连接方案或具体动作；方案连接到错误类型；父疾病方案被子分型自动继承；正式推荐终点是方案而不是具体动作。
21. 同一医学概念因教材、指南或共识来源不同而重复建实体，或同一证据被无必要地连接到多个上层容器。
22. 教材/指南句子片段被误建为方案或可执行规则；`TreatmentPlan` 继续连接 `TreatmentPlan` 形成方案套方案。
23. 手术主名称是英文缩写、存在同 UUID/同标准编码重复、标准手术无临床动作引用，或临床手术未映射有效标准手术。
24. 宽泛治疗词、复合治疗策略、随访观察或生活方式被误标为 `Procedure`。
25. 空壳节点的证据被批量复制到所有上级治疗方案，或 `supported_by_evidence` 关系缺少来源定位与追溯属性。
26. 治疗方案仅检查药品和手术而漏掉 `TreatmentItem`，造成已有真实治疗项目的方案被误判为空。
27. 标准手术仍使用 `validation_status`、`validation_sources`、`validation_note` 等旧简称，而未使用 5.4 节统一字段。
28. 多个同类型图谱节点指向同一个 CDSS 字典 UUID，或标准字典身份字段两组兼容值不一致。
29. 疑似诊断规则项参与自动排序但缺少标准字典 UUID、标准诊断、证据编码、原文上下文或版本号。
30. 把抽取置信度直接当作诊断权重，或由大模型无依据生成疾病概率和数值分数。
31. 既有 Oracle 字典的改名、合并、删除、失效或新增未进入待审队列和评审页面就直接执行。

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
standard_dictionary_snapshot.csv          本批次 Oracle/CDSS 有效候选字典快照
standard_dictionary_validation.csv        候选字典二次校验结论、来源和状态
standard_dictionary_issue_queue.csv       重复、缺码、语义或来源冲突问题队列
standard_dictionary_mapping.csv           校验通过实体与 CDSS 业务 UUID 映射
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
