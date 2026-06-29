---
name: parsing-medical-guidelines
description: Use when starting a specialty, disease-category, or single-disease knowledge-graph task from original medical PDFs, guidelines, textbooks, or expert documents.
---

# AI自动化工具-文献指南解析

版本：V1.28  
Schema：`专科知识图谱Schema标准.md` V1.7  
用途：从原始医学文献生成可审计、可合并的专科知识图谱标准数据实例。

## 变更记录

变更记录时间必须精确到秒，格式统一为 `YYYY-MM-DD HH:mm:ss`。历史记录若原始记录仅精确到月份，不得伪造真实发生时间，应标注为“历史补录”。

| 版本 | 变更时间 | 变更内容 |
|---|---|---|
| V1.0 | — | 初版 |
| V1.1 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | 新增§10实体归一与别名归一化、§11否定事实与极性过滤、§12数值与阈值节点处理规则；原§10–16顺延为§13–19；§9 Schema版本更新为V1.1 |
| V1.2 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | §10.1词表类别抽象为通用模板，新增心肌病、急性心肌梗死两个病种示例；§10.3 prompt注入格式抽象为通用模板，新增两病种注入示例；§12.2阈值规则通用化，新增两病种阈值对照表（含时间窗阈值） |
| V1.3 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | 新增 Definition 防漏映射规则和 SOURCE_DOES_NOT_COVER 判定前置复核；禁止把已有定义证据的抽取/映射遗漏判为文献覆盖不足 |
| V1.4 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | 新增图谱数据生成后的强制导入交接规则：必须主动输出可导入文件清单、导入判定、阻断原因和修复路径；新增专科批次登记台账要求；新增集合根目录PDF来源清单要求 |
| V1.5 | 2026-06-24 09:03:11（历史补录；原记录仅到月份） | 强化 Definition 兜底映射、国际指南中文实体映射和推荐等级冲突处置计划；禁止把宽关系聚合造成的推荐等级差异直接作为未解决冲突 |
| V1.6 | 2026-06-24 09:03:11 | 变更记录日期统一升级为精确到秒的变更时间；后续所有方案、Schema、批次台账和交付记录不得只记录到月份 |
| V1.7 | 2026-06-24 09:21:20 | 强化临床表现实体化审计：症状、体征及截图统计中的主要实体类型必须做证据到实体的覆盖复核；教材章节证据允许使用 disease_code/disease_name 上下文锚定，不要求每个段落重复疾病名；图谱生成后必须输出并核对实体类型计数，发现异常需先修复再导入 |
| V1.8 | 2026-06-24 22:40:49 | 纳入满分优化方案：确立“内科学搭骨架、指南填血肉”的执行顺序；新增全局术语字典、药品三层归一、P0/P1 Schema 覆盖、真实反向抽检、OCR/解析/语义失败原因分型和证据归因审计硬规则 |
| V1.9 | 2026-06-24 22:49:34 | 将核心原则升级为“基础权威教材/专科专著搭骨架，指南/共识/路径填血肉”；《内科学》仅作为心血管内科本批次基础教材示例，不得固化为所有学科默认教材；新增跨学科教材选择与确认规则 |
| V1.10 | 2026-06-24 22:53:36 | 明确 `术语字典/` 为与 SKILL 同目录的人工维护主术语库；新增 YAML 字典读取、校验、注入、待审核队列和禁止自动改写规则；`PENDING`、合并缩写、跨类型别名冲突不得进入正式图谱 |
| V1.11 | 2026-06-24 23:08:26 | 新增“学科基础骨架库”建设规则：先完整解析本学科教材/专著，建立顶层学科-疾病大类-疾病/亚型三层目录和基础画像，再按疾病大类匹配指南；新增心血管内科骨架库细则和其他学科配置补充模板 |
| V1.12 | 2026-06-25 09:18:00 | 同步 Schema V1.2：字段说明统一为“英文技术字段名+中文名称+类型/枚举+是否必填+说明”；后续新批次默认使用 Schema V1.2，历史 V1.1 批次保留原 provenance |
| V1.13 | 2026-06-25 09:16:30 | 强化 Neo4j 测试库同步规则：测试库修复同步默认使用 KGNode 子图替换导入，禁止把最终同步建立在保留历史脏数据的普通合并上；导入脚本必须支持请求级重试、小批次补导入和导入后服务器统计报告 |
| V1.14 | 2026-06-25 09:53:09 | 同步 Schema V1.3：§7.2–§7.7 标准关系表统一增加关系中文名、方向说明和用途说明；后续新批次默认使用 Schema V1.3 |
| V1.15 | 2026-06-25 10:03:43 | 同步 Schema V1.4：§9 新增 Guideline 与 Evidence 的白话解释、差异对照和示例；后续新批次默认使用 Schema V1.4 |
| V1.16 | 2026-06-25 15:20:34 | 修复心血管骨架库执行漏洞：新增全书跨章节回捞、反证检索硬门禁、SOURCE_DOES_NOT_COVER 反证前置规则、样板图谱只按 scope 疾病闭环审计、生成后必须输出可导入文件和服务器同步统计；新增独立《_全局复利与踩坑日志.md》维护规则 |
| V1.17 | 2026-06-26 08:45:41 | 修复 Neo4j 标签顺序审计规范：明确 `labels(n)` 为 Neo4j 无序标签集合，禁止把原始返回顺序作为质量失败依据；导入脚本必须统一使用 `:KGNode:实体类型` 标签契约，并写入 `primary_label`、`type_label`、`canonical_labels` 作为审核用规范标签元数据；导入摘要必须输出标签元数据审计结果 |
| V1.18 | 2026-06-26 08:58:17 | 新增本地输出文件夹命名规范：以后新增目录统一采用“中文说明_英文技术名或批次号”的双语可读命名；保留英文 batch_id 和技术后缀用于脚本稳定；历史英文目录不强制重命名，避免破坏既有审计、导入和路径记录 |
| V1.19 | 2026-06-26 15:24:02 | 修复语义空壳节点、药物类别别名污染、跨批次同名不同 code 合并漏洞；同步 Schema V1.5，新增 `has_specific_medication`、`clinical_review_status`、正式 CDSS 推荐层硬门槛；要求生成后审计 semantic_shell、medication_alias_instance_gap、target_match、global duplicate，并同步记录《_全局复利与踩坑日志.md》 |
| V1.20 | 2026-06-27 00:28:13 | 同步 Schema V1.6：新增治疗方案可执行性、技术编码显示名、药物类别具体化、疾病药物视图去重和服务器关系语义键去重硬规则；要求所有截图/前端/审核统计按 `KGNode.code` 统计唯一实体，不能把多条路径当成多个药物节点；修复经验必须同步写入《_全局复利与踩坑日志.md》 |
| V1.21 | 2026-06-27 21:46:59 | 同步 Schema V1.7：新增 Neo4j 全库标签契约硬闸门，禁止任何导入、补丁或外部脚本创建不带 `KGNode` 主标签的临床节点；导入后必须验证 `all_node_count == kg_node_count`、`all_relation_count == kg_relation_count`、非 `KGNode` 节点数=0、触达非 `KGNode` 的关系数=0 |
| V1.22 | 2026-06-27 22:10:57 | 新增《AI自动化工具-文献指南解析步骤记录.md》过程记录要求：每天/每轮关键提示后必须记录用户问题、判断结论、执行方案、执行结果、遗留阻断，并关联《_全局复利与踩坑日志.md》；步骤记录用于复盘执行过程，踩坑日志用于沉淀可复用事故规则 |
| V1.23 | 2026-06-27 22:43:11 | 新增重复问题升级机制、证据回捞候选防误判规则、大图谱数据增量优先规则和版本管理边界：同类问题反复出现必须升级为测试/审计/SKILL硬规则；Trae/外部模型候选不得直接写库；大 JSONL 快照不得作为日常小修复的唯一写入对象；代码文档进版本管理，大图谱快照以 manifest/hash/delta 管理 |
| V1.24 | 2026-06-28 08:43:37 | 新增 Neo4j delta 导入语义键去重规则和 GitHub 凭据安全规则：增量关系导入必须先按 `(source.code, relationType, target.code)` 查重/合并，不得仅按关系 `id` MERGE；GitHub 不得使用明文账号密码自动化，必须使用 SSH、浏览器授权或细粒度 PAT |
| V1.25 | 2026-06-28 18:48:43 | 新增 required 缺口闭环冲刺规则、策展补丁规则、delta 节点 upsert 规则和新病种启动预检规则：required 缺口必须先回查指南/教材 evidence index；可修复项必须写入本地 JSONL 并重跑审计；没有明确随访/诊断/治疗原文不得硬补；delta 包必须同时提供节点 upsert、关系 add、manifest 和可导入文件清单；新病种开工前必须运行预检或等价清单 |
| V1.26 | 2026-06-29 08:57:53 | 新增临床使用效果审核规则：`pending_clinical_review` 不得要求专家逐条查看图谱边，必须生成疾病级、场景级和药师专项的简化审核包；边级明细只作为证据追溯；AI 不得把 pending 自动改成专家已确认；正式 CDSS 推荐层必须以审核决策表回写为准 |
| V1.27 | 2026-06-29 14:39:49 | 新增多智能体协作与 Trae 前端审核边界：Trae 可负责审核页面、候选清单、OCR/术语辅助和结果导出；不得直接写 Neo4j、不得直接改正式 JSONL、不得自动批准 pending；Codex 负责回写脚本、质量门禁、Neo4j 导入和最终上线判定 |
| V1.28 | 2026-06-29 14:58:40 | 修复新批次启动版本留痕规则：`batch_config.json` 中 Schema/SKILL 版本必须从主文档当前 `版本：Vx.x` 读取，不得硬编码旧版本；新批次预检和准备后必须复核版本号、纳入文件数和纳入文件清单 |

## 1. 核心原则

- 每次任务只使用本次确认的执行范围和原始文献路径。
- 未确认专科/疾病范围和 PDF/指南路径，不得开始扫描或解析。
- 先生成标准数据实例与审核报告；Neo4j 导入必须单独确认。
- 每条核心知识必须能追溯到原始文献、章节/页码或文本位置及原文片段。
- 文本不合格、疾病归属不明确或 Schema 无法承载时，阻断并报告，不猜测入图。
- 各批次独立抽取、独立验收；验收通过后才能合并到标准主图谱。
- `pending_clinical_review` 是正式 CDSS 推荐层阻断标记，不是让临床专家逐条查看图谱关系的工作方式。每批必须把复杂图谱转换为疾病级、场景级、药师专项的简化审核表，专家从临床使用效果和风险角度确认。
- AI 可以整理审核包、证据链和建议修复项，但不得自行把 `clinical_review_status=pending_clinical_review` 批量改为 `clinical_approved`。

### 1.1 满分执行目标

本工具的目标不是“能导入 Neo4j”，而是生成可用于 CDSS 推理的疾病画像图谱。每个病种必须同时形成三层结构：

```text
基础画像层：定义、病因、危险因素、机制、症状、体征、检查、诊断、鉴别、治疗原则、预后
指南决策层：推荐陈述、推荐等级、证据等级、阈值、路径、药物、操作、随访、风险分层
术语归一层：疾病、症状、体征、药物、检查、操作、评分、危险因素的标准名、英文名、缩写和别名
```

正式批次不得只满足结构合规。若图谱中 Evidence 很多但可推理实体少，或常见临床概念只停留在 `evidence_text` 未实体化，视为语义质量不合格。

### 1.2 “基础权威教材/专科专著搭骨架，指南/共识/路径填血肉”

每个专科首次执行时，必须优先确认并解析该学科适用的基础权威教材、统编教材、专科专著或权威参考书，建立基础证据库；指南、共识、路径和专家建议用于增强规范化决策，不得反过来替代基础画像。

《内科学》只适用于内科系统疾病，当前心血管内科批次可作为基础教材来源；后续外科、妇产科、儿科、肿瘤、神经、感染、急诊、重症等学科，必须按顶层学科重新确认对应基础教材或专科专著。若用户未提供教材路径，必须先提示补充或明确“本批次缺基础教材，基础画像完整性受限”，不得静默把《内科学》套用于所有学科。

疾病批次执行顺序固定为：

```text
1. 基础教材/专著确认：按 specialty 确认本学科适用教材、专科专著或权威参考书路径
2. 教材章节定位：确定本疾病/疾病大类在基础来源中的页码、章节和段落范围
3. 教材骨架抽取：先抽定义、病因、危险因素、机制、症状、体征、检查、诊断、鉴别诊断、治疗原则、预后
4. 指南血肉增强：再抽指南推荐等级、证据等级、阈值、药物、操作、路径、随访、风险分层和正式推荐
5. 骨架-血肉对齐：检查指南推荐是否挂接到已有疾病、症状、体征、检查、药物、操作、危险因素等基础实体
6. 术语归一：用全局术语字典和本批次受控词表统一实体名称
7. 反向抽查：从原文高频临床词反查图谱节点、关系和证据链
8. 审计通过后再导入或合并
```

若基础教材/专著骨架未完成，不得用指南证据直接替代基础画像；指南优先用于规范化决策，不负责补齐全部基础医学常识。若指南中出现教材未覆盖的新术语或新治疗，应进入术语扩展和临床决策增强层，并记录来源优先级。

### 1.2.1 全书跨章节回捞与反证检索硬规则

基础教材/专著抽取不得只截取某一章节作为唯一语料。疾病知识常跨章节出现，例如心血管疾病可在呼吸、血液、肾脏、风湿免疫、急诊、重症、病理生理等章节出现。首次建设学科骨架库时，必须执行“两阶段抽取”：

```text
阶段1：定位本学科/本疾病大类核心章节，完成主章节骨架抽取。
阶段2：以疾病标准名、别名、英文缩写、旧称、相关综合征名为检索词，对基础教材/专著全书执行跨章节回捞。
```

缺失归因必须先做反证检索：

```text
未抽到图谱节点或关系 ≠ 来源不覆盖。
只有全书反证检索未命中疾病名/别名及对应临床元素证据时，才允许标记 SOURCE_DOES_NOT_COVER。
若全书反证检索命中原文，但图谱缺节点、关系或映射，则必须标记 EXTRACTION_MISS_REVIEW_REQUIRED 或 EXTRACTION_MAPPING_GAP，并阻断质量闸门。
```

骨架库审计必须输出：

```text
06_quality_audit/反证检索登记表.csv
06_quality_audit/疑似漏抽清单.csv
06_quality_audit/missing_reason_and_solution.csv
06_quality_audit/quality_gate_summary.json
```

`SOURCE_DOES_NOT_COVER` 只能表示“已检索确认来源确实没有覆盖”，不得作为抽取失败、章节截取过窄、术语字典不全或实体映射失败的默认兜底原因。

### 1.2.2 样板图谱合并范围规则

疾病大类或单病种样板图谱合并学科骨架库时，必须以本批次 `00_scope_and_config/scope_taxonomy.csv` 中非空 `disease_code` 为闭环审计范围。骨架库中的鉴别诊断疾病、相邻疾病、并发疾病可以作为关联知识引用，但不得自动扩大本批次 Disease 闭环范围。

若合并后 `disease_count` 超过 scope 疾病数，必须检查是否把非本批次疾病节点纳入闭环审计；未修复前不得宣称样板图谱完整。

### 1.2.3 生成后主动交付规则

每次图谱数据生成后，必须主动输出以下文件的绝对路径，避免上下文或 token 中断导致用户无法继续工作：

```text
05_data_instance/nodes_final.jsonl
05_data_instance/relations_final.jsonl
06_quality_audit/quality_gate_summary.json
06_quality_audit/disease_pathway_coverage.csv
06_quality_audit/missing_reason_and_solution.csv
07_review_package/可导入图谱文件清单.md
08_neo4j_import/neo4j_import_summary.json（若已导入）
```

### 1.2.4 Neo4j 标签规范与审计口径

Neo4j 节点标签是无序集合，`labels(n)` 的返回顺序可能受数据库内部标签 token 顺序影响。即使创建语句写成 `CREATE (n:KGNode:Disease)`，某些数据库也可能返回 `['Disease','KGNode']`。因此：

1. 业务规范标签顺序固定为 `['KGNode', entityType]`。
2. 导入脚本创建或匹配节点时必须使用 `MERGE (n:KGNode:\`实体类型\` {code: row.code})` 的标签契约。
3. 每个节点必须写入 `primary_label='KGNode'`、`type_label=entityType`、`canonical_labels=['KGNode', entityType]`。
4. 审核工具、统计脚本和给其他模型的审核包应读取 `canonical_labels`，不得直接用 `labels(n)` 的原始顺序判断合格/不合格。
5. 任何导入脚本、补丁脚本、外部模型修复脚本不得创建只带 `Disease`、`TreatmentPlan`、`DiagnosisCriteria` 等类型标签但不带 `KGNode` 的临床节点。此类节点会绕过 `KGNode` 子图审计，必须判定为服务器级质量失败。
6. 导入摘要必须输出：
   - `canonical_label_metadata_mismatch_count`：规范标签元数据不一致数，必须为 0。
   - `raw_label_order_differs_count`：Neo4j 原始 `labels(n)` 顺序与规范顺序不同的数量，仅作诊断信息，不作为 CDSS 图谱质量失败项。
   - `non_kgnode_node_count`：非 `KGNode` 节点数，必须为 0。
   - `relation_touching_non_kgnode_count`：任一端不是 `KGNode` 的关系数，必须为 0。

### 1.3 学科基础骨架库总则

每个顶层学科首次建设时，必须先建立“学科基础骨架库”，再启动单个疾病大类或单病种指南抽取。骨架库不是某个病种批次的临时材料，而是该学科后续所有疾病图谱复用的基础层。

骨架库必须覆盖三层范围：

```text
第1层：顶层学科/专科，例如 心血管内科、呼吸内科、神经内科、普外科
第2层：疾病大类，例如 冠心病、心肌病、心力衰竭、高血压、心律失常
第3层：疾病、分型、亚型、临床综合征，例如 ACS、STEMI、NSTEMI、肥厚型心肌病
```

骨架库最小内容：

```text
1. 学科疾病目录：顶层学科、疾病大类、疾病/亚型、上下位关系、纳入/排除边界
2. 疾病基础画像：定义、流行病学、病因、危险因素、发病机制、症状、体征、并发症、预后
3. 诊断骨架：诊断标准、鉴别诊断、检查、检验、影像、关键指标、基础阈值、评分/风险分层
4. 治疗原则骨架：治疗目标、治疗原则、药物类别、具体药物、操作/手术/介入类别、随访原则
5. 术语骨架：标准中文名、英文名、缩写、中文别名、英文别名、旧称、俗称、教材用名、指南用名
6. 证据骨架：书名、版本、章节、页码、段落、原文片段、document_id、segment_id
7. 复用接口：后续疾病批次必须优先复用骨架库节点，不得重复造疾病、症状、体征、检查、药品节点
```

新建骨架库输出目录固定为中文+英文双语命名：

```text
{专科输出集合}/00_学科基础骨架库_foundation_skeleton/
```

历史兼容目录 `{专科输出集合}/00_foundation_skeleton/` 不强制重命名；若已经产生审计、导入摘要或服务器同步记录，禁止只改文件夹名。

骨架库最小交付文件：

```text
specialty_foundation_config.yaml
foundation_source_documents_manifest.csv
foundation_document_quality_audit.csv
foundation_scope_taxonomy.csv
foundation_controlled_vocabulary.csv
foundation_segments.jsonl
foundation_evidence.jsonl
foundation_nodes.jsonl
foundation_relations.jsonl
foundation_coverage_audit.csv
foundation_quality_summary.json
```

后续疾病批次启动时，必须先读取同专科 `00_学科基础骨架库_foundation_skeleton/`；历史批次可兼容读取 `00_foundation_skeleton/`，再处理疾病指南。若该学科骨架库不存在或质量闸门未通过，必须先建设或修复骨架库，不得直接做指南图谱。

### 1.4 心血管内科基础骨架库细则

心血管内科必须优先完整解析心内科教材/专著和《内科学》心血管章节，形成可复用骨架库。该骨架库至少覆盖：

```text
冠心病/冠状动脉疾病
心肌病
心力衰竭
心律失常
高血压
心脏瓣膜病
心包疾病
感染性心内膜炎
先天性心脏病成人相关内容
肺血管与肺心病相关内容
主动脉和外周血管相关心血管内容
```

心血管内科骨架库必须先完成以下动作：

```text
1. 完整扫描 `心血管内科/书籍教材` 路径下的 PDF/DOCX/TXT
2. 建立教材/专著文档清单、哈希、版本、页码、章节和文本质量审计
3. 从教材/专著中冻结心血管疾病三层目录
4. 对每个疾病大类建立基础画像、诊断骨架、治疗原则骨架和术语骨架
5. 将心肌病、冠心病已生成节点回填对齐到骨架库，避免后续疾病批次重复建节点
6. 再按疾病大类匹配 `心血管内科/诊疗指南` 中对应 PDF 指南
```

心血管内科后续疾病执行规则：

```text
先调用心血管内科骨架库 → 再筛选该疾病大类指南 → 再抽取指南血肉 → 再做骨架-血肉对齐 → 再审计/导入
```

### 1.5 其他学科骨架库配置补充规则

新增其他学科时，不修改主流程，必须新增或更新该学科的骨架配置。配置至少包含：

```yaml
specialty: 顶层学科/专科名
foundation_source_roots:
  - 本学科基础教材/专著路径
guideline_source_roots:
  - 本学科指南/共识/路径路径
foundation_scope_levels:
  - specialty
  - disease_category
  - disease_or_subtype
minimum_foundation_elements:
  - definition
  - epidemiology
  - etiology
  - risk_factor
  - pathophysiology
  - symptom
  - sign
  - complication
  - prognosis
  - diagnosis_criteria
  - differential_diagnosis
  - exam
  - lab_test
  - treatment_principle
  - medication_class
  - procedure_class
  - follow_up_principle
terminology_dictionary_extensions:
  - 疾病
  - 症状
  - 体征
  - 药物
  - 检查
  - 手术/操作
  - 危险因素
guideline_matching_policy: 按疾病大类和同义词字典匹配指南，禁止仅凭文件夹名称自动纳入
```

每个学科可以补充本学科特有骨架项，但不得删除通用最小项。例如肿瘤学应增加分期、分子分型、病理类型、治疗线数；外科应增加手术适应证、禁忌证、术式、围手术期管理；妇产科应增加孕周、胎儿/母体状态；儿科应增加年龄段、体重、发育阶段。

### 1.6 全局复利与踩坑日志

项目根目录必须维护独立文件：

```text
_全局复利与踩坑日志.md
```

该文件用于记录已经发生过的错误、根因、修复方式、回归测试和可复用规则。它不是替代 SKILL 的流程标准，而是 SKILL 的经验来源。处理原则：

```text
1. 事故和踩坑写入独立日志，保留背景、证据、错误表现和修复结果。
2. 可复用且会影响未来执行的规则，提炼后同步进入 SKILL。
3. 日志必须记录到具体时间，格式为 YYYY-MM-DD HH:mm:ss。
4. 每次新批次开始前，应先快速读取日志中与本学科、本流程相关的条目。
5. 若同类错误重复出现，必须补充自动化测试或质量闸门，不能只追加文字提醒。
```

本日志至少包含字段：

```text
时间、影响范围、错误表现、根因、修复动作、验证证据、复用规则、关联文件、是否已同步SKILL/Schema/测试
```

### 1.7 每日/每轮步骤记录

项目根目录必须维护独立文件：

```text
AI自动化工具-文献指南解析步骤记录.md
```

该文件用于记录每天或每轮关键提示后的执行过程，不能替代 `_全局复利与踩坑日志.md`。两者分工如下：

| 文件 | 中文定位 | 必须记录内容 | 用途 |
|---|---|---|---|
| `AI自动化工具-文献指南解析步骤记录.md` | 执行过程记录 | 用户提出的问题、判断结论、执行方案、执行结果、遗留阻断、关联踩坑日志 | 复盘当天/本轮到底做了什么 |
| `_全局复利与踩坑日志.md` | 事故与复用规则库 | 错误表现、根因、修复动作、验证证据、复用规则、是否同步 SKILL/Schema/测试 | 防止同类错误在后续病种重复 |

执行规则：

```text
1. 每天或每轮关键提示后，必须追加步骤记录。
2. 若本轮只产生普通进展，写入步骤记录即可。
3. 若本轮暴露流程漏洞、质量事故、可复用错误模式，必须同步写入踩坑日志，并在步骤记录中引用对应时间。
4. 新病种启动前，先读取最近步骤记录和相关踩坑日志，再开始解析。
5. 不得口头声称“已记录”；必须实际写入文件。
```

### 1.8 重复问题升级机制

同类问题不得依赖用户反复截图或追问后才处理。出现重复问题时，必须按以下规则升级：

```text
第1次：定位根因，完成本批次修复，并写入步骤记录。
第2次：写入《_全局复利与踩坑日志.md》，形成可复用规则。
第3次：必须新增或修改自动化测试、审计脚本或 SKILL 硬规则；不得继续只靠人工提醒。
```

新病种或新专科启动前，必须读取最近步骤记录和踩坑日志，并执行“历史踩坑清单检查”。至少包括：

- 语义空壳实体：诊断标准、鉴别诊断、治疗方案、药物治疗、预后良好/不良等不得作为疾病直连目标。
- 药物类别必须连接具体药物，别名不得污染为具体药物或英文缩写。
- 治疗方案必须有下游药物、操作、路径、适应证、禁忌证或时机信息，不能只停留在方案名称。
- 证据回捞候选必须同时满足疾病锚点、目标实体锚点和关系语义锚点，不能把“合并某病”“鉴别某病”“另一个疾病的治疗”误连到目标疾病。
- 服务器验收必须同时查全库和 `KGNode` 子图，不能只查 `KGNode`。
- 前端统计必须按 `KGNode.code` 去重，不能把多条路径当成多个节点。

## 2. 启动确认闸门

每次新任务必须先向用户展示并确认以下内容：

```text
specialty: 顶层学科/专科名
scope_type: specialty | category | disease
scope_target: 专科名 | 疾病大类名 | 单病种名
foundation_source_roots: 本学科基础教材、统编教材、专科专著或权威参考书根目录
guideline_source_roots: 原始指南、共识、临床路径、专家资料根目录
source_roots: 兼容旧字段；若使用，必须拆分确认 foundation_source_roots 与 guideline_source_roots
output_root: 本批次输出目录
schema_file: 专科知识图谱Schema标准.md
```

执行范围示例：

```text
specialty=心血管内科
scope_type=specialty, scope_target=心血管内科
scope_type=category, scope_target=心肌病
scope_type=disease, scope_target=肥厚型心肌病
```

路径确认时必须列出：

- 根目录绝对路径
- PDF、DOCX、DOC、TXT 文件数量
- 预计纳入与排除数量
- 文件名重复和内容哈希重复数量
- 本学科基础权威教材、统编教材、专科专著或权威参考书路径；心血管内科可使用《内科学》作为基础教材之一
- 本学科基础骨架库路径：新建默认 `{专科输出集合}/00_学科基础骨架库_foundation_skeleton/`；历史兼容 `{专科输出集合}/00_foundation_skeleton/`

顶层学科/专科是每次任务的必填项。用户未填写时，可依据已冻结的疾病目录自动推断；只能得到唯一结果时，必须向用户展示推断结果并获得确认，不得静默补充。存在多个可能学科时必须阻断并询问。

当 `scope_type=specialty` 且该学科尚无合格 `00_学科基础骨架库_foundation_skeleton/` 或历史兼容 `00_foundation_skeleton/` 时，默认任务必须先建设学科基础骨架库。只有骨架库质量闸门通过后，才进入疾病大类或单病种指南抽取。

只有用户明确回复顶层学科、范围和路径已确认，才可进入文献清单阶段。相同目录在新任务中也必须重新确认。

### 2.1 批次登记台账

每个专科输出集合必须维护一个批次登记台账，固定命名为：

```text
批次登记台账.md
```

位置：该专科输出集合根目录下，例如：

```text
心血管内科文献集合/批次登记台账.md
```

每次开始新批次前，必须先登记：

- 顶层学科
- 范围类型
- 目标范围
- 批次编号
- 来源路径
- 输出目录
- 当前状态

每次批次完成后，必须回填：

- 测试库导入结论
- 正式 CDSS 上线结论
- 节点数、关系数
- required 缺口数
- 来源冲突数
- `可导入图谱文件清单.md` 路径
- PDF/文献来源清单路径
- 具体正式纳入 PDF/文献文件名清单。不得只登记清单路径。

不得只依赖聊天记录判断已执行批次、下一批次范围或主图谱合并顺序。

## 3. 执行范围解析

### 3.1 专科范围

`scope_type=specialty` 时，处理该专科目录体系内的全部疾病大类与疾病。先冻结专科疾病目录，再建立文献覆盖矩阵。

### 3.2 疾病大类范围

`scope_type=category` 时，处理该大类下全部规范疾病与亚型。例如“心肌病”可覆盖肥厚型、扩张型、限制型及配置中纳入的其他心肌病。

### 3.3 单病种范围

`scope_type=disease` 时，只处理目标疾病及其诊疗所必需的分型、患者状态、并发症和规则，不扩展到同类其他疾病。

### 3.4 目录冻结

执行前生成 `scope_taxonomy.csv`，至少包括：

```text
specialty_code, category_code, subcategory_code, disease_code,
name, name_en, aliases, inclusion_status, inclusion_reason
```

文献发现新病种时先写入范围变更建议，未经确认不得扩大本批次范围。

## 4. 来源体系

### 4.1 来源优先级

| 优先级 | 来源类型 | 主要用途 | 推荐类别/证据等级 |
|---|---|---|---|
| 1 | 最新权威指南、正式共识 | 诊断标准、治疗推荐、剂量、阈值、随访、正式分级 | 按原文记录 |
| 2 | 本学科基础权威教材、统编教材、专科专著或权威参考书 | 定义、病因、病理生理、流行病学、症状体征、基础诊疗 | `N/A` |
| 3 | 可追溯的专家整理 TXT | 补充指南和教材未覆盖知识 | `N/A`，除非原文明确分级 |
| 4 | 用户人工整理的网页 TXT | 待核验补充来源 | 不得自动赋级 |

禁止自动抓取网页后直接入图。

### 4.2 来源冲突

- 正式推荐、剂量、阈值和证据等级以最新权威指南为准。
- 不删除冲突来源，分别保留证据。
- 输出 `source_conflict_register.csv` 和 `source_conflict_resolution_plan.csv`，记录主题、来源、冲突内容、主来源建议、处置动作、是否阻断 CDSS。
- 宽关系（如 `based_on_guideline`、`supported_by_evidence`、目录/来源关系）不得承载最终推荐等级冲突；推荐等级必须回到 evidence / recommendation statement 粒度。
- 对同一宽关系聚合出多个推荐等级时，默认处置为 `resolved_by_statement_level_priority_plan`：保留全部来源，正式 CDSS 读取 statement/evidence 粒度主推荐，不直接读取宽关系推荐等级。
- 来源优先级默认规则：中文最新版权威指南优先；若中文指南缺失或国际指南更新，则允许引用 ESC/ACC/AHA/EACTS 等国际新版指南作为补强来源；旧版来源保留证据但标记为 deprecated 或 lower_priority，不删除。
- 国际指南证据必须映射到中文疾病实体。不得因为英文指南使用 ACS、NSTEMI、STEMI、CCS 等英文缩写就另建英文疾病节点；应通过 `controlled_vocabulary.csv` 的中文规范名、英文名、缩写和别名统一归一。
- 批次完成时不得只给 `conflict_status=open` 清单；必须给出每条冲突的处置状态。无法机器处置的才保留 `open`，并写明必须临床裁决的具体原因。

## 5. 基础教材/专科专著证据库

基础教材/专科专著证据库用于承载“搭骨架”知识，不固定绑定某一本书。心血管内科可使用《内科学》作为基础教材之一；其他学科必须按 `specialty` 确认对应基础权威教材、统编教材、专科专著或权威参考书，不得默认沿用《内科学》。

首次使用某一教材或专著时，应完整建立可复用证据库；后续同学科、同教材版本任务按章节复用，不重复解析整本书。若同一学科存在多本基础来源，应建立来源优先级并记录到批次台账。

### 5.1 建库内容

- 文档哈希、书名、版次、出版信息
- 篇、章、节、页码和段落边界
- 稳定 `document_id` 与 `segment_id`
- 疾病名称、英文名、缩写和别名索引
- 每页文本质量和页面分类

### 5.2 调用规则

- 后续任务按 `scope_type/scope_target` 调用相关章节，不重复解析整本书。
- 教材只提供与本次疾病范围相关的证据分段。
- 教材内容不得标为指南推荐类别或证据等级。

教材字段固定为：

```text
source_type=authoritative_textbook
source_authority=authoritative_textbook
knowledge_strength=high
clinical_applicability=general
recommendation_class=N/A
evidence_level=N/A
```

## 6. 文献清单与去重

输入扩展名支持 `.pdf`、`.docx`、`.doc`、`.txt`。

每个文件计算流式 SHA-256，并生成：

- `source_documents_manifest.csv`
- `dedup_index.csv`
- `source_folder_summary.csv`

文献清单至少包含：

```text
document_id, file_name, full_path, relative_path, extension,
source_root, source_type, size_bytes, last_write_time, sha256,
normalized_title, dedup_group, keep_or_duplicate, duplicate_reason
```

`full_path` 仅用于本地执行审计，不得写入正式节点或关系。

去重顺序：内容哈希完全相同 → 规范化标题相同 → 同指南不同版本。完全重复只保留一个解析对象；不同版本分别保留并记录版本关系。

## 7. 逐页解析

### 7.1 双指标验收

```text
page_accounting_rate = 100%
eligible_content_pass_rate = 100%
```

- 每页必须有页码、页面分类、解析方法和处理状态。
- 正文、表格、图注、推荐、剂量、阈值、诊断标准和治疗路径必须解析合格或明确阻断。
- 目录、索引、版权、封面和空白页可不参与知识抽取，但必须计入页面清点。

### 7.2 解析顺序

1. 原生文本提取引擎 A。
2. 独立文本提取引擎 B 交叉检查。
3. 空文本、低密度、乱码、图片页和复杂表格页进入 OCR。
4. 表格保留行列结构；推荐等级、剂量和阈值单独校验。
5. 仍无法可靠恢复时阻断该文献，不生成正式知识。

### 7.3 页面审计

每页输出：

```text
document_id, page_number, page_class, parse_method,
char_count, chinese_ratio, replacement_char_count, mojibake_score,
ocr_used, table_detected, clinical_keyword_hits,
status, failure_reason
```

页面分类至少包括：`body`、`table`、`figure_caption`、`recommendation`、`contents`、`index`、`copyright`、`blank`、`unreadable`。

### 7.4 干净文本

文本必须保留稳定边界：

```text
<<<DOCUMENT document_id=...>>>
<<<PAGE page=... class=...>>>
<<<SECTION section_id=... title=...>>>
原文
```

分段主键：

```text
SEG-{document_id}-{page_or_line}-{section_id}-{start_offset}-{end_offset}
```

专家 TXT 没有页码时，必须保留章节/段落号、行号或字符区间和内容哈希。

## 8. 编码与运行安全

- 所有 Markdown、CSV、JSON、JSONL 和 TXT 使用 UTF-8。
- 需要 PowerShell 5.1 人工读取的中文 Markdown 和 CSV 使用 UTF-8 BOM。
- Python 文件读写显式指定 `utf-8` 或 `utf-8-sig`。
- 禁止通过默认 PowerShell 管道传递含中文路径的长 Python/Cypher 文本。
- 任一输出出现 Unicode 替换字符、典型错码或中文路径被替换为 `?`，立即停止当前批次。
- 单文献解析必须设置超时；单个文件失败不得卡死整批任务。
- 每完成一份文献立即写入进度日志，支持断点续跑。

## 9. Schema 映射

所有实体、关系、字段、编码和证据必须符合根目录 `专科知识图谱Schema标准.md` V1.5。

Schema 分三层：

1. 统一核心层：所有专科共享的实体、关系和证据契约。
2. 专科/疾病大类配置层：定义本范围的必需、可选和不适用模块。
3. 单病种规则层：使用 `ClinicalRule`、`ThresholdRule` 和适用条件承载疾病特异语义。

单病种特有字段不得直接加入统一核心层。发现 Schema 无法无损表达的内容时，写入 `schema_gap_register.csv`，本批次不得自行改变标准。

## 10. 实体归一与别名归一化

本节规定在知识抽取阶段如何保证同一医学实体全局唯一、命名一致，覆盖批次内归一和批次间合并两个阶段。

### 10.1 受控词表

每个执行批次启动前，必须在 `00_scope_and_config/` 目录下生成受控词表文件：

```text
controlled_vocabulary.csv
```

字段：

```text
canonical_name        中文规范主名称（唯一，作为节点 name 字段值）
name_en               英文标准名
abbr                  常用缩写（逗号分隔多个）
aliases               别名列表（逗号分隔，含俗称、旧称、教材用名）
entityType            对应 Schema 实体类型
disease_scope         适用病种范围（HCM | DCM | ALL | ...）
source                词表来源（指南/教材/专家确认）
```

心肌病批次初始词表须覆盖以下类别的核心术语：

- 疾病名称及其缩写（HCM/肥厚型心肌病、DCM/扩张型心肌病等文献中出现的全部病种）
- 高频检查和指标（LVEF、LVOT 梗阻压差、BNP/NT-proBNP 等）
- 核心药物（β受体阻滞剂/倍他乐克/美托洛尔等）
- 关键操作（室间隔切除术/Morrow手术、酒精室间隔消融术/TASH等）
- 常见评分量表（SCD风险评分、NYHA分级等）

词表由人工初始化，每批次执行后根据 `alias_normalization_log.csv` 中发现的新变体增量更新，更新须经人工确认后方可生效。

**每批次初始词表须覆盖的核心术语类别（通用模板）：**

```text
1. 本批次全部目标疾病名称及其缩写、别名、亚型名
2. 高频检查项目和指标（含中英文缩写归一）
3. 核心药物（通用名、商品名、药物类别名归一）
4. 关键操作和介入术式（含简称、俗称归一）
5. 常用评分量表和分级系统
6. 高频患者状态和特殊人群描述
```

**病种案例一：心肌病批次（scope_target=心肌病）**

初始词表核心条目示例：

| canonical_name | abbr | aliases示例 | entityType |
|---|---|---|---|
| 肥厚型心肌病 | HCM | 肥厚性心肌病、梗阻性肥厚型心肌病、HOCM | Disease |
| 扩张型心肌病 | DCM | 充血型心肌病、特发性扩张型心肌病 | Disease |
| 左心室射血分数 | LVEF | 射血分数、左室射血分数、EF值 | ExamIndicator |
| 左室流出道压差 | LVOT压差 | LVOT梗阻压差、流出道梗阻 | ExamIndicator |
| 氨基末端脑钠肽前体 | NT-proBNP | NT-proBNP、脑钠肽前体 | ExamIndicator |
| 美托洛尔 | — | 倍他乐克、metoprolol | Medication |
| β受体拮抗剂 | β-blocker | β受体阻滞剂、beta blocker | Medication |
| 室间隔切除术 | — | Morrow手术、外科室间隔减容术、心肌切除术 | Procedure |
| 酒精室间隔消融术 | TASH/ASA | 化学消融术、室间隔消融 | Procedure |
| 纽约心功能分级 | NYHA分级 | 心功能分级、NYHA心功能分类 | ScoringScale |
| 心脏性猝死风险评分 | SCD风险评分 | HCM SCD评分、猝死风险评估 | ScoringScale |

**病种案例二：急性心肌梗死批次（scope_target=急性心肌梗死）**

初始词表核心条目示例：

| canonical_name | abbr | aliases示例 | entityType |
|---|---|---|---|
| 急性心肌梗死 | AMI | 心梗、心肌梗死、急性心梗 | Disease |
| ST段抬高型心肌梗死 | STEMI | ST抬高心梗、ST段抬高性心肌梗死 | Disease |
| 非ST段抬高型心肌梗死 | NSTEMI | 非ST抬高心梗、非ST段抬高性心肌梗死 | Disease |
| 急性冠脉综合征 | ACS | 急性冠状动脉综合征、冠脉综合征 | Disease |
| 高敏肌钙蛋白 | hs-cTn | 肌钙蛋白、cTnI、cTnT、troponin | ExamIndicator |
| 肌酸激酶同工酶 | CK-MB | 心肌酶、CK同工酶 | ExamIndicator |
| 经皮冠状动脉介入治疗 | PCI | 冠脉介入、支架手术、球囊扩张、PTCA | Procedure |
| 溶栓治疗 | — | 静脉溶栓、链激酶溶栓、rt-PA溶栓、药物溶栓 | Procedure |
| 冠状动脉旁路移植术 | CABG | 搭桥手术、冠脉搭桥、心脏搭桥 | Procedure |
| 阿司匹林 | — | 乙酰水杨酸、aspirin、拜阿司匹灵 | Medication |
| 替格瑞洛 | — | 倍林达、ticagrelor | Medication |
| 氯吡格雷 | — | 波立维、泰嘉、clopidogrel | Medication |
| GRACE评分 | — | GRACE风险评分、全球急性冠状动脉事件注册评分 | ScoringScale |
| 心肌梗死溶栓评分 | TIMI评分 | TIMI血流、TIMI危险评分 | ScoringScale |
| 首次医疗接触时间 | FMC | 首次医疗接触、first medical contact | TreatmentTiming |
| 门球时间 | D-to-B | door-to-balloon、门-球时间 | TimeWindow |

### 10.2 归一优先级

同一实体存在多种写法时，主名称选取顺序：

```text
1. 最新权威指南中文版规范全称
2. 本学科基础教材/专科专著规范全称
3. 常见中文标准名（非俗称、非口语）
4. 中文意译名
```

禁止以英文缩写、英文全称或口语化表述作为 `canonical_name`。同一实体只允许一个 `canonical_name`，不允许因来源不同生成两个主名称节点。

### 10.2.1 全局术语字典

`controlled_vocabulary.csv` 是单批次执行词表；全局长期维护必须使用与本 SKILL 文件同目录的 `术语字典/` 作为人工维护主术语库，作为跨批次合并和抽取前注入的标准源。

当前主目录固定为：

```text
E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\术语字典
```

标准目录：

```text
术语字典/
1_疾病同义词表.yaml
2_症状同义词表.yaml
3_体征同义词表.yaml
4_药物同义词表.yaml
5_检查同义词表.yaml
6_手术同义词表.yaml
7_危险因素同义词表.yaml
8_关系类型注册表.yaml（可选；若存在，必须与 Schema 关系类型一致）
9_待审核队列.yaml
```

每个正式字典条目至少包含：

```yaml
- canonical: 标准中文名称
  code: 稳定业务编码
  name_en: 英文标准名
  abbr: [英文缩写, 中文缩写]   # 可选；若 YAML 未单列 abbr，可暂存于 aliases，但生成图谱时必须拆到 abbr
  aliases: [商品名, 旧称, 俗称, 教材用名, 指南写法]
  entityType: Schema实体类型     # 可由文件名推断，但生成 controlled_vocabulary.csv 时必须显式落列
  same_as: []      # 仅存放待人工确认的疑似同义实体
  note: 备注
```

读取规则：

- 执行新批次前，必须先加载 `术语字典/*.yaml`，生成本批次 `controlled_vocabulary.csv` 的初始版本。
- 字典是只读标准源；AI 和脚本不得直接自动修改 YAML 原文，只能输出 `alias_normalization_log.csv`、`term_dictionary_validation_report.csv` 和 `9_待审核队列.yaml` 的新增建议。
- 若抽取发现新术语，应先写入本批次 `controlled_vocabulary_candidate.csv`，状态为 `pending_review`；临床/数据管理员确认后，才能进入全局 YAML 字典。
- `PENDING`、空 code、重复 code、跨实体类型别名冲突、跨 `entityType` 别名冲突，均不得进入正式图谱节点。
- `9_待审核队列.yaml` 只记录人工裁决事项，不视为正式同义词来源；队列中的实体不得自动合并。

合并规则固定为三级确定性：

```text
L1: code 完全相同，可自动合并
L2: 同 entityType 且 aliases 精确命中字典，可自动归一，但不得跨文件、跨实体类型合并
L3: same_as 或疑似语义相近，必须人工确认后才能合并
```

禁止使用 AI 语义相似度自动合并。禁止跨 `entityType` 合并。语义相关但不等价的概念不得合并，例如“呼吸困难”与“端坐呼吸”应保留层级或修饰关系，不得合并为同一节点。

### 10.2.2 药品三层归一规则

`Medication.name` 必须是中文标准通用名或中文标准药物类别名。英文缩写、组合缩写、商品名、剂量写法不得作为 `name`。

药品必须区分三层：

```text
药物类别：β受体拮抗剂、他汀类药物、P2Y12受体抑制剂
通用名药品：美托洛尔、阿托伐他汀、氯吡格雷、替格瑞洛
商品名/俗称：倍他乐克、立普妥、波立维、倍林达
```

建模要求：

- 商品名、英文名、旧称、俗称进入 `aliases`。
- 英文缩写和中文缩写进入 `abbr`，支持多个。
- 药物类别和具体药物不得互相写入 `aliases`。
- `ACEI/ARB`、`DAPT`、`GDMT` 等组合缩写不得作为标准药品节点名。应拆成具体药物类别、具体药物或治疗方案节点。
- 具体药物与药物类别之间必须使用 `Medication has_specific_medication Medication` 表达类别-实例关系；`TreatmentPlan includes_medication Medication` 只表达治疗方案包含某药物，不得替代药物类别成员关系。
- 药物类别 aliases 只能写同义类别名；不得写具体药物、英文缩写或治疗动作词。示例：`溶栓药物.aliases` 可写 `纤溶药物`，不得写 `t-PA`、`rt-PA`、`溶栓治疗`；`抗凝药物.aliases` 可写 `抗凝剂`，不得写 `华法林`、`肝素`。
- 剂量、频次、疗程写入药物节点属性或治疗关系属性，不得生成新的药物节点。

药品命名硬闸门：

```text
Medication.name 为纯英文缩写 → failed
Medication.name 包含 “/” 且表示组合类别 → failed
Medication.name 为商品名 → failed
Medication.name 带剂量/频次 → failed
具体药物只出现在类别 aliases 且无独立节点 → failed
```

### 10.3 抽取阶段归一规则

模型在每次抽取调用前，必须将 `controlled_vocabulary.csv` 中与本次文献疾病范围相关的条目注入 prompt，格式固定如下：

```text
【受控词表（本次抽取必须遵守）】
- "[别名1]" / "[别名2]" / "[缩写]" → 统一输出为：[canonical_name]
- "[别名1]" / "[别名2]" → 统一输出为：[canonical_name]
...
```

**病种案例一：心肌病批次注入示例**

```text
【受控词表（本次抽取必须遵守）】
- "HCM" / "肥厚性心肌病" / "梗阻性肥厚型心肌病" / "HOCM" → 统一输出为：肥厚型心肌病
- "DCM" / "充血型心肌病" → 统一输出为：扩张型心肌病
- "LVEF" / "左室射血分数" / "射血分数" / "EF值" → 统一输出为：左心室射血分数
- "美托洛尔" / "倍他乐克" / "metoprolol" → 统一输出为：美托洛尔
- "Morrow手术" / "心肌切除术" / "外科室间隔减容术" → 统一输出为：室间隔切除术
- "TASH" / "化学消融术" / "室间隔消融" → 统一输出为：酒精室间隔消融术
```

**病种案例二：急性心肌梗死批次注入示例**

```text
【受控词表（本次抽取必须遵守）】
- "AMI" / "心梗" / "心肌梗死" / "急性心梗" → 统一输出为：急性心肌梗死
- "STEMI" / "ST抬高心梗" / "ST段抬高性心肌梗死" → 统一输出为：ST段抬高型心肌梗死
- "NSTEMI" / "非ST抬高心梗" → 统一输出为：非ST段抬高型心肌梗死
- "ACS" / "急性冠状动脉综合征" / "冠脉综合征" → 统一输出为：急性冠脉综合征
- "cTnI" / "cTnT" / "troponin" / "肌钙蛋白" / "hs-cTn" → 统一输出为：高敏肌钙蛋白
- "PCI" / "冠脉介入" / "支架手术" / "球囊扩张" / "PTCA" → 统一输出为：经皮冠状动脉介入治疗
- "CABG" / "搭桥手术" / "冠脉搭桥" / "心脏搭桥" → 统一输出为：冠状动脉旁路移植术
- "拜阿司匹灵" / "乙酰水杨酸" / "aspirin" → 统一输出为：阿司匹林
- "波立维" / "泰嘉" / "clopidogrel" → 统一输出为：氯吡格雷
- "倍林达" / "ticagrelor" → 统一输出为：替格瑞洛
- "D-to-B" / "door-to-balloon" / "门-球时间" → 统一输出为：门球时间
```

模型输出的节点 `name` 字段必须严格使用 `canonical_name`，不得输出别名、缩写或变体写法。

跨句指代消解规则：

- 代词（"该病"、"后者"、"它"）必须还原为 `canonical_name`，不得输出代词作为节点名。
- 简称/缩写在前文已出现全称时，后续统一映射到全称对应的 `canonical_name`。
- 多疾病文献中，章节切换后必须重新绑定当前章节的疾病锚点，不得沿用上一章节的指代。

### 10.4 批次内后处理归一扫描

每批次全部文献抽取完成后，在生成 `nodes_final.jsonl` 之前，必须执行归一扫描脚本，逻辑如下：

**步骤一：别名碰撞检测**
对所有抽取节点，按 `entityType` 分组，将每个节点的 `name` 与受控词表的 `aliases` 字段逐一比对。发现 `name` 命中某条目的别名而非 `canonical_name` 时，自动替换为 `canonical_name` 并记录。

**步骤二：同类型同名重复合并**
替换完成后，对 `entityType + name` 完全相同的节点执行合并：保留首次出现的 `id/code`，将后续重复节点的 `provenance_records` 追加合并，废弃重复节点的技术 ID。

**步骤三：未命中词表的新变体登记**
若某节点 `name` 既不是任何条目的 `canonical_name` 也不在 `aliases` 中，判定为词表未收录变体，写入 `alias_normalization_log.csv`，标记 `status=pending_review`，不自动合并，等待人工确认后更新词表。

归一扫描输出文件：

```text
04_evidence_and_extraction/alias_normalization_log.csv
```

字段：

```text
original_name       抽取时的原始名称
canonical_name      归一后的规范名称（未命中时为空）
entityType
document_id
segment_id
action              replaced | merged | pending_review
reason
```

### 10.5 批次间合并归一

多批次合并到标准主图谱时，归一匹配顺序（与 Schema V1.5 §14.2 一致）：

1. 相同全局 `code`
2. 相同 `entityType` ＋ `canonical_name`
3. 受控别名或外部标准编码（ICD/ATC/LOINC）确认同一实体

无法匹配时进入冲突队列，写入 `conflict_status=open`，不自动合并。禁止仅凭名称字符相似度自动合并不同实体。

合并后必须做服务器级全局重复审计：

- `entityType + name` 同名不同 `code` 的数量必须为 0。
- 若多个批次存在同名同实体，应统一 canonical code 后再导入；不得依赖 Neo4j 前端“看起来相同”。
- 跨疾病重复实体（症状、体征、检查、药物、阈值规则等）必须共享标准 code；疾病归属差异通过多条关系表达，不得复制实体节点。
- 疾病同时属于不同目录时，保留一个疾病实体，允许同时存在多个 `belongs_to_category` / `belongs_to_subcategory` 关系；例如“缺血性心肌病”使用一个 Disease 节点，同时可被冠心病与心肌病相关路径引用。

### 10.6 归一禁止规则

- 禁止将语义相关但不等价的概念强行合并（如"心肌病"不得合并为"肥厚型心肌病"）。
- 禁止跨 `entityType` 合并（名称相同但类型不同的节点不合并）。
- 禁止在词表未更新的情况下，由脚本自动将 `pending_review` 状态条目写入正式节点。
- 批次内归一扫描日志必须在质量审计报告中引用，归一操作须可追溯。

---

## 11. 否定事实与极性过滤

本节规定如何识别和处理文献中的否定、禁忌、条件和不推荐语义，防止将负向陈述误抽取为正向临床关系。

### 11.1 否定语义识别

抽取前，模型必须对每个候选关系判断其极性（`polarity`）。以下触发词出现在关系语境中时，必须触发否定/禁忌语义判断：

**强否定（直接禁止）：**

```text
禁忌、禁止、禁用、不得、不应、不可、不能
contraindicated、prohibited、must not
```

**弱否定（不推荐/慎用）：**

```text
不推荐、不建议、不宜、慎用、避免、不首选、不作为首选
not recommended、should avoid、use with caution
```

**条件否定（特定状态下禁止）：**

```text
除非、仅在…时禁用、…患者禁用、…情况下不适用
```

### 11.2 极性字段写法

所有关系必须填写 `polarity` 字段，取值：

```text
positive     明确正向推荐或存在关系
negative     明确否定、禁忌或不推荐
conditional  在特定条件下成立，条件写入 condition_text
```

对应关系写法规则：

| 语义 | relationType | polarity | 备注 |
|---|---|---|---|
| 推荐使用某药 | `treated_by_medication` | `positive` | 正常写法 |
| 禁忌使用某药 | `has_contraindication` | `negative` | target 为 Contraindication 节点 |
| 特定患者状态下禁用 | `state_contraindicates_medication` | `negative` | source 为 PatientState |
| 不推荐某术式 | `treated_by_procedure` | `negative` | 保留关系但标记 polarity |
| 慎用（条件性） | `treated_by_medication` | `conditional` | condition_text 写明条件 |

**禁止：** 将 `polarity=negative` 的关系写成正向 `relationType`（如把"禁用胺碘酮"抽取为 `treated_by_medication` 且 `polarity=positive`）。

### 11.3 常见易错场景

心肌病文献中高频出现的否定语义，模型容易误判为正向，执行时重点核查：

- "HCM 患者**禁用**纯血管扩张剂" → `state_contraindicates_medication`，`polarity=negative`
- "**不推荐**对梗阻性 HCM 使用硝酸酯类" → `treated_by_medication`，`polarity=negative`
- "DCM **慎用** NSAID" → `treated_by_medication`，`polarity=conditional`，`condition_text=需评估肾功能和心功能`
- "**除非**合并房颤，否则不常规抗凝" → `treated_by_medication`，`polarity=conditional`

### 11.4 否定事实排除规则

以下情况**不生成任何节点或关系**，直接跳过：

- 患者病史阴性陈述（"患者无高血压"、"否认心肌炎病史"）
- 检查结果阴性（"未见明显异常"、"心电图正常"）
- 文献中用于对比的排除标准（"排除继发性心肌病"）

上述内容不得建立节点，不得建立关系，不写入 `nodes_final.jsonl` 或 `relations_final.jsonl`。

### 11.5 否定关系审计

批次完成后，质量审计必须输出否定关系统计：

```text
06_quality_audit/polarity_audit.csv
```

字段：

```text
relation_id
source_code
relationType
target_code
polarity
condition_text
evidence_text
审核状态     auto_passed | pending_review
```

所有 `polarity=negative` 和 `polarity=conditional` 的关系默认标记 `pending_review`，须经人工确认后方可进入合并阶段。

---

## 12. 数值与阈值节点处理规则

本节规定如何处理文献中的数值、单位、阈值和剂量信息，防止产生悬空数值节点或结构化信息丢失。

### 12.1 核心原则

**数值不独立建节点。** 纯数值（"40%"、"30 mmHg"、"5mg"）不得作为独立节点写入图谱。数值必须结构化写入对应实体的专用字段，或封装在 `ThresholdRule` / `Medication` 节点的属性中。

### 12.2 阈值处理规则

文献中出现的指标阈值，必须建立 `ThresholdRule` 节点，字段按 Schema V1.5 §11.1 填写：

```text
indicator_code    对应 ExamIndicator 的 code
operator          枚举：> | >= | < | <= | = | between
value             数值（between 时填低值）
value_high        between 时填高值
unit              单位（mmHg、%、ms、cm、min 等）
condition         阈值适用条件（静息 | 激发后 | 运动后 | 发病后X小时内 等）
patient_state     适用患者状态
time_context      时间上下文（如适用）
```

**通用建模规则：**

- **范围型阈值**（如"30–50 mmHg"）：使用 `operator=between`，`value=30`，`value_high=50`，不拆成两条 ThresholdRule。
- **多条件阈值**（同一指标在不同条件下有不同阈值）：每个条件建立一条独立 `ThresholdRule` 节点，`condition` 字段分别填写，不得合并为一条。
- **时间型阈值**（如"发病12小时内"）：`unit=h`，`condition` 填写适用的临床决策节点（溶栓适应证、再灌注时机等）。

**病种案例一：心肌病常见阈值**

| 文献原文 | operator | value | value_high | unit | condition |
|---|---|---|---|---|---|
| LVOT 压差 ≥ 30 mmHg | `>=` | 30 | — | mmHg | 静息或激发 |
| LVOT 压差 ≥ 50 mmHg | `>=` | 50 | — | mmHg | 静息或激发后，手术适应证 |
| LVEF < 50% | `<` | 50 | — | % | 静息，DCM 诊断标准 |
| LVEF 30–40% | `between` | 30 | 40 | % | 静息 |
| 室壁厚度 ≥ 15 mm | `>=` | 15 | — | mm | 最大室壁厚度，HCM 诊断 |
| 室壁厚度 ≥ 30 mm | `>=` | 30 | — | mm | SCD 高风险因素 |

**病种案例二：急性心肌梗死常见阈值**

| 文献原文 | operator | value | value_high | unit | condition |
|---|---|---|---|---|---|
| 发病 ≤ 12 h 内 | `<=` | 12 | — | h | STEMI 再灌注适应证时间窗 |
| 发病 ≤ 3 h 内 | `<=` | 3 | — | h | 溶栓优先考虑时间窗 |
| D-to-B ≤ 90 min | `<=` | 90 | — | min | 直接 PCI 门球时间标准 |
| FMC-to-B ≤ 120 min | `<=` | 120 | — | min | 首次医疗接触到球囊时间 |
| ST 段抬高 ≥ 1 mm | `>=` | 1 | — | mm | 相邻两个肢体导联，STEMI 诊断 |
| ST 段抬高 ≥ 2 mm | `>=` | 2 | — | mm | 相邻两个胸前导联，STEMI 诊断 |
| hs-cTn 超过第99百分位 | `>` | 99th | — | percentile | 心肌损伤诊断阈值 |
| LVEF ≤ 40% | `<=` | 40 | — | % | AMI 后心功能减低，ICD 适应证评估 |
| GRACE 评分 > 140 | `>` | 140 | — | 分 | 高危 NSTEMI，早期介入指征 |

### 12.3 剂量处理规则

药物剂量信息不独立建节点，必须写入 `Medication` 节点或对应关系的属性字段：

```text
dosage       数值+单位，如"5 mg"、"200 mg"
route        给药途径：口服 | 静脉 | 皮下 | 吸入 | 其他
frequency    给药频次：每日一次 | 每日两次 | 按需 | 其他
duration     疗程（如适用）：长期 | 3个月 | 至手术前
```

单次抽取若只能确定部分字段，其余字段填 `null`，不得凭推断填写未明确的剂量信息。

**禁止：**
- 把"5 mg/d"建成独立节点
- 把不同剂量的同一药物建成两个不同的 `Medication` 节点（剂量差异用关系属性区分，不建重复节点）
- 凭推断填写指南未明确的剂量

### 12.4 评分与量表数值处理

评分量表（如 SCD 风险评分、NYHA 分级）的分级阈值处理：

- 量表本身建 `ScoringScale` 节点
- 各分级/分层建 `ClassificationStage` 节点，通过 `has_classification_stage` 关系连接
- 分级对应的数值阈值建 `ThresholdRule` 节点，挂载在对应 `ClassificationStage` 下
- 不得把"NYHA III级"建成独立的 `Medication` 或 `Disease` 节点

### 12.5 数值质量审计

批次完成后，质量审计必须检查：

- `nodes_final.jsonl` 中是否存在 `name` 字段为纯数值或数值+单位格式的节点 → 发现则标记为错误，阻断该节点入图
- 所有 `ThresholdRule` 节点的 `operator`、`value`、`unit` 字段是否均已填写 → 任一为空则标记 `pending_review`
- 关系属性中 `dosage` 字段格式是否为"数值+空格+单位"标准格式 → 不符合则标记修正

---

## 13. 疾病锚点与证据绑定

抽取前必须建立：

```text
(batch_id, document_id, segment_id, disease_code, pathway_element)
```

禁止按文件顺序、数组索引、相邻窗口或全库关键词命中直接分配疾病。

### 13.1 文献归属

- 标题、章节标题、正文疾病锚点和文档主题必须一致。
- 参考文献、目录、缩写表、并发症或偶然提及不能授予全文疾病归属。
- 多疾病指南必须按章节和局部疾病锚点绑定。

### 13.2 Definition

- 展示定义必须使用中文。
- 原始证据写入 `definition_evidence_text`。
- 英文来源保留英文原文，并记录忠实翻译方法。
- 证据必须命中目标疾病规范名、英文名或受控别名。
- 不得使用版权页、摘要背景、缩写表、参考文献或其他疾病章节作为定义。
- Definition 不依赖 `pathway_element=definition` 单一路径。只要同一证据分段命中目标疾病规范名、英文名或受控别名，并出现“是一类”“是指”“定义为”“为特征”“defined as”“characterized by”等定义句式，必须提升写入 `Disease.description` 和 `definition_evidence_text`。
- 若 required 的 `definition` 缺失，但已纳入证据中存在上述定义句式，缺失原因必须标记为 `EXTRACTION_MAPPING_GAP`，不得标记为 `SOURCE_DOES_NOT_COVER`。
- 若指南/教材没有可靠定义句，但 `scope_taxonomy.csv` 或 `controlled_vocabulary.csv` 已给出中文规范名、英文名、缩写、所属疾病谱系，则必须生成“术语映射定义”作为兜底 `Disease.description`，并标记 `definition_source_type=controlled_vocabulary`、`definition_source=scope_taxonomy.csv;controlled_vocabulary.csv`。该兜底不得伪造成指南证据。
- 术语映射定义只解决中文实体显示和跨语言实体归一，不替代临床定义证据；若后续补充到权威定义句，应以指南/教材定义覆盖兜底定义。
- 在输出 `missing_reason_and_solution.csv` 前，必须逐病种执行 Definition 防漏扫描；未通过该扫描不得宣布批次完成。

### 13.3 实体关系

- 目标实体规范名或受控别名必须在同一证据分段出现。
- 推荐、否定、禁忌和条件语义必须区分，不能把“不推荐”抽取为正向治疗关系。
- `source_name`、`document_id`、`segment_id`、`evidence_text` 必须来自同一 provenance 记录。
- 两个不同疾病出现字符级相同定义或临床证据时，必须阻断并复核。

## 14. 诊疗路径闭环

根据范围配置逐病审计：

- 定义、别名
- 病因、危险因素、病理生理、流行病学
- 症状、体征
- 检查、检验、指标和阈值
- 诊断标准、鉴别诊断
- 分型、分期、风险分层和评分量表
- 治疗方案、具体药物、剂量、操作/介入/手术
- 适应证、禁忌证、时间窗和特殊人群
- 并发症、预后和随访
- 指南、教材和原文证据

每个模块只能标记：`covered`、`missing`、`not_applicable`。必需模块只有在存在有效证据时才算覆盖。

缺失原因使用固定枚举：

```text
SOURCE_NOT_PROVIDED
SOURCE_DOES_NOT_COVER
TEXT_QUALITY_FAILED
OCR_REQUIRED
DISEASE_ANCHOR_UNCLEAR
SCHEMA_UNSUPPORTED
EXTRACTION_RULE_MISSING
EXTRACTION_MAPPING_GAP
HUMAN_CLINICAL_JUDGEMENT_REQUIRED
```

## 15. 数据实例质量闸门

正式批次必须同时满足：

- Schema 外实体、关系和错误方向为 0。
- 节点 `id/code` 全局唯一。
- 同类型同名重复实体为 0。
- 关系语义重复为 0。
- 悬空节点引用为 0。
- 本机路径污染为 0。
- Unicode 替换字符和典型错码为 0。
- 核心关系证据链完整率为 100%。
- 临床关系目标实体在证据分段中的名称/别名命中率为 100%。
- Definition 疾病相关性命中率为 100%。
- 跨疾病来源污染为 0。
- 教材知识伪装为指南正式分级的记录为 0。
- 疾病闭环覆盖矩阵和缺口解决方案已生成。
- `alias_normalization_log.csv` 已生成，`status=pending_review` 的条目已人工处理或明确标注待下批次处理。
- `polarity_audit.csv` 已生成，所有 `polarity=negative` 和 `polarity=conditional` 关系已人工确认。
- `nodes_final.jsonl` 中不存在 `name` 字段为纯数值或"数值+单位"格式的节点。
- Schema P0 实体类型和关系类型必须具备实例，尤其是 `RiskFactor`、`DifferentialDiagnosis`、`has_risk_factor`、`differentiates_from`。
- 药品命名必须通过 §10.2.2 药品三层归一硬闸门。

任一硬闸门失败，不得标记批次完成。

### 15.1 临床表现与实体类型覆盖审计

图谱生成后必须对主要实体类型做覆盖复核，至少包括：

- Disease、DiagnosisCriteria、Etiology、Exam、RiskStratification
- Symptom、Sign
- TreatmentPlan、FollowUp、Prognosis
- Guideline、Evidence、ThresholdRule

执行要求：

- 不得只统计 Evidence 数量。必须检查 `evidence_text` 中已出现的症状、体征、检查、治疗、风险分层、预后等内容是否已实体化为对应节点和关系。
- Symptom 和 Sign 不得只依赖少量初始化词。必须结合指南、共识、路径和本学科基础教材/专科专著章节证据扩展受控词表，常见临床表现应拆成独立实体，而不是只留在 Evidence 文本里。
- 基础教材/专科专著按章节切分出的证据若已带 `disease_code` 和 `disease_name`，可视为疾病上下文已锚定；审计时不得因段落未重复疾病名而误判为疾病相关性失败。
- 若某实体类型数量明显偏低，必须先定位为 `SOURCE_DOES_NOT_COVER`、`EXTRACTION_MAPPING_GAP` 或 `CONTROLLED_VOCABULARY_GAP`，再决定补文献或修复抽取；不得直接进入 Neo4j 导入。

### 15.1.1 维度节点可执行性与视图去重硬闸门

以下问题属于结构可用性失败，不得只靠前端展示层修补：

- `TreatmentPlan` 不得停留在“溶栓治疗、抗凝治疗、治疗方案”等名称层。具体治疗方案必须继续连接 `includes_medication`、`includes_procedure`、`has_timing`、`has_indication`、`has_contraindication` 或 `has_clinical_pathway`。
- 疾病级总方案（如“急性心肌梗死治疗方案”）不得复制该疾病所有药物和操作。总方案应连接 `has_clinical_pathway`；具体药物应挂到“溶栓治疗、抗凝治疗、抗血小板治疗、降压治疗、复律治疗”等具体方案下。
- `Medication` 类别节点必须通过 `has_specific_medication` 连接具体药物；`aliases` 只保存同义类别名，不得保存具体药物、英文缩写或治疗动作词。
- `name`、`preferred_name`、`display_name` 不得使用 `EXAM-TTE`、`PLAN-...`、`MED-...` 等技术编码。技术编码只能写入 `code`；临床展示字段必须使用中文标准名。
- 疾病药物、检查、治疗方案等前端视图和审核统计必须按 `KGNode.code` 或 canonical code 去重。多条临床路径可以作为关系或路径明细保留，但不得把同一节点的多条路径统计为多个药物节点。

必须输出以下审计指标，且结构可用性验收时均应为 0：

```text
semantic_shell_node_relation_count
treatment_plan_actionability_error_count
medication_class_without_specific_count
technical_display_name_error_count
duplicate_semantic_relation_count
view_duplicate_entity_path_count（按疾病+维度+target_code 统计多路径，前端节点数必须用 unique target_code）
```

### 15.2 真实抽检与反向抽查机制

抽检不得只证明“文件能解析、Schema 不报错、节点能导入”。每批次必须同时执行正向和反向检查：

```text
正向检查：图谱节点/关系 → 回查 evidence_text、source_page、document_id
反向检查：原文高频临床词 → 回查是否生成节点、关系、证据链
```

反向抽查必须覆盖：

- 高频症状、体征、危险因素、检查、药物、操作、评分、诊断标准、鉴别诊断。
- 教材章节中的每个疾病画像环节。
- 指南表格、流程图、推荐陈述、阈值和时间窗。

抽检分层：

```text
高置信：字典 aliases 精确命中 + 有 Evidence，抽检 5%
中置信：same_as 或新变体经规则映射，抽检 20%
低置信：字典未命中、新增实体、跨语言映射、药品拆分，100% 人工复核
```

若反向抽查发现原文有高频临床概念但图谱无节点或无关系，批次必须判为不合格，缺失原因不得写成“抽检通过”。

### 15.3 OCR/解析/语义失败原因分型

所有缺口必须归入以下原因之一，不得笼统写 `SOURCE_DOES_NOT_COVER`：

```text
OCR_PARSE_FAILED：原文页或图像未正确识别
SECTION_NOT_PARSED：章节、表格或流程图未进入 clean_text
EVIDENCE_NOT_EXTRACTED：clean_text 有内容，但未进入 evidence_index
ENTITY_NOT_MAPPED：evidence 有内容，但未生成实体
RELATION_NOT_BUILT：实体有内容，但未建立疾病关系或路径关系
CONTROLLED_VOCABULARY_GAP：受控词表/术语字典缺少标准项或别名
SCHEMA_UNSUPPORTED：Schema 无法表达该知识
SOURCE_DOES_NOT_COVER：已确认原文确实没有覆盖
CLINICAL_JUDGEMENT_REQUIRED：需要临床专家判断
```

判定顺序固定：

```text
先查 OCR/页面解析 → 再查章节覆盖 → 再查 evidence_index → 再查实体映射 → 再查关系构建 → 最后才允许判定文献未覆盖
```

### 15.4 证据归因审计

教材和指南证据必须检查来源页码与疾病章节是否匹配。若证据来自其他疾病章节、参考文献、目录、缩写表、肺栓塞等非目标疾病内容，却关联到当前疾病，必须判为跨疾病来源污染。

每批次必须输出或更新：

```text
source_attribution_audit.csv
```

字段：

```text
disease_code, disease_name, evidence_id, document_id, source_page,
expected_section_or_page_range, evidence_text,
attribution_status, failure_reason, action
```

### 15.5 满分闭环覆盖要求

每个疾病至少审计以下闭环环节：

```text
definition
etiology
risk_factor
pathophysiology
epidemiology
symptom
sign
exam
lab_test
diagnosis_criteria
differential_diagnosis
risk_stratification
scoring_scale
classification_stage
treatment_plan
medication
procedure
indication
contraindication
prognosis
follow_up
clinical_pathway
guideline
evidence
```

P0 环节 `risk_factor` 和 `differential_diagnosis` 不得长期缺失。若 Schema 已定义但本批次没有实例，必须说明是来源不足、抽取遗漏、Schema 配置未启用，还是需要专家裁决。

## 16. 独立批次交付

每个任务创建独立 `batch_id` 和版本化输出目录。以后新增的本地文件夹必须采用“中文说明_英文技术名或批次号”的双语可读命名；中文用于人工识别，英文技术名或 batch_id 用于脚本稳定、跨系统检索和审计追踪。

推荐实际目录至少包含：

```text
00_范围配置_scope_and_config/
01_来源清单_source_manifest/
02_页面质量审计_page_audit/
03_清洗文本_clean_text/
04_证据抽取_evidence_and_extraction/
05_图谱数据实例_data_instance/
06_质量审计_quality_audit/
07_审核交付包_review_package/
08_Neo4j导入_neo4j_import/
```

批次父目录命名规则：

```text
{中文疾病大类或病种}图谱_{batch_id}/
```

示例：

```text
心肌病图谱_BATCH-CARD-CM-20260622-001/
冠心病图谱_BATCH-CARD-CAD-20260623-001/
00_学科基础骨架库_foundation_skeleton/
```

必须遵守：

- 中文说明放在前面，英文技术名或批次号放在后面。
- 保留稳定 `batch_id`，但不能只用纯英文缩写作为人工交付目录名。
- 目录名不得使用空格；允许中文、英文字母、数字、下划线 `_`、连字符 `-`。
- 脚本内部字段名、CSV 字段名、Neo4j 属性名仍保持英文技术名；本地目录可通过英文后缀识别。
- 历史目录不强制重命名；若确需重命名，必须同步更新批次登记台账、审计文件路径、导入摘要、脚本配置和交付报告，禁止只改文件夹名。

核心文件：

- `scope_taxonomy.csv`
- `source_documents_manifest.csv`
- `page_audit.jsonl`
- `document_quality_audit.csv`
- `clean_text/*.clean.txt`
- `segment_index.jsonl`
- `nodes_final.jsonl` / `nodes_final.csv`
- `relations_final.jsonl` / `relations_final.csv`
- `graph_final.json`
- `disease_pathway_coverage.csv`
- `missing_reason_and_solution.csv`
- `source_conflict_register.csv`
- `schema_gap_register.csv`
- `quality_gate_summary.json`
- `专家审核说明.md`

### 16.1 来源清单便捷入口（强制）

每批次完成来源筛选后，必须在专科输出集合根目录生成便捷来源清单，不能只放在批次子目录深层路径。

命名格式：

```text
{scope_target}PDF来源清单.md
{scope_target}PDF来源清单.csv
```

示例：

```text
心血管内科文献集合/心肌病PDF来源清单.md
心血管内科文献集合/心肌病PDF来源清单.csv
```

清单必须至少包含：

- 批次编号
- 正式纳入 PDF 数量
- 原始明细 `source_documents_manifest.csv` 路径
- `document_id`
- 文件名
- 来源类型
- 原始绝对路径

最终回复和批次登记台账必须主动给出该清单路径。

批次登记台账还必须直接写入正式纳入的 PDF/文献文件名清单；不能只写“见某某清单”。路径很长时，台账至少保留 `document_id`、`source_type`、`file_name`，完整路径可同时放在根目录便捷清单。

### 16.2 导入交接包（强制）

每次生成 `05_data_instance/` 后，必须同步生成并主动交付导入交接包，不能等待用户追问。

必须输出文件：

- `07_review_package/可导入图谱文件清单.md`

该文件必须包含：

- 批次编号、范围、Schema/SKILL版本
- 测试库导入结论：`可以导入` 或 `不可以导入`
- 若不可以导入：逐条列出阻断原因、对应文件、是否可修复、修复动作
- 若可以导入：明确列出可导入图谱文件的绝对路径
- 最小导入文件：`nodes_final.jsonl`、`relations_final.jsonl`
- 辅助导入文件：`graph_final.json`、`nodes_final.csv`、`relations_final.csv`
- 审核必带文件：`quality_gate_summary.json`、`disease_pathway_coverage.csv`、`missing_reason_and_solution.csv`、`source_conflict_register.csv`
- Neo4j 导入脚本或命令文件路径（如已生成）

最终回复必须主动给出以下最小清单：

```text
测试库导入：可以/不可以
正式CDSS上线：可以/不可以
节点文件：绝对路径
关系文件：绝对路径
完整图文件：绝对路径
质量审计：绝对路径
导入交接包：绝对路径
```

若 token 即将不足，优先输出上述最小清单，不得只输出过程描述。

### 16.3 大图谱数据版本与增量修复规则

`nodes_final.jsonl`、`relations_final.jsonl`、`graph_final.json` 是阶段快照，不得作为日常小修复的唯一工作对象。大文件超过 50MB 或关系文件超过 100MB 时，日常修复必须优先采用增量包：

```text
delta_nodes_upsert.jsonl
delta_nodes_delete.jsonl
delta_relations_add.jsonl
delta_relations_delete.jsonl
delta_manifest.json
```

增量包必须记录：

- 基线批次和基线文件 hash。
- 变更原因和关联步骤记录。
- 变更来源：教材回捞、指南补充、人工审核、服务器去重或前端修复。
- 每条新增临床关系的 evidence/provenance。
- 应用前后节点数、关系数、重复数、空壳数、正式 CDSS 阻断项。

阶段验收时再将“基线快照 + 已审核增量包”合成为新的 `nodes_final.jsonl` 和 `relations_final.jsonl`。不得为 1～数十条关系反复重写数百 MB 快照作为常规流程。

版本管理边界：

- SKILL、Schema、脚本、测试、步骤记录、踩坑日志、审计摘要、manifest 必须纳入 Git/GitHub 或等价版本管理。
- 大图谱快照不建议直接进入普通 Git 主仓；应使用制品目录、hash 清单、压缩包、对象存储或 Git LFS。
- 若使用 GitHub，仓库必须为私有仓库；不得上传含患者隐私、未脱敏临床数据或受版权限制的原文全文。
- GitHub 自动化不得使用明文账号密码；必须使用 SSH key、浏览器登录授权、GitHub CLI 授权或细粒度 Personal Access Token。任何密码、Token、Cookie、Neo4j 密码不得写入 Git、步骤记录、踩坑日志或命令文件。
- 每次可导入图谱交付必须提供版本号、批次号、数据 hash 和增量包路径，便于回滚。

Neo4j delta 导入规则：

- 增量包必须同时考虑节点和关系：新增实体、别名修正、属性修正写入 `delta_nodes_upsert.jsonl`；新增临床关系写入 `delta_relations_add.jsonl`；两者必须由 `delta_manifest.json` 统一登记。
- `delta_nodes_upsert.jsonl` 必须按全局 `code` 去重。同一节点如果来自多个批次，只能在 delta 包中出现一次；导入时执行节点 upsert，不得创建同 code 多节点。
- 增量包中的节点和关系一律不得标记 `formal_cdss_ready=true`。未完成临床专家审核的补丁只能进入测试库工作版本。
- 增量关系导入前必须先按 `(source.code, relationType, target.code)` 查询服务器是否已有同义语义边。
- 若已有同义语义边但缺少标准 `id/provenance`，应更新该语义边或先删除旧边后写入标准边；不得仅按新关系 `id` 执行 `MERGE`。
- 导入后必须验证目标语义键 `count(r)=1`，并全库验证 `duplicate_semantic_keys=0`。
- 若发现旧边证据属于误判证据，不得合并进标准 provenance，应登记删除原因并保留清理记录。

Required 缺口闭环冲刺规则：

- 每次样板图谱或新病种生成后，必须读取 `disease_pathway_coverage.csv`，逐项列出 required 缺口。
- 每个 required 缺口必须回查本批指南 evidence index、教材 evidence index 和基础骨架候选索引；不能只看审计里的 `SOURCE_DOES_NOT_COVER`。
- 反查命中同病种原文但 pathway 标注不准时，归类为“抽取/映射漏掉”，进入策展补丁或重新抽取；不得继续声称文献不覆盖。
- 策展补丁必须明确：新增/更新节点、关系、证据文本、来源名称、页码、segment_id、证据等级字段、`clinical_review_status=pending_clinical_review`、`formal_cdss_ready=false`。
- 没有明确原文支持的 required 项不得硬补。例如仅出现“及时发现/及早治疗”不能自动生成“随访方案”；必须继续阻断正式 CDSS。
- 策展补丁应用后必须重跑本地审计；至少验证 required 缺口变化、target_name_or_alias_match、duplicate_code、duplicate_semantic_relation、semantic_shell、technical_display_name、local_path_pollution。

临床使用效果审核规则：

- 每批图谱生成或修复后，必须同时生成两类审核资料：
  - 详细追溯包：`clinical_review_items.csv`、`clinical_review_summary.json`，用于数据团队回写和证据追溯。
  - 简化使用效果审核包：`00_审核说明_先看这个.md`、`01_疾病级使用效果审核表.csv`、`02_场景级推荐审核卡.csv`、`03_药师专项审核清单.csv`、`clinical_effect_review_summary.json`，用于临床专家和药师快速审核。
- 临床专家主入口不是 Neo4j 网络图，也不是逐条边审核；主入口必须是：
  - 疾病级：判断该病种图谱能否作为辅助诊疗参考、整体风险等级、是否可试用。
  - 场景级：按治疗方案、药物治疗、手术/操作、随访、临床路径等场景确认是否符合临床使用效果。
  - 药师专项：药物标准名/别名、剂量、禁忌、相互作用必须单独给药师审核。
- 边级 `clinical_review_items.csv` 只用于追溯到具体关系、证据、字段缺口和回写脚本，不得作为专家日常主审核界面。
- 专家审核表建议使用明确枚举：`可试用`、`仅参考`、`需修改`、`禁用`。只有审核表中 reviewer_name、reviewer_role、reviewed_at、decision 和 comment 完整，且 decision 允许回写时，脚本才可把对应推荐关系更新为 `clinical_approved` 或等价状态。
- 使用效果审核只能确认“该场景是否可用于辅助诊疗参考”；不能替代药物剂量、禁忌、相互作用、推荐等级/证据等级、适用人群、排除条件等字段的结构化补全。
- 若 required 缺口为 0，但仍存在 `pending_clinical_review` 或 CDSS 推荐字段缺口，本批只能进入测试库工作版本，不得进入正式 CDSS 推荐层。

多智能体协作与 Trae 前端审核边界：

- Codex 是图谱建设主控 agent，负责 Schema/SKILL、抽取规则、证据裁决、回写脚本、本地审计、Neo4j 导入、服务器硬闸门和正式 CDSS 判定。
- Trae 可作为并行工程 agent，负责前端页面、审核表展示、筛选搜索、CSV/JSON 导出、PDF 清单整理、OCR 质量报告、术语候选和候选缺口清单。
- Trae 不得直接写 Neo4j；不得直接修改 `nodes_final.jsonl`、`relations_final.jsonl`、delta 包；不得把候选关系直接变成正式图谱；不得设置 `formal_cdss_ready=true`；不得批量把 `pending_clinical_review` 改为 `clinical_approved`。
- Trae 审核页面必须读取 Codex 生成的 `clinical_review_frontend_data.json`，只导出 `clinical_review_decisions_export_*.csv/json`。
- Codex 收到 Trae 导出的审核结果后，必须先校验 review_id、batch_id、relation_id、审核人、审核角色、审核时间、备注规则，再转换为 detail 级回写 CSV。
- 疾病级和场景级审核只表示临床使用效果判断；只有 detail 级 `approve` 且字段完整的行，才允许进入 `apply_clinical_review_decisions.py` 回写。
- 多 agent 任务必须遵循“候选/展示/导出可并行，证据裁决/回写/导入必须串行由 Codex 控制”的原则。

新病种启动预检规则：

- 每次开始新专科、新疾病大类或单病种前，必须确认：顶层学科、scope_type、scope_target、PDF/指南来源路径、教材/基础骨架路径、本批输出路径、Schema 主文件、SKILL 主文件。
- 推荐运行 `scripts/preflight_new_disease_batch.py` 或按同等字段生成预检记录。预检失败不得开始解析 PDF。
- 每批生成后必须主动输出可导入图谱文件：`nodes_final.jsonl`、`relations_final.jsonl`、`quality_gate_summary.json`、`delta_manifest.json`、`delta_nodes_upsert.jsonl`、`delta_relations_add.jsonl`、详细追溯审核包路径、临床使用效果审核包路径、Claude/外部模型审核包路径。
- 创建批次目录后必须复核 `00_scope_and_config/batch_config.json`：`schema_version` 必须等于 `专科知识图谱Schema标准.md` 当前版本；`skill_version` 必须等于 `AI自动化工具-文献指南解析.md` 当前版本。发现硬编码旧版本必须立即修复脚本和已生成配置。
- 新批次正式开始解析前必须输出纳入文献清单，至少包括文件名、来源类型、扩展名和大小；纳入数异常时先检查 scope aliases 和路径匹配规则。

## 17. 受控合并

从零开始时建立空的标准主图谱。后续批次通过验收后才能合并。

- 节点按全局 `code`、规范名称和受控别名归一。
- 关系语义键为 `(source.code, relationType, target.code)`。
- 多来源证据合并到同一语义关系，完整保留 provenance。
- 属性冲突不得静默覆盖，写入冲突台账。
- 合并前生成主图谱快照，失败时回滚。
- 抽取阶段不读取其他批次中间文本；合并阶段读取当前标准主图谱进行去重和一致性检查。

## 18. Neo4j 可选阶段

默认在标准数据实例和审核报告处停止。

只有用户明确确认验收通过并要求导入后，才执行：

1. 备份当前 Neo4j。
2. 预演节点、关系、约束和索引。
3. 以 `code` 作为业务唯一键导入。
4. 执行全库 Schema、重复、证据、路径和计数审计。
5. 输出导入验收报告。

禁止边解析边写正式数据库。

### 18.1 测试库修复同步规则

当用户要求“同步服务器图谱数据库”“导入测试库”或“修复后直接导入”时，必须先确认目标是测试库还是正式库。测试库可执行替换导入；正式库必须走备份、变更评审和回滚方案。

测试库最终同步不得只用普通合并作为完成口径。若目标是“本批次修复后的最终状态”，必须使用以下策略：

- 固定执行口径：KGNode 子图级替换导入 + 请求级重试 + 小批次补导入 + 服务器统计验收。
- 先完成本地质量门禁；结构/语义硬错误必须为 0。若因 required 缺口或 `clinical_review_status=pending_clinical_review` 导致 `quality_gate_status=failed`，允许同步测试库工作版本，但必须明确标注“不得进入正式 CDSS 推荐层”。
- 对测试库执行 `KGNode` 子图级替换导入，删除旧 `KGNode` 节点及其关系后再导入当前审计通过版本。
- 导入脚本必须支持请求级重试，避免 HTTP/Bolt 瞬时超时导致半导入。
- 大批量关系导入必须允许调小批次；发生中断时，先查询服务器现有节点/关系计数，再通过幂等补导入恢复，不得盲目重复清库。
- 导入后必须从 Neo4j 服务器重新统计节点数、关系数、实体类型计数和关系类型计数；最终统计以服务器查询结果为准，不以本地文件行数替代。服务器全库必须满足 `all_node_count == kg_node_count`、`all_relation_count == kg_relation_count`。
- 导入后必须额外复核：非 `KGNode` 节点数=0、触达非 `KGNode` 的关系数=0、语义空壳关系数=0、治疗方案无下游实体=0、药物类别无具体药物=0、技术编码显示名=0、药物类别 aliases 污染=0、药物类别到具体药物 `has_specific_medication` 可查、`entityType+name` 全局重复=0、服务器关系语义键重复=0、标签元数据 mismatch=0。
- 服务器合并多个批次后，必须按 `(source.code, relationType, target.code)` 去重关系；不得让骨架库和疾病批次的同义关系重复存在。
- 前端图谱接口必须按节点 `code` 去重返回节点集合；关系路径可以保留多条，但“药物数量、检查数量、症状数量、治疗方案数量”等节点计数必须使用唯一节点数。
- 必须写入 `08_neo4j_import/neo4j_import_summary.json`；如发生中断和补导入，还必须在同步报告中说明中断原因、恢复动作和最终一致性结果。

## 19. 执行红线

- 范围或路径未确认就开始处理。
- 使用非本次确认来源生成知识。
- 文本质量失败仍继续抽取。
- 用文档级关键词命中代替章节级疾病绑定。
- 把教材内容写成指南正式推荐等级。
- 把疾病特异字段加入统一核心 Schema。
- 先导入 Neo4j、后补质量审计。
- 抽样无问题就宣称全库无污染。
- 缺少原文证据仍生成核心临床关系。
- 受控词表未加载就开始抽取，或抽取后未执行批次内归一扫描。
- 将 `polarity=negative` 的否定/禁忌关系写成正向 `relationType`。
- 把纯数值或"数值+单位"建成独立节点写入图谱。

出现任一红线，立即停止并输出阻断原因。
