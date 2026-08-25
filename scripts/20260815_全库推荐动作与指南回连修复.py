from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
LINK_FILE = ROOT / "图谱数据库链接.txt"
RUN_ID = "GLOBAL-ALL-DISEASE-CDSS-LINK-FIX-20260815-02"


def parse_neo4j_link() -> tuple[str, str, str]:
    text = LINK_FILE.read_text(encoding="utf-8", errors="ignore")
    uri_match = re.search(r"bolt://[^\s\u3000，,]+", text)
    user_match = re.search(r"(?:用户名|用户|user|username)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    password_match = re.search(r"(?:密码|password)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    if not uri_match or not password_match:
        raise RuntimeError("未在图谱数据库链接.txt 中解析到 bolt 地址或密码")
    return uri_match.group(0), (user_match.group(1) if user_match else "neo4j"), password_match.group(1)


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value)
    for sep in ["；", "|", "、", "\n"]:
        text = text.replace(sep, ",")
    return [x.strip() for x in text.split(",") if x.strip()]


def main() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = {
        "run_id": RUN_ID,
        "recommendations_checked": 0,
        "action_links": 0,
        "guideline_links": 0,
        "missing_action_codes": [],
        "missing_guideline_names": [],
        "blocked_remaining": 0,
    }

    uri, user, password = parse_neo4j_link()
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session() as session:
            rows = [
                dict(record)
                for record in session.run(
                    """
                    MATCH (rs:RecommendationStatement)
                    WHERE coalesce(rs.hidden_from_cdss,false)<>true
                      AND coalesce(rs.status,'active') <> 'deprecated'
                      AND (
                        NOT (rs)-[:recommends_action]->()
                        OR NOT (rs)-[:uses_primary_guideline]->(:Guideline)
                      )
                    RETURN id(rs) AS rid,
                           coalesce(rs.code,rs.id) AS code,
                           rs.recommended_action_codes AS action_codes,
                           rs.guideline_names AS guideline_names,
                           rs.primary_source_name AS primary_source_name
                    """
                )
            ]

            for row in rows:
                summary["recommendations_checked"] += 1

                for action_code in as_list(row.get("action_codes")):
                    linked = session.run(
                        """
                        MATCH (rs:RecommendationStatement)
                        WHERE id(rs)=$rid
                        MATCH (a:KGNode {code:$action_code})
                        WHERE coalesce(a.hidden_from_cdss,false)<>true
                          AND coalesce(a.status,'active') <> 'deprecated'
                        MERGE (rs)-[rel:recommends_action]->(a)
                        ON CREATE SET rel.created_at=$now,
                                      rel.created_by='codex',
                                      rel.batch_id=$run_id
                        SET rel.relation_use='formal_cdss_action',
                            rel.link_basis='RecommendationStatement.recommended_action_codes',
                            rel.updated_at=$now,
                            rs.action_link_status='linked_by_recommended_action_codes',
                            rs.last_fix_run_id=$run_id,
                            rs.updated_at=$now
                        RETURN count(rel) AS n
                        """,
                        rid=row["rid"],
                        action_code=action_code,
                        now=now,
                        run_id=RUN_ID,
                    ).single()["n"]
                    if linked:
                        summary["action_links"] += linked
                    else:
                        summary["missing_action_codes"].append(
                            {"recommendation": row["code"], "action_code": action_code}
                        )

                guideline_names = as_list(row.get("guideline_names"))
                primary_source = row.get("primary_source_name")
                if primary_source and primary_source not in guideline_names:
                    guideline_names.insert(0, primary_source)

                guideline_linked = False
                for guideline_name in guideline_names:
                    linked = session.run(
                        """
                        MATCH (rs:RecommendationStatement)
                        WHERE id(rs)=$rid
                        MATCH (g:Guideline)
                        WHERE coalesce(g.name,'')=$guideline_name
                           OR coalesce(g.display_name,'')=$guideline_name
                           OR coalesce(g.file_name,'')=$guideline_name
                           OR coalesce(g.source_name,'')=$guideline_name
                        MERGE (rs)-[rel:uses_primary_guideline]->(g)
                        ON CREATE SET rel.created_at=$now,
                                      rel.created_by='codex',
                                      rel.batch_id=$run_id
                        SET rel.relation_use='formal_primary_guideline',
                            rel.link_basis='RecommendationStatement.guideline_names',
                            rel.updated_at=$now,
                            rs.guideline_link_status='linked_by_guideline_names',
                            rs.last_fix_run_id=$run_id,
                            rs.updated_at=$now
                        RETURN count(rel) AS n
                        """,
                        rid=row["rid"],
                        guideline_name=guideline_name,
                        now=now,
                        run_id=RUN_ID,
                    ).single()["n"]
                    if linked:
                        summary["guideline_links"] += linked
                        guideline_linked = True
                        break

                if guideline_names and not guideline_linked:
                    summary["missing_guideline_names"].append(
                        {"recommendation": row["code"], "guideline_names": guideline_names}
                    )

            blocked = session.run(
                """
                MATCH (rs:RecommendationStatement)
                WHERE coalesce(rs.hidden_from_cdss,false)<>true
                  AND coalesce(rs.status,'active') <> 'deprecated'
                  AND (
                    NOT (rs)-[:recommends_action]->()
                    OR NOT (rs)-[:uses_primary_guideline]->(:Guideline)
                  )
                SET rs.formal_cdss_ready=false,
                    rs.cdss_use_status='blocked_missing_action_or_primary_guideline',
                    rs.formal_block_reason='缺少可命中的推荐动作实体或主依据指南，不能进入正式CDSS推荐区',
                    rs.last_fix_run_id=$run_id,
                    rs.updated_at=$now
                RETURN count(rs) AS n
                """,
                now=now,
                run_id=RUN_ID,
            ).single()["n"]
            summary["blocked_remaining"] = blocked

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
