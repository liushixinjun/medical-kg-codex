from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "2026年8月真实性来源核验"
LINK_FILE = ROOT / "图谱数据库链接.txt"
TARGET_BATCH = "20260817_全库关系证据安全回填"
BATCH_SIZE = 100


def parse_link() -> tuple[str, str, str]:
    text = LINK_FILE.read_text(encoding="utf-8", errors="ignore")
    uri_match = re.search(r"bolt://[^\s\u3000，,]+", text)
    if not uri_match:
        raise RuntimeError("未解析到 Neo4j bolt 地址")
    user_match = re.search(r"(?:用户名|用户|user|username)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    pwd_match = re.search(r"(?:密码|password)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    if not pwd_match:
        raise RuntimeError("未在图谱数据库链接.txt 中解析到密码")
    return uri_match.group(0), (user_match.group(1) if user_match else "neo4j"), pwd_match.group(1)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    uri, user, password = parse_link()
    summary = {
        "rollback_batch": "20260817_不安全关系证据回填_分批回滚",
        "target_batch": TARGET_BATCH,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "database": uri,
        "matched_before": None,
        "rolled_back": 0,
        "matched_after": None,
        "batch_size": BATCH_SIZE,
        "reason": "通用项目证据不能直接继承为疾病关系证据，避免跨疾病证据污染",
    }
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session() as session:
            summary["matched_before"] = session.run(
                "MATCH ()-[r]->() WHERE r.provenance_fix_batch = $target RETURN count(r) AS c",
                target=TARGET_BATCH,
            ).single()["c"]
            while True:
                count = session.run(
                    """
                    MATCH ()-[r]->()
                    WHERE r.provenance_fix_batch = $target
                    WITH r LIMIT $limit
                    REMOVE r.evidence_id,
                           r.evidence_ids,
                           r.source_name,
                           r.source_names,
                           r.evidence_text,
                           r.provenance_inherited_from,
                           r.provenance_fix_batch,
                           r.provenance_fix_time
                    RETURN count(r) AS c
                    """,
                    target=TARGET_BATCH,
                    limit=BATCH_SIZE,
                ).single()["c"]
                summary["rolled_back"] += count
                if count == 0:
                    break
            summary["matched_after"] = session.run(
                "MATCH ()-[r]->() WHERE r.provenance_fix_batch = $target RETURN count(r) AS c",
                target=TARGET_BATCH,
            ).single()["c"]

    out = OUT_DIR / "不安全关系证据回填_分批回滚结果_20260817.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
