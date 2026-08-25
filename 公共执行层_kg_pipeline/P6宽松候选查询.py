#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P6 剩余缺口的 Oracle 宽松候选查询，只读，不写库。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Any

import oracledb


ROOT = Path(__file__).resolve().parents[1]
P6_DIR = ROOT / "项目管理中心_project_management" / "2026年8月P6已解析大类终验" / "05_标准字典收口后复核_20260803"

TABLE_BY_TYPE = {
    "Disease": ["K_ICD10_DICT"],
    "ExamItem": ["K_EXAM_ITEM_DICT"],
    "LabItem": ["K_LAB_ITEM_DICT", "K_LAB_SUBITEM_DICT"],
    "LabSubitem": ["K_LAB_SUBITEM_DICT", "K_LAB_ITEM_DICT"],
    "Medication": ["K_DRUG_DICT"],
    "Procedure": ["K_OPERATION_HANDLE_DICT"],
    "TreatmentItem": ["K_TREATMENT_DICT"],
}


def terms(name: str) -> list[str]:
    base = name.strip()
    result = [base]
    clean = re.sub(r"（.*?）|\\(.*?\\)", "", base).strip()
    if clean and clean not in result:
        result.append(clean)
    for token in re.split(r"[、/／及与和，, ]+", clean):
        token = token.strip()
        if len(token) >= 2 and token not in result:
            result.append(token)
    # 常见诊断/医嘱同义线索，只用于候选展示，不自动裁决。
    alias = {
        "外周动脉疾病": ["周围动脉疾病", "外周动脉病"],
        "静脉血栓症": ["静脉血栓形成", "静脉血栓栓塞"],
        "卵圆孔未闭": ["卵圆孔"],
        "心包积液及心脏压塞": ["心包积液", "心脏压塞"],
        "心室扑动与心室颤动": ["心室扑动", "心室颤动"],
        "缓慢性心律失常": ["心动过缓", "缓慢型心律失常"],
        "多瓣膜病": ["多瓣膜"],
        "动脉性肺动脉高压": ["肺动脉高压"],
        "12导联心电图": ["十二导联心电图", "常规心电图"],
        "心脏电生理检查": ["电生理检查", "心内电生理检查"],
        "事件记录仪": ["事件记录"],
        "食管心房调搏": ["食管心房调搏", "食道调搏"],
        "利钠肽": ["BNP", "NT-proBNP", "脑钠肽", "B型钠尿肽"],
        "肾功能与电解质": ["肾功能", "电解质"],
        "尿酸": ["尿酸"],
        "醛固酮/肾素比值": ["醛固酮", "肾素", "醛固酮肾素比"],
        "尿白蛋白/肌酐比值": ["尿白蛋白", "肌酐", "白蛋白肌酐比"],
    }
    for value in alias.get(base, []):
        if value not in result:
            result.append(value)
    return result


def oracle_rows(cursor: oracledb.Cursor, table: str, term: str) -> list[dict[str, Any]]:
    try:
        cursor.execute(
            f"""
            SELECT id, code, name, valid_flag
              FROM {table}
             WHERE valid_flag = 1
               AND name LIKE :kw
             ORDER BY name, code
             FETCH FIRST 20 ROWS ONLY
            """,
            kw=f"%{term}%",
        )
    except Exception as exc:
        return [{"error": str(exc).splitlines()[0]}]
    columns = [column[0].lower() for column in cursor.description]
    return [{column: str(value) if value is not None else "" for column, value in zip(columns, row)} for row in cursor.fetchall()]


def read_gaps(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gap-csv", type=Path, default=P6_DIR / "03_样板缺口清单.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "项目管理中心_project_management" / "2026年8月P6已解析大类终验" / "06_剩余缺口Oracle候选_20260803")
    parser.add_argument("--oracle-user", default="zycdss")
    parser.add_argument("--oracle-dsn", default="192.168.4.25:1521/ORCL")
    args = parser.parse_args()
    password = os.environ.get("ORACLE_PASSWORD")
    if not password:
        raise RuntimeError("缺少 ORACLE_PASSWORD 环境变量。")

    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"gap_count": 0, "candidate_count": 0}
    connection = oracledb.connect(user=args.oracle_user, password=password, dsn=args.oracle_dsn)
    try:
        cursor = connection.cursor()
        for gap in read_gaps(args.gap_csv):
            issue = gap.get("问题类别", "")
            if issue not in {"标准诊断阻断", "正式推荐动作标准字典未闭环", "检查检验路径结构错误"}:
                continue
            entity_type = gap.get("对象类型", "")
            name = gap.get("对象名称", "")
            summary["gap_count"] += 1
            seen = set()
            for table in TABLE_BY_TYPE.get(entity_type, []):
                for term in terms(name):
                    for candidate in oracle_rows(cursor, table, term):
                        key = (table, candidate.get("id", ""), candidate.get("code", ""), candidate.get("name", ""))
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append(
                            {
                                "问题类别": issue,
                                "对象类型": entity_type,
                                "对象名称": name,
                                "疾病编码": gap.get("疾病编码", ""),
                                "疾病名称": gap.get("疾病名称", ""),
                                "查询表": table,
                                "查询词": term,
                                "候选ID": candidate.get("id", ""),
                                "候选编码": candidate.get("code", ""),
                                "候选名称": candidate.get("name", ""),
                                "错误": candidate.get("error", ""),
                            }
                        )
    finally:
        connection.close()
    summary["candidate_count"] = len(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.output_dir / "01_剩余缺口Oracle宽松候选.csv",
        rows,
        ["问题类别", "对象类型", "对象名称", "疾病编码", "疾病名称", "查询表", "查询词", "候选ID", "候选编码", "候选名称", "错误"],
    )
    (args.output_dir / "00_候选查询摘要.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
