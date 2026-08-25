from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "2026年8月真实性来源核验"
LINK_FILE = ROOT / "图谱数据库链接.txt"
BATCH_ID = "20260817_证据原文字段归一"


def parse_neo4j_link() -> tuple[str, str, str]:
    text = LINK_FILE.read_text(encoding="utf-8", errors="ignore")
    uri_match = re.search(r"bolt://[^\s\u3000，,]+", text)
    user_match = re.search(r"(?:用户名|用户|user|username)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    password_match = re.search(r"(?:密码|password)\s*[:：]\s*([^\s\u3000，,]+)", text, re.I)
    if not uri_match or not password_match:
        raise RuntimeError("未在图谱数据库链接.txt 中解析到 bolt 地址或密码")
    return uri_match.group(0), (user_match.group(1) if user_match else "neo4j"), password_match.group(1)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    uri, user, password = parse_neo4j_link()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session() as session:
            updated = session.run(
                """
                MATCH (e:Evidence)
                WHERE (e.evidence_text IS NULL OR trim(toString(e.evidence_text)) = '')
                  AND e.text_excerpt IS NOT NULL AND trim(toString(e.text_excerpt)) <> ''
                SET e.evidence_text = e.text_excerpt,
                    e.evidence_text_source_field = 'text_excerpt',
                    e.evidence_normalized_batch = $batch_id,
                    e.evidence_normalized_time = $now
                RETURN count(e) AS c
                """,
                batch_id=BATCH_ID,
                now=now,
            ).single()["c"]

    result = {"batch_id": BATCH_ID, "time": now, "database": uri, "updated_evidence_nodes": updated}
    path = OUT_DIR / "证据原文字段归一_执行结果_20260817.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
