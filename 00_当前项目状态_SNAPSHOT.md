# 当前项目状态 SNAPSHOT

更新时间：2026-07-14 08:53:44

## 当前阶段

心血管内科知识图谱进入服务器端质量治理阶段。本轮已优先处理 VTE 历史骨架污染。

## 已完成内容

- VTE 历史污染关系治理批次：`BATCH-CARD-VTE-CLEAN-20260714-001`。
- 已写入 Neo4j：是。
- 删除关系：350 条，仅删除 `DIS-CARD-VTE` 出边关系，不删除节点。
- VTE 出边：844 → 494。
- VTE 专项闸门：通过。
- 全库正式 CDSS 硬闸门：通过。

## 当前核心问题

1. VTE 已清除高置信污染，但 5 条临床可能相关项需要后续按原文证据重建，不应直接删除。
2. 历史宽口径仍有 12 个早期诊断特征项误分型、148 个早期鉴别展示项无明细；这是历史节点类型治理任务，不是 VTE 清理失败。
3. 后续批次必须强制校验证据正文疾病语义主体，不能只依赖 Evidence 生成名称。

## 关键文件入口

- VTE 批次目录：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\BATCH-CARD-VTE-CLEAN-20260714-001_静脉血栓症历史骨架污染治理_VTE_skeleton_pollution_cleanup`
- 写库摘要：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\BATCH-CARD-VTE-CLEAN-20260714-001_静脉血栓症历史骨架污染治理_VTE_skeleton_pollution_cleanup\neo4j_cleanup_summary.json`
- 服务器复核：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\BATCH-CARD-VTE-CLEAN-20260714-001_静脉血栓症历史骨架污染治理_VTE_skeleton_pollution_cleanup\neo4j_postcheck_summary.json`
- 步骤记录：`AI自动化工具-文献指南解析步骤记录.md`
- 踩坑日志：`_全局复利与踩坑日志.md`
- 批次台账：`心血管内科文献集合\批次登记台账.md`

## 下一步唯一建议动作

提交本轮 VTE 治理到 GitHub；随后治理早期节点类型遗留问题：诊断特征项误分型、鉴别展示项无明细。

## 禁止事项

- 不得把候选/展示层节点直接标记为正式 CDSS 推荐。
- 不得只凭 Evidence 名称建立疾病证据关系。
- 不得删除目标实体节点；治理污染优先删除错误关系并保留审计记录。
