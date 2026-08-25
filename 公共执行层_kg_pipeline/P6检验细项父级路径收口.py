from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import oracledb
from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = (
    ROOT
    / "项目管理中心_project_management"
    / "2026年8月P6已解析大类终验"
    / "08_语义等价收口后复核_20260803"
    / "00_P6已解析大类终验_raw.json"
)
DEFAULT_OUT = (
    ROOT
    / "项目管理中心_project_management"
    / "2026年8月P6已解析大类终验"
    / "09_检验细项父级路径收口_20260803"
)


# 只做确定性映射：能从 Oracle 有效检验项目表确认的，用 Oracle；Oracle 没有的，只生成“知识父级”，不进入正式 CDSS 医嘱回填。
PARENT_TERMS: dict[str, list[str]] = {
    "尿酸": ["尿酸", "血清尿酸", "血清尿酸(UA)测定"],
    "醛固酮/肾素比值": ["醛固酮/肾素比值", "醛固酮肾素比值", "ARR"],
    "尿白蛋白/肌酐比值": ["尿白蛋白/肌酐比值", "尿白蛋白肌酐比值", "UACR"],
}

GRAPH_PARENT_FALLBACK: dict[str, dict[str, str]] = {
    "醛固酮/肾素比值": {
        "graph_code": "LABITEM-GRAPH-ARR",
        "name": "醛固酮/肾素比值测定",
        "source_table": "GRAPH_KNOWLEDGE_PARENT",
        "validation_status": "pending_dictionary_registration",
        "decision": "Oracle未找到有效检验项目父级；生成知识父级，暂不作为CDSS正式医嘱项目",
    },
    "尿白蛋白/肌酐比值": {
        "graph_code": "LABITEM-GRAPH-UACR",
        "name": "尿白蛋白/肌酐比值测定",
        "source_table": "GRAPH_KNOWLEDGE_PARENT",
        "validation_status": "pending_dictionary_registration",
        "decision": "Oracle未找到有效检验项目父级；生成知识父级，暂不作为CDSS正式医嘱项目",
    },
}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normal_name(value: str) -> str:
    value = (value or "").lower()
    value = value.replace("（", "(").replace("）", ")")
    value = re.sub(r"[\s·、,/()（）\-—_：:]+", "", value)
    value = value.replace("测定", "").replace("检查", "").replace("检验", "")
    return value


def oracle_value(value: Any) -> Any:
    if isinstance(value, oracledb.LOB):
        return value.read()
    return value


def read_graph_config() -> dict[str, str]:
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USERNAME")
    password = os.environ.get("NEO4J_PASSWORD")
    if uri and user and password:
        return {"uri": uri, "user": user, "password": password}

    cfg_path = ROOT / "图谱数据库链接.txt"
    text = cfg_path.read_text(encoding="utf-8", errors="ignore")

    def pick(pattern: str, default: str = "") -> str:
        match = re.search(pattern, text, flags=re.I)
        return match.group(1).strip() if match else default

    uri = pick(r"bolt://([^\s]+)", "192.168.3.27:7687")
    user = pick(r"用户名[:：]\s*([^\s]+)", "neo4j")
    password = pick(r"密码[:：]\s*([^\s]+)", "")
    if not password:
        raise RuntimeError("缺少 NEO4J_PASSWORD 环境变量，且图谱数据库链接.txt 未提供密码字段。")
    return {"uri": f"bolt://{uri}", "user": user, "password": password}


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def load_invalid_paths(raw_json: Path) -> list[dict[str, Any]]:
    raw = json.loads(raw_json.read_text(encoding="utf-8"))
    return [
        row
        for row in raw.get("invalid_paths", [])
        if row.get("problem") == "ExamPlan直接连接检验细项"
        and row.get("target_type") == "LabSubitem"
    ]


def lab_item_candidates(cursor: oracledb.Cursor, subitem_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for term in PARENT_TERMS.get(subitem_name, [subitem_name]):
        cursor.execute(
            """
            SELECT id, code, name, valid_flag
              FROM K_LAB_ITEM_DICT
             WHERE valid_flag = 1
               AND name LIKE :kw
             ORDER BY name, code
             FETCH FIRST 30 ROWS ONLY
            """,
            kw=f"%{term}%",
        )
        columns = [column[0].lower() for column in cursor.description]
        for record in cursor.fetchall():
            row = {column: oracle_value(value) for column, value in zip(columns, record)}
            key = (str(row.get("id") or ""), str(row.get("code") or ""), str(row.get("name") or ""))
            if key in seen:
                continue
            seen.add(key)
            row["query_term"] = term
            rows.append(row)
    return rows


def choose_parent_candidate(subitem_name: str, candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    target_norms = {normal_name(term) for term in PARENT_TERMS.get(subitem_name, [subitem_name])}
    target_norms.add(normal_name(subitem_name))

    strict = [row for row in candidates if normal_name(str(row.get("name") or "")) in target_norms]
    unique_by_id: dict[str, dict[str, Any]] = {str(row.get("id") or ""): row for row in strict}
    strict_unique = list(unique_by_id.values())

    if len(strict_unique) == 1:
        chosen = dict(strict_unique[0])
        chosen["source_table"] = "K_LAB_ITEM_DICT"
        chosen["validation_status"] = "validated"
        chosen["graph_code"] = f"LABITEM-CDSS-{str(chosen.get('code') or '').strip()}"
        return chosen, "唯一严格命中Oracle有效检验项目"

    if len(strict_unique) > 1:
        return None, "多个Oracle严格命中，需人工裁决"

    if subitem_name in GRAPH_PARENT_FALLBACK:
        fallback = dict(GRAPH_PARENT_FALLBACK[subitem_name])
        fallback["id"] = ""
        fallback["code"] = ""
        return fallback, fallback["decision"]

    if candidates:
        return None, "只有宽松候选，不能自动修复"
    return None, "Oracle无有效候选"


def collect_plan(session, cursor: oracledb.Cursor, invalid_paths: list[dict[str, Any]]) -> dict[str, Any]:
    unique_subitems = sorted({row["target_name"] for row in invalid_paths})
    candidate_rows: list[dict[str, Any]] = []
    chosen_by_subitem: dict[str, dict[str, Any]] = {}
    decision_by_subitem: dict[str, str] = {}

    for subitem_name in unique_subitems:
        candidates = lab_item_candidates(cursor, subitem_name)
        chosen, decision = choose_parent_candidate(subitem_name, candidates)
        decision_by_subitem[subitem_name] = decision
        if chosen:
            chosen_by_subitem[subitem_name] = chosen

        for candidate in candidates:
            candidate_rows.append(
                {
                    "检验细项": subitem_name,
                    "候选父级检验项目ID": candidate.get("id", ""),
                    "候选父级检验项目编码": candidate.get("code", ""),
                    "候选父级检验项目名称": candidate.get("name", ""),
                    "查询词": candidate.get("query_term", ""),
                    "判定": decision,
                    "是否选中": "是" if chosen and candidate.get("id") == chosen.get("id") else "否",
                }
            )

        if chosen and chosen.get("validation_status") == "pending_dictionary_registration":
            candidate_rows.append(
                {
                    "检验细项": subitem_name,
                    "候选父级检验项目ID": "",
                    "候选父级检验项目编码": chosen.get("graph_code", ""),
                    "候选父级检验项目名称": chosen.get("name", ""),
                    "查询词": "教材/指南证据",
                    "判定": decision,
                    "是否选中": "是",
                }
            )
        elif not candidates:
            candidate_rows.append(
                {
                    "检验细项": subitem_name,
                    "候选父级检验项目ID": "",
                    "候选父级检验项目编码": "",
                    "候选父级检验项目名称": "",
                    "查询词": "",
                    "判定": decision,
                    "是否选中": "否",
                }
            )

    repairable: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in invalid_paths:
        subitem_name = row["target_name"]
        chosen = chosen_by_subitem.get(subitem_name)
        base = dict(row)
        base["判定"] = decision_by_subitem.get(subitem_name, "")
        if not chosen:
            blocked.append(base)
            continue
        base.update(
            {
                "父级检验项目ID": chosen.get("id", ""),
                "父级检验项目编码": chosen.get("code", ""),
                "父级检验项目名称": chosen.get("name", ""),
                "父级图谱编码": chosen.get("graph_code", ""),
                "父级来源表": chosen.get("source_table", ""),
                "父级字典校验状态": chosen.get("validation_status", ""),
            }
        )
        repairable.append(base)

    backup_rows = [
        dict(r)
        for r in session.run(
            """
            MATCH (p:KGNode)-[rel:includes_lab_item]->(sub:KGNode {entityType:'LabSubitem'})
            WHERE p.code IN $plan_codes AND sub.code IN $subitem_codes
            RETURN elementId(rel) AS rel_eid,
                   p.code AS plan_code,
                   p.name AS plan_name,
                   sub.code AS subitem_code,
                   sub.name AS subitem_name,
                   properties(p) AS plan_props,
                   properties(sub) AS subitem_props,
                   properties(rel) AS rel_props
            ORDER BY plan_name, subitem_name
            """,
            plan_codes=sorted({row["source_code"] for row in invalid_paths}),
            subitem_codes=sorted({row["target_code"] for row in invalid_paths}),
        )
    ]

    return {
        "generated_at": now_text(),
        "invalid_path_count": len(invalid_paths),
        "unique_subitems": unique_subitems,
        "candidate_rows": candidate_rows,
        "repairable": repairable,
        "blocked": blocked,
        "backup_rows": backup_rows,
    }


def verify(session) -> dict[str, int]:
    row = session.run(
        """
        MATCH (:KGNode {entityType:'Disease'})-[:has_exam_plan]->(:KGNode {entityType:'ExamPlan'})
              -[r:includes_lab_item]->(:KGNode {entityType:'LabSubitem'})
        RETURN count(r) AS direct_examplan_to_labsubitem
        """
    ).single()
    return {"direct_examplan_to_labsubitem": int(row["direct_examplan_to_labsubitem"])}


def apply_repairs(session, plan: dict[str, Any]) -> dict[str, Any]:
    ts = now_text()
    result = {
        "executed_at": ts,
        "created_or_matched_lab_items": 0,
        "created_or_matched_parent_child_relations": 0,
        "created_or_matched_plan_parent_relations": 0,
        "deleted_direct_plan_subitem_relations": 0,
        "blocked_path_count": len(plan["blocked"]),
    }

    for row in plan["repairable"]:
        parent_code = row["父级图谱编码"]
        parent_name = row["父级检验项目名称"]
        parent_dict_id = row["父级检验项目ID"] or None
        parent_dict_code = row["父级检验项目编码"] or None
        parent_source_table = row["父级来源表"]
        parent_validation_status = row["父级字典校验状态"]
        formal_ready = parent_validation_status == "validated"
        subitem_code = row["target_code"]
        plan_code = row["source_code"]

        session.run(
            """
            MERGE (li:KGNode:LabItem {code:$parent_code})
            ON CREATE SET li.created_at=$ts,
                          li.created_by='P6检验细项父级路径收口'
            SET li.entityType='LabItem',
                li.type_label='LabItem',
                li.name=$parent_name,
                li.display_name=$parent_name,
                li.preferred_name=$parent_name,
                li.source_table=$parent_source_table,
                li.cdss_dict_id=$parent_dict_id,
                li.cdss_dict_code=$parent_dict_code,
                li.standard_source_table=CASE WHEN $formal_ready THEN 'K_LAB_ITEM_DICT' ELSE null END,
                li.standard_dict_id=$parent_dict_id,
                li.standard_dict_code=$parent_dict_code,
                li.standard_name=$parent_name,
                li.dictionary_validation_status=$parent_validation_status,
                li.valid_flag=CASE WHEN $formal_ready THEN 1 ELSE 0 END,
                li.formal_cdss_ready=$formal_ready,
                li.orderable=$formal_ready,
                li.dictionary_block_reason=CASE WHEN $formal_ready THEN null ELSE 'CDSS检验项目字典未注册，当前只作为知识父级用于路径结构收口' END,
                li.status='active',
                li.updated_at=$ts
            """,
            parent_code=parent_code,
            parent_name=parent_name,
            parent_source_table=parent_source_table,
            parent_dict_id=parent_dict_id,
            parent_dict_code=parent_dict_code,
            parent_validation_status=parent_validation_status,
            formal_ready=formal_ready,
            ts=ts,
        )
        result["created_or_matched_lab_items"] += 1

        session.run(
            """
            MATCH (li:KGNode {code:$parent_code, entityType:'LabItem'})
            MATCH (sub:KGNode {code:$subitem_code, entityType:'LabSubitem'})
            MERGE (li)-[r:lab_item_has_subitem]->(sub)
            ON CREATE SET r.created_at=$ts,
                          r.created_by='P6检验细项父级路径收口'
            SET r.source='P6检验细项父级路径收口',
                r.updated_at=$ts,
                r.status='active'
            """,
            parent_code=parent_code,
            subitem_code=subitem_code,
            ts=ts,
        )
        result["created_or_matched_parent_child_relations"] += 1

        session.run(
            """
            MATCH (plan:KGNode {code:$plan_code, entityType:'ExamPlan'})
            MATCH (li:KGNode {code:$parent_code, entityType:'LabItem'})
            MERGE (plan)-[r:includes_lab_item]->(li)
            ON CREATE SET r.created_at=$ts,
                          r.created_by='P6检验细项父级路径收口'
            SET r.source='P6检验细项父级路径收口',
                r.migration_reason='ExamPlan不能直接连接LabSubitem，需通过LabItem中转',
                r.updated_at=$ts,
                r.status='active'
            """,
            plan_code=plan_code,
            parent_code=parent_code,
            ts=ts,
        )
        result["created_or_matched_plan_parent_relations"] += 1

        delete_result = session.run(
            """
            MATCH (plan:KGNode {code:$plan_code, entityType:'ExamPlan'})
                  -[old:includes_lab_item]->(sub:KGNode {code:$subitem_code, entityType:'LabSubitem'})
            DELETE old
            RETURN count(old) AS n
            """,
            plan_code=plan_code,
            subitem_code=subitem_code,
        ).single()
        result["deleted_direct_plan_subitem_relations"] += int(delete_result["n"] if delete_result else 0)

    return result


def save_outputs(out_dir: Path, plan: dict[str, Any], result: dict[str, Any] | None = None) -> None:
    write_csv(
        out_dir / "01_检验细项父级候选.csv",
        plan["candidate_rows"],
        ["检验细项", "候选父级检验项目ID", "候选父级检验项目编码", "候选父级检验项目名称", "查询词", "判定", "是否选中"],
    )
    write_csv(
        out_dir / "02_可修复路径.csv",
        plan["repairable"],
        [
            "disease_code",
            "disease_name",
            "source_code",
            "source_name",
            "target_code",
            "target_name",
            "父级检验项目ID",
            "父级检验项目编码",
            "父级检验项目名称",
            "父级图谱编码",
            "父级来源表",
            "父级字典校验状态",
            "判定",
        ],
    )
    write_csv(
        out_dir / "03_阻断路径.csv",
        plan["blocked"],
        ["disease_code", "disease_name", "source_code", "source_name", "target_code", "target_name", "判定"],
    )
    write_json(out_dir / "04_写库前Neo4j备份.json", plan["backup_rows"])
    write_json(
        out_dir / "00_检验细项父级路径收口_summary.json",
        {
            "generated_at": plan["generated_at"],
            "invalid_path_count": plan["invalid_path_count"],
            "unique_subitems": plan["unique_subitems"],
            "repairable_count": len(plan["repairable"]),
            "blocked_count": len(plan["blocked"]),
            "result": result,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="P6检验细项父级路径收口：只读Oracle，可选写Neo4j，不写Oracle。")
    parser.add_argument("--raw-json", default=str(DEFAULT_RAW))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--write", action="store_true", help="写入Neo4j；默认只生成计划。")
    parser.add_argument("--oracle-user", default=os.environ.get("CDSS_ORACLE_USER", "zycdss"))
    parser.add_argument("--oracle-dsn", default=os.environ.get("CDSS_ORACLE_DSN", "192.168.4.25:1521/ORCL"))
    parser.add_argument("--oracle-password-env", default="ORACLE_PASSWORD")
    args = parser.parse_args()

    oracle_password = os.environ.get(args.oracle_password_env) or os.environ.get("CDSS_ORACLE_PASSWORD")
    if not oracle_password:
        raise RuntimeError("缺少Oracle密码环境变量：ORACLE_PASSWORD 或 CDSS_ORACLE_PASSWORD")

    invalid_paths = load_invalid_paths(Path(args.raw_json))
    cfg = read_graph_config()
    out_dir = Path(args.output_dir)

    driver = GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))
    oracle = oracledb.connect(user=args.oracle_user, password=oracle_password, dsn=args.oracle_dsn)
    try:
        with driver.session() as session:
            before = verify(session)
            with oracle.cursor() as cursor:
                plan = collect_plan(session, cursor, invalid_paths)
            result: dict[str, Any] = {
                "mode": "dry_run",
                "neo4j_written": False,
                "oracle_written": False,
                "before": before,
                "after": before,
            }
            if args.write:
                write_result = apply_repairs(session, plan)
                after = verify(session)
                result = {
                    "mode": "write",
                    "neo4j_written": True,
                    "oracle_written": False,
                    "before": before,
                    "after": after,
                    "write_counts": write_result,
                }
            save_outputs(out_dir, plan, result)
            print(
                json.dumps(
                    {
                        "mode": result["mode"],
                        "invalid_path_count": plan["invalid_path_count"],
                        "repairable_count": len(plan["repairable"]),
                        "blocked_count": len(plan["blocked"]),
                        "before": before,
                        "after": result["after"],
                        "output_dir": str(out_dir),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
    finally:
        oracle.close()
        driver.close()


if __name__ == "__main__":
    main()
