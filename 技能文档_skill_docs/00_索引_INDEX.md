# 技能文档索引

更新时间：2026-07-11 23:55:00

本目录承接 `AI自动化工具-文献指南解析.md` V2.0 精简后迁出的细则。主 SKILL 只保留执行总纲，细节按任务阶段读取。

## 文件清单

| 文件 | 用途 |
|---|---|
| `SKILL规则迁移覆盖矩阵_rule_mapping_20260711.csv` | 证明旧 SKILL 的 P0/P1 规则没有丢失 |
| `附录A_批次启动与范围确认_scope_batch.md` | 启动范围、路径、批次编号、目录规则 |
| `附录B_来源体系与教材骨架_sources_skeleton.md` | 教材骨架、指南血肉、来源优先级 |
| `附录C_PDF解析OCR与证据抽取_pdf_ocr_evidence.md` | PDF/OCR、Evidence、RecommendationStatement |
| `附录D_实体归一别名术语字典_terminology_alias.md` | 同义词、药品、检查、alias 规则 |
| `附录E_Schema映射与CDSS决策层_schema_cdss.md` | Schema、诊断组件、鉴别诊断、规则引擎分工 |
| `附录F_质量闸门审计与Neo4j入库_quality_neo4j.md` | G1/G2/G3/G4、Neo4j 入库、postcheck |
| `附录G_日志归档错误指纹与交接_handoff_logs.md` | 步骤记录、踩坑日志、错误指纹、交接模板 |

## 使用顺序

1. 先读主 SKILL。
2. 再按当前阶段读对应附录。
3. 涉及规则迁移或重构时查覆盖矩阵。
4. 任务结束更新步骤记录、交接文件和必要的错误指纹。
