# 专科知识图谱 Schema 标准

版本：V1.7
状态：正式执行标准
适用范围：所有专科、疾病大类和单病种知识图谱数据实例。
变更说明：基于 V1.0 审核报告修订，修复 P0×3、P1×3、P2×3 共 9 项问题。

## 变更记录

变更记录时间必须精确到秒，格式统一为 `YYYY-MM-DD HH:mm:ss`。历史记录若原始记录仅精确到月份，不得伪造真实发生时间，应标注为“历史补录”。

| 版本 | 变更时间 | 变更类型 | 涉及章节 | 说明 |
|---|---|---|---|---|
| V1.0 | — | 初版 | 全文 | 正式执行标准 |
| V1.1 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | P0修复 | §4.4、§7.6、§13.1 | 补充 ClassificationStage 实体；补充患者状态否定语义关系；classification_stage 纳入闭环路径 |
| V1.1 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | P0修复 | §4 说明 | 显式注明本 Schema 无 DiseaseSubtype |
| V1.1 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | P1修复 | §9.3、§13.1 | 补充教材转引指南分级的处理规则 |
| V1.1 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | P1修复 | §16 | 硬闸门补充 schema_gap 未解决不得标记 covered |
| V1.1 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | P1修复 | §13.1、§4.5 | ClinicalPathway 纳入闭环路径审计，标注 optional |
| V1.1 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | P2修复 | §18 | 交付清单补充 source_conflict_register、dedup_index、source_folder_summary |
| V1.1 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | P2修复 | §7.5 | DrugInteraction 建模歧义消除，补充注释 |
| V1.1 | 2026-06-24 09:03:11 | 记录规范 | 变更记录 | 变更记录日期统一升级为精确到秒的变更时间；后续 Schema 变更、批次台账和交付记录不得只记录到月份 |
| V1.2 | 2026-06-25 09:18:00 | 可读性增强 | §5.2、§5.3、§7.1、§11、§12、§13.1 | 统一字段说明格式，保留英文技术字段名，同时增加中文名称、类型/枚举、是否必填和临床/数据含义说明，避免标准文档出现纯英文清单 |
| V1.3 | 2026-06-25 09:51:49 | 可读性增强 | §7.2–§7.7、§8、§9 | 标准关系表统一增加中文名称、关系方向和用途说明；关系通用字段、Guideline、Evidence 和教材来源字段改为中英对照表，解决多处纯英文字段清单问题 |
| V1.4 | 2026-06-25 10:03:10 | 可读性增强 | §9 | 新增 Guideline 与 Evidence 的白话解释、差异对照和示例，明确 Guideline 是来源文献/资料，Evidence 是从来源中抽取的可追溯原文证据片段 |
| V1.5 | 2026-06-26 15:24:02 | 质量闸门与药物建模修复 | §7.5、§13、§16 | 新增 `Medication -> has_specific_medication -> Medication`，用于药物类别到具体药物的类别-实例关系；明确药物类别 aliases 不得存放具体药物、英文缩写或治疗动作词；正式 CDSS 推荐层必须具备 clinical_review_status 与推荐闭环字段 |
| V1.6 | 2026-06-27 00:28:13 | 可执行图谱与视图去重修复 | §7.5、§13、§16、§17 | 明确治疗方案必须有下游药物/操作/时机/路径；疾病级总治疗方案不得复制全部药物；前端和审核统计必须按 `KGNode.code` 统计唯一节点；服务器合并后必须按 `(source.code, relationType, target.code)` 去重关系；技术编码不得作为临床显示名 |
| V1.7 | 2026-06-27 21:46:59 | Neo4j 标签契约修复 | §16、§17 | 新增全库 `KGNode` 契约硬闸门：所有临床、目录和证据节点必须带 `KGNode` 主标签；禁止外部修复脚本创建非 `KGNode` 临床节点；服务器验收必须满足非 `KGNode` 节点数=0、触达非 `KGNode` 的关系数=0 |

---

## 1. 设计目标

本标准把指南、共识、教材和经确认的专家资料转化为可检索、可推理、可审核和可增量合并的知识图谱。

核心诊疗路径：

```text
专科与疾病目录
  -> 疾病定义与基础医学知识
  -> 症状/体征
  -> 检查/检验/指标/阈值
  -> 诊断/鉴别诊断/风险分层
  -> 治疗方案/药物/操作/条件
  -> 并发症/预后/随访
  -> 指南/教材/专家证据
```

## 2. 三层架构

### 2.1 统一核心层

定义所有专科共享的实体、关系、字段、编码和证据契约。核心层不得包含只适用于单一疾病的专用字段。

### 2.2 专科/疾病大类配置层

配置当前范围内每个诊疗模块的：

```text
required | optional | not_applicable
```

示例：心肌病大类可将遗传检测、心脏磁共振、家族筛查和猝死风险评估配置为 required 或 optional。

配置层控制抽取和验收，不创建额外临床图谱层。

### 2.3 单病种规则层

使用 `ClinicalRule`、`ThresholdRule`、适用人群、时间条件和证据表达疾病特异语义。

示例：

- 肥厚型心肌病的 LVOT 梗阻阈值
- 急性心肌梗死的再灌注时间窗
- 心力衰竭的 LVEF 分型条件

## 3. 疾病目录骨架

统一层级：

```text
Specialty
  -> DiseaseCategory
    -> DiseaseSubcategory
      -> Disease
```

规则：

- `Specialty` 是根节点。
- 除根节点外，目录节点必须有 `parentCode`。
- 每个 `Disease` 必须可追溯到 `Specialty`。
- 同一临床疾病只建立一个 canonical `Disease`。
- 多分类视角使用关系表达，不复制疾病节点。
- 每个疾病必须有且仅有一个主 `belongs_to_subcategory` 关系；其他分类使用 secondary 关系。

> **[V1.1 新增说明]** 本 Schema 不存在 `DiseaseSubtype` 实体类型。疾病亚型统一使用 `DiseaseSubcategory` 节点表示目录层级，或使用 `ClassificationStage` 节点表示分型/分期语义，通过关系与 `Disease` 连接。执行工具中不得出现 `entityType=DiseaseSubtype`，否则触发硬闸门失败。

## 4. 标准实体类型

### 4.1 目录与疾病

| entityType | 用途 |
|---|---|
| `Specialty` | 专科 |
| `DiseaseCategory` | 疾病大类 |
| `DiseaseSubcategory` | 疾病亚类（含目录层级的疾病亚型） |
| `Disease` | 规范疾病实体 |

### 4.2 临床表现与基础医学

| entityType | 用途 |
|---|---|
| `Symptom` | 患者主观症状 |
| `Sign` | 客观体征 |
| `Etiology` | 病因 |
| `Pathophysiology` | 病理生理机制 |
| `Epidemiology` | 流行病学特征 |
| `RiskFactor` | 危险因素 |
| `Complication` | 并发症 |
| `Prognosis` | 预后 |

### 4.3 检查与检验

| entityType | 用途 | 示例 |
|---|---|---|
| `Exam` | 影像、生理、介入等检查项目 | 心电图、超声心动图、冠脉造影 |
| `LabTest` | 实验室检验大项 | 血常规、肾功能、心肌损伤标志物检测 |
| `ExamIndicator` | 检查或检验的具体指标 | 肌钙蛋白、LVEF、ST 段改变 |
| `ThresholdRule` | 指标阈值及适用条件 | LVEF < 40% |

禁止：

- 把 `LabTest` 建成 `Exam`。
- 把检验大项建成单个 `ExamIndicator`。
- 把阈值仅保存为无法计算的长文本。

### 4.4 诊断与风险

| entityType | 用途 |
|---|---|
| `DiagnosisCriteria` | 诊断标准或诊断依据 |
| `DifferentialDiagnosis` | 鉴别诊断项 |
| `RiskStratification` | 风险分层方案 |
| `ScoringScale` | 评分量表 |
| `ClinicalRule` | 多条件临床规则 |
| `PatientState` | 患者状态或特殊人群 |
| `ClinicalEvent` | 临床事件 |
| `ClassificationStage` | **[V1.1 新增]** 疾病分型、分期或分级方案（如 NYHA 心功能分级、LVEF 分型、肿瘤 TNM 分期） |

> **[V1.1 说明]** `ClassificationStage` 用于承载结构化分型/分期方案，与 `Disease` 通过 `has_classification_stage` 关系连接（见 §7.4）。单一阈值条件优先使用 `ThresholdRule`；多条件分型体系使用 `ClinicalRule`；需要独立命名和引用的分型方案使用 `ClassificationStage`。

### 4.5 治疗与管理

| entityType | 用途 |
|---|---|
| `TreatmentPlan` | 治疗策略或方案 |
| `Medication` | 药物类别或具体药品 |
| `Procedure` | 操作、介入、手术或器械治疗 |
| `Indication` | 适应证 |
| `Contraindication` | 禁忌证 |
| `TreatmentTiming` | 治疗时机 |
| `TimeWindow` | 明确时间窗 |
| `FollowUp` | 随访与复查计划 |
| `DrugInteraction` | 药物相互作用（用于复杂三药或机制描述场景，见 §7.5 注释） |
| `AdverseEffect` | 不良反应 |
| `ClinicalPathway` | 诊疗路径（综合性容器，参与路径闭环审计，见 §13.1） |

### 4.6 来源与证据

| entityType | 用途 |
|---|---|
| `Guideline` | 指南、共识、教材或专家资料来源 |
| `Evidence` | 可定位的原文证据分段 |
| `RecommendationStatement` | 正式推荐陈述及分级 |

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
| `Disease` | `has_pathophysiology` | 具有病理生理机制 | `Pathophysiology` | 疾病 → 病理生理 | 表达疾病形成和进展机制，如心室重构、纤维化、心肌缺血等 |
| `Disease` | `has_epidemiology` | 具有流行病学特征 | `Epidemiology` | 疾病 → 流行病学 | 表达患病率、发病率、人群分布、年龄性别特征等 |
| `Disease` | `has_symptom` | 具有症状 | `Symptom` | 疾病 → 症状 | 表达患者主观感受，如胸痛、胸闷、呼吸困难、心悸等 |
| `Disease` | `has_sign` | 具有体征 | `Sign` | 疾病 → 体征 | 表达医生查体或客观观察发现，如水肿、肺部啰音、心脏杂音等 |
| `Disease` | `has_risk_factor` | 具有危险因素 | `RiskFactor` | 疾病 → 危险因素 | 表达增加疾病发生或不良结局概率的因素，如吸烟、高血压、家族史等 |
| `Disease` | `may_cause_complication` | 可导致并发症 | `Complication` | 疾病 → 并发症 | 表达疾病可能引起的并发症或临床后果 |
| `Disease` | `has_prognosis` | 具有预后 | `Prognosis` | 疾病 → 预后 | 表达死亡、复发、进展、再住院、功能恢复等结局信息 |

### 7.4 检查、检验和诊断

| 源实体 source | 关系英文名 relationType | 关系中文名 | 目标实体 target | 方向说明 | 用途说明 |
|---|---|---|---|---|---|
| `Disease` | `requires_exam` | 需要检查 | `Exam` | 疾病 → 检查 | 表达诊断、评估、随访需要使用的影像、心电、超声、内镜、病理等检查 |
| `Disease` | `requires_lab_test` | 需要检验 | `LabTest` | 疾病 → 检验 | 表达诊断、评估、随访需要使用的实验室检验 |
| `Exam` | `exam_has_indicator` | 检查包含指标 | `ExamIndicator` | 检查 → 检查指标 | 表达某项检查下可观察或测量的指标，如 LVEF、室壁厚度、ST 段改变等 |
| `LabTest` | `lab_test_has_indicator` | 检验包含指标 | `ExamIndicator` | 检验 → 检验指标 | 表达某项检验下的具体指标，如肌钙蛋白、BNP、肌酐、LDL-C 等 |
| `ExamIndicator` | `has_threshold_rule` | 指标具有阈值规则 | `ThresholdRule` | 指标 → 阈值规则 | 表达指标的判断阈值、范围、时间窗和阳性/阴性标准 |
| `Disease` | `has_diagnostic_criteria` | 具有诊断标准 | `DiagnosisCriteria` | 疾病 → 诊断标准 | 表达疾病确诊、疑诊、排除或分型所需满足的诊断条件 |
| `Disease` | `differentiates_from` | 需要鉴别 | `Disease/DifferentialDiagnosis` | 疾病 → 鉴别对象 | 表达本病需要与哪些疾病或鉴别诊断条目区分 |
| `Disease` | `has_risk_stratification` | 具有风险分层 | `RiskStratification` | 疾病 → 风险分层 | 表达低危、中危、高危等风险分层方案 |
| `Disease` | `uses_scoring_scale` | 使用评分量表 | `ScoringScale` | 疾病 → 评分量表 | 表达疾病评估时使用的评分、量表或风险评分工具 |
| `Disease` | `has_clinical_rule` | 具有临床规则 | `ClinicalRule` | 疾病 → 临床规则 | 表达多条件判断规则，如诊断组合、治疗适应证、排除条件等 |
| `Disease` | `has_classification_stage` | 具有分型/分期 | `ClassificationStage` | 疾病 → 分型/分期 | 表达疾病分型、分期、分级或临床阶段 |

> **[V1.1 新增]** `has_classification_stage` 用于连接疾病与其分型/分期方案节点。分型方案内部的具体条件和阈值使用 `ClinicalRule` 或 `ThresholdRule` 在 `ClassificationStage` 节点下挂载。

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

> **[V1.1 新增注释 — DrugInteraction 建模规则]**
> `Medication -> interacts_with` 的 target 优先指向另一个 `Medication` 节点（直接药物对，适用于大多数双药相互作用场景）。仅当需要描述三药组合、机制容器或复杂相互作用说明时，才建立独立的 `DrugInteraction` 节点作为 target，并在该节点上挂载涉及药物和机制描述。两种建模方式不得混用于同一相互作用。

> **[V1.5 新增注释 — 药物类别与具体药物建模规则]**
> 药物类别节点（如“抗凝药物”“溶栓药物”“硝酸酯类药物”）的 `aliases` 只能保存同义类别名，不得保存具体药物名、英文缩写或治疗动作词。具体药物必须建立独立 `Medication` 节点，并通过 `has_specific_medication` 从类别节点连接。英文缩写（如 `t-PA`、`rt-PA`）应放入具体药物节点 aliases，而不是药物类别 aliases。

> **[V1.6 新增注释 — 治疗方案可执行性与视图去重规则]**
> `TreatmentPlan` 必须可执行。具体治疗方案（如“溶栓治疗”“抗凝治疗”“抗血小板治疗”“血运重建”）必须至少连接一个下游实体：`includes_medication`、`includes_procedure`、`has_timing`、`has_indication`、`has_contraindication` 或 `has_clinical_pathway`。疾病级总治疗方案（如“急性心肌梗死治疗方案”）不得复制疾病下所有药物或操作；总方案应连接 `has_clinical_pathway`，具体药物和操作应挂在下级具体治疗方案下。前端、审核包和统计报表中的实体数量必须按 `KGNode.code` 或 canonical code 去重；多条关系路径可作为临床路径明细保留，但不得把同一药物、同一检查或同一治疗节点的多条路径统计为多个实体节点。

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

| 源实体 source | 关系英文名 relationType | 关系中文名 | 目标实体 target | 方向说明 | 用途说明 |
|---|---|---|---|---|---|
| `Disease` | `based_on_guideline` | 基于指南 | `Guideline` | 疾病 → 指南 | 表达疾病图谱内容来自或参考的指南、共识、教材或路径文件 |
| `Guideline` | `guideline_has_evidence` | 指南包含证据 | `Evidence` | 指南 → 证据 | 表达指南、教材或文献中的证据片段 |
| 任意临床实体 | `supported_by_evidence` | 由证据支持 | `Evidence` | 临床实体/关系承载对象 → 证据 | 表达实体、关系或推荐陈述有可追溯证据支撑 |
| `RecommendationStatement` | `derived_from` | 来源于证据 | `Evidence` | 推荐陈述 → 证据 | 表达具体推荐语句来源于哪一条证据片段 |

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
| `source_page` | 来源页码 | Integer/String | 是 | PDF 页码；无页码文本可填 `N/A`，但必须有可定位片段 |
| `evidence_text` | 原文证据 | String | 是 | 原始文献片段，不得只保存改写文本 |
| `guideline_id` | 指南ID | String | 条件必填 | 来源为指南/共识时填写对应 Guideline 节点编码 |
| `evidence_id` | 证据ID | String | 是 | 对应 Evidence 节点编码 |
| `recommendation_class` | 推荐等级 | Enum/String | 是 | 指南推荐等级；教材或无分级来源填 `N/A` |
| `evidence_level` | 证据等级 | Enum/String | 是 | 指南证据等级；教材或无分级来源填 `N/A` |
| `confidence` | 抽取置信度 | Number | 是 | 0–1，表示抽取或映射可信度 |

`source_page` 对无页码 TXT 可为 `N/A`，但 `source_section`、行号/字符区间和 `segment_id` 必须可定位原文。

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

### 9.2 Evidence 字段

| 字段英文名 | 中文名称 | 类型/枚举 | 必填 | 说明 |
|---|---|---|---|---|
| `evidence_id` | 证据ID | String | 是 | 证据片段唯一编码 |
| `document_id` | 文档ID | String | 是 | 证据所属文档编码 |
| `segment_id` | 文本片段ID | String | 是 | 证据所在片段编码 |
| `source_name` | 来源名称 | String | 是 | 指南、教材、共识或专家资料名称 |
| `source_type` | 来源类型 | Enum | 是 | 与 Guideline 的 `source_type` 保持一致 |
| `source_section` | 来源章节 | String | 是 | 章节、标题、小节或段落定位 |
| `source_page` | 来源页码 | Integer/String | 是 | PDF 页码；无页码时填 `N/A` 并保留行号或字符区间 |
| `line_start` | 起始行号 | Integer/String | 否 | 文本证据起始行；无行号时可填 `N/A` |
| `line_end` | 结束行号 | Integer/String | 否 | 文本证据结束行；无行号时可填 `N/A` |
| `start_offset` | 起始字符位置 | Integer | 否 | 证据在清洗文本中的起始字符偏移 |
| `end_offset` | 结束字符位置 | Integer | 否 | 证据在清洗文本中的结束字符偏移 |
| `evidence_text` | 原文证据 | String | 是 | 必须保存原文片段，不得只保存总结或翻译 |
| `language` | 原文语言 | String | 是 | `zh-CN`、`en` 等 |
| `translation_text` | 中文翻译 | String | 条件必填 | 非中文来源必须保存中文翻译 |
| `translation_method` | 翻译方式 | String | 条件必填 | 人工翻译、机器初译+人工校对等 |
| `content_hash` | 证据内容哈希 | String | 是 | 用于证据去重、追溯和防篡改 |

规则：

- `evidence_text` 必须是原文，不得只保留改写文本。
- 英文原文与中文翻译分别保存。
- 目录、版权页、缩写表和参考文献默认不能作为临床证据。
- 证据节点不得保存本地文件绝对路径。

### 9.3 教材来源

教材证据固定：

| 字段英文名 | 中文名称 | 固定值 | 说明 |
|---|---|---|---|
| `source_type` | 来源类型 | `authoritative_textbook` | 标记来源为权威教材或专著 |
| `source_authority` | 来源权威性 | `authoritative_textbook` | 表示该证据来自基础权威资料 |
| `knowledge_strength` | 知识强度 | `high` | 教材骨架知识强度较高，但不等同指南推荐等级 |
| `clinical_applicability` | 临床适用性 | `general` | 作为通用基础医学和临床知识 |
| `recommendation_class` | 推荐等级 | `N/A` | 教材来源不得直接写指南推荐等级 |
| `evidence_level` | 证据等级 | `N/A` | 教材来源不得直接写指南证据等级 |

> **[V1.1 新增 — 教材转引指南分级的处理规则]**
> 教材正文中有时直接引用指南推荐级别（如"指南推荐I类A级"）。处理规则如下：
>
> 1. 来源仍登记为 `source_type=authoritative_textbook`，`recommendation_class` 和 `evidence_level` 字段强制保持 `N/A`，不得因教材正文含有分级文字而更改。
> 2. 教材中的分级引用文字可原文保留在 `evidence_text` 中，不得删除。
> 3. 如需引用该推荐的正式等级，必须另行从原始指南建立独立的 `Evidence` 记录和 `RecommendationStatement` 节点，source_type 使用 `guideline`。
> 4. 不得以教材中的转引文字替代原始指南证据，两者可并列 provenance，但不得混同字段值。

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
