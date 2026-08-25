from __future__ import annotations

import json

from neo4j import GraphDatabase


URI = "bolt://192.168.3.27:7687"
AUTH = ("neo4j", "zysoft@2024")
TERMS = [
    "超声心动图",
    "磁共振",
    "心电图",
    "肌钙蛋白",
    "基因检测",
    "冠状动脉造影",
    "重症监护",
    "机械循环",
    "心脏磁共振",
]

QUERY = """
MATCH (n:KGNode)
WHERE any(t IN $terms WHERE coalesce(n.name,'') CONTAINS t OR coalesce(n.display_name,'') CONTAINS t)
RETURN labels(n) AS labels,
       n.entityType AS entityType,
       n.name AS name,
       n.code AS code,
       n.dictionary_validation_status AS dictionary_validation_status,
       n.cdss_use_status AS cdss_use_status
LIMIT 100
"""


def main() -> None:
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        with driver.session() as session:
            for row in session.run(QUERY, terms=TERMS):
                print(json.dumps(dict(row), ensure_ascii=False))


if __name__ == "__main__":
    main()
