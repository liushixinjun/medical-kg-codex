# Schema关系兼容与禁用清单

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
