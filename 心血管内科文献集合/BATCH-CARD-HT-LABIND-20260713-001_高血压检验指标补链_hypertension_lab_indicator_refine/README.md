# BATCH-CARD-HT-LABIND-20260713-001 高血压检验指标补链

生成时间：2026-07-13 23:21:02

## 本批次做什么

- 对高血压相关疾病中 51 条 `requires_lab_test` 缺指标问题进行补链。
- 不按疾病重复造指标，而是按 7 个 LabTest 统一建立 `lab_test_has_indicator`。
- 对 3 条已有关系原文证据的血培养老骨架缺口，转为 Evidence 节点并补 `血培养结果` 指标。
- 对 2 条 D-二聚体空证据缺口不硬补，记录在 `blocked_lab_evidence_gaps.csv`。

## 文件

- `delta_nodes_upsert.jsonl`：待 upsert 节点。
- `delta_relations_add.jsonl`：待新增/替换关系。
- `delta_audit_summary.json`：本地审计摘要。
- `blocked_lab_evidence_gaps.csv`：无法安全自动补齐的阻断项。
