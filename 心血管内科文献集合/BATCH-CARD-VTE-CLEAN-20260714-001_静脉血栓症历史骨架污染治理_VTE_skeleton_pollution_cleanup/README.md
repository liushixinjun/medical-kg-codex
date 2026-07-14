# BATCH-CARD-VTE-CLEAN-20260714-001｜静脉血栓症历史骨架污染治理

执行时间：2026-07-14 08:53:44

## 治理结论

- 已写入 Neo4j：是。
- 删除对象：只删除 `静脉血栓症(DIS-CARD-VTE)` 指向错误实体/错误证据的关系，不删除任何节点。
- 删除关系总数：350 条。
- 删除前 VTE 出边：844 条。
- 删除后 VTE 出边：494 条。
- 保守保留待重建：5 条。

## 删除构成

| 类型 | 删除数 |
|---|---:|
| Etiology | 2 |
| Sign | 1 |
| Symptom | 2 |
| TreatmentPlan | 1 |
| Complication | 3 |
| LabTest | 4 |
| Evidence | 329 |
| Medication | 7 |
| Procedure | 1 |


## Postcheck

| 检查项 | 结果 |
|---|---:|
| VTE 已删除关系残留 | 0 |
| VTE 剩余 Evidence 语义不含 VTE/PTE/DVT | 0 |
| VTE 专项闸门 | 通过 |
| 全库正式 CDSS 硬闸门 | 通过 |
| 非 KGNode 节点 | 0 |
| 正式推荐缺核心链路 | 0 |
| 重复语义关系 | 0 |

## 暂不删除、后续重建的 5 条

- `has_symptom` → 水肿感：水肿感：DVT下肢症状可能相关，需规范为下肢肿胀/水肿
- `may_cause_complication` → 心力衰竭：心力衰竭：PTE右心衰可能相关，需改为右心衰/急性右心衰并补证据
- `requires_exam` → 磁共振成像：磁共振成像：可能作为特殊影像补充，需确认具体VTE场景
- `requires_lab_test` → 肾功能：肾功能：抗凝用药/造影前评估可能相关，需补证据与场景关系
- `requires_lab_test` → 脑钠肽：脑钠肽：PTE右心负荷/风险分层可能相关，需补VTE证据后重建


## 历史宽口径提示

- 原始宽口径仍发现 `DiagnosisCriteria` 无组件：12 条。
- 原始宽口径仍发现 `DifferentialDiagnosis` 无明细：148 条。
- 这些主要是早期房颤、室上速、传导阻滞、高血压批次把 ECG 特征项/候选展示项误标为诊断标准或鉴别诊断；不属于本轮 VTE 污染清理失败条件，后续进入历史节点类型治理。

## 关键文件

- `vte_outgoing_relation_audit.csv`：清理前审计明细。
- `delete_candidates_high_confidence.jsonl`：初始高置信污染候选。
- `delete_candidates_to_apply.jsonl`：实际执行删除清单。
- `manual_review_keep_temporarily.jsonl`：保守保留清单。
- `neo4j_cleanup_summary.json`：写库摘要。
- `neo4j_postcheck_summary.json`：服务器复核结果。
