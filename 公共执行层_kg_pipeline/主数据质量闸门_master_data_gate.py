from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient, first_row


EXCLUDED_ENTITY_TYPES = [
    "Evidence",
    "Guideline",
    "RecommendationStatement",
    "ClinicalRule",
    "ClinicalPathway",
    "PathwayStage",
    "SourceDocument",
]


@dataclass(frozen=True)
class GateCheck:
    metric: str
    chinese_name: str
    description: str
    count_query: str
    detail_query: str


CHECKS: list[GateCheck] = [
    GateCheck(
        metric="noncanonical_disease_category_count",
        chinese_name="非标准疾病大类残留",
        description="正式疾病大类编码必须使用 CAT- 前缀；非标准旧目录会造成统计重复和疾病漏展示。",
        count_query="""
            MATCH (c:KGNode {entityType:'DiseaseCategory'})
            WHERE coalesce(c.status,'active') <> 'deprecated'
              AND coalesce(c.deprecated,false) <> true
              AND NOT c.code STARTS WITH 'CAT-'
            RETURN count(c) AS value
        """,
        detail_query="""
            MATCH (c:KGNode {entityType:'DiseaseCategory'})
            WHERE coalesce(c.status,'active') <> 'deprecated'
              AND coalesce(c.deprecated,false) <> true
              AND NOT c.code STARTS WITH 'CAT-'
            OPTIONAL MATCH (c)-[:has_disease]->(d:KGNode {entityType:'Disease'})
            RETURN c.code AS category_code, c.name AS category_name,
                   count(DISTINCT d) AS direct_disease_count
            ORDER BY category_name, category_code
        """,
    ),
    GateCheck(
        metric="disease_unreachable_from_canonical_category_count",
        chinese_name="疾病无法从正式大类到达",
        description="每个疾病必须能从正式疾病大类经直接包含或临床分型关系到达，否则页面与CDSS目录会漏掉该疾病。",
        count_query="""
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE coalesce(d.status,'active') <> 'deprecated'
              AND coalesce(d.deprecated,false) <> true
              AND NOT EXISTS {
                MATCH (:KGNode {entityType:'Specialty'})-[:has_disease_category]->
                      (c:KGNode {entityType:'DiseaseCategory'})-[:has_disease]->
                      (:KGNode {entityType:'Disease'})-[:has_clinical_subtype*0..3]->(d)
                WHERE c.code STARTS WITH 'CAT-'
              }
            RETURN count(d) AS value
        """,
        detail_query="""
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE coalesce(d.status,'active') <> 'deprecated'
              AND coalesce(d.deprecated,false) <> true
              AND NOT EXISTS {
                MATCH (:KGNode {entityType:'Specialty'})-[:has_disease_category]->
                      (c:KGNode {entityType:'DiseaseCategory'})-[:has_disease]->
                      (:KGNode {entityType:'Disease'})-[:has_clinical_subtype*0..3]->(d)
                WHERE c.code STARTS WITH 'CAT-'
              }
            RETURN d.code AS disease_code, d.name AS disease_name,
                   d.diagnostic_role AS diagnostic_role, d.parentCode AS parent_code
            ORDER BY disease_name, disease_code
        """,
    ),
    GateCheck(
        metric="clinical_subtype_multiple_parent_count",
        chinese_name="临床分型存在多个父疾病",
        description="一个具体临床分型只能归属一个待分型父疾病，避免同一分型同时出现在不相干诊断路径。",
        count_query="""
            MATCH (d:KGNode {entityType:'Disease',diagnostic_role:'clinical_subtype'})
            OPTIONAL MATCH (p:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->(d)
            WITH d, count(DISTINCT p) AS parent_count
            WHERE parent_count > 1
            RETURN count(d) AS value
        """,
        detail_query="""
            MATCH (d:KGNode {entityType:'Disease',diagnostic_role:'clinical_subtype'})
            OPTIONAL MATCH (p:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->(d)
            WITH d, collect(DISTINCT {code:p.code,name:p.name}) AS parents,
                 count(DISTINCT p) AS parent_count
            WHERE parent_count > 1
            RETURN d.code AS disease_code, d.name AS disease_name, parent_count, parents
            ORDER BY parent_count DESC, disease_name
        """,
    ),
    GateCheck(
        metric="clinical_subtype_parent_role_error_count",
        chinese_name="临床分型父疾病角色错误",
        description="临床分型的唯一父疾病必须是待分型诊断，不能挂在独立疾病或另一个具体分型下面。",
        count_query="""
            MATCH (p:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->
                  (d:KGNode {entityType:'Disease',diagnostic_role:'clinical_subtype'})
            WHERE coalesce(p.diagnostic_role,'') <> 'broad_diagnosis'
            RETURN count(DISTINCT d) AS value
        """,
        detail_query="""
            MATCH (p:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->
                  (d:KGNode {entityType:'Disease',diagnostic_role:'clinical_subtype'})
            WHERE coalesce(p.diagnostic_role,'') <> 'broad_diagnosis'
            RETURN p.code AS parent_code, p.name AS parent_name,
                   p.diagnostic_role AS parent_role,
                   d.code AS subtype_code, d.name AS subtype_name
            ORDER BY parent_name, subtype_name
        """,
    ),
    GateCheck(
        metric="disease_without_parent_count",
        chinese_name="疾病无父级",
        description="正式疾病必须由疾病大类直接包含，或作为另一个疾病的临床分型；两者都没有即为目录断链。",
        count_query="""
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE coalesce(d.status,'active') <> 'deprecated'
              AND coalesce(d.deprecated, false) <> true
              AND d.duplicate_replaced_by IS NULL
              AND NOT (:KGNode {entityType:'DiseaseCategory'})-[:has_disease]->(d)
              AND NOT (:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->(d)
            RETURN count(d) AS value
        """,
        detail_query="""
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE coalesce(d.status,'active') <> 'deprecated'
              AND coalesce(d.deprecated, false) <> true
              AND d.duplicate_replaced_by IS NULL
              AND NOT (:KGNode {entityType:'DiseaseCategory'})-[:has_disease]->(d)
              AND NOT (:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->(d)
            RETURN d.code AS disease_code, d.name AS disease_name, d.batch_id AS batch_id
            ORDER BY disease_name, disease_code
        """,
    ),
    GateCheck(
        metric="clinical_subtype_without_parent_count",
        chinese_name="临床分型无父疾病",
        description="标记为具体临床分型的疾病必须由宽口径疾病通过 has_clinical_subtype 连接。",
        count_query="""
            MATCH (d:KGNode {entityType:'Disease', diagnostic_role:'clinical_subtype'})
            WHERE NOT (:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->(d)
            RETURN count(d) AS value
        """,
        detail_query="""
            MATCH (d:KGNode {entityType:'Disease', diagnostic_role:'clinical_subtype'})
            WHERE NOT (:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->(d)
            RETURN d.code AS disease_code, d.name AS disease_name, d.batch_id AS batch_id
            ORDER BY disease_name, disease_code
        """,
    ),
    GateCheck(
        metric="display_group_without_category_count",
        chinese_name="展示分组无疾病大类",
        description="DiseaseSubcategory 只用于页面展示分组，必须由疾病大类通过 has_display_group 连接。",
        count_query="""
            MATCH (s:KGNode {entityType:'DiseaseSubcategory'})
            WHERE coalesce(s.status,'active') <> 'deprecated'
              AND coalesce(s.deprecated, false) <> true
              AND NOT (:KGNode {entityType:'DiseaseCategory'})-[:has_display_group]->(s)
            RETURN count(s) AS value
        """,
        detail_query="""
            MATCH (s:KGNode {entityType:'DiseaseSubcategory'})
            WHERE coalesce(s.status,'active') <> 'deprecated'
              AND coalesce(s.deprecated, false) <> true
              AND NOT (:KGNode {entityType:'DiseaseCategory'})-[:has_display_group]->(s)
            RETURN s.code AS subcategory_code, s.name AS subcategory_name, s.batch_id AS batch_id
            ORDER BY subcategory_name, subcategory_code
        """,
    ),
    GateCheck(
        metric="legacy_disease_classification_count",
        chinese_name="旧疾病分型实体残留",
        description="V2.0 已用 Disease 加 has_clinical_subtype 表达诊断分型，DiseaseClassification 必须为零。",
        count_query="""
            MATCH (cl:KGNode {entityType:'DiseaseClassification'})
            RETURN count(cl) AS value
        """,
        detail_query="""
            MATCH (cl:KGNode {entityType:'DiseaseClassification'})
            RETURN cl.code AS classification_code, cl.name AS classification_name, cl.batch_id AS batch_id
            ORDER BY classification_name, classification_code
        """,
    ),
    GateCheck(
        metric="legacy_disease_hierarchy_relation_count",
        chinese_name="旧疾病层级关系残留",
        description="V1 的双向和过载关系不得回流；新结构只使用 V2.0 单向层级关系。",
        count_query="""
            MATCH ()-[r]->()
            WHERE type(r) IN ['has_category','belongs_to_category','has_subcategory','belongs_to_subcategory','has_classification']
            RETURN count(r) AS value
        """,
        detail_query="""
            MATCH (source)-[r]->(target)
            WHERE type(r) IN ['has_category','belongs_to_category','has_subcategory','belongs_to_subcategory','has_classification']
            RETURN source.code AS source_code, source.name AS source_name,
                   type(r) AS relation_type, target.code AS target_code, target.name AS target_name
            ORDER BY relation_type, source_name, target_name
        """,
    ),
    GateCheck(
        metric="active_duplicate_disease_name_count",
        chinese_name="正式疾病同名重复",
        description="同一个疾病名称不能存在多个正式 Disease 节点；一病多目录应使用一个疾病节点连接多个目录。",
        count_query="""
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE coalesce(d.status,'active') <> 'deprecated'
              AND coalesce(d.deprecated, false) <> true
              AND d.duplicate_replaced_by IS NULL
              AND d.name IS NOT NULL
              AND trim(d.name) <> ''
            WITH d.name AS disease_name, count(DISTINCT d.code) AS node_count
            WHERE node_count > 1
            RETURN count(*) AS value
        """,
        detail_query="""
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE coalesce(d.status,'active') <> 'deprecated'
              AND coalesce(d.deprecated, false) <> true
              AND d.duplicate_replaced_by IS NULL
              AND d.name IS NOT NULL
              AND trim(d.name) <> ''
            WITH d.name AS disease_name, collect(DISTINCT d.code) AS disease_codes, count(DISTINCT d.code) AS node_count
            WHERE node_count > 1
            RETURN disease_name, node_count, disease_codes
            ORDER BY node_count DESC, disease_name
        """,
    ),
    GateCheck(
        metric="retired_disease_node_remaining_count",
        chinese_name="退役疾病节点残留",
        description="已被标准疾病替换的旧 Disease 节点不得继续留在正式图谱库；留痕应放在本地备份文件，不放在医生可查图谱里。",
        count_query="""
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE d.duplicate_replaced_by IS NOT NULL
               OR coalesce(d.status,'active') = 'deprecated'
               OR coalesce(d.deprecated, false) = true
            RETURN count(d) AS value
        """,
        detail_query="""
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE d.duplicate_replaced_by IS NOT NULL
               OR coalesce(d.status,'active') = 'deprecated'
               OR coalesce(d.deprecated, false) = true
            OPTIONAL MATCH (d)-[r]-()
            RETURN d.code AS disease_code, d.name AS disease_name, d.status AS status,
                   d.deprecated AS deprecated, d.duplicate_replaced_by AS duplicate_replaced_by,
                   count(r) AS relation_count
            ORDER BY relation_count DESC, disease_name
        """,
    ),
    GateCheck(
        metric="non_scalar_code_count",
        chinese_name="编码字段不是单值字符串",
        description="实体 code 必须是唯一、稳定的单值字符串；历史合并编码应写入 merged_from_codes，不能把编码数组继续留在主编码字段。",
        count_query="""
            MATCH (n:KGNode)
            WHERE n.code IS NOT NULL
              AND valueType(n.code) STARTS WITH 'LIST'
            RETURN count(n) AS value
        """,
        detail_query="""
            MATCH (n:KGNode)
            WHERE n.code IS NOT NULL
              AND valueType(n.code) STARTS WITH 'LIST'
            RETURN elementId(n) AS node_element_id, n.entityType AS entity_type,
                   n.name AS name, n.code AS code, n.duplicate_replaced_by AS duplicate_replaced_by,
                   n.batch_id AS batch_id
            ORDER BY entity_type, name
        """,
    ),
    GateCheck(
        metric="same_disease_same_type_same_name_duplicate_count",
        chinese_name="同病种同类型同名重复直连",
        description="同一个疾病下，同一实体类型、同一名称出现多个节点。应复用标准主节点，不应重复创建。",
        count_query="""
            MATCH (d:Disease)-[]->(n:KGNode)
            WHERE n.entityType IS NOT NULL
              AND n.name IS NOT NULL
              AND trim(n.name) <> ''
              AND NOT n.entityType IN $excluded_entity_types
            WITH d.code AS disease_code, n.entityType AS entity_type, n.name AS name,
                 count(DISTINCT n.code) AS node_count
            WHERE node_count > 1
            RETURN count(*) AS value
        """,
        detail_query="""
            MATCH (d:Disease)-[]->(n:KGNode)
            WHERE n.entityType IS NOT NULL
              AND n.name IS NOT NULL
              AND trim(n.name) <> ''
              AND NOT n.entityType IN $excluded_entity_types
            WITH d.code AS disease_code, d.name AS disease_name, n.entityType AS entity_type, n.name AS name,
                 count(DISTINCT n.code) AS node_count,
                 collect(DISTINCT n.code)[0..30] AS node_codes
            WHERE node_count > 1
            RETURN disease_code, disease_name, entity_type, name, node_count, node_codes
            ORDER BY disease_code, entity_type, name
        """,
    ),
    GateCheck(
        metric="standard_procedure_required_field_error_count",
        chinese_name="标准手术关键字段缺失或无效",
        description="CDSS 标准手术必须保留 Oracle UUID、标准编码、标准名称、有效标志、来源表和二次校验结论，且只能使用有效标志为1并已校验通过的记录。",
        count_query="""
            MATCH (s:KGNode {entityType:'StandardProcedure'})
            WHERE s.cdss_dict_id IS NULL OR trim(toString(s.cdss_dict_id)) = ''
               OR s.standard_code IS NULL OR trim(toString(s.standard_code)) = ''
               OR s.name IS NULL OR trim(s.name) = ''
               OR coalesce(s.valid_flag, 0) <> 1
               OR coalesce(s.source_table, '') <> 'K_OPERATION_HANDLE_DICT'
               OR coalesce(s.dictionary_validation_status, '') <> 'validated'
               OR s.dictionary_validation_sources IS NULL
               OR size(s.dictionary_validation_sources) = 0
            RETURN count(s) AS value
        """,
        detail_query="""
            MATCH (s:KGNode {entityType:'StandardProcedure'})
            WHERE s.cdss_dict_id IS NULL OR trim(toString(s.cdss_dict_id)) = ''
               OR s.standard_code IS NULL OR trim(toString(s.standard_code)) = ''
               OR s.name IS NULL OR trim(s.name) = ''
               OR coalesce(s.valid_flag, 0) <> 1
               OR coalesce(s.source_table, '') <> 'K_OPERATION_HANDLE_DICT'
               OR coalesce(s.dictionary_validation_status, '') <> 'validated'
               OR s.dictionary_validation_sources IS NULL
               OR size(s.dictionary_validation_sources) = 0
            RETURN s.code AS node_code, s.cdss_dict_id AS cdss_dict_id,
                   s.standard_code AS standard_code, s.name AS name,
                   s.valid_flag AS valid_flag, s.source_table AS source_table,
                   s.dictionary_validation_status AS dictionary_validation_status,
                   s.dictionary_validation_sources AS dictionary_validation_sources
            ORDER BY name, standard_code
        """,
    ),
    GateCheck(
        metric="standard_procedure_duplicate_uuid_count",
        chinese_name="标准手术Oracle UUID重复",
        description="同一个 CDSS 手术字典 UUID 只能对应一个 StandardProcedure 节点。",
        count_query="""
            MATCH (s:KGNode {entityType:'StandardProcedure'})
            WITH s.cdss_dict_id AS cdss_dict_id, count(DISTINCT s.code) AS node_count
            WHERE cdss_dict_id IS NOT NULL AND trim(toString(cdss_dict_id)) <> '' AND node_count > 1
            RETURN count(*) AS value
        """,
        detail_query="""
            MATCH (s:KGNode {entityType:'StandardProcedure'})
            WITH s.cdss_dict_id AS cdss_dict_id, collect(DISTINCT s.code) AS node_codes,
                 collect(DISTINCT s.name) AS names, count(DISTINCT s.code) AS node_count
            WHERE cdss_dict_id IS NOT NULL AND trim(toString(cdss_dict_id)) <> '' AND node_count > 1
            RETURN cdss_dict_id, node_count, node_codes, names
            ORDER BY node_count DESC, cdss_dict_id
        """,
    ),
    GateCheck(
        metric="standard_procedure_duplicate_code_count",
        chinese_name="标准手术编码重复",
        description="同一手术编码体系版本下，一个标准手术编码只能对应一个 StandardProcedure 节点。",
        count_query="""
            MATCH (s:KGNode {entityType:'StandardProcedure'})
            WITH s.coding_system AS coding_system, s.coding_system_version AS coding_system_version,
                 s.standard_code AS standard_code, count(DISTINCT s.code) AS node_count
            WHERE standard_code IS NOT NULL AND trim(toString(standard_code)) <> '' AND node_count > 1
            RETURN count(*) AS value
        """,
        detail_query="""
            MATCH (s:KGNode {entityType:'StandardProcedure'})
            WITH s.coding_system AS coding_system, s.coding_system_version AS coding_system_version,
                 s.standard_code AS standard_code, collect(DISTINCT s.code) AS node_codes,
                 collect(DISTINCT s.name) AS names, count(DISTINCT s.code) AS node_count
            WHERE standard_code IS NOT NULL AND trim(toString(standard_code)) <> '' AND node_count > 1
            RETURN coding_system, coding_system_version, standard_code, node_count, node_codes, names
            ORDER BY node_count DESC, standard_code
        """,
    ),
    GateCheck(
        metric="orphan_standard_procedure_count",
        chinese_name="标准手术无临床手术引用",
        description="StandardProcedure 必须由临床 Procedure 通过 has_standard_procedure 引用，不能形成孤立字典节点。",
        count_query="""
            MATCH (s:KGNode {entityType:'StandardProcedure'})
            WHERE NOT (:KGNode {entityType:'Procedure'})-[:has_standard_procedure]->(s)
            RETURN count(s) AS value
        """,
        detail_query="""
            MATCH (s:KGNode {entityType:'StandardProcedure'})
            WHERE NOT (:KGNode {entityType:'Procedure'})-[:has_standard_procedure]->(s)
            RETURN s.code AS node_code, s.standard_code AS standard_code,
                   s.name AS name, s.cdss_dict_id AS cdss_dict_id
            ORDER BY name, standard_code
        """,
    ),
    GateCheck(
        metric="formal_procedure_without_standard_count",
        chinese_name="正式推荐手术缺标准手术映射",
        description="进入正式 CDSS 推荐链路的 Procedure 必须映射到至少一个有效 StandardProcedure，才能生成可回填的手术医嘱。",
        count_query="""
            MATCH (r:KGNode {entityType:'RecommendationStatement'})-[:recommends_action]->
                  (p:KGNode {entityType:'Procedure'})
            WHERE coalesce(r.cdss_use_status, '') = '正式推荐'
              AND NOT (p)-[:has_standard_procedure]->(:KGNode {entityType:'StandardProcedure', valid_flag:1})
            RETURN count(DISTINCT p) AS value
        """,
        detail_query="""
            MATCH (r:KGNode {entityType:'RecommendationStatement'})-[:recommends_action]->
                  (p:KGNode {entityType:'Procedure'})
            WHERE coalesce(r.cdss_use_status, '') = '正式推荐'
              AND NOT (p)-[:has_standard_procedure]->(:KGNode {entityType:'StandardProcedure', valid_flag:1})
            RETURN p.code AS procedure_code, p.name AS procedure_name,
                   collect(DISTINCT r.code)[0..20] AS recommendation_codes
            ORDER BY procedure_name, procedure_code
        """,
    ),
    GateCheck(
        metric="diagnosis_criteria_without_component_count",
        chinese_name="诊断标准无明细",
        description="诊断标准只有标题，没有下钻到具体诊断条件。",
        count_query="""
            MATCH (d:Disease)-[:has_diagnostic_criteria]->(c:DiagnosisCriteria)
            WHERE NOT (c)-[:has_diagnostic_component]->(:KGNode)
            RETURN count(DISTINCT c) AS value
        """,
        detail_query="""
            MATCH (d:Disease)-[:has_diagnostic_criteria]->(c:DiagnosisCriteria)
            WHERE NOT (c)-[:has_diagnostic_component]->(:KGNode)
            RETURN d.code AS disease_code, d.name AS disease_name,
                   c.code AS criteria_code, c.name AS criteria_name, c.batch_id AS batch_id
            ORDER BY disease_code, criteria_name
        """,
    ),
    GateCheck(
        metric="orphan_diagnosis_criteria_count",
        chinese_name="孤儿诊断标准",
        description="诊断标准节点没有任何关系，通常是历史归并后残留的空节点。",
        count_query="""
            MATCH (c:DiagnosisCriteria)
            WHERE NOT (c)--()
            RETURN count(c) AS value
        """,
        detail_query="""
            MATCH (c:DiagnosisCriteria)
            WHERE NOT (c)--()
            RETURN c.code AS criteria_code, c.name AS criteria_name, c.batch_id AS batch_id, c.created_at AS created_at
            ORDER BY criteria_code
        """,
    ),
    GateCheck(
        metric="treatment_plan_without_downstream_count",
        chinese_name="治疗方案无下游",
        description="治疗方案没有药物、操作、其他治疗项目、证据或路径动作，医生无法落地执行。",
        count_query="""
            MATCH (p:TreatmentPlan)
            WHERE coalesce(p.deprecated, false) <> true
              AND NOT (p)-[:includes_medication|includes_procedure|includes_treatment_item|has_treatment_component|supported_by_evidence|has_clinical_pathway|has_follow_up|has_indication|has_contraindication|has_recommended_action|recommends_action|treated_by_medication|treated_by_procedure]->(:KGNode)
            OPTIONAL MATCH (src:KGNode)-[r]->(p)
            WITH p, count(r) AS in_degree
            WHERE in_degree > 0 OR coalesce(p.formal_cdss_ready, false) = true
            RETURN count(DISTINCT p) AS value
        """,
        detail_query="""
            MATCH (p:TreatmentPlan)
            WHERE coalesce(p.deprecated, false) <> true
              AND NOT (p)-[:includes_medication|includes_procedure|includes_treatment_item|has_treatment_component|supported_by_evidence|has_clinical_pathway|has_follow_up|has_indication|has_contraindication|has_recommended_action|recommends_action|treated_by_medication|treated_by_procedure]->(:KGNode)
            OPTIONAL MATCH (src:KGNode)-[r]->(p)
            WITH p, count(r) AS in_degree,
                 collect(DISTINCT {source_code: src.code, source_name: src.name, relation_type: type(r)})[0..20] AS incoming
            WHERE in_degree > 0 OR coalesce(p.formal_cdss_ready, false) = true
            RETURN p.code AS plan_code, p.name AS plan_name, p.batch_id AS batch_id, in_degree, incoming
            ORDER BY in_degree DESC, plan_name
        """,
    ),
    GateCheck(
        metric="replaced_duplicate_still_referenced_count",
        chinese_name="已替换重复节点仍被引用",
        description="重复节点已经被标记为归并替换，但仍被任意实体或关系引用。检查范围覆盖全部关系类型，不再只检查少数临床关系。",
        count_query="""
            MATCH (n:KGNode)-[r]-()
            WHERE n.duplicate_replaced_by IS NOT NULL
              AND n.duplicate_replaced_by <> n.code
            RETURN count(r) AS value
        """,
        detail_query="""
            MATCH (n:KGNode)-[r]-(other:KGNode)
            WHERE n.duplicate_replaced_by IS NOT NULL
              AND n.duplicate_replaced_by <> n.code
            RETURN other.code AS related_code, other.name AS related_name, type(r) AS relation_type,
                   n.code AS duplicate_code, n.name AS duplicate_name,
                   n.duplicate_replaced_by AS standard_node_code
            ORDER BY relation_type, related_code, duplicate_name
        """,
    ),
    GateCheck(
        metric="duplicate_replacement_marker_count",
        chinese_name="历史重复替代标记未收口",
        description="完成物理归并后不应继续保留 duplicate_replaced_by。有效重复节点应物理归并，失效或自指标记应清除。",
        count_query="""
            MATCH (n:KGNode)
            WHERE n.duplicate_replaced_by IS NOT NULL
            RETURN count(n) AS value
        """,
        detail_query="""
            MATCH (n:KGNode)
            WHERE n.duplicate_replaced_by IS NOT NULL
            RETURN elementId(n) AS node_element_id, n.entityType AS entity_type,
                   n.code AS code, n.name AS name,
                   n.duplicate_replaced_by AS duplicate_replaced_by,
                   COUNT {(n)--()} AS relation_count
            ORDER BY relation_count DESC, entity_type, name
        """,
    ),
]


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    http = re.search(r"https?://[^\s，,]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s，,]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,]+)", text, re.I)
    if not http:
        raise ValueError(f"未在连接文件中找到 Neo4j HTTP 地址：{path}")
    if not password:
        raise ValueError(f"未在连接文件中找到密码字段：{path}")
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


def run_value(client: Neo4jHttpClient, statement: str) -> int:
    row = first_row(client.run(statement, {"excluded_entity_types": EXCLUDED_ENTITY_TYPES}))
    return int(row[0] or 0) if row else 0


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def summarize_counts(counts: dict[str, int]) -> dict[str, Any]:
    blocking_items = [
        {
            "metric": check.metric,
            "chinese_name": check.chinese_name,
            "count": int(counts.get(check.metric, 0) or 0),
            "description": check.description,
        }
        for check in CHECKS
        if int(counts.get(check.metric, 0) or 0) > 0
    ]
    gate_status = "passed" if not blocking_items else "failed"
    return {
        "gate_name": "主数据质量闸门",
        "gate_status": gate_status,
        "gate_status_cn": "通过" if gate_status == "passed" else "未通过",
        "blocking_issue_count": len(blocking_items),
        "blocking_items": blocking_items,
        "counts": counts,
    }


def write_report(path: Path, summary: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# 主数据质量闸门报告",
        "",
        f"- 生成时间：{summary['generated_at']}",
        f"- 闸门状态：{summary.get('gate_status_cn', summary['gate_status'])}",
        f"- 阻断项数量：{summary['blocking_issue_count']}",
        "",
        "## 检查结果",
        "",
        "| 检查项 | 数量 | 说明 |",
        "|---|---:|---|",
    ]
    counts = summary["counts"]
    by_metric = {check.metric: check for check in CHECKS}
    for metric, count in counts.items():
        check = by_metric[metric]
        lines.append(f"| {check.chinese_name} | {count} | {check.description} |")
    lines.extend(["", "## 结论", ""])
    if summary["gate_status"] == "passed":
        lines.append("本轮主数据质量闸门通过：未发现疾病层级断链、孤立疾病分型、同名疾病重复、退役疾病残留、孤儿诊断标准、空壳治疗方案或已替换节点仍被引用。")
    else:
        lines.append("本轮主数据质量闸门未通过：必须先处理阻断项，再进入新病种入库或正式 CDSS 转正。")
    lines.extend(["", "## 明细目录", "", f"`{output_dir / 'details'}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_gate(connection_file: Path, output_dir: Path, database: str = "neo4j") -> dict[str, Any]:
    conn = parse_connection_file(connection_file)
    client = Neo4jHttpClient(conn["uri"], conn["username"], conn["password"], database, 3, 1)
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_dir = output_dir / "details"

    counts: dict[str, int] = {}
    details: dict[str, list[dict[str, Any]]] = {}
    for check in CHECKS:
        counts[check.metric] = run_value(client, check.count_query)
        rows = result_rows(client.run(check.detail_query, {"excluded_entity_types": EXCLUDED_ENTITY_TYPES}))
        details[check.metric] = rows
        write_csv(detail_dir / f"{check.metric}.csv", rows)

    summary = summarize_counts(counts)
    summary["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary["output_dir"] = str(output_dir)

    (output_dir / "主数据质量闸门_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "主数据质量闸门_detail.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_report(output_dir / "主数据质量闸门报告.md", summary, output_dir)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="主数据质量闸门：只读检查标准主节点、孤儿诊断标准和空壳治疗方案。")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--fail-on-blocking", action="store_true", help="发现阻断项时返回非 0，便于自动化流水线阻断。")
    args = parser.parse_args()

    summary = run_gate(args.connection_file, args.output_dir, args.database)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.fail_on_blocking and summary["gate_status"] != "passed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
