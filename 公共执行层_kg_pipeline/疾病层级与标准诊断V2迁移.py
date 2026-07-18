#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""疾病层级与 CDSS 标准诊断 V2.0 受控迁移。

默认只生成计划，不写数据库。只有显式使用 ``--mode apply`` 才执行写库。
支持先迁移 AMI/心肌病样板，再迁移全部疾病；每次写库前生成迁移专用回滚包。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = (
    ROOT
    / "项目管理中心_project_management"
    / "139_CDSS标准主数据与疾病分型升级_20260719"
)
SAMPLE_NODE_FILE = PROJECT_DIR / "05_AMI与心肌病V2样板_nodes.jsonl"
SAMPLE_RELATION_FILE = PROJECT_DIR / "06_AMI与心肌病V2样板_relations.jsonl"
BACKUP_MODULE = ROOT / "公共执行层_kg_pipeline" / "Neo4j全量逻辑备份.py"

SCHEMA_VERSION = "V2.0"
CANONICAL_SPECIALTY_CODE = "SPEC-CARD"
MIGRATION_BATCH_SAMPLE = "MIG-CARD-V2-20260719-001"
MIGRATION_BATCH_ALL = "MIG-CARD-V2-20260719-ALL"

SAMPLE_DISEASE_CODES = {
    "DIS-CARD-CAD-AMI",
    "DIS-CARD-CAD-STEMI",
    "DIS-CARD-CAD-NSTEMI",
    "DIS-CARD-CM-GENERAL",
    "DIS-CARD-CM-HCM",
    "DIS-CARD-CM-DCM",
}
SAMPLE_CATEGORY_CODES = {"CAT-CARD-CAD", "CAT-CARD-CM"}

ALLOWED_SOURCE_TYPES = {
    "authoritative_textbook",
    "guideline",
    "consensus",
    "clinical_pathway",
    "cdss_standard_dict",
    "external_authority",
    "governed_composite",
}

ALLOWED_STRUCTURAL_RELATIONS = {
    "has_disease_category",
    "has_disease",
    "has_clinical_subtype",
    "has_display_group",
    "groups_disease",
    "classified_as",
    "has_standard_diagnosis",
    "has_risk_stratification",
}

LEGACY_STRUCTURAL_RELATIONS = {
    "has_category",
    "belongs_to_category",
    "has_subcategory",
    "belongs_to_subcategory",
    "has_classification",
}

REQUIRED_NODE_FIELDS = {
    "code",
    "entityType",
    "name",
    "aliases",
    "source_type",
    "batch_id",
    "schema_version",
    "clinical_use_status",
}
REQUIRED_RELATION_FIELDS = {
    "id",
    "source_code",
    "relationType",
    "target_code",
    "batch_id",
    "schema_version",
    "review_status",
    "clinical_review_status",
}

ENTITY_LABELS = {
    "Specialty",
    "DiseaseCategory",
    "DiseaseSubcategory",
    "Disease",
    "StandardDiagnosis",
    "RiskStratification",
}

MANUAL_DUPLICATE_DISEASE_MAP = {
    "DIS-CARD-HF": "DIS-CARD-HF-GENERAL",
    "DIS-CARD-ASD": "DIS-CARD-CHD-ASD",
    "DIS-CARD-HTN-ESSENTIAL": "DIS-CARD-HT",
}

MANUAL_CLASSIFICATION_TARGET_MAP = {
    "CLASS-CARD-CADREM-CCS-631884375C": "DIS-CARD-CAD-SILENT-ISCHEMIA",
}

MANUAL_CLASSIFICATION_PARENT_ALLOWLIST = {
    "CLASS-CARD-CADREM-CCS-631884375C": {"DIS-CARD-CAD-CCS"},
}

SAMPLE_RISK_RENAMES = {
    "CLASS-CARD-CADREM-UA-3ED0E5D680": "Braunwald不稳定型心绞痛分级",
    "CLASS-CARD-CADREM-UA-44D099513F": "GRACE评分高危（>140分）",
    "CLASS-CARD-CADREM-UA-69F8FA5ADF": "GRACE评分中危（109～140分）",
    "CLASS-CARD-CADREM-UA-B60FDF102A": "GRACE评分低危（≤108分）",
}

AUTO_ALIAS_STANDARD_NAME_ALLOWLIST = {
    "DIS-CARD-CAD-STEMI": {"急性ST段抬高型心肌梗死"},
    "DIS-CARD-CAD-NSTEMI": {"急性非ST段抬高型心肌梗死"},
    "DIS-CARD-VHD-TR": {"三尖瓣关闭不全"},
    "DIS-CARD-VHD-AR": {"主动脉瓣关闭不全"},
    "DIS-CARD-ARR-SQTS": {"短QT综合征"},
    "DIS-CARD-ARR-LQTS": {"长QT综合征"},
    "DIS-CARD-CAD-SILENT-ISCHEMIA": {"无症状心肌缺血"},
}


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    iso_format = getattr(value, "iso_format", None)
    if callable(iso_format):
        return iso_format()
    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(json_safe(row), ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            count += 1
    return count


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["无数据"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def normalize_name(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"[\s，,。；;：:（）()【】\[\]·\-_/]+", "", text).lower()


def validate_package(
    nodes: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    *,
    scope_name: str,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    node_codes = [str(node.get("code") or "") for node in nodes]
    node_code_set = set(node_codes)

    for node in nodes:
        missing = sorted(field for field in REQUIRED_NODE_FIELDS if field not in node)
        if missing:
            errors.append({"code": "NODE_REQUIRED_FIELD_MISSING", "node": node.get("code"), "fields": missing})
        if node.get("source_type") not in ALLOWED_SOURCE_TYPES:
            errors.append({"code": "SOURCE_TYPE_INVALID", "node": node.get("code"), "value": node.get("source_type")})
        if node.get("schema_version") != SCHEMA_VERSION:
            errors.append({"code": "SCHEMA_VERSION_INVALID", "node": node.get("code"), "value": node.get("schema_version")})
        if node.get("entityType") == "DiseaseCategory" and node.get("is_diagnosable") is True:
            errors.append({"code": "DISEASE_CATEGORY_DIAGNOSABLE", "node": node.get("code")})
        if node.get("entityType") == "StandardDiagnosis":
            required = ["cdss_dict_id", "standard_code", "source_table", "valid_flag"]
            missing_standard = [field for field in required if node.get(field) in (None, "")]
            if missing_standard:
                errors.append({"code": "STANDARD_DIAGNOSIS_FIELD_MISSING", "node": node.get("code"), "fields": missing_standard})
            if str(node.get("valid_flag")) != "1":
                errors.append({"code": "STANDARD_DIAGNOSIS_NOT_ACTIVE", "node": node.get("code")})

    duplicates = sorted(code for code, count in Counter(node_codes).items() if code and count > 1)
    if duplicates:
        errors.append({"code": "DUPLICATE_NODE_CODE", "nodes": duplicates})

    relation_keys: list[tuple[str, str, str]] = []
    for relation in relations:
        missing = sorted(field for field in REQUIRED_RELATION_FIELDS if field not in relation)
        if missing:
            errors.append({"code": "RELATION_REQUIRED_FIELD_MISSING", "relation": relation.get("id"), "fields": missing})
        key = (
            str(relation.get("source_code") or ""),
            str(relation.get("relationType") or ""),
            str(relation.get("target_code") or ""),
        )
        relation_keys.append(key)
        if key[0] not in node_code_set or key[2] not in node_code_set:
            errors.append({"code": "RELATION_ENDPOINT_MISSING", "relation": relation.get("id"), "triple": key})
        if relation.get("relationType") not in ALLOWED_STRUCTURAL_RELATIONS:
            errors.append({"code": "RELATION_TYPE_INVALID", "relation": relation.get("id"), "value": relation.get("relationType")})
        if relation.get("schema_version") != SCHEMA_VERSION:
            errors.append({"code": "RELATION_SCHEMA_VERSION_INVALID", "relation": relation.get("id")})

    duplicate_relations = [key for key, count in Counter(relation_keys).items() if count > 1]
    if duplicate_relations:
        errors.append({"code": "DUPLICATE_RELATION", "relations": duplicate_relations})

    parent_by_subtype = defaultdict(set)
    category_parent = defaultdict(set)
    standard_by_disease = defaultdict(set)
    for source, relation_type, target in relation_keys:
        if relation_type == "has_clinical_subtype":
            parent_by_subtype[target].add(source)
        elif relation_type == "has_disease":
            category_parent[target].add(source)
        elif relation_type == "has_standard_diagnosis":
            standard_by_disease[source].add(target)

    for node in nodes:
        if node.get("entityType") != "Disease":
            continue
        role = node.get("diagnostic_role")
        code = node.get("code")
        if role == "clinical_subtype" and not parent_by_subtype.get(code):
            errors.append({"code": "CLINICAL_SUBTYPE_WITHOUT_PARENT", "node": code})
        if role in {"broad_diagnosis", "independent_disease"} and not category_parent.get(code):
            warnings.append({"code": "DISEASE_WITHOUT_CATEGORY_IN_PACKAGE", "node": code})
        if node.get("is_emr_writable") is True and not standard_by_disease.get(code):
            errors.append({"code": "EMR_WRITABLE_WITHOUT_STANDARD_DIAGNOSIS", "node": code})

    return {
        "scope_name": scope_name,
        "node_count": len(nodes),
        "relationship_count": len(relations),
        "standard_diagnosis_count": sum(node.get("entityType") == "StandardDiagnosis" for node in nodes),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }


def classify_legacy_classification(
    name: str,
    code: str,
    existing_disease_names: dict[str, str],
) -> dict[str, Any]:
    text = str(name or "").strip()
    if code in MANUAL_CLASSIFICATION_TARGET_MAP:
        return {
            "action": "clinical_subtype",
            "target_disease_code": MANUAL_CLASSIFICATION_TARGET_MAP[code],
            "allowed_parent_codes": sorted(MANUAL_CLASSIFICATION_PARENT_ALLOWLIST.get(code, set())),
            "reason": "经临床语义核对映射到现有疾病实体",
        }
    if text in existing_disease_names:
        return {
            "action": "clinical_subtype",
            "target_disease_code": existing_disease_names[text],
            "reason": "旧分型名称与现有疾病实体精确一致",
        }

    if re.search(r"分类要点\s*\d+", text, re.I):
        return {"action": "invalid_fragment", "reason": "抽取生成的无语义分类要点标题"}
    if len(text) > 34 or re.match(r"^[（(]?[一二三四五六七八九十0-9]+[、.)）]", text):
        return {"action": "invalid_fragment", "reason": "教材句段或列表残句，不是稳定实体"}
    if re.search(r"19\d{2}年|本章主要|本节主要|见表|表\d", text):
        return {"action": "invalid_fragment", "reason": "教材说明句或表格标题，不是稳定实体"}

    risk_patterns = (
        r"评分|高危|中危|低危|很高危|分级|分期|危险分层|"
        r"射血分数|LVEF|NYHA|Braunwald|干冷|干暖|湿冷|湿暖|"
        r"组织低灌注|淤血|血流动力学"
    )
    if re.search(risk_patterns, text, re.I):
        return {"action": "risk_stratification", "reason": "风险、分期或血流动力学分层"}

    disease_suffixes = (
        "病",
        "心力衰竭",
        "心衰竭",
        "心包炎",
        "心肌炎",
        "心肌病",
        "心肌梗死",
        "高血压",
        "肺动脉高压",
        "心动过速",
        "心动过缓",
        "传导阻滞",
    )
    if text.endswith(disease_suffixes):
        return {"action": "clinical_subtype_candidate", "reason": "名称具有疾病语义但未命中现有疾病"}

    return {"action": "invalid_fragment", "reason": "不能稳定表达诊断分型、展示分组或风险分层"}


def convert_structural_relations(
    old_relations: list[dict[str, Any]],
    *,
    canonical_specialty_code: str,
    batch_id: str = MIGRATION_BATCH_ALL,
    subtype_codes: set[str] | None = None,
) -> list[dict[str, Any]]:
    subtype_codes = subtype_codes or set()
    triples: set[tuple[str, str, str]] = set()
    for row in old_relations:
        source = str(row.get("source_code") or "")
        source_type = str(row.get("source_type") or "")
        relation_type = str(row.get("relation_type") or row.get("relationType") or "")
        target = str(row.get("target_code") or "")
        target_type = str(row.get("target_type") or "")
        triple: tuple[str, str, str] | None = None

        if relation_type == "has_category" and source_type == "Specialty":
            triple = (canonical_specialty_code, "has_disease_category", target)
        elif relation_type == "belongs_to_category" and source_type == "Disease":
            if source not in subtype_codes:
                triple = (target, "has_disease", source)
        elif relation_type == "has_subcategory" and source_type == "DiseaseCategory":
            triple = (source, "has_display_group", target)
        elif relation_type == "belongs_to_subcategory" and source_type == "Disease":
            triple = (target, "groups_disease", source)
        elif relation_type == "has_disease" and source_type == "DiseaseSubcategory" and target_type == "Disease":
            triple = (source, "groups_disease", target)
        elif relation_type in ALLOWED_STRUCTURAL_RELATIONS:
            triple = (source, relation_type, target)

        if triple and all(triple):
            triples.add(triple)

    return [
        {
            "id": stable_id("REL-V2", source, relation_type, target),
            "source_code": source,
            "relationType": relation_type,
            "target_code": target,
            "batch_id": batch_id,
            "schema_version": SCHEMA_VERSION,
            "review_status": "passed",
            "clinical_review_status": "not_required",
        }
        for source, relation_type, target in sorted(triples)
    ]


def load_connection_parser() -> Any:
    spec = importlib.util.spec_from_file_location("neo4j_backup", BACKUP_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载数据库连接解析模块：{BACKUP_MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_connection_file


def query_rows(session: Any, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [dict(record) for record in session.run(cypher, parameters or {})]


def query_scalar(
    session: Any,
    cypher: str,
    key: str = "value",
    parameters: dict[str, Any] | None = None,
) -> int:
    record = session.run(cypher, parameters or {}).single(strict=True)
    return int(record[key])


def safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"非法 Neo4j 标识符：{value}")
    return value


def fetch_hierarchy_nodes(session: Any) -> list[dict[str, Any]]:
    return query_rows(
        session,
        """
        MATCH (n:KGNode)
        WHERE n.entityType IN [
          'Specialty','DiseaseCategory','DiseaseSubcategory',
          'DiseaseClassification','Disease','StandardDiagnosis','RiskStratification'
        ]
        RETURN labels(n) AS labels, properties(n) AS properties
        ORDER BY n.entityType, n.name, n.code
        """,
    )


def fetch_structural_relations(session: Any) -> list[dict[str, Any]]:
    return query_rows(
        session,
        """
        MATCH (source)-[r]->(target)
        WHERE source.entityType IN [
          'Specialty','DiseaseCategory','DiseaseSubcategory',
          'DiseaseClassification','Disease'
        ]
          AND target.entityType IN [
          'Specialty','DiseaseCategory','DiseaseSubcategory',
          'DiseaseClassification','Disease','StandardDiagnosis','RiskStratification'
        ]
        RETURN elementId(r) AS relation_element_id,
               source.code AS source_code, source.entityType AS source_type,
               type(r) AS relation_type,
               target.code AS target_code, target.entityType AS target_type,
               properties(r) AS properties
        ORDER BY source_code, relation_type, target_code
        """,
    )


def fetch_all_legacy_relations(session: Any) -> list[dict[str, Any]]:
    """读取全库所有 V1 旧关系，包括历史上误用于来源章节的同名关系。"""
    return query_rows(
        session,
        """
        MATCH (source)-[r]->(target)
        WHERE type(r) IN $types
        RETURN elementId(r) AS relation_element_id,
               source.code AS source_code, source.entityType AS source_type,
               type(r) AS relation_type,
               target.code AS target_code, target.entityType AS target_type,
               properties(r) AS properties
        ORDER BY relation_type, source_type, target_type, source_code, target_code
        """,
        {"types": sorted(LEGACY_STRUCTURAL_RELATIONS)},
    )


def fetch_orphan_classification_nodes(session: Any) -> list[dict[str, Any]]:
    """读取未挂在任何疾病下的历史分型残留节点。"""
    return query_rows(
        session,
        """
        MATCH (n:KGNode {entityType:'DiseaseClassification'})
        WHERE NOT (:KGNode {entityType:'Disease'})-[:has_classification]->(n)
        OPTIONAL MATCH (n)-[r]-()
        RETURN n.code AS classification_code,
               n.name AS classification_name,
               count(r) AS relationship_count,
               'orphan_legacy_classification' AS action,
               '未挂接疾病的历史误分类或抽取残句；完整内容已进入回滚包' AS reason
        ORDER BY classification_name, classification_code
        """,
    )


def fetch_relationships_touching_codes(
    session: Any,
    codes: set[str],
    *,
    include_all_types: bool,
) -> list[dict[str, Any]]:
    if not codes:
        return []
    type_filter = "" if include_all_types else "AND type(r) IN $legacy_types"
    return query_rows(
        session,
        f"""
        MATCH (source)-[r]->(target)
        WHERE (source.code IN $codes OR target.code IN $codes)
          {type_filter}
        RETURN source.code AS source_code, target.code AS target_code,
               type(r) AS relation_type, properties(r) AS properties
        ORDER BY source_code, relation_type, target_code
        """,
        {"codes": sorted(codes), "legacy_types": sorted(LEGACY_STRUCTURAL_RELATIONS)},
    )


def fetch_nodes_by_codes(session: Any, codes: set[str]) -> list[dict[str, Any]]:
    if not codes:
        return []
    return query_rows(
        session,
        """
        MATCH (n:KGNode)
        WHERE n.code IN $codes
        RETURN labels(n) AS labels, properties(n) AS properties
        ORDER BY n.code
        """,
        {"codes": sorted(codes)},
    )


def fetch_classification_edges(session: Any, disease_codes: set[str] | None = None) -> list[dict[str, Any]]:
    where = "" if disease_codes is None else "WHERE parent.code IN $disease_codes"
    return query_rows(
        session,
        f"""
        MATCH (parent:KGNode {{entityType:'Disease'}})-[:has_classification]->(classification:KGNode {{entityType:'DiseaseClassification'}})
        {where}
        RETURN parent.code AS parent_disease_code,
               classification.code AS classification_code,
               classification.name AS classification_name
        ORDER BY parent_disease_code, classification_code
        """,
        {"disease_codes": sorted(disease_codes or set())},
    )


def fetch_disease_nodes(session: Any) -> list[dict[str, Any]]:
    return query_rows(
        session,
        """
        MATCH (d:KGNode {entityType:'Disease'})
        WHERE coalesce(d.status,'active') <> 'deprecated'
          AND coalesce(d.deprecated,false) = false
          AND d.duplicate_replaced_by IS NULL
        RETURN properties(d) AS properties
        ORDER BY d.name, d.code
        """,
    )


def build_sample_plan(session: Any) -> dict[str, Any]:
    nodes = load_jsonl(SAMPLE_NODE_FILE)
    relations = load_jsonl(SAMPLE_RELATION_FILE)
    package_audit = validate_package(nodes, relations, scope_name="AMI与心肌病样板")

    hierarchy_nodes = fetch_hierarchy_nodes(session)
    node_by_code = {
        str(row["properties"].get("code")): row
        for row in hierarchy_nodes
        if row.get("properties", {}).get("code")
    }
    all_structural = fetch_structural_relations(session)
    related_subcategories: set[str] = set()
    for row in all_structural:
        if row["relation_type"] == "belongs_to_subcategory" and row["source_code"] in SAMPLE_DISEASE_CODES:
            related_subcategories.add(str(row["target_code"]))

    relevant_old: list[dict[str, Any]] = []
    for row in all_structural:
        source = str(row["source_code"])
        target = str(row["target_code"])
        relation_type = str(row["relation_type"])
        if relation_type == "has_category" and target in SAMPLE_CATEGORY_CODES:
            relevant_old.append(row)
        elif relation_type == "has_subcategory" and source in SAMPLE_CATEGORY_CODES:
            relevant_old.append(row)
        elif relation_type == "belongs_to_category" and source in SAMPLE_DISEASE_CODES:
            relevant_old.append(row)
        elif relation_type == "belongs_to_subcategory" and source in SAMPLE_DISEASE_CODES:
            relevant_old.append(row)
        elif relation_type == "has_disease" and source in related_subcategories and target in SAMPLE_DISEASE_CODES:
            relevant_old.append(row)
        elif relation_type == "has_classification" and source in SAMPLE_DISEASE_CODES:
            relevant_old.append(row)

    converted = convert_structural_relations(
        relevant_old,
        canonical_specialty_code=CANONICAL_SPECIALTY_CODE,
        batch_id=MIGRATION_BATCH_SAMPLE,
        subtype_codes={
            "DIS-CARD-CAD-STEMI",
            "DIS-CARD-CAD-NSTEMI",
            "DIS-CARD-CM-HCM",
            "DIS-CARD-CM-DCM",
        },
    )
    relation_by_key = {
        (row["source_code"], row["relationType"], row["target_code"]): row
        for row in [*relations, *converted]
        if row["relationType"] != "has_clinical_subtype"
        or row["source_code"] in {"DIS-CARD-CAD-AMI", "DIS-CARD-CM-GENERAL"}
    }
    for row in relations:
        relation_by_key[(row["source_code"], row["relationType"], row["target_code"])] = row

    display_nodes: list[dict[str, Any]] = []
    for code in sorted(related_subcategories):
        current = node_by_code.get(code)
        if not current:
            continue
        props = dict(current["properties"])
        aliases = props.get("aliases")
        if not isinstance(aliases, list):
            aliases = [] if aliases in (None, "") else [str(aliases)]
        props.update(
            {
                "aliases": aliases,
                "source_type": props.get("source_type") or "governed_composite",
                "batch_id": MIGRATION_BATCH_SAMPLE,
                "schema_version": SCHEMA_VERSION,
                "clinical_use_status": "review_ready",
                "display_only": True,
                "is_diagnosable": False,
                "is_emr_writable": False,
            }
        )
        display_nodes.append(props)

    existing_disease_names = {
        str(row["properties"].get("name")): str(row["properties"].get("code"))
        for row in hierarchy_nodes
        if row["properties"].get("entityType") == "Disease"
    }
    classification_edges = fetch_classification_edges(session, SAMPLE_DISEASE_CODES)
    classification_actions: list[dict[str, Any]] = []
    for edge in classification_edges:
        action = classify_legacy_classification(
            str(edge["classification_name"]),
            str(edge["classification_code"]),
            existing_disease_names,
        )
        classification_actions.append({**edge, **action})

    return {
        "scope": "sample",
        "batch_id": MIGRATION_BATCH_SAMPLE,
        "package_audit": package_audit,
        "upsert_nodes": [*nodes, *display_nodes],
        "upsert_relations": list(relation_by_key.values()),
        "legacy_relations_to_remove": relevant_old,
        "classification_actions": classification_actions,
        "duplicate_disease_map": {},
        "related_subcategory_codes": sorted(related_subcategories),
        "unresolved_classification_count": sum(
            row["action"] == "clinical_subtype_candidate" for row in classification_actions
        ),
    }


def build_all_plan(session: Any) -> dict[str, Any]:
    hierarchy_nodes = fetch_hierarchy_nodes(session)
    structural_relations = fetch_structural_relations(session)
    all_legacy_relations = fetch_all_legacy_relations(session)
    orphan_classifications = fetch_orphan_classification_nodes(session)
    disease_rows = [
        dict(row["properties"])
        for row in hierarchy_nodes
        if row["properties"].get("entityType") == "Disease"
        and row["properties"].get("code") not in MANUAL_DUPLICATE_DISEASE_MAP
    ]
    existing_disease_names = {
        str(row.get("name")): str(row.get("code")) for row in disease_rows if row.get("name")
    }
    classification_edges = fetch_classification_edges(session)
    classification_actions: list[dict[str, Any]] = []
    for edge in classification_edges:
        action = classify_legacy_classification(
            str(edge["classification_name"]),
            str(edge["classification_code"]),
            existing_disease_names,
        )
        classification_actions.append({**edge, **action})

    subtype_codes = {
        str(row["target_disease_code"])
        for row in classification_actions
        if row["action"] == "clinical_subtype"
    }
    subtype_codes.update(
        str(row["target_code"])
        for row in structural_relations
        if row["relation_type"] == "has_clinical_subtype"
    )

    converted = convert_structural_relations(
        structural_relations,
        canonical_specialty_code=CANONICAL_SPECIALTY_CODE,
        batch_id=MIGRATION_BATCH_ALL,
        subtype_codes=subtype_codes,
    )
    relation_by_key = {
        (row["source_code"], row["relationType"], row["target_code"]): row
        for row in converted
    }
    for row in classification_actions:
        if row["action"] != "clinical_subtype":
            continue
        allowed_parents = set(row.get("allowed_parent_codes") or [])
        if allowed_parents and row["parent_disease_code"] not in allowed_parents:
            continue
        key = (
            str(row["parent_disease_code"]),
            "has_clinical_subtype",
            str(row["target_disease_code"]),
        )
        relation_by_key[key] = {
            "id": stable_id("REL-V2", *key),
            "source_code": key[0],
            "relationType": key[1],
            "target_code": key[2],
            "batch_id": MIGRATION_BATCH_ALL,
            "schema_version": SCHEMA_VERSION,
            "review_status": "passed",
            "clinical_review_status": "not_required",
        }

    parent_codes = {
        row["source_code"]
        for row in relation_by_key.values()
        if row["relationType"] == "has_clinical_subtype"
    }
    updated_diseases: list[dict[str, Any]] = []
    for props in disease_rows:
        code = str(props["code"])
        aliases = props.get("aliases")
        if not isinstance(aliases, list):
            aliases = [] if aliases in (None, "") else [str(aliases)]
        props.update(
            {
                "aliases": aliases,
                "source_type": props.get("source_type") or "governed_composite",
                "batch_id": MIGRATION_BATCH_ALL,
                "schema_version": SCHEMA_VERSION,
                "clinical_use_status": props.get("clinical_use_status") or "review_ready",
                "is_diagnosable": True,
                "diagnostic_role": (
                    "clinical_subtype"
                    if code in subtype_codes
                    else "broad_diagnosis"
                    if code in parent_codes
                    else "independent_disease"
                ),
            }
        )
        updated_diseases.append(props)

    updated_categories: list[dict[str, Any]] = []
    updated_display_groups: list[dict[str, Any]] = []
    for row in hierarchy_nodes:
        props = dict(row["properties"])
        entity_type = props.get("entityType")
        if entity_type not in {"DiseaseCategory", "DiseaseSubcategory", "Specialty"}:
            continue
        aliases = props.get("aliases")
        if not isinstance(aliases, list):
            aliases = [] if aliases in (None, "") else [str(aliases)]
        props.update(
            {
                "aliases": aliases,
                "source_type": props.get("source_type") or "governed_composite",
                "batch_id": MIGRATION_BATCH_ALL,
                "schema_version": SCHEMA_VERSION,
                "clinical_use_status": props.get("clinical_use_status") or "review_ready",
            }
        )
        if entity_type in {"DiseaseCategory", "DiseaseSubcategory"}:
            props.update({"display_only": True, "is_diagnosable": False, "is_emr_writable": False})
        if entity_type == "Specialty" and props.get("code") != CANONICAL_SPECIALTY_CODE:
            continue
        (updated_display_groups if entity_type == "DiseaseSubcategory" else updated_categories).append(props)

    unresolved = [row for row in classification_actions if row["action"] == "clinical_subtype_candidate"]
    return {
        "scope": "all",
        "batch_id": MIGRATION_BATCH_ALL,
        "upsert_nodes": [*updated_categories, *updated_display_groups, *updated_diseases],
        "upsert_relations": list(relation_by_key.values()),
        "legacy_relations_to_remove": all_legacy_relations,
        "classification_actions": classification_actions,
        "orphan_classification_nodes": orphan_classifications,
        "duplicate_disease_map": MANUAL_DUPLICATE_DISEASE_MAP,
        "unresolved_classifications": unresolved,
        "unresolved_classification_count": len(unresolved),
        "entity_counts_before": dict(
            Counter(str(row["properties"].get("entityType")) for row in hierarchy_nodes)
        ),
    }


def chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def oracle_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    return str(value)


def fetch_oracle_diagnoses_by_names(
    names: set[str],
    *,
    dsn: str,
    user: str,
    password: str,
) -> list[dict[str, Any]]:
    if not names:
        return []
    import oracledb

    selected = sorted(name for name in names if name)
    rows: list[dict[str, Any]] = []
    connection = oracledb.connect(user=user, password=password, dsn=dsn)
    try:
        with connection.cursor() as cursor:
            for part in chunked(selected, 900):
                binds = {f"n{index}": value for index, value in enumerate(part)}
                placeholders = ",".join(f":{key}" for key in binds)
                cursor.execute(
                    f"""
                    SELECT id, code, name, class_code, version, source,
                           sex_limit, age_limit_l, age_limit_h, crb_flag, valid_flag
                      FROM k_icd10_dict
                     WHERE valid_flag = 1
                       AND name IN ({placeholders})
                     ORDER BY name, code, id
                    """,
                    binds,
                )
                columns = [column[0].lower() for column in cursor.description]
                for record in cursor:
                    rows.append(
                        {column: oracle_value(value) for column, value in zip(columns, record)}
                    )
    finally:
        connection.close()
    return rows


def fetch_oracle_diagnoses_by_ids(
    ids: set[str],
    *,
    dsn: str,
    user: str,
    password: str,
) -> list[dict[str, Any]]:
    if not ids:
        return []
    import oracledb

    selected = sorted(ids)
    rows: list[dict[str, Any]] = []
    connection = oracledb.connect(user=user, password=password, dsn=dsn)
    try:
        with connection.cursor() as cursor:
            for part in chunked(selected, 900):
                binds = {f"n{index}": value for index, value in enumerate(part)}
                placeholders = ",".join(f":{key}" for key in binds)
                cursor.execute(
                    f"""
                    SELECT id, code, name, class_code, version, source,
                           sex_limit, age_limit_l, age_limit_h, crb_flag, valid_flag
                      FROM k_icd10_dict
                     WHERE id IN ({placeholders})
                     ORDER BY name, code, id
                    """,
                    binds,
                )
                columns = [column[0].lower() for column in cursor.description]
                for record in cursor:
                    rows.append(
                        {column: oracle_value(value) for column, value in zip(columns, record)}
                    )
    finally:
        connection.close()
    return rows


def standard_diagnosis_node(record: dict[str, Any], batch_id: str) -> dict[str, Any]:
    uuid = str(record["id"])
    return {
        "code": f"STDDX-{uuid}",
        "entityType": "StandardDiagnosis",
        "name": str(record["name"]),
        "aliases": [],
        "source_type": "cdss_standard_dict",
        "batch_id": batch_id,
        "schema_version": SCHEMA_VERSION,
        "clinical_use_status": "clinical_ready",
        "cdss_dict_id": uuid,
        "standard_code": str(record["code"]),
        "coding_system": "ICD-10（诊断）",
        "coding_system_version": record.get("version"),
        "valid_flag": record.get("valid_flag"),
        "source_table": "K_ICD10_DICT",
        "source_version": record.get("version"),
        "source_name": record.get("source"),
        "sex_limit_code": record.get("sex_limit"),
        "sex_limit_name": None,
        "age_min": record.get("age_limit_l"),
        "age_max": record.get("age_limit_h"),
        "age_unit": "岁",
        "pregnancy_limit_code": record.get("crb_flag"),
        "last_sync_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def attach_sample_oracle_verification(
    plan: dict[str, Any],
    *,
    dsn: str,
    user: str,
    password: str,
) -> None:
    standard_nodes = [
        node for node in plan["upsert_nodes"] if node.get("entityType") == "StandardDiagnosis"
    ]
    records = fetch_oracle_diagnoses_by_ids(
        {str(node["cdss_dict_id"]) for node in standard_nodes},
        dsn=dsn,
        user=user,
        password=password,
    )
    by_id = {str(record["id"]): record for record in records}
    differences: list[dict[str, Any]] = []
    for node in standard_nodes:
        record = by_id.get(str(node["cdss_dict_id"]))
        if not record:
            differences.append({"cdss_dict_id": node["cdss_dict_id"], "issue": "Oracle有效记录不存在"})
            continue
        for node_field, oracle_field in (
            ("standard_code", "code"),
            ("name", "name"),
            ("valid_flag", "valid_flag"),
        ):
            if str(node.get(node_field)) != str(record.get(oracle_field)):
                differences.append(
                    {
                        "cdss_dict_id": node["cdss_dict_id"],
                        "field": node_field,
                        "sample_value": node.get(node_field),
                        "oracle_value": record.get(oracle_field),
                    }
                )
    plan["oracle_verification"] = {
        "requested_count": len(standard_nodes),
        "matched_count": len(records),
        "difference_count": len(differences),
        "differences": differences,
        "passed": len(records) == len(standard_nodes) and not differences,
    }


def attach_all_standard_diagnoses(
    plan: dict[str, Any],
    *,
    dsn: str,
    user: str,
    password: str,
) -> None:
    diseases = [node for node in plan["upsert_nodes"] if node.get("entityType") == "Disease"]
    query_names = {str(node.get("name") or "") for node in diseases}
    for node in diseases:
        aliases = node.get("aliases")
        if isinstance(aliases, list):
            query_names.update(str(alias) for alias in aliases if str(alias).strip())
    records = fetch_oracle_diagnoses_by_names(query_names, dsn=dsn, user=user, password=password)
    records_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        records_by_name[str(record["name"])].append(record)

    existing_relation_keys = {
        (row["source_code"], row["relationType"], row["target_code"])
        for row in plan["upsert_relations"]
    }
    standard_nodes: dict[str, dict[str, Any]] = {}
    mapping_rows: list[dict[str, Any]] = []
    unmatched_rows: list[dict[str, Any]] = []
    for disease in diseases:
        disease_code = str(disease["code"])
        disease_name = str(disease["name"])
        matched = list(records_by_name.get(disease_name, []))
        match_type = "标准名称精确匹配"
        if not matched:
            aliases = disease.get("aliases") if isinstance(disease.get("aliases"), list) else []
            alias_candidates: dict[str, dict[str, Any]] = {}
            for alias in aliases:
                for record in records_by_name.get(str(alias), []):
                    alias_candidates[str(record["id"])] = record
            candidate_names = {str(record["name"]) for record in alias_candidates.values()}
            allowed_standard_names = AUTO_ALIAS_STANDARD_NAME_ALLOWLIST.get(disease_code, set())
            if (
                alias_candidates
                and len(candidate_names) == 1
                and candidate_names.issubset(allowed_standard_names)
            ):
                matched = list(alias_candidates.values())
                match_type = "已审核别名精确匹配"
            elif alias_candidates:
                unmatched_rows.append(
                    {
                        "disease_code": disease_code,
                        "disease_name": disease_name,
                        "reason": "别名候选未进入等价白名单，不能自动裁决",
                        "candidate_names": "；".join(sorted(candidate_names)),
                        "handling": "进入标准字典候选匹配队列",
                    }
                )
                disease["is_emr_writable"] = False
                continue
        if not matched:
            disease["is_emr_writable"] = False
            unmatched_rows.append(
                {
                    "disease_code": disease_code,
                    "disease_name": disease_name,
                    "reason": "CDSS有效标准诊断名称未精确命中",
                    "handling": "进入标准字典候选匹配/注册队列，不自动猜测",
                }
            )
            continue
        disease["is_emr_writable"] = True
        for record in matched:
            standard = standard_diagnosis_node(record, MIGRATION_BATCH_ALL)
            standard_nodes[standard["code"]] = standard
            key = (disease_code, "has_standard_diagnosis", standard["code"])
            if key not in existing_relation_keys:
                plan["upsert_relations"].append(
                    {
                        "id": stable_id("REL-V2", *key),
                        "source_code": key[0],
                        "relationType": key[1],
                        "target_code": key[2],
                        "batch_id": MIGRATION_BATCH_ALL,
                        "schema_version": SCHEMA_VERSION,
                        "review_status": "passed",
                        "clinical_review_status": "not_required",
                    }
                )
                existing_relation_keys.add(key)
            mapping_rows.append(
                {
                    "disease_code": disease_code,
                    "disease_name": disease_name,
                    "match_type": match_type,
                    "cdss_dict_id": record["id"],
                    "standard_code": record["code"],
                    "standard_name": record["name"],
                    "valid_flag": record["valid_flag"],
                }
            )

    # 样板中已经过 Oracle UUID 精确核验的多编码映射继续保留。
    for node in load_jsonl(SAMPLE_NODE_FILE):
        if node.get("entityType") == "StandardDiagnosis":
            standard_nodes[str(node["code"])] = node
    for relation in load_jsonl(SAMPLE_RELATION_FILE):
        if relation.get("relationType") != "has_standard_diagnosis":
            continue
        key = (relation["source_code"], relation["relationType"], relation["target_code"])
        if key not in existing_relation_keys:
            plan["upsert_relations"].append(relation)
            existing_relation_keys.add(key)
    sample_standard_by_code = {
        str(node["code"]): node
        for node in load_jsonl(SAMPLE_NODE_FILE)
        if node.get("entityType") == "StandardDiagnosis"
    }
    existing_mapping_pairs = {
        (str(row["disease_code"]), str(row["cdss_dict_id"])) for row in mapping_rows
    }
    for relation in load_jsonl(SAMPLE_RELATION_FILE):
        if relation.get("relationType") != "has_standard_diagnosis":
            continue
        standard = sample_standard_by_code.get(str(relation["target_code"]))
        if not standard:
            continue
        pair = (str(relation["source_code"]), str(standard["cdss_dict_id"]))
        if pair in existing_mapping_pairs:
            continue
        disease = next(
            (item for item in diseases if item["code"] == relation["source_code"]),
            None,
        )
        mapping_rows.append(
            {
                "disease_code": relation["source_code"],
                "disease_name": disease["name"] if disease else "",
                "match_type": "样板UUID精确核验",
                "cdss_dict_id": standard["cdss_dict_id"],
                "standard_code": standard["standard_code"],
                "standard_name": standard["name"],
                "valid_flag": standard["valid_flag"],
            }
        )
        existing_mapping_pairs.add(pair)
    mapped_disease_codes = {
        row["source_code"]
        for row in plan["upsert_relations"]
        if row["relationType"] == "has_standard_diagnosis"
    }
    for disease in diseases:
        if disease["code"] in mapped_disease_codes:
            disease["is_emr_writable"] = True

    unmatched_rows = [
        row for row in unmatched_rows if row["disease_code"] not in mapped_disease_codes
    ]

    plan["upsert_nodes"].extend(standard_nodes.values())
    plan["standard_dictionary_mapping"] = mapping_rows
    plan["dictionary_registration_queue"] = unmatched_rows
    plan["standard_diagnosis_count"] = len(standard_nodes)
    plan["exact_standard_mapping_count"] = len(mapping_rows)
    plan["unmatched_disease_count"] = len(unmatched_rows)


def merge_node(tx: Any, node: dict[str, Any]) -> None:
    entity_type = safe_identifier(str(node["entityType"]))
    if entity_type not in ENTITY_LABELS:
        raise ValueError(f"迁移脚本不允许写入实体类型：{entity_type}")
    props = json_safe(dict(node))
    tx.run(
        "MERGE (n:KGNode {code:$code}) SET n += $props",
        {"code": node["code"], "props": props},
    ).consume()
    tx.run(
        f"MATCH (n:KGNode {{code:$code}}) SET n:`{entity_type}`",
        {"code": node["code"]},
    ).consume()


def merge_relation(tx: Any, relation: dict[str, Any], *, migration_batch_id: str | None = None) -> None:
    relation_type = safe_identifier(str(relation["relationType"]))
    props = json_safe(dict(relation))
    if migration_batch_id:
        props["migration_batch_id"] = migration_batch_id
    result = tx.run(
        f"""
        MATCH (source:KGNode {{code:$source_code}})
        MATCH (target:KGNode {{code:$target_code}})
        MERGE (source)-[r:`{relation_type}`]->(target)
        SET r += $props
        RETURN count(r) AS count
        """,
        {
            "source_code": relation["source_code"],
            "target_code": relation["target_code"],
            "props": props,
        },
    ).single(strict=True)
    if int(result["count"]) != 1:
        raise RuntimeError(f"关系端点缺失或关系重复：{relation}")


def delete_relation(tx: Any, source_code: str, relation_type: str, target_code: str) -> int:
    safe = safe_identifier(relation_type)
    record = tx.run(
        f"""
        MATCH (source:KGNode {{code:$source_code}})-[r:`{safe}`]->(target:KGNode {{code:$target_code}})
        WITH collect(r) AS relationships
        FOREACH (item IN relationships | DELETE item)
        RETURN size(relationships) AS count
        """,
        {"source_code": source_code, "target_code": target_code},
    ).single(strict=True)
    return int(record["count"])


def delete_legacy_relation(tx: Any, relation: dict[str, Any]) -> int:
    """优先按关系内部标识删除，兼容端点 code 为历史列表值的脏数据。"""
    relation_element_id = relation.get("relation_element_id")
    if relation_element_id:
        record = tx.run(
            """
            MATCH ()-[r]->()
            WHERE elementId(r)=$relation_element_id
            DELETE r
            RETURN count(r) AS count
            """,
            {"relation_element_id": relation_element_id},
        ).single(strict=True)
        return int(record["count"])
    return delete_relation(
        tx,
        scalar_endpoint_code(relation.get("source_code")),
        str(relation["relation_type"]),
        scalar_endpoint_code(relation.get("target_code")),
    )


def scalar_endpoint_code(value: Any) -> str:
    """把历史合并产生的列表型编码降为关系审计字段可用的单值编码。"""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def transfer_nonlegacy_relationships(
    tx: Any,
    old_code: str,
    new_code: str,
    *,
    migration_batch_id: str,
) -> int:
    rows = query_rows(
        tx,
        """
        MATCH (source)-[r]->(target)
        WHERE source.code=$old_code OR target.code=$old_code
        RETURN elementId(source) AS source_element_id,
               elementId(target) AS target_element_id,
               source.code AS source_code, target.code AS target_code,
               type(r) AS relation_type, properties(r) AS properties
        """,
        {"old_code": old_code},
    )
    count = 0
    for row in rows:
        relation_type = str(row["relation_type"])
        if relation_type in LEGACY_STRUCTURAL_RELATIONS:
            continue
        source_is_old = row["source_code"] == old_code
        target_is_old = row["target_code"] == old_code
        source_code = new_code if source_is_old else scalar_endpoint_code(row["source_code"])
        target_code = new_code if target_is_old else scalar_endpoint_code(row["target_code"])
        if not source_code or not target_code or source_code == target_code:
            continue
        properties = dict(row.get("properties") or {})
        relation_properties = {
            **properties,
            "source_code": source_code,
            "relationType": relation_type,
            "target_code": target_code,
            "migration_batch_id": migration_batch_id,
        }
        source_match = (
            "MATCH (source:KGNode {code:$new_code})"
            if source_is_old
            else "MATCH (source) WHERE elementId(source)=$source_element_id"
        )
        target_match = (
            "MATCH (target:KGNode {code:$new_code})"
            if target_is_old
            else "MATCH (target) WHERE elementId(target)=$target_element_id"
        )
        safe_relation_type = safe_identifier(relation_type)
        result = tx.run(
            f"""
            {source_match}
            {target_match}
            MERGE (source)-[r:`{safe_relation_type}`]->(target)
            SET r += $props
            RETURN count(r) AS count
            """,
            {
                "new_code": new_code,
                "source_element_id": row["source_element_id"],
                "target_element_id": row["target_element_id"],
                "props": json_safe(relation_properties),
            },
        ).single(strict=True)
        if int(result["count"]) != 1:
            raise RuntimeError(
                f"重复疾病关系转移失败：{old_code} -> {new_code} / {relation_type}"
            )
        count += 1
    return count


def snapshot_before_apply(session: Any, plan: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    classification_codes = {
        str(row["classification_code"]) for row in plan.get("classification_actions", [])
    }
    orphan_classification_codes = {
        str(row["classification_code"])
        for row in plan.get("orphan_classification_nodes", [])
    }
    duplicate_codes = set(plan.get("duplicate_disease_map", {})) | set(
        plan.get("duplicate_disease_map", {}).values()
    )
    upsert_codes = {str(node["code"]) for node in plan["upsert_nodes"]}
    changed_codes = (
        upsert_codes
        | classification_codes
        | orphan_classification_codes
        | duplicate_codes
        | {"CARD", CANONICAL_SPECIALTY_CODE}
    )
    before_nodes = fetch_nodes_by_codes(session, changed_codes)

    all_touching_special = fetch_relationships_touching_codes(
        session,
        classification_codes | duplicate_codes | {"CARD"},
        include_all_types=True,
    )
    structural_before = query_rows(
        session,
        """
        MATCH (source)-[r]->(target)
        WHERE (source.code IN $codes OR target.code IN $codes)
          AND type(r) IN $types
        RETURN source.code AS source_code, target.code AS target_code,
               type(r) AS relation_type, properties(r) AS properties
        ORDER BY source_code, relation_type, target_code
        """,
        {
            "codes": sorted(changed_codes),
            "types": sorted(LEGACY_STRUCTURAL_RELATIONS | ALLOWED_STRUCTURAL_RELATIONS),
        },
    )
    relation_map = {
        (
            str(row["source_code"]),
            str(row["relation_type"]),
            str(row["target_code"]),
            json.dumps(json_safe(row.get("properties") or {}), ensure_ascii=False, sort_keys=True),
        ): row
        for row in [
            *all_touching_special,
            *structural_before,
            *plan.get("legacy_relations_to_remove", []),
        ]
    }
    before_relations = list(relation_map.values())
    rollback_dir = output_dir / "01_写库前回滚包"
    write_jsonl(rollback_dir / "节点_before.jsonl", before_nodes)
    write_jsonl(rollback_dir / "关系_before.jsonl", before_relations)
    snapshot = {
        "migration_batch_id": plan["batch_id"],
        "scope": plan["scope"],
        "changed_code_count": len(changed_codes),
        "existing_node_snapshot_count": len(before_nodes),
        "existing_relationship_snapshot_count": len(before_relations),
        "upsert_node_count": len(plan["upsert_nodes"]),
        "upsert_relationship_count": len(plan["upsert_relations"]),
        "full_database_backup": str(ROOT / "数据库备份_backup" / "20260718_大版本升级前"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    write_json(rollback_dir / "回滚清单_manifest.json", snapshot)
    return snapshot


def apply_classification_actions(tx: Any, plan: dict[str, Any]) -> dict[str, int]:
    stats = Counter()
    grouped: dict[str, dict[str, Any]] = {}
    for row in plan.get("classification_actions", []):
        grouped.setdefault(str(row["classification_code"]), row)

    for classification_code, action in sorted(grouped.items()):
        action_type = str(action["action"])
        parent_rows = query_rows(
            tx,
            """
            MATCH (parent:KGNode {entityType:'Disease'})-[:has_classification]->(classification:KGNode {code:$code})
            RETURN DISTINCT parent.code AS parent_code
            """,
            {"code": classification_code},
        )
        parent_codes = [str(row["parent_code"]) for row in parent_rows]
        allowed_parent_codes = set(action.get("allowed_parent_codes") or [])
        if allowed_parent_codes:
            parent_codes = [code for code in parent_codes if code in allowed_parent_codes]

        if action_type == "clinical_subtype":
            target_code = str(action["target_disease_code"])
            for parent_code in parent_codes:
                if parent_code == target_code:
                    continue
                merge_relation(
                    tx,
                    {
                        "id": stable_id("REL-V2", parent_code, "has_clinical_subtype", target_code),
                        "source_code": parent_code,
                        "relationType": "has_clinical_subtype",
                        "target_code": target_code,
                        "batch_id": plan["batch_id"],
                        "schema_version": SCHEMA_VERSION,
                        "review_status": "passed",
                        "clinical_review_status": "not_required",
                    },
                    migration_batch_id=plan["batch_id"],
                )
            stats["transferred_nonlegacy_relationships"] += transfer_nonlegacy_relationships(
                tx,
                classification_code,
                target_code,
                migration_batch_id=plan["batch_id"],
            )
            tx.run(
                "MATCH (n:KGNode {code:$code}) DETACH DELETE n",
                {"code": classification_code},
            ).consume()
            stats["classification_to_disease"] += 1
            continue

        if action_type == "risk_stratification":
            old_name_row = tx.run(
                "MATCH (n:KGNode {code:$code}) RETURN n.name AS name",
                {"code": classification_code},
            ).single()
            if old_name_row is None:
                continue
            old_name = str(old_name_row["name"] or "")
            new_name = SAMPLE_RISK_RENAMES.get(classification_code, old_name)
            aliases = [] if old_name == new_name else [old_name]
            tx.run(
                """
                MATCH (n:KGNode {code:$code})
                REMOVE n:DiseaseClassification
                SET n:RiskStratification,
                    n.entityType='RiskStratification', n.name=$name,
                    n.aliases=CASE WHEN n.aliases IS NULL THEN $aliases ELSE n.aliases + $aliases END,
                    n.schema_version=$schema_version, n.batch_id=$batch_id,
                    n.source_type=coalesce(n.source_type,'authoritative_textbook'),
                    n.clinical_use_status='review_ready',
                    n.migration_batch_id=$batch_id
                """,
                {
                    "code": classification_code,
                    "name": new_name,
                    "aliases": aliases,
                    "schema_version": SCHEMA_VERSION,
                    "batch_id": plan["batch_id"],
                },
            ).consume()
            for parent_code in parent_codes:
                merge_relation(
                    tx,
                    {
                        "id": stable_id("REL-V2", parent_code, "has_risk_stratification", classification_code),
                        "source_code": parent_code,
                        "relationType": "has_risk_stratification",
                        "target_code": classification_code,
                        "batch_id": plan["batch_id"],
                        "schema_version": SCHEMA_VERSION,
                        "review_status": "passed",
                        "clinical_review_status": "not_required",
                    },
                    migration_batch_id=plan["batch_id"],
                )
            stats["classification_to_risk"] += 1
            continue

        if action_type == "invalid_fragment":
            evidence_rows = query_rows(
                tx,
                """
                MATCH (classification:KGNode {code:$code})-[r:supported_by_evidence]->(evidence:KGNode)
                RETURN evidence.code AS evidence_code, properties(r) AS properties
                """,
                {"code": classification_code},
            )
            for parent_code in parent_codes:
                for evidence in evidence_rows:
                    relation = {
                        **dict(evidence.get("properties") or {}),
                        "id": stable_id("REL-V2", parent_code, "supported_by_evidence", str(evidence["evidence_code"])),
                        "source_code": parent_code,
                        "relationType": "supported_by_evidence",
                        "target_code": str(evidence["evidence_code"]),
                        "batch_id": plan["batch_id"],
                        "schema_version": SCHEMA_VERSION,
                    }
                    merge_relation(tx, relation, migration_batch_id=plan["batch_id"])
            tx.run(
                "MATCH (n:KGNode {code:$code}) DETACH DELETE n",
                {"code": classification_code},
            ).consume()
            stats["classification_fragment_deleted"] += 1
            continue

        raise RuntimeError(f"存在未处理的旧分型：{classification_code} / {action_type}")
    return dict(stats)


def consolidate_duplicate_diseases(tx: Any, duplicate_map: dict[str, str], batch_id: str) -> dict[str, int]:
    stats = Counter()
    for old_code, canonical_code in duplicate_map.items():
        exists = query_scalar(
            tx,
            "MATCH (n:KGNode {code:$code}) RETURN count(n) AS value",
            parameters={"code": old_code},
        )
        if not exists:
            continue
        stats["transferred_relationships"] += transfer_nonlegacy_relationships(
            tx,
            old_code,
            canonical_code,
            migration_batch_id=batch_id,
        )
        tx.run("MATCH (n:KGNode {code:$code}) DETACH DELETE n", {"code": old_code}).consume()
        stats["deleted_duplicate_diseases"] += 1
    return dict(stats)


def apply_plan(session: Any, plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("unresolved_classification_count", 0):
        raise RuntimeError(
            f"仍有 {plan['unresolved_classification_count']} 个疾病型旧分型未裁定，禁止写库"
        )
    if plan.get("package_audit") and not plan["package_audit"].get("passed"):
        raise RuntimeError("样板包本地审计未通过，禁止写库")
    if plan.get("oracle_verification") and not plan["oracle_verification"].get("passed"):
        raise RuntimeError("样板标准诊断与 Oracle 有效字典不一致，禁止写库")

    duplicate_code_count = query_scalar(
        session,
        """
        MATCH (n:KGNode)
        WHERE n.code IS NOT NULL
        WITH n.code AS code, count(*) AS count
        WHERE count > 1
        RETURN count(*) AS value
        """,
    )
    if duplicate_code_count:
        raise RuntimeError(f"服务器存在 {duplicate_code_count} 组重复 code，禁止迁移")

    stats = Counter()
    for node in plan["upsert_nodes"]:
        merge_node(session, node)
        stats["upsert_nodes"] += 1
    for relation in plan["upsert_relations"]:
        merge_relation(session, relation, migration_batch_id=plan["batch_id"])
        stats["upsert_relations"] += 1

    classification_stats = apply_classification_actions(session, plan)
    orphan_codes = [
        str(row["classification_code"])
        for row in plan.get("orphan_classification_nodes", [])
    ]
    if orphan_codes:
        orphan_record = session.run(
            """
            MATCH (n:KGNode {entityType:'DiseaseClassification'})
            WHERE n.code IN $codes
            WITH collect(n) AS nodes
            FOREACH (n IN nodes | DETACH DELETE n)
            RETURN size(nodes) AS count
            """,
            {"codes": orphan_codes},
        ).single(strict=True)
        stats["deleted_orphan_classification_nodes"] = int(orphan_record["count"])
    duplicate_stats = consolidate_duplicate_diseases(
        session,
        plan.get("duplicate_disease_map", {}),
        plan["batch_id"],
    )

    for old in plan["legacy_relations_to_remove"]:
        stats["deleted_legacy_relations"] += delete_legacy_relation(session, old)

    if plan["scope"] == "all":
        # 旧根节点所有目录关系已迁移到标准根节点后，物理删除空壳重复根。
        tx_record = session.run(
            """
            MATCH (old:KGNode {code:'CARD'})
            OPTIONAL MATCH (old)-[r]-()
            WITH old, count(r) AS relation_count
            FOREACH (_ IN CASE WHEN relation_count=0 THEN [1] ELSE [] END | DELETE old)
            RETURN relation_count
            """
        ).single()
        stats["duplicate_specialty_remaining_relations"] = (
            int(tx_record["relation_count"]) if tx_record else 0
        )

    return {
        "batch_id": plan["batch_id"],
        "scope": plan["scope"],
        "stats": dict(stats),
        "classification_stats": classification_stats,
        "duplicate_stats": duplicate_stats,
        "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def postcheck(session: Any, scope: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(metric: str, chinese_name: str, cypher: str, parameters: dict[str, Any] | None = None) -> None:
        value = query_scalar(session, cypher, parameters=parameters)
        checks.append(
            {
                "metric": metric,
                "chinese_name": chinese_name,
                "value": value,
                "passed": value == 0,
            }
        )

    if scope == "sample":
        add(
            "sample_legacy_relation_count",
            "AMI与心肌病仍有旧层级关系",
            """
            MATCH (source)-[r]->(target)
            WHERE type(r) IN $legacy_types
              AND (
                source.code IN $disease_codes OR target.code IN $disease_codes
                OR (type(r)='has_category' AND target.code IN $category_codes)
              )
            RETURN count(r) AS value
            """,
            {
                "legacy_types": sorted(LEGACY_STRUCTURAL_RELATIONS),
                "disease_codes": sorted(SAMPLE_DISEASE_CODES),
                "category_codes": sorted(SAMPLE_CATEGORY_CODES),
            },
        )
        add(
            "sample_missing_core_relation_count",
            "AMI与心肌病缺少核心层级关系",
            """
            UNWIND [
              ['SPEC-CARD','has_disease_category','CAT-CARD-CAD'],
              ['SPEC-CARD','has_disease_category','CAT-CARD-CM'],
              ['CAT-CARD-CAD','has_disease','DIS-CARD-CAD-AMI'],
              ['DIS-CARD-CAD-AMI','has_clinical_subtype','DIS-CARD-CAD-STEMI'],
              ['DIS-CARD-CAD-AMI','has_clinical_subtype','DIS-CARD-CAD-NSTEMI'],
              ['CAT-CARD-CM','has_disease','DIS-CARD-CM-GENERAL'],
              ['DIS-CARD-CM-GENERAL','has_clinical_subtype','DIS-CARD-CM-HCM'],
              ['DIS-CARD-CM-GENERAL','has_clinical_subtype','DIS-CARD-CM-DCM']
            ] AS item
            OPTIONAL MATCH (source:KGNode {code:item[0]})-[r]->(target:KGNode {code:item[2]})
            WHERE type(r)=item[1]
            WITH item, count(r) AS relation_count
            WHERE relation_count=0
            RETURN count(*) AS value
            """,
        )
        add(
            "sample_missing_standard_diagnosis_count",
            "AMI与心肌病可回填疾病缺少标准诊断",
            """
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE d.code IN $disease_codes AND d.is_emr_writable=true
              AND NOT (d)-[:has_standard_diagnosis]->(:KGNode {entityType:'StandardDiagnosis', valid_flag:1})
            RETURN count(d) AS value
            """,
            {"disease_codes": sorted(SAMPLE_DISEASE_CODES)},
        )
        add(
            "sample_duplicate_classification_node_count",
            "AMI重复分型节点仍残留",
            """
            MATCH (n:KGNode)
            WHERE n.code IN ['CLASS-CARD-CAD-AMI-STEMI','CLASS-CARD-CAD-AMI-NSTEMI']
            RETURN count(n) AS value
            """,
        )
        add(
            "sample_invalid_classification_remaining_count",
            "AMI与心肌病旧分型实体仍被使用",
            """
            MATCH (d:KGNode {entityType:'Disease'})-[:has_classification]->(:KGNode)
            WHERE d.code IN $disease_codes
            RETURN count(*) AS value
            """,
            {"disease_codes": sorted(SAMPLE_DISEASE_CODES)},
        )
    else:
        add(
            "legacy_structural_relation_count",
            "全库仍有V1旧层级关系",
            "MATCH ()-[r]->() WHERE type(r) IN $types RETURN count(r) AS value",
            {"types": sorted(LEGACY_STRUCTURAL_RELATIONS)},
        )
        add(
            "disease_classification_node_count",
            "全库仍有旧疾病分型节点",
            "MATCH (n:KGNode {entityType:'DiseaseClassification'}) RETURN count(n) AS value",
        )
        add(
            "duplicate_specialty_root_count",
            "心血管内科重复根节点",
            "MATCH (n:KGNode {entityType:'Specialty'}) WHERE n.name='心血管内科' AND n.code<>'SPEC-CARD' RETURN count(n) AS value",
        )
        add(
            "category_without_specialty_count",
            "疾病大类未挂顶层学科",
            """
            MATCH (c:KGNode {entityType:'DiseaseCategory'})
            WHERE NOT (:KGNode {entityType:'Specialty'})-[:has_disease_category]->(c)
            RETURN count(c) AS value
            """,
        )
        add(
            "disease_without_parent_count",
            "疾病既无大类也无父疾病",
            """
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE coalesce(d.status,'active') <> 'deprecated'
              AND coalesce(d.deprecated,false)=false
              AND NOT (:KGNode {entityType:'DiseaseCategory'})-[:has_disease]->(d)
              AND NOT (:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->(d)
            RETURN count(d) AS value
            """,
        )
        add(
            "clinical_subtype_without_parent_count",
            "临床分型无父疾病",
            """
            MATCH (d:KGNode {entityType:'Disease', diagnostic_role:'clinical_subtype'})
            WHERE NOT (:KGNode {entityType:'Disease'})-[:has_clinical_subtype]->(d)
            RETURN count(d) AS value
            """,
        )
        add(
            "disease_subtype_cycle_count",
            "疾病分型形成循环",
            """
            MATCH p=(d:KGNode {entityType:'Disease'})-[:has_clinical_subtype*1..10]->(d)
            RETURN count(p) AS value
            """,
        )
        add(
            "duplicate_active_disease_name_count",
            "正式疾病同名重复",
            """
            MATCH (d:KGNode {entityType:'Disease'})
            WHERE coalesce(d.status,'active') <> 'deprecated'
              AND coalesce(d.deprecated,false)=false
              AND d.duplicate_replaced_by IS NULL
            WITH d.name AS name, count(DISTINCT d.code) AS count
            WHERE count>1
            RETURN count(*) AS value
            """,
        )
        add(
            "diagnosable_category_count",
            "疾病大类被错误标记为可诊断",
            "MATCH (n:KGNode {entityType:'DiseaseCategory', is_diagnosable:true}) RETURN count(n) AS value",
        )
        add(
            "display_group_not_display_only_count",
            "展示分组被误作诊断",
            """
            MATCH (n:KGNode {entityType:'DiseaseSubcategory'})
            WHERE coalesce(n.display_only,false)<>true OR coalesce(n.is_diagnosable,false)=true
            RETURN count(n) AS value
            """,
        )
        add(
            "emr_writable_without_standard_diagnosis_count",
            "可回填疾病缺少有效标准诊断",
            """
            MATCH (d:KGNode {entityType:'Disease', is_emr_writable:true})
            WHERE NOT (d)-[:has_standard_diagnosis]->(:KGNode {entityType:'StandardDiagnosis', valid_flag:1})
            RETURN count(d) AS value
            """,
        )
        add(
            "invalid_standard_diagnosis_count",
            "标准诊断不是有效字典记录",
            """
            MATCH (n:KGNode {entityType:'StandardDiagnosis'})
            WHERE n.cdss_dict_id IS NULL OR n.standard_code IS NULL OR n.name IS NULL
               OR toString(n.valid_flag)<>'1' OR n.source_table<>'K_ICD10_DICT'
            RETURN count(n) AS value
            """,
        )
        add(
            "duplicate_standard_diagnosis_uuid_count",
            "标准诊断UUID重复",
            """
            MATCH (n:KGNode {entityType:'StandardDiagnosis'})
            WITH n.cdss_dict_id AS uuid, count(DISTINCT n.code) AS count
            WHERE uuid IS NOT NULL AND count>1
            RETURN count(*) AS value
            """,
        )
        add(
            "duplicate_structural_relation_count",
            "V2层级关系重复",
            """
            MATCH (source)-[r]->(target)
            WHERE type(r) IN $types
            WITH source.code AS source_code, type(r) AS relation_type,
                 target.code AS target_code, count(r) AS count
            WHERE count>1
            RETURN count(*) AS value
            """,
            {"types": sorted(ALLOWED_STRUCTURAL_RELATIONS)},
        )

    blocking_count = sum(not check["passed"] for check in checks)
    return {
        "scope": scope,
        "check_count": len(checks),
        "blocking_count": blocking_count,
        "passed": blocking_count == 0,
        "checks": checks,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_plan_outputs(plan: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "00_迁移计划摘要.json", {
        key: value
        for key, value in plan.items()
        if key not in {"upsert_nodes", "upsert_relations", "legacy_relations_to_remove"}
    })
    write_jsonl(output_dir / "01_待写入节点.jsonl", plan["upsert_nodes"])
    write_jsonl(output_dir / "02_待写入关系.jsonl", plan["upsert_relations"])
    write_json(output_dir / "03_待删除旧关系.json", plan["legacy_relations_to_remove"])
    write_csv(output_dir / "04_旧分型处置清单.csv", plan.get("classification_actions", []))
    write_csv(
        output_dir / "04B_孤立旧分型清理清单.csv",
        plan.get("orphan_classification_nodes", []),
    )
    if "standard_dictionary_mapping" in plan:
        write_csv(output_dir / "05_标准诊断映射.csv", plan["standard_dictionary_mapping"])
        write_csv(output_dir / "06_标准诊断未命中队列.csv", plan["dictionary_registration_queue"])


def default_output_dir(scope: str) -> Path:
    folder = "11_AMI与心肌病样板迁移" if scope == "sample" else "12_全部疾病迁移"
    return PROJECT_DIR / folder


def main() -> int:
    parser = argparse.ArgumentParser(description="疾病层级与标准诊断 V2.0 受控迁移")
    parser.add_argument("--scope", choices=("sample", "all"), required=True)
    parser.add_argument("--mode", choices=("plan", "apply", "postcheck"), default="plan")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--oracle-dsn", default=os.environ.get("CDSS_ORACLE_DSN"))
    parser.add_argument("--oracle-user", default=os.environ.get("CDSS_ORACLE_USER"))
    parser.add_argument("--oracle-password-env", default="CDSS_ORACLE_PASSWORD")
    args = parser.parse_args()

    output_dir = (args.output_dir or default_output_dir(args.scope)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    parse_connection_file = load_connection_parser()
    connection = parse_connection_file(args.connection_file.resolve())
    driver = GraphDatabase.driver(
        connection["uri"], auth=(connection["username"], connection["password"])
    )
    try:
        driver.verify_connectivity()
        with driver.session(database="neo4j") as session:
            if args.mode == "postcheck":
                report = postcheck(session, args.scope)
                write_json(output_dir / "09_服务器迁移后复核.json", report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0 if report["passed"] else 2

            plan = build_sample_plan(session) if args.scope == "sample" else build_all_plan(session)
            oracle_password = os.environ.get(args.oracle_password_env)
            if not args.oracle_dsn or not args.oracle_user or not oracle_password:
                raise RuntimeError(
                    "缺少 Oracle 只读连接环境变量：CDSS_ORACLE_DSN、CDSS_ORACLE_USER、CDSS_ORACLE_PASSWORD"
                )
            if args.scope == "sample":
                attach_sample_oracle_verification(
                    plan,
                    dsn=args.oracle_dsn,
                    user=args.oracle_user,
                    password=oracle_password,
                )
            else:
                attach_all_standard_diagnoses(
                    plan,
                    dsn=args.oracle_dsn,
                    user=args.oracle_user,
                    password=oracle_password,
                )
            save_plan_outputs(plan, output_dir)

            if args.mode == "plan":
                print(
                    json.dumps(
                        {
                            "scope": args.scope,
                            "mode": "plan",
                            "upsert_node_count": len(plan["upsert_nodes"]),
                            "upsert_relationship_count": len(plan["upsert_relations"]),
                            "legacy_relation_remove_count": len(plan["legacy_relations_to_remove"]),
                            "classification_action_count": len(plan["classification_actions"]),
                            "unresolved_classification_count": plan.get("unresolved_classification_count", 0),
                            "oracle_verification": plan.get("oracle_verification"),
                            "unmatched_disease_count": plan.get("unmatched_disease_count"),
                            "output_dir": str(output_dir),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0 if not plan.get("unresolved_classification_count", 0) else 2

            rollback = snapshot_before_apply(session, plan, output_dir)

            def apply_and_validate(tx: Any) -> tuple[dict[str, Any], dict[str, Any]]:
                """同一事务内写入并复核；任一硬闸门失败时整批自动撤销。"""
                result = apply_plan(tx, plan)
                in_transaction_validation = postcheck(tx, args.scope)
                if not in_transaction_validation["passed"]:
                    failed = [
                        {
                            "中文指标": check["chinese_name"],
                            "问题数量": check["value"],
                        }
                        for check in in_transaction_validation["checks"]
                        if not check["passed"]
                    ]
                    raise RuntimeError(
                        "迁移后硬闸门未通过，当前事务已自动撤销："
                        + json.dumps(failed, ensure_ascii=False)
                    )
                return result, in_transaction_validation

            # 全量迁移需要处理历史关系转移与去重，显式放宽事务时限；
            # 仍坚持单事务，避免拆批后留下“迁了一半”的服务器状态。
            with session.begin_transaction(timeout=600) as tx:
                try:
                    write_result, transaction_validation = apply_and_validate(tx)
                    tx.commit()
                except Exception:
                    tx.rollback()
                    raise
            # 事务提交后再以独立只读查询复核一次，防止提交前后状态差异。
            validation = postcheck(session, args.scope)
            write_json(output_dir / "07_写库执行结果.json", write_result)
            write_json(output_dir / "08_回滚包摘要.json", rollback)
            write_json(output_dir / "09_事务内硬闸门复核.json", transaction_validation)
            write_json(output_dir / "09_服务器迁移后复核.json", validation)
            summary = {
                "scope": args.scope,
                "mode": "apply",
                "write_result": write_result,
                "validation": validation,
                "output_dir": str(output_dir),
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0 if validation["passed"] else 3
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
