from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "公共执行层_kg_pipeline" / "AMI与心肌病样板收口.py"
spec = importlib.util.spec_from_file_location("sample_closure", MODULE)
assert spec and spec.loader
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)

config = closure.read_connection_file(ROOT / "图谱数据库链接.txt")
query = """
MATCH (n)
WHERE (n:LabItem OR n:LabSubitem)
  AND (
    n.name CONTAINS '肌钙蛋白'
    OR n.name CONTAINS '利钠肽'
    OR n.name CONTAINS 'D-二聚体'
    OR n.name CONTAINS 'C反应蛋白'
    OR n.name CONTAINS '红细胞沉降率'
    OR n.name CONTAINS '炎症指标'
    OR n.name CONTAINS '凝血功能'
    OR n.name CONTAINS '心肌损伤标志物'
    OR n.name CONTAINS '心脏生物标志物'
  )
OPTIONAL MATCH (n)-[out]->(o)
OPTIONAL MATCH (i)-[inc:lab_item_has_subitem]->(n)
RETURN labels(n) AS labels, n.code AS code, n.name AS name,
       n.standard_dict_id AS standard_dict_id,
       n.cdss_dict_id AS cdss_dict_id, n.source_name AS source_name,
       n.status AS status,
       collect(DISTINCT {rel:type(out),code:o.code,name:o.name})[0..20] AS outgoing,
       collect(DISTINCT {rel:type(inc),code:i.code,name:i.name})[0..20] AS incoming
ORDER BY labels, name, code
"""

with GraphDatabase.driver(
    config["uri"], auth=(config["username"], config["password"])
) as driver:
    with driver.session() as session:
        result = [dict(record) for record in session.run(query)]

print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
