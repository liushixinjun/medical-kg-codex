# 附录E：Schema映射与CDSS决策层

更新时间：2026-07-11 23:55:00

## 1. Schema 使用原则

先查 `专科知识图谱Schema标准.md`，再抽取实体和关系。若 Schema 无法表达，登记 `schema_gap_register`，不私自扩展字段。

## 2. 诊断标准结构

诊断标准不能只有标题，必须下钻到组件：

```text
Disease -> has_diagnostic_criteria -> DiagnosisCriteria
DiagnosisCriteria -> has_diagnostic_component -> DiagnosisCriteriaComponent / ClinicalRule / Exam / LabTest / ThresholdRule
```

AMI 示例：

```text
急性心肌梗死诊断标准
  - 肌钙蛋白升高和/或动态变化
  - 缺血性胸痛症状
  - 新发 ST-T 改变或左束支传导阻滞
  - 影像学新发室壁运动异常
```

## 3. 鉴别诊断结构

鉴别诊断不是简单疾病列表，应包含：

| 内容 | 示例 |
|---|---|
| 鉴别对象 | 主动脉夹层 |
| 鉴别要点 | 撕裂样胸痛、血压双上肢不对称 |
| 排除检查 | 主动脉 CTA |
| 适用场景 | 胸痛疑似 AMI 但表现不典型 |

## 4. 阶段动作与正式推荐

| 关系 | 中文解释 | 使用场景 |
|---|---|---|
| `stage_has_available_action` | 阶段可选动作 | 专病路径编辑器中显示“这一阶段可以配置哪些动作” |
| `recommends_action` | 当前患者正式推荐动作 | 患者满足规则后，CDSS 给医生展示 |

旧名 `has_recommended_action` 不再作为新增推荐关系使用，历史数据后续迁移到 `stage_has_available_action`。

## 5. 图谱与规则引擎分工

| 内容 | 放图谱 | 放规则/流程引擎 |
|---|---|---|
| 疾病、症状、检查、药物、治疗方案、证据 | 是 | 否 |
| 诊疗阶段可用动作 | 是 | 可引用 |
| 患者实时数据触发 | 否 | 是 |
| “当前患者是否推荐某动作” | 由图谱提供知识，规则引擎判定 | 是 |
