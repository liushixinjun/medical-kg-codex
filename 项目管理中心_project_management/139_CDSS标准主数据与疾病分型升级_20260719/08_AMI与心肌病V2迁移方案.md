# AMI 与心肌病 V2.0 迁移方案

## 1. 本轮结论

AMI 和心肌病样板已按 Oracle `K_ICD10_DICT` 中 `VALID_FLAG=1` 的真实记录建立，不使用截图猜测编码。

- 急性心肌梗死：`I21.900`。
- ST 段抬高型心肌梗死：`I21.300x004`。
- 非 ST 段抬高型心肌梗死：`I21.401`。
- 心肌病：`I42.900`。
- 扩张型心肌病：`I42.000`。
- 肥厚型心肌病当前可关联 6 条有效标准诊断记录，保留标准字典原名称，不把多个编码强行合成一条。

## 2. 目标层级

```text
心血管内科
  -> 冠心病
    -> 急性心肌梗死（待分型/初步诊断）
      -> ST段抬高型心肌梗死
      -> 非ST段抬高型心肌梗死

心血管内科
  -> 心肌病（疾病大类）
    -> 心肌病（待分型/初步诊断）
      -> 肥厚型心肌病
      -> 扩张型心肌病
```

疾病大类和同名待分型疾病在数据库中分开；前端可以折叠显示，但不能删除任一层。

## 3. 当前服务器真实差异

1. 同时存在 `SPEC-CARD` 和 `CARD` 两个心血管内科根节点，应以关系更完整、编码更明确的 `SPEC-CARD` 为主节点。
2. 当前使用 `has_category` 和 `belongs_to_category`，V2.0 改为单向 `has_disease_category`、`has_disease`、`has_clinical_subtype`。
3. AMI 同时存在 `Disease` 分型和重复 `DiseaseClassification` 分型，需迁移关系后清理两个重复分类节点。
4. STEMI、NSTEMI、HCM、DCM 当前直接挂疾病大类，V2.0 应挂到各自宽口径父疾病。
5. 当前疾病节点没有 CDSS 标准诊断 UUID 和标准编码关系；样板已补 `StandardDiagnosis` 和 `has_standard_diagnosis`。

## 4. 写库顺序

1. 导入 `StandardDiagnosis` 节点，按 `(entityType, cdss_dict_id)` 防重复。
2. 更新现有疾病节点的 V2.0 诊断角色，不复制疾病知识关系。
3. 新建 `has_disease_category`、`has_disease`、`has_clinical_subtype` 和 `has_standard_diagnosis`。
4. 核对新层级、标准诊断 UUID、编码和名称。
5. 迁移 `CARD`、`DiseaseClassification` 旧节点的有效关系。
6. 删除已替代旧关系；旧节点无引用后进入物理删除候选。
7. 运行本地审计和服务器入库后复核，阻断项为 0 才结束。

## 5. 本轮暂不写库的原因

当前文件是迁移样板和审计输入，还需先通过 V2.0 自动校验，并生成可回滚的正式增量脚本。通过后可在同一批次直接写入 Neo4j，不需要临床专家逐条确认标准字典的精确匹配结果。
