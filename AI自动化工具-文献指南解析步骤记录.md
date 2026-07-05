# AI自动化工具-文献指南解析步骤记录

用途：记录每个工作日/每轮用户提示后的问题、处理方案、执行结果和后续状态。  
定位：本文件记录“执行过程”；`_全局复利与踩坑日志.md` 记录“事故根因与复用规则”。两者必须互相对得上。

## 记录规则

1. 每天或每轮关键提示后，必须追加一条记录。
2. 每条记录必须包含：用户提出的问题、判断结论、执行方案、执行结果、遗留阻断、关联踩坑日志。
3. 若本轮发现可复用错误或流程漏洞，必须同步写入 `_全局复利与踩坑日志.md`；若只是普通执行进展，则只写本文件。
4. 记录时间必须精确到秒，格式为 `YYYY-MM-DD HH:mm:ss`。
5. 新病种启动前，先读取本文件最近记录和 `_全局复利与踩坑日志.md` 相关规则，作为执行依据。

---

## 2026-06-27 22:10:57｜全局质量体检与 Trae 候选回证据流程

### 用户提出的问题

1. 要求直接执行“全局质量体检”，目标不是证明没问题，而是一次性暴露剩余问题。
2. 能修的全部修，不能修的明确挡在正式 CDSS。
3. Trae 的成果不能直接写 Neo4j；必须读取缺失分析结果，把每条候选回到教材原文证据，抽成具体临床实体，再进入本地 JSONL、审计、导入流程。
4. 前端截图仍显示“诊断标准/鉴别诊断/药物治疗”等旧问题，需区分是数据库问题、前端缓存还是展示逻辑问题。
5. 要新增步骤记录文件，便于以后复盘和新病种执行复用。

### 判断结论

1. 服务器 Neo4j 主图谱当前结构硬闸门为干净状态：非 `KGNode` 节点、触达非 `KGNode` 关系、语义空壳关系、技术编码显示名、药物类别无具体药物、同类型同名重复均为 0。
2. 前端截图问题主要来自旧静态快照 `kg-test-page/assets/kg_full_data.json` 和一跳展示逻辑，不代表当前 Neo4j 主库仍有这些空壳关系。
3. 本地审计显示三批次仍未达到正式 CDSS 上线标准，核心阻断是 required 缺口、`EXTRACTION_MISS_REVIEW_REQUIRED`、临床审核状态和推荐闭环，而不是节点/关系结构脏数据。
4. Trae 报告中混有旧快照误判和语义空壳候选，必须分层处理：空壳词拒绝、已覆盖候选跳过、无证据候选拒绝、具体实体候选才进入回填。

### 已执行方案

1. 建立本轮体检目录：
   `心血管内科文献集合/99_全局质量体检_global_quality_audit/20260627_220151/`
2. 运行服务器硬闸门脚本：
   `scripts/verify_server_global_repair.py`
3. 重跑本地三批审计：
   - `00_foundation_skeleton`
   - `BATCH-CARD-CM-20260622-001`
   - `BATCH-CARD-CAD-20260623-001`
4. 复制并索引 Trae 报告：
   - `校验_全量_20260627.md`
   - `交叉核对报告_20260627.md`
   - `精细问题清单_20260627.md`
5. 新增候选分类测试：
   `tests/test_classify_evidence_backfill_candidates.py`

### 当前执行结果

服务器 Neo4j 关键结果：

```text
all_node_count = 26249
kg_node_count = 26249
all_relation_count = 53179
kg_relation_count = 53179
non_kgnode_node_count = 0
relation_touching_non_kgnode_count = 0
semantic_shell_relation_count = 0
diagnosis_generic_direct_relation_count = 0
technical_display_name_error_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
duplicate_type_name_count = 0
```

本地三批审计结果：

```text
00_foundation_skeleton：quality_gate_status=failed，required_pathway_missing_count=301，extraction_miss_review_required_count=174，cdss_recommendation_readiness_error_count=711
BATCH-CARD-CAD-20260623-001：quality_gate_status=failed，required_pathway_missing_count=6，cdss_recommendation_readiness_error_count=215
BATCH-CARD-CM-20260622-001：quality_gate_status=failed，required_pathway_missing_count=26，cdss_recommendation_readiness_error_count=83
```

药物层级核实：

```text
溶栓治疗 → 溶栓药物 → 尿激酶、链激酶、阿替普酶、瑞替普酶、组织型纤溶酶原激活物、替奈普酶
抗凝药物 → 肝素、华法林、低分子量肝素、阿哌沙班、普通肝素、利伐沙班、依度沙班、达比加群、艾多沙班
抗血小板药物 → 氯吡格雷、西洛他唑、替格瑞洛、普拉格雷、阿司匹林
```

### 遗留阻断

1. 当前图谱可以继续作为测试库工作版本，但不能进入正式 CDSS 推荐层。
2. 必须处理骨架库 174 条 `EXTRACTION_MISS_REVIEW_REQUIRED`，只允许采纳能回到原文证据并抽成具体实体的候选。
3. 前端需要修复静态快照和一跳展示逻辑，否则会继续显示旧问题。

### 关联踩坑日志

已关联 `_全局复利与踩坑日志.md`：

- `2026-06-27 21:46:59`：Trae 直接补库创建非 `KGNode` 空壳节点，已修复并新增全库 `KGNode` 契约硬闸门。
- `2026-06-27 00:28:13`：多路径被前端统计为重复药物节点，已修复关系去重与前端按 `KGNode.code` 去重规则。
- `2026-06-26 15:24:02`：语义空壳节点、药物类别别名污染、服务器同名重复问题，已形成硬闸门。

### 下一步

1. 实现并运行 Trae/教材证据候选分类脚本。
2. 输出 `ACCEPT_CANDIDATE / REJECT_SEMANTIC_SHELL / ALREADY_COVERED / REJECT_NO_EVIDENCE / NEEDS_GUIDELINE_OR_CLINICAL_REVIEW` 分类表。
3. 仅对 `ACCEPT_CANDIDATE` 生成本地 JSONL 修复补丁。
4. 重跑审计，合格后再同步测试库；不合格项继续挡在正式 CDSS。

---

## 2026-06-27 22:43:11｜候选回捞修复、版本管理与大文件机制

### 用户提出的问题

1. 当前目录虽然存在 `.git` 文件夹，但 `git status` 无法识别为有效 Git 仓库；是否需要提供 GitHub 做版本管理。
2. 本地骨架库 `nodes_final.jsonl` 约 62MB、`relations_final.jsonl` 约 347MB，日常修复效率太差，需要解决方案。
3. 类似空壳实体、重复实体、前端旧快照、证据候选误连等问题反复出现，需要机制化记录、升级和复用，否则无法支撑后续大量心血管疾病和其他专科建设。

### 判断结论

1. 需要版本管理，但不建议把大图谱快照直接放入普通 Git 主仓。代码、Schema、SKILL、测试、审计摘要、步骤记录、踩坑日志应纳入 Git/GitHub；大图谱快照应以 manifest、hash、压缩制品、对象存储或 Git LFS 管理。
2. 当前大 JSONL 反复整文件重写不适合作为长期流程。后续应采用“基线快照 + 增量包 delta + 阶段合并快照”的机制。
3. Trae/教材候选回捞必须增加疾病锚点、目标实体锚点、关系语义锚点三重门禁，避免把“STEMI 合并心房颤动”误连成“心房颤动→溶栓药物”。
4. 同类问题重复出现时，必须升级为自动化测试、审计脚本或 SKILL 硬规则，不能只靠用户截图提醒。

### 已执行方案

1. 新增候选回捞应用测试：
   `tests/test_apply_evidence_backfill_candidates.py`
2. 更新候选分类脚本：
   `scripts/classify_evidence_backfill_candidates.py`
3. 新增本地候选回填脚本：
   `scripts/apply_evidence_backfill_candidates.py`
4. 重新分类教材/Trae 候选：
   `心血管内科文献集合/99_全局质量体检_global_quality_audit/20260627_220151/03_trae_candidates/textbook_candidate_classification.csv`
5. 对本地骨架库仅应用已通过校验的候选，不直接写 Neo4j。
6. 更新 SKILL 到 V1.23，新增：
   - 重复问题升级机制；
   - 证据回捞候选防误判规则；
   - 大图谱数据增量优先规则；
   - Git/GitHub 与大图谱制品管理边界。

### 当前执行结果

候选分类结果：

```text
total = 19562
ALREADY_COVERED = 17835
REJECT_SEMANTIC_SHELL = 1683
NEEDS_DISEASE_ANCHOR_REVIEW = 35
NEEDS_RELATION_SEMANTIC_REVIEW = 3
ACCEPT_CANDIDATE = 6
```

本地回填结果：

```text
accepted_rows = 6
unique_candidate_relations = 2
added_relations = 2
added_evidence_records = 6
skipped_existing_relations = 0
skipped_missing_node = 0
```

新增的唯一关系：

```text
急性心力衰竭 → treated_by_medication → 硝酸酯类药物
二尖瓣狭窄 → treated_by_medication → 抗凝药物
```

拦截的典型误判：

```text
心房颤动 → treated_by_medication → 溶栓药物
原因：证据主语为 STEMI，心房颤动只是合并情况；应归入关系语义人工复核，不得自动入图。
```

回填后骨架库审计：

```text
quality_gate_status = failed
node_count = 26249
relation_count = 53108
semantic_shell_node_relation_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
technical_display_name_error_count = 0
duplicate_semantic_relation_count = 0
target_match_failure_count = 0
required_pathway_missing_count = 301
extraction_miss_review_required_count = 174
cdss_recommendation_readiness_error_count = 713
```

服务器复核结果：

```text
all_node_count = 26249
kg_node_count = 26249
all_relation_count = 53179
kg_relation_count = 53179
non_kgnode_node_count = 0
relation_touching_non_kgnode_count = 0
semantic_shell_relation_count = 0
diagnosis_generic_direct_relation_count = 0
technical_display_name_error_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
duplicate_type_name_count = 0
```

结论：结构硬错误未回退；新增关系按 `pending_clinical_review` 进入工作版本，因此仍不能进入正式 CDSS 推荐层。

### 遗留阻断

1. 需要确认是否建立私有 GitHub 仓库或使用本地 Git + 制品目录；大图谱快照不建议直接进普通 Git。
2. 需要后续实现 delta 增量包流水线，避免每次小修复重写 300MB+ 关系快照。
3. 35 条 `NEEDS_DISEASE_ANCHOR_REVIEW` 和 3 条 `NEEDS_RELATION_SEMANTIC_REVIEW` 不得自动入图，需继续回原文证据或等待指南/临床审核。
4. 本地回填暂未同步 Neo4j；按当前规则，Trae/教材候选必须先完成本地 JSONL、审计和审核，再进入测试库导入流程。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-06-27 22:43:11`：证据回捞候选误判、大文件快照效率、版本管理边界和重复问题升级机制。

### 下一步

1. 完成本轮服务器硬闸门复核，确认测试库未被本地候选回填误写。
2. 若用户确认 GitHub/版本管理方案，建立私有仓库或本地 Git 初始化，并排除大图谱快照。
3. 若用户确认 delta 方案，新增 `09_增量补丁_delta/` 目录和 delta manifest 生成/应用脚本。
4. 对剩余人工复核候选继续按证据锚点规则处理，不直接写库。

---

## 2026-06-28 08:43:37｜测试库 delta 同步与版本管理初始化

### 用户提出的问题

1. 询问“未直接写入本地候选回填”是什么意思，并要求如果有把握就直接写入测试库。
2. 同意启动版本管理，并提供 GitHub 账号密码。

### 判断结论

1. “未直接写入”应表述为：本地 JSONL 已回填并审计，服务器 Neo4j 当时尚未同步这 2 条关系。
2. 本轮只允许同步到 Neo4j 测试库工作版本；新增关系仍为 `clinical_review_status=pending_clinical_review`、`formal_cdss_ready=false`，不得进入正式 CDSS 推荐层。
3. 不能使用 GitHub 明文密码；GitHub 也不支持普通密码推送。应改用 SSH key、浏览器授权、GitHub CLI 或细粒度 PAT。用户已在聊天中暴露密码，建议立即修改密码。
4. 当前 `.git` 是空壳目录，无 `HEAD`、无 `config`，因此 `git status` 原先失败；可以安全 `git init`。

### 已执行方案

1. 生成 delta 增量目录：
   `心血管内科文献集合/09_增量补丁_delta/20260628_测试库回填_textbook_backfill_2rels/`
2. 写入 delta 文件：
   - `delta_relations_add.jsonl`
   - `delta_manifest.json`
   - `neo4j_delta_import_summary.json`
   - `neo4j_targeted_duplicate_cleanup.json`
   - `semantic_uniqueness_after_delta_import.json`
   - `verify_server_after_delta_import.json`
3. 将 2 条本地已审计关系同步到 Neo4j 测试库：
   - 急性心力衰竭 → treated_by_medication → 硝酸酯类药物
   - 二尖瓣狭窄 → treated_by_medication → 抗凝药物
4. 同步过程中发现服务器已有 2 条旧的同义语义边，但旧边缺少标准 `id/provenance`；已删除旧边，只保留标准化新边。
5. 新增 `.gitignore`，排除 PDF、zip、大 JSONL/CSV 图谱快照、清洗文本、Python 缓存、批次大产物。
6. 执行 `git init`，本地 Git 仓库初始化成功；尚未提交，尚未绑定 GitHub 远程。
7. SKILL 升级到 V1.24，新增 Neo4j delta 导入语义键去重规则和 GitHub 凭据安全规则。

### 当前执行结果

Neo4j delta 同步结果：

```text
REL-DC94A019381A：急性心力衰竭 → 硝酸酯类药物，evidence_count=2
REL-8E8493537C57：二尖瓣狭窄 → 抗凝药物，evidence_count=4
clinical_review_status = pending_clinical_review
formal_cdss_ready = false
```

目标语义键唯一性：

```text
急性心力衰竭 → treated_by_medication → 硝酸酯类药物：relation_count=1
二尖瓣狭窄 → treated_by_medication → 抗凝药物：relation_count=1
global duplicate_semantic_keys = 0
global redundant_relationship_count = 0
```

服务器硬闸门：

```text
all_node_count = 26249
kg_node_count = 26249
all_relation_count = 53179
kg_relation_count = 53179
non_kgnode_node_count = 0
relation_touching_non_kgnode_count = 0
semantic_shell_relation_count = 0
diagnosis_generic_direct_relation_count = 0
technical_display_name_error_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
duplicate_type_name_count = 0
```

版本管理初始化：

```text
git init 成功
.gitignore 已创建
GitHub 远程未绑定
未提交
```

### 遗留阻断

1. 正式 CDSS 仍不可上线，因为 required 缺口和 `pending_clinical_review` 未清零。
2. GitHub 远程需要用户用安全方式提供仓库地址和授权方式；不能使用明文密码。
3. 需要后续补一个正式 `scripts/import_neo4j_delta.py`，避免再用临时脚本做 delta 导入。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-06-28 08:43:37`：Neo4j delta 导入不能只按关系 id MERGE，必须按语义键去重；GitHub 凭据不得明文使用。

---

## 2026-06-28 18:48:43｜CAD/CM required 缺口闭环冲刺、delta 节点导入和新病种预检

### 用户提出的问题

1. 询问骨架、冠心病、心肌病是否已经搞定，并同意继续执行。
2. 要求下一步直接推进，不再停留在候选；可修复项应一次性修复，不能硬造证据。
3. 要求后续新病种启动前有可靠机制，避免漏顶层学科、PDF路径、教材骨架、可导入文件交接。

### 判断结论

1. 心肌病和冠心病结构硬错误已经为 0，但仍存在 required 缺口和 `clinical_review_status=pending_clinical_review`，不能进入正式 CDSS 推荐层。
2. required 缺口不能只看 `SOURCE_DOES_NOT_COVER`；必须回查指南/教材 evidence index。若同病种原文存在但 pathway 标注不准，应按抽取/映射漏掉处理。
3. 本轮只允许把有明确原文证据的缺口写入本地 JSONL 和测试库工作版本；没有明确随访原文的“隐匿型冠心病随访”不得硬补。

### 已执行方案

1. 新增并测试 `scripts/probe_required_gap_evidence.py`，用于从 `disease_pathway_coverage.csv` 反查指南/教材/候选索引。
2. 新增并测试 `scripts/apply_curated_required_backfill.py`，用于应用“人工策展补丁”，支持新增节点、关系和既有节点别名合并。
3. 生成策展补丁：
   `心血管内科文献集合/99_闭环冲刺_closure_sprint/20260628_required_gap_probe/curated_required_backfill_20260628.json`
4. 本地应用补丁：新增 4 个诊断标准实体、8 条关系，后续又合并 5 个节点别名。
5. 扩展 `scripts/import_neo4j_delta.py`，支持 `delta_nodes_upsert.jsonl` 节点 upsert + `delta_relations_add.jsonl` 关系导入。
6. 生成可导入增量包：
   `心血管内科文献集合/09_增量补丁_delta/20260628_CAD_CM_required_gap_backfill/`
7. 新增并测试 `scripts/preflight_new_disease_batch.py`，生成下一批新病种启动预检样例。
8. SKILL 升级到 V1.25，写入 required 缺口闭环、delta 节点 upsert、新病种预检和可导入文件交接规则。

### 当前执行结果

本地补丁应用：

```text
新增节点：4
更新别名节点：5
新增关系：8
delta_nodes_upsert：5
delta_relations_add：8
```

冠心病审计变化：

```text
required_pathway_missing_count：6 → 1
closed_loop_ready_disease_count：6 → 9
target_match_failure_count：0
duplicate_code_count：0
duplicate_semantic_relation_count：0
semantic_shell_node_relation_count：0
technical_display_name_error_count：0
```

心肌病审计变化：

```text
required_pathway_missing_count：26 → 25
closed_loop_ready_disease_count：4 → 5
target_match_failure_count：0
duplicate_code_count：0
duplicate_semantic_relation_count：0
semantic_shell_node_relation_count：0
technical_display_name_error_count：0
```

新增测试：

```text
python -m unittest tests.test_preflight_new_disease_batch tests.test_apply_curated_required_backfill tests.test_import_neo4j_delta tests.test_probe_required_gap_evidence
10 项 OK
```

### 遗留阻断

1. 服务器导入尚未执行：当前环境未设置 `NEO4J_PASSWORD`，不能把密码写入命令、脚本或日志。
2. 冠心病仍剩 1 个 required 缺口：隐匿型冠心病 follow_up。当前原文只有“及时发现、及早治疗”，不足以生成随访方案。
3. 心肌病仍剩 25 个 required 缺口，主要是 ABVC/ALVC/心房心肌病/法布雷病心肌病/非扩张型左心室心肌病等稀有分型深层证据不足。
4. 两个样板仍有 therapeutic recommendation 的 `clinical_review_status=pending_clinical_review`，正式 CDSS 推荐层不可上线。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-06-28 18:48:43`：required 缺口不能直接等同文献不覆盖；策展补丁必须带原文证据；delta 节点必须按 code 去重；没有明确随访原文不得硬补。

---

## 2026-06-29 08:57:53｜pending 临床审核改为“临床使用效果审核包”

### 用户提出的问题

1. `pending_clinical_review` 和 CDSS 推荐字段不可能让专家逐条看图谱网络节点确认。
2. 专家只能从实际使用效果上确认，除非整理成非常简单清晰的数据格式。
3. 用户截图显示已在本机 PowerShell 设置 `NEO4J_PASSWORD`，要求继续查看和执行。

### 判断结论

1. 用户判断正确：专家审核不能以 Neo4j 网络图或 303 条边级 pending 明细作为主入口。
2. 正确流程是“疾病级整体可用性 → 场景级推荐卡 → 药师专项药物风险 → 边级证据追溯”。边级明细只给数据团队和回写脚本使用。
3. AI 不得把 `pending_clinical_review` 自动改为专家已确认；只能生成审核包、回写脚本和阻断清单。
4. 截图里的密码变量只对用户当前 PowerShell 会话有效；当前 Codex 执行进程仍读取不到 `NEO4J_PASSWORD`，因此服务器导入暂缓。

### 已执行方案

1. 新增并测试 `scripts/build_clinical_effect_review_pack.py`。
2. 新增测试 `tests/test_build_clinical_effect_review_pack.py`，验证治疗方案下游药物推荐能回溯到疾病，并生成疾病级、场景级、药师专项三类审核表。
3. 重新生成详细 pending 审核包：
   `心血管内科文献集合/99_临床审核_clinical_review/20260629_pending_review_pack_latest/`
4. 新增临床使用效果审核包：
   `心血管内科文献集合/99_临床审核_clinical_review/20260629_临床使用效果审核包_effect_review/`
5. 将规则同步到 `AI自动化工具-文献指南解析.md` V1.26，并追加本步骤记录和踩坑日志。

### 当前执行结果

详细 pending 审核包：

```text
review_item_count = 303
CAD = 216
CM = 87
clinical_review_status 缺口 = 303
```

临床使用效果审核包：

```text
disease_review_count = 22
scenario_card_count = 103
pharmacist_item_count = 187
```

本地 required 闭环状态：

```text
CAD required_pathway_missing_count = 0
CAD closed_loop_ready_disease_count = 10/10
CM required_pathway_missing_count = 0
CM closed_loop_ready_disease_count = 12/12
```

可导入增量包：

```text
心血管内科文献集合/09_增量补丁_delta/20260628_CAD_CM_required_gap_closure_round2/
delta_nodes_upsert.jsonl = 31 nodes
delta_relations_add.jsonl = 35 relations
formal_cdss_ready = false
```

### 遗留阻断

1. 服务器导入仍未执行：当前 Codex 执行进程未读取到 `NEO4J_PASSWORD`。
2. 正式 CDSS 仍不可上线：pending 审核和部分 CDSS 推荐字段需要通过简化审核包回写，而不是 AI 自动批准。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-06-29 08:57:53`：临床专家审核不能逐边进行，必须产品化为疾病级、场景级、药师专项审核包；边级明细只作为证据追溯。

---

## 2026-06-29 09:20:00｜CAD/CM required closure round2 delta 导入测试库

### 用户提出的问题

1. 已在 Windows 用户级环境变量中设置 `NEO4J_USERNAME`、`NEO4J_URI`、`NEO4J_HTTP`、`NEO4J_PASSWORD`，要求核对无误后继续导入。
2. 追问为什么此前一直可以连接数据库，本次却提示需要 PowerShell 环境变量。
3. 询问后续如何做多智能体协调作战，哪些基础性工作可以分给 Trae，不影响 Codex 总体计划。

### 判断结论

1. 用户级环境变量已存在：`NEO4J_USERNAME=neo4j`、`NEO4J_URI=bolt://192.168.3.27:7687`、`NEO4J_HTTP=http://192.168.3.27:7474`、`NEO4J_PASSWORD` 已设置且未回显明文。
2. 当前 Codex 命令进程没有自动继承用户新开的 PowerShell 会话变量，因此需要从 Windows User 环境读取后注入本次命令进程；这不是数据库不可连接。
3. `scripts/import_neo4j_delta.py` 使用 Neo4j HTTP API，导入端点应使用 `NEO4J_HTTP`。

### 已执行方案

1. 从 User 环境读取 `NEO4J_PASSWORD`、`NEO4J_HTTP`、`NEO4J_USERNAME`，只注入当前导入命令进程，不写入脚本、日志或 Git。
2. 执行 round2 delta 导入：
   `心血管内科文献集合/09_增量补丁_delta/20260628_CAD_CM_required_gap_closure_round2/`
3. 导入后运行服务器硬闸门复核 `scripts/verify_server_global_repair.py`。

### 当前执行结果

Delta 导入摘要：

```text
input_node_count = 31
merged_node_count = 31
input_relation_count = 35
merged_relation_count = 35
deleted_legacy_relationship_count = 1
postcheck = 35 条语义键均 existing_count=1
```

服务器硬闸门复核：

```text
all_node_count = 26279
kg_node_count = 26279
all_relation_count = 53213
kg_relation_count = 53213
non_kgnode_node_count = 0
relation_touching_non_kgnode_count = 0
semantic_shell_relation_count = 0
diagnosis_generic_direct_relation_count = 0
technical_display_name_error_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
label_metadata_mismatch_count = 0
duplicate_type_name_count = 0
```

药物具体化复核：

```text
抗凝药物 has_specific_medication = 9
溶栓药物 has_specific_medication = 6
他汀类药物 has_specific_medication = 4
β受体拮抗剂/阻滞剂各 has_specific_medication = 4
```

### 遗留阻断

1. 测试库工作版本已同步；正式 CDSS 仍不可上线。
2. `clinical_review_status_counts` 显示 `pending_clinical_review=597`，必须通过临床使用效果审核包和药师专项审核表回写，不得由 AI 自动批准。

### 关联踩坑日志

本次未新增新的质量事故；沿用：

- `2026-06-29 08:57:53`：专家审核必须走疾病级、场景级、药师专项审核包。
- `2026-06-28 08:43:37`：Neo4j delta 导入必须按语义键去重/替换，不得只按关系 id。

---

## 2026-06-29 14:39:49｜Trae 图谱系统分析、前端审核包与多智能体协作方案

### 用户提出的问题

1. 按既定计划继续：补推 GitHub → 做 pending 审核包前端/回写机制 → 让 Trae 做审核页面 → 启动心力衰竭批次。
2. 用户说明 Trae 已开发图谱系统，地址为 `http://192.168.3.27:4001/index.html`，要求读取分析功能并补充专家审核设计。
3. 用户截图显示 GitHub 浏览器可打开，但命令行 `git push` 仍失败。

### 判断结论

1. Trae 当前系统已有总览、图谱探索、网络探索、覆盖分析、诊断模拟、数据字典、Schema 标准、术语库、系统配置页面。
2. 当前系统没有 `clinical_review` / `pending` 专家审核工作流；不能直接承接 597 个 pending 的审核闭环。
3. 正确方式是由 Codex 生成前端审核 JSON 包，Trae 只读取展示并导出审核结果；Codex 再校验导出文件、执行 detail 级回写、重跑审计并导入测试库。
4. GitHub 浏览器能打开不等于当前 git 进程可推送；本轮 `git push origin main` 仍因 HTTPS 连接 reset 失败，需网络恢复后补推。

### Trae 系统功能盘点

已读取页面：

```text
index.html：专病总览、KPI、疾病大类、知识维度成熟度
explore.html：疾病维度浏览、实体视角，调用 /api/kg/diseases/summary
network.html：交互式图谱网络、实体详情、路径分析、导出
heatmap.html：77 疾病 × 17 维度覆盖分析
diagnosis.html：病例文本诊断模拟
schema.html：图谱数据字典
standard.html：Schema 标准
terminology.html：医学术语知识库
config.html：Neo4j 配置
```

已读取接口：

```text
/api/kg/stats
/api/kg/diseases
/api/kg/diseases/summary
/api/kg/disease/{code}
./assets/kg_full_data.json
```

### 已执行方案

1. 按 TDD 新增测试 `tests/test_build_clinical_review_frontend_package.py`。
2. 新增脚本 `scripts/build_clinical_review_frontend_package.py`，把疾病级、场景级、药师专项、边级明细转换成 Trae 前端可直接消费的 JSON。
3. 生成真实前端审核包：
   `心血管内科文献集合/99_临床审核_clinical_review/20260629_Trae前端审核包_frontend_review_package/`
4. 新增正式计划文档：
   `docs/superpowers/plans/2026-06-29-clinical-review-frontend-trae-integration.md`
5. 新增 Trae 开发说明：
   `心血管内科文献集合/99_临床审核_clinical_review/20260629_Trae前端审核包_frontend_review_package/Trae审核页面开发说明.md`
6. 打包 Trae 前端审核包：
   `20260629_Trae临床审核页面前端包.zip`
7. SKILL 升级到 V1.27，写入多智能体协作边界和 Trae 不得直接写库规则。

### 当前执行结果

前端审核包：

```text
clinical_review_frontend_manifest.json
clinical_review_frontend_data.json
clinical_review_decision_export_template.csv
Trae审核页面开发说明.md
20260629_Trae临床审核页面前端包.zip
```

数据量：

```text
disease_review_count = 22
scenario_card_count = 103
pharmacist_item_count = 187
detail_item_count = 303
```

测试：

```text
python -m unittest discover -s tests
72 项 OK
```

### 遗留阻断

1. GitHub 命令行推送仍失败：`Failed to connect to github.com port 443` 或 `Recv failure: Connection was reset`。本地提交未丢失，需网络恢复后执行 `git push origin main`。
2. Trae 审核页面尚需 Trae 按开发说明实现；实现后只能导出审核结果，不能直接回写数据库。
3. 心力衰竭批次尚未正式启动，下一步先跑新病种预检。

### 关联踩坑日志

本次同步到 SKILL V1.27：

- 多智能体协作必须划清边界：Trae 做展示/候选/导出，Codex 做证据裁决/回写/导入/质量门禁。

---

## 2026-06-29 14:58:40｜心力衰竭批次启动预检与版本留痕修复

### 用户提出的问题

1. 按计划在 Trae 审核页面设计之后启动心力衰竭批次。

### 判断结论

1. 心力衰竭可以作为下一批疾病大类启动，指南路径和教材路径沿用心血管内科既定路径。
2. 启动时发现 `prepare_medical_kg_batch.py` 仍把 `schema_version` 和 `skill_version` 硬编码为 V1.4，属于新批次留痕错误，必须先修脚本再继续。

### 已执行方案

1. 运行新病种预检：
   `心血管内科文献集合/00_新病种预检_preflight/20260629_心力衰竭_heart_failure_preflight.json`
2. 预检通过后创建批次：
   `心血管内科文献集合/BATCH-CARD-HF-20260629-001/`
3. 按 TDD 修改 `scripts/prepare_medical_kg_batch.py`，新增从主文档读取当前版本号的逻辑。
4. 更新 `tests/test_prepare_medical_kg_batch.py`，验证新批次配置不再硬编码 V1.4。
5. 修复已生成心力衰竭批次 `batch_config.json`：Schema V1.7、SKILL V1.27。
6. SKILL 升级 V1.28，新增批次启动后必须复核版本号和纳入文件清单规则。

### 当前执行结果

预检结果：

```text
status = pass
specialty = 心血管内科
scope_type = 疾病大类
scope_target = 心力衰竭
missing_required_fields = []
missing_paths = []
warnings = []
```

批次配置：

```text
batch_id = BATCH-CARD-HF-20260629-001
schema_version = V1.7
skill_version = V1.27
included_file_count = 18
excluded_file_count = 405
```

纳入文献：

```text
纳入指南/共识/建议/路径 = 15
纳入教材/基础书籍 = 3
合计 = 18
```

测试：

```text
python -m unittest discover -s tests
72 项 OK
```

### 遗留阻断

1. 心力衰竭批次已启动并完成预检/目录/来源清单，尚未进入 PDF 解析与证据抽取。
2. 开始解析前建议先人工确认 18 个纳入文件是否覆盖目标范围，尤其同名“心力衰竭患者利尿剂抵抗诊断及管理中国专家共识”存在两份不同大小文件，需保留为不同来源或后续按证据质量处理。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-06-29 14:58:40`：新批次 `batch_config.json` 版本号不得硬编码旧版本，必须从主文档读取。
---

## 2026-06-29 23:15:28～心肌病/冠心病临床安全直接修复与服务器硬闸门复核

### 用户提出的问题

1. 不再生成额外反馈报告，不做繁琐风险冻结补丁，已确认错误要直接处理正确。
2. 修复 4 个心肌病定义污染。
3. 数据库连接信息统一从 `图谱数据库链接.txt` 读取。
4. 执行完成后继续心力衰竭批次 PDF 解析与证据抽取。

### 判断结论

1. 心肌病定义污染和冠心病/心肌病错误治疗关系属于已确认数据错误，不应进入候选或冻结状态。
2. 服务器残留问题不能只按关系 `id` 删除；历史边存在缺失/截断 `id`，必须按语义条件清理。
3. 同义药物重复节点即使仍有入边/出边，也必须先迁移关系，再删除重复节点，否则会出现“本地归一但服务器重复”的假通过。

### 已执行方案

1. 新增/更新回归测试：`tests/test_repair_cad_cm_clinical_safety.py`。
2. 新增/更新直接修复脚本：`scripts/repair_cad_cm_clinical_safety.py`。
3. 执行本地回归：`python -m unittest tests.test_repair_cad_cm_clinical_safety`。
4. 从 `图谱数据库链接.txt` 解析 HTTP 地址、用户名、密码，不在日志输出密码。
5. 执行服务器同步：`python scripts\repair_cad_cm_clinical_safety.py --workspace . --apply-server`。
6. 执行服务器全局硬闸门：`python scripts\verify_server_global_repair.py`（连接信息由包装脚本从链接文件传入）。
7. SKILL 升级 V1.29，并同步 `_全局复利与踩坑日志.md`。

### 当前执行结果

```text
本地回归测试：4 项 OK

服务器目标验证：
cm_polluted_definition_count = 0
invalid_thrombolysis_relation_count = 0
hcm_pci_relation_count = 0
hcm_broad_ccb_relation_count = 0
hcm_ndhp_ccb_conditioned_count = 1
dcm_beta_synonym_duplicate_relation_count = 0

服务器同义节点合并：
moved_incoming_synonym_relations = 4
moved_outgoing_synonym_relations = 183
deleted_duplicate_synonym_nodes = 2

服务器全局硬闸门：
non_kgnode_node_count = 0
semantic_shell_relation_count = 0
technical_display_name_error_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
label_metadata_mismatch_count = 0
duplicate_type_name_count = 0
```

### 遗留阻断

1. `clinical_review_status=pending_clinical_review` 仍有 595 条，这是临床使用效果审核状态，不由 AI 自动批量改为专家已确认。
2. 下一步继续心力衰竭批次 PDF 解析与证据抽取，并沿用 V1.29 直接修复与服务器硬闸门规则。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：
- `2026-06-29 23:15:28`：已确认错误不得候选/冻结；服务器修复必须支持语义条件清理；非孤儿同义重复节点必须迁移关系后删除。

---

## 2026-06-30 10:44:51～心力衰竭批次 OCR 修复、图谱生成、服务器导入与实时复核

### 用户提出的问题

1. 继续处理 2 份 OCR 阻断 PDF，生成心力衰竭图谱实例和审计结果。
2. 缺少 Poppler/Tesseract 时可自行安装，但统一安装到 `D:\Program Files Ai`，结束后检查是否误装到 C 盘。
3. 执行结束必须说明做到什么程度。
4. 用户反馈 Trae 监测说图谱没变化，要求核实是否已经全部导入图谱数据库。

### 判断结论

1. 心力衰竭批次已完成 OCR 恢复、证据抽取、本地图谱生成、语义修复、本地审计、Neo4j 服务器导入和服务器实时复核。
2. Trae 监测“没变化”不能直接说明未导入；必须按服务器 `batch_id`、疾病 code、证据数、关系数实时查询确认。
3. 当前心力衰竭批次可作为 Neo4j 测试库工作版本；仍不能作为正式 CDSS 推荐层上线，因为 74 条直接 CDSS 推荐关系仍为 `pending_clinical_review` 或缺少完整推荐字段。

### 已执行方案

1. 完成 OCR 工具链处理：Tesseract 统一到 `D:\Program Files Ai\Tesseract-OCR`；Poppler 使用 Codex runtime 自带二进制。
2. 对 2 份阻断 PDF 执行 OCR 恢复，30 页全部成功。
3. 重跑心力衰竭证据抽取、图谱实例生成、语义质量修复和本地质量审计。
4. 修复 `scripts/import_neo4j_test_db.py`：节点导入改为先 `MERGE (n:KGNode {code})`，再补实体类型标签，避免既有同 code 节点触发唯一约束。
5. 将心力衰竭批次导入 Neo4j 测试库，并完成同类型同名重复节点合并、重复语义关系合并。
6. 更新 SKILL 至 V1.30，并同步 `_全局复利与踩坑日志.md`。
7. 生成心力衰竭批次导入报告和可导入图谱文件清单。

### 当前执行结果

```text
OCR 恢复：
target_page_count = 30
ocr_success_page_count = 30
failed = 0

本地图谱：
node_count = 2723
relation_count = 10380
evidence_node_count = 2582
disease_count = 11
closed_loop_ready_disease_count = 11
required_pathway_missing_count = 0
cdss_recommendation_readiness_error_count = 74

服务器实时复核：
kg_node_count = 28966
kg_relation_count = 63544
hf_batch_node_count = 2723
hf_batch_direct_relation_count = 10377
hf_evidence_count = 2582
hf_disease_count = 11

服务器硬闸门：
non_kgnode_node_count = 0
technical_display_name_error_count = 0
duplicate_type_name_count = 0
duplicate_semantic_relation_count = 0
medication_class_without_specific_count = 0
```

### 遗留阻断

1. 心力衰竭正式 CDSS 上线仍阻断：74 条直接 CDSS 推荐关系待临床使用效果审核或缺少完整推荐字段。
2. Trae 若仍显示没变化，应按 `batch_id='BATCH-CARD-HF-20260629-001'` 或疾病 code `DIS-CARD-HF` 查询，并清理前端缓存/固定疾病列表过滤。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-06-30 10:44:51`：Neo4j 增量导入必须按 `KGNode.code` upsert；导入验收必须以服务器实时查询为准；Trae 前端未显示不能反推未导入。

---

## 2026-06-30 22:14:47～全库安全体检、心衰 CDSS AI 预审核与专家批量签收

### 用户提出的问题

1. 继续其他疾病前，先确认是否需要全面安全检查。
2. 用户确认按方案执行。
3. 用户补充：专家同意采用批量签收机制，可以执行。

### 判断结论

1. 继续新疾病前必须先做全库安全体检，否则后续疾病会继承并放大历史质量问题。
2. AI 不能伪造“逐条专家审核”，但在专家同意批量签收机制后，可以做证据预审核、分级，并写入 `clinical_batch_signed_off`。
3. 进入测试推荐层和进入正式 CDSS 是两件事：`test_recommendation` 可用于测试推荐；`knowledge_display` 只做知识展示；`formal_cdss_ready` 不由 AI 自动置为 true。

### 已执行方案

1. 新增测试：
   - `tests/test_cdss_ai_precheck_signoff.py`
   - `tests/test_global_safety_check.py`
2. 新增脚本：
   - `scripts/apply_cdss_ai_precheck_signoff.py`
   - `scripts/global_safety_check.py`
3. 更新审计规则：`clinical_batch_signed_off` 纳入临床批量签收状态。
4. 执行服务器全库只读安全体检。
5. 对心衰 74 条阻断关系执行 AI 证据预审核和专家批量签收回写。
6. 重跑本地心衰审计。
7. 增量导入 Neo4j 测试库。
8. 发现导入后重复语义关系 227 组，执行服务器语义关系去重。
9. 修复 `scripts/import_neo4j_test_db.py`，关系导入改为按 `(source.code, relationType, target.code)` 语义键 MERGE，不再按关系 `id` MERGE。
10. 用修复后的导入脚本再次导入心衰批次，验证服务器关系数不再增加。
11. 再次执行服务器全库硬闸门。
12. 更新 SKILL V1.31、踩坑日志、执行报告和 Trae 前端核查说明。

### 当前执行结果

```text
全库安全体检（导入前）：
kg_node_count = 28966
kg_relation_count = 63544
global_safety_gate_status = passed

心衰 74 条 AI 预审核：
target_relation_count = 74
ai_prechecked_pass = 40
ai_prechecked_limited = 34
ai_prechecked_blocked = 0
clinical_review_status_set_to = clinical_batch_signed_off
formal_cdss_ready_set_true = 0

本地心衰审计：
cdss_recommendation_readiness_error_count = 34
required_pathway_missing_count = 0
closed_loop_ready_disease_count = 11
duplicate_semantic_relation_count = 0
medication_class_without_specific_count = 0
treatment_plan_actionability_error_count = 0

Neo4j 导入后：
input_node_count = 2723
input_relation_count = 10380
imported_node_rows = 2723
imported_relation_rows = 10380

导入后语义去重：
duplicate_semantic_keys_before = 227
deleted_relationship_count = 227
duplicate_semantic_keys_after = 0

导入脚本修复后再次导入：
database_kg_node_count = 28966
database_relation_count = 63544
duplicate_semantic_relation_count = 0

服务器最终硬闸门：
kg_node_count = 28966
kg_relation_count = 63544
non_kgnode_node_count = 0
relation_touching_non_kgnode_count = 0
technical_display_name_error_count = 0
treatment_plan_actionability_error_count = 0
medication_class_without_specific_count = 0
duplicate_type_name_count = 0
duplicate_semantic_relation_count = 0
semantic_shell_relation_count = 0
global_safety_gate_status = passed

服务器心衰 CDSS 状态：
ai_prechecked_pass = 40
ai_prechecked_limited = 34
test_recommendation = 40
knowledge_display = 34
clinical_batch_signed_off = 74
formal_cdss_ready_true = 0
```

测试：

```text
python -m unittest tests.test_cdss_ai_precheck_signoff tests.test_global_safety_check
6 项 OK
```

### 遗留阻断

1. 心力衰竭仍有 34 条关系不能进入强推荐，原因是推荐等级为 `N/A/N/A`，只能作为知识展示。
2. 所有正式 CDSS 上线仍需后续正式发布规则；本次没有设置任何 `formal_cdss_ready=true`。
3. 增量导入脚本已修复为语义键 MERGE；后续每次导入后仍必须复查 `duplicate_semantic_relation_count=0`。

### 关联踩坑日志

已同步 `_全局复利与踩坑日志.md`：

- `2026-06-30 22:14:47`：专家批量签收只能作为证据预审核分级机制，不等于 AI 伪造逐条专家审核；关系导入必须按语义键 MERGE，并在导入后复查重复语义关系。

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
