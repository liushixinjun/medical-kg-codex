# RecommendationStatement 推荐陈述迁移执行报告

版本：V1.1  
日期：2026-07-07 21:50:00  
状态：已写入服务器 Neo4j，并通过全库硬闸门  
执行脚本：`scripts/migrate_recommendation_statements.py`

## 1. 迁移目的

将历史结构：

```text
ClinicalRule -> recommends_action / blocks_action -> Action
ClinicalRule -> supported_by_evidence -> Evidence
```

升级为正式 CDSS 推荐证据根模型：

```text
ClinicalRule
  -> has_recommendation_statement
RecommendationStatement
  -> recommends_action / blocks_action
  -> derived_from Evidence
  -> based_on_guideline Guideline
```

迁移后，前端不再从“疾病证据池”或“动作证据池”二次推理推荐依据，而是直接读取 `RecommendationStatement`。

## 2. 本次迁移范围

本次迁移对象为服务器 Neo4j 中所有满足以下条件的关系：

```text
ClinicalRule -> recommends_action / blocks_action / has_recommended_action -> Action
且 ClinicalRule -> supported_by_evidence -> Evidence
```

无证据链的历史静态展示关系不迁移为正式 CDSS 推荐。

## 3. 写库结果

```text
候选规则-动作关系：291
生成 RecommendationStatement：291
未迁移候选：0
无动作 RecommendationStatement：0
无证据 RecommendationStatement：0
无指南匹配 RecommendationStatement：0
重复推荐三元组：0
同类型同名重复：0
```

专项校验文件：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\_migration_20260707_recommendation_statement\recommendation_statement_postfix_validation.json
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\_migration_20260707_recommendation_statement\cdss_recommendation_statement_matrix.csv
```

## 4. 全库硬闸门结果

最终硬闸门输出目录：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\_server_safety_after_recommendation_statement_20260707_final
```

最终结果：

```text
kg_node_count：35035
kg_relation_count：104312
non_kgnode_node_count：0
relation_touching_non_kgnode_count：0
technical_display_name_error_count：0
treatment_plan_actionability_error_count：0
medication_class_without_specific_count：0
duplicate_type_name_count：0
duplicate_semantic_relation_count：0
semantic_shell_relation_count：0
blocking_issue_count：0
global_safety_gate_status：passed
```

## 5. 修复过的问题

初次迁移后出现 31 组 `RecommendationStatement` 同类型同名重复，原因是显示名只写成“抗凝治疗推荐”“溶栓治疗推荐”等动作级名称。

已根治为：

```text
规则或阶段上下文｜动作名（动作类型）推荐/阻断
```

示例：

```text
STEMI再灌注策略选择规则｜溶栓治疗（治疗方案）推荐
STEMI溶栓禁忌阻断规则｜溶栓治疗（操作/手术）阻断
```

这个规则已同步进 `AI自动化工具-文献指南解析.md` V1.42 和 `Trae前端开发全局提示词.md` V1.0。

## 6. 前端使用入口

Trae/前端后续统一读取：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\Trae前端开发全局提示词.md
```

旧的局部提示词文件已移除，避免后续误读。
