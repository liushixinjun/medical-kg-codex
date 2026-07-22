from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import oracledb


DEFAULT_DSN = "192.168.4.25:1521/ORCL"
DEFAULT_USER = "zycdss"


NEW_TABLE_DDLS: dict[str, str] = {
    "K_CLINICAL_SIGN_DICT": """
        CREATE TABLE K_CLINICAL_SIGN_DICT (
            ID VARCHAR2(100) NOT NULL,
            CODE VARCHAR2(200) NOT NULL,
            NAME VARCHAR2(400) NOT NULL,
            VERSION VARCHAR2(100),
            SOURCE VARCHAR2(1000),
            VALID_FLAG NUMBER(1) DEFAULT 1 NOT NULL,
            SPELL_CODE VARCHAR2(200),
            WBZX_CODE VARCHAR2(200),
            SORT_NO NUMBER,
            CREATE_TIME DATE DEFAULT SYSDATE NOT NULL,
            CREATE_OPERATOR NUMBER DEFAULT -1,
            MODIFY_TIME DATE,
            MODIFY_OPERATOR NUMBER,
            REMARK VARCHAR2(4000),
            CONSTRAINT PK_K_CLINICAL_SIGN_DICT PRIMARY KEY (ID),
            CONSTRAINT UK_K_CLINICAL_SIGN_CODE UNIQUE (CODE)
        )
    """,
    "K_EXAM_OBSERVATION_DICT": """
        CREATE TABLE K_EXAM_OBSERVATION_DICT (
            ID VARCHAR2(100) NOT NULL,
            CODE VARCHAR2(200) NOT NULL,
            NAME VARCHAR2(400) NOT NULL,
            VERSION VARCHAR2(100),
            SOURCE VARCHAR2(1000),
            VALID_FLAG NUMBER(1) DEFAULT 1 NOT NULL,
            SPELL_CODE VARCHAR2(200),
            WBZX_CODE VARCHAR2(200),
            SORT_NO NUMBER,
            CREATE_TIME DATE DEFAULT SYSDATE NOT NULL,
            CREATE_OPERATOR NUMBER DEFAULT -1,
            MODIFY_TIME DATE,
            MODIFY_OPERATOR NUMBER,
            REMARK VARCHAR2(4000),
            CONSTRAINT PK_K_EXAM_OBSERVATION PRIMARY KEY (ID),
            CONSTRAINT UK_K_EXAM_OBSERV_CODE UNIQUE (CODE)
        )
    """,
    "K_VITAL_SIGN_ITEM_DICT": """
        CREATE TABLE K_VITAL_SIGN_ITEM_DICT (
            ID VARCHAR2(100) NOT NULL,
            CODE VARCHAR2(200) NOT NULL,
            NAME VARCHAR2(400) NOT NULL,
            UNIT VARCHAR2(100),
            VALUE_TYPE VARCHAR2(50) DEFAULT 'NUMBER',
            VERSION VARCHAR2(100),
            SOURCE VARCHAR2(1000),
            VALID_FLAG NUMBER(1) DEFAULT 1 NOT NULL,
            SORT_NO NUMBER,
            CREATE_TIME DATE DEFAULT SYSDATE NOT NULL,
            CREATE_OPERATOR NUMBER DEFAULT -1,
            MODIFY_TIME DATE,
            MODIFY_OPERATOR NUMBER,
            REMARK VARCHAR2(4000),
            CONSTRAINT PK_K_VITAL_SIGN_ITEM PRIMARY KEY (ID),
            CONSTRAINT UK_K_VITAL_SIGN_CODE UNIQUE (CODE)
        )
    """,
    "K_EXAM_OBSERVATION_REL": """
        CREATE TABLE K_EXAM_OBSERVATION_REL (
            ID VARCHAR2(100) NOT NULL,
            EXAM_ITEM_ID VARCHAR2(100) NOT NULL,
            OBSERVATION_ID VARCHAR2(100) NOT NULL,
            SOURCE VARCHAR2(1000),
            EVIDENCE_ID VARCHAR2(200),
            VALID_FLAG NUMBER(1) DEFAULT 1 NOT NULL,
            CREATE_TIME DATE DEFAULT SYSDATE NOT NULL,
            CREATE_OPERATOR NUMBER DEFAULT -1,
            MODIFY_TIME DATE,
            MODIFY_OPERATOR NUMBER,
            REMARK VARCHAR2(4000),
            CONSTRAINT PK_K_EXAM_OBSERV_REL PRIMARY KEY (ID)
        )
    """,
    "K_TERM_DICT_MAPPING": """
        CREATE TABLE K_TERM_DICT_MAPPING (
            ID VARCHAR2(100) NOT NULL,
            TERM_ID VARCHAR2(100) NOT NULL,
            DICT_TABLE VARCHAR2(100) NOT NULL,
            DICT_ID VARCHAR2(100) NOT NULL,
            DICT_CODE VARCHAR2(200),
            DICT_NAME VARCHAR2(400),
            MATCH_TYPE VARCHAR2(50) NOT NULL,
            MATCH_STATUS VARCHAR2(50) DEFAULT 'VALIDATED' NOT NULL,
            MATCH_CONFIDENCE NUMBER(5,4),
            SOURCE VARCHAR2(1000),
            VALID_FLAG NUMBER(1) DEFAULT 1 NOT NULL,
            CREATE_TIME DATE DEFAULT SYSDATE NOT NULL,
            CREATE_OPERATOR NUMBER DEFAULT -1,
            MODIFY_TIME DATE,
            MODIFY_OPERATOR NUMBER,
            REMARK VARCHAR2(4000),
            CONSTRAINT PK_K_TERM_DICT_MAPPING PRIMARY KEY (ID)
        )
    """,
    "K_KG_DICT_CHANGE_REVIEW": """
        CREATE TABLE K_KG_DICT_CHANGE_REVIEW (
            ID VARCHAR2(100) NOT NULL,
            ENTITY_TYPE VARCHAR2(100),
            KG_NODE_CODE VARCHAR2(200),
            KG_NODE_NAME VARCHAR2(400),
            TARGET_TABLE VARCHAR2(100),
            TARGET_ID VARCHAR2(100),
            TARGET_CODE VARCHAR2(200),
            TARGET_NAME VARCHAR2(400),
            ISSUE_TYPE VARCHAR2(100) NOT NULL,
            CURRENT_VALUE CLOB,
            PROPOSED_VALUE CLOB,
            REASON VARCHAR2(4000),
            SOURCE VARCHAR2(1000),
            REVIEW_STATUS VARCHAR2(50) DEFAULT 'PENDING' NOT NULL,
            EXECUTION_STATUS VARCHAR2(50) DEFAULT 'NOT_EXECUTED' NOT NULL,
            VALID_FLAG NUMBER(1) DEFAULT 1 NOT NULL,
            CREATE_TIME DATE DEFAULT SYSDATE NOT NULL,
            CREATE_OPERATOR NUMBER DEFAULT -1,
            MODIFY_TIME DATE,
            MODIFY_OPERATOR NUMBER,
            REMARK VARCHAR2(4000),
            CONSTRAINT PK_K_KG_DICT_CHANGE_REVIEW PRIMARY KEY (ID)
        )
    """,
    "K_DIAGNOSIS_RULE": """
        CREATE TABLE K_DIAGNOSIS_RULE (
            ID VARCHAR2(100) NOT NULL,
            DISEASE_NODE_CODE VARCHAR2(200) NOT NULL,
            DISEASE_NAME VARCHAR2(400) NOT NULL,
            DIAGNOSIS_DICT_ID VARCHAR2(100),
            RULE_NAME VARCHAR2(400) NOT NULL,
            RULE_SCOPE VARCHAR2(50) DEFAULT 'SUSPECTED_DIAGNOSIS' NOT NULL,
            RULE_VERSION VARCHAR2(100) NOT NULL,
            STATUS VARCHAR2(50) DEFAULT 'ACTIVE' NOT NULL,
            EFFECT_MODEL_VERSION VARCHAR2(100) NOT NULL,
            SOURCE VARCHAR2(1000),
            VALID_FLAG NUMBER(1) DEFAULT 1 NOT NULL,
            CREATE_TIME DATE DEFAULT SYSDATE NOT NULL,
            CREATE_OPERATOR NUMBER DEFAULT -1,
            MODIFY_TIME DATE,
            MODIFY_OPERATOR NUMBER,
            REMARK VARCHAR2(4000),
            CONSTRAINT PK_K_DIAGNOSIS_RULE PRIMARY KEY (ID)
        )
    """,
    "K_DIAGNOSIS_RULE_ITEM": """
        CREATE TABLE K_DIAGNOSIS_RULE_ITEM (
            ID VARCHAR2(100) NOT NULL,
            RULE_ID VARCHAR2(100) NOT NULL,
            FINDING_TYPE VARCHAR2(100) NOT NULL,
            FINDING_DICT_TABLE VARCHAR2(100),
            FINDING_DICT_ID VARCHAR2(100),
            FINDING_CODE VARCHAR2(200),
            FINDING_NAME VARCHAR2(400) NOT NULL,
            EFFECT_CODE VARCHAR2(50) NOT NULL,
            WEIGHT_LEVEL NUMBER(1) DEFAULT 0 NOT NULL,
            SCORE_ENABLED NUMBER(1) DEFAULT 0 NOT NULL,
            TRIGGER_OPERATOR VARCHAR2(50) DEFAULT 'PRESENT',
            TRIGGER_VALUE VARCHAR2(400),
            UNIT VARCHAR2(100),
            REQUIRED_FLAG NUMBER(1) DEFAULT 0 NOT NULL,
            NEGATION_POLICY VARCHAR2(50) DEFAULT 'NO_SCORE',
            EXTRACTION_CONFIDENCE NUMBER(5,4),
            INITIALIZATION_METHOD VARCHAR2(100) NOT NULL,
            SOURCE_EVIDENCE_ID VARCHAR2(200),
            SOURCE_TEXT CLOB,
            MANUAL_OVERRIDE NUMBER(1) DEFAULT 0 NOT NULL,
            REVIEW_STATUS VARCHAR2(50) DEFAULT 'AUTO_INITIALIZED' NOT NULL,
            VALID_FLAG NUMBER(1) DEFAULT 1 NOT NULL,
            CREATE_TIME DATE DEFAULT SYSDATE NOT NULL,
            CREATE_OPERATOR NUMBER DEFAULT -1,
            MODIFY_TIME DATE,
            MODIFY_OPERATOR NUMBER,
            REMARK VARCHAR2(4000),
            CONSTRAINT PK_K_DIAGNOSIS_RULE_ITEM PRIMARY KEY (ID)
        )
    """,
    "K_DIAGNOSIS_RULE_VERSION": """
        CREATE TABLE K_DIAGNOSIS_RULE_VERSION (
            ID VARCHAR2(100) NOT NULL,
            MODEL_VERSION VARCHAR2(100) NOT NULL,
            MODEL_NAME VARCHAR2(400) NOT NULL,
            SCORE_MATRIX CLOB NOT NULL,
            STATUS VARCHAR2(50) DEFAULT 'ACTIVE' NOT NULL,
            RELEASE_TIME DATE,
            SOURCE VARCHAR2(1000),
            VALID_FLAG NUMBER(1) DEFAULT 1 NOT NULL,
            CREATE_TIME DATE DEFAULT SYSDATE NOT NULL,
            CREATE_OPERATOR NUMBER DEFAULT -1,
            MODIFY_TIME DATE,
            MODIFY_OPERATOR NUMBER,
            REMARK VARCHAR2(4000),
            CONSTRAINT PK_K_DIAG_RULE_VERSION PRIMARY KEY (ID),
            CONSTRAINT UK_K_DIAG_MODEL_VERSION UNIQUE (MODEL_VERSION)
        )
    """,
    "K_DIAGNOSIS_RULE_LOG": """
        CREATE TABLE K_DIAGNOSIS_RULE_LOG (
            ID VARCHAR2(100) NOT NULL,
            RULE_ID VARCHAR2(100),
            RULE_ITEM_ID VARCHAR2(100),
            ACTION_TYPE VARCHAR2(100) NOT NULL,
            BEFORE_VALUE CLOB,
            AFTER_VALUE CLOB,
            OPERATOR_ID VARCHAR2(100),
            OPERATOR_NAME VARCHAR2(200),
            ACTION_TIME DATE DEFAULT SYSDATE NOT NULL,
            REMARK VARCHAR2(4000),
            CONSTRAINT PK_K_DIAGNOSIS_RULE_LOG PRIMARY KEY (ID)
        )
    """,
}


NEW_INDEX_DDLS: list[tuple[str, str]] = [
    ("IX_K_CLINICAL_SIGN_NAME", "CREATE INDEX IX_K_CLINICAL_SIGN_NAME ON K_CLINICAL_SIGN_DICT(NAME)"),
    ("IX_K_EXAM_OBSERV_NAME", "CREATE INDEX IX_K_EXAM_OBSERV_NAME ON K_EXAM_OBSERVATION_DICT(NAME)"),
    ("IX_K_EXAM_OBSERV_REL_ITEM", "CREATE INDEX IX_K_EXAM_OBSERV_REL_ITEM ON K_EXAM_OBSERVATION_REL(EXAM_ITEM_ID)"),
    ("IX_K_EXAM_OBSERV_REL_OBS", "CREATE INDEX IX_K_EXAM_OBSERV_REL_OBS ON K_EXAM_OBSERVATION_REL(OBSERVATION_ID)"),
    ("IX_K_TERM_MAP_TERM", "CREATE INDEX IX_K_TERM_MAP_TERM ON K_TERM_DICT_MAPPING(TERM_ID)"),
    ("IX_K_TERM_MAP_DICT", "CREATE INDEX IX_K_TERM_MAP_DICT ON K_TERM_DICT_MAPPING(DICT_TABLE, DICT_ID)"),
    ("IX_K_DICT_REVIEW_STATUS", "CREATE INDEX IX_K_DICT_REVIEW_STATUS ON K_KG_DICT_CHANGE_REVIEW(REVIEW_STATUS, EXECUTION_STATUS)"),
    ("IX_K_DIAG_RULE_DISEASE", "CREATE INDEX IX_K_DIAG_RULE_DISEASE ON K_DIAGNOSIS_RULE(DISEASE_NODE_CODE)"),
    ("IX_K_DIAG_ITEM_RULE", "CREATE INDEX IX_K_DIAG_ITEM_RULE ON K_DIAGNOSIS_RULE_ITEM(RULE_ID)"),
    ("IX_K_DIAG_ITEM_FINDING", "CREATE INDEX IX_K_DIAG_ITEM_FINDING ON K_DIAGNOSIS_RULE_ITEM(FINDING_TYPE, FINDING_DICT_ID)"),
]


def json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, oracledb.LOB):
        content = value.read()
        if isinstance(content, bytes):
            return content.hex()
        return content
    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=json_value), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fetch_dicts(cursor: oracledb.Cursor, sql: str, **binds: Any) -> list[dict[str, Any]]:
    cursor.execute(sql, binds)
    fields = [item[0].lower() for item in cursor.description]
    return [dict(zip(fields, row)) for row in cursor]


def discover_tables(cursor: oracledb.Cursor) -> list[str]:
    cursor.execute(
        """
        SELECT table_name
          FROM user_tables
         WHERE table_name LIKE '%DICT%'
            OR table_name LIKE 'K_TERM%'
            OR table_name LIKE '%BACK%NAME%'
            OR table_name LIKE '%SIGN%'
            OR table_name LIKE '%VITAL%'
            OR table_name LIKE '%OBSERV%'
         ORDER BY table_name
        """
    )
    return [row[0] for row in cursor]


def table_snapshot(cursor: oracledb.Cursor, tables: list[str]) -> dict[str, Any]:
    if not tables:
        return {"tables": [], "columns": [], "constraints": [], "indexes": [], "triggers": []}
    binds = {f"t{i}": name for i, name in enumerate(tables)}
    in_list = ",".join(f":t{i}" for i in range(len(tables)))
    columns = fetch_dicts(
        cursor,
        f"""
        SELECT table_name, column_id, column_name, data_type, data_length,
               data_precision, data_scale, nullable, data_default
          FROM user_tab_columns
         WHERE table_name IN ({in_list})
         ORDER BY table_name, column_id
        """,
        **binds,
    )
    constraints = fetch_dicts(
        cursor,
        f"""
        SELECT c.table_name, c.constraint_name, c.constraint_type, c.status,
               cc.column_name, cc.position, c.r_constraint_name
          FROM user_constraints c
          LEFT JOIN user_cons_columns cc
            ON cc.constraint_name = c.constraint_name
           AND cc.table_name = c.table_name
         WHERE c.table_name IN ({in_list})
         ORDER BY c.table_name, c.constraint_name, cc.position
        """,
        **binds,
    )
    indexes = fetch_dicts(
        cursor,
        f"""
        SELECT i.table_name, i.index_name, i.uniqueness, ic.column_name, ic.column_position
          FROM user_indexes i
          JOIN user_ind_columns ic ON ic.index_name = i.index_name
         WHERE i.table_name IN ({in_list})
         ORDER BY i.table_name, i.index_name, ic.column_position
        """,
        **binds,
    )
    triggers = fetch_dicts(
        cursor,
        f"""
        SELECT table_name, trigger_name, status, triggering_event, trigger_type
          FROM user_triggers
         WHERE table_name IN ({in_list})
         ORDER BY table_name, trigger_name
        """,
        **binds,
    )
    table_rows: list[dict[str, Any]] = []
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        table_rows.append({"table_name": table, "row_count": cursor.fetchone()[0]})
    return {
        "tables": table_rows,
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "triggers": triggers,
    }


def sample_rows(cursor: oracledb.Cursor, tables: list[str], limit: int = 3) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for table in tables:
        cursor.execute(f'SELECT * FROM "{table}" WHERE ROWNUM <= :limit', limit=limit)
        fields = [item[0].lower() for item in cursor.description]
        result[table] = [dict(zip(fields, row)) for row in cursor]
    return result


def run_snapshot(cursor: oracledb.Cursor, output_dir: Path) -> dict[str, Any]:
    tables = discover_tables(cursor)
    snapshot = table_snapshot(cursor, tables)
    samples = sample_rows(cursor, tables)
    write_json(output_dir / "01_Oracle字典表结构快照.json", snapshot)
    write_json(output_dir / "02_Oracle字典样例数据.json", samples)
    write_csv(
        output_dir / "03_Oracle字典表清单.csv",
        snapshot["tables"],
        ["table_name", "row_count"],
    )
    write_csv(
        output_dir / "04_Oracle字典字段清单.csv",
        snapshot["columns"],
        [
            "table_name",
            "column_id",
            "column_name",
            "data_type",
            "data_length",
            "data_precision",
            "data_scale",
            "nullable",
            "data_default",
        ],
    )
    return {
        "table_count": len(tables),
        "tables": snapshot["tables"],
        "output_dir": str(output_dir),
    }


def existing_objects(cursor: oracledb.Cursor, object_type: str) -> set[str]:
    cursor.execute(
        "SELECT object_name FROM user_objects WHERE object_type = :object_type",
        object_type=object_type,
    )
    return {row[0] for row in cursor}


def create_new_tables(connection: oracledb.Connection, output_dir: Path) -> dict[str, Any]:
    cursor = connection.cursor()
    created_tables: list[str] = []
    retained_tables: list[str] = []
    created_indexes: list[str] = []
    retained_indexes: list[str] = []
    try:
        tables = existing_objects(cursor, "TABLE")
        for table, ddl in NEW_TABLE_DDLS.items():
            if table in tables:
                retained_tables.append(table)
                continue
            cursor.execute(ddl)
            created_tables.append(table)
        indexes = existing_objects(cursor, "INDEX")
        for index_name, ddl in NEW_INDEX_DDLS:
            if index_name in indexes:
                retained_indexes.append(index_name)
                continue
            cursor.execute(ddl)
            created_indexes.append(index_name)
        connection.commit()
        result = {
            "created_tables": created_tables,
            "retained_tables": retained_tables,
            "created_indexes": created_indexes,
            "retained_indexes": retained_indexes,
        }
        write_json(output_dir / "05_Oracle新增表执行结果.json", result)
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def postcheck_new_tables(cursor: oracledb.Cursor, output_dir: Path) -> dict[str, Any]:
    expected = list(NEW_TABLE_DDLS)
    existing = existing_objects(cursor, "TABLE")
    rows: list[dict[str, Any]] = []
    for table in expected:
        if table in existing:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            count = cursor.fetchone()[0]
        else:
            count = None
        rows.append({"table_name": table, "exists": table in existing, "row_count": count})
    result = {
        "expected_table_count": len(expected),
        "existing_table_count": sum(1 for row in rows if row["exists"]),
        "missing_tables": [row["table_name"] for row in rows if not row["exists"]],
        "tables": rows,
    }
    write_json(output_dir / "06_Oracle新增表复核.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Oracle 标准字典治理 V2.0")
    parser.add_argument("--mode", choices=["snapshot", "create-new-tables", "postcheck-new-tables"], required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password-env", default="CDSS_ORACLE_PASSWORD")
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise ValueError(f"缺少环境变量：{args.password_env}")
    output_dir = args.output_dir.resolve()
    connection = oracledb.connect(user=args.user, password=password, dsn=args.dsn)
    try:
        cursor = connection.cursor()
        try:
            if args.mode == "snapshot":
                result = run_snapshot(cursor, output_dir)
            elif args.mode == "create-new-tables":
                cursor.close()
                result = create_new_tables(connection, output_dir)
                cursor = None
            elif args.mode == "postcheck-new-tables":
                result = postcheck_new_tables(cursor, output_dir)
            else:
                raise ValueError(f"不支持的模式：{args.mode}")
        finally:
            if cursor is not None:
                cursor.close()
    finally:
        connection.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=json_value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
