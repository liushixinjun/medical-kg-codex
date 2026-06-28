from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient


SEMANTIC_SHELL_QUERY = """
MATCH (:KGNode {entityType:'Disease'})-[r]->(n:KGNode)
WHERE
  (n.entityType='DifferentialDiagnosis' AND n.name IN ['鉴别诊断','鉴别','除外','排除'])
  OR (n.entityType='DiagnosisCriteria' AND n.name IN ['诊断标准','诊断','确诊','诊断依据','临床诊断'])
  OR (n.entityType='TreatmentPlan' AND n.name IN ['治疗','治疗方案','治疗原则','一般治疗','药物治疗','非药物治疗'])
  OR (n.entityType='FollowUp' AND n.name IN ['随访','定期随访','随访方案','长期随访','复查'])
  OR (n.entityType='Prognosis' AND n.name IN ['预后','预后良好','预后不良','预后不佳'])
  OR (n.entityType='RiskStratification' AND n.name IN ['风险分层','危险分层','风险评估','评分','危险因素评估'])
RETURN count(r) AS bad_relations
"""


QUERIES = {
    "all_node_count": "MATCH (n) RETURN count(n) AS value",
    "all_relation_count": "MATCH ()-[r]->() RETURN count(r) AS value",
    "kg_node_count": "MATCH (n:KGNode) RETURN count(n) AS value",
    "kg_relation_count": "MATCH (:KGNode)-[r]->(:KGNode) RETURN count(r) AS value",
    "non_kgnode_node_count": """
        MATCH (n)
        WHERE NOT n:KGNode
        RETURN count(n) AS value
    """,
    "relation_touching_non_kgnode_count": """
        MATCH (a)-[r]->(b)
        WHERE NOT a:KGNode OR NOT b:KGNode
        RETURN count(r) AS value
    """,
    "top_non_kgnode_nodes": """
        MATCH (n)
        WHERE NOT n:KGNode
        OPTIONAL MATCH (a)-[rin]->(n)
        OPTIONAL MATCH (n)-[rout]->(b)
        RETURN labels(n) AS labels, n.name AS name, n.entityType AS entityType,
               n.code AS code, n.schema_version AS schema_version,
               n.source_name AS source_name,
               count(DISTINCT rin) AS in_rel_count,
               count(DISTINCT rout) AS out_rel_count
        ORDER BY in_rel_count DESC, name
        LIMIT 50
    """,
    "semantic_shell_relation_count": SEMANTIC_SHELL_QUERY,
    "diagnosis_generic_direct_relation_count": """
        MATCH (:KGNode {entityType:'Disease'})-[r:has_diagnostic_criteria]->(n:KGNode {entityType:'DiagnosisCriteria'})
        WHERE n.name IN ['诊断标准','诊断','确诊','诊断依据','临床诊断']
        RETURN count(r) AS value
    """,
    "technical_display_name_error_count": """
        MATCH (n:KGNode)
        WHERE NOT n.entityType IN ['Evidence','Guideline']
          AND (
            n.name = n.code OR n.preferred_name = n.code OR n.display_name = n.code
            OR n.name =~ '^[A-Z][A-Z0-9]+(-[A-Z0-9]+)+$'
            OR n.preferred_name =~ '^[A-Z][A-Z0-9]+(-[A-Z0-9]+)+$'
            OR n.display_name =~ '^[A-Z][A-Z0-9]+(-[A-Z0-9]+)+$'
          )
        RETURN count(n) AS value
    """,
    "treatment_plan_actionability_error_count": """
        MATCH (p:KGNode {entityType:'TreatmentPlan'})<-[:has_treatment_plan]-(:KGNode {entityType:'Disease'})
        WHERE NOT (p)-[:includes_medication|includes_procedure|has_timing|has_follow_up|has_clinical_pathway|has_indication|has_contraindication]->(:KGNode)
        RETURN count(DISTINCT p) AS value
    """,
    "medication_class_without_specific_count": """
        MATCH (m:KGNode {entityType:'Medication'})
        WHERE m.name IN [
          '抗凝药物','溶栓药物','抗血小板药物','硝酸酯类药物','醛固酮受体拮抗剂',
          'β受体阻滞剂','β受体拮抗剂','血管紧张素转换酶抑制剂','血管紧张素Ⅱ受体阻滞剂',
          '血管紧张素Ⅱ受体拮抗剂','钙通道阻滞剂','非二氢吡啶类钙通道阻滞剂',
          '他汀类药物','P2Y12受体抑制剂','利尿剂','洋地黄类药物'
        ]
        AND NOT (m)-[:has_specific_medication]->(:KGNode {entityType:'Medication'})
        RETURN count(DISTINCT m) AS value
    """,
    "label_metadata_mismatch_count": """
        MATCH (n:KGNode)
        WHERE n.canonical_labels IS NULL OR n.primary_label <> 'KGNode' OR n.type_label <> n.entityType
        RETURN count(n) AS value
    """,
    "anticoagulant_specific_medications": """
        MATCH (m:KGNode {entityType:'Medication', name:'抗凝药物'})
        OPTIONAL MATCH (m)-[:has_specific_medication]->(x:KGNode {entityType:'Medication'})
        RETURN m.name AS class_name, collect(DISTINCT m.code) AS class_codes, collect(DISTINCT m.aliases) AS alias_sets, count(DISTINCT x.name) AS specific_count, collect(DISTINCT x.name)[0..50] AS specifics
    """,
    "thrombolytic_specific_medications": """
        MATCH (m:KGNode {entityType:'Medication', name:'溶栓药物'})
        OPTIONAL MATCH (m)-[:has_specific_medication]->(x:KGNode {entityType:'Medication'})
        RETURN m.name AS class_name, collect(DISTINCT m.code) AS class_codes, collect(DISTINCT m.aliases) AS alias_sets, count(DISTINCT x.name) AS specific_count, collect(DISTINCT x.name)[0..50] AS specifics
    """,
    "statin_specific_medications": """
        MATCH (m:KGNode {entityType:'Medication', name:'他汀类药物'})
        OPTIONAL MATCH (m)-[:has_specific_medication]->(x:KGNode {entityType:'Medication'})
        RETURN m.name AS class_name, collect(DISTINCT m.code) AS class_codes, count(DISTINCT x.name) AS specific_count, collect(DISTINCT x.name)[0..50] AS specifics
    """,
    "beta_blocker_specific_medications": """
        MATCH (m:KGNode {entityType:'Medication'})
        WHERE m.name IN ['β受体阻滞剂','β受体拮抗剂']
        OPTIONAL MATCH (m)-[:has_specific_medication]->(x:KGNode {entityType:'Medication'})
        RETURN m.name AS class_name, collect(DISTINCT m.code) AS class_codes, count(DISTINCT x.name) AS specific_count, collect(DISTINCT x.name)[0..50] AS specifics
        ORDER BY class_name
    """,
    "thrombolysis_execution_links": """
        MATCH (p:KGNode {entityType:'TreatmentPlan', name:'溶栓治疗'})
        OPTIONAL MATCH (p)-[r]->(t:KGNode)
        WHERE type(r) IN ['includes_medication','includes_procedure','has_timing','has_clinical_pathway']
        RETURN p.name AS plan_name, collect(DISTINCT {relation:type(r), target:t.name, target_type:t.entityType}) AS downstream
    """,
    "duplicate_type_name_count": """
        MATCH (n:KGNode)
        WITH n.entityType AS entity_type, n.name AS name, count(n) AS c
        WHERE c > 1
        RETURN count(*) AS duplicate_pairs
    """,
    "top_duplicate_type_names": """
        MATCH (n:KGNode)
        WITH n.entityType AS entity_type, n.name AS name, count(n) AS c, collect(n.code)[0..10] AS codes
        WHERE c > 1
        RETURN entity_type, name, c, codes
        ORDER BY c DESC, entity_type, name
        LIMIT 20
    """,
    "clinical_review_status_counts": """
        MATCH (n:KGNode)
        RETURN n.clinical_review_status AS status, count(n) AS count
        ORDER BY count DESC
    """,
}


def rows(result: dict) -> list[dict]:
    return [
        {col: item["row"][idx] for idx, col in enumerate(result["results"][0]["columns"])}
        for item in result["results"][0]["data"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify global repair effects on the Neo4j test server.")
    parser.add_argument("--uri", default="http://192.168.3.27:7474")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    if not args.password:
        parser.error("Neo4j password must be provided via --password or NEO4J_PASSWORD.")

    client = Neo4jHttpClient(args.uri, args.username, args.password, args.database, 5, 1)
    output = {}
    for name, query in QUERIES.items():
        output[name] = rows(client.run(query))
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
