# 专科知识图谱最终 Schema V1.1（定型版）

版本：V1.1  
状态：当前执行标准  
适用范围：全专科通用，心血管内科作为首个落地专科  
基线来源：`专科知识图谱最终_Schema_V1.0_完整版.md`、PDF解析实践、Neo4j落库审计、专家审核反馈  

---

## 0. 设计目标

本 Schema 用于把临床指南、共识、教材和医院规则沉淀为可检索、可推理、可审核的专科知识图谱。目标不是堆积实体数量，而是形成疾病诊疗路径闭环：

```text
专科/疾病体系
  -> 疾病定义
  -> 症状/体征
  -> 检查/检验/指标
  -> 诊断标准
  -> 风险因素
  -> 并发症
  -> 治疗方案/药物/操作
  -> 指南证据
  -> AI辅助诊疗推理
```

---

## 1. 分层原则

### 1.1 全专科通用骨架

所有专科必须遵循统一疾病层级：

```text
Specialty
  -> DiseaseCategory
    -> DiseaseSubcategory
      -> Disease
```

规则：

- `Specialty` 是根节点，可无 `parentCode`。
- 除根节点外，结构层节点必须有 `parentCode`。
- `Disease` 必须可以追溯到 `Specialty`。
- 一个真实疾病实体原则上只建一个 `Disease` 节点。
- 如果同一个疾病存在多分类视角，使用多条分类关系，不复制疾病节点。

### 1.2 通用、专科、疾病特异的边界

| 层级 | 是否进入 Schema 主体 | 示例 |
|---|---:|---|
| 全专科通用 | 是 | Disease、Symptom、Exam、LabTest、Medication、Guideline |
| 专科通用 | 是，作为属性或代码体系扩展 | 心血管 `CARD` code 前缀、心电图、超声心动图 |
| 疾病特异 | 否，优先放入属性/证据/规则 | STEMI 的 ST段抬高阈值、心衰 EF 分型阈值 |

---

## 2. 实体类型标准

### 2.1 当前采纳实体类型

```text
Specialty
DiseaseCategory
DiseaseSubcategory
Disease
Symptom
Sign
Exam
LabTest
ExamIndicator
Medication
Procedure
TreatmentPlan
DiagnosisCriteria
RiskFactor
Complication
ClinicalPathway
PatientState
ClinicalEvent
Guideline
Evidence
EvidenceSource
Department
AnatomySite
AdverseEffect
```

### 2.2 检查、检验、指标拆分

V1.1 明确拆分“检验检查”，禁止都放到 `Exam`：

| 概念 | 实体类型 | code 前缀 | 示例 |
|---|---|---|---|
| 检查项目 | `Exam` | `EXAM-*` | 心电图、超声心动图、冠脉造影、CT血管成像、心脏磁共振、Holter |
| 实验室检验大项 | `LabTest` | `LAB-*` | 血常规、尿常规、肝功能、肾功能、凝血功能、血脂、心肌损伤标志物检测 |
| 指标/阈值项 | `ExamIndicator` | `IND-*` | 白细胞计数、血红蛋白、尿蛋白、肌钙蛋白、BNP、NT-proBNP、D-二聚体、LDL-C、LVEF、ST段改变 |

标准关系：

```text
Disease -requires_exam-> Exam
Disease -requires_lab_test-> LabTest
Exam -exam_has_indicator-> ExamIndicator
LabTest -lab_test_has_indicator-> ExamIndicator
```

说明：

- `血常规`、`尿常规` 是 `LabTest`，不是 `Exam`。
- `肌钙蛋白`、`LDL-C`、`白细胞计数` 是 `ExamIndicator`，不是 `LabTest`。
- `LVEF` 是 `ExamIndicator`，通常由 `超声心动图(Exam)` 或相关影像检查产生。

---

## 3. 通用节点字段

所有实体建议保留以下字段，便于 Neo4j 导入、前端展示、医生审核和版本追踪。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `id` | String | 是 | 全局唯一技术 ID，稳定不复用 |
| `code` | String | 是 | 业务编码，全局唯一，不允许重复 |
| `name` | String | 是 | 中文主名称，前端默认展示字段 |
| `preferred_name` | String | 是 | 推荐名称，通常等于 `name` |
| `display_name` | String | 是 | 展示名称，通常等于 `name` |
| `name_en` | String | 否 | 英文名或缩写 |
| `aliases` | Array | 否 | 同义词、旧称、英文缩写 |
| `entityType` | Enum | 是 | 实体类型，必须唯一枚举 |
| `entityCategory` | String | 是 | 实体大类，用于前端分组 |
| `parentCode` | String | 条件必填 | 非根结构节点和领域节点必须填写 |
| `description` | Text | 否 | 定义或说明 |
| `source_id` | String | 否 | 来源节点 ID，不写本地文件路径 |
| `source_name` | String | 否 | 指南/共识/文献名称，不写本地文件路径 |
| `guideline_id` | String | 否 | 关联指南节点 |
| `evidence_id` | String | 否 | 关联证据节点 |
| `review_status` | Enum | 是 | `draft` / `pending_review` / `approved` / `rejected` / `deprecated` |
| `confidence` | Float | 否 | 抽取置信度，0-1 |
| `schema_version` | String | 是 | 当前 Schema 版本 |
| `created_by` | String | 否 | `AI` / `human` / `doctor` / `system` |
| `created_time` | DateTime | 否 | 创建时间 |
| `updated_time` | DateTime | 否 | 更新时间 |

硬性规则：

- `source`、`source_name`、`file_name` 只能写指南/共识/文献名称，禁止写本地 Windows 路径。
- 本地路径只能出现在导入日志、备份日志或审计文件中，不能进入临床图谱节点/关系属性。
- 前端展示优先级：`display_name -> preferred_name -> name`。

---

## 4. 编码规范

### 4.1 业务 code

`code` 是全局唯一业务键，不能只靠英文缩写。

推荐格式：

```text
<TYPE>-<SPECIALTY>-<CATEGORY>-<ABBR>
```

示例：

```text
SPEC-CARD
CAT-CARD-CAD
SUB-CARD-CAD-GENERAL
DIS-CARD-CAD-STEMI
EXAM-CARD-ECG
LAB-CARD-CARDIAC-BIOMARKER
IND-CARD-TROPONIN
MED-CARD-ASPIRIN
PROC-CARD-PCI
```

### 4.2 id

`id` 是技术 ID，可与 code 派生但必须稳定：

```text
KG_DIS_CARD_CAD_STEMI
KG_LAB_CARD_CARDIAC_BIOMARKER
```

### 4.3 缩写 abbr

`abbr` 只是别名字段，不允许作为唯一键。`CAD` 可以同时是“冠心病缩写”和“冠状动脉疾病概念缩写”，但 `code` 必须唯一。

---

## 5. 关系类型标准

### 5.1 relationCategory

关系必须归入以下类别：

```text
STRUCTURAL
CLINICAL
DIAGNOSTIC
THERAPEUTIC
RISK
COMPLICATION
EVIDENCE
REASONING
SAFETY
```

### 5.2 核心关系

| relationType | 起点 | 终点 | relationCategory | 说明 |
|---|---|---|---|---|
| `has_category` | Specialty | DiseaseCategory | STRUCTURAL | 专科包含疾病大类 |
| `has_subcategory` | DiseaseCategory | DiseaseSubcategory | STRUCTURAL | 疾病大类包含亚类 |
| `has_disease` | DiseaseSubcategory | Disease | STRUCTURAL | 疾病亚类包含疾病 |
| `belongs_to_specialty` | DiseaseCategory | Specialty | STRUCTURAL | 大类属于专科 |
| `belongs_to_category` | DiseaseSubcategory / Disease | DiseaseCategory | STRUCTURAL | 亚类或多视角疾病属于大类 |
| `belongs_to_subcategory` | Disease | DiseaseSubcategory | STRUCTURAL | 疾病属于亚类 |
| `has_secondary_disease_view` | DiseaseSubcategory / DiseaseCategory | Disease | STRUCTURAL | 多视角分类，不复制实体 |
| `has_symptom` | Disease | Symptom | CLINICAL | 疾病常见症状 |
| `has_sign` | Disease | Sign | CLINICAL | 疾病常见体征 |
| `requires_exam` | Disease | Exam | DIAGNOSTIC | 诊断/评估需要检查 |
| `requires_lab_test` | Disease | LabTest | DIAGNOSTIC | 诊断/评估需要实验室检验 |
| `exam_has_indicator` | Exam | ExamIndicator | DIAGNOSTIC | 检查产生指标 |
| `lab_test_has_indicator` | LabTest | ExamIndicator | DIAGNOSTIC | 检验大项包含指标 |
| `has_diagnostic_criteria` | Disease | DiagnosisCriteria | DIAGNOSTIC | 疾病诊断标准 |
| `has_risk_factor` | Disease | RiskFactor | RISK | 疾病风险因素 |
| `may_cause_complication` | Disease | Complication | COMPLICATION | 可能导致并发症 |
| `has_treatment_plan` | Disease | TreatmentPlan | THERAPEUTIC | 疾病治疗方案 |
| `has_clinical_pathway` | Disease | ClinicalPathway | THERAPEUTIC | 疾病诊疗路径 |
| `treated_by_medication` | Disease / TreatmentPlan | Medication | THERAPEUTIC | 药物治疗 |
| `treated_by_procedure` | Disease / TreatmentPlan | Procedure | THERAPEUTIC | 操作/手术/介入治疗 |
| `contraindicated_with` | Medication / Procedure | Disease / PatientState / RiskFactor / ExamIndicator | SAFETY | 禁忌 |
| `requires_monitoring` | Medication / Procedure | ExamIndicator | SAFETY | 治疗监测指标 |
| `evidenced_by` | Entity / Relation | Evidence | EVIDENCE | 证据支撑 |
| `from_guideline` | Evidence | Guideline | EVIDENCE | 证据来自指南 |
| `based_on_guideline` | Entity / Relation | Guideline | EVIDENCE | 实体或关系依据指南 |
| `pathway_next_step` | ClinicalPathway | ClinicalPathway / ClinicalEvent | REASONING | 路径下一步 |

### 5.3 禁止关系

以下旧关系不得进入最终库：

```text
requires_exam_indicator
REQUIRES_EXAM
REQUIRES_LAB_TEST
RECOMMENDS_DRUG
RECOMMENDS_EXAM
HAS_CLINICAL_MANIFESTATION
RISK_FACTOR_OF
DIAGNOSTIC_BASIS_OF
SUBTYPE_OF
```

如历史数据存在，必须迁移到 V1.1 标准关系。

---

## 6. 关系通用字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `id` | String | 是 | 关系唯一 ID |
| `source` | String | 是 | 起点 code 或 id，不是本地路径 |
| `target` | String | 是 | 终点 code 或 id |
| `relationType` | String | 是 | 标准关系类型 |
| `relationCategory` | Enum | 是 | 标准关系类别 |
| `evidence_text` | Text | 否 | 原文证据片段 |
| `source_id` | String | 否 | 文献/指南来源 ID |
| `source_name` | String | 否 | 文献/指南名称 |
| `file_name` | String | 否 | 文件名，不含本地路径 |
| `document_id` | String | 否 | 文档 ID |
| `guideline_id` | String | 否 | 指南 ID |
| `evidence_level` | Enum | 否 | A / B / C 或指南原始等级 |
| `recommendation_class` | Enum | 否 | I / IIa / IIb / III 或指南原始等级 |
| `confidence` | Float | 否 | 抽取置信度 |
| `review_status` | Enum | 是 | 审核状态 |
| `schema_version` | String | 是 | Schema 版本 |

---

## 7. 证据与指南

### 7.1 Guideline

`Guideline` 表示指南、共识、标准或教材来源。

关键字段：

```text
code
name
name_en
year
issuer
region
document_type
source_name
source_id
```

### 7.2 Evidence

`Evidence` 表示具体证据片段或推荐条目。

关键字段：

```text
code
name
evidence_text
guideline_id
source_name
file_name
chapter
page
recommendation_class
evidence_level
confidence
review_status
```

规则：

- 疾病定义、诊断标准、治疗方案必须尽量绑定证据。
- 如果 PDF 没有推荐级别，保留空值或 `not_specified`，不能伪造 A/B/C 或 I/IIa。
- `evidence_text` 必须来自文献解析结果或明确来源，不得凭空生成。

---

## 8. 疾病诊疗路径闭环审计

疾病质量不按关系数量判断，必须按环节覆盖度判断。

### 8.1 必查环节

```text
definition
symptom
sign
exam
lab_test
exam_indicator
diagnosis_criteria
risk_factor
complication
treatment_plan
medication
procedure
guideline_or_evidence
```

### 8.2 输出字段

每个疾病必须输出：

```text
disease_code
disease_name
category_code
subcategory_code
covered_elements
missing_elements
coverage_rate
closed_loop_ready
blocking_missing_elements
gap_reason
recommended_action
```

### 8.3 closed_loop_ready 判定

`closed_loop_ready=yes` 只表示“诊疗路径环节完整度达到当前标准”，不等于医生审核通过。

建议规则：

- 核心环节缺失时必须为 `no`：`definition`、`diagnosis_criteria`、`treatment_plan`、`guideline_or_evidence`。
- 非核心指标缺失时可显示覆盖率，但仍需列入缺口清单。
- 必须同时输出 `missing_elements`，不能只输出布尔值。

---

## 9. 占位亚类标准

当三层体系中某个疾病暂时无法准确归入真实临床亚类，可建立占位 `DiseaseSubcategory`，但必须显式标记。

必填字段：

```text
is_placeholder = true
placeholder_reason
placeholder_scope
needs_medical_review = true
review_status = pending_review
```

禁止：

- 把占位亚类当成正式临床分类展示给医生。
- 不带标记地创建 `GENERAL`、`OTHER`、`UNCATEGORIZED` 亚类。

---

## 10. 多分类与重复实体

### 10.1 同名疾病

同一个真实疾病不得复制为多个 `Disease` 节点。

例：`心源性休克` 只能有一个 canonical Disease 节点。它可同时有：

```text
心源性休克 -belongs_to_category {classification_role:'primary'}-> 心血管急危重症
心源性休克 -belongs_to_category {classification_role:'secondary_view'}-> 心力衰竭
心力衰竭相关亚类 -has_secondary_disease_view-> 心源性休克
```

### 10.2 缩写冲突

缩写冲突不等于业务 code 冲突。审计重点是：

- `code` 是否重复。
- `name` 是否同名不同节点。
- 同一真实概念是否被建成不同 entityType。

---

## 11. 数据导入硬性闸门

导入 Neo4j 前必须通过以下检查：

```text
1. code 全局唯一
2. Disease 同名重复为 0，或有明确 same_clinical_entity_as / secondary_view 说明
3. 非根结构节点 parentCode 不为空
4. 所有节点 name / preferred_name / display_name 不为空
5. source/source_name/file_name 不包含本地路径
6. entityType 不含 Drug / Examination / Test 等旧类型
7. relationType 不含大写遗留关系
8. relationCategory 不为空且属于标准枚举
9. 不存在 Disease -requires_exam_indicator-> ExamIndicator 直连
10. LabTest 与 ExamIndicator 分层存在
11. 占位 DiseaseSubcategory 必须有占位字段
12. 输出疾病闭环完整度审计
```

---

## 12. V1.0 到 V1.1 迁移映射

| 历史类型/关系 | V1.1 标准 |
|---|---|
| `Drug` | `Medication` |
| `Examination` | `Exam` |
| `Test` | `ExamIndicator`，若为检验大项则改为 `LabTest` |
| `Disease -requires_exam_indicator-> ExamIndicator` | `Disease -requires_lab_test-> LabTest` 或 `Disease -requires_exam-> Exam`，再由中间层连接指标 |
| `RECOMMENDS_DRUG` | `treated_by_medication` |
| `RECOMMENDS_EXAM` | `requires_exam` / `requires_lab_test` |
| `HAS_CLINICAL_MANIFESTATION` | `has_symptom` / `has_sign` |
| `RISK_FACTOR_OF` | `has_risk_factor`，方向统一为 Disease -> RiskFactor |
| `DIAGNOSTIC_BASIS_OF` | `has_diagnostic_criteria` / `requires_exam` / `requires_lab_test` |
| `SUBTYPE_OF` | `belongs_to_subcategory` / `belongs_to_category` |

---

## 13. 当前心血管内科实现基线

当前心血管内科实现应满足：

```text
Specialty: Cardiology / 心血管内科
DiseaseCategory: 按心血管三层体系建立
DiseaseSubcategory: 按三层体系建立，占位亚类显式标记
Disease: 真实疾病不重复，支持多分类视角
Exam: 心电图、超声心动图、冠脉造影、CT血管成像、心脏磁共振、Holter等
LabTest: 心肌损伤标志物检测、利钠肽检测、凝血与血栓标志物检测、血脂检测、电解质检测等
ExamIndicator: 肌钙蛋白、CK-MB、BNP、D-二聚体、LDL-C、血钾、LVEF等
```

优先深度验证疾病：

```text
急性冠脉综合征 / 急性心肌梗死 / STEMI / NSTEMI / 不稳定型心绞痛
心肌病体系
```

---

## 14. 后续候选扩展

以下内容暂不进入 V1.1 主体，作为后续 V1.2 候选，避免 Schema 臃肿：

```text
ThresholdRule
DoseRule
TimeWindow
ContraindicationRule
RiskScoreItem
FollowupPlan
QualityIndicator
```

如指南证据中已出现相关内容，V1.1 阶段可先挂在 `DiagnosisCriteria`、`TreatmentPlan`、`ClinicalPathway` 或 `Evidence` 属性中。

---

## 15. 交付要求

每次交付至少包含：

```text
1. Schema 标准文档
2. 节点 CSV / JSON
3. 关系 CSV / JSON
4. 疾病闭环完整度审计
5. Neo4j 导入/迁移日志
6. 数据质量审计报告
7. 给专家审核的说明
8. 给开发接入的字段与查询说明
```
