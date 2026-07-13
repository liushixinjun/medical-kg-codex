# 00_当前项目状态_SNAPSHOT

更新时间：2026-07-14 08:20:00

## 当前阶段
心血管内科图谱处于“全库质量治理 + 已解析疾病 CDSS 决策层补强”阶段。

## 最新完成
- `BATCH-CARD-DXC-AVB-COMP-20260714-001` 已导入 Neo4j。
- 传导阻滞共享诊断标准补齐 8 个下钻明细组件。
- 全库 `diagnosis_criteria_without_component`：6 → 0。
- 全库 `required_lab_without_indicator_or_evidence`：0。

## 当前核心问题
- 全量 `RecommendationStatement` 仍有 53 条候选治理缺口；其中正式 CDSS 推荐缺核心链路为 0。
- VTE 骨架存在历史段落污染线索，已登记为独立治理任务，未混入本轮。

## 本次不做什么
- 不清理 VTE 历史污染。
- 不新增外部网页证据。
- 不修改 Schema/SKILL 主文档。
- 不删除历史批次。

## 关键文件入口
- 本轮批次：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\BATCH-CARD-DXC-AVB-COMP-20260714-001_传导阻滞诊断标准明细补齐_AVB_SAB_diagnosis_component_refine`
- 后置体检：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成\心血管内科文献集合\00_全局质量体检_global_quality_audit\20260714_after_avb_diagnosis_component_refine`
- 步骤记录：`AI自动化工具-文献指南解析步骤记录.md`
- 踩坑日志：`_全局复利与踩坑日志.md`

## 下一步唯一建议动作
治理 53 条全量 RecommendationStatement 候选缺口，先统计缺口类型，再决定补证据、补 action/guideline 关系，或降级为非正式 CDSS 展示。

---

# 00_当前项目状态_SNAPSHOT

更新时间：2026-07-13 23:27:54

## 当前阶段
心血管内科图谱进入“全库质量治理 + 已解析疾病 CDSS 决策层补强”阶段。

## 最新完成
- `BATCH-CARD-HT-LABIND-20260713-001` 已导入 Neo4j。
- 高血压 required LabTest 缺口 51→0。
- 全库 required LabTest 缺口 56→2。
- 本轮新增/更新节点 9、关系 28。

## 当前核心问题
- 剩余 2 条 required LabTest 缺口均为 D-二聚体，需要回原文补证据，不能跨疾病套用 AMI 同名证据。
- `RecommendationStatement` 缺核心链路真实为 344 条，旧报告 100 是 LIMIT 截断。
- 诊断标准无明细 24 条仍需治理。

## 下一步唯一建议动作
按疾病大类批量治理 RecommendationStatement 和 DiagnosisCriteria：优先冠心病、心肌病、心力衰竭、心律失常、高血压。

---

# 当前项目状态 SNAPSHOT

更新时间：2026-07-09 08:10:00

## 当前阶段

项目处于“心血管内科骨架稳定 + 专病样板治理 + 脚本资产盘点与公共执行层设计”阶段。当前不是继续扩新病种的最佳时点，应先稳定骨架和专病业务闭环。

## 当前核心问题

1. 心血管内科骨架信息仍未完全稳固，部分疾病、分型、临床状态、并发症边界需要继续治理。
2. 服务器图谱知识展示层基本可用，但正式 CDSS 推荐仍有业务阻断。
3. scripts/ 下已有 68 个 Python 脚本，包含公共脚本、病种脚本、一次性修复脚本、Neo4j 风险脚本，需要台账化管理。
4. 长上下文和 Plus 对话额度不足，后续必须依赖文件化交接，而不是聊天记忆。

## 已完成内容

- 已形成统一 SKILL 和 Schema 标准。
- 已构建心血管内科教材骨架与多个专病样板。
- 优先 68 疾病 definition 已复核：68/68 非空。
- 服务器全局体检已完成：非KGNode=0、同类型同名重复=0、技术编码名=0、药物类别缺具体药物=0。
- 本轮完成 scripts 静态盘点，脚本总数 68 个，并生成脚本资产台账。
- 已新增 `batch_config模板.yaml` 和 `G0启动闸门设计.md`，作为未来新病种/新批次启动前的统一入口设计。

## 服务器是否写入

本轮脚本资产盘点和 G0 设计任务没有连接 Neo4j，没有写数据库，没有导入图谱，没有运行修复脚本。

最近一次服务器安全体检结论：

```text
知识展示：可用
专病诊疗流程：需先修复阻断项
正式 CDSS 推荐：不可直接上线
```

主要阻断：

```text
疾病definition为空=32
诊断标准无明细=4个诊断标准节点
治疗方案无下游动作=46
推荐关系缺核心字段=1104
```

## 本次不做什么

```text
不连接 Neo4j
不写数据库
不导入图谱
不运行修复脚本
不删除/移动/重命名旧脚本
不修改旧批次目录
不修改历史 nodes/relations/evidence/audit/report
不修改 SKILL 和 Schema
不创建真正 kg_pipeline 代码目录
```

## 关键文件入口

```text
脚本资产台账.csv
kg_pipeline渐进式重构方案.md
batch_config模板.yaml
G0启动闸门设计.md
00_当前项目状态_SNAPSHOT.md
当前进度与后续计划_交接.md
AI自动化工具-文献指南解析步骤记录.md
_全局复利与踩坑日志.md
心血管内科文献集合/00_全局质量体检_global_quality_audit/server_global_cdss_safety_audit_report_20260709.md
```

## 下一步唯一建议动作

先不要继续开新病种。下一步建议只做一个小任务：

```text
下一步如果继续推进，只实现 G0_startup_gate 的只读校验小工具：读取 batch_config.yaml，校验必填字段、路径、权限组合，输出 G0_startup_gate_result.json。
```

骨架和业务闭环仍需随后分批治理：

```text
1. 诊断标准无明细
2. 治疗方案无下游动作
3. 推荐关系证据字段
4. 32 个其他疾病 definition 空值
```

## 禁止事项

```text
禁止直接运行 import_*.py
禁止直接运行 delete_*.py
禁止直接运行 dedupe_neo4j_*.py
禁止直接运行 repair_*clinical_safety*.py
禁止未经 G2/G3 闸门直接写 Neo4j
禁止把条件性 definition 当作正式 CDSS 推荐触发依据
禁止新病种继续靠临时脚本补洞
```
# 00_当前项目状态_SNAPSHOT

更新时间：2026-07-14 07:25:00

## 当前阶段

心血管内科图谱进入全库 CDSS 决策层质量治理阶段。

## 最新完成

- `BATCH-CARD-RS-CORELINK-20260714-001` 已导入 Neo4j：新增/回连推荐陈述核心关系 293 条。
- `BATCH-CARD-DXC-COMP-20260714-001` 已导入 Neo4j：新增诊断标准组件 18 个、关系 36 条。
- RecommendationStatement 缺核心链路 344 → 53。
- DiagnosisCriteria 无明细 24 → 6。

## 当前核心问题

- 高血压 50 条推荐陈述缺主证据 code。
- 冠心病 3 条推荐陈述缺动作/指南端点。
- 传导阻滞 6 条诊断标准缺非空证据。
- required LabTest 剩余 2 条 D-二聚体缺当前疾病场景原文证据。

## 下一步唯一建议动作

处理高血压 CDSS 推荐陈述证据补齐，并同步修冠心病 3 条 blocker。

---
## 2026-07-14 07:39:04｜当前状态快照

当前阶段：心血管内科图谱质量治理，已完成推荐核心链路、诊断标准明细、D-二聚体检验指标证据三轮补齐。

已写入服务器：

- `BATCH-CARD-RS-CORELINK-20260714-001`：推荐陈述核心链路补齐，新增关系 293。
- `BATCH-CARD-DXC-COMP-20260714-001`：诊断标准明细组件补齐，新增节点 18、关系 36。
- `BATCH-CARD-LAB-DDIMER-20260714-001`：D-二聚体指标证据补齐，新增指标节点 3、关系 8、关系场景说明 2。

当前硬闸门：

| 指标 | 数量 |
|---|---:|
| 非 KGNode | 0 |
| required LabTest 缺指标或非空证据 | 0 |
| DiagnosisCriteria 无明细组件 | 6 |
| RecommendationStatement 缺证据/动作/指南 | 53 |
| 鉴别诊断无明细 | 0 |
| 重复语义关系 | 0 |

当前核心风险：

- `DIS-CARD-VTE` 发现历史串段污染，外连关系约 844 条，需单独做 VTE 骨架重建/污染清理。
- 传导阻滞相关 6 条诊断标准仍缺明细组件。
- 高血压相关 RecommendationStatement 仍有较多缺原文证据。

下一步唯一建议动作：先提交 D-二聚体批次，再处理 6 条传导阻滞诊断标准明细缺口。
