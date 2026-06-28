# 专科知识图谱 Schema 标准

版本：V1.1
状态：正式执行标准
适用范围：所有专科、疾病大类和单病种知识图谱数据实例。
变更说明：基于 V1.0 审核报告修订，修复 P0×3、P1×3、P2×3 共 9 项问题。

## 变更记录

| 版本 | 日期 | 变更类型 | 涉及章节 | 说明 |
|---|---|---|---|---|
| V1.0 | — | 初版 | 全文 | 正式执行标准 |
| V1.1 | 2026-06 | P0修复 | §4.4、§7.6、§13.1 | 补充 ClassificationStage 实体；补充患者状态否定语义关系；classification_stage 纳入闭环路径 |
| V1.1 | 2026-06 | P0修复 | §4 说明 | 显式注明本 Schema 无 DiseaseSubtype |
| V1.1 | 2026-06 | P1修复 | §9.3、§13.1 | 补充教材转引指南分级的处理规则 |
| V1.1 | 2026-06 | P1修复 | §16 | 硬闸门补充 schema_gap 未解决不得标记 covered |
| V1.1 | 2026-06 | P1修复 | §13.1、§4.5 | ClinicalPathway 纳入闭环路径审计，标注 optional |
| V1.1 | 2026-06 | P2修复 | §18 | 交付清单补充 source_conflict_register、dedup_index、source_folder_summary |
| V1.1 | 2026-06 | P2修复 | §7.5 | DrugInteraction 建模歧义消除，补充注释 |

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

### 5.1 所有节点必填字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | String | 全局唯一技术 ID，稳定不复用 |
| `code` | String | 全局唯一业务编码 |
| `name` | String | 中文规范名称 |
| `preferred_name` | String | 推荐名称，默认等于 `name` |
| `display_name` | String | 展示名称，默认等于 `name` |
| `entityType` | Enum | 标准实体类型 |
| `entityCategory` | String | 目录、临床、治疗、证据等大类 |
| `schema_version` | String | 固定为 `V1.1` |
| `review_status` | Enum | `draft/pending_review/approved/rejected/deprecated` |

### 5.2 通用可选字段

```text
name_en
aliases[]
abbr
description
parentCode
standard_code
standard_system
confidence
created_by
created_time
updated_time
```

### 5.3 批次与范围字段

```text
batch_id
scope_type        specialty | category | disease
scope_target
merge_status      isolated | validated | merged | conflict | rejected
source_version
conflict_status   none | open | resolved
```

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

```text
structural
clinical
diagnostic
therapeutic
risk
temporal
evidence
rule
```

### 7.2 目录关系

| source | relationType | target |
|---|---|---|
| `Specialty` | `has_category` | `DiseaseCategory` |
| `DiseaseCategory` | `has_subcategory` | `DiseaseSubcategory` |
| `DiseaseSubcategory` | `has_disease` | `Disease` |
| `Disease` | `belongs_to_subcategory` | `DiseaseSubcategory` |
| `Disease` | `belongs_to_category` | `DiseaseCategory` |

`belongs_to_category` 使用 `classification_role=primary/secondary_view` 区分主分类和次分类视角。

### 7.3 基础医学与临床表现

| source | relationType | target |
|---|---|---|
| `Disease` | `has_etiology` | `Etiology` |
| `Disease` | `has_pathophysiology` | `Pathophysiology` |
| `Disease` | `has_epidemiology` | `Epidemiology` |
| `Disease` | `has_symptom` | `Symptom` |
| `Disease` | `has_sign` | `Sign` |
| `Disease` | `has_risk_factor` | `RiskFactor` |
| `Disease` | `may_cause_complication` | `Complication` |
| `Disease` | `has_prognosis` | `Prognosis` |

### 7.4 检查、检验和诊断

| source | relationType | target |
|---|---|---|
| `Disease` | `requires_exam` | `Exam` |
| `Disease` | `requires_lab_test` | `LabTest` |
| `Exam` | `exam_has_indicator` | `ExamIndicator` |
| `LabTest` | `lab_test_has_indicator` | `ExamIndicator` |
| `ExamIndicator` | `has_threshold_rule` | `ThresholdRule` |
| `Disease` | `has_diagnostic_criteria` | `DiagnosisCriteria` |
| `Disease` | `differentiates_from` | `Disease/DifferentialDiagnosis` |
| `Disease` | `has_risk_stratification` | `RiskStratification` |
| `Disease` | `uses_scoring_scale` | `ScoringScale` |
| `Disease` | `has_clinical_rule` | `ClinicalRule` |
| `Disease` | `has_classification_stage` | `ClassificationStage` |

> **[V1.1 新增]** `has_classification_stage` 用于连接疾病与其分型/分期方案节点。分型方案内部的具体条件和阈值使用 `ClinicalRule` 或 `ThresholdRule` 在 `ClassificationStage` 节点下挂载。

### 7.5 治疗与随访

| source | relationType | target |
|---|---|---|
| `Disease` | `has_treatment_plan` | `TreatmentPlan` |
| `Disease` | `treated_by_medication` | `Medication` |
| `Disease` | `treated_by_procedure` | `Procedure` |
| `TreatmentPlan` | `includes_medication` | `Medication` |
| `TreatmentPlan` | `includes_procedure` | `Procedure` |
| `Medication/Procedure` | `has_indication` | `Indication` |
| `Medication/Procedure` | `has_contraindication` | `Contraindication` |
| `TreatmentPlan/Procedure` | `has_timing` | `TreatmentTiming` |
| `TreatmentTiming` | `has_time_window` | `TimeWindow` |
| `Disease/TreatmentPlan` | `has_follow_up` | `FollowUp` |
| `Medication` | `interacts_with` | `Medication/DrugInteraction` |
| `Medication` | `may_cause_adverse_effect` | `AdverseEffect` |
| `Disease` | `has_clinical_pathway` | `ClinicalPathway` |

> **[V1.1 新增注释 — DrugInteraction 建模规则]**
> `Medication -> interacts_with` 的 target 优先指向另一个 `Medication` 节点（直接药物对，适用于大多数双药相互作用场景）。仅当需要描述三药组合、机制容器或复杂相互作用说明时，才建立独立的 `DrugInteraction` 节点作为 target，并在该节点上挂载涉及药物和机制描述。两种建模方式不得混用于同一相互作用。

### 7.6 患者状态和事件

| source | relationType | target |
|---|---|---|
| `Disease` | `applies_to_state` | `PatientState` |
| `PatientState` | `state_recommends_medication` | `Medication` |
| `PatientState` | `state_recommends_procedure` | `Procedure` |
| `PatientState` | `state_contraindicates_medication` | `Medication` |
| `PatientState` | `state_contraindicates_procedure` | `Procedure` |
| `Disease` | `has_clinical_event` | `ClinicalEvent` |

> **[V1.1 新增]** `state_contraindicates_medication` 和 `state_contraindicates_procedure` 用于表达特殊患者状态下的禁忌语义（如肾功能不全禁用某药、妊娠禁用某操作）。禁止将此类禁忌语义写成 `state_recommends_*` 正向关系，必须使用专用否定关系或配合 `polarity=negative` 字段（见 §8.3）。

### 7.7 证据关系

| source | relationType | target |
|---|---|---|
| `Disease` | `based_on_guideline` | `Guideline` |
| `Guideline` | `guideline_has_evidence` | `Evidence` |
| 任意临床实体 | `supported_by_evidence` | `Evidence` |
| `RecommendationStatement` | `derived_from` | `Evidence` |

## 8. 关系通用字段

### 8.1 必填字段

```text
id
source_code
relationType
target_code
relationCategory
batch_id
schema_version=V1.1
review_status
```

### 8.2 核心临床关系证据字段

```text
document_id
segment_id
source_name
source_type
source_version
source_section
source_page
evidence_text
guideline_id
evidence_id
recommendation_class
evidence_level
confidence
```

`source_page` 对无页码 TXT 可为 `N/A`，但 `source_section`、行号/字符区间和 `segment_id` 必须可定位原文。

### 8.3 条件与语义字段

```text
polarity          positive | negative | conditional
applicability
patient_state
condition_text
dosage
route
frequency
duration
timing
classification_role
```

否定、禁忌和不推荐语义不得写成正向治疗关系。`polarity=negative` 可用于 `state_recommends_*` 等关系以补充否定语义，但首选使用专用否定关系（`state_contraindicates_*`、`has_contraindication`）。

## 9. Guideline 与 Evidence

### 9.1 Guideline 字段

```text
document_id
title
source_type
issuing_body
publication_year
version
language
sha256
```

`source_type` 枚举：

```text
guideline
consensus
authoritative_textbook
expert_material
curated_web_text
```

### 9.2 Evidence 字段

```text
evidence_id
document_id
segment_id
source_name
source_type
source_section
source_page
line_start
line_end
start_offset
end_offset
evidence_text
language
translation_text
translation_method
content_hash
```

规则：

- `evidence_text` 必须是原文，不得只保留改写文本。
- 英文原文与中文翻译分别保存。
- 目录、版权页、缩写表和参考文献默认不能作为临床证据。
- 证据节点不得保存本地文件绝对路径。

### 9.3 教材来源

教材证据固定：

```text
source_type=authoritative_textbook
source_authority=authoritative_textbook
knowledge_strength=high
clinical_applicability=general
recommendation_class=N/A
evidence_level=N/A
```

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

```text
evidence_ids[]
document_ids[]
source_names[]
source_types[]
evidence_count
provenance_records_json
```

数组记录数、`evidence_count` 和 provenance 记录数必须一致。

## 11. 临床规则与阈值

### 11.1 ThresholdRule

必填字段：

```text
indicator_code
operator
value
unit
condition
patient_state
time_context
```

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

```text
rule_type
if_conditions[]
then_actions[]
exceptions[]
applicability
evidence_id
```

## 12. 专科/疾病大类配置

每个执行范围生成配置文件，至少包含：

```text
scope_type
scope_target
specialty_code
category_code
disease_code
pathway_element
applicability_status
reason
```

`applicability_status` 枚举：

```text
required
optional
not_applicable
```

配置决定闭环验收要求，但不得改变实体和关系的标准定义。

## 13. 诊疗路径闭环

### 13.1 标准环节

```text
definition
aliases
etiology
pathophysiology
epidemiology
symptom
sign
exam
lab_test
exam_indicator
threshold_rule
diagnosis_criteria
differential_diagnosis
classification_stage     [V1.1 新增，默认 optional，遗传病/分型复杂疾病可配置为 required]
risk_factor
risk_stratification
scoring_scale
treatment_plan
medication
procedure
indication
contraindication
complication
prognosis
follow_up
clinical_pathway         [V1.1 新增，默认 optional]
guideline
evidence
```

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

## 17. Neo4j 导入标准

数据实例验收通过并获得用户确认后才允许导入。

节点写入：

```cypher
MERGE (n:KGEntity {code: $code})
SET n += $properties
```

规则：

- `code` 建立唯一约束。
- 目录、临床和证据可增加辅助标签，但 `entityType` 只有一个标准值。
- 关系按语义键去重后创建。
- 导入前备份，导入后执行全库质量审计。
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
