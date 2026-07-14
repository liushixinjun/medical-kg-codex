# 教材骨架锚点矩阵说明

生成时间：2026-07-08 08:49:28

本目录用于修复“教材骨架 definition/description 跨章节污染”和“definition 为空”的问题。

## 文件说明

| 文件 | 用途 |
|---|---|
| `textbook_cardiology_chapter_outline_20260708.csv` | 《内科学（第10版）》心血管内科章节目录和可识别槽位。 |
| `textbook_skeleton_matrix_priority_four_20260708.csv` | 冠心病、心肌病、心力衰竭、心律失常四类优先验证疾病的教材锚点矩阵。四类只是优先验证集，不是最终范围。 |
| `p0_definition_repair_input_priority_four_20260708.jsonl` | 可进入后续抽样复核/导入流程的 definition 修复输入。 |
| `summary_20260708.json` | 本轮统计摘要。 |

## 当前结论

```text
P0 疾病数：68
ready_for_import_after_sampling：25
ready_for_review：18
needs_manual_anchor_review：17
needs_guideline_or_manual_source：8
```

## 使用规则

1. `ready_for_import_after_sampling`：允许抽样复核后生成 Neo4j 更新脚本。
2. `ready_for_review`：需要复核后才能导入，特别是合并标题章节。
3. `needs_manual_anchor_review`：只说明教材正文有命中，不能直接当作 definition。
4. `needs_guideline_or_manual_source`：教材未直接覆盖或不是独立专病章节，需要指南或其他权威来源补充。

## 禁止事项

- 禁止把关键词命中直接写入 `Disease.definition`。
- 禁止把合并标题拆成单病种精确定义直接入库。
- 禁止把跨章节、筛查背景、鉴别诊断中的疾病提及当作目标疾病定义。
- 禁止四类验证未通过前扩展到心血管内科全量疾病。
