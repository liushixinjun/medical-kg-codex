from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient  # noqa: E402


OUTPUT_DIR = ROOT / "心血管内科文献集合" / "20260714_冠心病大类交付验收"
ISSUE_FILE = OUTPUT_DIR / "04_质量问题明细.json"


KEYWORDS_BY_RECOMMENDATION = {
    "氧疗": ["氧疗", "吸氧", "血氧", "氧饱和度", "SpO2", "SaO2", "呼吸困难"],
    "血运重建": ["血运重建", "再灌注", "PCI", "介入治疗", "冠状动脉介入", "CABG", "旁路移植", "开通闭塞"],
    "降压治疗": ["降压", "血压", "高血压", "收缩压", "舒张压"],
    "控制心室率": ["控制心室率", "心室率", "心率控制", "房颤", "心房颤动"],
}


BLOCKED_PAIRS = {
    ("DIS-CARD-CAD-AMI", "降压治疗"): "候选证据主要来自脑出血、糖尿病高血压或溶栓禁忌筛查，不是AMI降压治疗的直接推荐证据",
    ("DIS-CARD-CAD-ATHEROSCLEROSIS", "降压治疗"): "候选证据主要来自高血压章节，属于危险因素管理，不适合作为动脉粥样硬化治疗方案的直接CDSS推荐",
    ("DIS-CARD-CAD-CHD", "控制心室率"): "候选证据主要来自房颤或瓣膜病场景，控制心室率不应作为冠心病本病种通用治疗方案直接推荐",
    ("DIS-CARD-CAD-CHD", "降压治疗"): "候选证据属于高血压风险管理，应归入危险因素/预防场景，不作为冠心病治疗方案直接推荐",
    ("DIS-CARD-CAD-ICM", "降压治疗"): "候选证据来自稳定型心绞痛或高血压管理，缺少缺血性心肌病本病种直接治疗证据",
}


PREFERRED_SNIPPETS = {
    ("DIS-CARD-CAD-ACS", "血运重建"): ["NSTE⁃ACS患者冠状动脉造影和血运重建策略推荐意见", "急性冠脉综合征"],
    ("DIS-CARD-CAD-AMI", "血运重建"): ["急性冠脉综合征", "冠状动脉旁路移植术"],
    ("DIS-CARD-CAD-STEMI", "血运重建"): ["STEMI 时", "急诊PCI"],
    ("DIS-CARD-CAD-NSTEMI", "血运重建"): ["UA/NSTEMI 病人血运重建", "NSTE-ACS"],
    ("DIS-CARD-CAD-ATHEROSCLEROSIS", "血运重建"): ["对于狭窄或闭塞血管", "介入和外科手术"],
    ("DIS-CARD-CAD-CHD", "血运重建"): ["血运重建治疗", "对狭窄或阻塞的冠状动脉进行血运"],
    ("DIS-CARD-CAD-STABLE-ANGINA", "降压治疗"): ["ABCDE 方案"],
    ("DIS-CARD-CAD-ICM", "血运重建"): ["缺血性心肌病患者", "首选CABG"],
}


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    http = re.search(r"https?://[^\s，,；;]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    if not http:
        raise RuntimeError(f"连接文件缺少 HTTP 地址：{path}")
    if not password:
        raise RuntimeError(f"连接文件缺少密码字段：{path}")
    return {
        "uri": http.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def result_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    columns = result["results"][0]["columns"]
    return [
        {column: item["row"][index] for index, column in enumerate(columns)}
        for item in result["results"][0]["data"]
    ]


def query(client: Neo4jHttpClient, statement: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return result_rows(client.run(statement, params or {}))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_missing_recommendations() -> list[dict[str, Any]]:
    data = json.loads(ISSUE_FILE.read_text(encoding="utf-8"))
    return data.get("CDSS推荐节点缺证据", [])


def candidate_keywords(node_name: str) -> list[str]:
    keywords = list(KEYWORDS_BY_RECOMMENDATION.get(node_name, []))
    if node_name and node_name not in keywords:
        keywords.insert(0, node_name)
    return keywords


def fetch_candidate_evidence(client: Neo4jHttpClient, issue: dict[str, Any]) -> list[dict[str, Any]]:
    keywords = candidate_keywords(issue.get("node_name", ""))
    rows = query(
        client,
        """
        MATCH (d:KGNode {code: $disease_code})--(e:KGNode {entityType: 'Evidence'})
        WITH d, e,
             toLower(
               coalesce(toString(e.evidence_text), '') + ' ' +
               coalesce(toString(e.original_text), '') + ' ' +
               coalesce(toString(e.text), '') + ' ' +
               coalesce(toString(e.summary), '') + ' ' +
               coalesce(toString(e.name), '')
             ) AS evidence_text,
             $keywords AS keywords
        WITH d, e, evidence_text,
             [k IN keywords WHERE evidence_text CONTAINS toLower(k)] AS matched_keywords
        WHERE size(matched_keywords) > 0
        WITH d, e, matched_keywords,
             CASE WHEN evidence_text CONTAINS toLower($node_name) THEN 100 ELSE 0 END +
             CASE WHEN any(k IN ['氧疗','吸氧','血运重建','再灌注','降压','控制心室率','心室率'] WHERE evidence_text CONTAINS toLower(k)) THEN 30 ELSE 0 END +
             size(matched_keywords) * 10 AS match_score
        RETURN
          e.code AS evidence_code,
          e.name AS evidence_name,
          coalesce(e.source_document, e.source, e.guideline_name, '') AS source_name,
          coalesce(e.page, e.page_number, e.page_start, '') AS page,
          coalesce(e.recommendation_class, e.recommendation_level, '') AS recommendation_level,
          coalesce(e.evidence_level, '') AS evidence_level,
          matched_keywords AS matched_keywords,
          match_score AS match_score,
          left(coalesce(toString(e.evidence_text), toString(e.original_text), toString(e.text), toString(e.name), ''), 240) AS evidence_preview
        ORDER BY match_score DESC, evidence_code
        LIMIT 5
        """,
        {"disease_code": issue["disease_code"], "keywords": keywords, "node_name": issue.get("node_name", "")},
    )
    for row in rows:
        row.update(
            {
                "disease_code": issue["disease_code"],
                "disease_name": issue["disease_name"],
                "node_code": issue["node_code"],
                "node_name": issue["node_name"],
                "entity_type": issue["entity_type"],
                "candidate_count": len(rows),
            }
        )
    return rows


def choose_best_candidate(issue: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    pair = (issue["disease_code"], issue["node_name"])
    if pair in BLOCKED_PAIRS:
        return None, BLOCKED_PAIRS[pair]
    if not rows:
        return None, "同病种证据中未检出匹配关键词，未自动补链"

    preferred = PREFERRED_SNIPPETS.get(pair, [])
    for snippet in preferred:
        for row in rows:
            haystack = f"{row.get('evidence_name', '')} {row.get('evidence_preview', '')}"
            if snippet in haystack:
                return row, f"命中优先证据片段：{snippet}"

    node_name = issue.get("node_name", "")
    if node_name == "氧疗":
        for row in rows:
            haystack = f"{row.get('evidence_name', '')} {row.get('evidence_preview', '')}"
            if "氧疗" in haystack or "吸氧" in haystack:
                return row, "命中氧疗/吸氧直接证据"
    if node_name == "血运重建":
        for row in rows:
            text = row.get("evidence_preview", "")
            if "血运重建" in text and any(token in text for token in ["PCI", "CABG", "介入", "旁路移植", "冠脉"]):
                return row, "命中血运重建直接证据"
    if node_name == "降压治疗":
        for row in rows:
            haystack = f"{row.get('evidence_name', '')} {row.get('evidence_preview', '')}"
            if "降压治疗" in haystack and not any(bad in haystack for bad in ["脑出血", "假性难治性高血压"]):
                return row, "命中降压治疗直接证据"

    return None, "候选证据存在，但未达到同病种同动作的安全补链标准"


def apply_best_links(client: Neo4jHttpClient, best_rows: list[dict[str, Any]]) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = query(
        client,
        """
        UNWIND $rows AS row
        MATCH (n:KGNode {code: row.node_code})
        MATCH (e:KGNode {code: row.evidence_code})
        MERGE (n)-[r:supported_by_evidence]->(e)
        SET
          r.disease_code = row.disease_code,
          r.disease_name = row.disease_name,
          r.link_reason = '冠心病大类CDSS推荐节点直接证据链补齐',
          r.match_keywords = row.matched_keywords,
          r.source_batch = '20260714_冠心病大类交付验收',
          r.review_status = '规则匹配后进入临床使用效果验证',
          r.updated_at = $now
        RETURN count(r) AS linked_count
        """,
        {"rows": best_rows, "now": now},
    )
    return int(result[0]["linked_count"] or 0)


def apply_blocked_pairs(client: Neo4jHttpClient, blocked_rows: list[dict[str, Any]]) -> int:
    if not blocked_rows:
        return 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = query(
        client,
        """
        UNWIND $rows AS row
        MATCH (d:KGNode {code: row.disease_code})-[r]-(n:KGNode {code: row.node_code})
        SET
          r.formal_cdss_ready = false,
          r.quality_block_reason = row.reason,
          r.quality_block_stage = '冠心病大类交付验收',
          r.updated_at = $now
        RETURN count(r) AS blocked_count
        """,
        {"rows": blocked_rows, "now": now},
    )
    return int(result[0]["blocked_count"] or 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="补齐冠心病大类CDSS推荐节点的直接证据链")
    parser.add_argument("--apply", action="store_true", help="写入 Neo4j；不加则只生成候选表")
    args = parser.parse_args()

    conn = parse_connection_file(ROOT / "图谱数据库链接.txt")
    client = Neo4jHttpClient(conn["uri"], conn["username"], conn["password"], "neo4j")

    issues = load_missing_recommendations()
    candidates: list[dict[str, Any]] = []
    best_rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []

    for issue in issues:
        rows = fetch_candidate_evidence(client, issue)
        candidates.extend(rows)
        best, decision_reason = choose_best_candidate(issue, rows)
        if best:
            best["decision_reason"] = decision_reason
            best_rows.append(best)
        else:
            blocked_rows.append(
                {
                    "disease_code": issue["disease_code"],
                    "disease_name": issue["disease_name"],
                    "node_code": issue["node_code"],
                    "node_name": issue["node_name"],
                    "reason": decision_reason,
                }
            )
            unresolved.append(
                {
                    "disease_code": issue["disease_code"],
                    "disease_name": issue["disease_name"],
                    "node_code": issue["node_code"],
                    "node_name": issue["node_name"],
                    "reason": decision_reason,
                    "keywords": candidate_keywords(issue.get("node_name", "")),
                }
            )

    candidate_file = OUTPUT_DIR / "06_CDSS推荐节点证据候选_20260714.csv"
    write_csv(
        candidate_file,
        candidates,
        [
            "disease_code",
            "disease_name",
            "node_code",
            "node_name",
            "entity_type",
            "evidence_code",
            "evidence_name",
            "source_name",
            "page",
            "recommendation_level",
            "evidence_level",
            "matched_keywords",
            "match_score",
            "evidence_preview",
            "candidate_count",
        ],
    )

    selected_file = OUTPUT_DIR / "07_CDSS推荐节点证据正式补链清单_20260714.csv"
    write_csv(
        selected_file,
        best_rows,
        [
            "disease_code",
            "disease_name",
            "node_code",
            "node_name",
            "entity_type",
            "evidence_code",
            "evidence_name",
            "source_name",
            "page",
            "recommendation_level",
            "evidence_level",
            "matched_keywords",
            "match_score",
            "decision_reason",
            "evidence_preview",
        ],
    )

    blocked_file = OUTPUT_DIR / "08_CDSS推荐节点正式阻断清单_20260714.csv"
    write_csv(
        blocked_file,
        blocked_rows,
        ["disease_code", "disease_name", "node_code", "node_name", "reason"],
    )

    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "apply": bool(args.apply),
        "issue_count": len(issues),
        "candidate_issue_count": len(best_rows),
        "unresolved_count": len(unresolved),
        "blocked_pair_count": len(blocked_rows),
        "linked_count": 0,
        "blocked_relation_count": 0,
        "candidate_file": str(candidate_file),
        "selected_file": str(selected_file),
        "blocked_file": str(blocked_file),
        "unresolved": unresolved,
        "blocked_rows": blocked_rows,
    }
    if args.apply and best_rows:
        result["linked_count"] = apply_best_links(client, best_rows)
    if args.apply and blocked_rows:
        result["blocked_relation_count"] = apply_blocked_pairs(client, blocked_rows)

    result_file = OUTPUT_DIR / "09_CDSS推荐节点证据补链结果_20260714.json"
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
