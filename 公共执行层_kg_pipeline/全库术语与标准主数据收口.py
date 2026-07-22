from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP = ROOT / "数据库备份_backup" / "20260722_术语收口前"
DEFAULT_AUDIT = (
    ROOT
    / "项目管理中心_project_management"
    / "148_标准字典融合V2_20260721"
    / "07_批量审核"
)
DEFAULT_OUTPUT = (
    ROOT
    / "项目管理中心_project_management"
    / "149_全库术语收口_20260722"
)

RENAME_ACTIONS = {
    "保留为别名映射",
    "保留为别名并匹配规范制剂",
    "保留为别名并匹配规范检查",
    "保留为别名并匹配规范治疗",
    "归一症状主名并保留情境",
}
RETYPE_ACTIONS = {
    "转为检验细项": "LabSubitem",
    "转为治疗项目": "TreatmentItem",
}
CLEANUP_ACTIONS = {
    "退回并重分类",
    "退回并清理污染",
    "退回并拆分为原子项",
    "拆分为检验细项与结果状态",
    "拆分为具体手术与组合方案",
}
NO_DICTIONARY_ACTIONS = {
    "转入临床规则": "clinical_rule",
    "转入临床评估": "clinical_assessment",
    "转入检验结果规则": "lab_result_rule",
    "保留为治疗方案知识": "treatment_strategy",
}
CANONICAL_CONSOLIDATION_RULES = (
    {
        "entity_types": {"LabItem", "LabSubitem"},
        "target_type": "LabSubitem",
        "canonical_name": "B型利钠肽",
        "member_names": {"B型利钠肽", "B型钠尿肽", "BNP"},
        "aliases": ["BNP", "B型钠尿肽", "脑钠肽"],
    },
    {
        "entity_types": {"LabItem", "LabSubitem"},
        "target_type": "LabSubitem",
        "canonical_name": "N末端B型利钠肽原",
        "member_names": {"N末端B型利钠肽原", "N末端B型钠尿肽前体", "NT-proBNP"},
        "aliases": ["NT-proBNP", "N末端B型钠尿肽前体", "N端脑钠肽前体"],
    },
)
TYPE_LABEL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
RELATION_TYPE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def normalize_name(value: Any) -> str:
    return re.sub(r"[\s\u3000]+", "", str(value or "").strip()).lower()


def as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in re.split(r"[,，;；|]", text) if item.strip()]


def merge_aliases(*values: Any, exclude: str | None = None) -> list[str]:
    excluded = normalize_name(exclude)
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        for item in as_list(value):
            key = normalize_name(item)
            if not key or key == excluded or key in seen:
                continue
            seen.add(key)
            result.append(item)
    return result


def parse_qualifiers(value: Any) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return as_list(value)
    return as_list(parsed)


def parse_proposed_aliases(value: Any) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    return as_list(parsed.get("aliases"))


def node_priority(node: dict[str, Any]) -> tuple[int, int, int, str]:
    props = node.get("properties", {})
    return (
        0 if props.get("source_dict_id") else 1,
        0 if str(props.get("status") or "").lower() == "active" else 1,
        0 if props.get("formal_cdss_ready") is True else 1,
        str(props.get("code") or props.get("id") or node.get("element_id") or ""),
    )


def node_quality_priority(node: dict[str, Any]) -> tuple[int, int, int]:
    return node_priority(node)[:-1]


def add_canonical_consolidations(
    nodes: list[dict[str, Any]],
    plan: dict[str, list[dict[str, Any]]],
    scheduled_duplicates: set[str],
) -> None:
    for rule in CANONICAL_CONSOLIDATION_RULES:
        canonical_name = str(rule["canonical_name"])
        target_type = str(rule["target_type"])
        member_keys = {normalize_name(item) for item in rule["member_names"]}
        members = [
            item
            for item in nodes
            if str(item.get("properties", {}).get("entityType") or "") in rule["entity_types"]
            and normalize_name(item.get("properties", {}).get("name")) in member_keys
        ]
        if len(members) < 2:
            continue
        exact_targets = [
            item
            for item in members
            if str(item.get("properties", {}).get("entityType") or "") == target_type
            and normalize_name(item.get("properties", {}).get("name")) == normalize_name(canonical_name)
        ]
        typed_targets = [
            item for item in members if str(item.get("properties", {}).get("entityType") or "") == target_type
        ]
        candidates = exact_targets or typed_targets or members
        candidates.sort(key=node_priority)
        if len(candidates) > 1 and node_quality_priority(candidates[0]) == node_quality_priority(candidates[1]):
            plan["conflicting_canonical_targets"].append(
                {
                    "source_code": "",
                    "source_name": "同义词组",
                    "normalized_name": canonical_name,
                    "target_codes": [item.get("properties", {}).get("code") for item in candidates],
                }
            )
            continue
        survivor = candidates[0]
        survivor_props = survivor.get("properties", {})
        survivor_element = str(survivor.get("element_id"))
        aliases = merge_aliases(rule["aliases"], exclude=canonical_name)
        duplicate_codes = [
            str(item.get("properties", {}).get("code") or "")
            for item in members
            if str(item.get("element_id")) != survivor_element
        ]
        legacy_codes = merge_aliases(survivor_props.get("legacy_codes"), duplicate_codes)

        if str(survivor_props.get("entityType") or "") != target_type:
            plan["retype_nodes"].append(
                {
                    "element_id": survivor.get("element_id"),
                    "code": survivor_props.get("code"),
                    "id": survivor_props.get("id"),
                    "name": survivor_props.get("name"),
                    "old_entity_type": survivor_props.get("entityType"),
                    "new_entity_type": target_type,
                    "reason": "规范同义词组归并",
                }
            )
        if normalize_name(survivor_props.get("name")) != normalize_name(canonical_name):
            plan["rename_nodes"].append(
                {
                    "element_id": survivor.get("element_id"),
                    "code": survivor_props.get("code"),
                    "id": survivor_props.get("id"),
                    "old_name": survivor_props.get("name"),
                    "new_name": canonical_name,
                    "entity_type": target_type,
                    "aliases": aliases,
                    "clinical_qualifiers": [],
                    "reason": "规范同义词组归并",
                }
            )
        for duplicate in members:
            if str(duplicate.get("element_id")) == survivor_element:
                continue
            duplicate_props = duplicate.get("properties", {})
            duplicate_element = str(duplicate.get("element_id"))
            scheduled_duplicates.add(duplicate_element)
            plan["merge_nodes"].append(
                {
                    "duplicate_element_id": duplicate.get("element_id"),
                    "duplicate_code": duplicate_props.get("code"),
                    "duplicate_id": duplicate_props.get("id"),
                    "duplicate_name": duplicate_props.get("name"),
                    "survivor_element_id": survivor.get("element_id"),
                    "survivor_code": survivor_props.get("code"),
                    "survivor_id": survivor_props.get("id"),
                    "survivor_name": canonical_name,
                    "entity_type": target_type,
                    "aliases": aliases,
                    "legacy_codes": legacy_codes,
                    "clinical_qualifiers": [],
                    "reason": "规范同义词组归并",
                }
            )


def consolidate_survivor_metadata(plan: dict[str, Any]) -> None:
    """防止同一保留节点被多次更新时，后一次写入覆盖前一次别名。"""
    aliases_by_code: dict[str, list[Any]] = {}
    legacy_codes_by_code: dict[str, list[Any]] = {}

    for key in ("rename_nodes", "term_mapping_updates"):
        for item in plan.get(key, []):
            code = str(item.get("code") or "")
            if code:
                aliases_by_code.setdefault(code, []).append(item.get("aliases", []))

    for item in plan.get("merge_nodes", []):
        code = str(item.get("survivor_code") or "")
        if not code:
            continue
        aliases_by_code.setdefault(code, []).append(item.get("aliases", []))
        legacy_codes_by_code.setdefault(code, []).append(item.get("legacy_codes", []))

    for key in ("rename_nodes", "term_mapping_updates"):
        for item in plan.get(key, []):
            code = str(item.get("code") or "")
            if code:
                item["aliases"] = merge_aliases(
                    *aliases_by_code.get(code, []),
                    exclude=str(item.get("new_name") or item.get("name") or ""),
                )

    for item in plan.get("merge_nodes", []):
        code = str(item.get("survivor_code") or "")
        if not code:
            continue
        item["aliases"] = merge_aliases(
            *aliases_by_code.get(code, []), exclude=str(item.get("survivor_name") or "")
        )
        item["legacy_codes"] = merge_aliases(
            *legacy_codes_by_code.get(code, []), exclude=code
        )


def build_plan(nodes: list[dict[str, Any]], audit_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_type_name: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in nodes:
        props = item.get("properties", {})
        code = str(props.get("code") or "").strip()
        entity_type = str(props.get("entityType") or "").strip()
        name = normalize_name(props.get("name"))
        if code:
            by_code[code].append(item)
        if entity_type and name:
            by_type_name[(entity_type, name)].append(item)

    plan: dict[str, list[dict[str, Any]]] = {
        "rename_nodes": [],
        "retype_nodes": [],
        "merge_nodes": [],
        "term_mapping_updates": [],
        "metadata_updates": [],
        "cleanup_candidates": [],
        "physical_delete_nodes": [],
        "manual_or_registration": [],
        "unmatched_nodes": [],
        "stale_audit_rows": [],
        "conflicting_graph_codes": [],
        "conflicting_canonical_targets": [],
    }
    scheduled_duplicates: set[str] = set()
    add_canonical_consolidations(nodes, plan, scheduled_duplicates)
    local_term_codes = {
        str(row.get("kg_node_code") or "").strip()
        for row in audit_rows
        if str(row.get("source") or "").lower().endswith((".yaml", ".yml"))
        and str(row.get("recommended_action") or "").strip() in RENAME_ACTIONS
    }

    for row in audit_rows:
        code = str(row.get("kg_node_code") or "").strip()
        candidates = by_code.get(code, [])
        if not candidates:
            action = str(row.get("recommended_action") or "").strip()
            is_local_term_mapping = (
                str(row.get("source") or "").lower().endswith((".yaml", ".yml"))
                and action in RENAME_ACTIONS
            )
            if is_local_term_mapping:
                entity_type = str(row.get("entity_type") or "").strip()
                normalized = str(row.get("normalized_name") or "").strip()
                target_candidates = by_type_name.get((entity_type, normalize_name(normalized)), [])
                if len(target_candidates) == 1:
                    target = target_candidates[0]
                    target_props = target.get("properties", {})
                    plan["term_mapping_updates"].append(
                        {
                            "element_id": target.get("element_id"),
                            "code": target_props.get("code"),
                            "id": target_props.get("id"),
                            "name": target_props.get("name"),
                            "entity_type": entity_type,
                            "aliases": merge_aliases(
                                target_props.get("aliases"),
                                parse_proposed_aliases(row.get("proposed_value")),
                                exclude=str(target_props.get("name") or normalized),
                            ),
                            "source_term": row.get("kg_node_name"),
                            "source_code": code,
                            "reason": action,
                        }
                    )
                    continue
                if len(target_candidates) > 1:
                    plan["conflicting_canonical_targets"].append(
                        {
                            "source_code": code,
                            "source_name": row.get("kg_node_name"),
                            "normalized_name": normalized,
                            "target_codes": [item.get("properties", {}).get("code") for item in target_candidates],
                        }
                    )
                    continue
            if code in local_term_codes:
                plan["stale_audit_rows"].append(
                    {
                        **dict(row),
                        "stale_reason": "同一旧编码已有本地术语映射记录，当前图谱无该旧节点。",
                    }
                )
                continue
            plan["unmatched_nodes"].append(dict(row))
            continue
        if len(candidates) != 1:
            plan["conflicting_graph_codes"].append(
                {"kg_node_code": code, "node_count": len(candidates), "audit": dict(row)}
            )
            continue
        source = candidates[0]
        if str(source.get("element_id")) in scheduled_duplicates:
            continue
        source_props = source.get("properties", {})
        source_type = str(source_props.get("entityType") or "")
        source_name = str(source_props.get("name") or "")
        action = str(row.get("recommended_action") or "").strip()
        normalized = str(row.get("normalized_name") or source_name).strip() or source_name
        qualifiers = parse_qualifiers(row.get("clinical_qualifiers"))

        if action in RENAME_ACTIONS:
            target_candidates = [
                item
                for item in by_type_name.get((source_type, normalize_name(normalized)), [])
                if item.get("element_id") != source.get("element_id")
            ]
            if len(target_candidates) > 1:
                target_candidates.sort(key=node_priority)
                best = target_candidates[0]
                if node_quality_priority(best) == node_quality_priority(target_candidates[1]):
                    plan["conflicting_canonical_targets"].append(
                        {
                            "source_code": code,
                            "source_name": source_name,
                            "normalized_name": normalized,
                            "target_codes": [
                                item.get("properties", {}).get("code") for item in target_candidates
                            ],
                        }
                    )
                    continue
            if target_candidates:
                survivor = sorted(target_candidates, key=node_priority)[0]
                survivor_props = survivor.get("properties", {})
                duplicate_key = str(source.get("element_id"))
                if duplicate_key in scheduled_duplicates:
                    continue
                scheduled_duplicates.add(duplicate_key)
                plan["merge_nodes"].append(
                    {
                        "duplicate_element_id": source.get("element_id"),
                        "duplicate_code": code,
                        "duplicate_id": source_props.get("id"),
                        "duplicate_name": source_name,
                        "survivor_element_id": survivor.get("element_id"),
                        "survivor_code": survivor_props.get("code"),
                        "survivor_id": survivor_props.get("id"),
                        "survivor_name": survivor_props.get("name"),
                        "entity_type": source_type,
                        "aliases": merge_aliases(
                            survivor_props.get("aliases"),
                            source_props.get("aliases"),
                            source_name,
                            exclude=str(survivor_props.get("name") or normalized),
                        ),
                        "legacy_codes": merge_aliases(
                            survivor_props.get("legacy_codes"), code, exclude=str(survivor_props.get("code") or "")
                        ),
                        "clinical_qualifiers": qualifiers,
                        "reason": action,
                    }
                )
            elif normalize_name(source_name) != normalize_name(normalized):
                plan["rename_nodes"].append(
                    {
                        "element_id": source.get("element_id"),
                        "code": code,
                        "id": source_props.get("id"),
                        "old_name": source_name,
                        "new_name": normalized,
                        "entity_type": source_type,
                        "aliases": merge_aliases(source_props.get("aliases"), source_name, exclude=normalized),
                        "clinical_qualifiers": qualifiers,
                        "reason": action,
                    }
                )
            else:
                plan["metadata_updates"].append(
                    {
                        "element_id": source.get("element_id"),
                        "code": code,
                        "id": source_props.get("id"),
                        "standardization_status": "alias_validated",
                        "dictionary_eligible": True,
                        "knowledge_role": "standard_term",
                        "reason": action,
                    }
                )
            continue

        if action in RETYPE_ACTIONS:
            new_type = RETYPE_ACTIONS[action]
            target_candidates = [
                item
                for item in by_type_name.get((new_type, normalize_name(normalized)), [])
                if item.get("element_id") != source.get("element_id")
            ]
            if len(target_candidates) > 1:
                target_candidates.sort(key=node_priority)
                best = target_candidates[0]
                if node_quality_priority(best) == node_quality_priority(target_candidates[1]):
                    plan["conflicting_canonical_targets"].append(
                        {
                            "source_code": code,
                            "source_name": source_name,
                            "normalized_name": normalized,
                            "target_codes": [
                                item.get("properties", {}).get("code") for item in target_candidates
                            ],
                        }
                    )
                    continue
            if target_candidates:
                survivor = sorted(target_candidates, key=node_priority)[0]
                survivor_props = survivor.get("properties", {})
                plan["merge_nodes"].append(
                    {
                        "duplicate_element_id": source.get("element_id"),
                        "duplicate_code": code,
                        "duplicate_id": source_props.get("id"),
                        "duplicate_name": source_name,
                        "survivor_element_id": survivor.get("element_id"),
                        "survivor_code": survivor_props.get("code"),
                        "survivor_id": survivor_props.get("id"),
                        "survivor_name": survivor_props.get("name"),
                        "entity_type": new_type,
                        "aliases": merge_aliases(survivor_props.get("aliases"), source_props.get("aliases")),
                        "legacy_codes": merge_aliases(
                            survivor_props.get("legacy_codes"), code, exclude=str(survivor_props.get("code") or "")
                        ),
                        "clinical_qualifiers": qualifiers,
                        "reason": action,
                    }
                )
            else:
                plan["retype_nodes"].append(
                    {
                        "element_id": source.get("element_id"),
                        "code": code,
                        "id": source_props.get("id"),
                        "name": source_name,
                        "old_entity_type": source_type,
                        "new_entity_type": new_type,
                        "reason": action,
                    }
                )
            continue

        if action == "转为药物类别":
            plan["metadata_updates"].append(
                {
                    "element_id": source.get("element_id"),
                    "code": code,
                    "id": source_props.get("id"),
                    "standardization_status": "knowledge_only",
                    "dictionary_eligible": False,
                    "knowledge_role": "medication_class",
                    "reason": action,
                }
            )
            continue

        if action in NO_DICTIONARY_ACTIONS:
            plan["metadata_updates"].append(
                {
                    "element_id": source.get("element_id"),
                    "code": code,
                    "id": source_props.get("id"),
                    "standardization_status": "knowledge_only",
                    "dictionary_eligible": False,
                    "knowledge_role": NO_DICTIONARY_ACTIONS[action],
                    "reason": action,
                }
            )
            continue

        if action in CLEANUP_ACTIONS:
            plan["cleanup_candidates"].append(
                {
                    "element_id": source.get("element_id"),
                    "code": code,
                    "id": source_props.get("id"),
                    "name": source_name,
                    "entity_type": source_type,
                    "active_for_cdss": False,
                    "dictionary_eligible": False,
                    "standardization_status": "blocked",
                    "reason": action,
                }
            )
            continue

        plan["manual_or_registration"].append(dict(row))

    consolidate_survivor_metadata(plan)
    return plan


def evaluate_gate(
    plan: dict[str, Any], relationship_plan: dict[str, Any] | None = None
) -> dict[str, Any]:
    relationship_plan = relationship_plan or {}
    create_relationships = list(relationship_plan.get("create_relationships", []))
    delete_relationship_ids = list(relationship_plan.get("delete_relationship_ids", []))
    deduplicated_relationship_count = int(
        relationship_plan.get("deduplicated_relationship_count", 0) or 0
    )

    def endpoint_key(ref: dict[str, Any]) -> str | None:
        value = ref.get("code") or ref.get("id") or ref.get("element_id")
        return str(value) if value not in (None, "") else None

    self_loop_count = 0
    invalid_endpoint_count = 0
    create_signatures: list[str] = []
    for relation in create_relationships:
        source = dict(relation.get("source") or {})
        target = dict(relation.get("target") or {})
        source_key = endpoint_key(source)
        target_key = endpoint_key(target)
        if source_key is None or target_key is None:
            invalid_endpoint_count += 1
        elif source_key == target_key:
            self_loop_count += 1
        create_signatures.append(
            relation_signature(
                source,
                str(relation.get("relationship_type") or ""),
                target,
                dict(relation.get("properties") or {}),
            )
        )

    unique_delete_count = len(set(str(value) for value in delete_relationship_ids))
    relationship_preservation_error_count = int(
        unique_delete_count
        != len(create_relationships) + deduplicated_relationship_count
    )
    blocking = {
        "unmatched_node_count": len(plan.get("unmatched_nodes", [])),
        "duplicate_graph_code_count": len(plan.get("conflicting_graph_codes", [])),
        "ambiguous_canonical_target_count": len(plan.get("conflicting_canonical_targets", [])),
        "physical_delete_without_mapping_count": len(plan.get("physical_delete_nodes", [])),
        "relationship_preservation_error_count": relationship_preservation_error_count,
        "relationship_self_loop_count": self_loop_count,
        "invalid_relationship_endpoint_count": invalid_endpoint_count,
        "duplicate_create_relationship_count": len(create_signatures) - len(set(create_signatures)),
        "duplicate_delete_relationship_id_count": len(delete_relationship_ids) - unique_delete_count,
    }
    return {
        "passed": all(value == 0 for value in blocking.values()),
        "blocking": blocking,
        "safe_change_counts": {
            key: len(plan.get(key, []))
            for key in (
                "rename_nodes",
                "retype_nodes",
                "merge_nodes",
                "term_mapping_updates",
                "metadata_updates",
                "cleanup_candidates",
            )
        },
        "manual_or_registration_count": len(plan.get("manual_or_registration", [])),
    }


def node_ref(node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties", {})
    return {
        "element_id": node.get("element_id"),
        "code": props.get("code"),
        "id": props.get("id"),
        "name": props.get("name"),
        "entity_type": props.get("entityType"),
    }


def relation_signature(source_ref: dict[str, Any], relation_type: str, target_ref: dict[str, Any], properties: dict[str, Any]) -> str:
    stable = {
        "source": source_ref.get("code") or source_ref.get("id") or source_ref.get("element_id"),
        "type": relation_type,
        "target": target_ref.get("code") or target_ref.get("id") or target_ref.get("element_id"),
        "properties": properties,
    }
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def build_relationship_plan(
    relation_path: Path,
    nodes: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    node_by_element = {str(item.get("element_id")): item for item in nodes}
    replacement = {
        str(item["duplicate_element_id"]): str(item["survivor_element_id"])
        for item in plan.get("merge_nodes", [])
    }
    qualifiers = {
        str(item["duplicate_element_id"]): item.get("clinical_qualifiers", [])
        for item in plan.get("merge_nodes", [])
        if item.get("clinical_qualifiers")
    }
    impacted = set(replacement) | set(replacement.values())
    before_rows: list[dict[str, Any]] = []
    existing_signatures: set[str] = set()
    proposed: list[dict[str, Any]] = []

    with relation_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            relation = json.loads(line)
            source_element = str(relation.get("start_element_id"))
            target_element = str(relation.get("end_element_id"))
            if source_element not in impacted and target_element not in impacted:
                continue
            before_rows.append(relation)
            relation_type = str(relation.get("relationship_type") or "")
            if not RELATION_TYPE_PATTERN.fullmatch(relation_type):
                raise ValueError(f"非法关系类型：{relation_type}")
            properties = dict(relation.get("properties") or {})
            current_source = node_ref(node_by_element[source_element])
            current_target = node_ref(node_by_element[target_element])
            current_signature = relation_signature(current_source, relation_type, current_target, properties)
            if source_element in replacement or target_element in replacement:
                new_source_element = replacement.get(source_element, source_element)
                new_target_element = replacement.get(target_element, target_element)
                if source_element in qualifiers and current_target.get("entity_type") == "Disease":
                    properties["clinical_qualifiers"] = qualifiers[source_element]
                if target_element in qualifiers and current_source.get("entity_type") == "Disease":
                    properties["clinical_qualifiers"] = qualifiers[target_element]
                new_source = node_ref(node_by_element[new_source_element])
                new_target = node_ref(node_by_element[new_target_element])
                proposed.append(
                    {
                        "old_element_id": relation.get("element_id"),
                        "relationship_type": relation_type,
                        "source": new_source,
                        "target": new_target,
                        "properties": properties,
                        "signature": relation_signature(new_source, relation_type, new_target, properties),
                    }
                )
            else:
                existing_signatures.add(current_signature)

    create_rows: list[dict[str, Any]] = []
    delete_relation_ids: list[str] = []
    seen_new: set[str] = set(existing_signatures)
    for item in proposed:
        delete_relation_ids.append(str(item["old_element_id"]))
        if item["signature"] in seen_new:
            continue
        seen_new.add(item["signature"])
        create_rows.append(item)
    return {
        "create_relationships": create_rows,
        "delete_relationship_ids": sorted(set(delete_relation_ids)),
        "relationship_before": before_rows,
        "deduplicated_relationship_count": len(proposed) - len(create_rows),
    }


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    uri_match = re.search(r"bolt://[^\s；;]+", text)
    user_match = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s；;]+)", text, re.I)
    password_match = re.search(r"(?:密码|password)\s*[:：]\s*([^\s；;]+)", text, re.I)
    if not uri_match or not user_match or not password_match:
        raise ValueError(f"无法从连接文件读取 Bolt、用户名和密码：{path}")
    return {"uri": uri_match.group(0), "username": user_match.group(1), "password": password_match.group(1)}


def find_node_tx(tx: Any, ref: dict[str, Any]) -> Any:
    result = tx.run(
        """
        MATCH (n:KGNode)
        WHERE ($code <> '' AND n.code=$code) OR ($id <> '' AND n.id=$id)
        RETURN n
        """,
        code=str(ref.get("code") or ""),
        id=str(ref.get("id") or ""),
    ).single()
    if result is None:
        raise RuntimeError(f"在线节点未找到：{ref}")
    return result["n"]


def apply_plan(tx: Any, plan: dict[str, Any], relationship_plan: dict[str, Any]) -> dict[str, int]:
    stats = Counter()
    for item in plan.get("rename_nodes", []):
        result = tx.run(
            """
            MATCH (n:KGNode {code:$code})
            WHERE n.name=$old_name
            SET n.name=$new_name, n.display_name=$new_name, n.preferred_name=$new_name,
                n.aliases=$aliases, n.standardization_status='validated',
                n.term_normalized_at=datetime(), n.term_normalized_by='Codex'
            RETURN count(n) AS c
            """,
            **item,
        ).single()
        if not result or int(result["c"] or 0) != 1:
            raise RuntimeError(f"重命名在线前置条件不满足：{item['code']}")
        stats["重命名并沉淀别名"] += 1

    for item in plan.get("retype_nodes", []):
        old_type = str(item["old_entity_type"])
        new_type = str(item["new_entity_type"])
        if not TYPE_LABEL_PATTERN.fullmatch(old_type) or not TYPE_LABEL_PATTERN.fullmatch(new_type):
            raise ValueError(f"非法实体类型：{old_type}->{new_type}")
        result = tx.run(
            f"""
            MATCH (n:KGNode {{code:$code}})
            WHERE n.entityType=$old_type
            REMOVE n:`{old_type}`
            SET n:KGNode:`{new_type}`, n.entityType=$new_type,
                n.type_label=$new_type, n.canonical_labels=['KGNode',$new_type],
                n.standardization_status='validated', n.term_normalized_at=datetime(),
                n.term_normalized_by='Codex'
            RETURN count(n) AS c
            """,
            code=item["code"],
            old_type=old_type,
            new_type=new_type,
        ).single()
        if not result or int(result["c"] or 0) != 1:
            raise RuntimeError(f"重分类在线前置条件不满足：{item['code']}")
        stats["实体重分类"] += 1

    for item in plan.get("metadata_updates", []):
        result = tx.run(
            """
            MATCH (n:KGNode {code:$code})
            SET n.dictionary_eligible=$dictionary_eligible,
                n.knowledge_role=$knowledge_role,
                n.standardization_status=$standardization_status,
                n.term_normalized_at=datetime(), n.term_normalized_by='Codex'
            RETURN count(n) AS c
            """,
            **item,
        ).single()
        if not result or int(result["c"] or 0) != 1:
            raise RuntimeError(f"元数据更新在线节点不唯一：{item['code']}")
        stats["知识角色标注"] += 1

    for item in plan.get("term_mapping_updates", []):
        result = tx.run(
            """
            MATCH (n:KGNode {code:$code})
            SET n.aliases=$aliases, n.standardization_status='alias_validated',
                n.term_normalized_at=datetime(), n.term_normalized_by='Codex'
            RETURN count(n) AS c
            """,
            **item,
        ).single()
        if not result or int(result["c"] or 0) != 1:
            raise RuntimeError(f"本地术语别名回写在线节点不唯一：{item['code']}")
        stats["本地术语别名回写"] += 1

    for item in plan.get("cleanup_candidates", []):
        result = tx.run(
            """
            MATCH (n:KGNode {code:$code})
            SET n.active_for_cdss=false, n.dictionary_eligible=false,
                n.standardization_status='blocked', n.formal_cdss_ready=false,
                n.cleanup_reason=$reason, n.term_normalized_at=datetime(),
                n.term_normalized_by='Codex'
            RETURN count(n) AS c
            """,
            **item,
        ).single()
        if not result or int(result["c"] or 0) != 1:
            raise RuntimeError(f"污染节点阻断在线节点不唯一：{item['code']}")
        stats["污染或复合节点阻断"] += 1

    for item in plan.get("merge_nodes", []):
        result = tx.run(
            """
            MATCH (s:KGNode {code:$survivor_code})
            MATCH (d:KGNode {code:$duplicate_code})
            SET s.aliases=$aliases, s.legacy_codes=$legacy_codes,
                s.standardization_status='validated',
                s.term_normalized_at=datetime(), s.term_normalized_by='Codex'
            RETURN count(DISTINCT s) AS survivor_count, count(DISTINCT d) AS duplicate_count
            """,
            **item,
        ).single()
        if not result or int(result["survivor_count"] or 0) != 1 or int(result["duplicate_count"] or 0) != 1:
            raise RuntimeError(f"归并在线前置条件不满足：{item['duplicate_code']}->{item['survivor_code']}")
        stats["待归并节点"] += 1

    for relation in relationship_plan.get("create_relationships", []):
        relation_type = str(relation["relationship_type"])
        if not RELATION_TYPE_PATTERN.fullmatch(relation_type):
            raise ValueError(f"非法关系类型：{relation_type}")
        source = relation["source"]
        target = relation["target"]
        result = tx.run(
            f"""
            MATCH (s:KGNode), (t:KGNode)
            WHERE (($source_code <> '' AND s.code=$source_code) OR ($source_id <> '' AND s.id=$source_id))
              AND (($target_code <> '' AND t.code=$target_code) OR ($target_id <> '' AND t.id=$target_id))
            CREATE (s)-[r:`{relation_type}`]->(t)
            SET r += $properties
            RETURN count(r) AS c
            """,
            source_code=str(source.get("code") or ""),
            source_id=str(source.get("id") or ""),
            target_code=str(target.get("code") or ""),
            target_id=str(target.get("id") or ""),
            properties=relation.get("properties", {}),
        ).single()
        if not result or int(result["c"] or 0) != 1:
            raise RuntimeError(f"关系迁移失败：{source}->{relation_type}->{target}")
        stats["新建迁移关系"] += 1

    relation_ids = relationship_plan.get("delete_relationship_ids", [])
    if relation_ids:
        result = tx.run(
            """
            MATCH ()-[r]->()
            WHERE elementId(r) IN $ids
            DELETE r
            RETURN count(*) AS c
            """,
            ids=relation_ids,
        ).single()
        stats["删除原关系"] += int(result["c"] or 0) if result else 0

    for item in plan.get("merge_nodes", []):
        result = tx.run(
            """
            MATCH (d:KGNode {code:$duplicate_code})
            WHERE NOT (d)--()
            DELETE d
            RETURN count(*) AS c
            """,
            duplicate_code=item["duplicate_code"],
        ).single()
        if not result or int(result["c"] or 0) != 1:
            raise RuntimeError(f"归并后重复节点仍有关系或不唯一：{item['duplicate_code']}")
        stats["物理删除已归并重复节点"] += 1
    return dict(stats)


def apply_alias_repair(tx: Any, plan: dict[str, Any]) -> dict[str, int]:
    """仅重写已存在主实体的别名元数据，用于写库后别名覆盖故障修复。"""
    by_code: dict[str, dict[str, Any]] = {}
    for key in ("rename_nodes", "term_mapping_updates"):
        for item in plan.get(key, []):
            code = str(item.get("code") or "")
            if code:
                by_code.setdefault(code, {"aliases": [], "legacy_codes": []})["aliases"] = item.get(
                    "aliases", []
                )
    for item in plan.get("merge_nodes", []):
        code = str(item.get("survivor_code") or "")
        if code:
            by_code[code] = {
                "aliases": item.get("aliases", []),
                "legacy_codes": item.get("legacy_codes", []),
            }

    updated = 0
    for code, values in by_code.items():
        result = tx.run(
            """
            MATCH (n:KGNode {code:$code})
            SET n.aliases=$aliases,
                n.legacy_codes=CASE WHEN size($legacy_codes)>0 THEN $legacy_codes ELSE n.legacy_codes END,
                n.term_normalized_at=datetime(), n.term_normalized_by='Codex'
            RETURN count(n) AS c
            """,
            code=code,
            aliases=values["aliases"],
            legacy_codes=values["legacy_codes"],
        ).single()
        if not result or int(result["c"] or 0) != 1:
            raise RuntimeError(f"别名修复在线节点不唯一：{code}")
        updated += 1
    return {"主实体别名修复": updated}


def verify_online(session: Any, plan: dict[str, Any]) -> dict[str, Any]:
    renamed = 0
    for item in plan.get("rename_nodes", []):
        record = session.run(
            "MATCH (n:KGNode {code:$code}) RETURN n.name AS name, n.aliases AS aliases",
            code=item["code"],
        ).single()
        if record and record["name"] == item["new_name"] and item["old_name"] in as_list(record["aliases"]):
            renamed += 1
    retyped = 0
    for item in plan.get("retype_nodes", []):
        record = session.run(
            "MATCH (n:KGNode {code:$code}) RETURN n.entityType AS entity_type",
            code=item["code"],
        ).single()
        if record and record["entity_type"] == item["new_entity_type"]:
            retyped += 1
    deleted_duplicates = 0
    for item in plan.get("merge_nodes", []):
        record = session.run(
            "MATCH (n:KGNode {code:$code}) RETURN count(n) AS c",
            code=item["duplicate_code"],
        ).single()
        if record and int(record["c"] or 0) == 0:
            deleted_duplicates += 1
    term_mappings = 0
    for item in plan.get("term_mapping_updates", []):
        record = session.run(
            "MATCH (n:KGNode {code:$code}) RETURN n.aliases AS aliases",
            code=item["code"],
        ).single()
        if record and all(alias in as_list(record["aliases"]) for alias in item.get("aliases", [])):
            term_mappings += 1
    return {
        "rename_expected": len(plan.get("rename_nodes", [])),
        "rename_verified": renamed,
        "retype_expected": len(plan.get("retype_nodes", [])),
        "retype_verified": retyped,
        "merge_expected": len(plan.get("merge_nodes", [])),
        "merge_verified": deleted_duplicates,
        "term_mapping_expected": len(plan.get("term_mapping_updates", [])),
        "term_mapping_verified": term_mappings,
        "passed": renamed == len(plan.get("rename_nodes", []))
        and retyped == len(plan.get("retype_nodes", []))
        and deleted_duplicates == len(plan.get("merge_nodes", []))
        and term_mappings == len(plan.get("term_mapping_updates", [])),
        "verified_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_summary(nodes: list[dict[str, Any]], audit_rows: list[dict[str, Any]], plan: dict[str, Any], relation_plan: dict[str, Any]) -> dict[str, Any]:
    action_counts = Counter(str(row.get("recommended_action") or "") for row in audit_rows)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "backup_node_count": len(nodes),
        "audit_row_count": len(audit_rows),
        "audit_action_counts": dict(sorted(action_counts.items())),
        "plan_counts": {key: len(value) for key, value in plan.items()},
        "relationship_plan": {
            "affected_before": len(relation_plan.get("relationship_before", [])),
            "create": len(relation_plan.get("create_relationships", [])),
            "delete": len(relation_plan.get("delete_relationship_ids", [])),
            "deduplicated": relation_plan.get("deduplicated_relationship_count", 0),
        },
        "oracle_write_performed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="全库术语与标准主数据收口")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--apply", action="store_true", help="通过硬闸门后写入Neo4j；不写Oracle")
    parser.add_argument(
        "--repair-aliases-only",
        action="store_true",
        help="仅修复已存在主实体的别名元数据，不重复执行节点归并和关系迁移",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backup_dir = args.backup_dir.resolve()
    audit_dir = args.audit_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes = read_jsonl(backup_dir / "全部节点_nodes.jsonl")
    automatic = read_csv(audit_dir / "02_无需人工审核清单.csv")
    manual = read_csv(audit_dir / "04_分组候选明细.csv") + read_csv(audit_dir / "05_人工裁决清单.csv")
    audit_rows = automatic + manual
    plan = build_plan(nodes, audit_rows)
    relation_plan = build_relationship_plan(
        backup_dir / "全部关系_relationships.jsonl", nodes, plan
    )
    gate = evaluate_gate(plan, relation_plan)
    summary = build_summary(nodes, audit_rows, plan, relation_plan)

    write_json(output_dir / "01_全库术语扫描汇总.json", summary)
    write_json(output_dir / "02_自动修复计划.json", plan)
    write_csv(
        output_dir / "03_待查证与人工歧义清单.csv",
        plan["manual_or_registration"] + plan["unmatched_nodes"],
        [
            "kg_node_code",
            "kg_node_name",
            "target_table",
            "recommended_action",
            "normalized_name",
            "classification_reason",
        ],
    )
    affected_elements = {
        str(item.get("element_id"))
        for key in (
            "rename_nodes",
            "retype_nodes",
            "term_mapping_updates",
            "metadata_updates",
            "cleanup_candidates",
        )
        for item in plan[key]
    } | {
        str(item.get(field))
        for item in plan["merge_nodes"]
        for field in ("duplicate_element_id", "survivor_element_id")
    }
    write_jsonl(
        output_dir / "04_受影响节点回滚快照.jsonl",
        (item for item in nodes if str(item.get("element_id")) in affected_elements),
    )
    write_jsonl(output_dir / "05_受影响关系回滚快照.jsonl", relation_plan["relationship_before"])
    write_json(output_dir / "06_写库前硬闸门.json", gate)
    write_json(
        output_dir / "06_关系迁移计划.json",
        {key: value for key, value in relation_plan.items() if key != "relationship_before"},
    )

    result: dict[str, Any] = {"applied": False, "reason": "未传入--apply"}
    verification: dict[str, Any] = {"passed": False, "reason": "尚未写库"}
    if args.apply and args.repair_aliases_only:
        raise ValueError("--apply 与 --repair-aliases-only 不能同时使用")
    if args.apply or args.repair_aliases_only:
        if not gate["passed"]:
            result = {"applied": False, "reason": "写库前硬闸门未通过", "blocking": gate["blocking"]}
        else:
            from neo4j import GraphDatabase

            connection = parse_connection_file(args.connection_file.resolve())
            driver = GraphDatabase.driver(
                connection["uri"], auth=(connection["username"], connection["password"])
            )
            try:
                with driver.session(database="neo4j") as session:
                    tx = session.begin_transaction()
                    try:
                        stats = (
                            apply_alias_repair(tx, plan)
                            if args.repair_aliases_only
                            else apply_plan(tx, plan, relation_plan)
                        )
                        tx.commit()
                    except Exception:
                        tx.rollback()
                        raise
                    result = {
                        "applied": True,
                        "mode": "仅修复主实体别名" if args.repair_aliases_only else "全库术语收口写库",
                        "stats": stats,
                        "applied_at": datetime.now().isoformat(timespec="seconds"),
                    }
                    verification = verify_online(session, plan)
            finally:
                driver.close()
    write_json(output_dir / "07_写库结果.json", result)
    write_json(output_dir / "08_写库后复核.json", verification)
    print(json.dumps({"summary": summary, "gate": gate, "write": result, "verification": verification}, ensure_ascii=False, indent=2))
    if args.apply or args.repair_aliases_only:
        return 0 if result.get("applied") and verification.get("passed") else 2
    return 0 if gate["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
