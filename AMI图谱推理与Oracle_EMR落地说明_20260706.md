# AMI 图谱推理与 Oracle/EMR 落地说明

版本：V1.0  
生成时间：2026-07-06  
适用对象：Oracle/EMR 开发同事、Trae 前端同事、CDSS 接口开发同事  
适用场景：拿到专科知识图谱 Schema 和 Neo4j 图谱数据库后，不知道如何把图谱真正用于临床推理、查询和推荐。

---

## 1. 这份文档解决什么问题

当前同事已经拿到：

- 图谱 Schema；
- Neo4j 图谱数据库连接；
- 前端图谱展示页面；
- EMR/Oracle 业务库。

但还缺一层“应用说明”：  
**临床系统如何用患者 EMR 数据去匹配图谱实体、沿图谱关系推理、再生成诊断/检查/治疗/随访建议。**

本文件用 AMI（急性心肌梗死）作为案例，说明：

1. Oracle/EMR 需要准备哪些患者字段；
2. 图谱中哪些实体和关系要被查询；
3. 每一步推理如何写成 Cypher；
4. 如果 Oracle 不直接写 Cypher，如何转换成类似 SQL 的表结构与查询逻辑；
5. 推荐结果如何带出证据链、指南来源和推荐等级。

---

## 2. 图谱不是“展示网络图”，而是“临床规则知识库”

图谱应用时不要把所有节点一次性拉到前端。正确方式是：

```text
患者 EMR 数据
  -> 抽取结构化事实
  -> 匹配图谱实体
  -> 沿关系查询候选诊断/检查/治疗/禁忌/随访
  -> 用患者条件过滤
  -> 输出推荐 + 证据链 + 来源指南
```

以 AMI 为例：

```text
胸痛 + ST段抬高 + 肌钙蛋白升高
  -> 匹配 Symptom / ExamIndicator / LabTest / DiagnosisCriteria
  -> 推断候选疾病：急性心肌梗死 / STEMI
  -> 查询 STEMI 治疗路径
  -> 判断再灌注策略：PCI / 溶栓
  -> 判断禁忌证：出血风险、抗栓禁忌、肾功能等
  -> 输出 CDSS 推荐
```

---

## 3. 服务器当前 AMI 相关真实图谱节点

当前服务器中 AMI 相关疾病节点包括：

| code | name | aliases |
|---|---|---|
| `DIS-CARD-CAD-AMI` | 急性心肌梗死 | AMI、心梗、心肌梗死、急性心梗 |
| `DIS-CARD-CAD-STEMI` | ST段抬高型心肌梗死 | STEMI、ST抬高心梗、ST段抬高性心肌梗死 |
| `DIS-CARD-CAD-NSTEMI` | 非ST段抬高型心肌梗死 | NSTEMI、非ST抬高心梗、NSTE-ACS |

AMI 图谱关系覆盖方向示例：

| 疾病 | 关系 | 目标实体类型 | 作用 |
|---|---|---|---|
| 急性心肌梗死 | `has_symptom` | Symptom | 识别胸痛、胸闷、出汗等临床表现 |
| 急性心肌梗死 | `has_sign` | Sign | 识别低血压、休克、心衰体征等 |
| 急性心肌梗死 | `requires_exam` | Exam | 心电图、冠脉造影等检查 |
| 急性心肌梗死 | `requires_lab_test` | LabTest | 肌钙蛋白、心肌损伤标志物等 |
| 急性心肌梗死 | `has_diagnostic_criteria` | DiagnosisCriteria | 诊断标准 |
| 急性心肌梗死 | `has_risk_stratification` | RiskStratification | 危险分层 |
| 急性心肌梗死 | `has_treatment_plan` | TreatmentPlan | 治疗策略 |
| 急性心肌梗死 | `treated_by_medication` | Medication | 药物治疗 |
| 急性心肌梗死 | `treated_by_procedure` | Procedure | PCI、CABG、溶栓等操作 |
| 急性心肌梗死 | `may_cause_complication` | Complication | 心衰、心律失常、休克等并发症 |
| 急性心肌梗死 | `has_follow_up` | FollowUp | 出院后随访与复查 |
| 急性心肌梗死 | `based_on_guideline` | Guideline | 指南/教材来源 |
| 任意临床实体 | `supported_by_evidence` | Evidence | 原文证据链 |

---

## 4. 建议给 Oracle 建的“图谱镜像表/视图”

如果 Oracle 侧不直接访问 Neo4j，建议把 Neo4j 同步成两张核心宽表或物化视图。

### 4.1 节点表：KG_NODE

```sql
CREATE TABLE KG_NODE (
    CODE                 VARCHAR2(100) PRIMARY KEY,
    NAME                 VARCHAR2(500),
    PREFERRED_NAME       VARCHAR2(500),
    DISPLAY_NAME         VARCHAR2(500),
    ENTITY_TYPE          VARCHAR2(100),
    ENTITY_CATEGORY      VARCHAR2(100),
    ALIASES_JSON         CLOB,
    DESCRIPTION          CLOB,
    SCHEMA_VERSION       VARCHAR2(50),
    REVIEW_STATUS        VARCHAR2(50),
    CLINICAL_REVIEW_STATUS VARCHAR2(100),
    FORMAL_CDSS_READY    NUMBER(1),
    BATCH_ID             VARCHAR2(200),
    SCOPE_TYPE           VARCHAR2(50),
    SCOPE_TARGET         VARCHAR2(500),
    PROPS_JSON           CLOB
);
```

### 4.2 关系表：KG_RELATION

```sql
CREATE TABLE KG_RELATION (
    REL_ID               VARCHAR2(120) PRIMARY KEY,
    SOURCE_CODE          VARCHAR2(100),
    RELATION_TYPE        VARCHAR2(100),
    TARGET_CODE          VARCHAR2(100),
    RELATION_CATEGORY    VARCHAR2(100),
    POLARITY             VARCHAR2(50),
    DOCUMENT_ID          VARCHAR2(120),
    SEGMENT_ID           VARCHAR2(200),
    SOURCE_NAME          VARCHAR2(1000),
    SOURCE_TYPE          VARCHAR2(100),
    SOURCE_VERSION       VARCHAR2(100),
    SOURCE_SECTION       VARCHAR2(500),
    SOURCE_PAGE          VARCHAR2(100),
    EVIDENCE_TEXT        CLOB,
    GUIDELINE_ID         VARCHAR2(120),
    EVIDENCE_ID          VARCHAR2(120),
    RECOMMENDATION_CLASS VARCHAR2(50),
    EVIDENCE_LEVEL       VARCHAR2(50),
    CONFIDENCE           NUMBER,
    APPLICABLE_POPULATION CLOB,
    EXCLUSION_CRITERIA   CLOB,
    RECOMMENDATION_CONTEXT CLOB,
    CLINICAL_REVIEW_STATUS VARCHAR2(100),
    FORMAL_CDSS_READY    NUMBER(1),
    PROPS_JSON           CLOB
);
```

### 4.3 推荐索引

```sql
CREATE INDEX IDX_KG_NODE_TYPE_NAME ON KG_NODE (ENTITY_TYPE, NAME);
CREATE INDEX IDX_KG_NODE_CODE ON KG_NODE (CODE);
CREATE INDEX IDX_KG_REL_SOURCE_TYPE ON KG_RELATION (SOURCE_CODE, RELATION_TYPE);
CREATE INDEX IDX_KG_REL_TARGET_TYPE ON KG_RELATION (TARGET_CODE, RELATION_TYPE);
CREATE INDEX IDX_KG_REL_SOURCE_TARGET ON KG_RELATION (SOURCE_CODE, TARGET_CODE);
```

---

## 5. EMR 需要准备的患者事实表

图谱推理前，先把 EMR 转成“患者事实”。不要直接拿非结构化病历文本和图谱硬匹配。

### 5.1 患者就诊主表

```sql
EMR_ENCOUNTER (
    PATIENT_ID,
    VISIT_ID,
    AGE,
    SEX,
    DEPT_CODE,
    VISIT_TIME,
    CHIEF_COMPLAINT,
    PRESENT_ILLNESS,
    ADMISSION_DIAGNOSIS
)
```

### 5.2 症状事实

```sql
EMR_SYMPTOM_FACT (
    PATIENT_ID,
    VISIT_ID,
    SYMPTOM_NAME,
    START_TIME,
    DURATION_MINUTES,
    SEVERITY,
    NEGATED_FLAG,
    SOURCE_TEXT
)
```

AMI 示例：

| SYMPTOM_NAME | DURATION_MINUTES | NEGATED_FLAG |
|---|---:|---|
| 胸痛 | 90 | 0 |
| 大汗 | 90 | 0 |
| 呼吸困难 | 30 | 0 |

### 5.3 体征/生命体征事实

```sql
EMR_VITAL_SIGN (
    PATIENT_ID,
    VISIT_ID,
    ITEM_NAME,
    ITEM_VALUE,
    ITEM_UNIT,
    MEASURE_TIME
)
```

AMI 示例：

| ITEM_NAME | ITEM_VALUE | ITEM_UNIT |
|---|---:|---|
| 收缩压 | 86 | mmHg |
| 心率 | 112 | 次/分 |

### 5.4 检查事实

```sql
EMR_EXAM_RESULT (
    PATIENT_ID,
    VISIT_ID,
    EXAM_NAME,
    REPORT_TIME,
    CONCLUSION_TEXT,
    STRUCTURED_FINDING_JSON
)
```

AMI 心电图结构化字段建议：

```json
{
  "ST_ELEVATION": true,
  "ST_ELEVATION_LEADS": ["II", "III", "aVF"],
  "NEW_LBBB": false,
  "Q_WAVE": false
}
```

### 5.5 检验事实

```sql
EMR_LAB_RESULT (
    PATIENT_ID,
    VISIT_ID,
    ITEM_NAME,
    ITEM_VALUE,
    ITEM_UNIT,
    REF_LOW,
    REF_HIGH,
    ABNORMAL_FLAG,
    REPORT_TIME
)
```

AMI 示例：

| ITEM_NAME | ITEM_VALUE | REF_HIGH | ABNORMAL_FLAG |
|---|---:|---:|---|
| 肌钙蛋白I | 2.6 | 0.04 | H |
| CK-MB | 35 | 5 | H |

### 5.6 禁忌证/风险事实

```sql
EMR_CONTRAINDICATION_FACT (
    PATIENT_ID,
    VISIT_ID,
    FACT_NAME,
    PRESENT_FLAG,
    SOURCE_TEXT
)
```

AMI 治疗前至少需要：

| FACT_NAME | 用途 |
|---|---|
| 活动性出血 | 抗栓/溶栓禁忌判断 |
| 近期脑出血 | 溶栓禁忌判断 |
| 严重未控制高血压 | 溶栓风险判断 |
| 已知药物过敏 | 药物推荐过滤 |
| 肾功能不全 | 抗凝/造影风险判断 |

---

## 6. AMI 推理总流程

### 总体流程图

```text
Step 0 读取患者 EMR
  ↓
Step 1 症状/体征匹配：是否疑似 ACS/AMI
  ↓
Step 2 检查/检验匹配：ECG + 肌钙蛋白
  ↓
Step 3 疾病候选排序：AMI / STEMI / NSTEMI
  ↓
Step 4 诊断标准确认：是否达到诊断闭环
  ↓
Step 5 危险分层：休克、心衰、出血风险、缺血风险
  ↓
Step 6 治疗路径查询：再灌注、抗血小板、抗凝、他汀等
  ↓
Step 7 禁忌证过滤：患者不适用的推荐剔除或降级
  ↓
Step 8 输出推荐：推荐项 + 理由 + 证据链 + 指南来源
```

---

## 7. Step 1：用症状/体征推断候选疾病

### 7.1 图谱 Cypher

```cypher
MATCH (d:KGNode {entityType:'Disease'})-[r:has_symptom|has_sign]->(x:KGNode)
WHERE d.code IN ['DIS-CARD-CAD-AMI','DIS-CARD-CAD-STEMI','DIS-CARD-CAD-NSTEMI']
  AND x.name IN $patient_symptoms_or_signs
RETURN
  d.code AS disease_code,
  d.name AS disease_name,
  collect(DISTINCT x.name) AS matched_features,
  count(DISTINCT x) AS match_count;
```

参数示例：

```json
{
  "patient_symptoms_or_signs": ["胸痛", "大汗", "呼吸困难", "低血压"]
}
```

### 7.2 Oracle 类 SQL

```sql
SELECT
    d.code AS disease_code,
    d.name AS disease_name,
    COUNT(DISTINCT x.code) AS match_count,
    LISTAGG(x.name, '、') WITHIN GROUP (ORDER BY x.name) AS matched_features
FROM KG_NODE d
JOIN KG_RELATION r
  ON r.source_code = d.code
JOIN KG_NODE x
  ON x.code = r.target_code
JOIN EMR_SYMPTOM_FACT sf
  ON sf.symptom_name = x.name
 AND sf.patient_id = :patient_id
 AND sf.visit_id = :visit_id
 AND sf.negated_flag = 0
WHERE d.entity_type = 'Disease'
  AND d.code IN ('DIS-CARD-CAD-AMI','DIS-CARD-CAD-STEMI','DIS-CARD-CAD-NSTEMI')
  AND r.relation_type IN ('has_symptom','has_sign')
GROUP BY d.code, d.name
ORDER BY match_count DESC;
```

### 7.3 推理含义

如果患者存在胸痛、大汗、呼吸困难、低血压等，而这些实体与 AMI/STEMI/NSTEMI 存在 `has_symptom` 或 `has_sign` 关系，则将 AMI 类疾病加入候选诊断。

这一阶段只做“疑似”，不能直接下诊断。

---

## 8. Step 2：用心电图和检验确认 AMI 证据

### 8.1 查询 AMI 需要哪些检查/检验

```cypher
MATCH (d:KGNode {code:'DIS-CARD-CAD-AMI'})-[r:requires_exam|requires_lab_test]->(x:KGNode)
RETURN
  type(r) AS relation_type,
  x.entityType AS target_type,
  x.code AS target_code,
  x.name AS target_name,
  r.evidence_text AS evidence_text,
  r.source_name AS source_name,
  r.source_page AS source_page;
```

### 8.2 Oracle 类 SQL：检查患者是否已完成 AMI 必要检查

```sql
SELECT
    x.name AS required_item,
    x.entity_type,
    CASE
      WHEN er.exam_name IS NOT NULL THEN '已完成'
      WHEN lr.item_name IS NOT NULL THEN '已完成'
      ELSE '未完成'
    END AS completion_status
FROM KG_RELATION r
JOIN KG_NODE x
  ON x.code = r.target_code
LEFT JOIN EMR_EXAM_RESULT er
  ON er.patient_id = :patient_id
 AND er.visit_id = :visit_id
 AND er.exam_name = x.name
LEFT JOIN EMR_LAB_RESULT lr
  ON lr.patient_id = :patient_id
 AND lr.visit_id = :visit_id
 AND lr.item_name = x.name
WHERE r.source_code = 'DIS-CARD-CAD-AMI'
  AND r.relation_type IN ('requires_exam','requires_lab_test');
```

### 8.3 AMI 判断逻辑示例

```sql
CASE
  WHEN EXISTS (
      SELECT 1 FROM EMR_EXAM_RESULT
      WHERE patient_id = :patient_id
        AND visit_id = :visit_id
        AND exam_name = '心电图'
        AND JSON_VALUE(structured_finding_json, '$.ST_ELEVATION') = 'true'
  )
  AND EXISTS (
      SELECT 1 FROM EMR_LAB_RESULT
      WHERE patient_id = :patient_id
        AND visit_id = :visit_id
        AND item_name IN ('肌钙蛋白I','肌钙蛋白T','心肌肌钙蛋白')
        AND abnormal_flag = 'H'
  )
  THEN '高度疑似AMI，倾向STEMI'
END
```

注意：这个 SQL 是应用规则示例，正式诊断需要结合图谱中的 `DiagnosisCriteria` 和医院实际数据字典。

---

## 9. Step 3：区分 AMI / STEMI / NSTEMI

### 9.1 核心临床逻辑

```text
胸痛/缺血症状
  + 心肌损伤标志物升高
  + ST段抬高
  -> STEMI

胸痛/缺血症状
  + 心肌损伤标志物升高
  + 无ST段抬高
  -> NSTEMI
```

### 9.2 类 Oracle 伪代码

```sql
WITH patient_ami_facts AS (
    SELECT
        :patient_id AS patient_id,
        :visit_id AS visit_id,
        CASE WHEN EXISTS (
            SELECT 1 FROM EMR_SYMPTOM_FACT
            WHERE patient_id = :patient_id
              AND visit_id = :visit_id
              AND symptom_name IN ('胸痛','胸闷','呼吸困难','大汗')
              AND negated_flag = 0
        ) THEN 1 ELSE 0 END AS has_ischemic_symptom,

        CASE WHEN EXISTS (
            SELECT 1 FROM EMR_LAB_RESULT
            WHERE patient_id = :patient_id
              AND visit_id = :visit_id
              AND item_name IN ('肌钙蛋白I','肌钙蛋白T','心肌肌钙蛋白')
              AND abnormal_flag = 'H'
        ) THEN 1 ELSE 0 END AS has_troponin_elevation,

        CASE WHEN EXISTS (
            SELECT 1 FROM EMR_EXAM_RESULT
            WHERE patient_id = :patient_id
              AND visit_id = :visit_id
              AND exam_name = '心电图'
              AND JSON_VALUE(structured_finding_json, '$.ST_ELEVATION') = 'true'
        ) THEN 1 ELSE 0 END AS has_st_elevation
    FROM dual
)
SELECT
    CASE
      WHEN has_ischemic_symptom = 1
       AND has_troponin_elevation = 1
       AND has_st_elevation = 1
      THEN 'DIS-CARD-CAD-STEMI'

      WHEN has_ischemic_symptom = 1
       AND has_troponin_elevation = 1
       AND has_st_elevation = 0
      THEN 'DIS-CARD-CAD-NSTEMI'

      WHEN has_ischemic_symptom = 1
      THEN 'DIS-CARD-CAD-AMI'

      ELSE NULL
    END AS candidate_disease_code
FROM patient_ami_facts;
```

---

## 10. Step 4：查询诊断标准并形成“诊断理由”

### 10.1 Cypher

```cypher
MATCH (d:KGNode {code:$disease_code})-[r:has_diagnostic_criteria]->(dx:KGNode)
RETURN
  d.name AS disease_name,
  dx.name AS diagnosis_criteria,
  dx.description AS criteria_description,
  r.evidence_text AS evidence_text,
  r.source_name AS source_name,
  r.source_page AS source_page;
```

### 10.2 Oracle 类 SQL

```sql
SELECT
    d.name AS disease_name,
    dx.name AS diagnosis_criteria,
    r.evidence_text,
    r.source_name,
    r.source_page
FROM KG_NODE d
JOIN KG_RELATION r
  ON r.source_code = d.code
JOIN KG_NODE dx
  ON dx.code = r.target_code
WHERE d.code = :candidate_disease_code
  AND r.relation_type = 'has_diagnostic_criteria';
```

### 10.3 输出示例

```json
{
  "candidate_disease": "ST段抬高型心肌梗死",
  "matched_reason": [
    "患者存在胸痛/缺血症状",
    "心电图提示ST段抬高",
    "肌钙蛋白升高"
  ],
  "diagnosis_criteria_source": {
    "source_name": "STEMI CN 2019.pdf",
    "source_page": "1"
  }
}
```

---

## 11. Step 5：查询治疗方案

### 11.1 查询疾病级治疗方案

```cypher
MATCH (d:KGNode {code:$disease_code})-[r:has_treatment_plan]->(plan:KGNode)
RETURN
  plan.code AS plan_code,
  plan.name AS plan_name,
  r.recommendation_class AS recommendation_class,
  r.evidence_level AS evidence_level,
  r.applicable_population AS applicable_population,
  r.exclusion_criteria AS exclusion_criteria,
  r.evidence_text AS evidence_text,
  r.source_name AS source_name,
  r.source_page AS source_page;
```

### 11.2 查询具体药物和操作

疾病可能直接连药物/操作：

```cypher
MATCH (d:KGNode {code:$disease_code})-[r:treated_by_medication|treated_by_procedure]->(x:KGNode)
RETURN
  type(r) AS relation_type,
  x.entityType AS target_type,
  x.name AS target_name,
  r.recommendation_class AS recommendation_class,
  r.evidence_level AS evidence_level,
  r.applicable_population AS applicable_population,
  r.exclusion_criteria AS exclusion_criteria,
  r.evidence_text AS evidence_text,
  r.source_name AS source_name,
  r.source_page AS source_page;
```

治疗方案也可能下接具体药物/操作：

```cypher
MATCH (d:KGNode {code:$disease_code})-[:has_treatment_plan]->(plan:KGNode)
OPTIONAL MATCH (plan)-[r:includes_medication|includes_procedure|has_clinical_pathway]->(x:KGNode)
RETURN
  plan.name AS plan_name,
  type(r) AS relation_type,
  x.entityType AS target_type,
  x.name AS target_name,
  r.evidence_text AS evidence_text,
  r.source_name AS source_name,
  r.source_page AS source_page;
```

### 11.3 Oracle 类 SQL：查询候选治疗

```sql
SELECT
    d.name AS disease_name,
    r.relation_type,
    x.entity_type AS target_type,
    x.name AS target_name,
    r.recommendation_class,
    r.evidence_level,
    r.applicable_population,
    r.exclusion_criteria,
    r.evidence_text,
    r.source_name,
    r.source_page
FROM KG_NODE d
JOIN KG_RELATION r
  ON r.source_code = d.code
JOIN KG_NODE x
  ON x.code = r.target_code
WHERE d.code = :candidate_disease_code
  AND r.relation_type IN (
      'has_treatment_plan',
      'treated_by_medication',
      'treated_by_procedure',
      'has_follow_up'
  )
ORDER BY
    CASE r.recommendation_class
      WHEN 'Ⅰ' THEN 1
      WHEN 'I' THEN 1
      WHEN 'Ⅱa' THEN 2
      WHEN 'IIa' THEN 2
      WHEN 'Ⅱb' THEN 3
      WHEN 'IIb' THEN 3
      ELSE 9
    END,
    r.evidence_level;
```

---

## 12. Step 6：结合患者禁忌证过滤推荐

图谱关系里有两个关键属性：

| 字段 | 含义 |
|---|---|
| `applicable_population` | 适用人群 |
| `exclusion_criteria` | 排除条件/禁忌证 |

Oracle 侧要把患者事实和这些字段做匹配。初期可以规则化处理，后续可接 NLP。

### 12.1 示例：溶栓前禁忌证过滤

```sql
SELECT
    rec.*
FROM CDSS_CANDIDATE_RECOMMENDATION rec
WHERE rec.patient_id = :patient_id
  AND rec.visit_id = :visit_id
  AND rec.target_name LIKE '%溶栓%'
  AND NOT EXISTS (
      SELECT 1
      FROM EMR_CONTRAINDICATION_FACT c
      WHERE c.patient_id = rec.patient_id
        AND c.visit_id = rec.visit_id
        AND c.present_flag = 1
        AND c.fact_name IN (
            '活动性出血',
            '既往脑出血',
            '近期颅内手术',
            '严重未控制高血压'
        )
  );
```

### 12.2 推荐状态分级

建议 CDSS 不要只有“推荐/不推荐”，至少分四级：

| 状态 | 含义 |
|---|---|
| `recommend` | 条件满足，证据链完整，可提示 |
| `recommend_with_caution` | 条件基本满足，但有风险因素，需医生确认 |
| `not_recommend_due_to_contraindication` | 命中禁忌证，不推荐 |
| `insufficient_data` | 关键 EMR 数据缺失，先提示补检查/补资料 |

---

## 13. Step 7：输出证据链

任何 CDSS 推荐都必须能回溯到：

- 关系 ID；
- 指南/教材名称；
- 页码或非分页定位；
- 原文证据；
- 推荐等级；
- 证据等级。

### 13.1 Cypher：查询推荐证据链

```cypher
MATCH (d:KGNode {code:$disease_code})-[r]->(x:KGNode)
WHERE type(r) IN ['has_treatment_plan','treated_by_medication','treated_by_procedure','has_follow_up']
RETURN
  d.name AS disease_name,
  type(r) AS relation_type,
  x.name AS recommendation_target,
  r.recommendation_class AS recommendation_class,
  r.evidence_level AS evidence_level,
  r.source_name AS source_name,
  r.source_page AS source_page,
  r.evidence_text AS evidence_text,
  r.guideline_id AS guideline_id,
  r.evidence_id AS evidence_id
ORDER BY recommendation_class, evidence_level;
```

### 13.2 Oracle 类 SQL

```sql
SELECT
    d.name AS disease_name,
    x.name AS recommendation_target,
    r.relation_type,
    r.recommendation_class,
    r.evidence_level,
    r.source_name,
    r.source_page,
    r.evidence_text,
    r.guideline_id,
    r.evidence_id
FROM KG_RELATION r
JOIN KG_NODE d ON d.code = r.source_code
JOIN KG_NODE x ON x.code = r.target_code
WHERE d.code = :candidate_disease_code
  AND r.relation_type IN (
      'has_treatment_plan',
      'treated_by_medication',
      'treated_by_procedure',
      'has_follow_up'
  );
```

---

## 14. Step 8：AMI CDSS 输出 JSON 建议

CDSS 最终不要只返回“一个药名”或“一条结论”。建议返回结构化 JSON：

```json
{
  "patient_id": "P001",
  "visit_id": "V001",
  "candidate_disease": {
    "code": "DIS-CARD-CAD-STEMI",
    "name": "ST段抬高型心肌梗死",
    "confidence": 0.86,
    "matched_facts": [
      "胸痛",
      "ST段抬高",
      "肌钙蛋白升高"
    ]
  },
  "missing_data_prompts": [
    "请确认发病时间",
    "请确认是否存在溶栓禁忌证",
    "请确认是否已完成冠脉造影/PCI评估"
  ],
  "recommendations": [
    {
      "recommendation_type": "Procedure",
      "target_name": "经皮冠状动脉介入治疗",
      "status": "recommend",
      "reason": "患者疑似STEMI，需评估再灌注治疗策略",
      "recommendation_class": "Ⅰ",
      "evidence_level": "A",
      "source_name": "STEMI CN 2019.pdf",
      "source_page": "1",
      "evidence_text": "原文证据片段..."
    },
    {
      "recommendation_type": "Medication",
      "target_name": "抗血小板药物",
      "status": "recommend_with_caution",
      "reason": "需先排除活动性出血、近期脑出血等禁忌证",
      "recommendation_class": "Ⅰ",
      "evidence_level": "A",
      "source_name": "ACS ESC 2023.pdf",
      "source_page": "N/A"
    }
  ]
}
```

---

## 15. Oracle/EMR 与图谱实体的匹配表

| EMR 数据 | 匹配图谱实体 | entityType | 图谱关系 |
|---|---|---|---|
| 主诉/现病史症状 | 胸痛、胸闷、呼吸困难、大汗 | Symptom | `Disease -> has_symptom -> Symptom` |
| 查体/生命体征 | 低血压、休克、心衰体征 | Sign | `Disease -> has_sign -> Sign` |
| 心电图报告 | 心电图 | Exam | `Disease -> requires_exam -> Exam` |
| 心电图结构化指标 | ST段抬高、ST段压低、Q波 | ExamIndicator / DiagnosisCriteria | `Exam -> exam_has_indicator -> ExamIndicator` 或 `Disease -> has_diagnostic_criteria` |
| 检验报告 | 肌钙蛋白、CK-MB | LabTest / ExamIndicator | `Disease -> requires_lab_test -> LabTest` |
| 入院诊断 | 急性心肌梗死、STEMI、NSTEMI | Disease | `Disease.code` |
| 医嘱药品 | 阿司匹林、P2Y12抑制剂、他汀、抗凝药 | Medication | `Disease -> treated_by_medication -> Medication` |
| 手术/操作 | PCI、CABG、溶栓、冠脉造影 | Procedure | `Disease -> treated_by_procedure -> Procedure` |
| 禁忌证/既往史 | 活动性出血、脑出血、药物过敏 | Contraindication / PatientState | 过滤 `exclusion_criteria` |
| 出院计划 | 复查、随访、二级预防 | FollowUp | `Disease -> has_follow_up -> FollowUp` |

---

## 16. 类 SQL 的完整 AMI 推理样例

下面是一个“先候选诊断，再查推荐”的 SQL 伪流程。

### 16.1 生成候选疾病

```sql
WITH symptom_match AS (
    SELECT
        d.code AS disease_code,
        d.name AS disease_name,
        COUNT(DISTINCT x.code) AS symptom_score
    FROM KG_NODE d
    JOIN KG_RELATION r ON r.source_code = d.code
    JOIN KG_NODE x ON x.code = r.target_code
    JOIN EMR_SYMPTOM_FACT sf
      ON sf.symptom_name = x.name
     AND sf.patient_id = :patient_id
     AND sf.visit_id = :visit_id
     AND sf.negated_flag = 0
    WHERE d.code IN ('DIS-CARD-CAD-AMI','DIS-CARD-CAD-STEMI','DIS-CARD-CAD-NSTEMI')
      AND r.relation_type IN ('has_symptom','has_sign')
    GROUP BY d.code, d.name
),
objective_evidence AS (
    SELECT
        CASE WHEN EXISTS (
            SELECT 1 FROM EMR_EXAM_RESULT
            WHERE patient_id = :patient_id
              AND visit_id = :visit_id
              AND exam_name = '心电图'
              AND JSON_VALUE(structured_finding_json, '$.ST_ELEVATION') = 'true'
        ) THEN 2 ELSE 0 END AS ecg_score,
        CASE WHEN EXISTS (
            SELECT 1 FROM EMR_LAB_RESULT
            WHERE patient_id = :patient_id
              AND visit_id = :visit_id
              AND item_name IN ('肌钙蛋白I','肌钙蛋白T','心肌肌钙蛋白')
              AND abnormal_flag = 'H'
        ) THEN 2 ELSE 0 END AS lab_score
    FROM dual
)
SELECT
    sm.disease_code,
    sm.disease_name,
    sm.symptom_score + oe.ecg_score + oe.lab_score AS total_score
FROM symptom_match sm
CROSS JOIN objective_evidence oe
ORDER BY total_score DESC;
```

### 16.2 根据候选疾病查推荐

```sql
SELECT
    r.rel_id,
    r.relation_type,
    x.entity_type,
    x.name AS recommendation_target,
    r.recommendation_class,
    r.evidence_level,
    r.applicable_population,
    r.exclusion_criteria,
    r.source_name,
    r.source_page,
    r.evidence_text
FROM KG_RELATION r
JOIN KG_NODE x ON x.code = r.target_code
WHERE r.source_code = :candidate_disease_code
  AND r.relation_type IN (
      'has_treatment_plan',
      'treated_by_medication',
      'treated_by_procedure',
      'has_follow_up'
  )
ORDER BY
    CASE r.recommendation_class
      WHEN 'Ⅰ' THEN 1
      WHEN 'I' THEN 1
      WHEN 'Ⅱa' THEN 2
      WHEN 'IIa' THEN 2
      WHEN 'Ⅱb' THEN 3
      WHEN 'IIb' THEN 3
      ELSE 9
    END;
```

### 16.3 根据禁忌证过滤

```sql
SELECT rec.*
FROM CDSS_RECOMMENDATION_CANDIDATE rec
WHERE NOT EXISTS (
    SELECT 1
    FROM EMR_CONTRAINDICATION_FACT c
    WHERE c.patient_id = rec.patient_id
      AND c.visit_id = rec.visit_id
      AND c.present_flag = 1
      AND (
          rec.exclusion_criteria LIKE '%' || c.fact_name || '%'
          OR rec.recommendation_target LIKE '%溶栓%' AND c.fact_name IN ('活动性出血','既往脑出血')
          OR rec.recommendation_target LIKE '%抗凝%' AND c.fact_name IN ('活动性出血','严重血小板减少')
      )
);
```

---

## 17. Neo4j 查询和 Oracle 查询的对应关系

| 图查询概念 | Cypher | Oracle/SQL |
|---|---|---|
| 找疾病节点 | `MATCH (d:KGNode {entityType:'Disease'})` | `FROM KG_NODE d WHERE d.entity_type='Disease'` |
| 找疾病症状 | `(d)-[:has_symptom]->(s)` | `KG_RELATION.source_code=d.code AND relation_type='has_symptom'` |
| 找治疗方案 | `(d)-[:has_treatment_plan]->(p)` | `relation_type='has_treatment_plan'` |
| 找药物治疗 | `(d)-[:treated_by_medication]->(m)` | `relation_type='treated_by_medication'` |
| 找操作治疗 | `(d)-[:treated_by_procedure]->(p)` | `relation_type='treated_by_procedure'` |
| 找证据链 | 关系属性或 `supported_by_evidence` | `KG_RELATION.evidence_text/source_name/source_page` |
| 根据别名匹配 | `n.aliases CONTAINS '心梗'` | `JSON_EXISTS(ALIASES_JSON, '$?(@ == \"心梗\")')` |

---

## 18. 前端/Trae 应该怎么展示 AMI 推理链

建议做一个“临床推理过程卡片”，不是只展示网络图。

### 18.1 页面结构

```text
患者事实
  - 症状：胸痛、大汗
  - 检查：心电图 ST段抬高
  - 检验：肌钙蛋白升高

候选疾病
  - STEMI：匹配分 0.86
  - AMI：匹配分 0.78
  - NSTEMI：匹配分 0.42

推荐路径
  - 再灌注治疗
  - PCI
  - 抗血小板治疗
  - 抗凝治疗
  - 高强度他汀

风险/禁忌检查
  - 溶栓禁忌证：待确认
  - 出血风险：待确认
  - 肾功能：待确认

证据链
  - 指南名称
  - 页码
  - 原文
  - 推荐等级
  - 证据等级
```

### 18.2 前端接口返回建议

```json
{
  "reasoning_trace": [
    {
      "step": "症状匹配",
      "matched_entities": ["胸痛", "大汗"],
      "matched_relation_types": ["has_symptom"]
    },
    {
      "step": "客观证据匹配",
      "matched_entities": ["心电图", "肌钙蛋白"],
      "matched_relation_types": ["requires_exam", "requires_lab_test"]
    },
    {
      "step": "候选疾病",
      "disease": "ST段抬高型心肌梗死",
      "disease_code": "DIS-CARD-CAD-STEMI"
    },
    {
      "step": "治疗推荐",
      "recommendations": ["PCI", "抗血小板治疗", "抗凝治疗", "他汀类药物"]
    }
  ]
}
```

---

## 19. 开发落地顺序

建议按以下顺序开发，不要一开始就做复杂 AI 推理：

### 阶段 1：只做图谱查询

1. 输入疾病 code：`DIS-CARD-CAD-AMI`
2. 返回症状、检查、检验、诊断标准、治疗方案、药物、操作、随访。
3. 每条返回都带证据链。

### 阶段 2：接 EMR 结构化事实

1. 输入患者 visit_id。
2. 从 EMR 抽取症状、检查、检验、禁忌证。
3. 和图谱实体做 name/alias 匹配。
4. 返回候选疾病。

### 阶段 3：做规则评分

1. 症状命中加分。
2. 心电图命中加分。
3. 肌钙蛋白命中加分。
4. 禁忌证命中扣分或阻断。

### 阶段 4：做 CDSS 推荐

1. 根据候选疾病查治疗路径。
2. 根据患者禁忌证过滤。
3. 输出推荐、风险提示、证据链。

### 阶段 5：专家/医生使用效果反馈

1. 医生点击“接受/忽略/不适用”。
2. 记录推荐命中情况。
3. 反向优化权重和规则。

---

## 20. 最重要的开发约定

1. `code` 是图谱主键，不要用 `name` 当主键。
2. `name` 用于展示，`aliases` 用于匹配。
3. Evidence 节点不要混入临床实体统计。
4. CDSS 推荐必须返回证据链。
5. 没有患者禁忌证数据时，不得输出“强推荐”，只能输出“建议评估”。
6. 图谱关系不是单纯展示边，而是推理路径。
7. Oracle 侧至少要有 `KG_NODE` 和 `KG_RELATION` 两张图谱镜像表，才能用 SQL 写类似图查询。
8. 前端展示时必须能从推荐点击到：
   - 疾病；
   - 推荐项；
   - 推荐关系；
   - 指南来源；
   - 原文证据。

---

## 21. 给开发同事的一句话总结

不要把图谱理解成“很多节点的可视化页面”。  
在 CDSS 里，图谱的真正用法是：

```text
用 EMR 事实匹配图谱实体，
用图谱关系找到诊断/检查/治疗/随访候选，
用患者禁忌证和上下文过滤，
最后输出带证据链的推荐。
```

