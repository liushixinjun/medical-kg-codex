#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
P6 标准字典闭环收口。

只做三类事情：
1. 从 P6 终验 raw.json 中读取标准诊断与正式推荐动作缺口。
2. 只读 Oracle CDSS 标准字典，做“有效记录唯一命中”判断。
3. 可选写入 Neo4j：只写唯一命中的标准映射；宽口径类别只标记为不可直接医嘱。

不写 Oracle，不伪造字典 ID，不对多候选/无候选做自动裁决。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import oracledb
from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
P6_DIR = ROOT / "项目管理中心_project_management" / "2026年8月P6已解析大类终验" / "03_确定性修复后复核_20260803"
RAW_JSON = P6_DIR / "00_P6已解析大类终验_raw.json"
GAP_CSV = P6_DIR / "03_样板缺口清单.csv"

ACTION_TABLE_BY_TYPE: dict[str, str] = {
    "ExamItem": "K_EXAM_ITEM_DICT",
    "LabItem": "K_LAB_ITEM_DICT",
    "LabSubitem": "K_LAB_SUBITEM_DICT",
    "Medication": "K_DRUG_DICT",
    "Procedure": "K_OPERATION_HANDLE_DICT",
    "TreatmentItem": "K_TREATMENT_DICT",
}

NON_ORDERABLE_MEDICATION_PATTERNS = [
    "类药物",
    "类制剂",
    "阻滞剂",
    "抑制剂",
    "拮抗剂",
    "利尿剂",
    "抗凝药物",
    "抗血小板药物",
    "低分子肝素",
    "硝酸酯",
]


def parse_neo4j_config(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;]+)", text)
    if not (uri and user and password):
        raise RuntimeError("无法解析图谱数据库连接文件。")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def oracle_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "read"):
        return value.read()
    return value


def load_inputs(raw_json: Path, gap_csv: Path) -> tuple[dict[str, Any], set[str]]:
    raw = json.loads(raw_json.read_text(encoding="utf-8"))
    standard_blocked: set[str] = set()
    with gap_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("问题类别") == "标准诊断阻断":
                standard_blocked.add(str(row.get("疾病编码") or "").strip())
    return raw, standard_blocked


def fetch_exact_rows(cursor: oracledb.Cursor, table: str, name: str) -> list[dict[str, Any]]:
    sql = f"""
        SELECT id, code, name, valid_flag
          FROM {table}
         WHERE valid_flag = 1
           AND trim(name) = :name
         ORDER BY code, id
    """
    try:
        cursor.execute(sql, name=name.strip())
    except Exception:
        return []
    columns = [column[0].lower() for column in cursor.description]
    return [
        {column: oracle_value(value) for column, value in zip(columns, record)}
        for record in cursor.fetchall()
    ]


def is_non_orderable_action(entity_type: str, name: str) -> bool:
    if entity_type != "Medication":
        return False
    return any(pattern in name for pattern in NON_ORDERABLE_MEDICATION_PATTERNS)


def build_diagnosis_matrix(raw: dict[str, Any], blocked_codes: set[str], cursor: oracledb.Cursor) -> list[dict[str, Any]]:
    diseases = [row for row in raw.get("diseases", []) if row.get("disease_code") in blocked_codes]
    rows: list[dict[str, Any]] = []
    for disease in sorted(diseases, key=lambda item: item.get("disease_code") or ""):
        name = str(disease.get("disease_name") or "").strip()
        candidates = fetch_exact_rows(cursor, "K_ICD10_DICT", name)
        status = "唯一命中" if len(candidates) == 1 else ("无命中" if not candidates else "多命中")
        chosen = candidates[0] if len(candidates) == 1 else {}
        rows.append(
            {
                "disease_code": disease.get("disease_code", ""),
                "disease_name": name,
                "diagnostic_role": disease.get("diagnostic_role", ""),
                "match_status": status,
                "candidate_count": len(candidates),
                "target_table": "K_ICD10_DICT",
                "target_id": chosen.get("id", ""),
                "target_code": chosen.get("code", ""),
                "target_name": chosen.get("name", ""),
                "write_allowed": "是" if len(candidates) == 1 else "否",
            }
        )
    return rows


def build_action_matrix(raw: dict[str, Any], cursor: oracledb.Cursor) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    ref_count: Counter[str] = Counter()
    for gap in raw.get("formal_action_standard_dictionary_gaps", []):
        code = str(gap.get("node_code") or "").strip()
        if not code:
            continue
        by_code[code] = gap
        ref_count[code] += 1

    rows: list[dict[str, Any]] = []
    for code, gap in sorted(by_code.items(), key=lambda item: (item[1].get("entity_type") or "", item[1].get("node_name") or "")):
        entity_type = str(gap.get("entity_type") or "").strip()
        name = str(gap.get("node_name") or "").strip()
        table = ACTION_TABLE_BY_TYPE.get(entity_type, "")
        candidates = fetch_exact_rows(cursor, table, name) if table else []

        if is_non_orderable_action(entity_type, name):
            status = "宽口径动作"
            write_allowed = "是"
            chosen: dict[str, Any] = {}
            note = "药物类别或宽口径药物名称，可展示但不可直接下医嘱。"
        elif len(candidates) == 1:
            status = "唯一命中"
            write_allowed = "是"
            chosen = candidates[0]
            note = "Oracle有效标准字典唯一命中。"
        elif not candidates:
            status = "无命中"
            write_allowed = "否"
            chosen = {}
            note = "未在对应CDSS有效字典中精确命中。"
        else:
            status = "多命中"
            write_allowed = "否"
            chosen = {}
            note = "对应CDSS有效字典存在多条同名记录，不能自动裁决。"

        rows.append(
            {
                "node_code": code,
                "node_name": name,
                "entity_type": entity_type,
                "ref_count": ref_count[code],
                "match_status": status,
                "target_table": table,
                "candidate_count": len(candidates),
                "target_id": chosen.get("id", ""),
                "target_code": chosen.get("code", ""),
                "target_name": chosen.get("name", ""),
                "write_allowed": write_allowed,
                "order_ready": "否" if status == "宽口径动作" else ("是" if status == "唯一命中" else "否"),
                "note": note,
            }
        )
    return rows


def backup_neo4j(driver, diagnosis_rows: list[dict[str, Any]], action_rows: list[dict[str, Any]]) -> dict[str, Any]:
    disease_codes = [row["disease_code"] for row in diagnosis_rows if row["write_allowed"] == "是"]
    action_codes = [row["node_code"] for row in action_rows if row["write_allowed"] == "是"]
    cypher = """
    MATCH (n:KGNode)
    WHERE n.code IN $codes
    OPTIONAL MATCH (n)-[r:has_standard_diagnosis]->(sd:KGNode {entityType:'StandardDiagnosis'})
    RETURN n.code AS code, labels(n) AS labels, properties(n) AS props,
           collect(CASE WHEN sd IS NULL THEN NULL ELSE {
             rel: properties(r),
             sd_code: sd.code,
             sd_props: properties(sd)
           } END) AS standard_diagnosis
    ORDER BY code
    """
    with driver.session() as session:
        records = session.run(cypher, codes=disease_codes + action_codes).data()
    return {"nodes": records}


def write_diagnosis(driver, rows: list[dict[str, Any]], batch_id: str) -> int:
    payload = [
        {
            "disease_code": row["disease_code"],
            "cdss_dict_id": str(row["target_id"]),
            "standard_code": str(row["target_code"]),
            "standard_name": str(row["target_name"]),
        }
        for row in rows
        if row["write_allowed"] == "是"
    ]
    if not payload:
        return 0
    cypher = """
    UNWIND $rows AS row
    MATCH (d:KGNode {entityType:'Disease', code: row.disease_code})
    MERGE (sd:KGNode {entityType:'StandardDiagnosis', cdss_dict_id: row.cdss_dict_id})
    ON CREATE SET sd.code = 'STDDX-' + row.cdss_dict_id,
                  sd.created_at = datetime()
    SET sd.name = row.standard_name,
        sd.standard_code = row.standard_code,
        sd.icd10 = row.standard_code,
        sd.coding_system = 'ICD-10（诊断）',
        sd.source_type = 'cdss_standard_dict',
        sd.source_table = 'K_ICD10_DICT',
        sd.valid_flag = 1,
        sd.dictionary_validation_status = 'validated',
        sd.clinical_use_status = 'clinical_ready',
        sd.updated_at = datetime()
    MERGE (d)-[r:has_standard_diagnosis]->(sd)
    SET r.mapping_type = 'oracle有效字典唯一命中',
        r.mapping_status = 'validated',
        r.mapping_scope = 'clinical_diagnosis',
        r.emr_write_allowed = true,
        r.source_table = 'K_ICD10_DICT',
        r.updated_at = datetime()
    SET d.cdss_dict_id = row.cdss_dict_id,
        d.standard_code = row.standard_code,
        d.icd10 = row.standard_code,
        d.dictionary_validation_status = 'validated',
        d.emr_write_allowed = true,
        d.standard_mapping_batch = $batch_id,
        d.updated_at = datetime()
    RETURN count(DISTINCT d) AS changed
    """
    with driver.session() as session:
        return int(session.run(cypher, rows=payload, batch_id=batch_id).single()["changed"])


def write_actions(driver, rows: list[dict[str, Any]], batch_id: str) -> dict[str, int]:
    exact_payload = [
        {
            "node_code": row["node_code"],
            "cdss_dict_id": str(row["target_id"]),
            "standard_code": str(row["target_code"]),
            "standard_name": str(row["target_name"]),
            "source_table": row["target_table"],
        }
        for row in rows
        if row["match_status"] == "唯一命中" and row["write_allowed"] == "是"
    ]
    broad_payload = [
        {"node_code": row["node_code"], "note": row["note"]}
        for row in rows
        if row["match_status"] == "宽口径动作" and row["write_allowed"] == "是"
    ]
    result = {"exact_updated": 0, "broad_classified": 0}
    with driver.session() as session:
        if exact_payload:
            cypher = """
            UNWIND $rows AS row
            MATCH (n:KGNode {code: row.node_code})
            SET n.cdss_dict_id = row.cdss_dict_id,
                n.standard_code = row.standard_code,
                n.standard_name = row.standard_name,
                n.source_table = row.source_table,
                n.valid_flag = 1,
                n.dictionary_validation_status = 'validated',
                n.cdss_dictionary_resolution_status = 'standard_dict_validated',
                n.cdss_dictionary_resolution_note = 'Oracle有效标准字典唯一命中',
                n.cdss_order_ready = true,
                n.cdss_display_ready = true,
                n.emr_write_allowed = true,
                n.standard_mapping_batch = $batch_id,
                n.updated_at = datetime()
            RETURN count(n) AS changed
            """
            result["exact_updated"] = int(session.run(cypher, rows=exact_payload, batch_id=batch_id).single()["changed"])
        if broad_payload:
            cypher = """
            UNWIND $rows AS row
            MATCH (n:KGNode {code: row.node_code})
            SET n.cdss_dictionary_resolution_status = 'non_orderable_category',
                n.cdss_dictionary_resolution_note = row.note,
                n.cdss_dictionary_required_action = '保留为知识展示或上位类别；正式医嘱需下钻到具体标准字典项目。',
                n.cdss_order_ready = false,
                n.cdss_display_ready = true,
                n.emr_write_allowed = false,
                n.standard_mapping_batch = $batch_id,
                n.updated_at = datetime()
            RETURN count(n) AS changed
            """
            result["broad_classified"] = int(session.run(cypher, rows=broad_payload, batch_id=batch_id).single()["changed"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-json", type=Path, default=RAW_JSON)
    parser.add_argument("--gap-csv", type=Path, default=GAP_CSV)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "项目管理中心_project_management" / "2026年8月P6已解析大类终验" / "04_标准字典闭环收口_20260803")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--oracle-user", default="zycdss")
    parser.add_argument("--oracle-dsn", default="192.168.4.25:1521/ORCL")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    oracle_password = os.environ.get("ORACLE_PASSWORD")
    if not oracle_password:
        raise RuntimeError("缺少 ORACLE_PASSWORD 环境变量。")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    batch_id = "P6_STANDARD_DICT_CLOSE_20260803"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    raw, blocked_codes = load_inputs(args.raw_json, args.gap_csv)

    connection = oracledb.connect(user=args.oracle_user, password=oracle_password, dsn=args.oracle_dsn)
    try:
        cursor = connection.cursor()
        diagnosis_rows = build_diagnosis_matrix(raw, blocked_codes, cursor)
        action_rows = build_action_matrix(raw, cursor)
    finally:
        connection.close()

    unresolved_rows = []
    for row in diagnosis_rows:
        if row["write_allowed"] != "是":
            unresolved_rows.append({"gap_type": "标准诊断", **row})
    for row in action_rows:
        if row["write_allowed"] != "是":
            unresolved_rows.append({"gap_type": "正式推荐动作", **row})

    write_csv(
        args.output_dir / "01_标准诊断匹配矩阵.csv",
        diagnosis_rows,
        ["disease_code", "disease_name", "diagnostic_role", "match_status", "candidate_count", "target_table", "target_id", "target_code", "target_name", "write_allowed"],
    )
    write_csv(
        args.output_dir / "02_正式动作匹配矩阵.csv",
        action_rows,
        ["node_code", "node_name", "entity_type", "ref_count", "match_status", "target_table", "candidate_count", "target_id", "target_code", "target_name", "write_allowed", "order_ready", "note"],
    )
    write_csv(
        args.output_dir / "03_未闭环清单.csv",
        unresolved_rows,
        ["gap_type", "disease_code", "disease_name", "diagnostic_role", "node_code", "node_name", "entity_type", "match_status", "target_table", "candidate_count", "note"],
    )

    summary = {
        "generated_at": now,
        "mode": "write" if args.write else "dry_run",
        "diagnosis_total": len(diagnosis_rows),
        "diagnosis_status_count": dict(Counter(row["match_status"] for row in diagnosis_rows)),
        "diagnosis_write_allowed": sum(1 for row in diagnosis_rows if row["write_allowed"] == "是"),
        "action_total": len(action_rows),
        "action_status_count": dict(Counter(row["match_status"] for row in action_rows)),
        "action_write_allowed": sum(1 for row in action_rows if row["write_allowed"] == "是"),
        "unresolved_count": len(unresolved_rows),
        "neo4j_write": {"diagnosis_changed": 0, "action_exact_updated": 0, "action_broad_classified": 0},
        "oracle_written": False,
    }

    if args.write:
        cfg = parse_neo4j_config(args.connection_file)
        driver = GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))
        try:
            backup = backup_neo4j(driver, diagnosis_rows, action_rows)
            write_json(args.output_dir / "04_写库前备份.json", backup)
            summary["neo4j_write"]["diagnosis_changed"] = write_diagnosis(driver, diagnosis_rows, batch_id)
            action_result = write_actions(driver, action_rows, batch_id)
            summary["neo4j_write"]["action_exact_updated"] = action_result["exact_updated"]
            summary["neo4j_write"]["action_broad_classified"] = action_result["broad_classified"]
        finally:
            driver.close()

    write_json(args.output_dir / "00_标准字典闭环收口摘要.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
