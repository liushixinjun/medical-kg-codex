# BATCH-CARD-RS-GAP-20260714-002

用途：补齐 RecommendationStatement 候选推荐的证据/动作核心链路。

- 高血压推荐：将已有 `derived_from -> Evidence` 同步补为 `supported_by_evidence -> Evidence`。
- STEMI 溶栓阻断推荐：补 `recommends_action -> STEMI溶栓禁忌阻断规则`。
- 不做：不把教材证据伪装成 guideline；两条教材来源 STEMI 推荐在调整后审计口径下不算缺 guideline。

结果：原始全量缺口 53 → 2；调整后合理审计缺口 51 → 0。
