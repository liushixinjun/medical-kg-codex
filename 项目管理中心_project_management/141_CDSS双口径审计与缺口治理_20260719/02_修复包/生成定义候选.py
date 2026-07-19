from __future__ import annotations

import json
import sys
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "公共执行层_kg_pipeline"))

from CDSS双口径安全审计 import read_db_config  # noqa: E402


BASELINE = (
    ROOT
    / "项目管理中心_project_management"
    / "141_CDSS双口径审计与缺口治理_20260719"
    / "01_治理前基线"
    / "知识内容完整性明细.json"
)
OUTPUT = Path(__file__).resolve().parent / "定义候选原文.json"

QUERY = """
MATCH (e:KGNode {entityType:'Evidence'})
WHERE valueType(e.evidence_text) STARTS WITH 'STRING'
   OR valueType(e.original_text) STARTS WITH 'STRING'
WITH e,
     CASE WHEN valueType(e.evidence_text) STARTS WITH 'STRING'
          THEN e.evidence_text ELSE e.original_text END AS txt
WHERE coalesce(e.status,'') <> 'deprecated'
  AND trim(txt) <> ''
  AND (e.disease_code=$code OR txt CONTAINS $name)
WITH e, txt,
     CASE WHEN e.disease_code=$code THEN 30 ELSE 0 END
     + CASE WHEN txt STARTS WITH $name THEN 50 ELSE 0 END
     + CASE WHEN txt CONTAINS ($name+'（') OR txt CONTAINS ($name+'(')
            THEN 25 ELSE 0 END
     + CASE WHEN txt CONTAINS '是指' OR txt CONTAINS '是由'
                  OR txt CONTAINS '是一种' OR txt CONTAINS '为一种'
            THEN 20 ELSE 0 END
     + CASE WHEN coalesce(e.source_type,'')='authoritative_textbook'
                  OR coalesce(e.source_name,'') CONTAINS '内科学'
            THEN 15 ELSE 0 END AS score
RETURN e.code AS evidence_code,
       e.source_name AS source_name,
       e.source_type AS source_type,
       e.source_version AS source_version,
       e.source_page AS source_page,
       e.source_section AS source_section,
       score,
       txt AS evidence_text
ORDER BY score DESC, size(txt) ASC
LIMIT 8
"""


def main() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    gaps = baseline["疾病定义缺口"]
    config = read_db_config(ROOT / "图谱数据库链接.txt")
    result: list[dict[str, object]] = []
    with GraphDatabase.driver(
        config["uri"], auth=(config["user"], config["password"])
    ) as driver:
        for gap in gaps:
            records = driver.execute_query(
                QUERY,
                parameters_={
                    "code": gap["disease_code"],
                    "name": gap["disease_name"],
                },
            ).records
            result.append(
                {
                    **gap,
                    "candidates": [dict(record) for record in records],
                }
            )
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"已生成 {len(result)} 个疾病的定义候选：{OUTPUT}")


if __name__ == "__main__":
    main()
