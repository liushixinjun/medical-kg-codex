# 专科知识图谱 Schema 标准

版本：V3.0（CDSS落地稳定版）

更新时间：2026-08-18 13:22:00

适用范围：心血管内科专科知识图谱，并支持后续扩展到其他专科。

## 更新日志

| 时间 | 版本 | 变更内容 | 影响范围 |
|---|---|---|---|
| 2026-08-18 13:22:00 | V3.0 | 修正证据关系执行口径：主证据身份由 `primary_evidence_code` 字段标识，证据关系沿用现库 `supported_by_evidence`、`derived_from`、`based_on_guideline`、`uses_primary_guideline`，不制造未迁移的新关系名。 | 来源和证据关系、入库后复核 |
| 2026-08-18 12:31:00 | V3.0 | 明确结构性知识关系与正式 CDSS 推荐关系的边界：检查/检验/治疗方案/鉴别诊断下钻关系不直接进入正式推荐，正式推荐统一走“疾病 → 推荐陈述 → 推荐动作 → 主证据/主指南”。 | 关系标准、CDSS读取口径、入库后复核 |
| 2026-08-14 23:22:35 | V3.0 | 补充 AMI 与心肌病样板的泛化关系治理记录：旧关系不得作为正式推荐结构；鉴别诊断必须走“疾病 → 鉴别对象 → 鉴别规则/排除检查/排除检验 → 证据”的标准路径。 | Schema 关系标准、样板数据复核 |
| 2026-08-14 22:25:00 | V3.0 | 发布 8 月大版本主标准，明确五层架构、疾病三层结构、CDSS 字典优先、正式推荐证据链、AI 解析治理字段隐藏边界。 | 全文 |

## 0. 本版定位

V3.0 是 8 月大版本标准升级的正式主文件。主文件只保留当前可执行标准，不再堆放历史迁移细节、临时修复过程和过渡字段。旧版本内容通过 Git 历史和《专科知识图谱大版本变更记录.md》追溯。

本版解决四类问题：

| 问题 | V3.0 处理方式 | AMI 示例 |
|---|---|---|
| 图谱结构看不懂 | 把疾病目录、临床诊断、标准字典、医学知识、证据链分层说明 | 冠心病是大类，急性心肌梗死是待分型诊断，STEMI/NSTEMI 是具体分型 |
| CDSS 导入后属性节点过多 | 明确“业务实体保留、属性保持属性、AI治理字段隐藏” | `batch_id` 不得显示成节点 |
| 标准字典与图谱名称不一致 | 图谱实体优先绑定 CDSS 标准字典，简称和口语名进入别名 | “PCI”只作为“经皮冠状动脉介入治疗”的别名 |
| 证据节点过多且推荐依据不清 | 正式推荐必须走“推荐陈述 → 推荐动作 → 主证据/支持证据” | “急诊 PCI”展示主依据指南、页码、推荐等级、证据等级和摘要 |

## 1. 核心原则

1. 专科图谱是一张完整业务图谱，不做“展示版子图”。CDSS 导入时应完整导入业务结构，再按场景过滤显示。
2. 医生端、维护端、治理端读取同一张图谱，但读取字段和关系不同。
3. 教材负责疾病骨架，指南负责诊疗决策细节，CDSS 标准字典负责实体身份。
4. 能进入医嘱、诊断、检查、检验、用药、手术推荐的实体，必须优先绑定 CDSS 标准字典。
5. Oracle 既有标准字典默认只读；缺失、重复、名称不规范、别名冲突进入待处理清单，不得直接改旧字典。
6. 新增授权字典表可以按审批边界直接注册，例如体征字典、检查发现字典。
7. 临床实体主名称必须使用标准中文全称；英文缩写、品牌名、口语名、旧名称保存到 `aliases`。
8. 不能为凑覆盖率伪造 ICD 编码、手术编码、药品编码或证据来源。
9. 正式 CDSS 推荐必须具备适用场景、触发条件、禁忌或排除条件、推荐动作、主依据和证据等级。
10. 一般知识展示可以没有正式推荐链，但必须有来源。
11. 过程字段只能用于追溯和治理，不得进入普通 CDSS 图谱元模型展示。
12. 后续指南升级时，不覆盖旧证据；用来源年份、版本、适用范围和冲突状态做裁决。
13. 检查、检验、治疗、用药、手术不得只靠“疾病直接关联项目”进入正式推荐，必须说明服务于哪个诊疗阶段、哪个临床目的、哪个疾病或鉴别对象。
14. 旧泛化关系只能作为候选来源，不能作为新批次抽取目标；新数据必须生成带业务语义的关系和正式推荐链路。

## 2. 总体架构

### 2.1 五个层次

| 层次 | 作用 | 典型实体 | 是否进入 CDSS 业务图谱 | 是否默认给医生展示 |
|---|---|---|---|---|
| 目录层 | 组织专科和疾病大类 | Specialty、DiseaseCategory、DiseaseSubcategory | 是 | 是 |
| 临床诊断层 | 表示疑似诊断、待分型诊断、具体分型诊断 | Disease、StandardDiagnosis | 是 | 是 |
| 医学知识层 | 表示疾病定义、病因、症状、检查、治疗、随访 | Definition、Symptom、ExamItem、Medication、Procedure | 是 | 是 |
| CDSS决策层 | 表示可触发的正式推荐 | ClinicalRule、RecommendationStatement、TreatmentPlan | 是 | 按场景展示 |
| 证据治理层 | 追溯教材、指南、页码、原文和抽取过程 | Guideline、Evidence、SourceSection、治理字段 | 是 | 只展示证据摘要入口 |

### 2.2 疾病三层结构

疾病目录和临床诊断必须区分。

| 层级 | 实体类型 | 中文解释 | 是否作为临床诊断 | AMI 示例 | 心肌病示例 |
|---|---|---|---|---|---|
| 顶层学科 | Specialty | 专科根节点 | 否 | 心血管内科 | 心血管内科 |
| 疾病大类 | DiseaseCategory | 专科下的疾病大类 | 否 | 冠心病 | 心肌病 |
| 疾病亚类 | DiseaseSubcategory | 大类下的展示分组 | 否 | 急性冠脉综合征 | 心肌疾病 |
| 疑似或待分型诊断 | Disease | 临床可以先选择但需要继续分型的诊断 | 是 | 急性心肌梗死 | 心肌病 |
| 具体分型诊断 | Disease | 诊断明确后的分型 | 是 | STEMI、NSTEMI | 肥厚型心肌病、扩张型心肌病 |
| 标准诊断 | StandardDiagnosis | CDSS/ICD 标准字典记录，包含编码和名称 | 是，用于回填和映射 | I21.900 急性心肌梗死 | I42.900 心肌病 |

`DiseaseSubcategory` 只用于目录分组和页面导航，不参与诊断回填，不参与疑似疾病推荐排序。

### 2.3 诊断角色

`Disease.diagnostic_role` 用来说明疾病节点在临床流程中的角色。

| 值 | 中文含义 | 使用场景 | AMI 示例 | 心肌病示例 |
|---|---|---|---|---|
| `suspected_parent` | 疑似或待分型诊断 | 医生早期只能判断大方向，后续需要分型 | 急性心肌梗死 | 心肌病 |
| `specific_subtype` | 具体分型诊断 | 诊断证据充分，可进入出院诊断或明确诊断 | 急性ST段抬高型心肌梗死 | 肥厚型心肌病 |
| `standalone_diagnosis` | 独立诊断 | 不依赖上级待分型诊断，自己就是完整诊断 | 稳定型心绞痛 | 心肌炎 |

### 2.4 标准诊断实体

`StandardDiagnosis` 不是“只有代码”的节点，而是“标准诊断字典项”。

| 字段 | 中文名 | 格式要求 | AMI 示例 |
|---|---|---|---|
| `cdss_dict_id` | CDSS 字典主键 | Oracle UUID 或标准字典唯一主键 | `7f...` |
| `standard_code` | 标准编码 | 原样保存字典编码 | `I21.900` |
| `standard_name` | 标准名称 | 使用字典标准中文名 | 急性心肌梗死 |
| `coding_system` | 编码体系 | `ICD-10`、`ICD-11`、`ICD-9-CM-3` | ICD-10 |
| `source_table` | 来源表 | CDSS 字典表名 | K_ICD10_DICT |
| `valid_flag` | 有效标志 | 只能使用有效记录 | 1 |
| `dictionary_validation_status` | 字典校验状态 | `validated`、`pending_review`、`blocked` | validated |

## 3. 标准实体类型

### 3.1 目录和疾病

| 实体类型 entityType | 中文名 | 用途 | AMI 示例 |
|---|---|---|---|
| `Specialty` | 专科 | 多专科根节点 | 心血管内科 |
| `DiseaseCategory` | 疾病大类 | 专科下的大类目录 | 冠心病 |
| `DiseaseSubcategory` | 疾病亚类 | 大类下的可选分组 | 急性冠脉综合征 |
| `Disease` | 疾病/诊断 | 疑似诊断、待分型诊断、具体分型诊断、独立诊断 | 急性心肌梗死 |
| `StandardDiagnosis` | 标准诊断字典项 | CDSS/ICD 诊断身份 | I21.900 急性心肌梗死 |

### 3.2 医学事实

| 实体类型 entityType | 中文名 | 用途 | AMI 示例 |
|---|---|---|---|
| `Definition` | 疾病定义 | 疾病概述和定义原文摘要 | AMI 是急性心肌缺血性坏死 |
| `DefinitionComponent` | 定义明细 | 定义可拆解要点 | 冠状动脉血供中断 |
| `Etiology` | 病因 | 发病原因 | 冠状动脉粥样硬化 |
| `Pathophysiology` | 病理生理 | 机制和功能变化 | 心肌坏死后心室重构 |
| `Epidemiology` | 流行病学 | 发病趋势、人群特征 | AMI 发病率上升 |
| `Symptom` | 症状 | 患者主观感受 | 胸痛、胸闷、出汗 |
| `Sign` | 体征 | 医生查体观察结果 | 低血压、奔马律 |
| `VitalSignItem` | 生命体征 | 体温、脉搏、呼吸、血压、血氧饱和度 | 收缩压低于 80mmHg |
| `RiskFactor` | 危险因素 | 增加发病或不良结局风险的因素 | 高血压、糖尿病、吸烟 |
| `Complication` | 并发症 | 疾病导致的并发问题 | 心源性休克、心力衰竭 |
| `DifferentialDiagnosis` | 鉴别诊断 | 需要区分的疾病或状态 | 主动脉夹层、肺栓塞 |
| `RiskStratification` | 风险分层 | 风险评分或分层结果 | Killip 分级 |
| `Prognosis` | 预后 | 结局、复发、死亡风险 | 住院死亡风险 |
| `Prevention` | 预防 | 一级预防、二级预防、患者教育 | ABCDE 二级预防 |
| `FollowUp` | 随访 | 复查、康复、长期管理 | 出院后康复随访 |
| `Contraindication` | 禁忌/排除条件 | 推荐动作不可执行的条件 | 未排除主动脉夹层禁用溶栓 |

### 3.3 检查、检验、治疗和动作

| 实体类型 entityType | 中文名 | 用途 | AMI 示例 |
|---|---|---|---|
| `ExamPlan` | 检查方案 | 一组检查项目的临床方案 | 胸痛首诊检查方案 |
| `ExamItem` | 检查项目 | 可开立或可执行的检查 | 心电图、冠状动脉 CTA |
| `ExamObservation` | 检查发现 | 检查报告中的观察结论 | ST 段抬高、病理性 Q 波 |
| `LabItem` | 检验项目 | 可开立的检验项目 | 血常规、心肌损伤标志物 |
| `LabSubitem` | 检验细项 | 检验项目下的指标细项 | 白细胞计数、肌钙蛋白 I |
| `LabSample` | 检验标本 | 标本类型 | 血清、血浆、全血 |
| `TreatmentPlan` | 治疗方案 | 临床治疗策略标题 | 再灌注治疗、抗血小板治疗 |
| `Medication` | 药品 | 标准药品或药物类别 | 阿司匹林肠溶片、氯吡格雷 |
| `Procedure` | 手术/操作 | 标准手术或操作项目 | 经皮冠状动脉介入治疗 |
| `TreatmentItem` | 治疗项目 | 非药品、非手术的治疗处置 | 吸氧、卧床休息、康复治疗 |

治疗方案是策略，药品、手术、治疗项目是可执行动作。疾病大类可以有共性知识，但正式推荐动作优先挂在具体诊断、场景和规则链路下。

### 3.4 来源、证据和推荐

| 实体类型 entityType | 中文名 | 用途 | AMI 示例 |
|---|---|---|---|
| `Guideline` | 指南/教材/共识/说明书 | 文献级来源 | 《内科学（第10版）》 |
| `SourceSection` | 来源章节 | 文献章节或页码范围 | 急性 ST 段抬高型心肌梗死章节 |
| `Evidence` | 证据片段 | 原文证据摘要，支撑某个知识或推荐 | “FMC 后 90 分钟内完成 PCI” |
| `ClinicalRule` | 临床规则 | 触发条件、排除条件、判断逻辑 | STEMI 再灌注路径规则 |
| `RecommendationStatement` | 推荐陈述 | 正式 CDSS 推荐展示和审核主体 | 符合 STEMI 且可 90 分钟内 PCI，推荐直接 PCI |

## 4. 标准关系

### 4.1 疾病目录和诊断关系

| 起点 | 关系 | 终点 | 中文含义 | 案例 |
|---|---|---|---|---|
| Specialty | `has_category` | DiseaseCategory | 专科包含疾病大类 | 心血管内科 → 冠心病 |
| DiseaseCategory | `has_subcategory` | DiseaseSubcategory | 大类包含疾病亚类 | 冠心病 → 急性冠脉综合征 |
| DiseaseCategory | `has_disease` | Disease | 大类包含疾病诊断 | 心肌病 → 心肌病 |
| DiseaseSubcategory | `has_disease` | Disease | 亚类包含疾病诊断 | 急性冠脉综合征 → 急性心肌梗死 |
| Disease | `has_clinical_subtype` | Disease | 待分型诊断包含具体分型 | 急性心肌梗死 → STEMI |
| Disease | `has_standard_diagnosis` | StandardDiagnosis | 疾病绑定标准诊断 | 急性心肌梗死 → I21.900 |
| Disease | `has_alias` | MedicalTermAlias | 疾病别名 | 急性心肌梗死 → AMI |

### 4.2 医学事实关系

| 起点 | 关系 | 终点 | 中文含义 | 案例 |
|---|---|---|---|---|
| Disease | `has_definition` | Definition | 有疾病定义 | AMI → AMI 定义 |
| Definition | `has_definition_component` | DefinitionComponent | 定义拆解明细 | AMI 定义 → 急性缺血性坏死 |
| Disease | `has_etiology` | Etiology | 有病因 | STEMI → 冠脉血栓形成 |
| Disease | `has_pathophysiology` | Pathophysiology | 有病理生理 | STEMI → 左室收缩功能下降 |
| Disease | `has_epidemiology` | Epidemiology | 有流行病学 | AMI → 发病率上升 |
| Disease | `has_symptom` | Symptom | 有症状 | STEMI → 胸痛 |
| Disease | `has_sign` | Sign | 有体征 | STEMI → 低血压 |
| Disease | `has_risk_factor` | RiskFactor | 有危险因素 | STEMI → 高血压 |
| Disease | `has_complication` | Complication | 有并发症 | STEMI → 心源性休克 |
| Disease | `has_differential_diagnosis` | DifferentialDiagnosis | 有鉴别诊断对象 | STEMI → 主动脉夹层 |
| DifferentialDiagnosis | `has_differential_rule` | ClinicalRule | 有鉴别规则 | 主动脉夹层鉴别 → 胸痛放射至背部 |
| DifferentialDiagnosis | `requires_exclusion_exam` | ExamItem | 鉴别诊断需要排除检查 | 主动脉夹层鉴别 → 主动脉 CTA |
| DifferentialDiagnosis | `requires_exclusion_lab` | LabItem/LabSubitem | 鉴别诊断需要排除检验或检验细项 | 肺栓塞鉴别 → D-二聚体 |
| Disease | `has_risk_stratification` | RiskStratification | 有风险分层 | STEMI → Killip 分级 |
| Disease | `has_followup` | FollowUp | 有随访 | AMI → 康复随访 |
| Disease | `has_prognosis` | Prognosis | 有预后 | AMI → 院前猝死风险 |

### 4.3 检查和检验关系

| 起点 | 关系 | 终点 | 中文含义 | 案例 |
|---|---|---|---|---|
| Disease | `has_exam_plan` | ExamPlan | 疾病有检查方案 | STEMI → 急性胸痛首诊检查方案 |
| ExamPlan | `includes_exam_item` | ExamItem | 检查方案包含检查项目 | 首诊检查方案 → 心电图 |
| ExamItem | `exam_item_has_observation` | ExamObservation | 检查项目产生检查发现 | 心电图 → ST 段抬高 |
| Disease | `has_lab_plan` | ExamPlan | 疾病有检验方案 | STEMI → 心肌坏死标志物检测方案 |
| ExamPlan | `includes_lab_item` | LabItem | 检验方案包含检验项目 | 心肌坏死标志物检测方案 → 肌钙蛋白检测 |
| LabItem | `lab_item_has_subitem` | LabSubitem | 检验项目包含检验细项 | 血常规 → 白细胞计数 |
| LabSubitem | `uses_lab_sample` | LabSample | 检验细项使用标本 | 肌钙蛋白 I → 血清 |

检查和检验项目可以被多个场景复用，例如心电图既可用于急性胸痛首诊，也可用于再灌注后疗效评估。是否推荐给医生，不由项目名称决定，而由“关系上的业务语义”决定。

| 关系字段 | 中文含义 | 必填范围 | AMI 示例 |
|---|---|---|---|
| `clinical_stage` | 诊疗阶段 | 检查、检验、治疗动作关系必填 | 首诊、鉴别诊断、治疗前评估、治疗后评估、随访 |
| `purpose` | 推荐目的 | 检查、检验、治疗动作关系必填 | 确诊、分型、排除、风险分层、治疗前安全评估 |
| `recommendation_context` | 推荐语境 | 正式推荐必填 | 急性胸痛、疑似 STEMI、溶栓前、PCI 后 |
| `service_target_type` | 服务对象类型 | 正式推荐必填 | 疾病、鉴别诊断、治疗方案、路径阶段 |
| `service_target_code` | 服务对象编码 | 正式推荐必填 | DIS-CARD-CAD-AMI、DIFF-CARD-AMI-AAD |
| `service_target_name` | 服务对象名称 | 正式推荐必填 | 急性心肌梗死、主动脉夹层鉴别 |
| `priority_level` | 推荐优先级 | 正式推荐必填 | 核心、重要、可选 |

硬规则：

1. 疾病直连检查/检验只能表示“知识上相关”，不能直接作为医生端正式推荐。
2. 首诊辅助检查必须挂在 ExamPlan/LabPlan，并标明 `clinical_stage=首诊`、`purpose=确诊/分型/风险分层`。
3. 鉴别诊断检查必须从 DifferentialDiagnosis 出发，或由 RecommendationStatement 指向鉴别对象和推荐动作，不能只挂在疾病下面。
4. 治疗前检查必须从 TreatmentPlan 或 RecommendationStatement 出发，标明 `purpose=治疗前安全评估/禁忌排除`。
5. 旧关系名 `RECOMMEND_CHECK`、`RECOMMEND_LAB_CHECK`、`HAS_DRUG`、`RECOMMEND_OPERATION` 不作为本 Schema 新增关系。

### 4.4 治疗和正式推荐关系

| 起点 | 关系 | 终点 | 中文含义 | 案例 |
|---|---|---|---|---|
| Disease | `has_treatment_plan` | TreatmentPlan | 疾病有治疗方案 | STEMI → 再灌注治疗 |
| TreatmentPlan | `includes_medication` | Medication | 方案包含药品 | 抗血小板治疗 → 阿司匹林肠溶片 |
| TreatmentPlan | `includes_procedure` | Procedure | 方案包含手术/操作 | 再灌注治疗 → 经皮冠状动脉介入治疗 |
| TreatmentPlan | `includes_treatment_item` | TreatmentItem | 方案包含其他治疗项目 | 一般治疗 → 吸氧 |
| Disease | `has_recommendation_statement` | RecommendationStatement | 疾病有正式推荐陈述 | STEMI → STEMI 直接 PCI 推荐陈述 |
| ClinicalRule | `triggers_recommendation` | RecommendationStatement | 规则触发推荐陈述 | STEMI 再灌注规则 → STEMI 直接 PCI 推荐陈述 |
| RecommendationStatement | `recommends_action` | Medication / Procedure / TreatmentItem / ExamItem / LabItem / LabSubitem | 推荐陈述指向具体动作 | STEMI 直接 PCI 推荐陈述 → 经皮冠状动脉介入治疗 |
| RecommendationStatement | `targets_differential_diagnosis` | DifferentialDiagnosis | 推荐服务于鉴别诊断 | 主动脉夹层排除推荐 → 主动脉夹层 |
| RecommendationStatement | `has_contraindication` | Contraindication | 推荐有禁忌或排除条件 | 溶栓治疗 → 未排除主动脉夹层禁用 |

`has_treatment_plan`、`includes_medication`、`includes_procedure`、`includes_treatment_item` 表示知识展示和方案下钻；`recommends_action` 只允许从 RecommendationStatement 出发，表示患者满足规则后的正式推荐。两者不得混用。

历史兼容说明：旧数据中如存在 `recommends_medication`、`recommends_procedure`、`recommends_exam_item` 等细分推荐关系，仅作为兼容读取；新批次统一生成 `recommends_action`，动作类型由终点实体类型区分。

正式推荐链路必须至少具备：

```text
疾病或鉴别对象
→ 规则或适用场景
→ 推荐陈述
→ 具体动作（检查、检验、药品、手术、治疗项目）
→ 主证据
```

如果只有“治疗方案标题”或“检查项目标题”，没有适用场景、推荐目的和证据，只能进入知识展示，不能进入正式 CDSS 推荐区。

服务器治理口径：结构性知识关系的 `formal_recommendation` 必须为 `no`；正式推荐动作关系的 `formal_recommendation` 才允许为 `yes`。

### 4.5 来源和证据关系

| 起点 | 关系 | 终点 | 中文含义 | 案例 |
|---|---|---|---|---|
| Guideline | `has_source_section` | SourceSection | 文献包含章节 | 《内科学（第10版）》 → STEMI 治疗章节 |
| SourceSection | `has_evidence` | Evidence | 章节包含证据片段 | STEMI 治疗章节 → FMC 后 90 分钟内 PCI |
| 任一医学知识实体 | `supported_by_evidence` | Evidence | 知识有证据支撑 | STEMI 胸痛症状 → 教材临床表现原文 |
| RecommendationStatement | `supported_by_evidence` | Evidence | 推荐陈述有证据支撑 | 直接 PCI 推荐 → 2025 ACS 指南证据 |
| RecommendationStatement | `derived_from` | Evidence | 推荐陈述来源于证据片段 | 直接 PCI 推荐 → 指南原文段落 |
| RecommendationStatement | `based_on_guideline` | Guideline | 推荐依据指南 | 直接 PCI 推荐 → 2025 ACS 指南 |
| RecommendationStatement | `uses_primary_guideline` | Guideline | 推荐主依据文献 | 直接 PCI 推荐 → 2025 ACS 指南 |

“任一医学知识实体”指本 Schema 中的临床实体，包括 Disease、Definition、Symptom、Sign、ExamItem、LabItem、Medication、Procedure、TreatmentPlan、ClinicalRule、RecommendationStatement。

主证据不是靠额外新关系名区分，而是靠 `RecommendationStatement.primary_evidence_code` 指向主 Evidence；支持证据仍可通过 `supported_by_evidence` 或 `derived_from` 关联。主指南同理优先读取 `primary_guideline_code`，并可通过 `uses_primary_guideline` 或 `based_on_guideline` 下钻查看指南实体。

## 5. 字段标准

### 5.1 所有业务节点通用字段

| 字段 | 中文名 | 格式要求 | 是否给普通 CDSS 展示 | AMI 示例 |
|---|---|---|---|---|
| `id` | 图谱内部ID | 全库唯一字符串 | 否 | DIS-CARD-CAD-AMI |
| `entityType` | 实体类型 | 使用第 3 章枚举值 | 是 | Disease |
| `code` | 图谱编码 | 稳定、可追溯、不得复用 | 是 | DIS-CARD-CAD-AMI |
| `name` | 标准主名称 | 中文标准全称优先 | 是 | 急性心肌梗死 |
| `display_name` | 展示名称 | 默认等于 `name`，确有展示需要才单独设置 | 是 | 急性心肌梗死 |
| `aliases` | 别名 | 字符串数组 | 是 | AMI、急性MI |
| `description` | 描述 | 简短中文说明 | 是 | 急性心肌缺血性坏死 |
| `status` | 数据状态 | `active`、`deprecated`、`blocked` | 治理页展示 | active |
| `source` | 来源名称 | 具体书籍、指南、共识、说明书或字典表名称 | 证据页展示 | 《内科学（第10版）》 |
| `schema_version` | Schema 版本 | V主版本.次版本 | 治理页展示 | V3.0 |

### 5.2 标准字典字段

| 字段 | 中文名 | 格式要求 | 适用实体 | AMI 示例 |
|---|---|---|---|---|
| `cdss_dict_id` | CDSS字典主键 | Oracle UUID 或标准字典主键 | StandardDiagnosis、Medication、Procedure、ExamItem、LabItem、LabSubitem、Symptom、Sign、VitalSignItem、TreatmentItem | Oracle UUID |
| `standard_code` | 标准编码 | 原样保存字典编码 | 同上 | I21.900 |
| `standard_name` | 标准名称 | 字典标准中文名 | 同上 | 急性心肌梗死 |
| `source_table` | 来源表 | CDSS 字典表名 | 同上 | K_ICD10_DICT |
| `valid_flag` | 有效标志 | 只允许有效值进入正式链 | 同上 | 1 |
| `dictionary_validation_status` | 字典校验状态 | `validated`、`pending_review`、`blocked` | 同上 | validated |
| `dictionary_snapshot_version` | 字典快照版本 | 每次同步生成稳定版本号 | 同上 | CDSS-DICT-202607 |

### 5.3 基础人群和有效性限制

以下字段用于 Disease、StandardDiagnosis、Medication、Procedure、ExamItem、LabItem、LabSubitem、VitalSignItem、TreatmentItem。

| 字段 | 中文名 | 格式要求 | AMI 示例 |
|---|---|---|---|
| `sex_limit_code` | 性别限制编码 | 使用 CDSS 字典值，空表示不限制 | 空 |
| `sex_limit_name` | 性别限制名称 | 不限制、男性、女性 | 不限制 |
| `age_min` | 最小年龄 | 数值或空 | 18 |
| `age_max` | 最大年龄 | 数值或空 | 空 |
| `age_unit` | 年龄单位 | 岁、月、天 | 岁 |
| `pregnancy_limit_code` | 妊娠限制编码 | CDSS 字典值或空 | 空 |
| `pregnancy_limit_name` | 妊娠限制名称 | 不限制、慎用、禁用 | 空 |
| `lactation_limit_code` | 哺乳限制编码 | CDSS 字典值或空 | 空 |
| `lactation_limit_name` | 哺乳限制名称 | 不限制、慎用、禁用 | 空 |
| `valid_from` | 生效时间 | 日期或空 | 2026-08-02 |
| `valid_to` | 失效时间 | 日期或空 | 空 |

基础过滤顺序：有效期 → 性别 → 年龄 → 妊娠 → 哺乳。基础过滤后，再由规则引擎判断肝肾功能、过敏史、出血风险、药物相互作用、检查结果、诊疗阶段、时间窗、既往手术、孕产状态、并发症。

### 5.4 AI解析治理字段

这些字段允许保存在图谱，但普通 CDSS 图谱元模型配置页和医生端默认不展示。

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

## 6. CDSS 标准字典映射

### 6.1 既有字典来源

| 图谱实体 | CDSS来源表 | 使用方式 | 备注 |
|---|---|---|---|
| StandardDiagnosis | K_ICD10_DICT | 诊断标准主数据 | 只使用有效记录 |
| StandardProcedure / Procedure | K_OPERATION_HANDLE_DICT | 手术/操作标准主数据 | 图谱统一用 Procedure 实体 |
| Medication | K_DRUG_DICT | 药品标准主数据 | 药品全称为主名 |
| ExamItem | K_EXAM_ITEM_DICT | 检查项目字典 | X线、CT 这类笼统词不得直接作为最终项目 |
| LabItem | K_LAB_ITEM_DICT | 检验项目字典 | 血常规、心肌损伤标志物 |
| LabSubitem | K_LAB_SUBITEM_DICT | 检验细项字典 | 白细胞计数、肌钙蛋白 I |
| Symptom | K_SYMPTOM_DICT | 症状字典 | 主观感受 |
| VitalSignItem | K_VITAL_SIGN_ITEM_DICT | 生命体征标准字典 | 体温、脉搏、呼吸、血压、血氧饱和度 |
| TreatmentItem | K_TREATMENT_DICT | 其他治疗项目字典 | 吸氧、卧床休息、康复治疗 |
| MedicalTermAlias | K_TERM、K_TERM_CLASS | 术语和可选用词 | 用于别名、检索、归一 |

### 6.2 需要新增或已新增的字典来源

| 图谱实体 | 建议表名 | 使用方式 | 备注 |
|---|---|---|---|
| Sign | K_CLINICAL_SIGN_DICT | 体征标准字典 | 按症状字典建表风格设计 |
| ExamObservation | K_EXAM_OBSERVATION_DICT | 检查发现字典 | 例如 ST 段抬高、病理性 Q 波 |
| LabSample | K_LAB_SAMPLE_DICT | 检验标本字典 | 血清、血浆、全血 |

新增授权字典可直接注册；旧字典修名、合并、删除必须进入待处理清单。

### 6.3 名称归一规则

| 情况 | 处理方式 | 示例 |
|---|---|---|
| 英文缩写 | 标准中文全称为主名，缩写进别名 | PCI → 经皮冠状动脉介入治疗 |
| 口语药名 | 匹配规范剂型名，口语名进别名 | 肠溶阿司匹林 → 阿司匹林肠溶片 |
| 品牌名 | 匹配通用名或药品标准名，品牌进别名 | 拜阿司匹林 → 阿司匹林肠溶片 |
| 类别词 | 建为类别知识，并连接具体成员 | P2Y12受体抑制剂 → 氯吡格雷 |
| 笼统检查 | 必须结合原文场景匹配具体检查项目 | X线 → 胸部X线检查 |
| 多症状合并短语 | 拆成多个症状实体并保留原句证据 | 胸痛、背痛或腹痛 → 胸痛、背痛、腹痛 |

## 7. 正式 CDSS 推荐链

正式推荐不是“疾病直连治疗方案”。正式推荐必须经过规则和证据。

标准链路：

```text
患者数据
→ ClinicalRule 临床规则
→ RecommendationStatement 推荐陈述
→ Medication / Procedure / TreatmentItem / ExamItem / LabItem
→ Evidence 主证据和支持证据
→ Guideline 来源文献
```

推荐陈述必填字段：

| 字段 | 中文名 | 格式要求 | AMI 示例 |
|---|---|---|---|
| `clinical_scene` | 临床场景 | 急诊、门诊、住院、围手术期、随访 | 急诊 |
| `applicable_population` | 适用人群 | 明确人群描述 | STEMI 发病 12 小时内 |
| `trigger_condition` | 触发条件 | 结构化条件或原文摘要 | 持续 ST 段抬高 |
| `exclusion_condition` | 排除条件 | 禁忌或不适用条件 | 未排除主动脉夹层 |
| `recommendation_text` | 推荐文字 | 面向医生的中文推荐 | 首选直接 PCI |
| `recommendation_class` | 推荐等级 | 原文等级，教材无等级写 N/A | I |
| `evidence_level` | 证据等级 | 原文等级，教材无等级写 N/A | A |
| `primary_source_name` | 主依据来源 | 指南或教材名称 | 2025 ACS 指南 |
| `primary_evidence_id` | 主证据ID | Evidence 节点 ID | EVD-AMI-PCI-001 |
| `clinical_review_status` | 临床使用状态 | `formal_cdss_ready`、`review_required`、`blocked` | formal_cdss_ready |

## 8. 证据模型

### 8.1 Guideline 与 Evidence 区别

| 对象 | 中文解释 | 粒度 | AMI 示例 |
|---|---|---|---|
| Guideline | 整份教材、指南、共识、说明书 | 文件级 | 《内科学（第10版）》 |
| SourceSection | 文献中的章节或页码范围 | 章节级 | STEMI 治疗章节 |
| Evidence | 可支撑一个知识点或推荐的一段原文摘要 | 片段级 | “FMC 后 90 分钟内完成再灌注” |

医生端不展示一大堆 Evidence 节点，只在具体推荐或知识卡片中展示“主依据、页码、推荐等级、证据等级、原文摘要”。证据池用于追溯和审核。

### 8.2 证据必填字段

| 字段 | 中文名 | 格式要求 | AMI 示例 |
|---|---|---|---|
| `source_name` | 来源名称 | 具体文献名称 | 《内科学（第10版）》 |
| `source_type` | 来源类型 | textbook、guideline、consensus、drug_label、authority_web | textbook |
| `source_year` | 来源年份 | 四位年份或空 | 2024 |
| `page_start` | 起始页 | 数字或空 | 253 |
| `page_end` | 结束页 | 数字或空 | 255 |
| `section_title` | 章节标题 | 原文章节名 | 治疗 |
| `evidence_text` | 证据原文摘要 | 保留原文含义，不改写为模型结论 | FMC 后 90 分钟内完成 PCI |
| `recommendation_class` | 推荐等级 | 有则原样保存，无则 N/A | I |
| `evidence_level` | 证据等级 | 有则原样保存，无则 N/A | A |
| `language` | 语言 | zh、en | zh |

## 9. 覆盖率和验收口径

覆盖率必须按诊断角色计算，不得把疑似诊断和具体分型用同一套必填项硬套。

| 诊断角色 | 必须覆盖 | 可以继承或汇总 | 不作为必填 |
|---|---|---|---|
| 疑似或待分型诊断 | 标准诊断、定义、症状、体征、初筛检查、初筛检验、分型入口、危险信号 | 共性病因、共性危险因素、共性并发症 | 具体分型专属治疗推荐 |
| 具体分型诊断 | 标准诊断、定义、诊断标准、鉴别诊断、检查项目、检查发现、检验项目、检验细项、治疗方案、正式推荐链、禁忌、证据 | 上级共性知识 | 无证据的正式推荐 |
| 独立诊断 | 标准诊断、定义、临床表现、诊断、检查、检验、治疗、随访、证据 | 所属大类知识 | 上级分型入口 |

AMI 和心肌病样板验收必须同时检查两件事：知识内容完整性、正式 CDSS 推荐链完整性。

## 10. 疾病差异扩展

核心 Schema 保持通用，不为每个特殊疾病硬造一套主结构。遇到专病差异，按“专病扩展槽位”启用实体和关系。

执行配置文件固定为：

```text
公共执行层_kg_pipeline/专病扩展槽位配置.yaml
```

### 10.1 启用原则

| 规则 | 说明 | AMI 示例 |
|---|---|---|
| 主结构不膨胀 | 疾病、症状、体征、检查、检验、药品、手术、治疗、诊断、证据仍是主干 | STEMI 仍挂检查、检验、治疗、手术和正式推荐 |
| 差异走槽位 | 遗传、血流动力学、瓣膜严重度、心电机制、设备参数等走扩展槽位 | STEMI 的再灌注时间窗走“时间窗”槽位 |
| 必须有来源 | 教材、指南、共识或权威来源明确写到，才允许生成扩展实体 | “FMC 后 90 分钟内 PCI”必须有指南或教材原文 |
| 不建空壳 | 没有原文依据、没有疾病引用、没有临床用途，不生成节点 | 不能只因为想到“罪犯血管”就生成空节点 |
| 不替代字典 | 检查、检验、药品、手术、治疗项目仍优先绑定 CDSS 标准字典 | PCI 主名称仍映射手术字典，时间窗只是推荐条件 |

### 10.2 心血管专病扩展槽位

| 疾病方向 | 扩展内容 | 可启用实体 | 主要用途 |
|---|---|---|---|
| 心肌病 | 遗传方式、基因、变异、家族史、猝死风险 | Gene、GeneticVariant、InheritancePattern、FamilyHistory | 解释遗传性差异、风险分层和家系筛查 |
| 冠心病/AMI | 再灌注时间窗、罪犯血管、梗死部位、危险分层 | TimeWindow、VascularTerritory、InfarctLocation | 支持再灌注推荐和诊断解释 |
| 心力衰竭 | 射血分数表型、容量状态、器械治疗条件 | HeartFailurePhenotype、VolumeStatus | 支持心衰分型和治疗触发条件 |
| 心律失常 | 心电分型、电生理机制、消融靶点 | ECGPattern、ElectrophysiologyMechanism、AblationTarget | 支持诊断解释、消融策略说明 |
| 高血压 | 血压分级、危险分层、靶器官损害、继发病因 | BloodPressureGrade、TargetOrganDamage、SecondaryCause | 支持分级、风险评估和继发病因排查 |
| 瓣膜病 | 瓣膜部位、狭窄/反流、严重程度、手术时机 | ValveAnatomy、ValveLesionType、SeverityGrade | 支持瓣膜病分型和手术时机判断 |
| 肺动脉高压 | 血流动力学指标、临床分型、风险分层 | HemodynamicIndicator、ClinicalSubtype、RiskStratification | 支持诊断标准和风险分层 |
| 起搏治疗相关疾病 | 起搏模式、导线位置、设备参数、并发症 | Device、DeviceParameter、Complication | 支持器械治疗说明和随访 |

### 10.3 扩展实体进入 CDSS 的边界

| 类型 | 是否进入普通知识展示 | 是否进入正式推荐 | 是否需要 CDSS 标准字典 |
|---|---|---|---|
| 基因、遗传方式、家族史 | 可以 | 只能作为风险解释或筛查依据 | 通常不需要 |
| 时间窗、严重程度、容量状态 | 可以 | 可以作为触发条件或排除条件 | 通常不需要 |
| 心电模式、血流动力学指标、瓣膜部位 | 可以 | 可以作为诊断或治疗条件 | 视是否对应检查发现/指标字典 |
| 药品、检查、检验、手术、治疗项目 | 可以 | 可以作为正式动作 | 必须优先绑定 CDSS 标准字典 |
| 设备和设备参数 | 可以 | 通常只做说明，除非存在标准医嘱或耗材字典 | 视医院字典能力 |

### 10.4 审计要求

每个扩展槽位必须通过以下检查：

1. 扩展实体有来源证据。
2. 扩展实体被疾病、诊断标准、风险分层、治疗方案或推荐陈述引用。
3. 扩展实体没有被误抽成普通症状、检查、药品或手术。
4. 扩展实体进入正式推荐时，必须同时具备适用场景、触发条件、禁忌/排除条件和主证据。
5. 需要医嘱回填的实体必须绑定 CDSS 标准字典；不能绑定时只能做知识展示。

## 11. CDSS 导入和展示边界

### 11.1 必须导入的业务实体

Specialty、DiseaseCategory、DiseaseSubcategory、Disease、StandardDiagnosis、Definition、DefinitionComponent、Etiology、Pathophysiology、Epidemiology、Symptom、Sign、VitalSignItem、RiskFactor、Complication、DifferentialDiagnosis、RiskStratification、ExamPlan、ExamItem、ExamObservation、LabItem、LabSubitem、LabSample、TreatmentPlan、Medication、Procedure、TreatmentItem、Contraindication、ClinicalRule、RecommendationStatement、FollowUp、Prognosis、Prevention、Guideline、SourceSection、Evidence、MedicalTermAlias。

### 11.2 普通 CDSS 元模型配置默认不展示的字段

batch_id、scope_type、scope_target、source_roots、parser_version、extraction_version、import_batch、migration_status、repair_status、merge_status、source_hash、document_hash、evidence_hash、raw_text_anchor、provenance、extraction_log、audit_result、review_notes、created_by、created_at、updated_at。

这些是属性，不是实体节点。导入程序不得用 `keys(n)` 把属性名渲染成图谱节点。

### 11.3 需要过滤的历史对象

| 对象 | 处理 |
|---|---|
| `DiseaseClassification` | 停用，不再新增；已迁移后清理 |
| `Exam` | 停用，改用 ExamItem |
| `LabTest` | 停用，改用 LabItem |
| `ExamIndicator` | 停用，改用 ExamObservation |
| 纯过程节点 | 不进入普通 CDSS 维护页 |
| 审核过程节点 | 不进入普通 CDSS 维护页 |
| 历史兼容节点 | 本月清理范围内处理 |

## 12. 数据质量硬闸门

入库前和入库后都必须检查：

1. 所有临床业务节点必须有 `entityType`、`code`、`name`。
2. 需要回填 CDSS 的实体必须绑定有效标准字典。
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
17. 鉴别诊断必须能说明“鉴别谁、为什么鉴别、用什么检查检验鉴别、结果如何解释、依据来自哪里”。
18. 治疗方案必须区分“方案标题”和“可执行动作”；方案标题不能直接替代医嘱动作。

## 13. 当前禁止新增项

1. 禁止新增 `DiseaseClassification`。
2. 禁止新增 `Exam`、`LabTest`、`ExamIndicator`。
3. 禁止新增只有标题、没有下钻明细的诊断标准。
4. 禁止新增只有标题、没有具体动作的治疗方案。
5. 禁止新增只有缩写的药品、手术、检查、检验实体。
6. 禁止把批次、哈希、路径、脚本版本、审核状态渲染为业务节点。
7. 禁止直接写旧 Oracle 字典修名、合并、删除。
8. 禁止用大模型常识替代来源证据。
9. 禁止新批次继续生成旧泛化关系 `RECOMMEND_CHECK`、`RECOMMEND_LAB_CHECK`、`HAS_DRUG`、`RECOMMEND_OPERATION`、`RECOMMEND_TREATMENT`。

## 14. 与解析 SKILL 的关系

本文件定义“图谱应该长什么样”。《AI自动化工具-文献指南解析.md》定义“如何从教材、指南、CDSS字典和外部权威来源生成这些数据”。执行时以本 Schema 为验收标准，以 SKILL 为流程标准，两者版本必须同步记录在大版本变更记录中。
