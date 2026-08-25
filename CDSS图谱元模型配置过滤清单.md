# CDSS图谱元模型配置导入对照清单

当前版本：V1.8
状态：唯一主文件
用途：用于说明专科知识图谱 Schema 进入 CDSS 图谱元模型配置时，实体类型、实体属性、实体关系分别如何映射、复用或新增。

## 0. 顶层设计与导入边界

专科图谱进入 CDSS 图谱元模型配置，不允许扫描 Neo4j 全部节点、全部关系、全部属性后直接写入；必须按“Schema 允许导入清单、`entityType` 约束、`code` 唯一键、CDSS 元模型映射”执行。

| 对象 | 导入前置约束 | 允许进入 CDSS 元模型 | 禁止进入 CDSS 元模型 |
|---|---|---|---|
| 实体类型 | 节点必须有 `entityType`，且 `entityType` 必须在 Schema 实体类型允许导入清单内 | 第 5 章和第 6 章列出的全部实体类型 | 没有 `entityType` 的节点、临时标签、解析过程节点、具体业务实例名称 |
| 实体实例 | 节点必须有 `code`、`name`，使用 `entityType + code` 作为业务唯一识别依据 | 标准业务实体数据 | 只有中文名称但没有标准 `entityType/code` 的散点数据 |
| 实体属性 | 属性必须来自 Schema 属性允许导入清单或第 7 章属性对照表 | 第 7 章列出的全部业务属性 | 批次字段、哈希字段、解析字段、迁移字段、治理字段 |
| 实体关系 | 起点和终点都必须是合规业务实体，关系必须来自 Schema 关系允许导入清单或第 8 章关系对照表 | 第 8 章列出的全部实体关系 | 治理关系、历史临时关系、未纳入对照表的关系 |

执行边界：

1. `NEO4J_NODE_CLASS` 维护“实体类型/节点分类”，不维护具体业务数据；可以新增 `Specialty`，不能把“心血管内科”写成节点分类。
2. `NEO4J_NODE_RELATION` 的 `TYPE=2` 维护“实体属性配置”；只能写入第 7 章列出的属性。
3. `NEO4J_NODE_RELATION` 的 `TYPE=1` 维护“实体关系规则配置”；只能写入第 8 章列出的关系。
4. CDSS 已有实体、属性、关系时，只做映射，不修改历史编码；CDSS 没有时，按新 Schema 标准新增。
5. 缺少 `entityType`、缺少 `code`、`entityType` 不在 Schema 允许导入清单内的数据，不进入元模型配置，先进入治理或人工确认。

禁止使用这种导入口径：

```cypher
MATCH (n)
UNWIND keys(n) AS propertyName
RETURN labels(n), propertyName
```

这会把 AI 解析字段、治理字段、展示字段、临时字段一起扫出来，导致 CDSS 图谱元模型配置页面出现大量无效实体和属性。

### 0.1 Neo4j 当前真实落库格式

当前 Neo4j 服务器采用“基础标签 + 业务标签 + 业务类型字段”的三件套结构：

```cypher
(:KGNode:Disease {
  code: "DIS-CARD-CAD-AMI",
  entityType: "Disease",
  name: "急性心肌梗死"
})
```

这不是 Oracle 表格式，也不是 JSON；这是 Neo4j 的节点模式写法。`KGNode` 和 `Disease` 是 Neo4j 标签，`code`、`entityType`、`name` 是节点属性。

| 项目 | 在库里的真实含义 | CDSS导入时怎么用 |
|---|---|---|
| `:KGNode` | 所有知识图谱节点的统一基础标签 | 作为图谱节点查询入口 |
| `:Disease` | 具体业务标签，表示疾病节点 | 对应 `NEO4J_NODE_CLASS.CLASS_CODE = Disease` |
| `entityType: "Disease"` | Schema 业务类型字段 | 作为导入过滤、接口识别和一致性校验的主依据 |
| `code` | 业务唯一编码 | 作为实体实例唯一键 |
| `name` | 医生可读名称 | 作为实体显示名称 |

当前库已只读核对：所有节点均带 `KGNode` 标签；`Disease` 标签节点 132 个；`entityType = Disease` 节点 132 个；`(:KGNode:Disease {entityType:"Disease"})` 节点 132 个；`Disease` 标签与 `entityType` 不一致数量为 0。

因此，Schema 的落库方向是正确的；需要避免的是把示例写成 `:KGNode::Disease`。两个标签连续写时只能使用一个冒号分隔：`(:KGNode:Disease {...})`。

## 1. 版本记录

| 版本 | 日期 | 变更说明 |
|---|---|---|
| V1.8 | 2026-07-29 | 统一使用“允许导入清单”表述，避免误解为禁止导入；明确允许进入 CDSS 元模型的是实体类型、业务属性和实体关系规则，不是 AI 解析治理字段。 |
| V1.7 | 2026-07-29 | 增加 Neo4j 当前真实落库格式说明，明确 `:KGNode:Disease`、`entityType`、`code` 和 CDSS 元模型映射关系；修正实体类型章节引用。 |
| V1.6 | 2026-07-29 | 去掉样例列和泛化描述；补齐 Schema 实体、属性、关系允许导入清单；将截图层级拆成节点分类配置和关系规则配置；删除不存在数据的防御性说明。 |
| V1.5 | 2026-07-29 | 前置补充顶层设计、`entityType` 约束、`code` 唯一键、Schema 允许导入清单和禁止全量扫描属性的导入边界。 |
| V1.4 | 2026-07-29 | 增加执行表，突出实体、属性、关系三类对照；明确 CDSS 没有的内容直接按新标准新增。 |
| V1.3 | 2026-07-29 | 精简为实体、属性、关系三类对照表；明确 CDSS 已有配置优先映射，CDSS 没有的按新 Schema 新增。 |
| V1.2 | 2026-07-29 | 文件名去掉日期，时间统一放入文档版本记录；补充 CDSS Oracle 元模型表读取后的执行口径。 |
| V1.1 | 2026-07-29 | 收口为唯一主文件，明确 `NEO4J_NODE_CLASS` 只写实体类型定义，`NEO4J_NODE_RELATION` 只写属性配置和实体关系规则。 |
| V1.0 | 2026-07-28 | 形成初版过滤清单，区分业务实体、业务属性、业务关系和 AI 解析治理字段。 |

## 2. 总体原则

1. CDSS 已有实体、属性、关系配置，优先映射现有 Oracle 编码，不改历史编码。
2. CDSS 没有的专科图谱实体、属性、关系，按《专科知识图谱 Schema 标准》新增。
3. `NEO4J_NODE_CLASS` 只维护节点分类，不维护具体疾病名称、具体症状名称、具体检查名称。
4. `NEO4J_NODE_RELATION` 只维护两类内容：节点属性配置、实体关系规则配置。
5. AI 解析过程字段、批次字段、哈希字段、迁移修复字段，不进入图谱元模型配置页。

## 3. CDSS Oracle 表落点

| Oracle表 | 用途 | 可以写入 | 不能写入 |
|---|---|---|---|
| `ZYCDSS.NEO4J_NODE_CLASS` | 节点分类定义 | 第 6 章和第 7 章列出的实体类型编码 | 具体疾病名称、具体专科名称、属性名、批次字段、哈希字段 |
| `ZYCDSS.NEO4J_NODE_RELATION`，`TYPE=2` | 节点属性配置 | 第 7 章列出的业务属性编码 | 批次字段、哈希字段、解析字段、治理字段 |
| `ZYCDSS.NEO4J_NODE_RELATION`，`TYPE=1` | 实体关系规则配置 | 第 8 章列出的实体关系编码 | 解析字段、治理字段、历史临时关系 |

已只读核对当前 CDSS Oracle：`NEO4J_NODE_CLASS` 共 41 行，其中有效 32 行；`NEO4J_NODE_RELATION` 共 157 行。当前 CDSS 关系编码多为历史大写编码，新增标准图谱时采用“Schema 标准名 -> CDSS 现有编码/新增编码”的映射方式。

## 4. 截图层级的落库拆解

截图中的“图谱节点标签、专科/顶层学科、疾病大类、疾病亚类”要拆成两类配置：一类是节点分类配置，写入 `NEO4J_NODE_CLASS`；另一类是图谱业务关系配置，写入 `NEO4J_NODE_RELATION TYPE=1`。

### 4.1 节点分类配置

| 页面层级名称 | Schema实体类型 | CDSS当前状态 | 写入表 | 处理方式 |
|---|---|---|---|---|
| 图谱节点标签 | `NODE` | 已有根分类 | `NEO4J_NODE_CLASS` | 复用现有根分类 |
| 专科/顶层学科 | `Specialty` | 当前缺失 | `NEO4J_NODE_CLASS` | 新增节点分类 |
| 疾病大类 | `DiseaseCategory` | 当前缺失 | `NEO4J_NODE_CLASS` | 新增节点分类 |
| 疾病亚类 | `DiseaseSubcategory` | 当前缺失 | `NEO4J_NODE_CLASS` | 新增节点分类 |
| 疾病 | `Disease` | 当前已有 | `NEO4J_NODE_CLASS` | 复用现有节点分类 |

### 4.2 关系规则配置

| 业务层级关系 | Schema关系编码 | 起点实体 | 终点实体 | 写入表 | 处理方式 |
|---|---|---|---|---|---|
| 顶层学科包含疾病大类 | `has_disease_category` | `Specialty` | `DiseaseCategory` | `NEO4J_NODE_RELATION TYPE=1` | 新增关系规则 |
| 疾病大类包含临床疾病 | `has_disease` | `DiseaseCategory` | `Disease` | `NEO4J_NODE_RELATION TYPE=1` | 新增关系规则 |
| 临床疾病包含临床分型 | `has_clinical_subtype` | `Disease` | `Disease` | `NEO4J_NODE_RELATION TYPE=1` | 新增关系规则 |
| 疾病大类包含展示分组 | `has_display_group` | `DiseaseCategory` | `DiseaseSubcategory` | `NEO4J_NODE_RELATION TYPE=1` | 新增关系规则 |
| 展示分组包含临床疾病 | `groups_disease` | `DiseaseSubcategory` | `Disease` | `NEO4J_NODE_RELATION TYPE=1` | 新增关系规则 |
| 临床疾病归入展示分组 | `classified_as` | `Disease` | `DiseaseSubcategory` | `NEO4J_NODE_RELATION TYPE=1` | 新增关系规则 |

## 5. 临床业务实体类型对照：写入节点分类

| Schema实体类型 | 中文名称 | CDSS现有元模型 | 处理方式 |
|---|---|---|---|
| `Specialty` | 顶层学科 | 无 | 新增 |
| `DiseaseCategory` | 疾病大类 | 无 | 新增 |
| `DiseaseSubcategory` | 疾病亚类/展示分组 | 无 | 新增 |
| `Disease` | 临床疾病 | `Disease / 疾病` | 复用 |
| `StandardDiagnosis` | 标准诊断 | `ICD10 / 诊断ICD-10` | 复用 |
| `Definition` | 疾病定义 | 无 | 新增 |
| `DefinitionComponent` | 定义明细 | 无 | 新增 |
| `Etiology` | 病因 | 无 | 新增 |
| `Pathophysiology` | 病理生理 | 无 | 新增 |
| `Epidemiology` | 流行病学 | 无 | 新增 |
| `Symptom` | 症状 | `Symptom / 症状` | 复用 |
| `Sign` | 体征 | 无 | 新增 |
| `RiskFactor` | 危险因素 | 无 | 新增 |
| `Complication` | 并发症 | `Complication / 并发症` | 复用 |
| `ExamPlan` | 辅助检查方案 | `EXAM_PLAN / 检查方案` | 复用 |
| `ExamItem` | 检查项目 | `Check / 检查项目` | 兼容映射 |
| `ExamObservation` | 检查发现 | `Imageology / 影像学表现` 可承接影像类发现 | 新增通用检查发现，影像表现临时兼容 |
| `LabItem` | 检验项目 | `LabCheck / 检验项目` | 兼容映射 |
| `LabSubitem` | 检验细项 | 无 | 新增 |
| `LabSpecimen` | 检验标本 | 无 | 新增 |
| `ThresholdRule` | 阈值规则 | 无 | 新增 |
| `DiagnosisCriteria` | 诊断标准 | `diagnosticCriteria` 属性、`DIAGNOSIS_RULES` 规则入口 | 短期兼容，结构化诊断标准新增 |
| `DiagnosisCriteriaComponent` | 诊断明细 | 无 | 新增 |
| `DifferentialDiagnosis` | 鉴别诊断 | 无 | 新增 |
| `RiskStratification` | 风险分层 | 无 | 新增 |
| `TreatmentPlan` | 治疗方案 | `TREATMENT_PALN / 治疗方案` | 复用现有历史编码，不改 `PALN` |
| `Medication` | 药品 | `Drug / 药品项目` | 兼容映射 |
| `Procedure` | 操作/手术 | `Operation / 手术项目` | 兼容映射 |
| `StandardProcedure` | 标准手术 | `ICD9 / 手术ICD-9` | 复用 |
| `TreatmentItem` | 治疗项目 | `Treatment / 治疗项目` | 兼容映射 |
| `FollowUp` | 随访 | 无 | 新增 |
| `Prognosis` | 预后 | 无 | 新增 |
| `Prevention` | 预防 | 无 | 新增 |
| `Contraindication` | 禁忌/排除条件 | 无 | 新增 |
| `ClinicalPathway` | 专病诊疗路径 | `PROCESS / 流程` | 兼容映射 |
| `PathwayStage` | 路径阶段 | 无 | 新增 |
| `ClinicalRule` | 临床规则 | `DIAGNOSIS_RULES`、`QUALITY_CONTROL_RULES` 可承接部分场景 | 兼容并新增专科规则 |
| `RecommendationStatement` | 推荐陈述 | 无 | 新增 |
| `PatientState` | 患者状态 | 无 | 新增 |
| `ClinicalEvent` | 临床事件 | 无 | 新增 |

## 6. 依据、审核和治理实体类型对照：按页面受控展示

| Schema实体类型 | 中文名称 | CDSS现有元模型 | 处理方式 |
|---|---|---|---|
| `Guideline` | 指南/教材/共识 | `CLINICAL_GUIDELINES / 临床指南` | 复用现有，默认在依据详情展示 |
| `SourceSection` | 来源章节 | 无 | 只作为原文定位锚点进入依据详情；孤立空壳不导入 |
| `Evidence` | 证据片段 | 无 | 进入依据详情和证据追溯，不进入普通疾病维护画布 |
| `SourceAdjudication` | 推荐来源裁决过程节点 | 无 | 禁止导入普通 CDSS 元模型；历史节点迁移到推荐陈述字段后物理删除 |

## 7. 实体属性对照：写入属性配置

| Schema属性 | 中文含义 | CDSS现有属性/字段 | 处理方式 |
|---|---|---|---|
| `name` | 名称 | `name / 名称` | 复用 |
| `code` | 编码 | `code / 代码` | 复用 |
| `entityType` | 实体类型 | 无通用业务字段 | 作为导入约束字段保留 |
| `display_name` | 显示名称 | 无通用字段 | 新增为属性 |
| `preferred_name` | 首选名称 | 无通用字段 | 新增为属性 |
| `aliases` | 别名 | `ALIAS_IS -> Alias` 或别名属性 | 兼容映射 |
| `standard_code` | 标准编码 | `icd10`、`ICD10`、`ICD9` | 按实体类型映射 |
| `coding_system` | 编码体系 | 无通用字段 | 新增为属性 |
| `description` | 描述 | `ImageologyDesc` 可承接影像描述 | 新增通用描述属性 |
| `definition_text` | 定义正文 | 无通用字段 | 新增为属性 |
| `summary` | 摘要 | 无通用字段 | 新增为属性 |
| `diagnostic_role` | 诊断作用 | 无通用字段 | 新增为属性 |
| `clinical_role` | 临床作用 | 无通用字段 | 新增为属性 |
| `is_diagnosable` | 是否可诊断 | 无通用字段 | 新增为属性 |
| `is_emr_writable` | 是否可回填病历 | 无通用字段 | 新增为属性 |
| `diagnosticCriteria` | 诊断依据说明 | `Disease.diagnosticCriteria` | 复用现有属性 |
| `spell` | 拼音 | `spell / 拼音` | 复用 |
| `spellShort` | 拼音缩写 | `spellShort / 拼音缩写` | 复用 |
| `ageLimitL` | 年龄低限制 | `ageLimitL` | 复用 |
| `ageLimitH` | 年龄高限制 | `ageLimitH` | 复用 |
| `sexLimit` | 性别限制 | `sexLimit` | 复用 |
| `trigger_condition` | 触发条件 | 无通用字段 | 新增为属性 |
| `contraindication_text` | 禁忌说明 | 无通用字段 | 新增为属性 |
| `indication_text` | 适应证说明 | 无通用字段 | 新增为属性 |
| `population_text` | 适用人群 | 无通用字段 | 新增为属性 |
| `recommendation_text` | 推荐内容 | 无通用字段 | 新增为属性 |
| `recommendation_class` | 推荐等级 | 无通用字段 | 新增为属性 |
| `evidence_level` | 证据等级 | 无通用字段 | 新增为属性 |
| `rule_type` | 规则类型 | 无通用字段 | 新增为属性 |
| `guideline_name` | 指南名称 | `guideName` 或指南实体 | 兼容映射 |
| `source_page` | 来源页码 | 无通用字段 | 只在依据详情展示 |
| `source_section` | 来源章节 | 无通用字段 | 只在依据详情展示 |
| `source_type` | 来源类型 | 无通用字段 | 只在依据/审核/治理模块展示 |
| `schema_version` | Schema版本 | 无通用字段 | 只在治理模块展示 |
| `clinical_use_status` | 临床使用状态 | 无通用字段 | 只在审核/治理模块展示 |

以下字段不进入普通图谱元模型配置页：`batch_id`、`source_hash`、`document_hash`、`parser_version`、`extraction_version`、`import_batch`、`merge_status`、`migration_status`、`repair_status`、`rollback_batch`、`created_at`、`updated_at`、`review_notes`、`provenance`、`dictionary_validation_status`。这些字段只进入后台治理、审核或导入日志。

## 8. 实体关系对照：写入关系规则

| Schema关系 | 中文关系 | 起点实体 | 终点实体 | CDSS现有关系/字段 | 处理方式 |
|---|---|---|---|---|---|
| `has_disease_category` | 包含疾病大类 | `Specialty` | `DiseaseCategory` | 无 | 新增 |
| `has_disease` | 包含临床疾病 | `DiseaseCategory` | `Disease` | 无 | 新增 |
| `has_clinical_subtype` | 包含临床分型 | `Disease` | `Disease` | 无 | 新增 |
| `has_display_group` | 有展示分组 | `DiseaseCategory` | `DiseaseSubcategory` | 无 | 新增 |
| `groups_disease` | 展示分组包含疾病 | `DiseaseSubcategory` | `Disease` | 无 | 新增 |
| `classified_as` | 归入展示分组 | `Disease` | `DiseaseSubcategory` | 无 | 新增 |
| `has_standard_diagnosis` | 对应标准诊断 | `Disease` | `StandardDiagnosis` | `Disease / HAS_ICD10 / ICD10` | 复用 |
| `has_exam_plan` | 有辅助检查方案 | `Disease` | `ExamPlan` | `Disease / DISEASE_HAS_EXAM_PLAN / EXAM_PLAN` | 复用 |
| `includes_exam_item` | 包含检查项目 | `ExamPlan` | `ExamItem` | `EXAM_PLAN / EXAM_PLAN_HAS_CHECK / Check` | 兼容映射 |
| `exam_item_has_observation` | 包含检查发现 | `ExamItem` | `ExamObservation` | 无 | 新增 |
| `includes_lab_item` | 包含检验项目 | `ExamPlan` | `LabItem` | `EXAM_PLAN / EXAM_PLAN_HAS_LABCHECK / LabCheck` | 兼容映射 |
| `lab_item_has_subitem` | 包含检验细项 | `LabItem` | `LabSubitem` | 无 | 新增 |
| `lab_item_uses_specimen` | 使用标本 | `LabItem` 或 `LabSubitem` | `LabSpecimen` | 无 | 新增 |
| `has_standard_procedure` | 对应标准手术 | `Procedure` | `StandardProcedure` | `ICD9 / 手术ICD-9` | 复用 |
| `term_has_alias` | 有别名 | `KGNode` | `Alias` | `ALIAS_IS -> Alias` | 兼容映射 |
| `has_definition` | 有定义 | `Disease` | `Definition` | 无 | 新增 |
| `has_definition_component` | 有定义明细 | `Definition` | `DefinitionComponent` | 无 | 新增 |
| `has_etiology` | 有病因 | `Disease` | `Etiology` | 无 | 新增 |
| `has_pathophysiology` | 有病理生理 | `Disease` | `Pathophysiology` | 无 | 新增 |
| `has_epidemiology` | 有流行病学 | `Disease` | `Epidemiology` | 无 | 新增 |
| `has_symptom` | 有症状 | `Disease` | `Symptom` | `Disease / HAS_SYMPTOM / Symptom` | 复用 |
| `has_sign` | 有体征 | `Disease` | `Sign` | 无 | 新增 |
| `has_risk_factor` | 有危险因素 | `Disease` | `RiskFactor` | 无 | 新增 |
| `may_cause_complication` | 可导致并发症 | `Disease` | `Complication` | `Disease / DISEASE_HAS_COMPLICATION / Complication` | 兼容映射 |
| `has_diagnostic_criteria` | 有诊断标准 | `Disease` | `DiagnosisCriteria` | `diagnosticCriteria` 属性或 `DISEASE_HAS_DIAGNOSIS_RULES` | 短期兼容，结构化关系新增 |
| `has_diagnostic_component` | 有诊断明细 | `DiagnosisCriteria` | `DiagnosisCriteriaComponent`、`Symptom`、`Sign`、`ExamObservation`、`LabSubitem`、`ThresholdRule`、`ClinicalRule` | 无 | 新增 |
| `differentiates_from` | 需要鉴别 | `Disease` | `DifferentialDiagnosis` | 无 | 新增 |
| `has_risk_stratification` | 有风险分层 | `Disease` | `RiskStratification` | 无 | 新增 |
| `has_treatment_plan` | 有治疗方案 | `Disease` | `TreatmentPlan` | `Disease / DISEASE_HAS_TREATMENT_PALN / TREATMENT_PALN` | 复用现有历史编码 |
| `includes_medication` | 包含药品 | `TreatmentPlan` | `Medication` | `Disease / HAS_DRUG / Drug` 可临时承接 | 方案到药品关系新增 |
| `includes_procedure` | 包含操作/手术 | `TreatmentPlan` | `Procedure` | `Disease / RECOMMEND_OPERATION / Operation` 可临时承接 | 方案到操作关系新增 |
| `includes_treatment_item` | 包含治疗项目 | `TreatmentPlan` | `TreatmentItem` | `Disease / RECOMMEND_TREATMENT / Treatment` 可临时承接 | 方案到治疗项目关系新增 |
| `has_follow_up` | 有随访 | `Disease` | `FollowUp` | 无 | 新增 |
| `has_prognosis` | 有预后 | `Disease` | `Prognosis` | 无 | 新增 |
| `has_prevention` | 有预防 | `Disease` | `Prevention` | 无 | 新增 |
| `has_clinical_pathway` | 有专病诊疗路径 | `Disease` | `ClinicalPathway` | `Disease / DISEASE_HAS_PROCESS / PROCESS` | 兼容映射 |
| `has_pathway_stage` | 包含阶段 | `ClinicalPathway` | `PathwayStage` | 无 | 新增 |
| `has_stage_rule` | 有阶段规则 | `PathwayStage` | `ClinicalRule` | `DIAGNOSIS_RULES`、`QUALITY_CONTROL_RULES` 可承接部分场景 | 兼容并新增专科阶段规则 |
| `stage_has_available_action` | 有可选动作 | `PathwayStage` | `Medication`、`Procedure`、`ExamItem`、`LabItem`、`TreatmentItem`、`FollowUp` | 无 | 新增 |
| `recommends_action` | 正式推荐具体项目 | `RecommendationStatement` | `Medication`、`Procedure`、`ExamItem`、`LabItem`、`TreatmentItem`、`FollowUp` | 无 | 新增 |
| `recommends_assessment` | 推荐临床评估 | `RecommendationStatement` | `DiagnosisCriteria`、`DifferentialDiagnosis`、`RiskStratification`、`RiskFactor`、`Complication`、`ExamObservation`、`LabSubitem`、`Etiology` | 无 | 新增 |
| `blocks_action` | 阻断具体项目 | `RecommendationStatement`、`Contraindication`、`ClinicalRule` | `Medication`、`Procedure`、`ExamItem`、`LabItem`、`TreatmentItem`、`FollowUp` | 无 | 新增 |
| `next_pathway_stage` | 下一阶段 | `PathwayStage` | `PathwayStage` | 无 | 新增 |
| `has_source_section` | 有来源章节 | `Guideline` | `SourceSection` | 无 | 只进依据详情，不进普通疾病维护画布 |
| `section_has_evidence` | 章节包含证据 | `SourceSection` | `Evidence` | 无 | 只进依据详情，不进普通疾病维护画布 |
| `guideline_has_evidence` | 指南包含证据 | `Guideline` | `Evidence` | 无 | 只进依据详情，不进普通疾病维护画布 |
| `supported_by_evidence` | 由证据支持 | `RecommendationStatement`、临床实体 | `Evidence` | `KGNode / supported_by_evidence / KGNode` | 保留，用于证据追溯 |
| `uses_primary_guideline` | 使用主依据 | `RecommendationStatement` | `Guideline` | 可承接到临床指南关系 | 保留，用于正式推荐主依据 |
| `supported_by_guideline` | 由指南支持 | `RecommendationStatement` | `Guideline` | 可承接到临床指南关系 | 保留，用于支持依据 |
| `has_source_adjudication` | 有推荐来源裁决 | `Disease` | `SourceAdjudication` | 无 | 历史过程关系，禁止导入，必须清理 |
| `decides_recommendation` | 形成正式推荐 | `SourceAdjudication` | `RecommendationStatement` | 无 | 历史过程关系，禁止导入，必须清理 |
| `derived_from` | 来自证据 | `SourceAdjudication` | `Evidence` | 无 | 历史过程关系，禁止导入；推荐到证据统一用 `supported_by_evidence` |

## 9. 不进入普通业务元模型的内容

| 类型 | 对象清单 | 处理方式 |
|---|---|---|
| AI解析过程字段 | `batch_id`、`parser_version`、`source_hash`、`document_hash`、`extraction_version`、`import_batch` | 不进普通图谱元模型配置页，只进治理日志 |
| 迁移修复字段 | `merge_status`、`migration_status`、`repair_status`、`rollback_batch`、`created_at`、`updated_at`、`review_notes`、`provenance`、`dictionary_validation_status` | 不进普通图谱元模型配置页 |
| 历史兼容实体 | `DiseaseClassification`、`Exam`、`LabTest`、`ExamIndicator` | 不新增使用，只进历史兼容或迁移清理 |
| 历史兼容关系 | `USES_MEDICATION`、`HAS_PROCEDURE`、`HAS_CLINICAL_MANIFESTATION`、`requires_exam_item`、`requires_lab_item` | 不新增使用，只进历史兼容或迁移清理 |
| 证据全文和来源细节 | 原文锚点、页码、证据哈希、来源冲突说明 | 不在普通元模型铺开，只在依据详情、审核页、治理页展示 |

## 10. 最终执行口径

```text
先校验 entityType。
再校验 code 和 name。
再查 CDSS 是否已有实体类型、属性配置、关系规则。
已有：映射现有 Oracle 编码，不改历史编码。
没有：按专科知识图谱 Schema 新增。
属性：写入 TYPE=2 属性配置。
关系：写入 TYPE=1 关系规则，必须是实体到实体。
AI解析字段、治理字段、迁移字段：不进入普通图谱元模型配置页。
```
