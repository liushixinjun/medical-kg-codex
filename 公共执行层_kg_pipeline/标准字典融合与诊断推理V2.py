from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import unicodedata
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import oracledb
from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORACLE_DSN = "192.168.4.25:1521/ORCL"
DEFAULT_ORACLE_USER = "zycdss"
MODEL_VERSION = "DIAG-EFFECT-V2.0-20260721"
DICT_SOURCE = "专科知识图谱V2.0（教材、指南及CDSS二次校验）"

ENTITY_TABLES: dict[str, str] = {
    "Symptom": "K_SYMPTOM_DICT",
    "Sign": "K_CLINICAL_SIGN_DICT",
    "ExamItem": "K_EXAM_ITEM_DICT",
    "ExamObservation": "K_EXAM_OBSERVATION_DICT",
    "LabItem": "K_LAB_ITEM_DICT",
    "LabSubitem": "K_LAB_SUBITEM_DICT",
    "Medication": "K_DRUG_DICT",
    "TreatmentItem": "K_TREATMENT_DICT",
}

OBSERVATION_ALIASES = {
    "左室射血分数": "左心室射血分数",
    "延迟钆增强": "钆延迟增强",
}

VITAL_SIGN_ITEMS = [
    ("SMTZ000001", "体温", "℃", "TEMPERATURE"),
    ("SMTZ000002", "心率", "次/分", "HEART_RATE"),
    ("SMTZ000003", "脉搏", "次/分", "PULSE"),
    ("SMTZ000004", "呼吸频率", "次/分", "RESPIRATION"),
    ("SMTZ000005", "收缩压", "mmHg", "SYSTOLIC_PRESSURE"),
    ("SMTZ000006", "舒张压", "mmHg", "DIASTOLIC_PRESSURE"),
    ("SMTZ000007", "血氧饱和度", "%", "OXYGEN_SATURATION"),
]


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, oracledb.LOB):
        return value.read()
    return value


def connect_oracle() -> oracledb.Connection:
    password = os.environ.get("CDSS_ORACLE_PASSWORD")
    if not password:
        raise RuntimeError("缺少环境变量 CDSS_ORACLE_PASSWORD，未连接 Oracle")
    return oracledb.connect(
        user=os.environ.get("CDSS_ORACLE_USER", DEFAULT_ORACLE_USER),
        password=password,
        dsn=os.environ.get("CDSS_ORACLE_DSN", DEFAULT_ORACLE_DSN),
    )


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(data), ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in data:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().upper()
    text = re.sub(r"[\s\-—_·•,，、;；:：/\\()（）\[\]【】]+", "", text)
    return text


def parse_aliases(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = list(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            raw = parsed if isinstance(parsed, list) else [stripped]
        except json.JSONDecodeError:
            raw = re.split(r"[、,，;；|]", stripped)
    else:
        raw = [value]
    result: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def merge_aliases(*values: Any, exclude: str | None = None) -> list[str]:
    result: list[str] = []
    excluded = normalize_name(exclude)
    for value in values:
        for alias in parse_aliases(value):
            if normalize_name(alias) == excluded:
                continue
            if alias not in result:
                result.append(alias)
    return result


def stable_id(namespace: str, value: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"medical-kg:{namespace}:{normalize_name(value)}").hex


def text_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length].upper()


def is_composite_sign(name: str) -> tuple[bool, str]:
    text = name.strip()
    if not text:
        return True, "空名称"
    if text.endswith("体征") or text.endswith("表现"):
        return True, "疾病概括体征或表现，不是原子体征"
    if "或" in text or "与" in text and len(text) > 10:
        return True, "复合体征，应拆分为原子项或规则"
    wrong_type = {
        "靶器官损害",
        "心功能不全",
        "肺水肿",
        "肺淤血",
        "胸腔积液",
        "左心室肥厚",
        "室壁增厚与心电低电压不匹配",
        "血脂异常体征",
        "高胆固醇血症体征",
    }
    if text in wrong_type:
        return True, "更适合并发症、检查发现或临床规则，不注册为标准体征"
    return False, ""


def is_rule_observation(name: str) -> tuple[bool, str]:
    text = name.strip()
    if not text:
        return True, "空名称"
    if "提示" in text:
        return True, "包含推理结论，应迁移为临床规则"
    if text in {"发病时间", "家族遗传证据", "病原体证据"}:
        return True, "不是检查观察结果"
    return False, ""


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    bolt = re.search(r"bolt(?:\+s|\+ssc)?://[^\s；;，,]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s；;，,]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s；;，,]+)", text, re.I)
    if not bolt or not password:
        raise ValueError(f"无法从连接文件解析 Bolt 地址或密码：{path}")
    return {
        "uri": bolt.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def one(session, query: str, **params: Any) -> Any:
    record = session.run(query, **params).single()
    return record.data() if record else None


def rows(session, query: str, **params: Any) -> list[dict[str, Any]]:
    return [record.data() for record in session.run(query, **params)]


def inventory(session) -> dict[str, Any]:
    entity_counts = rows(
        session,
        """
        MATCH (n:KGNode)
        RETURN coalesce(n.entityType, head([label IN labels(n) WHERE label <> 'KGNode'])) AS entity_type,
               count(*) AS node_count
        ORDER BY node_count DESC, entity_type
        """,
    )
    relation_counts = rows(
        session,
        """
        MATCH ()-[r]->()
        RETURN type(r) AS relation_type, count(*) AS relation_count
        ORDER BY relation_count DESC, relation_type
        """,
    )
    target_types = [
        "Disease",
        "StandardDiagnosis",
        "Symptom",
        "Sign",
        "Exam",
        "ExamIndicator",
        "LabTest",
        "LabIndicator",
        "Medication",
        "Procedure",
        "StandardProcedure",
        "TreatmentPlan",
        "TreatmentItem",
    ]
    target_samples: dict[str, list[dict[str, Any]]] = {}
    for entity_type in target_types:
        target_samples[entity_type] = rows(
            session,
            """
            MATCH (n:KGNode)
            WHERE n.entityType = $entity_type OR $entity_type IN labels(n)
            RETURN labels(n) AS labels, properties(n) AS properties
            ORDER BY coalesce(n.name, n.display_name, n.code)
            LIMIT 5
            """,
            entity_type=entity_type,
        )
    clinical_relation_samples = rows(
        session,
        """
        MATCH (d:Disease)-[r]->(x:KGNode)
        WHERE x.entityType IN ['Symptom','Sign','ExamIndicator','LabIndicator']
           OR any(label IN labels(x) WHERE label IN ['Symptom','Sign','ExamIndicator','LabIndicator'])
        OPTIONAL MATCH (x)-[]-(e:Evidence)
        RETURN d.code AS disease_code, d.name AS disease_name,
               type(r) AS relation_type, properties(r) AS relation_properties,
               x.entityType AS target_type, x.code AS target_code, x.name AS target_name,
               count(e) AS evidence_count
        ORDER BY evidence_count DESC, disease_name, target_name
        LIMIT 80
        """,
    )
    sign_candidates = rows(
        session,
        """
        MATCH (s:KGNode)
        WHERE s.entityType = 'Sign' OR 'Sign' IN labels(s)
        OPTIONAL MATCH (d:Disease)-[r]->(s)
        OPTIONAL MATCH (s)-[]-(e:Evidence)
        RETURN s.code AS code, s.name AS name, s.aliases AS aliases,
               count(DISTINCT d) AS disease_count, count(DISTINCT e) AS disease_evidence_count,
               collect(DISTINCT type(r))[0..10] AS relation_types
        ORDER BY disease_count DESC, name
        """,
    )
    observation_candidates = rows(
        session,
        """
        MATCH (n:KGNode)
        WHERE n.entityType = 'ExamObservation' OR 'ExamObservation' IN labels(n)
        OPTIONAL MATCH (d:Disease)-[r]->(n)
        RETURN n.code AS code, n.name AS name, n.aliases AS aliases,
               count(DISTINCT d) AS disease_count, collect(DISTINCT type(r))[0..10] AS relation_types
        ORDER BY disease_count DESC, name
        """,
    )
    diagnostic_links = rows(
        session,
        """
        MATCH (d:Disease)-[r]->(x:KGNode)
        WHERE x.entityType IN ['Symptom','Sign'] OR any(label IN labels(x) WHERE label IN ['Symptom','Sign'])
        RETURN elementId(r) AS relation_element_id,
               d.code AS disease_code, d.name AS disease_name, d.diagnostic_role AS diagnostic_role,
               type(r) AS relation_type, x.entityType AS finding_type, x.code AS finding_code,
               x.name AS finding_name, properties(r) AS relation_properties
        ORDER BY disease_name, finding_type, finding_name
        """,
    )
    return {
        "summary": {
            "node_count": one(session, "MATCH (n) RETURN count(n) AS value")["value"],
            "relationship_count": one(session, "MATCH ()-[r]->() RETURN count(r) AS value")["value"],
            "sign_count": len(sign_candidates),
            "exam_observation_count": len(observation_candidates),
            "diagnostic_finding_links": len(diagnostic_links),
        },
        "entity_counts": entity_counts,
        "relation_counts": relation_counts,
        "target_samples": target_samples,
        "clinical_relation_samples": clinical_relation_samples,
        "sign_candidates": sign_candidates,
        "exam_observation_candidates": observation_candidates,
        "diagnostic_finding_links": diagnostic_links,
    }


def oracle_rows(cursor: oracledb.Cursor, table: str) -> list[dict[str, Any]]:
    cursor.execute(
        f'SELECT ID, CODE, NAME FROM "{table}" WHERE VALID_FLAG = 1'
    )
    return [
        {"id": str(row[0]), "code": str(row[1] or ""), "name": str(row[2] or "")}
        for row in cursor
    ]


def graph_nodes(session, entity_type: str) -> list[dict[str, Any]]:
    return rows(
        session,
        """
        MATCH (n:KGNode)
        WHERE n.entityType = $entity_type OR $entity_type IN labels(n)
        RETURN elementId(n) AS element_id, properties(n) AS properties,
               size([(n)--() | 1]) AS degree
        ORDER BY coalesce(n.name, n.display_name, n.code)
        """,
        entity_type=entity_type,
    )


def build_indexes(data: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    by_code: dict[str, list[dict[str, Any]]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for row in data:
        by_id[str(row["id"]).upper()] = row
        name_key = normalize_name(row.get("name"))
        code_key = normalize_name(row.get("code"))
        if name_key:
            by_name.setdefault(name_key, []).append(row)
        if code_key:
            by_code.setdefault(code_key, []).append(row)
    return by_name, by_code, by_id


def match_graph_node(
    node: dict[str, Any],
    table_rows: list[dict[str, Any]] | None = None,
    indexes: tuple[
        dict[str, list[dict[str, Any]]],
        dict[str, list[dict[str, Any]]],
        dict[str, dict[str, Any]],
    ] | None = None,
) -> dict[str, Any]:
    props = node["properties"]
    if indexes is None:
        if table_rows is None:
            raise ValueError("缺少字典数据或预建索引")
        indexes = build_indexes(table_rows)
    by_name, by_code, by_id = indexes
    source_id = str(props.get("source_dict_id") or props.get("cdss_dict_id") or "").upper()
    if source_id and source_id in by_id:
        return {"status": "matched", "match_type": "source_dict_id", "target": by_id[source_id], "confidence": 1.0}
    candidate_codes = [
        props.get("dictionary_code"),
        props.get("cdss_dict_code"),
        props.get("standard_code"),
    ]
    raw_code = str(props.get("code") or "")
    if raw_code and not raw_code.startswith(("DIS-", "SYM-", "SIGN-", "EXAM-", "LAB-", "MED-", "PROC-", "TRT-")):
        candidate_codes.append(raw_code)
    for code in candidate_codes:
        key = normalize_name(code)
        matches = by_code.get(key, [])
        if len(matches) == 1:
            return {"status": "matched", "match_type": "code", "target": matches[0], "confidence": 1.0}
        if len(matches) > 1:
            return {"status": "ambiguous", "match_type": "code", "targets": matches, "confidence": 0.0}
    names = [props.get("name"), props.get("display_name"), props.get("preferred_name"), *parse_aliases(props.get("aliases"))]
    seen: set[str] = set()
    for index, name in enumerate(names):
        key = normalize_name(name)
        if not key or key in seen:
            continue
        seen.add(key)
        matches = by_name.get(key, [])
        if len(matches) == 1:
            return {
                "status": "matched",
                "match_type": "name" if index == 0 else "alias",
                "target": matches[0],
                "confidence": 1.0 if index == 0 else 0.98,
            }
        if len(matches) > 1:
            return {"status": "ambiguous", "match_type": "name", "targets": matches, "confidence": 0.0}
    return {"status": "unmatched", "match_type": "none", "confidence": 0.0}


def make_new_dictionary_rows(inventory_data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    sign_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    aliases_by_canonical: dict[str, list[str]] = {}
    accepted_signs: list[dict[str, Any]] = []
    for item in inventory_data["sign_candidates"]:
        name = str(item.get("name") or "").strip()
        rejected, reason = is_composite_sign(name)
        if rejected:
            review_rows.append({
                "id": stable_id("review-sign", name),
                "entity_type": "Sign",
                "kg_node_code": item.get("code"),
                "kg_node_name": name,
                "target_table": "K_CLINICAL_SIGN_DICT",
                "issue_type": "WRONG_TYPE_OR_COMPOSITE",
                "reason": reason,
                "proposed_value": json.dumps({"action": "reclassify_or_decompose"}, ensure_ascii=False),
            })
            continue
        accepted_signs.append(item)
    for index, item in enumerate(sorted(accepted_signs, key=lambda row: normalize_name(row.get("name"))), start=100001):
        name = str(item["name"]).strip()
        sign_rows.append({
            "id": stable_id("K_CLINICAL_SIGN_DICT", name),
            "code": f"TZ{index:06d}",
            "name": name,
            "version": "V2.0",
            "source": DICT_SOURCE,
            "valid_flag": 1,
            "sort_no": index,
            "remark": f"由图谱体征二次校验注册；原图谱编码={item.get('code') or ''}",
        })
    canonical_observations: dict[str, dict[str, Any]] = {}
    for item in inventory_data["exam_observation_candidates"]:
        original_name = str(item.get("name") or "").strip()
        rejected, reason = is_rule_observation(original_name)
        if rejected:
            review_rows.append({
                "id": stable_id("review-observation", original_name),
                "entity_type": "ExamObservation",
                "kg_node_code": item.get("code"),
                "kg_node_name": original_name,
                "target_table": "K_EXAM_OBSERVATION_DICT",
                "issue_type": "RULE_OR_WRONG_TYPE",
                "reason": reason,
                "proposed_value": json.dumps({"action": "move_to_clinical_rule"}, ensure_ascii=False),
            })
            continue
        canonical_name = OBSERVATION_ALIASES.get(original_name, original_name)
        key = normalize_name(canonical_name)
        canonical_observations.setdefault(key, {**item, "name": canonical_name})
        if canonical_name != original_name:
            aliases_by_canonical.setdefault(canonical_name, []).append(original_name)
    for index, item in enumerate(sorted(canonical_observations.values(), key=lambda row: normalize_name(row.get("name"))), start=100001):
        name = str(item["name"]).strip()
        aliases = aliases_by_canonical.get(name, [])
        remark = f"由图谱检查发现二次校验注册；原图谱编码={item.get('code') or ''}"
        if aliases:
            remark += f"；别名={','.join(aliases)}"
        observation_rows.append({
            "id": stable_id("K_EXAM_OBSERVATION_DICT", name),
            "code": f"JCGC{index:06d}",
            "name": name,
            "version": "V2.0",
            "source": DICT_SOURCE,
            "valid_flag": 1,
            "sort_no": index,
            "remark": remark,
        })
    vital_rows = [
        {
            "id": stable_id("K_VITAL_SIGN_ITEM_DICT", name),
            "code": code,
            "name": name,
            "unit": unit,
            "value_type": "NUMBER",
            "version": "V2.0",
            "source": "CDSS既有生命体征阈值配置与临床常用生命体征二次校验",
            "valid_flag": 1,
            "sort_no": index,
            "remark": f"兼容既有K_SIGN_DICT类型：{legacy_type}",
        }
        for index, (code, name, unit, legacy_type) in enumerate(VITAL_SIGN_ITEMS, start=1)
    ]
    return sign_rows, observation_rows, vital_rows, review_rows


def local_evidence_context(text: str, finding_name: str, radius: int = 140) -> tuple[str, bool]:
    if not text or not finding_name:
        return "", False
    index = text.find(finding_name)
    if index < 0:
        aliases = parse_aliases(finding_name)
        for alias in aliases:
            index = text.find(alias)
            if index >= 0:
                break
    if index < 0:
        return "", False
    start = max(0, index - radius)
    end = min(len(text), index + len(finding_name) + radius)
    return text[start:end], True


def classify_diagnostic_effect(relation_properties: dict[str, Any], finding_name: str) -> dict[str, Any]:
    text = str(relation_properties.get("evidence_text") or "")
    context, mentioned = local_evidence_context(text, finding_name)
    source_section = str(relation_properties.get("source_section") or "")
    conflict = str(relation_properties.get("conflict_status") or "none").lower()
    approved = str(relation_properties.get("review_status") or "").lower() in {"approved", "validated", "clinical_ready"}
    if not mentioned:
        return {
            "effect_code": "UNSET",
            "weight_level": 0,
            "score_enabled": 0,
            "required_flag": 0,
            "method": "RELATION_ONLY_UNSCORED",
            "confidence": 0.4,
            "context": "",
        }
    required_patterns = ["必须", "必要条件", "诊断标准", "确诊需", "不可缺少"]
    strong_patterns = ["特征性", "典型", "最常见", "主要症状", "主要体征", "多数患者", "大多数患者"]
    support_patterns = ["常见", "多见", "表现为", "伴有", "可见", "可有", "出现"]
    if source_section in {"diagnosis", "diagnostic_criteria"} and any(word in context for word in required_patterns):
        effect_code, level, required = "REQUIRED", 3, 1
    elif any(word in context for word in strong_patterns):
        effect_code, level, required = "STRONG_SUPPORT", 3, 0
    elif any(word in context for word in support_patterns):
        effect_code, level, required = "SUPPORT", 2, 0
    else:
        effect_code, level, required = "WEAK_SUPPORT", 1, 0
    enabled = int(conflict in {"", "none"} and approved and level >= 2)
    confidence = 0.95 if enabled and level == 3 else 0.88 if enabled else 0.7
    return {
        "effect_code": effect_code,
        "weight_level": level,
        "score_enabled": enabled,
        "required_flag": required,
        "method": "EXPLICIT_TEXT_WINDOW",
        "confidence": confidence,
        "context": context,
    }


def fetch_standard_diagnoses(session) -> dict[str, str]:
    data = rows(
        session,
        """
        MATCH (d:Disease)-[:has_standard_diagnosis]->(s:StandardDiagnosis)
        WHERE coalesce(s.valid_flag, 1) = 1
        RETURN d.code AS disease_code, collect(DISTINCT coalesce(s.cdss_dict_id, s.id))[0] AS dict_id
        """,
    )
    return {str(row["disease_code"]): str(row["dict_id"]) for row in data if row.get("disease_code") and row.get("dict_id")}


def fetch_exam_observation_links(session) -> list[dict[str, Any]]:
    return rows(
        session,
        """
        MATCH (exam:KGNode)-[r]-(observation:KGNode)
        WHERE (exam.entityType = 'ExamItem' OR 'ExamItem' IN labels(exam))
          AND (observation.entityType = 'ExamObservation' OR 'ExamObservation' IN labels(observation))
        RETURN exam.code AS exam_code, exam.name AS exam_name,
               observation.code AS observation_code, observation.name AS observation_name,
               type(r) AS relation_type, properties(r) AS relation_properties
        ORDER BY exam_name, observation_name
        """,
    )


def build_collision_groups(mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in mapping_rows:
        grouped.setdefault((str(row["entity_type"]), str(row["dict_id"])), []).append(row)
    result: list[dict[str, Any]] = []
    for (entity_type, dict_id), items in grouped.items():
        if len(items) < 2:
            continue
        ordered = sorted(
            items,
            key=lambda item: (
                -int(item.get("degree") or 0),
                0 if normalize_name(item.get("kg_name")) == normalize_name(item.get("dict_name")) else 1,
                str(item.get("kg_code") or ""),
            ),
        )
        result.append({
            "entity_type": entity_type,
            "dict_id": dict_id,
            "dict_code": ordered[0].get("dict_code"),
            "dict_name": ordered[0].get("dict_name"),
            "canonical_element_id": ordered[0]["element_id"],
            "duplicate_element_ids": [item["element_id"] for item in ordered[1:]],
            "node_count": len(ordered),
        })
    return result


def write_review_preview(path: Path, rows_data: list[dict[str, Any]]) -> None:
    payload = json.dumps(json_safe(rows_data), ensure_ascii=False).replace("</", "<\\/")
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oracle现有字典变更预览</title>
<style>
body{{font-family:"Microsoft YaHei",sans-serif;margin:0;background:#f4f6f8;color:#1f2937}}header{{padding:18px 24px;background:#15395b;color:#fff}}
main{{padding:18px 24px}}.toolbar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}}input,select,button{{padding:8px;border:1px solid #cbd5e1;border-radius:6px}}
table{{width:100%;border-collapse:collapse;background:#fff;font-size:13px}}th,td{{border:1px solid #e2e8f0;padding:7px;vertical-align:top}}th{{background:#eaf2f8;position:sticky;top:0}}
.tag{{padding:2px 6px;border-radius:10px;background:#fff3cd}}.summary{{margin:10px 0;font-weight:600}}
</style></head><body><header><h2>Oracle现有字典变更预览（第二批候选）</h2><div>本页面只用于评审；第一批未修改任何既有Oracle字典表。</div></header>
<main><div class="toolbar"><input id="q" placeholder="搜索名称、问题或原因"><select id="type"><option value="">全部问题</option></select><select id="entity"><option value="">全部实体</option></select><button id="export">导出当前CSV</button></div><div class="summary" id="summary"></div><table><thead><tr><th>实体类型</th><th>图谱名称</th><th>目标表</th><th>问题</th><th>当前值</th><th>建议值</th><th>原因</th></tr></thead><tbody id="body"></tbody></table></main>
<script>const rows={payload};const q=document.querySelector('#q'),type=document.querySelector('#type'),entity=document.querySelector('#entity'),body=document.querySelector('#body');
function options(el,key){{[...new Set(rows.map(x=>x[key]).filter(Boolean))].sort().forEach(v=>{{const o=document.createElement('option');o.value=v;o.textContent=v;el.appendChild(o)}})}}options(type,'issue_type');options(entity,'entity_type');
function filtered(){{const s=q.value.trim().toLowerCase();return rows.filter(x=>(!type.value||x.issue_type===type.value)&&(!entity.value||x.entity_type===entity.value)&&(!s||JSON.stringify(x).toLowerCase().includes(s)))}}
function render(){{const data=filtered();document.querySelector('#summary').textContent=`当前 ${{data.length}} 条 / 共 ${{rows.length}} 条`;body.innerHTML=data.map(x=>`<tr><td>${{x.entity_type||''}}</td><td>${{x.kg_node_name||''}}</td><td>${{x.target_table||''}}</td><td><span class="tag">${{x.issue_type||''}}</span></td><td>${{x.current_value||''}}</td><td>${{x.proposed_value||''}}</td><td>${{x.reason||''}}</td></tr>`).join('')}}
[q,type,entity].forEach(x=>x.addEventListener('input',render));document.querySelector('#export').onclick=()=>{{const data=filtered(),keys=['entity_type','kg_node_code','kg_node_name','target_table','issue_type','current_value','proposed_value','reason'];const csv='\\ufeff'+[keys.join(','),...data.map(r=>keys.map(k=>'"'+String(r[k]||'').replaceAll('"','""')+'"').join(','))].join('\\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));a.download='Oracle现有字典变更候选.csv';a.click()}};render();</script></body></html>"""
    path.write_text(html, encoding="utf-8")


def build_term_mappings(cursor: oracledb.Cursor, mapped_targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cursor.execute("SELECT ID, TERM_NAME, BACK_UP_NAME FROM K_TERM WHERE VALID_FLAG = 1")
    term_by_name: dict[str, list[dict[str, str]]] = {}
    for term_id, term_name, back_up_name in cursor:
        values = [str(term_name or ""), *parse_aliases(back_up_name)]
        for value in values:
            key = normalize_name(value)
            if key:
                term_by_name.setdefault(key, []).append({"id": str(term_id), "name": str(term_name or "")})
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for target in mapped_targets:
        key = normalize_name(target.get("dict_name"))
        matches = term_by_name.get(key, [])
        unique_ids = {item["id"] for item in matches}
        if len(unique_ids) != 1:
            continue
        term = matches[0]
        row_key = (term["id"], str(target["dict_table"]), str(target["dict_id"]))
        result[row_key] = {
            "id": stable_id("K_TERM_DICT_MAPPING", "|".join(row_key)),
            "term_id": term["id"],
            "dict_table": target["dict_table"],
            "dict_id": target["dict_id"],
            "dict_code": target.get("dict_code"),
            "dict_name": target.get("dict_name"),
            "match_type": "EXACT_UNIQUE_NAME",
            "match_status": "VALIDATED",
            "match_confidence": 1.0,
            "source": "K_TERM与CDSS标准字典唯一同名匹配",
            "valid_flag": 1,
            "remark": f"术语名称={term['name']}",
        }
    return list(result.values())


def yaml_alias_reviews(output_rows: list[dict[str, Any]], mapped_targets: list[dict[str, Any]]) -> None:
    try:
        import yaml
    except ImportError:
        return
    target_by_name = {normalize_name(item.get("kg_name")): item for item in mapped_targets if item.get("kg_name")}
    target_by_name.update({normalize_name(item.get("dict_name")): item for item in mapped_targets if item.get("dict_name")})
    yaml_dir = ROOT / "术语字典"
    for path in sorted(yaml_dir.glob("*.yaml")):
        if path.name.startswith("9_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            canonical = str(item.get("canonical") or "").strip()
            target = target_by_name.get(normalize_name(canonical))
            if not target:
                continue
            aliases = [alias for alias in parse_aliases(item.get("aliases")) if normalize_name(alias) != normalize_name(canonical)]
            if not aliases:
                continue
            output_rows.append({
                "id": stable_id("yaml-alias-review", f"{path.name}|{canonical}"),
                "entity_type": target.get("entity_type"),
                "kg_node_code": target.get("kg_code"),
                "kg_node_name": target.get("kg_name"),
                "target_table": target.get("dict_table"),
                "target_id": target.get("dict_id"),
                "target_code": target.get("dict_code"),
                "target_name": target.get("dict_name"),
                "issue_type": "ALIAS_TO_TERM_CANDIDATE",
                "current_value": json.dumps({"source_yaml": path.name}, ensure_ascii=False),
                "proposed_value": json.dumps({"aliases": aliases}, ensure_ascii=False),
                "reason": "本地术语字典已沉淀别名，待第二批写入既有K_TERM/K_TERM_SYNONYM",
                "source": str(path),
            })


def build_plan(session, cursor: oracledb.Cursor, output_dir: Path) -> dict[str, Any]:
    inventory_data = inventory(session)
    sign_rows, observation_rows, vital_rows, review_rows = make_new_dictionary_rows(inventory_data)
    all_dictionary_rows: dict[str, list[dict[str, Any]]] = {}
    for entity_type, table in ENTITY_TABLES.items():
        if table == "K_CLINICAL_SIGN_DICT":
            table_rows = sign_rows
        elif table == "K_EXAM_OBSERVATION_DICT":
            table_rows = observation_rows
        else:
            table_rows = oracle_rows(cursor, table)
        all_dictionary_rows[entity_type] = table_rows
    mapping_rows: list[dict[str, Any]] = []
    node_updates: list[dict[str, Any]] = []
    node_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for entity_type, table in ENTITY_TABLES.items():
        table_rows = all_dictionary_rows[entity_type]
        table_indexes = build_indexes(table_rows)
        for node in graph_nodes(session, entity_type):
            props = node["properties"]
            match = match_graph_node(node, indexes=table_indexes)
            base = {
                "element_id": node["element_id"],
                "entity_type": entity_type,
                "kg_code": props.get("code"),
                "kg_name": props.get("name"),
                "kg_aliases": merge_aliases(props.get("aliases"), props.get("name")),
                "degree": node.get("degree") or 0,
                "dict_table": table,
                "status": match["status"],
                "match_type": match["match_type"],
                "match_confidence": match["confidence"],
            }
            if match["status"] == "matched":
                target = match["target"]
                row = {
                    **base,
                    "dict_id": target["id"],
                    "dict_code": target["code"],
                    "dict_name": target["name"],
                }
                mapping_rows.append(row)
                node_updates.append(row)
                if props.get("code"):
                    node_lookup[(entity_type, str(props["code"]))] = row
                if props.get("name"):
                    node_lookup[(entity_type, str(props["name"]))] = row
            else:
                targets = match.get("targets", [])
                review_rows.append({
                    "id": stable_id("dict-match-review", f"{entity_type}|{props.get('code')}|{props.get('name')}"),
                    "entity_type": entity_type,
                    "kg_node_code": props.get("code"),
                    "kg_node_name": props.get("name"),
                    "target_table": table,
                    "issue_type": "AMBIGUOUS_MATCH" if match["status"] == "ambiguous" else "MISSING_IN_EXISTING_DICTIONARY",
                    "current_value": json.dumps({"aliases": parse_aliases(props.get("aliases"))}, ensure_ascii=False),
                    "proposed_value": json.dumps(targets, ensure_ascii=False),
                    "reason": "现有Oracle字典未能唯一匹配；第一批不修改既有字典",
                    "source": "Neo4j图谱与Oracle有效字典只读比对",
                })
    collision_groups = build_collision_groups(mapping_rows)
    term_mapping_rows = build_term_mappings(cursor, mapping_rows)
    yaml_alias_reviews(review_rows, mapping_rows)
    exam_observation_rows: list[dict[str, Any]] = []
    for link in fetch_exam_observation_links(session):
        exam = node_lookup.get(("ExamItem", str(link.get("exam_code") or ""))) or node_lookup.get(("ExamItem", str(link.get("exam_name") or "")))
        observation = node_lookup.get(("ExamObservation", str(link.get("observation_code") or ""))) or node_lookup.get(("ExamObservation", str(link.get("observation_name") or "")))
        if not exam or not observation:
            continue
        properties = link.get("relation_properties") or {}
        evidence_id = properties.get("evidence_id")
        if not evidence_id:
            evidence_ids = properties.get("evidence_ids") or []
            evidence_id = evidence_ids[0] if evidence_ids else None
        row_key = f"{exam['dict_id']}|{observation['dict_id']}"
        exam_observation_rows.append({
            "id": stable_id("K_EXAM_OBSERVATION_REL", row_key),
            "exam_item_id": exam["dict_id"],
            "observation_id": observation["dict_id"],
            "source": "专科知识图谱显式检查项目—检查发现关系",
            "evidence_id": evidence_id,
            "valid_flag": 1,
            "remark": f"原关系类型={link.get('relation_type') or ''}",
        })
    exam_observation_rows = list({row["id"]: row for row in exam_observation_rows}.values())
    standard_diagnoses = fetch_standard_diagnoses(session)
    rule_rows: list[dict[str, Any]] = []
    rule_item_rows: list[dict[str, Any]] = []
    diagnostic_links = inventory_data["diagnostic_finding_links"]
    diseases: dict[str, dict[str, Any]] = {}
    for link in diagnostic_links:
        disease_code = str(link.get("disease_code") or "")
        if not disease_code:
            continue
        diseases.setdefault(disease_code, link)
    for disease_code, item in sorted(diseases.items()):
        rule_id = stable_id("K_DIAGNOSIS_RULE", disease_code)
        diagnosis_dict_id = standard_diagnoses.get(disease_code)
        rule_rows.append({
            "id": rule_id,
            "disease_node_code": disease_code,
            "disease_name": item.get("disease_name"),
            "diagnosis_dict_id": diagnosis_dict_id,
            "rule_name": f"{item.get('disease_name')}疑似诊断初筛规则",
            "rule_scope": "SUSPECTED_DIAGNOSIS",
            "rule_version": "V2.0",
            "status": "ACTIVE" if diagnosis_dict_id else "KNOWLEDGE_ONLY",
            "effect_model_version": MODEL_VERSION,
            "source": "教材与指南症状/体征关系自动初始化",
            "valid_flag": 1,
            "remark": "仅用于疑似疾病排序，不替代确诊与分型" if diagnosis_dict_id else "尚未绑定标准诊断，仅保留知识展示，不参与自动排序",
        })
    for link in diagnostic_links:
        disease_code = str(link.get("disease_code") or "")
        finding_type = str(link.get("finding_type") or "")
        finding_code = str(link.get("finding_code") or "")
        finding_name = str(link.get("finding_name") or "")
        if not disease_code or not finding_name:
            continue
        mapping = node_lookup.get((finding_type, finding_code)) or node_lookup.get((finding_type, finding_name))
        effect = classify_diagnostic_effect(link.get("relation_properties") or {}, finding_name)
        props = link.get("relation_properties") or {}
        evidence_id = props.get("evidence_id")
        if not evidence_id:
            evidence_ids = props.get("evidence_ids") or []
            evidence_id = evidence_ids[0] if evidence_ids else None
        item_id = stable_id("K_DIAGNOSIS_RULE_ITEM", f"{disease_code}|{finding_type}|{finding_code or finding_name}")
        diagnosis_dict_id = standard_diagnoses.get(disease_code)
        score_enabled = int(bool(effect["score_enabled"] and mapping and diagnosis_dict_id and evidence_id and effect["context"]))
        rule_item_rows.append({
            "id": item_id,
            "rule_id": stable_id("K_DIAGNOSIS_RULE", disease_code),
            "relation_element_id": link.get("relation_element_id"),
            "finding_type": finding_type.upper(),
            "finding_dict_table": mapping.get("dict_table") if mapping else None,
            "finding_dict_id": mapping.get("dict_id") if mapping else None,
            "finding_code": mapping.get("dict_code") if mapping else finding_code,
            "finding_name": mapping.get("dict_name") if mapping else finding_name,
            "effect_code": effect["effect_code"],
            "weight_level": effect["weight_level"],
            "score_enabled": score_enabled,
            "trigger_operator": "PRESENT",
            "required_flag": effect["required_flag"],
            "negation_policy": "NO_SCORE",
            "extraction_confidence": effect["confidence"],
            "initialization_method": effect["method"],
            "source_evidence_id": evidence_id,
            "source_text": effect["context"],
            "manual_override": 0,
            "review_status": "AUTO_ENABLED" if score_enabled else "AUTO_UNSCORED",
            "valid_flag": 1,
            "remark": "自动初始化；人工维护时仅覆盖本条规则项",
        })
    model_row = {
        "id": stable_id("K_DIAGNOSIS_RULE_VERSION", MODEL_VERSION),
        "model_version": MODEL_VERSION,
        "model_name": "专科CDSS疑似疾病诊断作用等级模型V2.0",
        "score_matrix": json.dumps({
            "REQUIRED": {"level": 3, "score": 3, "meaning": "必要或强制条件"},
            "STRONG_SUPPORT": {"level": 3, "score": 3, "meaning": "强支持"},
            "SUPPORT": {"level": 2, "score": 2, "meaning": "一般支持"},
            "WEAK_SUPPORT": {"level": 1, "score": 1, "meaning": "弱支持，默认不启用自动计分"},
            "AGAINST": {"level": 2, "score": -2, "meaning": "反对证据"},
            "EXCLUDE": {"hard_stop": True, "meaning": "排除条件"},
            "UNSET": {"level": 0, "score": 0, "meaning": "仅有关联，未形成诊断作用"},
        }, ensure_ascii=False),
        "status": "ACTIVE",
        "release_time": datetime.now(),
        "source": "教材与指南显式措辞初始化；大模型不得自行发明数值",
        "valid_flag": 1,
        "remark": "运行时分值由版本矩阵解释，图谱关系仅保存作用等级",
    }
    plan = {
        "summary": {
            "sign_candidates": len(inventory_data["sign_candidates"]),
            "registered_signs": len(sign_rows),
            "exam_observation_candidates": len(inventory_data["exam_observation_candidates"]),
            "registered_exam_observations": len(observation_rows),
            "vital_sign_items": len(vital_rows),
            "graph_dictionary_mappings": len(mapping_rows),
            "duplicate_mapping_groups": len(collision_groups),
            "term_dictionary_mappings": len(term_mapping_rows),
            "exam_observation_relations": len(exam_observation_rows),
            "review_items": len(review_rows),
            "diagnosis_rules": len(rule_rows),
            "diagnosis_rule_items": len(rule_item_rows),
            "scored_rule_items": sum(int(row["score_enabled"]) for row in rule_item_rows),
        },
        "sign_rows": sign_rows,
        "observation_rows": observation_rows,
        "vital_rows": vital_rows,
        "graph_mapping_rows": mapping_rows,
        "node_updates": node_updates,
        "collision_groups": collision_groups,
        "term_mapping_rows": term_mapping_rows,
        "exam_observation_rows": exam_observation_rows,
        "review_rows": review_rows,
        "rule_rows": rule_rows,
        "rule_item_rows": rule_item_rows,
        "model_row": model_row,
    }
    write_json(output_dir / "02_标准字典融合与诊断作用初始化计划.json", plan)
    write_csv(output_dir / "03_图谱实体标准字典匹配.csv", mapping_rows)
    write_csv(output_dir / "04_Oracle现有字典变更待审清单.csv", review_rows)
    write_csv(output_dir / "05_诊断作用初始化明细.csv", rule_item_rows)
    write_csv(output_dir / "06_图谱重复主数据自动合并计划.csv", collision_groups)
    write_review_preview(output_dir / "Oracle现有字典变更预览_20260722.html", review_rows)
    return plan


def unique_rows(rows_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list({str(row["id"]): row for row in rows_data}.values())


def merge_oracle_rows(
    cursor: oracledb.Cursor,
    table: str,
    rows_data: list[dict[str, Any]],
    columns: list[str],
    touch_modify_time: bool = True,
) -> int:
    data = unique_rows(rows_data)
    if not data:
        return 0
    aliases = [column.lower() for column in columns]
    source_columns = ", ".join(f":{alias} {column}" for alias, column in zip(aliases, columns))
    updates = [column for column in columns if column != "ID"]
    update_sql = ", ".join(f"target.{column} = source.{column}" for column in updates)
    insert_columns = ", ".join(columns)
    insert_values = ", ".join(f"source.{column}" for column in columns)
    matched_update = update_sql + (", target.MODIFY_TIME = SYSDATE" if touch_modify_time else "")
    sql = f"""
        MERGE INTO {table} target
        USING (SELECT {source_columns} FROM dual) source
           ON (target.ID = source.ID)
        WHEN MATCHED THEN UPDATE SET {matched_update}
        WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})
    """
    binds = [{alias: row.get(alias) for alias in aliases} for row in data]
    cursor.executemany(sql, binds)
    return len(data)


def apply_oracle_plan(connection: oracledb.Connection, plan: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    cursor = connection.cursor()
    counts: dict[str, int] = {}
    try:
        counts["K_CLINICAL_SIGN_DICT"] = merge_oracle_rows(
            cursor, "K_CLINICAL_SIGN_DICT", plan["sign_rows"],
            ["ID", "CODE", "NAME", "VERSION", "SOURCE", "VALID_FLAG", "SORT_NO", "REMARK"],
        )
        counts["K_EXAM_OBSERVATION_DICT"] = merge_oracle_rows(
            cursor, "K_EXAM_OBSERVATION_DICT", plan["observation_rows"],
            ["ID", "CODE", "NAME", "VERSION", "SOURCE", "VALID_FLAG", "SORT_NO", "REMARK"],
        )
        counts["K_VITAL_SIGN_ITEM_DICT"] = merge_oracle_rows(
            cursor, "K_VITAL_SIGN_ITEM_DICT", plan["vital_rows"],
            ["ID", "CODE", "NAME", "UNIT", "VALUE_TYPE", "VERSION", "SOURCE", "VALID_FLAG", "SORT_NO", "REMARK"],
        )
        counts["K_EXAM_OBSERVATION_REL"] = merge_oracle_rows(
            cursor, "K_EXAM_OBSERVATION_REL", plan.get("exam_observation_rows", []),
            ["ID", "EXAM_ITEM_ID", "OBSERVATION_ID", "SOURCE", "EVIDENCE_ID", "VALID_FLAG", "REMARK"],
        )
        counts["K_TERM_DICT_MAPPING"] = merge_oracle_rows(
            cursor, "K_TERM_DICT_MAPPING", plan["term_mapping_rows"],
            ["ID", "TERM_ID", "DICT_TABLE", "DICT_ID", "DICT_CODE", "DICT_NAME", "MATCH_TYPE", "MATCH_STATUS", "MATCH_CONFIDENCE", "SOURCE", "VALID_FLAG", "REMARK"],
        )
        review_rows = [
            {
                **row,
                "review_status": row.get("review_status") or "PENDING",
                "execution_status": row.get("execution_status") or "NOT_EXECUTED",
                "valid_flag": row.get("valid_flag", 1),
                "remark": row.get("remark"),
            }
            for row in plan["review_rows"]
        ]
        counts["K_KG_DICT_CHANGE_REVIEW"] = merge_oracle_rows(
            cursor, "K_KG_DICT_CHANGE_REVIEW", review_rows,
            ["ID", "ENTITY_TYPE", "KG_NODE_CODE", "KG_NODE_NAME", "TARGET_TABLE", "TARGET_ID", "TARGET_CODE", "TARGET_NAME", "ISSUE_TYPE", "CURRENT_VALUE", "PROPOSED_VALUE", "REASON", "SOURCE", "REVIEW_STATUS", "EXECUTION_STATUS", "VALID_FLAG", "REMARK"],
        )
        counts["K_DIAGNOSIS_RULE"] = merge_oracle_rows(
            cursor, "K_DIAGNOSIS_RULE", plan["rule_rows"],
            ["ID", "DISEASE_NODE_CODE", "DISEASE_NAME", "DIAGNOSIS_DICT_ID", "RULE_NAME", "RULE_SCOPE", "RULE_VERSION", "STATUS", "EFFECT_MODEL_VERSION", "SOURCE", "VALID_FLAG", "REMARK"],
        )
        counts["K_DIAGNOSIS_RULE_ITEM"] = merge_oracle_rows(
            cursor, "K_DIAGNOSIS_RULE_ITEM", plan["rule_item_rows"],
            ["ID", "RULE_ID", "FINDING_TYPE", "FINDING_DICT_TABLE", "FINDING_DICT_ID", "FINDING_CODE", "FINDING_NAME", "EFFECT_CODE", "WEIGHT_LEVEL", "SCORE_ENABLED", "TRIGGER_OPERATOR", "TRIGGER_VALUE", "UNIT", "REQUIRED_FLAG", "NEGATION_POLICY", "EXTRACTION_CONFIDENCE", "INITIALIZATION_METHOD", "SOURCE_EVIDENCE_ID", "SOURCE_TEXT", "MANUAL_OVERRIDE", "REVIEW_STATUS", "VALID_FLAG", "REMARK"],
        )
        model_row = dict(plan["model_row"])
        if isinstance(model_row.get("release_time"), str):
            model_row["release_time"] = datetime.fromisoformat(model_row["release_time"])
        counts["K_DIAGNOSIS_RULE_VERSION"] = merge_oracle_rows(
            cursor, "K_DIAGNOSIS_RULE_VERSION", [model_row],
            ["ID", "MODEL_VERSION", "MODEL_NAME", "SCORE_MATRIX", "STATUS", "RELEASE_TIME", "SOURCE", "VALID_FLAG", "REMARK"],
        )
        log_row = {
            "id": stable_id("K_DIAGNOSIS_RULE_LOG", f"BATCH-20260722|{MODEL_VERSION}"),
            "rule_id": None,
            "rule_item_id": None,
            "action_type": "BATCH_INITIALIZE",
            "before_value": None,
            "after_value": json.dumps(plan["summary"], ensure_ascii=False),
            "operator_id": "CODEX",
            "operator_name": "专科知识图谱自动化流程",
            "action_time": datetime.now(),
            "remark": "只写新增表；未修改Oracle既有字典",
        }
        counts["K_DIAGNOSIS_RULE_LOG"] = merge_oracle_rows(
            cursor, "K_DIAGNOSIS_RULE_LOG", [log_row],
            ["ID", "RULE_ID", "RULE_ITEM_ID", "ACTION_TYPE", "BEFORE_VALUE", "AFTER_VALUE", "OPERATOR_ID", "OPERATOR_NAME", "ACTION_TIME", "REMARK"],
            touch_modify_time=False,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
    result = {"written_or_updated": counts, "existing_oracle_tables_modified": False}
    write_json(output_dir / "07_Oracle新增表写入结果.json", result)
    return result


def safe_relation_type(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"非法关系类型：{value}")
    return value


def merge_duplicate_node(tx, canonical_id: str, duplicate_id: str) -> dict[str, int]:
    exists = tx.run(
        "MATCH (duplicate) WHERE elementId(duplicate) = $duplicate_id RETURN count(duplicate) AS total",
        duplicate_id=duplicate_id,
    ).single()["total"]
    if not exists:
        return {"copied_relationships": 0, "deleted_nodes": 0}
    outgoing = rows(
        tx,
        """
        MATCH (duplicate)-[r]->(target)
        WHERE elementId(duplicate) = $duplicate_id
        RETURN elementId(target) AS other_id, type(r) AS relation_type, properties(r) AS properties
        """,
        duplicate_id=duplicate_id,
    )
    incoming = rows(
        tx,
        """
        MATCH (source)-[r]->(duplicate)
        WHERE elementId(duplicate) = $duplicate_id
        RETURN elementId(source) AS other_id, type(r) AS relation_type, properties(r) AS properties
        """,
        duplicate_id=duplicate_id,
    )
    copied = 0
    for relation in outgoing:
        if relation["other_id"] in {canonical_id, duplicate_id}:
            continue
        relation_type = safe_relation_type(str(relation["relation_type"]))
        tx.run(
            f"""
            MATCH (canonical), (target)
            WHERE elementId(canonical) = $canonical_id AND elementId(target) = $other_id
            MERGE (canonical)-[r:`{relation_type}`]->(target)
            SET r += $properties
            """,
            canonical_id=canonical_id,
            other_id=relation["other_id"],
            properties=relation["properties"] or {},
        ).consume()
        copied += 1
    for relation in incoming:
        if relation["other_id"] in {canonical_id, duplicate_id}:
            continue
        relation_type = safe_relation_type(str(relation["relation_type"]))
        tx.run(
            f"""
            MATCH (source), (canonical)
            WHERE elementId(source) = $other_id AND elementId(canonical) = $canonical_id
            MERGE (source)-[r:`{relation_type}`]->(canonical)
            SET r += $properties
            """,
            canonical_id=canonical_id,
            other_id=relation["other_id"],
            properties=relation["properties"] or {},
        ).consume()
        copied += 1
    tx.run(
        "MATCH (duplicate) WHERE elementId(duplicate) = $duplicate_id DETACH DELETE duplicate",
        duplicate_id=duplicate_id,
    ).consume()
    return {"copied_relationships": copied, "deleted_nodes": 1}


def apply_graph_plan(driver, plan: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    node_rows = []
    for row in plan["node_updates"]:
        node_rows.append({
            **row,
            "aliases": merge_aliases(row.get("kg_aliases"), row.get("kg_name"), exclude=str(row.get("dict_name") or "")),
        })
    relation_rows = [
        {
            "relation_element_id": row["relation_element_id"],
            "diagnostic_effect_code": row["effect_code"],
            "diagnostic_weight_level": row["weight_level"],
            "diagnostic_score_enabled": row["score_enabled"],
            "diagnostic_rule_item_id": row["id"],
            "diagnostic_model_version": MODEL_VERSION,
            "source_evidence_id": row.get("source_evidence_id"),
            "diagnostic_initialization_method": row["initialization_method"],
            "diagnostic_review_status": row["review_status"],
        }
        for row in plan["rule_item_rows"]
    ]
    rule_rows = [
        {
            "disease_code": row["disease_node_code"],
            "diagnosis_rule_id": row["id"],
            "diagnosis_rule_status": row["status"],
            "diagnosis_effect_model_version": row["effect_model_version"],
        }
        for row in plan["rule_rows"]
    ]

    def write_transaction(tx):
        tx.run(
            """
            UNWIND $rows AS row
            MATCH ()-[r]->() WHERE elementId(r) = row.relation_element_id
            SET r.diagnostic_effect_code = row.diagnostic_effect_code,
                r.diagnostic_weight_level = row.diagnostic_weight_level,
                r.diagnostic_score_enabled = row.diagnostic_score_enabled,
                r.diagnostic_rule_item_id = row.diagnostic_rule_item_id,
                r.diagnostic_model_version = row.diagnostic_model_version,
                r.source_evidence_id = row.source_evidence_id,
                r.diagnostic_initialization_method = row.diagnostic_initialization_method,
                r.diagnostic_review_status = row.diagnostic_review_status,
                r.updated_at = datetime()
            """,
            rows=relation_rows,
        ).consume()
        copied_relationships = 0
        deleted_nodes = 0
        for group in plan.get("collision_groups", []):
            canonical_id = group["canonical_element_id"]
            for duplicate_id in group["duplicate_element_ids"]:
                stats = merge_duplicate_node(tx, canonical_id, duplicate_id)
                copied_relationships += stats["copied_relationships"]
                deleted_nodes += stats["deleted_nodes"]
        tx.run(
            """
            UNWIND $rows AS row
            MATCH (n) WHERE elementId(n) = row.element_id
            SET n.kg_code = coalesce(n.kg_code, n.code),
                n.name = row.dict_name,
                n.display_name = row.dict_name,
                n.preferred_name = row.dict_name,
                n.aliases = row.aliases,
                n.source_dict_id = row.dict_id,
                n.cdss_dict_id = row.dict_id,
                n.dictionary_code = row.dict_code,
                n.standard_code = row.dict_code,
                n.dictionary_source_table = row.dict_table,
                n.source_table = row.dict_table,
                n.dictionary_status = 'validated',
                n.dictionary_match_type = row.match_type,
                n.dictionary_match_confidence = row.match_confidence,
                n.standard_data_version = 'V2.0',
                n.updated_at = datetime()
            """,
            rows=node_rows,
        ).consume()
        tx.run(
            """
            UNWIND $rows AS row
            MATCH (d:Disease {code: row.disease_code})
            SET d.diagnosis_rule_id = row.diagnosis_rule_id,
                d.diagnosis_rule_status = row.diagnosis_rule_status,
                d.diagnosis_effect_model_version = row.diagnosis_effect_model_version,
                d.updated_at = datetime()
            """,
            rows=rule_rows,
        ).consume()
        return {"copied_relationships": copied_relationships, "deleted_duplicate_nodes": deleted_nodes}

    with driver.session(database="neo4j") as session:
        duplicate_result = session.execute_write(write_transaction)
    result = {
        "dictionary_node_updates_planned": len(node_rows),
        "diagnostic_relation_updates_planned": len(relation_rows),
        "disease_rule_updates_planned": len(rule_rows),
        **duplicate_result,
    }
    write_json(output_dir / "08_Neo4j标准字典与诊断作用写入结果.json", result)
    return result


def oracle_postcheck(connection: oracledb.Connection, plan: dict[str, Any]) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        tables = [
            "K_CLINICAL_SIGN_DICT", "K_EXAM_OBSERVATION_DICT", "K_VITAL_SIGN_ITEM_DICT",
            "K_EXAM_OBSERVATION_REL", "K_TERM_DICT_MAPPING", "K_KG_DICT_CHANGE_REVIEW",
            "K_DIAGNOSIS_RULE", "K_DIAGNOSIS_RULE_ITEM", "K_DIAGNOSIS_RULE_VERSION", "K_DIAGNOSIS_RULE_LOG",
        ]
        counts: dict[str, int] = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE VALID_FLAG = 1" if table != "K_DIAGNOSIS_RULE_LOG" else f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM K_DIAGNOSIS_RULE_ITEM item LEFT JOIN K_DIAGNOSIS_RULE rule ON rule.ID=item.RULE_ID WHERE rule.ID IS NULL")
        orphan_rule_items = int(cursor.fetchone()[0])
        cursor.execute("""
            SELECT COUNT(*) FROM K_DIAGNOSIS_RULE_ITEM
             WHERE SCORE_ENABLED = 1
               AND (FINDING_DICT_ID IS NULL OR SOURCE_EVIDENCE_ID IS NULL OR SOURCE_TEXT IS NULL
                    OR DBMS_LOB.GETLENGTH(SOURCE_TEXT) = 0 OR WEIGHT_LEVEL < 2 OR REVIEW_STATUS <> 'AUTO_ENABLED')
        """)
        invalid_enabled_items = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM K_DIAGNOSIS_RULE WHERE STATUS='ACTIVE' AND DIAGNOSIS_DICT_ID IS NULL")
        active_without_diagnosis = int(cursor.fetchone()[0])
        duplicates: dict[str, int] = {}
        for table in ["K_CLINICAL_SIGN_DICT", "K_EXAM_OBSERVATION_DICT", "K_VITAL_SIGN_ITEM_DICT"]:
            cursor.execute(f"SELECT COUNT(*) FROM (SELECT NAME FROM {table} WHERE VALID_FLAG=1 GROUP BY NAME HAVING COUNT(*)>1)")
            duplicates[table] = int(cursor.fetchone()[0])
        expected = {
            "K_CLINICAL_SIGN_DICT": len(unique_rows(plan["sign_rows"])),
            "K_EXAM_OBSERVATION_DICT": len(unique_rows(plan["observation_rows"])),
            "K_VITAL_SIGN_ITEM_DICT": len(unique_rows(plan["vital_rows"])),
            "K_EXAM_OBSERVATION_REL": len(unique_rows(plan.get("exam_observation_rows", []))),
            "K_TERM_DICT_MAPPING": len(unique_rows(plan["term_mapping_rows"])),
            "K_KG_DICT_CHANGE_REVIEW": len(unique_rows(plan["review_rows"])),
            "K_DIAGNOSIS_RULE": len(unique_rows(plan["rule_rows"])),
            "K_DIAGNOSIS_RULE_ITEM": len(unique_rows(plan["rule_item_rows"])),
        }
        return {
            "counts": counts,
            "expected_minimum": expected,
            "orphan_rule_items": orphan_rule_items,
            "invalid_enabled_rule_items": invalid_enabled_items,
            "active_rules_without_standard_diagnosis": active_without_diagnosis,
            "duplicate_new_dictionary_names": duplicates,
            "passed": orphan_rule_items == 0 and invalid_enabled_items == 0 and active_without_diagnosis == 0 and not any(duplicates.values()) and all(counts[key] >= value for key, value in expected.items()),
        }
    finally:
        cursor.close()


def graph_postcheck(driver) -> dict[str, Any]:
    with driver.session(database="neo4j") as session:
        return {
            "summary": {
                "node_count": one(session, "MATCH (n) RETURN count(n) AS value")["value"],
                "relationship_count": one(session, "MATCH ()-[r]->() RETURN count(r) AS value")["value"],
            },
            "validated_dictionary_nodes": one(session, "MATCH (n:KGNode) WHERE n.dictionary_status='validated' RETURN count(n) AS value")["value"],
            "duplicate_dictionary_identity_groups": one(
                session,
                """
                MATCH (n:KGNode) WHERE n.dictionary_status='validated' AND n.source_dict_id IS NOT NULL
                WITH n.entityType AS entity_type, n.source_dict_id AS dict_id, count(*) AS total
                WHERE total > 1 RETURN count(*) AS value
                """,
            )["value"],
            "scored_relations": one(session, "MATCH ()-[r]->() WHERE r.diagnostic_score_enabled=1 RETURN count(r) AS value")["value"],
            "invalid_scored_relations": one(
                session,
                """
                MATCH ()-[r]->() WHERE r.diagnostic_score_enabled=1
                  AND (r.diagnostic_rule_item_id IS NULL OR r.source_evidence_id IS NULL
                       OR r.diagnostic_weight_level < 2 OR r.diagnostic_review_status <> 'AUTO_ENABLED')
                RETURN count(r) AS value
                """,
            )["value"],
            "active_disease_rules_without_standard_diagnosis": one(
                session,
                """
                MATCH (d:Disease) WHERE d.diagnosis_rule_status='ACTIVE'
                  AND NOT (d)-[:has_standard_diagnosis]->(:StandardDiagnosis)
                RETURN count(d) AS value
                """,
            )["value"],
        }


def load_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="标准字典融合与诊断推理 V2.0")
    parser.add_argument("--mode", choices=["inventory", "plan", "apply", "postcheck"], required=True)
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--plan-file", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    graph = parse_connection_file(args.connection_file.resolve())
    driver = GraphDatabase.driver(graph["uri"], auth=(graph["username"], graph["password"]))
    try:
        driver.verify_connectivity()
        with driver.session(database="neo4j") as session:
            if args.mode == "inventory":
                result = inventory(session)
                write_json(output_dir / "01_图谱标准字典与诊断关系盘点.json", result)
            elif args.mode == "plan":
                connection = connect_oracle()
                try:
                    result = build_plan(session, connection.cursor(), output_dir)
                finally:
                    connection.close()
            elif args.mode == "apply":
                plan_file = (args.plan_file or output_dir / "02_标准字典融合与诊断作用初始化计划.json").resolve()
                plan = load_plan(plan_file)
                connection = connect_oracle()
                try:
                    oracle_result = apply_oracle_plan(connection, plan, output_dir)
                    graph_result = apply_graph_plan(driver, plan, output_dir)
                    result = {"summary": {"oracle": oracle_result, "neo4j": graph_result}}
                finally:
                    connection.close()
            elif args.mode == "postcheck":
                plan_file = (args.plan_file or output_dir / "02_标准字典融合与诊断作用初始化计划.json").resolve()
                plan = load_plan(plan_file)
                connection = connect_oracle()
                try:
                    oracle_result = oracle_postcheck(connection, plan)
                    graph_result = graph_postcheck(driver)
                    graph_result["passed"] = (
                        graph_result["duplicate_dictionary_identity_groups"] == 0
                        and graph_result["invalid_scored_relations"] == 0
                        and graph_result["active_disease_rules_without_standard_diagnosis"] == 0
                    )
                    result = {
                        "summary": {
                            "oracle_passed": oracle_result["passed"],
                            "neo4j_passed": graph_result["passed"],
                            "passed": oracle_result["passed"] and graph_result["passed"],
                        },
                        "oracle": oracle_result,
                        "neo4j": graph_result,
                    }
                    write_json(output_dir / "09_标准字典融合与诊断推理最终复核.json", result)
                finally:
                    connection.close()
            else:
                raise ValueError(f"不支持的模式：{args.mode}")
    finally:
        driver.close()
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
