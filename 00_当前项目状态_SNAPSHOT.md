# 当前项目状态 SNAPSHOT

更新时间：2026-07-14 09:20:46

## 当前阶段

心血管内科知识图谱进入服务器端历史质量治理阶段。VTE 历史骨架污染已治理，历史节点类型误分型已治理。

## 已完成内容

- VTE 历史污染关系清理：删除关系 350 条，VTE 出边 844 → 494。
- 历史节点类型治理：`BATCH-CARD-HIST-TYPE-CLEAN-20260714-001`。
- 诊断标准误分型：12 → 0。
- 鉴别要点误分型：134 个 `DifferentialDiagnosis` → `ClinicalRule`。
- 错误关系转换：160 条 `differentiates_from` → `has_differential_point`。
- 全库正式 CDSS 硬闸门：通过。

## 当前核心问题

1. 剩余 14 个 `DifferentialDiagnosis` 是真实鉴别疾病/状态，缺少 `has_differential_point` 鉴别规则。
2. 这些不能通过改类型解决，必须基于原文 Evidence 补规则。
3. 后续新病种抽取必须区分：鉴别对象 = `DifferentialDiagnosis`；鉴别要点/排除规则 = `ClinicalRule`。

## 关键文件入口

- 历史节点类型治理批次：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\BATCH-CARD-HIST-TYPE-CLEAN-20260714-001_历史节点类型治理_historical_node_type_cleanup`
- 写库摘要：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\BATCH-CARD-HIST-TYPE-CLEAN-20260714-001_历史节点类型治理_historical_node_type_cleanup\neo4j_node_type_cleanup_summary.json`
- 服务器复核：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\BATCH-CARD-HIST-TYPE-CLEAN-20260714-001_历史节点类型治理_historical_node_type_cleanup\neo4j_postcheck_summary.json`
- 全局体检：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\00_全局质量体检_global_quality_audit\20260714_after_historical_node_type_cleanup`

## 下一步唯一建议动作

启动“鉴别规则补齐批次”，给 14 个真实鉴别对象补 `has_differential_point -> ClinicalRule`，优先 STEMI 和心肌病。

## 禁止事项

- 不得把句子型鉴别要点标为 `DifferentialDiagnosis`。
- 不得为通过硬闸门伪造空规则。
- 不得把真实鉴别疾病/状态改成规则节点。
