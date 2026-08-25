from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "项目管理中心_project_management" / "142_证据层去重与性能收口_20260719"
BATCH_CODE = "EVIDENCE-DEDUP-20260719"

REFERENCE_KEYS = {
    "primary_evidence_code",
    "evidence_ids",
    "primary_evidence_id",
    "evidence_id",
    "source_evidence_code",
    "definition_evidence_id",
    "source_evidence_id",
    "target_code",
}
PROVENANCE_KEYS = {
    "original_evidence_id",
    "original_evidence_ids",
    "merged_from_codes",
    "migrated_from_evidence_code",
    "evidence_id_before_migration",
}
EVIDENCE_RELATION_PROPERTY_KEYS = {
    "relationType",
    "relationCategory",
    "polarity",
    "confidence",
    "review_status",
    "clinical_review_status",
    "formal_cdss_ready",
    "recommendation_class",
    "evidence_level",
    "source_type",
    "source_code",
    "disease_code",
    "batch_id",
    "schema_version",
    "updated_at",
    "evidence_id",
    "target_code",
}

TEXTBOOK_NAME = "《内科学（第10版）》"
TEXT_REPAIR_SELECTORS = {
    "EVID-DEF-DIS-CARD-CHD-BAV": "先天性二叶主动脉瓣（",
    "EVID-DEF-DIS-CARD-CHD-COA": "先天性主动脉缩窄（",
    "EVID-DEF-DIS-CARD-HTN-EMERGENCY": "高血压亚急症是指",
    "EVID-DEF-DIS-CARD-INFECTIVE-ENDOCARDITIS": "感染性心内膜炎（",
    "EVID-TEXTBOOK-DEF-DEF-CARD-CADREM-AMI-70CA4D0055": "急性冠脉综合征是一组",
    "EVID-TEXTBOOK-DEF-DEF-DIS-CARD-ARR-BRUGADA": "Brugada综合征是与",
    "EVID-TEXTBOOK-DEF-DEF-DIS-CARD-ARR-PSVT": "房室交界区相关的折返性",
    "EVID-TEXTBOOK-DEF-DEF-DIS-CARD-CAD-CHD": "冠状动脉粥样硬化性心脏病（",
    "EVID-TEXTBOOK-DEF-DEF-DIS-CARD-SCD-ARREST": "按照发生地点不同",
    "EVID-TEXTBOOK-DEF-DEF-DIS-CARD-SCD-SUDDEN": "急性症状发作后1小时",
}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_source_name(value: Any, code: str = "") -> str:
    if isinstance(value, (list, tuple)):
        normalized = []
        for item in value:
            item_value = normalize_source_name(item, code)
            if item_value and item_value not in normalized:
                normalized.append(item_value)
        if len(normalized) > 1:
            raise ValueError(f"证据 {code} 存在多个不同来源，禁止自动选择：{normalized}")
        return normalized[0] if normalized else ""
    text = normalize_space(value)
    if text in {f"{TEXTBOOK_NAME}.docx", f"{TEXTBOOK_NAME}.pdf"}:
        return TEXTBOOK_NAME
    if not text and code.startswith("EVD-CARD-TEXTBOOK-"):
        return TEXTBOOK_NAME
    return text


def normalize_source_page(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return normalize_space(value)


def normalize_evidence_text(code: str, value: Any, original_text: Any = None) -> str:
    candidate = value if value not in (None, "") else original_text
    if isinstance(candidate, (list, tuple)):
        values = [normalize_space(item) for item in candidate if normalize_space(item)]
        unique_values = list(dict.fromkeys(values))
        if len(unique_values) == 1:
            return unique_values[0]
        selector = TEXT_REPAIR_SELECTORS.get(code)
        if selector:
            matches = [item for item in unique_values if selector in item]
            if len(matches) == 1:
                return matches[0]
        if code == "EVID-DEF-DIS-CARD-NEUROSIS" and unique_values:
            return max(unique_values, key=len)
        raise ValueError(f"证据 {code} 的原文数组没有明确修复规则，禁止自动拼接")
    return normalize_space(candidate)


def build_evidence_fingerprint(source_name: Any, source_page: Any, evidence_text: Any) -> str:
    normalized = "|".join(
        (
            normalize_source_name(source_name).casefold(),
            normalize_source_page(source_page),
            normalize_space(evidence_text),
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def choose_survivor(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        nodes,
        key=lambda row: (
            -int(row.get("formal_count") or 0),
            -int(bool(row.get("active", True))),
            -int(str(row.get("code") or "").startswith("EVD-SHARED-")),
            -int(row.get("degree") or 0),
            str(row.get("code") or ""),
        ),
    )[0]


def remap_reference_value(value: Any, code_mapping: dict[str, str]) -> Any:
    if isinstance(value, str):
        return code_mapping.get(value, value)
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            remapped = remap_reference_value(item, code_mapping)
            if remapped not in result:
                result.append(remapped)
        return result
    return value


def remap_reference_properties(
    properties: dict[str, Any], code_mapping: dict[str, str]
) -> dict[str, Any]:
    result = dict(properties)
    for key in REFERENCE_KEYS:
        if key in result and key not in PROVENANCE_KEYS:
            result[key] = remap_reference_value(result[key], code_mapping)
    return result


def merge_property_dicts(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    conflicts: dict[str, list[Any]] = {}
    for props in rows:
        for key, value in props.items():
            if key == "evidence_relation_conflicts_json":
                continue
            if key not in merged or merged[key] in (None, "", []):
                merged[key] = value
                continue
            if value in (None, "", []) or value == merged[key]:
                continue
            values = conflicts.setdefault(key, [merged[key]])
            if value not in values:
                values.append(value)
    if conflicts:
        merged["evidence_relation_conflicts_json"] = json.dumps(
            conflicts, ensure_ascii=False, default=str, sort_keys=True
        )
    return merged


def aggregate_relationships(
    rows: list[dict[str, Any]],
    element_mapping: dict[str, str],
    code_mapping: dict[str, str],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    relation_ids: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for row in sorted(rows, key=lambda item: str(item.get("relationship_id") or "")):
        start_id = element_mapping.get(row["start_id"], row["start_id"])
        end_id = element_mapping.get(row["end_id"], row["end_id"])
        relation_type = row["relationship_type"]
        key = (start_id, relation_type, end_id)
        groups[key].append(remap_reference_properties(row.get("properties") or {}, code_mapping))
        relation_ids[key].append(row["relationship_id"])
    return [
        {
            "start_id": key[0],
            "relationship_type": key[1],
            "end_id": key[2],
            "properties": merge_property_dicts(groups[key]),
            "merged_relationship_ids": relation_ids[key],
        }
        for key in sorted(groups)
    ]


def compact_evidence_relationship_properties(
    properties: dict[str, Any], survivor_code: str
) -> dict[str, Any]:
    """证据正文和大段溯源只存 Evidence 节点，关系只保留查询所需轻量字段。"""
    result = {
        key: value
        for key, value in properties.items()
        if key in EVIDENCE_RELATION_PROPERTY_KEYS and value not in (None, "", [])
    }
    result["evidence_id"] = survivor_code
    if "target_code" in properties:
        result["target_code"] = survivor_code
    return result


def read_db_config(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    uri = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;]+)", text)
    if not (uri and user and password):
        raise ValueError("数据库连接文件无法解析 Bolt 地址、用户名或密码")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def chunks(values: list[Any], size: int = 1000) -> Iterable[list[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_gzip_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(value, handle, ensure_ascii=False, default=str)


def read_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def load_prepared_plan(output_dir: Path, driver: Any) -> dict[str, Any]:
    baseline_path = output_dir / "01_治理前基线" / "证据重复基线.json"
    plan_path = output_dir / "02_写库前方案" / "证据归并计划.json.gz"
    if not (baseline_path.exists() and plan_path.exists()):
        raise FileNotFoundError("未找到完整写库前预演产物，请先执行 dry-run")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = dict(
        driver.execute_query(
            "MATCH (n) WITH count(n) AS node_count MATCH ()-[r]->() RETURN node_count, count(r) AS relation_count"
        ).records[0]
    )
    raw = read_gzip_json(plan_path)
    done_records = driver.execute_query(
        "MATCH (e:KGNode {entityType:'Evidence'}) WHERE e.evidence_dedup_group_done=$batch RETURN elementId(e) AS element_id",
        batch=BATCH_CODE,
    ).records
    done_survivors = {str(record["element_id"]) for record in done_records}
    if current != baseline["服务器概况"] and not done_survivors:
        raise RuntimeError(
            f"预演后服务器数据发生非本批次变化，禁止使用旧计划写库：预演={baseline['服务器概况']}，当前={current}"
        )
    code_mapping = {
        old_code: str(group["survivor_code"])
        for group in raw["group_summaries"]
        for old_code in group["duplicate_codes"]
    }
    code_to_element: dict[str, str] = {}
    for subset in chunks(sorted(code_mapping), 2000):
        records = driver.execute_query(
            "MATCH (e:KGNode {entityType:'Evidence'}) WHERE e.code IN $codes RETURN e.code AS code, elementId(e) AS element_id",
            codes=subset,
        ).records
        code_to_element.update({str(record["code"]): str(record["element_id"]) for record in records})
    group_summaries = []
    for group in raw["group_summaries"]:
        missing = [code for code in group["duplicate_codes"] if code not in code_to_element]
        if missing and group["survivor_element_id"] not in done_survivors:
            raise RuntimeError(
                f"未完成分组 {group['survivor_code']} 缺少 {len(missing)} 个重复节点，禁止续跑"
            )
        group_summaries.append(
            {
                **group,
                "duplicate_element_ids": [
                    code_to_element[code] for code in group["duplicate_codes"] if code in code_to_element
                ],
            }
        )
    incident_relationships = [
        {"relationship_id": relationship_id}
        for row in raw["aggregated_relationships"]
        for relationship_id in row.get("merged_relationship_ids", [])
    ]
    return {
        "baseline": baseline,
        "code_mapping": code_mapping,
        "group_summaries": group_summaries,
        "survivor_updates": raw["survivor_updates"],
        "node_reference_updates": raw["node_reference_updates"],
        "relationship_reference_updates": raw["relationship_reference_updates"],
        "aggregated_relationships": raw["aggregated_relationships"],
        "duplicate_element_ids": raw["duplicate_element_ids"],
        "incident_relationships": incident_relationships,
    }


def fetch_evidence_baseline(driver: Any) -> tuple[list[dict[str, Any]], float]:
    query = """
        MATCH (e:KGNode {entityType:'Evidence'})
        OPTIONAL MATCH (adj:KGNode {entityType:'SourceAdjudication'})-[:derived_from]->(e)
        WITH e, count(CASE WHEN adj.formal_cdss_ready=true AND adj.cdss_use_status='正式推荐'
                           THEN adj END) AS formal_count
        RETURN elementId(e) AS element_id, e.code AS code,
               e.source_name AS source_name, e.source_guideline AS source_guideline,
               e.source_page AS source_page, e.page AS page, e.page_number AS page_number,
               e.evidence_text AS evidence_text, e.original_text AS original_text,
               e.status AS status, e.deprecated AS deprecated,
               formal_count, COUNT {(e)--()} AS degree, labels(e) AS labels
        ORDER BY e.code
    """
    started = time.perf_counter()
    records = driver.execute_query(query).records
    return [dict(record) for record in records], time.perf_counter() - started


def prepare_plan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_fingerprint: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        code = str(row.get("code") or "")
        source_raw = row.get("source_name") or row.get("source_guideline")
        page_raw = row.get("source_page")
        if page_raw is None:
            page_raw = row.get("page") if row.get("page") is not None else row.get("page_number")
        source_name = normalize_source_name(source_raw, code)
        source_page = normalize_source_page(page_raw)
        evidence_text = normalize_evidence_text(code, row.get("evidence_text"), row.get("original_text"))
        fingerprint = (
            build_evidence_fingerprint(source_name, source_page, evidence_text)
            if evidence_text
            else ""
        )
        normalized = {
            **row,
            "source_name_normalized": source_name,
            "source_page_normalized": source_page,
            "evidence_text_normalized": evidence_text,
            "evidence_key": fingerprint,
            "active": row.get("deprecated") is not True and row.get("status") != "deprecated",
        }
        normalized_rows.append(normalized)
        if fingerprint:
            by_fingerprint[fingerprint].append(normalized)

    duplicate_groups = [group for group in by_fingerprint.values() if len(group) > 1]
    duplicate_groups.sort(key=lambda group: (-len(group), str(group[0].get("code") or "")))
    blank_source_groups = [
        [str(row.get("code") or "") for row in group]
        for group in duplicate_groups
        if not group[0]["source_name_normalized"]
    ]
    if blank_source_groups:
        raise ValueError(f"仍有 {len(blank_source_groups)} 组重复证据缺少来源，禁止自动归并")

    element_mapping: dict[str, str] = {}
    code_mapping: dict[str, str] = {}
    group_summaries: list[dict[str, Any]] = []
    survivor_by_fingerprint: dict[str, dict[str, Any]] = {}
    for group in duplicate_groups:
        survivor = choose_survivor(group)
        survivor_by_fingerprint[survivor["evidence_key"]] = survivor
        old_codes = []
        for row in group:
            if row["element_id"] == survivor["element_id"]:
                continue
            element_mapping[row["element_id"]] = survivor["element_id"]
            code_mapping[str(row["code"])] = str(survivor["code"])
            old_codes.append(str(row["code"]))
        group_summaries.append(
            {
                "evidence_key": survivor["evidence_key"],
                "survivor_code": survivor["code"],
                "survivor_element_id": survivor["element_id"],
                "duplicate_codes": old_codes,
                "group_size": len(group),
                "source_name": survivor["source_name_normalized"],
                "source_page": survivor["source_page_normalized"],
                "evidence_excerpt": survivor["evidence_text_normalized"][:180],
            }
        )

    deleted_ids = set(element_mapping)
    survivor_updates = []
    for row in normalized_rows:
        if row["element_id"] in deleted_ids:
            continue
        merged_from = []
        raw_merged = row.get("merged_from_codes") or []
        if isinstance(raw_merged, str):
            raw_merged = [raw_merged]
        merged_from.extend(raw_merged)
        group_summary = next(
            (item for item in group_summaries if item["survivor_element_id"] == row["element_id"]),
            None,
        )
        if group_summary:
            merged_from.extend(group_summary["duplicate_codes"])
        merged_from = list(dict.fromkeys(str(item) for item in merged_from if item))
        props = {
            "source_name": row["source_name_normalized"] or None,
            "source_page": row["source_page_normalized"] or None,
            "evidence_text": row["evidence_text_normalized"] or None,
            "evidence_key": row["evidence_key"] or None,
            "evidence_id": row["code"],
            "evidence_dedup_batch": BATCH_CODE,
            "evidence_dedup_at": now_text(),
        }
        if merged_from:
            props["merged_from_codes"] = merged_from
        survivor_updates.append({"element_id": row["element_id"], "properties": props})

    return {
        "normalized_rows": normalized_rows,
        "duplicate_groups": duplicate_groups,
        "group_summaries": group_summaries,
        "element_mapping": element_mapping,
        "code_mapping": code_mapping,
        "survivor_updates": survivor_updates,
    }


def fetch_all_evidence_snapshot(driver: Any) -> list[dict[str, Any]]:
    records = driver.execute_query(
        "MATCH (e:KGNode {entityType:'Evidence'}) RETURN elementId(e) AS element_id, labels(e) AS labels, properties(e) AS properties ORDER BY e.code"
    ).records
    return [dict(record) for record in records]


def fetch_incident_relationships(driver: Any, evidence_ids: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for subset in chunks(evidence_ids, 2000):
        records = driver.execute_query(
            """
            MATCH (s)-[r]->(e:KGNode {entityType:'Evidence'})
            WHERE elementId(e) IN $ids
            RETURN elementId(r) AS relationship_id, elementId(s) AS start_id,
                   elementId(e) AS end_id, type(r) AS relationship_type,
                   properties(r) AS properties
            """,
            ids=subset,
        ).records
        result.extend(dict(record) for record in records)
    return result


def fetch_reference_updates(
    driver: Any,
    code_mapping: dict[str, str],
    deleted_node_ids: set[str],
    incident_relationship_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    keys = sorted(REFERENCE_KEYS)
    node_records = driver.execute_query(
        "MATCH (n) WHERE any(k IN keys(n) WHERE k IN $keys) RETURN elementId(n) AS element_id, properties(n) AS properties",
        keys=keys,
    ).records
    rel_records = driver.execute_query(
        "MATCH ()-[r]->() WHERE any(k IN keys(r) WHERE k IN $keys) RETURN elementId(r) AS relationship_id, properties(r) AS properties",
        keys=keys,
    ).records
    node_updates, node_backup = [], []
    for record in node_records:
        row = dict(record)
        if row["element_id"] in deleted_node_ids:
            continue
        after = remap_reference_properties(row["properties"], code_mapping)
        changed = {key: after[key] for key in REFERENCE_KEYS if after.get(key) != row["properties"].get(key)}
        if changed:
            node_updates.append({"element_id": row["element_id"], "properties": changed})
            node_backup.append({"element_id": row["element_id"], "properties": {key: row["properties"].get(key) for key in changed}})
    rel_updates, rel_backup = [], []
    for record in rel_records:
        row = dict(record)
        if row["relationship_id"] in incident_relationship_ids:
            continue
        after = remap_reference_properties(row["properties"], code_mapping)
        changed = {key: after[key] for key in REFERENCE_KEYS if after.get(key) != row["properties"].get(key)}
        if changed:
            rel_updates.append({"relationship_id": row["relationship_id"], "properties": changed})
            rel_backup.append({"relationship_id": row["relationship_id"], "properties": {key: row["properties"].get(key) for key in changed}})
    return node_updates, rel_updates, node_backup, rel_backup


def benchmark(driver: Any, evidence_key: str | None = None, repeats: int = 5) -> dict[str, Any]:
    timings = []
    query = (
        "MATCH (e:KGNode {entityType:'Evidence'}) WHERE e.evidence_key=$key RETURN e.code LIMIT 1"
        if evidence_key
        else "MATCH (e:KGNode {entityType:'Evidence'}) RETURN count(e) AS evidence_count"
    )
    for _ in range(repeats):
        started = time.perf_counter()
        driver.execute_query(query, key=evidence_key)
        timings.append(round((time.perf_counter() - started) * 1000, 3))
    return {
        "query": "按证据指纹定位" if evidence_key else "证据总数统计",
        "repeats": repeats,
        "milliseconds": timings,
        "average_ms": round(sum(timings) / len(timings), 3),
    }


def prepare(output_dir: Path, driver: Any) -> dict[str, Any]:
    rows, baseline_seconds = fetch_evidence_baseline(driver)
    plan = prepare_plan(rows)
    duplicate_ids = sorted(plan["element_mapping"])
    affected_ids = sorted(
        {row["element_id"] for group in plan["duplicate_groups"] for row in group}
    )
    incident = fetch_incident_relationships(driver, affected_ids)
    incident_ids = {row["relationship_id"] for row in incident}
    outgoing_count = driver.execute_query(
        "MATCH (e:KGNode {entityType:'Evidence'})-[r]->() WHERE elementId(e) IN $ids RETURN count(r) AS c",
        ids=affected_ids,
    ).records[0]["c"]
    if outgoing_count:
        raise ValueError(f"发现 {outgoing_count} 条证据向外关系，当前迁移模型禁止继续")
    aggregated = aggregate_relationships(incident, plan["element_mapping"], plan["code_mapping"])
    survivor_codes_by_element = {
        str(group["survivor_element_id"]): str(group["survivor_code"])
        for group in plan["group_summaries"]
    }
    for row in aggregated:
        row["properties"] = compact_evidence_relationship_properties(
            row["properties"], survivor_codes_by_element[row["end_id"]]
        )
    node_updates, rel_updates, node_backup, rel_backup = fetch_reference_updates(
        driver, plan["code_mapping"], set(duplicate_ids), incident_ids
    )
    evidence_snapshot = fetch_all_evidence_snapshot(driver)
    overview = dict(
        driver.execute_query(
            "MATCH (n) WITH count(n) AS node_count MATCH ()-[r]->() RETURN node_count, count(r) AS relation_count"
        ).records[0]
    )
    label_overview = dict(
        driver.execute_query(
            "MATCH (e:KGNode {entityType:'Evidence'}) RETURN count(e) AS total, count(CASE WHEN e:Evidence THEN 1 END) AS evidence_label_count"
        ).records[0]
    )
    formal_overview = dict(
        driver.execute_query(
            """
            MATCH (adj:KGNode {entityType:'SourceAdjudication'})
            WHERE adj.formal_cdss_ready=true AND adj.cdss_use_status='正式推荐'
            OPTIONAL MATCH (adj)-[:derived_from]->(e:KGNode {entityType:'Evidence'})
            WITH adj, collect(e.code) AS codes
            RETURN count(adj) AS formal_total,
                   count(CASE WHEN adj.primary_evidence_code IN codes THEN 1 END) AS primary_matched
            """
        ).records[0]
    )
    baseline = {
        "生成时间": now_text(),
        "服务器概况": overview,
        "证据节点总数": len(rows),
        "带Evidence标签数": label_overview["evidence_label_count"],
        "正式推荐总数": formal_overview["formal_total"],
        "正式推荐主证据一致数": formal_overview["primary_matched"],
        "重复组数": len(plan["duplicate_groups"]),
        "重复组涉及节点数": sum(len(group) for group in plan["duplicate_groups"]),
        "预计物理删除重复节点数": len(duplicate_ids),
        "受影响证据关系数": len(incident),
        "归并后证据关系数": len(aggregated),
        "节点属性引用更新数": len(node_updates),
        "关系属性引用更新数": len(rel_updates),
        "证据读取耗时秒": round(baseline_seconds, 3),
        "预计归并后证据节点数": len(rows) - len(duplicate_ids),
    }
    write_json(output_dir / "01_治理前基线" / "证据重复基线.json", baseline)
    write_json(output_dir / "02_写库前方案" / "归并摘要.json", {**baseline, "前20组": plan["group_summaries"][:20]})
    write_gzip_json(
        output_dir / "02_写库前方案" / "证据归并计划.json.gz",
        {
            "group_summaries": plan["group_summaries"],
            "survivor_updates": plan["survivor_updates"],
            "node_reference_updates": node_updates,
            "relationship_reference_updates": rel_updates,
            "aggregated_relationships": aggregated,
            "duplicate_element_ids": duplicate_ids,
        },
    )
    write_gzip_json(
        output_dir / "03_回滚包" / "证据节点关系回滚.json.gz",
        {
            "generated_at": now_text(),
            "evidence_nodes": evidence_snapshot,
            "incident_relationships": incident,
            "node_reference_properties_before": node_backup,
            "relationship_reference_properties_before": rel_backup,
        },
    )
    (output_dir / "03_回滚包" / "回滚说明.md").write_text(
        "# 证据层治理回滚说明\n\n该压缩包保存治理前全部 Evidence 节点、受影响关系以及外部引用属性。"
        "本轮正式写库按证据指纹组分批原子提交，并通过数据库进度标记支持断点续跑；任一分组失败只回滚当前分组。全部分组完成后统一执行全量硬闸门；提交后如需人工恢复，必须先停写并由数据库管理员按此快照执行，不允许直接运行历史修复脚本。\n",
        encoding="utf-8",
    )
    plan.update(
        {
            "baseline": baseline,
            "incident_relationships": incident,
            "aggregated_relationships": aggregated,
            "node_reference_updates": node_updates,
            "relationship_reference_updates": rel_updates,
            "duplicate_element_ids": duplicate_ids,
        }
    )
    return plan


def apply_rows(tx: Any, query: str, rows: list[dict[str, Any]], size: int = 500) -> None:
    for subset in chunks(rows, size):
        tx.run(query, rows=subset).consume()


def run_write_batch(driver: Any, query: str, rows: list[dict[str, Any]], size: int = 500) -> None:
    for subset in chunks(rows, size):
        with driver.session() as session:
            session.execute_write(lambda tx: tx.run(query, rows=subset).consume())


def build_safe_group_batches(
    groups: list[dict[str, Any]],
    relation_rows_by_survivor: dict[str, list[dict[str, Any]]],
) -> list[list[dict[str, Any]]]:
    limits = {
        "归并后关系数": 250,
        "归并前关系数": 900,
        "重复节点数": 250,
        "关系属性字符数": 750_000,
    }
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    relation_rows = old_relationships = duplicate_nodes = property_chars = 0
    for group in groups:
        rows = relation_rows_by_survivor.get(group["survivor_element_id"], [])
        group_relation_rows = len(rows)
        group_old_relationships = sum(len(row.get("merged_relationship_ids", [])) for row in rows)
        group_duplicate_nodes = len(group["duplicate_element_ids"])
        group_property_chars = sum(
            len(json.dumps(row.get("properties") or {}, ensure_ascii=False, default=str))
            for row in rows
        )
        group_size = {
            "归并后关系数": group_relation_rows,
            "归并前关系数": group_old_relationships,
            "重复节点数": group_duplicate_nodes,
            "关系属性字符数": group_property_chars,
        }
        oversized = {
            name: {"实际值": group_size[name], "安全上限": limit}
            for name, limit in limits.items()
            if group_size[name] > limit
        }
        if oversized:
            raise ValueError(
                f"证据归并组 {group['survivor_code']} 单组规模超过安全上限，禁止写库："
                f"{json.dumps(oversized, ensure_ascii=False)}"
            )
        exceeds = current and (
            relation_rows + group_relation_rows > limits["归并后关系数"]
            or old_relationships + group_old_relationships > limits["归并前关系数"]
            or duplicate_nodes + group_duplicate_nodes > limits["重复节点数"]
            or property_chars + group_property_chars > limits["关系属性字符数"]
        )
        if exceeds:
            batches.append(current)
            current = []
            relation_rows = old_relationships = duplicate_nodes = property_chars = 0
        current.append(group)
        relation_rows += group_relation_rows
        old_relationships += group_old_relationships
        duplicate_nodes += group_duplicate_nodes
        property_chars += group_property_chars
    if current:
        batches.append(current)
    return batches


def apply_plan(driver: Any, plan: dict[str, Any], output_dir: Path | None = None) -> dict[str, Any]:
    """按证据指纹组分批提交；每组原子化，数据库标记支持安全续跑。"""
    started = time.perf_counter()
    old_codes = sorted(plan["code_mapping"])
    run_write_batch(
        driver,
        "UNWIND $rows AS row MATCH (n) WHERE elementId(n)=row.element_id SET n += row.properties",
        plan["node_reference_updates"],
        300,
    )
    run_write_batch(
        driver,
        "UNWIND $rows AS row MATCH ()-[r]->() WHERE elementId(r)=row.relationship_id SET r += row.properties",
        plan["relationship_reference_updates"],
        500,
    )

    done_records = driver.execute_query(
        "MATCH (e:KGNode {entityType:'Evidence'}) WHERE e.evidence_dedup_group_done=$batch RETURN elementId(e) AS element_id",
        batch=BATCH_CODE,
    ).records
    done_survivors = {str(record["element_id"]) for record in done_records}
    relation_rows_by_survivor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in plan["aggregated_relationships"]:
        relation_rows_by_survivor[row["end_id"]].append(row)
    survivor_updates = {row["element_id"]: row for row in plan["survivor_updates"]}
    pending_groups = [
        group for group in plan["group_summaries"]
        if group["survivor_element_id"] not in done_survivors
    ]
    processed = len(plan["group_summaries"]) - len(pending_groups)
    safe_batches = build_safe_group_batches(pending_groups, relation_rows_by_survivor)
    for group_batch in safe_batches:
        survivor_ids = {group["survivor_element_id"] for group in group_batch}
        relation_rows = [
            row for survivor_id in survivor_ids
            for row in relation_rows_by_survivor.get(survivor_id, [])
        ]
        relationship_ids = [
            relationship_id for row in relation_rows
            for relationship_id in row.get("merged_relationship_ids", [])
        ]
        duplicate_ids = [
            element_id for group in group_batch for element_id in group["duplicate_element_ids"]
        ]
        group_updates = []
        for group in group_batch:
            row = dict(survivor_updates[group["survivor_element_id"]])
            row["properties"] = {
                **row["properties"],
                "evidence_dedup_group_done": BATCH_CODE,
            }
            group_updates.append(row)
        with driver.session() as session:
            tx = session.begin_transaction(timeout=600)
            try:
                for subset in chunks(relationship_ids, 1500):
                    tx.run("MATCH ()-[r]->() WHERE elementId(r) IN $ids DELETE r", ids=subset).consume()
                for subset in chunks(duplicate_ids, 750):
                    tx.run("MATCH (e) WHERE elementId(e) IN $ids DETACH DELETE e", ids=subset).consume()
                apply_rows(
                    tx,
                    "UNWIND $rows AS row MATCH (e) WHERE elementId(e)=row.element_id SET e:Evidence SET e += row.properties",
                    group_updates,
                    300,
                )
                by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for row in relation_rows:
                    relation_type = row["relationship_type"]
                    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", relation_type):
                        raise ValueError(f"非法关系类型：{relation_type}")
                    by_type[relation_type].append(row)
                for relation_type, rows in by_type.items():
                    apply_rows(
                        tx,
                        f"UNWIND $rows AS row MATCH (s),(e) WHERE elementId(s)=row.start_id AND elementId(e)=row.end_id CREATE (s)-[r:{relation_type}]->(e) SET r += row.properties",
                        rows,
                        300,
                    )
                remaining = tx.run(
                    "MATCH (e) WHERE elementId(e) IN $ids RETURN count(e) AS c",
                    ids=duplicate_ids,
                ).single()["c"]
                if remaining:
                    raise RuntimeError(f"当前分组仍残留 {remaining} 个重复证据节点")
                tx.commit()
            except Exception:
                tx.rollback()
                raise
        processed += len(group_batch)
        if output_dir and (processed % 750 < len(group_batch) or processed == len(plan["group_summaries"])):
            write_json(
                output_dir / "04_写库结果" / "分批写库进度.json",
                {
                    "更新时间": now_text(),
                    "总分组": len(plan["group_summaries"]),
                    "已完成分组": processed,
                    "完成比例": round(processed / len(plan["group_summaries"]) * 100, 2),
                },
            )

    run_write_batch(
        driver,
        "UNWIND $rows AS row MATCH (e) WHERE elementId(e)=row.element_id SET e:Evidence SET e += row.properties",
        plan["survivor_updates"],
        500,
    )
    driver.execute_query(
        "CREATE CONSTRAINT evidence_key_unique IF NOT EXISTS FOR (e:Evidence) REQUIRE e.evidence_key IS UNIQUE"
    )
    checks = {}
    checks["evidence_count"] = driver.execute_query(
        "MATCH (e:KGNode {entityType:'Evidence'}) RETURN count(e) AS c"
    ).records[0]["c"]
    checks["duplicate_key_groups"] = driver.execute_query(
        "MATCH (e:KGNode {entityType:'Evidence'}) WHERE e.evidence_key IS NOT NULL WITH e.evidence_key AS k,count(e) AS c WHERE c>1 RETURN count(*) AS c"
    ).records[0]["c"]
    checks["text_array_count"] = driver.execute_query(
        "MATCH (e:KGNode {entityType:'Evidence'}) WHERE e.evidence_text IS NOT NULL AND NOT (valueType(e.evidence_text) STARTS WITH 'STRING') RETURN count(e) AS c"
    ).records[0]["c"]
    checks["source_array_count"] = driver.execute_query(
        "MATCH (e:KGNode {entityType:'Evidence'}) WHERE e.source_name IS NOT NULL AND NOT (valueType(e.source_name) STARTS WITH 'STRING') RETURN count(e) AS c"
    ).records[0]["c"]
    checks["duplicate_evidence_relationship_groups"] = driver.execute_query(
        "MATCH (s)-[r]->(e:KGNode {entityType:'Evidence'}) WITH elementId(s) AS s,type(r) AS t,elementId(e) AS e,count(r) AS c WHERE c>1 RETURN count(*) AS c"
    ).records[0]["c"]
    expected_formal_total = plan["baseline"].get("正式推荐总数", 0)
    expected_primary_matched = plan["baseline"].get("正式推荐主证据一致数", expected_formal_total)
    checks["formal_total"] = driver.execute_query(
        "MATCH (adj:KGNode {entityType:'SourceAdjudication'}) WHERE adj.formal_cdss_ready=true AND adj.cdss_use_status='正式推荐' RETURN count(adj) AS c"
    ).records[0]["c"]
    checks["formal_primary_mismatch"] = driver.execute_query(
        "MATCH (adj:KGNode {entityType:'SourceAdjudication'}) WHERE adj.formal_cdss_ready=true AND adj.cdss_use_status='正式推荐' OPTIONAL MATCH (adj)-[:derived_from]->(e:KGNode {entityType:'Evidence'}) WITH adj,collect(e.code) AS codes WHERE adj.primary_evidence_code IS NULL OR NOT adj.primary_evidence_code IN codes RETURN count(adj) AS c"
    ).records[0]["c"]
    old_node_count = 0
    for subset in chunks(old_codes, 2000):
        old_node_count += driver.execute_query(
            "MATCH (e:KGNode {entityType:'Evidence'}) WHERE e.code IN $codes RETURN count(e) AS c",
            codes=subset,
        ).records[0]["c"]
    checks["old_evidence_nodes"] = old_node_count
    blockers = {
        "证据节点数异常": int(checks["evidence_count"] != plan["baseline"]["预计归并后证据节点数"]),
        "证据指纹仍重复": checks["duplicate_key_groups"],
        "证据原文仍为数组": checks["text_array_count"],
        "证据来源仍为数组": checks["source_array_count"],
        "证据关系仍重复": checks["duplicate_evidence_relationship_groups"],
        "正式推荐总数异常": int(checks["formal_total"] != expected_formal_total),
        "正式推荐主证据不一致": checks["formal_primary_mismatch"],
        "旧证据节点仍存在": checks["old_evidence_nodes"],
    }
    blockers = {key: value for key, value in blockers.items() if value}
    if blockers:
        raise RuntimeError(f"分批写库完成但最终硬闸门不通过，必须按回滚包处置：{blockers}")
    return {
        "写库方式": "按证据指纹组分批原子提交，可从数据库进度标记续跑",
        "写库耗时秒": round(time.perf_counter() - started, 3),
        "事务内检查": checks,
    }


def postcheck(driver: Any, output_dir: Path, baseline: dict[str, Any]) -> dict[str, Any]:
    overview = dict(
        driver.execute_query(
            "MATCH (n) WITH count(n) AS node_count MATCH ()-[r]->() RETURN node_count, count(r) AS relation_count"
        ).records[0]
    )
    evidence = dict(
        driver.execute_query(
            """
            MATCH (e:KGNode {entityType:'Evidence'})
            WITH count(e) AS total,
                 count(CASE WHEN e.evidence_key IS NOT NULL THEN 1 END) AS keyed,
                 count(CASE WHEN e.evidence_text IS NOT NULL AND NOT (valueType(e.evidence_text) STARTS WITH 'STRING') THEN 1 END) AS invalid_text,
                 count(CASE WHEN e.source_name IS NOT NULL AND NOT (valueType(e.source_name) STARTS WITH 'STRING') THEN 1 END) AS invalid_source
            CALL { MATCH (e:KGNode {entityType:'Evidence'}) WHERE e.evidence_key IS NOT NULL WITH e.evidence_key AS k,count(e) AS c WHERE c>1 RETURN count(*) AS duplicate_groups }
            RETURN total,keyed,invalid_text,invalid_source,duplicate_groups
            """
        ).records[0]
    )
    formal = dict(
        driver.execute_query(
            """
            MATCH (adj:KGNode {entityType:'SourceAdjudication'})
            WHERE adj.formal_cdss_ready=true AND adj.cdss_use_status='正式推荐'
            OPTIONAL MATCH (adj)-[:derived_from]->(e:KGNode {entityType:'Evidence'})
            WITH adj,collect(e.code) AS codes
            RETURN count(adj) AS formal_total,
                   count(CASE WHEN adj.primary_evidence_code IN codes THEN 1 END) AS primary_matched
            """
        ).records[0]
    )
    sample_key = driver.execute_query(
        "MATCH (e:KGNode {entityType:'Evidence'}) WHERE e.evidence_key IS NOT NULL RETURN e.evidence_key AS k LIMIT 1"
    ).records[0]["k"]
    performance = benchmark(driver, sample_key)
    result = {
        "复核时间": now_text(),
        "治理前": baseline,
        "治理后服务器概况": overview,
        "治理后证据层": evidence,
        "正式推荐链路": formal,
        "查询性能": performance,
        "结论": "通过" if evidence["duplicate_groups"] == 0
        and evidence["invalid_text"] == 0
        and evidence["invalid_source"] == 0
        and formal["formal_total"] == baseline.get("正式推荐总数", 0)
        and formal["primary_matched"] == baseline.get("正式推荐主证据一致数", baseline.get("正式推荐总数", 0))
        else "不通过",
    }
    write_json(output_dir / "05_服务器复核" / "证据层服务器复核.json", result)
    return result


def render_report(baseline: dict[str, Any], write_result: dict[str, Any], final: dict[str, Any]) -> str:
    after = final["治理后证据层"]
    overview_after = final["治理后服务器概况"]
    return f"""# Evidence 证据层去重与入库性能收口报告

生成时间：{now_text()}

## 结论

本轮结论：**{final['结论']}**。证据按“标准化来源、页码、原文”唯一归并，不合并不同来源、不同页码或不同原文的临床证据。

## 治理前后

| 指标 | 治理前 | 治理后 | 变化 |
|---|---:|---:|---:|
| Evidence 证据节点 | {baseline['证据节点总数']:,} | {after['total']:,} | {after['total']-baseline['证据节点总数']:,} |
| 重复证据组 | {baseline['重复组数']:,} | {after['duplicate_groups']:,} | {-baseline['重复组数']:,} |
| 全图节点 | {baseline['服务器概况']['node_count']:,} | {overview_after['node_count']:,} | {overview_after['node_count']-baseline['服务器概况']['node_count']:,} |
| 全图关系 | {baseline['服务器概况']['relation_count']:,} | {overview_after['relation_count']:,} | {overview_after['relation_count']-baseline['服务器概况']['relation_count']:,} |
| 非文本证据原文 | 11 | {after['invalid_text']} | {-11 + after['invalid_text']} |
| 正式推荐 | {baseline.get('正式推荐总数', 0)} | {final['正式推荐链路']['formal_total']} | {final['正式推荐链路']['formal_total']-baseline.get('正式推荐总数', 0)} |
| 主证据编码与关系一致 | {baseline.get('正式推荐主证据一致数', 0)} | {final['正式推荐链路']['primary_matched']} | {final['正式推荐链路']['primary_matched']-baseline.get('正式推荐主证据一致数', 0)} |

## 安全边界

- 不同来源、页码或原文不归并。
- 11 条数组型原文按明确疾病规则选回正确原文，未拼接污染内容。
- 所有节点属性、关系属性中的现行证据编码均同步改写；历史迁移字段保留旧编码用于追溯。
- 写库按证据指纹组分批原子提交，任一分组失败只回滚当前分组，并可依据数据库进度标记安全续跑；全部分组完成后统一执行全量硬闸门。
- 写库后已建立证据指纹唯一约束，后续批次重复证据将被数据库拦截。

## 性能

按证据指纹定位平均耗时：{final['查询性能']['average_ms']} ms。
写库耗时：{write_result['写库耗时秒']} 秒。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evidence 证据层去重与入库性能收口")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mode", choices=("dry-run", "apply"), default="dry-run")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = read_db_config(args.connection_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"])) as driver:
        driver.verify_connectivity()
        if args.mode == "dry-run":
            plan = prepare(args.output_dir, driver)
            print(json.dumps({"mode": "dry-run", **plan["baseline"]}, ensure_ascii=False, indent=2))
            return 0
        plan = load_prepared_plan(args.output_dir, driver)
        write_result = apply_plan(driver, plan, args.output_dir)
        write_json(args.output_dir / "04_写库结果" / "写库结果.json", write_result)
        final = postcheck(driver, args.output_dir, plan["baseline"])
        report = render_report(plan["baseline"], write_result, final)
        (args.output_dir / "Evidence证据层去重与入库性能收口报告.md").write_text(report, encoding="utf-8")
        print(json.dumps({"mode": "apply", **write_result, "复核": final}, ensure_ascii=False, indent=2))
        return 0 if final["结论"] == "通过" else 2


if __name__ == "__main__":
    raise SystemExit(main())
