from __future__ import annotations

import json
import os

import oracledb


TERMS = (
    "致心律失常",
    "心律失常性",
    "右室心肌病",
    "右心室心肌病",
    "左心室心肌病",
    "双心室心肌病",
    "淀粉样",
    "心房心肌病",
    "法布雷",
    "法布里",
    "Fabry",
    "α-半乳糖苷酶",
    "非扩张型",
    "限制型心肌病",
)


def main() -> None:
    password = os.environ.get("CDSS_ORACLE_PASSWORD")
    if not password:
        raise RuntimeError("缺少 CDSS_ORACLE_PASSWORD")
    connection = oracledb.connect(
        user=os.environ.get("CDSS_ORACLE_USER", "zycdss"),
        password=password,
        dsn=os.environ.get("CDSS_ORACLE_DSN", "192.168.4.25:1521/ORCL"),
    )
    try:
        cursor = connection.cursor()
        clauses = " OR ".join(
            f"UPPER(NAME) LIKE UPPER(:n{i})" for i in range(len(TERMS))
        )
        binds = {f"n{i}": f"%{name}%" for i, name in enumerate(TERMS)}
        cursor.execute(
            f"""
            SELECT ID, CODE, NAME, CLASS_CODE, VALID_FLAG, SOURCE, REMARK
            FROM K_ICD10_DICT
            WHERE VALID_FLAG = 1 AND ({clauses})
            ORDER BY NAME, CODE
            """,
            binds,
        )
        cols = [d[0].lower() for d in cursor.description]
        print(
            json.dumps(
                [dict(zip(cols, row, strict=True)) for row in cursor],
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
