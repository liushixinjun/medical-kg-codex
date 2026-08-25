from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


REQUIRED_TOP_KEYS = {"version", "name", "purpose", "global_rules", "source_requirements", "slots"}
REQUIRED_SLOT_KEYS = {
    "slot_code",
    "slot_name",
    "applies_to_categories",
    "applies_to_disease_examples",
    "extension_entities",
    "extension_relations",
    "audit_gates",
}
REQUIRED_ENTITY_KEYS = {"entity_type", "chinese_name", "purpose", "cdss_dictionary_policy"}
REQUIRED_RELATION_KEYS = {"relation", "chinese_name", "source", "target", "usage"}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"配置文件不是字典结构：{path}")
    return data


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def audit_config(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    missing_top = sorted(REQUIRED_TOP_KEYS - set(data.keys()))
    for key in missing_top:
        errors.append(f"缺少顶层字段：{key}")

    slots = data.get("slots", [])
    if not isinstance(slots, list) or not slots:
        errors.append("slots 必须是非空列表。")
        slots = []

    slot_codes: list[str] = []
    entity_types: list[str] = []
    relation_names: list[str] = []
    categories: set[str] = set()

    for idx, slot in enumerate(slots, start=1):
        if not isinstance(slot, dict):
            errors.append(f"第 {idx} 个槽位不是字典结构。")
            continue

        slot_code = str(slot.get("slot_code", "")).strip()
        slot_name = str(slot.get("slot_name", "")).strip()
        slot_codes.append(slot_code)

        for key in sorted(REQUIRED_SLOT_KEYS - set(slot.keys())):
            errors.append(f"槽位 {slot_code or idx} 缺少字段：{key}")

        if not slot_code:
            errors.append(f"第 {idx} 个槽位缺少 slot_code。")
        if not slot_name:
            errors.append(f"槽位 {slot_code or idx} 缺少中文名称。")

        applies_to = as_list(slot.get("applies_to_categories"))
        examples = as_list(slot.get("applies_to_disease_examples"))
        if not applies_to:
            errors.append(f"槽位 {slot_code} 未声明适用疾病大类。")
        if not examples:
            warnings.append(f"槽位 {slot_code} 未声明典型疾病样例。")
        categories.update(str(x) for x in applies_to if x)

        entities = slot.get("extension_entities", [])
        if not isinstance(entities, list) or not entities:
            errors.append(f"槽位 {slot_code} 未声明扩展实体。")
            entities = []
        for entity in entities:
            if not isinstance(entity, dict):
                errors.append(f"槽位 {slot_code} 存在非字典扩展实体。")
                continue
            etype = str(entity.get("entity_type", "")).strip()
            entity_types.append(etype)
            for key in sorted(REQUIRED_ENTITY_KEYS - set(entity.keys())):
                errors.append(f"槽位 {slot_code} 的实体 {etype or '[空]'} 缺少字段：{key}")
            if not str(entity.get("chinese_name", "")).strip():
                errors.append(f"槽位 {slot_code} 的实体 {etype or '[空]'} 缺少中文名称。")
            if "不走医嘱字典" not in str(entity.get("cdss_dictionary_policy", "")) and "映射" not in str(entity.get("cdss_dictionary_policy", "")):
                warnings.append(f"槽位 {slot_code} 的实体 {etype} 未明确 CDSS 字典处理边界。")

        relations = slot.get("extension_relations", [])
        if not isinstance(relations, list) or not relations:
            errors.append(f"槽位 {slot_code} 未声明扩展关系。")
            relations = []
        for rel in relations:
            if not isinstance(rel, dict):
                errors.append(f"槽位 {slot_code} 存在非字典扩展关系。")
                continue
            rname = str(rel.get("relation", "")).strip()
            relation_names.append(rname)
            for key in sorted(REQUIRED_RELATION_KEYS - set(rel.keys())):
                errors.append(f"槽位 {slot_code} 的关系 {rname or '[空]'} 缺少字段：{key}")
            if not str(rel.get("chinese_name", "")).strip():
                errors.append(f"槽位 {slot_code} 的关系 {rname or '[空]'} 缺少中文名称。")

        gates = as_list(slot.get("audit_gates"))
        if len(gates) < 2:
            warnings.append(f"槽位 {slot_code} 的审计闸门少于 2 条，后续执行容易失控。")

    duplicate_slots = sorted(k for k, v in Counter(slot_codes).items() if k and v > 1)
    duplicate_relations = sorted(k for k, v in Counter(relation_names).items() if k and v > 1)
    if duplicate_slots:
        errors.append(f"槽位编码重复：{duplicate_slots}")
    if duplicate_relations:
        warnings.append(f"关系名称重复，请确认是否有意复用：{duplicate_relations}")

    expected_categories = {
        "心肌病",
        "冠心病",
        "心力衰竭",
        "心律失常",
        "高血压",
        "瓣膜病",
        "肺动脉高压",
        "起搏治疗相关疾病",
    }
    missing_categories = sorted(expected_categories - categories)
    if missing_categories:
        errors.append(f"P7重点疾病大类未覆盖：{missing_categories}")

    return {
        "status": "pass" if not errors else "fail",
        "slot_count": len(slots),
        "category_count": len(categories),
        "categories": sorted(categories),
        "entity_type_count": len(set(x for x in entity_types if x)),
        "entity_types": sorted(set(x for x in entity_types if x)),
        "relation_count": len(set(x for x in relation_names if x)),
        "relations": sorted(set(x for x in relation_names if x)),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="审计专病拓展结构槽位配置。")
    parser.add_argument("--config", default="公共执行层_kg_pipeline/专病扩展槽位配置.yaml")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    root = Path.cwd()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    data = load_yaml(config_path)
    result = audit_config(data)

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = root / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
