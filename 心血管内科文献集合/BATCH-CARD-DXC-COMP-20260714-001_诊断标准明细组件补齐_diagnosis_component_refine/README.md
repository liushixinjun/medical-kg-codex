# BATCH-CARD-DXC-COMP-20260714-001 诊断标准明细组件补齐

生成时间：2026-07-14 07:19:25

## 处理边界

- 对已挂非空 Evidence、但没有 `has_diagnostic_component` 的 `DiagnosisCriteria`，生成一个“原文诊断依据组件”。
- 对没有非空 Evidence 的诊断标准不自动补，写入 blocker。
- 本批先解决前端下钻和空壳审计；不把原文进一步拆成阈值规则，阈值规则后续按专病精修。

## 结果

- 新增组件节点：18
- 新增关系：36
- 阻断行：6
