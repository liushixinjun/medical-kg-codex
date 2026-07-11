# 专科知识图谱 Schema 标准

版本：V1.15
状态：正式执行标准
更新时间：2026-07-11 17:34:47
适用范围：所有专科、疾病大类和单病种知识图谱数据实例。

## 0. 文档边界

主Schema只保留“当前必须执行的标准”：实体、关系、字段概要、硬闸门和建模边界。历史变更、迁移证据、字段细则、CDSS长案例已迁出到 `schema_docs/`。

附录入口：

- `schema_docs/专科知识图谱Schema标准_完整归档_V1.13_20260711.md`：瘦身前完整归档。
- `schema_docs/Schema历史变更记录.md`：历史版本记录。
- `schema_docs/Schema字段字典与证据规则.md`：字段、Evidence、Guideline、RecommendationStatement、provenance 细则。
- `schema_docs/Schema关系兼容与禁用清单.md`：旧关系、禁用关系、待改名关系。
- `schema_docs/Schema专病CDSS动态流程映射.md`：专病流程引擎和前端/后端使用说明。

## 1. 核心原则

1. 基础权威教材搭骨架，指南/共识填决策血肉。
2. 图谱存医学知识、结构化关系和证据链；专病流程引擎根据 EMR/患者状态触发推荐。
3. CDSS 推荐必须落到 `RecommendationStatement`，不得从疾病级证据池或动作节点二次推理依据。
4. 诊断标准必须拆解为可推理明细组件，不得只有标题节点。
5. 新关系统一小写 snake_case；旧大写 `HAS_*` 关系禁止继续生成。
6. `Specialty` 是多学科顶层根节点，属于战略保留实体，不得因低频删除。

## 2. 三层架构

```text
Specialty 专科
  -> DiseaseCategory 疾病大类
    -> DiseaseSubcategory 疾病亚类/分组
      -> Disease 单病种
        -> 医学事实层：定义、病因、机制、症状、体征、检查、诊断、治疗、随访、预后
        -> CDSS决策层：路径阶段、临床规则、推荐陈述、动作、证据链
```

## 3. 标准实体类型

> 阅读规则：表格先看“中文名”和“临床含义”，`entityType` 是实体类型编码，给 Neo4j、接口和脚本使用。

### 3.1 目录与疾病

| 中文名     | 实体类型 entityType         | 格式或使用要求                           | AMI示例           |
| ------- | ----------------------- | --------------------------------- | --------------- |
| 专科/顶层学科 | `Specialty`             | 多学科根节点；当前只有 1 个也不能删；`code` 全局唯一。  | 心血管内科           |
| 疾病大类    | `DiseaseCategory`       | 一组相关疾病；名称用临床常用中文标准名。              | 冠心病             |
| 疾病亚类    | `DiseaseSubcategory`    | 大类下分组；没有明确亚类时可不建。                 | 急性冠脉综合征         |
| 疾病/专病   | `Disease`               | CDSS 和知识图谱核心对象；标准名入 `name`，简称入别名。 | 急性心肌梗死；别名 `AMI` |
| 疾病分型/分类 | `DiseaseClassification` | 疾病的临床分型或分类；不得替代 `Disease` 主体。     | STEMI、NSTEMI    |

### 3.2 医学事实层

| 中文名     | 实体类型 entityType              | 格式或使用要求                               | AMI示例                  |
| ------- | ---------------------------- | ------------------------------------- | ---------------------- |
| 疾病定义    | `Definition`                 | 存疾病概念总述；可保留教材或指南原文摘要；不能写空泛标题。         | 急性心肌梗死定义               |
| 定义明细    | `DefinitionComponent`        | 定义中的可拆解要点；每个明细应可单独追溯证据。               | 心肌坏死、急性心肌缺血证据          |
| 病因      | `Etiology`                   | 疾病发生原因；名称用病因短语，不写长段落。                 | 冠状动脉粥样硬化斑块破裂           |
| 病理生理    | `Pathophysiology`            | 发病机制和病理过程；可拆成多个机制节点。                  | 血栓形成导致冠脉急性闭塞           |
| 流行病学    | `Epidemiology`               | 发病率、人群、地区等；数值要带单位和来源。                 | 发病率升高、高危人群             |
| 症状      | `Symptom`                    | 患者主观感受；症状标准名入 `name`，口语说法入 `aliases`。 | 胸痛；别名 `胸闷痛`            |
| 体征      | `Sign`                       | 医生客观发现；体征和症状不能混用。                     | 出汗、低血压                 |
| 危险因素    | `RiskFactor`                 | 增加患病或不良结局风险的因素；不得写成诊断结论。              | 吸烟、高血压、糖尿病             |
| 并发症     | `Complication`               | 疾病导致的并发问题；需能与疾病通过关系追溯。                | 心力衰竭、心律失常、心源性休克        |
| 检查      | `Exam`                       | 影像、心电、超声等检查项目；项目名标准化。                 | 心电图、冠状动脉造影             |
| 检验      | `LabTest`                    | 血液、生化、标志物等检验项目；项目名标准化。                | 肌钙蛋白、CK-MB             |
| 检查/检验指标 | `ExamIndicator`              | 结构化指标或数值项；指标名、方向、单位要清楚。               | ST段抬高、肌钙蛋白升高           |
| 阈值规则    | `ThresholdRule`              | 指标阈值、动态变化、阳性/阴性条件；数值必须带单位、方向和时间窗。     | 肌钙蛋白超过第99百分位并呈动态变化     |
| 诊断标准    | `DiagnosisCriteria`          | 一组诊断标准标题或总规则；必须继续拆明细。                 | 急性心肌梗死诊断标准             |
| 诊断标准明细  | `DiagnosisCriteriaComponent` | 诊断标准下可推理的具体条件；不得只写“诊断标准明细”。           | 缺血性症状、心电图缺血改变、肌钙蛋白动态升高 |
| 鉴别诊断    | `DifferentialDiagnosis`      | 需要排除或区分的疾病/状态；应有鉴别要点或排除检查。            | 主动脉夹层、肺栓塞、急性心包炎        |
| 风险分层    | `RiskStratification`         | 评分或分层工具；评分项和阈值另用规则/指标表达。              | GRACE评分                |
| 治疗方案    | `TreatmentPlan`              | 治疗策略、路径或方案对象；必须有关联药物、操作、规则或证据。        | 再灌注治疗方案                |
| 药物      | `Medication`                 | 药物类别或具体药品；标准全称入 `name`，缩写入 `aliases`。 | 阿司匹林；别名 `ASA`          |
| 操作/手术   | `Procedure`                  | 介入、手术、器械、操作；名称应可转为医嘱或路径动作。            | 急诊PCI、溶栓治疗             |
| 随访      | `FollowUp`                   | 复诊、监测、长期管理；应说明频率或触发条件。                | 出院后心功能和再缺血风险随访         |
| 预后      | `Prognosis`                  | 结局、复发、死亡风险等；风险描述需有来源。                 | 再梗死风险、死亡风险             |
| 预防      | `Prevention`                 | 一级/二级预防、生活方式、患者教育；应能落到可执行建议。          | 戒烟、血脂管理、抗血小板二级预防       |
| 禁忌/排除条件 | `Contraindication`           | 禁忌证、排除条件、阻断推荐原因；正式推荐阻断必须引用。           | 活动性出血阻断抗栓治疗            |

### 3.3 来源、证据与 CDSS 决策层

| 中文名        | 实体类型 entityType           | 格式或使用要求                           | AMI示例                    |
| ---------- | ------------------------- | --------------------------------- | ------------------------ |
| 指南/教材/共识来源 | `Guideline`               | 来源文献对象；名称、年份、版本、来源类型必须清楚。         | 2023 ESC 急性冠脉综合征指南       |
| 来源章节       | `SourceSection`           | 文献中的章、节、小标题、页码范围；不得只写本地文件路径。      | STEMI再灌注治疗章节             |
| 循证证据片段     | `Evidence`                | 一段可追溯原文证据；必须有原文、页码/段落、来源。         | “STEMI患者优先行直接PCI...”原文片段 |
| 专病诊疗路径     | `ClinicalPathway`         | 一组诊疗阶段构成的专病路径；是 CDSS 入口，不是治疗方案。   | 急性心肌梗死急诊诊疗路径             |
| 路径阶段       | `PathwayStage`            | 疑似识别、确诊、分层、治疗、随访等阶段；阶段名不能与治疗方案混用。 | STEMI再灌注决策阶段             |
| 临床规则       | `ClinicalRule`            | 触发、适用、排除、禁忌、阈值逻辑；条件必须结构化。         | 发病12小时内且PCI可及            |
| 推荐陈述       | `RecommendationStatement` | CDSS 推荐卡片根实体；必须连接动作、证据和指南。        | 推荐急诊PCI                  |
| 患者状态       | `PatientState`            | 妊娠、肾功能不全、老年、急性期等；用于触发或阻断规则。       | 急性期、出血高风险                |
| 临床事件       | `ClinicalEvent`           | 复发、急性发作、猝死、再住院等；用于路径流转或预后。        | 再梗死、心源性休克                |

## 4. 标准关系

> 阅读规则：关系表示“谁连接到谁”。中文业务关系帮助人理解，`relationType` 是关系类型编码，给 Neo4j、接口和脚本使用。

### 4.1 目录关系

| 起点   | 业务关系    | 关系类型 relationType    | 终点      | 格式或使用要求           | AMI示例             |
| ---- | ------- | -------------------- | ------- | ----------------- | ----------------- |
| 专科   | 包含疾病大类  | `has_category`       | 疾病大类    | 起点和终点必须都是目录实体。    | 心血管内科 -> 冠心病      |
| 疾病大类 | 包含疾病亚类  | `has_subcategory`    | 疾病亚类    | 有明确亚类时使用；没有亚类可跳过。 | 冠心病 -> 急性冠脉综合征    |
| 疾病大类 | 包含疾病    | `has_disease`        | 疾病      | 大类直接包含疾病时使用。      | 冠心病 -> 急性心肌梗死     |
| 疾病亚类 | 包含疾病    | `has_disease`        | 疾病      | 亚类下疾病归属关系。        | 急性冠脉综合征 -> 急性心肌梗死 |
| 疾病   | 具有分型/分类 | `has_classification` | 疾病分型/分类 | 只表达分类，不替代疾病本体。    | 急性心肌梗死 -> STEMI   |

示例：

```text
心血管内科 -> has_category -> 冠心病
冠心病 -> has_disease -> 急性心肌梗死
急性心肌梗死 -> has_classification -> STEMI
```

### 4.2 医学事实关系

| 起点   | 业务关系   | 关系类型 relationType          | 终点       | 格式或使用要求               | AMI示例                  |
| ---- | ------ | -------------------------- | -------- | --------------------- | ---------------------- |
| 疾病   | 有定义    | `has_definition`           | 疾病定义     | 每个核心疾病应有定义；来源优先教材/指南。 | 急性心肌梗死 -> 急性心肌梗死定义     |
| 疾病定义 | 有定义明细  | `has_definition_component` | 定义明细     | 定义可拆解时使用；明细要可追溯。      | AMI定义 -> 心肌坏死          |
| 疾病   | 有病因    | `has_etiology`             | 病因       | 病因短语标准化，避免长段落。        | 急性心肌梗死 -> 斑块破裂         |
| 疾病   | 有病理生理  | `has_pathophysiology`      | 病理生理     | 机制过程可拆多个节点。           | 急性心肌梗死 -> 冠脉血栓形成       |
| 疾病   | 有流行病学  | `has_epidemiology`         | 流行病学     | 数值类信息要带单位、来源。         | 急性心肌梗死 -> 高危人群         |
| 疾病   | 有症状    | `has_symptom`              | 症状       | 主观感受用症状，不和体征混用。       | 急性心肌梗死 -> 胸痛           |
| 疾病   | 有体征    | `has_sign`                 | 体征       | 客观发现用体征。              | 急性心肌梗死 -> 出汗           |
| 疾病   | 有危险因素  | `has_risk_factor`          | 危险因素     | 不写诊断结论。               | 急性心肌梗死 -> 吸烟           |
| 疾病   | 可导致并发症 | `may_cause_complication`   | 并发症      | 表达可能导致，不等于已经发生。       | 急性心肌梗死 -> 心源性休克        |
| 疾病   | 需要检查   | `requires_exam`            | 检查       | 检查项目标准化。              | 急性心肌梗死 -> 心电图          |
| 疾病   | 需要检验   | `requires_lab_test`        | 检验       | 检验项目标准化。              | 急性心肌梗死 -> 肌钙蛋白         |
| 检查   | 包含指标   | `exam_has_indicator`       | 检查/检验指标  | 指标必须属于该检查。            | 心电图 -> ST段抬高           |
| 检验   | 包含指标   | `lab_test_has_indicator`   | 检查/检验指标  | 指标必须属于该检验。            | 肌钙蛋白 -> 肌钙蛋白升高         |
| 疾病   | 有诊断标准  | `has_diagnostic_criteria`  | 诊断标准     | 诊断标准必须继续拆明细。          | 急性心肌梗死 -> 急性心肌梗死诊断标准   |
| 诊断标准 | 有诊断明细  | `has_diagnostic_component` | 诊断标准明细组件 | 下级必须是可判断条件。           | 急性心肌梗死诊断标准 -> 缺血性心电图改变 |
| 疾病   | 需要鉴别   | `differentiates_from`      | 鉴别诊断     | 鉴别诊断应补鉴别要点或排除检查。      | 急性心肌梗死 -> 主动脉夹层        |
| 疾病   | 有风险分层  | `has_risk_stratification`  | 风险分层     | 风险工具或分层方案。            | 急性冠脉综合征 -> GRACE评分     |

#### 诊断标准明细怎么理解

`DiagnosisCriteria` 是“诊断标准标题”，不能只停留在标题。
`has_diagnostic_component` 负责把诊断标准拆成医生能判断、系统能推理的明细。

示例：急性心肌梗死诊断标准

```text
急性心肌梗死
  -> has_diagnostic_criteria
    -> 急性心肌梗死诊断标准
      -> has_diagnostic_component
        -> 急性缺血症状或等效表现
        -> 肌钙蛋白升高及动态变化
        -> 缺血性心电图改变
        -> 新发室壁运动异常
        -> 冠状动脉血栓或责任病变
```

明细组件可以落到不同实体类型：

| 明细类型      | 可以使用的实体                                       | 格式或使用要求              | AMI示例             |
| --------- | --------------------------------------------- | -------------------- | ----------------- |
| 症状/体征条件   | `Symptom`、`Sign`、`DiagnosisCriteriaComponent` | 可用已有症状/体征，也可建诊断明细组件。 | 缺血性胸痛             |
| 检查/检验条件   | `Exam`、`LabTest`、`ExamIndicator`              | 检查项目和指标要分清。          | 心电图ST段抬高、肌钙蛋白升高   |
| 阈值/动态变化   | `ThresholdRule`                               | 数值、单位、方向、时间窗必须明确。    | 肌钙蛋白超过第99百分位并动态变化 |
| 组合逻辑/排除条件 | `ClinicalRule`、`Contraindication`             | 用于“至少满足一项”“排除某情况”等。  | 排除非缺血性心肌损伤        |

前端展示时，不要只显示“急性心肌梗死诊断标准”一个标题，必须继续下钻显示这些明细。

### 4.3 治疗、管理与 CDSS 关系

| 起点        | 业务关系      | 关系类型 relationType            | 终点     | 格式或使用要求                                     | AMI示例                      |
| --------- | --------- | ---------------------------- | ------ | ------------------------------------------- | -------------------------- |
| 疾病        | 有治疗方案     | `has_treatment_plan`         | 治疗方案   | 用于知识浏览；不等于当前患者推荐。                           | 急性心肌梗死 -> 再灌注治疗方案          |
| 治疗方案      | 包含药物      | `includes_medication`        | 药物     | 表达方案组成；药物类别应继续连具体药物。                        | 抗血小板治疗 -> 阿司匹林             |
| 治疗方案      | 包含操作/手术   | `includes_procedure`         | 操作/手术  | 表达方案组成；操作名应可转为医嘱或路径动作。                      | 再灌注治疗方案 -> 急诊PCI           |
| 疾病        | 可用药物治疗    | `treated_by_medication`      | 药物     | 疾病事实，不等于当前患者推荐。                             | 急性心肌梗死 -> 阿司匹林             |
| 疾病        | 可用操作/手术治疗 | `treated_by_procedure`       | 操作/手术  | 疾病事实，不等于当前患者推荐。                             | STEMI -> 急诊PCI             |
| 药物类别      | 包含具体药物    | `has_specific_medication`    | 具体药物   | 药品归一；类别不能替代具体药物。                            | P2Y12受体抑制剂 -> 氯吡格雷         |
| 疾病        | 有随访       | `has_follow_up`              | 随访     | 长期管理；应说明频率或触发条件。                            | 急性心肌梗死 -> 出院后随访            |
| 疾病        | 有预后       | `has_prognosis`              | 预后     | 结局说明；不能替代风险分层。                              | 急性心肌梗死 -> 再梗死风险            |
| 疾病        | 有预防       | `has_prevention`             | 预防     | 预防/教育；应能落到可执行建议。                            | 急性心肌梗死 -> 戒烟               |
| 疾病        | 有专病路径     | `has_clinical_pathway`       | 专病诊疗路径 | CDSS 入口；路径不是治疗方案。                           | 急性心肌梗死 -> 急诊诊疗路径           |
| 专病路径      | 包含阶段      | `has_pathway_stage`          | 路径阶段   | 流程结构；阶段名不能与治疗方案混用。                          | 急诊诊疗路径 -> STEMI再灌注决策阶段     |
| 路径阶段      | 有阶段规则     | `has_stage_rule`             | 临床规则   | 阶段触发条件；规则必须结构化。                             | STEMI再灌注决策阶段 -> PCI可及规则    |
| 路径阶段      | 有阶段候选动作   | `has_recommended_action`（旧名） | 动作节点   | 仅用于阶段菜单；建议迁移为 `stage_has_available_action`。 | STEMI再灌注决策阶段 -> 急诊PCI、溶栓治疗 |
| 临床规则/推荐陈述 | 正式推荐动作    | `recommends_action`          | 动作节点   | 当前患者满足规则后才展示。                               | 推荐急诊PCI -> 急诊PCI           |
| 临床规则/推荐陈述 | 阻断/禁忌动作   | `blocks_action`              | 动作节点   | 当前患者存在禁忌或需排除时展示。                            | 活动性出血规则 -> 阻断溶栓治疗          |
| 路径阶段      | 下一阶段      | `next_pathway_stage`         | 路径阶段   | 阶段流转；不能跨越必要判断阶段。                            | 疑似识别阶段 -> 确诊与分型阶段          |

#### 阶段候选动作和正式推荐动作怎么区分

可以把它理解为“菜单”和“医嘱建议”的区别。

```text
路径阶段：STEMI 再灌注决策阶段
  -> has_recommended_action
    -> 急诊 PCI
    -> 溶栓治疗
    -> 抗血小板治疗
```

上面表示：这个阶段可能涉及这些动作，类似页面菜单或路径编辑器候选项。

```text
患者：发病 2 小时，PCI 可及，无溶栓禁忌
  -> 命中 ClinicalRule
  -> RecommendationStatement
  -> recommends_action
    -> 急诊 PCI
```

上面才表示：基于当前患者条件，系统正式推荐“急诊 PCI”。

硬规则：

1. 医生推荐卡片只能用 `recommends_action` / `blocks_action`。
2. `has_recommended_action` 不能展示为“当前患者推荐”。
3. `has_recommended_action` 名称不清晰，后续数据治理建议迁移为 `stage_has_available_action`。

### 4.4 来源与证据关系

| 起点          | 业务关系  | 关系类型 relationType        | 终点       | 格式或使用要求                 | AMI示例                     |
| ----------- | ----- | ------------------------ | -------- | ----------------------- | ------------------------- |
| 指南/教材/共识    | 有来源章节 | `has_source_section`     | 来源章节     | 文献分章分节；章节需有页码或标题。       | 2023 ESC ACS指南 -> 再灌注章节   |
| 来源章节        | 包含证据  | `section_has_evidence`   | 证据片段     | 章节到原文证据；证据必须保留原文。       | 再灌注章节 -> PCI推荐原文片段        |
| 指南/教材/共识    | 包含证据  | `guideline_has_evidence` | 证据片段     | 文献直接到证据；用于全局追溯。         | ESC指南 -> STEMI直接PCI证据     |
| 可被证据支持的临床节点 | 由证据支持 | `supported_by_evidence`  | 证据片段     | 疾病、症状、检查、治疗、规则等都可以有证据。  | 急诊PCI -> PCI推荐原文片段        |
| 推荐陈述        | 基于指南  | `based_on_guideline`     | 指南/教材/共识 | 推荐来自哪份资料；医生端可展示指南名。     | 推荐急诊PCI -> 2023 ESC ACS指南 |
| 推荐陈述        | 来自证据  | `derived_from`           | 证据片段     | 推荐对应哪段原文；医生端只展示本推荐直连证据。 | 推荐急诊PCI -> PCI推荐原文片段      |

#### Evidence 为什么很多

`Guideline` 是一份资料，`Evidence` 是从资料里切出来的一段可追溯原文。
一本书或一份指南会产生很多 Evidence，这是正常的。

示例：

```text
《内科学》第10版
  -> guideline_has_evidence
    -> HCM 定义原文片段
    -> HCM 临床表现原文片段
    -> HCM 治疗原文片段
```

每个 Evidence 节点至少要能回答：

| 问题      | Evidence里应该有                                   | 格式或使用要求                          | AMI示例                           |
| ------- | ---------------------------------------------- | -------------------------------- | ------------------------------- |
| 来源是哪份资料 | `source_name` / `document_id`                  | 来源名和文档ID至少保留一个，建议都保留。            | `source_name=2023 ESC ACS指南`    |
| 在哪里     | 页码、章节、小标题、段落                                   | 页码和章节能定位原文；没有页码时写段落或小标题。         | `page=42; section=再灌注治疗`        |
| 原文是什么   | `evidence_text`                                | 保存原文摘录；翻译或摘要不能覆盖原文。              | “Primary PCI is recommended...” |
| 支持什么知识  | 通过 `supported_by_evidence` / `derived_from` 连接 | 推荐类证据优先通过 `derived_from` 直连推荐陈述。 | 推荐急诊PCI -> PCI推荐原文片段            |

医生界面不应该把某疾病下所有 Evidence 一次性展示出来。
CDSS 推荐卡片只展示当前 `RecommendationStatement` 直连的主证据。

## 5. 字段概要

### 5.1 节点必填字段

| 字段                    | 中文名      | 格式要求                                 | 示例                                                      |
| --------------------- | -------- | ------------------------------------ | ------------------------------------------------------- |
| `code`                | 实体编码     | 字符串；全局唯一；建议使用“实体类型缩写-学科-疾病/主题-哈希或序号” | `DIS-CARD-CAD-AMI`、`MED-CARD-AMI-ASPIRIN`               |
| `entityType`          | 实体类型     | 字符串；必须来自本 Schema 的标准实体类型             | `Disease`、`Medication`、`RecommendationStatement`        |
| `name`                | 标准名称     | 字符串；医生可读；不得写生成前缀、技术缩写前缀或临时编号         | `急性心肌梗死`、`阿司匹林`                                         |
| `aliases`             | 别名       | 字符串数组；没有别名时用空数组 `[]`；英文缩写、中文简称放这里    | `["AMI","急性心梗"]`                                        |
| `source_type`         | 来源类型     | 字符串；使用固定值                            | `textbook`、`guideline`、`consensus`、`external_authority` |
| `batch_id`            | 批次编号     | 字符串；必须能追溯到批次目录或批次台账                  | `BATCH-CARD-CAD-20260623-001`                           |
| `schema_version`      | Schema版本 | 字符串；使用 `V主版本.次版本` 格式                 | `V1.15`                                                 |
| `clinical_use_status` | 临床使用状态   | 字符串；必须使用固定状态值                        | `draft`、`review_ready`、`clinical_ready`、`blocked`       |

### 5.2 关系必填字段

| 字段                       | 中文名      | 格式要求                                                         | 示例                                                  |
| ------------------------ | -------- | ------------------------------------------------------------ | --------------------------------------------------- |
| `id`                     | 关系ID     | 字符串；全局唯一；建议由 `source_code + relationType + target_code` 哈希生成 | `REL-CARD-8F31A2C9`                                 |
| `source_code`            | 起点实体编码   | 字符串；必须等于某个节点的 `code`                                         | `DIS-CARD-CAD-AMI`                                  |
| `relationType`           | 关系类型     | 字符串；必须来自本 Schema 的标准关系类型；统一小写 snake_case                     | `has_diagnostic_criteria`、`recommends_action`       |
| `target_code`            | 终点实体编码   | 字符串；必须等于某个节点的 `code`                                         | `DXC-CARD-AMI-001`                                  |
| `batch_id`               | 批次编号     | 字符串；与本关系产生的批次一致                                              | `BATCH-CARD-CAD-20260623-001`                       |
| `schema_version`         | Schema版本 | 字符串；使用 `V主版本.次版本` 格式                                         | `V1.15`                                             |
| `review_status`          | 结构审核状态   | 字符串；表示结构和证据链是否通过自动审计                                         | `pending`、`passed`、`failed`                         |
| `clinical_review_status` | 临床审核状态   | 字符串；正式 CDSS 推荐关系必填；知识浏览关系可为 `not_required`                   | `pending`、`clinical_ready`、`blocked`、`not_required` |

### 5.3 通用字段格式规则

| 字段类别        | 格式要求                                    | 不允许                           | AMI示例                                           |
| ----------- | --------------------------------------- | ----------------------------- | ----------------------------------------------- |
| 带 `code` 字段 | 必须引用真实存在的节点编码；不得引用名称；不得留空               | `source_code="急性心肌梗死"`        | `source_code="DIS-CARD-CAD-AMI"`                |
| 带 `id` 字段   | 用于关系或证据片段唯一标识；必须稳定、可重复生成或可追踪            | 每次运行随机生成导致重复关系                | `REL-CARD-8F31A2C9`                             |
| 名称字段        | 医生可读中文标准名优先；英文缩写放 `aliases`             | `AMI诊断明细：肌钙蛋白升高`              | `name="肌钙蛋白升高及动态变化"`                            |
| 别名字段        | 必须是数组；英文缩写、中文简称、旧称都放数组                  | `aliases="AMI,急性心梗"`          | `aliases=["AMI","急性心梗"]`                        |
| 状态字段        | 必须使用固定枚举值；不能自由写自然语言                     | `clinical_review_status="挺好"` | `clinical_review_status="clinical_ready"`       |
| 版本字段        | 必须写 Schema 版本，不写脚本版本                    | `schema_version="脚本V3"`       | `schema_version="V1.15"`                        |
| 时间字段        | 使用 `YYYY-MM-DD HH:mm:ss`；不能只写年月         | `2026-07`                     | `2026-07-11 17:18:30`                           |
| 证据文本字段      | `evidence_text` 必须保存原文摘录；中文翻译可另存，不得覆盖原文 | 只保存改写总结，不保留原文                 | `evidence_text="Primary PCI is recommended..."` |

### 5.4 状态字段怎么理解

状态字段分两类：节点自己的临床使用状态、关系/推荐的审核状态。二者不能混用。

#### 节点字段：`clinical_use_status`

表示“这个实体本身当前能不能用于临床系统”。

| 状态值              | 中文含义  | 什么时候用                      | AMI示例              |
| ---------------- | ----- | -------------------------- | ------------------ |
| `draft`          | 草稿    | 刚抽取出来，还没有完成结构审计和证据核对。      | 新抽取的“AMI预后”节点      |
| `review_ready`   | 待审核可看 | 结构基本完整，可以给临床或产品审核，但不能正式推荐。 | 待临床确认的“AMI随访方案”节点  |
| `clinical_ready` | 可临床使用 | 已通过自动审计，证据链完整，且符合当前上线使用要求。 | 已验收的“急性心肌梗死”疾病节点   |
| `blocked`        | 阻断    | 存在缺证据、语义错误、禁忌冲突、来源不可靠等问题。  | 证据来源不明的“AMI治疗方案”节点 |

#### 关系字段：`review_status`

表示“这条关系的结构和证据链有没有通过自动审计”。

| 状态值       | 中文含义 | 什么时候用                  | AMI示例                      |
| --------- | ---- | ---------------------- | -------------------------- |
| `pending` | 待审   | 新生成关系，还没有跑审计或审计结果未确认。  | 新生成的“AMI -> 需要鉴别 -> 肺栓塞”关系 |
| `passed`  | 通过   | 关系两端存在、关系类型合法、证据链符合要求。 | “AMI -> 有症状 -> 胸痛”关系       |
| `failed`  | 失败   | 关系端点缺失、关系类型错误、证据不匹配等。  | 指向不存在药物编码的 AMI 用药关系        |

#### 关系字段：`clinical_review_status`

表示“这条关系是否允许进入正式 CDSS 临床推荐”。知识浏览关系可以不要求临床审核，推荐类关系必须明确状态。

| 状态值              | 中文含义    | 什么时候用                               | AMI示例                    |
| ---------------- | ------- | ----------------------------------- | ------------------------ |
| `pending`        | 待临床确认   | 结构审计已过，但推荐等级、适用人群、禁忌、用药剂量等还未满足上线要求。 | “推荐某抗栓方案”但剂量/禁忌未补齐       |
| `clinical_ready` | 可临床使用   | 已满足 CDSS 推荐卡片展示要求，可以进入正式推荐链路。       | “STEMI且PCI可及 -> 推荐急诊PCI” |
| `blocked`        | 临床阻断    | 存在冲突、禁忌、证据不足或不适合上线的问题。              | “活动性出血 -> 阻断溶栓治疗”        |
| `not_required`   | 不需要临床审核 | 普通知识浏览关系，例如“疾病有症状”“疾病有病因”，不直接生成推荐。  | “AMI -> 有症状 -> 胸痛”知识浏览关系 |

示例：

```text
“急性心肌梗死 -> 有症状 -> 胸痛”
review_status = passed
clinical_review_status = not_required

“STEMI患者满足急诊PCI条件 -> 正式推荐 -> 急诊PCI”
review_status = passed
clinical_review_status = clinical_ready
```

节点最小示例：

```json
{
  "code": "DIS-CARD-CAD-AMI",
  "entityType": "Disease",
  "name": "急性心肌梗死",
  "aliases": ["AMI", "急性心梗"],
  "source_type": "guideline",
  "batch_id": "BATCH-CARD-CAD-20260623-001",
  "schema_version": "V1.15",
  "clinical_use_status": "clinical_ready"
}
```

关系最小示例：

```json
{
  "id": "REL-CARD-8F31A2C9",
  "source_code": "DIS-CARD-CAD-AMI",
  "relationType": "has_diagnostic_criteria",
  "target_code": "DXC-CARD-AMI-001",
  "batch_id": "BATCH-CARD-CAD-20260623-001",
  "schema_version": "V1.15",
  "review_status": "passed",
  "clinical_review_status": "not_required"
}
```

字段细则见 `schema_docs/Schema字段字典与证据规则.md`。

## 6. 禁止关系与兼容规则

禁止新生成或查询：

```text
USES_MEDICATION
HAS_PROCEDURE
HAS_CLINICAL_MANIFESTATION
HAS_* 大写历史关系
has_differential_diagnosis
```

处理规则：

1. 正式用药推荐使用 `treated_by_medication`、`includes_medication` 或 `recommends_action`。
2. 正式操作/手术推荐使用 `treated_by_procedure`、`includes_procedure` 或 `recommends_action`。
3. 临床表现使用 `has_symptom`、`has_sign` 或 `has_diagnostic_component`。
4. 鉴别诊断使用 `differentiates_from`。
5. 教材章节提及不进入主图谱关系层，保存在 `SourceSection`/`Evidence` 或归档文件中。

## 7. 数据实例硬闸门

入库前必须满足：

1. 所有临床、目录、证据节点必须带 `KGNode` 主标签。
2. `entityType` 必须来自本Schema或明确 legacy 兼容清单。
3. 所有关系必须来自标准关系表或兼容清单。
4. 诊断标准不得只有标题，必须具备 `has_diagnostic_component`，不能补齐时标记为待补，不得伪造。
5. `RecommendationStatement` 必须至少具备动作或阻断、证据、指南。
6. 治疗方案必须有药物、操作、时机、路径或规则下游之一，不得为空壳。
7. 药物类别必须通过 `has_specific_medication` 关联具体药物或明确为知识展示类。
8. 重复语义关系按 `(source.code, relationType, target.code)` 去重。
9. 技术编码不得作为医生界面显示名。
10. 未经临床审核的推荐不得进入正式 CDSS 推荐层。

## 8. Neo4j 导入标准

1. 节点使用 `MERGE (n:KGNode {code})`，再补实体类型标签和属性。
2. 关系使用 `(source.code, relationType, target.code)` 作为语义唯一键。
3. 导入后必须复核：非KGNode、旧关系、重复关系、空壳实体、推荐证据链、诊断标准明细。
4. 外部模型和前端不得直接写 Neo4j；必须生成候选、审计、归档后由正式导入脚本入库。

## 9. 专病CDSS使用链路

```text
患者数据/EMR
  -> 疑似疾病识别
  -> 进入 ClinicalPathway
  -> 定位 PathwayStage
  -> 匹配 ClinicalRule
  -> 输出 RecommendationStatement
  -> recommends_action / blocks_action
  -> derived_from Evidence + based_on_guideline Guideline
```

医生界面只展示当前推荐自己的主证据，不展示疾病级证据池。

## 10. 交付文件

每批次至少交付：

```text
batch_config.yaml
source_documents_manifest.csv
nodes_final.jsonl
relations_final.jsonl
audit_report.json
server_postcheck_summary.json
source_folder_summary.md
```

## 11. 当前禁用与待迁移项

| 项目                           | 状态       | 下一步                                | AMI示例                                    |
| ---------------------------- | -------- | ---------------------------------- | ---------------------------------------- |
| `USES_MEDICATION`            | 已清零      | 禁止再生成                              | 不再生成 `AMI USES_MEDICATION 阿司匹林`          |
| `HAS_PROCEDURE`              | 已清零      | 禁止再生成                              | 不再生成 `AMI HAS_PROCEDURE 急诊PCI`           |
| `HAS_CLINICAL_MANIFESTATION` | 已清零      | 禁止再生成                              | 不再生成 `AMI HAS_CLINICAL_MANIFESTATION 胸痛` |
| `HAS_*` 大写关系                 | 已清零      | 禁止再生成                              | 不再生成任何 `HAS_SYMPTOM` 等大写关系               |
| `has_recommended_action`     | 在用但名称不清晰 | 评估迁移为 `stage_has_available_action` | STEMI再灌注阶段候选动作后续改用新关系名                   |
| `Specialty`                  | 战略保留     | 多学科根节点，禁止低频删除                      | 心血管内科作为 AMI 所属顶层学科保留                     |
