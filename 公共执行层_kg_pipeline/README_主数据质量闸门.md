# 主数据质量闸门说明

用途：把已经反复出现的三类问题固化成可重复执行的只读检查，避免新病种再次产生同名重复节点、孤儿诊断标准、空壳治疗方案。

## 固化的硬闸门

| 中文检查项 | 判断标准 | 阻断原因 |
|---|---|---|
| 同病种同类型同名重复直连 | 同一个疾病下，同一实体类型、同一名称出现多个节点 | 前端会重复展示，CDSS 推理入口不稳定 |
| 诊断标准无明细 | `DiagnosisCriteria` 没有 `has_diagnostic_component` | 医生只能看到标题，看不到诊断条件 |
| 孤儿诊断标准 | `DiagnosisCriteria` 没有任何关系 | 历史残留空节点，不应进入正式图谱 |
| 治疗方案无下游 | `TreatmentPlan` 没有药物、操作、子方案、证据或路径动作 | 医生看不到具体怎么治疗 |
| 标准主节点替换后仍被引用 | 已被归并替换的重复节点仍被路径/规则/疾病引用 | 说明归并不彻底，可能继续重复展示 |

## 执行命令

```powershell
$py = "D:\Program Files Ai\python-venvs\medical-kg\Scripts\python.exe"
& $py "公共执行层_kg_pipeline\主数据质量闸门_master_data_gate.py" `
  --connection-file "图谱数据库链接.txt" `
  --output-dir "心血管内科文献集合\00_全局质量体检_global_quality_audit\20260714_主数据质量闸门"
```

## 输出文件

| 文件 | 用途 |
|---|---|
| `主数据质量闸门_summary.json` | 给脚本和自动化读取的汇总结果 |
| `主数据质量闸门报告.md` | 给人看的中文报告 |
| `details/*.csv` | 每个阻断项的明细 |

## 后续接入位置

- G1：本地 JSONL 生成后，先查本地是否准备生成重复主节点。
- G2：导入前只读连接 Neo4j，确认服务器已有标准主节点，避免重复创建。
- G3/postcheck：入库后再次查服务器，必须全部为 0 才能继续新病种。

## 批次入库后统一复测入口

以后新病种或精修批次写入 Neo4j 后，不再单独记忆多个旧脚本，统一执行：

```powershell
$py = "D:\Program Files Ai\python-venvs\medical-kg\Scripts\python.exe"
& $py "公共执行层_kg_pipeline\批次入库后复测_postcheck.py" `
  --batch-id "BATCH-示例" `
  --batch-output-dir "心血管内科文献集合\示例批次目录" `
  --connection-file "图谱数据库链接.txt"
```

统一入口会在批次目录下生成：

| 输出 | 用途 |
|---|---|
| `99_入库后复测/00_入库后复测总览.json` | 给脚本读取的总结果 |
| `99_入库后复测/00_入库后复测报告.md` | 给人看的中文复测报告 |
| `99_入库后复测/01_主数据质量闸门/` | 主数据质量闸门明细 |
