from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
P5_PATH = ROOT / "公共执行层_kg_pipeline" / "P5样板终验.py"
DEFAULT_OUT = ROOT / "项目管理中心_project_management" / "2026年8月P6已解析大类终验" / "02_确定性收口修复_20260803"


def load_p5():
    spec = importlib.util.spec_from_file_location("p5_sample_gate", P5_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载P5脚本: {P5_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def json_default(value: Any) -> str:
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def strip_section_prefix(name: str) -> str:
    text = (name or "").strip()
    text = re.sub(r"^第[一二三四五六七八九十百千万0-9]+[章节]\s*", "", text)
    text = re.sub(r"^[一二三四五六七八九十百千万0-9]+[、.．]\s*", "", text)
    return text.strip()


COMPOSITE_SIGNS = {
    "SIGN-CARD-PAD-PULSE-WOUND-GANGRENE": [
        {
            "code": "SIGN-CARD-PAD-LOWER-LIMB-PULSE-ABNORMAL",
            "name": "下肢脉搏异常",
            "description": "由组合体征“下肢脉搏异常、伤口不愈合或坏疽”拆分。",
        },
        {
            "code": "SIGN-CARD-PAD-WOUND-NONHEALING",
            "name": "伤口不愈合",
            "description": "由组合体征“下肢脉搏异常、伤口不愈合或坏疽”拆分。",
        },
        {
            "code": "SIGN-CARD-PAD-GANGRENE",
            "name": "坏疽",
            "description": "由组合体征“下肢脉搏异常、伤口不愈合或坏疽”拆分。",
        },
    ],
    "SIGN-CARD-AAS-PULSE-BP-DIFFERENTIAL": [
        {
            "code": "SIGN-CARD-AAS-PULSE-DEFICIT",
            "name": "脉搏缺失",
            "description": "由组合体征“脉搏缺失或双上肢收缩压差”拆分。",
        },
        {
            "code": "SIGN-CARD-AAS-BILATERAL-ARM-SBP-DIFFERENCE",
            "name": "双上肢收缩压差",
            "description": "由组合体征“脉搏缺失或双上肢收缩压差”拆分。",
        },
    ],
}


def collect_plans(session) -> dict[str, Any]:
    old_path_rows = [dict(r) for r in session.run(
        """
        MATCH (d:KGNode {entityType:'Disease'})-[:has_exam_plan]->(p:KGNode {entityType:'ExamPlan'})
          -[r:includes_lab_item]->(sub:KGNode {entityType:'LabSubitem'})
        WHERE coalesce(r.status,'') <> 'deprecated'
        OPTIONAL MATCH (li:KGNode {entityType:'LabItem'})-[:lab_item_has_subitem]->(sub)
        WITH d,p,r,sub,collect(DISTINCT li) AS parents
        RETURN elementId(r) AS rel_eid,
               d.code AS disease_code,d.name AS disease_name,
               p.code AS plan_code,p.name AS plan_name,
               sub.code AS subitem_code,sub.name AS subitem_name,
               [x IN parents WHERE x IS NOT NULL | {code:x.code,name:x.name}] AS parent_lab_items,
               properties(r) AS rel_props
        ORDER BY disease_name, plan_name, subitem_name
        """
    )]

    definition_rows = []
    for r in session.run(
        """
        MATCH (n:KGNode {entityType:'Definition'})
        WHERE coalesce(n.status,'') <> 'deprecated'
          AND (n.name STARTS WITH '第' OR n.name =~ '^[一二三四五六七八九十百千万0-9]+[、.．].*')
        OPTIONAL MATCH (d:KGNode {entityType:'Disease'})-[*1..2]->(n)
        RETURN n.code AS node_code,n.name AS old_name,collect(DISTINCT d.name) AS diseases
        ORDER BY old_name
        """
    ):
        row = dict(r)
        new_name = strip_section_prefix(row["old_name"])
        if new_name and new_name != row["old_name"]:
            row["new_name"] = new_name
            definition_rows.append(row)

    composite_rows = [dict(r) for r in session.run(
        """
        MATCH (old:KGNode {entityType:'Sign'})
        WHERE old.code IN $codes AND coalesce(old.status,'') <> 'deprecated'
        OPTIONAL MATCH (d:KGNode {entityType:'Disease'})-[dr]->(old)
        OPTIONAL MATCH (old)-[er:supported_by_evidence|derived_from]->(ev:KGNode {entityType:'Evidence'})
        RETURN old.code AS old_code,old.name AS old_name,properties(old) AS old_props,
               collect(DISTINCT {code:d.code,name:d.name,rel_type:type(dr),rel_props:properties(dr)}) AS disease_links,
               collect(DISTINCT {code:ev.code,name:ev.name,rel_type:type(er),rel_props:properties(er)}) AS evidence_links
        ORDER BY old.name
        """,
        codes=list(COMPOSITE_SIGNS.keys()),
    )]

    return {
        "old_paths": old_path_rows,
        "definition_renames": definition_rows,
        "composite_signs": composite_rows,
    }


def write_plan_files(out_dir: Path, plan: dict[str, Any]) -> None:
    migratable = []
    blocked = []
    for row in plan["old_paths"]:
        target = migratable if row["parent_lab_items"] else blocked
        target.append(row)
    write_csv(
        out_dir / "01_旧路径可迁移清单.csv",
        migratable,
        ["rel_eid", "disease_code", "disease_name", "plan_code", "plan_name", "subitem_code", "subitem_name", "parent_lab_items"],
    )
    write_csv(
        out_dir / "02_旧路径暂不自动迁移清单.csv",
        blocked,
        ["rel_eid", "disease_code", "disease_name", "plan_code", "plan_name", "subitem_code", "subitem_name", "parent_lab_items"],
    )
    write_csv(
        out_dir / "03_定义标题前缀修复清单.csv",
        plan["definition_renames"],
        ["node_code", "old_name", "new_name", "diseases"],
    )
    sign_rows: list[dict[str, Any]] = []
    for row in plan["composite_signs"]:
        for child in COMPOSITE_SIGNS.get(row["old_code"], []):
            sign_rows.append({
                "old_code": row["old_code"],
                "old_name": row["old_name"],
                "new_code": child["code"],
                "new_name": child["name"],
                "linked_diseases": row["disease_links"],
            })
    write_csv(
        out_dir / "04_组合体征拆分清单.csv",
        sign_rows,
        ["old_code", "old_name", "new_code", "new_name", "linked_diseases"],
    )
    write_json(out_dir / "05_写库前回滚快照.json", plan)


def apply_repairs(session, plan: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "executed_at": now_text(),
        "old_path_rel_deleted": 0,
        "old_path_plan_to_labitem_created_or_matched": 0,
        "old_path_blocked_no_parent": 0,
        "definition_renamed": 0,
        "composite_sign_created_or_matched": 0,
        "composite_sign_deleted": 0,
    }

    # 1. 旧路径：只迁移已有父检验项目的细项。
    for row in plan["old_paths"]:
        if not row["parent_lab_items"]:
            result["old_path_blocked_no_parent"] += 1
            continue
        counters = session.run(
            """
            MATCH (p:KGNode {code:$plan_code})-[r:includes_lab_item]->(sub:KGNode {code:$subitem_code})
            WHERE elementId(r)=$rel_eid
            MATCH (li:KGNode {entityType:'LabItem'})-[:lab_item_has_subitem]->(sub)
            MERGE (p)-[nr:includes_lab_item]->(li)
            ON CREATE SET nr.created_at=$ts,
                          nr.created_by='P6确定性收口修复',
                          nr.source='P6旧路径迁移',
                          nr.migration_reason='ExamPlan不能直接连接LabSubitem，需经LabItem中转'
            SET nr.updated_at=$ts,
                nr.migrated_from_relation=coalesce(nr.migrated_from_relation, []) + [$rel_eid],
                nr.formal_cdss_ready=coalesce(nr.formal_cdss_ready, false)
            WITH r, count(DISTINCT nr) AS linked_count
            DELETE r
            RETURN linked_count
            """,
            plan_code=row["plan_code"],
            subitem_code=row["subitem_code"],
            rel_eid=row["rel_eid"],
            ts=now_text(),
        ).single()
        linked_count = counters["linked_count"] if counters else 0
        result["old_path_plan_to_labitem_created_or_matched"] += linked_count
        result["old_path_rel_deleted"] += 1

    # 2. 定义节点只去掉章节编号前缀。
    for row in plan["definition_renames"]:
        session.run(
            """
            MATCH (n:KGNode {code:$code, entityType:'Definition'})
            SET n.name=$new_name,
                n.display_name=$new_name,
                n.updated_at=$ts,
                n.name_cleanup_reason='P6去除教材章节编号前缀'
            """,
            code=row["node_code"],
            new_name=row["new_name"],
            ts=now_text(),
        )
        result["definition_renamed"] += 1

    # 3. 组合体征拆分成单项体征；复制疾病关系和证据关系后物理删除组合节点。
    for row in plan["composite_signs"]:
        old_code = row["old_code"]
        components = COMPOSITE_SIGNS.get(old_code, [])
        for child in components:
            session.run(
                """
                MERGE (new:KGNode {code:$code})
                ON CREATE SET new.created_at=$ts, new.created_by='P6确定性收口修复'
                SET new.entityType='Sign',
                    new.name=$name,
                    new.display_name=$name,
                    new.preferred_name=$name,
                    new.description=$description,
                    new.source='P6组合体征拆分',
                    new.status='active',
                    new.updated_at=$ts
                """,
                code=child["code"],
                name=child["name"],
                description=child["description"],
                ts=now_text(),
            )
            session.run(
                """
                MATCH (old:KGNode {code:$old_code, entityType:'Sign'})
                MATCH (new:KGNode {code:$new_code, entityType:'Sign'})
                OPTIONAL MATCH (d:KGNode {entityType:'Disease'})-[dr]->(old)
                WHERE d IS NOT NULL AND type(dr) <> 'supported_by_evidence'
                CALL {
                  WITH d, dr, new
                  WITH d, dr, new WHERE d IS NOT NULL
                  MERGE (d)-[nr:has_sign]->(new)
                  ON CREATE SET nr.created_at=$ts, nr.created_by='P6确定性收口修复'
                  SET nr.source='P6组合体征拆分',
                      nr.migrated_from_relation_type=type(dr),
                      nr.updated_at=$ts
                  RETURN count(nr) AS c
                }
                RETURN sum(c) AS created_count
                """,
                old_code=old_code,
                new_code=child["code"],
                ts=now_text(),
            )
            session.run(
                """
                MATCH (old:KGNode {code:$old_code, entityType:'Sign'})
                MATCH (new:KGNode {code:$new_code, entityType:'Sign'})
                OPTIONAL MATCH (old)-[er:supported_by_evidence|derived_from]->(ev:KGNode {entityType:'Evidence'})
                WITH new, er, ev WHERE ev IS NOT NULL
                MERGE (new)-[nr:supported_by_evidence]->(ev)
                ON CREATE SET nr.created_at=$ts, nr.created_by='P6确定性收口修复'
                SET nr.source='P6组合体征拆分',
                    nr.migrated_from_relation_type=type(er),
                    nr.updated_at=$ts
                """,
                old_code=old_code,
                new_code=child["code"],
                ts=now_text(),
            )
            result["composite_sign_created_or_matched"] += 1

        deleted = session.run(
            """
            MATCH (old:KGNode {code:$old_code, entityType:'Sign'})
            DETACH DELETE old
            RETURN 1 AS deleted
            """,
            old_code=old_code,
        ).single()
        if deleted:
            result["composite_sign_deleted"] += 1

    return result


def verify(session) -> dict[str, Any]:
    data = {}
    data["direct_examplan_to_labsubitem"] = session.run(
        """
        MATCH (:KGNode {entityType:'Disease'})-[:has_exam_plan]->(:KGNode {entityType:'ExamPlan'})
          -[r:includes_lab_item]->(:KGNode {entityType:'LabSubitem'})
        WHERE coalesce(r.status,'') <> 'deprecated'
        RETURN count(r) AS n
        """
    ).single()["n"]
    data["section_prefix_definition"] = session.run(
        """
        MATCH (n:KGNode {entityType:'Definition'})
        WHERE coalesce(n.status,'') <> 'deprecated'
          AND (n.name STARTS WITH '第' OR n.name =~ '^[一二三四五六七八九十百千万0-9]+[、.．].*')
        RETURN count(n) AS n
        """
    ).single()["n"]
    data["known_composite_sign_remaining"] = session.run(
        """
        MATCH (n:KGNode {entityType:'Sign'})
        WHERE n.code IN $codes
        RETURN count(n) AS n
        """,
        codes=list(COMPOSITE_SIGNS.keys()),
    ).single()["n"]
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="P6已解析大类确定性收口修复")
    parser.add_argument("--write", action="store_true", help="执行写库；不加则只生成计划。")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT), help="输出目录。")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    p5 = load_p5()
    cfg = p5.read_db_config(ROOT / "图谱数据库链接.txt")
    driver = p5.GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))
    try:
        with driver.session() as session:
            plan = collect_plans(session)
            write_plan_files(out_dir, plan)
            before = verify(session)
            result = {"mode": "dry_run", "before": before, "after": before}
            if args.write:
                write_result = apply_repairs(session, plan)
                after = verify(session)
                result = {"mode": "write", "before": before, "write_result": write_result, "after": after}
            write_json(out_dir / "06_执行结果.json", result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
