# Schema Documentation Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 将主Schema从大而全的历史/案例/迁移混合文档，瘦身为当前执行标准，并把历史、字段细则、兼容禁用清单、CDSS案例迁入附录。

**Architecture:** 主Schema只保留当前实体、关系、字段、硬闸门和关键边界；附录保留完整历史和长示例；服务器数据本轮不迁移。

**Tech Stack:** Markdown、Neo4j只读统计、Python文档整理。

## Global Constraints

- 不删除历史内容，先归档再瘦身。
- 本轮不写Neo4j。
- Specialty 明确为多学科顶层根节点，禁止作为瘦身候选。
- has_recommended_action 文档上标记为旧命名/阶段候选动作，下一步数据迁移再处理。

---

### Task 1: 建立schema_docs附录结构

- [ ] 创建 schema_docs/。
- [ ] 归档当前完整Schema。
- [ ] 迁出历史变更、兼容禁用清单、字段细则、CDSS动态流程说明。

### Task 2: 重写主Schema为精简执行版

- [ ] 主Schema保留版本、核心原则、实体表、关系表、字段概要、硬闸门。
- [ ] 明确 Specialty 战略保留。
- [ ] 明确 has_recommended_action 与 
ecommends_action 区分，并将前者列入后续改名候选。

### Task 3: 更新对接与记录

- [ ] 更新Trae提示词。
- [ ] 更新交接、步骤记录、踩坑日志、瘦身报告。
- [ ] 验证文件存在、大小下降、版本一致。
