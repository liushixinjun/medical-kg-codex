# kg_pipeline 渐进式重构方案

## 2026-07-14 15:51 更新｜批次入库后复测入口已接入

本轮在公共执行层新增统一入口：`批次入库后复测_postcheck.py`。

定位：以后所有专病批次写入 Neo4j 后，不再临时挑选旧脚本，而是统一执行“批次入库后复测”。当前先接入主数据质量闸门，后续可继续挂接证据链、推荐规则、术语别名等复测项。

固定输出目录：`<批次目录>\99_入库后复测`。

阻断原则：复测失败时默认返回非 0 退出码，必须先修复阻断项；不得转正式 CDSS，不得继续叠加新病种。

## 2026-07-14 15:27 更新｜主数据质量闸门已落地

本轮已新增公共执行层目录：`公共执行层_kg_pipeline`。该目录不是新病种临时补丁，而是后续 `kg_pipeline` 的公共质量闸门雏形。

已固化 5 个只读服务器闸门：

| 中文闸门 | 用途 |
|---|---|
| 同病种同类型同名重复直连 | 防止教材骨架、指南批次、精修批次重复挂同名实体 |
| 诊断标准无明细 | 防止医生只能看到“诊断标准”标题 |
| 孤儿诊断标准 | 清除历史归并后残留的零关系诊断标准节点 |
| 治疗方案无下游 | 防止“治疗方案”只有标题，没有药物、操作、子方案或证据 |
| 已替换重复节点仍被引用 | 防止重复节点已归并但仍被路径、规则、疾病关系引用 |

执行入口：

```powershell
D:\Program Files Ai\python-venvs\medical-kg\Scripts\python.exe `
  公共执行层_kg_pipeline\主数据质量闸门_master_data_gate.py `
  --connection-file 图谱数据库链接.txt `
  --output-dir 心血管内科文献集合\00_全局质量体检_global_quality_audit\20260714_主数据质量闸门 `
  --fail-on-blocking
```

本轮服务器复核结果：5 个闸门全部为 0。后续新病种在 G2 导入前和 G3 入库后必须执行该闸门。

更新时间：2026-07-09 07:45:02

## 1. 本次任务边界

本次只做脚本资产盘点和长期运行机制设计，不做代码迁移，不连接 Neo4j，不写数据库，不运行修复/导入脚本，不移动、不删除、不重命名旧脚本，不修改旧批次目录，不修改 SKILL 和 Schema。

需要特别说明：本轮“绝对不连接 Neo4j”只限定脚本盘点任务。长期机制中，Neo4j 必须在导入前预检、导入后体检、一致性校验阶段使用，但必须通过统一闸门区分只读、写入、删除三种权限。

## 2. 为什么不能推倒重来

当前项目已经形成教材骨架、专病批次、服务器图谱、前端展示、专家审核、Trae 开发提示词等一整套历史资产。推倒重来会带来三个风险：

1. 历史批次和服务器状态失去可追溯性。
2. 已修复过的问题无法复用，容易反复犯同样错误。
3. 新旧图谱口径同时存在，前端和 CDSS 逻辑无法判断哪个可信。

因此采用渐进式治理：旧脚本保留，旧批次不动，先建立脚本台账和公共执行标准，再逐步抽取公共能力进入未来 kg_pipeline。

## 3. 当前根因判断：骨架优先

当前问题不是单个病种解析失败，而是骨架信息尚未完全稳固。链路如下：

```text
教材/权威骨架不稳
→ 疾病、分型、章节、临床状态边界不稳
→ Schema 实体落点不稳
→ 每个病种临时补洞
→ 临时脚本增多
→ 图谱出现空壳节点、泛化治疗方案、诊断标准无明细、推荐证据链不完整
```

长期原则必须改为：

```text
教材/权威基础资料先搭稳定骨架，指南再补决策血肉。
先稳骨架，再跑专病，再补指南，再导入图谱，再做 CDSS 推荐。
```

## 4. 旧批次和旧脚本保留策略

- 旧批次目录不动。
- 旧脚本不删除、不移动、不重命名。
- 旧脚本通过《脚本资产台账.csv》分级管理。
- C/D 类脚本默认只作为历史经验和问题定位资料，不作为新病种执行入口。
- 极高风险脚本必须进入禁止直接执行清单。
- 未来只迁移公共能力，不迁移历史副作用。

## 5. 脚本资产分类标准

复用等级：

```text
A类：公共可复用，可迁移到未来 kg_pipeline。
B类：批次专用，只适用于某个疾病或批次。
C类：一次性修复，已完成任务，后续不建议直接复用。
D类：风险脚本，会删除/覆盖/直接写 Neo4j/批量改关系，暂不删除但禁止直接执行。
E类：废弃或用途不明。
```

风险等级：

```text
低风险：只读、只统计、只生成报告。
中风险：生成本地 delta/候选/审计文件，但不写数据库。
高风险：修改本地正式产物，或生成可直接导入图谱的数据。
极高风险：直接写 Neo4j、删除 Neo4j、批量修改实体/关系。
```

本次静态扫描结果：

```text
脚本总数：68
A类：27
B类：6
C类：27
D类：8
E类：0
低风险：3
中风险：37
高风险：20
极高风险：8
```

## 6. 未来 kg_pipeline 目标结构

本次不创建目录，仅定义目标结构：

```text
kg_pipeline/
  config/              batch_config.yaml、启动参数、范围校验
  source_manifest/     资料登记、PDF/教材清单、文件hash
  parsing/             PDF、DOCX、OCR、文本抽取
  terminology/         术语标准化、alias、同义词、字典校验
  skeleton/            学科骨架、疾病大类、疾病、分型、槽位
  graph_build/         nodes/relations/evidence 构建
  audit/               本地质量审计、Schema审计、CDSS审计
  delta/               可导入 delta 生成
  import_gate/         导入前预检、导入后服务器体检、一致性校验
  reporting/           统计报告、交接报告、专家审核包
```

## 7. 第一批适合迁移的模块

第一批只迁移低副作用公共能力：

```text
1. batch_config.yaml 读取与 G0 启动闸门
2. 资料 manifest 生成
3. PDF/DOCX/OCR 解析封装
4. 术语字典校验与 alias 增量登记
5. 教材骨架锚点矩阵生成
6. 本地图谱审计
7. 证据链审计
8. 统计报告生成
9. 服务器只读体检
```

暂不迁移：

```text
repair_*
delete_*
dedupe_neo4j_*
import_*
特定病种 build_*_evidence
历史一次性 definition delta 脚本
```

## 8. 禁止直接执行的脚本类型

以下脚本类型必须先进入审批/预检，不得凭上下文直接运行：

```text
import_*.py
delete_*.py
dedupe_neo4j_*.py
repair_*clinical_safety*.py
任何包含 DETACH DELETE / DELETE / MERGE / SET 并连接 Neo4j 的脚本
任何会批量覆盖 nodes/relations/evidence 正式产物的脚本
```

执行前必须有：

```text
本地备份
输入 delta hash
dry-run 或只读预检
服务器目标库确认
导入 manifest
导入后服务器回执
导入后全局体检
```

## 9. 新病种以后如何通过 batch_config.yaml 执行

未来新病种不再直接指定脚本，而是先创建批次配置：

```yaml
batch_id: BATCH-CARD-XXX-YYYYMMDD-001
specialty: 心血管内科
disease_category: 心律失常
scope_type: 专病
scope_target:
  - 疾病名称
source_roots:
  guideline: E:/.../心血管内科/诊疗指南
  textbook: E:/.../心血管内科/书籍教材
output_root: E:/.../AI专科知识图谱生成/心血管内科文献集合
allow_neo4j_write: false
allow_skill_schema_change: false
run_gates:
  - G0_startup
  - G1_local_audit
  - G2_import_precheck
  - G3_server_postcheck
```

执行入口只允许读取配置，不允许每个病种新写临时脚本。

## 10. 四级闸门机制

```text
G0 启动闸门：确认学科、疾病大类、病种范围、PDF路径、教材路径、输出路径、是否允许写库。
G1 本地闸门：nodes/relations/evidence/audit 必须通过，本地无空壳、无重复、无技术名。
G2 导入闸门：delta 唯一性、证据链、推荐字段、禁忌/排除条件、适用人群检查通过。
G3 服务器闸门：导入后服务器全局体检，确认非KGNode、重复、空壳、诊断明细、治疗动作、推荐证据链。
```

## 11. 本地文件与 Neo4j 一致性机制

不是永远不连 Neo4j，而是分阶段、分权限连接：

```text
脚本盘点阶段：不连 Neo4j。
本地构建阶段：默认不连 Neo4j。
导入前预检：可只读连接 Neo4j。
正式导入：必须走 import_gate 写 Neo4j。
导入后体检：只读连接 Neo4j。
一致性校验：只读连接 Neo4j。
```

每次写库必须形成闭环：

```text
本地 nodes/relations/evidence
→ delta_nodes/delta_relations
→ import_manifest.json
→ server_import_result.json
→ server_postimport_gate.json
→ server_entity_count_snapshot.json
→ server_sample_query_check.json
→ import_ledger.csv / 批次登记台账.md
```

一致性检查至少包括：

```text
本地 delta node 数 = 服务器新增/更新 node 数
本地 delta relation 数 = 服务器新增/更新 relation 数
relation semantic key 在服务器唯一
evidence_id 在服务器存在
disease_code 在服务器存在
条件性 definition 不参与 formal_cdss_ready=true 推荐关系
```

## 12. 如何保证不再每个病种重复写脚本

- 所有病种共用 batch_config.yaml。
- 所有公共逻辑进 kg_pipeline 模块。
- 病种差异只允许放在配置、术语字典、source_manifest、规则模板中。
- 新增脚本前必须先登记脚本资产台账。
- 若脚本只为单病种补洞，默认标 C 类或 B 类，不进入公共入口。

## 13. 和现有 SKILL、Schema、步骤记录、踩坑日志衔接

- SKILL：定义执行纪律和用户命令入口。
- Schema：定义实体、关系、字段标准。
- kg_pipeline：执行公共流程，不替代 Schema。
- 步骤记录：记录每轮任务问题、方案、结果。
- 踩坑日志：沉淀错误根因和复用规则。
- 批次台账：记录资料、批次、导入、服务器状态。
- 脚本资产台账：记录脚本用途、风险、迁移建议。

本次不修改 SKILL 和 Schema。后续如要把这些规则固化进 SKILL，需要单独任务确认。

## 14. 上下文压缩与多账号交接机制

长期机制不能依赖聊天上下文。固定规则：

```text
1. 每次任务结束必须更新 SNAPSHOT。
2. 大任务拆成可验收小任务。
3. 关键路径、服务器结果、导入文件必须落文件。
4. 新账号接手先读 SNAPSHOT + 交接文件 + 步骤记录 + 踩坑日志。
5. 回复默认使用：结论、已做、发现问题、生成文件、是否写库、下一步。
```

## 15. 下一步最小可执行动作

下一步不是迁移代码，而是建立第一个最小公共执行壳：

```text
只新增 kg_pipeline 方案级目录设计，不移动旧脚本；
先实现 batch_config.yaml 模板 + G0 启动闸门只读校验；
再把 prepare_medical_kg_batch.py、preflight_new_disease_batch.py 的公共逻辑抽成可复用函数。
```

在此之前，不建议继续用临时脚本启动新病种。

## 16. 已落地的 G0 方案入口

本轮已先落地两个非代码入口文件：

```text
batch_config模板.yaml
G0启动闸门设计.md
```

这两个文件的作用：

```text
batch_config模板.yaml：以后新病种/新批次的统一启动参数模板。
G0启动闸门设计.md：定义启动前必须检查的范围、路径、骨架、权限、输出目录和禁止事项。
```

当前仍未创建真正 `kg_pipeline/` 代码目录，未迁移旧脚本，未连接 Neo4j，未写库。
