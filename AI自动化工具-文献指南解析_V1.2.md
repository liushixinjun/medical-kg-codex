---
name: parsing-medical-guidelines
description: Use when starting a specialty, disease-category, or single-disease knowledge-graph task from original medical PDFs, guidelines, textbooks, or expert documents.
---

# AI自动化工具-文献指南解析

版本：V1.2  
Schema：`专科知识图谱Schema标准.md` V1.1  
用途：从原始医学文献生成可审计、可合并的专科知识图谱标准数据实例。

## 变更记录

| 版本 | 日期 | 变更内容 |
|---|---|---|
| V1.0 | — | 初版 |
| V1.1 | 2026-06 | 新增§10实体归一与别名归一化、§11否定事实与极性过滤、§12数值与阈值节点处理规则；原§10–16顺延为§13–19；§9 Schema版本更新为V1.1 |
| V1.2 | 2026-06 | §10.1词表类别抽象为通用模板，新增心肌病、急性心肌梗死两个病种示例；§10.3 prompt注入格式抽象为通用模板，新增两病种注入示例；§12.2阈值规则通用化，新增两病种阈值对照表（含时间窗阈值） |

## 1. 核心原则

- 每次任务只使用本次确认的执行范围和原始文献路径。
- 未确认专科/疾病范围和 PDF/指南路径，不得开始扫描或解析。
- 先生成标准数据实例与审核报告；Neo4j 导入必须单独确认。
- 每条核心知识必须能追溯到原始文献、章节/页码或文本位置及原文片段。
- 文本不合格、疾病归属不明确或 Schema 无法承载时，阻断并报告，不猜测入图。
- 各批次独立抽取、独立验收；验收通过后才能合并到标准主图谱。

## 2. 启动确认闸门

每次新任务必须先向用户展示并确认以下内容：

```text
scope_type: specialty | category | disease
scope_target: 专科名 | 疾病大类名 | 单病种名
source_roots: 原始指南、教材、专家资料根目录
output_root: 本批次输出目录
schema_file: 专科知识图谱Schema标准.md
```

执行范围示例：

```text
scope_type=specialty, scope_target=心血管内科
scope_type=category, scope_target=心肌病
scope_type=disease, scope_target=肥厚型心肌病
```

路径确认时必须列出：

- 根目录绝对路径
- PDF、DOCX、DOC、TXT 文件数量
- 预计纳入与排除数量
- 文件名重复和内容哈希重复数量
- 《内科学》及其他教材路径

只有用户明确回复范围和路径已确认，才可进入文献清单阶段。相同目录在新任务中也必须重新确认。

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
| 2 | 权威教材《内科学》 | 定义、病因、病理生理、流行病学、症状体征、基础诊疗 | `N/A` |
| 3 | 可追溯的专家整理 TXT | 补充指南和教材未覆盖知识 | `N/A`，除非原文明确分级 |
| 4 | 用户人工整理的网页 TXT | 待核验补充来源 | 不得自动赋级 |

禁止自动抓取网页后直接入图。

### 4.2 来源冲突

- 正式推荐、剂量、阈值和证据等级以最新权威指南为准。
- 不删除冲突来源，分别保留证据。
- 输出 `source_conflict_register.csv`，记录主题、来源、冲突内容、采用结论和理由。

## 5. 《内科学》基础证据库

《内科学》作为心血管内科疾病基础知识源，首次使用时完整解析一次并建立可复用证据库。其他专科科疾病需要询问提供对应的学科教材

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

所有实体、关系、字段、编码和证据必须符合根目录 `专科知识图谱Schema标准.md` V1.1。

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
| 美托洛尔 | — | 倍他乐克、metoprolol、β受体阻滞剂（具体药物时） | Medication |
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
2. 《内科学》教材规范全称
3. 常见中文标准名（非俗称、非口语）
4. 中文意译名
```

禁止以英文缩写、英文全称或口语化表述作为 `canonical_name`。同一实体只允许一个 `canonical_name`，不允许因来源不同生成两个主名称节点。

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

多批次合并到标准主图谱时，归一匹配顺序（与 Schema V1.1 §14.2 一致）：

1. 相同全局 `code`
2. 相同 `entityType` ＋ `canonical_name`
3. 受控别名或外部标准编码（ICD/ATC/LOINC）确认同一实体

无法匹配时进入冲突队列，写入 `conflict_status=open`，不自动合并。禁止仅凭名称字符相似度自动合并不同实体。

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

文献中出现的指标阈值，必须建立 `ThresholdRule` 节点，字段按 Schema V1.1 §11.1 填写：

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

任一硬闸门失败，不得标记批次完成。

## 16. 独立批次交付

每个任务创建独立 `batch_id` 和版本化输出目录，至少包含：

```text
00_scope_and_config/
01_source_manifest/
02_page_audit/
03_clean_text/
04_evidence_and_extraction/
05_data_instance/
06_quality_audit/
07_review_package/
```

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
