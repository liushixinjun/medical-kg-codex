# 专科知识图谱最终 Schema V1.0

**版本号**：V1.0  
**定位**：专科知识图谱通用 Schema，心血管内科优先落地，后续扩展神经内科、儿科、骨科、呼吸、消化、肿瘤等专科。  
**适用场景**：专科辅助诊疗、专病管理、专科病历治理、指南证据沉淀、医生审核、知识图谱建模导入、AI 推理规则构建。  
**核心原则**：可审核、可追溯、可扩展、可导入、可推理、可版本化。

---

## 0. 总体设计原则

### 0.1 总体分层

```text
学科 / 专科 Specialty
  └── 疾病大类 DiseaseCategory
        └── 疾病亚类 DiseaseSubcategory
              └── 疾病 Disease
                    ├── 疾病分型 DiseaseType
                    ├── 疾病分期 / 分层 DiseaseStage
                    ├── 诊断标准 DiagnosisCriteria
                    ├── 症状 Symptom
                    ├── 体征 Sign
                    ├── 检查项目 Exam
                    ├── 检查指标 ExamIndicator
                    ├── 危险因素 RiskFactor
                    ├── 并发症 Complication
                    ├── 鉴别诊断 DifferentialDiagnosis
                    ├── 治疗方案 TreatmentPlan
                    ├── 药物 Medication
                    ├── 手术 / 介入 Procedure
                    ├── 临床路径 ClinicalPathway
                    ├── 患者状态 PatientState
                    ├── 病程事件 ClinicalEvent
                    ├── 推理规则 ReasoningRule
                    ├── 医生角色 DoctorRole
                    ├── 科室 Department
                    ├── 指南 Guideline
                    ├── 证据条目 Evidence
                    ├── 数据来源 DataSource
                    └── 审核状态 ReviewStatus
```

### 0.2 通用节点字段

所有实体建议保留以下通用字段，便于图数据库导入、版本管理和医生审核。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| id | String | 是 | 全局唯一 ID | CARD-CAD-ACS-STEMI |
| name_cn | String | 是 | 中文名称 | ST 段抬高型心肌梗死 |
| name_en | String | 否 | 英文名称 | ST-elevation myocardial infarction |
| entity_type | String | 是 | 实体类型 | Disease |
| code | String | 否 | 业务编码 | STEMI |
| standard_code | String | 否 | 标准编码 | ICD-10: I21.0 |
| description | Text | 否 | 说明 | 疾病定义或实体说明 |
| source_id | String | 否 | 数据来源 ID | SOURCE-ESC-ACS-2023 |
| guideline_id | String | 否 | 指南 ID | GUIDELINE-ESC-ACS-2023 |
| evidence_id | String | 否 | 证据 ID | EVIDENCE-ACS-001 |
| review_status | Enum | 是 | 审核状态 | draft / pending_review / approved / rejected / deprecated |
| confidence | Float | 否 | 置信度 | 0.92 |
| version | String | 是 | 版本号 | V1.0 |
| created_by | String | 否 | 创建人或来源 | AI / 人工 / 医生 |
| created_time | DateTime | 否 | 创建时间 | 2026-06-13 10:00:00 |
| updated_time | DateTime | 否 | 更新时间 | 2026-06-13 10:00:00 |

### 0.3 通用关系字段

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| relation_id | String | 是 | 关系唯一 ID | REL-000001 |
| relation_type | String | 是 | 关系类型 | has_symptom |
| source_node_id | String | 是 | 起点节点 ID | CARD-CAD-ACS-STEMI |
| target_node_id | String | 是 | 终点节点 ID | SYM-CHEST-PAIN |
| source_entity_type | String | 否 | 起点实体类型 | Disease |
| target_entity_type | String | 否 | 终点实体类型 | Symptom |
| relation_name_cn | String | 否 | 中文关系名 | 具有症状 |
| description | Text | 否 | 关系说明 | STEMI 常表现为胸痛 |
| confidence | Float | 否 | 置信度 | 0.95 |
| evidence_id | String | 否 | 证据 ID | EVIDENCE-STEMI-001 |
| source_id | String | 否 | 数据来源 ID | SOURCE-GUIDELINE-001 |
| review_status | Enum | 是 | 审核状态 | draft / pending_review / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1. 核心实体 Schema

## 1.1 学科 / 专科 Specialty

**作用**：承载知识图谱顶层目录，支持跨专科扩展。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| specialty_id | String | 是 | 专科唯一 ID | CARDIOLOGY |
| specialty_name_cn | String | 是 | 中文名称 | 心血管内科 |
| specialty_name_en | String | 否 | 英文名称 | Cardiology |
| parent_specialty_id | String | 否 | 上级学科 ID | INTERNAL_MEDICINE |
| hospital_dept_mapping | Array | 否 | 院内科室映射 | 心内科、CCU、胸痛中心 |
| description | Text | 否 | 专科说明 | 心血管疾病诊疗相关专科 |
| applicable_scope | Text | 否 | 适用范围 | 门诊、急诊、住院、随访 |
| enabled_status | Enum | 是 | 启用状态 | enabled / disabled |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.2 疾病大类 DiseaseCategory

**作用**：专科下的疾病一级分类，解决疾病目录管理和扩展问题。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| category_id | String | 是 | 疾病大类 ID | CARD-CAD |
| specialty_id | String | 是 | 所属专科 ID | CARDIOLOGY |
| category_name_cn | String | 是 | 中文名称 | 冠状动脉疾病 |
| category_name_en | String | 否 | 英文名称 | Coronary Artery Disease |
| category_code | String | 否 | 分类编码 | CAD |
| classification_basis | String | 是 | 分类依据 | ICD-10 / 临床专科分类 / 指南分类 |
| included_scope | Text | 否 | 包含范围 | 冠心病、ACS、心绞痛、心肌梗死 |
| excluded_scope | Text | 否 | 排除范围 | 非冠脉缺血性心肌损伤 |
| description | Text | 否 | 大类说明 | 冠脉粥样硬化及其相关疾病 |
| sort_order | Integer | 否 | 排序 | 1 |
| review_status | Enum | 是 | 审核状态 | draft / pending_review / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.3 疾病亚类 DiseaseSubcategory

**作用**：疾病大类下的二级细分，支撑专病管理与医生审核。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| subcategory_id | String | 是 | 疾病亚类 ID | CARD-CAD-ACS |
| category_id | String | 是 | 所属疾病大类 ID | CARD-CAD |
| specialty_id | String | 是 | 所属专科 ID | CARDIOLOGY |
| subcategory_name_cn | String | 是 | 中文名称 | 急性冠脉综合征 |
| subcategory_name_en | String | 否 | 英文名称 | Acute Coronary Syndrome |
| subcategory_code | String | 否 | 亚类编码 | ACS |
| classification_basis | String | 是 | 分类依据 | 指南分类 / 临床路径 / ICD-10 |
| included_disease_scope | Text | 否 | 包含疾病 | STEMI、NSTEMI、不稳定型心绞痛 |
| description | Text | 否 | 亚类说明 | ACS 相关疾病集合 |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.4 疾病 Disease

**作用**：具体疾病诊断实体，是知识组织的核心锚点。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| disease_id | String | 是 | 疾病唯一 ID | CARD-CAD-ACS-STEMI |
| disease_name_cn | String | 是 | 中文名称 | ST 段抬高型心肌梗死 |
| disease_name_en | String | 否 | 英文名称 | ST-elevation myocardial infarction |
| alias | Array | 否 | 别名 | STEMI、急性 ST 段抬高型心梗 |
| specialty_id | String | 是 | 所属专科 | CARDIOLOGY |
| category_id | String | 是 | 所属疾病大类 | CARD-CAD |
| subcategory_id | String | 是 | 所属疾病亚类 | CARD-CAD-ACS |
| icd10_code | String | 否 | ICD-10 编码 | I21.0 / I21.1 |
| icd11_code | String | 否 | ICD-11 编码 | BA41 |
| snomed_ct_code | String | 否 | SNOMED CT 编码 | 待补充 |
| disease_definition | Text | 是 | 疾病定义 | 冠状动脉急性闭塞导致心肌坏死 |
| pathogenesis | Text | 否 | 发病机制 | 斑块破裂、血栓形成、冠脉闭塞 |
| epidemiology | Text | 否 | 流行病学 | 发病率、危险人群 |
| severity_level | Enum | 否 | 严重程度 | mild / moderate / severe / critical |
| emergency_level | Enum | 否 | 急诊等级 | routine / urgent / emergency |
| chronicity | Enum | 否 | 急慢性 | acute / chronic / recurrent |
| contagious | Boolean | 否 | 是否传染 | false |
| genetic_related | Boolean | 否 | 是否遗传相关 | false |
| rare_disease | Boolean | 否 | 是否罕见病 | false |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-ESC-ACS-2023 |
| review_status | Enum | 是 | 审核状态 | draft / pending_review / approved / rejected |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.5 疾病分型 DiseaseType

**作用**：描述疾病内部分类，如 1 型心肌梗死、2 型心肌梗死等。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| type_id | String | 是 | 分型 ID | AMI-TYPE-1 |
| disease_id | String | 是 | 所属疾病 | AMI |
| type_name_cn | String | 是 | 分型名称 | 1 型心肌梗死 |
| type_name_en | String | 否 | 英文名称 | Type 1 myocardial infarction |
| type_basis | String | 是 | 分型依据 | Universal Definition of MI |
| diagnostic_feature | Text | 否 | 分型诊断特征 | 冠脉斑块破裂及血栓形成 |
| clinical_meaning | Text | 否 | 临床意义 | 指导再灌注和抗栓治疗 |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-UDMI |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.6 疾病分期 / 分层 DiseaseStage

**作用**：描述疾病阶段、严重程度、风险分层或功能分级。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| stage_id | String | 是 | 分期 ID | HF-STAGE-C |
| disease_id | String | 是 | 所属疾病 | HeartFailure |
| stage_name_cn | String | 是 | 分期名称 | C 期心衰 |
| stage_name_en | String | 否 | 英文名称 | Stage C Heart Failure |
| stage_type | Enum | 是 | 类型 | stage / grade / risk_level / functional_class |
| stage_basis | String | 是 | 分期依据 | ACC/AHA 分期 |
| clinical_feature | Text | 否 | 临床特征 | 有结构性心脏病并出现心衰症状 |
| severity | Enum | 否 | 严重程度 | low / medium / high / critical |
| recommended_action | Text | 否 | 推荐处理 | 规范药物治疗、随访评估 |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-HF |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.7 症状 Symptom

**作用**：患者主观感受，用于预问诊、病历结构化和推理输入。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| symptom_id | String | 是 | 症状 ID | SYM-CHEST-PAIN |
| symptom_name_cn | String | 是 | 中文名称 | 胸痛 |
| symptom_name_en | String | 否 | 英文名称 | Chest pain |
| alias | Array | 否 | 别名 | 胸闷痛、胸部压榨感 |
| description | Text | 否 | 症状说明 | 胸骨后压榨样疼痛 |
| body_location | String | 否 | 部位 | 胸骨后、心前区 |
| onset_pattern | Enum | 否 | 起病方式 | sudden / gradual |
| duration | String | 否 | 持续时间 | 大于 20 分钟 |
| frequency | String | 否 | 发作频率 | 持续 / 间断 |
| severity_scale | String | 否 | 严重程度量表 | NRS 0-10 |
| aggravating_factor | Array | 否 | 加重因素 | 活动、情绪激动 |
| relieving_factor | Array | 否 | 缓解因素 | 休息、硝酸甘油 |
| accompanying_symptoms | Array | 否 | 伴随症状 | 大汗、恶心、呼吸困难 |
| typicality | Enum | 否 | 典型程度 | typical / atypical |
| red_flag | Boolean | 否 | 是否危险信号 | true |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.8 体征 Sign

**作用**：医生查体或客观发现，用于诊疗判断和风险识别。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| sign_id | String | 是 | 体征 ID | SIGN-HYPOTENSION |
| sign_name_cn | String | 是 | 中文名称 | 低血压 |
| sign_name_en | String | 否 | 英文名称 | Hypotension |
| examination_method | String | 否 | 检查方式 | 血压测量 |
| normal_range | String | 否 | 正常范围 | SBP ≥ 90mmHg |
| abnormal_threshold | String | 否 | 异常阈值 | SBP < 90mmHg |
| clinical_meaning | Text | 否 | 临床意义 | 提示休克、心衰或严重缺血 |
| associated_disease_scope | Array | 否 | 关联疾病范围 | AMI、心衰、心源性休克 |
| severity_level | Enum | 否 | 严重程度 | mild / moderate / severe / critical |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.9 检查项目 Exam

**作用**：辅助诊断检查，包括检验、影像、功能、床旁检查等。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| exam_id | String | 是 | 检查 ID | EXAM-ECG |
| exam_name_cn | String | 是 | 中文名称 | 心电图 |
| exam_name_en | String | 否 | 英文名称 | Electrocardiogram |
| alias | Array | 否 | 别名 | ECG、十二导联心电图 |
| exam_type | Enum | 是 | 检查类型 | lab / imaging / function / pathology / bedside |
| indication | Text | 否 | 适应场景 | 胸痛、心悸、晕厥 |
| contraindication | Text | 否 | 禁忌或限制 | 无绝对禁忌 |
| timing_requirement | String | 否 | 时间要求 | 首次医疗接触后 10 分钟内 |
| interpretation_rule | Text | 否 | 判读规则 | ST 段抬高、新发左束支传导阻滞等 |
| execution_department | String | 否 | 执行科室 | 心电图室 / 急诊 / 心内科 |
| urgency_level | Enum | 否 | 紧急程度 | routine / urgent / emergency |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-ACS |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.10 检查指标 ExamIndicator

**作用**：检查项目中的具体指标、阈值、动态变化和临床意义。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| indicator_id | String | 是 | 指标 ID | IND-TROPONIN |
| exam_id | String | 是 | 所属检查 | EXAM-TROPONIN |
| indicator_name_cn | String | 是 | 中文名称 | 肌钙蛋白 |
| indicator_name_en | String | 否 | 英文名称 | Troponin |
| abbreviation | String | 否 | 缩写 | cTn / hs-cTn |
| unit | String | 否 | 单位 | ng/L |
| normal_range | String | 否 | 正常范围 | 参考实验室标准 |
| abnormal_threshold | String | 否 | 异常阈值 | 超过第 99 百分位值 |
| critical_value | String | 否 | 危急值 | 院内定义 |
| clinical_meaning | Text | 否 | 临床意义 | 心肌损伤标志物 |
| trend_required | Boolean | 否 | 是否需要动态观察 | true |
| trend_rule | Text | 否 | 动态变化规则 | 升高 / 下降提示急性过程 |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-UDMI |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.11 诊断标准 DiagnosisCriteria

**作用**：结构化疾病诊断依据，支撑 AI 诊断推理和医生审核。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| criteria_id | String | 是 | 诊断标准 ID | DC-AMI-001 |
| disease_id | String | 是 | 所属疾病 | AMI |
| criteria_name | String | 是 | 标准名称 | 急性心肌梗死诊断标准 |
| criteria_type | Enum | 否 | 标准类型 | definitive / suspected / exclusion / classification |
| required_conditions | Array | 是 | 必要条件 | 肌钙蛋白升高/下降 + 缺血证据 |
| optional_conditions | Array | 否 | 可选条件 | 缺血症状、ECG 改变、影像证据 |
| exclusion_conditions | Array | 否 | 排除条件 | 非缺血性心肌损伤 |
| diagnostic_logic | Text | 是 | 诊断逻辑 | 满足心肌损伤并存在急性缺血证据 |
| input_entities | Array | 否 | 输入实体 | Symptom、ExamIndicator、Sign |
| output_diagnosis | String | 否 | 输出诊断 | AMI |
| source_guideline_id | String | 是 | 来源指南 | GUIDELINE-ESC-ACS-2023 |
| evidence_level | String | 否 | 证据等级 | A / B / C |
| recommendation_class | String | 否 | 推荐等级 | I / IIa / IIb / III |
| review_status | Enum | 是 | 审核状态 | draft / pending_review / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.12 鉴别诊断 DifferentialDiagnosis

**作用**：描述疾病间的相似点、区分点和关键检查，减少误诊漏诊。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| diff_id | String | 是 | 鉴别诊断 ID | DIFF-AMI-AORTIC-DISSECTION |
| disease_id | String | 是 | 当前疾病 | AMI |
| differential_disease_id | String | 是 | 需鉴别疾病 | 主动脉夹层 |
| similar_features | Array | 否 | 相似表现 | 胸痛、休克 |
| distinguishing_features | Array | 是 | 区分要点 | 撕裂样疼痛、纵隔增宽、CTA 阳性 |
| key_exam | Array | 否 | 关键检查 | CTA、D-二聚体、超声 |
| risk_warning | Text | 否 | 风险提示 | 误用抗凝可能加重出血风险 |
| diagnostic_priority | Enum | 否 | 鉴别优先级 | high / medium / low |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-CHEST-PAIN |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.13 危险因素 RiskFactor

**作用**：管理疾病发生、进展、复发、并发症相关风险。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| risk_factor_id | String | 是 | 危险因素 ID | RF-SMOKING |
| risk_factor_name_cn | String | 是 | 中文名称 | 吸烟 |
| risk_factor_name_en | String | 否 | 英文名称 | Smoking |
| risk_type | Enum | 是 | 类型 | lifestyle / disease / genetic / lab / demographic / medication |
| modifiable | Boolean | 否 | 是否可干预 | true |
| risk_level | Enum | 否 | 风险等级 | low / medium / high |
| risk_direction | Enum | 否 | 风险方向 | increase / decrease / uncertain |
| measurement_method | String | 否 | 评估方式 | 问诊、检验、病史 |
| intervention_strategy | Text | 否 | 干预策略 | 戒烟、控压、降脂 |
| description | Text | 否 | 说明 | 增加冠心病及心梗风险 |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-PREVENTION |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.14 并发症 Complication

**作用**：描述疾病可能引发的后果及预警处理策略。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| complication_id | String | 是 | 并发症 ID | COMP-CARDIOGENIC-SHOCK |
| complication_name_cn | String | 是 | 中文名称 | 心源性休克 |
| complication_name_en | String | 否 | 英文名称 | Cardiogenic shock |
| complication_type | Enum | 否 | 类型 | acute / chronic / procedure_related / medication_related |
| severity | Enum | 是 | 严重程度 | mild / moderate / severe / critical |
| occurrence_stage | String | 否 | 发生阶段 | 急性期 |
| warning_signs | Array | 否 | 预警表现 | 低血压、少尿、意识改变 |
| related_indicators | Array | 否 | 相关指标 | 乳酸、血压、尿量 |
| management_strategy | Text | 否 | 处理策略 | 血流动力学支持、急诊再灌注 |
| emergency_level | Enum | 否 | 紧急程度 | urgent / emergency |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-SHOCK |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.15 药物 Medication

**作用**：沉淀药物知识，支撑治疗推荐、禁忌提醒和用药审核。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| medication_id | String | 是 | 药物 ID | MED-ASPIRIN |
| drug_name_cn | String | 是 | 中文名称 | 阿司匹林 |
| drug_name_en | String | 否 | 英文名称 | Aspirin |
| generic_name | String | 否 | 通用名 | 阿司匹林 |
| trade_name | Array | 否 | 商品名 | 拜阿司匹灵 |
| drug_class | String | 是 | 药物类别 | 抗血小板药 |
| mechanism | Text | 否 | 作用机制 | 抑制血小板聚集 |
| indication | Text | 是 | 适应症 | ACS、冠心病二级预防 |
| contraindication | Text | 是 | 禁忌症 | 活动性出血、严重过敏 |
| caution | Text | 否 | 注意事项 | 胃肠道出血风险 |
| dosage | String | 否 | 推荐剂量 | 负荷剂量 / 维持剂量 |
| administration_route | String | 否 | 给药途径 | 口服 |
| frequency | String | 否 | 给药频次 | 每日一次 |
| adverse_reaction | Array | 否 | 不良反应 | 出血、胃肠道反应 |
| interaction | Array | 否 | 药物相互作用 | 抗凝药增加出血风险 |
| renal_adjustment | Text | 否 | 肾功能调整 | 视药物而定 |
| hepatic_adjustment | Text | 否 | 肝功能调整 | 视药物而定 |
| pregnancy_lactation | Text | 否 | 妊娠哺乳说明 | 按说明书及指南 |
| monitoring_indicators | Array | 否 | 监测指标 | 出血、血红蛋白 |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-ACS |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.16 手术 / 介入 Procedure

**作用**：描述手术、介入、消融、器械治疗等操作知识。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| procedure_id | String | 是 | 操作 ID | PROC-PCI |
| procedure_name_cn | String | 是 | 中文名称 | 经皮冠状动脉介入治疗 |
| procedure_name_en | String | 否 | 英文名称 | Percutaneous coronary intervention |
| abbreviation | String | 否 | 缩写 | PCI |
| procedure_type | Enum | 是 | 类型 | intervention / surgery / ablation / device / examination |
| indication | Text | 是 | 适应症 | STEMI 急诊再灌注 |
| contraindication | Text | 否 | 禁忌症 | 严重出血风险等 |
| preoperative_evaluation | Text | 否 | 术前评估 | 冠脉造影、凝血、肾功能 |
| timing_requirement | String | 否 | 时间要求 | 首次医疗接触后尽快开通血管 |
| risk | Text | 否 | 风险 | 出血、血管并发症、再狭窄 |
| postoperative_management | Text | 否 | 术后管理 | DAPT、监测并发症、二级预防 |
| responsible_department | String | 否 | 责任科室 | 心内科 / 导管室 |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-ACS |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.17 治疗方案 TreatmentPlan

**作用**：按疾病、场景、状态组织治疗策略，是辅助诊疗输出核心。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| plan_id | String | 是 | 治疗方案 ID | TP-STEMI-ACUTE |
| disease_id | String | 是 | 所属疾病 | STEMI |
| plan_name | String | 是 | 方案名称 | STEMI 急性期治疗方案 |
| scenario | Enum | 是 | 场景 | emergency / outpatient / inpatient / followup |
| applicable_state_id | String | 否 | 适用患者状态 | STATE-STEMI-CONFIRMED |
| treatment_goal | Text | 是 | 治疗目标 | 尽快再灌注、降低死亡率 |
| first_line_strategy | Text | 是 | 一线策略 | 急诊 PCI 优先 |
| alternative_strategy | Text | 否 | 替代策略 | 溶栓后转运 PCI |
| medication_ids | Array | 否 | 关联药物 | 阿司匹林、P2Y12、他汀 |
| procedure_ids | Array | 否 | 关联操作 | PCI |
| contraindication_check | Array | 否 | 禁忌校验 | 出血、夹层、过敏 |
| monitoring_plan | Text | 否 | 监测方案 | 生命体征、心电、出血 |
| discharge_plan | Text | 否 | 出院方案 | 二级预防、复诊、康复 |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-ACS |
| review_status | Enum | 是 | 审核状态 | draft / pending_review / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.18 临床路径 ClinicalPathway

**作用**：描述门诊、急诊、住院、随访等完整流程路径。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| pathway_id | String | 是 | 路径 ID | PATHWAY-STEMI-EMERGENCY |
| disease_id | String | 是 | 所属疾病 | STEMI |
| pathway_name | String | 是 | 路径名称 | STEMI 急诊救治路径 |
| scenario | Enum | 是 | 场景 | outpatient / emergency / inpatient / followup |
| start_event | String | 是 | 起点事件 | 患者胸痛就诊 |
| end_event | String | 否 | 终点事件 | 完成再灌注并进入监护 |
| steps | Array | 是 | 路径步骤 | 分诊、心电图、肌钙蛋白、激活导管室 |
| key_time_nodes | Array | 否 | 关键时间节点 | 10 分钟心电图、D-to-B 时间 |
| responsible_role | Array | 否 | 责任角色 | 急诊医生、心内科医生、介入医生 |
| required_data | Array | 否 | 所需数据 | 主诉、生命体征、ECG、肌钙蛋白 |
| output_document | Array | 否 | 输出文书 | 预问诊、病历、会诊单、随访计划 |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-ACS |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.19 患者状态 PatientState

**作用**：描述患者在诊疗过程中的动态状态，用于状态机和推理流转。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| state_id | String | 是 | 状态 ID | STATE-ACS-HIGH-RISK |
| disease_id | String | 否 | 关联疾病 | ACS |
| state_name | String | 是 | 状态名称 | ACS 高危状态 |
| state_type | Enum | 是 | 状态类型 | suspected / confirmed / worsening / stable / post_treatment / followup |
| trigger_conditions | Array | 是 | 触发条件 | 胸痛 + ST 改变 + 肌钙蛋白升高 |
| risk_level | Enum | 是 | 风险等级 | low / medium / high / critical |
| recommended_action | Text | 否 | 推荐处理 | 立即心内科会诊，启动 ACS 流程 |
| prohibited_action | Text | 否 | 禁止或警示动作 | 未排除夹层前谨慎抗凝 |
| exit_conditions | Array | 否 | 退出条件 | 完成再灌注、生命体征稳定 |
| next_state_ids | Array | 否 | 下一状态 | STATE-POST-PCI-STABLE |
| source_rule_id | String | 否 | 来源规则 | RULE-STEMI-001 |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.20 病程事件 ClinicalEvent

**作用**：描述诊疗过程中的事件节点，支撑事件驱动图谱和状态流转。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| event_id | String | 是 | 事件 ID | EVENT-CHEST-PAIN-ARRIVAL |
| event_name | String | 是 | 事件名称 | 胸痛患者到达急诊 |
| event_type | Enum | 是 | 事件类型 | symptom_onset / visit / exam / diagnosis / treatment / consult / followup |
| trigger_source | Enum | 否 | 触发来源 | patient / doctor / system / exam_result |
| input_data | Array | 否 | 输入数据 | 主诉、生命体征、心电图 |
| output_state | String | 否 | 输出状态 | suspected_ACS |
| next_action | Text | 否 | 下一步动作 | 10 分钟内完成心电图 |
| responsible_role | String | 否 | 责任角色 | 急诊医生 |
| time_requirement | String | 否 | 时间要求 | 10 分钟内 |
| related_pathway_id | String | 否 | 关联路径 | PATHWAY-STEMI-EMERGENCY |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.21 推理规则 ReasoningRule

**作用**：将指南、诊断标准、临床路径转成可解释、可审核的推理规则。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| rule_id | String | 是 | 规则 ID | RULE-STEMI-001 |
| rule_name | String | 是 | 规则名称 | STEMI 初筛规则 |
| disease_id | String | 否 | 关联疾病 | STEMI |
| rule_type | Enum | 是 | 规则类型 | diagnosis / risk / treatment / warning / followup / quality_control |
| scenario | Enum | 否 | 适用场景 | emergency / outpatient / inpatient / followup |
| input_conditions | Array | 是 | 输入条件 | 胸痛 + ST 段抬高 |
| logic_expression | Text | 是 | 逻辑表达式 | IF 胸痛 AND ST 抬高 THEN 疑似 STEMI |
| output_result | String | 是 | 输出结果 | 疑似 STEMI |
| output_state_id | String | 否 | 输出状态 ID | STATE-STEMI-SUSPECTED |
| recommended_action | Text | 否 | 推荐动作 | 立即启动胸痛中心流程 |
| priority | Enum | 是 | 优先级 | normal / high / critical |
| explainability | Text | 是 | 可解释说明 | 依据 ECG 缺血性改变和典型胸痛 |
| source_evidence_id | String | 否 | 来源证据 | EVIDENCE-STEMI-001 |
| source_guideline_id | String | 否 | 来源指南 | GUIDELINE-ACS |
| rule_status | Enum | 是 | 规则状态 | enabled / disabled / deprecated |
| review_status | Enum | 是 | 审核状态 | draft / pending_review / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.22 医生角色 DoctorRole

**作用**：表示诊疗路径中的责任角色，不建议直接绑定具体医生个人。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| role_id | String | 是 | 角色 ID | ROLE-ER-DOCTOR |
| role_name_cn | String | 是 | 角色名称 | 急诊医生 |
| role_name_en | String | 否 | 英文名称 | Emergency physician |
| department_id | String | 否 | 所属科室 | DEPT-EMERGENCY |
| responsibility | Text | 否 | 职责 | 初筛、评估、启动急诊流程 |
| decision_permission | Text | 否 | 决策权限 | 可发起心内科会诊 |
| related_events | Array | 否 | 关联事件 | 胸痛到诊、心电图判读 |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.23 科室 Department

**作用**：表示院内科室、中心和执行部门，用于路径分工和院内落地。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| department_id | String | 是 | 科室 ID | DEPT-CARDIOLOGY |
| department_name_cn | String | 是 | 科室中文名 | 心血管内科 |
| department_name_en | String | 否 | 英文名 | Cardiology Department |
| parent_department_id | String | 否 | 上级科室 | DEPT-INTERNAL |
| department_type | Enum | 否 | 科室类型 | clinical / medical_tech / emergency / ward / center |
| hospital_area | String | 否 | 院区 | 本部 |
| responsibility | Text | 否 | 职责 | 心血管疾病诊疗 |
| related_specialty_id | String | 否 | 关联专科 | CARDIOLOGY |
| enabled_status | Enum | 是 | 启用状态 | enabled / disabled |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.24 指南 Guideline

**作用**：沉淀指南、共识、国家标准等依据，实现知识来源可追溯。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| guideline_id | String | 是 | 指南 ID | GUIDELINE-ESC-ACS-2023 |
| guideline_name_cn | String | 是 | 中文名称 | 急性冠脉综合征管理指南 |
| guideline_name_en | String | 否 | 英文名称 | ESC Guidelines for ACS |
| organization | String | 是 | 发布机构 | ESC / AHA / ACC / 中华医学会 |
| publish_year | Integer | 是 | 发布年份 | 2023 |
| version | String | 否 | 指南版本 | 2023 |
| disease_scope | Array | 否 | 适用疾病 | ACS、STEMI、NSTEMI |
| url_or_reference | String | 否 | 来源链接或文献 | 指南来源 |
| authority_level | Enum | 是 | 权威等级 | international / national / society / local / expert |
| language | String | 否 | 语言 | 中文 / 英文 |
| update_status | Enum | 是 | 更新状态 | current / outdated / replaced |
| replacement_guideline_id | String | 否 | 替代指南 ID | GUIDELINE-ACS-2026 |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| created_time | DateTime | 否 | 创建时间 | 2026-06-13 10:00:00 |

---

## 1.25 证据条目 Evidence

**作用**：把指南中的关键段落、推荐意见、证据等级拆成可审核知识点。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| evidence_id | String | 是 | 证据 ID | EVIDENCE-ACS-001 |
| guideline_id | String | 是 | 所属指南 | GUIDELINE-ACS |
| chapter | String | 否 | 章节 | 诊断 / 治疗 / 风险分层 |
| section | String | 否 | 小节 | ECG 初筛 |
| original_text | Text | 是 | 指南关键原文或要点 | 推荐尽早进行 ECG 评估 |
| summary_cn | Text | 是 | 中文摘要 | 胸痛患者需快速完成心电图 |
| evidence_type | Enum | 否 | 证据类型 | recommendation / definition / criteria / warning / pathway |
| recommendation_class | String | 否 | 推荐等级 | I / IIa / IIb / III |
| evidence_level | String | 否 | 证据等级 | A / B / C |
| applicable_condition | Text | 否 | 适用条件 | 疑似 ACS 患者 |
| linked_rule_id | String | 否 | 关联推理规则 | RULE-STEMI-001 |
| linked_criteria_id | String | 否 | 关联诊断标准 | DC-AMI-001 |
| reviewer | String | 否 | 审核人 | 心内科专家 |
| review_status | Enum | 是 | 审核状态 | draft / pending_review / approved / rejected |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.26 数据来源 DataSource

**作用**：记录数据来自哪里、由谁抽取、质量如何，支撑审计追溯。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| source_id | String | 是 | 数据来源 ID | SOURCE-GUIDELINE-001 |
| source_type | Enum | 是 | 来源类型 | guideline / textbook / paper / hospital_rule / expert_review / public_standard / EMR |
| source_name | String | 是 | 来源名称 | ESC ACS Guidelines |
| authority_level | Enum | 是 | 权威等级 | high / medium / low |
| source_url | String | 否 | 来源地址 | 指南链接 |
| citation | Text | 否 | 引用格式 | 文献引用 |
| access_date | Date | 否 | 获取日期 | 2026-06-13 |
| extracted_by | String | 否 | 提取方式 | AI / 人工 / 规则 |
| extractor_version | String | 否 | 抽取工具版本 | KG-Extractor V1.0 |
| quality_score | Float | 否 | 质量评分 | 0.95 |
| license_note | Text | 否 | 授权说明 | 院内使用 |
| review_status | Enum | 是 | 审核状态 | draft / approved |
| version | String | 是 | 版本号 | V1.0 |

---

## 1.27 审核状态 ReviewStatus

**作用**：记录医生审核过程，支持草稿、待审核、通过、驳回、废弃等状态。

| 字段 | 类型 | 是否必填 | 说明 | 示例 |
|---|---|---:|---|---|
| review_id | String | 是 | 审核记录 ID | REVIEW-001 |
| target_entity_type | String | 是 | 审核对象类型 | Disease / Rule / Evidence |
| target_entity_id | String | 是 | 审核对象 ID | RULE-STEMI-001 |
| review_status | Enum | 是 | 审核状态 | draft / pending_review / approved / rejected / deprecated |
| reviewer_id | String | 否 | 审核人 ID | DOC-001 |
| reviewer_name | String | 否 | 审核医生 | 张主任 |
| reviewer_role | String | 否 | 审核角色 | 心内科主任 |
| review_comment | Text | 否 | 审核意见 | 建议补充鉴别主动脉夹层 |
| review_time | DateTime | 否 | 审核时间 | 2026-06-13 10:00 |
| version_before_review | String | 否 | 审核前版本 | V1.0 |
| version_after_review | String | 否 | 审核后版本 | V1.1 |
| change_summary | Text | 否 | 修改摘要 | 补充禁忌与鉴别诊断 |
| operator | String | 否 | 操作人 | AI / 医生 / 产品经理 |

---

# 2. 核心关系 Schema

## 2.1 层级归属关系

| 关系名 | 起点实体 | 终点实体 | 关系中文名 | 说明 |
|---|---|---|---|---|
| has_category | Specialty | DiseaseCategory | 包含疾病大类 | 专科包含多个疾病大类 |
| belongs_to_specialty | DiseaseCategory | Specialty | 属于专科 | 疾病大类归属某专科 |
| has_subcategory | DiseaseCategory | DiseaseSubcategory | 包含疾病亚类 | 疾病大类包含多个亚类 |
| belongs_to_category | DiseaseSubcategory | DiseaseCategory | 属于疾病大类 | 疾病亚类归属疾病大类 |
| contains_disease | DiseaseSubcategory | Disease | 包含疾病 | 疾病亚类包含具体疾病 |
| belongs_to_subcategory | Disease | DiseaseSubcategory | 属于疾病亚类 | 疾病归属亚类 |
| belongs_to_category | Disease | DiseaseCategory | 属于疾病大类 | 疾病直接归属大类 |
| belongs_to_specialty | Disease | Specialty | 属于专科 | 疾病直接归属专科 |

## 2.2 疾病知识关系

| 关系名 | 起点实体 | 终点实体 | 关系中文名 | 说明 |
|---|---|---|---|---|
| has_type | Disease | DiseaseType | 具有分型 | 疾病具有一种或多种分型 |
| has_stage | Disease | DiseaseStage | 具有分期/分层 | 疾病具有分期、分级或风险层级 |
| has_symptom | Disease | Symptom | 具有症状 | 疾病常见症状 |
| has_sign | Disease | Sign | 具有体征 | 疾病相关体征 |
| requires_exam | Disease | Exam | 需要检查 | 疾病诊断或评估需要检查 |
| exam_has_indicator | Exam | ExamIndicator | 包含指标 | 检查包含具体指标 |
| has_diagnostic_criteria | Disease | DiagnosisCriteria | 具有诊断标准 | 疾病对应诊断标准 |
| differentiates_from | Disease | Disease | 需要鉴别 | 当前疾病需要与目标疾病鉴别 |
| has_differential_diagnosis | Disease | DifferentialDiagnosis | 具有鉴别诊断项 | 疾病挂载结构化鉴别诊断 |
| has_risk_factor | Disease | RiskFactor | 具有危险因素 | 疾病发生或进展相关风险 |
| may_cause_complication | Disease | Complication | 可能导致并发症 | 疾病可能导致某并发症 |
| complication_related_to_indicator | Complication | ExamIndicator | 并发症关联指标 | 并发症监测指标 |
| symptom_suggests_disease | Symptom | Disease | 症状提示疾病 | 症状可作为疾病线索 |
| sign_suggests_disease | Sign | Disease | 体征提示疾病 | 体征可作为疾病线索 |

## 2.3 治疗关系

| 关系名 | 起点实体 | 终点实体 | 关系中文名 | 说明 |
|---|---|---|---|---|
| has_treatment_plan | Disease | TreatmentPlan | 具有治疗方案 | 疾病对应治疗方案 |
| treated_by_medication | Disease | Medication | 可用药物治疗 | 疾病可用药物治疗 |
| treated_by_procedure | Disease | Procedure | 可用手术/介入治疗 | 疾病可用手术或介入处理 |
| plan_includes_medication | TreatmentPlan | Medication | 方案包含药物 | 治疗方案中包含药物 |
| plan_includes_procedure | TreatmentPlan | Procedure | 方案包含操作 | 治疗方案中包含操作 |
| medication_has_contraindication | Medication | Disease / PatientState / RiskFactor / ExamIndicator | 药物禁忌 | 药物在特定疾病、状态、风险或指标下禁忌 |
| procedure_has_contraindication | Procedure | Disease / PatientState / RiskFactor / ExamIndicator | 操作禁忌 | 操作在特定情况禁忌 |
| requires_monitoring | Medication / Procedure | ExamIndicator | 需要监测 | 治疗过程需要监测指标 |
| medication_causes_adverse_reaction | Medication | Complication | 药物可能导致不良反应 | 药物可能引起并发症或不良事件 |
| procedure_causes_complication | Procedure | Complication | 操作可能导致并发症 | 手术/介入风险 |

## 2.4 路径、状态、事件关系

| 关系名 | 起点实体 | 终点实体 | 关系中文名 | 说明 |
|---|---|---|---|---|
| has_clinical_pathway | Disease | ClinicalPathway | 具有临床路径 | 疾病对应路径 |
| pathway_has_event | ClinicalPathway | ClinicalEvent | 路径包含事件 | 临床路径包含多个事件 |
| event_triggers_state | ClinicalEvent | PatientState | 事件触发状态 | 某事件触发患者状态 |
| state_triggers_event | PatientState | ClinicalEvent | 状态触发事件 | 患者状态触发下一事件 |
| state_recommends_plan | PatientState | TreatmentPlan | 状态推荐方案 | 状态对应推荐治疗方案 |
| state_recommends_medication | PatientState | Medication | 状态推荐药物 | 状态对应用药建议 |
| state_recommends_procedure | PatientState | Procedure | 状态推荐操作 | 状态对应介入或手术 |
| event_handled_by_role | ClinicalEvent | DoctorRole | 事件由角色处理 | 事件责任人 |
| event_executed_by_department | ClinicalEvent | Department | 事件由科室执行 | 事件执行科室 |
| pathway_managed_by_department | ClinicalPathway | Department | 路径由科室管理 | 路径责任科室 |
| state_has_risk_factor | PatientState | RiskFactor | 状态关联风险 | 患者状态关联风险因素 |
| state_warns_complication | PatientState | Complication | 状态预警并发症 | 状态提示并发症风险 |

## 2.5 推理规则关系

| 关系名 | 起点实体 | 终点实体 | 关系中文名 | 说明 |
|---|---|---|---|---|
| rule_for_disease | ReasoningRule | Disease | 规则服务疾病 | 规则服务于某疾病 |
| rule_uses_symptom | ReasoningRule | Symptom | 规则使用症状 | 规则输入包含症状 |
| rule_uses_sign | ReasoningRule | Sign | 规则使用体征 | 规则输入包含体征 |
| rule_uses_exam | ReasoningRule | Exam | 规则使用检查 | 规则输入包含检查 |
| rule_uses_indicator | ReasoningRule | ExamIndicator | 规则使用指标 | 规则输入包含检查指标 |
| rule_uses_risk_factor | ReasoningRule | RiskFactor | 规则使用危险因素 | 规则输入包含风险因素 |
| rule_outputs_state | ReasoningRule | PatientState | 规则输出状态 | 规则推理结果为患者状态 |
| rule_outputs_disease | ReasoningRule | Disease | 规则输出疾病 | 规则推理结果为疑似或确诊疾病 |
| rule_recommends_plan | ReasoningRule | TreatmentPlan | 规则推荐方案 | 规则推荐治疗方案 |
| rule_recommends_exam | ReasoningRule | Exam | 规则推荐检查 | 规则推荐下一步检查 |
| rule_warns_complication | ReasoningRule | Complication | 规则预警并发症 | 规则输出风险预警 |
| rule_supported_by_evidence | ReasoningRule | Evidence | 规则由证据支持 | 规则可追溯到证据 |

## 2.6 指南证据关系

| 关系名 | 起点实体 | 终点实体 | 关系中文名 | 说明 |
|---|---|---|---|---|
| based_on_guideline | Disease | Guideline | 基于指南 | 疾病定义或分类来源于指南 |
| based_on_guideline | DiagnosisCriteria | Guideline | 基于指南 | 诊断标准来源于指南 |
| based_on_guideline | TreatmentPlan | Guideline | 基于指南 | 治疗方案来源于指南 |
| based_on_guideline | Procedure | Guideline | 基于指南 | 操作适应症来源于指南 |
| based_on_guideline | Medication | Guideline | 基于指南 | 药物推荐来源于指南 |
| guideline_has_evidence | Guideline | Evidence | 指南包含证据 | 指南拆解为证据条目 |
| evidence_supports_rule | Evidence | ReasoningRule | 证据支持规则 | 证据支持推理规则 |
| evidence_supports_criteria | Evidence | DiagnosisCriteria | 证据支持诊断标准 | 证据支持诊断标准 |
| evidence_supports_treatment | Evidence | TreatmentPlan | 证据支持治疗方案 | 证据支持治疗方案 |
| evidence_supports_medication | Evidence | Medication | 证据支持药物 | 证据支持用药 |
| evidence_supports_procedure | Evidence | Procedure | 证据支持操作 | 证据支持介入或手术 |
| has_data_source | 任意知识实体 | DataSource | 具有数据来源 | 任何实体均可关联来源 |
| has_review_status | 任意知识实体 | ReviewStatus | 具有审核状态 | 任何实体均可关联审核记录 |

## 2.7 科室与角色关系

| 关系名 | 起点实体 | 终点实体 | 关系中文名 | 说明 |
|---|---|---|---|---|
| department_belongs_to_specialty | Department | Specialty | 科室归属专科 | 院内科室与学科映射 |
| role_belongs_to_department | DoctorRole | Department | 角色归属科室 | 医生角色所属科室 |
| disease_managed_by_department | Disease | Department | 疾病由科室管理 | 疾病院内管理科室 |
| procedure_performed_by_department | Procedure | Department | 操作由科室执行 | 手术或介入执行科室 |
| pathway_involves_role | ClinicalPathway | DoctorRole | 路径涉及角色 | 临床路径涉及多角色协同 |
| treatment_plan_executed_by_role | TreatmentPlan | DoctorRole | 方案由角色执行 | 方案执行责任角色 |

---

# 3. 心血管内科疾病大类标准初版

| 大类编码 | 疾病大类 | 英文名称 | 说明 |
|---|---|---|---|
| CARD-CAD | 冠状动脉疾病 | Coronary Artery Disease | 冠心病、ACS、心绞痛、心肌梗死 |
| CARD-ARR | 心律失常 | Arrhythmia | 房颤、室速、传导阻滞、早搏等 |
| CARD-HF | 心力衰竭 | Heart Failure | 急性心衰、慢性心衰、射血分数分类 |
| CARD-CM | 心肌病 | Cardiomyopathy | 扩张型、肥厚型、限制型、致心律失常性、遗传代谢性心肌病 |
| CARD-HTN | 高血压及血压相关疾病 | Hypertension and Blood Pressure Disorders | 原发性高血压、继发性高血压、高血压急症 |
| CARD-VHD | 心脏瓣膜病 | Valvular Heart Disease | 二尖瓣、主动脉瓣、三尖瓣、肺动脉瓣疾病 |
| CARD-PCD | 心包疾病 | Pericardial Disease | 心包炎、心包积液、缩窄性心包炎 |
| CARD-IE | 感染性心内膜炎 | Infective Endocarditis | 自体瓣膜、人工瓣膜、器械相关感染 |
| CARD-PH | 肺循环疾病 / 肺高压 | Pulmonary Circulation Disease / Pulmonary Hypertension | 肺动脉高压、慢性血栓栓塞性肺高压 |
| CARD-AORTA | 主动脉及外周血管疾病 | Aortic and Peripheral Vascular Disease | 主动脉夹层、主动脉瘤、外周动脉疾病 |
| CARD-ACHD | 成人先天性心脏病 | Adult Congenital Heart Disease | 房缺、室缺、法洛四联症术后管理等 |
| CARD-LIPID | 血脂异常与动脉粥样硬化 | Dyslipidemia and Atherosclerosis | 高 LDL-C、家族性高胆固醇血症 |
| CARD-CRITICAL | 心血管急危重症 | Cardiovascular Critical Care | 心源性休克、恶性心律失常、心脏骤停 |
| CARD-RARE | 遗传性 / 罕见心血管疾病 | Genetic and Rare Cardiovascular Disease | 法布里病、淀粉样变、离子通道病等 |

---

# 4. 心血管内科疾病亚类示例

## 4.1 冠状动脉疾病 CARD-CAD

| 亚类编码 | 疾病亚类 | 示例疾病 |
|---|---|---|
| CARD-CAD-ACS | 急性冠脉综合征 | STEMI、NSTEMI、不稳定型心绞痛 |
| CARD-CAD-SCAD | 稳定性冠状动脉疾病 | 稳定型心绞痛、慢性冠脉综合征 |
| CARD-CAD-MINOCA | 非阻塞性冠脉心肌梗死 | MINOCA |
| CARD-CAD-VASO | 冠脉痉挛 / 微血管疾病 | 变异型心绞痛、微血管性心绞痛 |

## 4.2 心律失常 CARD-ARR

| 亚类编码 | 疾病亚类 | 示例疾病 |
|---|---|---|
| CARD-ARR-AF | 房性心律失常 | 房颤、房扑、房速 |
| CARD-ARR-VA | 室性心律失常 | 室早、室速、室颤 |
| CARD-ARR-BLOCK | 传导阻滞 | 房室传导阻滞、束支传导阻滞 |
| CARD-ARR-CHANNEL | 离子通道病 | 长 QT 综合征、Brugada 综合征 |

## 4.3 心力衰竭 CARD-HF

| 亚类编码 | 疾病亚类 | 示例疾病 |
|---|---|---|
| CARD-HF-ACUTE | 急性心力衰竭 | 急性左心衰、急性肺水肿 |
| CARD-HF-CHRONIC | 慢性心力衰竭 | 慢性心衰 |
| CARD-HF-HFrEF | 射血分数降低型心衰 | HFrEF |
| CARD-HF-HFpEF | 射血分数保留型心衰 | HFpEF |
| CARD-HF-HFmrEF | 射血分数轻度降低型心衰 | HFmrEF |

## 4.4 心肌病 CARD-CM

| 亚类编码 | 疾病亚类 | 示例疾病 |
|---|---|---|
| CARD-CM-DCM | 扩张型心肌病 | DCM |
| CARD-CM-HCM | 肥厚型心肌病 | HCM |
| CARD-CM-RCM | 限制型心肌病 | RCM |
| CARD-CM-ARVC | 致心律失常性心肌病 | ARVC |
| CARD-CM-INFILTRATIVE | 浸润 / 代谢性心肌病 | 淀粉样变、法布里病 |
| CARD-CM-MYOCARDITIS | 心肌炎相关心肌病 | 病毒性心肌炎、免疫性心肌炎 |

---

# 5. 建模导入建议

## 5.1 节点导入 JSON 模板

```json
{
  "id": "CARD-CAD-ACS-STEMI",
  "name_cn": "ST 段抬高型心肌梗死",
  "name_en": "ST-elevation myocardial infarction",
  "entity_type": "Disease",
  "code": "STEMI",
  "standard_code": "ICD-10: I21.0",
  "description": "急性冠状动脉闭塞导致心肌坏死的临床综合征",
  "source_id": "SOURCE-GUIDELINE-001",
  "guideline_id": "GUIDELINE-ESC-ACS-2023",
  "evidence_id": "EVIDENCE-STEMI-001",
  "review_status": "pending_review",
  "confidence": 0.92,
  "version": "V1.0",
  "created_by": "AI",
  "created_time": "2026-06-13 10:00:00",
  "updated_time": "2026-06-13 10:00:00"
}
```

## 5.2 关系导入 JSON 模板

```json
{
  "relation_id": "REL-000001",
  "relation_type": "has_symptom",
  "source_node_id": "CARD-CAD-ACS-STEMI",
  "target_node_id": "SYM-CHEST-PAIN",
  "source_entity_type": "Disease",
  "target_entity_type": "Symptom",
  "relation_name_cn": "具有症状",
  "description": "STEMI 常表现为胸痛",
  "confidence": 0.95,
  "evidence_id": "EVIDENCE-STEMI-001",
  "source_id": "SOURCE-GUIDELINE-001",
  "review_status": "pending_review",
  "version": "V1.0"
}
```

## 5.3 图数据库落地建议

### Neo4j 标签建议

```text
:Specialty
:DiseaseCategory
:DiseaseSubcategory
:Disease
:DiseaseType
:DiseaseStage
:Symptom
:Sign
:Exam
:ExamIndicator
:DiagnosisCriteria
:DifferentialDiagnosis
:RiskFactor
:Complication
:Medication
:Procedure
:TreatmentPlan
:ClinicalPathway
:PatientState
:ClinicalEvent
:ReasoningRule
:DoctorRole
:Department
:Guideline
:Evidence
:DataSource
:ReviewStatus
```

### Neo4j 关系建议

```text
(:Specialty)-[:HAS_CATEGORY]->(:DiseaseCategory)
(:DiseaseCategory)-[:HAS_SUBCATEGORY]->(:DiseaseSubcategory)
(:DiseaseSubcategory)-[:CONTAINS_DISEASE]->(:Disease)
(:Disease)-[:HAS_SYMPTOM]->(:Symptom)
(:Disease)-[:HAS_SIGN]->(:Sign)
(:Disease)-[:REQUIRES_EXAM]->(:Exam)
(:Exam)-[:EXAM_HAS_INDICATOR]->(:ExamIndicator)
(:Disease)-[:HAS_DIAGNOSTIC_CRITERIA]->(:DiagnosisCriteria)
(:Disease)-[:HAS_TREATMENT_PLAN]->(:TreatmentPlan)
(:TreatmentPlan)-[:PLAN_INCLUDES_MEDICATION]->(:Medication)
(:TreatmentPlan)-[:PLAN_INCLUDES_PROCEDURE]->(:Procedure)
(:Disease)-[:HAS_CLINICAL_PATHWAY]->(:ClinicalPathway)
(:ClinicalPathway)-[:PATHWAY_HAS_EVENT]->(:ClinicalEvent)
(:ClinicalEvent)-[:EVENT_TRIGGERS_STATE]->(:PatientState)
(:ReasoningRule)-[:RULE_SUPPORTED_BY_EVIDENCE]->(:Evidence)
(:Guideline)-[:GUIDELINE_HAS_EVIDENCE]->(:Evidence)
```

---

# 6. 医生审核版建议

## 6.1 医生审核重点

| 审核对象 | 审核重点 |
|---|---|
| 疾病分类 | 大类、亚类是否符合专科医生习惯 |
| 疾病定义 | 是否准确、是否符合指南和临床表达 |
| ICD 编码 | 是否准确，是否存在一病多码情况 |
| 诊断标准 | 必要条件、可选条件、排除条件是否合理 |
| 鉴别诊断 | 是否覆盖关键高危鉴别 |
| 治疗方案 | 是否符合本院能力和流程 |
| 药物禁忌 | 是否充分覆盖高危禁忌 |
| 介入 / 手术 | 适应症、禁忌症、时机是否合理 |
| 临床路径 | 门诊、急诊、住院、随访是否贴近真实流程 |
| 推理规则 | 逻辑是否可解释、是否容易误触发 |
| 指南证据 | 来源是否权威、是否需要更新 |
| 审核状态 | 是否区分草稿、待审、通过、驳回 |

## 6.2 审核状态流转

```text
draft 草稿
  → pending_review 待医生审核
      → approved 审核通过
      → rejected 驳回修改
          → draft 草稿修订
  → deprecated 废弃
```

---

# 7. 第一阶段落地范围建议

## 7.1 第一阶段不建议一次性做全量

建议优先选择心血管内科中高价值、高频、高风险、路径清晰的疾病：

| 优先级 | 疾病方向 | 原因 |
|---|---|---|
| P0 | 急性冠脉综合征 / 急性心肌梗死 | 急诊高危、路径明确、价值明显 |
| P0 | 心力衰竭 | 高频、住院多、随访管理价值高 |
| P1 | 房颤 | 抗凝风险分层、长期管理价值高 |
| P1 | 高血压急症 | 急诊场景明确、规则可建 |
| P1 | 心肌病 | 专科特色强，适合专家审核 |
| P2 | 瓣膜病 | 影像和手术决策复杂 |
| P2 | 罕见 / 遗传性心血管病 | 专科能力体现明显，但数据建设难度高 |

## 7.2 第一阶段推荐最小闭环

```text
专科：心血管内科
疾病大类：冠状动脉疾病
疾病亚类：急性冠脉综合征
疾病：STEMI / NSTEMI / 不稳定型心绞痛
核心能力：
  1. 患者预问诊
  2. 症状结构化
  3. ECG / 肌钙蛋白 / 生命体征接入
  4. 疑似 ACS 状态识别
  5. 鉴别主动脉夹层、肺栓塞等高危疾病
  6. 触发胸痛中心路径
  7. 生成医生审核提示
  8. 记录指南证据来源
```

---

# 8. 最终版核心总结

本 Schema 不是简单的：

```text
疾病 → 症状 → 检查 → 治疗
```

而是完整的：

```text
专科 → 疾病大类 → 疾病亚类 → 疾病
→ 诊断标准 / 症状 / 体征 / 检查 / 指标
→ 风险因素 / 并发症 / 鉴别诊断
→ 治疗方案 / 药物 / 手术介入
→ 临床路径 / 患者状态 / 病程事件
→ 推理规则
→ 指南 / 证据条目
→ 数据来源
→ 医生审核
```

这套结构用于支撑：

1. 专科知识资产沉淀；
2. 专病数据库结构化治理；
3. 专科辅助诊疗推理；
4. 患者预问诊与病历结构化；
5. 医生审核与知识迭代；
6. 后续扩展多专科、多病种、多院区场景。

---

# 9. 文件版本记录

| 版本 | 日期 | 说明 |
|---|---|---|
| V1.0 | 2026-06-13 | 专科知识图谱最终 Schema 初版，心血管内科优先落地 |
