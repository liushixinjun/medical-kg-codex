# -*- coding: utf-8 -*-
"""SKILL治理校验脚本。

只读校验，不连接Neo4j，不修改业务数据。
"""
from pathlib import Path
import csv
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8-sig')

def fail(msg: str, failures: list[str]):
    failures.append(msg)

def main() -> int:
    failures: list[str] = []
    skill = ROOT / 'AI自动化工具-文献指南解析.md'
    if not skill.exists():
        fail('主SKILL不存在', failures)
    else:
        text = read_text(skill)
        if '版本：V2.0' not in text:
            fail('主SKILL未升级到V2.0', failures)
        if len(text.encode('utf-8')) > 40000:
            fail('主SKILL仍超过40KB，未完成瘦身', failures)
        for required in ['核心原则', '标准执行流', '质量硬闸门', '附录索引', '禁止事项']:
            if required not in text:
                fail(f'主SKILL缺少章节：{required}', failures)

    appendix_dir = ROOT / '技能文档_skill_docs'
    appendix_files = list(appendix_dir.glob('附录*_*.md'))
    if len(appendix_files) < 7:
        fail(f'附录数量不足：{len(appendix_files)}', failures)

    matrix = appendix_dir / 'SKILL规则迁移覆盖矩阵_rule_mapping_20260711.csv'
    if not matrix.exists():
        fail('SKILL规则迁移覆盖矩阵不存在', failures)
    else:
        rows = list(csv.DictReader(matrix.open(encoding='utf-8-sig')))
        if len(rows) < 40:
            fail(f'规则覆盖矩阵少于40条：{len(rows)}', failures)
        empty = [r for r in rows if r.get('规则等级') in ('P0', 'P1') and not r.get('新位置')]
        if empty:
            fail(f'P0/P1规则存在未指定新位置：{len(empty)}', failures)

    fp = ROOT / '项目管理中心_project_management/05_全局错误指纹索引_error_fingerprint.csv'
    if not fp.exists():
        fail('错误指纹索引不存在', failures)
    else:
        rows = list(csv.DictReader(fp.open(encoding='utf-8-sig')))
        if len(rows) < 10:
            fail(f'错误指纹少于10条：{len(rows)}', failures)

    log_index = ROOT / '日志归档_log_archive/00_日志归档索引_log_archive_index.md'
    if not log_index.exists():
        fail('日志归档索引不存在', failures)

    manifest = ROOT / '项目管理中心_project_management/01_项目运行清单_manifest.json'
    if not manifest.exists():
        fail('项目运行清单不存在', failures)
    else:
        data = json.loads(read_text(manifest))
        if data.get('current_skill_version') != 'V2.0 精简总纲':
            fail('manifest未记录当前SKILL版本V2.0', failures)

    try:
        staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT, text=True, encoding='utf-8', errors='replace').splitlines()
        protected = [p for p in staged if p.startswith('心血管内科文献集合/')]
        if protected:
            fail('Git缓存区包含心血管内科文献集合文件：' + ';'.join(protected[:5]), failures)
    except Exception:
        pass

    if failures:
        print('VALIDATION_FAILED')
        for item in failures:
            print('-', item)
        return 1

    print('VALIDATION_OK')
    print('main_skill_bytes=', skill.stat().st_size)
    print('appendix_count=', len(appendix_files))
    print('error_fingerprint_rows>=10')
    return 0

if __name__ == '__main__':
    sys.exit(main())
