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
