from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_graph_instance import (
    CONCRETE_MEDICATION_ALIASES_BY_CLASS,
    CORE_CATEGORIES,
    FORBIDDEN_MEDICATION_CLASS_ALIASES_BY_CLASS,
    SEMANTIC_SHELL_NAMES,
    _as_list,
    _mentions,
    _relation_evidence_texts,
)


DEFAULT_BATCH_DIRS = [
    Path("心血管内科文献集合/00_foundation_skeleton"),
    Path("心血管内科文献集合/BATCH-CARD-CM-20260622-001"),
    Path("心血管内科文献集合/BATCH-CARD-CAD-20260623-001"),
]


MEDICATION_CLASS_ALIASES = {
    "抗凝药物": ["抗凝剂"],
    "溶栓药物": ["纤溶药物"],
    "抗血小板药物": ["抗血小板剂"],
    "硝酸酯类药物": ["硝酸酯"],
    "醛固酮受体拮抗剂": ["MRA"],
    "β受体阻滞剂": ["β受体拮抗剂"],
    "血管紧张素转换酶抑制剂": ["ACEI"],
    "血管紧张素Ⅱ受体拮抗剂": ["ARB"],
    "钙通道阻滞剂": ["钙拮抗剂"],
    "他汀类药物": ["他汀"],
}

SPECIFIC_MEDICATION_ALIASES = {
    "组织型纤溶酶原激活物": ["t-PA", "rt-PA"],
    "依度沙班": ["艾多沙班"],
}
CANONICAL_MEDICATION_CODE_BY_NAME = {
    "美托洛尔": "MED-CARD-C9175F150C3D",
    "比索洛尔": "MED-CARD-2CF15595A00F",
    "血管紧张素Ⅱ受体阻滞剂": "MED-CARD-C015B7A5655A",
}
TECHNICAL_DISPLAY_NAME_RE = re.compile(r"^[A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+$")
STANDARD_DISPLAY_NAME_BY_CODE = {
    "EXAM-TTE": "超声心动图",
    "EXAM-ECG": "心电图",
    "EXAM-HOLTER": "动态心电图",
    "EXAM-CMR": "心脏磁共振成像",
    "EXAM-CAG": "冠状动脉造影",
    "EXAM-EMB": "心内膜心肌活检",
    "EXAM-GENETIC": "基因检测",
    "LAB-CARDIAC-BIOMARKERS": "心脏生物标志物检测",
}
TREATMENT_PLAN_EXECUTION_TARGETS = {
    "溶栓治疗": [("includes_medication", "Medication", "溶栓药物")],
    "抗凝治疗": [("includes_medication", "Medication", "抗凝药物")],
    "抗血小板治疗": [("includes_medication", "Medication", "抗血小板药物")],
    "血运重建": [
        ("includes_procedure", "Procedure", "经皮冠状动脉介入治疗"),
        ("includes_procedure", "Procedure", "冠状动脉旁路移植术"),
    ],
    "再灌注治疗": [
        ("includes_procedure", "Procedure", "经皮冠状动脉介入治疗"),
        ("includes_medication", "Medication", "溶栓药物"),
    ],
    "控制心室率": [
        ("includes_medication", "Medication", "β受体阻滞剂"),
        ("includes_medication", "Medication", "β受体拮抗剂"),
        ("includes_medication", "Medication", "钙通道阻滞剂"),
        ("includes_medication", "Medication", "洋地黄类药物"),
    ],
    "降压治疗": [
        ("includes_medication", "Medication", "血管紧张素转换酶抑制剂"),
        ("includes_medication", "Medication", "血管紧张素Ⅱ受体阻滞剂"),
        ("includes_medication", "Medication", "血管紧张素Ⅱ受体拮抗剂"),
        ("includes_medication", "Medication", "钙通道阻滞剂"),
        ("includes_medication", "Medication", "利尿剂"),
    ],
    "氧疗": [("includes_procedure", "Procedure", "吸氧治疗")],
    "复律治疗": [
        ("includes_procedure", "Procedure", "电复律"),
        ("includes_medication", "Medication", "胺碘酮"),
    ],
    "非扩张型左心室心肌病治疗方案": [
        ("includes_medication", "Medication", "β受体阻滞剂"),
        ("includes_medication", "Medication", "血管紧张素转换酶抑制剂"),
        ("includes_medication", "Medication", "血管紧张素Ⅱ受体阻滞剂"),
    ],
    "法布雷病心肌病治疗方案": [
        ("includes_medication", "Medication", "阿加糖酶α"),
        ("includes_medication", "Medication", "阿加糖酶β"),
    ],
    "隐匿性冠心病治疗方案": [
        ("includes_medication", "Medication", "他汀类药物"),
        ("includes_medication", "Medication", "抗血小板药物"),
        ("includes_medication", "Medication", "β受体阻滞剂"),
    ],
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def stable_suffix(*parts: str, length: int = 12) -> str:
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest().upper()[:length]


def stable_code(prefix: str, *parts: str) -> str:
    return f"{prefix}-{stable_suffix(*parts)}"


def normalize_aliases(value) -> list[str]:
    seen = set()
    result = []
    for item in _as_list(value):
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def is_semantic_shell(node: dict) -> bool:
    return str(node.get("name", "")).strip() in SEMANTIC_SHELL_NAMES.get(node.get("entityType", ""), set())


def clinical_status_for(item: dict) -> str:
    if item.get("relationCategory") in {"structural", "evidence", "taxonomy"} or item.get("entityType") in {
        "Guideline",
        "Evidence",
        "Specialty",
        "DiseaseCategory",
        "DiseaseSubcategory",
    }:
        return "not_applicable"
    return "pending_clinical_review"


def is_technical_display_value(node: dict, field: str) -> bool:
    value = str(node.get(field, "")).strip()
    code = str(node.get("code", "")).strip()
    return bool(value and (value == code or TECHNICAL_DISPLAY_NAME_RE.fullmatch(value)))


def choose_clinical_display_name(node: dict) -> str:
    code = str(node.get("code", "")).strip()
    if code in STANDARD_DISPLAY_NAME_BY_CODE:
        return STANDARD_DISPLAY_NAME_BY_CODE[code]
    for alias in normalize_aliases(node.get("aliases")):
        if re.search(r"[\u4e00-\u9fff]", alias) and not TECHNICAL_DISPLAY_NAME_RE.fullmatch(alias):
            return alias
    name = str(node.get("name", "")).strip()
    return name


def repair_technical_display_names(nodes: list[dict]) -> int:
    changed = 0
    for node in nodes:
        if node.get("entityType") in {"Evidence", "Guideline"}:
            continue
        if not any(is_technical_display_value(node, field) for field in ("name", "preferred_name", "display_name")):
            continue
        display_name = choose_clinical_display_name(node)
        if not display_name or is_technical_display_value({"code": node.get("code"), "name": display_name}, "name"):
            continue
        for field in ("name", "preferred_name", "display_name"):
            if node.get(field) != display_name:
                node[field] = display_name
                changed += 1
        code = str(node.get("code", ""))
        if "-" in code:
            tail = code.rsplit("-", 1)[-1]
            if tail and tail.isascii() and len(tail) <= 10:
                abbr_values = normalize_aliases(node.get("abbr"))
                if tail not in abbr_values:
                    node["abbr"] = normalize_aliases(abbr_values + [tail])
    return changed


def enrich_review_status(items: list[dict]) -> int:
    changed = 0
    for item in items:
        if not item.get("clinical_review_status"):
            item["clinical_review_status"] = clinical_status_for(item)
            changed += 1
        if item.get("clinical_review_status") != "clinical_approved":
            item.setdefault("formal_cdss_ready", False)
    return changed


def medication_template(name: str, class_node: dict, batch_id: str) -> dict:
    schema_version = class_node.get("schema_version") or "V1.1"
    entity_category = class_node.get("entityCategory") or "治疗"
    return {
        "id": stable_code("N-MED", batch_id, name),
        "code": CANONICAL_MEDICATION_CODE_BY_NAME.get(name, stable_code("MED-CARD", name)),
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "aliases": SPECIFIC_MEDICATION_ALIASES.get(name, []),
        "entityType": "Medication",
        "entityCategory": entity_category,
        "schema_version": schema_version,
        "review_status": "approved",
        "clinical_review_status": "pending_clinical_review",
        "formal_cdss_ready": False,
        "batch_id": batch_id,
        "source_quality": "auto_repair_from_medication_class_alias",
        "description": f"{name}为具体药物节点；由药物类别别名拆分生成，剂量、禁忌证、相互作用需按指南证据和临床专家审核补全。",
    }


def procedure_template(name: str, reference_node: dict, batch_id: str) -> dict:
    schema_version = reference_node.get("schema_version") or "V1.5"
    return {
        "id": stable_code("N-PROC", batch_id, name),
        "code": stable_code("PROC-CARD", name),
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "aliases": [],
        "entityType": "Procedure",
        "entityCategory": "治疗",
        "schema_version": schema_version,
        "review_status": "approved",
        "clinical_review_status": "pending_clinical_review",
        "formal_cdss_ready": False,
        "batch_id": batch_id,
        "source_quality": "auto_repair_from_treatment_plan_actionability",
        "description": f"{name}为治疗方案下游操作实体；由治疗方案可执行性修复生成，适应证、禁忌证、时机和证据链需按指南继续补全。",
    }


def clinical_pathway_template(name: str, reference_node: dict, batch_id: str) -> dict:
    schema_version = reference_node.get("schema_version") or "V1.5"
    return {
        "id": stable_code("N-PATHWAY", batch_id, name),
        "code": stable_code("PATHWAY-CARD", name),
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "aliases": [],
        "entityType": "ClinicalPathway",
        "entityCategory": "路径",
        "schema_version": schema_version,
        "review_status": "approved",
        "clinical_review_status": "pending_clinical_review",
        "formal_cdss_ready": False,
        "batch_id": batch_id,
        "source_quality": "auto_repair_from_generic_treatment_plan_actionability",
        "description": f"{name}为疾病级总治疗方案的路径承载节点；具体药物和操作应挂在下级具体治疗方案，不得在总治疗方案下重复复制。",
    }


def taxonomy_relation(class_node: dict, specific_node: dict, batch_id: str) -> dict:
    return {
        "id": stable_code("REL-MEDSPEC", class_node["code"], specific_node["code"], batch_id),
        "source_code": class_node["code"],
        "relationType": "has_specific_medication",
        "target_code": specific_node["code"],
        "relationCategory": "taxonomy",
        "batch_id": batch_id,
        "schema_version": class_node.get("schema_version") or specific_node.get("schema_version") or "V1.1",
        "review_status": "approved",
        "clinical_review_status": "not_applicable",
        "formal_cdss_ready": False,
        "polarity": "positive",
        "source_note": "auto_repair_category_to_specific_medication",
    }


def treatment_plan_execution_relation(plan_node: dict, target_node: dict, relation_type: str, batch_id: str) -> dict:
    return {
        "id": stable_code("REL-PLANEXEC", plan_node["code"], relation_type, target_node["code"], batch_id),
        "source_code": plan_node["code"],
        "relationType": relation_type,
        "target_code": target_node["code"],
        "relationCategory": "taxonomy",
        "batch_id": batch_id,
        "schema_version": plan_node.get("schema_version") or target_node.get("schema_version") or "V1.5",
        "review_status": "approved",
        "clinical_review_status": "not_applicable",
        "formal_cdss_ready": False,
        "polarity": "positive",
        "source_note": "auto_repair_treatment_plan_to_execution_entity",
    }


def repair_batch(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir)
    data_dir = batch_dir / "05_data_instance"
    audit_dir = batch_dir / "06_quality_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = data_dir / "nodes_final.jsonl"
    relations_path = data_dir / "relations_final.jsonl"
    nodes = read_jsonl(nodes_path)
    relations = read_jsonl(relations_path)
    batch_id = batch_dir.name

    node_by_code = {node["code"]: node for node in nodes}
    semantic_shell_relation_ids = set()
    for rel in relations:
        source = node_by_code.get(rel.get("source_code"), {})
        target = node_by_code.get(rel.get("target_code"), {})
        if source.get("entityType") == "Disease" and is_semantic_shell(target):
            semantic_shell_relation_ids.add(rel.get("id"))
    relations_after_shell = [rel for rel in relations if rel.get("id") not in semantic_shell_relation_ids]

    active_non_evidence_codes = set()
    for rel in relations_after_shell:
        if rel.get("relationType") == "supported_by_evidence":
            continue
        active_non_evidence_codes.add(rel.get("source_code"))
        active_non_evidence_codes.add(rel.get("target_code"))
    shell_codes_to_remove = {
        node["code"]
        for node in nodes
        if is_semantic_shell(node) and node["code"] not in active_non_evidence_codes
    }
    relations_after_shell = [
        rel
        for rel in relations_after_shell
        if rel.get("source_code") not in shell_codes_to_remove and rel.get("target_code") not in shell_codes_to_remove
    ]
    nodes_after_shell = [node for node in nodes if node.get("code") not in shell_codes_to_remove]
    repaired_technical_display_fields = repair_technical_display_names(nodes_after_shell)
    node_by_code_after_shell = {node["code"]: node for node in nodes_after_shell}
    target_mismatch_relation_ids = set()
    for rel in relations_after_shell:
        if rel.get("relationCategory") not in CORE_CATEGORIES:
            continue
        target = node_by_code_after_shell.get(rel.get("target_code"), {})
        if not target:
            continue
        matched = any(_mentions(text, target) for text in _relation_evidence_texts(rel))
        if rel.get("relationType") == "has_threshold_rule":
            source = node_by_code_after_shell.get(rel.get("source_code"), {})
            matched = any(
                _mentions(text, source) and str(target.get("value", "")) in text
                for text in _relation_evidence_texts(rel)
            )
        if not matched:
            target_mismatch_relation_ids.add(rel.get("id"))
    relations_after_shell = [
        rel for rel in relations_after_shell if rel.get("id") not in target_mismatch_relation_ids
    ]

    medication_nodes = [node for node in nodes_after_shell if node.get("entityType") == "Medication"]
    medication_by_name = {str(node.get("name", "")).strip(): node for node in medication_nodes}
    added_medications = []
    cleaned_medication_aliases = 0
    for class_name, concrete_names in CONCRETE_MEDICATION_ALIASES_BY_CLASS.items():
        class_node = medication_by_name.get(class_name)
        if not class_node:
            continue
        old_aliases = normalize_aliases(class_node.get("aliases"))
        allowed_aliases = MEDICATION_CLASS_ALIASES.get(class_name, [])
        forbidden_aliases = FORBIDDEN_MEDICATION_CLASS_ALIASES_BY_CLASS.get(class_name, set())
        new_aliases = normalize_aliases(
            [alias for alias in old_aliases if alias not in concrete_names and alias not in forbidden_aliases]
            + allowed_aliases
        )
        if new_aliases != old_aliases:
            class_node["aliases"] = new_aliases
            cleaned_medication_aliases += 1
        for medication_name in sorted(concrete_names):
            specific_node = medication_by_name.get(medication_name)
            if specific_node is None:
                specific_node = medication_template(medication_name, class_node, batch_id)
                nodes_after_shell.append(specific_node)
                medication_by_name[medication_name] = specific_node
                added_medications.append(medication_name)

    node_by_code_for_generic_plan_cleanup = {node["code"]: node for node in nodes_after_shell}
    generic_treatment_plan_component_relation_ids = {
        rel.get("id")
        for rel in relations_after_shell
        if rel.get("relationType") in {"includes_medication", "includes_procedure"}
        and str(node_by_code_for_generic_plan_cleanup.get(rel.get("source_code"), {}).get("name", "")).endswith("治疗方案")
    }
    relations_after_shell = [
        rel
        for rel in relations_after_shell
        if rel.get("id") not in generic_treatment_plan_component_relation_ids
    ]

    relation_key = {
        (rel.get("source_code"), rel.get("relationType"), rel.get("target_code"))
        for rel in relations_after_shell
    }
    added_taxonomy_relations = []
    for class_name, concrete_names in CONCRETE_MEDICATION_ALIASES_BY_CLASS.items():
        class_node = medication_by_name.get(class_name)
        if not class_node:
            continue
        for medication_name in sorted(concrete_names):
            specific_node = medication_by_name.get(medication_name)
            if not specific_node:
                continue
            key = (class_node["code"], "has_specific_medication", specific_node["code"])
            if key in relation_key:
                continue
            rel = taxonomy_relation(class_node, specific_node, batch_id)
            relations_after_shell.append(rel)
            relation_key.add(key)
            added_taxonomy_relations.append(rel["id"])

    node_by_name_type = {
        (node.get("entityType"), str(node.get("name", "")).strip()): node
        for node in nodes_after_shell
    }
    node_by_code_current = {node["code"]: node for node in nodes_after_shell}
    incoming_has_treatment_plan = {}
    disease_medication_targets = {}
    disease_procedure_targets = {}
    for rel in relations_after_shell:
        source = node_by_code_current.get(rel.get("source_code"), {})
        target = node_by_code_current.get(rel.get("target_code"), {})
        if rel.get("relationType") == "has_treatment_plan" and source.get("entityType") == "Disease" and target.get("entityType") == "TreatmentPlan":
            incoming_has_treatment_plan.setdefault(target["code"], []).append(source["code"])
        elif rel.get("relationType") == "treated_by_medication" and source.get("entityType") == "Disease" and target.get("entityType") == "Medication":
            disease_medication_targets.setdefault(source["code"], []).append(target["code"])
        elif rel.get("relationType") == "treated_by_procedure" and source.get("entityType") == "Disease" and target.get("entityType") == "Procedure":
            disease_procedure_targets.setdefault(source["code"], []).append(target["code"])

    added_execution_nodes = []
    added_treatment_plan_execution_relations = []

    def ensure_execution_target(entity_type: str, name: str, reference_node: dict) -> dict | None:
        target = node_by_name_type.get((entity_type, name))
        if target:
            return target
        if entity_type == "Procedure":
            target = procedure_template(name, reference_node, batch_id)
        elif entity_type == "Medication":
            target = medication_template(name, reference_node, batch_id)
            target["source_quality"] = "auto_repair_from_treatment_plan_actionability"
        elif entity_type == "ClinicalPathway":
            target = clinical_pathway_template(name, reference_node, batch_id)
        else:
            return None
        nodes_after_shell.append(target)
        node_by_name_type[(entity_type, name)] = target
        node_by_code_current[target["code"]] = target
        added_execution_nodes.append(target["code"])
        return target

    for plan_node in [node for node in nodes_after_shell if node.get("entityType") == "TreatmentPlan"]:
        plan_name = str(plan_node.get("name", "")).strip()
        if plan_node["code"] not in incoming_has_treatment_plan:
            continue
        target_specs = list(TREATMENT_PLAN_EXECUTION_TARGETS.get(plan_name, []))
        if plan_name.endswith("治疗方案"):
            target_specs.append(("has_clinical_pathway", "ClinicalPathway", plan_name.replace("治疗方案", "治疗路径")))
        for relation_type, entity_type, target_name in target_specs:
            target_node = ensure_execution_target(entity_type, target_name, plan_node)
            if not target_node:
                continue
            key = (plan_node["code"], relation_type, target_node["code"])
            if key in relation_key:
                continue
            rel = treatment_plan_execution_relation(plan_node, target_node, relation_type, batch_id)
            relations_after_shell.append(rel)
            relation_key.add(key)
            added_treatment_plan_execution_relations.append(rel["id"])

    medication_by_name = {
        str(node.get("name", "")).strip(): node
        for node in nodes_after_shell
        if node.get("entityType") == "Medication" and str(node.get("name", "")).strip()
    }
    for class_name, concrete_names in CONCRETE_MEDICATION_ALIASES_BY_CLASS.items():
        class_node = medication_by_name.get(class_name)
        if not class_node:
            continue
        for medication_name in sorted(concrete_names):
            specific_node = medication_by_name.get(medication_name)
            if specific_node is None:
                specific_node = medication_template(medication_name, class_node, batch_id)
                nodes_after_shell.append(specific_node)
                medication_by_name[medication_name] = specific_node
                added_medications.append(medication_name)
            key = (class_node["code"], "has_specific_medication", specific_node["code"])
            if key in relation_key:
                continue
            rel = taxonomy_relation(class_node, specific_node, batch_id)
            relations_after_shell.append(rel)
            relation_key.add(key)
            added_taxonomy_relations.append(rel["id"])

    node_review_added = enrich_review_status(nodes_after_shell)
    relation_review_added = enrich_review_status(relations_after_shell)

    write_jsonl(nodes_path, nodes_after_shell)
    write_jsonl(relations_path, relations_after_shell)

    summary = {
        "batch_dir": str(batch_dir),
        "removed_semantic_shell_relations": len(semantic_shell_relation_ids),
        "removed_orphan_semantic_shell_nodes": len(shell_codes_to_remove),
        "removed_target_mismatch_core_relations": len(target_mismatch_relation_ids),
        "removed_generic_treatment_plan_component_relations": len(generic_treatment_plan_component_relation_ids),
        "repaired_technical_display_name_fields": repaired_technical_display_fields,
        "cleaned_medication_class_alias_nodes": cleaned_medication_aliases,
        "added_specific_medication_nodes": len(added_medications),
        "added_medication_taxonomy_relations": len(added_taxonomy_relations),
        "added_treatment_plan_execution_nodes": len(added_execution_nodes),
        "added_treatment_plan_execution_relations": len(added_treatment_plan_execution_relations),
        "node_clinical_review_status_added": node_review_added,
        "relation_clinical_review_status_added": relation_review_added,
    }
    (audit_dir / "semantic_quality_repair_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair semantic-shell nodes and medication class aliases in graph JSONL batches.")
    parser.add_argument("--batch-dir", action="append", type=Path, default=[])
    args = parser.parse_args()
    batch_dirs = args.batch_dir or DEFAULT_BATCH_DIRS
    summaries = [repair_batch(batch_dir) for batch_dir in batch_dirs]
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
