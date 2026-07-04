from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient, cleaned_props, cypher_name


CARD_COLLECTION = Path("心血管内科文献集合")
CAD_BATCH = "BATCH-CARD-CAD-20260623-001"
CM_BATCH = "BATCH-CARD-CM-20260622-001"

INVALID_THROMBOLYSIS_DISEASES = {
    "DIS-CARD-CAD-STABLE-ANGINA",
    "DIS-CARD-CAD-CCS",
    "DIS-CARD-CAD-OLD-MI",
    "DIS-CARD-CAD-ICM",
    "DIS-CARD-CAD-UA",
    "DIS-CARD-CAD-NSTEMI",
}
ACS_CONDITIONAL_REPERFUSION_DISEASES = {"DIS-CARD-CAD-ACS", "DIS-CARD-CAD-AMI"}
STEMI_REPERFUSION_DISEASES = {"DIS-CARD-CAD-STEMI"}
ARRHYTHMIA_CONDITIONAL_PLAN_DISEASES = {
    "DIS-CARD-CAD-ACS",
    "DIS-CARD-CAD-UA",
    "DIS-CARD-CAD-NSTEMI",
}

HCM_DISEASE_CODE = "DIS-CARD-CM-HCM"
HCM_CCB_TARGET = "MED-NDHP-CCB"

SYNONYM_CANONICAL_CODES = {
    "MED-CARD-36D5B18BD8D3": "MED-BETA-BLOCKER",
    "MED-CARD-C015B7A5655A": "MED-CARD-TEXT-B905AF3E59",
}

CANONICAL_MEDICATION_NODE_PATCHES = {
    "MED-BETA-BLOCKER": {
        "name": "β受体阻滞剂",
        "preferred_name": "β受体阻滞剂",
        "display_name": "β受体阻滞剂",
        "aliases": ["β受体拮抗剂", "beta blocker"],
        "terminology_repair_reason": "同义词归一：β受体拮抗剂归并为β受体阻滞剂，原名进入别名。",
    },
    "MED-CARD-TEXT-B905AF3E59": {
        "name": "血管紧张素Ⅱ受体拮抗剂",
        "preferred_name": "血管紧张素Ⅱ受体拮抗剂",
        "display_name": "血管紧张素Ⅱ受体拮抗剂",
        "aliases": ["ARB", "血管紧张素Ⅱ受体阻滞剂", "血管紧张素受体阻滞剂", "沙坦类药物"],
        "terminology_repair_reason": "同义词归一：ARB/血管紧张素Ⅱ受体阻滞剂归并为血管紧张素Ⅱ受体拮抗剂。",
    },
}

DEFINITION_REPAIRS = {
    "DIS-CARD-CM-ACM": {
        "description": "致心律失常性心肌病是一组以心肌结构和功能异常、心肌纤维脂肪样替代或瘢痕形成、室性心律失常和心源性猝死风险增高为主要特征的心肌病谱系，可累及右心室、左心室或双心室。",
        "definition_evidence_text": "致心律失常性心肌病是一组以心肌结构和功能异常、心肌纤维脂肪样替代或瘢痕形成、室性心律失常和心源性猝死风险增高为主要特征的心肌病谱系，可累及右心室、左心室或双心室。",
        "definition_source_type": "curated_authoritative_definition_repair",
        "definition_source": "中国心肌病综合管理指南2025；ESC Cardiomyopathy Guidelines 2023；本轮修复用于替换RCM/HCM污染定义。",
    },
    "DIS-CARD-CM-AMYLOID": {
        "description": "淀粉样变心肌病是由淀粉样蛋白沉积于心肌间质和血管等部位引起的浸润性心肌病，常表现为心室壁增厚、舒张/限制性充盈障碍、传导异常、心律失常和心力衰竭，可见于AL型或ATTR型等淀粉样变。",
        "definition_evidence_text": "淀粉样变心肌病是由淀粉样蛋白沉积于心肌间质和血管等部位引起的浸润性心肌病，常表现为心室壁增厚、舒张/限制性充盈障碍、传导异常、心律失常和心力衰竭，可见于AL型或ATTR型等淀粉样变。",
        "definition_source_type": "curated_authoritative_definition_repair",
        "definition_source": "中国心肌病综合管理指南2025；ESC Cardiomyopathy Guidelines 2023；本轮修复用于替换RCM污染定义。",
    },
    "DIS-CARD-CM-ATRIAL": {
        "description": "心房心肌病是指心房结构、收缩、舒张或电生理特性发生异常并具有潜在临床相关表现的一组心房病变，可与房性心律失常、血栓栓塞风险增加和心功能异常相关。",
        "definition_evidence_text": "心房心肌病是指心房结构、收缩、舒张或电生理特性发生异常并具有潜在临床相关表现的一组心房病变，可与房性心律失常、血栓栓塞风险增加和心功能异常相关。",
        "definition_source_type": "curated_authoritative_definition_repair",
        "definition_source": "ESC/EHRA atrial cardiomyopathy consensus；本轮修复用于替换HCM污染定义。",
    },
    "DIS-CARD-CM-FABRY": {
        "description": "法布雷病心肌病是法布雷病累及心脏所致的贮积性心肌病，通常由α-半乳糖苷酶A活性缺乏导致糖鞘脂在心肌细胞、传导系统和血管内皮等部位沉积，常表现为左心室肥厚、心律失常、传导异常、心绞痛样症状和心力衰竭风险。",
        "definition_evidence_text": "法布雷病心肌病是法布雷病累及心脏所致的贮积性心肌病，通常由α-半乳糖苷酶A活性缺乏导致糖鞘脂在心肌细胞、传导系统和血管内皮等部位沉积，常表现为左心室肥厚、心律失常、传导异常、心绞痛样症状和心力衰竭风险。",
        "definition_source_type": "curated_authoritative_definition_repair",
        "definition_source": "中国心肌病综合管理指南2025；ESC Cardiomyopathy Guidelines 2023；本轮修复用于替换RCM污染定义。",
    },
}

POLLUTION_MARKERS = {
    "DIS-CARD-CM-ACM": ["RCM", "HCM", "限制性"],
    "DIS-CARD-CM-AMYLOID": ["RCM", "限制性"],
    "DIS-CARD-CM-ATRIAL": ["HCM", "流出道梗阻", "饮酒"],
    "DIS-CARD-CM-FABRY": ["RCM", "限制性"],
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8-sig",
    )


def node_name(nodes_by_code: dict[str, dict[str, Any]], code: str) -> str:
    return str(nodes_by_code.get(code, {}).get("name") or "")


def node_type(nodes_by_code: dict[str, dict[str, Any]], code: str) -> str:
    return str(nodes_by_code.get(code, {}).get("entityType") or "")


def normalize_aliases(*values: Any) -> list[str]:
    seen = set()
    aliases = []
    for value in values:
        if value is None:
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                aliases.append(text)
    return aliases


def set_props(row: dict[str, Any], props: dict[str, Any]) -> bool:
    changed = False
    for key, value in props.items():
        if row.get(key) != value:
            row[key] = value
            changed = True
    return changed


def is_polluted_definition(node: dict[str, Any]) -> bool:
    markers = POLLUTION_MARKERS.get(str(node.get("code")))
    if not markers:
        return False
    text = f"{node.get('description', '')} {node.get('definition_evidence_text', '')}"
    return any(marker in text for marker in markers)


def repair_definitions(nodes_by_code: dict[str, dict[str, Any]]) -> int:
    count = 0
    for code, props in DEFINITION_REPAIRS.items():
        node = nodes_by_code.get(code)
        if not node:
            continue
        patch = {
            **props,
            "clinical_review_status": node.get("clinical_review_status") or "pending_clinical_review",
            "formal_cdss_ready": False,
            "definition_repair_reason": "2026-06-29 Claude临床使用效果审核后核验：原definition/description存在跨病种污染，已直接替换为对应病种定义。",
        }
        if is_polluted_definition(node) or any(node.get(k) != v for k, v in patch.items()):
            if set_props(node, patch):
                count += 1
    return count


def repair_canonical_medication_nodes(nodes_by_code: dict[str, dict[str, Any]]) -> int:
    count = 0
    for code, props in CANONICAL_MEDICATION_NODE_PATCHES.items():
        node = nodes_by_code.get(code)
        if not node:
            continue
        aliases = normalize_aliases(props.get("aliases"), node.get("aliases"))
        patch = {
            **{key: value for key, value in props.items() if key != "aliases"},
            "aliases": aliases,
            "clinical_review_status": node.get("clinical_review_status") or "pending_clinical_review",
            "formal_cdss_ready": False,
        }
        if set_props(node, patch):
            count += 1
    return count


def is_invalid_thrombolysis_relation(
    relation: dict[str, Any], nodes_by_code: dict[str, dict[str, Any]]
) -> bool:
    source = relation.get("source_code")
    if source not in INVALID_THROMBOLYSIS_DISEASES:
        return False
    target = relation.get("target_code")
    target_name = node_name(nodes_by_code, target)
    target_type = node_type(nodes_by_code, target)
    relation_type = relation.get("relationType")
    if target_type not in {"TreatmentPlan", "Procedure", "Medication"}:
        return False
    if relation_type not in {
        "has_treatment_plan",
        "treated_by_procedure",
        "treated_by_medication",
        "includes_medication",
        "includes_procedure",
    }:
        return False
    if "溶栓" in target_name:
        return True
    return target_type == "TreatmentPlan" and target_name == "再灌注治疗"


def conditionally_mark_acs_reperfusion(
    relation: dict[str, Any], nodes_by_code: dict[str, dict[str, Any]]
) -> bool:
    if relation.get("source_code") not in ACS_CONDITIONAL_REPERFUSION_DISEASES:
        return False
    target_name = node_name(nodes_by_code, relation.get("target_code"))
    if target_name not in {"再灌注治疗", "溶栓治疗", "溶栓药物"}:
        return False
    return set_props(
        relation,
        {
            "applicable_population": "急性冠脉综合征中明确ST段抬高型心肌梗死或符合急诊再灌注/溶栓指征、且不能及时接受直接PCI的患者；非ST段抬高型心肌梗死和不稳定型心绞痛不得按此路径自动推荐溶栓。",
            "exclusion_criteria": "非ST段抬高型心肌梗死、不稳定型心绞痛、稳定型心绞痛、慢性冠脉综合征、陈旧性心肌梗死、出血高风险或存在溶栓禁忌证者，不得触发溶栓推荐。",
            "clinical_rule_or_clinical_pathway": "STEMI急诊再灌注/溶栓适应证路径",
            "clinical_review_status": "pending_clinical_review",
            "formal_cdss_ready": False,
            "safety_repair_reason": "ACS/AMI总称下再灌注/溶栓路径补充STEMI适用条件，避免非STEMI/UA误触发。",
        },
    )


def conditionally_mark_arrhythmia_plan(
    relation: dict[str, Any], nodes_by_code: dict[str, dict[str, Any]]
) -> bool:
    if relation.get("source_code") not in ARRHYTHMIA_CONDITIONAL_PLAN_DISEASES:
        return False
    target_name = node_name(nodes_by_code, relation.get("target_code"))
    if target_name != "复律治疗":
        return False
    return set_props(
        relation,
        {
            "applicable_population": "合并持续性、症状性或血流动力学不稳定心律失常，且经临床评估需要复律或抗心律失常治疗的患者。",
            "exclusion_criteria": "无心律失常、无需复律、存在胺碘酮禁忌或药物相互作用风险未评估者，不得触发胺碘酮或复律治疗推荐。",
            "clinical_rule_or_clinical_pathway": "ACS合并心律失常复律/抗心律失常治疗路径",
            "clinical_review_status": "pending_clinical_review",
            "formal_cdss_ready": False,
            "safety_repair_reason": "复律/胺碘酮仅限合并心律失常场景，禁止作为ACS/UA/NSTEMI主路径常规推荐。",
        },
    )


def repair_hcm_relation(
    relation: dict[str, Any], nodes_by_code: dict[str, dict[str, Any]]
) -> tuple[bool, bool]:
    if relation.get("source_code") != HCM_DISEASE_CODE:
        return False, False
    target = relation.get("target_code")
    target_name = node_name(nodes_by_code, target)
    if relation.get("relationType") == "treated_by_procedure" and target_name == "经皮冠状动脉介入治疗":
        return True, False
    if relation.get("relationType") == "treated_by_medication" and target_name in {"钙通道阻滞剂", "非二氢吡啶类钙通道阻滞剂"}:
        if HCM_CCB_TARGET in nodes_by_code:
            relation["target_code"] = HCM_CCB_TARGET
        changed = set_props(
            relation,
            {
                "applicable_population": "有症状肥厚型心肌病患者，优先评估左室流出道梗阻状态；非梗阻性HCM或经临床评估适合使用非二氢吡啶类钙通道阻滞剂且β受体阻滞剂不耐受/禁忌者，可作为症状控制选择。",
                "exclusion_criteria": "未评估梗阻状态、重度左室流出道梗阻且血流动力学不稳定、低血压、严重心力衰竭、显著传导阻滞、窦房/房室结功能异常或存在药物相互作用风险未评估者，不得自动推荐。",
                "clinical_rule_or_clinical_pathway": "HCM症状控制用药路径：先分型评估LVOTO，再个体化选择β受体阻滞剂或非二氢吡啶类钙通道阻滞剂。",
                "clinical_review_status": "pending_clinical_review",
                "formal_cdss_ready": False,
                "safety_repair_reason": "HCM钙通道阻滞剂由宽泛药物类改为非二氢吡啶类，并补充梗阻/禁忌条件。",
            },
        )
        return False, changed
    return False, False


def retarget_synonym_medications(relation: dict[str, Any]) -> bool:
    changed = False
    source = relation.get("source_code")
    target = relation.get("target_code")
    if source in SYNONYM_CANONICAL_CODES:
        relation["source_code"] = SYNONYM_CANONICAL_CODES[source]
        changed = True
    if target in SYNONYM_CANONICAL_CODES:
        relation["target_code"] = SYNONYM_CANONICAL_CODES[target]
        changed = True
    if changed:
        set_props(
            relation,
            {
                "terminology_repair_reason": "药物同义词实体归一，关系已改挂标准药物实体。",
                "clinical_review_status": relation.get("clinical_review_status") or "pending_clinical_review",
                "formal_cdss_ready": False,
            },
        )
    return changed


def dedupe_semantic_relations(relations: list[dict[str, Any]]) -> int:
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    deduped = []
    removed = 0
    for relation in relations:
        key = (
            str(relation.get("source_code")),
            str(relation.get("relationType")),
            str(relation.get("target_code")),
        )
        if key in seen:
            kept = seen[key]
            for field, value in relation.items():
                if field not in kept or kept[field] in (None, "", []):
                    kept[field] = value
            removed += 1
            continue
        seen[key] = relation
        deduped.append(relation)
    if removed:
        relations[:] = deduped
    return removed


def remove_orphan_synonym_nodes(nodes: list[dict[str, Any]], relations: list[dict[str, Any]]) -> int:
    referenced = {rel.get("source_code") for rel in relations} | {rel.get("target_code") for rel in relations}
    remove_codes = {code for code in SYNONYM_CANONICAL_CODES if code not in referenced}
    before = len(nodes)
    nodes[:] = [node for node in nodes if node.get("code") not in remove_codes]
    return before - len(nodes)


def repair_rows(nodes: list[dict[str, Any]], relations: list[dict[str, Any]], batch_id: str) -> dict[str, int]:
    nodes_by_code = {str(node.get("code")): node for node in nodes}
    summary = {
        "updated_polluted_definition_nodes": repair_definitions(nodes_by_code),
        "updated_canonical_medication_nodes": repair_canonical_medication_nodes(nodes_by_code),
        "deleted_invalid_thrombolysis_relations": 0,
        "conditioned_acs_reperfusion_relations": 0,
        "conditioned_arrhythmia_plan_relations": 0,
        "deleted_hcm_pci_relations": 0,
        "retargeted_hcm_ccb_relations": 0,
        "retargeted_synonym_medication_relations": 0,
        "removed_duplicate_semantic_relations": 0,
        "removed_orphan_synonym_nodes": 0,
    }
    repaired_relations = []
    for relation in relations:
        if is_invalid_thrombolysis_relation(relation, nodes_by_code):
            summary["deleted_invalid_thrombolysis_relations"] += 1
            continue
        delete_hcm, changed_hcm_ccb = repair_hcm_relation(relation, nodes_by_code)
        if delete_hcm:
            summary["deleted_hcm_pci_relations"] += 1
            continue
        if changed_hcm_ccb:
            summary["retargeted_hcm_ccb_relations"] += 1
        if conditionally_mark_acs_reperfusion(relation, nodes_by_code):
            summary["conditioned_acs_reperfusion_relations"] += 1
        if conditionally_mark_arrhythmia_plan(relation, nodes_by_code):
            summary["conditioned_arrhythmia_plan_relations"] += 1
        if retarget_synonym_medications(relation):
            summary["retargeted_synonym_medication_relations"] += 1
        repaired_relations.append(relation)
    relations[:] = repaired_relations
    summary["removed_duplicate_semantic_relations"] = dedupe_semantic_relations(relations)
    summary["removed_orphan_synonym_nodes"] = remove_orphan_synonym_nodes(nodes, relations)
    return summary


def diff_operations(
    before_nodes: list[dict[str, Any]],
    after_nodes: list[dict[str, Any]],
    before_relations: list[dict[str, Any]],
    after_relations: list[dict[str, Any]],
) -> dict[str, Any]:
    before_nodes_by_code = {node["code"]: node for node in before_nodes}
    after_nodes_by_code = {node["code"]: node for node in after_nodes}
    before_rel_by_id = {rel["id"]: rel for rel in before_relations}
    after_rel_by_id = {rel["id"]: rel for rel in after_relations}
    updated_nodes = [
        node
        for code, node in after_nodes_by_code.items()
        if code not in before_nodes_by_code or before_nodes_by_code[code] != node
    ]
    deleted_node_codes = [code for code in before_nodes_by_code if code not in after_nodes_by_code]
    deleted_relation_ids = [rel_id for rel_id in before_rel_by_id if rel_id not in after_rel_by_id]
    upsert_relations = []
    for rel_id, relation in after_rel_by_id.items():
        if rel_id not in before_rel_by_id or before_rel_by_id[rel_id] != relation:
            before = before_rel_by_id.get(rel_id)
            if before and (
                before.get("source_code") != relation.get("source_code")
                or before.get("target_code") != relation.get("target_code")
                or before.get("relationType") != relation.get("relationType")
            ):
                deleted_relation_ids.append(rel_id)
            upsert_relations.append(relation)
    return {
        "updated_nodes": updated_nodes,
        "deleted_node_codes": deleted_node_codes,
        "deleted_relation_ids": sorted(set(deleted_relation_ids)),
        "upsert_relations": upsert_relations,
    }


def repair_batch(batch_dir: Path) -> dict[str, Any]:
    data_dir = batch_dir / "05_data_instance"
    nodes_path = data_dir / "nodes_final.jsonl"
    relations_path = data_dir / "relations_final.jsonl"
    nodes = read_jsonl(nodes_path)
    relations = read_jsonl(relations_path)
    before_nodes = deepcopy(nodes)
    before_relations = deepcopy(relations)
    summary = repair_rows(nodes, relations, batch_dir.name)
    if nodes != before_nodes:
        write_jsonl(nodes_path, nodes)
    if relations != before_relations:
        write_jsonl(relations_path, relations)
    operations = diff_operations(before_nodes, nodes, before_relations, relations)
    return {
        "batch_dir": str(batch_dir),
        "batch_id": batch_dir.name,
        "summary": summary,
        "operations": operations,
        "input_node_count": len(before_nodes),
        "output_node_count": len(nodes),
        "input_relation_count": len(before_relations),
        "output_relation_count": len(relations),
    }


def parse_db_link(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    urls = re.findall(r"(?:https?|bolt)://[^\s，,；;]+", text)
    http = next((url for url in urls if url.startswith("http")), "")
    username_match = re.search(r"(?:用户名|username|user)\s*[:：=]\s*([^\s，,；;]+)", text, re.I)
    password_match = re.search(r"(?:密码|password|pwd)\s*[:：=]\s*([^\s，,；;]+)", text, re.I)
    if not http or not username_match or not password_match:
        raise ValueError("数据库链接文件缺少 http 地址、用户名或密码。")
    return {
        "http": http,
        "username": username_match.group(1).strip(),
        "password": password_match.group(1).strip(),
    }


def rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {col: item["row"][idx] for idx, col in enumerate(result["results"][0]["columns"])}
        for item in result["results"][0]["data"]
    ]


def upsert_nodes(client: Neo4jHttpClient, nodes: list[dict[str, Any]]) -> int:
    if not nodes:
        return 0
    by_type: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        entity_type = str(node.get("entityType") or "")
        by_type.setdefault(entity_type, []).append({"code": node["code"], "props": cleaned_props(node)})
    merged = 0
    for entity_type, group in by_type.items():
        label = cypher_name(entity_type)
        result = client.run(
            f"""
            UNWIND $rows AS row
            MERGE (n:KGNode:{label} {{code: row.code}})
            SET n += row.props
            RETURN count(n) AS merged
            """,
            {"rows": group},
        )
        merged += int(rows(result)[0]["merged"] or 0)
    return merged


def upsert_relations(client: Neo4jHttpClient, relations: list[dict[str, Any]]) -> int:
    if not relations:
        return 0
    by_type: dict[str, list[dict[str, Any]]] = {}
    for relation in relations:
        by_type.setdefault(str(relation["relationType"]), []).append(
            {
                "id": relation["id"],
                "source_code": relation["source_code"],
                "target_code": relation["target_code"],
                "props": cleaned_props(relation),
            }
        )
    merged = 0
    for relation_type, group in by_type.items():
        rel_type = cypher_name(relation_type)
        result = client.run(
            f"""
            UNWIND $rows AS row
            MATCH (s:KGNode {{code: row.source_code}})
            MATCH (t:KGNode {{code: row.target_code}})
            MERGE (s)-[r:{rel_type} {{id: row.id}}]->(t)
            SET r += row.props
            RETURN count(r) AS merged
            """,
            {"rows": group},
        )
        merged += int(rows(result)[0]["merged"] or 0)
    return merged


def apply_server_operations(client: Neo4jHttpClient, operations: dict[str, Any]) -> dict[str, int]:
    deleted_relationships = 0
    relation_ids = sorted(set(operations.get("deleted_relation_ids") or []))
    if relation_ids:
        result = client.run(
            """
            MATCH ()-[r]->()
            WHERE r.id IN $ids
            DELETE r
            RETURN count(r) AS deleted
            """,
            {"ids": relation_ids},
        )
        deleted_relationships = int(rows(result)[0]["deleted"] or 0)
    merged_nodes = upsert_nodes(client, operations.get("updated_nodes") or [])
    merged_relations = upsert_relations(client, operations.get("upsert_relations") or [])
    deleted_nodes = 0
    deleted_node_codes = sorted(set(operations.get("deleted_node_codes") or []))
    if deleted_node_codes:
        result = client.run(
            """
            UNWIND $codes AS code
            OPTIONAL MATCH (n:KGNode {code: code})
            WITH n
            WHERE n IS NOT NULL AND NOT (n)--()
            DELETE n
            RETURN count(n) AS deleted
            """,
            {"codes": deleted_node_codes},
        )
        deleted_nodes = int(rows(result)[0]["deleted"] or 0)
    return {
        "deleted_relationships": deleted_relationships,
        "merged_nodes": merged_nodes,
        "merged_relations": merged_relations,
        "deleted_orphan_nodes": deleted_nodes,
    }


def delete_server_invalid_semantic_edges(client: Neo4jHttpClient) -> dict[str, int]:
    invalid_thrombolysis = client.run(
        """
        MATCH (d:KGNode)-[r]->(t:KGNode)
        WHERE d.code IN ['DIS-CARD-CAD-STABLE-ANGINA','DIS-CARD-CAD-CCS','DIS-CARD-CAD-OLD-MI','DIS-CARD-CAD-ICM','DIS-CARD-CAD-UA','DIS-CARD-CAD-NSTEMI']
          AND type(r) IN ['has_treatment_plan','treated_by_procedure','treated_by_medication','includes_medication','includes_procedure']
          AND t.entityType IN ['TreatmentPlan','Procedure','Medication']
          AND (t.name CONTAINS '溶栓' OR t.name='再灌注治疗')
        DELETE r
        RETURN count(r) AS deleted
        """
    )
    hcm_pci = client.run(
        """
        MATCH (:KGNode {code:'DIS-CARD-CM-HCM'})-[r:treated_by_procedure]->(:KGNode {name:'经皮冠状动脉介入治疗'})
        DELETE r
        RETURN count(r) AS deleted
        """
    )
    return {
        "deleted_invalid_thrombolysis_semantic_edges": int(rows(invalid_thrombolysis)[0]["deleted"] or 0),
        "deleted_hcm_pci_semantic_edges": int(rows(hcm_pci)[0]["deleted"] or 0),
    }


def merge_server_synonym_medication_nodes(client: Neo4jHttpClient) -> dict[str, int]:
    moved_incoming = 0
    moved_outgoing = 0
    deleted_duplicates = 0
    for duplicate_code, canonical_code in SYNONYM_CANONICAL_CODES.items():
        exists = rows(
            client.run(
                """
                OPTIONAL MATCH (dup:KGNode {code:$duplicate_code})
                OPTIONAL MATCH (can:KGNode {code:$canonical_code})
                RETURN count(dup) AS duplicate_exists, count(can) AS canonical_exists
                """,
                {"duplicate_code": duplicate_code, "canonical_code": canonical_code},
            )
        )[0]
        if not exists["duplicate_exists"] or not exists["canonical_exists"]:
            continue

        incoming_types = [
            row["rel_type"]
            for row in rows(
                client.run(
                    """
                    MATCH (:KGNode)-[r]->(:KGNode {code:$duplicate_code})
                    RETURN DISTINCT type(r) AS rel_type
                    """,
                    {"duplicate_code": duplicate_code},
                )
            )
        ]
        for relation_type in incoming_types:
            rel_type = cypher_name(relation_type)
            result = client.run(
                f"""
                MATCH (dup:KGNode {{code:$duplicate_code}})
                MATCH (can:KGNode {{code:$canonical_code}})
                MATCH (src:KGNode)-[r:{rel_type}]->(dup)
                WITH src, r, can, properties(r) AS props
                MERGE (src)-[nr:{rel_type}]->(can)
                ON CREATE SET nr = props
                SET nr.terminology_repair_reason = coalesce(
                    nr.terminology_repair_reason,
                    '同义药物重复节点合并：关系已迁移到标准药物实体'
                )
                WITH r
                DELETE r
                RETURN count(r) AS moved
                """,
                {"duplicate_code": duplicate_code, "canonical_code": canonical_code},
            )
            moved_incoming += int(rows(result)[0]["moved"] or 0)

        outgoing_types = [
            row["rel_type"]
            for row in rows(
                client.run(
                    """
                    MATCH (:KGNode {code:$duplicate_code})-[r]->(:KGNode)
                    RETURN DISTINCT type(r) AS rel_type
                    """,
                    {"duplicate_code": duplicate_code},
                )
            )
        ]
        for relation_type in outgoing_types:
            rel_type = cypher_name(relation_type)
            result = client.run(
                f"""
                MATCH (dup:KGNode {{code:$duplicate_code}})
                MATCH (can:KGNode {{code:$canonical_code}})
                MATCH (dup)-[r:{rel_type}]->(dst:KGNode)
                WITH can, r, dst, properties(r) AS props
                MERGE (can)-[nr:{rel_type}]->(dst)
                ON CREATE SET nr = props
                SET nr.terminology_repair_reason = coalesce(
                    nr.terminology_repair_reason,
                    '同义药物重复节点合并：关系已迁移到标准药物实体'
                )
                WITH r
                DELETE r
                RETURN count(r) AS moved
                """,
                {"duplicate_code": duplicate_code, "canonical_code": canonical_code},
            )
            moved_outgoing += int(rows(result)[0]["moved"] or 0)

        deleted = rows(
            client.run(
                """
                MATCH (dup:KGNode {code:$duplicate_code})
                DETACH DELETE dup
                RETURN count(dup) AS deleted
                """,
                {"duplicate_code": duplicate_code},
            )
        )[0]["deleted"]
        deleted_duplicates += int(deleted or 0)
    return {
        "moved_incoming_synonym_relations": moved_incoming,
        "moved_outgoing_synonym_relations": moved_outgoing,
        "deleted_duplicate_synonym_nodes": deleted_duplicates,
    }


def verify_targeted_server_state(client: Neo4jHttpClient) -> dict[str, Any]:
    queries = {
        "cm_polluted_definition_count": """
            MATCH (n:KGNode {entityType:'Disease'})
            WHERE n.code IN ['DIS-CARD-CM-ACM','DIS-CARD-CM-AMYLOID','DIS-CARD-CM-ATRIAL','DIS-CARD-CM-FABRY']
              AND (
                (n.code='DIS-CARD-CM-ACM' AND (n.description CONTAINS 'RCM' OR n.description CONTAINS 'HCM'))
                OR (n.code IN ['DIS-CARD-CM-AMYLOID','DIS-CARD-CM-FABRY'] AND n.description CONTAINS 'RCM')
                OR (n.code='DIS-CARD-CM-ATRIAL' AND (n.description CONTAINS 'HCM' OR n.description CONTAINS '流出道梗阻'))
              )
            RETURN count(n) AS value
        """,
        "invalid_thrombolysis_relation_count": """
            MATCH (d:KGNode)-[r]->(t:KGNode)
            WHERE d.code IN ['DIS-CARD-CAD-STABLE-ANGINA','DIS-CARD-CAD-CCS','DIS-CARD-CAD-OLD-MI','DIS-CARD-CAD-ICM','DIS-CARD-CAD-UA','DIS-CARD-CAD-NSTEMI']
              AND type(r) IN ['has_treatment_plan','treated_by_procedure','treated_by_medication','includes_medication','includes_procedure']
              AND t.entityType IN ['TreatmentPlan','Procedure','Medication']
              AND (t.name CONTAINS '溶栓' OR t.name='再灌注治疗')
            RETURN count(r) AS value
        """,
        "hcm_pci_relation_count": """
            MATCH (:KGNode {code:'DIS-CARD-CM-HCM'})-[r:treated_by_procedure]->(p:KGNode {name:'经皮冠状动脉介入治疗'})
            RETURN count(r) AS value
        """,
        "hcm_broad_ccb_relation_count": """
            MATCH (:KGNode {code:'DIS-CARD-CM-HCM'})-[r:treated_by_medication]->(m:KGNode {name:'钙通道阻滞剂'})
            RETURN count(r) AS value
        """,
        "hcm_ndhp_ccb_conditioned_count": """
            MATCH (:KGNode {code:'DIS-CARD-CM-HCM'})-[r:treated_by_medication]->(m:KGNode {code:'MED-NDHP-CCB'})
            WHERE r.applicable_population IS NOT NULL AND r.exclusion_criteria IS NOT NULL
            RETURN count(r) AS value
        """,
        "dcm_beta_synonym_duplicate_relation_count": """
            MATCH (:KGNode {code:'DIS-CARD-CM-DCM'})-[r:treated_by_medication]->(m:KGNode)
            WHERE m.name IN ['β受体拮抗剂','血管紧张素Ⅱ受体阻滞剂']
            RETURN count(r) AS value
        """,
    }
    return {name: rows(client.run(query))[0]["value"] for name, query in queries.items()}


def merge_operations(batch_results: list[dict[str, Any]]) -> dict[str, Any]:
    merged = {
        "updated_nodes": [],
        "deleted_node_codes": [],
        "deleted_relation_ids": [],
        "upsert_relations": [],
    }
    for result in batch_results:
        ops = result["operations"]
        for key in merged:
            merged[key].extend(ops.get(key) or [])
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Directly repair CAD/CM clinical safety issues identified after Claude review.")
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--db-link", type=Path, default=Path("图谱数据库链接.txt"))
    parser.add_argument("--apply-server", action="store_true")
    parser.add_argument("--summary-out", type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    batch_dirs = [
        workspace / CARD_COLLECTION / CAD_BATCH,
        workspace / CARD_COLLECTION / CM_BATCH,
    ]
    results = [repair_batch(batch_dir) for batch_dir in batch_dirs]
    out_dir = workspace / CARD_COLLECTION / "09_增量补丁_delta" / "20260629_CAD_CM_clinical_safety_direct_repair"
    out_dir.mkdir(parents=True, exist_ok=True)
    merged_ops = merge_operations(results)
    summary = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "repair_scope": [CAD_BATCH, CM_BATCH],
        "policy": "confirmed_wrong_delete; conditional_valid_relation_add_conditions; polluted_definition_replace_directly",
        "batch_results": results,
        "merged_operation_counts": {
            "updated_nodes": len(merged_ops["updated_nodes"]),
            "deleted_node_codes": len(merged_ops["deleted_node_codes"]),
            "deleted_relation_ids": len(merged_ops["deleted_relation_ids"]),
            "upsert_relations": len(merged_ops["upsert_relations"]),
        },
    }
    if args.apply_server:
        db = parse_db_link((workspace / args.db_link).resolve())
        client = Neo4jHttpClient(db["http"], db["username"], db["password"], "neo4j", 5, 1)
        client.run("RETURN 1 AS ok")
        summary["server_apply"] = apply_server_operations(client, merged_ops)
        summary["server_semantic_cleanup"] = delete_server_invalid_semantic_edges(client)
        summary["server_synonym_merge"] = merge_server_synonym_medication_nodes(client)
        summary["server_targeted_verification"] = verify_targeted_server_state(client)
    summary_path = args.summary_out or out_dir / "direct_repair_operation_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["created_at", "repair_scope", "merged_operation_counts"] if k in summary}, ensure_ascii=False))
    if "server_apply" in summary:
        print(json.dumps({"server_apply": summary["server_apply"], "server_semantic_cleanup": summary["server_semantic_cleanup"], "server_synonym_merge": summary["server_synonym_merge"], "server_targeted_verification": summary["server_targeted_verification"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
