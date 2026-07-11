# 2026-07-07 21:50:00 RecommendationStatement 迁移落地与显示名重复修复

| 时间 | 影响范围 | 错误/风险表现 | 根因 | 修复动作 | 验证证据 | 复用规则 | 已同步 |
|---|---|---|---|---|---|---|---|
| 2026-07-07 21:50:00 | CDSS 推荐证据模型、Neo4j、Trae 前端、SKILL、专病 CDSS 方案 | 如果前端从 `Disease -> Evidence` 或 `Action -> Evidence` 取推荐依据，会把疾病/动作证据池一箩筐展示给医生；初次迁移后还出现 31 组 `RecommendationStatement` 同类型同名重复，如“抗凝治疗推荐”“溶栓治疗推荐” | 把“动作是什么”和“在什么场景下为什么推荐该动作”混在一起；推荐陈述显示名只用了动作名，没有规则/阶段上下文和动作类型 | 迁移 291 个 `RecommendationStatement` 到服务器 Neo4j；建立 `ClinicalRule -> has_recommendation_statement -> RecommendationStatement -> recommends_action/blocks_action + derived_from Evidence + based_on_guideline Guideline`；将推荐陈述显示名改为“规则或阶段上下文｜动作名（动作类型）推荐/阻断”；生成 `Trae前端开发全局提示词.md` | 最终全库硬闸门：`non_kgnode_node_count=0`、`technical_display_name_error_count=0`、`duplicate_type_name_count=0`、`duplicate_semantic_relation_count=0`、`blocking_issue_count=0`、`global_safety_gate_status=passed`；专项校验：RecommendationStatement=291、无动作=0、无证据=0、无指南匹配=0、未迁移候选=0 | 正式 CDSS 推荐必须以 `RecommendationStatement` 为根；推荐陈述显示名必须含规则/阶段上下文和动作类型；前端展示单条推荐证据，不展示疾病级或动作级证据池；同名动作跨规则不得合并推荐陈述 | SKILL V1.42、专科 CDSS 六级方案 V1.7、Trae 全局提示词 V1.0、迁移执行报告、步骤记录 |

---

# 2026-07-07 22:48:44 缓慢性心律失常批次导入后复盘

| 时间 | 影响范围 | 错误/风险表现 | 根因 | 修复动作 | 验证证据 | 复用规则 | 已同步 |
|---|---|---|---|---|---|---|---|
| 2026-07-07 22:48:44 | 缓慢性心律失常及传导阻滞批次、Neo4j 累计库、术语字典、批次台账 | 本地质量门禁通过并导入服务器后，服务器全局仍出现 3 组跨批次 `entityType+name` 重复；alias 增量只写入批次 JSONL/Neo4j，未及时回写 `术语字典`；`批次登记台账.md` 顶部汇总仍停留在早期批次。 | 我把“本地批次通过”误当成“累计库无新增冲突”；术语 alias 没有形成“JSONL/Neo4j/术语字典三处一致”的硬流程；批次结束缺少固定交接清单。 | 执行 `dedupe_neo4j_type_name_nodes.py`，保留骨架库实体并迁移本批次关系，删除 3 个重复节点；服务器硬闸门复测 passed；新增 `scripts/validate_terminology_dictionaries.py`，修复药物字典 PENDING 重复编码，新增 `8_路径与治疗方案同义词表.yaml`；更新 `批次登记台账.md` 和缓慢性批次来源清单。 | 服务器复测：`kg_node_count=35858`、`kg_relation_count=108057`、`duplicate_type_name_count=0`、`duplicate_semantic_relation_count=0`、`blocking_issue_count=0`、`global_safety_gate_status=passed`；术语字典校验：9 个文件、blocking=0、warning=0、passed。 | 每批次导入后必须跑累计库硬闸门，不得只看本地审计；alias 新增/合并必须同步回写术语字典并跑术语字典校验；批次完成必须更新批次登记台账、正式纳入来源清单、步骤记录和踩坑日志。 | 脚本、术语字典、批次台账、来源清单、步骤记录 |

---

---

## 2026-07-08 08:34:30 追加记录：教材骨架锚点矩阵与 P0 definition 修复

- 影响范围：教材骨架锚点矩阵、P0 definition 修复输入、心血管内科四类优先验证集。
- 错误表现：
  - `不稳定型心绞痛` 可能被简单子串误吸附到 `稳定型心绞痛`。
  - `心力衰竭` 定义在章标题后、第一节前，若只识别节级会漏抽。
  - `不稳定型心绞痛和非 ST 段抬高型心肌梗死` 这类合并标题不能直接拆成两个单病种精确定义入库。
- 根因：抽取算法过度依赖标题/关键词相似度，未区分否定词、章级 overview、合并标题和单病种标题。
- 修复动作：
  - 新增 `scripts/build_textbook_skeleton_anchor_matrix.py`。
  - 支持章级、节级、条目级锚点。
  - 过滤“本章数字资源”等噪声。
  - 新增否定词误吸附保护。
  - 合并标题降级为待复核候选。
  - 生成教材目录、P0 锚点矩阵和 definition 修复 JSONL；本轮未写 Neo4j。
- 验证证据：
  - `textbook_cardiology_chapter_outline_20260708.csv`
  - `textbook_skeleton_matrix_priority_four_20260708.csv`
  - `p0_definition_repair_input_priority_four_20260708.jsonl`
  - 68 个 P0 疾病中：25 条可抽样后导入、18 条待复核、17 条需人工锚点、8 条需指南/权威来源补充。
- 复用规则：
  - 疾病定义抽取不得只用关键词。
  - 带“不/非”等否定前缀的相似名称必须阻断自动匹配。
  - 章级 overview 必须纳入骨架抽取。
  - 合并标题只能作为候选证据，不得直接作为单病种精确定义。
  - 四类优先验证通过后，自动扩展到心血管内科全疾病。
- 已同步：Schema V1.11、SKILL V1.44、步骤记录、P0 锚点矩阵。

---

---

## 2026-07-08 09:07:00 追加记录：严格 definition delta 与导入前硬闸门

- 影响范围：教材 definition 修复、Neo4j 写库前安全控制。
- 风险表现：前一阶段的 `p0_definition_repair_input_priority_four_20260708.jsonl` 同时包含 `ready_for_review` 候选，若直接写库，会把合并标题/待复核内容误写进 `Disease.definition`。
- 根因：修复输入文件用于“复核工作流”，不是最终导入包；文件名未明确区分“候选输入”和“严格 delta”。
- 修复动作：
  - 新增 `scripts/build_textbook_definition_delta.py`。
  - 只筛选 `ready_for_import_after_sampling`。
  - 生成独立 delta 目录 `20260708_textbook_definition_delta`。
  - 导入前硬闸门通过后，额外做服务器只读预检查。
- 验证证据：
  - 严格候选数 25。
  - delta 数 25。
  - 阻断错误 0。
  - 服务器 Disease code 缺失 0。
  - 服务器 Disease code 重复 0。
  - 服务器现有 definition 非空 0。
- 复用规则：
  - 候选复核 JSONL 不得直接作为导入输入。
  - 图谱写库必须使用单独 delta 包。
  - delta 包必须有导入前硬闸门和服务器只读预检查。
  - 写库后必须立即跑服务器硬闸门。

---

---

## 2026-07-08 09:12:00 追加记录：严格 definition delta 写入服务器

- 影响范围：心血管内科优先四类教材 definition、服务器 Neo4j。
- 执行动作：将 25 条 `ready_for_import_after_sampling` 严格 delta 写入服务器测试库。
- 验证证据：
  - 服务器更新数 25。
  - 写入后硬闸门 passed。
  - blocking_total 0。
  - 优先 68 疾病中 definition 已补齐 25，仍缺 43。
- 复用规则：
  - 写库后必须立即跑服务器硬闸门。
  - 写库后必须输出“已补齐/仍缺失”范围级统计。
  - 剩余缺口不得用低置信候选凑数，必须分 `ready_for_review`、`needs_manual_anchor_review`、`needs_guideline_or_manual_source` 三类推进。

---

---

## 2026-07-08 09:19:00 追加记录：下级条目识别与定义句打分修复

- 影响范围：教材 definition 自动锚定。
- 错误表现：冠状动脉痉挛、窦性心动过缓等有教材定义，但早期抽取未识别为下级疾病条目，或选中了诱发因素/伴随表现句。
- 根因：条目识别关键词不全；definition 句子打分把普通“是”与“是指/称为/是一类”同等处理。
- 修复动作：扩展条目识别关键词；提高强定义句权重；降低诱发因素、治疗、伴随表现等非定义句权重。
- 验证证据：新增 3 条严格 delta 写入服务器，写入后硬闸门 passed；优先 68 疾病 definition 已补齐 28，仍缺 40。
- 复用规则：教材条目抽取要覆盖章、节、下级条目；definition 句必须优先选择定义句型，不得用诱因、治疗、伴随表现句替代。
---

---

## 2026-07-08 20:40:00 追加记录：教材 definition 剩余 40 条人工校准与写库

| 时间 | 影响范围 | 错误/风险表现 | 根因 | 修复动作 | 验证证据 | 复用规则 | 已同步 |
|---|---|---|---|---|---|---|---|
| 2026-07-08 20:40:00 | 心血管内科教材骨架库、Disease.definition、服务器 Neo4j、后续全学科骨架抽取 | 自动候选中存在三类风险：1）合并标题被误当作单病种定义；2）鉴别诊断列表或病因列表中的疾病名被误当作定义；3）章节类目被误当作疾病定义。若直接写库，会污染 `Disease.definition`。 | 早期抽取偏重关键词命中和相邻句，未强制区分“定义句、分类句、列表提及、章节标题、鉴别诊断提及”。 | 新增 `scripts/build_textbook_definition_curated_delta.py`；对剩余 40 条逐条回到《内科学（第10版）》原文段落校准；只将 30 条有明确定义句或分类定义句的疾病写入服务器；10 条证据不足继续阻断。 | 服务器写入 30 条，硬闸门 passed，blocking_total=0；优先 68 疾病 definition 非空从 28 提升到 58；剩余 10 条全部有阻断理由。 | `Disease.definition` 只能来自明确定义句或分类型定义句；鉴别诊断列表、病因列表、章节标题不得写入 definition；人工校准 delta 必须保留 docx 段落、PDF 页码、source_section_path、skeleton_slot、knowledge_layer；写库前必须查唯一性和是否覆盖，写库后必须跑硬闸门。 | 步骤记录、脚本、服务器导入结果、阻断清单 |

---

---

## 2026-07-08 22:05:00 追加记录：外部权威来源补定义与条件性入库

| 时间 | 影响范围 | 错误/风险表现 | 根因 | 修复动作 | 验证证据 | 复用规则 | 已同步 |
|---|---|---|---|---|---|---|---|
| 2026-07-08 22:05:00 | 心血管内科外部权威资料库、Disease.definition、服务器 Neo4j、后续全学科权威补充流程 | 教材未覆盖的疾病/谱系/临床状态若强行从章节标题、鉴别诊断列表或百科摘要补 definition，会造成“看似补齐、实际证据污染”。 | 既有流程只有教材锚点修复，没有外部权威白名单、下载登记、来源分级、条件性入库规则；网页来源容易被误认为专家共识。 | 新建外部权威目录、白名单、命名规范；下载 ESC、ACC/AHA/HRS、EHRA/HRS/APHRS/SOLAECE、GeneReviews、国家罕见病指南、中华肾脏病杂志指南等资料；生成人工候选定义表；高可信 6 条、条件性 5 条写入服务器。 | `server_postcheck_external_authority_definition_final_20260708.json`：checked_count=11，definition_empty_count=0，high_confidence_count=6，conditional_count=5。 | 外部权威补充必须先建白名单和本地留档；百度健康医典只能作为患者教育/别名/辅助来源，不得作为正式推荐证据；谱系分型、人群限定状态必须标 `definition_confidence=conditional`；条件性 definition 可消除空值缺口，但不得自动进入正式 CDSS 推荐触发。 | 步骤记录、外部权威目录、白名单、候选表、delta、服务器复核结果 |

---

---

## 2026-07-09 09:20:00 追加记录：项目运行环境与教材骨架重建启动

| 时间 | 影响范围 | 错误/风险表现 | 根因 | 修复动作 | 验证证据 | 复用规则 | 已同步 |
|---|---|---|---|---|---|---|---|
| 2026-07-09 09:20:00 | 全项目脚本执行环境、心血管内科教材骨架重建 | 如果继续混用 Codex 缓存 Python 和项目 Python，后续多账号交接、依赖安装、脚本复现会不稳定；骨架信息若只做关键词统计，不做教材槽位矩阵，会继续出现“看起来有数据、临床闭环不稳”。 | 早期为了快速推进，部分抽取和审计使用了 Codex 缓存 Python；教材骨架缺少统一 G1 完成标准。 | 新增 `项目运行环境规则.md`；后续正式项目脚本统一切换到 `D:\Program Files Ai\python-venvs\medical-kg\Scripts\python.exe`；补齐项目 Python 的 `python-docx/pdfplumber/pypdf/neo4j`；启动 `心血管内科基础骨架库重建_CARD-SKELETON-20260709`，生成章节目录和 G1 骨架槽位初筛矩阵。 | 项目 Python 复核通过；章节目录 119 行、覆盖矩阵 1140 行、覆盖汇总 57 行；服务器统计为只读执行，未写 Neo4j。 | 正式项目脚本必须写明 Python 路径；缺包安装到 `D:\Program Files Ai\python-venvs\medical-kg`；G1 先输出“疾病/章节 × 骨架槽位 × 是否覆盖 × 来源页码 × 是否可用于 CDSS”的矩阵，不能直接把关键词命中当成最终实体化。 | 步骤记录、运行环境规则、输出目录 manifest、项目 Python 复核文件 |

---

---

## 2026-07-09 10:10:00 追加记录：目录容器误判与DOCX拆行标题父级错误

| 时间 | 影响范围 | 错误/风险表现 | 根因 | 修复动作 | 验证证据 | 复用规则 | 已同步 |
|---|---|---|---|---|---|---|---|
| 2026-07-09 10:10:00 | 教材目录抽取、G1深审计、结构化候选入库前质量控制 | 1）“房性心律失常、室性心律失常”等上级分类容器被当作具体专病，导致虚假 required 缺口；2）“第一节动脉粥样硬化”因 DOCX 标题拆行被挂到“第三章心律失常”。 | 早期审计只看章节名称，没有判断是否有下级条目；DOCX 中“第四章”与完整章名拆成多段，目录生成时过滤了短标题。 | 修正 G1 审计脚本：有下级条目的对象标记为 `category_container`，不按专病闭环要求；修正本地目录/审计/证据元数据中的“第一节动脉粥样硬化”父级与页码；生成目录父级修正记录。 | 补抽后 G1：ready 从 13 提升到 37；needs_backfill 从 31 降到 7；container 12；no_candidate 1。修正记录：`阶段C3_目录父级修正记录_20260709.json`。 | 教材目录抽取必须识别“拆行章标题”；G1 审计必须区分“分类容器”和“具体疾病”；任何父级修正后，进入 curated delta 前必须重新生成稳定 ID，不得直接使用旧候选入库。 | 步骤记录、踩坑日志、交接文件、批次台账 |

---

---

## 2026-07-09 11:05:00 追加记录：心电图定义型心律失常审计规则

| 时间 | 影响范围 | 错误/风险表现 | 根因 | 修复动作 | 验证证据 | 复用规则 | 已同步 |
|---|---|---|---|---|---|---|---|
| 2026-07-09 11:05:00 | 心律失常教材骨架、G1深审计、后续全专科疾病骨架审计 | 窦性心动过速、窦性心动过缓、房室交界性期前收缩等 ECG 定义型心律失常，教材重点是心电图诊断和处理，若强制要求“临床表现”槽位，会制造虚假缺口。 | G1 审计最初按普通疾病闭环统一要求，未区分“临床综合征型疾病”和“心电图定义型疾病/状态”。 | 新增 `ecg_defined_arrhythmia` 审计类型；C4 对剩余缺口从教材原文精修；对动脉粥样硬化补入防治/药物/介入内容；对心律失常条目补入 ECG 诊断组件。 | C4 后 G1：ready=44，container=13，needs_backfill=0，no_candidate=0，missing_group_counter 为空。 | 疾病骨架完成标准不能机械套同一模板；必须按疾病/状态类型使用不同必备槽位。ECG 定义型疾病以 definition + exam/lab + diagnostic component + treatment 为核心闭环，不强制症状体征。 | 步骤记录、踩坑日志、交接文件、批次台账 |

---

---

## 2026-07-09 14:55:00 追加记录：教材骨架入库闭环、缩写主名合并与来源感知审计

| 时间 | 影响范围 | 错误/风险表现 | 根因 | 修复动作 | 验证证据 | 复用规则 | 已同步 |
|---|---|---|---|---|---|---|---|
| 2026-07-09 14:55:00 | 四大优先教材骨架、服务器 Neo4j、本地 C5 delta | BNP、NT-proBNP、CK-MB、ICD、CRT、IVUS、ACEI、ARB、ARNI、PCI 等缩写如果作为主名称，会影响前端展示、术语统一和后续同义词归并；部分缩写还与服务器已有中文标准节点重复。 | 早期结构化抽取把教材英文缩写直接当作 canonical name，未在入库前执行“中文主名 + 缩写 alias + 服务器同名查重合并”。 | C5 入库后立即执行 C6 服务器审计；发现缩写主名后，原地改中文主名；对已有标准中文节点执行关系迁移、证据迁移、重复缩写节点删除；同步修正本地 C5 delta。 | G2复审：blocker=0、warning=0；服务器复核：非KGNode=0、同类型同名重复=0、语义关系重复=0、缺证据=0、技术编码主名=0。 | 入库前后均必须跑“缩写主名”审计；药物、检查、手术/操作不得以英文缩写作为主名称，英文缩写进入 alias；若服务器已有标准中文节点，必须迁移关系后合并，不得并存两个节点。 | 步骤记录、C6服务器复核报告、批次台账、交接文件 |
| 2026-07-09 14:55:00 | 全心血管章节骨架扩展、D1-D6审计 | 全章节扩展时，节级节点一度被写成自己的父级，导致大量对象被误判为 category_container；后段“肿瘤治疗相关/糖尿病相关心血管疾病”被 DOCX 目录解析挂到“心血管神经症”下。 | DOCX 目录结构存在拆行/跨章标题识别问题，父级推断不能简单使用 `section_title or chapter_title`；章节结束边界也不能只靠固定段落窗口。 | 修正父级逻辑：章→第三篇循环系统疾病，节→章，条目→节；将肿瘤治疗相关主题校准到“肿瘤心脏病学”，将糖尿病相关主题校准到“糖尿病相关心血管疾病”；重跑 D1/C2/G1/D3/D6/C5/G2，并导入服务器。 | 最终 D6：候选节点=1504，候选关系=2532，container=18，source_limited=45，source_covered=18，extraction_gap=0；C5/G2：节点=1798，关系=5146，阻断=0，警告=0；C6服务器复核 passed，硬闸门全0。 | 全章节扩展必须先校验父级树；父级错误时不得进入 curated delta 和 Neo4j。任何目录解析规则修改后，必须重跑 C1/C2/G1，而不是只改显示字段。入库前必须复用服务器既有 DiseaseCategory，英文缩写主名必须归并到中文主名或 alias。 | 步骤记录、D6报告、C6服务器复核、交接文件、台账 |
| 2026-07-09 14:55:00 | 教材骨架质量评估、指南补充策略 | 如果机械要求每个章节都有定义、症状体征、检查、诊断鉴别、治疗，会把教材未覆盖内容误判成抽取失败；也会诱导模型硬补不存在内容。 | 早期 G1 混淆了“教材来源未覆盖”和“抽取器没抽到”。 | 新增 D4/D5/D6 来源感知审计：区分 `source_covered_ready`、`source_limited_ready_as_textbook_core`、`reference_only_groups`、`extraction_gap_groups`；对“参见/参照其他章节”不再算抽取失败。 | D6：source_covered_ready=18，source_limited_ready_as_textbook_core=44，container=19，extraction_gap_group_counter 为空。 | 教材是骨架，指南是决策血肉。教材未写的槽位标 `SOURCE_DOES_NOT_COVER/source_limited`，后续由指南 PDF 或外部权威补充；禁止为追求全绿硬造教材没有的实体。 | 步骤记录、D6来源感知审计报告、批次台账 |
| 2026-07-09 18:29:57 | 冠心病 CDSS 决策层、推荐证据模型、前端展示口径 | 初版证据选择如果只靠关键词和年份，可能把“同一页混排/表格串行/相邻主题”的证据误选为主证据，导致医生看到的推荐依据不精准；另外禁忌类推荐会被旧审计误判为“无推荐动作”。 | 指南 PDF 页面存在表格、双栏、多个推荐主题混排；早期审计只认 `recommends_action`，未把 `blocks_action` 视为 CDSS 阻断动作。 | 冠心病 CDSS delta 增加 evidence anchor 白名单和结构化推荐摘要；RecommendationStatement 同时保留 `primary_evidence_summary` 与 `primary_evidence_raw_excerpt`；服务器复核口径改为“有推荐动作或有阻断动作”；动作名称按名称去重。 | 本批次服务器复核 passed：RecommendationStatement=33，ClinicalRule=33，PathwayStage=29，ClinicalPathway=10；无缺证据、无缺动作/阻断、无缺指南、无展示字段缺失、无阶段与治疗方案重名、无阻断动作名称重复。 | CDSS 医生端展示必须以 RecommendationStatement 为最小推荐单元；主证据必须是该推荐直连证据，不得从疾病级证据池随便取；禁忌/排除类推荐是 `blocks_action`，不应被当作缺动作；原文摘录用于追溯，医生端默认展示结构化摘要。 | 步骤记录、批次台账、neo4j_batch_postcheck_summary.json |
| 2026-07-11 22:45:00 | Schema V1.12 迁移、服务器 Neo4j、Trae 前端/后端查询 | 早期计划文件仍写“不写 Neo4j”，但实际执行阶段用户已授权写库；独立后验第一次误用 `entity_type` 查询，导致 SourceSection/RecommendationStatement 看似为空；333 条旧关系不能直接转标准推荐关系。 | 计划文件没有随用户后续授权同步；服务器真实字段是 `entityType`；`USES_MEDICATION`、`HAS_PROCEDURE`、`HAS_CLINICAL_MANIFESTATION` 中有大量 SourceSection/DiseaseCategory 章节提及，不具备“疾病/治疗方案正式推荐”语义。 | 已执行 Schema V1.12 入库迁移 7432 条关系；节点治理完成；重跑 `entityType` 口径后验；重建 `Trae前端开发全局提示词.md` V1.1，明确前端只用小写标准关系，旧关系只作遗留提示。 | 服务器：43020 节点、139845 关系、SourceSection=75、旧节点=0、重复语义关系=0；单测 `tests.test_audit_graph_instance` 16 项 OK。 | 1）所有 Neo4j 节点类型查询必须使用 `entityType`；2）迁移脚本必须区分“章节提及”和“临床推荐”，不能为了清零旧关系而硬改语义；3）Trae 前端不得查询 `HAS_*` 作为正式 CDSS 数据；4）计划约束必须以用户最新授权为准，并在交接文件写清当前状态。 | 步骤记录、交接文件、Trae 全局提示词、迁移摘要 |
| 2026-07-11 08:58:00 | Schema V1.13、Neo4j主图谱、Trae前端查询、文档瘦身 | `USES_MEDICATION`、`HAS_PROCEDURE`、`HAS_CLINICAL_MANIFESTATION` 虽然已标记为 knowledge_display_only，但仍残留在主图谱关系层，前端/后端一旦误查就可能把“教材章节提及”误当成 CDSS 推荐；Schema 和 SKILL 主MD也持续膨胀。 | 早期骨架抽取把教材章节提及直接建成关系；后续为了可追溯不断往主Schema和主SKILL补详细案例、迁移说明、踩坑内容，导致主标准职责变重。 | 新增清理脚本，先归档再删除 333 条旧弱语义关系；Schema 升级 V1.13，只补硬规则不塞长篇；新增瘦身评估报告；Trae提示词更新为 V1.2。 | 服务器后验：三类旧关系=0，HAS_*历史大写关系=0，总关系 139512，RecommendationStatement 缺动作/证据/指南均为0。 | 1）旧弱语义关系必须归档后删除，不能只靠前端忽略；2）低频不等于冗余，必须看临床语义；3）主Schema只放标准和硬闸门，迁移细节、案例、统计、踩坑必须外置；4）阶段候选动作和正式推荐动作必须区分。 | 步骤记录、交接文件、Schema V1.13、Trae提示词 V1.2、瘦身评估报告 |
