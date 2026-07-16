from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = Path(__file__).resolve().parent
LINK_FILE = ROOT / "图谱数据库链接.txt"
CHAPTER_FILE = (
    ROOT
    / "项目管理中心_project_management"
    / "123_内科学心血管骨架V1冻结_20260716"
    / "02_章节目录完整性.csv"
)
ORIGINAL_BASELINE_FILE = OUT_DIR / "01_V1.2知识浏览层证据基线扫描.json"

TARGET_ENTITY_TYPES = ["Exam", "RiskStratification", "TreatmentPlan"]
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_text_safely(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk", "cp936"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def connect_driver():
    text = read_text_safely(LINK_FILE)
    bolt_match = re.search(r"bolt://[^\s，,;；]+", text)
    if not bolt_match:
        raise RuntimeError("图谱数据库链接文件中没有找到 bolt 地址")

    candidates: list[str] = []
    for env_name in ("NEO4J_PASSWORD", "NEO4J_PASS"):
        if os.environ.get(env_name):
            candidates.append(os.environ[env_name])

    for line in text.splitlines():
        if "@" not in line:
            continue
        if "bolt://" in line or "http://" in line or "https://" in line:
            continue
        if ":" in line:
            candidates.append(line.split(":", 1)[1].strip())
        else:
            match = re.search(r"([A-Za-z0-9._%+\-#$!]+@[A-Za-z0-9._%+\-#$!]+)", line)
            if match:
                candidates.append(match.group(1))

    unique_candidates: list[str] = []
    for item in candidates:
        if item and item not in unique_candidates:
            unique_candidates.append(item)

    last_error = None
    for password in unique_candidates:
        driver = GraphDatabase.driver(bolt_match.group(0), auth=("neo4j", password))
        try:
            driver.verify_connectivity()
            return driver
        except Exception as exc:  # noqa: BLE001
            last_error = type(exc).__name__
            driver.close()

    raise RuntimeError(f"无法连接 Neo4j，最后错误类型：{last_error}")


def run_query(session, query: str, **params):
    return [dict(record) for record in session.run(query, **params)]


def evidence_baseline(session):
    return {
        "by_type": run_query(
            session,
            """
            MATCH (n:KGNode)
            WHERE n.cdss_usage_scope = 'knowledge_browse_only'
              AND n.entityType IN $types
            OPTIONAL MATCH (n)-[:supported_by_evidence]->(e:Evidence)
            WITH n.entityType AS entity_type,
                 count(DISTINCT n) AS node_count,
                 sum(CASE WHEN e IS NULL THEN 0 ELSE 1 END) AS evidence_links,
                 collect(DISTINCT CASE WHEN e IS NULL THEN n.code END) AS raw_missing_codes
            RETURN entity_type,
                   node_count,
                   evidence_links,
                   [x IN raw_missing_codes WHERE x IS NOT NULL] AS missing_codes
            ORDER BY entity_type
            """,
            types=TARGET_ENTITY_TYPES,
        ),
        "missing": run_query(
            session,
            """
            MATCH (n:KGNode)
            WHERE n.cdss_usage_scope = 'knowledge_browse_only'
              AND n.entityType IN $types
            OPTIONAL MATCH (n)-[:supported_by_evidence]->(e:Evidence)
            WITH n, count(DISTINCT e) AS evidence_count
            WHERE evidence_count = 0
            RETURN n.code AS code,
                   n.name AS name,
                   n.entityType AS entity_type,
                   n.status AS status,
                   labels(n) AS labels
            ORDER BY entity_type, name
            """,
            types=TARGET_ENTITY_TYPES,
        ),
    }


def load_original_baseline_for_report():
    if not ORIGINAL_BASELINE_FILE.exists():
        return None
    raw = json.loads(ORIGINAL_BASELINE_FILE.read_text(encoding="utf-8"))
    results = raw.get("results", {})
    missing = []
    for group in results.get("browse_without_evidence", []):
        entity_type = group.get("type")
        for item in group.get("sample", []):
            missing.append(
                {
                    "code": item.get("code"),
                    "name": item.get("name"),
                    "entity_type": entity_type,
                    "status": item.get("status"),
                    "labels": [],
                }
            )
    return {
        "generated_at": raw.get("generated_at"),
        "by_type": results.get("knowledge_browse_by_type", []),
        "missing": missing,
        "source_file": str(ORIGINAL_BASELINE_FILE),
    }


def execute_refinement(session):
    result = {}

    result["隐藏旧CTA缩写节点"] = run_query(
        session,
        """
        MATCH (old:KGNode {code:'EXAM-CARD-3A1C9D9E3AEB'})
        OPTIONAL MATCH (target:KGNode {code:'EXAM-CARD-CF719F4B0836'})
        SET old.status = 'deprecated',
            old.cdss_usage_scope = 'deprecated_hidden',
            old.deprecated_reason = 'V1.2证据精修：CTA为旧缩写节点，已由CT血管造影/冠状动脉CT血管成像承接',
            old.duplicate_of = coalesce(target.code, 'EXAM-CARD-CF719F4B0836'),
            old.replaced_by = coalesce(target.code, 'EXAM-CARD-CF719F4B0836'),
            old.v1_2_evidence_status = 'not_required_deprecated_duplicate',
            old.v1_2_status = 'excluded_from_knowledge_browse_layer',
            old.updated_at = $now,
            old.aliases = CASE
                WHEN old.aliases IS NULL THEN ['CTA']
                WHEN NOT 'CTA' IN old.aliases THEN old.aliases + ['CTA']
                ELSE old.aliases
            END
        WITH old, target
        WHERE target IS NOT NULL
        MERGE (old)-[:deprecated_duplicate_of]->(target)
        RETURN old.code AS old_code,
               old.name AS old_name,
               old.cdss_usage_scope AS scope,
               old.status AS status,
               target.code AS target_code,
               target.name AS target_name
        """,
        now=NOW,
    )

    result["心房心肌病卒中风险管理补证据"] = run_query(
        session,
        """
        MATCH (plan:KGNode {code:'PLAN-CARD-CM-ATRIAL-AF-STROKE-RISK-MANAGEMENT'})
        MATCH (rec:KGNode {code:'REC-CDSS-CM-ATRIAL-02-01-TREAT'})-[:supported_by_evidence]->(e:Evidence)
        MERGE (plan)-[:supported_by_evidence]->(e)
        MERGE (plan)-[:has_related_recommendation]->(rec)
        SET plan.v1_2_evidence_status = 'has_evidence_via_related_recommendation',
            plan.v1_2_status = 'chapter_evidence_refined',
            plan.supporting_recommendation_code = rec.code,
            plan.supporting_recommendation_name = rec.name,
            plan.updated_at = $now
        RETURN plan.code AS plan_code,
               plan.name AS plan_name,
               rec.code AS recommendation_code,
               count(DISTINCT e) AS evidence_added_or_confirmed
        """,
        now=NOW,
    )

    result["修正误标废弃的有效检查节点"] = run_query(
        session,
        """
        MATCH (n:KGNode {code:'EXAM-CARD-D690076CB8EB'})
        OPTIONAL MATCH (n)-[:supported_by_evidence]->(e:Evidence)
        OPTIONAL MATCH (d:Disease)-[r]->(n)
        WITH n, count(DISTINCT e) AS evidence_count, count(DISTINCT r) AS relation_count
        WHERE n.name = '胸部X线'
          AND n.cdss_usage_scope = 'knowledge_browse_only'
          AND evidence_count > 0
          AND relation_count > 0
        SET n.status = CASE WHEN coalesce(n.status, '') = 'deprecated' THEN 'active' ELSE n.status END,
            n.deprecated_reason = null,
            n.v1_2_evidence_status = 'has_evidence_status_corrected',
            n.v1_2_status = 'chapter_evidence_refined',
            n.updated_at = $now
        RETURN n.code AS code,
               n.name AS name,
               n.status AS status,
               evidence_count,
               relation_count
        """,
        now=NOW,
    )

    result["知识浏览层证据状态统一标记"] = run_query(
        session,
        """
        MATCH (n:KGNode)
        WHERE n.cdss_usage_scope = 'knowledge_browse_only'
          AND n.entityType IN $types
          AND coalesce(n.status, '') <> 'deprecated'
        OPTIONAL MATCH (n)-[:supported_by_evidence]->(e:Evidence)
        WITH n, count(DISTINCT e) AS evidence_count
        SET n.v1_2_evidence_count = evidence_count,
            n.v1_2_status = 'chapter_evidence_refined',
            n.v1_2_evidence_status = CASE
                WHEN n.v1_2_evidence_status IS NOT NULL THEN n.v1_2_evidence_status
                WHEN evidence_count > 0 THEN 'has_evidence'
                ELSE 'evidence_gap_wait_guideline'
            END,
            n.updated_at = $now
        RETURN n.entityType AS entity_type,
               count(n) AS marked_nodes,
               sum(CASE WHEN evidence_count = 0 THEN 1 ELSE 0 END) AS still_missing_evidence
        ORDER BY entity_type
        """,
        types=TARGET_ENTITY_TYPES,
        now=NOW,
    )

    return result


def postcheck(session):
    return {
        "knowledge_browse_missing_evidence": run_query(
            session,
            """
            MATCH (n:KGNode)
            WHERE n.cdss_usage_scope = 'knowledge_browse_only'
              AND n.entityType IN $types
              AND coalesce(n.status, '') <> 'deprecated'
            OPTIONAL MATCH (n)-[:supported_by_evidence]->(e:Evidence)
            WITH n, count(DISTINCT e) AS evidence_count
            WHERE evidence_count = 0
            RETURN n.code AS code,
                   n.name AS name,
                   n.entityType AS entity_type,
                   n.v1_2_evidence_status AS evidence_status
            ORDER BY entity_type, name
            """,
            types=TARGET_ENTITY_TYPES,
        ),
        "v1_2_status_distribution": run_query(
            session,
            """
            MATCH (n:KGNode)
            WHERE n.entityType IN $types
              AND (n.v1_2_status IS NOT NULL OR n.v1_2_evidence_status IS NOT NULL)
            RETURN n.entityType AS entity_type,
                   n.v1_2_status AS v1_2_status,
                   n.v1_2_evidence_status AS evidence_status,
                   count(*) AS count
            ORDER BY entity_type, evidence_status, v1_2_status
            """,
            types=TARGET_ENTITY_TYPES,
        ),
        "knowledge_browse_counts": run_query(
            session,
            """
            MATCH (n:KGNode)
            WHERE n.entityType IN $types
            RETURN n.entityType AS entity_type,
                   n.cdss_usage_scope AS scope,
                   coalesce(n.status, '') AS status,
                   count(*) AS count
            ORDER BY entity_type, scope, status
            """,
            types=TARGET_ENTITY_TYPES,
        ),
    }


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_chapter_matrix(path: Path, baseline_after):
    evidence_status = "通过"
    missing = baseline_after["missing"]
    if missing:
        evidence_status = f"仍有{len(missing)}个知识浏览节点缺证据"

    rows = []
    if CHAPTER_FILE.exists():
        with CHAPTER_FILE.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(
                    {
                        "层级": row.get("层级", ""),
                        "标题": row.get("标题", ""),
                        "路径": row.get("路径", ""),
                        "可用槽位": row.get("可用槽位", ""),
                        "V1冻结匹配状态": row.get("服务器匹配状态", ""),
                        "V1.2证据精修状态": evidence_status,
                        "说明": "V1.2按知识浏览层实体复测证据链；正式CDSS推荐仍以正式推荐节点和规则链为准",
                    }
                )

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "层级",
                "标题",
                "路径",
                "可用槽位",
                "V1冻结匹配状态",
                "V1.2证据精修状态",
                "说明",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, before, actions, after):
    missing_before = before["missing"]
    missing_after = after["knowledge_browse_missing_evidence"]
    browse_counts = after["knowledge_browse_counts"]
    status_dist = after["v1_2_status_distribution"]

    lines = [
        "# 《内科学》第10版心血管内科骨架 V1.2 章节级证据精修与指南补强报告",
        "",
        f"- 生成时间：{NOW}",
        "- 执行范围：知识浏览层的检查、风险分层、治疗方案三类节点。",
        "- 边界说明：本次是证据精修，不把知识浏览节点升级为正式 CDSS 推荐；正式推荐仍必须走“推荐陈述 → 推荐动作 → 证据”。",
        "",
        "## 1. 基线问题",
        "",
        f"- V1.2 前缺证据节点数：{len(missing_before)}",
    ]
    for item in missing_before:
        lines.append(f"  - {item['entity_type']}：{item['name']}（{item['code']}，状态：{item.get('status') or '空'}）")

    lines += [
        "",
        "## 2. 本次处理",
        "",
        "- CTA：确认为已废弃旧缩写节点，退出知识浏览层，保留别名追溯，指向标准节点“CT血管造影”。",
        "- 房性心律失常与卒中风险管理：补挂心房心肌病相关推荐陈述的 3 条指南证据。",
        "- 胸部X线：发现有效检查节点被误标为废弃，因其有疾病关系和证据链，已改回有效状态。",
        "- 其余知识浏览节点：统一写入 V1.2 证据状态和证据数量，后续复测可直接按字段统计。",
        "",
        "## 3. 写库动作结果",
        "",
        "```json",
        json.dumps(actions, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 4. 入库后复测",
        "",
        f"- 知识浏览层缺证据节点数：{len(missing_after)}",
    ]
    if missing_after:
        for item in missing_after:
            lines.append(f"  - {item['entity_type']}：{item['name']}（{item['code']}）")
    else:
        lines.append("  - 无")

    lines += [
        "",
        "### 4.1 知识浏览层节点分布",
        "",
        "| 实体类型 | 使用范围 | 状态 | 数量 |",
        "|---|---|---|---:|",
    ]
    for row in browse_counts:
        lines.append(
            f"| {row.get('entity_type') or ''} | {row.get('scope') or ''} | {row.get('status') or ''} | {row.get('count') or 0} |"
        )

    lines += [
        "",
        "### 4.2 V1.2证据状态分布",
        "",
        "| 实体类型 | V1.2状态 | 证据状态 | 数量 |",
        "|---|---|---|---:|",
    ]
    for row in status_dist:
        lines.append(
            f"| {row.get('entity_type') or ''} | {row.get('v1_2_status') or ''} | {row.get('evidence_status') or ''} | {row.get('count') or 0} |"
        )

    lines += [
        "",
        "## 5. 结论",
        "",
        "- V1.2 的目标是让教材骨架中的知识浏览层具备可追溯证据，不替代正式 CDSS 推荐资格审查。",
        "- 前端展示时，知识浏览区可展示这些节点；正式推荐区不得直接使用 knowledge_browse_only 节点。",
        "- 后续指南补强应继续围绕正式推荐链路补充：适用场景、触发条件、推荐动作、禁忌/排除、证据。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    driver = connect_driver()
    try:
        with driver.session() as session:
            before_current = evidence_baseline(session)
            actions = execute_refinement(session)
            after = postcheck(session)
    finally:
        driver.close()

    before_for_report = load_original_baseline_for_report() or before_current

    write_json(
        OUT_DIR / "02_V1.2章节级证据精修执行结果.json",
        {
            "original_baseline_used_for_report": before_for_report,
            "current_before_rerun_state": before_current,
            "actions": actions,
        },
    )
    write_json(OUT_DIR / "03_V1.2章节级证据精修复测_summary.json", after)
    write_chapter_matrix(OUT_DIR / "04_章节顺序V1.2证据精修覆盖矩阵.csv", {"missing": after["knowledge_browse_missing_evidence"]})
    write_report(OUT_DIR / "00_内科学心血管骨架V1.2章节级证据精修与指南补强报告_20260716.md", before_for_report, actions, after)

    print(
        json.dumps(
            {
                "original_baseline_missing": len(before_for_report["missing"]),
                "current_before_missing": len(before_current["missing"]),
                "after_missing": len(after["knowledge_browse_missing_evidence"]),
                "report": str(OUT_DIR / "00_内科学心血管骨架V1.2章节级证据精修与指南补强报告_20260716.md"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
