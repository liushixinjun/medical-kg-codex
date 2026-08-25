# Trae 前端疾病目录与统计修复提示词

请基于服务器 Neo4j 当前正式数据修改 `E:\Trae CN\AI专科知识图谱生成TraeCN\kg-test-page`，不要增加旧目录兼容逻辑，也不要硬编码统计数字。

## 已确认的数据库基线

- 正式疾病大类：15 个。
- 疾病：132 个，全部可以从正式疾病大类访问。
- 非证据图谱节点：13,830 个。
- 关系：139,578 条。
- 非正式疾病大类编码：0。
- 无目录归属疾病：0。
- 多父级具体分型：0。

## 必须修改

1. `query_global_stats()` 的疾病大类数量必须只统计从 `Specialty` 通过 `has_disease_category` 连接、编码以 `CAT-` 开头且有效的正式大类，禁止直接统计全部 `DiseaseCategory`。
2. 疾病数量按正式目录可达口径统计：正式大类通过 `has_disease` 到待分型诊断/独立诊断，再通过 `has_clinical_subtype` 下钻具体分型，按疾病编码去重。
3. 首页“可视化实体”改名为“非证据图谱节点”，或至少增加说明：“不含 Evidence 证据节点，包含疾病、医学知识、临床规则、推荐陈述和来源裁决等图谱节点。”不要把它解释成纯临床实体数。
4. 左侧疾病树保持三层诊断结构：疾病大类 → 待分型诊断/独立诊断 → 具体分型。`DiseaseSubcategory` 只作可选展示分组，不插入诊断链。
5. 宽口径疾病点击后显示自身基础知识并展示具体分型入口；具体分型点击后显示分型知识。不得把待分型诊断和具体分型平铺成同级列表。
6. 清理 Redis 缓存键 `kg:disease_tree`、`kg:global_stats`、`kg:full_data`；若没有管理入口则重启后端服务。否则页面仍会显示迁移前的 20 个疾病大类和旧树。
7. 同步检查 `explore.html`、`disease.html`、网络探索、疾病审核、临床审核及所有复用疾病树/全局统计接口的页面，不能只改一个页面。
8. 更新项目说明中的旧统计数字，但运行页面始终以接口实时返回为准。

## 查询口径示例

正式疾病大类数量：

```cypher
MATCH (sp:Specialty)-[:has_disease_category]->(cat:DiseaseCategory)
WHERE cat.code STARTS WITH 'CAT-'
  AND coalesce(cat.status, 'active') <> 'deprecated'
RETURN count(DISTINCT cat) AS disease_category_count
```

正式目录可达疾病数量：

```cypher
MATCH (:Specialty)-[:has_disease_category]->(cat:DiseaseCategory)-[:has_disease]->(root:Disease)
WHERE cat.code STARTS WITH 'CAT-'
MATCH (root)-[:has_clinical_subtype*0..3]->(d:Disease)
WHERE coalesce(d.status, 'active') <> 'deprecated'
RETURN count(DISTINCT d) AS disease_count
```

## 页面验收案例

1. 心肌病显示为待分型诊断，展开后应有 11 个具体分型；不能只显示肥厚型、扩张型，也不能把这些具体分型平铺到疾病大类下。
2. 急性心肌梗死展开后显示 ST 段抬高型和非 ST 段抬高型两个具体分型。
3. 慢性冠脉综合征可以包含缺血性心肌病；急性冠脉综合征不得包含缺血性心肌病。
4. 首页显示 15 个疾病大类、132 个疾病、13,830 个非证据图谱节点、139,578 条关系。
5. 刷新页面和重启后端后数字保持一致；接口和页面不存在硬编码旧值。

完成后请输出：修改文件清单、接口返回样例、上述 5 项验收结果，以及是否已清理缓存。
