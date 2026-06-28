# Skill 与 Schema V1.0 重写实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零重写 PDF 文献指南解析 Skill，并生成统一的专科知识图谱 Schema 标准 V1.0。

**Architecture:** 两个根目录正式文件职责分离：Skill 规定启动确认、来源解析、抽取、审计、批次交付和合并流程；Schema 规定实体、关系、字段、编码、证据、配置层和合并契约。静态验证脚本检查文件名、版本、必需章节、历史版本残留和 UTF-8 BOM。

**Tech Stack:** Markdown、PowerShell 5.1、UTF-8 BOM、正则静态验证。

---

### Task 1: 建立失败基线

**Files:**
- Inspect: `AI自动化工具-文献指南解析.md`
- Inspect: `专科知识图谱Schema标准.md`

- [ ] **Step 1: 运行失败基线检查**

```powershell
$skill = '.\AI自动化工具-文献指南解析.md'
$schema = '.\专科知识图谱Schema标准.md'
$skillText = [IO.File]::ReadAllText((Resolve-Path $skill), [Text.UTF8Encoding]::new($true))
$valid = $skillText.Contains('版本：V1.0') -and (Test-Path -LiteralPath $schema)
if ($valid) { exit 0 } else { Write-Error 'V1.0 formal files do not exist yet'; exit 1 }
```

Expected: FAIL，因为旧 Skill 不是 V1.0，且新 Schema 文件尚不存在。

### Task 2: 重写正式 Skill

**Files:**
- Modify: `AI自动化工具-文献指南解析.md`

- [ ] **Step 1: 将文件重写为 V1.0 正式执行规范**

文件必须只包含以下可重复执行模块：

1. 适用范围和启动确认闸门
2. `specialty/category/disease` 范围契约
3. 原始 PDF/指南路径确认
4. 来源优先级和《内科学》基础证据库
5. 文献清单、去重、逐页解析、OCR 和质量阻断
6. Schema V1.0 映射
7. 疾病锚点、证据绑定和跨疾病污染防护
8. 数据实例和诊疗闭环审计
9. 独立批次交付和受控合并
10. 用户确认后的可选 Neo4j 导入

禁止出现旧版本号、迁移记录、历史批次数字、旧错误案例、旧目录状态和数据库现状。

- [ ] **Step 2: 使用 UTF-8 BOM 保存**

```powershell
$p = (Resolve-Path '.\AI自动化工具-文献指南解析.md').Path
$s = [IO.File]::ReadAllText($p, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText($p, $s, [Text.UTF8Encoding]::new($true))
```

### Task 3: 创建正式 Schema 标准

**Files:**
- Create: `专科知识图谱Schema标准.md`

- [ ] **Step 1: 写入 Schema V1.0**

文件必须定义：

- 统一核心层、专科/疾病大类配置层、单病种规则层
- 标准实体、关系方向、关系类别和禁止关系
- 节点与关系必填字段
- `Exam/LabTest/ExamIndicator/ThresholdRule` 边界
- `id/code/standard_code` 编码规则
- Guideline、Evidence 和 provenance 证据链
- `batch_id/scope_type/scope_target/source_type/document_id/segment_id`
- 诊疗路径闭环和适用性配置
- 批次去重、冲突、快照、回滚和合并规则
- 数据实例与 Neo4j 导入硬闸门

禁止出现任何旧 Schema 版本、迁移映射或历史实现基线。

- [ ] **Step 2: 使用 UTF-8 BOM 保存**

```powershell
$p = (Resolve-Path '.\专科知识图谱Schema标准.md').Path
$s = [IO.File]::ReadAllText($p, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText($p, $s, [Text.UTF8Encoding]::new($true))
```

### Task 4: 静态验收

**Files:**
- Verify: `AI自动化工具-文献指南解析.md`
- Verify: `专科知识图谱Schema标准.md`

- [ ] **Step 1: 检查版本、章节、编码和历史残留**

```powershell
$files = @('.\AI自动化工具-文献指南解析.md', '.\专科知识图谱Schema标准.md')
foreach ($file in $files) {
  $bytes = [IO.File]::ReadAllBytes((Resolve-Path $file))
  $text = [IO.File]::ReadAllText((Resolve-Path $file), [Text.UTF8Encoding]::new($true))
  if (($bytes[0..2] -join ',') -ne '239,187,191') { throw "$file missing UTF-8 BOM" }
  if (-not $text.Contains('版本：V1.0')) { throw "$file missing V1.0" }
  if ($text -match 'V1\.1|V1\.2|V2\.|迁移映射|历史批次|当前数据库') { throw "$file contains historical content" }
  if ($text.Contains([char]0xFFFD)) { throw "$file contains replacement characters" }
}
```

- [ ] **Step 2: 检查关键要求覆盖**

```powershell
$skill = [IO.File]::ReadAllText((Resolve-Path '.\AI自动化工具-文献指南解析.md'), [Text.UTF8Encoding]::new($true))
$schema = [IO.File]::ReadAllText((Resolve-Path '.\专科知识图谱Schema标准.md'), [Text.UTF8Encoding]::new($true))
$skillRequired = @('scope_type', 'PDF/指南根目录', '《内科学》基础证据库', '逐页', '独立批次', 'Neo4j')
$schemaRequired = @('统一核心层', '专科/疾病大类配置层', '单病种规则层', 'segment_id', 'provenance', 'ThresholdRule', '关系语义键')
if (@($skillRequired | Where-Object { -not $skill.Contains($_) }).Count) { throw 'Skill coverage failed' }
if (@($schemaRequired | Where-Object { -not $schema.Contains($_) }).Count) { throw 'Schema coverage failed' }
```

Expected: PASS，退出码 0。

### Task 5: 交付

**Files:**
- Deliver: `AI自动化工具-文献指南解析.md`
- Deliver: `专科知识图谱Schema标准.md`

- [ ] **Step 1: 报告两个文件的绝对路径、版本、行数和 SHA-256**

```powershell
Get-Item '.\AI自动化工具-文献指南解析.md', '.\专科知识图谱Schema标准.md' |
  ForEach-Object {
    [pscustomobject]@{
      Path = $_.FullName
      Lines = ([IO.File]::ReadAllLines($_.FullName, [Text.UTF8Encoding]::new($true))).Count
      SHA256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
  }
```

本工作目录不是 Git 仓库，不执行 commit、push 或 PR。
