## 2026-07-11 23:31:11｜项目治理第一轮：归档、入口、规则覆盖矩阵与校验报告

### 用户提出的问题

用户确认开始执行最终治理方案，要求先解决 SKILL、日志、项目入口和长期运行机制问题，同时明确：

1. `心血管内科文献集合/` 暂不移动、不重命名、不拆分。
2. 新目录不能使用纯英文名称。
3. 项目要可迁移、可软件化管理，不能只靠 Codex 记忆。
4. 历史版本必须保留并纳入 GitHub 版本管理。

### 判断结论

本轮必须先做“可逆治理”，不能直接重写主 SKILL，也不能动大型批次产物目录。正确顺序是：先归档与 hash 固化，再建立项目管理入口，再建立 SKILL 规则迁移覆盖矩阵，最后生成校验报告。

### 执行方案

1. 建立 `治理归档_governance_archive/20260711_SKILL与日志治理/`，归档 9 个关键治理文件并生成 SHA256。
2. 建立 `项目管理中心_project_management/`，形成项目地图、运行清单、关键文件索引、目录索引、迁移复制清单和软件化数据字典。
3. 建立 `技能文档_skill_docs/`，生成 `SKILL规则迁移覆盖矩阵_rule_mapping_20260711.csv`。
4. 生成第一轮治理校验报告 MD 与 JSON。

### 执行结果

```text
归档文件：9
SHA256记录：9
项目管理中心文件：12
SKILL规则覆盖矩阵：40条
P0/P1规则未指定新位置：0
数据库写入：否
Neo4j连接：否
心血管内科文献集合：只登记，不移动、不重命名、不拆分、不提交
```

### 遗留阻断

无业务阻断。下一轮才能执行主 SKILL 瘦身、附录拆分、日志按月归档和错误指纹索引固化。

### 关联踩坑日志

本轮属于治理机制建设，暂不新增错误指纹；后续第二轮将把“日志过大、重复规则、上下文压缩后难接续”纳入错误指纹库。

---


用途：记录每个工作日/每轮用户提示后的问题、处理方案、执行结果和后续状态。
定位：本文件记录“执行过程”；`_全局复利与踩坑日志.md` 记录“事故根因与复用规则”。两者必须互相对得上。

## 记录规则

1. 每天或每轮关键提示后，必须新增一条记录；自 2026-07-09 起，新记录写在历史记录最前面。
2. 每条记录必须包含：用户提出的问题、判断结论、执行方案、执行结果、遗留阻断、关联踩坑日志。
3. 若本轮发现可复用错误或流程漏洞，必须同步写入 `_全局复利与踩坑日志.md`；若只是普通执行进展，则只写本文件。
4. 记录时间必须精确到秒，格式为 `YYYY-MM-DD HH:mm:ss`。
5. 新病种启动前，先读取本文件最近记录和 `_全局复利与踩坑日志.md` 相关规则，作为执行依据。

---

---

## 2026-07-11 17:06:21｜Schema V1.15 主文档格式与可读性治理

### 用户提出的问题

用户指出 `专科知识图谱Schema标准.md` 标题和内容参差不齐，表格英文过多，复杂关系难以理解，尤其是：

1. `DiagnosisCriteria | has_diagnostic_component | DiagnosisCriteriaComponent/ClinicalRule/Exam/LabTest/ExamIndicator/Symptom/Sign/ThresholdRule` 太长，无法看懂。
2. `has_recommended_action` 与 `recommends_action` 虽有解释，但仍难区分。
3. `任意临床实体 | supported_by_evidence | Evidence` 中英混杂，业务含义不清。
4. Evidence 节点数量很多，但 Evidence 到底代表什么仍不清楚。

### 判断结论

问题不是图谱数据库缺数据，而是 Schema 主文档表达方式仍偏程序字段，未达到“临床、产品、前端、后端都能读懂”的标准。主 Schema 需要中文优先、英文技术名辅助，并在复杂关系处放最小临床案例。

### 执行方案

1. 将 Schema 升级到 V1.15。
2. 3章实体类型改为“中文名、技术名、临床含义”。
3. 4章关系改为“起点、业务关系、relationType、终点、使用边界”。
4. 对诊断标准明细、阶段候选动作/正式推荐动作、Evidence 证据片段补充中文解释和示例。
5. 用户补充指出“技术名 entityType”不准确，已统一改为“实体类型 entityType”；关系表同步改为“关系类型 relationType”。
6. 用户补充指出 §5 字段概要缺少格式要求，已补 `code`、`id`、`aliases`、状态、版本、时间、证据文本字段格式，并给出节点/关系 JSON 示例。
7. 用户补充指出 `draft/review_ready/clinical_ready/blocked`、`pending/clinical_ready/blocked/not_required` 看不懂，已补 §5.4 状态字段说明，区分节点临床使用状态、关系结构审核状态、关系临床审核状态。
8. 用户补充建议全部表格参考第 5 章，最后加一列示例，示例统一用 AMI 内容；已将 Schema 全部表格统一补 AMI 示例列，涉及具体值的字段补格式要求、正确示例和禁止写法。
9. 同步更新 SKILL、Trae 全局提示词、交接文件和踩坑日志。

### 执行结果

```text
Schema：专科知识图谱Schema标准.md V1.15
SKILL：AI自动化工具-文献指南解析.md V1.47
Trae提示词：Trae前端开发全局提示词.md V1.4
数据库写入：无
```

### 遗留阻断

无数据库阻断。本轮是文档治理，不涉及服务器图谱迁移。

### 关联踩坑日志

`2026-07-11 17:06:21 | Schema标准、前端/后端协作、临床阅读成本`

---

---

## 2026-07-11 00:18:00｜Schema V1.12 结构治理与 9.2–9.5 可读性修复

### 用户提出的问题

用户要求按下一步执行 Schema 优化，并指出 §9.2、§9.3、§9.4、§9.5 完全看不懂；同时追问 §7.7 也是证据关系，如何与 §9.2–§9.5 区分。

### 判断结论

问题成立。§7.7 和 §9.2–§9.5 原本都在讲“证据”，但层级不同：§7.7 是关系层，定义证据链怎么连接；§9.2–§9.5 是字段层，定义 Evidence、教材来源、RecommendationStatement 和教材骨架字段里具体存什么。此前文档没有把这个边界讲清楚，且实际库已出现教材骨架拆解实体，但 Schema 未正式收编。

### 执行结果

```text
Schema：V1.11 -> V1.12
解析 SKILL：V1.44 -> V1.45
审计脚本：已收编 V1.12 新实体和小写新关系
单元测试：tests.test_audit_graph_instance 16 项 OK
Neo4j：未写入，未迁移服务器数据
```

新增/更新内容：

- 收编 `Definition`、`DefinitionComponent`、`DiagnosisCriteriaComponent`、`Prevention`、`SourceSection`。
- 明确 `DiseaseClassification` 新批次优先，`ClassificationStage` 作为历史兼容。
- §7.7 增加“关系层 vs 字段层”说明。
- §9.2–§9.5 改为白话解释、字段表、示例和硬规则。
- 新批次禁止生成 `HAS_*` 大写历史关系，统一小写 snake_case。
- 新增兼容迁移表和字段统一规则。

### 关联文件

```text
专科知识图谱Schema标准.md
AI自动化工具-文献指南解析.md
scripts/audit_graph_instance.py
tests/test_audit_graph_instance.py
Schema实体关系兼容迁移表_20260711.csv
Schema字段统一规则_20260711.md
docs/superpowers/plans/2026-07-11-schema-v1.12-governance.md
```

### 遗留阻断

本次未执行服务器迁移。后续若要处理历史数据，必须先做 dry-run，重点包括：

```text
TextbookSection -> SourceSection
HAS_* 大写关系 -> 小写标准关系
knowledge_layer=textbook_skeleton -> textbook_core
definition_skeleton_slot -> skeleton_slot 补齐
ClinicalManifestation -> Symptom/Sign/SourceSection
```

### 关联踩坑日志

已新增“Schema 关系层和字段层必须分开讲；实际已入库实体必须及时收编或标记 legacy”的复用规则。

---

---

## 2026-07-10 23:42:10｜高血压批次 G1 通过并已导入服务器，单个历史节点不阻断全局进度

### 用户提出的问题

用户要求继续高效推进，不要因为一个节点数据影响全局进度。

### 判断结论

高血压批次自身已经闭环：本地 G1 质量门禁 passed，AI 预审核签收完成，已导入 `192.168.3.27` Neo4j 测试库，并完成服务器批次级复核。服务器复核发现的 1 个“诊断标准无明细”节点不属于高血压批次，而属于历史缓慢性心律失常/传导阻滞批次，应进入全局遗留队列，不能阻断高血压批次和后续疾病大类推进。

### 执行方案

1. 修正审计规则：允许新版 CDSS 决策链关系与 `PathwayStage` 实体类型，并支持 `pathway_applicability_profile.json` 区分“适用缺失”和“疾病本身不适用”。
2. 修复高血压批次：补齐真实 required 槽位、ClinicalPathway、PathwayStage、ClinicalRule、RecommendationStatement、药物别名和证据链字段。
3. 本地审计通过后执行 AI 预审核签收，再导入 Neo4j。
4. 服务器复核只区分“本批次问题”和“全局历史遗留问题”，避免单点阻断全局。

### 执行结果

```text
本地测试：23 项 OK
高血压本地 G1：passed
本地节点/关系：3355 / 17956
高血压疾病数：15
closed_loop_ready 疾病数：15
RecommendationStatement：50
ClinicalPathway：15
AI 预审核签收关系：155
Neo4j 导入：节点 3355/3355，关系 17956/17956
服务器全库节点/关系：43020 / 140183
服务器全库 KGNode/关系：43020 / 140183
服务器疾病大类/疾病：34 / 115
高血压批次服务器节点/关系：3355 / 17956
高血压批次服务器疾病：15
高血压批次 RecommendationStatement：50
高血压批次 ClinicalPathway：15
```

服务器硬闸门结果：

```text
非 KGNode=0
重复或缺失 code 分组=0
空壳节点=0
RecommendationStatement 缺证据=0
RecommendationStatement 缺动作=0
formal_ready 直接正式推荐=0
```

### 遗留阻断

不阻断当前批次的全局遗留项：

```text
节点：DX-CARD-5F28B989F353
名称：心电图传导阻滞诊断依据
批次：BATCH-CARD-BRADY-AVB-20260705-001_缓慢性心律失常传导阻滞_Bradyarrhythmia_AVBlock
问题：DiagnosisCriteria 无 has_diagnostic_component 明细
处置：进入全局遗留队列，后续按缓慢性心律失常批次单独修复；不阻断高血压批次。
```

### 关联踩坑日志

已新增“批次门禁与全局遗留项必须分账”的规则：当前批次通过不应被其他历史批次单个节点阻断；但遗留项必须登记到交接与踩坑日志，后续按所属批次修复。

---

---

## 2026-07-10 16:31:26｜服务器网络恢复与实时全库复核

### 用户提出的问题

用户截图证明 `192.168.3.27` 持续 ping 正常，指出网络没有问题。

### 判断结论

用户判断正确。重新检测后 7474/7687 均可达；此前“无活动路由”只是检测时的瞬时状态。后续两次认证失败分别由连接文件编码读取和正则转义/字段行号解析错误引起，不是数据库账号或密码错误。

### 执行结果

```text
服务器节点=39706
服务器关系=122237
KGNode=39706
疾病大类=33
疾病=100
非KGNode=0
RecommendationStatement缺动作/证据/指南=0/0/0
高血压本批次服务器节点=0
```

当前全库基础治理项：同类型同名重复组13、疾病定义空值32、诊断标准无明细4、路径无阶段9、治疗方案无下游动作46。

### 遗留阻断

高血压仍为本地批次，G1 未通过且未导入。下一步需修正病种适用性审计，再补真正缺失证据与 CDSS 决策层。

### 关联踩坑日志

已新增“网络/数据库连接必须分层复核，连接文件不得按固定行号和不稳定正则解析”的复用规则。

---

---

## 2026-07-10 11:04:27｜本周专科知识图谱升级改造成果统计

### 用户提出的问题

要求统计本周专科知识图谱升级改造内容和成果。

### 判断结论

按 2026-07-06 至 2026-07-10 统计，必须区分服务器已入库、本地已完成未入库、历史审计快照和实时数据库数据；高血压本地成果不得计入服务器总量。

### 执行结果

已生成：`专科知识图谱升级改造周报_20260706-20260710.md`。

核心统计：

```text
Schema：V1.8 -> V1.11
解析 SKILL：V1.36 -> V1.44
教材骨架两批次：3129 节点、7754 关系、1269 Evidence，均已入库并通过批次复核
优先疾病 definition：68/68 已补齐
历史 RecommendationStatement 迁移：291
诊断标准明细迁移：31/31
历史静态路径迁移：51/51
7 个专病 CDSS 决策层：61 条批次疾病范围、60 个去重疾病名、712 个决策层节点、6426 条关系，全部通过批次硬闸门
高血压本地批次：16 份资料、1721 页、3105 条证据、3167 节点、17377 关系；G1 未通过，未导入
```

### 遗留阻断

本次统计时服务器连接不可达；全库实时总量未伪造，周报分别记录最后一次全库审计快照和后续批次导入回执推算。高血压 required 缺口 30、CDSS 推荐字段缺口 155，需修复后重新审计。

### 关联踩坑日志

无新增事故；沿用“服务器快照、导入回执、本地候选不得混算”和“未实时复核不得宣称当前服务器最终值”规则。

---

---

## 2026-07-10 07:45:00｜高血压疾病大类批次启动与本地 G1 审计

### 用户提出的问题

要求直接启动“高血压疾病大类”解析批次。

### 判断结论

1. 高血压资料来源充足，可作为冠心病、心肌病、心衰、心律失常之后的下一个疾病大类批次。
2. 现有批次准备脚本缺少高血压/HT 别名，直接使用会漏掉 `HT ACC/ESC/AHA` 等资料，因此本轮新增通用 G0 准备脚本，按 batch_config 显式纳入范围。
3. 高血压首批不应纳入护理患者教育 DOCX 和“左室辅助装置患者高血压”特殊场景声明，已作为污染项排除。
4. 本批次当前只完成到本地图谱实例与 G1 审计；因 required 槽位和 CDSS 推荐字段仍有缺口，暂不导入 Neo4j。

### 执行方案

```text
1. 新增通用 G0 批次准备脚本：scripts/kg_pipeline_g0_prepare_batch.py
2. 新增高血压 batch_config：心血管内科文献集合/BATCH-CARD-HT-20260709-001_高血压_Hypertension.batch_config.yaml
3. G0 生成批次目录、source manifest、scope_taxonomy、controlled_vocabulary。
4. PDF 解析：parse_pdf_batch.py。
5. 证据抽取：extract_guideline_evidence.py。
6. 图谱实例构建：build_graph_instance.py。
7. 本地语义修复：repair_graph_semantic_quality.py。
8. 本地质量审计：audit_graph_instance.py。
```

### 执行结果

```text
批次目录：心血管内科文献集合/BATCH-CARD-HT-20260709-001_高血压_Hypertension
最终纳入资料：16 份
排除污染资料：4 份
PDF 页数：1721
OCR 阻断页：0
证据条数：3105
覆盖疾病/亚型：15/15
本地节点：3167
本地关系：17377
治疗方案空壳：0
药物类别缺具体药物：0
target-match 失败：0
核心关系证据链完整率：100%
```

新增/更新文件：

```text
scripts/kg_pipeline_g0_prepare_batch.py
scripts/extract_guideline_evidence.py
scripts/repair_graph_semantic_quality.py
心血管内科文献集合/BATCH-CARD-HT-20260709-001_高血压_Hypertension.batch_config.yaml
心血管内科文献集合/高血压文献来源清单.md
心血管内科文献集合/高血压文献来源清单.csv
心血管内科文献集合/BATCH-CARD-HT-20260709-001_高血压_Hypertension/06_quality_audit/高血压批次本地审计报告_20260710.md
```

### 遗留阻断

```text
G1 质量门禁：failed
required 槽位缺口：30
CDSS 推荐字段缺口：155
closed_loop_ready 疾病数：4/15
Neo4j 导入：未执行
正式 CDSS 推荐层：不允许
```

下一步：补高血压专用抽取规则与 CDSS 决策层，特别是诊断阈值、继发性高血压病因、血压测量表型、靶器官损害、急症/亚急症判断、推荐适用人群和禁忌/排除条件。

### 关联踩坑日志

已同步记录：

```text
1. PDF 抽取乱码/C1 控制字符会破坏 JSONL，必须在证据抽取阶段过滤。
2. “××治疗方案 -> ××治疗路径”属于泛化补丁节点，不得自动生成。
3. 治疗方案动作关系必须找到直接提到目标药物/措施的证据，否则不得生成。
4. 血压测量表型疾病需要区分“不适用槽位”和“抽取缺失”，不能硬造症状。
```

---

## 2026-07-09 22:45:00｜Trae 图谱探索页面设计与数据问题分析

### 用户提出的问题

要求分析 Trae 开发的网站 `http://192.168.3.27:4001/explore.html`，判断页面设计和数据使用问题。

### 判断结论

1. 当前页面已经接入 `RecommendationStatement` 推荐卡片，但主体仍是“疾病静态实体浏览页”，不是完整“专病 CDSS 流程页”。
2. AMI 动态 CDSS 推荐数据在 Neo4j 中存在，但 API 对 `pathway_name/stage_name/rule_name/primary_source_name/primary_evidence_summary` 等字段映射不完整。
3. 页面把动态 CDSS 路径、历史静态路径、诊断标准迁移推荐混在一起展示，容易误导前端和临床使用。

### 执行结果

```text
新增分析目录：心血管内科文献集合/99_Trae前端页面分析_20260709
下载页面文件：explore.html、app.js
新增报告：Trae图谱探索页面设计与数据问题分析_20260709.md
```

### 关联踩坑日志

本轮属于前端/API 对接问题，复用既有规则：CDSS 展示必须以 `RecommendationStatement` 为根，推荐动作必须同时处理 `recommends_action` 与 `blocks_action`。

---

## 2026-07-09 22:20:00｜心血管内科 CDSS 决策层总览与 Trae 对接报告

### 用户提出的问题

要求按下一步计划执行：生成“心血管内科 CDSS 决策层总览与 Trae 对接报告”，让 Trae/前端/后端明确图谱如何被专科 CDSS 使用，而不是只看 Schema 和数据库连接。

### 判断结论

1. 报告必须从服务器 Neo4j 实际数据生成，不能只用本地估算。
2. 前端展示必须以 `RecommendationStatement` 为推荐根节点，不能从疾病证据池或动作证据池反推证据。
3. 查询推荐动作时必须同时包含 `recommends_action` 和 `blocks_action`，否则会把禁忌/阻断类推荐误判成“缺动作”。

### 执行结果

```text
新增报告：心血管内科CDSS决策层总览与Trae对接报告_20260709.md
服务器统计 JSON：心血管内科文献集合/99_CDSS决策层批量升级_summary_20260709_from_server.json
覆盖范围：冠心病、心肌病、心力衰竭、房颤、室上速/房扑、室性心律失常/心脏性猝死、缓慢性心律失常/传导阻滞
内容：现状总览、CDSS 正确链路、前端页面建议、后端接口建议、Cypher 模板、EMR/规则引擎组合、禁止误用规则、推荐卡片样例。
```

### 关联踩坑日志

已同步记录“CDSS 查询动作口径必须包含 recommends_action 与 blocks_action”。

---

## 2026-07-09 22:06:42｜剩余已解析批次 CDSS 决策层连续升级完成

### 用户提出的问题

要求在冠心病、心肌病之后，按照已解析 PDF 批次顺序，把剩余疾病大类全部执行完；同时保证服务器图谱数据库同步、硬闸门复核通过，并保持任务交接记录最新内容在最前。

### 判断结论

1. 剩余已解析批次按现有台账顺序升级：心力衰竭、房颤、室上速/房扑、室性心律失常/心脏性猝死、缓慢性心律失常/传导阻滞。
2. CDSS 决策层继续采用已验证模型：`Disease -> ClinicalPathway -> PathwayStage -> ClinicalRule -> RecommendationStatement -> Action/Evidence/Guideline`。
3. 服务器导入前必须检查关系端点。若推荐关系引用的原始事实节点服务器缺失，只允许补齐依赖节点，不补旧批次关系网，避免悬空关系。

### 执行方案

```text
通用脚本：scripts/build_remaining_cdss_recommendation_deltas.py
升级批次：
1. BATCH-CARD-HF-CDSS-20260709-001
2. BATCH-CARD-AF-CDSS-20260709-001
3. BATCH-CARD-SVT-AFL-CDSS-20260709-001
4. BATCH-CARD-VA-SCD-CDSS-20260709-001
5. BATCH-CARD-BRADY-AVB-CDSS-20260709-001
导入方式：Neo4j 幂等 MERGE；不删除旧关系；端点缺失时仅补齐依赖节点。
```

### 执行结果

```text
心力衰竭：ClinicalPathway=11，PathwayStage=44，ClinicalRule=44，RecommendationStatement=44，关系=1110，服务器复核 passed
房颤：ClinicalPathway=1，PathwayStage=4，ClinicalRule=4，RecommendationStatement=4，关系=162，依赖节点补齐=4，服务器复核 passed
室上速/房扑：ClinicalPathway=6，PathwayStage=24，ClinicalRule=24，RecommendationStatement=24，关系=912，依赖节点补齐=2，服务器复核 passed
室性心律失常/心脏性猝死：ClinicalPathway=12，PathwayStage=48，ClinicalRule=48，RecommendationStatement=48，关系=1749，服务器复核 passed
缓慢性心律失常/传导阻滞：ClinicalPathway=9，PathwayStage=36，ClinicalRule=36，RecommendationStatement=36，关系=804，依赖节点补齐=1，服务器复核 passed
```

服务器硬闸门均为 0：

```text
非 KGNode 节点、路径缺阶段、阶段缺规则、规则缺推荐陈述、推荐缺动作、推荐缺证据、推荐缺指南、推荐展示字段缺失、阶段与治疗方案同名、批次内重复语义关系、formal_cdss_ready=true。
```

### 遗留阻断

无批次级阻断。当前 7 个已解析疾病大类均已具备测试推荐层 CDSS 决策链；仍不等于正式上线，正式上线需结合前端专病流程引擎、真实患者字段触发和临床使用效果签收。

### 关联踩坑日志

已同步记录“CDSS 决策层批量导入必须先做端点依赖检查，缺失原始事实节点只补依赖节点，不补旧关系网”。

---

## 2026-07-09 21:11:01｜心肌病 CDSS 决策层升级与记录文件最新在前

### 用户提出的问题

1. 执行心肌病 CDSS 决策层升级。
2. 要求步骤记录、踩坑日志、交接文件、批次登记台账后续按日期“最新内容放最前面”，方便阅读。

### 判断结论

1. 心肌病应复用冠心病已验证通过的 CDSS 决策层模型：`ClinicalPathway -> PathwayStage -> ClinicalRule -> RecommendationStatement -> Evidence/Guideline/Action`。
2. 本次只新增心肌病 CDSS 决策层 delta，不覆盖旧心肌病事实层。
3. 日志/台账维护方式从“尾部追加”调整为“顶部插入最新记录”。

### 已执行方案

```text
来源批次：BATCH-CARD-CM-20260622-001
新增批次：BATCH-CARD-CM-CDSS-20260709-001
输出目录：心血管内科文献集合/BATCH-CARD-CM-CDSS-20260709-001_心肌病_CDSS决策层升级
脚本：scripts/build_cm_cdss_recommendation_delta.py
```

### 执行结果

```text
ClinicalPathway：12
PathwayStage：28
ClinicalRule：30
RecommendationStatement：30
关系：825
覆盖疾病：12
Neo4j写入：是
服务器批次级复核：passed
```

服务器批次硬闸门：

```text
recommendation_without_evidence：0
recommendation_without_action_or_block：0
recommendation_without_guideline：0
recommendation_missing_display_fields：0
clinical_rule_without_recommendation_statement：0
stage_without_rule：0
pathway_without_stage：0
stage_treatment_plan_same_name：0
duplicate_blocked_action_names：0
```

### 关键质量处理

```text
缺血性心肌病两条推荐的主证据已锚定到《缺血性心肌病血运重建专家共识》，避免默认落到 PCI 指南。
禁忌/阻断类推荐仍按 blocks_action 复核，不误判为缺动作。
推荐展示字段以 RecommendationStatement 为根，医生端不展示疾病级证据池。
```

### 关键产物

```text
心血管内科文献集合/BATCH-CARD-CM-CDSS-20260709-001_心肌病_CDSS决策层升级/01_delta/delta_nodes_upsert.jsonl
心血管内科文献集合/BATCH-CARD-CM-CDSS-20260709-001_心肌病_CDSS决策层升级/01_delta/delta_relations_add.jsonl
心血管内科文献集合/BATCH-CARD-CM-CDSS-20260709-001_心肌病_CDSS决策层升级/02_audit/cdss_recommendation_statement_matrix.csv
心血管内科文献集合/BATCH-CARD-CM-CDSS-20260709-001_心肌病_CDSS决策层升级/04_import/neo4j_batch_postcheck_summary.json
```

### 遗留阻断

```text
本批次心肌病 CDSS 决策层无批次级阻断。
全库历史旧问题仍需按批次逐步迁移到 RecommendationStatement 模型后再判定正式 CDSS 上线。
```

### 关联踩坑日志

```text
2026-07-09 21:11:01｜心肌病 CDSS 决策层证据锚定与日志最新在前规则
```

---

---

## 2026-07-08 07:47:46｜教材骨架槽位与知识层级规则落地

### 用户提出的问题

1. 确认可以按下一步建议开始执行。
2. 要求补充：不是只修冠心病、心肌病、心力衰竭、心律失常四类；四类只是优先验证范围，验证没问题后应自行扩大到其他心血管内科疾病。

### 判断结论

1. 先落地 Schema/SKILL 硬规则，再执行图谱数据修复，避免继续用旧标准生成或修复。
2. 四类优先是工程验证策略，不是业务范围收缩；规则验证通过后应自动扩展到心血管内科教材全部疾病大类。
3. 本轮只更新规则文档和评估报告，不直接改服务器图谱数据。

### 已执行方案

1. `专科知识图谱Schema标准.md` 升级至 V1.11：
   - 新增 `skeleton_slot` 教材骨架槽位。
   - 新增 `knowledge_layer` 知识层级。
   - 新增 `source_section_path`、`pdf_page_start/pdf_page_end`、`book_page_start/book_page_end`、`text_anchor`。
   - 新增教材骨架章节锚点规则和硬闸门。
   - 明确四类优先验证后自动扩展到全部心血管内科教材疾病。
2. `AI自动化工具-文献指南解析.md` 升级至 V1.44：
   - 同步 Schema V1.11。
   - 新增 DOCX+PDF 双源校验流程。
   - 新增教材骨架槽位与知识层级抽取规则。
   - 新增四类优先验证和自动扩展规则。
   - 新增教材骨架矩阵和章节污染审计交付要求。
3. 更新评估报告：
   `心血管内科文献集合/心血管内科教材骨架质量评估_冠心病心肌病心衰心律失常_20260707.md`

### 当前执行结果

已完成规则层落地。下一步可进入实际数据修复：

```text
第一批：冠心病、心肌病、心力衰竭、心律失常
验证通过后：自动扩展到高血压、瓣膜病、心包疾病、感染性心内膜炎、先心病、主动脉和周围血管病等全部心血管内科教材疾病
```

已生成只读 P0 审计清单：

```text
心血管内科文献集合/99_教材骨架质量审计_textbook_skeleton_audit/20260708_074929/priority_four_p0_textbook_skeleton_audit.csv
```

审计摘要：

```text
disease_count = 68
p0_count = 68
definition_empty_count = 68
description_no_self_anchor_count = 1
description_other_disease_anchor_count = 43
known_pollution_keyword_count = 14
```

说明：`known_pollution_keyword_count` 是提示字段，不等于全部错误；例如关键词命中本疾病自身定义时可判为合理。后续修复以“章节锚点 + definition 是否来自目标疾病概述段”为准。

### 遗留阻断

服务器图谱尚未修复；当前只是修复执行标准。下一步必须生成四类 P0 修复清单和 delta，再导入服务器并跑硬闸门。

### 关联踩坑日志

延续 2026-07-07 23:35:00 条目：教材章节锚点缺失导致 definition/description 污染。本轮已把复用规则同步进入 Schema V1.11 和 SKILL V1.44。

---

## 2026-07-07 23:35:00｜心血管内科教材骨架质量评估

### 用户提出的问题

1. 要求回到《内科学》第10版教材骨架，评估基础内容是否真实进入图谱。
2. 优先比对冠心病、心肌病、心力衰竭、心律失常四个大类。
3. 要同时读取 PDF 原文交叉校验，避免 DOCX 转换导致目录或正文偏差。
4. 要反查 Schema 骨架是否存在缺失或不合理之处，并给出精确论证。

### 判断结论

1. DOCX 与 PDF 原文章节结构一致，可以采用“DOCX 抽目录、PDF 校页码和原文”的双源校验策略。
2. 教材确实基本覆盖临床基础诊疗框架，适合作为“专科骨架”；指南 PDF 应作为“决策血肉”，补推荐等级、证据等级、时间窗、禁忌证和精细方案。
3. 当前图谱还不能判定为教材骨架完成。问题不是数量不足，而是章节锚点、骨架槽位和定义强校验不足。
4. 服务器抽查发现四类重点疾病 `definition` 全为空，且部分 `description` 已被跨章节错误段落污染，如 UA 命中呼吸康复、AMI 命中窦性停搏、ACS 命中心衰段落。
5. Schema 主体方向正确，但需要补充教材骨架专用字段和硬闸门：`skeleton_slot`、`knowledge_layer`、页码范围、章节路径、definition 源文一致性校验。

### 已执行方案

1. 读取《内科学（第10版）》DOCX，定位四类章节：
   - 心力衰竭：DOCX 3905-4228；PDF 第 207 页；书内第 176 页。
   - 心律失常：DOCX 4229-4889；PDF 第 221 页；书内第 190 页。
   - 冠心病：DOCX 4890-5478；PDF 第 258 页；书内第 227 页。
   - 心肌病：DOCX 5739-6066；PDF 第 306 页；书内第 275 页。
2. 用 PDF 原文校验四类章节标题和页码，确认 PDF 可直接抽文字，不是 OCR 阻断。
3. 查询服务器 Neo4j 四类疾病 `definition/description` 状态，抽查污染样例。
4. 生成评估报告：
   `心血管内科文献集合/心血管内科教材骨架质量评估_冠心病心肌病心衰心律失常_20260707.md`

### 当前执行结果

关键发现：

```text
冠状动脉粥样硬化性心脏病：疾病数 10，definition 为空 10
心肌病：疾病数 12，definition 为空 12
心力衰竭：疾病数 11，definition 为空 11
心律失常：疾病数 29，definition 为空 29
心脏骤停与心脏性猝死：疾病数 2，definition 为空 2
```

已确认的污染样例：

```text
不稳定型心绞痛 description -> 呼吸康复段落
急性心肌梗死 description -> 窦性停搏段落
急性冠脉综合征 description -> 急性心力衰竭段落
缺血性心肌病 description -> 非扩张型左心室心肌病段落
陈旧性心肌梗死 description -> 心脏骤停段落
心房颤动 description -> HCM/心室充盈受限段落
右心衰竭 description -> 限制型心肌病段落
```

### 遗留阻断

1. 不能继续把当前骨架库视为“已完成”，必须先完成四类教材骨架 P0 修复。
2. 修复前不建议继续大规模扩新病种，否则污染会复用到后续疾病。
3. 当前报告未直接修改服务器图谱，需下一轮先确认 Schema/SKILL 硬规则，再执行四类骨架修复 delta。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：2026-07-07 23:35:00｜教材章节锚点缺失导致 definition/description 污染。

---

## 2026-07-01 10:24:43～房颤 AF 批次解析、修复、导入与服务器去重

### 用户提出的问题

用户确认下一步开始“房颤 AF”批次。

### 判断结论

1. 房颤适合做下一批：指南充足，且能检验抗凝、节律控制、心室率控制、风险评分、药物具体化和跨病种合并质量。
2. 启动前必须先补齐 AF scope aliases、`scope_taxonomy.csv` 和 `controlled_vocabulary.csv`。
3. 本批可导入测试库/知识展示层；正式 CDSS 仍不得上线，因为部分关系为 `knowledge_display`，且 `formal_cdss_ready=true` 保持 0。

### 已执行方案

1. 补充并收窄 AF scope aliases，避免漏掉 AF/AHA/ESC 文件，也避免过宽“导管消融”误纳 LVAD 心律失常材料。
2. 建立批次：`BATCH-CARD-AF-20260701-001_房颤_AtrialFibrillation`。
3. 生成并复核纳入文献清单：18 个文件。
4. 解析 PDF/DOCX，生成页级审计和 clean text。
5. 补齐 AF taxonomy 与 104 行受控词表。
6. 抽取证据、生成图谱实例。
7. 执行本地审计；修复 β受体阻滞剂类别别名、治疗方案下游实体、AF 专病治疗方案执行关系。
8. 执行 CDSS AI 预审核与专家批量签收元数据回写。
9. 导入服务器 Neo4j 测试库。
10. 导入后发现 `duplicate_type_name_count=12`，新增服务器同类型同名实体合并脚本并执行合并。
11. 复跑服务器全库安全门。

### 当前执行结果

```text
PDF 解析：
document_count = 11
page_count = 1687
page_accounting_rate = 1.0
ocr_required_page_count = 0

DOCX 解析：
document_count = 7
failed_document_count = 0
segment_count = 39260

证据抽取：
document_count = 18
document_with_evidence_count = 17
evidence_count = 1966

本地图谱：
node_count = 1787
relation_count = 8825
required_pathway_missing_count = 0
closed_loop_ready_disease_count = 1
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
duplicate_semantic_relation_count = 0
duplicate_type_name_count = 0

CDSS AI 预审核：
target_relation_count = 33
ai_prechecked_pass = 5
ai_prechecked_limited = 28
ai_prechecked_blocked = 0
clinical_review_status_set_to = clinical_batch_signed_off
formal_cdss_ready_set_true = 0

服务器导入：
input_node_count = 1787
input_relation_count = 8825
database_kg_node_count_after_import = 30719
database_relation_count_after_import = 72348

服务器同名实体合并：
duplicate_group_count = 12
deleted_nodes = 12
outgoing_transferred = 772
incoming_transferred = 22

服务器最终硬闸门：
kg_node_count = 30707
kg_relation_count = 72334
non_kgnode_node_count = 0
relation_touching_non_kgnode_count = 0
technical_display_name_error_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
duplicate_type_name_count = 0
duplicate_semantic_relation_count = 0
semantic_shell_relation_count = 0
global_safety_gate_status = passed
```

测试：

```text
python -m unittest tests.test_prepare_medical_kg_batch tests.test_preflight_new_disease_batch
5 项 OK

python -m unittest tests.test_repair_graph_semantic_quality tests.test_audit_graph_instance
17 项 OK

python -m py_compile scripts/dedupe_neo4j_type_name_nodes.py
OK
```

### 遗留阻断

1. 本批仍有 28 条 `knowledge_display` 关系，不进入正式 CDSS 强推荐。
2. 服务器已完成同名实体合并；后续如果重导本批，必须再次跑全局安全门，防止本地 batch code 与服务器 canonical code 再次形成重复。
3. `threshold_rule` 与 `differential_diagnosis` 为 optional missing，不影响本批 required 闭环，但后续可专项增强。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-07-01 10:24:43`：新病种必须先补 taxonomy/vocabulary；scope aliases 必须同时防漏纳和防误纳；累计库导入后必须清零同类型同名重复实体并迁移全部入/出边。

---

---

## 2026-07-03 11:36:27～已执行批次统计汇总与 HTML 报告生成

### 用户提出的问题

用户要求把目前已经执行的内容按学科、疾病大类、疾病进行统计汇总，覆盖资料总数、书籍和指南 PDF 数、各疾病解析利用数量、心内科骨架信息、已解析专病图谱维度统计，并新增报告统计 SKILL 文件和日期版本 HTML 报告。

### 判断结论

1. 统计报告必须脚本化生成，不能手工拼表，避免后续新增病种后口径不一致。
2. “利用数量”拆成两个口径：`纳入解析文件数` 和 `产生证据文档数`。
3. 服务器最终状态必须读取最新全局安全体检结果，不以本地 JSONL 行数替代。

### 已执行方案

1. 新增报告统计规范文件：`AI自动化工具-文献指南解析-报告统计.md`。
2. 新增统计脚本：`scripts/build_report_statistics.py`。
3. 读取以下产物汇总：
   - `source_documents_manifest.csv`
   - `quality_gate_summary.json`
   - `guideline_evidence_summary.json`
   - `nodes_final.jsonl`
   - `relations_final.jsonl`
   - `neo4j_import_summary.json`
   - 最新 `99_全局安全体检_global_safety_check/*/01_服务器全库硬闸门_summary.json`
4. 生成 HTML 报告和 JSON 数据底稿。

### 当前执行结果

```text
资料总库：
指南/文献目录总文件 = 420
指南/文献 PDF = 224
书籍教材总文件 = 3
书籍教材 PDF = 1

已统计批次：
心血管内科基础骨架库
心肌病
冠状动脉粥样硬化性心脏病（冠心病）
心力衰竭
心房颤动（房颤，AF）

服务器最终状态：
kg_node_count = 30707
kg_relation_count = 72334
global_safety_gate_status = passed
```

输出文件：

```text
AI自动化工具-文献指南解析-报告统计.md
scripts/build_report_statistics.py
AI自动化工具-文献指南解析-统计报告_20260703.html
AI自动化工具-文献指南解析-统计报告_20260703.json
```

自检结果：

```text
文件存在性检查：OK
脚本语法检查：python -m py_compile scripts/build_report_statistics.py OK
生成批次数：5
```

### 遗留阻断

无本次报告生成阻断。

### 关联踩坑日志

本次为统计报告能力建设，没有新增质量事故，未新增 `_全局复利与踩坑日志.md` 条目。

---

---

## 2026-07-03 12:00:03～23:18:42 心律失常：室上性心动过速及心房扑动批次执行

### 用户提出的问题

用户要求在统计报告完成后，继续解析：

- 顶层学科：心血管内科
- 疾病大类：心律失常
- 本批次专病：室上性心动过速及心房扑动
- 指南来源路径：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南`
- 教材路径：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\书籍教材`
- 输出路径：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合`

### 执行方案

1. 先做新病种预检和源文件筛选。
2. 生成 `scope_taxonomy.csv` 和 `controlled_vocabulary.csv`，覆盖 SVT、AVNRT、AVRT、房速、预激综合征、心房扑动。
3. 解析 PDF 和 DOCX，生成页级/段落级 clean text。
4. 抽取指南和教材证据，构建本地图谱 JSONL。
5. 本地审计后先修结构语义：治疗方案下游动作、药物类别具体化、短缩写污染。
6. 执行专家批量签收机制，但不把 AI limited 关系标记为正式 CDSS ready。
7. 导入前跑服务器全局安全检查，导入后再跑全局安全检查和同类型同名去重。

### 关键执行结果

源文件：

```text
总扫描资料：423
纳入资料：7
纳入清单：
1. SVT ESC 2019.pdf
2. 中国 抗心律失常药物临床应用中国专家共识2023.pdf
3. 室上性心动过速诊断及治疗中国专家共识(2021).pdf
4. 抗心律失常药物临床应用中国专家共识.pdf
5. 《内科学（第10版）》.docx
6. 《内科学（第10版）》.pdf
7. 内科学(第8版).docx
```

解析与抽取：

```text
PDF 解析：5 份，1136 页，页数核对率 100%，OCR 阻断 0
DOCX 解析：2 份，39151 个片段，失败 0
证据抽取：7 份资料均命中，6 个疾病/亚型，1140 条证据
```

本地图谱：

```text
节点：1254
关系：9221
疾病：6
Evidence：1105
Medication：21
TreatmentPlan：11
Procedure：7
```

本地最终审计：

```text
quality_gate_status = passed
unknown_entity_type_count = 0
wrong_relation_direction_count = 0
duplicate_code_count = 0
duplicate_type_name_count = 0
semantic_shell_node_relation_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
medication_alias_instance_gap_count = 0
cdss_recommendation_readiness_error_count = 0
core_relation_evidence_chain_rate = 1.0
target_name_or_alias_match_rate = 1.0
required_pathway_missing_count = 0
closed_loop_ready_disease_count = 6/6
```

服务器导入：

```text
导入前服务器安全检查：passed
导入节点：1254
导入关系：9221
导入后出现同类型同名重复：6 组
去重迁移出边：363
去重迁移入边：17
删除重复节点：6
最终服务器安全检查：passed
服务器 KGNode：31911
服务器关系：81520
duplicate_type_name_count = 0
duplicate_semantic_relation_count = 0
global_safety_gate_status = passed
```

### 本次发现并修复的问题

1. `AT` 不能单独作为房性心动过速锚点；`α1-AT`、`ATⅡ`、抗凝血酶 AT 等必须判为缩写污染。
2. WPW/预激综合征不能从 G6PD、补体、房颤病因段落继承病因或风险因素。
3. DOCX 教材无页码时，`source_page` 统一写 `N/A`，不能留空。
4. 未显式给出 I/IIa/A/B 等推荐等级的教材/专家共识关系，可写“未分级推荐/专家共识或教材证据”，但只能 `ai_prechecked_limited`，`formal_cdss_ready=false`。
5. 累计 Neo4j 导入后仍必须查并清零 `duplicate_type_name_count`。

### 输出文件

```text
心血管内科文献集合\BATCH-CARD-SVT-AFL-20260703-001_室上速房扑_SVT_AtrialFlutter
scripts\repair_svt_afl_batch_quality.py
scripts\repair_graph_semantic_quality.py
scripts\apply_cdss_ai_precheck_signoff.py
```

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-07-03 23:18:42`：心律失常短缩写消歧、DOCX 页码 N/A、未分级推荐 limited 处理、导入后同类型同名去重。

---

## 2026-07-04 23:00:00～2026-07-05 21:22:26 心律失常：室性心律失常及心脏性猝死批次执行

### 用户提出的问题

用户要求继续心律失常疾病大类建设，并在执行中确认全量测试是本地还是数据库验证。执行目标为：

- 顶层学科：心血管内科
- 疾病大类：心律失常
- 本批次专病：室性心律失常及心脏性猝死
- 指南来源路径：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南`
- 教材路径：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\书籍教材`
- 输出路径：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合`

### 执行方案

1. 新批次前先跑服务器全库硬闸门，确认上一批累计库安全。
2. 预检专科、疾病范围、指南路径、教材路径和输出路径。
3. 生成室性心律失常及心脏性猝死 taxonomy 与受控词表。
4. 解析 PDF 与 DOCX，构建教材骨架证据和指南证据。
5. 构建本地图谱 JSONL，执行语义修复、药物类别具体化和治疗方案可执行化。
6. 对 required 缺口执行证据反查和策展回填，但只允许使用同病种专属证据，不允许用缩略语页或混排表格硬补。
7. 本地审计通过后执行 CDSS AI 预审与专家批量签收机制。
8. 相关单测、全量单测通过后导入 Neo4j 测试库。
9. 导入后执行语义关系去重、同类型同名节点去重和服务器全局安全体检。

### 关键执行结果

源文件：

```text
纳入资料：5
1. 《内科学（第10版）》.docx
2. 《内科学（第10版）》.pdf
3. 内科学(第8版).docx
4. 室性心律失常中国专家共识基层版.pdf
5. ESC指南：室性心律失常患者的管理和心源性猝死的预防 2022.pdf
```

解析与抽取：

```text
PDF 解析：3 份，1133 页，页数核对率 100%，OCR 阻断 0
DOCX 解析：2 份，39151 个片段，失败 0
证据抽取：5 份资料均命中，12 个疾病/亚型，1979 条指南/教材证据
教材骨架证据：264 条
```

本地图谱：

```text
节点：2428
关系：17845
疾病/亚型：12
Evidence：2208
Guideline：5
DiagnosisCriteria：12
TreatmentPlan：18
Medication：15
Procedure：7
Symptom：8
Sign：7
ThresholdRule：32
```

本地最终审计：

```text
quality_gate_status = passed
required_pathway_missing_count = 0
closed_loop_ready_disease_count = 12/12
cdss_recommendation_readiness_error_count = 0
duplicate_type_name_count = 0
duplicate_semantic_relation_count = 0
technical_display_name_error_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
core_relation_evidence_chain_rate = 1.0
target_name_or_alias_match_rate = 1.0
```

服务器导入与复核：

```text
导入模式：idempotent_merge_no_delete
导入节点：2428
导入关系：17845
导入前服务器：KGNode=31911，关系=81520
导入后服务器：KGNode=34293，关系=99273
语义重复关系：0，未删除
同类型同名重复：1 组，已合并；转移出边 2、入边 3，删除重复节点 1
最终服务器：KGNode=34292，关系=99269
global_safety_gate_status = passed
blocking_issue_count = 0
```

批次级服务器统计：

```text
batch_id = BATCH-CARD-VA-SCD-20260704-001_室性心律失常心脏性猝死_VA_SCD
服务器本批次节点 = 2428
服务器本批次关系 = 17841
服务器本批次疾病 = 12
```

测试：

```text
相关单测：11 项 OK
全量单测：93 项 OK
脚本 py_compile：OK
```

统计报告：

```text
AI自动化工具-文献指南解析-统计报告_20260705.html
AI自动化工具-文献指南解析-统计报告_20260705.json
报告批次数：7
```

### 本次发现并修复的问题

1. `VT` 作为别名时会误命中 `SVT`，`VA` 会误命中 `LVAD`；已在批次准备脚本中加入短 ASCII 别名词边界匹配，并去除过宽别名。
2. required 回填初版评分误选 ESC 缩略语页、药物表或混排表格作为诊断证据；已改为 12 个缺口的专属证据规则，禁止缩略语页作为核心证据。
3. DOCX 证据 `source_page=None` 会破坏证据链完整率；已统一写 `N/A`，并补单测。
4. `钾剂` 药物类别缺少具体药物承接；已补 `氯化钾`，并补药物类别具体化规则。
5. required 回填按 code 新增节点时，曾创建“心室扑动与心室颤动诊断标准”同类型同名重复；已修 `apply_curated_required_backfill.py`，按 `entityType+name` 复用既有节点并重映射关系。
6. 两条随访关系缺 `exclusion_criteria`，导致 CDSS readiness 仍剩 2 项；已补模板和当前关系字段。

### 输出文件

```text
心血管内科文献集合\BATCH-CARD-VA-SCD-20260704-001_室性心律失常心脏性猝死_VA_SCD
心血管内科文献集合\BATCH-CARD-VA-SCD-20260704-001_室性心律失常心脏性猝死_VA_SCD\08_neo4j_import\neo4j_import_summary.json
心血管内科文献集合\BATCH-CARD-VA-SCD-20260704-001_室性心律失常心脏性猝死_VA_SCD\08_neo4j_import\global_safety_check_20260704_post_import\01_服务器全库硬闸门_summary.json
scripts\build_ventricular_arrhythmia_evidence.py
scripts\build_va_scd_required_backfill_spec.py
scripts\apply_curated_required_backfill.py
```

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-07-05 21:22:26`：室性心律失常/心脏性猝死批次，短 ASCII 别名边界、required 回填证据选择、同类型同名节点复用、CDSS 排除/禁忌字段补齐。

---

## 2026-07-06 16:56:17 专科 CDSS 产品业务设计升级

### 用户问题

1. 现有专科 CDSS 仍偏“症状推荐疑似疾病，再一次性关联查询所有检验、检查、用药、手术、鉴别”等静态知识罗列模式。
2. Oracle 只是举例，真实问题是开发同事拿到图谱 Schema 和数据库后，不知道如何基于图谱结构写专病推理语法。
3. 需要明确诊疗阶段、触发条件到底放图谱还是流程引擎。
4. 可执行路径表中的阶段1、阶段2与既有 12 个节点/维度如何区分。
5. `PathwayStage` 与 `TreatmentPlan` 是否会重名，如何防止混用。
6. 截图显示推荐鉴别只有疾病名，下一级鉴别要点、建议检查、治疗阻断逻辑缺失。
7. 用户账号 Token 可能中断，要求每次任务结束必须提供当前进度和后续计划，便于另一个账号接手。

### 判断结论

本轮标志着项目从“专科知识图谱建设”进入“临床专科 CDSS 产品业务设计”阶段。核心边界确定为：

```text
图谱：维护医学知识、诊疗阶段、条件、推荐动作、禁忌阻断和证据链
流程引擎：维护 EMR/系统事件、患者实时状态、是否触发和如何展示
前端/业务系统：展示当前阶段、推荐、缺失条件、阻断原因、证据和医生反馈
```

### 执行结果

1. `专科知识图谱Schema标准.md` 升级到 V1.8，新增专病 CDSS 动态流程应用层、`PathwayStage`、专病流程引擎映射、阶段/规则/推荐动作关系。
2. `AI自动化工具-文献指南解析.md` 升级到 V1.36，新增动态 CDSS 路径抽取目标、`cdss_executable_pathway.csv`、`cdss_rule_action_matrix.csv`、阶段与治疗方案防混淆规则、鉴别诊断下一级内容规则、任务结束交接摘要规则。
3. 新增 `专病辅助诊疗建设方案_专科CDSS六级建设.md`，统一承载总体解决方案和给开发同事的 AMI/STEMI 案例说明。
4. 补充硬规则：同一疾病/路径内 `PathwayStage.name` 不得与 `TreatmentPlan.name` 完全相同；阶段必须体现流程语义，治疗方案必须体现可执行动作语义。
5. 补充硬规则：进入 CDSS 的鉴别诊断不得只有疾病名，必须包含鉴别要点、建议排除检查/检验、治疗安全影响和证据链。
6. 补充交接规则：每次任务结束必须输出当前任务目标、完成事项、文件路径、验证情况、遗留阻断、下一步、换账号继续应读文件、日志同步状态。

### 本轮新增/修改文件

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\专科知识图谱Schema标准.md
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\AI自动化工具-文献指南解析.md
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\专病辅助诊疗建设方案_专科CDSS六级建设.md
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\AI自动化工具-文献指南解析步骤记录.md
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\_全局复利与踩坑日志.md
```

### 遗留事项

1. 需要按新规则回看 AMI、心衰、房颤、室上速、室性心律失常等已建图谱，补 `PathwayStage`、`ClinicalRule`、鉴别诊断下一级结构和可执行路径表。
2. 需要给 Trae/开发同事输出前端或接口字段约定，基于 `专病辅助诊疗建设方案_专科CDSS六级建设.md` 实现 L3/L4 专病流程展示与动态推荐。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-07-06 16:56:17`：专病 CDSS 静态知识罗列、阶段/治疗方案混用、鉴别诊断空壳、任务结束缺交接摘要。

---

## 2026-07-07 00:00:00 AMI/STEMI 动态专病 CDSS 样板补全

### 用户问题

1. 急性心肌梗死“诊断标准”节点只有标题，没有下一级诊断标准明细，前端无法判断怎么使用。
2. 鉴别诊断只列出主动脉夹层、冠状动脉痉挛、急性心包炎、肺栓塞等名称，缺少鉴别要点、排除检查和治疗安全影响。
3. 需要把硬规则同步到 Schema 和 SKILL，防止后续病种继续只生成标题节点或空壳鉴别诊断。

### 判断结论

诊断标准和鉴别诊断都不能作为“标题节点”进入专病 CDSS。诊断标准必须拆成可推理组件；鉴别诊断必须拆成鉴别要点、排除检查和治疗阻断/影响。否则前端只能展示知识，不能形成动态辅助诊疗推荐。

### 执行结果

1. `专科知识图谱Schema标准.md` 升级到 V1.9，新增 `DiagnosisCriteria -> has_diagnostic_component -> ClinicalRule/Exam/LabTest/ExamIndicator/Symptom/Sign/ThresholdRule`。
2. `AI自动化工具-文献指南解析.md` 升级到 V1.37，新增诊断标准明细组件硬规则和 `cdss_diagnosis_criteria_detail_matrix.csv` 交付要求。
3. 生成 AMI/STEMI 动态专病 CDSS 样板包：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\BATCH-CARD-CAD-20260623-001\09_专病CDSS动态路径样板_dynamic_cdss_pathway\AMI_STEMI_20260707
```

4. 样板包内容：
   - `delta_nodes_upsert.jsonl`：24 个候选节点
   - `delta_relations_add.jsonl`：137 条候选关系
   - `cdss_executable_pathway.csv`：6 个路径阶段
   - `cdss_rule_action_matrix.csv`：6 条阶段规则
   - `cdss_diagnosis_criteria_detail_matrix.csv`：9 条诊断标准明细
   - `cdss_differential_diagnosis_matrix.csv`：5 条鉴别诊断明细
   - `README_开发交接.md`：给开发同事的 Cypher 查询示例和使用说明

### 验证结果

```text
all_referenced_codes_exist_or_in_delta = true
all_evidence_ids_exist_in_local_graph = true
pathway_stage_treatment_plan_same_name_collision_count = 0
not_imported_to_neo4j = true
```

### 遗留事项

1. 本包尚未导入 Neo4j；需要先确认前端/规则引擎接受这些关系类型和展示方式。
2. 若确认导入，必须按 `KGNode.code` 合并节点，按 `(source_code, relationType, target_code)` 合并关系，并跑导入后硬闸门。
3. 需要把相同规则逐步回补到心衰、房颤、室上速、室性心律失常等已建专病。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-07-07 00:00:00`：诊断标准标题化、鉴别诊断名称化、CDSS 无法使用下级推理内容。

---

## 2026-07-07 00:00:00 AMI/STEMI 样板包融入专科 CDSS 六级建设方案

### 用户问题

AMI/STEMI 样板包虽然已生成，但如果只给一个目录，开发同事仍然看不懂它和《专病辅助诊疗建设方案_专科CDSS六级建设.md》的关系。需要把样板包作为案例直接融入方案文件。

### 执行结果

1. 将 `专病辅助诊疗建设方案_专科CDSS六级建设.md` 升级到 V1.1。
2. 同步关联标准为 `专科知识图谱Schema标准.md V1.9` 和 `AI自动化工具-文献指南解析.md V1.37`。
3. 在第 7 章 AMI/STEMI 开发案例中补充样板包目录：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\BATCH-CARD-CAD-20260623-001\09_专病CDSS动态路径样板_dynamic_cdss_pathway\AMI_STEMI_20260707
```

4. 补充样板包文件对照表：
   - `README_开发交接.md`
   - `cdss_executable_pathway.csv`
   - `cdss_rule_action_matrix.csv`
   - `cdss_diagnosis_criteria_detail_matrix.csv`
   - `cdss_differential_diagnosis_matrix.csv`
   - `delta_nodes_upsert.jsonl`
   - `delta_relations_add.jsonl`
   - `import_manifest.json`
5. 补充开发阅读顺序和样板包当前统计。
6. 新增 §7.4“诊断标准不是标题节点”，把 `cdss_diagnosis_criteria_detail_matrix.csv` 和 `DiagnosisCriteria -> has_diagnostic_component` 查询方式写入方案。

### 验证结果

已复核方案文件包含以下内容：

```text
版本：V1.1
Schema V1.9 / SKILL V1.37
AMI_STEMI_20260707
cdss_diagnosis_criteria_detail_matrix.csv
DiagnosisCriteria -has_diagnostic_component
### 7.4 诊断标准不是标题节点
```

### 关联踩坑日志

本次属于 `2026-07-07 00:00:00` 诊断标准标题化、鉴别诊断名称化问题的落地补充，不新增独立踩坑条目。

---

## 2026-07-07 15:18:58 服务器动态CDSS回补：心衰、房颤、室上速/房扑

### 用户问题

1. AMI/STEMI 动态 CDSS 样板导入后，需要按同一规则回补已建专病：心力衰竭、心房颤动、室上性心动过速及心房扑动。
2. 导入后必须跑硬闸门：非 KGNode、空壳节点、重复关系、诊断标准无明细、鉴别诊断无下级内容。
3. 同名实体重复属于基础质量问题，不能再依赖前端或人工截图发现。

### 执行结果

1. 新增复用脚本：
   - `scripts/build_dynamic_cdss_backfill.py`
2. 生成并导入三批动态 CDSS 回补包：
   - 心衰：`心血管内科文献集合/BATCH-CARD-HF-20260629-001/09_专病CDSS动态路径样板_dynamic_cdss_pathway/HF_20260707`
   - 房颤：`心血管内科文献集合/BATCH-CARD-AF-20260701-001_房颤_AtrialFibrillation/09_专病CDSS动态路径样板_dynamic_cdss_pathway/AF_20260707`
   - 室上速/房扑：`心血管内科文献集合/BATCH-CARD-SVT-AFL-20260703-001_室上速房扑_SVT_AtrialFlutter/09_专病CDSS动态路径样板_dynamic_cdss_pathway/SVT_AFL_20260707`
3. 服务器导入结果：
   - 心衰：41 节点、163 关系。
   - 房颤：22 节点、107 关系。
   - 室上速/房扑：25 节点、110 关系。
4. 修复导入后发现的同类型同名重复：
   - 问题：`DifferentialDiagnosis` 下“心房扑动”被建成 `DDX-CARD-AF-AFL` 与 `DDX-CARD-SVT-AFL` 两个节点。
   - 修复：统一为中立编码 `DDX-CARD-ARR-AFL`，重新导入 canonical 关系后删除两个旧重复节点。

### 服务器硬闸门复核

复核文件：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\09_服务器硬闸门复核_20260707_dynamic_backfill\post_dynamic_backfill_hard_gate_summary.json
```

关键结果：

```text
kg_node_count = 34402
kg_relation_count = 99784
non_kgnode_node_count = 0
relation_touching_non_kgnode_count = 0
technical_display_name_error_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
duplicate_type_name_count = 0
duplicate_semantic_relation_count = 0
semantic_shell_relation_count = 0
global_safety_gate_status = passed

target_dxc_without_component = 0
target_ddx_without_detail = 0
dynamic_pathway_without_stage = 0
stage_without_rule_or_action = 0
clinical_rule_without_evidence = 0
stage_plan_name_collision = 0
```

### 未完成/后续硬任务

1. 全库仍有 `global_dxc_without_component = 31`，集中在未按动态 CDSS 规则补齐的其他已建专病，例如室性心律失常、部分冠心病、心肌病、心脏性猝死等。它们不得进入正式动态 CDSS 推荐层。
2. 全库仍有 `pathway_without_stage_global = 51`，属于历史静态 ClinicalPathway；本轮动态路径 `dynamic_pathway_without_stage = 0`。后续需要把历史静态路径迁移为 PathwayStage + ClinicalRule，而不是前端直接当动态流程使用。
3. 后续解析新病种前，应先把本轮脚本规则并入批次生成流程：诊断标准必须拆明细、鉴别诊断必须有下级要点/排除检查、同名实体必须先查 canonical code。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-07-07 15:18:58 服务器动态CDSS回补`：同一临床概念不得按不同使用场景重复建 DDX 节点；动态路径回补后必须同时查目标专病硬闸门和全库基础安全闸门。

---

## 2026-07-07 15:47:39 全库历史静态路径与诊断标准迁移

### 用户问题

继续把全库剩余 `31` 个诊断标准缺明细和 `51` 个历史静态 `ClinicalPathway` 缺阶段按本轮动态 CDSS 规则批量迁移，优先处理冠心病、心肌病、室性心律失常/心脏性猝死。

### 执行方案

1. 从服务器实时拉取剩余缺口清单，避免使用过期本地统计。
2. 对 31 个 `DiagnosisCriteria` 生成 `has_diagnostic_component -> ClinicalRule`，每个诊断标准补 3 个组成规则。
3. 对 51 个历史静态 `ClinicalPathway` 生成 3 阶段结构：
   - 路径评估阶段
   - 治疗决策阶段
   - 随访安全阶段
4. 能找到证据链的历史路径，补 `has_stage_rule -> ClinicalRule`；找不到证据链但已有诊断/治疗/随访/风险动作锚点的历史路径，只补阶段和动作，不生成无证据 ClinicalRule。
5. 导入前按端点和语义关系预检；导入后跑全库硬闸门。

### 执行结果

新增脚本：

```text
scripts/migrate_static_cdss_gaps.py
```

迁移包目录：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\10_历史静态路径与诊断标准迁移_static_cdss_migration\STATIC_MIGRATION_20260707
```

生成内容：

```text
delta_nodes_upsert.jsonl：342 个节点
delta_relations_add.jsonl：1744 条关系
diagnosis_criteria_component_matrix.csv
static_pathway_stage_matrix.csv
README_迁移说明.md
```

迁移覆盖：

```text
diagnostic_criteria_migrated = 31 / 31
static_pathways_migrated = 51 / 51
static_pathways_unmapped = 0
```

服务器导入：

```text
merged_node_count = 342
merged_relation_count = 1744
deleted_legacy_relationship_count = 0
replace_semantic_edge_count = 0
```

### 服务器硬闸门复核

复核文件：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\10_历史静态路径与诊断标准迁移_static_cdss_migration\STATIC_MIGRATION_20260707\neo4j_post_import_quality_gate\post_static_migration_hard_gate_summary.json
```

结果：

```text
kg_node_count = 34744
kg_relation_count = 101528
global_safety_gate_status = passed

global_dxc_without_component = 0
global_pathway_without_stage = 0
stage_without_rule_or_action = 0
clinical_rule_without_evidence = 0
stage_plan_name_collision = 0
duplicate_type_name_count_now = 0
duplicate_semantic_relation_count_now = 0
```

### 后续注意

1. 历史静态路径已补阶段，但其中部分心衰/房颤/室上速旧路径没有新增 ClinicalRule，原因是它们已有新的动态路径，本次只为旧路径补阶段与动作，避免生成无证据规则。
2. 后续新病种不应再产生“静态 ClinicalPathway 无阶段”问题；生成图谱时必须直接输出 `ClinicalPathway -> PathwayStage -> ClinicalRule/Action`。
3. 下一步可转向业务可用性增强：按真实 CDSS 场景补患者输入字段、触发条件、禁忌/排除条件、推荐优先级和前端查询接口。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-07-07 15:47:39`：历史静态路径迁移不得为追求形式完整而生成无证据 ClinicalRule；没有证据链时只允许补阶段与既有动作，正式推荐仍需证据链和临床审核。

---

## 2026-07-07 15:52:50 专科CDSS业务可用性增强方案补充

### 用户问题

下一步进入“CDSS业务可用性增强”，需要明确具体怎么做，并主要体现在 `专病辅助诊疗建设方案_专科CDSS六级建设.md` 里面。

### 执行结果

已将方案文件升级为 V1.2：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\专病辅助诊疗建设方案_专科CDSS六级建设.md
```

新增第 9 章：

```text
CDSS业务可用性增强落地设计
```

新增内容包括：

1. 患者事实字段标准化：`CDSS_PATIENT_FACT_VIEW` / `CDSS_PATIENT_FACT`。
2. 图谱规则与患者字段映射：`required_patient_data`、`match_conditions`、`block_conditions`、`recommendation_priority`。
3. 触发条件边界：医学触发条件放图谱，系统事件触发放流程引擎/Oracle配置。
4. 前端接口建议：`POST /cdss/specialty/evaluate`。
5. 前端页面改造：从疾病邻居节点列表改为当前阶段、已满足条件、缺失项、推荐动作、阻断动作、证据、医生反馈。
6. Oracle/EMR 中间表建议：`CDSS_PATIENT_FACT`、`CDSS_EVALUATION_RESULT`、`CDSS_RECOMMENDATION_ITEM`、`CDSS_DOCTOR_FEEDBACK`、`CDSS_RULE_EXECUTION_LOG`。
7. AMI/STEMI 先做 5 个业务闭环场景：急性胸痛初筛、诊断确认、再灌注决策、溶栓安全阻断、出院二级预防。

### 校验结果

已校验方案包含以下关键内容：

```text
版本：V1.2
CDSS业务可用性增强落地设计
CDSS_PATIENT_FACT
/cdss/specialty/evaluate
触发条件放哪里
AMI/STEMI 第一版只做 5 个场景
## 11. 关键红线
```

### 后续计划

下一步应把方案落成开发交付物：

1. 输出 Oracle 中间表 DDL 草案。
2. 输出 `/cdss/specialty/evaluate` 接口字段说明。
3. 输出 AMI/STEMI 5 个场景的规则字段映射表。
4. 给 Trae/前端同事一份开发任务提示词。

---

## 2026-07-07 16:03:22 Trae前端诊断标准旧展示问题核对与开发提示词输出

### 用户问题

用户反馈 `http://192.168.3.27:4001/explore.html` 中“急性心肌梗死”的“诊断标准”仍是旧展示，只显示标题节点“急性心肌梗死诊断标准”，没有显示下级诊断明细。

### 核对结论

服务器 Neo4j 中“急性心肌梗死诊断标准”不是空壳，已存在 5 条下级诊断明细组件：

```text
疾病：急性心肌梗死
disease_code = DIS-CARD-CAD-AMI

诊断标准：
dx_code = DXC-CARD-547346EE2FED
dx_name = 急性心肌梗死诊断标准

下级关系：
DiagnosisCriteria -[:has_diagnostic_component]-> ClinicalRule

下级明细组件数 = 5
```

5 个组件为：

```text
1. 急性缺血症状或等效表现
2. 肌钙蛋白升高及动态变化
3. 缺血性心电图改变
4. 冠状动脉血栓或责任病变
5. 影像学新发室壁运动异常
```

因此本次问题不是图谱数据库缺失，而是前端查询仍停留在：

```text
Disease -> DiagnosisCriteria
```

没有继续下钻：

```text
DiagnosisCriteria -> has_diagnostic_component -> ClinicalRule
```

### 执行结果

已输出给 Trae/前端同事的开发提示词文件：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\Trae前端专科CDSS动态诊断标准与路径展示改造提示词_20260707.md
```

该文件包含：

1. 急性心肌梗死诊断标准旧展示问题说明。
2. 诊断标准、鉴别诊断、专病路径 3 类下钻查询规则。
3. 可直接使用的 Cypher 查询语句。
4. 前端推荐的数据结构。
5. 页面验收标准。
6. 标签顺序、去重、显示名、缓存等注意事项。

### 后续计划

1. Trae 按提示词修改前端查询逻辑后，再打开 `explore.html` 复核。
2. 验收重点不是“诊断标准卡片数量”，而是点击诊断标准后是否展示 5 个诊断明细组件及对应证据。
3. 同理复核鉴别诊断是否展示鉴别要点、排除检查、阻断动作；复核路径是否展示阶段、规则、动作、证据。

---

## 2026-07-07 16:45:00 AMI临床展示名前缀清理与动作级证据展示规则

### 用户问题

Trae 前端已能下钻展示 AMI 诊断标准和鉴别诊断，但页面出现：

```text
AMI诊断明细：...
AMI鉴别：...
```

用户判断内容怪，不符合医生阅读习惯；同时指出“证据与指南一箩筐”，医生无法知道具体治疗方案依据哪条指南。

### 判断

1. `AMI诊断明细：`、`AMI鉴别：` 是生成上下文，不是临床展示名。
2. 医生界面应展示短名称，如“肌钙蛋白升高及动态变化”“主动脉夹层排除与溶栓阻断”。
3. CDSS 不能默认展示疾病全部证据池，必须按“推荐动作/阻断动作”展示主证据。

### 执行结果

已直接修复服务器 Neo4j 中 10 个 AMI/STEMI ClinicalRule 节点的 `name/preferred_name/display_name`：

```text
急性缺血症状或等效表现
肌钙蛋白升高及动态变化
缺血性心电图改变
冠状动脉血栓或责任病变
影像学新发室壁运动异常
不稳定型/稳定型心绞痛
主动脉夹层排除与溶栓阻断
急性心包炎排除
肺栓塞排除
持续ST段抬高或等效表现
```

已同步更新：

```text
Trae前端专科CDSS动态诊断标准与路径展示改造提示词_20260707.md
专病辅助诊疗建设方案_专科CDSS六级建设.md  V1.5
AI自动化工具-文献指南解析.md  V1.40
```

新增硬规则：

```text
医生界面不得显示生成前缀。
疾病/用途/规则类型写入 code、pathway_code、rule_type、scope_disease_code，不写进展示名。
CDSS 推荐证据必须绑定当前推荐/阻断动作。
疾病证据池只做知识追溯，不作为当前推荐默认证据。
```

### 服务器复核

全库硬闸门通过：

```text
kg_node_count = 34744
kg_relation_count = 101528
technical_display_name_error_count = 0
duplicate_type_name_count = 0
duplicate_semantic_relation_count = 0
remaining_prefix_name_count = 0
global_safety_gate_status = passed
```

复核报告：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\99_全局质量体检_global_quality_audit\20260707_164500_display_evidence_fix\01_服务器全库硬闸门_summary.json
```

---

## 2026-07-07 20:10:00 推荐证据根模型修正：启用 RecommendationStatement

### 用户问题

用户指出：如果前端还需要从动作节点、规则节点和证据池之间二次推理“这个推荐依据哪条指南”，就失去图谱建模意义；不合理处需要根治，不能继续通过关系属性补丁解决。

### 判断

用户判断正确。

根模型应为：

```text
ClinicalRule
  -> has_recommendation_statement
RecommendationStatement
  -> recommends_action / blocks_action
  -> derived_from Evidence
  -> based_on_guideline Guideline
```

原因：

```text
Action 只表示动作是什么，例如 PCI、溶栓、阿司匹林。
RecommendationStatement 才表示在什么场景下为什么推荐/阻断这个动作。
同一个 Action 可被多个疾病、阶段、规则和指南复用，不能直接承载唯一推荐依据。
```

### 执行结果

本轮只更新标准和方案，未写服务器 Neo4j。

已更新：

```text
专科知识图谱Schema标准.md  V1.10
AI自动化工具-文献指南解析.md  V1.41
专病辅助诊疗建设方案_专科CDSS六级建设.md  V1.6
Trae前端专科CDSS动态诊断标准与路径展示改造提示词_20260707.md
AMI_STEMI_RecommendationStatement推荐陈述迁移方案_20260707.md
```

已删除上一轮临时方向中的动作级证据回填脚本：

```text
scripts/backfill_action_evidence_display_fields.py
```

该脚本此前只执行过 dry-run，没有正式写入服务器。

### 新硬规则

```text
1. CDSS 推荐卡片必须以 RecommendationStatement 为根。
2. 前端不得从 Disease -> Evidence 或 Action -> Evidence 推断当前推荐依据。
3. ClinicalRule 负责触发条件；RecommendationStatement 负责推荐/阻断语义、动作、指南和证据。
4. 新病种解析必须输出 cdss_recommendation_statement_matrix.csv。
5. 服务器迁移前必须先确认推荐陈述模型和 AMI/STEMI 样板迁移方案。
```

### 下一步

等待用户确认后，再执行 AMI/STEMI 样板迁移：

```text
生成 RecommendationStatement 节点
建立 ClinicalRule -> has_recommendation_statement
建立 RecommendationStatement -> recommends_action / blocks_action
建立 RecommendationStatement -> derived_from Evidence
建立 RecommendationStatement -> based_on_guideline Guideline
跑全库硬闸门和 AMI 推荐陈述专项验收
```

---

# 2026-07-07 21:50:00 RecommendationStatement 根模型迁移与 Trae 全局提示词

## 用户问题

用户要求校验无误后直接全部写入数据库并完成迁移，同时把原局部 Trae 提示词升级为 `Trae前端开发全局提示词.md`，支持 CDSS 全业务场景，并新增版本修改记录，便于 Trae 后续迭代读取。

## 执行方案

1. 只迁移已有证据链的 `ClinicalRule -> recommends_action / blocks_action / has_recommended_action -> Action`。
2. 生成 `RecommendationStatement` 节点，连接规则、动作、证据和指南。
3. 禁止从疾病证据池或动作证据池推断当前推荐依据。
4. 推荐陈述显示名采用“规则或阶段上下文｜动作名（动作类型）推荐/阻断”，避免同名推荐陈述重复。
5. 写入后跑全库硬闸门和 RecommendationStatement 专项校验。
6. 旧 Trae 局部提示词移除，统一改为 `Trae前端开发全局提示词.md`。

## 执行结果

```text
服务器 Neo4j 已写入 RecommendationStatement：291 个
候选规则-动作关系：291
未迁移候选：0
无动作 RecommendationStatement：0
无证据 RecommendationStatement：0
无指南匹配 RecommendationStatement：0
重复推荐三元组：0
同类型同名重复：0
全库硬闸门：passed
```

## 产物

```text
scripts/migrate_recommendation_statements.py
Trae前端开发全局提示词.md
AMI_STEMI_RecommendationStatement推荐陈述迁移方案_20260707.md
心血管内科文献集合/_migration_20260707_recommendation_statement/cdss_recommendation_statement_matrix.csv
心血管内科文献集合/_migration_20260707_recommendation_statement/recommendation_statement_postfix_validation.json
心血管内科文献集合/_server_safety_after_recommendation_statement_20260707_final/01_服务器全库硬闸门_summary.json
```

## 已同步规则

已同步到：

```text
AI自动化工具-文献指南解析.md V1.42
专病辅助诊疗建设方案_专科CDSS六级建设.md V1.7
_全局复利与踩坑日志.md
```

---

# 2026-07-07 22:48:44 图谱给 CDSS 用的接口说明 + 缓慢性心律失常批次收尾

## 用户问题

用户确认先补齐“图谱怎么给 CDSS 用”的接口说明，再继续新病种/新批次；随后指出 alias 同义词增量没有同步到 `术语字典`，`批次登记台账.md` 也没有及时更新。

## 执行方案

1. 新增 `专科CDSS图谱查询接口与Cypher示例.md`，把 Schema 转成后端/Trae 可直接使用的接口与 Cypher 示例。
2. 更新 `专病辅助诊疗建设方案_专科CDSS六级建设.md`，将接口说明作为开发实施附件。
3. 收尾缓慢性心律失常及传导阻滞批次：本地审计、服务器导入、跨批次去重、服务器硬闸门复测。
4. 将本轮 alias 增量同步回写 `术语字典`，新增路径/治疗方案同义词表，并增加术语字典校验脚本。
5. 更新 `心血管内科文献集合\批次登记台账.md` 和缓慢性批次正式纳入文献清单。

## 执行结果

```text
新增接口说明：专科CDSS图谱查询接口与Cypher示例.md
六级方案版本：V1.8
缓慢性批次本地质量门禁：passed
本地节点/关系：844 / 3758
服务器导入：844 节点、3758 关系
服务器跨批次重复实体：3 组 -> 0
服务器最终节点/关系：35858 / 108057
服务器硬闸门：passed
RecommendationStatement 未迁移候选：0
术语字典校验：9 个文件，blocking=0，warning=0，passed
正式纳入文献：8 份
```

## 本次修复文件

```text
专科CDSS图谱查询接口与Cypher示例.md
专病辅助诊疗建设方案_专科CDSS六级建设.md
术语字典\3_体征同义词表.yaml
术语字典\4_药物同义词表.yaml
术语字典\5_检查同义词表.yaml
术语字典\6_手术同义词表.yaml
术语字典\8_路径与治疗方案同义词表.yaml
术语字典\terminology_validation_summary_20260707.json
scripts\validate_terminology_dictionaries.py
心血管内科文献集合\批次登记台账.md
心血管内科文献集合\缓慢性心律失常传导阻滞文献来源清单.md
心血管内科文献集合\缓慢性心律失常传导阻滞文献来源清单.csv
```

## 强制规则

```text
1. 每批次导入服务器后，必须跑累计库硬闸门，不得只看本地审计。
2. alias 新增、同名实体合并、证据匹配 alias 修复后，必须同步回写术语字典。
3. 术语字典每次修改后必须运行 validate_terminology_dictionaries.py，blocking 和 warning 都必须为 0。
4. 批次完成后必须更新批次登记台账，并生成正式纳入文献便捷清单。
5. 本地 JSONL、Neo4j、术语字典、批次台账四处状态必须一致，缺一项视为批次未收尾。
```

## 下一步

继续新病种前，先以 `专科CDSS图谱查询接口与Cypher示例.md` 给后端/Trae 对接查询方式；随后再启动下一个心律失常或其他心血管专病批次。
---

---

# 2026-07-08 08:34:30 教材骨架锚点矩阵与 P0 修复输入清单

## 用户补充

四类范围不能写成最终范围。冠心病、心肌病、心力衰竭、心律失常只是优先验证集；验证没问题后，需要按同一规则自行扩大到心血管内科其他疾病大类和疾病。

## 执行方案

1. 同步 Schema 与 SKILL：新增 `skeleton_slot`、`knowledge_layer`、`source_section_path`、DOCX 段落锚点和 PDF 页码锚点。
2. 抽取《内科学（第10版）》心血管内科章节目录，支持章级、节级、条目级结构。
3. 修复三类抽取规则缺陷：
   - 支持“章标题后、第一节前”的章级 definition/overview，例如心力衰竭定义。
   - 支持“节标题后、第一个【栏目】前”的疾病 definition/overview，例如肥厚型心肌病定义。
   - 禁止简单子串误吸附，例如“不稳定型心绞痛”不得误配“稳定型心绞痛”。
4. 对合并标题降级处理，例如“不稳定型心绞痛和非 ST 段抬高型心肌梗死”只能作为待复核候选，不得直接按单病种自动入库。
5. 生成教材骨架目录、优先四类 P0 锚点矩阵和 definition 修复输入 JSONL；本轮未写入 Neo4j。

## 执行结果

```text
心血管教材结构段落数：74
P0 疾病数：68
definition 修复候选：43
ready_for_import_after_sampling：25
ready_for_review：18
needs_manual_anchor_review：17
needs_guideline_or_manual_source：8
```

## 产物

```text
scripts/build_textbook_skeleton_anchor_matrix.py
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_anchor_matrix/textbook_cardiology_chapter_outline_20260708.csv
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_anchor_matrix/textbook_skeleton_matrix_priority_four_20260708.csv
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_anchor_matrix/p0_definition_repair_input_priority_four_20260708.jsonl
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_anchor_matrix/summary_20260708.json
```

## 下一步

1. 对 25 条 `ready_for_import_after_sampling` 做抽样复核，重点看疾病名、章节路径、definition 是否一致。
2. 对 18 条 `ready_for_review` 做人工规则复核，合并章节不得直接拆成单病种定义。
3. 对 17 条 `needs_manual_anchor_review` 回到原文段落补更精确锚点。
4. 对 8 条 `needs_guideline_or_manual_source` 用指南或权威来源补充，不得伪装为教材骨架。
5. 四类通过硬闸门后，自动扩大到高血压、瓣膜病、心包疾病、感染性心内膜炎、先心病、主动脉和周围血管病、心血管神经症、肿瘤心脏病学等心血管内科其他疾病。
---

---

# 2026-07-08 09:07:00 25 条教材 definition delta 导入前校验

## 执行方案

1. 不直接使用 `p0_definition_repair_input_priority_four_20260708.jsonl`，因为该文件包含 `ready_for_review` 候选。
2. 新增 `scripts/build_textbook_definition_delta.py`，只读取矩阵中 `match_status=ready_for_import_after_sampling` 的 25 条。
3. 生成 Neo4j definition 更新 delta。
4. 跑导入前硬闸门：
   - 只允许 `ready_for_import_after_sampling`。
   - 禁止 body mention 和 combined title。
   - 禁止标题型伪 definition。
   - 必须有 `source_section_path`。
   - 必须有 `skeleton_slot=overview`。
   - 必须有 `knowledge_layer=textbook_core`。
   - 必须有 DOCX 段落和 PDF 页码锚点。
5. 对服务器 Neo4j 做只读预检查，确认 25 个 Disease code 都能唯一匹配。

## 执行结果

```text
严格候选数：25
delta 数：25
导入前阻断错误：0
重复 disease_code：0
导入前硬闸门：passed
服务器只读预检查：passed
服务器 Disease code 缺失：0
服务器 Disease code 重复：0
服务器现有 definition 非空：0
写库状态：未写入
```

## 产物

```text
scripts/build_textbook_definition_delta.py
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta/delta_disease_definition_update_ready25_20260708.jsonl
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta/preimport_validation_detail_ready25_20260708.csv
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta/preimport_validation_summary_ready25_20260708.json
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta/server_precheck_ready25_20260708.json
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta/neo4j_update_disease_definition_ready25_20260708.cypher
```

## 下一步

写入 25 条严格 definition delta 到服务器测试库，随后立即跑服务器硬闸门。
---

---

# 2026-07-08 09:12:00 25 条教材 definition 写入服务器并复核

## 执行方案

1. 使用 `scripts/import_textbook_definition_delta.py --execute` 写入严格 delta。
2. 只写入 `ready_for_import_after_sampling` 的 25 条。
3. 写入后立即跑服务器硬闸门。
4. 对优先 68 个疾病重新统计 definition 状态。

## 执行结果

```text
delta 数：25
服务器更新数：25
写入后硬闸门：passed
blocking_total：0

写入后硬闸门明细：
missing_count=0
duplicate_match_count=0
definition_empty_count=0
source_type_error_count=0
source_section_missing_count=0
skeleton_slot_error_count=0
knowledge_layer_error_count=0
pdf_page_missing_count=0
docx_anchor_missing_count=0
definition_noise_count=0

优先 68 疾病：
definition_nonempty_count=25
definition_empty_count=43
```

## 产物

```text
scripts/import_textbook_definition_delta.py
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta/server_import_result_ready25_20260708.json
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta/server_postimport_gate_ready25_20260708.json
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta/server_priority68_definition_status_after_ready25_20260708.json
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta/remaining_definition_gap_after_ready25_20260708.csv
```

## 下一步

继续处理剩余 43 条 definition 缺口：18 条 ready_for_review、17 条 needs_manual_anchor_review、8 条 needs_guideline_or_manual_source。
---

---

# 2026-07-08 09:19:00 增量 3 条教材 definition 写入服务器

## 执行方案

1. 细化教材条目识别规则，新增识别：冠状动脉痉挛、窦性心动过缓、病态窦房结综合征等下级条目。
2. 修正 definition 句子选择规则：优先 `是指/称为/是一类/是一组/简称`，降低诱发因素、治疗、伴有等非定义句权重。
3. 只筛选服务器 definition 仍为空的 ready 候选，生成增量 delta。
4. 写入服务器并跑硬闸门。

## 执行结果

```text
新增严格候选：3
写入服务器：3
写入后硬闸门：passed
blocking_total：0
新增补齐疾病：
- DIS-CARD-CAD-SPASM 冠状动脉痉挛
- DIS-CARD-ARR-SB 窦性心动过缓
- DIS-CARD-ARR-SND 窦房结功能障碍

优先 68 疾病：
definition_nonempty_count=28
definition_empty_count=40
```

## 产物

```text
scripts/build_textbook_definition_incremental_delta.py
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_incremental/delta_disease_definition_update_incremental3_20260708.jsonl
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_incremental/server_import_result_incremental3_20260708.json
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_incremental/server_postimport_gate_incremental3_20260708.json
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_incremental/server_priority68_definition_status_after_incremental3_20260708.json
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_incremental/remaining_definition_gap_after_incremental3_20260708.csv
```

## 下一步

继续处理剩余 40 条：15 条 ready_for_review、17 条 needs_manual_anchor_review、8 条 needs_guideline_or_manual_source。
---

---

# 2026-07-08 20:40:00 剩余 40 条教材 definition 缺口处理

## 本轮目标

继续处理优先验证集（冠心病、心肌病、心力衰竭、心律失常）剩余 40 条疾病 definition 缺口，并判断其他心血管骨架疾病是否可以启动。

## 执行方案

1. 不直接使用自动候选写库，先回到《内科学（第10版）》DOCX 原文段落。
2. 对每条缺口按三类处理：
   - 教材有明确定义句：进入人工校准 delta；
   - 教材只在鉴别诊断、病因或列表中出现：阻断，不写入 definition；
   - 教材未覆盖：标记需要指南/权威来源补充。
3. 写库前执行服务器只读预检：
   - Disease code 必须存在；
   - Disease code 不得重复；
   - 当前 definition 必须为空，避免覆盖已有定义。
4. 写库后执行服务器硬闸门：
   - missing_count=0；
   - duplicate_match_count=0；
   - definition_empty_count=0；
   - source_type_error_count=0；
   - source_section_missing_count=0；
   - skeleton_slot_error_count=0；
   - knowledge_layer_error_count=0；
   - pdf_page_missing_count=0；
   - docx_anchor_missing_count=0；
   - definition_noise_count=0。

## 执行结果

```text
剩余待处理：40
本轮生成人工校准 delta：30
本轮写入服务器 Neo4j：30
写入后硬闸门：passed
blocking_total：0

优先 68 疾病最终状态：
definition_nonempty_count=58
definition_empty_count=10
missing_count=0
duplicate_match_count=0
```

## 本轮写入的 30 条

```text
DIS-CARD-CAD-UA 不稳定型心绞痛
DIS-CARD-CAD-NSTEMI 非ST段抬高型心肌梗死
DIS-CARD-CAD-AMI 急性心肌梗死
DIS-CARD-CAD-POST-MI-SYNDROME 心肌梗死后综合征
DIS-CARD-CAD-OLD-MI 陈旧性心肌梗死
DIS-CARD-CAD-SILENT-ISCHEMIA 隐匿性冠心病
DIS-CARD-HF-LEFT 左心衰竭
DIS-CARD-HF-RIGHT 右心衰竭
DIS-CARD-HF-BIVENTRICULAR 全心衰竭
DIS-CARD-HF-HFrEF 射血分数降低的心力衰竭
DIS-CARD-HF-HFmrEF 射血分数轻度降低的心力衰竭
DIS-CARD-HF-HFpEF 射血分数保留的心力衰竭
DIS-CARD-HF-CHF 慢性心力衰竭
DIS-CARD-ARR-AVB1 一度房室传导阻滞
DIS-CARD-ARR-AVB2 二度房室传导阻滞
DIS-CARD-ARR-AVB3 三度房室传导阻滞
DIS-CARD-ARR-SVT 室上性心动过速
DIS-CARD-ARR-PSVT 阵发性室上性心动过速
DIS-CARD-ARR-AVNRT 房室结折返性心动过速
DIS-CARD-ARR-AVRT 房室折返性心动过速
DIS-CARD-ARR-WPW 预激综合征
DIS-CARD-ARR-TDP 尖端扭转型室性心动过速
DIS-CARD-ARR-NSVT 非持续性室性心动过速
DIS-CARD-ARR-LQTS 长QT间期综合征
DIS-CARD-ARR-BRUGADA Brugada综合征
DIS-CARD-ARR-CPVT 儿茶酚胺敏感性多形性室性心动过速
DIS-CARD-ARR-SQTS 短QT间期综合征
DIS-CARD-ARR-ERS 早期复极综合征
DIS-CARD-SCD-ARREST 心脏骤停
DIS-CARD-SCD-SUDDEN 心脏性猝死
```

## 仍阻断的 10 条

```text
DIS-CARD-HF-POST-MI 心肌梗死后心力衰竭：教材只说明心肌梗死可导致心衰，未给独立疾病定义。
DIS-CARD-HF-DIALYSIS-CHF 透析患者慢性心力衰竭：教材未定位到独立定义。
DIS-CARD-ARR-VA 室性心律失常：教材是章节类目，不是独立疾病定义。
DIS-CARD-ARR-BRADY 缓慢性心律失常：教材未以该名称给出总论定义。
DIS-CARD-CM-ATRIAL 心房心肌病：教材未定位到定义。
DIS-CARD-CM-FABRY 法布雷病心肌病：教材心肌病章节仅在鉴别诊断列表出现。
DIS-CARD-CM-AMYLOID 淀粉样变心肌病：教材心肌病章节仅在鉴别诊断列表出现。
DIS-CARD-CM-ABVC 致心律失常性双心室心肌病：教材未定位到定义。
DIS-CARD-CM-ALVC 致心律失常性左心室心肌病：教材未定位到定义。
DIS-CARD-CM-ACM 致心律失常性心肌病：教材未定位到定义。
```

## 产物

```text
scripts/build_textbook_definition_curated_delta.py
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_curated/delta_disease_definition_update_curated30_20260708.jsonl
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_curated/preimport_validation_detail_curated30_20260708.csv
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_curated/blocked_after_curated30_20260708.csv
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_curated/server_import_result_curated30_20260708.json
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_curated/server_postimport_gate_curated30_20260708.json
心血管内科文献集合/00_教材骨架库_foundation_skeleton/20260708_textbook_definition_delta_curated/server_priority68_definition_status_after_curated30_20260708.json
```

## 下一步

1. 可以开始“心血管内科其他疾病骨架”的自动锚点抽取和本地矩阵生成。
2. 但服务器正式写入仍执行同一规则：只写“教材定义句明确 + 来源锚点明确 + 预检通过”的条目。
3. 剩余 10 条需要走指南/权威来源补充，不得用教材鉴别列表或章节标题硬补。

---

---

# 2026-07-08 22:05:00 外部权威来源补齐剩余 definition 缺口

## 用户问题

教材和既有指南内仍有 10 条 definition 缺口。用户要求如果教材和指南确实没有，应使用网络权威内容补充，并将外部权威资料统一下载到：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威
```

文件命名规则：

```text
专科+大类+疾病+权威来源+日期
```

## 执行方案

1. 建立外部权威目录与白名单。
2. 优先使用官方指南、学会指南、专家共识、政府/罕见病指南、NCBI/GeneReviews、PMC 开放全文。
3. 百度健康医典只作为患者教育/别名/辅助定义来源，不作为正式推荐证据。
4. 对剩余缺口生成外部权威候选定义表。
5. 只将来源可追溯的定义写入 Neo4j；谱系分型、人群限定状态用 `conditional` 标记。

## 服务器写入结果

```text
检查 Disease definition：11 条
definition_empty_count：0
高可信 high：6 条
条件性 conditional：5 条
```

高可信写入：

```text
DIS-CARD-ARR-VA 室性心律失常
DIS-CARD-ARR-BRADY 缓慢性心律失常
DIS-CARD-CM-ACM 致心律失常性心肌病
DIS-CARD-CM-ARVC 致心律失常性右心室心肌病
DIS-CARD-CM-ATRIAL 心房心肌病
DIS-CARD-CM-AMYLOID 淀粉样变心肌病
```

条件性写入：

```text
DIS-CARD-CM-ABVC 致心律失常性双心室心肌病
DIS-CARD-CM-ALVC 致心律失常性左心室心肌病
DIS-CARD-CM-FABRY 法布雷病心肌病
DIS-CARD-HF-POST-MI 心肌梗死后心力衰竭
DIS-CARD-HF-DIALYSIS-CHF 透析患者慢性心力衰竭
```

## 关键产物

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威\00_来源白名单_source_whitelist\外部权威来源白名单_authoritative_source_whitelist_20260708.csv
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威\02_结构化候选_structured_candidates\心血管内科+剩余10条+外部权威人工候选定义+20260708.csv
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威\03_入库delta_import_delta\delta_external_authority_definition_yes_conditional_20260708.jsonl
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威\03_入库delta_import_delta\delta_external_authority_definition_dialysis_hf_20260708.jsonl
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威\03_入库delta_import_delta\server_postcheck_external_authority_definition_final_20260708.json
```

## 当前判断

本轮已把剩余 definition 空值缺口归零，但 `conditional` 不等于正式 CDSS 推荐通过。后续专病诊疗引擎应识别：

```text
definition_confidence=high：可作为知识展示基础定义
definition_confidence=conditional：可用于解释/检索，不得单独作为正式推荐触发依据
```

---

---

# 2026-07-09 07:15:00 优先68复核与服务器全局安全体检

## 执行动作

1. 修复优先 68 definition 统计逻辑：原先错误读取汇总 JSON，导致 code 数为 0；已改为从三批 delta 和阻断清单还原 68 个 code。
2. 重跑服务器优先 68 definition 覆盖统计。
3. 新增全局安全体检脚本，按技术质量、知识展示、专病路径、正式 CDSS 推荐四类检查。

## 优先 68 复核结果

```text
checked_count=68
missing_count=0
definition_empty_count=0
definition_nonempty_count=68
authoritative_textbook=57
external_authoritative_source=6
external_authoritative_source_conditional=5
status=passed
```

## 服务器全局体检结果

```text
节点总数=35858
关系总数=108057
KGNode节点=35858
KGNode内关系=108057
```

技术层通过项：

```text
非KGNode节点=0
连接非KGNode关系=0
同类型同名重复=0
药物类别无具体药物=0
技术编码名节点=0
条件性definition参与正式推荐=0
```

业务阻断项：

```text
疾病definition为空=32
诊断标准无明细=4个诊断标准节点，影响9条疾病-诊断关系
治疗方案无下游动作=46
推荐关系缺推荐等级/证据等级/来源证据等核心字段=1104
```

警告项：

```text
标签原始顺序不统一=137
推荐类节点缺直接证据/指南连接=247
```

## 可用性结论

```text
知识展示：可用
专病诊疗流程：可继续样板验证，但需先修复阻断项
正式CDSS推荐：不可直接上线
```

## 产物

```text
scripts/verify_priority68_definition_after_external_authority.py
scripts/run_server_global_cdss_safety_audit.py
心血管内科文献集合/00_全局质量体检_global_quality_audit/server_global_cdss_safety_audit_summary_20260709.json
心血管内科文献集合/00_全局质量体检_global_quality_audit/server_global_cdss_safety_audit_detail_20260709.json
心血管内科文献集合/00_全局质量体检_global_quality_audit/server_global_cdss_safety_audit_report_20260709.md
```

## 下一步决策

暂不建议马上开新病种。下一步应按以下顺序治理：

1. 修复 4 个诊断标准无明细节点。
2. 修复 46 个治疗方案无下游动作。
3. 批量补 1104 条推荐关系的推荐等级、证据等级、来源证据、适用条件、禁忌/排除条件。
4. 处理 32 个非优先疾病 definition 空值，作为“心血管内科其他疾病骨架扩大范围”的第一批任务。

---

---

## 2026-07-09 09:20:00 追加记录：启动心血管内科基础骨架库重建

### 本轮任务

按最新总方案启动 `心血管内科基础骨架库重建_CARD-SKELETON-20260709`，目标是先稳定教材骨架，再继续专病指南 PDF 精抽。

### 执行原则

```text
先骨架，后指南
先本地 delta，后 Neo4j
先审计，后导入
教材负责基础临床框架，指南负责精细推荐和证据等级
```

### 本轮已完成

1. 创建本轮输出目录：

```text
心血管内科文献集合/00_教材骨架库_foundation_skeleton/心血管内科基础骨架库重建_CARD-SKELETON-20260709
```

2. 完成服务器 Neo4j 只读统计，未写库。
3. 完成《内科学（第10版）》DOCX 心血管内科章节目录抽取。
4. 完成 PDF 章节起始页反查校验。
5. 生成四大优先范围 G1 骨架槽位初筛矩阵。
6. 按项目运行环境新规则，切换后续正式脚本环境为：

```text
D:\Program Files Ai\python-venvs\medical-kg\Scripts\python.exe
```

7. 已向项目 Python 安装并核验：

```text
python-docx
pdfplumber
pypdf
neo4j
```

### 关键产物

```text
项目运行环境规则.md
心血管内科教材章节目录_20260709.csv
心血管内科教材疾病目录树_20260709.md
四大优先疾病教材骨架槽位覆盖矩阵_G1初筛_20260709.csv
四大优先疾病教材骨架覆盖汇总_G1初筛_20260709.csv
阶段A_服务器只读统计_20260709.json
阶段A_项目运行环境核验_20260709.json
阶段B_项目Python复核_20260709.json
```

### 当前判断

本轮只是 G1 初筛，不等于实体化完成。下一步必须进入“教材原文深抽取”：对冠心病、心肌病、心衰、心律失常逐疾病拆出定义、症状、体征、检查、诊断标准、鉴别诊断、治疗原则等结构化实体，并生成本地 delta 和审计报告。

---

---

## 2026-07-09 09:30:00 追加记录：阶段C.1教材原文锚点深抽取

### 执行范围

四大优先范围：

```text
冠心病/冠状动脉疾病
心肌病/心肌疾病
心力衰竭
心律失常
```

### 执行结果

```text
抽取对象：57 个章节/疾病/下级条目
候选节点：253
候选关系：196
原文证据锚点：196
审计行数：57
Neo4j写入：否
```

### 产物

```text
阶段C1_教材骨架原文锚点_nodes_20260709.jsonl
阶段C1_教材骨架原文锚点_relations_20260709.jsonl
阶段C1_教材骨架原文锚点_evidence_20260709.jsonl
阶段C1_教材骨架原文锚点审计_20260709.csv
阶段C1_教材骨架原文锚点_summary_20260709.json
```

### 审计结论

本阶段只完成“教材原文锚点层”，所有 57 个对象状态均为 `needs_slot_backfill_or_manual_review`。这不是失败，而是防止把原文段落直接冒充最终结构化实体。

下一层必须继续做：

```text
从原文锚点中拆出症状、体征、检查、诊断标准明细、鉴别诊断要点、治疗动作、药物/操作等实体。
```

---

---

## 2026-07-09 10:10:00 追加记录：阶段C2/C3结构化候选抽取与补抽

### C2执行结果

从 C1 教材原文锚点生成结构化候选：

```text
输入原文锚点：196
候选实体：713
候选关系：995
证据-实体链接：1014
审计行：196
Neo4j写入：否
```

新增脚本：

```text
scripts/build_textbook_skeleton_structured_candidates.py
scripts/audit_textbook_skeleton_structured_candidates.py
```

### C2初次G1审计

```text
g1_structured_candidate_ready：13
g1_needs_backfill：31
g1_container_rollup_only：12
g1_no_structured_candidate：1
```

其中修正了一个审计规则问题：有下级条目的章节/小节不再按具体专病要求完整闭环，而是标记为 `category_container`，避免制造虚假缺口。

### C3定向补抽

对 C2 缺口对象回到 DOCX 原始段落范围补抽：

```text
补抽对象：32
新增候选实体：194
新增候选关系：279
新增证据链接：279
合并后候选实体：860
合并后候选关系：1274
Neo4j写入：否
```

新增脚本：

```text
scripts/backfill_textbook_skeleton_from_docx_ranges.py
```

### C3补抽后G1审计

```text
g1_structured_candidate_ready：37
g1_needs_backfill：7
g1_container_rollup_only：12
g1_no_structured_candidate：1
```

剩余缺口已降到 8 个对象，清单见：

```text
阶段C3_补抽后剩余缺口清单_20260709.csv
```

### 目录父级修正

发现并修复一个 DOCX 标题拆行导致的目录错误：

```text
错误：第一节动脉粥样硬化 被挂到 第三章心律失常
修正：第一节动脉粥样硬化 挂到 第四章动脉粥样硬化和冠状动脉粥样硬化性心脏病
```

修正记录：

```text
阶段C3_目录父级修正记录_20260709.json
```

说明：当前 C2/C3 仍是本地候选，不允许直接导入 Neo4j；进入 curated delta 前，需要对受影响对象重新生成稳定 ID。

---

---

## 2026-07-09 11:05:00 追加记录：阶段C4剩余缺口精修完成

### 执行动作

对 C3 后剩余 8 个对象回到教材原文逐条核查，分为三类处理：

```text
1. 明确教材原文可补：直接生成 C4 curated 候选。
2. 分类/治疗容器：不按具体疾病闭环要求，标记为 container_rollup_only。
3. 心电图定义型心律失常：按 ECG-defined arrhythmia 审计，不强制要求临床表现槽位。
```

新增脚本：

```text
scripts/curate_textbook_skeleton_remaining_gaps.py
```

### C4执行结果

```text
C4精修对象：7
C4新增候选节点：24
C4新增候选关系：29
C4新增证据链接：29
C4合并后候选节点：883
C4合并后候选关系：1303
Neo4j写入：否
```

### C4后G1审计

```text
g1_structured_candidate_ready：44
g1_container_rollup_only：13
g1_needs_backfill：0
g1_no_structured_candidate：0
missing_group_counter：空
```

### 关键产物

```text
阶段C4_剩余缺口精修_nodes_20260709.jsonl
阶段C4_剩余缺口精修_relations_20260709.jsonl
阶段C4_剩余缺口精修_evidence_links_20260709.jsonl
阶段C4_合并结构化候选_nodes_20260709.jsonl
阶段C4_合并结构化候选_relations_20260709.jsonl
阶段C4_精修后G1深审计矩阵_20260709.csv
阶段C4_精修后G1深审计_summary_20260709.json
阶段C4_精修后剩余缺口清单_20260709.csv
阶段C4_执行报告_20260709.md
```

### 当前结论

教材骨架四大优先范围的结构化候选层 G1 缺口已清零。下一步不是直接入库，而是生成稳定 ID 版 curated delta，并进行 G2 入库前审计。

---

---

## 2026-07-09 14:55:00 追加记录：教材骨架四大优先 C5/C6 入库闭环与全章节扩展

### 四大优先 C5/C6 结果

```text
批次：CARD-SKELETON-20260709
范围：冠心病、心肌病、心力衰竭、心律失常四大优先教材骨架
C5稳定delta节点：1331
C5稳定delta关系：2608
C5 Evidence节点：496
G2入库前审计：passed
G2阻断：0
G2警告：0
Neo4j写入：是
服务器本批次节点：1331
服务器本批次关系：2608
服务器复核：passed
```

### 服务器硬闸门

```text
non_kgnode_batch_nodes：0
duplicate_type_name_in_batch：0
duplicate_semantic_relations_in_batch：0
relations_missing_evidence_ids：0
formal_cdss_ready_nodes：0
formal_cdss_ready_relations：0
evidence_missing_excerpt：0
evidence_without_inbound_relation：0
technical_code_like_primary_name：0
```

### 关键修复

```text
BNP、NT-proBNP、CK-MB、CT、ICD、CRT、IVUS、ACEI/ARB、ACEI、ARB、ARNI、PCI 已从英文缩写主名规范为中文主名，英文缩写写入 alias。
服务器已有标准中文节点的缩写重复节点已合并，关系和证据已迁移，本地 C5 delta 已同步修正。
```

### 全心血管章节扩展 D1-D6

```text
批次：CARD-SKELETON-FULL-20260709
全章节/条目：81
教材原文锚点：348
C2候选节点：1282
C2候选关系：2092
D3回填后候选节点：1488
D3回填后候选关系：2513
D5/D6人工精修新增节点：7
D6合并候选节点：1504
D6合并候选关系：2532
D6来源感知审计：抽取缺口=0
C5稳定delta节点：1798
C5稳定delta关系：5146
C5 Evidence节点：773
G2入库前审计：passed
G2阻断：0
G2警告：0
Neo4j写入：是
服务器本批次节点：1798
服务器本批次关系：5146
服务器复核：passed
```

### 全章节入库说明

```text
1. 后段“肿瘤治疗相关/糖尿病相关心血管疾病”等章节父级已校准到“肿瘤心脏病学”和“糖尿病相关心血管疾病”。
2. D6 候选层已生成稳定 ID curated delta，并通过 G2 后写入服务器 Neo4j。
3. 教材未覆盖的槽位已标记为 source_limited，不再误判为抽取失败；后续由指南 PDF 补充决策层。
4. 全章节教材骨架仍是知识骨架层，不等于正式 CDSS 推荐层。
```

### 关键产物

```text
心血管内科基础骨架库重建_CARD-SKELETON-20260709/阶段C6_服务器复核报告_20260709.md
心血管内科基础骨架库重建_CARD-SKELETON-20260709/心血管内科四大优先骨架闭环报告_20260709.md
心血管内科全章节骨架扩展_CARD-SKELETON-FULL-20260709/阶段D6_来源感知G1全章节审计报告_20260709.md
心血管内科全章节骨架扩展_CARD-SKELETON-FULL-20260709/阶段D6_合并结构化候选_nodes_20260709.jsonl
心血管内科全章节骨架扩展_CARD-SKELETON-FULL-20260709/阶段D6_合并结构化候选_relations_20260709.jsonl
心血管内科全章节骨架扩展_CARD-SKELETON-FULL-20260709/阶段C6_服务器复核报告_20260709.md
```

---

---

## 2026-07-09 18:29:57 追加记录：冠心病 CDSS 决策层升级入库与批次级复核

### 执行范围

```text
顶层学科：心血管内科
疾病大类：冠心病
执行批次：BATCH-CARD-CAD-CDSS-20260709-001
批次名称：BATCH-CARD-CAD-CDSS-20260709-001_冠心病_CDSS决策层升级
来源基线：BATCH-CARD-CAD-20260623-001
```

### 本次新增/更新内容

```text
ClinicalPathway：10
PathwayStage：29
ClinicalRule：33
RecommendationStatement：33
关系：864
覆盖疾病：10
```

覆盖疾病：

```text
急性冠脉综合征、急性心肌梗死、ST段抬高型心肌梗死、非ST段抬高型心肌梗死、不稳定型心绞痛、慢性冠脉综合征、稳定型心绞痛、缺血性心肌病、陈旧性心肌梗死、隐匿性冠心病
```

### 本地硬闸门

```text
missing_endpoint_count：0
duplicate_relation_key_count：0
recommendation_required_empty_count：0
recommendation_without_action_count：0
recommendation_without_evidence_count：0
stage_treatment_plan_name_collision_count：0
mojibake_suspect_node_count：0
hard_gate_pass：true
```

### 服务器写入与复核

```text
Neo4j写入：是
写入/合并节点：105
写入/合并关系：864
服务器批次级复核：passed
```

服务器批次硬闸门：

```text
recommendation_without_evidence：0
recommendation_without_action_or_block：0
recommendation_without_guideline：0
recommendation_missing_display_fields：0
clinical_rule_without_recommendation_statement：0
stage_without_rule：0
pathway_without_stage：0
stage_treatment_plan_same_name：0
duplicate_blocked_action_names：0
```

### 关键产物

```text
心血管内科文献集合/BATCH-CARD-CAD-CDSS-20260709-001_冠心病_CDSS决策层升级/01_delta/delta_nodes_upsert.jsonl
心血管内科文献集合/BATCH-CARD-CAD-CDSS-20260709-001_冠心病_CDSS决策层升级/01_delta/delta_relations_add.jsonl
心血管内科文献集合/BATCH-CARD-CAD-CDSS-20260709-001_冠心病_CDSS决策层升级/02_audit/quality_audit_summary.json
心血管内科文献集合/BATCH-CARD-CAD-CDSS-20260709-001_冠心病_CDSS决策层升级/04_import/neo4j_delta_import_summary.json
心血管内科文献集合/BATCH-CARD-CAD-CDSS-20260709-001_冠心病_CDSS决策层升级/04_import/neo4j_batch_postcheck_summary.json
```

### 说明

```text
本批次是“专病指南决策层”升级，不是重复抽取教材骨架。
前端和后端应优先使用 ClinicalPathway -> PathwayStage -> ClinicalRule -> RecommendationStatement 的链路。
医生看到某条推荐时，只展示该 RecommendationStatement 直连的主证据、指南、页码、推荐等级、证据等级和结构化摘要，不展示疾病级证据池。
```

---

# 2026-07-11 22:45:00｜Schema V1.12 服务器迁移与 Trae 全局提示词更新

## 用户提出的问题

用户要求按步骤继续执行，第二步由 Codex 自行评估确认，最终告诉 Trae 需要怎么修改。

## 判断结论

早期计划文件仍写着“不写 Neo4j”，但用户后续已明确授权校验无问题后直接迁移入库。因此本轮按最新授权执行：先 dry-run 判断，再正式写入服务器，最后做服务器后验、本地测试和 Trae 交接。

## 执行方案

1. 读取 `schema_v112_dry_run_report.json`，确认迁移映射无重复目标三元组。
2. 执行 `scripts/migrate_schema_v112_neo4j.py --apply`。
3. 生成压缩迁移摘要和服务器后验 JSON。
4. 跑本地审计单元测试。
5. 重建 `Trae前端开发全局提示词.md`，要求 Trae 使用 Schema V1.12 查询口径。

## 执行结果

```text
迁移关系：7432 条
节点迁移：
  TextbookSection -> SourceSection：73
  ClinicalManifestation -> SourceSection：2
  knowledge_layer textbook_skeleton -> textbook_core：1860
  definition_skeleton_slot -> skeleton_slot：68
本地测试：tests.test_audit_graph_instance 16 项 OK
```

服务器后验：

```text
总节点：43020
总关系：139845
SourceSection：75
旧节点 TextbookSection/ClinicalManifestation：0
重复语义关系：0
RecommendationStatement：560
推荐缺证据：0
推荐缺指南：0
推荐缺动作：3
DiagnosisCriteria：81，其中 31 条暂无 has_diagnostic_component
```

## 遗留阻断

333 条旧关系未自动迁移：

```text
USES_MEDICATION：225
HAS_PROCEDURE：106
HAS_CLINICAL_MANIFESTATION：2
```

这些关系主要是 `SourceSection -> Medication/Procedure` 或 `DiseaseCategory -> Medication/Procedure`，属于“章节提及/大类提及”，不能直接当作疾病级或治疗方案级推荐。

## 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：记录“字段名 entityType 不能误写 entity_type”“章节提及关系不能硬迁移为 CDSS 推荐”“前端不得把旧大写关系当正式临床事实”。

---

---

# 2026-07-11 08:58:00｜旧弱语义关系清理与Schema瘦身评估

## 用户提出的问题

用户确认优化掉 `USES_MEDICATION`、`HAS_PROCEDURE`、`HAS_CLINICAL_MANIFESTATION`，并追问 Schema 标准是否需要补充；随后指出 Schema 和 MD 文件越来越大，要求评估是否还有类似节点/关系可优化。

## 判断结论

这 333 条不是重复边，而是旧命名、弱语义、易被前端误用的关系。它们全部是 `knowledge_display_only`、`formal_cdss_ready=false`、`knowledge_layer=textbook_skeleton`，不应进入正式关系层。Schema 需要补充，但只能补一条硬规则，详细证据外置到报告和 JSON，避免主Schema继续膨胀。

## 执行结果

```text
归档并删除旧弱语义关系：333 条
USES_MEDICATION：225 -> 0
HAS_PROCEDURE：106 -> 0
HAS_CLINICAL_MANIFESTATION：2 -> 0
HAS_* 历史大写关系：0
服务器总节点：43020
服务器总关系：139512
RecommendationStatement 缺动作/阻断：0
RecommendationStatement 缺证据：0
RecommendationStatement 缺指南：0
```

## Schema/文档处理

```text
专科知识图谱Schema标准.md：V1.12 -> V1.13
Trae前端开发全局提示词.md：V1.1 -> V1.2
新增 Schema与图谱瘦身评估报告_20260711.md
```

## 后续候选

`has_recommended_action` 与 `recommends_action` 名称接近，但语义不同：前者是 PathwayStage 阶段候选动作，后者是 ClinicalRule/RecommendationStatement 正式推荐动作。不能直接删，建议下一轮改名或强说明。

## 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：旧弱语义关系要归档清理；低频不等于冗余；主Schema不再承载迁移细节和长篇案例。

---
