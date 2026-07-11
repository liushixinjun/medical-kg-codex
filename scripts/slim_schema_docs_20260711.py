from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "专科知识图谱Schema标准.md"
OUT_DIR = ROOT / "schema_docs"


def section(lines: list[str], start_heading: str, end_heading: str | None = None) -> str:
    start = next(i for i, line in enumerate(lines) if line.startswith(start_heading))
    if end_heading:
        end = next(i for i, line in enumerate(lines) if i > start and line.startswith(end_heading))
    else:
        end = len(lines)
    return "\n".join(lines[start:end]).strip() + "\n"


def main() -> None:
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    OUT_DIR.mkdir(exist_ok=True)

    archive = OUT_DIR / "专科知识图谱Schema标准_完整归档_V1.13_20260711.md"
    archive.write_text(text, encoding="utf-8")

    change = "\n".join(lines[7:35]).strip() + "\n"
    (OUT_DIR / "Schema历史变更记录.md").write_text(
        "# Schema历史变更记录\n\n> 从主Schema迁出。主Schema只保留当前执行标准。\n\n" + change,
        encoding="utf-8",
    )

    (OUT_DIR / "Schema字段字典与证据规则.md").write_text(
        "# Schema字段字典与证据规则\n\n"
        "> 从主Schema迁出，保留字段细则、Evidence、Guideline、RecommendationStatement 和 provenance 规则。\n\n"
        + section(lines, "## 5.")
        + "\n"
        + section(lines, "## 8.")
        + "\n"
        + section(lines, "## 9.")
        + "\n"
        + section(lines, "## 10."),
        encoding="utf-8",
    )

    (OUT_DIR / "Schema关系兼容与禁用清单.md").write_text(
        """# Schema关系兼容与禁用清单

更新时间：2026-07-11 09:08:00

## 禁用旧关系

| 旧关系 | 状态 | 处理规则 |
|---|---|---|
| `USES_MEDICATION` | 已从服务器清零 | 禁止新批次生成；不得作为用药推荐查询 |
| `HAS_PROCEDURE` | 已从服务器清零 | 禁止新批次生成；不得作为治疗/手术推荐查询 |
| `HAS_CLINICAL_MANIFESTATION` | 已从服务器清零 | 禁止新批次生成；临床表现必须拆为 `has_symptom` / `has_sign` 或诊断组件 |
| `HAS_*` 大写历史关系 | 已从服务器清零 | 新批次统一小写 snake_case |
| `has_differential_diagnosis` | 已迁移 | 使用 `differentiates_from` |

## 关系命名待优化

| 当前关系 | 当前语义 | 问题 | 建议新名 | 数据迁移状态 |
|---|---|---|---|---|
| `has_recommended_action` | `PathwayStage -> Action`，阶段可选/候选动作 | 名字像正式推荐，容易和 `recommends_action` 混淆 | `stage_has_available_action` | 待专项迁移 |
| `recommends_action` | `ClinicalRule/RecommendationStatement -> Action`，患者规则触发后的正式推荐 | 保留 | 保留 | 已在用 |
| `blocks_action` | `ClinicalRule/RecommendationStatement -> Action`，患者规则触发后的阻断/禁忌 | 保留 | 保留 | 已在用 |

## 多学科战略保留实体

`Specialty` 是多学科顶层根节点。即使当前只有 1 个，也不得作为低频冗余删除。
""",
        encoding="utf-8",
    )

    (OUT_DIR / "Schema专病CDSS动态流程映射.md").write_text(
        "# Schema专病CDSS动态流程映射\n\n> 从主Schema迁出，供产品、后端、Trae 前端理解专病流程引擎。\n\n"
        + section(lines, "## 19."),
        encoding="utf-8",
    )

    slim = """# 专科知识图谱 Schema 标准

版本：V1.14  
状态：正式执行标准  
更新时间：2026-07-11 09:08:00  
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

### 3.1 目录与疾病

| entityType | 中文名 | 用途 |
|---|---|---|
| `Specialty` | 专科/顶层学科 | 多学科根节点；如心血管内科、呼吸内科、神经内科 |
| `DiseaseCategory` | 疾病大类 | 如冠心病、心肌病、心律失常 |
| `DiseaseSubcategory` | 疾病亚类 | 大类下分组，可选 |
| `Disease` | 疾病/专病 | CDSS和知识图谱核心对象 |
| `DiseaseClassification` | 疾病分型/分类 | 新批次标准分类实体 |

### 3.2 医学事实层

| entityType | 中文名 | 用途 |
|---|---|---|
| `Definition` | 疾病定义 | 疾病概念总述 |
| `DefinitionComponent` | 定义明细 | 定义拆解要点 |
| `Etiology` | 病因 | 疾病发生原因 |
| `Pathophysiology` | 病理生理 | 发病机制和病理过程 |
| `Epidemiology` | 流行病学 | 发病率、人群、地区等 |
| `Symptom` | 症状 | 患者主观感受 |
| `Sign` | 体征 | 医生客观发现 |
| `RiskFactor` | 危险因素 | 增加患病或不良结局风险的因素 |
| `Complication` | 并发症 | 疾病导致的并发问题 |
| `Exam` | 检查 | 影像、心电、超声等检查 |
| `LabTest` | 检验 | 血液、生化、标志物等检验 |
| `ExamIndicator` | 检查/检验指标 | 结构化指标或数值项 |
| `ThresholdRule` | 阈值规则 | 指标阈值、动态变化、阳性/阴性条件 |
| `DiagnosisCriteria` | 诊断标准 | 诊断标准标题/规则集合 |
| `DiagnosisCriteriaComponent` | 诊断标准明细 | 诊断标准下可推理组件 |
| `DifferentialDiagnosis` | 鉴别诊断 | 需要排除或区分的疾病/状态 |
| `RiskStratification` | 风险分层 | GRACE、CHA2DS2-VASc 等 |
| `TreatmentPlan` | 治疗方案 | 治疗策略、路径或方案对象 |
| `Medication` | 药物 | 药物类别或具体药品 |
| `Procedure` | 操作/手术 | 介入、手术、器械、操作 |
| `FollowUp` | 随访 | 复诊、监测、长期管理 |
| `Prognosis` | 预后 | 结局、复发、死亡风险等 |
| `Prevention` | 预防 | 一级/二级预防、生活方式、患者教育 |
| `Contraindication` | 禁忌/排除条件 | 禁忌证、排除条件、阻断推荐原因 |

### 3.3 来源、证据与CDSS决策层

| entityType | 中文名 | 用途 |
|---|---|---|
| `Guideline` | 指南/教材/共识来源 | 来源文献对象 |
| `SourceSection` | 来源章节 | 章节、页码、小标题锚点 |
| `Evidence` | 循证证据片段 | 原文证据、页码、段落、哈希 |
| `ClinicalPathway` | 专病诊疗路径 | 一组诊疗阶段的路径 |
| `PathwayStage` | 路径阶段 | 疑似识别、确诊、分层、治疗、随访等阶段 |
| `ClinicalRule` | 临床规则 | 触发、适用、排除、禁忌、阈值逻辑 |
| `RecommendationStatement` | 推荐陈述 | CDSS推荐卡片根实体，连接动作、证据和指南 |
| `PatientState` | 患者状态 | 妊娠、肾功能不全、老年、急性期等 |
| `ClinicalEvent` | 临床事件 | 复发、急性发作、猝死、再住院等 |

## 4. 标准关系

### 4.1 目录关系

| 源 | 关系 | 目标 | 说明 |
|---|---|---|---|
| `Specialty` | `has_category` | `DiseaseCategory` | 专科包含疾病大类 |
| `DiseaseCategory` | `has_subcategory` | `DiseaseSubcategory` | 大类包含亚类 |
| `DiseaseCategory` | `has_disease` | `Disease` | 大类直接包含疾病 |
| `DiseaseSubcategory` | `has_disease` | `Disease` | 亚类包含疾病 |
| `Disease` | `has_classification` | `DiseaseClassification` | 疾病分型/分类 |

### 4.2 医学事实关系

| 源 | 关系 | 目标 |
|---|---|---|
| `Disease` | `has_definition` | `Definition` |
| `Definition` | `has_definition_component` | `DefinitionComponent` |
| `Disease` | `has_etiology` | `Etiology` |
| `Disease` | `has_pathophysiology` | `Pathophysiology` |
| `Disease` | `has_epidemiology` | `Epidemiology` |
| `Disease` | `has_symptom` | `Symptom` |
| `Disease` | `has_sign` | `Sign` |
| `Disease` | `has_risk_factor` | `RiskFactor` |
| `Disease` | `may_cause_complication` | `Complication` |
| `Disease` | `requires_exam` | `Exam` |
| `Disease` | `requires_lab_test` | `LabTest` |
| `Exam` | `exam_has_indicator` | `ExamIndicator` |
| `LabTest` | `lab_test_has_indicator` | `ExamIndicator` |
| `Disease` | `has_diagnostic_criteria` | `DiagnosisCriteria` |
| `DiagnosisCriteria` | `has_diagnostic_component` | `DiagnosisCriteriaComponent/ClinicalRule/Exam/LabTest/ExamIndicator/Symptom/Sign/ThresholdRule` |
| `Disease` | `differentiates_from` | `DifferentialDiagnosis` |
| `Disease` | `has_risk_stratification` | `RiskStratification` |

### 4.3 治疗、管理与CDSS关系

| 源 | 关系 | 目标 | 说明 |
|---|---|---|---|
| `Disease` | `has_treatment_plan` | `TreatmentPlan` | 疾病治疗方案 |
| `TreatmentPlan` | `includes_medication` | `Medication` | 方案包含药物 |
| `TreatmentPlan` | `includes_procedure` | `Procedure` | 方案包含操作/手术 |
| `Disease` | `treated_by_medication` | `Medication` | 疾病直接治疗药物事实 |
| `Disease` | `treated_by_procedure` | `Procedure` | 疾病直接操作/手术事实 |
| `Medication` | `has_specific_medication` | `Medication` | 药物类别到具体药物 |
| `Disease` | `has_follow_up` | `FollowUp` | 随访管理 |
| `Disease` | `has_prognosis` | `Prognosis` | 预后 |
| `Disease` | `has_prevention` | `Prevention` | 预防措施 |
| `Disease` | `has_clinical_pathway` | `ClinicalPathway` | 疾病关联专病路径 |
| `ClinicalPathway` | `has_pathway_stage` | `PathwayStage` | 路径包含阶段 |
| `PathwayStage` | `has_stage_rule` | `ClinicalRule` | 阶段包含触发规则 |
| `PathwayStage` | `has_recommended_action` | Action | 阶段候选动作；旧命名，后续建议迁移为 `stage_has_available_action` |
| `ClinicalRule` | `has_recommendation_statement` | `RecommendationStatement` | 规则输出推荐陈述 |
| `ClinicalRule/RecommendationStatement` | `recommends_action` | Action | 患者规则触发后的正式推荐动作 |
| `ClinicalRule/RecommendationStatement` | `blocks_action` | Action | 患者规则触发后的阻断/禁忌动作 |
| `PathwayStage` | `next_pathway_stage` | `PathwayStage` | 阶段流转 |

`has_recommended_action` 与 `recommends_action` 不得混用。前者是阶段候选动作，后者是患者满足规则后的正式推荐。下一轮数据治理建议将前者改名为 `stage_has_available_action`。

### 4.4 来源与证据关系

| 源 | 关系 | 目标 |
|---|---|---|
| `Guideline` | `has_source_section` | `SourceSection` |
| `SourceSection` | `section_has_evidence` | `Evidence` |
| `Guideline` | `guideline_has_evidence` | `Evidence` |
| 任意临床实体 | `supported_by_evidence` | `Evidence` |
| `RecommendationStatement` | `based_on_guideline` | `Guideline` |
| `RecommendationStatement` | `derived_from` | `Evidence` |

## 5. 字段概要

### 5.1 节点必填字段

| 字段 | 说明 |
|---|---|
| `code` | 全局唯一业务编码 |
| `entityType` | 实体类型，必须来自本Schema |
| `name` | 标准名称 |
| `aliases` | 别名数组 |
| `source_type` | 来源类型 |
| `batch_id` | 批次编号 |
| `schema_version` | Schema版本 |
| `clinical_use_status` | 临床使用状态 |

### 5.2 关系必填字段

| 字段 | 说明 |
|---|---|
| `id` | 关系技术ID |
| `source_code` | 起点实体code |
| `relationType` | 标准关系名 |
| `target_code` | 终点实体code |
| `batch_id` | 批次编号 |
| `schema_version` | Schema版本 |
| `review_status` | 审核状态 |
| `clinical_review_status` | 临床审核状态；正式推荐必填 |

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

| 项目 | 状态 | 下一步 |
|---|---|---|
| `USES_MEDICATION` | 已清零 | 禁止再生成 |
| `HAS_PROCEDURE` | 已清零 | 禁止再生成 |
| `HAS_CLINICAL_MANIFESTATION` | 已清零 | 禁止再生成 |
| `HAS_*` 大写关系 | 已清零 | 禁止再生成 |
| `has_recommended_action` | 在用但名称不清晰 | 评估迁移为 `stage_has_available_action` |
| `Specialty` | 战略保留 | 多学科根节点，禁止低频删除 |
"""
    SCHEMA_PATH.write_text(slim, encoding="utf-8")

    print("archive", archive, round(archive.stat().st_size / 1024, 1), "KB")
    print("schema_slim", SCHEMA_PATH, round(SCHEMA_PATH.stat().st_size / 1024, 1), "KB")
    print("schema_docs", [p.name for p in sorted(OUT_DIR.glob("*.md"))])


if __name__ == "__main__":
    main()
