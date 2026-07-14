# -*- coding: utf-8 -*-
"""SKILL 治理校验脚本。

只读校验，不连接 Neo4j，不修改业务数据。
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_MONTHLY_ORDER = [
    "冠心病",
    "心肌病",
    "急性心肌梗死",
    "心力衰竭",
    "高血压",
    "心律失常",
    "起搏治疗相关疾病",
    "瓣膜病",
    "肺动脉高压",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def fail(msg: str, failures: list[str]) -> None:
    failures.append(msg)


def assert_text_order(name: str, text: str, expected: list[str], failures: list[str]) -> None:
    positions: list[tuple[str, int]] = []
    for item in expected:
        pos = text.find(item)
        if pos < 0:
            fail(f"{name} 缺少目标：{item}", failures)
        else:
            positions.append((item, pos))
    if len(positions) == len(expected):
        actual = [item for item, _ in sorted(positions, key=lambda x: x[1])]
        if actual != expected:
            fail(f"{name} 疾病顺序不一致：当前={actual}；应为={expected}", failures)


def main() -> int:
    failures: list[str] = []

    skill = ROOT / "AI自动化工具-文献指南解析.md"
    if not skill.exists():
        fail("主 SKILL 不存在", failures)
    else:
        text = read_text(skill)
        if "版本：V2.1" not in text:
            fail("主 SKILL 未升级到 V2.1", failures)
        if len(text.encode("utf-8")) > 40000:
            fail("主 SKILL 超过 40KB，未保持精简总纲", failures)
        for required in [
            "核心原则",
            "当前建设目标",
            "标准执行流",
            "质量硬闸门",
            "附录索引",
            "禁止事项",
            "旧候选池",
        ]:
            if required not in text:
                fail(f"主 SKILL 缺少关键内容：{required}", failures)
        assert_text_order("主 SKILL 当前建设目标", text, EXPECTED_MONTHLY_ORDER, failures)

    appendix_dir = ROOT / "技能文档_skill_docs"
    appendix_files = list(appendix_dir.glob("附录*_*.md"))
    if len(appendix_files) < 7:
        fail(f"附录数量不足：{len(appendix_files)}", failures)
    for appendix in appendix_files:
        text = read_text(appendix)
        if appendix.name in {
            "附录A_批次启动与范围确认_scope_batch.md",
            "附录B_来源体系与教材骨架_sources_skeleton.md",
            "附录F_质量闸门审计与Neo4j入库_quality_neo4j.md",
            "附录G_日志归档错误指纹与交接_handoff_logs.md",
        } and "2026-07-12" not in text:
            fail(f"关键附录未更新日期：{appendix.name}", failures)

    matrix = appendix_dir / "SKILL规则迁移覆盖矩阵_rule_mapping_20260711.csv"
    if not matrix.exists():
        fail("SKILL 规则迁移覆盖矩阵不存在", failures)
    else:
        rows = list(csv.DictReader(matrix.open(encoding="utf-8-sig")))
        if len(rows) < 40:
            fail(f"规则覆盖矩阵少于 40 条：{len(rows)}", failures)
        empty = [r for r in rows if r.get("规则等级") in ("P0", "P1") and not r.get("新位置")]
        if empty:
            fail(f"P0/P1 规则存在未指定新位置：{len(empty)}", failures)

    fp = ROOT / "项目管理中心_project_management/05_全局错误指纹索引_error_fingerprint.csv"
    if not fp.exists():
        fail("错误指纹索引不存在", failures)
    else:
        rows = list(csv.DictReader(fp.open(encoding="utf-8-sig")))
        if len(rows) < 13:
            fail(f"错误指纹少于 13 条：{len(rows)}", failures)
        if not any("历史候选池" in r.get("错误指纹关键词", "") for r in rows):
            fail("错误指纹未登记历史候选池防复发规则", failures)

    log_index = ROOT / "日志归档_log_archive/00_日志归档索引_log_archive_index.md"
    if not log_index.exists():
        fail("日志归档索引不存在", failures)

    monthly_plan = ROOT / "项目管理中心_project_management/14_心血管内科月度建设计划_202607.md"
    if not monthly_plan.exists():
        fail("心血管内科月度建设计划不存在", failures)
    else:
        plan_text = read_text(monthly_plan)
        assert_text_order("月度计划", plan_text, EXPECTED_MONTHLY_ORDER, failures)
        if "旧候选池不复用" not in plan_text:
            fail("月度计划未写明旧候选池不复用", failures)

    ledger = ROOT / "项目管理中心_project_management/04_批次登记台账_batch_ledger.csv"
    if not ledger.exists():
        fail("批次登记台账不存在", failures)
    else:
        rows = list(csv.DictReader(ledger.open(encoding="utf-8-sig")))
        if len(rows) < 9:
            fail(f"批次计划少于 9 条：{len(rows)}", failures)
        else:
            actual_order = [r.get("疾病大类", "") for r in rows[:9]]
            if actual_order != EXPECTED_MONTHLY_ORDER:
                fail(f"批次登记台账疾病顺序不一致：当前={actual_order}；应为={EXPECTED_MONTHLY_ORDER}", failures)

    manifest = ROOT / "项目管理中心_project_management/01_项目运行清单_manifest.json"
    if not manifest.exists():
        fail("项目运行清单不存在", failures)
    else:
        data = json.loads(read_text(manifest))
        if data.get("current_skill_version") != "V2.1 收尾版":
            fail("manifest 未记录当前 SKILL 版本 V2.1 收尾版", failures)
        if not data.get("current_monthly_plan"):
            fail("manifest 未记录当前月度计划", failures)

    try:
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).splitlines()
        protected = [p for p in staged if p.startswith("心血管内科文献集合/")]
        if protected:
            fail("Git 缓存区包含心血管内科文献集合文件：" + ";".join(protected[:5]), failures)
    except Exception:
        pass

    if failures:
        print("VALIDATION_FAILED")
        for item in failures:
            print("-", item)
        return 1

    print("VALIDATION_OK")
    print("main_skill_bytes=", skill.stat().st_size)
    print("appendix_count=", len(appendix_files))
    print("monthly_plan=present")
    print("batch_plan_rows>=9")
    print("monthly_order=ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
