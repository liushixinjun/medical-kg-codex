# Schema字段字典与证据规则

> 从主Schema迁出，保留字段细则、Evidence、Guideline、RecommendationStatement 和 provenance 规则。

## 5. 通用节点字段

字段说明统一采用以下格式：英文技术字段名必须保留，供程序、CSV、JSON、Neo4j 导入使用；中文名称和说明必须同步提供，供临床、数据治理和实施团队阅读。

### 5.1 所有节点必填字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `id` | 技术ID | String | 是 | 全局唯一技术 ID，稳定不复用 |
| `code` | 业务编码 | String | 是 | 全局唯一业务编码，是跨批次合并和 Neo4j MERGE 的主键 |
| `name` | 中文规范名称 | String | 是 | 面向临床展示的标准中文名称 |
| `preferred_name` | 推荐名称 | String | 是 | 推荐展示名称，默认等于 `name` |
| `display_name` | 显示名称 | String | 是 | 前端展示名称，默认等于 `name` |
| `entityType` | 实体类型 | Enum | 是 | 标准实体类型，必须来自 §4 |
| `entityCategory` | 实体大类 | String | 是 | 目录、临床、诊断、治疗、证据等大类 |
| `schema_version` | Schema版本 | String | 是 | 固定记录当前 Schema 版本，例如 `V1.5` |
| `review_status` | 审核状态 | Enum | 是 | `draft` 草稿、`pending_review` 待审、`approved` 已审、`rejected` 驳回、`deprecated` 已废弃 |

### 5.2 通用可选字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `name_en` | 英文名称 | String | 否 | 标准英文名，例如 `hypertrophic cardiomyopathy` |
| `aliases` | 别名列表 | String[] | 否 | 中文别名、英文别名、旧称、俗称、教材用名、指南用名，可多个 |
| `abbr` | 缩写 | String/String[] | 否 | 英文缩写或中文简称，例如 HCM、STEMI、冠心病 |
| `description` | 定义/描述 | String | 否 | 疾病、规则、方案等实体的定义或简要说明；疾病定义优先写入本字段 |
| `skeleton_slot` | 教材骨架槽位 | Enum/String | V1.11新增；教材骨架知识必填 | 标记该节点或知识属于教材章节哪一栏，如 `overview` 疾病概述/定义、`etiology` 病因、`pathogenesis` 发病机制/病理生理、`clinical_manifestation` 临床表现、`exam_lab` 检查检验、`diagnosis_differential` 诊断与鉴别、`classification_risk` 分型/分级/危险分层、`treatment` 治疗、`prognosis_followup_prevention` 预后/随访/预防 |
| `knowledge_layer` | 知识层级 | Enum/String | V1.11新增；来源分层必填 | 标记该知识在 CDSS 中的使用层级：`textbook_core` 教材基础骨架、`guideline_supplement` 指南补充、`guideline_decision` 指南决策推荐、`screening_context` 筛查/背景上下文、`cross_reference` 跨章节引用。前端和规则引擎必须按该字段区分展示和推荐用途 |
| `clinical_review_status` | 临床审核状态 | Enum | V1.5新增；正式CDSS推荐层必填 | `pending_clinical_review` 待临床审核、`clinical_approved` 已临床审核、`not_applicable` 不适用；未经临床审核不得进入正式 CDSS 推荐层 |
| `formal_cdss_ready` | 正式CDSS可用标志 | Boolean | V1.5新增；正式CDSS推荐层必填 | 仅当 required 闭环、推荐证据、适用/排除条件、药物剂量/禁忌/相互作用和临床审核均完成时为 `true` |
| `parentCode` | 父级编码 | String | 目录节点必填 | 目录层级父节点编码，适用于 `DiseaseCategory`、`DiseaseSubcategory` 等 |
| `standard_code` | 外部标准编码 | String | 否 | ICD、ATC、LOINC、SNOMED CT 等外部标准编码 |
| `standard_system` | 外部标准体系 | String | 否 | 外部编码体系名称，例如 ICD-10、ATC、LOINC |
| `confidence` | 置信度 | Number | 否 | 抽取或映射置信度，范围 0–1；人工确认可设为 1 |
| `created_by` | 创建来源 | String | 否 | 创建该实体的工具、人员或流程 |
| `created_time` | 创建时间 | DateTime | 否 | 格式建议 `YYYY-MM-DD HH:mm:ss` |
| `updated_time` | 更新时间 | DateTime | 否 | 格式建议 `YYYY-MM-DD HH:mm:ss` |

### 5.3 批次与范围字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `batch_id` | 批次编号 | String | 是 | 实体或关系首次进入标准数据实例的批次编号 |
| `scope_type` | 执行范围类型 | Enum | 是 | `specialty` 专科、`category` 疾病大类、`disease` 单病种 |
| `scope_target` | 执行范围目标 | String | 是 | 本批次目标专科、疾病大类或病种名称 |
| `merge_status` | 合并状态 | Enum | 是 | `isolated` 批次隔离、`validated` 已验收、`merged` 已合并、`conflict` 有冲突、`rejected` 已拒绝 |
| `source_version` | 来源版本 | String | 否 | 指南、教材或专家资料版本，例如 2025版、第10版 |
| `conflict_status` | 冲突状态 | Enum | 否 | `none` 无冲突、`open` 待裁决、`resolved` 已处置 |

`batch_id` 标记实体首次进入标准数据实例的批次。合并后不得因新来源覆盖原始 provenance。

## 6. 编码标准

### 6.1 code

`code` 是业务唯一键，推荐格式：

```text
{TYPE_PREFIX}-{DOMAIN_PREFIX}-{SEMANTIC_CODE}
```

示例：

```text
SPEC-CARD
CAT-CARD-CM
SUB-CARD-CM-GENERAL
DIS-CARD-CM-HCM
EXAM-ECG
LAB-CARDIAC-BIOMARKER
IND-LVEF
MED-METOPROLOL
CLS-HCM-LVEF-TYPE
```

规则：

- `code` 全局唯一且稳定。
- 不使用纯随机 code、纯中文 code 或文件序号。
- 同一实体不得因来源文件不同生成多个 code。
- `abbr` 不是唯一键。

### 6.2 id

技术 ID 推荐格式：

```text
KG_{TYPE_PREFIX}_{BUSINESS_CODE_NORMALIZED}
```

### 6.3 standard_code

`standard_code` 仅保存 ICD、ATC、LOINC、SNOMED CT 等外部标准编码，不保存项目业务 code。

## 7. 标准关系

### 7.1 relationCategory

| 枚举值 | 中文名称 | 用途说明 |
|---|---|---|
| `structural` | 结构关系 | 专科、疾病大类、亚类、疾病目录之间的层级关系 |
| `clinical` | 临床关系 | 疾病与症状、体征、病因、危险因素、并发症、预后等关系 |
| `diagnostic` | 诊断关系 | 疾病与检查、检验、诊断标准、鉴别诊断、风险分层等关系 |
| `therapeutic` | 治疗关系 | 疾病与治疗方案、药物、操作、适应证、禁忌证等关系 |
| `risk` | 风险关系 | 风险分层、评分、预后风险、患者状态相关关系 |
| `temporal` | 时间关系 | 治疗时机、随访周期、时间窗等关系 |
| `evidence` | 证据关系 | 来源文献、证据片段、推荐陈述和实体/关系之间的证据链 |
| `rule` | 规则关系 | 临床规则、阈值规则、多条件判断规则之间的关系 |

### 7.2 目录关系

| 源实体 source | 关系英文名 relationType | 关系中文名 | 目标实体 target | 方向说明 | 用途说明 |
|---|---|---|---|---|---|
| `Specialty` | `has_category` | 包含疾病大类 | `DiseaseCategory` | 专科 → 疾病大类 | 表达某专科下包含哪些疾病大类，如心血管内科包含冠心病、心肌病、心力衰竭等 |
| `DiseaseCategory` | `has_subcategory` | 包含疾病亚类 | `DiseaseSubcategory` | 疾病大类 → 疾病亚类 | 表达疾病大类下的一级/二级分组 |
| `DiseaseSubcategory` | `has_disease` | 包含疾病 | `Disease` | 疾病亚类 → 疾病 | 表达具体疾病归属到某个亚类 |
| `Disease` | `belongs_to_subcategory` | 属于疾病亚类 | `DiseaseSubcategory` | 疾病 → 疾病亚类 | 反向归属关系，便于从疾病回查其所属亚类 |
| `Disease` | `belongs_to_category` | 属于疾病大类 | `DiseaseCategory` | 疾病 → 疾病大类 | 反向归属关系，便于从疾病回查其所属大类 |

`belongs_to_category` 使用 `classification_role=primary/secondary_view` 区分主分类和次分类视角。

### 7.3 基础医学与临床表现

| 源实体 source | 关系英文名 relationType | 关系中文名 | 目标实体 target | 方向说明 | 用途说明 |
|---|---|---|---|---|---|
| `Disease` | `has_etiology` | 具有病因 | `Etiology` | 疾病 → 病因 | 表达疾病发生原因，如遗传因素、感染、缺血、代谢异常等 |
| `Disease` | `has_definition` | 具有定义 | `Definition` | 疾病 → 定义容器 | 表达某来源或章节下对疾病的定义原文集合；用于保留不同来源定义差异 |
| `Definition` | `has_definition_component` | 定义包含组件 | `DefinitionComponent` | 定义 → 定义组件 | 表达定义中的疾病性质、核心机制、诊断前提、临床意义、流行病学等拆解片段 |
| `Disease` | `has_pathophysiology` | 具有病理生理机制 | `Pathophysiology` | 疾病 → 病理生理 | 表达疾病形成和进展机制，如心室重构、纤维化、心肌缺血等 |
| `Disease` | `has_epidemiology` | 具有流行病学特征 | `Epidemiology` | 疾病 → 流行病学 | 表达患病率、发病率、人群分布、年龄性别特征等 |
| `Disease` | `has_symptom` | 具有症状 | `Symptom` | 疾病 → 症状 | 表达患者主观感受，如胸痛、胸闷、呼吸困难、心悸等 |
| `Disease` | `has_sign` | 具有体征 | `Sign` | 疾病 → 体征 | 表达医生查体或客观观察发现，如水肿、肺部啰音、心脏杂音等 |
| `Disease` | `has_risk_factor` | 具有危险因素 | `RiskFactor` | 疾病 → 危险因素 | 表达增加疾病发生或不良结局概率的因素，如吸烟、高血压、家族史等 |
| `Disease` | `may_cause_complication` | 可导致并发症 | `Complication` | 疾病 → 并发症 | 表达疾病可能引起的并发症或临床后果 |
| `Disease` | `has_prognosis` | 具有预后 | `Prognosis` | 疾病 → 预后 | 表达死亡、复发、进展、再住院、功能恢复等结局信息 |
| `Disease` | `has_prevention` | 具有预防措施 | `Prevention` | 疾病 → 预防 | 表达一级预防、二级预防、生活方式、健康管理、患者教育等 |

### 7.4 检查、检验和诊断

| 源实体 source | 关系英文名 relationType | 关系中文名 | 目标实体 target | 方向说明 | 用途说明 |
|---|---|---|---|---|---|
| `Disease` | `requires_exam` | 需要检查 | `Exam` | 疾病 → 检查 | 表达诊断、评估、随访需要使用的影像、心电、超声、内镜、病理等检查 |
| `Disease` | `requires_lab_test` | 需要检验 | `LabTest` | 疾病 → 检验 | 表达诊断、评估、随访需要使用的实验室检验 |
| `Exam` | `exam_has_indicator` | 检查包含指标 | `ExamIndicator` | 检查 → 检查指标 | 表达某项检查下可观察或测量的指标，如 LVEF、室壁厚度、ST 段改变等 |
| `LabTest` | `lab_test_has_indicator` | 检验包含指标 | `ExamIndicator` | 检验 → 检验指标 | 表达某项检验下的具体指标，如肌钙蛋白、BNP、肌酐、LDL-C 等 |
| `ExamIndicator` | `has_threshold_rule` | 指标具有阈值规则 | `ThresholdRule` | 指标 → 阈值规则 | 表达指标的判断阈值、范围、时间窗和阳性/阴性标准 |
| `Disease` | `has_diagnostic_criteria` | 具有诊断标准 | `DiagnosisCriteria` | 疾病 → 诊断标准 | 表达疾病确诊、疑诊、排除或分型所需满足的诊断条件 |
| `DiagnosisCriteria` | `has_diagnostic_component` | 具有诊断明细组件 | `DiagnosisCriteriaComponent/ClinicalRule/Exam/LabTest/ExamIndicator/Symptom/Sign/ThresholdRule` | 诊断标准 → 诊断明细 | 表达诊断标准下的可推理组成部分，如症状或缺血证据、心电图改变、肌钙蛋白升高/动态变化、影像证据、阈值规则、排除条件等 |
| `Disease` | `differentiates_from` | 需要鉴别 | `Disease/DifferentialDiagnosis` | 疾病 → 鉴别对象 | 表达本病需要与哪些疾病或鉴别诊断条目区分 |
| `Disease/DifferentialDiagnosis` | `has_differential_point` | 具有鉴别要点 | `ClinicalRule/ExamIndicator/Symptom/Sign` | 鉴别对象 → 鉴别要点 | 表达本病与鉴别对象的关键区别，如疼痛性质、心电图、肌钙蛋白、影像征象等 |
| `Disease/DifferentialDiagnosis` | `requires_exclusion_exam` | 需要排除检查 | `Exam/LabTest/ExamIndicator` | 鉴别对象 → 排除检查 | 表达为排除某鉴别诊断应补充的检查、检验或关键指标 |
| `Disease/DifferentialDiagnosis` | `may_block_action` | 可阻断动作 | `Medication/Procedure/TreatmentPlan` | 鉴别对象 → 被阻断动作 | 表达未排除该鉴别诊断前不得执行的高风险动作，如可疑主动脉夹层阻断溶栓 |
| `Disease` | `has_risk_stratification` | 具有风险分层 | `RiskStratification` | 疾病 → 风险分层 | 表达低危、中危、高危等风险分层方案 |
| `Disease` | `uses_scoring_scale` | 使用评分量表 | `ScoringScale` | 疾病 → 评分量表 | 表达疾病评估时使用的评分、量表或风险评分工具 |
| `Disease` | `has_clinical_rule` | 具有临床规则 | `ClinicalRule` | 疾病 → 临床规则 | 表达多条件判断规则，如诊断组合、治疗适应证、排除条件等 |
| `Disease` | `has_classification_stage` | 具有分型/分期 | `ClassificationStage` | 疾病 → 分型/分期 | 表达疾病分型、分期、分级或临床阶段 |
| `Disease` | `has_classification` | 具有疾病分类 | `DiseaseClassification` | 疾病 → 疾病分类 | 表达疾病分型、分类、分级或分期；V1.12 后新批次优先使用 |

> **[V1.1 新增]** `has_classification_stage` 用于连接疾病与其分型/分期方案节点。分型方案内部的具体条件和阈值使用 `ClinicalRule` 或 `ThresholdRule` 在 `ClassificationStage` 节点下挂载。
>
> **[V1.12 新增]** 新批次优先使用 `Disease -> has_classification -> DiseaseClassification`。历史 `has_classification_stage` 保留兼容，不作为新批次首选关系。

> **[V1.8 新增硬规则 — 鉴别诊断不得空壳化]**
> `differentiates_from` 不能只连接一个鉴别疾病名称。每个进入 CDSS 的 `DifferentialDiagnosis` 或鉴别疾病节点，至少必须具备以下三类信息之一组完整结构：鉴别要点（`has_differential_point`）、建议排除检查/检验（`requires_exclusion_exam`）、对治疗动作的阻断或安全影响（`may_block_action`），并必须有 `supported_by_evidence`。若只有“心绞痛、肺栓塞、主动脉夹层、急性心包炎”等名称而无下一级内容，只能作为知识展示，不得作为 CDSS 鉴别推荐。

> `DiagnosisCriteria` 不能只创建“某疾病诊断标准”标题节点。进入 CDSS 的诊断标准必须至少拆解为一组 `has_diagnostic_component` 下级组件，并能回答：依据什么临床表现、检查/检验、指标变化、阈值或排除条件完成疑诊/确诊/分型。若只有标题而无组件，只能作为知识展示，不得作为诊断推理或推荐入口。

### 7.5 治疗与随访

| 源实体 source | 关系英文名 relationType | 关系中文名 | 目标实体 target | 方向说明 | 用途说明 |
|---|---|---|---|---|---|
| `Disease` | `has_treatment_plan` | 具有治疗方案 | `TreatmentPlan` | 疾病 → 治疗方案 | 表达疾病总体治疗策略、路径或分层治疗方案 |
| `Disease` | `treated_by_medication` | 可用药物治疗 | `Medication` | 疾病 → 药物 | 表达疾病可使用的药物或药物类别 |
| `Disease` | `treated_by_procedure` | 可用操作/手术治疗 | `Procedure` | 疾病 → 操作/手术 | 表达疾病可使用的介入、手术、器械或其他操作治疗 |
| `TreatmentPlan` | `includes_medication` | 方案包含药物 | `Medication` | 治疗方案 → 药物 | 表达某治疗方案中包含的药物 |
| `TreatmentPlan` | `includes_procedure` | 方案包含操作/手术 | `Procedure` | 治疗方案 → 操作/手术 | 表达某治疗方案中包含的操作、介入或手术 |
| `Medication/Procedure` | `has_indication` | 具有适应证 | `Indication` | 药物/操作 → 适应证 | 表达药物或操作适用于哪些临床场景 |
| `Medication/Procedure` | `has_contraindication` | 具有禁忌证 | `Contraindication` | 药物/操作 → 禁忌证 | 表达药物或操作不应使用的临床场景 |
| `Medication` | `has_specific_medication` | 具有具体药物 | `Medication` | 药物类别 → 具体药物 | 表达“抗凝药物 → 华法林/肝素/利伐沙班”等类别-实例关系；该关系属于词表/分类关系，不等同于疾病治疗推荐 |
| `TreatmentPlan/Procedure` | `has_timing` | 具有治疗时机 | `TreatmentTiming` | 治疗方案/操作 → 治疗时机 | 表达何时启动、何时转换、何时终止治疗 |
| `TreatmentTiming` | `has_time_window` | 具有时间窗 | `TimeWindow` | 治疗时机 → 时间窗 | 表达治疗或检查的具体时间窗口，如发病后 12 小时内 |
| `Disease/TreatmentPlan` | `has_follow_up` | 具有随访方案 | `FollowUp` | 疾病/治疗方案 → 随访 | 表达随访频率、内容、复查项目和长期管理要求 |
| `Medication` | `interacts_with` | 与药物相互作用 | `Medication/DrugInteraction` | 药物 → 药物/相互作用 | 表达药物之间的相互作用；复杂机制可指向 DrugInteraction 节点 |
| `Medication` | `may_cause_adverse_effect` | 可导致不良反应 | `AdverseEffect` | 药物 → 不良反应 | 表达药物可能产生的不良反应或安全风险 |
| `Disease` | `has_clinical_pathway` | 具有临床路径 | `ClinicalPathway` | 疾病 → 临床路径 | 表达疾病标准化诊疗流程或院内路径 |
| `ClinicalPathway` | `has_pathway_stage` | 包含诊疗阶段 | `PathwayStage` | 临床路径 → 诊疗阶段 | 表达专病诊疗流程由哪些阶段组成 |
| `PathwayStage` | `next_pathway_stage` | 下一诊疗阶段 | `PathwayStage` | 诊疗阶段 → 下一阶段 | 表达路径阶段顺序；允许存在条件分支 |
| `PathwayStage` | `has_stage_rule` | 具有阶段规则 | `ClinicalRule` | 诊疗阶段 → 临床规则 | 表达该阶段进入、退出、推荐或阻断所需规则 |
| `PathwayStage` | `has_recommendation_statement` | 具有推荐陈述 | `RecommendationStatement` | 诊疗阶段 → 推荐陈述 | 表达该阶段可展示的推荐、暂不推荐或阻断陈述；用于前端阶段化展示 |
| `ClinicalRule` | `has_recommendation_statement` | 规则具有推荐陈述 | `RecommendationStatement` | 临床规则 → 推荐陈述 | 表达规则命中后输出的可审核推荐语句，是 CDSS 推荐证据展示的根入口 |
| `PathwayStage` | `has_recommended_action` | 具有推荐动作 | `Exam/LabTest/Medication/Procedure/TreatmentPlan/FollowUp/DifferentialDiagnosis/RiskStratification` | 诊疗阶段 → 推荐对象 | 表达该阶段可能推荐的检查、检验、药物、操作、治疗方案、随访、鉴别诊断或风险分层 |
| `ClinicalRule` | `recommends_action` | 规则推荐动作 | `Exam/LabTest/Medication/Procedure/TreatmentPlan/FollowUp/DifferentialDiagnosis/RiskStratification` | 临床规则 → 推荐对象 | 表达条件满足后应推荐的具体动作 |
| `ClinicalRule` | `blocks_action` | 规则阻断动作 | `Medication/Procedure/TreatmentPlan` | 临床规则 → 被阻断对象 | 表达禁忌证、排除条件或风险过高时不得执行的动作 |
| `RecommendationStatement` | `recommends_action` | 推荐陈述推荐动作 | `Exam/LabTest/Medication/Procedure/TreatmentPlan/FollowUp/DifferentialDiagnosis/RiskStratification` | 推荐陈述 → 推荐对象 | 表达本条推荐陈述对应的具体临床动作；前端推荐卡片以此为准 |
| `RecommendationStatement` | `blocks_action` | 推荐陈述阻断动作 | `Medication/Procedure/TreatmentPlan` | 推荐陈述 → 被阻断对象 | 表达本条陈述阻断或暂不推荐的动作；前端阻断卡片以此为准 |
| `RecommendationStatement` | `has_indication` | 推荐陈述具有适应证 | `Indication/ClinicalRule/PatientState` | 推荐陈述 → 适应证 | 表达这条推荐适用于哪些人群、疾病阶段或临床条件 |
| `RecommendationStatement` | `has_contraindication` | 推荐陈述具有禁忌证 | `Contraindication/ClinicalRule/PatientState` | 推荐陈述 → 禁忌证 | 表达这条推荐在何种情况下禁用、暂缓或需排除 |

> **[V1.1 新增注释 — DrugInteraction 建模规则]**
> `Medication -> interacts_with` 的 target 优先指向另一个 `Medication` 节点（直接药物对，适用于大多数双药相互作用场景）。仅当需要描述三药组合、机制容器或复杂相互作用说明时，才建立独立的 `DrugInteraction` 节点作为 target，并在该节点上挂载涉及药物和机制描述。两种建模方式不得混用于同一相互作用。

> **[V1.5 新增注释 — 药物类别与具体药物建模规则]**
> 药物类别节点（如“抗凝药物”“溶栓药物”“硝酸酯类药物”）的 `aliases` 只能保存同义类别名，不得保存具体药物名、英文缩写或治疗动作词。具体药物必须建立独立 `Medication` 节点，并通过 `has_specific_medication` 从类别节点连接。英文缩写（如 `t-PA`、`rt-PA`）应放入具体药物节点 aliases，而不是药物类别 aliases。

> **[V1.6 新增注释 — 治疗方案可执行性与视图去重规则]**
> `TreatmentPlan` 必须可执行。具体治疗方案（如“溶栓治疗”“抗凝治疗”“抗血小板治疗”“血运重建”）必须至少连接一个下游实体：`includes_medication`、`includes_procedure`、`has_timing`、`has_indication`、`has_contraindication` 或 `has_clinical_pathway`。疾病级总治疗方案（如“急性心肌梗死治疗方案”）不得复制疾病下所有药物或操作；总方案应连接 `has_clinical_pathway`，具体药物和操作应挂在下级具体治疗方案下。前端、审核包和统计报表中的实体数量必须按 `KGNode.code` 或 canonical code 去重；多条关系路径可作为临床路径明细保留，但不得把同一药物、同一检查或同一治疗节点的多条路径统计为多个实体节点。

> **[V1.8 新增注释 — 专病 CDSS 动态推荐规则]**
> `PathwayStage` 和 `ClinicalRule` 用于支撑流程引擎动态推荐。图谱中的推荐动作必须具备医学条件、适用人群、禁忌/排除条件和证据链；流程引擎根据 EMR 事件与患者实时数据判断是否展示。禁止把 `has_recommended_action` 理解为“任何时候都推荐”，它只表示该阶段的候选医学动作，实际触发必须经过规则判断。

> **[V1.10 新增硬规则 — 推荐证据根模型]**
> 进入 CDSS 推荐层的动作必须由 `RecommendationStatement` 承载推荐语义和证据分级。`ClinicalRule -> recommends_action` 可作为兼容关系保留，但前端不得把它作为证据展示根；动作节点直接挂载的大量 `Evidence` 只能用于知识追溯，不得作为当前推荐依据。标准展示路径为：`PathwayStage/ClinicalRule -> has_recommendation_statement -> RecommendationStatement -> recommends_action/blocks_action -> Action`，证据路径为：`RecommendationStatement -> derived_from -> Evidence`。

> **[V1.8 新增硬规则 — 诊疗阶段与治疗方案防混淆]**
> `PathwayStage` 表示“临床流程走到哪一步”，`TreatmentPlan` 表示“这一步具体做什么治疗”。同一疾病或同一 `ClinicalPathway` 范围内，`PathwayStage.name` 不得与 `TreatmentPlan.name` 完全相同。若原文使用同一术语，阶段节点必须补充“阶段/决策/管理/监测/评估”等流程语义后缀，例如“再灌注决策阶段”“抗栓治疗管理阶段”；治疗方案节点保留可执行动作语义，例如“溶栓治疗”“急诊PCI”“双联抗血小板治疗”。导入和审计必须按 `entityType + name + disease_code/pathway_code` 检查阶段-方案重名；发现重名时不得交付 CDSS 推荐层。

### 7.6 患者状态和事件

| 源实体 source | 关系英文名 relationType | 关系中文名 | 目标实体 target | 方向说明 | 用途说明 |
|---|---|---|---|---|---|
| `Disease` | `applies_to_state` | 适用于患者状态 | `PatientState` | 疾病 → 患者状态 | 表达疾病诊疗建议需要区分的特殊人群或状态，如妊娠、肾功能不全、老年、急性期等 |
| `PatientState` | `state_recommends_medication` | 状态推荐药物 | `Medication` | 患者状态 → 药物 | 表达某患者状态下推荐或优先使用的药物 |
| `PatientState` | `state_recommends_procedure` | 状态推荐操作/手术 | `Procedure` | 患者状态 → 操作/手术 | 表达某患者状态下推荐或优先使用的操作、介入或手术 |
| `PatientState` | `state_contraindicates_medication` | 状态禁忌药物 | `Medication` | 患者状态 → 药物 | 表达某患者状态下禁用或不推荐使用的药物 |
| `PatientState` | `state_contraindicates_procedure` | 状态禁忌操作/手术 | `Procedure` | 患者状态 → 操作/手术 | 表达某患者状态下禁用或不推荐使用的操作、介入或手术 |
| `Disease` | `has_clinical_event` | 具有临床事件 | `ClinicalEvent` | 疾病 → 临床事件 | 表达疾病相关事件，如复发、急性发作、再住院、猝死、主要不良心血管事件等 |

> **[V1.1 新增]** `state_contraindicates_medication` 和 `state_contraindicates_procedure` 用于表达特殊患者状态下的禁忌语义（如肾功能不全禁用某药、妊娠禁用某操作）。禁止将此类禁忌语义写成 `state_recommends_*` 正向关系，必须使用专用否定关系或配合 `polarity=negative` 字段（见 §8.3）。

### 7.7 证据关系

本节只定义“节点之间怎么连接”，回答的是：

```text
哪份资料 -> 包含哪条证据
哪个推荐 -> 来自哪条证据
哪个实体/关系 -> 由哪条证据支持
```

本节不规定 Evidence 节点内部保存哪些字段。字段保存规则见 §9.2–§9.5。

| 源实体 source | 关系英文名 relationType | 关系中文名 | 目标实体 target | 方向说明 | 用途说明 |
|---|---|---|---|---|---|
| `Disease` | `based_on_guideline` | 基于指南 | `Guideline` | 疾病 → 指南 | 表达疾病图谱内容来自或参考的指南、共识、教材或路径文件 |
| `Guideline` | `has_source_section` | 具有来源章节 | `SourceSection` | 指南/教材/资料 → 来源章节 | 表达一份来源资料下的章、节、小标题或页码范围 |
| `SourceSection` | `section_has_evidence` | 章节包含证据 | `Evidence` | 来源章节 → 证据 | 表达某章节下抽取出的证据片段 |
| `Guideline` | `guideline_has_evidence` | 指南包含证据 | `Evidence` | 指南 → 证据 | 表达指南、教材或文献中的证据片段 |
| 任意临床实体 | `supported_by_evidence` | 由证据支持 | `Evidence` | 临床实体/关系承载对象 → 证据 | 表达实体、关系或推荐陈述有可追溯证据支撑 |
| `RecommendationStatement` | `based_on_guideline` | 推荐陈述基于指南 | `Guideline` | 推荐陈述 → 指南 | 表达这条推荐陈述来自哪份指南、共识、教材或专家资料 |
| `RecommendationStatement` | `derived_from` | 来源于证据 | `Evidence` | 推荐陈述 → 证据 | 表达具体推荐语句来源于哪一条证据片段 |

> **[V1.10 新增说明 — 证据展示路径]**
> CDSS 推荐卡片只允许展示 `RecommendationStatement` 直连的主证据和扩展证据。疾病级 `based_on_guideline`、动作级 `supported_by_evidence` 和全疾病 Evidence 池只能用于知识追溯，不得作为当前推荐卡片默认依据。
>
> **[V1.12 说明 — §7.7 与 §9.2–§9.5 的区别]** §7.7 是“关系层”，只管证据链连接方向；§9.2 是“Evidence 节点字段层”，规定原文、页码、章节、哈希等怎么存；§9.3 是“教材来源分级规则”，规定教材不能冒充指南推荐等级；§9.4 是“RecommendationStatement 字段层”，规定 CDSS 推荐卡片存哪些字段；§9.5 是“教材骨架锚点规则”，规定教材章节、槽位和知识层级怎么标记。
>
> **[V1.13 硬规则 — 禁止旧弱语义关系]** `USES_MEDICATION`、`HAS_PROCEDURE`、`HAS_CLINICAL_MANIFESTATION` 不再属于正式 Schema 关系。新批次、修复脚本、前端查询和后端接口均不得继续生成或使用这三类关系；正式临床语义必须改写为 `treated_by_medication`、`includes_medication`、`treated_by_procedure`、`includes_procedure`、`has_symptom`、`has_sign` 或 `has_diagnostic_component` 等标准关系。

## 8. 关系通用字段

### 8.1 必填字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `id` | 关系技术ID | String | 是 | 关系记录的唯一技术标识 |
| `source_code` | 源实体编码 | String | 是 | 关系起点实体的业务编码 |
| `relationType` | 关系类型 | Enum | 是 | 必须取 §7 中定义的标准关系英文名 |
| `target_code` | 目标实体编码 | String | 是 | 关系终点实体的业务编码 |
| `relationCategory` | 关系类别 | Enum | 是 | 必须取 §7.1 定义的关系类别，如 clinical、diagnostic、therapeutic |
| `batch_id` | 批次编号 | String | 是 | 生成该关系的数据批次编号 |
| `schema_version` | Schema版本 | String | 是 | 当前新批次使用 `V1.5`；历史批次保留原版本并通过 provenance 追溯 |
| `review_status` | 审核状态 | Enum | 是 | `approved`、`pending_review`、`rejected` 等 |
| `clinical_review_status` | 临床审核状态 | Enum | V1.5新增；正式CDSS推荐关系必填 | `pending_clinical_review`、`clinical_approved`、`not_applicable`；治疗推荐、诊断推荐、路径推荐未经临床审核不得进入正式 CDSS 推荐层 |

### 8.2 核心临床关系证据字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `document_id` | 文档ID | String | 是 | 证据来源文档编码 |
| `segment_id` | 文本片段ID | String | 是 | 证据所在章节、段落、页码或行号片段编码 |
| `source_name` | 来源名称 | String | 是 | 指南、教材、共识或专家资料名称 |
| `source_type` | 来源类型 | Enum | 是 | `guideline`、`consensus`、`authoritative_textbook`、`expert_material`、`curated_web_text` |
| `source_version` | 来源版本 | String | 是 | 指南年份、教材版次或资料版本 |
| `source_section` | 来源章节 | String | 是 | 证据所在章节、标题或小节 |
| `source_section_path` | 来源章节路径 | String | V1.11新增；教材和长文档必填 | 从篇、章、节到小标题的完整路径，例如 `第三篇 循环系统疾病 > 第六章 心肌疾病 > 第一节 肥厚型心肌病 > 诊断与鉴别诊断`；用于防止关键词跨章节误抓 |
| `source_page` | 来源页码 | Integer/String | 是 | PDF 页码；无页码文本可填 `N/A`，但必须有可定位片段 |
| `pdf_page_start` | PDF起始页码 | Integer/String | V1.11新增；PDF来源必填 | 证据片段在 PDF 文件中的起始页码，按 PDF 阅读器页码计，不等同书内印刷页码 |
| `pdf_page_end` | PDF结束页码 | Integer/String | V1.11新增；PDF来源必填 | 证据片段在 PDF 文件中的结束页码；单页证据与 `pdf_page_start` 相同 |
| `book_page_start` | 书内起始页码 | Integer/String | V1.11新增；教材/书籍来源必填 | 教材页面印刷页码；若原文无印刷页码可填 `N/A` |
| `book_page_end` | 书内结束页码 | Integer/String | V1.11新增；教材/书籍来源必填 | 教材页面印刷结束页码；单页证据与 `book_page_start` 相同 |
| `text_anchor` | 文本锚点 | String | V1.11新增；建议必填 | 用于复核的短锚点，可取原文标题、首句或关键短语；不得替代 `evidence_text` |
| `evidence_text` | 原文证据 | String | 是 | 原始文献片段，不得只保存改写文本 |
| `guideline_id` | 指南ID | String | 条件必填 | 来源为指南/共识时填写对应 Guideline 节点编码 |
| `evidence_id` | 证据ID | String | 是 | 对应 Evidence 节点编码 |
| `recommendation_class` | 推荐等级 | Enum/String | 是 | 指南推荐等级；教材或无分级来源填 `N/A` |
| `evidence_level` | 证据等级 | Enum/String | 是 | 指南证据等级；教材或无分级来源填 `N/A` |
| `confidence` | 抽取置信度 | Number | 是 | 0–1，表示抽取或映射可信度 |

`source_page` 对无页码 TXT 可为 `N/A`，但 `source_section`、`source_section_path`、行号/字符区间和 `segment_id` 必须可定位原文。对于 PDF 教材和指南，`source_page` 可继续保留兼容，但质量审计以 `pdf_page_start/pdf_page_end` 和 `source_section_path` 为准。

### 8.3 条件与语义字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `polarity` | 语义极性 | Enum | 否 | `positive` 正向、`negative` 否定/禁忌、`conditional` 条件性 |
| `applicability` | 适用范围 | String | 否 | 关系适用的人群、疾病阶段或临床场景 |
| `patient_state` | 患者状态 | String | 否 | 妊娠、肾功能不全、急性期、老年等状态 |
| `condition_text` | 条件文本 | String | 否 | 原文中的条件说明或触发条件 |
| `dosage` | 剂量 | String | 否 | 药物剂量或治疗强度 |
| `route` | 给药途径 | String | 否 | 口服、静脉、皮下、吸入等 |
| `frequency` | 频次 | String | 否 | 每日一次、每周一次、持续监测等 |
| `duration` | 疗程/持续时间 | String | 否 | 治疗持续时间、观察周期或随访周期 |
| `timing` | 时机 | String | 否 | 启动、转换、终止或复查时机 |
| `classification_role` | 分类角色 | Enum | 否 | `primary` 主分类、`secondary_view` 次分类视角 |
| `skeleton_slot` | 教材骨架槽位 | Enum/String | V1.11新增；教材关系必填 | 与 §5.2 同义，用于关系级标记该关系属于疾病章节的哪一栏；同一节点被多个疾病复用时，以关系上的 `skeleton_slot` 为准 |
| `knowledge_layer` | 知识层级 | Enum/String | V1.11新增；教材/指南关系必填 | 与 §5.2 同义，用于关系级标记该关系是教材基础骨架、指南补充、指南决策、筛查背景还是跨章节引用；CDSS 推荐层不得把 `cross_reference` 或 `screening_context` 当作核心推荐依据 |

否定、禁忌和不推荐语义不得写成正向治疗关系。`polarity=negative` 可用于 `state_recommends_*` 等关系以补充否定语义，但首选使用专用否定关系（`state_contraindicates_*`、`has_contraindication`）。

## 9. Guideline 与 Evidence

### 9.0 白话解释

`Guideline` 和 `Evidence` 是证据链里的两个不同层级，不能混用。

| 名称 | 中文理解 | 回答的问题 | 举例 |
|---|---|---|---|
| `Guideline` | 来源文献/资料本身 | 这条知识来自哪一份指南、共识、教材或专家资料？ | 《2025 ESC 心肌病指南》这一整份文献 |
| `Evidence` | 原文证据片段 | 这条知识在文献里的哪一句、哪一段、哪一页能证明？ | 指南第 35 页中“肥厚型心肌病患者应进行超声心动图评估”的原文片段 |

简单说：

- `Guideline` 是“书/指南/资料这份文件”。
- `Evidence` 是“从这份文件里截出来、能支撑某个节点或关系的原文句子/段落”。
- 一个 `Guideline` 可以包含很多条 `Evidence`。
- 一个疾病、检查、药物、诊断标准或治疗关系，必须能追溯到具体 `Evidence`，不能只说“来自某指南”。

示例：

```text
Guideline：
《中国冠心病诊疗指南 2024》

Evidence：
该指南第 12 页某段原文：急性冠脉综合征患者应尽早进行心电图和肌钙蛋白检测。

图谱关系：
急性冠脉综合征 --requires_exam--> 心电图
急性冠脉综合征 --requires_lab_test--> 肌钙蛋白

证据链：
上述两个关系 --supported_by_evidence--> 该 Evidence
该 Guideline --guideline_has_evidence--> 该 Evidence
```

这样设计的目的：

- 临床团队可以追溯“这条知识从哪里来”。
- 审核人员可以直接查看原文，不依赖抽取模型的总结。
- 多份指南冲突时，可以比较每条 Evidence 的年份、来源、推荐等级和证据等级。

### 9.1 Guideline 字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `document_id` | 文档ID | String | 是 | 文献或资料的唯一编码 |
| `title` | 标题 | String | 是 | 指南、共识、教材或资料标题 |
| `source_type` | 来源类型 | Enum | 是 | 见下方来源类型枚举 |
| `issuing_body` | 发布机构 | String | 否 | 学会、协会、出版社、专家组或机构名称 |
| `publication_year` | 发布年份 | Integer/String | 否 | 发表、发布或出版年份 |
| `version` | 版本 | String | 否 | 指南版本、教材版次或修订版本 |
| `language` | 语言 | String | 是 | `zh-CN`、`en` 等 |
| `sha256` | 文件哈希 | String | 是 | 原始文件内容哈希，用于去重和来源追溯 |

`source_type` 枚举：

| 枚举值 | 中文名称 | 说明 |
|---|---|---|
| `guideline` | 指南 | 正式诊疗指南 |
| `consensus` | 共识 | 专家共识、声明、建议 |
| `authoritative_textbook` | 权威教材/专著 | 教材、专科专著、权威参考书 |
| `expert_material` | 专家资料 | 经确认的专家课件、内部资料、审稿意见 |
| `curated_web_text` | 人工筛选网页文本 | 经人工确认可信的网页资料 |

### 9.2 Evidence 证据片段字段

白话解释：`Evidence` 是“原文证据片段”。医生或审核人员问“这句话从哪里来的”，就应该能从 `Evidence` 找到原文、页码、章节和定位信息。

与 §7.7 的区别：

```text
§7.7：定义 Evidence 和其他节点怎么连。
§9.2：定义 Evidence 节点自己要保存哪些字段。
```

#### 9.2.1 Evidence 必填字段

| 字段英文名 | 中文名称 | 必填 | 说明 |
|---|---|---|---|
| `evidence_id` | 证据ID | 是 | 证据片段唯一编码；用于被推荐、疾病、检查等节点引用 |
| `document_id` | 文档ID | 是 | 证据来自哪份 PDF、DOCX、网页或专家资料 |
| `segment_id` | 片段ID | 是 | 证据在解析文本中的段落、行号或切片编号 |
| `source_name` | 来源名称 | 是 | 例如《中国心房颤动管理指南（2025）》或《内科学（第10版）》 |
| `source_type` | 来源类型 | 是 | `guideline`、`consensus`、`authoritative_textbook`、`expert_material`、`curated_web_text` |
| `source_section` | 来源章节 | 是 | 原文所在章节标题；短标题即可 |
| `source_section_path` | 完整章节路径 | 长文档必填 | 从篇、章、节到小标题的完整路径，用于防止跨章节误抓 |
| `source_page` | 页码 | 是 | PDF 页码；无页码文本填 `N/A`，但必须有 `segment_id` 或行号 |
| `pdf_page_start` / `pdf_page_end` | PDF页码范围 | PDF 必填 | 按 PDF 阅读器页码，不等同书内印刷页码 |
| `book_page_start` / `book_page_end` | 书内页码范围 | 教材建议必填 | 教材印刷页码；没有则填 `N/A` |
| `text_anchor` | 文本锚点 | 建议必填 | 原文首句、标题或关键短语，便于人工快速核对 |
| `evidence_text` | 原文证据 | 是 | 必须保存原文，不得只保存总结、改写或翻译 |
| `language` | 原文语言 | 是 | `zh-CN`、`en` 等 |
| `translation_text` | 中文翻译 | 英文来源必填 | 英文原文不能被中文翻译替代，两者要分别保存 |
| `content_hash` | 内容哈希 | 是 | 用于去重、防篡改和复核 |

#### 9.2.2 Evidence 示例

```json
{
  "entityType": "Evidence",
  "evidence_id": "EV-CARD-AMI-0001",
  "source_name": "ESC 急性冠脉综合征指南（2023）",
  "source_type": "guideline",
  "source_section_path": "ACS > STEMI > Reperfusion therapy",
  "source_page": 42,
  "evidence_text": "原文片段……",
  "content_hash": "sha256:..."
}
```

#### 9.2.3 Evidence 硬规则

1. `evidence_text` 必须是原文，不能只存中文总结。
2. 英文原文和中文翻译必须分字段保存。
3. 目录、版权页、缩写表、参考文献默认不能作为临床证据。
4. 证据节点不得保存本地文件绝对路径，只能保存文档ID、章节、页码、片段ID。
5. 教材、指南、网页都可以生成 Evidence，但 `source_type` 必须准确区分。

### 9.3 教材来源与指南来源的区别

白话解释：教材负责“基础骨架”，指南负责“决策推荐”。教材很权威，但教材中的知识不能自动等同于指南推荐等级。

| 来源类型 | 主要作用 | 能不能直接给 I/A 推荐等级 | CDSS 用途 |
|---|---|---|---|
| 教材/专著 `authoritative_textbook` | 搭疾病基础骨架 | 不能 | 定义、病因、机制、临床表现、基础诊断、治疗原则 |
| 指南 `guideline` | 给规范化推荐 | 可以，按原文 | 推荐陈述、推荐等级、证据等级、时间窗、禁忌证 |
| 共识 `consensus` | 补充专家建议 | 视原文而定 | 专家共识推荐、操作规范、特殊场景 |
| 外部权威网页 `curated_web_text` | 补缺基础知识 | 不能 | 定义、概述、背景补充；不得直接作为正式推荐 |

#### 9.3.1 教材来源固定字段

| 字段英文名 | 中文名称 | 固定值/建议值 | 说明 |
|---|---|---|---|
| `source_type` | 来源类型 | `authoritative_textbook` | 标记来源为权威教材或专著 |
| `source_authority` | 来源权威性 | `authoritative_textbook` | 表示该证据来自基础权威资料 |
| `knowledge_strength` | 知识强度 | `high` | 教材骨架可信度高，但不是指南证据等级 |
| `clinical_applicability` | 临床适用性 | `general` | 用于通用基础医学和临床基础知识 |
| `recommendation_class` | 推荐等级 | `N/A` | 教材来源不得直接写 I、IIa、A、B 等指南分级 |
| `evidence_level` | 证据等级 | `N/A` | 教材来源不得直接写指南证据等级 |
| `knowledge_layer` | 知识层级 | `textbook_core` | V1.12 标准值；历史 `textbook_skeleton` 后续迁移为本值 |

#### 9.3.2 教材转引指南分级的处理规则

教材正文有时会写“指南推荐 I 类 A 级”。处理规则：

1. 如果来源是教材，`source_type` 仍写 `authoritative_textbook`。
2. 教材这条 Evidence 的 `recommendation_class` 和 `evidence_level` 仍写 `N/A`。
3. 教材原文里的“I类A级”可以保留在 `evidence_text`，不能删除。
4. 如果要使用正式推荐等级，必须回到原始指南，另建 `Guideline`、`Evidence` 和 `RecommendationStatement`。

一句话：教材可以告诉我们“这个病是什么、怎么看、原则上怎么治”，但正式 CDSS 推荐要以原始指南/共识推荐为准。

### 9.4 RecommendationStatement 推荐陈述

白话解释：`RecommendationStatement` 是“医生界面推荐卡片的根节点”。医生看到“建议急诊 PCI”时，前端应该从这一类节点拿到推荐内容、推荐动作、禁忌条件、指南来源、页码和原文摘要。

与 `TreatmentPlan` 的区别：

| 实体 | 回答的问题 | 示例 |
|---|---|---|
| `TreatmentPlan` | 做什么治疗 | 溶栓治疗、急诊PCI、抗凝治疗 |
| `RecommendationStatement` | 在什么条件下，为什么推荐/阻断这个动作 | STEMI发病12小时内且PCI可及时完成时推荐急诊PCI |

#### 9.4.1 推荐陈述必填字段

| 字段英文名 | 中文名称 | 必填 | 说明 |
|---|---|---|---|
| `statement_text` | 推荐原文/标准陈述 | 是 | 推荐语句原文或结构化改写；必须能追溯 |
| `statement_summary` | 医生展示摘要 | 是 | 前端卡片展示用短句 |
| `recommendation_type` | 推荐类型 | 是 | `recommend` 推荐、`consider` 可考虑、`do_not_recommend` 不推荐、`block` 阻断 |
| `scope_disease_code` | 适用疾病编码 | 是 | 推荐属于哪个疾病或专病范围 |
| `pathway_code` | 路径编码 | 是 | 所属 `ClinicalPathway`；没有则填 `N/A` |
| `stage_code` | 阶段编码 | 是 | 所属 `PathwayStage`；没有则填 `N/A` |
| `rule_code` | 触发规则编码 | 是 | 对应 `ClinicalRule.code` |
| `action_code` | 动作编码 | 是 | 推荐或阻断的检查、检验、药物、操作、治疗方案等 |
| `required_patient_data` | 需要的患者数据 | 是 | 规则要读取的主诉、诊断、检查、检验、禁忌证等字段 |
| `applicable_population` | 适用人群 | 是 | 适用患者范围、分型、阶段或场景 |
| `indication_conditions` | 适应条件 | 是 | 满足哪些条件才推荐 |
| `contraindication_conditions` | 禁忌/阻断条件 | 是 | 哪些情况不能推荐或需要阻断 |
| `recommendation_class` | 推荐等级 | 是 | I、IIa、IIb、III、未分级推荐、N/A |
| `evidence_level` | 证据等级 | 是 | A、B、C、专家共识、教材证据、N/A |
| `primary_evidence_code` | 主证据编码 | 是 | 默认展示给医生的主 Evidence |
| `primary_guideline_code` | 主来源编码 | 是 | 主 Evidence 对应的 Guideline/教材/共识 |
| `cdss_display_level` | 展示级别 | 是 | `strong_alert`、`recommendation`、`knowledge_display`、`block` |
| `clinical_review_status` | 临床审核状态 | 是 | 测试库可批量签收；正式上线需按临床机制确认 |
| `formal_cdss_ready` | 正式CDSS可用 | 是 | 只有字段、证据、禁忌、审核闭环完整才允许为 true |

#### 9.4.2 推荐卡片标准查询路径

```text
ClinicalRule / PathwayStage
  -> has_recommendation_statement
  -> RecommendationStatement
      -> recommends_action / blocks_action
      -> derived_from Evidence
      -> based_on_guideline Guideline
```

禁止前端为了显示推荐依据，再从 `Disease -> Evidence` 或 `Action -> Evidence` 反推主证据。

#### 9.4.3 推荐陈述示例

```json
{
  "entityType": "RecommendationStatement",
  "statement_summary": "STEMI且PCI可及时完成时，推荐急诊PCI",
  "recommendation_type": "recommend",
  "action_code": "PROC-CARD-PCI",
  "recommendation_class": "I",
  "evidence_level": "A",
  "primary_evidence_code": "EV-CARD-AMI-0001",
  "cdss_display_level": "recommendation",
  "formal_cdss_ready": false
}
```

### 9.5 教材骨架来源与章节锚点

白话解释：教材骨架不是“全文搜索疾病名”。必须先定位到目标疾病章节，再判断这段话属于定义、病因、临床表现、检查、诊断、治疗还是随访预防。

#### 9.5.1 教材骨架实体分工

| 实体 | 用途 | 是否建议新批次使用 |
|---|---|---|
| `SourceSection` | 来源章节锚点，保存章/节/小标题/页码范围 | 是 |
| `Definition` | 某来源下的定义容器 | 是 |
| `DefinitionComponent` | 定义拆解片段 | 是 |
| `DiagnosisCriteriaComponent` | 诊断标准明细组件 | 是 |
| `Prevention` | 预防、二级预防、健康管理 | 是 |
| `TextbookSection` | 历史教材章节实体 | legacy；后续迁移到 `SourceSection` |
| `ClinicalManifestation` | 历史临床表现容器 | 不建议；应拆到 `Symptom`/`Sign` 或 `SourceSection` |

#### 9.5.2 skeleton_slot：这条知识属于教材哪一栏

| skeleton_slot | 中文名称 | 说明 |
|---|---|---|
| `overview` | 疾病概述/定义 | 疾病定义、临床意义、总体描述 |
| `etiology` | 病因 | 导致疾病发生的原因 |
| `pathogenesis` | 发病机制/病理生理 | 机制、病理生理、病理改变、组织学改变 |
| `epidemiology` | 流行病学 | 发病率、患病率、好发人群、死亡风险 |
| `clinical_manifestation` | 临床表现 | 症状、体征、临床特征 |
| `exam_lab` | 检查/检验 | 辅助检查、实验室检查、心电图、影像、指标 |
| `diagnosis_differential` | 诊断与鉴别诊断 | 诊断标准、诊断依据、鉴别对象、排除条件 |
| `classification_risk` | 分型/分级/危险分层 | 疾病分型、分期、分级、风险分层、评分 |
| `treatment` | 治疗 | 治疗原则、治疗目标、药物、操作、器械、手术 |
| `prognosis_followup_prevention` | 预后/随访/预防 | 预后、二级预防、随访、复查、健康管理 |

#### 9.5.3 knowledge_layer：这条知识在 CDSS 中怎么用

| knowledge_layer | 中文名称 | 使用规则 |
|---|---|---|
| `textbook_core` | 教材基础骨架 | 可作为疾病基础知识、基础诊断框架和基础治疗原则 |
| `guideline_supplement` | 指南补充知识 | 可补充教材未覆盖的特殊人群、检查、治疗细节 |
| `guideline_decision` | 指南决策知识 | 可进入 `RecommendationStatement`，作为 CDSS 推荐卡片依据 |
| `screening_context` | 筛查/背景上下文 | 只能用于背景展示或筛查提示，不得直接作为目标疾病核心表现 |
| `cross_reference` | 跨章节引用 | 只能表达“其他章节提到本病”，不得写入目标疾病 definition、核心症状、核心治疗或诊断标准 |

历史兼容：服务器已有 `knowledge_layer=textbook_skeleton`，后续迁移时统一改为 `textbook_core`；`knowledge_layer=evidence` 按来源和用途拆分为 `textbook_core/guideline_supplement/guideline_decision`。

#### 9.5.4 章节锚点硬规则

1. `Disease.definition` 必须来自目标疾病所在章节的定义段或概述段。
2. 教材核心节点和关系必须标记 `skeleton_slot` 与 `knowledge_layer`。
3. `Disease.description` 不得使用其他疾病章节、其他系统章节或跨章节引用段落。
4. 教材关系若来自目标疾病章节外，必须标记为 `knowledge_layer=cross_reference` 或 `screening_context`，不得进入核心骨架槽位。
5. 每条教材核心关系必须同时具备：
   - `source_type=authoritative_textbook`
   - `source_section_path`
   - `skeleton_slot`
   - `knowledge_layer`
   - `pdf_page_start/pdf_page_end`；若无 PDF，则必须有等价文本定位
   - `evidence_text`
6. 禁止用文档级关键词命中替代疾病章节绑定。若目标疾病名称只出现在其他疾病段落的鉴别、病因、并发症或转引中，只能作为跨章节引用，不得写入目标疾病核心字段。

#### 9.5.5 心血管内科教材骨架扩展顺序

心血管内科本轮先以四个大类验证教材骨架方法：

1. 冠心病
2. 心肌病
3. 心力衰竭
4. 心律失常

上述四类不是最终范围，只是优先验证范围。验证通过后，执行团队必须按同一规则自行扩大到《内科学》第10版心血管内科章节中其他疾病大类和疾病，包括但不限于高血压、心脏瓣膜病、心包疾病、感染性心内膜炎、先天性心血管病、主动脉和周围血管病、心血管神经症、肿瘤心脏病学及其他心血管疾病。扩大范围不需要重新设计规则，但必须保留批次登记、来源清单和骨架槽位审计。

## 10. provenance 证据集合

同一语义关系存在多份来源时，只保留一条关系，聚合完整证据集合：

```json
{
  "provenance_records": [
    {
      "document_id": "DOC-...",
      "segment_id": "SEG-...",
      "source_name": "文献名称",
      "source_type": "guideline",
      "source_version": "2025",
      "source_section": "章节名称",
      "source_page": 12,
      "evidence_text": "原文片段",
      "recommendation_class": "I",
      "evidence_level": "A"
    }
  ]
}
```

关系同时维护：

| 字段英文名 | 中文名称 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `evidence_ids` | 证据ID列表 | String[] | 是 | 支持该关系的 Evidence 节点编码列表 |
| `document_ids` | 文档ID列表 | String[] | 是 | 证据来源文档编码列表 |
| `source_names` | 来源名称列表 | String[] | 是 | 指南、教材、共识或专家资料名称 |
| `source_types` | 来源类型列表 | String[] | 是 | `guideline`、`consensus`、`authoritative_textbook`、`expert_material` 等 |
| `evidence_count` | 证据数量 | Integer | 是 | 支持该关系的证据条数，必须等于 provenance 记录数 |
| `provenance_records_json` | 证据溯源集合 | JSON Array | 是 | 完整保存每条证据的文档、章节、页码、原文片段和分级信息 |

数组记录数、`evidence_count` 和 provenance 记录数必须一致。

## 11. 临床规则与阈值

### 11.1 ThresholdRule

必填字段：

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `indicator_code` | 指标编码 | String | 是 | 关联的 `ExamIndicator` 编码，例如 LVEF、LVOT 压差 |
| `operator` | 比较符 | Enum | 是 | `>`、`>=`、`<`、`<=`、`=`、`between` 等 |
| `value` | 阈值 | Number/String | 是 | 结构化阈值数值；区间可用数组或规范字符串 |
| `unit` | 单位 | String | 是 | mmHg、%、ms、ng/L 等 |
| `condition` | 适用条件 | String | 是 | 静息、负荷、激发、特定检查方法等条件 |
| `patient_state` | 患者状态 | String | 是 | 适用疾病、分型、人群或状态 |
| `time_context` | 时间上下文 | String | 是 | 发病后、术后、随访时、入院时等时间条件 |

示例：

```json
{
  "indicator_code": "IND-LVOT-GRADIENT",
  "operator": ">=",
  "value": 30,
  "unit": "mmHg",
  "condition": "静息或激发",
  "patient_state": "肥厚型心肌病"
}
```

### 11.2 ClinicalRule

用于多条件规则，至少保存：

| 字段英文名 | 中文名称 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `rule_type` | 规则类型 | String | 是 | 诊断规则、治疗规则、风险分层规则、禁忌规则等 |
| `if_conditions` | 前提条件 | JSON Array/String[] | 是 | 触发规则所需条件，可包含症状、检查、阈值、患者状态 |
| `then_actions` | 结论/动作 | JSON Array/String[] | 是 | 满足条件后的诊断、治疗、检查、转诊或随访建议 |
| `exceptions` | 例外条件 | JSON Array/String[] | 否 | 不适用或需排除的条件 |
| `applicability` | 适用范围 | String | 是 | 适用病种、分型、人群、场景或路径 |
| `evidence_id` | 证据ID | String | 是 | 支持该规则的 Evidence 编码 |

## 12. 专科/疾病大类配置

每个执行范围生成配置文件，至少包含：

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `scope_type` | 执行范围类型 | Enum | 是 | `specialty` 专科、`category` 疾病大类、`disease` 单病种 |
| `scope_target` | 执行范围目标 | String | 是 | 当前批次要处理的专科、大类或病种名称 |
| `specialty_code` | 专科编码 | String | 是 | 顶层专科节点编码 |
| `category_code` | 疾病大类编码 | String | 视范围而定 | 疾病大类节点编码；专科全量建设时可为空或逐行配置 |
| `disease_code` | 疾病编码 | String | 视范围而定 | 具体疾病节点编码；大类或单病种配置时必填 |
| `pathway_element` | 路径环节 | Enum | 是 | 见 §13.1 标准环节 |
| `applicability_status` | 适用性状态 | Enum | 是 | `required` 必填、`optional` 可选、`not_applicable` 不适用 |
| `reason` | 配置原因 | String | 是 | 说明为什么该环节在本范围内为必填、可选或不适用 |

配置决定闭环验收要求，但不得改变实体和关系的标准定义。

## 13. 诊疗路径闭环

### 13.1 标准环节

| 路径环节英文名 | 中文名称 | 默认适用性 | 说明 |
|---|---|---|---|
| `definition` | 定义 | required | 疾病或核心概念的权威定义 |
| `aliases` | 别名 | required | 中文别名、英文名、缩写、旧称和同义词 |
| `etiology` | 病因 | required | 导致疾病发生的原因 |
| `pathophysiology` | 发病机制/病理生理 | optional | 疾病发生发展的机制；复杂疾病可设为 required |
| `epidemiology` | 流行病学 | optional | 发病率、患病率、人群分布等 |
| `risk_factor` | 危险因素 | required | 增加疾病发生或进展风险的因素 |
| `symptom` | 症状 | required | 患者主观感受 |
| `sign` | 体征 | required | 医师客观发现 |
| `exam` | 检查 | required | 影像、生理、内镜、介入等检查 |
| `lab_test` | 实验室检验 | optional | 检验大项，如肝肾功能、心肌标志物 |
| `exam_indicator` | 检查/检验指标 | optional | 具体指标，如 LVEF、肌钙蛋白、ST 段改变 |
| `threshold_rule` | 阈值规则 | optional | 可计算的诊断、分层或治疗阈值 |
| `diagnosis_criteria` | 诊断标准 | required | 明确诊断依据或标准 |
| `differential_diagnosis` | 鉴别诊断 | required | 需要鉴别或排除的疾病/状态 |
| `classification_stage` | 分型/分期/分级 | optional | V1.1 新增；遗传病、肿瘤、心衰分型等可配置为 required |
| `risk_stratification` | 风险分层 | optional | 风险分层方案或风险等级 |
| `scoring_scale` | 评分量表 | optional | GRACE、TIMI、CHA2DS2-VASc 等评分 |
| `treatment_plan` | 治疗方案 | required | 治疗策略、治疗路径或治疗原则 |
| `medication` | 药物 | optional | 药物类别或具体药品 |
| `procedure` | 操作/手术/介入 | optional | PCI、CABG、消融、手术等 |
| `indication` | 适应证 | optional | 药物或操作适用条件 |
| `contraindication` | 禁忌证 | optional | 药物或操作禁用条件 |
| `complication` | 并发症 | required | 疾病可导致的并发症 |
| `prognosis` | 预后 | required | 结局、死亡风险、复发风险等 |
| `follow_up` | 随访 | required | 复查项目、频率、随访周期 |
| `clinical_pathway` | 诊疗路径 | optional | V1.1 新增；综合性路径容器，路径复杂时配置为 required |
| `guideline` | 指南/来源 | required | 支撑该疾病图谱的指南、教材、共识、专家资料 |
| `evidence` | 证据 | required | 可定位原文证据片段 |

> **[V1.1 说明 — classification_stage]** 此环节对应 `ClassificationStage` 实体及 `has_classification_stage` 关系。闭环审计时检查该疾病是否存在已建立的分型/分期节点。对于无标准分型的疾病，配置为 `not_applicable`。
>
> **[V1.1 说明 — clinical_pathway]** `ClinicalPathway` 作为综合性容器实体参与路径闭环审计，标注为 `optional`。对于具有明确诊疗流程图或标准路径的疾病（如 AMI/STEMI），可在专科配置层将此环节设为 `required`。

### 13.2 审计字段

```text
disease_code
pathway_element
applicability_status
coverage_status       covered | missing | not_applicable
evidence_count
source_names
missing_reason
solution
```

### 13.3 完整判定

只有所有 `required` 环节均为 `covered` 时，才能标记：

```text
closed_loop_ready=yes
closed_loop_basis=element_coverage_not_quantity_threshold
```

证据数量不能弥补必需环节缺失。

> **[V1.1 新增 — schema_gap 的闭环影响]** 若某必需路径环节的缺失原因登记为 `SCHEMA_UNSUPPORTED`（即写入了 `schema_gap_register.csv`），该环节不得标记为 `covered`，闭环状态不得标记为 `yes`，直至 Schema 修订并通过重新验收。`schema_gap` 登记本身不构成通过质量闸门的依据。

## 14. 批次与合并契约

### 14.1 批次字段

```text
batch_id
scope_type
scope_target
created_time
source_manifest_hash
schema_version
quality_gate_status
merge_status
```

### 14.2 节点合并

匹配顺序：

1. 相同全局 `code`。
2. 相同 `entityType` ＋ 规范名称。
3. 受控别名或外部标准编码确认同一实体。

无法确认时进入冲突队列，不自动合并。

### 14.3 关系合并

关系语义键：

```text
(source.code, relationType, target.code)
```

相同语义关系聚合 provenance，不建立平行重复边。

### 14.4 冲突与回滚

- 属性冲突使用 `conflict_status=open` 并写入冲突台账。
- 合并前创建标准主图谱快照。
- 合并验证失败时恢复快照。
- 每个批次保留独立、不可变的数据实例包。

## 15. 禁止关系与错误建模

禁止：

- 关系方向与标准相反。
- 使用自然语言短语作为 `relationType`。
- 使用 `entityType=DiseaseSubtype`（本 Schema 已无此类型）。
- 把 `DiseaseCategory` 复制为同名 `Disease`。
- 把并发症语义误建成独立疾病副本。
- 把药物类别和具体药品混为同一节点。
- 把教材权威性写成指南 I/A 分级。
- 把教材转引的分级文字直接填入 `recommendation_class` 字段。
- 把本机路径写入节点或关系。
- 用文档级关键词命中替代疾病章节绑定。
- 缺少原文证据仍创建核心临床关系。
- 把患者状态禁忌语义写成 `state_recommends_*` 正向关系。
- 对同一药物相互作用混用直接药物对建模和 DrugInteraction 节点建模。

## 16. 数据实例硬闸门

正式数据实例必须满足：

- 未知 `entityType` 数量为 0（包含已废弃的 `DiseaseSubtype`）。
- 未知 `relationType` 数量为 0。
- 错误关系方向数量为 0。
- 重复 `code` 数量为 0。
- 同类型同名重复实体数量为 0。
- 悬空关系数量为 0。
- 重复语义关系数量为 0。
- 本机路径污染数量为 0。
- Unicode 替换字符和典型错码数量为 0。
- 核心临床关系证据链完整率为 100%。
- 关系目标名称/别名在证据分段命中率为 100%。
- Definition 与目标疾病相关性命中率为 100%。
- 跨疾病来源污染数量为 0。
- `disease_definition_empty_count=0`：scope 内所有正式疾病必须有 `definition`。
- `disease_definition_source_mismatch_count=0`：疾病定义必须来自目标疾病章节定义/概述段，不得来自其他疾病、其他章节或跨章节引用。
- `description_cross_chapter_pollution_count=0`：`Disease.description` 不得命中其他疾病章节、其他系统章节、鉴别引用段或并发症引用段。
- `textbook_core_without_skeleton_slot_count=0`：`source_type=authoritative_textbook` 且用于教材核心骨架的节点/关系必须有 `skeleton_slot`。
- `textbook_core_without_knowledge_layer_count=0`：教材核心关系必须有 `knowledge_layer=textbook_core`；筛查背景和跨章节引用不得伪装为核心骨架。
- `textbook_source_anchor_missing_count=0`：教材核心证据必须有 `source_section_path` 和可定位页码/文本锚点。
- 教材伪装正式指南分级数量为 0（`source_type=authoritative_textbook` 记录中 `recommendation_class ≠ N/A` 的数量为 0）。
- 必需环节缺口均有原因和解决方案。
- **[V1.1 新增]** `schema_gap_register.csv` 中存在未解决条目且涉及 `required` 路径环节的批次，`quality_gate_status` 不得标记为 `passed`。
- **[V1.1 新增]** 患者状态否定语义（禁忌）使用 `state_contraindicates_*` 或 `has_contraindication` 表达，`state_recommends_*` 关系中 `polarity=negative` 的记录数为 0（此写法已废弃）。
- **[V1.5 新增]** 疾病不得直接连接“鉴别诊断”“诊断标准”“药物治疗”“一般治疗”“预后良好/不良”“定期随访”“危险分层”等通用语义空壳节点；必须抽取具体对象或具体规则。
- **[V1.5 新增]** 药物类别 aliases 不得包含具体药物、英文缩写或治疗动作词；具体药物必须独立建 `Medication` 节点，并通过 `has_specific_medication` 连接。
- **[V1.5 新增]** 正式 CDSS 推荐层硬门槛：scope 内所有疾病 required 缺口为 0；治疗推荐至少覆盖 ClinicalRule/Indication/Contraindication/ClinicalPathway；所有推荐必须有适用人群、排除条件、证据来源、推荐等级和 `clinical_review_status=clinical_approved`；药物必须有标准名、别名、剂量、禁忌证、相互作用字段。未临床审核的节点和关系可进入测试图谱，但不得进入正式 CDSS 推荐层。
- **[V1.6 新增]** 结构可用性硬闸门：`technical_display_name_error_count=0`、`treatment_plan_actionability_error_count=0`、`medication_class_without_specific_count=0`、`duplicate_semantic_relation_count=0`。截图、前端或审核统计中出现“同一疾病下同一药物/检查/治疗节点重复计数”，必须判定为视图去重或关系语义键去重失败，先修复再交付。

## 17. Neo4j 导入标准

数据实例验收通过并获得用户确认后才允许导入。

节点写入：

```cypher
MERGE (n:KGNode:`实体类型` {code: $code})
SET n += $properties,
    n.primary_label = 'KGNode',
    n.type_label = $entityType,
    n.canonical_labels = ['KGNode', $entityType]
```

规则：

- `code` 建立唯一约束。
- 目录、临床和证据节点必须带 `KGNode` 主标签，可增加辅助类型标签，但 `entityType` 只有一个标准值。
- 禁止创建只带 `Disease`、`TreatmentPlan`、`DiagnosisCriteria` 等类型标签而不带 `KGNode` 的节点；此类节点不属于标准图谱，可绕过质量审计，必须阻断交付。
- 关系按语义键去重后创建。
- 多批次合并后必须在服务器执行关系语义键去重；同一 `(source.code, relationType, target.code)` 只允许保留一条关系，来源差异应合并到 provenance 或审计字段，不得生成重复边。
- 前端图谱接口必须按节点 `code` 去重构造节点集合；关系集合可保留多条路径，但实体数量、维度节点数量和截图统计必须使用唯一节点数。
- 导入前备份，导入后执行全库质量审计。必须满足 `all_node_count == kg_node_count`、`all_relation_count == kg_relation_count`、`non_kgnode_node_count=0`、`relation_touching_non_kgnode_count=0`。
- 禁止用完整属性集合 `MERGE` 节点。

## 18. 标准交付文件

每个批次至少交付：

```text
scope_taxonomy.csv
source_documents_manifest.csv
dedup_index.csv                    [V1.1 新增]
source_folder_summary.csv          [V1.1 新增]
page_audit.jsonl
document_quality_audit.csv
segment_index.jsonl
textbook_skeleton_matrix.csv        [V1.11 新增，教材骨架槽位覆盖矩阵]
textbook_chapter_anchor_audit.csv   [V1.11 新增，教材章节锚点与污染审计]
nodes_final.jsonl
nodes_final.csv
relations_final.jsonl
relations_final.csv
graph_final.json
disease_pathway_coverage.csv
missing_reason_and_solution.csv
source_conflict_register.csv       [V1.1 补入主清单]
schema_gap_register.csv
quality_gate_summary.json
专家审核说明.md
```

正式节点和关系不得包含本地路径；本地路径只允许存在于执行清单和审计日志。

## 19. 专病 CDSS 动态流程引擎映射

### 19.1 白话解释

专科知识图谱不是让前端或 Oracle 一次性把某个疾病下所有检查、检验、药物、手术、鉴别诊断全部圈出来。图谱应作为医学规则来源，供专病流程引擎按患者当前状态实时调用。

标准调用链：

```text
EMR/业务系统事件
  -> 流程引擎读取患者当前数据
  -> 流程引擎查询图谱中的 ClinicalPathway / PathwayStage / ClinicalRule
  -> 计算当前阶段、已满足条件、缺失条件、阻断原因
  -> 返回当前可执行推荐、暂不推荐项目和证据链
  -> 前端展示给医生并记录医生反馈
```

### 19.2 图谱维护什么

图谱必须维护以下医学知识：

| 内容 | 推荐实体/字段 | 示例 |
|---|---|---|
| 专病路径 | `ClinicalPathway` | 急性心肌梗死诊疗路径 |
| 诊疗阶段 | `PathwayStage` | 疑诊评估、诊断确认、再灌注决策、抗栓治疗、二级预防 |
| 阶段顺序 | `next_pathway_stage` | 诊断确认 → 再灌注决策 |
| 阶段规则 | `ClinicalRule` | STEMI 溶栓适应证规则 |
| 条件文本 | `if_conditions`、`condition_text` | STEMI、发病≤12小时、PCI不可及时、无溶栓禁忌证 |
| 推荐陈述 | `RecommendationStatement` | “STEMI且发病≤12小时，优先评估急诊PCI可及性” |
| 推荐动作 | `RecommendationStatement -> recommends_action` | 急诊PCI、溶栓治疗、肌钙蛋白检测 |
| 阻断动作 | `RecommendationStatement -> blocks_action` | 可疑主动脉夹层阻断溶栓 |
| 证据链 | `RecommendationStatement -> derived_from` | 指南、页码、推荐等级、证据等级 |

### 19.3 流程引擎维护什么

以下内容不属于医学知识图谱主体，不应作为标准图谱关系硬编码：

| 内容 | 所属层 | 示例 |
|---|---|---|
| EMR字段映射 | 流程引擎/集成层 | 主诉字段、主诊断字段、心电图报告字段、检验结果字段 |
| 系统事件 | 流程引擎 | 主诊断保存、检验回报、医嘱提交、过敏史更新 |
| 当前患者阶段 | 流程引擎运行态 | 当前处于“再灌注决策阶段” |
| 是否弹窗/提醒/置顶 | 前端/流程引擎 | 高危提醒、静默提示、知识展示 |
| 医生反馈 | 业务系统 | 采纳、忽略、暂不处理、原因 |

### 19.4 AMI 示例

图谱表达：

```text
Disease: ST段抬高型心肌梗死
  has_clinical_pathway -> ClinicalPathway: STEMI诊疗路径
ClinicalPathway
  has_pathway_stage -> PathwayStage: 再灌注决策阶段
PathwayStage
  has_stage_rule -> ClinicalRule: STEMI再灌注策略选择规则
ClinicalRule
  if_conditions:
    - 确诊或高度疑似STEMI
    - 发病时间≤12小时
    - 评估PCI可及性
    - 排除溶栓禁忌证
  has_recommendation_statement -> RecommendationStatement: STEMI急诊PCI推荐陈述
RecommendationStatement
  statement_summary: STEMI且发病≤12小时，优先评估急诊PCI可及性
  recommendation_class: I
  evidence_level: A
  recommends_action -> Procedure: 急诊PCI
  based_on_guideline -> Guideline: STEMI ESC 2017
  derived_from -> Evidence: STEMI ESC 2017 第48页
```

流程引擎执行：

```text
事件：心电图结果返回 / 主诊断保存 / 发病时间录入
读取：主诊断、发病时间、心电图、肌钙蛋白、禁忌证、PCI可及性
判断：当前是否满足再灌注决策阶段条件
输出：
  - 当前阶段：再灌注决策
  - 已满足：STEMI、发病≤12小时
  - 缺失：PCI预计时间、溶栓禁忌证评估
  - 推荐：补充PCI可及性和禁忌证评估
  - 暂不推荐：直接溶栓
  - 原因：主动脉夹层/出血风险未排除
  - 证据：直接读取 RecommendationStatement 的指南、页码、推荐等级、证据等级
```

### 19.5 CDSS 应用硬规则

- CDSS 推荐不得等同于“疾病下所有关联节点”。
- 进入 CDSS 推荐层的动作必须通过 `PathwayStage + ClinicalRule + Evidence` 组合表达。
- 推荐动作必须区分：立即推荐、条件满足后推荐、缺资料暂缓、禁忌阻断、仅知识展示。
- 前端必须展示推荐原因、缺失条件、禁忌/排除条件和证据来源。
- 如果只查到诊断标准、治疗方案或药物标题，缺少条件、动作明细和证据链，不得作为可执行 CDSS 推荐。

## 8. 关系通用字段

### 8.1 必填字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `id` | 关系技术ID | String | 是 | 关系记录的唯一技术标识 |
| `source_code` | 源实体编码 | String | 是 | 关系起点实体的业务编码 |
| `relationType` | 关系类型 | Enum | 是 | 必须取 §7 中定义的标准关系英文名 |
| `target_code` | 目标实体编码 | String | 是 | 关系终点实体的业务编码 |
| `relationCategory` | 关系类别 | Enum | 是 | 必须取 §7.1 定义的关系类别，如 clinical、diagnostic、therapeutic |
| `batch_id` | 批次编号 | String | 是 | 生成该关系的数据批次编号 |
| `schema_version` | Schema版本 | String | 是 | 当前新批次使用 `V1.5`；历史批次保留原版本并通过 provenance 追溯 |
| `review_status` | 审核状态 | Enum | 是 | `approved`、`pending_review`、`rejected` 等 |
| `clinical_review_status` | 临床审核状态 | Enum | V1.5新增；正式CDSS推荐关系必填 | `pending_clinical_review`、`clinical_approved`、`not_applicable`；治疗推荐、诊断推荐、路径推荐未经临床审核不得进入正式 CDSS 推荐层 |

### 8.2 核心临床关系证据字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `document_id` | 文档ID | String | 是 | 证据来源文档编码 |
| `segment_id` | 文本片段ID | String | 是 | 证据所在章节、段落、页码或行号片段编码 |
| `source_name` | 来源名称 | String | 是 | 指南、教材、共识或专家资料名称 |
| `source_type` | 来源类型 | Enum | 是 | `guideline`、`consensus`、`authoritative_textbook`、`expert_material`、`curated_web_text` |
| `source_version` | 来源版本 | String | 是 | 指南年份、教材版次或资料版本 |
| `source_section` | 来源章节 | String | 是 | 证据所在章节、标题或小节 |
| `source_section_path` | 来源章节路径 | String | V1.11新增；教材和长文档必填 | 从篇、章、节到小标题的完整路径，例如 `第三篇 循环系统疾病 > 第六章 心肌疾病 > 第一节 肥厚型心肌病 > 诊断与鉴别诊断`；用于防止关键词跨章节误抓 |
| `source_page` | 来源页码 | Integer/String | 是 | PDF 页码；无页码文本可填 `N/A`，但必须有可定位片段 |
| `pdf_page_start` | PDF起始页码 | Integer/String | V1.11新增；PDF来源必填 | 证据片段在 PDF 文件中的起始页码，按 PDF 阅读器页码计，不等同书内印刷页码 |
| `pdf_page_end` | PDF结束页码 | Integer/String | V1.11新增；PDF来源必填 | 证据片段在 PDF 文件中的结束页码；单页证据与 `pdf_page_start` 相同 |
| `book_page_start` | 书内起始页码 | Integer/String | V1.11新增；教材/书籍来源必填 | 教材页面印刷页码；若原文无印刷页码可填 `N/A` |
| `book_page_end` | 书内结束页码 | Integer/String | V1.11新增；教材/书籍来源必填 | 教材页面印刷结束页码；单页证据与 `book_page_start` 相同 |
| `text_anchor` | 文本锚点 | String | V1.11新增；建议必填 | 用于复核的短锚点，可取原文标题、首句或关键短语；不得替代 `evidence_text` |
| `evidence_text` | 原文证据 | String | 是 | 原始文献片段，不得只保存改写文本 |
| `guideline_id` | 指南ID | String | 条件必填 | 来源为指南/共识时填写对应 Guideline 节点编码 |
| `evidence_id` | 证据ID | String | 是 | 对应 Evidence 节点编码 |
| `recommendation_class` | 推荐等级 | Enum/String | 是 | 指南推荐等级；教材或无分级来源填 `N/A` |
| `evidence_level` | 证据等级 | Enum/String | 是 | 指南证据等级；教材或无分级来源填 `N/A` |
| `confidence` | 抽取置信度 | Number | 是 | 0–1，表示抽取或映射可信度 |

`source_page` 对无页码 TXT 可为 `N/A`，但 `source_section`、`source_section_path`、行号/字符区间和 `segment_id` 必须可定位原文。对于 PDF 教材和指南，`source_page` 可继续保留兼容，但质量审计以 `pdf_page_start/pdf_page_end` 和 `source_section_path` 为准。

### 8.3 条件与语义字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `polarity` | 语义极性 | Enum | 否 | `positive` 正向、`negative` 否定/禁忌、`conditional` 条件性 |
| `applicability` | 适用范围 | String | 否 | 关系适用的人群、疾病阶段或临床场景 |
| `patient_state` | 患者状态 | String | 否 | 妊娠、肾功能不全、急性期、老年等状态 |
| `condition_text` | 条件文本 | String | 否 | 原文中的条件说明或触发条件 |
| `dosage` | 剂量 | String | 否 | 药物剂量或治疗强度 |
| `route` | 给药途径 | String | 否 | 口服、静脉、皮下、吸入等 |
| `frequency` | 频次 | String | 否 | 每日一次、每周一次、持续监测等 |
| `duration` | 疗程/持续时间 | String | 否 | 治疗持续时间、观察周期或随访周期 |
| `timing` | 时机 | String | 否 | 启动、转换、终止或复查时机 |
| `classification_role` | 分类角色 | Enum | 否 | `primary` 主分类、`secondary_view` 次分类视角 |
| `skeleton_slot` | 教材骨架槽位 | Enum/String | V1.11新增；教材关系必填 | 与 §5.2 同义，用于关系级标记该关系属于疾病章节的哪一栏；同一节点被多个疾病复用时，以关系上的 `skeleton_slot` 为准 |
| `knowledge_layer` | 知识层级 | Enum/String | V1.11新增；教材/指南关系必填 | 与 §5.2 同义，用于关系级标记该关系是教材基础骨架、指南补充、指南决策、筛查背景还是跨章节引用；CDSS 推荐层不得把 `cross_reference` 或 `screening_context` 当作核心推荐依据 |

否定、禁忌和不推荐语义不得写成正向治疗关系。`polarity=negative` 可用于 `state_recommends_*` 等关系以补充否定语义，但首选使用专用否定关系（`state_contraindicates_*`、`has_contraindication`）。

## 9. Guideline 与 Evidence

### 9.0 白话解释

`Guideline` 和 `Evidence` 是证据链里的两个不同层级，不能混用。

| 名称 | 中文理解 | 回答的问题 | 举例 |
|---|---|---|---|
| `Guideline` | 来源文献/资料本身 | 这条知识来自哪一份指南、共识、教材或专家资料？ | 《2025 ESC 心肌病指南》这一整份文献 |
| `Evidence` | 原文证据片段 | 这条知识在文献里的哪一句、哪一段、哪一页能证明？ | 指南第 35 页中“肥厚型心肌病患者应进行超声心动图评估”的原文片段 |

简单说：

- `Guideline` 是“书/指南/资料这份文件”。
- `Evidence` 是“从这份文件里截出来、能支撑某个节点或关系的原文句子/段落”。
- 一个 `Guideline` 可以包含很多条 `Evidence`。
- 一个疾病、检查、药物、诊断标准或治疗关系，必须能追溯到具体 `Evidence`，不能只说“来自某指南”。

示例：

```text
Guideline：
《中国冠心病诊疗指南 2024》

Evidence：
该指南第 12 页某段原文：急性冠脉综合征患者应尽早进行心电图和肌钙蛋白检测。

图谱关系：
急性冠脉综合征 --requires_exam--> 心电图
急性冠脉综合征 --requires_lab_test--> 肌钙蛋白

证据链：
上述两个关系 --supported_by_evidence--> 该 Evidence
该 Guideline --guideline_has_evidence--> 该 Evidence
```

这样设计的目的：

- 临床团队可以追溯“这条知识从哪里来”。
- 审核人员可以直接查看原文，不依赖抽取模型的总结。
- 多份指南冲突时，可以比较每条 Evidence 的年份、来源、推荐等级和证据等级。

### 9.1 Guideline 字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `document_id` | 文档ID | String | 是 | 文献或资料的唯一编码 |
| `title` | 标题 | String | 是 | 指南、共识、教材或资料标题 |
| `source_type` | 来源类型 | Enum | 是 | 见下方来源类型枚举 |
| `issuing_body` | 发布机构 | String | 否 | 学会、协会、出版社、专家组或机构名称 |
| `publication_year` | 发布年份 | Integer/String | 否 | 发表、发布或出版年份 |
| `version` | 版本 | String | 否 | 指南版本、教材版次或修订版本 |
| `language` | 语言 | String | 是 | `zh-CN`、`en` 等 |
| `sha256` | 文件哈希 | String | 是 | 原始文件内容哈希，用于去重和来源追溯 |

`source_type` 枚举：

| 枚举值 | 中文名称 | 说明 |
|---|---|---|
| `guideline` | 指南 | 正式诊疗指南 |
| `consensus` | 共识 | 专家共识、声明、建议 |
| `authoritative_textbook` | 权威教材/专著 | 教材、专科专著、权威参考书 |
| `expert_material` | 专家资料 | 经确认的专家课件、内部资料、审稿意见 |
| `curated_web_text` | 人工筛选网页文本 | 经人工确认可信的网页资料 |

### 9.2 Evidence 证据片段字段

白话解释：`Evidence` 是“原文证据片段”。医生或审核人员问“这句话从哪里来的”，就应该能从 `Evidence` 找到原文、页码、章节和定位信息。

与 §7.7 的区别：

```text
§7.7：定义 Evidence 和其他节点怎么连。
§9.2：定义 Evidence 节点自己要保存哪些字段。
```

#### 9.2.1 Evidence 必填字段

| 字段英文名 | 中文名称 | 必填 | 说明 |
|---|---|---|---|
| `evidence_id` | 证据ID | 是 | 证据片段唯一编码；用于被推荐、疾病、检查等节点引用 |
| `document_id` | 文档ID | 是 | 证据来自哪份 PDF、DOCX、网页或专家资料 |
| `segment_id` | 片段ID | 是 | 证据在解析文本中的段落、行号或切片编号 |
| `source_name` | 来源名称 | 是 | 例如《中国心房颤动管理指南（2025）》或《内科学（第10版）》 |
| `source_type` | 来源类型 | 是 | `guideline`、`consensus`、`authoritative_textbook`、`expert_material`、`curated_web_text` |
| `source_section` | 来源章节 | 是 | 原文所在章节标题；短标题即可 |
| `source_section_path` | 完整章节路径 | 长文档必填 | 从篇、章、节到小标题的完整路径，用于防止跨章节误抓 |
| `source_page` | 页码 | 是 | PDF 页码；无页码文本填 `N/A`，但必须有 `segment_id` 或行号 |
| `pdf_page_start` / `pdf_page_end` | PDF页码范围 | PDF 必填 | 按 PDF 阅读器页码，不等同书内印刷页码 |
| `book_page_start` / `book_page_end` | 书内页码范围 | 教材建议必填 | 教材印刷页码；没有则填 `N/A` |
| `text_anchor` | 文本锚点 | 建议必填 | 原文首句、标题或关键短语，便于人工快速核对 |
| `evidence_text` | 原文证据 | 是 | 必须保存原文，不得只保存总结、改写或翻译 |
| `language` | 原文语言 | 是 | `zh-CN`、`en` 等 |
| `translation_text` | 中文翻译 | 英文来源必填 | 英文原文不能被中文翻译替代，两者要分别保存 |
| `content_hash` | 内容哈希 | 是 | 用于去重、防篡改和复核 |

#### 9.2.2 Evidence 示例

```json
{
  "entityType": "Evidence",
  "evidence_id": "EV-CARD-AMI-0001",
  "source_name": "ESC 急性冠脉综合征指南（2023）",
  "source_type": "guideline",
  "source_section_path": "ACS > STEMI > Reperfusion therapy",
  "source_page": 42,
  "evidence_text": "原文片段……",
  "content_hash": "sha256:..."
}
```

#### 9.2.3 Evidence 硬规则

1. `evidence_text` 必须是原文，不能只存中文总结。
2. 英文原文和中文翻译必须分字段保存。
3. 目录、版权页、缩写表、参考文献默认不能作为临床证据。
4. 证据节点不得保存本地文件绝对路径，只能保存文档ID、章节、页码、片段ID。
5. 教材、指南、网页都可以生成 Evidence，但 `source_type` 必须准确区分。

### 9.3 教材来源与指南来源的区别

白话解释：教材负责“基础骨架”，指南负责“决策推荐”。教材很权威，但教材中的知识不能自动等同于指南推荐等级。

| 来源类型 | 主要作用 | 能不能直接给 I/A 推荐等级 | CDSS 用途 |
|---|---|---|---|
| 教材/专著 `authoritative_textbook` | 搭疾病基础骨架 | 不能 | 定义、病因、机制、临床表现、基础诊断、治疗原则 |
| 指南 `guideline` | 给规范化推荐 | 可以，按原文 | 推荐陈述、推荐等级、证据等级、时间窗、禁忌证 |
| 共识 `consensus` | 补充专家建议 | 视原文而定 | 专家共识推荐、操作规范、特殊场景 |
| 外部权威网页 `curated_web_text` | 补缺基础知识 | 不能 | 定义、概述、背景补充；不得直接作为正式推荐 |

#### 9.3.1 教材来源固定字段

| 字段英文名 | 中文名称 | 固定值/建议值 | 说明 |
|---|---|---|---|
| `source_type` | 来源类型 | `authoritative_textbook` | 标记来源为权威教材或专著 |
| `source_authority` | 来源权威性 | `authoritative_textbook` | 表示该证据来自基础权威资料 |
| `knowledge_strength` | 知识强度 | `high` | 教材骨架可信度高，但不是指南证据等级 |
| `clinical_applicability` | 临床适用性 | `general` | 用于通用基础医学和临床基础知识 |
| `recommendation_class` | 推荐等级 | `N/A` | 教材来源不得直接写 I、IIa、A、B 等指南分级 |
| `evidence_level` | 证据等级 | `N/A` | 教材来源不得直接写指南证据等级 |
| `knowledge_layer` | 知识层级 | `textbook_core` | V1.12 标准值；历史 `textbook_skeleton` 后续迁移为本值 |

#### 9.3.2 教材转引指南分级的处理规则

教材正文有时会写“指南推荐 I 类 A 级”。处理规则：

1. 如果来源是教材，`source_type` 仍写 `authoritative_textbook`。
2. 教材这条 Evidence 的 `recommendation_class` 和 `evidence_level` 仍写 `N/A`。
3. 教材原文里的“I类A级”可以保留在 `evidence_text`，不能删除。
4. 如果要使用正式推荐等级，必须回到原始指南，另建 `Guideline`、`Evidence` 和 `RecommendationStatement`。

一句话：教材可以告诉我们“这个病是什么、怎么看、原则上怎么治”，但正式 CDSS 推荐要以原始指南/共识推荐为准。

### 9.4 RecommendationStatement 推荐陈述

白话解释：`RecommendationStatement` 是“医生界面推荐卡片的根节点”。医生看到“建议急诊 PCI”时，前端应该从这一类节点拿到推荐内容、推荐动作、禁忌条件、指南来源、页码和原文摘要。

与 `TreatmentPlan` 的区别：

| 实体 | 回答的问题 | 示例 |
|---|---|---|
| `TreatmentPlan` | 做什么治疗 | 溶栓治疗、急诊PCI、抗凝治疗 |
| `RecommendationStatement` | 在什么条件下，为什么推荐/阻断这个动作 | STEMI发病12小时内且PCI可及时完成时推荐急诊PCI |

#### 9.4.1 推荐陈述必填字段

| 字段英文名 | 中文名称 | 必填 | 说明 |
|---|---|---|---|
| `statement_text` | 推荐原文/标准陈述 | 是 | 推荐语句原文或结构化改写；必须能追溯 |
| `statement_summary` | 医生展示摘要 | 是 | 前端卡片展示用短句 |
| `recommendation_type` | 推荐类型 | 是 | `recommend` 推荐、`consider` 可考虑、`do_not_recommend` 不推荐、`block` 阻断 |
| `scope_disease_code` | 适用疾病编码 | 是 | 推荐属于哪个疾病或专病范围 |
| `pathway_code` | 路径编码 | 是 | 所属 `ClinicalPathway`；没有则填 `N/A` |
| `stage_code` | 阶段编码 | 是 | 所属 `PathwayStage`；没有则填 `N/A` |
| `rule_code` | 触发规则编码 | 是 | 对应 `ClinicalRule.code` |
| `action_code` | 动作编码 | 是 | 推荐或阻断的检查、检验、药物、操作、治疗方案等 |
| `required_patient_data` | 需要的患者数据 | 是 | 规则要读取的主诉、诊断、检查、检验、禁忌证等字段 |
| `applicable_population` | 适用人群 | 是 | 适用患者范围、分型、阶段或场景 |
| `indication_conditions` | 适应条件 | 是 | 满足哪些条件才推荐 |
| `contraindication_conditions` | 禁忌/阻断条件 | 是 | 哪些情况不能推荐或需要阻断 |
| `recommendation_class` | 推荐等级 | 是 | I、IIa、IIb、III、未分级推荐、N/A |
| `evidence_level` | 证据等级 | 是 | A、B、C、专家共识、教材证据、N/A |
| `primary_evidence_code` | 主证据编码 | 是 | 默认展示给医生的主 Evidence |
| `primary_guideline_code` | 主来源编码 | 是 | 主 Evidence 对应的 Guideline/教材/共识 |
| `cdss_display_level` | 展示级别 | 是 | `strong_alert`、`recommendation`、`knowledge_display`、`block` |
| `clinical_review_status` | 临床审核状态 | 是 | 测试库可批量签收；正式上线需按临床机制确认 |
| `formal_cdss_ready` | 正式CDSS可用 | 是 | 只有字段、证据、禁忌、审核闭环完整才允许为 true |

#### 9.4.2 推荐卡片标准查询路径

```text
ClinicalRule / PathwayStage
  -> has_recommendation_statement
  -> RecommendationStatement
      -> recommends_action / blocks_action
      -> derived_from Evidence
      -> based_on_guideline Guideline
```

禁止前端为了显示推荐依据，再从 `Disease -> Evidence` 或 `Action -> Evidence` 反推主证据。

#### 9.4.3 推荐陈述示例

```json
{
  "entityType": "RecommendationStatement",
  "statement_summary": "STEMI且PCI可及时完成时，推荐急诊PCI",
  "recommendation_type": "recommend",
  "action_code": "PROC-CARD-PCI",
  "recommendation_class": "I",
  "evidence_level": "A",
  "primary_evidence_code": "EV-CARD-AMI-0001",
  "cdss_display_level": "recommendation",
  "formal_cdss_ready": false
}
```

### 9.5 教材骨架来源与章节锚点

白话解释：教材骨架不是“全文搜索疾病名”。必须先定位到目标疾病章节，再判断这段话属于定义、病因、临床表现、检查、诊断、治疗还是随访预防。

#### 9.5.1 教材骨架实体分工

| 实体 | 用途 | 是否建议新批次使用 |
|---|---|---|
| `SourceSection` | 来源章节锚点，保存章/节/小标题/页码范围 | 是 |
| `Definition` | 某来源下的定义容器 | 是 |
| `DefinitionComponent` | 定义拆解片段 | 是 |
| `DiagnosisCriteriaComponent` | 诊断标准明细组件 | 是 |
| `Prevention` | 预防、二级预防、健康管理 | 是 |
| `TextbookSection` | 历史教材章节实体 | legacy；后续迁移到 `SourceSection` |
| `ClinicalManifestation` | 历史临床表现容器 | 不建议；应拆到 `Symptom`/`Sign` 或 `SourceSection` |

#### 9.5.2 skeleton_slot：这条知识属于教材哪一栏

| skeleton_slot | 中文名称 | 说明 |
|---|---|---|
| `overview` | 疾病概述/定义 | 疾病定义、临床意义、总体描述 |
| `etiology` | 病因 | 导致疾病发生的原因 |
| `pathogenesis` | 发病机制/病理生理 | 机制、病理生理、病理改变、组织学改变 |
| `epidemiology` | 流行病学 | 发病率、患病率、好发人群、死亡风险 |
| `clinical_manifestation` | 临床表现 | 症状、体征、临床特征 |
| `exam_lab` | 检查/检验 | 辅助检查、实验室检查、心电图、影像、指标 |
| `diagnosis_differential` | 诊断与鉴别诊断 | 诊断标准、诊断依据、鉴别对象、排除条件 |
| `classification_risk` | 分型/分级/危险分层 | 疾病分型、分期、分级、风险分层、评分 |
| `treatment` | 治疗 | 治疗原则、治疗目标、药物、操作、器械、手术 |
| `prognosis_followup_prevention` | 预后/随访/预防 | 预后、二级预防、随访、复查、健康管理 |

#### 9.5.3 knowledge_layer：这条知识在 CDSS 中怎么用

| knowledge_layer | 中文名称 | 使用规则 |
|---|---|---|
| `textbook_core` | 教材基础骨架 | 可作为疾病基础知识、基础诊断框架和基础治疗原则 |
| `guideline_supplement` | 指南补充知识 | 可补充教材未覆盖的特殊人群、检查、治疗细节 |
| `guideline_decision` | 指南决策知识 | 可进入 `RecommendationStatement`，作为 CDSS 推荐卡片依据 |
| `screening_context` | 筛查/背景上下文 | 只能用于背景展示或筛查提示，不得直接作为目标疾病核心表现 |
| `cross_reference` | 跨章节引用 | 只能表达“其他章节提到本病”，不得写入目标疾病 definition、核心症状、核心治疗或诊断标准 |

历史兼容：服务器已有 `knowledge_layer=textbook_skeleton`，后续迁移时统一改为 `textbook_core`；`knowledge_layer=evidence` 按来源和用途拆分为 `textbook_core/guideline_supplement/guideline_decision`。

#### 9.5.4 章节锚点硬规则

1. `Disease.definition` 必须来自目标疾病所在章节的定义段或概述段。
2. 教材核心节点和关系必须标记 `skeleton_slot` 与 `knowledge_layer`。
3. `Disease.description` 不得使用其他疾病章节、其他系统章节或跨章节引用段落。
4. 教材关系若来自目标疾病章节外，必须标记为 `knowledge_layer=cross_reference` 或 `screening_context`，不得进入核心骨架槽位。
5. 每条教材核心关系必须同时具备：
   - `source_type=authoritative_textbook`
   - `source_section_path`
   - `skeleton_slot`
   - `knowledge_layer`
   - `pdf_page_start/pdf_page_end`；若无 PDF，则必须有等价文本定位
   - `evidence_text`
6. 禁止用文档级关键词命中替代疾病章节绑定。若目标疾病名称只出现在其他疾病段落的鉴别、病因、并发症或转引中，只能作为跨章节引用，不得写入目标疾病核心字段。

#### 9.5.5 心血管内科教材骨架扩展顺序

心血管内科本轮先以四个大类验证教材骨架方法：

1. 冠心病
2. 心肌病
3. 心力衰竭
4. 心律失常

上述四类不是最终范围，只是优先验证范围。验证通过后，执行团队必须按同一规则自行扩大到《内科学》第10版心血管内科章节中其他疾病大类和疾病，包括但不限于高血压、心脏瓣膜病、心包疾病、感染性心内膜炎、先天性心血管病、主动脉和周围血管病、心血管神经症、肿瘤心脏病学及其他心血管疾病。扩大范围不需要重新设计规则，但必须保留批次登记、来源清单和骨架槽位审计。

## 10. provenance 证据集合

同一语义关系存在多份来源时，只保留一条关系，聚合完整证据集合：

```json
{
  "provenance_records": [
    {
      "document_id": "DOC-...",
      "segment_id": "SEG-...",
      "source_name": "文献名称",
      "source_type": "guideline",
      "source_version": "2025",
      "source_section": "章节名称",
      "source_page": 12,
      "evidence_text": "原文片段",
      "recommendation_class": "I",
      "evidence_level": "A"
    }
  ]
}
```

关系同时维护：

| 字段英文名 | 中文名称 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `evidence_ids` | 证据ID列表 | String[] | 是 | 支持该关系的 Evidence 节点编码列表 |
| `document_ids` | 文档ID列表 | String[] | 是 | 证据来源文档编码列表 |
| `source_names` | 来源名称列表 | String[] | 是 | 指南、教材、共识或专家资料名称 |
| `source_types` | 来源类型列表 | String[] | 是 | `guideline`、`consensus`、`authoritative_textbook`、`expert_material` 等 |
| `evidence_count` | 证据数量 | Integer | 是 | 支持该关系的证据条数，必须等于 provenance 记录数 |
| `provenance_records_json` | 证据溯源集合 | JSON Array | 是 | 完整保存每条证据的文档、章节、页码、原文片段和分级信息 |

数组记录数、`evidence_count` 和 provenance 记录数必须一致。

## 11. 临床规则与阈值

### 11.1 ThresholdRule

必填字段：

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `indicator_code` | 指标编码 | String | 是 | 关联的 `ExamIndicator` 编码，例如 LVEF、LVOT 压差 |
| `operator` | 比较符 | Enum | 是 | `>`、`>=`、`<`、`<=`、`=`、`between` 等 |
| `value` | 阈值 | Number/String | 是 | 结构化阈值数值；区间可用数组或规范字符串 |
| `unit` | 单位 | String | 是 | mmHg、%、ms、ng/L 等 |
| `condition` | 适用条件 | String | 是 | 静息、负荷、激发、特定检查方法等条件 |
| `patient_state` | 患者状态 | String | 是 | 适用疾病、分型、人群或状态 |
| `time_context` | 时间上下文 | String | 是 | 发病后、术后、随访时、入院时等时间条件 |

示例：

```json
{
  "indicator_code": "IND-LVOT-GRADIENT",
  "operator": ">=",
  "value": 30,
  "unit": "mmHg",
  "condition": "静息或激发",
  "patient_state": "肥厚型心肌病"
}
```

### 11.2 ClinicalRule

用于多条件规则，至少保存：

| 字段英文名 | 中文名称 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `rule_type` | 规则类型 | String | 是 | 诊断规则、治疗规则、风险分层规则、禁忌规则等 |
| `if_conditions` | 前提条件 | JSON Array/String[] | 是 | 触发规则所需条件，可包含症状、检查、阈值、患者状态 |
| `then_actions` | 结论/动作 | JSON Array/String[] | 是 | 满足条件后的诊断、治疗、检查、转诊或随访建议 |
| `exceptions` | 例外条件 | JSON Array/String[] | 否 | 不适用或需排除的条件 |
| `applicability` | 适用范围 | String | 是 | 适用病种、分型、人群、场景或路径 |
| `evidence_id` | 证据ID | String | 是 | 支持该规则的 Evidence 编码 |

## 12. 专科/疾病大类配置

每个执行范围生成配置文件，至少包含：

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `scope_type` | 执行范围类型 | Enum | 是 | `specialty` 专科、`category` 疾病大类、`disease` 单病种 |
| `scope_target` | 执行范围目标 | String | 是 | 当前批次要处理的专科、大类或病种名称 |
| `specialty_code` | 专科编码 | String | 是 | 顶层专科节点编码 |
| `category_code` | 疾病大类编码 | String | 视范围而定 | 疾病大类节点编码；专科全量建设时可为空或逐行配置 |
| `disease_code` | 疾病编码 | String | 视范围而定 | 具体疾病节点编码；大类或单病种配置时必填 |
| `pathway_element` | 路径环节 | Enum | 是 | 见 §13.1 标准环节 |
| `applicability_status` | 适用性状态 | Enum | 是 | `required` 必填、`optional` 可选、`not_applicable` 不适用 |
| `reason` | 配置原因 | String | 是 | 说明为什么该环节在本范围内为必填、可选或不适用 |

配置决定闭环验收要求，但不得改变实体和关系的标准定义。

## 13. 诊疗路径闭环

### 13.1 标准环节

| 路径环节英文名 | 中文名称 | 默认适用性 | 说明 |
|---|---|---|---|
| `definition` | 定义 | required | 疾病或核心概念的权威定义 |
| `aliases` | 别名 | required | 中文别名、英文名、缩写、旧称和同义词 |
| `etiology` | 病因 | required | 导致疾病发生的原因 |
| `pathophysiology` | 发病机制/病理生理 | optional | 疾病发生发展的机制；复杂疾病可设为 required |
| `epidemiology` | 流行病学 | optional | 发病率、患病率、人群分布等 |
| `risk_factor` | 危险因素 | required | 增加疾病发生或进展风险的因素 |
| `symptom` | 症状 | required | 患者主观感受 |
| `sign` | 体征 | required | 医师客观发现 |
| `exam` | 检查 | required | 影像、生理、内镜、介入等检查 |
| `lab_test` | 实验室检验 | optional | 检验大项，如肝肾功能、心肌标志物 |
| `exam_indicator` | 检查/检验指标 | optional | 具体指标，如 LVEF、肌钙蛋白、ST 段改变 |
| `threshold_rule` | 阈值规则 | optional | 可计算的诊断、分层或治疗阈值 |
| `diagnosis_criteria` | 诊断标准 | required | 明确诊断依据或标准 |
| `differential_diagnosis` | 鉴别诊断 | required | 需要鉴别或排除的疾病/状态 |
| `classification_stage` | 分型/分期/分级 | optional | V1.1 新增；遗传病、肿瘤、心衰分型等可配置为 required |
| `risk_stratification` | 风险分层 | optional | 风险分层方案或风险等级 |
| `scoring_scale` | 评分量表 | optional | GRACE、TIMI、CHA2DS2-VASc 等评分 |
| `treatment_plan` | 治疗方案 | required | 治疗策略、治疗路径或治疗原则 |
| `medication` | 药物 | optional | 药物类别或具体药品 |
| `procedure` | 操作/手术/介入 | optional | PCI、CABG、消融、手术等 |
| `indication` | 适应证 | optional | 药物或操作适用条件 |
| `contraindication` | 禁忌证 | optional | 药物或操作禁用条件 |
| `complication` | 并发症 | required | 疾病可导致的并发症 |
| `prognosis` | 预后 | required | 结局、死亡风险、复发风险等 |
| `follow_up` | 随访 | required | 复查项目、频率、随访周期 |
| `clinical_pathway` | 诊疗路径 | optional | V1.1 新增；综合性路径容器，路径复杂时配置为 required |
| `guideline` | 指南/来源 | required | 支撑该疾病图谱的指南、教材、共识、专家资料 |
| `evidence` | 证据 | required | 可定位原文证据片段 |

> **[V1.1 说明 — classification_stage]** 此环节对应 `ClassificationStage` 实体及 `has_classification_stage` 关系。闭环审计时检查该疾病是否存在已建立的分型/分期节点。对于无标准分型的疾病，配置为 `not_applicable`。
>
> **[V1.1 说明 — clinical_pathway]** `ClinicalPathway` 作为综合性容器实体参与路径闭环审计，标注为 `optional`。对于具有明确诊疗流程图或标准路径的疾病（如 AMI/STEMI），可在专科配置层将此环节设为 `required`。

### 13.2 审计字段

```text
disease_code
pathway_element
applicability_status
coverage_status       covered | missing | not_applicable
evidence_count
source_names
missing_reason
solution
```

### 13.3 完整判定

只有所有 `required` 环节均为 `covered` 时，才能标记：

```text
closed_loop_ready=yes
closed_loop_basis=element_coverage_not_quantity_threshold
```

证据数量不能弥补必需环节缺失。

> **[V1.1 新增 — schema_gap 的闭环影响]** 若某必需路径环节的缺失原因登记为 `SCHEMA_UNSUPPORTED`（即写入了 `schema_gap_register.csv`），该环节不得标记为 `covered`，闭环状态不得标记为 `yes`，直至 Schema 修订并通过重新验收。`schema_gap` 登记本身不构成通过质量闸门的依据。

## 14. 批次与合并契约

### 14.1 批次字段

```text
batch_id
scope_type
scope_target
created_time
source_manifest_hash
schema_version
quality_gate_status
merge_status
```

### 14.2 节点合并

匹配顺序：

1. 相同全局 `code`。
2. 相同 `entityType` ＋ 规范名称。
3. 受控别名或外部标准编码确认同一实体。

无法确认时进入冲突队列，不自动合并。

### 14.3 关系合并

关系语义键：

```text
(source.code, relationType, target.code)
```

相同语义关系聚合 provenance，不建立平行重复边。

### 14.4 冲突与回滚

- 属性冲突使用 `conflict_status=open` 并写入冲突台账。
- 合并前创建标准主图谱快照。
- 合并验证失败时恢复快照。
- 每个批次保留独立、不可变的数据实例包。

## 15. 禁止关系与错误建模

禁止：

- 关系方向与标准相反。
- 使用自然语言短语作为 `relationType`。
- 使用 `entityType=DiseaseSubtype`（本 Schema 已无此类型）。
- 把 `DiseaseCategory` 复制为同名 `Disease`。
- 把并发症语义误建成独立疾病副本。
- 把药物类别和具体药品混为同一节点。
- 把教材权威性写成指南 I/A 分级。
- 把教材转引的分级文字直接填入 `recommendation_class` 字段。
- 把本机路径写入节点或关系。
- 用文档级关键词命中替代疾病章节绑定。
- 缺少原文证据仍创建核心临床关系。
- 把患者状态禁忌语义写成 `state_recommends_*` 正向关系。
- 对同一药物相互作用混用直接药物对建模和 DrugInteraction 节点建模。

## 16. 数据实例硬闸门

正式数据实例必须满足：

- 未知 `entityType` 数量为 0（包含已废弃的 `DiseaseSubtype`）。
- 未知 `relationType` 数量为 0。
- 错误关系方向数量为 0。
- 重复 `code` 数量为 0。
- 同类型同名重复实体数量为 0。
- 悬空关系数量为 0。
- 重复语义关系数量为 0。
- 本机路径污染数量为 0。
- Unicode 替换字符和典型错码数量为 0。
- 核心临床关系证据链完整率为 100%。
- 关系目标名称/别名在证据分段命中率为 100%。
- Definition 与目标疾病相关性命中率为 100%。
- 跨疾病来源污染数量为 0。
- `disease_definition_empty_count=0`：scope 内所有正式疾病必须有 `definition`。
- `disease_definition_source_mismatch_count=0`：疾病定义必须来自目标疾病章节定义/概述段，不得来自其他疾病、其他章节或跨章节引用。
- `description_cross_chapter_pollution_count=0`：`Disease.description` 不得命中其他疾病章节、其他系统章节、鉴别引用段或并发症引用段。
- `textbook_core_without_skeleton_slot_count=0`：`source_type=authoritative_textbook` 且用于教材核心骨架的节点/关系必须有 `skeleton_slot`。
- `textbook_core_without_knowledge_layer_count=0`：教材核心关系必须有 `knowledge_layer=textbook_core`；筛查背景和跨章节引用不得伪装为核心骨架。
- `textbook_source_anchor_missing_count=0`：教材核心证据必须有 `source_section_path` 和可定位页码/文本锚点。
- 教材伪装正式指南分级数量为 0（`source_type=authoritative_textbook` 记录中 `recommendation_class ≠ N/A` 的数量为 0）。
- 必需环节缺口均有原因和解决方案。
- **[V1.1 新增]** `schema_gap_register.csv` 中存在未解决条目且涉及 `required` 路径环节的批次，`quality_gate_status` 不得标记为 `passed`。
- **[V1.1 新增]** 患者状态否定语义（禁忌）使用 `state_contraindicates_*` 或 `has_contraindication` 表达，`state_recommends_*` 关系中 `polarity=negative` 的记录数为 0（此写法已废弃）。
- **[V1.5 新增]** 疾病不得直接连接“鉴别诊断”“诊断标准”“药物治疗”“一般治疗”“预后良好/不良”“定期随访”“危险分层”等通用语义空壳节点；必须抽取具体对象或具体规则。
- **[V1.5 新增]** 药物类别 aliases 不得包含具体药物、英文缩写或治疗动作词；具体药物必须独立建 `Medication` 节点，并通过 `has_specific_medication` 连接。
- **[V1.5 新增]** 正式 CDSS 推荐层硬门槛：scope 内所有疾病 required 缺口为 0；治疗推荐至少覆盖 ClinicalRule/Indication/Contraindication/ClinicalPathway；所有推荐必须有适用人群、排除条件、证据来源、推荐等级和 `clinical_review_status=clinical_approved`；药物必须有标准名、别名、剂量、禁忌证、相互作用字段。未临床审核的节点和关系可进入测试图谱，但不得进入正式 CDSS 推荐层。
- **[V1.6 新增]** 结构可用性硬闸门：`technical_display_name_error_count=0`、`treatment_plan_actionability_error_count=0`、`medication_class_without_specific_count=0`、`duplicate_semantic_relation_count=0`。截图、前端或审核统计中出现“同一疾病下同一药物/检查/治疗节点重复计数”，必须判定为视图去重或关系语义键去重失败，先修复再交付。

## 17. Neo4j 导入标准

数据实例验收通过并获得用户确认后才允许导入。

节点写入：

```cypher
MERGE (n:KGNode:`实体类型` {code: $code})
SET n += $properties,
    n.primary_label = 'KGNode',
    n.type_label = $entityType,
    n.canonical_labels = ['KGNode', $entityType]
```

规则：

- `code` 建立唯一约束。
- 目录、临床和证据节点必须带 `KGNode` 主标签，可增加辅助类型标签，但 `entityType` 只有一个标准值。
- 禁止创建只带 `Disease`、`TreatmentPlan`、`DiagnosisCriteria` 等类型标签而不带 `KGNode` 的节点；此类节点不属于标准图谱，可绕过质量审计，必须阻断交付。
- 关系按语义键去重后创建。
- 多批次合并后必须在服务器执行关系语义键去重；同一 `(source.code, relationType, target.code)` 只允许保留一条关系，来源差异应合并到 provenance 或审计字段，不得生成重复边。
- 前端图谱接口必须按节点 `code` 去重构造节点集合；关系集合可保留多条路径，但实体数量、维度节点数量和截图统计必须使用唯一节点数。
- 导入前备份，导入后执行全库质量审计。必须满足 `all_node_count == kg_node_count`、`all_relation_count == kg_relation_count`、`non_kgnode_node_count=0`、`relation_touching_non_kgnode_count=0`。
- 禁止用完整属性集合 `MERGE` 节点。

## 18. 标准交付文件

每个批次至少交付：

```text
scope_taxonomy.csv
source_documents_manifest.csv
dedup_index.csv                    [V1.1 新增]
source_folder_summary.csv          [V1.1 新增]
page_audit.jsonl
document_quality_audit.csv
segment_index.jsonl
textbook_skeleton_matrix.csv        [V1.11 新增，教材骨架槽位覆盖矩阵]
textbook_chapter_anchor_audit.csv   [V1.11 新增，教材章节锚点与污染审计]
nodes_final.jsonl
nodes_final.csv
relations_final.jsonl
relations_final.csv
graph_final.json
disease_pathway_coverage.csv
missing_reason_and_solution.csv
source_conflict_register.csv       [V1.1 补入主清单]
schema_gap_register.csv
quality_gate_summary.json
专家审核说明.md
```

正式节点和关系不得包含本地路径；本地路径只允许存在于执行清单和审计日志。

## 19. 专病 CDSS 动态流程引擎映射

### 19.1 白话解释

专科知识图谱不是让前端或 Oracle 一次性把某个疾病下所有检查、检验、药物、手术、鉴别诊断全部圈出来。图谱应作为医学规则来源，供专病流程引擎按患者当前状态实时调用。

标准调用链：

```text
EMR/业务系统事件
  -> 流程引擎读取患者当前数据
  -> 流程引擎查询图谱中的 ClinicalPathway / PathwayStage / ClinicalRule
  -> 计算当前阶段、已满足条件、缺失条件、阻断原因
  -> 返回当前可执行推荐、暂不推荐项目和证据链
  -> 前端展示给医生并记录医生反馈
```

### 19.2 图谱维护什么

图谱必须维护以下医学知识：

| 内容 | 推荐实体/字段 | 示例 |
|---|---|---|
| 专病路径 | `ClinicalPathway` | 急性心肌梗死诊疗路径 |
| 诊疗阶段 | `PathwayStage` | 疑诊评估、诊断确认、再灌注决策、抗栓治疗、二级预防 |
| 阶段顺序 | `next_pathway_stage` | 诊断确认 → 再灌注决策 |
| 阶段规则 | `ClinicalRule` | STEMI 溶栓适应证规则 |
| 条件文本 | `if_conditions`、`condition_text` | STEMI、发病≤12小时、PCI不可及时、无溶栓禁忌证 |
| 推荐陈述 | `RecommendationStatement` | “STEMI且发病≤12小时，优先评估急诊PCI可及性” |
| 推荐动作 | `RecommendationStatement -> recommends_action` | 急诊PCI、溶栓治疗、肌钙蛋白检测 |
| 阻断动作 | `RecommendationStatement -> blocks_action` | 可疑主动脉夹层阻断溶栓 |
| 证据链 | `RecommendationStatement -> derived_from` | 指南、页码、推荐等级、证据等级 |

### 19.3 流程引擎维护什么

以下内容不属于医学知识图谱主体，不应作为标准图谱关系硬编码：

| 内容 | 所属层 | 示例 |
|---|---|---|
| EMR字段映射 | 流程引擎/集成层 | 主诉字段、主诊断字段、心电图报告字段、检验结果字段 |
| 系统事件 | 流程引擎 | 主诊断保存、检验回报、医嘱提交、过敏史更新 |
| 当前患者阶段 | 流程引擎运行态 | 当前处于“再灌注决策阶段” |
| 是否弹窗/提醒/置顶 | 前端/流程引擎 | 高危提醒、静默提示、知识展示 |
| 医生反馈 | 业务系统 | 采纳、忽略、暂不处理、原因 |

### 19.4 AMI 示例

图谱表达：

```text
Disease: ST段抬高型心肌梗死
  has_clinical_pathway -> ClinicalPathway: STEMI诊疗路径
ClinicalPathway
  has_pathway_stage -> PathwayStage: 再灌注决策阶段
PathwayStage
  has_stage_rule -> ClinicalRule: STEMI再灌注策略选择规则
ClinicalRule
  if_conditions:
    - 确诊或高度疑似STEMI
    - 发病时间≤12小时
    - 评估PCI可及性
    - 排除溶栓禁忌证
  has_recommendation_statement -> RecommendationStatement: STEMI急诊PCI推荐陈述
RecommendationStatement
  statement_summary: STEMI且发病≤12小时，优先评估急诊PCI可及性
  recommendation_class: I
  evidence_level: A
  recommends_action -> Procedure: 急诊PCI
  based_on_guideline -> Guideline: STEMI ESC 2017
  derived_from -> Evidence: STEMI ESC 2017 第48页
```

流程引擎执行：

```text
事件：心电图结果返回 / 主诊断保存 / 发病时间录入
读取：主诊断、发病时间、心电图、肌钙蛋白、禁忌证、PCI可及性
判断：当前是否满足再灌注决策阶段条件
输出：
  - 当前阶段：再灌注决策
  - 已满足：STEMI、发病≤12小时
  - 缺失：PCI预计时间、溶栓禁忌证评估
  - 推荐：补充PCI可及性和禁忌证评估
  - 暂不推荐：直接溶栓
  - 原因：主动脉夹层/出血风险未排除
  - 证据：直接读取 RecommendationStatement 的指南、页码、推荐等级、证据等级
```

### 19.5 CDSS 应用硬规则

- CDSS 推荐不得等同于“疾病下所有关联节点”。
- 进入 CDSS 推荐层的动作必须通过 `PathwayStage + ClinicalRule + Evidence` 组合表达。
- 推荐动作必须区分：立即推荐、条件满足后推荐、缺资料暂缓、禁忌阻断、仅知识展示。
- 前端必须展示推荐原因、缺失条件、禁忌/排除条件和证据来源。
- 如果只查到诊断标准、治疗方案或药物标题，缺少条件、动作明细和证据链，不得作为可执行 CDSS 推荐。

## 9. Guideline 与 Evidence

### 9.0 白话解释

`Guideline` 和 `Evidence` 是证据链里的两个不同层级，不能混用。

| 名称 | 中文理解 | 回答的问题 | 举例 |
|---|---|---|---|
| `Guideline` | 来源文献/资料本身 | 这条知识来自哪一份指南、共识、教材或专家资料？ | 《2025 ESC 心肌病指南》这一整份文献 |
| `Evidence` | 原文证据片段 | 这条知识在文献里的哪一句、哪一段、哪一页能证明？ | 指南第 35 页中“肥厚型心肌病患者应进行超声心动图评估”的原文片段 |

简单说：

- `Guideline` 是“书/指南/资料这份文件”。
- `Evidence` 是“从这份文件里截出来、能支撑某个节点或关系的原文句子/段落”。
- 一个 `Guideline` 可以包含很多条 `Evidence`。
- 一个疾病、检查、药物、诊断标准或治疗关系，必须能追溯到具体 `Evidence`，不能只说“来自某指南”。

示例：

```text
Guideline：
《中国冠心病诊疗指南 2024》

Evidence：
该指南第 12 页某段原文：急性冠脉综合征患者应尽早进行心电图和肌钙蛋白检测。

图谱关系：
急性冠脉综合征 --requires_exam--> 心电图
急性冠脉综合征 --requires_lab_test--> 肌钙蛋白

证据链：
上述两个关系 --supported_by_evidence--> 该 Evidence
该 Guideline --guideline_has_evidence--> 该 Evidence
```

这样设计的目的：

- 临床团队可以追溯“这条知识从哪里来”。
- 审核人员可以直接查看原文，不依赖抽取模型的总结。
- 多份指南冲突时，可以比较每条 Evidence 的年份、来源、推荐等级和证据等级。

### 9.1 Guideline 字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `document_id` | 文档ID | String | 是 | 文献或资料的唯一编码 |
| `title` | 标题 | String | 是 | 指南、共识、教材或资料标题 |
| `source_type` | 来源类型 | Enum | 是 | 见下方来源类型枚举 |
| `issuing_body` | 发布机构 | String | 否 | 学会、协会、出版社、专家组或机构名称 |
| `publication_year` | 发布年份 | Integer/String | 否 | 发表、发布或出版年份 |
| `version` | 版本 | String | 否 | 指南版本、教材版次或修订版本 |
| `language` | 语言 | String | 是 | `zh-CN`、`en` 等 |
| `sha256` | 文件哈希 | String | 是 | 原始文件内容哈希，用于去重和来源追溯 |

`source_type` 枚举：

| 枚举值 | 中文名称 | 说明 |
|---|---|---|
| `guideline` | 指南 | 正式诊疗指南 |
| `consensus` | 共识 | 专家共识、声明、建议 |
| `authoritative_textbook` | 权威教材/专著 | 教材、专科专著、权威参考书 |
| `expert_material` | 专家资料 | 经确认的专家课件、内部资料、审稿意见 |
| `curated_web_text` | 人工筛选网页文本 | 经人工确认可信的网页资料 |

### 9.2 Evidence 证据片段字段

白话解释：`Evidence` 是“原文证据片段”。医生或审核人员问“这句话从哪里来的”，就应该能从 `Evidence` 找到原文、页码、章节和定位信息。

与 §7.7 的区别：

```text
§7.7：定义 Evidence 和其他节点怎么连。
§9.2：定义 Evidence 节点自己要保存哪些字段。
```

#### 9.2.1 Evidence 必填字段

| 字段英文名 | 中文名称 | 必填 | 说明 |
|---|---|---|---|
| `evidence_id` | 证据ID | 是 | 证据片段唯一编码；用于被推荐、疾病、检查等节点引用 |
| `document_id` | 文档ID | 是 | 证据来自哪份 PDF、DOCX、网页或专家资料 |
| `segment_id` | 片段ID | 是 | 证据在解析文本中的段落、行号或切片编号 |
| `source_name` | 来源名称 | 是 | 例如《中国心房颤动管理指南（2025）》或《内科学（第10版）》 |
| `source_type` | 来源类型 | 是 | `guideline`、`consensus`、`authoritative_textbook`、`expert_material`、`curated_web_text` |
| `source_section` | 来源章节 | 是 | 原文所在章节标题；短标题即可 |
| `source_section_path` | 完整章节路径 | 长文档必填 | 从篇、章、节到小标题的完整路径，用于防止跨章节误抓 |
| `source_page` | 页码 | 是 | PDF 页码；无页码文本填 `N/A`，但必须有 `segment_id` 或行号 |
| `pdf_page_start` / `pdf_page_end` | PDF页码范围 | PDF 必填 | 按 PDF 阅读器页码，不等同书内印刷页码 |
| `book_page_start` / `book_page_end` | 书内页码范围 | 教材建议必填 | 教材印刷页码；没有则填 `N/A` |
| `text_anchor` | 文本锚点 | 建议必填 | 原文首句、标题或关键短语，便于人工快速核对 |
| `evidence_text` | 原文证据 | 是 | 必须保存原文，不得只保存总结、改写或翻译 |
| `language` | 原文语言 | 是 | `zh-CN`、`en` 等 |
| `translation_text` | 中文翻译 | 英文来源必填 | 英文原文不能被中文翻译替代，两者要分别保存 |
| `content_hash` | 内容哈希 | 是 | 用于去重、防篡改和复核 |

#### 9.2.2 Evidence 示例

```json
{
  "entityType": "Evidence",
  "evidence_id": "EV-CARD-AMI-0001",
  "source_name": "ESC 急性冠脉综合征指南（2023）",
  "source_type": "guideline",
  "source_section_path": "ACS > STEMI > Reperfusion therapy",
  "source_page": 42,
  "evidence_text": "原文片段……",
  "content_hash": "sha256:..."
}
```

#### 9.2.3 Evidence 硬规则

1. `evidence_text` 必须是原文，不能只存中文总结。
2. 英文原文和中文翻译必须分字段保存。
3. 目录、版权页、缩写表、参考文献默认不能作为临床证据。
4. 证据节点不得保存本地文件绝对路径，只能保存文档ID、章节、页码、片段ID。
5. 教材、指南、网页都可以生成 Evidence，但 `source_type` 必须准确区分。

### 9.3 教材来源与指南来源的区别

白话解释：教材负责“基础骨架”，指南负责“决策推荐”。教材很权威，但教材中的知识不能自动等同于指南推荐等级。

| 来源类型 | 主要作用 | 能不能直接给 I/A 推荐等级 | CDSS 用途 |
|---|---|---|---|
| 教材/专著 `authoritative_textbook` | 搭疾病基础骨架 | 不能 | 定义、病因、机制、临床表现、基础诊断、治疗原则 |
| 指南 `guideline` | 给规范化推荐 | 可以，按原文 | 推荐陈述、推荐等级、证据等级、时间窗、禁忌证 |
| 共识 `consensus` | 补充专家建议 | 视原文而定 | 专家共识推荐、操作规范、特殊场景 |
| 外部权威网页 `curated_web_text` | 补缺基础知识 | 不能 | 定义、概述、背景补充；不得直接作为正式推荐 |

#### 9.3.1 教材来源固定字段

| 字段英文名 | 中文名称 | 固定值/建议值 | 说明 |
|---|---|---|---|
| `source_type` | 来源类型 | `authoritative_textbook` | 标记来源为权威教材或专著 |
| `source_authority` | 来源权威性 | `authoritative_textbook` | 表示该证据来自基础权威资料 |
| `knowledge_strength` | 知识强度 | `high` | 教材骨架可信度高，但不是指南证据等级 |
| `clinical_applicability` | 临床适用性 | `general` | 用于通用基础医学和临床基础知识 |
| `recommendation_class` | 推荐等级 | `N/A` | 教材来源不得直接写 I、IIa、A、B 等指南分级 |
| `evidence_level` | 证据等级 | `N/A` | 教材来源不得直接写指南证据等级 |
| `knowledge_layer` | 知识层级 | `textbook_core` | V1.12 标准值；历史 `textbook_skeleton` 后续迁移为本值 |

#### 9.3.2 教材转引指南分级的处理规则

教材正文有时会写“指南推荐 I 类 A 级”。处理规则：

1. 如果来源是教材，`source_type` 仍写 `authoritative_textbook`。
2. 教材这条 Evidence 的 `recommendation_class` 和 `evidence_level` 仍写 `N/A`。
3. 教材原文里的“I类A级”可以保留在 `evidence_text`，不能删除。
4. 如果要使用正式推荐等级，必须回到原始指南，另建 `Guideline`、`Evidence` 和 `RecommendationStatement`。

一句话：教材可以告诉我们“这个病是什么、怎么看、原则上怎么治”，但正式 CDSS 推荐要以原始指南/共识推荐为准。

### 9.4 RecommendationStatement 推荐陈述

白话解释：`RecommendationStatement` 是“医生界面推荐卡片的根节点”。医生看到“建议急诊 PCI”时，前端应该从这一类节点拿到推荐内容、推荐动作、禁忌条件、指南来源、页码和原文摘要。

与 `TreatmentPlan` 的区别：

| 实体 | 回答的问题 | 示例 |
|---|---|---|
| `TreatmentPlan` | 做什么治疗 | 溶栓治疗、急诊PCI、抗凝治疗 |
| `RecommendationStatement` | 在什么条件下，为什么推荐/阻断这个动作 | STEMI发病12小时内且PCI可及时完成时推荐急诊PCI |

#### 9.4.1 推荐陈述必填字段

| 字段英文名 | 中文名称 | 必填 | 说明 |
|---|---|---|---|
| `statement_text` | 推荐原文/标准陈述 | 是 | 推荐语句原文或结构化改写；必须能追溯 |
| `statement_summary` | 医生展示摘要 | 是 | 前端卡片展示用短句 |
| `recommendation_type` | 推荐类型 | 是 | `recommend` 推荐、`consider` 可考虑、`do_not_recommend` 不推荐、`block` 阻断 |
| `scope_disease_code` | 适用疾病编码 | 是 | 推荐属于哪个疾病或专病范围 |
| `pathway_code` | 路径编码 | 是 | 所属 `ClinicalPathway`；没有则填 `N/A` |
| `stage_code` | 阶段编码 | 是 | 所属 `PathwayStage`；没有则填 `N/A` |
| `rule_code` | 触发规则编码 | 是 | 对应 `ClinicalRule.code` |
| `action_code` | 动作编码 | 是 | 推荐或阻断的检查、检验、药物、操作、治疗方案等 |
| `required_patient_data` | 需要的患者数据 | 是 | 规则要读取的主诉、诊断、检查、检验、禁忌证等字段 |
| `applicable_population` | 适用人群 | 是 | 适用患者范围、分型、阶段或场景 |
| `indication_conditions` | 适应条件 | 是 | 满足哪些条件才推荐 |
| `contraindication_conditions` | 禁忌/阻断条件 | 是 | 哪些情况不能推荐或需要阻断 |
| `recommendation_class` | 推荐等级 | 是 | I、IIa、IIb、III、未分级推荐、N/A |
| `evidence_level` | 证据等级 | 是 | A、B、C、专家共识、教材证据、N/A |
| `primary_evidence_code` | 主证据编码 | 是 | 默认展示给医生的主 Evidence |
| `primary_guideline_code` | 主来源编码 | 是 | 主 Evidence 对应的 Guideline/教材/共识 |
| `cdss_display_level` | 展示级别 | 是 | `strong_alert`、`recommendation`、`knowledge_display`、`block` |
| `clinical_review_status` | 临床审核状态 | 是 | 测试库可批量签收；正式上线需按临床机制确认 |
| `formal_cdss_ready` | 正式CDSS可用 | 是 | 只有字段、证据、禁忌、审核闭环完整才允许为 true |

#### 9.4.2 推荐卡片标准查询路径

```text
ClinicalRule / PathwayStage
  -> has_recommendation_statement
  -> RecommendationStatement
      -> recommends_action / blocks_action
      -> derived_from Evidence
      -> based_on_guideline Guideline
```

禁止前端为了显示推荐依据，再从 `Disease -> Evidence` 或 `Action -> Evidence` 反推主证据。

#### 9.4.3 推荐陈述示例

```json
{
  "entityType": "RecommendationStatement",
  "statement_summary": "STEMI且PCI可及时完成时，推荐急诊PCI",
  "recommendation_type": "recommend",
  "action_code": "PROC-CARD-PCI",
  "recommendation_class": "I",
  "evidence_level": "A",
  "primary_evidence_code": "EV-CARD-AMI-0001",
  "cdss_display_level": "recommendation",
  "formal_cdss_ready": false
}
```

### 9.5 教材骨架来源与章节锚点

白话解释：教材骨架不是“全文搜索疾病名”。必须先定位到目标疾病章节，再判断这段话属于定义、病因、临床表现、检查、诊断、治疗还是随访预防。

#### 9.5.1 教材骨架实体分工

| 实体 | 用途 | 是否建议新批次使用 |
|---|---|---|
| `SourceSection` | 来源章节锚点，保存章/节/小标题/页码范围 | 是 |
| `Definition` | 某来源下的定义容器 | 是 |
| `DefinitionComponent` | 定义拆解片段 | 是 |
| `DiagnosisCriteriaComponent` | 诊断标准明细组件 | 是 |
| `Prevention` | 预防、二级预防、健康管理 | 是 |
| `TextbookSection` | 历史教材章节实体 | legacy；后续迁移到 `SourceSection` |
| `ClinicalManifestation` | 历史临床表现容器 | 不建议；应拆到 `Symptom`/`Sign` 或 `SourceSection` |

#### 9.5.2 skeleton_slot：这条知识属于教材哪一栏

| skeleton_slot | 中文名称 | 说明 |
|---|---|---|
| `overview` | 疾病概述/定义 | 疾病定义、临床意义、总体描述 |
| `etiology` | 病因 | 导致疾病发生的原因 |
| `pathogenesis` | 发病机制/病理生理 | 机制、病理生理、病理改变、组织学改变 |
| `epidemiology` | 流行病学 | 发病率、患病率、好发人群、死亡风险 |
| `clinical_manifestation` | 临床表现 | 症状、体征、临床特征 |
| `exam_lab` | 检查/检验 | 辅助检查、实验室检查、心电图、影像、指标 |
| `diagnosis_differential` | 诊断与鉴别诊断 | 诊断标准、诊断依据、鉴别对象、排除条件 |
| `classification_risk` | 分型/分级/危险分层 | 疾病分型、分期、分级、风险分层、评分 |
| `treatment` | 治疗 | 治疗原则、治疗目标、药物、操作、器械、手术 |
| `prognosis_followup_prevention` | 预后/随访/预防 | 预后、二级预防、随访、复查、健康管理 |

#### 9.5.3 knowledge_layer：这条知识在 CDSS 中怎么用

| knowledge_layer | 中文名称 | 使用规则 |
|---|---|---|
| `textbook_core` | 教材基础骨架 | 可作为疾病基础知识、基础诊断框架和基础治疗原则 |
| `guideline_supplement` | 指南补充知识 | 可补充教材未覆盖的特殊人群、检查、治疗细节 |
| `guideline_decision` | 指南决策知识 | 可进入 `RecommendationStatement`，作为 CDSS 推荐卡片依据 |
| `screening_context` | 筛查/背景上下文 | 只能用于背景展示或筛查提示，不得直接作为目标疾病核心表现 |
| `cross_reference` | 跨章节引用 | 只能表达“其他章节提到本病”，不得写入目标疾病 definition、核心症状、核心治疗或诊断标准 |

历史兼容：服务器已有 `knowledge_layer=textbook_skeleton`，后续迁移时统一改为 `textbook_core`；`knowledge_layer=evidence` 按来源和用途拆分为 `textbook_core/guideline_supplement/guideline_decision`。

#### 9.5.4 章节锚点硬规则

1. `Disease.definition` 必须来自目标疾病所在章节的定义段或概述段。
2. 教材核心节点和关系必须标记 `skeleton_slot` 与 `knowledge_layer`。
3. `Disease.description` 不得使用其他疾病章节、其他系统章节或跨章节引用段落。
4. 教材关系若来自目标疾病章节外，必须标记为 `knowledge_layer=cross_reference` 或 `screening_context`，不得进入核心骨架槽位。
5. 每条教材核心关系必须同时具备：
   - `source_type=authoritative_textbook`
   - `source_section_path`
   - `skeleton_slot`
   - `knowledge_layer`
   - `pdf_page_start/pdf_page_end`；若无 PDF，则必须有等价文本定位
   - `evidence_text`
6. 禁止用文档级关键词命中替代疾病章节绑定。若目标疾病名称只出现在其他疾病段落的鉴别、病因、并发症或转引中，只能作为跨章节引用，不得写入目标疾病核心字段。

#### 9.5.5 心血管内科教材骨架扩展顺序

心血管内科本轮先以四个大类验证教材骨架方法：

1. 冠心病
2. 心肌病
3. 心力衰竭
4. 心律失常

上述四类不是最终范围，只是优先验证范围。验证通过后，执行团队必须按同一规则自行扩大到《内科学》第10版心血管内科章节中其他疾病大类和疾病，包括但不限于高血压、心脏瓣膜病、心包疾病、感染性心内膜炎、先天性心血管病、主动脉和周围血管病、心血管神经症、肿瘤心脏病学及其他心血管疾病。扩大范围不需要重新设计规则，但必须保留批次登记、来源清单和骨架槽位审计。

## 10. provenance 证据集合

同一语义关系存在多份来源时，只保留一条关系，聚合完整证据集合：

```json
{
  "provenance_records": [
    {
      "document_id": "DOC-...",
      "segment_id": "SEG-...",
      "source_name": "文献名称",
      "source_type": "guideline",
      "source_version": "2025",
      "source_section": "章节名称",
      "source_page": 12,
      "evidence_text": "原文片段",
      "recommendation_class": "I",
      "evidence_level": "A"
    }
  ]
}
```

关系同时维护：

| 字段英文名 | 中文名称 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `evidence_ids` | 证据ID列表 | String[] | 是 | 支持该关系的 Evidence 节点编码列表 |
| `document_ids` | 文档ID列表 | String[] | 是 | 证据来源文档编码列表 |
| `source_names` | 来源名称列表 | String[] | 是 | 指南、教材、共识或专家资料名称 |
| `source_types` | 来源类型列表 | String[] | 是 | `guideline`、`consensus`、`authoritative_textbook`、`expert_material` 等 |
| `evidence_count` | 证据数量 | Integer | 是 | 支持该关系的证据条数，必须等于 provenance 记录数 |
| `provenance_records_json` | 证据溯源集合 | JSON Array | 是 | 完整保存每条证据的文档、章节、页码、原文片段和分级信息 |

数组记录数、`evidence_count` 和 provenance 记录数必须一致。

## 11. 临床规则与阈值

### 11.1 ThresholdRule

必填字段：

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `indicator_code` | 指标编码 | String | 是 | 关联的 `ExamIndicator` 编码，例如 LVEF、LVOT 压差 |
| `operator` | 比较符 | Enum | 是 | `>`、`>=`、`<`、`<=`、`=`、`between` 等 |
| `value` | 阈值 | Number/String | 是 | 结构化阈值数值；区间可用数组或规范字符串 |
| `unit` | 单位 | String | 是 | mmHg、%、ms、ng/L 等 |
| `condition` | 适用条件 | String | 是 | 静息、负荷、激发、特定检查方法等条件 |
| `patient_state` | 患者状态 | String | 是 | 适用疾病、分型、人群或状态 |
| `time_context` | 时间上下文 | String | 是 | 发病后、术后、随访时、入院时等时间条件 |

示例：

```json
{
  "indicator_code": "IND-LVOT-GRADIENT",
  "operator": ">=",
  "value": 30,
  "unit": "mmHg",
  "condition": "静息或激发",
  "patient_state": "肥厚型心肌病"
}
```

### 11.2 ClinicalRule

用于多条件规则，至少保存：

| 字段英文名 | 中文名称 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `rule_type` | 规则类型 | String | 是 | 诊断规则、治疗规则、风险分层规则、禁忌规则等 |
| `if_conditions` | 前提条件 | JSON Array/String[] | 是 | 触发规则所需条件，可包含症状、检查、阈值、患者状态 |
| `then_actions` | 结论/动作 | JSON Array/String[] | 是 | 满足条件后的诊断、治疗、检查、转诊或随访建议 |
| `exceptions` | 例外条件 | JSON Array/String[] | 否 | 不适用或需排除的条件 |
| `applicability` | 适用范围 | String | 是 | 适用病种、分型、人群、场景或路径 |
| `evidence_id` | 证据ID | String | 是 | 支持该规则的 Evidence 编码 |

## 12. 专科/疾病大类配置

每个执行范围生成配置文件，至少包含：

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `scope_type` | 执行范围类型 | Enum | 是 | `specialty` 专科、`category` 疾病大类、`disease` 单病种 |
| `scope_target` | 执行范围目标 | String | 是 | 当前批次要处理的专科、大类或病种名称 |
| `specialty_code` | 专科编码 | String | 是 | 顶层专科节点编码 |
| `category_code` | 疾病大类编码 | String | 视范围而定 | 疾病大类节点编码；专科全量建设时可为空或逐行配置 |
| `disease_code` | 疾病编码 | String | 视范围而定 | 具体疾病节点编码；大类或单病种配置时必填 |
| `pathway_element` | 路径环节 | Enum | 是 | 见 §13.1 标准环节 |
| `applicability_status` | 适用性状态 | Enum | 是 | `required` 必填、`optional` 可选、`not_applicable` 不适用 |
| `reason` | 配置原因 | String | 是 | 说明为什么该环节在本范围内为必填、可选或不适用 |

配置决定闭环验收要求，但不得改变实体和关系的标准定义。

## 13. 诊疗路径闭环

### 13.1 标准环节

| 路径环节英文名 | 中文名称 | 默认适用性 | 说明 |
|---|---|---|---|
| `definition` | 定义 | required | 疾病或核心概念的权威定义 |
| `aliases` | 别名 | required | 中文别名、英文名、缩写、旧称和同义词 |
| `etiology` | 病因 | required | 导致疾病发生的原因 |
| `pathophysiology` | 发病机制/病理生理 | optional | 疾病发生发展的机制；复杂疾病可设为 required |
| `epidemiology` | 流行病学 | optional | 发病率、患病率、人群分布等 |
| `risk_factor` | 危险因素 | required | 增加疾病发生或进展风险的因素 |
| `symptom` | 症状 | required | 患者主观感受 |
| `sign` | 体征 | required | 医师客观发现 |
| `exam` | 检查 | required | 影像、生理、内镜、介入等检查 |
| `lab_test` | 实验室检验 | optional | 检验大项，如肝肾功能、心肌标志物 |
| `exam_indicator` | 检查/检验指标 | optional | 具体指标，如 LVEF、肌钙蛋白、ST 段改变 |
| `threshold_rule` | 阈值规则 | optional | 可计算的诊断、分层或治疗阈值 |
| `diagnosis_criteria` | 诊断标准 | required | 明确诊断依据或标准 |
| `differential_diagnosis` | 鉴别诊断 | required | 需要鉴别或排除的疾病/状态 |
| `classification_stage` | 分型/分期/分级 | optional | V1.1 新增；遗传病、肿瘤、心衰分型等可配置为 required |
| `risk_stratification` | 风险分层 | optional | 风险分层方案或风险等级 |
| `scoring_scale` | 评分量表 | optional | GRACE、TIMI、CHA2DS2-VASc 等评分 |
| `treatment_plan` | 治疗方案 | required | 治疗策略、治疗路径或治疗原则 |
| `medication` | 药物 | optional | 药物类别或具体药品 |
| `procedure` | 操作/手术/介入 | optional | PCI、CABG、消融、手术等 |
| `indication` | 适应证 | optional | 药物或操作适用条件 |
| `contraindication` | 禁忌证 | optional | 药物或操作禁用条件 |
| `complication` | 并发症 | required | 疾病可导致的并发症 |
| `prognosis` | 预后 | required | 结局、死亡风险、复发风险等 |
| `follow_up` | 随访 | required | 复查项目、频率、随访周期 |
| `clinical_pathway` | 诊疗路径 | optional | V1.1 新增；综合性路径容器，路径复杂时配置为 required |
| `guideline` | 指南/来源 | required | 支撑该疾病图谱的指南、教材、共识、专家资料 |
| `evidence` | 证据 | required | 可定位原文证据片段 |

> **[V1.1 说明 — classification_stage]** 此环节对应 `ClassificationStage` 实体及 `has_classification_stage` 关系。闭环审计时检查该疾病是否存在已建立的分型/分期节点。对于无标准分型的疾病，配置为 `not_applicable`。
>
> **[V1.1 说明 — clinical_pathway]** `ClinicalPathway` 作为综合性容器实体参与路径闭环审计，标注为 `optional`。对于具有明确诊疗流程图或标准路径的疾病（如 AMI/STEMI），可在专科配置层将此环节设为 `required`。

### 13.2 审计字段

```text
disease_code
pathway_element
applicability_status
coverage_status       covered | missing | not_applicable
evidence_count
source_names
missing_reason
solution
```

### 13.3 完整判定

只有所有 `required` 环节均为 `covered` 时，才能标记：

```text
closed_loop_ready=yes
closed_loop_basis=element_coverage_not_quantity_threshold
```

证据数量不能弥补必需环节缺失。

> **[V1.1 新增 — schema_gap 的闭环影响]** 若某必需路径环节的缺失原因登记为 `SCHEMA_UNSUPPORTED`（即写入了 `schema_gap_register.csv`），该环节不得标记为 `covered`，闭环状态不得标记为 `yes`，直至 Schema 修订并通过重新验收。`schema_gap` 登记本身不构成通过质量闸门的依据。

## 14. 批次与合并契约

### 14.1 批次字段

```text
batch_id
scope_type
scope_target
created_time
source_manifest_hash
schema_version
quality_gate_status
merge_status
```

### 14.2 节点合并

匹配顺序：

1. 相同全局 `code`。
2. 相同 `entityType` ＋ 规范名称。
3. 受控别名或外部标准编码确认同一实体。

无法确认时进入冲突队列，不自动合并。

### 14.3 关系合并

关系语义键：

```text
(source.code, relationType, target.code)
```

相同语义关系聚合 provenance，不建立平行重复边。

### 14.4 冲突与回滚

- 属性冲突使用 `conflict_status=open` 并写入冲突台账。
- 合并前创建标准主图谱快照。
- 合并验证失败时恢复快照。
- 每个批次保留独立、不可变的数据实例包。

## 15. 禁止关系与错误建模

禁止：

- 关系方向与标准相反。
- 使用自然语言短语作为 `relationType`。
- 使用 `entityType=DiseaseSubtype`（本 Schema 已无此类型）。
- 把 `DiseaseCategory` 复制为同名 `Disease`。
- 把并发症语义误建成独立疾病副本。
- 把药物类别和具体药品混为同一节点。
- 把教材权威性写成指南 I/A 分级。
- 把教材转引的分级文字直接填入 `recommendation_class` 字段。
- 把本机路径写入节点或关系。
- 用文档级关键词命中替代疾病章节绑定。
- 缺少原文证据仍创建核心临床关系。
- 把患者状态禁忌语义写成 `state_recommends_*` 正向关系。
- 对同一药物相互作用混用直接药物对建模和 DrugInteraction 节点建模。

## 16. 数据实例硬闸门

正式数据实例必须满足：

- 未知 `entityType` 数量为 0（包含已废弃的 `DiseaseSubtype`）。
- 未知 `relationType` 数量为 0。
- 错误关系方向数量为 0。
- 重复 `code` 数量为 0。
- 同类型同名重复实体数量为 0。
- 悬空关系数量为 0。
- 重复语义关系数量为 0。
- 本机路径污染数量为 0。
- Unicode 替换字符和典型错码数量为 0。
- 核心临床关系证据链完整率为 100%。
- 关系目标名称/别名在证据分段命中率为 100%。
- Definition 与目标疾病相关性命中率为 100%。
- 跨疾病来源污染数量为 0。
- `disease_definition_empty_count=0`：scope 内所有正式疾病必须有 `definition`。
- `disease_definition_source_mismatch_count=0`：疾病定义必须来自目标疾病章节定义/概述段，不得来自其他疾病、其他章节或跨章节引用。
- `description_cross_chapter_pollution_count=0`：`Disease.description` 不得命中其他疾病章节、其他系统章节、鉴别引用段或并发症引用段。
- `textbook_core_without_skeleton_slot_count=0`：`source_type=authoritative_textbook` 且用于教材核心骨架的节点/关系必须有 `skeleton_slot`。
- `textbook_core_without_knowledge_layer_count=0`：教材核心关系必须有 `knowledge_layer=textbook_core`；筛查背景和跨章节引用不得伪装为核心骨架。
- `textbook_source_anchor_missing_count=0`：教材核心证据必须有 `source_section_path` 和可定位页码/文本锚点。
- 教材伪装正式指南分级数量为 0（`source_type=authoritative_textbook` 记录中 `recommendation_class ≠ N/A` 的数量为 0）。
- 必需环节缺口均有原因和解决方案。
- **[V1.1 新增]** `schema_gap_register.csv` 中存在未解决条目且涉及 `required` 路径环节的批次，`quality_gate_status` 不得标记为 `passed`。
- **[V1.1 新增]** 患者状态否定语义（禁忌）使用 `state_contraindicates_*` 或 `has_contraindication` 表达，`state_recommends_*` 关系中 `polarity=negative` 的记录数为 0（此写法已废弃）。
- **[V1.5 新增]** 疾病不得直接连接“鉴别诊断”“诊断标准”“药物治疗”“一般治疗”“预后良好/不良”“定期随访”“危险分层”等通用语义空壳节点；必须抽取具体对象或具体规则。
- **[V1.5 新增]** 药物类别 aliases 不得包含具体药物、英文缩写或治疗动作词；具体药物必须独立建 `Medication` 节点，并通过 `has_specific_medication` 连接。
- **[V1.5 新增]** 正式 CDSS 推荐层硬门槛：scope 内所有疾病 required 缺口为 0；治疗推荐至少覆盖 ClinicalRule/Indication/Contraindication/ClinicalPathway；所有推荐必须有适用人群、排除条件、证据来源、推荐等级和 `clinical_review_status=clinical_approved`；药物必须有标准名、别名、剂量、禁忌证、相互作用字段。未临床审核的节点和关系可进入测试图谱，但不得进入正式 CDSS 推荐层。
- **[V1.6 新增]** 结构可用性硬闸门：`technical_display_name_error_count=0`、`treatment_plan_actionability_error_count=0`、`medication_class_without_specific_count=0`、`duplicate_semantic_relation_count=0`。截图、前端或审核统计中出现“同一疾病下同一药物/检查/治疗节点重复计数”，必须判定为视图去重或关系语义键去重失败，先修复再交付。

## 17. Neo4j 导入标准

数据实例验收通过并获得用户确认后才允许导入。

节点写入：

```cypher
MERGE (n:KGNode:`实体类型` {code: $code})
SET n += $properties,
    n.primary_label = 'KGNode',
    n.type_label = $entityType,
    n.canonical_labels = ['KGNode', $entityType]
```

规则：

- `code` 建立唯一约束。
- 目录、临床和证据节点必须带 `KGNode` 主标签，可增加辅助类型标签，但 `entityType` 只有一个标准值。
- 禁止创建只带 `Disease`、`TreatmentPlan`、`DiagnosisCriteria` 等类型标签而不带 `KGNode` 的节点；此类节点不属于标准图谱，可绕过质量审计，必须阻断交付。
- 关系按语义键去重后创建。
- 多批次合并后必须在服务器执行关系语义键去重；同一 `(source.code, relationType, target.code)` 只允许保留一条关系，来源差异应合并到 provenance 或审计字段，不得生成重复边。
- 前端图谱接口必须按节点 `code` 去重构造节点集合；关系集合可保留多条路径，但实体数量、维度节点数量和截图统计必须使用唯一节点数。
- 导入前备份，导入后执行全库质量审计。必须满足 `all_node_count == kg_node_count`、`all_relation_count == kg_relation_count`、`non_kgnode_node_count=0`、`relation_touching_non_kgnode_count=0`。
- 禁止用完整属性集合 `MERGE` 节点。

## 18. 标准交付文件

每个批次至少交付：

```text
scope_taxonomy.csv
source_documents_manifest.csv
dedup_index.csv                    [V1.1 新增]
source_folder_summary.csv          [V1.1 新增]
page_audit.jsonl
document_quality_audit.csv
segment_index.jsonl
textbook_skeleton_matrix.csv        [V1.11 新增，教材骨架槽位覆盖矩阵]
textbook_chapter_anchor_audit.csv   [V1.11 新增，教材章节锚点与污染审计]
nodes_final.jsonl
nodes_final.csv
relations_final.jsonl
relations_final.csv
graph_final.json
disease_pathway_coverage.csv
missing_reason_and_solution.csv
source_conflict_register.csv       [V1.1 补入主清单]
schema_gap_register.csv
quality_gate_summary.json
专家审核说明.md
```

正式节点和关系不得包含本地路径；本地路径只允许存在于执行清单和审计日志。

## 19. 专病 CDSS 动态流程引擎映射

### 19.1 白话解释

专科知识图谱不是让前端或 Oracle 一次性把某个疾病下所有检查、检验、药物、手术、鉴别诊断全部圈出来。图谱应作为医学规则来源，供专病流程引擎按患者当前状态实时调用。

标准调用链：

```text
EMR/业务系统事件
  -> 流程引擎读取患者当前数据
  -> 流程引擎查询图谱中的 ClinicalPathway / PathwayStage / ClinicalRule
  -> 计算当前阶段、已满足条件、缺失条件、阻断原因
  -> 返回当前可执行推荐、暂不推荐项目和证据链
  -> 前端展示给医生并记录医生反馈
```

### 19.2 图谱维护什么

图谱必须维护以下医学知识：

| 内容 | 推荐实体/字段 | 示例 |
|---|---|---|
| 专病路径 | `ClinicalPathway` | 急性心肌梗死诊疗路径 |
| 诊疗阶段 | `PathwayStage` | 疑诊评估、诊断确认、再灌注决策、抗栓治疗、二级预防 |
| 阶段顺序 | `next_pathway_stage` | 诊断确认 → 再灌注决策 |
| 阶段规则 | `ClinicalRule` | STEMI 溶栓适应证规则 |
| 条件文本 | `if_conditions`、`condition_text` | STEMI、发病≤12小时、PCI不可及时、无溶栓禁忌证 |
| 推荐陈述 | `RecommendationStatement` | “STEMI且发病≤12小时，优先评估急诊PCI可及性” |
| 推荐动作 | `RecommendationStatement -> recommends_action` | 急诊PCI、溶栓治疗、肌钙蛋白检测 |
| 阻断动作 | `RecommendationStatement -> blocks_action` | 可疑主动脉夹层阻断溶栓 |
| 证据链 | `RecommendationStatement -> derived_from` | 指南、页码、推荐等级、证据等级 |

### 19.3 流程引擎维护什么

以下内容不属于医学知识图谱主体，不应作为标准图谱关系硬编码：

| 内容 | 所属层 | 示例 |
|---|---|---|
| EMR字段映射 | 流程引擎/集成层 | 主诉字段、主诊断字段、心电图报告字段、检验结果字段 |
| 系统事件 | 流程引擎 | 主诊断保存、检验回报、医嘱提交、过敏史更新 |
| 当前患者阶段 | 流程引擎运行态 | 当前处于“再灌注决策阶段” |
| 是否弹窗/提醒/置顶 | 前端/流程引擎 | 高危提醒、静默提示、知识展示 |
| 医生反馈 | 业务系统 | 采纳、忽略、暂不处理、原因 |

### 19.4 AMI 示例

图谱表达：

```text
Disease: ST段抬高型心肌梗死
  has_clinical_pathway -> ClinicalPathway: STEMI诊疗路径
ClinicalPathway
  has_pathway_stage -> PathwayStage: 再灌注决策阶段
PathwayStage
  has_stage_rule -> ClinicalRule: STEMI再灌注策略选择规则
ClinicalRule
  if_conditions:
    - 确诊或高度疑似STEMI
    - 发病时间≤12小时
    - 评估PCI可及性
    - 排除溶栓禁忌证
  has_recommendation_statement -> RecommendationStatement: STEMI急诊PCI推荐陈述
RecommendationStatement
  statement_summary: STEMI且发病≤12小时，优先评估急诊PCI可及性
  recommendation_class: I
  evidence_level: A
  recommends_action -> Procedure: 急诊PCI
  based_on_guideline -> Guideline: STEMI ESC 2017
  derived_from -> Evidence: STEMI ESC 2017 第48页
```

流程引擎执行：

```text
事件：心电图结果返回 / 主诊断保存 / 发病时间录入
读取：主诊断、发病时间、心电图、肌钙蛋白、禁忌证、PCI可及性
判断：当前是否满足再灌注决策阶段条件
输出：
  - 当前阶段：再灌注决策
  - 已满足：STEMI、发病≤12小时
  - 缺失：PCI预计时间、溶栓禁忌证评估
  - 推荐：补充PCI可及性和禁忌证评估
  - 暂不推荐：直接溶栓
  - 原因：主动脉夹层/出血风险未排除
  - 证据：直接读取 RecommendationStatement 的指南、页码、推荐等级、证据等级
```

### 19.5 CDSS 应用硬规则

- CDSS 推荐不得等同于“疾病下所有关联节点”。
- 进入 CDSS 推荐层的动作必须通过 `PathwayStage + ClinicalRule + Evidence` 组合表达。
- 推荐动作必须区分：立即推荐、条件满足后推荐、缺资料暂缓、禁忌阻断、仅知识展示。
- 前端必须展示推荐原因、缺失条件、禁忌/排除条件和证据来源。
- 如果只查到诊断标准、治疗方案或药物标题，缺少条件、动作明细和证据链，不得作为可执行 CDSS 推荐。

## 10. provenance 证据集合

同一语义关系存在多份来源时，只保留一条关系，聚合完整证据集合：

```json
{
  "provenance_records": [
    {
      "document_id": "DOC-...",
      "segment_id": "SEG-...",
      "source_name": "文献名称",
      "source_type": "guideline",
      "source_version": "2025",
      "source_section": "章节名称",
      "source_page": 12,
      "evidence_text": "原文片段",
      "recommendation_class": "I",
      "evidence_level": "A"
    }
  ]
}
```

关系同时维护：

| 字段英文名 | 中文名称 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `evidence_ids` | 证据ID列表 | String[] | 是 | 支持该关系的 Evidence 节点编码列表 |
| `document_ids` | 文档ID列表 | String[] | 是 | 证据来源文档编码列表 |
| `source_names` | 来源名称列表 | String[] | 是 | 指南、教材、共识或专家资料名称 |
| `source_types` | 来源类型列表 | String[] | 是 | `guideline`、`consensus`、`authoritative_textbook`、`expert_material` 等 |
| `evidence_count` | 证据数量 | Integer | 是 | 支持该关系的证据条数，必须等于 provenance 记录数 |
| `provenance_records_json` | 证据溯源集合 | JSON Array | 是 | 完整保存每条证据的文档、章节、页码、原文片段和分级信息 |

数组记录数、`evidence_count` 和 provenance 记录数必须一致。

## 11. 临床规则与阈值

### 11.1 ThresholdRule

必填字段：

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `indicator_code` | 指标编码 | String | 是 | 关联的 `ExamIndicator` 编码，例如 LVEF、LVOT 压差 |
| `operator` | 比较符 | Enum | 是 | `>`、`>=`、`<`、`<=`、`=`、`between` 等 |
| `value` | 阈值 | Number/String | 是 | 结构化阈值数值；区间可用数组或规范字符串 |
| `unit` | 单位 | String | 是 | mmHg、%、ms、ng/L 等 |
| `condition` | 适用条件 | String | 是 | 静息、负荷、激发、特定检查方法等条件 |
| `patient_state` | 患者状态 | String | 是 | 适用疾病、分型、人群或状态 |
| `time_context` | 时间上下文 | String | 是 | 发病后、术后、随访时、入院时等时间条件 |

示例：

```json
{
  "indicator_code": "IND-LVOT-GRADIENT",
  "operator": ">=",
  "value": 30,
  "unit": "mmHg",
  "condition": "静息或激发",
  "patient_state": "肥厚型心肌病"
}
```

### 11.2 ClinicalRule

用于多条件规则，至少保存：

| 字段英文名 | 中文名称 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `rule_type` | 规则类型 | String | 是 | 诊断规则、治疗规则、风险分层规则、禁忌规则等 |
| `if_conditions` | 前提条件 | JSON Array/String[] | 是 | 触发规则所需条件，可包含症状、检查、阈值、患者状态 |
| `then_actions` | 结论/动作 | JSON Array/String[] | 是 | 满足条件后的诊断、治疗、检查、转诊或随访建议 |
| `exceptions` | 例外条件 | JSON Array/String[] | 否 | 不适用或需排除的条件 |
| `applicability` | 适用范围 | String | 是 | 适用病种、分型、人群、场景或路径 |
| `evidence_id` | 证据ID | String | 是 | 支持该规则的 Evidence 编码 |

## 12. 专科/疾病大类配置

每个执行范围生成配置文件，至少包含：

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `scope_type` | 执行范围类型 | Enum | 是 | `specialty` 专科、`category` 疾病大类、`disease` 单病种 |
| `scope_target` | 执行范围目标 | String | 是 | 当前批次要处理的专科、大类或病种名称 |
| `specialty_code` | 专科编码 | String | 是 | 顶层专科节点编码 |
| `category_code` | 疾病大类编码 | String | 视范围而定 | 疾病大类节点编码；专科全量建设时可为空或逐行配置 |
| `disease_code` | 疾病编码 | String | 视范围而定 | 具体疾病节点编码；大类或单病种配置时必填 |
| `pathway_element` | 路径环节 | Enum | 是 | 见 §13.1 标准环节 |
| `applicability_status` | 适用性状态 | Enum | 是 | `required` 必填、`optional` 可选、`not_applicable` 不适用 |
| `reason` | 配置原因 | String | 是 | 说明为什么该环节在本范围内为必填、可选或不适用 |

配置决定闭环验收要求，但不得改变实体和关系的标准定义。

## 13. 诊疗路径闭环

### 13.1 标准环节

| 路径环节英文名 | 中文名称 | 默认适用性 | 说明 |
|---|---|---|---|
| `definition` | 定义 | required | 疾病或核心概念的权威定义 |
| `aliases` | 别名 | required | 中文别名、英文名、缩写、旧称和同义词 |
| `etiology` | 病因 | required | 导致疾病发生的原因 |
| `pathophysiology` | 发病机制/病理生理 | optional | 疾病发生发展的机制；复杂疾病可设为 required |
| `epidemiology` | 流行病学 | optional | 发病率、患病率、人群分布等 |
| `risk_factor` | 危险因素 | required | 增加疾病发生或进展风险的因素 |
| `symptom` | 症状 | required | 患者主观感受 |
| `sign` | 体征 | required | 医师客观发现 |
| `exam` | 检查 | required | 影像、生理、内镜、介入等检查 |
| `lab_test` | 实验室检验 | optional | 检验大项，如肝肾功能、心肌标志物 |
| `exam_indicator` | 检查/检验指标 | optional | 具体指标，如 LVEF、肌钙蛋白、ST 段改变 |
| `threshold_rule` | 阈值规则 | optional | 可计算的诊断、分层或治疗阈值 |
| `diagnosis_criteria` | 诊断标准 | required | 明确诊断依据或标准 |
| `differential_diagnosis` | 鉴别诊断 | required | 需要鉴别或排除的疾病/状态 |
| `classification_stage` | 分型/分期/分级 | optional | V1.1 新增；遗传病、肿瘤、心衰分型等可配置为 required |
| `risk_stratification` | 风险分层 | optional | 风险分层方案或风险等级 |
| `scoring_scale` | 评分量表 | optional | GRACE、TIMI、CHA2DS2-VASc 等评分 |
| `treatment_plan` | 治疗方案 | required | 治疗策略、治疗路径或治疗原则 |
| `medication` | 药物 | optional | 药物类别或具体药品 |
| `procedure` | 操作/手术/介入 | optional | PCI、CABG、消融、手术等 |
| `indication` | 适应证 | optional | 药物或操作适用条件 |
| `contraindication` | 禁忌证 | optional | 药物或操作禁用条件 |
| `complication` | 并发症 | required | 疾病可导致的并发症 |
| `prognosis` | 预后 | required | 结局、死亡风险、复发风险等 |
| `follow_up` | 随访 | required | 复查项目、频率、随访周期 |
| `clinical_pathway` | 诊疗路径 | optional | V1.1 新增；综合性路径容器，路径复杂时配置为 required |
| `guideline` | 指南/来源 | required | 支撑该疾病图谱的指南、教材、共识、专家资料 |
| `evidence` | 证据 | required | 可定位原文证据片段 |

> **[V1.1 说明 — classification_stage]** 此环节对应 `ClassificationStage` 实体及 `has_classification_stage` 关系。闭环审计时检查该疾病是否存在已建立的分型/分期节点。对于无标准分型的疾病，配置为 `not_applicable`。
>
> **[V1.1 说明 — clinical_pathway]** `ClinicalPathway` 作为综合性容器实体参与路径闭环审计，标注为 `optional`。对于具有明确诊疗流程图或标准路径的疾病（如 AMI/STEMI），可在专科配置层将此环节设为 `required`。

### 13.2 审计字段

```text
disease_code
pathway_element
applicability_status
coverage_status       covered | missing | not_applicable
evidence_count
source_names
missing_reason
solution
```

### 13.3 完整判定

只有所有 `required` 环节均为 `covered` 时，才能标记：

```text
closed_loop_ready=yes
closed_loop_basis=element_coverage_not_quantity_threshold
```

证据数量不能弥补必需环节缺失。

> **[V1.1 新增 — schema_gap 的闭环影响]** 若某必需路径环节的缺失原因登记为 `SCHEMA_UNSUPPORTED`（即写入了 `schema_gap_register.csv`），该环节不得标记为 `covered`，闭环状态不得标记为 `yes`，直至 Schema 修订并通过重新验收。`schema_gap` 登记本身不构成通过质量闸门的依据。

## 14. 批次与合并契约

### 14.1 批次字段

```text
batch_id
scope_type
scope_target
created_time
source_manifest_hash
schema_version
quality_gate_status
merge_status
```

### 14.2 节点合并

匹配顺序：

1. 相同全局 `code`。
2. 相同 `entityType` ＋ 规范名称。
3. 受控别名或外部标准编码确认同一实体。

无法确认时进入冲突队列，不自动合并。

### 14.3 关系合并

关系语义键：

```text
(source.code, relationType, target.code)
```

相同语义关系聚合 provenance，不建立平行重复边。

### 14.4 冲突与回滚

- 属性冲突使用 `conflict_status=open` 并写入冲突台账。
- 合并前创建标准主图谱快照。
- 合并验证失败时恢复快照。
- 每个批次保留独立、不可变的数据实例包。

## 15. 禁止关系与错误建模

禁止：

- 关系方向与标准相反。
- 使用自然语言短语作为 `relationType`。
- 使用 `entityType=DiseaseSubtype`（本 Schema 已无此类型）。
- 把 `DiseaseCategory` 复制为同名 `Disease`。
- 把并发症语义误建成独立疾病副本。
- 把药物类别和具体药品混为同一节点。
- 把教材权威性写成指南 I/A 分级。
- 把教材转引的分级文字直接填入 `recommendation_class` 字段。
- 把本机路径写入节点或关系。
- 用文档级关键词命中替代疾病章节绑定。
- 缺少原文证据仍创建核心临床关系。
- 把患者状态禁忌语义写成 `state_recommends_*` 正向关系。
- 对同一药物相互作用混用直接药物对建模和 DrugInteraction 节点建模。

## 16. 数据实例硬闸门

正式数据实例必须满足：

- 未知 `entityType` 数量为 0（包含已废弃的 `DiseaseSubtype`）。
- 未知 `relationType` 数量为 0。
- 错误关系方向数量为 0。
- 重复 `code` 数量为 0。
- 同类型同名重复实体数量为 0。
- 悬空关系数量为 0。
- 重复语义关系数量为 0。
- 本机路径污染数量为 0。
- Unicode 替换字符和典型错码数量为 0。
- 核心临床关系证据链完整率为 100%。
- 关系目标名称/别名在证据分段命中率为 100%。
- Definition 与目标疾病相关性命中率为 100%。
- 跨疾病来源污染数量为 0。
- `disease_definition_empty_count=0`：scope 内所有正式疾病必须有 `definition`。
- `disease_definition_source_mismatch_count=0`：疾病定义必须来自目标疾病章节定义/概述段，不得来自其他疾病、其他章节或跨章节引用。
- `description_cross_chapter_pollution_count=0`：`Disease.description` 不得命中其他疾病章节、其他系统章节、鉴别引用段或并发症引用段。
- `textbook_core_without_skeleton_slot_count=0`：`source_type=authoritative_textbook` 且用于教材核心骨架的节点/关系必须有 `skeleton_slot`。
- `textbook_core_without_knowledge_layer_count=0`：教材核心关系必须有 `knowledge_layer=textbook_core`；筛查背景和跨章节引用不得伪装为核心骨架。
- `textbook_source_anchor_missing_count=0`：教材核心证据必须有 `source_section_path` 和可定位页码/文本锚点。
- 教材伪装正式指南分级数量为 0（`source_type=authoritative_textbook` 记录中 `recommendation_class ≠ N/A` 的数量为 0）。
- 必需环节缺口均有原因和解决方案。
- **[V1.1 新增]** `schema_gap_register.csv` 中存在未解决条目且涉及 `required` 路径环节的批次，`quality_gate_status` 不得标记为 `passed`。
- **[V1.1 新增]** 患者状态否定语义（禁忌）使用 `state_contraindicates_*` 或 `has_contraindication` 表达，`state_recommends_*` 关系中 `polarity=negative` 的记录数为 0（此写法已废弃）。
- **[V1.5 新增]** 疾病不得直接连接“鉴别诊断”“诊断标准”“药物治疗”“一般治疗”“预后良好/不良”“定期随访”“危险分层”等通用语义空壳节点；必须抽取具体对象或具体规则。
- **[V1.5 新增]** 药物类别 aliases 不得包含具体药物、英文缩写或治疗动作词；具体药物必须独立建 `Medication` 节点，并通过 `has_specific_medication` 连接。
- **[V1.5 新增]** 正式 CDSS 推荐层硬门槛：scope 内所有疾病 required 缺口为 0；治疗推荐至少覆盖 ClinicalRule/Indication/Contraindication/ClinicalPathway；所有推荐必须有适用人群、排除条件、证据来源、推荐等级和 `clinical_review_status=clinical_approved`；药物必须有标准名、别名、剂量、禁忌证、相互作用字段。未临床审核的节点和关系可进入测试图谱，但不得进入正式 CDSS 推荐层。
- **[V1.6 新增]** 结构可用性硬闸门：`technical_display_name_error_count=0`、`treatment_plan_actionability_error_count=0`、`medication_class_without_specific_count=0`、`duplicate_semantic_relation_count=0`。截图、前端或审核统计中出现“同一疾病下同一药物/检查/治疗节点重复计数”，必须判定为视图去重或关系语义键去重失败，先修复再交付。

## 17. Neo4j 导入标准

数据实例验收通过并获得用户确认后才允许导入。

节点写入：

```cypher
MERGE (n:KGNode:`实体类型` {code: $code})
SET n += $properties,
    n.primary_label = 'KGNode',
    n.type_label = $entityType,
    n.canonical_labels = ['KGNode', $entityType]
```

规则：

- `code` 建立唯一约束。
- 目录、临床和证据节点必须带 `KGNode` 主标签，可增加辅助类型标签，但 `entityType` 只有一个标准值。
- 禁止创建只带 `Disease`、`TreatmentPlan`、`DiagnosisCriteria` 等类型标签而不带 `KGNode` 的节点；此类节点不属于标准图谱，可绕过质量审计，必须阻断交付。
- 关系按语义键去重后创建。
- 多批次合并后必须在服务器执行关系语义键去重；同一 `(source.code, relationType, target.code)` 只允许保留一条关系，来源差异应合并到 provenance 或审计字段，不得生成重复边。
- 前端图谱接口必须按节点 `code` 去重构造节点集合；关系集合可保留多条路径，但实体数量、维度节点数量和截图统计必须使用唯一节点数。
- 导入前备份，导入后执行全库质量审计。必须满足 `all_node_count == kg_node_count`、`all_relation_count == kg_relation_count`、`non_kgnode_node_count=0`、`relation_touching_non_kgnode_count=0`。
- 禁止用完整属性集合 `MERGE` 节点。

## 18. 标准交付文件

每个批次至少交付：

```text
scope_taxonomy.csv
source_documents_manifest.csv
dedup_index.csv                    [V1.1 新增]
source_folder_summary.csv          [V1.1 新增]
page_audit.jsonl
document_quality_audit.csv
segment_index.jsonl
textbook_skeleton_matrix.csv        [V1.11 新增，教材骨架槽位覆盖矩阵]
textbook_chapter_anchor_audit.csv   [V1.11 新增，教材章节锚点与污染审计]
nodes_final.jsonl
nodes_final.csv
relations_final.jsonl
relations_final.csv
graph_final.json
disease_pathway_coverage.csv
missing_reason_and_solution.csv
source_conflict_register.csv       [V1.1 补入主清单]
schema_gap_register.csv
quality_gate_summary.json
专家审核说明.md
```

正式节点和关系不得包含本地路径；本地路径只允许存在于执行清单和审计日志。

## 19. 专病 CDSS 动态流程引擎映射

### 19.1 白话解释

专科知识图谱不是让前端或 Oracle 一次性把某个疾病下所有检查、检验、药物、手术、鉴别诊断全部圈出来。图谱应作为医学规则来源，供专病流程引擎按患者当前状态实时调用。

标准调用链：

```text
EMR/业务系统事件
  -> 流程引擎读取患者当前数据
  -> 流程引擎查询图谱中的 ClinicalPathway / PathwayStage / ClinicalRule
  -> 计算当前阶段、已满足条件、缺失条件、阻断原因
  -> 返回当前可执行推荐、暂不推荐项目和证据链
  -> 前端展示给医生并记录医生反馈
```

### 19.2 图谱维护什么

图谱必须维护以下医学知识：

| 内容 | 推荐实体/字段 | 示例 |
|---|---|---|
| 专病路径 | `ClinicalPathway` | 急性心肌梗死诊疗路径 |
| 诊疗阶段 | `PathwayStage` | 疑诊评估、诊断确认、再灌注决策、抗栓治疗、二级预防 |
| 阶段顺序 | `next_pathway_stage` | 诊断确认 → 再灌注决策 |
| 阶段规则 | `ClinicalRule` | STEMI 溶栓适应证规则 |
| 条件文本 | `if_conditions`、`condition_text` | STEMI、发病≤12小时、PCI不可及时、无溶栓禁忌证 |
| 推荐陈述 | `RecommendationStatement` | “STEMI且发病≤12小时，优先评估急诊PCI可及性” |
| 推荐动作 | `RecommendationStatement -> recommends_action` | 急诊PCI、溶栓治疗、肌钙蛋白检测 |
| 阻断动作 | `RecommendationStatement -> blocks_action` | 可疑主动脉夹层阻断溶栓 |
| 证据链 | `RecommendationStatement -> derived_from` | 指南、页码、推荐等级、证据等级 |

### 19.3 流程引擎维护什么

以下内容不属于医学知识图谱主体，不应作为标准图谱关系硬编码：

| 内容 | 所属层 | 示例 |
|---|---|---|
| EMR字段映射 | 流程引擎/集成层 | 主诉字段、主诊断字段、心电图报告字段、检验结果字段 |
| 系统事件 | 流程引擎 | 主诊断保存、检验回报、医嘱提交、过敏史更新 |
| 当前患者阶段 | 流程引擎运行态 | 当前处于“再灌注决策阶段” |
| 是否弹窗/提醒/置顶 | 前端/流程引擎 | 高危提醒、静默提示、知识展示 |
| 医生反馈 | 业务系统 | 采纳、忽略、暂不处理、原因 |

### 19.4 AMI 示例

图谱表达：

```text
Disease: ST段抬高型心肌梗死
  has_clinical_pathway -> ClinicalPathway: STEMI诊疗路径
ClinicalPathway
  has_pathway_stage -> PathwayStage: 再灌注决策阶段
PathwayStage
  has_stage_rule -> ClinicalRule: STEMI再灌注策略选择规则
ClinicalRule
  if_conditions:
    - 确诊或高度疑似STEMI
    - 发病时间≤12小时
    - 评估PCI可及性
    - 排除溶栓禁忌证
  has_recommendation_statement -> RecommendationStatement: STEMI急诊PCI推荐陈述
RecommendationStatement
  statement_summary: STEMI且发病≤12小时，优先评估急诊PCI可及性
  recommendation_class: I
  evidence_level: A
  recommends_action -> Procedure: 急诊PCI
  based_on_guideline -> Guideline: STEMI ESC 2017
  derived_from -> Evidence: STEMI ESC 2017 第48页
```

流程引擎执行：

```text
事件：心电图结果返回 / 主诊断保存 / 发病时间录入
读取：主诊断、发病时间、心电图、肌钙蛋白、禁忌证、PCI可及性
判断：当前是否满足再灌注决策阶段条件
输出：
  - 当前阶段：再灌注决策
  - 已满足：STEMI、发病≤12小时
  - 缺失：PCI预计时间、溶栓禁忌证评估
  - 推荐：补充PCI可及性和禁忌证评估
  - 暂不推荐：直接溶栓
  - 原因：主动脉夹层/出血风险未排除
  - 证据：直接读取 RecommendationStatement 的指南、页码、推荐等级、证据等级
```

### 19.5 CDSS 应用硬规则

- CDSS 推荐不得等同于“疾病下所有关联节点”。
- 进入 CDSS 推荐层的动作必须通过 `PathwayStage + ClinicalRule + Evidence` 组合表达。
- 推荐动作必须区分：立即推荐、条件满足后推荐、缺资料暂缓、禁忌阻断、仅知识展示。
- 前端必须展示推荐原因、缺失条件、禁忌/排除条件和证据来源。
- 如果只查到诊断标准、治疗方案或药物标题，缺少条件、动作明细和证据链，不得作为可执行 CDSS 推荐。
