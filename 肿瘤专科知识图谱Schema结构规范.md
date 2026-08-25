# 肿瘤专科知识图谱 Schema 结构规范

版本：V1.0（基于《专科知识图谱Schema标准》V3.0 主干，肿瘤专科完整落地版）

更新时间：2026-08-20

适用范围：肿瘤专科知识图谱（含实体瘤与血液系统肿瘤），并支持按器官/系统、按病种横向扩展。

---

## 全文标记说明

为明确区分"通用主干"与"肿瘤专科叠加"，全文统一使用以下标记：

- **【复用通用结构】**：直接沿用《专科知识图谱Schema标准》V3.0 的内容（已内联复制进本文，非肿瘤新增）。
- **【新增肿瘤特色】**：肿瘤专科叠加内容（V3.0 无，本规范新增）。

凡表格中同时含两类内容，均用「来源」列标注 `复用通用` 或 `新增肿瘤`。

---

## 本版定位

V3.0 通用主干（五层架构、疾病三层、实体、关系、字段、字典、推荐链、证据、验收、闸门）已内联复制进本文，肿瘤专科叠加内容按实体/关系/字典/验收/闸门正序融入对应章节，扩展模块配置规格集中在第 11 章。

---

## 1. 核心原则

### 1.1 继承 V3.0 设计原则 【复用通用结构】

1. **一张完整业务图谱**：不在子图层面做"展示版"，按场景在读取端过滤。
2. **同图分角色读取**：医生端、维护端、治理端读同一图，字段与关系视图不同。
3. **三层来源分工**：教材定疾病骨架，指南定诊疗决策细节，标准字典定实体身份。
4. **入库即绑定标准身份**：进入诊断、检查、检验、用药、手术等正式动作的实体，必须优先绑定标准字典，避免同名异物。
5. **字典只读、规范注册**：既有标准字典默认只读；缺失或冲突进待处理清单，不直接改旧字典；新增字典按审批边界注册。
6. **名称归一**：主名称用标准中文全称，缩写、品牌名、口语名、旧名存入别名。
7. **不伪造来源与编码**：不得为凑覆盖率编造编码或证据来源。
8. **推荐须有推理链**：正式推荐须含适用场景、触发条件、禁忌/排除、动作、主依据与证据等级。
9. **展示可有来源、推荐必有依据**：一般知识展示可无正式推荐链，但必须有来源。
10. **过程字段不进展示**：过程字段仅用于追溯与治理，不进入图谱元模型展示层。
11. **指南升级不覆盖旧证据**：以来源年份、版本、适用范围、冲突状态裁决。
12. **关联须有业务语义**：检查、检验，治疗，用药，手术不得仅以"疾病直接关联项目"入库，须说明服务的诊疗阶段、临床目的、对象。

### 1.2 肿瘤补充条款 【新增肿瘤特色】

- **T-1 多维分型不污染诊断角色**：组织学类型、TNM 分期、分子分型是同一疾病的不同描述轴，通过扩展模块挂在疾病下，不各自新建一条 Disease。
- **T-2 分子检测是靶向/免疫推荐的前置触发条件**：推荐陈述必须显式关联 Biomarker，并标明「需检测结果支持」。
- **T-3 TNM 分期保留标准版本与阈值**：TNM 分期是肿瘤治疗策略（手术 / 新辅助 / 辅助 / 姑息）的核心路由条件，必须保留原文分期标准、版本（AJCC/UICC 第几版）与阈值。
- **T-4 肿瘤指南更新按来源裁决**：NCCN/CSCO 年度更新存在多版指南冲突时，按来源年份、版本、适用范围、发布机构权威度裁决，不覆盖旧证据。
- **T-5 治疗方案下钻到可执行动作**：化疗方案、放疗方案、靶向/免疫方案是「治疗方案」下属的可执行动作集合，必须下钻到具体药品或操作，不得只保留方案标题。
- **T-6 扩展实体进入医嘱时绑定标准字典**：肿瘤标志物、基因变异、蛋白表达、体能状态评分、不良反应分级，默认只做知识展示与推荐条件；进入正式医嘱动作时，其承载实体（检验、药品）必须绑定标准字典。

---

## 2. 总体架构 【复用通用结构】

### 2.1 五个层次

| 层次 | 作用 | 典型实体 | 入图谱 | 默认展示 |
|---|---|---|---|---|
| 目录层 | 组织专科和疾病大类 | Specialty<br>DiseaseCategory<br>DiseaseSubcategory | 是 | 是 |
| 临床诊断层 | 表示疑似诊断、待分型诊断、具体分型诊断 | Disease、StandardDiagnosis | 是 | 是 |
| 医学知识层 | 表示疾病定义、病因、症状、检查、治疗、随访 | Definition、Symptom、ExamItem<br>Medication、Procedure | 是 | 是 |
| 决策层 | 表示可触发的正式推荐 | ClinicalRule<br>RecommendationStatement<br>TreatmentPlan | 是 | 按场景展示 |
| 证据治理层 | 追溯教材、指南、页码、原文和抽取过程 | Guideline、Evidence、SourceSection、治理字段 | 是 | 只展示证据摘要入口 |

### 2.2 疾病三层结构

| 层级 | 实体类型 | 中文解释 | 临床诊断 | 肿瘤示例 | 来源 |
|---|---|---|---|---|---|
| 顶层学科 | Specialty | 专科根节点 | 否 | 肿瘤内科 | 复用通用 |
| 疾病大类 | DiseaseCategory | 专科下的疾病大类 | 否 | 呼吸系统肿瘤 | 复用通用 |
| 疾病亚类 | DiseaseSubcategory | 大类下的展示分组 | 否 | 结肠肿瘤 | 复用通用 |
| 疑似或待分型诊断 | Disease | 临床可先选择但需继续分型的诊断 | 是 | 结直肠癌 | 复用通用 |
| 具体分型诊断 | Disease | 诊断明确后的分型 | 是 | 结直肠腺癌、子宫颈鳞癌 | 复用通用 |
| 标准诊断 | StandardDiagnosis | ICD 标准字典记录，含编码和名称 | 是，用于回填和映射 | ICD-10 C18 + ICD-O-3 形态学码 | 复用通用 |

`DiseaseSubcategory` 只用于目录分组和页面导航，不参与诊断回填，不参与疑似疾病推荐排序。

### 2.3 诊断角色 【复用通用结构】

`Disease.diagnostic_role` 用来说明疾病节点在临床流程中的角色。

| 值 | 中文含义 | 使用场景 | 肿瘤示例 | 来源 |
|---|---|---|---|---|
| `suspected_parent` | 疑似或待分型诊断 | 医生早期只能判断大方向，后续需分型 | 结直肠癌 | 复用通用 |
| `specific_subtype` | 具体分型诊断 | 诊断证据充分，可进入出院诊断或明确诊断 | 结直肠腺癌、子宫颈鳞癌 | 复用通用 |
| `standalone_diagnosis` | 独立诊断 | 不依赖上级待分型诊断，自身即完整诊断 | 卵巢上皮癌 | 复用通用 |

### 2.4 标准诊断实体 【复用通用结构 + 新增肿瘤】

| 字段 | 中文名 | 格式要求 | 示例 | 来源 |
|---|---|---|---|---|
| `std_dict_id` | 标准字典主键 | 标准字典唯一主键 | `7f...` | 复用通用 |
| `standard_code` | 标准编码 | 原样保存字典编码 | `C18.7` | 复用通用 |
| `standard_name` | 标准名称 | 字典标准中文名 | 结直肠腺癌 | 复用通用 |
| `coding_system` | 编码体系 | `ICD-10`、`ICD-11`、`ICD-9-CM-3`、`ICD-O-3` | ICD-10 + ICD-O-3 | 复用通用 |
| `source_table` | 来源表 | 标准字典表名 | 标准诊断字典表 | 复用通用 |
| `valid_flag` | 有效标志 | 仅有效记录可进入正式链 | 1 | 复用通用 |
| `dictionary_validation_status` | 字典校验状态 | `validated`、`pending_review`、`blocked` | validated | 复用通用 |
| `oncology_topography_code` | 解剖部位码 | ICD-O-3 部位码 | C18 | 新增肿瘤 |
| `oncology_morphology_code` | 形态学码 | ICD-O-3 形态学码（含行为学） | 8140/3 | 新增肿瘤 |

> 肿瘤的「解剖部位码 + 形态学码」组合，在 `standard_code` 中保留 ICD-O-3 形态学码，并补充 `oncology_topography_code`、`oncology_morphology_code` 两个扩展字段。

---

## 3. 肿瘤疾病目录与多维分型结构

### 3.1 目录层 【复用通用结构】

```text
Specialty 专科：肿瘤内科 / 肿瘤外科 / 放疗科（按院内学科组织）【新增肿瘤】
 └─ DiseaseCategory 疾病大类：按解剖系统/部位，如 呼吸系统肿瘤、消化系统肿瘤、乳腺肿瘤、血液系统肿瘤【新增肿瘤】
 └─ DiseaseSubcategory 疾病亚类：按器官/组织来源，如 结肠肿瘤、胃肿瘤、乳腺肿瘤【新增肿瘤】
 └─ Disease 疾病：待分型诊断或具体亚型，如 结直肠癌、结直肠腺癌、子宫颈鳞癌【新增肿瘤】
```

### 3.2 多维分型轴 【新增肿瘤特色】

肿瘤的「同一个病」常同时被组织学、分期、分子状态三种轴描述。用扩展模块表达，不新建平行的 Disease 节点。

| 分型轴 | 表达方式 | 实体/扩展模块 | 来源 |
|---|---|---|---|
| 组织学类型 | 扩展模块 `oncology_histopathology` | HistologyType、DifferentiationGrade | 新增肿瘤 |
| TNM 分期 | 扩展模块 `oncology_tnm_staging` | TCategory、NCategory、MCategory<br>TNMTStage、StageGrouping | 新增肿瘤 |
| 分子分型 | 扩展模块 `oncology_molecular` | Biomarker、Gene、GeneticVariant、MolecularSubtype | 新增肿瘤 |
| 诊断角色 | `Disease.diagnostic_role` | suspected_parent<br>specific_subtype<br>standalone_diagnosis | 复用通用 |

### 3.3 诊断角色映射示例 【新增肿瘤特色】

```text
结直肠癌（suspected_parent，待分型，ICD-10 C18/C20）
 ├─ 结直肠腺癌（specific_subtype）
 │ └─ RAS 野生型结直肠腺癌（分子分型挂扩展模块，不新建 Disease）
 ├─ 直肠鳞状细胞癌（specific_subtype）
 └─ 结肠神经内分泌肿瘤（specific_subtype，独立分型）
```

「RAS 野生型结直肠腺癌」不单独新建 Disease 节点，而是「结直肠腺癌」+ `oncology_molecular` 扩展模块的分子分型实体组合表达。诊断回填时，标准诊断编码仍映射到 C18/C20 系列 + 组织学 + 分子备注。

---

## 4. 标准实体类型

### 4.1 目录和疾病 【复用通用结构】

| 实体类型 entityType | 中文名 | 用途 | 来源 |
|---|---|---|---|
| `Specialty` | 专科 | 多专科根节点 | 复用通用 |
| `DiseaseCategory` | 疾病大类 | 专科下的大类目录 | 复用通用 |
| `DiseaseSubcategory` | 疾病亚类 | 大类下的可选分组 | 复用通用 |
| `Disease` | 疾病/诊断 | 疑似诊断、待分型诊断、具体分型诊断、独立诊断 | 复用通用 |
| `StandardDiagnosis` | 标准诊断字典项 | ICD 诊断身份 | 复用通用 |
| `MedicalTermAlias` | 术语别名 | 别名、检索、归一（由 `has_alias` 挂到疾病） | 复用通用 |

### 4.2 医学事实 【复用通用结构】

| 实体类型 entityType | 中文名 | 用途 | 来源 |
|---|---|---|---|
| `Definition` | 疾病定义 | 疾病概述和定义原文摘要 | 复用通用 |
| `DefinitionComponent` | 定义明细 | 定义可拆解要点 | 复用通用 |
| `Etiology` | 病因 | 发病原因 | 复用通用 |
| `Pathophysiology` | 病理生理 | 机制和功能变化 | 复用通用 |
| `Epidemiology` | 流行病学 | 发病趋势、人群特征 | 复用通用 |
| `Symptom` | 症状 | 患者主观感受 | 复用通用 |
| `Sign` | 体征 | 医生查体观察结果 | 复用通用 |
| `VitalSignItem` | 生命体征 | 体温、脉搏、呼吸、血压、血氧饱和度 | 复用通用 |
| `RiskFactor` | 危险因素 | 增加发病或不良结局风险的因素 | 复用通用 |
| `Complication` | 并发症 | 疾病导致的并发问题 | 复用通用 |
| `DifferentialDiagnosis` | 鉴别诊断 | 需要区分的疾病或状态 | 复用通用 |
| `RiskStratification` | 风险分层 | 风险评分或分层结果 | 复用通用 |
| `Prognosis` | 预后 | 结局、复发、死亡风险 | 复用通用 |
| `Prevention` | 预防 | 一级预防、二级预防、患者教育 | 复用通用 |
| `FollowUp` | 随访 | 复查、康复、长期管理 | 复用通用 |
| `Contraindication` | 禁忌/排除条件 | 推荐动作不可执行的条件 | 复用通用 |

### 4.3 检查、检验、治疗和动作 【复用通用结构】

| 实体类型 entityType | 中文名 | 用途 | 来源 |
|---|---|---|---|
| `ExamPlan` | 检查方案 | 一组检查项目的临床方案 | 复用通用 |
| `ExamItem` | 检查项目 | 可开立或可执行的检查 | 复用通用 |
| `ExamObservation` | 检查发现 | 检查报告中的观察结论 | 复用通用 |
| `LabItem` | 检验项目 | 可开立的检验项目 | 复用通用 |
| `LabSubitem` | 检验细项 | 检验项目下的指标细项 | 复用通用 |
| `LabSample` | 检验标本 | 标本类型 | 复用通用 |
| `TreatmentPlan` | 治疗方案 | 临床治疗策略标题 | 复用通用 |
| `Medication` | 药品 | 标准药品或药物类别 | 复用通用 |
| `Procedure` | 手术/操作 | 标准手术或操作项目 | 复用通用 |
| `TreatmentItem` | 治疗项目 | 非药品、非手术的治疗处置 | 复用通用 |

治疗方案是策略，药品、手术、治疗项目是可执行动作。疾病大类可以有共性知识，但正式推荐动作优先挂在具体诊断、场景和规则链路下。

### 4.4 来源、证据和推荐 【复用通用结构】

| 实体类型 entityType | 中文名 | 用途 | 来源 |
|---|---|---|---|
| `Guideline` | 指南/教材/共识/说明书 | 文献级来源 | 复用通用 |
| `SourceSection` | 来源章节 | 文献章节或页码范围 | 复用通用 |
| `Evidence` | 证据片段 | 原文证据摘要，支撑某个知识或推荐 | 复用通用 |
| `ClinicalRule` | 临床规则 | 触发条件、排除条件、判断逻辑 | 复用通用 |
| `RecommendationStatement` | 推荐陈述 | 正式推荐展示和审核主体 | 复用通用 |

### 4.5 肿瘤扩展实体类型 【新增肿瘤特色】

| 实体类型 | 中文名 | 扩展模块 | 用途 | 示例 | 来源 |
|---|---|---|---|---|---|
| `HistologyType` | 组织学类型 | `oncology_histopathology` | 组织学分型 | 腺癌、鳞癌 | 新增肿瘤 |
| `DifferentiationGrade` | 分化程度 | `oncology_histopathology` | 高/中/低分化 | 中分化 | 新增肿瘤 |
| `PrimarySite` | 原发部位 | `oncology_histopathology` | 器官内具体部位 | 直肠上段 | 新增肿瘤 |
| `TCategory` | T 分期 | `oncology_tnm_staging` | 原发肿瘤范围 | T2a | 新增肿瘤 |
| `NCategory` | N 分期 | `oncology_tnm_staging` | 区域淋巴结转移 | N1 | 新增肿瘤 |
| `MCategory` | M 分期 | `oncology_tnm_staging` | 远处转移 | M1b | 新增肿瘤 |
| `TNMTStage` | TNM 分期实例 | `oncology_tnm_staging` | 组合分期 | IIIA 期 | 新增肿瘤 |
| `StageGrouping` | 分期分组 | `oncology_tnm_staging` | 总分期归类 | Stage III | 新增肿瘤 |
| `TumorTopographyCode` | 解剖部位码 | `oncology_tnm_staging` | ICD-O-3 部位 | C18 | 新增肿瘤 |
| `TumorMorphologyCode` | 形态学码 | `oncology_tnm_staging` | ICD-O-3 形态学 | 8140/3 | 新增肿瘤 |
| `Biomarker` | 生物标志物 | `oncology_molecular` | 靶向/免疫触发 | EGFR 突变 | 新增肿瘤 |
| `Gene` | 基因 | `oncology_molecular` | 驱动基因 | EGFR、ALK | 新增肿瘤 |
| `GeneticVariant` | 基因变异 | `oncology_molecular` | 具体变异 | EGFR L858R | 新增肿瘤 |
| `FusionGene` | 融合基因 | `oncology_molecular` | 融合事件 | EML4-ALK | 新增肿瘤 |
| `ProteinExpression` | 蛋白表达 | `oncology_molecular` | IHC 表达 | PD-L1 TPS≥50% | 新增肿瘤 |
| `MolecularSubtype` | 分子分型 | `oncology_molecular` | 分子亚型 | RAS 野生型 | 新增肿瘤 |
| `TumorMarker` | 肿瘤标志物 | `oncology_tumor_markers` | 随访监测 | CEA、CA125 | 新增肿瘤 |
| `ChemoRegimen` | 化疗方案 | `oncology_chemotherapy` | 化疗执行 | FOLFOX | 新增肿瘤 |
| `ChemoCycle` | 化疗周期 | `oncology_chemotherapy` | 周期/疗程 | 第 3 周期 | 新增肿瘤 |
| `TargetedDrug` | 靶向药 | `oncology_targeted_immuno` | 靶向动作（绑定药品字典） | 西妥昔单抗 | 新增肿瘤 |
| `ImmuneCheckpointInhibitor` | 免疫检查点抑制剂 | `oncology_targeted_immuno` | 免疫动作（绑定药品字典） | 帕博利珠单抗 | 新增肿瘤 |
| `AntiAngiogenicDrug` | 抗血管生成药 | `oncology_targeted_immuno` | 抗血管动作（绑定药品字典） | 贝伐珠单抗 | 新增肿瘤 |
| `RadiotherapyPlan` | 放疗方案 | `oncology_radiotherapy` | 放疗执行 | 根治性放疗 | 新增肿瘤 |
| `TargetVolume` | 靶区 | `oncology_radiotherapy` | 照射范围 | GTV、CTV | 新增肿瘤 |
| `RadiationDose` | 照射剂量 | `oncology_radiotherapy` | 剂量分割 | 60Gy/30f | 新增肿瘤 |
| `MetastaticSite` | 转移部位 | `oncology_metastasis_recurrence` | 远处转移定位 | 肝转移 | 新增肿瘤 |
| `Oligometastasis` | 寡转移 | `oncology_metastasis_recurrence` | 寡转移判定 | 单器官≤3 灶 | 新增肿瘤 |
| `Recurrence` | 复发状态 | `oncology_metastasis_recurrence` | 复发判定 | 术后复发 | 新增肿瘤 |
| `PerformanceStatus` | 体能状态评分 | `oncology_performance_status` | 耐受性条件 | ECOG 1 | 新增肿瘤 |
| `AdverseEvent` | 不良反应 | `oncology_adverse_event` | 风险提示 | 粒细胞减少 | 新增肿瘤 |
| `AEGrade` | 不良反应分级 | `oncology_adverse_event` | CTCAE 分级 | G3 | 新增肿瘤 |

「扩展模块」是启用单位：第 11 章按模块（如 `oncology_tnm_staging`）配置启用与审计规则，启用某模块后该组实体才允许入库。实体进入展示/推荐/字典绑定的边界见第 11.3 章。

---

## 5. 标准关系

### 5.1 疾病目录和诊断关系 【复用通用结构】

| 起点 | 关系 | 终点 | 中文含义 | 来源 |
|---|---|---|---|---|
| Specialty | `has_category` | DiseaseCategory | 专科包含疾病大类 | 复用通用 |
| DiseaseCategory | `has_subcategory` | DiseaseSubcategory | 大类包含疾病亚类 | 复用通用 |
| DiseaseCategory | `has_disease` | Disease | 大类包含疾病诊断 | 复用通用 |
| DiseaseSubcategory | `has_disease` | Disease | 亚类包含疾病诊断 | 复用通用 |
| Disease | `has_clinical_subtype` | Disease | 待分型诊断包含具体分型 | 复用通用 |
| Disease | `has_standard_diagnosis` | StandardDiagnosis | 疾病绑定标准诊断 | 复用通用 |
| Disease | `has_alias` | MedicalTermAlias | 疾病别名 | 复用通用 |

### 5.2 医学事实关系 【复用通用结构】

| 起点 | 关系 | 终点 | 中文含义 | 来源 |
|---|---|---|---|---|
| Disease | `has_definition` | Definition | 有疾病定义 | 复用通用 |
| Definition | `has_definition_component` | DefinitionComponent | 定义拆解明细 | 复用通用 |
| Disease | `has_etiology` | Etiology | 有病因 | 复用通用 |
| Disease | `has_pathophysiology` | Pathophysiology | 有病理生理 | 复用通用 |
| Disease | `has_epidemiology` | Epidemiology | 有流行病学 | 复用通用 |
| Disease | `has_symptom` | Symptom | 有症状 | 复用通用 |
| Disease | `has_sign` | Sign | 有体征 | 复用通用 |
| Disease | `has_risk_factor` | RiskFactor | 有危险因素 | 复用通用 |
| Disease | `has_complication` | Complication | 有并发症 | 复用通用 |
| Disease | `has_differential_diagnosis` | DifferentialDiagnosis | 有鉴别诊断对象 | 复用通用 |
| DifferentialDiagnosis | `has_differential_rule` | ClinicalRule | 有鉴别规则 | 复用通用 |
| DifferentialDiagnosis | `requires_exclusion_exam` | ExamItem | 鉴别诊断需要排除检查 | 复用通用 |
| DifferentialDiagnosis | `requires_exclusion_lab` | LabItem/LabSubitem | 鉴别诊断需要排除检验或检验细项 | 复用通用 |
| Disease | `has_risk_stratification` | RiskStratification | 有风险分层 | 复用通用 |
| Disease | `has_followup` | FollowUp | 有随访 | 复用通用 |
| Disease | `has_prognosis` | Prognosis | 有预后 | 复用通用 |

### 5.3 检查和检验关系 【复用通用结构】

| 起点 | 关系 | 终点 | 中文含义 | 来源 |
|---|---|---|---|---|
| Disease | `has_exam_plan` | ExamPlan | 疾病有检查方案 | 复用通用 |
| ExamPlan | `includes_exam_item` | ExamItem | 检查方案包含检查项目 | 复用通用 |
| ExamItem | `exam_item_has_observation` | ExamObservation | 检查项目产生检查发现 | 复用通用 |
| Disease | `has_lab_plan` | ExamPlan | 疾病有检验方案 | 复用通用 |
| ExamPlan | `includes_lab_item` | LabItem | 检验方案包含检验项目 | 复用通用 |
| LabItem | `lab_item_has_subitem` | LabSubitem | 检验项目包含检验细项 | 复用通用 |
| LabSubitem | `uses_lab_sample` | LabSample | 检验细项使用标本 | 复用通用 |

检查和检验项目可以被多个场景复用。是否推荐给医生，不由项目名称决定，而由"关系上的业务语义"决定。

| 关系字段 | 中文含义 | 必填范围 | 来源 |
|---|---|---|---|
| `clinical_stage` | 诊疗阶段 | 检查、检验、治疗动作关系必填 | 复用通用 |
| `purpose` | 推荐目的 | 检查、检验、治疗动作关系必填 | 复用通用 |
| `recommendation_context` | 推荐语境 | 正式推荐必填 | 复用通用 |
| `service_target_type` | 服务对象类型 | 正式推荐必填 | 复用通用 |
| `service_target_code` | 服务对象编码 | 正式推荐必填 | 复用通用 |
| `service_target_name` | 服务对象名称 | 正式推荐必填 | 复用通用 |
| `priority_level` | 推荐优先级 | 正式推荐必填 | 复用通用 |

硬规则：

1. 疾病直连检查/检验只能表示"知识上相关"，不能直接作为医生端正式推荐。
2. 首诊辅助检查必须挂在 ExamPlan/LabPlan，并标明 `clinical_stage=首诊`、`purpose=确诊/分型/风险分层`。
3. 鉴别诊断检查必须从 DifferentialDiagnosis 出发，或由 RecommendationStatement 指向鉴别对象和推荐动作，不能只挂在疾病下面。
4. 治疗前检查必须从 TreatmentPlan 或 RecommendationStatement 出发，标明 `purpose=治疗前安全评估/禁忌排除`。
5. 禁止新增关系 `RECOMMEND_CHECK`、`RECOMMEND_LAB_CHECK`、`HAS_DRUG`、`RECOMMEND_OPERATION`。

### 5.4 治疗和正式推荐关系 【复用通用结构】

| 起点 | 关系 | 终点 | 中文含义 | 来源 |
|---|---|---|---|---|
| Disease | `has_treatment_plan` | TreatmentPlan | 疾病有治疗方案 | 复用通用 |
| TreatmentPlan | `includes_medication` | Medication | 方案包含药品 | 复用通用 |
| TreatmentPlan | `includes_procedure` | Procedure | 方案包含手术/操作 | 复用通用 |
| TreatmentPlan | `includes_treatment_item` | TreatmentItem | 方案包含其他治疗项目 | 复用通用 |
| Disease | `has_recommendation_statement` | RecommendationStatement | 疾病有正式推荐陈述 | 复用通用 |
| ClinicalRule | `triggers_recommendation` | RecommendationStatement | 规则触发推荐陈述 | 复用通用 |
| RecommendationStatement | `recommends_action` | Medication<br>Procedure<br>TreatmentItem<br>ExamItem<br>LabItem<br>LabSubitem | 推荐陈述指向具体动作 | 复用通用 |
| RecommendationStatement | `targets_differential_diagnosis` | DifferentialDiagnosis | 推荐服务于鉴别诊断 | 复用通用 |
| RecommendationStatement | `has_contraindication` | Contraindication | 推荐有禁忌或排除条件 | 复用通用 |

`has_treatment_plan`、`includes_medication`、`includes_procedure`、`includes_treatment_item` 表示知识展示和方案下钻；`recommends_action` 只允许从 RecommendationStatement 出发，表示患者满足规则后的正式推荐。两者不得混用。

正式推荐链路必须至少具备：

```text
疾病或鉴别对象
→ 规则或适用场景
→ 推荐陈述
→ 具体动作（检查、检验、药品、手术、治疗项目）
→ 主证据
```

### 5.5 来源和证据关系 【复用通用结构】

| 起点 | 关系 | 终点 | 中文含义 | 来源 |
|---|---|---|---|---|
| Guideline | `has_source_section` | SourceSection | 文献包含章节 | 复用通用 |
| SourceSection | `has_evidence` | Evidence | 章节包含证据片段 | 复用通用 |
| 任一医学知识实体 | `supported_by_evidence` | Evidence | 知识有证据支撑 | 复用通用 |
| RecommendationStatement | `supported_by_evidence` | Evidence | 推荐陈述有证据支撑 | 复用通用 |
| RecommendationStatement | `derived_from` | Evidence | 推荐陈述来源于证据片段 | 复用通用 |
| RecommendationStatement | `based_on_guideline` | Guideline | 推荐依据指南 | 复用通用 |
| RecommendationStatement | `uses_primary_guideline` | Guideline | 推荐主依据文献 | 复用通用 |

主证据不是靠额外新关系名区分，而是靠 `RecommendationStatement.primary_evidence_code` 指向主 Evidence；支持证据仍可通过 `supported_by_evidence` 或 `derived_from` 关联。

### 5.6 肿瘤扩展关系 【新增肿瘤特色】

| 起点 | 关系 | 终点 | 中文含义 | 示例 | 来源 |
|---|---|---|---|---|---|
| Disease | `disease_has_tnm_stage` | TCategory<br>NCategory<br>MCategory<br>TNMTStage<br>StageGrouping | 分期知识展示/解释 | 结直肠癌 → T3 | 新增肿瘤 |
| StandardDiagnosis | `has_topography_code` | TumorTopographyCode | 诊断含 ICD-O-3 部位码 | C18 诊断 → C18 | 新增肿瘤 |
| StandardDiagnosis | `has_morphology_code` | TumorMorphologyCode | 诊断含 ICD-O-3 形态学码 | C18 诊断 → 8140/3 | 新增肿瘤 |
| Disease | `diagnosis_criteria_uses_tnm` | TNMTStage | 诊断标准下钻分期 | 诊断标准 → IIIA 期 | 新增肿瘤 |
| RecommendationStatement | `recommendation_requires_tnm_stage` | TNMTStage | 正式推荐路由条件 | 推荐 → 需 IIIA 期 | 新增肿瘤 |
| Disease | `disease_has_histology_type` | HistologyType | 组织学类型 | 结直肠腺癌 → 腺癌 | 新增肿瘤 |
| Disease | `disease_has_differentiation` | DifferentiationGrade | 分化程度 | 结直肠腺癌 → 中分化 | 新增肿瘤 |
| Disease | `disease_has_primary_site` | PrimarySite | 原发部位 | 结直肠腺癌 → 直肠上段 | 新增肿瘤 |
| Disease | `disease_has_molecular_subtype` | MolecularSubtype | 分子分型 | 结直肠腺癌 → RAS 野生型 | 新增肿瘤 |
| Disease | `disease_has_biomarker` | Biomarker | 疾病相关生物标志物 | 结直肠癌 → RAS 状态 | 新增肿瘤 |
| Disease | `disease_has_gene` | Gene | 疾病相关驱动基因 | 结直肠癌 → KRAS | 新增肿瘤 |
| Gene | `gene_has_variant` | GeneticVariant | 基因含变异 | KRAS → G12D | 新增肿瘤 |
| Gene | `gene_has_fusion` | FusionGene | 基因融合事件 | EML4 → EML4-ALK | 新增肿瘤 |
| Biomarker | `biomarker_has_protein_expression` | ProteinExpression | 标志物蛋白表达 | PD-L1 → TPS≥50% | 新增肿瘤 |
| Biomarker | `biomarker_guides_targeted_therapy` | TargetedDrug | 标志物指导靶向 | RAS 野生型 → 西妥昔单抗 | 新增肿瘤 |
| RecommendationStatement | `recommendation_requires_biomarker` | Biomarker | 靶向/免疫前置触发 | 推荐 → 需 RAS 野生型 | 新增肿瘤 |
| Disease | `disease_has_tumor_marker` | TumorMarker | 肿瘤标志物 | 结直肠癌 → CEA | 新增肿瘤 |
| TumorMarker | `tumor_marker_uses_lab_subitem` | LabSubitem | 标志物下钻检验细项 | CEA → CEA 检测 | 新增肿瘤 |
| RecommendationStatement | `recommendation_uses_tumor_marker` | TumorMarker | 随访/监测条件 | 推荐 → 监测 CEA | 新增肿瘤 |
| TreatmentPlan | `treatment_plan_includes_chemo_regimen` | ChemoRegimen | 方案含化疗方案 | 新辅助 → FOLFOX | 新增肿瘤 |
| ChemoRegimen | `chemo_regimen_includes_medication` | Medication | 化疗方案含药品 | FOLFOX → 奥沙利铂 | 新增肿瘤 |
| ChemoRegimen | `chemo_regimen_has_cycle` | ChemoCycle | 方案含周期/疗程规则 | FOLFOX → 每2周×12周期 | 新增肿瘤 |
| RecommendationStatement | `recommendation_statement_recommends_chemo_regimen` | ChemoRegimen | 推荐化疗方案 | 推荐 → FOLFOX | 新增肿瘤 |
| RecommendationStatement | `recommends_action` | TargetedDrug / ImmuneCheckpointInhibitor / AntiAngiogenicDrug | 推荐靶向/免疫药（复用通用 `recommends_action`） | 推荐 → 西妥昔单抗 | 新增肿瘤 |
| TreatmentPlan | `treatment_plan_includes_radiotherapy` | RadiotherapyPlan | 方案含放疗 | 根治 → 根治性放疗 | 新增肿瘤 |
| RadiotherapyPlan | `radiotherapy_has_target_volume` | TargetVolume | 放疗含靶区 | 方案 → GTV | 新增肿瘤 |
| RadiotherapyPlan | `radiotherapy_has_dose` | RadiationDose | 放疗含照射剂量 | 方案 → 60Gy/30f | 新增肿瘤 |
| RecommendationStatement | `recommendation_statement_recommends_radiotherapy` | RadiotherapyPlan | 推荐放疗 | 推荐 → 根治性放疗 | 新增肿瘤 |
| Disease | `disease_has_metastatic_site` | MetastaticSite | 转移部位 | 结直肠癌 → 肝转移 | 新增肿瘤 |
| Disease | `disease_has_oligometastasis` | Oligometastasis | 寡转移状态 | 结直肠癌 → 肝寡转移 | 新增肿瘤 |
| Disease | `disease_has_recurrence` | Recurrence | 复发状态 | 术后 → 复发 | 新增肿瘤 |
| RecommendationStatement | `recommendation_uses_recurrence_status` | Recurrence | 复发相关推荐 | 推荐 → 复发后治疗 | 新增肿瘤 |
| RecommendationStatement | `recommendation_requires_performance_status` | PerformanceStatus | 耐受性触发/排除 | 推荐 → 需 ECOG≤1 | 新增肿瘤 |
| Medication | `medication_has_adverse_event` | AdverseEvent | 药品不良反应 | 西妥昔单抗 → 皮疹 | 新增肿瘤 |
| AdverseEvent | `adverse_event_has_grade` | AEGrade | 不良反应含分级 | 皮疹 → G3 | 新增肿瘤 |
| RecommendationStatement | `recommendation_has_ae_warning` | AdverseEvent | 推荐含 AE 警示 | 推荐 → 输液反应警示 | 新增肿瘤 |
| AdverseEvent | `blocks_action` | Medication / Procedure | AE 阻断动作 | G3 皮疹 → 暂停靶向 | 新增肿瘤 |

---

## 6. 字段标准

### 6.1 所有业务节点通用字段 【复用通用结构】

| 字段 | 中文名 | 格式要求 | 知识展示 | 来源 |
|---|---|---|---|---|
| `id` | 图谱内部ID | 全库唯一字符串 | 否 | 复用通用 |
| `entityType` | 实体类型 | 使用第 4 章枚举值 | 是 | 复用通用 |
| `code` | 图谱编码 | 稳定、可追溯、不得复用 | 是 | 复用通用 |
| `name` | 标准主名称 | 中文标准全称优先 | 是 | 复用通用 |
| `display_name` | 展示名称 | 默认等于 `name`，确有展示需要才单独设置 | 是 | 复用通用 |
| `aliases` | 别名 | 字符串数组 | 是 | 复用通用 |
| `description` | 描述 | 简短中文说明 | 是 | 复用通用 |
| `status` | 数据状态 | `active`、`deprecated`、`blocked` | 治理页展示 | 复用通用 |
| `source` | 来源名称 | 具体书籍、指南、共识、说明书或字典表名称 | 证据页展示 | 复用通用 |
| `schema_version` | Schema 版本 | V主版本.次版本 | 治理页展示 | 复用通用 |

### 6.2 标准字典字段 【复用通用结构】

| 字段 | 中文名 | 格式要求 | 适用实体 | 来源 |
|---|---|---|---|---|
| `std_dict_id` | 标准字典主键 | 标准字典唯一主键 | StandardDiagnosis、Medication、Procedure<br>ExamItem、LabItem、LabSubitem<br>Symptom、Sign、VitalSignItem<br>TreatmentItem | 复用通用 |
| `standard_code` | 标准编码 | 原样保存字典编码 | 同上 | 复用通用 |
| `standard_name` | 标准名称 | 字典标准中文名 | 同上 | 复用通用 |
| `source_table` | 来源表 | 标准字典表名 | 同上 | 复用通用 |
| `valid_flag` | 有效标志 | 只允许有效值进入正式链 | 同上 | 复用通用 |
| `dictionary_validation_status` | 字典校验状态 | `validated`、`pending_review`、`blocked` | 同上 | 复用通用 |
| `dictionary_snapshot_version` | 字典快照版本 | 每次同步生成稳定版本号 | 同上 | 复用通用 |

### 6.3 基础人群和有效性限制 【复用通用结构】

| 字段 | 中文名 | 格式要求 | 来源 |
|---|---|---|---|
| `sex_limit_code` | 性别限制编码 | 使用标准字典值，空表示不限制 | 复用通用 |
| `sex_limit_name` | 性别限制名称 | 不限制、男性、女性 | 复用通用 |
| `age_min` | 最小年龄 | 数值或空 | 复用通用 |
| `age_max` | 最大年龄 | 数值或空 | 复用通用 |
| `age_unit` | 年龄单位 | 岁、月、天 | 复用通用 |
| `pregnancy_limit_code` | 妊娠限制编码 | 标准字典值或空 | 复用通用 |
| `pregnancy_limit_name` | 妊娠限制名称 | 不限制、慎用、禁用 | 复用通用 |
| `lactation_limit_code` | 哺乳限制编码 | 标准字典值或空 | 复用通用 |
| `lactation_limit_name` | 哺乳限制名称 | 不限制、慎用、禁用 | 复用通用 |
| `valid_from` | 生效时间 | 日期或空 | 复用通用 |
| `valid_to` | 失效时间 | 日期或空 | 复用通用 |

基础过滤顺序：有效期 → 性别 → 年龄 → 妊娠 → 哺乳。基础过滤后，再由规则引擎判断肝肾功能、过敏史、出血风险、药物相互作用、检查结果、诊疗阶段、时间窗、既往手术、孕产状态、并发症。

### 6.4 AI解析治理字段 【复用通用结构】

这些字段允许保存在图谱，但图谱元模型配置页和医生端默认不展示。

| 字段 | 中文名 | 用途 |
|---|---|---|
| `batch_id` | 批次编号 | 追溯解析批次 |
| `scope_type` | 范围类型 | 标记专科、大类、病种 |
| `scope_target` | 范围目标 | 标记本批次疾病 |
| `source_roots` | 来源目录 | 追溯本地资料路径 |
| `parser_version` | 解析工具版本 | 定位解析逻辑 |
| `extraction_version` | 抽取版本 | 区分抽取轮次 |
| `import_batch` | 入库批次 | 支持回滚 |
| `migration_status` | 迁移状态 | 旧结构清理 |
| `repair_status` | 修复状态 | 问题闭环 |
| `source_hash` | 来源哈希 | 文件校验 |
| `evidence_hash` | 证据哈希 | 证据去重 |
| `raw_text_anchor` | 原文锚点 | 页码、段落、章节定位 |
| `audit_result` | 审计结果 | 质量检查 |
| `review_notes` | 审核备注 | 人工或模型复核说明 |

---

## 7. 标准字典映射

### 7.1 既有字典来源（通用） 【复用通用结构】

| 图谱实体 | 标准来源表 | 使用方式 | 备注 |
|---|---|---|---|
| StandardDiagnosis | 标准诊断字典表 | 诊断标准主数据 | 只使用有效记录；肿瘤补 ICD-O-3 |
| Procedure | 标准手术操作字典表 | 手术/操作标准主数据 | 图谱统一用 Procedure 实体 |
| Medication | 标准药品字典表 | 药品标准主数据 | 药品全称为主名 |
| ExamItem | 标准检查项目字典表 | 检查项目字典 | X线、CT 这类笼统词不得直接作为最终项目 |
| LabItem | 标准检验项目字典表 | 检验项目字典 | 肿瘤标志物、血常规 |
| LabSubitem | 标准检验细项字典表 | 检验细项字典 | CEA、CYFRA21-1 |
| Symptom | 标准症状字典表 | 症状字典 | 主观感受 |
| VitalSignItem | 标准生命体征字典表 | 生命体征标准字典 | 体温、脉搏、呼吸、血压、血氧饱和度 |
| TreatmentItem | 标准治疗项目字典表 | 其他治疗项目字典 | 放疗、最佳支持治疗 |
| MedicalTermAlias | 标准术语字典表 | 术语和可选用词 | 用于别名、检索、归一 |

### 7.2 需要新增或已新增的字典来源（肿瘤专病） 【新增肿瘤特色】

| 图谱实体 | 建议表名 | 使用方式 | 备注 |
|---|---|---|---|
| TumorMarker | 肿瘤标志物字典表 | 肿瘤标志物字典 | 映射到检验细项 |
| HistologyType | 病理分型字典表 | 病理分型/组织学类型字典 | 腺癌、鳞癌等 |
| Biomarker | 分子检测字典表 | 分子检测项目字典 | 检测项目映射检验字典 |
| Gene / GeneticVariant | 基因变异字典表 | 基因与变异字典 | 基因/变异不走医嘱 |
| TNMTStage | TNM 分期字典表 | TNM 分期字典 | 分期路由条件 |
| TumorTopographyCode<br>TumorMorphologyCode | ICD-O-3 编码字典表 | 解剖部位码/形态学码字典 | 标准编码，不走医嘱 |
| ChemoRegimen | 化疗方案字典表 | 化疗方案字典 | 方案下药品仍走药品字典 |
| RadiotherapyPlan | 放疗项目字典表 | 放疗项目字典 | 映射治疗项目/操作字典 |
| AdverseEvent / AEGrade | 不良反应字典表（CTCAE） | 不良反应字典 | 无则暂映射并发症 |
| PerformanceStatus | 体能状态评分字典表 | 体能状态评分字典 | 不走医嘱 |

新增授权字典可直接注册；旧字典修名、合并、删除必须进入待处理清单。

### 7.3 名称归一规则

#### 7.3.1 通用规则 【复用通用结构】

| 情况 | 处理方式 | 示例 |
|---|---|---|
| 英文缩写 | 标准中文全称为主名，缩写进别名 | PCI → 经皮冠状动脉介入治疗 |
| 口语药名 | 匹配规范剂型名，口语名进别名 | 肠溶阿司匹林 → 阿司匹林肠溶片 |
| 品牌名 | 匹配通用名或药品标准名，品牌进别名 | 拜阿司匹林 → 阿司匹林肠溶片 |
| 类别词 | 建为类别知识，并连接具体成员 | P2Y12受体抑制剂 → 氯吡格雷 |
| 笼统检查 | 必须结合原文场景匹配具体检查项目 | X线 → 胸部X线检查 |
| 多症状合并短语 | 拆成多个症状实体并保留原句证据 | 咳嗽、咯血或胸痛 → 咳嗽、咯血、胸痛 |

#### 7.3.2 肿瘤特有补充 【新增肿瘤特色】

| 情况 | 处理方式 | 示例 |
|---|---|---|
| 商品名靶向药 | 通用名为主名，商品名进别名 | 爱必妥 → 西妥昔单抗 |
| 免疫药缩写 | 标准中文全称为主名，缩写进别名 | PD-1 抑制剂 → 程序性死亡受体 1 抑制剂（帕博利珠单抗进别名） |
| 化疗方案缩写 | 方案名为主名，缩写进别名，并下钻到具体药品 | FOLFOX → 奥沙利铂+亚叶酸钙+氟尿嘧啶方案 |
| 分子检测口语 | 匹配规范检测项目名 | RAS 基因检测 → RAS 突变检测 |
| 基因变异写法 | 保留标准命名，如 KRAS G12D、BRAF V600E | 不得改写为模型结论 |

---

## 8. 正式推荐链

标准链路： 【复用通用结构】

```text
患者数据
→ ClinicalRule 临床规则
→ RecommendationStatement 推荐陈述
→ Medication / Procedure / TreatmentItem / ExamItem / LabItem
→ Evidence 主证据和支持证据
→ Guideline 来源文献
```

推荐陈述必填字段： 【复用通用结构】

| 字段 | 中文名 | 格式要求 | 来源 |
|---|---|---|---|
| `clinical_scene` | 临床场景 | 急诊、门诊、住院、围手术期、随访 | 复用通用 |
| `applicable_population` | 适用人群 | 明确人群描述 | 复用通用 |
| `trigger_condition` | 触发条件 | 结构化条件或原文摘要 | 复用通用 |
| `exclusion_condition` | 排除条件 | 禁忌或不适用条件 | 复用通用 |
| `recommendation_text` | 推荐文字 | 面向医生的中文推荐 | 复用通用 |
| `recommendation_class` | 推荐等级 | 原文等级，教材无等级写 N/A | 复用通用 |
| `evidence_level` | 证据等级 | 原文等级，教材无等级写 N/A | 复用通用 |
| `primary_source_name` | 主依据来源 | 指南或教材名称 | 复用通用 |
| `primary_evidence_id` | 主证据ID | Evidence 节点 ID | 复用通用 |
| `clinical_review_status` | 临床使用状态 | `formal_cdss_ready`、`review_required`、`blocked` | 复用通用 |

### 8.1 肿瘤推荐链特征补充 【新增肿瘤特色】

- **指南体系**：肿瘤正式推荐优先依据 NCCN、CSCO、ESMO、国家卫健委诊疗规范、《肿瘤学》教材。推荐陈述补 `guideline_edition`（版次）、`guideline_org`（发布机构）。
- **分子检测驱动靶向（强制前置）**：靶向/免疫推荐必须显式关联 Biomarker，且 `trigger_condition` 写明「需 XXX 检测结果阳性/表达阳性支持」。链路：`Disease→Biomarker→ClinicalRule→RecommendationStatement→Medication→Evidence`。
- **TNM 分期路由**：`Disease→TNMTStage→ClinicalRule→RecommendationStatement→Procedure/ChemoRegimen→Evidence`。
- **RAS 野生型晚期结直肠癌一线样例**：`Disease: 结直肠腺癌 → MolecularSubtype: RAS 野生型 → Biomarker: RAS 野生型 → ClinicalRule: RAS 野生型、晚期、无禁忌 → RecommendationStatement: 一线推荐西妥昔单抗 → Medication: 西妥昔单抗（标准药品字典表 绑定）→ Evidence: NCCN 原文 + I/A`。

---

## 9. 证据模型

### 9.1 Guideline 与 Evidence 区别 【复用通用结构】

| 对象 | 中文解释 | 粒度 | 来源 |
|---|---|---|---|
| Guideline | 整份教材、指南、共识、说明书 | 文件级 | 复用通用 |
| SourceSection | 文献中的章节或页码范围 | 章节级 | 复用通用 |
| Evidence | 可支撑一个知识点或推荐的一段原文摘要 | 片段级 | 复用通用 |

医生端不展示一大堆 Evidence 节点，只在具体推荐或知识卡片中展示"主依据、页码、推荐等级、证据等级、原文摘要"。证据池用于追溯和审核。

### 9.2 证据必填字段 【复用通用结构】

| 字段 | 中文名 | 格式要求 | 来源 |
|---|---|---|---|
| `source_name` | 来源名称 | 具体文献名称 | 复用通用 |
| `source_type` | 来源类型 | textbook、guideline、consensus、drug_label、authority_web | 复用通用 |
| `source_year` | 来源年份 | 四位年份或空 | 复用通用 |
| `page_start` | 起始页 | 数字或空 | 复用通用 |
| `page_end` | 结束页 | 数字或空 | 复用通用 |
| `section_title` | 章节标题 | 原文章节名 | 复用通用 |
| `evidence_text` | 证据原文摘要 | 保留原文含义，不改写为模型结论 | 复用通用 |
| `recommendation_class` | 推荐等级 | 有则原样保存，无则 N/A | 复用通用 |
| `evidence_level` | 证据等级 | 有则原样保存，无则 N/A | 复用通用 |
| `language` | 语言 | zh、en | 复用通用 |

> 肿瘤多版冲突裁决：同一推荐存在 NCCN/CSCO/卫健委多版冲突时，按来源年份、版本、适用范围、发布机构权威度裁决，不覆盖旧证据（呼应原则 T-4）。【新增肿瘤特色】

---

## 10. 覆盖率与验收口径

按诊断角色分别验收：【复用通用结构】

| 诊断角色 | 必须覆盖 | 可以继承或汇总 | 不作为必填 |
|---|---|---|---|
| 疑似或待分型诊断 | 标准诊断、定义、症状、体征、初筛检查、初筛检验、分型入口、危险信号 | 共性病因、共性危险因素 | 具体分型专属治疗推荐 |
| 具体分型诊断 | 标准诊断、定义、诊断标准、鉴别诊断、检查项目、检查发现、检验项目、检验细项、治疗方案、正式推荐链、禁忌、证据 | 上级共性知识 | 无证据的正式推荐 |
| 独立诊断 | 标准诊断、定义、临床表现、诊断、检查、检验、治疗、随访、证据 | 所属大类知识 | 上级分型入口 |

### 10.1 肿瘤诊断角色补充必填项 【新增肿瘤特色】

| 诊断角色 | 肿瘤必须补充覆盖 |
|---|---|
| 疑似或待分型诊断（如 结直肠癌 / 子宫颈癌 / 卵巢癌） | 标准诊断、定义、症状、体征、初筛影像、初筛标志物、病理/分子分型入口、TNM 分期入口、危险信号 |
| 具体亚型（如 结直肠腺癌、RAS 野生型；子宫颈鳞癌） | 标准诊断、组织学类型、诊断标准、鉴别诊断、影像、病理/分子检测、TNM 分期、化疗/靶向/放疗方案、正式推荐链、禁忌、证据 |
| 独立诊断（如 卵巢上皮癌） | 标准诊断、定义、临床表现、检查、检验、TNM 分期、治疗（化疗±放疗）、随访、证据 |

肿瘤样板（首模板建议：结直肠癌 / 子宫颈癌 / 卵巢癌，以结直肠癌为先行样板）验收必须同时检查：知识内容完整性、正式推荐链完整性、分子检测→靶向触发闭环、TNM 分期→治疗策略路由闭环。

---

## 11. 专病扩展模块机制与配置规格

核心 Schema 不随病种膨胀，差异通过扩展模块启用。执行配置文件沿用 V3.0 命名：`公共执行层_kg_pipeline/专病扩展槽位配置.yaml`。

扩展实体定义见第 4.5 章，扩展关系定义见第 5.6 章；本章只写 YAML 配置规格与审计边界。

### 11.1 启用原则 【复用通用结构】

| 规则 | 说明 | 来源 |
|---|---|---|
| 主结构不膨胀 | 疾病、症状、体征、检查、检验、药品、手术、治疗、诊断、证据仍是主干 | 复用通用 |
| 差异走扩展模块 | 病理、分子、分期、放化疗、转移、体能状态、不良反应走扩展模块 | 复用通用 |
| 必须有来源 | 教材、指南、共识或权威来源明确写到，才允许生成扩展实体 | 复用通用 |
| 不建空壳 | 没有原文依据、没有疾病引用、没有临床用途，不生成节点 | 复用通用 |
| 不替代字典 | 检查、检验、药品、手术、治疗项目仍优先绑定标准字典 | 复用通用 |

### 11.2 肿瘤专病扩展模块配置规格 【新增肿瘤特色】

落地时按相同结构追加进 YAML。

#### 11.2.1 oncology_tnm_staging（TNM 分期）

| 项目 | 内容 |
|---|---|
| 适用大类 | 全部实体瘤（按部位亚类） |
| 适用示例 | 结直肠癌、子宫颈癌、卵巢癌、胃癌、乳腺癌 |
| 扩展实体 | TCategory、NCategory、MCategory、TNMTStage、StageGrouping、TumorTopographyCode、TumorMorphologyCode（详见 4.5） |
| 扩展关系 | `disease_has_tnm_stage`、`diagnosis_criteria_uses_tnm`、`recommendation_requires_tnm_stage`、`has_topography_code`、`has_morphology_code`（详见 5.6） |
| 字典策略 | 分期与部位/形态学码建议走 AJCC/UICC 标准字典或映射标准诊断候选；部位码、形态学码、分期本身不走医嘱字典 |
| 审计闸门 | T/N/M 必须保留原文阈值与分期标准版本；分期不得误抽为检查项目；组合分期必须可回溯到 T/N/M 三个分量 |

> 本模块只定义 TNM 取值与关联，不定义分期计算逻辑。

#### 11.2.2 oncology_histopathology（组织病理与分化）

| 项目 | 内容 |
|---|---|
| 扩展实体 | HistologyType、DifferentiationGrade、PrimarySite（详见 4.5） |
| 扩展关系 | `disease_has_histology_type`、`disease_has_differentiation`、`disease_has_primary_site`（详见 5.6） |
| 字典策略 | 优先映射病理分型字典 / 标准诊断候选；不走医嘱字典 |
| 审计闸门 | 组织学类型不得误抽为症状或体征；分化程度必须绑定原文分级依据 |

#### 11.2.3 oncology_molecular（分子分型、驱动基因、生物标志物）

| 项目 | 内容 |
|---|---|
| 扩展实体 | Biomarker、Gene、GeneticVariant、FusionGene、ProteinExpression、MolecularSubtype（详见 4.5） |
| 扩展关系 | `disease_has_molecular_subtype`、`disease_has_biomarker`、`gene_has_variant`、`gene_has_fusion`、`biomarker_has_protein_expression`、`biomarker_guides_targeted_therapy`、`recommendation_requires_biomarker`（详见 5.6） |
| 字典策略 | 分子检测项目映射检验字典（LabItem/LabSubitem）；基因/变异/蛋白表达不走医嘱字典；靶向药、免疫药映射药品字典 |
| 审计闸门 | 基因名不得误抽为药品或检查；无原文依据不得生成变异节点；靶向推荐关联 Biomarker 时必须同时具备检测结果触发条件与主证据 |

#### 11.2.4 oncology_tumor_markers（肿瘤标志物）

| 项目 | 内容 |
|---|---|
| 扩展实体 | TumorMarker（详见 4.5） |
| 扩展关系 | `disease_has_tumor_marker`、`tumor_marker_uses_lab_subitem`、`recommendation_uses_tumor_marker`（详见 5.6） |
| 字典策略 | 标志物检测结果映射检验细项字典（LabSubitem）；标志物实体本身不走医嘱字典 |
| 审计闸门 | 标志物不得误抽为检验项目本身；必须能下钻到具体检验细项与标本 |

#### 11.2.5 oncology_chemotherapy（化疗方案）

| 项目 | 内容 |
|---|---|
| 扩展实体 | ChemoRegimen、ChemoCycle（详见 4.5） |
| 扩展关系 | `treatment_plan_includes_chemo_regimen`、`chemo_regimen_includes_medication`、`chemo_regimen_has_cycle`、`recommendation_statement_recommends_chemo_regimen`（详见 5.6） |
| 字典策略 | 方案优先映射治疗项目字典或标准治疗方案字典；方案下具体药品必须映射药品字典（标准药品字典表） |
| 审计闸门 | 化疗方案不得只保留标题；必须下钻到具体药品；药品必须绑定标准字典 |

#### 11.2.6 oncology_targeted_immuno（靶向与免疫治疗）

| 项目 | 内容 |
|---|---|
| 扩展实体 | TargetedDrug、ImmuneCheckpointInhibitor、AntiAngiogenicDrug（详见 4.5） |
| 扩展关系 | `recommends_action`（用于靶向/免疫药）；`recommendation_requires_biomarker`（前置触发）（详见 5.6） |
| 字典策略 | 全部映射药品字典（标准药品字典表），通用名为主名，商品名进别名 |
| 审计闸门 | 靶向/免疫药不得用商品名或缩写作主名；靶向推荐必须关联 Biomarker 与主证据 |

#### 11.2.7 oncology_radiotherapy（放疗）

| 项目 | 内容 |
|---|---|
| 扩展实体 | RadiotherapyPlan、TargetVolume、RadiationDose（详见 4.5） |
| 扩展关系 | `treatment_plan_includes_radiotherapy`、`radiotherapy_has_target_volume`、`radiotherapy_has_dose`、`recommendation_statement_recommends_radiotherapy`（详见 5.6） |
| 字典策略 | 放疗映射治疗项目字典 / 手术操作字典；靶区、剂量分割不走医嘱字典，作为方案说明 |
| 审计闸门 | 靶区不得误抽为手术；剂量必须保留数值、单位与分割方式；放疗方案必须能下钻到可执行项目 |

#### 11.2.8 oncology_metastasis_recurrence（转移、复发、寡转移）

| 项目 | 内容 |
|---|---|
| 扩展实体 | MetastaticSite、Oligometastasis、Recurrence（详见 4.5） |
| 扩展关系 | `disease_has_metastatic_site`、`disease_has_oligometastasis`、`disease_has_recurrence`、`recommendation_uses_recurrence_status`（详见 5.6） |
| 字典策略 | 转移部位优先映射标准诊断 / 部位字典；复发状态可映射并发症或独立状态实体，不走医嘱字典 |
| 审计闸门 | 转移部位不得误抽为并发症，除非原文明确为并发症；寡转移必须绑定原文判定标准 |

#### 11.2.9 oncology_performance_status（体能状态评分）

| 项目 | 内容 |
|---|---|
| 扩展实体 | PerformanceStatus（详见 4.5） |
| 扩展关系 | `recommendation_requires_performance_status`（详见 5.6） |
| 字典策略 | 不走医嘱字典；作为推荐触发/排除条件 |
| 审计闸门 | 评分必须保留体系（ECOG/KPS）与阈值；不得误抽为生命体征 |

#### 11.2.10 oncology_adverse_event（不良反应与 irAE）

| 项目 | 内容 |
|---|---|
| 扩展实体 | AdverseEvent、AEGrade（详见 4.5） |
| 扩展关系 | `medication_has_adverse_event`、`adverse_event_has_grade`、`recommendation_has_ae_warning`、`blocks_action`（详见 5.6） |
| 字典策略 | 不良反应优先映射不良反应字典（如有）或并发症；irAE 可映射并发症实体，不走医嘱字典 |
| 审计闸门 | 不良反应不得误抽为症状，除非原文明确为症状；分级必须绑定 CTCAE 版本与阈值 |

### 11.3 扩展实体进入展示与推荐的边界（肿瘤版） 【新增肿瘤特色】

| 类型 | 普通知识展示 | 正式推荐 | 标准字典 |
|---|---|---|---|
| 基因、变异、分子分型、蛋白表达 | 可以 | 只能作为靶向/免疫推荐的触发条件或解释 | 通常不需要 |
| TNM 分期、分化程度、体能状态、转移/复发状态 | 可以 | 可以作为治疗路由条件或排除条件 | 通常不需要 |
| 肿瘤标志物 | 可以 | 可以作为随访/监测推荐条件 | 检测结果需绑定检验细项字典 |
| 化疗/放疗/靶向/免疫方案 | 可以 | 可以作为正式动作 | 方案下具体药品/操作必须绑定标准字典 |
| 靶向药、免疫药 | 可以 | 可以作为正式动作 | 必须优先绑定药品字典 |
| 靶区、剂量、设备参数 | 可以 | 通常只做方案说明 | 视医院字典能力 |

### 11.4 审计要求 【复用通用结构 + 新增肿瘤特色】

每个扩展模块必须通过以下检查：

1. 扩展实体有来源证据。【复用通用】
2. 扩展实体被疾病、诊断标准、风险分层、治疗方案或推荐陈述引用。【复用通用】
3. 扩展实体没有被误抽成普通症状、检查、药品或手术。【复用通用】
4. 扩展实体进入正式推荐时，必须同时具备适用场景、触发条件、禁忌/排除条件和主证据。【复用通用 + 肿瘤】
5. 需要医嘱回填的实体必须绑定标准字典；不能绑定时只能做知识展示。【复用通用】

---

## 12. 导入和展示边界 【复用通用结构】

### 12.1 必须导入的业务实体

Specialty、DiseaseCategory、DiseaseSubcategory、Disease、StandardDiagnosis、Definition、DefinitionComponent、Etiology、Pathophysiology、Epidemiology、Symptom、Sign、VitalSignItem、RiskFactor、Complication、DifferentialDiagnosis、RiskStratification、ExamPlan、ExamItem、ExamObservation、LabItem、LabSubitem、LabSample、TreatmentPlan、Medication、Procedure、TreatmentItem、Contraindication、ClinicalRule、RecommendationStatement、FollowUp、Prognosis、Prevention、Guideline、SourceSection、Evidence、MedicalTermAlias。

> 肿瘤扩展模块实体（HistologyType、Biomarker、TCategory 等，见第 4.5 章）随对应 Disease 的模块启用一并导入，受第 11 章边界约束。

### 12.2 普通知识元模型配置默认不展示的字段

batch_id、scope_type、scope_target、source_roots、parser_version、extraction_version、import_batch、migration_status、repair_status、merge_status、source_hash、document_hash、evidence_hash、raw_text_anchor、provenance、extraction_log、audit_result、review_notes、created_by、created_at、updated_at。

这些是属性，不是实体节点。导入程序不得用 `keys(n)` 把属性名渲染成图谱节点。

### 12.3 需要过滤的历史对象

| 对象 | 处理 |
|---|---|
| `DiseaseClassification` | 停用，不再新增；已迁移后清理 |
| `Exam` | 停用，改用 ExamItem |
| `LabTest` | 停用，改用 LabItem |
| `ExamIndicator` | 停用，改用 ExamObservation |
| 纯过程节点 | 不进入维护页 |
| 审核过程节点 | 不进入维护页 |
| 历史兼容节点 | 本月清理范围内处理 |

---

## 13. 数据质量硬闸门

入库前和入库后都必须检查（内联 V3.0 18 条 + 肿瘤补充 10 条）。

### 13.1 通用闸门 【复用通用结构】

1. 所有临床业务节点必须有 `entityType`、`code`、`name`。
2. 需要回填医嘱的实体必须绑定有效标准字典。
3. 疾病三层关系不得断链。
4. 疑似诊断必须有具体分型入口或明确独立诊断身份。
5. 具体分型诊断必须有标准诊断。
6. 诊断标准必须有下钻明细。
7. 鉴别诊断必须有对象和鉴别规则。
8. 检查项目必须能下钻到检查发现，若来源不覆盖则记录缺口。
9. 检验项目必须能下钻到检验细项，若来源不覆盖则记录缺口。
10. 治疗方案必须下钻到药品、手术或治疗项目。
11. 正式推荐必须有推荐陈述、动作、禁忌或排除条件、主证据。
12. 证据必须能追溯到具体来源名称、章节或页码。
13. 药品、手术、检查、检验、症状、体征不得使用口语名或缩写作主名称。
14. 多症状、多药品、多检查合并短语必须拆分。
15. `source` 字段不得写项目版本或校验过程，必须写具体来源名称。
16. 检查、检验、药品、手术、治疗项目进入正式推荐时，关系必须有诊疗阶段、推荐目的、服务对象和优先级。
17. 鉴别诊断必须能说明"鉴别谁、为什么鉴别、用什么检查检验鉴别、结果如何解释、依据来自哪里"。
18. 治疗方案必须区分"方案标题"和"可执行动作"；方案标题不能直接替代医嘱动作。

### 13.2 肿瘤补充闸门 【新增肿瘤特色】

1. TNM 分期必须可回溯到 T/N/M 三个分量，且保留分期标准版本（AJCC/UICC）。
2. 组织学类型、分化程度不得误抽为症状、体征或检查项目。
3. 基因、变异、分子分型不得被误抽为药品、检查或普通术语。
4. 靶向/免疫推荐必须关联 Biomarker，并具备检测结果触发条件与主证据。
5. 化疗方案、放疗方案必须下钻到具体药品或可执行操作，不得只保留标题。
6. 靶向药、免疫药、化疗药主名称必须为标准通用名，商品名/缩写进别名。
7. 肿瘤标志物必须能下钻到检验细项与标本。
8. 不良反应分级必须绑定 CTCAE 版本与阈值；irAE 不得误抽为普通症状。
9. 体能状态评分必须保留评分体系（ECOG/KPS）与阈值，不得误抽为生命体征。
10. 转移/复发状态不得误抽为并发症，除非原文明确。

---

## 14. 当前禁止新增项

（内联 V3.0 9 条 + 肿瘤补充 7 条）

### 14.1 通用禁止项 【复用通用结构】

1. 禁止新增 `DiseaseClassification`。
2. 禁止新增 `Exam`、`LabTest`、`ExamIndicator`。
3. 禁止新增只有标题、没有下钻明细的诊断标准。
4. 禁止新增只有标题、没有具体动作的治疗方案。
5. 禁止新增只有缩写的药品、手术、检查、检验实体。
6. 禁止把批次、哈希、路径、脚本版本、审核状态渲染为业务节点。
7. 禁止直接改写既有标准字典修名、合并、删除。
8. 禁止用大模型常识替代来源证据。
9. 禁止新增通用泛化关系：`RECOMMEND_CHECK`、`RECOMMEND_LAB_CHECK`、`HAS_DRUG`、`RECOMMEND_OPERATION`、`RECOMMEND_TREATMENT`。

### 14.2 肿瘤补充禁止项 【新增肿瘤特色】

1. 禁止为「RAS 野生型结直肠腺癌」这类分子状态单独新建 Disease 节点（走分子分型扩展模块）。
2. 禁止把 T/N/M 分期、分化程度、体能状态误建为 Symptom / Sign / VitalSignItem。
3. 禁止把基因名、蛋白表达误建为 Medication / ExamItem。
4. 禁止靶向/免疫推荐缺少 Biomarker 关联与主证据。
5. 禁止化疗/放疗方案只建标题、不下钻到具体药品或操作。
6. 禁止用商品名或缩写作为靶向药、免疫药主名称。
7. 禁止编造 ICD-O-3 形态学码、基因变异命名或 TNM 分期。

---

## 15. 与解析 SKILL 的关系 【复用通用结构】

本 Schema 是验收标准，《AI自动化工具-文献指南解析.md》是生成流程标准，两者版本同步记录在大版本变更记录中。

---

## 附录：与 V3.0 的关系

通用主干已内联复制（标记【复用通用结构】），肿瘤叠加内容（标记【新增肿瘤特色】）正序融入；肿瘤通过第 11 章 10 个扩展模块补充分期、病理、分子、标志物、放化疗、转移、体能状态、不良反应，不新建平行主结构。
