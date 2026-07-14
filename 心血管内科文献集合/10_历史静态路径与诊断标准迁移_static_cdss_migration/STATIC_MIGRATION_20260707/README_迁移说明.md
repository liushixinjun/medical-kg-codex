# 历史静态路径与诊断标准迁移包

本包用于把存量图谱中尚未满足动态 CDSS 使用要求的两类内容迁移到可执行结构：

1. 诊断标准标题节点：补 `has_diagnostic_component -> ClinicalRule`。
2. 历史静态 ClinicalPathway：补 `has_pathway_stage -> PathwayStage`、`has_stage_rule -> ClinicalRule`，并尽量挂接既有诊断标准、治疗方案、随访和风险分层节点。

## 统计

- 节点：342
- 关系：1744
- 诊断标准迁移：31
- 静态路径迁移：51
- 未映射静态路径：0

## 导入文件

- `delta_nodes_upsert.jsonl`
- `delta_relations_add.jsonl`
- `static_pathway_stage_matrix.csv`
- `diagnosis_criteria_component_matrix.csv`
