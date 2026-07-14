# SKILL V2.1 精确校验报告（2026-07-12）

校验时间：2026-07-12 14:20:00
校验对象：`AI自动化工具-文献指南解析.md` V2.1 收尾版、`技能文档_skill_docs/` 附录、月度计划、批次台账、治理脚本。
本次动作：只校验和修正文档/治理规则；未连接 Neo4j，未写数据库，未生成图谱 delta。

## 1. 放行结论

SKILL V2.1 可以作为下一阶段心血管内科批次执行标准使用。

放行范围：

1. 新批次启动规则：可用。
2. 教材骨架与指南血肉边界：可用。
3. 旧候选池禁用规则：可用。
4. G0/G1/G2/G3/G4 闭环：可用。
5. Neo4j 受控写库边界：可用。
6. 本月心血管内科建设顺序：可用。

仍需执行层继续完成的内容：

1. 冠心病 V2.1 回归验证与差量补齐。
2. 心肌病 V2.1 回归验证与差量补齐。
3. 后续按月度计划推进急性心肌梗死、心力衰竭、高血压、心律失常、起搏治疗相关疾病、瓣膜病、肺动脉高压。

## 2. 本次发现并修复的问题

| 问题 | 影响 | 修复结果 |
|---|---|---|
| 月度计划顶部目标列表曾为“心肌病、冠心病……” | 与批次台账和用户确认顺序不一致，容易导致下一阶段从心肌病而不是冠心病开始 | 已修正为“冠心病、心肌病、急性心肌梗死……” |
| 治理脚本只检查“目标是否存在”，未检查“目标顺序是否一致” | 以后可能再次出现计划表、台账、SKILL 顺序不一致 | 已在 `校验SKILL治理_validate_skill_governance.py` 增加顺序校验 |
| 主 SKILL 已表达“不进入 Neo4j”，但缺少明确硬句“未通过 G2 不写 Neo4j” | 换账号或交接时可能理解不够直接 | 已补充硬句：`未通过 G2 不写 Neo4j` |

## 3. 自动化校验结果

### 3.1 SKILL 治理校验

```text
VALIDATION_OK
main_skill_bytes= 8113
appendix_count= 7
monthly_plan=present
batch_plan_rows>=9
monthly_order=ok
```

### 3.2 骨架质量闭环校验

```text
VALIDATION_OK
audited_subject_count= 55
quality_issue_rows= 15
reconcile_priority_rows= 416
name_alignment_rows= 68
names_not_in_d6= 34
neo4j_written=false
```

### 3.3 疾病名称与章节坐标对齐校验

```text
VALIDATION_OK
name_mapping_rows= 68
evidence_audit_rows= 13066
mergeable_summary_rows= 336
neo4j_written=false
```

### 3.4 历史候选池复用抽样校验

```text
VALIDATION_OK
precheck_rows= 6138
sample_rows= 180
direct_batch_reuse_allowed=false
neo4j_written=false
delta_generated=false
```

## 4. 精确校验项

| 校验项 | 结果 | 说明 |
|---|---:|---|
| 主 SKILL 疾病顺序 | OK | 冠心病 > 心肌病 > 急性心肌梗死 > 心力衰竭 > 高血压 > 心律失常 > 起搏治疗相关疾病 > 瓣膜病 > 肺动脉高压 |
| 月度计划疾病顺序 | OK | 与主 SKILL、批次台账一致 |
| 主 SKILL 关键规则覆盖 | OK | 教材搭骨架、指南填血肉、旧候选池只作线索、G0-G4、未通过 G2 不写 Neo4j 均已覆盖 |
| 附录数量 | OK | 7 个附录完整 |
| 规则迁移覆盖矩阵 | OK | 40 条规则，P0/P1 无空位置 |
| 批次台账顺序 | OK | 9 个本月目标齐全且顺序一致 |
| manifest 版本 | OK | `current_skill_version=V2.1 收尾版` |
| 跨电脑最小复制目录 | OK | 项目管理中心、技能文档、日志归档、治理脚本、术语字典均存在 |

## 5. 下一阶段唯一建议动作

启动“冠心病 V2.1 回归验证与差量补齐”。

执行边界：

1. 不从 0 重建冠心病骨架。
2. 不复用 2026-06-25 历史候选池直接补图谱。
3. 按当前 D6 骨架基线回到教材/指南原文重抽取。
4. 重点验证诊断、鉴别诊断、再灌注、抗栓、调脂、随访、禁忌、推荐等级和证据链。
5. 通过 G1/G2 后再进入受控 G3 入库；未通过 G2 不写 Neo4j。
