# BATCH-CARD-LAB-DDIMER-20260714-001 D-二聚体检验指标证据补齐

## 目的

补齐共享检验项目“D-二聚体”的指标和非空原文证据，解决全库质量体检中 2 条 `required_lab_without_indicator_or_evidence` 缺口。

## 处理边界

- 本批次只补 D-二聚体 LabTest 的指标和证据链。
- 不删除急性心包炎或 VTE 既有关联。
- 急性心包炎中的 D-二聚体用于“肺栓塞鉴别场景”，不是急性心包炎本身的确诊指标。
- 发现 `DIS-CARD-VTE` 存在大量历史串段污染，另列专项 VTE 骨架重建，不混入本批次。

## 文件

- `delta_nodes_upsert.jsonl`：新增/更新 3 个 ExamIndicator。
- `delta_relations_add.jsonl`：新增 LabTest->Indicator、LabTest/Indicator->Evidence 关系。
- `delta_audit_summary.json`：审计摘要。
- `neo4j_import_summary.json`：导入摘要。
- `neo4j_postcheck_summary.json`：导入后硬闸门复核。
