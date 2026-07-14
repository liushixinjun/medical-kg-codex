# BATCH-CARD-HIST-TYPE-CLEAN-20260714-001｜历史节点类型治理

执行时间：2026-07-14 09:20:46

## 治理结论

本轮处理的是早期抽取阶段的实体类型污染，不是新增专病抽取。

- 已写入 Neo4j：是。
- 节点删除：0。
- 诊断标准误分型治理：12 个节点。
  - 11 个 ECG/电生理特征项：`DiagnosisCriteria` → `ExamIndicator`。
  - 1 个筛查规则：`DiagnosisCriteria` → `ClinicalRule`。
- 鉴别诊断误分型治理：134 个句子型鉴别要点。
  - `DifferentialDiagnosis` → `ClinicalRule`。
  - 160 条入边：`differentiates_from` → `has_differential_point`。
- 保留待补：14 个真实鉴别疾病/状态节点，不改类型，后续补鉴别规则。

## 写库结果

| 项目 | 数量 |
|---|---:|
| DiagnosisCriteria 候选 | 12 |
| DiagnosisCriteria 实际改型 | 12 |
| DifferentialDiagnosis 句子型候选 | 134 |
| DifferentialDiagnosis 实际改型 | 134 |
| 入边关系转换 | 160 |
| 缺失节点 | 0 |

## Postcheck

| 检查项 | 结果 |
|---|---:|
| 原始宽口径 DiagnosisCriteria 无明细 | 0 |
| 原始宽口径 DifferentialDiagnosis 无明细 | 14 |
| `differentiates_from` 指向非 DifferentialDiagnosis | 0 |
| 标签与 entityType 不一致 | 0 |
| 全库正式 CDSS 硬闸门 | 通过 |

## 保留待补的 14 个真实鉴别对象

这些是真实疾病/状态，不应该改成 ClinicalRule；后续需要补 `has_differential_point -> ClinicalRule`。

- `DDX-CARD-A4091D292E4B`｜冠状动脉痉挛｜BATCH-CARD-CAD-20260623-001
- `DDX-CARD-STEMI-BED7C76BD0A8`｜嗜铬细胞瘤｜BATCH-CARD-CAD-STEMI-20260712-001
- `DDX-CARD-STEMI-4DD215C51903`｜心绞痛｜BATCH-CARD-CAD-STEMI-20260712-001
- `DDX-CARD-A07BA907BDB0`｜心肌炎｜BATCH-CARD-CAD-STEMI-20260712-001
- `DDX-CARD-STEMI-5ED3F170AA98`｜急性肺动脉栓塞｜BATCH-CARD-CAD-STEMI-20260712-001
- `DDX-CARD-STEMI-F118C9F80AE2`｜急腹症｜BATCH-CARD-CAD-STEMI-20260712-001
- `DDX-CARD-6AB732E54DB3`｜冠心病｜BATCH-CARD-CM-20260622-001
- `DDX-CARD-645287F85899`｜瓣膜性心脏病｜BATCH-CARD-CM-20260622-001
- `DDX-CARD-887CF6C354E7`｜高血压性心脏病｜BATCH-CARD-CM-20260622-001
- `DDX-CARD-91D172B6AA3C`｜心房颤动｜BATCH-CARD-SVT-AFL-20260703-001_室上速房扑_SVT_AtrialFlutter
- `DDX-CARD-F46806C9EB37`｜房性早搏｜BATCH-CARD-SVT-AFL-20260703-001_室上速房扑_SVT_AtrialFlutter
- `DDX-CARD-CE220DDF6AA5`｜窦性心动过速｜BATCH-CARD-SVT-AFL-20260703-001_室上速房扑_SVT_AtrialFlutter
- `DDX-CARD-E6C98B4ECF84`｜癫痫｜BATCH-CARD-VA-SCD-20260704-001_室性心律失常心脏性猝死_VA_SCD
- `DDX-CARD-660433DF4D1F`｜预激综合征伴心房颤动｜BATCH-CARD-VA-SCD-20260704-001_室性心律失常心脏性猝死_VA_SCD


## 关键文件

- `diagnosis_criteria_misclassified_audit.csv`：诊断标准误分型审计。
- `differential_diagnosis_misclassified_audit.csv`：鉴别诊断误分型审计。
- `diagnosis_criteria_retype_to_apply.jsonl`：实际执行的诊断标准改型清单。
- `differential_points_retype_to_apply.jsonl`：实际执行的鉴别要点改型清单。
- `differential_targets_need_detail_blocked.jsonl`：保留待补清单。
- `neo4j_node_type_cleanup_summary.json`：写库摘要。
- `neo4j_postcheck_summary.json`：服务器复核。
