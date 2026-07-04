---
name: medical-kg-report-statistics
description: Use when generating summary reports for the medical literature parsing and specialty knowledge graph workflow.
---

# AI自动化工具-文献指南解析-报告统计

版本：V1.0  
适用目录：`E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成`  
用途：基于已生成的批次产物，输出学科、疾病大类、专病、资料利用、图谱维度和服务器安全状态统计报告。

## 1. 统计原则

- 统计报告只读取已经生成的标准产物，不重新解析 PDF，不直接写 Neo4j。
- 最终服务器状态以 `99_全局安全体检_global_safety_check/*/01_服务器全库硬闸门_summary.json` 的最新结果为准。
- 本地图谱规模以 `06_quality_audit/quality_gate_summary.json` 为主；若缺失，则回退到 `05_data_instance/nodes_final.jsonl` 和 `relations_final.jsonl` 逐行统计。
- 资料利用数量分两类：
  - `纳入解析文件数`：`source_documents_manifest.csv` 中 `inclusion_status=included` 的文件数。
  - `产生证据文档数`：`guideline_evidence_summary.json` 中 `document_with_evidence_count`。
- 资料总数必须按“唯一资料名称”统计：同一资料同时存在 `.pdf`、`.docx`、`.doc` 等格式时，只算 1 份，同时在报告中标注已有格式和原始文件数。
- 书籍教材与指南 PDF 必须分开统计；教材用于基础骨架，指南/共识用于专病决策血肉。

## 2. 必须覆盖的报告维度

每次报告至少包含：

1. 资料总库统计：指南目录、教材目录、PDF、DOCX、支持格式总数。
2. 学科/疾病大类/疾病批次统计：批次号、范围、纳入文件、证据文档、节点、关系、疾病数、required 缺口、硬错误。
3. 心血管内科骨架库统计：初版目录骨架、批次增强、教材深层抽取、全书跨章节回捞。
4. 图谱实体维度统计：疾病、证据、指南、症状、体征、检查、检验、诊断标准、风险分层、治疗方案、药物、操作、随访、阈值规则等。
5. 图谱关系维度统计：症状、体征、病因、危险因素、检查、检验、诊断、治疗、药物、操作、随访、证据支撑等。
6. 服务器最终安全体检：非 KGNode、空壳治疗、药物类别缺具体药物、同类型同名重复、语义重复关系。
7. 服务器最终安全体检必须同时输出“人话版”：解释每个指标为 0 到底代表什么、非 0 为什么要阻断。
8. 文件来源说明必须用业务语言解释：哪些数字来自清单、哪些来自本地审计、哪些来自服务器复核。

## 3. 当前再生成命令

在工作目录执行：

```powershell
python scripts/build_report_statistics.py
```

输出文件：

```text
AI自动化工具-文献指南解析-统计报告_YYYYMMDD.html
AI自动化工具-文献指南解析-统计报告_YYYYMMDD.json
```

## 4. 判读规则

- `global_safety_gate_status=passed` 只说明服务器图谱硬闸门通过，不等于正式 CDSS 强推荐上线。
- `knowledge_display` 关系只能用于知识展示；`test_recommendation` 只能用于测试推荐层；`formal_cdss_ready=true` 才能作为正式推荐候选，但仍需正式发布流程。
- `required_pathway_missing_count=0` 是专病闭环的重要条件，但还必须同时满足空壳治疗、药物类别具体化、重复实体、重复语义关系均为 0。

## 5. 维护要求

- 新增专病批次后，必须重新运行本报告脚本。
- 新增图谱维度或 Schema 字段后，必须同步更新 `ENTITY_DIMENSIONS` 或 `RELATION_DIMENSIONS`。
- 发现统计口径变化时，必须同步记录到 `_全局复利与踩坑日志.md` 和 `AI自动化工具-文献指南解析步骤记录.md`。
