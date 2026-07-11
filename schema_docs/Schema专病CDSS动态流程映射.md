# Schema专病CDSS动态流程映射

> 从主Schema迁出，供产品、后端、Trae 前端理解专病流程引擎。

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
