from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from 公共执行层_kg_pipeline.主数据质量闸门_master_data_gate import (  # noqa: E402
    EXCLUDED_ENTITY_TYPES,
)


BATCH_ID = "20260719_全库历史主数据引用收口"
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "项目管理中心_project_management"
    / "140_全库历史主数据引用收口_20260719"
)
SCHEMA_VERSION = "V2.0"
AORTIC_BALLOON_CODE = "PROC-CARD-VHD-BAV"
AORTIC_BALLOON_NAME = "经皮球囊主动脉瓣成形术"
AORTIC_BALLOON_ALIASES = [
    "BAV",
    "BAVP",
    "PBAV",
    "主动脉瓣球囊成形术",
    "经皮球囊主动脉瓣成形术",
]

LIST_LIKE_KEYS = {
    "aliases",
    "document_ids",
    "evidence_id",
    "evidence_ids",
    "evidence_text",
    "merged_from_codes",
    "provenance_records_json",
    "segment_id",
    "source_names",
    "source_page",
    "source_types",
}


def parse_bolt_connection(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    bolt = re.search(r"(?:bolt|neo4j)(?:\+ssc|\+s)?://[^\s，,；;]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    if not bolt:
        raise ValueError(f"未在连接文件中找到 Neo4j Bolt 地址：{path}")
    if not password:
        raise ValueError(f"未在连接文件中找到密码字段：{path}")
    return {
        "uri": bolt.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def json_safe(value: Any) -> Any:
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def neo4j_property_safe(value: Any) -> Any:
    """Convert one value to a Neo4j-storable property without losing content."""
    value = json_safe(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list):
        cleaned = [item for item in value if item is not None]
        if not cleaned:
            return []
        if any(isinstance(item, (dict, list, tuple)) for item in cleaned):
            return json.dumps(cleaned, ensure_ascii=False, sort_keys=True)
        if all(isinstance(item, bool) for item in cleaned):
            return cleaned
        if all(isinstance(item, int) and not isinstance(item, bool) for item in cleaned):
            return cleaned
        if all(
            isinstance(item, (int, float)) and not isinstance(item, bool)
            for item in cleaned
        ):
            return [float(item) for item in cleaned]
        if all(isinstance(item, str) for item in cleaned):
            return cleaned
        return json.dumps(cleaned, ensure_ascii=False, sort_keys=True)
    return str(value)


def neo4j_properties_safe(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): neo4j_property_safe(value)
        for key, value in properties.items()
        if value is not None
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(value), ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(json_safe(value), ensure_ascii=False) + "\n")


def write_csv(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in values for key in row)) or ["说明"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(values or [{"说明": "无"}])


def query_rows(runner: Any, statement: str, **parameters: Any) -> list[dict[str, Any]]:
    return [dict(record) for record in runner.run(statement, **parameters)]


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _unique(values: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if value is None or value == "":
            continue
        marker = json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def _code_score(entity_type: str, code: str) -> tuple[int, int, str]:
    upper = code.upper()
    score = 0
    if entity_type == "Definition":
        score += 100 if upper.startswith("DEF-DIS-") else 0
        score -= 40 if "SKELETON" in upper else 0
    elif entity_type == "Evidence":
        score += 120 if upper.startswith("EVID-TEXTBOOK-DEF-") else 0
        score += 110 if upper.startswith("EVID-DEF-") else 0
        score += 60 if upper.startswith("EVD-CARD-FOUND-") else 0
    elif entity_type == "ExamIndicator":
        preferred = (
            "IND-EXAM-ECG-",
            "IND-EXAM-HOLTER-",
            "IND-EXAM-TTE-",
            "IND-EXAM-CAG-",
            "IND-EXAM-EMB-",
        )
        score += 150 if upper.startswith(preferred) else 0
        score += 100 if "-CDSS-" in upper else 0
        score += 60 if upper.startswith("IND-CARD-") else 0
        score -= 80 if "SKELETON" in upper else 0
        score -= 60 if "CADREM" in upper or "-TEXT-" in upper else 0
        score -= 100 if upper.startswith("LABIND-") else 0
    elif entity_type == "RiskFactor":
        score += 120 if upper.startswith("RF-CARD-") else 0
        score -= 40 if upper.startswith("RISKCOMP-") else 0
    elif entity_type == "Procedure":
        score += 80 if upper.startswith("PROC-") else 0
        score -= 20 if "SKELETON" in upper else 0
    return score, -len(code), code


def select_primary_code(
    entity_type: str,
    name: str,
    codes: Iterable[Any],
    duplicate_replaced_by: Any,
) -> str:
    del name
    normalized = [str(code).strip() for code in _as_list(list(codes)) if str(code).strip()]
    if not normalized:
        raise ValueError("主编码候选为空")
    replacement = str(duplicate_replaced_by or "").strip()
    if replacement and replacement in normalized:
        return replacement
    return max(normalized, key=lambda item: _code_score(entity_type, item))


def merge_property_values(
    base: dict[str, Any], incoming: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, list[Any]]]:
    merged = dict(base)
    conflicts: dict[str, list[Any]] = {}
    for key, value in incoming.items():
        if key in {"code", "duplicate_replaced_by", "deprecated", "status"}:
            continue
        if value is None or value == "":
            continue
        current = merged.get(key)
        if current is None or current == "":
            merged[key] = value
            continue
        if current == value:
            continue
        if key in LIST_LIKE_KEYS or isinstance(current, (list, tuple)) or isinstance(value, (list, tuple)):
            merged[key] = _unique([*_as_list(current), *_as_list(value)])
            continue
        conflicts[key] = _unique([current, value])
    return merged, conflicts


def build_neutral_evidence_title(source_name: Any, source_page: Any) -> str:
    source = str(source_name or "来源未标明").strip()
    pages = _unique(_as_list(source_page))
    if pages:
        page_text = "、".join(str(page) for page in pages)
        return f"{source} 第{page_text}页原文证据"
    return f"{source} 原文证据"


def normalized_name(value: Any) -> str:
    return re.sub(r"[\s（）()\-_—·,，。；;:/\\]", "", str(value or "")).lower()


def evidence_fingerprint(properties: dict[str, Any]) -> str:
    payload = {
        "source_name": properties.get("source_name") or "",
        "source_page": str(properties.get("source_page") or ""),
        "evidence_text": properties.get("evidence_text") or "",
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _node_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "element_id": row["element_id"],
        "labels": row.get("labels") or [],
        "properties": json_safe(row.get("properties") or {}),
        "degree": int(row.get("degree") or 0),
    }


def fetch_node_rows_by_codes(runner: Any, codes: list[str]) -> list[dict[str, Any]]:
    if not codes:
        return []
    return query_rows(
        runner,
        """
        UNWIND $codes AS wanted_code
        MATCH (n:KGNode {code:wanted_code})
        RETURN elementId(n) AS element_id, labels(n) AS labels,
               properties(n) AS properties, COUNT {(n)--()} AS degree
        """,
        codes=sorted(set(codes)),
    )


def fetch_initial_state(runner: Any) -> dict[str, Any]:
    list_nodes = query_rows(
        runner,
        """
        MATCH (n:KGNode)
        WHERE n.code IS NOT NULL AND valueType(n.code) STARTS WITH 'LIST'
        RETURN elementId(n) AS element_id, labels(n) AS labels,
               properties(n) AS properties, COUNT {(n)--()} AS degree
        ORDER BY n.entityType, n.name
        """,
    )
    replacement_nodes = query_rows(
        runner,
        """
        MATCH (n:KGNode)
        WHERE n.duplicate_replaced_by IS NOT NULL
        RETURN elementId(n) AS element_id, labels(n) AS labels,
               properties(n) AS properties, COUNT {(n)--()} AS degree
        ORDER BY n.entityType, n.name
        """,
    )
    group_rows = query_rows(
        runner,
        """
        MATCH (d:Disease)-[]->(n:KGNode)
        WHERE n.entityType IS NOT NULL AND n.name IS NOT NULL AND trim(n.name) <> ''
          AND NOT n.entityType IN $excluded
        WITH d, n.entityType AS entity_type, n.name AS entity_name,
             collect(DISTINCT elementId(n)) AS node_ids
        WHERE size(node_ids) > 1
        RETURN d.code AS disease_code, d.name AS disease_name,
               entity_type, entity_name, node_ids
        ORDER BY disease_code, entity_type, entity_name
        """,
        excluded=EXCLUDED_ENTITY_TYPES,
    )
    lookup_codes: list[str] = []
    for row in [*list_nodes, *replacement_nodes]:
        props = row["properties"]
        lookup_codes.extend(str(item) for item in _as_list(props.get("code")))
        if props.get("duplicate_replaced_by"):
            lookup_codes.append(str(props["duplicate_replaced_by"]))
    group_ids = sorted({item for row in group_rows for item in row["node_ids"]})
    group_nodes = (
        query_rows(
            runner,
            """
            UNWIND $ids AS node_id
            MATCH (n) WHERE elementId(n)=node_id
            RETURN elementId(n) AS element_id, labels(n) AS labels,
                   properties(n) AS properties, COUNT {(n)--()} AS degree
            """,
            ids=group_ids,
        )
        if group_ids
        else []
    )
    lookup_nodes = fetch_node_rows_by_codes(runner, lookup_codes)
    node_by_id = {
        row["element_id"]: row
        for row in [*list_nodes, *replacement_nodes, *group_nodes, *lookup_nodes]
    }
    return {
        "list_nodes": list_nodes,
        "replacement_nodes": replacement_nodes,
        "duplicate_groups": group_rows,
        "node_by_id": node_by_id,
    }


def resolve_mapping(node_id: str, mapping: dict[str, str]) -> str:
    seen: set[str] = set()
    current = node_id
    while current in mapping:
        if current in seen:
            raise RuntimeError(f"重复节点归并形成循环：{sorted(seen)}")
        seen.add(current)
        current = mapping[current]
    return current


def _pick_group_survivor(
    node_ids: list[str], node_by_id: dict[str, dict[str, Any]], entity_type: str, name: str
) -> str:
    def score(node_id: str) -> tuple[int, int, str]:
        row = node_by_id[node_id]
        props = row["properties"]
        code = props.get("code")
        scalar = 1 if isinstance(code, str) else 0
        preferred = 0
        if entity_type == "Exam" and name == "经食管超声心动图" and code == "EXAM-TEE":
            preferred = 1000
        if entity_type == "Procedure" and name == "经皮球囊肺动脉瓣成形术" and code == "PROC-CARD-5558D37982AF":
            preferred = 1000
        return preferred + scalar * 100, int(row.get("degree") or 0), str(code)

    return max(node_ids, key=score)


def build_cleanup_plan(runner: Any) -> dict[str, Any]:
    state = fetch_initial_state(runner)
    node_by_id: dict[str, dict[str, Any]] = state["node_by_id"]
    mapping: dict[str, str] = {}
    list_updates: dict[str, str] = {}
    stale_marker_ids: set[str] = set()
    reasons: dict[str, str] = {}

    def add_mapping(duplicate_id: str, survivor_id: str, reason: str) -> None:
        if duplicate_id == survivor_id:
            return
        previous = mapping.get(duplicate_id)
        if previous and resolve_mapping(previous, mapping) != resolve_mapping(survivor_id, mapping):
            raise RuntimeError(f"节点出现冲突归并目标：{duplicate_id}")
        mapping[duplicate_id] = survivor_id
        reasons[duplicate_id] = reason

    scalar_index: dict[str, list[str]] = defaultdict(list)
    for node_id, row in node_by_id.items():
        code = row["properties"].get("code")
        if isinstance(code, str) and code:
            scalar_index[code].append(node_id)

    for row in state["list_nodes"]:
        node_id = row["element_id"]
        props = row["properties"]
        codes = [str(code) for code in _as_list(props.get("code"))]
        primary = select_primary_code(
            str(props.get("entityType") or ""),
            str(props.get("name") or ""),
            codes,
            props.get("duplicate_replaced_by"),
        )
        matching_primary = [
            candidate
            for candidate in scalar_index.get(primary, [])
            if candidate != node_id
            and node_by_id[candidate]["properties"].get("entityType") == props.get("entityType")
            and normalized_name(node_by_id[candidate]["properties"].get("name"))
            == normalized_name(props.get("name"))
        ]
        if matching_primary:
            survivor = max(matching_primary, key=lambda item: int(node_by_id[item].get("degree") or 0))
            add_mapping(node_id, survivor, "数组主编码已有标量主节点")
        else:
            survivor = node_id
            list_updates[node_id] = primary
        for code in codes:
            for candidate in scalar_index.get(code, []):
                if candidate in {node_id, survivor}:
                    continue
                candidate_props = node_by_id[candidate]["properties"]
                if candidate_props.get("entityType") != props.get("entityType"):
                    continue
                if normalized_name(candidate_props.get("name")) != normalized_name(props.get("name")):
                    continue
                add_mapping(candidate, survivor, "数组编码中的外部同义主数据节点")

    planned_code_index: dict[str, list[str]] = defaultdict(list)
    for node_id, row in node_by_id.items():
        if node_id in mapping:
            continue
        code = list_updates.get(node_id, row["properties"].get("code"))
        if isinstance(code, str) and code:
            planned_code_index[code].append(node_id)

    for row in state["replacement_nodes"]:
        node_id = row["element_id"]
        if node_id in mapping:
            continue
        props = row["properties"]
        replacement = str(props.get("duplicate_replaced_by") or "")
        own_codes = {str(code) for code in _as_list(props.get("code"))}
        own_primary = list_updates.get(node_id)
        if replacement in own_codes or replacement == own_primary:
            stale_marker_ids.add(node_id)
            continue
        candidates = [candidate for candidate in planned_code_index.get(replacement, []) if candidate != node_id]
        if not candidates:
            stale_marker_ids.add(node_id)
            continue
        survivor = max(candidates, key=lambda item: int(node_by_id[item].get("degree") or 0))
        if props.get("entityType") == "Evidence":
            target_props = node_by_id[survivor]["properties"]
            if evidence_fingerprint(props) != evidence_fingerprint(target_props):
                raise RuntimeError(
                    f"Evidence 证据重复标记不满足来源+页码+原文一致：{props.get('code')} -> {target_props.get('code')}"
                )
        add_mapping(node_id, survivor, "duplicate_replaced_by 指向有效主节点")

    for group in state["duplicate_groups"]:
        survivors = sorted({resolve_mapping(node_id, mapping) for node_id in group["node_ids"]})
        if len(survivors) <= 1:
            continue
        winner = _pick_group_survivor(
            survivors,
            node_by_id,
            str(group["entity_type"]),
            str(group["entity_name"]),
        )
        for candidate in survivors:
            if candidate != winner:
                add_mapping(candidate, winner, "同一疾病直连的同类型同名主数据重复")

    mapping = {duplicate: resolve_mapping(target, mapping) for duplicate, target in mapping.items()}
    if any(duplicate == target for duplicate, target in mapping.items()):
        raise RuntimeError("归并决策存在自归并")

    final_survivor_ids = sorted(set(mapping.values()))
    missing_survivor_ids = [item for item in final_survivor_ids if item not in node_by_id]
    if missing_survivor_ids:
        raise RuntimeError(f"主节点详情缺失：{missing_survivor_ids[:5]}")

    canonical_updates: dict[str, dict[str, Any]] = {}
    conflicts_by_survivor: dict[str, dict[str, list[Any]]] = defaultdict(dict)
    duplicates_by_survivor: dict[str, list[str]] = defaultdict(list)
    for duplicate_id, survivor_id in mapping.items():
        duplicates_by_survivor[survivor_id].append(duplicate_id)

    update_ids = sorted(set(final_survivor_ids) | set(list_updates) | stale_marker_ids)
    for survivor_id in update_ids:
        survivor_props = dict(node_by_id[survivor_id]["properties"])
        primary_code = list_updates.get(survivor_id, survivor_props.get("code"))
        if not isinstance(primary_code, str):
            primary_code = select_primary_code(
                str(survivor_props.get("entityType") or ""),
                str(survivor_props.get("name") or ""),
                _as_list(primary_code),
                survivor_props.get("duplicate_replaced_by"),
            )
        merged_from_codes = _unique(
            [
                *_as_list(survivor_props.get("merged_from_codes")),
                *[
                    code
                    for code in _as_list(survivor_props.get("code"))
                    if str(code) != primary_code
                ],
            ]
        )
        if survivor_id in stale_marker_ids:
            old_replacement = survivor_props.get("duplicate_replaced_by")
            if old_replacement and str(old_replacement) != primary_code:
                merged_from_codes = _unique([*merged_from_codes, old_replacement])
        merged_props = dict(survivor_props)
        for duplicate_id in duplicates_by_survivor.get(survivor_id, []):
            duplicate_props = node_by_id[duplicate_id]["properties"]
            merged_props, conflicts = merge_property_values(merged_props, duplicate_props)
            for key, values in conflicts.items():
                conflicts_by_survivor[survivor_id][key] = _unique(
                    [*conflicts_by_survivor[survivor_id].get(key, []), *values]
                )
            merged_from_codes = _unique(
                [
                    *merged_from_codes,
                    *_as_list(duplicate_props.get("code")),
                    *_as_list(duplicate_props.get("merged_from_codes")),
                ]
            )
            duplicate_name = duplicate_props.get("name")
            if (
                duplicate_name
                and merged_props.get("entityType") != "Evidence"
                and normalized_name(duplicate_name) != normalized_name(merged_props.get("name"))
            ):
                merged_props["aliases"] = _unique(
                    [*_as_list(merged_props.get("aliases")), duplicate_name]
                )
        merged_from_codes = [str(code) for code in _unique(merged_from_codes) if str(code) != primary_code]
        update = {
            key: value
            for key, value in merged_props.items()
            if key
            not in {
                "code",
                "duplicate_replaced_by",
                "deprecated",
                "status",
                "evidence_merge_status",
                "merge_status",
                "migration_status",
            }
        }
        update.update({
            "code": primary_code,
            "merged_from_codes": merged_from_codes,
            "aliases": _unique(_as_list(merged_props.get("aliases"))),
            "deprecated": False,
            "status": "active",
            "master_data_cleanup_batch": BATCH_ID,
            "master_data_cleanup_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "schema_version": SCHEMA_VERSION,
        })
        if merged_props.get("entityType") == "Evidence" and duplicates_by_survivor.get(survivor_id):
            update["name"] = build_neutral_evidence_title(
                merged_props.get("source_name"), merged_props.get("source_page")
            )
        if conflicts_by_survivor.get(survivor_id):
            update["master_data_property_conflicts_json"] = json.dumps(
                conflicts_by_survivor[survivor_id], ensure_ascii=False, sort_keys=True
            )
        canonical_updates[survivor_id] = update

    plan: dict[str, Any] = {
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "state": state,
        "mapping": mapping,
        "mapping_reasons": reasons,
        "list_updates": list_updates,
        "stale_marker_ids": sorted(stale_marker_ids - set(mapping)),
        "canonical_updates": canonical_updates,
        "duplicates_by_survivor": dict(duplicates_by_survivor),
        "synthetic_nodes": [],
    }
    existing_aortic = fetch_node_rows_by_codes(runner, [AORTIC_BALLOON_CODE])
    if existing_aortic:
        plan["aortic_balloon_node_id"] = existing_aortic[0]["element_id"]
        node_by_id[existing_aortic[0]["element_id"]] = existing_aortic[0]
    else:
        plan["synthetic_nodes"].append(
            {
                "labels": ["KGNode", "Procedure"],
                "properties": {
                    "entityType": "Procedure",
                    "code": AORTIC_BALLOON_CODE,
                    "name": AORTIC_BALLOON_NAME,
                    "preferred_name": AORTIC_BALLOON_NAME,
                    "display_name": AORTIC_BALLOON_NAME,
                    "aliases": AORTIC_BALLOON_ALIASES,
                    "status": "active",
                    "deprecated": False,
                    "source_type": "consensus",
                    "batch_id": BATCH_ID,
                    "schema_version": SCHEMA_VERSION,
                    "review_status": "approved",
                    "clinical_review_status": "clinical_batch_signed_off",
                },
            }
        )
        plan["aortic_balloon_node_id"] = "__CREATE_AORTIC_BALLOON__"
    return plan


def fetch_relationships_for_plan(runner: Any, plan: dict[str, Any]) -> list[dict[str, Any]]:
    affected = sorted(plan["mapping"])
    rows = query_rows(
        runner,
        """
        MATCH (s)-[r]->(t)
        WHERE elementId(s) IN $affected OR elementId(t) IN $affected
        RETURN elementId(r) AS relation_id, type(r) AS relation_type,
               elementId(s) AS source_id, elementId(t) AS target_id,
               s.code AS source_code, s.name AS source_name, s.entityType AS source_type,
               t.code AS target_code, t.name AS target_name, t.entityType AS target_type,
               properties(r) AS properties
        """,
        affected=affected,
    )
    semantic_rows = query_rows(
        runner,
        """
        MATCH (d:Disease {code:'DIS-CARD-VHD-AS'})-[r:treated_by_procedure]->(p:Procedure)
        WHERE p.name='经皮球囊肺动脉瓣成形术'
        RETURN elementId(r) AS relation_id, type(r) AS relation_type,
               elementId(d) AS source_id, elementId(p) AS target_id,
               d.code AS source_code, d.name AS source_name, d.entityType AS source_type,
               p.code AS target_code, p.name AS target_name, p.entityType AS target_type,
               properties(r) AS properties
        """,
    )
    by_relation = {row["relation_id"]: row for row in [*rows, *semantic_rows]}
    return list(by_relation.values())


def fetch_existing_relation_rows(
    runner: Any, candidate_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        if row["source_id"].startswith("__") or row["target_id"].startswith("__"):
            continue
        grouped[row["relation_type"]].append(
            {"source_id": row["source_id"], "target_id": row["target_id"]}
        )
    result: list[dict[str, Any]] = []
    for relation_type, keys in grouped.items():
        if not re.fullmatch(r"[A-Za-z0-9_]+", relation_type):
            raise RuntimeError(f"非法关系类型：{relation_type}")
        result.extend(
            query_rows(
                runner,
                f"""
                UNWIND $keys AS key
                MATCH (s) WHERE elementId(s)=key.source_id
                MATCH (t) WHERE elementId(t)=key.target_id
                MATCH (s)-[r:`{relation_type}`]->(t)
                RETURN elementId(r) AS relation_id, type(r) AS relation_type,
                       elementId(s) AS source_id, elementId(t) AS target_id,
                       s.code AS source_code, s.name AS source_name, s.entityType AS source_type,
                       t.code AS target_code, t.name AS target_name, t.entityType AS target_type,
                       properties(r) AS properties
                """,
                keys=keys,
            )
        )
    return result


def build_relationship_plan(runner: Any, plan: dict[str, Any]) -> dict[str, Any]:
    originals = fetch_relationships_for_plan(runner, plan)
    transformed: list[dict[str, Any]] = []
    for row in originals:
        source_id = resolve_mapping(row["source_id"], plan["mapping"])
        target_id = resolve_mapping(row["target_id"], plan["mapping"])
        semantic_repair = (
            row["source_code"] == "DIS-CARD-VHD-AS"
            and row["relation_type"] == "treated_by_procedure"
            and row["target_name"] == "经皮球囊肺动脉瓣成形术"
        )
        if semantic_repair:
            target_id = plan["aortic_balloon_node_id"]
        if source_id == target_id:
            continue
        transformed.append(
            {
                **row,
                "source_id": source_id,
                "target_id": target_id,
                "semantic_repair": semantic_repair,
            }
        )
    existing = fetch_existing_relation_rows(runner, transformed)
    by_id = {row["relation_id"]: row for row in [*originals, *existing]}
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    transformed_key_by_id = {
        row["relation_id"]: (row["source_id"], row["relation_type"], row["target_id"])
        for row in transformed
    }
    target_keys = set(transformed_key_by_id.values())
    for relation_id, row in by_id.items():
        key = transformed_key_by_id.get(
            relation_id, (row["source_id"], row["relation_type"], row["target_id"])
        )
        if key in target_keys:
            grouped[key].append(row)

    node_by_id = plan["state"]["node_by_id"]
    final_codes: dict[str, Any] = {
        node_id: plan["canonical_updates"].get(node_id, {}).get(
            "code", row["properties"].get("code")
        )
        for node_id, row in node_by_id.items()
    }
    final_codes["__CREATE_AORTIC_BALLOON__"] = AORTIC_BALLOON_CODE
    relation_rows: list[dict[str, Any]] = []
    delete_relation_ids: set[str] = set()
    for (source_id, relation_type, target_id), rows in grouped.items():
        ordered = sorted(
            rows,
            key=lambda item: (
                item["source_id"] in plan["mapping"] or item["target_id"] in plan["mapping"],
                -sum(1 for value in item["properties"].values() if value not in (None, "", [])),
            ),
        )
        merged = dict(ordered[0]["properties"])
        relation_conflicts: dict[str, list[Any]] = {}
        relation_ids: list[str] = []
        for item in ordered:
            relation_ids.append(item["relation_id"])
            merged, conflicts = merge_property_values(merged, item["properties"])
            for key, values in conflicts.items():
                relation_conflicts[key] = _unique([*relation_conflicts.get(key, []), *values])
        merged["relationType"] = relation_type
        merged["source_code"] = final_codes.get(source_id)
        merged["target_code"] = final_codes.get(target_id)
        merged["merged_relation_element_ids"] = sorted(set(relation_ids))
        merged["master_data_cleanup_batch"] = BATCH_ID
        merged["master_data_cleanup_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if relation_conflicts:
            merged["master_data_relation_conflicts_json"] = json.dumps(
                relation_conflicts, ensure_ascii=False, sort_keys=True
            )
        relation_rows.append(
            {
                "source_id": source_id,
                "relation_type": relation_type,
                "target_id": target_id,
                "properties": neo4j_properties_safe(merged),
                "original_relation_ids": sorted(set(relation_ids)),
            }
        )
        delete_relation_ids.update(relation_ids)
    return {
        "original_rows": list(by_id.values()),
        "delete_relation_ids": sorted(delete_relation_ids),
        "create_rows": relation_rows,
    }


def plan_to_reports(plan: dict[str, Any], output_dir: Path) -> None:
    node_by_id = plan["state"]["node_by_id"]
    array_rows = []
    for row in plan["state"]["list_nodes"]:
        props = row["properties"]
        final_id = resolve_mapping(row["element_id"], plan["mapping"])
        final_props = node_by_id[final_id]["properties"]
        array_rows.append(
            {
                "实体类型": props.get("entityType"),
                "实体名称": props.get("name"),
                "原编码": json.dumps(props.get("code"), ensure_ascii=False),
                "最终主编码": plan["canonical_updates"].get(final_id, {}).get(
                    "code", final_props.get("code")
                ),
                "处理方式": "归并到已有主节点" if row["element_id"] in plan["mapping"] else "原节点编码标量化",
                "原节点元素ID": row["element_id"],
                "主节点元素ID": final_id,
            }
        )
    duplicate_rows = []
    for duplicate_id, survivor_id in sorted(plan["mapping"].items()):
        duplicate = node_by_id[duplicate_id]["properties"]
        survivor = node_by_id[survivor_id]["properties"]
        duplicate_rows.append(
            {
                "实体类型": duplicate.get("entityType"),
                "重复节点名称": duplicate.get("name"),
                "重复节点编码": json.dumps(duplicate.get("code"), ensure_ascii=False),
                "保留主节点名称": survivor.get("name"),
                "保留主节点编码": plan["canonical_updates"].get(survivor_id, {}).get(
                    "code", survivor.get("code")
                ),
                "处理原因": plan["mapping_reasons"].get(duplicate_id, "归并链路传递"),
                "重复节点元素ID": duplicate_id,
                "主节点元素ID": survivor_id,
                "处置": "迁移全部关系后物理删除重复节点",
            }
        )
    stale_rows = []
    for node_id in plan["stale_marker_ids"]:
        props = node_by_id[node_id]["properties"]
        if not props.get("duplicate_replaced_by"):
            continue
        stale_rows.append(
            {
                "实体类型": props.get("entityType"),
                "实体名称": props.get("name"),
                "当前编码": json.dumps(props.get("code"), ensure_ascii=False),
                "失效替代目标": props.get("duplicate_replaced_by"),
                "处置": "保留当前主节点；旧替代编码进入历史来源编码；清除失效标记",
                "节点元素ID": node_id,
            }
        )
    relationship_rows = [
        {
            "关系类型": row["relation_type"],
            "起点元素ID": row["source_id"],
            "终点元素ID": row["target_id"],
            "合并原关系数": len(row["original_relation_ids"]),
            "原关系元素ID": "；".join(row["original_relation_ids"]),
        }
        for row in plan["relationship_plan"]["create_rows"]
    ]
    write_csv(output_dir / "01_数组编码治理清单.csv", array_rows)
    write_csv(output_dir / "02_重复节点归并决策.csv", duplicate_rows)
    write_csv(output_dir / "03_失效替代标记清理清单.csv", stale_rows)
    write_csv(output_dir / "04_关系迁移与去重清单.csv", relationship_rows)
    summary = {
        "数组编码节点": len(plan["state"]["list_nodes"]),
        "物理归并重复节点": len(plan["mapping"]),
        "保留并清理旧标记节点": len(stale_rows),
        "待删除原关系": len(plan["relationship_plan"]["delete_relation_ids"]),
        "迁移后唯一关系": len(plan["relationship_plan"]["create_rows"]),
        "新增主动脉瓣球囊成形术主节点": len(plan["synthetic_nodes"]),
    }
    write_json(output_dir / "05_治理计划摘要.json", summary)
    report = f"""# 全库历史主数据引用收口执行方案

生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 本轮范围

- 数组编码标量化：{summary['数组编码节点']} 个节点。
- 重复节点物理归并：{summary['物理归并重复节点']} 个节点。
- 失效替代标记清理：{summary['保留并清理旧标记节点']} 个节点。
- 原关系迁移去重：{summary['待删除原关系']} 条归并为 {summary['迁移后唯一关系']} 条唯一关系。
- 语义纠正：主动脉瓣狭窄不再指向“经皮球囊肺动脉瓣成形术”，改为“经皮球囊主动脉瓣成形术”。

## 安全策略

1. 先保存全部受影响节点和关系的写库前快照。
2. 所有节点更新、关系迁移、重复节点删除在一个 Neo4j 事务中完成。
3. 事务内检查数组编码、替代标记、同病种同名重复、编码碰撞、疾病层级和瓣膜手术语义。
4. 任一检查不通过，整批自动撤销；提交后再独立复核。
5. 不使用旧 APOC 物理合并脚本，不保留前端必须过滤的 deprecated 垃圾节点。
"""
    (output_dir / "05_执行方案与风险说明.md").write_text(report, encoding="utf-8")


def snapshot_before_apply(runner: Any, plan: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    node_by_id = plan["state"]["node_by_id"]
    touched_ids = sorted(
        set(plan["mapping"])
        | set(plan["mapping"].values())
        | set(plan["canonical_updates"])
        | set(plan["stale_marker_ids"])
    )
    node_rows = [_node_snapshot(node_by_id[node_id]) for node_id in touched_ids]
    relation_rows = plan["relationship_plan"]["original_rows"]
    rollback_dir = output_dir / "06_写库前回滚包"
    write_jsonl(rollback_dir / "节点_before.jsonl", node_rows)
    write_jsonl(rollback_dir / "关系_before.jsonl", relation_rows)
    manifest = {
        "batch_id": BATCH_ID,
        "node_snapshot_count": len(node_rows),
        "relationship_snapshot_count": len(relation_rows),
        "physical_delete_node_count": len(plan["mapping"]),
        "full_database_backup": str(ROOT / "数据库备份_backup" / "20260718_大版本升级前"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    write_json(rollback_dir / "回滚清单_manifest.json", manifest)
    return manifest


def apply_plan(tx: Any, plan: dict[str, Any]) -> dict[str, int]:
    stats: Counter[str] = Counter()
    created_ids: dict[str, str] = {}
    for item in plan["synthetic_nodes"]:
        properties = item["properties"]
        record = tx.run(
            """
            MERGE (n:KGNode:Procedure {code:$code})
            SET n += $properties
            RETURN elementId(n) AS element_id
            """,
            code=properties["code"],
            properties=properties,
        ).single()
        created_ids["__CREATE_AORTIC_BALLOON__"] = record["element_id"]
        stats["新增主数据节点"] += 1

    update_rows = [
        {"element_id": node_id, "properties": properties}
        for node_id, properties in plan["canonical_updates"].items()
    ]
    if update_rows:
        result = tx.run(
            """
            UNWIND $rows AS row
            MATCH (n) WHERE elementId(n)=row.element_id
            SET n += row.properties
            REMOVE n.duplicate_replaced_by, n.evidence_merge_status,
                   n.merge_status, n.migration_status
            RETURN count(n) AS updated
            """,
            rows=update_rows,
        ).single()
        stats["更新主节点"] += int(result["updated"] or 0)

    stale_only = [
        {
            "element_id": node_id,
            "old_replacement": plan["state"]["node_by_id"][node_id]["properties"].get(
                "duplicate_replaced_by"
            ),
        }
        for node_id in plan["stale_marker_ids"]
        if node_id not in plan["canonical_updates"]
    ]
    if stale_only:
        result = tx.run(
            """
            UNWIND $rows AS row
            MATCH (n) WHERE elementId(n)=row.element_id
            SET n.merged_from_codes = reduce(acc=[], x IN coalesce(n.merged_from_codes, []) + [row.old_replacement] |
                CASE WHEN x IS NULL OR x IN acc THEN acc ELSE acc + x END),
                n.deprecated=false, n.status='active',
                n.master_data_cleanup_batch=$batch_id,
                n.master_data_cleanup_at=$updated_at
            REMOVE n.duplicate_replaced_by, n.evidence_merge_status,
                   n.merge_status, n.migration_status
            RETURN count(n) AS updated
            """,
            rows=stale_only,
            batch_id=BATCH_ID,
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ).single()
        stats["清理旧标记节点"] += int(result["updated"] or 0)

    delete_relation_ids = plan["relationship_plan"]["delete_relation_ids"]
    if delete_relation_ids:
        result = tx.run(
            """
            UNWIND $ids AS relation_id
            MATCH ()-[r]->() WHERE elementId(r)=relation_id
            DELETE r
            RETURN count(*) AS deleted
            """,
            ids=delete_relation_ids,
        ).single()
        stats["删除待归并原关系"] += int(result["deleted"] or 0)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in plan["relationship_plan"]["create_rows"]:
        row = dict(row)
        row["source_id"] = created_ids.get(row["source_id"], row["source_id"])
        row["target_id"] = created_ids.get(row["target_id"], row["target_id"])
        grouped[row["relation_type"]].append(row)
    for relation_type, rows in grouped.items():
        if not re.fullmatch(r"[A-Za-z0-9_]+", relation_type):
            raise RuntimeError(f"非法关系类型：{relation_type}")
        result = tx.run(
            f"""
            UNWIND $rows AS row
            MATCH (s) WHERE elementId(s)=row.source_id
            MATCH (t) WHERE elementId(t)=row.target_id
            MERGE (s)-[r:`{relation_type}`]->(t)
            SET r += row.properties
            RETURN count(r) AS created
            """,
            rows=rows,
        ).single()
        stats["写入迁移后唯一关系"] += int(result["created"] or 0)

    duplicate_ids = sorted(plan["mapping"])
    if duplicate_ids:
        result = tx.run(
            """
            UNWIND $ids AS node_id
            MATCH (n) WHERE elementId(n)=node_id
            DETACH DELETE n
            RETURN count(*) AS deleted
            """,
            ids=duplicate_ids,
        ).single()
        stats["物理删除重复节点"] += int(result["deleted"] or 0)
    return dict(stats)


def run_hard_gates(runner: Any) -> dict[str, Any]:
    checks = [
        (
            "编码字段不是单值字符串",
            "MATCH (n:KGNode) WHERE n.code IS NOT NULL AND valueType(n.code) STARTS WITH 'LIST' RETURN count(n) AS value",
        ),
        (
            "仍存在替代标记节点",
            "MATCH (n:KGNode) WHERE n.duplicate_replaced_by IS NOT NULL RETURN count(n) AS value",
        ),
        (
            "同编码对应多个主节点",
            "MATCH (n:KGNode) WHERE n.code IS NOT NULL WITH n.code AS code,count(n) AS c WHERE c>1 RETURN count(*) AS value",
        ),
        (
            "同一疾病直连同类型同名重复",
            """
            MATCH (d:Disease)-[]->(n:KGNode)
            WHERE n.entityType IS NOT NULL AND n.name IS NOT NULL AND trim(n.name)<>''
              AND NOT n.entityType IN $excluded
            WITH d.code AS disease_code,n.entityType AS entity_type,n.name AS name,count(DISTINCT n.code) AS c
            WHERE c>1 RETURN count(*) AS value
            """,
        ),
        (
            "主动脉瓣狭窄仍错误关联肺动脉瓣球囊术",
            """
            MATCH (:Disease {code:'DIS-CARD-VHD-AS'})-[:treated_by_procedure]->(p:Procedure {name:'经皮球囊肺动脉瓣成形术'})
            RETURN count(p) AS value
            """,
        ),
        (
            "主动脉瓣狭窄缺少对应主动脉瓣球囊术",
            """
            OPTIONAL MATCH (:Disease {code:'DIS-CARD-VHD-AS'})-[:treated_by_procedure]->(p:Procedure {code:'PROC-CARD-VHD-BAV'})
            RETURN CASE WHEN count(p)=1 THEN 0 ELSE 1 END AS value
            """,
        ),
        (
            "疾病层级父级关系缺失",
            """
            MATCH (d:Disease)
            WHERE (d.diagnostic_role='broad_diagnosis'
                   AND NOT (:DiseaseCategory)-[:has_disease]->(d))
               OR (d.diagnostic_role='clinical_subtype'
                   AND NOT (:Disease)-[:has_clinical_subtype]->(d))
            RETURN count(d) AS value
            """,
        ),
        (
            "疾病关联了无效标准诊断",
            """
            MATCH (:Disease)-[:has_standard_diagnosis]->(sd:StandardDiagnosis)
            WHERE coalesce(sd.valid_flag,0) <> 1
            RETURN count(sd) AS value
            """,
        ),
    ]
    results = []
    for chinese_name, statement in checks:
        record = runner.run(statement, excluded=EXCLUDED_ENTITY_TYPES).single()
        value = int(record["value"] or 0)
        results.append({"中文指标": chinese_name, "问题数量": value, "通过": value == 0})
    return {"passed": all(item["通过"] for item in results), "checks": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="全库历史主数据引用收口")
    parser.add_argument("--mode", choices=("plan", "apply", "postcheck"), default="plan")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    connection = parse_bolt_connection(args.connection_file.resolve())
    driver = GraphDatabase.driver(
        connection["uri"], auth=(connection["username"], connection["password"])
    )
    try:
        driver.verify_connectivity()
        with driver.session(database="neo4j") as session:
            if args.mode == "postcheck":
                gates = run_hard_gates(session)
                write_json(output_dir / "09_服务器迁移后专项复核.json", gates)
                print(json.dumps(gates, ensure_ascii=False, indent=2))
                return 0 if gates["passed"] else 2

            plan = build_cleanup_plan(session)
            plan["relationship_plan"] = build_relationship_plan(session, plan)
            plan_to_reports(plan, output_dir)
            if args.mode == "plan":
                print(
                    json.dumps(
                        json.loads((output_dir / "05_治理计划摘要.json").read_text(encoding="utf-8")),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0

            rollback_manifest = snapshot_before_apply(session, plan, output_dir)
            with session.begin_transaction(timeout=600) as tx:
                try:
                    result = apply_plan(tx, plan)
                    transaction_gates = run_hard_gates(tx)
                    if not transaction_gates["passed"]:
                        raise RuntimeError(
                            "事务内硬闸门未通过，整批自动撤销："
                            + json.dumps(
                                [item for item in transaction_gates["checks"] if not item["通过"]],
                                ensure_ascii=False,
                            )
                        )
                    tx.commit()
                except Exception:
                    tx.rollback()
                    raise
            server_gates = run_hard_gates(session)
            write_json(output_dir / "07_写库执行结果.json", result)
            write_json(output_dir / "08_事务内硬闸门复核.json", transaction_gates)
            write_json(output_dir / "09_服务器迁移后专项复核.json", server_gates)
            write_json(output_dir / "06_写库前回滚包" / "回滚清单_manifest.json", rollback_manifest)
            print(
                json.dumps(
                    {"执行结果": result, "服务器专项复核": server_gates},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if server_gates["passed"] else 3
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
