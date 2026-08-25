# 肿瘤 TNM 分期规则引擎与 AI 分析方案

版本：V1.0（设计稿）
更新时间：2026-08-20
配套文档：《专科知识图谱Schema标准》V3.0、《肿瘤专科知识图谱Schema结构规范》V1.0（第 3.1 章 `oncology_tnm_staging`）

---

## 0. 项目背景与目标

- **工程目标**：基于上海肿瘤历史 **50 万病例**，批量分析 TNM 分期结果，给到医院**最终的分期结果 + 分析依据**。
- **核心诉求**：各癌种有各自的分期指南要求；用知识图谱**维护分期推导知识**（而非只存分期结果），后续 AI 分析时**调取图谱规则**做更精准的分期。
- **四大分期规则族（特征提取与用法）**：
  1. **T 分期规则**：肿瘤大小 + 浸润深度 → T；侵犯结构 + 侵犯关系 → T；同器官内癌结节 → T/N（结直肠为肠旁癌结节，归 N1c）
  2. **N 分期规则**：阳性淋巴结数目 + 淋巴结位置 → N
  3. **M 分期规则**：转移器官 → M
  4. **Stage Group 规则**：T、N、M → 分期结果

---

## 1. 范式升级：从"存 TNM 结果"到"存可计算的分期规则"

既有《肿瘤专科知识图谱Schema结构规范》第 3.1 章 `oncology_tnm_staging` 槽位，把 `TCategory / NCategory / MCategory / TNMTStage` 当作**展示与路由结果**来存储（实体 + `disease_has_tnm_stage` 关系）。这对"已知分期、解释分期"够用，但**无法支撑"从临床特征反推分期"**——而 50 万病例分析恰恰要做的是后者。

本方案在 3.1 之上补一层**可计算的分期推导规则**，二者分工如下：

| 层 | 由谁定义 | 存什么 | 用途 |
|---|---|---|---|
| **分期词汇表**（已有 3.1 槽位） | Schema 规范 | T/N/M/Stage 的**合法取值枚举**（如 T1a、N2、M1b、IIIA）及其与疾病/推荐的关系 | 知识展示、治疗路由、结果归一 |
| **分期推导规则**（本方案新增） | 知识图谱 RuleSet | **从临床特征 → 分期取值**的结构化条件映射 | AI 计算分期、输出分析依据 |

> 一句话：3.1 定义"分期能取哪些值"，本方案定义"怎么从病历特征算到这些值"。图谱存**规则**，不存 50 万例各自的分期结果；分期结果在分析任务中**按需计算**。

---

## 2. 知识图谱如何维护各癌种的分期知识

### 2.1 隔离单元：RuleSet（规则集）

每个癌种的分期规则，按 **(癌种, 分期体系/版本)** 隔离成独立的 `RuleSet` 节点。不同癌种、不同指南版本互不污染，可并存、可追溯。

```text
Disease(结直肠癌 CRC)
  └─ has_staging_rule_set → CancerStagingRuleSet
        ├─ staging_system: AJCC   edition: 8th
        ├─ has_T_rule → TStageRule (×N)
        ├─ has_N_rule → NStageRule (×N)
        ├─ has_M_rule → MStageRule (×N)
        └─ has_stage_group → StageGroupRule / StageGroupTable (×N)

Disease(胃癌)
  └─ has_staging_rule_set → CancerStagingRuleSet
        ├─ staging_system: AJCC   edition: 8th
        └─ ...（结直肠癌的 T/N/M/Stage 规则与胃癌完全不同，独立维护）
```

**隔离原则**（呼应落地导向"四角色可运维"）：
- 知识专员用**业务语言**（"肿瘤最大径 > 3cm 且 ≤ 5cm 判 T2"）增删改规则，**不写代码**；
- 平台把业务语言翻译成图里的结构化规则节点；
- 信息科导入/回滚规则配置包，不碰规则语义；
- 实施工程师导出 `(癌种, 体系, 版本)` 的规则 JSON 对接分析任务。

### 2.2 规则节点结构化字段

每条规则是一个图节点，条件用**结构化数组**表达，保证 AI 可无歧义执行：

```yaml
RuleSet:
  rule_set_id:        RS_CRC_AJCC8
  cancer_type:        结直肠癌              # 关联 Disease 节点
  staging_system:     AJCC
  edition:            8th
  icd_scope:          ["C18","C20"]        # 适用 ICD 范围
  source:             "AJCC Cancer Staging Manual 8th / CSCO 结直肠癌 指南"
  version_status:     active               # active / deprecated / draft

TStageRule / NStageRule / MStageRule 通用字段:
  rule_id:            T_CRC_T3_pericolic
  component:          T | N | M
  result:             T2                    # 指向 3.1 词汇表的合法取值
  priority:           200                   # 越大越严重，AI 按降序匹配，命中即停
  conditions:         [ {feature, operator, value, qualifier?}, ... ]  # AND 关系
  evidence_text:      "肿瘤最大径 >3cm 且 ≤5cm，或侵犯主支气管（距隆突≥2cm）……"  # 指南原文
  source_ref:         "AJCC 8th p.21 / CSCO 2024 p.33"

StageGroupRule（组合映射）字段:
  rule_id:            SG_CRC_IIIB
  t_pattern:          ["T1","T2","T3"]       # 命中集合
  n_pattern:          ["N2"]
  m_pattern:          ["M0"]
  result:             IIIA                   # 指向 3.1 词汇表
  source_ref:         ...
```

### 2.3 与图谱主结构的衔接

| 规则节点引用 | 指向 | 说明 |
|---|---|---|
| `RuleSet.cancer_type` | `Disease` | 规则归属哪个癌种 |
| `RuleSet.staging_system` | 新建 `StagingSystem` 节点（或字符串属性） | 区分 AJCC / CSCO / CACA / 卫健委 |
| `*.result` | 3.1 槽位的 `TCategory/NCategory/MCategory/TNMTStage` 取值 | 结果必须落在词汇表内（治理闸门） |
| `*.evidence_text` + `source_ref` | `Evidence` / `SourceSection` | 每条规则可回溯到指南原文（分析依据的来源） |

> 治理要求：规则 `result` 必须是 3.1 词汇表已有取值；新增分期取值先扩词汇表，再写规则。避免规则产出"野生分期"。

---

## 3. 特征数据提取模型（四大规则族）

下面给出 AI 从病历/病理/影像报告中**抽取的特征 schema**，以及**每个特征如何喂给对应规则**。这是"主要提取特征数据以及如何使用"的落地规格。

### 3.1 通用特征总览

| 规则族 | 输入特征 | 输出 |
|---|---|---|
| T | `tumor_size_mm`、`invaded_structures`、`tumor_deposits` | T 取值 |
| N | `involved_node_stations`、`tumor_laterality` | N 取值 |
| M | `metastatic_sites` | M 取值 |
| Stage Group | `T`（来自 T 规则）、`N`（来自 N 规则）、`M`（来自 M 规则） | 分期结果 |

### 3.2 T 分期特征（3 条子规则）

| 子规则 | 特征字段 | 类型 | 取值/单位 | 如何使用 |
|---|---|---|---|---|
| **T-大小** | `tumor_size_mm` | number | 毫米（最大径） | 与阈值比较：`operator ∈ {≤, <, ≥, >, between}`，如 `between(2000,3000)`→T1c（单位统一为 mm 防错） |
| **T-侵犯** | `invaded_structures` | enum[] | 被侵犯的邻近结构枚举，如 `pericolic_fat`(肠周脂肪/T3)、`visceral_peritoneum`(脏层腹膜/T4a)、`adjacent_organ`(邻近器官如子宫/膀胱/小肠/T4b)、`mesorectal_fascia`(直肠系膜筋膜/CRM阳性) | `operator=contains_any`，命中任一即触发对应 T；如含 `pericolic_fat`→T3，含 `visceral_peritoneum`→T4a，含 `adjacent_organ`→T4b |
| **T-肠旁癌结节** | `tumor_deposits` | enum | `none` / `single_deposit`(单枚癌结节/肿瘤沉积) / `multiple_deposits`(多枚) | 结直肠 AJCC 8th：肠旁/肠系膜癌结节（肿瘤沉积 TD）归 **N1c**（区域淋巴结范畴），不计入 M；无阳性淋巴结时记为 N1c，有阳性淋巴结时升级 N 分期（见 4.4 冲突处理） |

> 特征抽取说明：`tumor_size_mm` 优先取病理标本径线，缺失取影像（CT）长径；`invaded_structures` 由影像/术中所见/病理浸润描述经 NER 抽取；`tumor_deposits` 由影像/病理报告"肠旁癌结节/肿瘤沉积"判定。

### 3.3 N 分期特征（数目 + 位置）

| 特征字段 | 类型 | 取值 | 如何使用 |
|---|---|---|---|
| `positive_node_count` | number | 阳性区域淋巴结枚数 | 结直肠 AJCC 8th：1–3 枚→N1，≥4 枚→N2；直肠癌侧方淋巴结(髂内/闭孔)阳性归区域 N |
| `node_location` | enum[] | 淋巴结位置枚举，如 `pericolic`(结肠旁)、`intermediate`(中间组)、`apical`(肠系膜根部/高位)、`lateral_pelvic`(直肠侧方) | `operator=contains_any`：侧方淋巴结(直肠癌)阳性→N1，肠系膜根部阳性按数目归入 N1/N2 |

> 关键：N 分期不能只看"有没有淋巴结"，必须结合**数目与位置**。规则写成 `positive_node_count between 1..3 AND node_location contains pericolic/intermediate → N1`；≥4 枚或高位/侧方阳性 → N2。

### 3.4 M 分期特征（转移器官）

| 特征字段 | 类型 | 取值 | 如何使用 |
|---|---|---|---|
| `metastatic_sites` | enum[] | 转移器官/部位枚举，如 `liver`(肝)、`peritoneum`(腹膜种植)、`lung`(肺)、`bone`(骨)、`distant_node`(远处淋巴结)、`ovary`(卵巢/Krukenberg)、`abdominopelvic_wall`(盆腹壁) | `operator=contains_any` + 计数：单器官→M1b；多器官→M1c；腹膜种植/远处淋巴结→M1a（结直肠 AJCC 8th 细分） |

### 3.5 Stage Group 特征（组合映射）

| 输入（均来自前序规则） | 类型 | 如何使用 |
|---|---|---|
| `T`（T 规则输出） | enum | 与 `N`、`M` 组合查 StageGroup 表 |
| `N`（N 规则输出） | enum | 同上 |
| `M`（M 规则输出） | enum | M1 任何值 → 直接 IV 期（IVA/IVB 再按器官数细分），不进 0–IIIC 组合表 |

> Stage Group 本质是 **(T,N,M) → Stage 的查找表**，按 (癌种, 体系) 存为 `StageGroupRule` 集合或一张 `StageGroupTable`。不建议用布尔规则硬套，组合爆炸难维护。

---

## 4. AI 分析时如何拿图谱数据算分期（端到端流程）

### 4.1 流程

```text
① 识别癌种        病例 → Disease 节点（如 结直肠癌，ICD C18/C20）
② 定位规则集      按 (癌种, 配置的分期体系/版本) 取 RuleSet
                   例：结直肠癌 + AJCC 8th → RS_CRC_AJCC8
③ 抽取特征        从 EMR/病理/影像结构化字段 + Dify 后结构化抽取 → 3.1~3.4 特征对象
④ 计算 T          取该 RuleSet 的全部 TStageRule，按 priority 降序，逐条匹配 conditions，
                   命中第一条即停 → T 取值
⑤ 计算 N          同理用 NStageRule + (involved_node_stations, tumor_laterality)
⑥ 计算 M          同理用 MStageRule + metastatic_sites
⑦ 计算 Stage      用 StageGroupRule/Table，输入 (T,N,M) → 分期结果（M1 优先短路）
⑧ 输出结果与依据  最终分期 + 每个分量的命中规则 + evidence_text + source_ref
```

### 4.2 图谱查询示例（Cypher）

```cypher
// 取某癌种某体系下的全部分期规则
MATCH (d:Disease {name:'结直肠癌'})
      -[:has_staging_rule_set]->(rs:CancerStagingRuleSet {staging_system:'AJCC', edition:'8th'})
OPTIONAL MATCH (rs)-[:has_T_rule]->(t:TStageRule)
OPTIONAL MATCH (rs)-[:has_N_rule]->(n:NStageRule)
OPTIONAL MATCH (rs)-[:has_M_rule]->(m:MStageRule)
OPTIONAL MATCH (rs)-[:has_stage_group]->(sg:StageGroupRule)
RETURN rs, collect(t) AS T, collect(n) AS N, collect(m) AS M, collect(sg) AS SG
```

```cypher
// 取单条规则的原文依据（分析依据溯源）
MATCH (r:TStageRule {rule_id:'T_CRC_T4b_adjacent_organ'})
RETURN r.result, r.conditions, r.evidence_text, r.source_ref
```

### 4.3 输出物（给医院的最终交付）

对每例病例输出结构化结果：

```json
{
  "case_id": "SH-2023-000123",
  "cancer_type": "结直肠癌",
  "staging_system": "AJCC 8th",
  "T": {
    "value": "T2",
    "matched_rule": "T_CRC_T3_pericolic",
    "basis": "肿瘤穿透肌层侵犯肠周脂肪（影像+病理）",
    "evidence": "肿瘤穿透肠壁肌层至肠周组织评为 T3 —— AJCC 8th"
  },
  "N": {
    "value": "N2",
    "matched_rule": "N_CRC_N1_pericolic",
    "basis": "结肠旁区域淋巴结 1–3 枚受累",
    "evidence": "区域淋巴结 1–3 枚转移为 N1 —— CSCO 结直肠癌"
  },
  "M": { "value": "M0", "matched_rule": "M_CRC_M0", "basis": "未见远处转移", "evidence": "..." },
  "stage": {
    "value": "IIIA",
    "matched_rule": "SG_CRC_IIIB",
    "basis": "T3N1M0 组合",
    "evidence": "T3N1M0 归为 IIIB 期 —— AJCC 8th 分期表"
  },
  "confidence": 0.92,
  "warnings": []
}
```

### 4.4 置信度与冲突处理

- **置信度**：特征字段完整度 + 规则命中清晰度。特征缺失（如未报淋巴结站）→ 该分量置信度降、标 `warnings`。
- **规则冲突**：同一分量多条规则同时命中（不应发生，因 priority 降序取首条）；若数据异常导致矛盾，记录所有候选并交人工审核。
- **肠旁癌结节陷阱**：结直肠中肠旁癌结节/肿瘤沉积（TD）归 **N1c**（区域淋巴结范畴）而非 M，规则集须在命中癌结节时**短路 N 规则**而非 M 规则（归 N1c 而非 M1a）。这是各癌种规则差异的典型，必须由知识专员按该癌种指南显式配置。

---

## 5. 落地建议与待确认项

### 5.1 建议落地路径

1. **先做结直肠癌 AJCC 8th 样板规则集**：把结直肠癌的 T/N/M/StageGroup 规则全部结构化入图，跑通 4.1 流程，验证 50 万例中的结直肠癌子集。
2. **规则维护界面**：知识专员用业务语言（"肿瘤最大径 >3cm 且 ≤5cm 判 T2"）增删改，平台翻译为规则节点；导出 `(癌种,体系,版本)` JSON 配置包。
3. **特征抽取对齐**：确认 50 万病例源数据里 `tumor_size / 侵犯结构 / 淋巴结站 / 侧别 / 转移器官` 这些字段从哪些系统/文书抽取（HIS 术记、病理报告、PACS 影像报告、Dify 后结构化），做字段映射。
4. **分期词汇表扩展**：若 3.1 槽位缺某取值（如 T1c、M1c），先扩词汇表再写规则。

### 5.2 待你确认

- **各癌种采用哪套分期体系/版本**（AJCC 8th？CSCO？CACA？是否多套并存由分析任务指定）？
- **首期覆盖哪些癌种**（建议结直肠癌先行，再扩子宫颈癌/卵巢癌/胃/肝/乳腺）？
- **50 万病例的特征字段来源映射**是否已有结构化字段，还是需要 Dify 后结构化补抽？
- 本方案的规则节点模型是否要**追加进 `公共执行层_kg_pipeline/专病扩展槽位配置.yaml`**（作为 `oncology_tnm_staging` 槽位的"规则子结构"），还是单独一个 staging_rules 配置？

---

## 附录 A：特征 → 规则 → 取值 速查（结直肠癌 AJCC 8th 样例）

| 规则族 | 特征（抽取） | 规则条件（结构化） | 取值 |
|---|---|---|---|
| T | invaded_structures 含 pericolic_fat | contains_any(pericolic_fat) | T3 |
| T | invaded_structures 含 visceral_peritoneum | contains_any(visceral_peritoneum) | T4a |
| T | invaded_structures 含 adjacent_organ | contains_any(adjacent_organ) | T4b |
| N | positive_node_count=2, location=pericolic | count 1..3 ∧ 区域 | N1 |
| N | positive_node_count=5, location=apical | count≥4 | N2 |
| M | metastatic_sites=[liver] | count==1 ∧ organ∈远处 | M1b |
| M | metastatic_sites=[peritoneum,lung] | count>1 | M1c |
| Stage | T3 ∧ N1 ∧ M0 | 组合查表 | IIIB |
| Stage | anyT ∧ anyN ∧ M1 | M 优先短路 | IVA/IVB |
