from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "项目管理中心_project_management" / "135_推荐来源裁决批量推广_20260717"
BASE_SCRIPT = OUT / "执行_推荐来源裁决批量推广_20260717.py"
BLOCKED_CSV = OUT / "推荐来源裁决批量推广_阻断清单_20260717.csv"

FIX_BATCH_ID = "推荐来源裁决动作编码映射修复_20260717"
FIX_RUN_AT = "2026-07-17 23:45:00"


def load_base_module():
    spec = importlib.util.spec_from_file_location("source_adjudication_bulk", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载基础脚本: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_blocked_rows() -> List[Dict[str, str]]:
    with BLOCKED_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.DictReader(f) if "缺动作节点" in row.get("阻断原因", "")]


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def choose_match(matches: List[Dict[str, Any]], old_code: str) -> Optional[Dict[str, Any]]:
    if not matches:
        return None
    prefix_priority = []
    if old_code.startswith("MED-"):
        prefix_priority = ["Medication"]
    elif old_code.startswith("PROC-"):
        prefix_priority = ["Procedure"]
    elif old_code.startswith("PLAN-"):
        prefix_priority = ["TreatmentPlan"]
    elif old_code.startswith("RULE-"):
        prefix_priority = ["ClinicalRule"]
    for entity_type in prefix_priority:
        for item in matches:
            if item.get("entityType") == entity_type:
                return item
    return matches[0]


def canonical_code(raw_code: Any, old_code: str) -> str:
    if isinstance(raw_code, list):
        values = [str(x) for x in raw_code if str(x).strip()]
        if old_code in values:
            return old_code
        if values:
            return values[0]
        return old_code
    return str(raw_code)


def find_action(tx, name: str, old_code: str) -> List[Dict[str, Any]]:
    return tx.run(
        """
        MATCH (n:KGNode)
        WHERE n.name = $name
           OR n.display_name = $name
           OR n.preferred_name = $name
           OR $name IN coalesce(n.aliases, [])
        RETURN elementId(n) AS id,
               n.code AS code,
               n.name AS name,
               n.display_name AS display_name,
               n.preferred_name AS preferred_name,
               n.entityType AS entityType,
               n.aliases AS aliases
        """,
        name=name,
    ).data()


def fix_action_node_and_rec(tx, row: Dict[str, str]) -> Dict[str, Any]:
    old_code = row["动作编码"]
    action_name = row["动作名称"]
    rec_code = row["推荐编码"]
    matches = find_action(tx, action_name, old_code)
    action = choose_match(matches, old_code)
    if not action:
        return {
            "推荐编码": rec_code,
            "动作名称": action_name,
            "旧动作编码": old_code,
            "新动作编码": "",
            "动作实体类型": "",
            "处理结果": "未找到可匹配动作实体",
        }

    new_code = canonical_code(action["code"], old_code)
    legacy_codes: List[str] = []
    if isinstance(action["code"], list):
        legacy_codes = [str(x) for x in action["code"] if str(x).strip()]
        tx.run(
            """
            MATCH (n) WHERE elementId(n)=$id
            SET n.code = $new_code,
                n.legacy_codes = $legacy_codes,
                n.updated_at = $updated_at,
                n.updated_reason = '动作实体code列表改为标准单值，旧值保留legacy_codes',
                n.mapping_fix_batch_id = $batch_id
            """,
            id=action["id"],
            new_code=new_code,
            legacy_codes=legacy_codes,
            updated_at=FIX_RUN_AT,
            batch_id=FIX_BATCH_ID,
        )

    tx.run(
        """
        MATCH (rs:KGNode {entityType:'RecommendationStatement', code:$rec_code})
        SET rs.action_code = $new_code,
            rs.action_name = $action_name,
            rs.action_entity_type = $entity_type,
            rs.updated_at = $updated_at,
            rs.action_code_mapping_batch_id = $batch_id,
            rs.legacy_action_codes =
              CASE
                WHEN $old_code IN coalesce(rs.legacy_action_codes, []) THEN coalesce(rs.legacy_action_codes, [])
                ELSE coalesce(rs.legacy_action_codes, []) + [$old_code]
              END,
            rs.recommended_action_codes =
              CASE
                WHEN rs.recommended_action_codes IS NULL THEN rs.recommended_action_codes
                ELSE [x IN rs.recommended_action_codes | CASE WHEN x=$old_code THEN $new_code ELSE x END]
              END
        """,
        rec_code=rec_code,
        old_code=old_code,
        new_code=new_code,
        action_name=action_name,
        entity_type=action["entityType"],
        updated_at=FIX_RUN_AT,
        batch_id=FIX_BATCH_ID,
    )

    return {
        "推荐编码": rec_code,
        "动作名称": action_name,
        "旧动作编码": old_code,
        "新动作编码": new_code,
        "动作实体类型": action["entityType"],
        "处理结果": "已映射并回写推荐动作编码",
    }


def force_block_relation_if_needed(candidate: Dict[str, Any]) -> None:
    row = candidate["raw"]
    text = " ".join(
        str(x or "")
        for x in [
            row.get("rec_name"),
            row.get("rec_display_name"),
            row.get("statement_text"),
            row.get("statement_summary"),
            candidate.get("action_name"),
        ]
    )
    if "禁忌" in text or "阻断" in text or "不推荐" in text:
        candidate["action_rel"] = "blocks_action"


def run() -> Dict[str, Any]:
    base = load_base_module()
    cfg = base.read_db_config()
    blocked_rows = read_blocked_rows()
    target_rec_codes = sorted({row["推荐编码"] for row in blocked_rows})

    mapping_rows: List[Dict[str, Any]] = []
    imported_rows: List[Dict[str, Any]] = []
    still_blocked_rows: List[Dict[str, Any]] = []

    with GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"])) as driver:
        with driver.session() as session:
            for row in blocked_rows:
                mapping_rows.append(session.execute_write(fix_action_node_and_rec, row))

            all_rows = session.execute_read(base.fetch_recommendations)
            by_code = {row["rec_code"]: row for row in all_rows if row["rec_code"] in target_rec_codes}

            for rec_code in target_rec_codes:
                row = by_code.get(rec_code)
                if not row:
                    still_blocked_rows.append({"推荐编码": rec_code, "阻断原因": "推荐陈述不存在"})
                    continue
                candidate = session.execute_read(base.normalize_candidate, row)
                force_block_relation_if_needed(candidate)
                if candidate["missing"]:
                    still_blocked_rows.append(
                        {
                            "大类": candidate["category"],
                            "推荐编码": rec_code,
                            "推荐名称": base.first_nonempty(row.get("rec_display_name"), row.get("rec_name")),
                            "动作编码": candidate["action_code"],
                            "动作名称": candidate["action_name"],
                            "阻断原因": "；".join(candidate["missing"]),
                        }
                    )
                    continue
                result = session.execute_write(base.import_candidate, candidate)
                imported_rows.append(
                    {
                        "大类": result["category"],
                        "推荐编码": result["rec_code"],
                        "推荐来源裁决编码": result["adj_code"],
                        "关系数": result["rel_count"],
                    }
                )

            verify = session.run(
                """
                MATCH (adj:KGNode {entityType:'SourceAdjudication', batch_id:$batch})
                RETURN count(adj) AS total,
                       sum(CASE WHEN adj.primary_evidence_code IS NULL OR trim(toString(adj.primary_evidence_code))='' THEN 1 ELSE 0 END) AS missing_primary_evidence,
                       sum(CASE WHEN adj.primary_guideline_code IS NULL OR trim(toString(adj.primary_guideline_code))='' THEN 1 ELSE 0 END) AS missing_primary_guideline,
                       sum(CASE WHEN adj.recommendation_class IS NULL OR trim(toString(adj.recommendation_class))='' THEN 1 ELSE 0 END) AS missing_recommendation_class,
                       sum(CASE WHEN adj.evidence_level IS NULL OR trim(toString(adj.evidence_level))='' THEN 1 ELSE 0 END) AS missing_evidence_level,
                       sum(CASE WHEN adj.action_code IS NULL OR trim(toString(adj.action_code))='' THEN 1 ELSE 0 END) AS missing_action_code,
                       sum(CASE WHEN coalesce(adj.formal_cdss_ready,false)<>true THEN 1 ELSE 0 END) AS non_formal
                """,
                batch=base.BATCH_ID,
            ).single().data()

    write_csv(OUT / "动作编码映射修复清单_20260717.csv", mapping_rows)
    write_csv(OUT / "推荐来源裁决补入库清单_20260717.csv", imported_rows)
    write_csv(OUT / "推荐来源裁决补入库后仍阻断清单_20260717.csv", still_blocked_rows)

    result = {
        "fix_batch_id": FIX_BATCH_ID,
        "source_adjudication_batch_id": base.BATCH_ID,
        "blocked_with_missing_action": len(blocked_rows),
        "mapping_fixed": sum(1 for row in mapping_rows if row["处理结果"].startswith("已映射")),
        "supplement_imported": len(imported_rows),
        "still_blocked": len(still_blocked_rows),
        "verify": verify,
    }
    (OUT / "动作编码修复与补入库结果_20260717.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()
