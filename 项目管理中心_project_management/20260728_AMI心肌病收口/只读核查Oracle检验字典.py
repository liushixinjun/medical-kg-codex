from __future__ import annotations

import json
import os

import oracledb


NAMES = (
    "肌钙蛋白",
    "心肌肌钙蛋白",
    "N末端B型利钠肽原",
    "D-二聚体",
    "C反应蛋白",
    "红细胞沉降率",
    "心肌损伤标志物",
    "心脏生物标志物检测",
    "利钠肽",
    "凝血",
    "炎症",
)


def fetch(cursor: oracledb.Cursor, table: str) -> list[dict[str, object]]:
    clauses = " OR ".join("NAME LIKE :n" + str(i) for i in range(len(NAMES)))
    binds = {f"n{i}": f"%{name}%" for i, name in enumerate(NAMES)}
    cursor.execute(
        f"""
        SELECT ID, CODE, NAME, VALID_FLAG, SOURCE, REMARK
        FROM {table}
        WHERE VALID_FLAG = 1 AND ({clauses})
        ORDER BY NAME, CODE
        """,
        binds,
    )
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, row, strict=True)) for row in cursor]


def main() -> None:
    password = os.environ.get("CDSS_ORACLE_PASSWORD")
    if not password:
        raise RuntimeError("缺少 CDSS_ORACLE_PASSWORD")
    connection = oracledb.connect(
        user=os.environ.get("CDSS_ORACLE_USER", "zycdss"),
        password=password,
        dsn=os.environ.get("CDSS_ORACLE_DSN", "cdss"),
    )
    try:
        cursor = connection.cursor()
        result = {
            "K_LAB_ITEM_DICT": fetch(cursor, "K_LAB_ITEM_DICT"),
            "K_LAB_SUBITEM_DICT": fetch(cursor, "K_LAB_SUBITEM_DICT"),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
