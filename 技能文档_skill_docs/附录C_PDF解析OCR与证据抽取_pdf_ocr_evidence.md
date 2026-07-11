# 附录C：PDF解析、OCR与证据抽取

更新时间：2026-07-11 23:55:00

## 1. 解析顺序

1. 建立来源清单并去重。
2. 判断文本型 PDF、扫描型 PDF、混合型 PDF。
3. 逐页抽取正文、表格、图注、推荐语和页码。
4. 对 OCR 低质量页建立阻断清单。
5. 生成 Evidence、Guideline、RecommendationStatement。

## 2. Evidence 是什么

Evidence 是“可追溯原文证据片段”，不是指南文件本身，也不是疾病级说明池。

医生看到某条推荐时，只展示该推荐直接绑定的 Evidence：

| 字段 | 示例 |
|---|---|
| 指南名称 | 2024 急性冠脉综合征指南 |
| 页码/段落 | 第 12 页，第 3 段 |
| 推荐等级 | I 类推荐 |
| 证据等级 | A 级证据 |
| 原文摘要 | 对符合条件的 STEMI 患者优先再灌注治疗 |

## 3. RecommendationStatement 是什么

RecommendationStatement 是“CDSS 推荐陈述实体”。它连接：

```text
患者满足规则 -> RecommendationStatement -> 推荐动作 -> 支持证据
```

禁止医生界面直接展示疾病级全部 Evidence 池。

## 4. OCR 阻断

以下情况必须进入 OCR 阻断清单：

- 页码缺失或错乱。
- 表格无法还原推荐等级/证据等级。
- 推荐语截断。
- 药物剂量、阈值、禁忌条件无法确认。
- 图片或扫描页未识别但被当成空白页。
