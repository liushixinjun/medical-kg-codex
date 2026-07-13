# BATCH-CARD-RS-CORELINK-20260714-001 推荐陈述核心链路补齐

生成时间：2026-07-14 07:16:37

## 处理边界

本批只补“属性中已有 code，且目标节点存在”的安全关系：

- `RecommendationStatement.primary_evidence_code -> Evidence`：生成 `supported_by_evidence`
- `RecommendationStatement.action_code -> 动作节点`：生成 `recommends_action`

不做的事情：

- 不根据文本猜证据。
- 不跨疾病复用证据。
- 不凭空补指南节点或动作节点。

## 结果

- 待导入关系：293
- 其中 supported_by_evidence：291
- 其中 recommends_action：2
- 阻断项：53
