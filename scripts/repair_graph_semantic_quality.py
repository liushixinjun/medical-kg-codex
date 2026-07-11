from __future__ import annotations

import argparse
import copy
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
    EVIDENCE_REQUIRED,
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
    "盐皮质激素受体拮抗剂": ["MRA"],
    "β受体阻滞剂": ["β受体拮抗剂"],
    "血管紧张素转换酶抑制剂": ["ACEI"],
    "血管紧张素Ⅱ受体拮抗剂": ["ARB"],
    "血管紧张素受体脑啡肽酶抑制剂": ["ARNI"],
    "钠-葡萄糖协同转运蛋白2抑制剂": ["SGLT2i", "SGLT2抑制剂"],
    "袢利尿剂": ["环利尿剂", "loop diuretics"],
    "钙通道阻滞剂": ["钙拮抗剂"],
    "他汀类药物": ["他汀"],
    "抗心律失常药物": ["抗心律失常药"],
}

SPECIFIC_MEDICATION_ALIASES = {
    "组织型纤溶酶原激活物": ["t-PA", "rt-PA"],
    "依度沙班": ["艾多沙班"],
    "艾多沙班": ["edoxaban", "依度沙班"],
    "达比加群酯": ["达比加群", "dabigatran"],
    "利伐沙班": ["rivaroxaban"],
    "阿哌沙班": ["apixaban"],
    "华法林": ["warfarin", "VKA", "维生素K拮抗剂"],
    "腺苷": ["adenosine", "ATP", "三磷酸腺苷"],
    "维拉帕米": ["verapamil"],
    "地尔硫卓": ["diltiazem"],
    "普罗帕酮": ["propafenone"],
    "氟卡尼": ["flecainide"],
    "胺碘酮": ["amiodarone"],
    "利多卡因": ["lidocaine"],
    "伊布利特": ["ibutilide"],
    "索他洛尔": ["sotalol"],
    "普萘洛尔": ["propranolol"],
    "奎尼丁": ["quinidine"],
    "硫酸镁": ["镁剂", "magnesium sulfate"],
    "钾剂": ["补钾"],
    "氯化钾": ["potassium chloride", "KCl"],
    "沙库巴曲缬沙坦": ["沙库巴曲/缬沙坦"],
    "达格列净": ["dapagliflozin"],
    "恩格列净": ["empagliflozin"],
    "呋塞米": ["速尿"],
}
CANONICAL_MEDICATION_CODE_BY_NAME = {
    "美托洛尔": "MED-CARD-C9175F150C3D",
    "比索洛尔": "MED-CARD-2CF15595A00F",
    "血管紧张素Ⅱ受体阻滞剂": "MED-CARD-C015B7A5655A",
}
for medication_class, concrete_names in {
    "抗凝药物": {"华法林", "肝素", "普通肝素", "低分子量肝素", "达比加群", "达比加群酯", "利伐沙班", "依度沙班", "阿哌沙班", "艾多沙班"},
    "β受体阻滞剂": {"美托洛尔", "比索洛尔", "卡维地洛", "阿替洛尔"},
    "抗心律失常药物": {"胺碘酮", "利多卡因", "索他洛尔", "普罗帕酮", "奎尼丁", "硫酸镁"},
    "钾剂": {"氯化钾"},
    "袢利尿剂": {"呋塞米", "托拉塞米", "布美他尼"},
    "盐皮质激素受体拮抗剂": {"螺内酯", "依普利酮"},
    "血管紧张素受体脑啡肽酶抑制剂": {"沙库巴曲缬沙坦"},
    "钠-葡萄糖协同转运蛋白2抑制剂": {"达格列净", "恩格列净"},
}.items():
    CONCRETE_MEDICATION_ALIASES_BY_CLASS.setdefault(medication_class, set()).update(concrete_names)
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
    "联合降压治疗": [
        ("includes_medication", "Medication", "血管紧张素转换酶抑制剂"),
        ("includes_medication", "Medication", "血管紧张素Ⅱ受体阻滞剂"),
        ("includes_medication", "Medication", "钙通道阻滞剂"),
        ("includes_medication", "Medication", "利尿剂"),
        ("includes_medication", "Medication", "β受体阻滞剂"),
    ],
    "生活方式干预": [
        ("includes_procedure", "Procedure", "限盐"),
        ("includes_procedure", "Procedure", "减重"),
        ("includes_procedure", "Procedure", "规律运动"),
        ("includes_procedure", "Procedure", "戒烟限酒"),
    ],
    "高血压急症降压治疗": [
        ("includes_medication", "Medication", "拉贝洛尔"),
        ("includes_medication", "Medication", "乌拉地尔"),
        ("includes_medication", "Medication", "尼卡地平"),
        ("includes_medication", "Medication", "硝普钠"),
        ("includes_medication", "Medication", "硝酸甘油"),
    ],
    "氧疗": [("includes_procedure", "Procedure", "吸氧治疗")],
    "复律治疗": [
        ("includes_procedure", "Procedure", "电复律"),
        ("includes_medication", "Medication", "胺碘酮"),
    ],
    "节律控制": [
        ("includes_medication", "Medication", "胺碘酮"),
        ("includes_medication", "Medication", "普罗帕酮"),
        ("includes_medication", "Medication", "氟卡尼"),
        ("includes_medication", "Medication", "决奈达隆"),
        ("includes_medication", "Medication", "索他洛尔"),
        ("includes_procedure", "Procedure", "电复律"),
        ("includes_procedure", "Procedure", "房颤导管消融"),
        ("includes_procedure", "Procedure", "肺静脉隔离"),
    ],
    "心室率控制": [
        ("includes_medication", "Medication", "β受体阻滞剂"),
        ("includes_medication", "Medication", "地尔硫卓"),
        ("includes_medication", "Medication", "维拉帕米"),
        ("includes_medication", "Medication", "地高辛"),
    ],
    "导管消融": [("includes_procedure", "Procedure", "射频导管消融")],
    "射频消融治疗": [("includes_procedure", "Procedure", "导管消融")],
    "电复律除颤": [
        ("includes_procedure", "Procedure", "同步电复律"),
        ("includes_procedure", "Procedure", "电除颤"),
    ],
    "急救复苏": [
        ("includes_procedure", "Procedure", "心肺复苏"),
        ("includes_procedure", "Procedure", "电除颤"),
    ],
    "ICD治疗": [("includes_procedure", "Procedure", "埋藏式心脏转复除颤器")],
    "抗心律失常药物治疗": [
        ("includes_medication", "Medication", "抗心律失常药物"),
        ("includes_medication", "Medication", "胺碘酮"),
        ("includes_medication", "Medication", "利多卡因"),
        ("includes_medication", "Medication", "索他洛尔"),
    ],
    "诱因纠正": [
        ("includes_medication", "Medication", "钾剂"),
        ("includes_medication", "Medication", "硫酸镁"),
    ],
    "起搏治疗": [
        ("includes_procedure", "Procedure", "临时心脏起搏"),
        ("includes_procedure", "Procedure", "永久起搏器植入"),
        ("includes_procedure", "Procedure", "心脏再同步治疗"),
    ],
    "房颤导管消融": [
        ("includes_procedure", "Procedure", "房颤导管消融"),
        ("includes_procedure", "Procedure", "肺静脉隔离"),
    ],
    "急性终止治疗": [
        ("includes_medication", "Medication", "腺苷"),
        ("includes_procedure", "Procedure", "Valsalva动作"),
        ("includes_procedure", "Procedure", "颈动脉窦按摩"),
        ("includes_procedure", "Procedure", "同步直流电复律"),
    ],
    "迷走神经刺激": [
        ("includes_procedure", "Procedure", "Valsalva动作"),
        ("includes_procedure", "Procedure", "颈动脉窦按摩"),
    ],
    "药物转复": [
        ("includes_medication", "Medication", "腺苷"),
        ("includes_medication", "Medication", "普罗帕酮"),
        ("includes_medication", "Medication", "胺碘酮"),
        ("includes_medication", "Medication", "伊布利特"),
    ],
    "同步电复律": [("includes_procedure", "Procedure", "同步直流电复律")],
    "长期药物预防": [
        ("includes_medication", "Medication", "β受体阻滞剂"),
        ("includes_medication", "Medication", "维拉帕米"),
        ("includes_medication", "Medication", "地尔硫卓"),
        ("includes_medication", "Medication", "普罗帕酮"),
        ("includes_medication", "Medication", "氟卡尼"),
        ("includes_medication", "Medication", "索他洛尔"),
    ],
    "抗凝治疗": [
        ("includes_medication", "Medication", "抗凝药物"),
        ("includes_medication", "Medication", "华法林"),
        ("includes_medication", "Medication", "利伐沙班"),
        ("includes_medication", "Medication", "达比加群酯"),
        ("includes_medication", "Medication", "阿哌沙班"),
        ("includes_medication", "Medication", "艾多沙班"),
    ],
    "左心耳封堵": [("includes_procedure", "Procedure", "左心耳封堵术")],
    "综合危险因素管理": [
        ("includes_procedure", "Procedure", "生活方式干预"),
        ("includes_procedure", "Procedure", "危险因素管理"),
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
    "心力衰竭治疗方案": [
        ("includes_medication", "Medication", "血管紧张素受体脑啡肽酶抑制剂"),
        ("includes_medication", "Medication", "β受体阻滞剂"),
        ("includes_medication", "Medication", "盐皮质激素受体拮抗剂"),
        ("includes_medication", "Medication", "钠-葡萄糖协同转运蛋白2抑制剂"),
        ("includes_medication", "Medication", "袢利尿剂"),
    ],
    "射血分数降低的心力衰竭治疗方案": [
        ("includes_medication", "Medication", "血管紧张素受体脑啡肽酶抑制剂"),
        ("includes_medication", "Medication", "β受体阻滞剂"),
        ("includes_medication", "Medication", "盐皮质激素受体拮抗剂"),
        ("includes_medication", "Medication", "钠-葡萄糖协同转运蛋白2抑制剂"),
        ("includes_medication", "Medication", "袢利尿剂"),
    ],
    "射血分数轻度降低的心力衰竭治疗方案": [
        ("includes_medication", "Medication", "钠-葡萄糖协同转运蛋白2抑制剂"),
        ("includes_medication", "Medication", "血管紧张素受体脑啡肽酶抑制剂"),
        ("includes_medication", "Medication", "β受体阻滞剂"),
        ("includes_medication", "Medication", "盐皮质激素受体拮抗剂"),
    ],
    "射血分数保留的心力衰竭治疗方案": [
        ("includes_medication", "Medication", "钠-葡萄糖协同转运蛋白2抑制剂"),
        ("includes_medication", "Medication", "袢利尿剂"),
    ],
    "急性心力衰竭治疗方案": [
        ("includes_medication", "Medication", "袢利尿剂"),
        ("includes_procedure", "Procedure", "氧疗"),
    ],
    "慢性心力衰竭治疗方案": [
        ("includes_medication", "Medication", "血管紧张素受体脑啡肽酶抑制剂"),
        ("includes_medication", "Medication", "β受体阻滞剂"),
        ("includes_medication", "Medication", "盐皮质激素受体拮抗剂"),
        ("includes_medication", "Medication", "钠-葡萄糖协同转运蛋白2抑制剂"),
        ("includes_medication", "Medication", "袢利尿剂"),
    ],
    "左心衰竭治疗方案": [("includes_medication", "Medication", "袢利尿剂")],
    "右心衰竭治疗方案": [("includes_medication", "Medication", "袢利尿剂")],
    "全心衰竭治疗方案": [("includes_medication", "Medication", "袢利尿剂")],
    "心肌梗死后心力衰竭治疗方案": [
        ("includes_medication", "Medication", "β受体阻滞剂"),
        ("includes_medication", "Medication", "血管紧张素转换酶抑制剂"),
        ("includes_medication", "Medication", "血管紧张素Ⅱ受体阻滞剂"),
    ],
    "透析患者慢性心力衰竭治疗方案": [("includes_medication", "Medication", "袢利尿剂")],
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


EVIDENCE_CHAIN_COPY_FIELDS = set(EVIDENCE_REQUIRED) | {
    "evidence_count",
    "provenance_records_json",
    "document_ids",
    "source_names",
    "source_types",
    "source_versions",
    "source_sections",
    "source_pages",
    "guideline_ids",
    "evidence_ids",
    "source_title",
    "source_titles",
    "recommendation_statement",
    "recommendation_context",
    "applicable_population",
    "exclusion_criteria",
    "contraindications",
    "clinical_review_status",
    "cdss_release_level",
    "ai_precheck_status",
    "ai_precheck_note",
    "clinical_effect_review_status",
    "recommendation_grade_source",
}


def copy_evidence_chain(target_rel: dict, reference_rel: dict | None, reason: str) -> dict:
    if not reference_rel:
        return target_rel
    for field in EVIDENCE_CHAIN_COPY_FIELDS:
        value = reference_rel.get(field)
        if value not in (None, ""):
            target_rel[field] = copy.deepcopy(value)
    target_rel["evidence_inherited_from_relation_id"] = reference_rel.get("id", "")
    target_rel["evidence_inherited_from_relation_type"] = reference_rel.get("relationType", "")
    target_rel["evidence_copy_reason"] = reason
    return target_rel


def treatment_plan_execution_relation(
    plan_node: dict,
    target_node: dict,
    relation_type: str,
    batch_id: str,
    reference_rel: dict | None = None,
) -> dict:
    rel = {
        "id": stable_code("REL-PLANEXEC", plan_node["code"], relation_type, target_node["code"], batch_id),
        "source_code": plan_node["code"],
        "relationType": relation_type,
        "target_code": target_node["code"],
        "relationCategory": "therapeutic" if relation_type in {"includes_medication", "includes_procedure", "has_clinical_pathway"} else "taxonomy",
        "batch_id": batch_id,
        "schema_version": plan_node.get("schema_version") or target_node.get("schema_version") or "V1.5",
        "review_status": "approved",
        "clinical_review_status": reference_rel.get("clinical_review_status") if reference_rel else "not_applicable",
        "formal_cdss_ready": False,
        "polarity": "positive",
        "source_note": "auto_repair_treatment_plan_to_execution_entity",
    }
    return copy_evidence_chain(rel, reference_rel, "treatment_plan_execution_inherits_disease_recommendation_evidence")


GRADE_CLASS_RANK = {"Ⅰ": 5, "I": 5, "Ⅱa": 4, "IIa": 4, "Ⅱb": 3, "IIb": 3, "Ⅲ": 2, "III": 2}
GRADE_EVIDENCE_RANK = {"A": 3, "B": 2, "C": 1}
THERAPEUTIC_RELATION_TYPES = {
    "has_treatment_plan",
    "treated_by_medication",
    "treated_by_procedure",
    "has_follow_up",
    "includes_medication",
    "includes_procedure",
}
HF_ROOT_DISEASE_CODE = "DIS-CARD-HF"
HF_ROOT_INHERITABLE_RELATION_TYPES = {
    "has_etiology",
    "has_sign",
    "has_diagnostic_criteria",
    "may_cause_complication",
    "has_follow_up",
}


def best_grade_from_relation(rel: dict) -> tuple[str, str, str]:
    candidates = []
    direct = (str(rel.get("recommendation_class", "")).strip(), str(rel.get("evidence_level", "")).strip())
    if direct[0] not in {"", "N/A", "None"} and direct[1] not in {"", "N/A", "None"}:
        candidates.append((direct[0], direct[1], "relation"))
    for prov in rel.get("provenance_records_json", []):
        if not isinstance(prov, dict):
            continue
        rec_class = str(prov.get("recommendation_class", "")).strip()
        evidence_level = str(prov.get("evidence_level", "")).strip()
        if rec_class in {"", "N/A", "None"} or evidence_level in {"", "N/A", "None"}:
            continue
        candidates.append((rec_class, evidence_level, "provenance"))
    if not candidates:
        return "", "", ""
    return max(
        candidates,
        key=lambda item: (GRADE_CLASS_RANK.get(item[0], 0), GRADE_EVIDENCE_RANK.get(item[1], 0)),
    )


def enrich_cdss_review_fields(nodes: list[dict], relations: list[dict]) -> dict:
    node_by_code = {node.get("code"): node for node in nodes}
    relation_changes = 0
    medication_changes = 0
    for node in nodes:
        if node.get("entityType") != "Medication":
            continue
        if not node.get("dosage"):
            node["dosage"] = "用法用量需依据指南原文、药品说明书、肾功能、电解质、血压/心率及临床状态个体化；未完成专家审核前不得自动给药。"
            medication_changes += 1
        if not node.get("contraindications"):
            node["contraindications"] = "存在药品说明书或指南列明禁忌证、严重不良反应风险、不能耐受或临床判断不适用者禁用或慎用。"
            medication_changes += 1
        if not node.get("drug_interactions"):
            node["drug_interactions"] = "需审核与RAAS抑制剂、ARNI、MRA、SGLT2抑制剂、利尿剂、抗心律失常药、抗凝/抗血小板药等联用风险。"
            medication_changes += 1
    for rel in relations:
        if rel.get("relationType") not in THERAPEUTIC_RELATION_TYPES and rel.get("relationCategory") != "therapeutic":
            continue
        source = node_by_code.get(rel.get("source_code"), {})
        target = node_by_code.get(rel.get("target_code"), {})
        source_name = source.get("name") or "相关疾病"
        target_name = target.get("name") or "相关治疗"
        if not rel.get("applicable_population"):
            rel["applicable_population"] = f"{source_name}患者中符合{target_name}适应证、且经临床评估获益大于风险者。"
            relation_changes += 1
        if not rel.get("exclusion_criteria"):
            rel["exclusion_criteria"] = "存在明确禁忌证、不能耐受、严重不良反应风险、证据语境不匹配或临床判断不适用者排除；正式CDSS启用前需专家审核。"
            relation_changes += 1
        if not rel.get("recommendation_context"):
            rel["recommendation_context"] = "由指南/教材证据链抽取形成的治疗推荐候选，供专家按临床使用效果审核。"
            relation_changes += 1
        rec_class, evidence_level, grade_source = best_grade_from_relation(rel)
        if rec_class and evidence_level and rel.get("recommendation_class") in (None, "", "N/A"):
            rel["recommendation_class"] = rec_class
            rel["evidence_level"] = evidence_level
            rel["recommendation_grade_source"] = grade_source
            relation_changes += 1
        if not rel.get("clinical_review_status"):
            rel["clinical_review_status"] = "pending_clinical_review"
            relation_changes += 1
        rel["formal_cdss_ready"] = False
    return {
        "relation_cdss_review_fields_added": relation_changes,
        "medication_safety_fields_added": medication_changes,
    }


def disambiguate_duplicate_guideline_names(nodes: list[dict]) -> int:
    grouped: dict[str, list[dict]] = {}
    for node in nodes:
        if node.get("entityType") != "Guideline":
            continue
        grouped.setdefault(str(node.get("name", "")).strip(), []).append(node)
    changed = 0
    for name, duplicates in grouped.items():
        if not name or len(duplicates) <= 1:
            continue
        for node in duplicates:
            suffix = str(node.get("document_id") or node.get("sha256") or node.get("code", "")).strip()
            if len(suffix) > 18 and re.fullmatch(r"[A-Fa-f0-9]+", suffix):
                suffix = suffix[:16]
            if not suffix:
                continue
            new_name = f"{name}（来源标识：{suffix}）"
            for field in ("name", "preferred_name", "display_name"):
                if node.get(field) != new_name:
                    node[field] = new_name
                    changed += 1
            node.setdefault("original_title", name)
    return changed


def inherit_hf_required_pathways_from_root(nodes: list[dict], relations: list[dict], batch_id: str) -> int:
    node_by_code = {node.get("code"): node for node in nodes}
    if HF_ROOT_DISEASE_CODE not in node_by_code:
        return 0
    existing_keys = {(rel.get("source_code"), rel.get("relationType"), rel.get("target_code")) for rel in relations}
    root_relations = [
        rel
        for rel in relations
        if rel.get("source_code") == HF_ROOT_DISEASE_CODE
        and rel.get("relationType") in HF_ROOT_INHERITABLE_RELATION_TYPES
    ]
    if not root_relations:
        return 0
    subtype_codes = [
        node.get("code")
        for node in nodes
        if node.get("entityType") == "Disease"
        and str(node.get("code", "")).startswith("DIS-CARD-HF-")
        and node.get("code") != HF_ROOT_DISEASE_CODE
    ]
    added = 0
    for disease_code in subtype_codes:
        for root_rel in root_relations:
            key = (disease_code, root_rel.get("relationType"), root_rel.get("target_code"))
            if key in existing_keys:
                continue
            inherited = dict(root_rel)
            inherited["id"] = stable_code("REL-HFINHERIT", disease_code, root_rel.get("relationType", ""), root_rel.get("target_code", ""), batch_id)
            inherited["source_code"] = disease_code
            inherited["batch_id"] = batch_id
            inherited["source_quality"] = "inherited_from_root_heart_failure_with_source_trace"
            inherited["inherited_from_disease_code"] = HF_ROOT_DISEASE_CODE
            inherited["inherited_from_relation_id"] = root_rel.get("id", "")
            inherited["clinical_review_status"] = root_rel.get("clinical_review_status") or "pending_clinical_review"
            inherited["formal_cdss_ready"] = False
            inherited.setdefault("scope_type", root_rel.get("scope_type", "category"))
            inherited.setdefault("scope_target", root_rel.get("scope_target", "心力衰竭"))
            relations.append(inherited)
            existing_keys.add(key)
            added += 1
    return added


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
        if (
            not matched
            and rel.get("relationType") == "has_treatment_plan"
            and target.get("entityType") == "TreatmentPlan"
        ):
            matched = any(re.search(r"治疗|方案|管理|用药|干预", text) for text in _relation_evidence_texts(rel))
        if (
            not matched
            and rel.get("relationType") == "has_follow_up"
            and target.get("entityType") == "FollowUp"
        ):
            matched = any(re.search(r"随访|复查|监测|管理", text) for text in _relation_evidence_texts(rel))
        if not matched and rel.get("relationType") == "has_etiology" and target.get("entityType") == "Etiology":
            matched = any(re.search(r"病因|原因|导致|引起|继发|由.+所致", text) for text in _relation_evidence_texts(rel))
        if (
            not matched
            and rel.get("relationType") == "has_diagnostic_criteria"
            and target.get("entityType") == "DiagnosisCriteria"
        ):
            matched = any(re.search(r"诊断|标准|依据|符合|满足", text) for text in _relation_evidence_texts(rel))
        if not matched and rel.get("relationType") == "has_prognosis" and target.get("entityType") == "Prognosis":
            matched = any(re.search(r"预后|死亡|风险|结局|再入院", text) for text in _relation_evidence_texts(rel))
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
    direct_therapeutic_relations = {}
    for rel in relations_after_shell:
        source = node_by_code_current.get(rel.get("source_code"), {})
        target = node_by_code_current.get(rel.get("target_code"), {})
        if rel.get("relationType") == "has_treatment_plan" and source.get("entityType") == "Disease" and target.get("entityType") == "TreatmentPlan":
            incoming_has_treatment_plan.setdefault(target["code"], []).append(rel)
        elif rel.get("relationType") == "treated_by_medication" and source.get("entityType") == "Disease" and target.get("entityType") == "Medication":
            disease_medication_targets.setdefault(source["code"], []).append(target["code"])
            direct_therapeutic_relations.setdefault((source["code"], target["code"]), []).append(rel)
        elif rel.get("relationType") == "treated_by_procedure" and source.get("entityType") == "Disease" and target.get("entityType") == "Procedure":
            disease_procedure_targets.setdefault(source["code"], []).append(target["code"])
            direct_therapeutic_relations.setdefault((source["code"], target["code"]), []).append(rel)

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

    def evidence_mentions_target(rel: dict | None, target_node: dict) -> bool:
        if not rel:
            return False
        return any(_mentions(text, target_node) for text in _relation_evidence_texts(rel))

    def best_execution_reference(incoming_plan_rels: list[dict], target_node: dict) -> dict | None:
        for rel in incoming_plan_rels:
            if evidence_mentions_target(rel, target_node):
                return rel
        for disease_code in (rel.get("source_code") for rel in incoming_plan_rels if rel.get("source_code")):
            for rel in direct_therapeutic_relations.get((disease_code, target_node["code"]), []):
                if evidence_mentions_target(rel, target_node):
                    return rel
        return None

    for plan_node in [node for node in nodes_after_shell if node.get("entityType") == "TreatmentPlan"]:
        plan_name = str(plan_node.get("name", "")).strip()
        if plan_node["code"] not in incoming_has_treatment_plan:
            continue
        incoming_plan_rels = incoming_has_treatment_plan.get(plan_node["code"], [])
        reference_plan_rel = next(
            (
                rel
                for rel in incoming_plan_rels
                if all(rel.get(field) not in (None, "") for field in EVIDENCE_REQUIRED)
            ),
            incoming_plan_rels[0] if incoming_plan_rels else None,
        )
        target_specs = list(TREATMENT_PLAN_EXECUTION_TARGETS.get(plan_name, []))
        for relation_type, entity_type, target_name in target_specs:
            target_node = ensure_execution_target(entity_type, target_name, plan_node)
            if not target_node:
                continue
            key = (plan_node["code"], relation_type, target_node["code"])
            if key in relation_key:
                continue
            target_reference_rel = best_execution_reference(incoming_plan_rels, target_node)
            if not target_reference_rel:
                continue
            rel = treatment_plan_execution_relation(plan_node, target_node, relation_type, batch_id, target_reference_rel)
            relations_after_shell.append(rel)
            relation_key.add(key)
            added_treatment_plan_execution_relations.append(rel["id"])
            if relation_type == "has_clinical_pathway":
                for disease_plan_rel in incoming_plan_rels:
                    disease_code = disease_plan_rel.get("source_code")
                    disease_node = node_by_code_current.get(disease_code)
                    if not disease_node:
                        continue
                    disease_key = (disease_node["code"], "has_clinical_pathway", target_node["code"])
                    if disease_key in relation_key:
                        continue
                    disease_rel = treatment_plan_execution_relation(
                        disease_node,
                        target_node,
                        "has_clinical_pathway",
                        batch_id,
                        disease_plan_rel,
                    )
                    disease_rel["source_note"] = "auto_repair_disease_to_treatment_pathway_for_cdss_review"
                    relations_after_shell.append(disease_rel)
                    relation_key.add(disease_key)
                    added_treatment_plan_execution_relations.append(disease_rel["id"])

    treatment_action_relation_types = {
        "includes_medication",
        "includes_procedure",
        "has_timing",
        "has_follow_up",
        "has_clinical_pathway",
        "has_indication",
        "has_contraindication",
    }
    action_plan_codes = {
        rel.get("source_code")
        for rel in relations_after_shell
        if rel.get("relationType") in treatment_action_relation_types
    }
    generic_treatment_plan_codes = {
        node["code"]
        for node in nodes_after_shell
        if node.get("entityType") == "TreatmentPlan"
        and str(node.get("name", "")).strip().endswith("治疗方案")
        and node["code"] not in action_plan_codes
    }
    if generic_treatment_plan_codes:
        relations_after_shell = [
            rel
            for rel in relations_after_shell
            if rel.get("source_code") not in generic_treatment_plan_codes
            and rel.get("target_code") not in generic_treatment_plan_codes
        ]
        nodes_after_shell = [node for node in nodes_after_shell if node["code"] not in generic_treatment_plan_codes]

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
    duplicate_guideline_name_fields_repaired = disambiguate_duplicate_guideline_names(nodes_after_shell)
    inherited_required_pathway_relations = inherit_hf_required_pathways_from_root(
        nodes_after_shell,
        relations_after_shell,
        batch_id,
    )
    cdss_review_summary = enrich_cdss_review_fields(nodes_after_shell, relations_after_shell)

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
        "removed_generic_treatment_plan_nodes": len(generic_treatment_plan_codes),
        "node_clinical_review_status_added": node_review_added,
        "relation_clinical_review_status_added": relation_review_added,
        "duplicate_guideline_name_fields_repaired": duplicate_guideline_name_fields_repaired,
        "inherited_required_pathway_relations": inherited_required_pathway_relations,
        **cdss_review_summary,
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
