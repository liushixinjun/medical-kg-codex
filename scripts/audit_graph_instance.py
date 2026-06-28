from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ALLOWED_ENTITY_TYPES = {
    "Specialty", "DiseaseCategory", "DiseaseSubcategory", "Disease",
    "Symptom", "Sign", "Etiology", "Pathophysiology", "Epidemiology",
    "RiskFactor", "Complication", "Prognosis", "Exam", "LabTest",
    "ExamIndicator", "ThresholdRule", "DiagnosisCriteria",
    "DifferentialDiagnosis", "RiskStratification", "ScoringScale",
    "ClinicalRule", "PatientState", "ClinicalEvent", "ClassificationStage",
    "TreatmentPlan", "Medication", "Procedure", "Indication",
    "Contraindication", "TreatmentTiming", "TimeWindow", "FollowUp",
    "DrugInteraction", "AdverseEffect", "ClinicalPathway", "Guideline",
    "Evidence", "RecommendationStatement",
}

ALLOWED_DIRECTIONS = {
    "has_category": ({"Specialty"}, {"DiseaseCategory"}),
    "has_subcategory": ({"DiseaseCategory"}, {"DiseaseSubcategory"}),
    "has_disease": ({"DiseaseSubcategory"}, {"Disease"}),
    "belongs_to_subcategory": ({"Disease"}, {"DiseaseSubcategory"}),
    "belongs_to_category": ({"Disease"}, {"DiseaseCategory"}),
    "has_etiology": ({"Disease"}, {"Etiology"}),
    "has_pathophysiology": ({"Disease"}, {"Pathophysiology"}),
    "has_epidemiology": ({"Disease"}, {"Epidemiology"}),
    "has_risk_factor": ({"Disease"}, {"RiskFactor"}),
    "has_symptom": ({"Disease"}, {"Symptom"}),
    "has_sign": ({"Disease"}, {"Sign"}),
    "may_cause_complication": ({"Disease"}, {"Complication"}),
    "has_prognosis": ({"Disease"}, {"Prognosis"}),
    "requires_exam": ({"Disease"}, {"Exam"}),
    "requires_lab_test": ({"Disease"}, {"LabTest"}),
    "exam_has_indicator": ({"Exam"}, {"ExamIndicator"}),
    "lab_test_has_indicator": ({"LabTest"}, {"ExamIndicator"}),
    "has_threshold_rule": ({"ExamIndicator"}, {"ThresholdRule"}),
    "has_diagnostic_criteria": ({"Disease"}, {"DiagnosisCriteria"}),
    "differentiates_from": ({"Disease"}, {"Disease", "DifferentialDiagnosis"}),
    "has_risk_stratification": ({"Disease"}, {"RiskStratification"}),
    "uses_scoring_scale": ({"Disease"}, {"ScoringScale"}),
    "has_clinical_rule": ({"Disease"}, {"ClinicalRule"}),
    "has_classification_stage": ({"Disease"}, {"ClassificationStage"}),
    "has_treatment_plan": ({"Disease"}, {"TreatmentPlan"}),
    "treated_by_medication": ({"Disease"}, {"Medication"}),
    "treated_by_procedure": ({"Disease"}, {"Procedure"}),
    "includes_medication": ({"TreatmentPlan"}, {"Medication"}),
    "includes_procedure": ({"TreatmentPlan"}, {"Procedure"}),
    "has_specific_medication": ({"Medication"}, {"Medication"}),
    "has_indication": ({"Medication", "Procedure"}, {"Indication"}),
    "has_contraindication": ({"Medication", "Procedure"}, {"Contraindication"}),
    "has_timing": ({"TreatmentPlan", "Procedure"}, {"TreatmentTiming"}),
    "has_time_window": ({"TreatmentTiming"}, {"TimeWindow"}),
    "has_follow_up": ({"Disease", "TreatmentPlan"}, {"FollowUp"}),
    "has_clinical_pathway": ({"Disease", "TreatmentPlan"}, {"ClinicalPathway"}),
    "interacts_with": ({"Medication"}, {"Medication", "DrugInteraction"}),
    "based_on_guideline": ({"Disease"}, {"Guideline"}),
    "guideline_has_evidence": ({"Guideline"}, {"Evidence"}),
    "supported_by_evidence": (ALLOWED_ENTITY_TYPES - {"Evidence", "Guideline", "Specialty", "DiseaseCategory", "DiseaseSubcategory"}, {"Evidence"}),
    "derived_from": ({"RecommendationStatement"}, {"Evidence"}),
}

CORE_CATEGORIES = {"clinical", "diagnostic", "therapeutic", "risk", "rule"}
RECOMMENDATION_CONFLICT_RELATIONS = {
    "requires_exam",
    "requires_lab_test",
    "has_threshold_rule",
    "has_diagnostic_criteria",
    "has_risk_stratification",
    "has_treatment_plan",
    "treated_by_medication",
    "treated_by_procedure",
    "may_cause_complication",
    "has_prognosis",
    "has_follow_up",
}
NODE_REQUIRED = {"id", "code", "name", "preferred_name", "display_name", "entityType", "entityCategory", "schema_version", "review_status"}
REL_REQUIRED = {"id", "source_code", "relationType", "target_code", "relationCategory", "batch_id", "schema_version", "review_status"}
EVIDENCE_REQUIRED = {"document_id", "segment_id", "source_name", "source_type", "source_version", "source_section", "source_page", "evidence_text", "guideline_id", "evidence_id", "recommendation_class", "evidence_level", "confidence"}
BAD_MEDICATION_STANDARD_NAMES = {
    "ACEI",
    "ARB",
    "ACEI/ARB",
    "DAPT",
    "GDMT",
    "NOAC",
    "DOAC",
    "MRA",
    "ARNI",
    "SGLT2I",
}
SEMANTIC_SHELL_NAMES = {
    "DifferentialDiagnosis": {"鉴别诊断", "鉴别", "除外", "排除"},
    "DiagnosisCriteria": {"诊断标准", "诊断", "确诊", "诊断依据", "临床诊断"},
    "TreatmentPlan": {"治疗", "治疗方案", "治疗原则", "一般治疗", "药物治疗", "非药物治疗"},
    "FollowUp": {"随访", "定期随访", "随访方案", "长期随访", "复查"},
    "Prognosis": {"预后", "预后良好", "预后不良", "预后不佳"},
    "RiskStratification": {"风险分层", "危险分层", "风险评估", "评分", "危险因素评估"},
}
CONCRETE_MEDICATION_ALIASES_BY_CLASS = {
    "抗凝药物": {"华法林", "肝素", "低分子量肝素", "普通肝素", "达比加群", "利伐沙班", "依度沙班", "阿哌沙班", "艾多沙班"},
    "溶栓药物": {"尿激酶", "链激酶", "阿替普酶", "替奈普酶", "瑞替普酶", "组织型纤溶酶原激活物"},
    "抗血小板药物": {"阿司匹林", "氯吡格雷", "替格瑞洛", "普拉格雷", "西洛他唑"},
    "硝酸酯类药物": {"硝酸甘油", "单硝酸异山梨酯", "硝酸异山梨酯"},
    "醛固酮受体拮抗剂": {"螺内酯", "依普利酮"},
    "β受体阻滞剂": {"美托洛尔", "比索洛尔", "卡维地洛", "阿替洛尔"},
    "血管紧张素转换酶抑制剂": {"卡托普利", "依那普利", "培哚普利", "雷米普利", "贝那普利"},
    "血管紧张素Ⅱ受体阻滞剂": {"缬沙坦", "氯沙坦", "坎地沙坦", "厄贝沙坦", "替米沙坦"},
    "钙通道阻滞剂": {"氨氯地平", "硝苯地平", "地尔硫卓", "维拉帕米"},
    "他汀类药物": {"阿托伐他汀", "瑞舒伐他汀", "辛伐他汀", "普伐他汀"},
}
FORBIDDEN_MEDICATION_CLASS_ALIASES_BY_CLASS = {
    "抗凝药物": {"口服抗凝药", "新型口服抗凝药", "NOAC", "DOAC"},
    "溶栓药物": {"溶栓治疗", "t-PA", "rt-PA", "r-PA", "TNK-tPA"},
    "抗血小板药物": {"DAPT"},
    "硝酸酯类药物": {"含硝酸甘油"},
}
CONCRETE_MEDICATION_ALIASES_BY_CLASS.update(
    {
        "P2Y12受体抑制剂": {"氯吡格雷", "替格瑞洛", "普拉格雷"},
        "β受体拮抗剂": {"美托洛尔", "比索洛尔", "卡维地洛", "阿替洛尔"},
        "利尿剂": {"呋塞米", "托拉塞米", "氢氯噻嗪"},
        "洋地黄类药物": {"地高辛"},
        "血管紧张素Ⅱ受体拮抗剂": {"缬沙坦", "氯沙坦", "坎地沙坦", "厄贝沙坦", "替米沙坦"},
        "非二氢吡啶类钙通道阻滞剂": {"维拉帕米", "地尔硫䓬"},
    }
)
THERAPEUTIC_RECOMMENDATION_RELATIONS = {
    "has_treatment_plan",
    "treated_by_medication",
    "treated_by_procedure",
    "includes_medication",
    "includes_procedure",
}
CDSS_CLINICAL_APPROVED_STATUSES = {
    "clinical_approved",
    "expert_approved",
    "approved_by_clinical_expert",
}
TECHNICAL_DISPLAY_NAME_RE = re.compile(r"^[A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+$")
TECHNICAL_DISPLAY_NAME_EXCLUDED_TYPES = {"Evidence", "Guideline"}
TREATMENT_PLAN_ACTION_RELATIONS = {
    "includes_medication",
    "includes_procedure",
    "has_timing",
    "has_follow_up",
    "has_clinical_pathway",
    "has_indication",
    "has_contraindication",
}
MEDICATION_CLASS_NAME_MARKERS = (
    "药物",
    "药",
    "剂",
    "抑制剂",
    "阻滞剂",
    "拮抗剂",
)
MEDICATION_CLASS_EXCLUDED_NAMES = {
    "肝素",
    "普通肝素",
    "低分子量肝素",
    "华法林",
    "阿司匹林",
    "氯吡格雷",
    "替格瑞洛",
    "普拉格雷",
    "西洛他唑",
    "阿托伐他汀",
    "瑞舒伐他汀",
    "辛伐他汀",
    "普伐他汀",
    "硝酸甘油",
    "单硝酸异山梨酯",
    "硝酸异山梨酯",
    "美托洛尔",
    "比索洛尔",
    "卡维地洛",
    "阿替洛尔",
    "胺碘酮",
    "地高辛",
    "呋塞米",
    "螺内酯",
    "依普利酮",
    "维拉帕米",
    "地尔硫䓬",
    "尿激酶",
    "链激酶",
    "阿替普酶",
    "替奈普酶",
    "瑞替普酶",
    "组织型纤溶酶原激活物",
    "达比加群",
    "利伐沙班",
    "依度沙班",
    "阿哌沙班",
}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _contains_local_path(value) -> bool:
    if isinstance(value, str):
        return bool(re.search(r"(?:^|[\s\"'])[A-Za-z]:[\\/]", value))
    if isinstance(value, list):
        return any(_contains_local_path(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_local_path(item) for item in value.values())
    return False


def _mentions(text: str, node: dict) -> bool:
    names = [node.get("name", ""), node.get("name_en", ""), node.get("abbr", "")]
    aliases = node.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [item for item in aliases.split(",") if item]
    names.extend(aliases)
    for name in (item for item in names if item):
        if name.isascii() and len(name) <= 8:
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", text, re.IGNORECASE):
                return True
        elif name.lower() in text.lower():
            return True
    return False


def _medication_name_error(node: dict) -> str:
    if node.get("entityType") != "Medication":
        return ""
    name = str(node.get("name", "")).strip()
    normalized = name.upper().replace(" ", "")
    if not name:
        return "empty_medication_name"
    if normalized in BAD_MEDICATION_STANDARD_NAMES:
        return "abbreviation_used_as_standard_name"
    if "/" in name:
        return "combined_abbreviation_or_drug_class_used_as_standard_name"
    if re.fullmatch(r"[A-Za-z0-9+\-_.]+", name):
        return "english_abbreviation_used_as_standard_name"
    if re.search(r"\d+\s*(?:mg|g|ml|mL|μg|ug|IU|U)\b", name, re.IGNORECASE):
        return "dose_or_specification_embedded_in_standard_name"
    return ""


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def _first_present(data: dict, fields: tuple[str, ...]):
    for field in fields:
        value = data.get(field)
        if value not in (None, "", []):
            return value
    return None


def _is_semantic_shell_node(node: dict) -> bool:
    name = str(node.get("name", "")).strip()
    entity_type = node.get("entityType", "")
    return name in SEMANTIC_SHELL_NAMES.get(entity_type, set())


def _clinical_review_status(rel: dict, target: dict) -> str:
    return str(
        _first_present(
            rel,
            ("clinical_review_status", "clinicalReviewStatus", "expert_review_status"),
        )
        or _first_present(
            target,
            ("clinical_review_status", "clinicalReviewStatus", "expert_review_status"),
        )
        or ""
    )


def _has_any_relation(relation_index: dict, source_code: str, relation_types: tuple[str, ...]) -> bool:
    return any(relation_index[(source_code, relation_type)] for relation_type in relation_types)


def _has_outgoing_relation(relation_index: dict, source_code: str, relation_types: set[str]) -> bool:
    return any(relation_index[(source_code, relation_type)] for relation_type in relation_types)


def _is_medication_class(node: dict) -> bool:
    if node.get("entityType") != "Medication":
        return False
    name = str(node.get("name", "")).strip()
    if not name or name in MEDICATION_CLASS_EXCLUDED_NAMES:
        return False
    if name in CONCRETE_MEDICATION_ALIASES_BY_CLASS:
        return True
    return any(marker in name for marker in MEDICATION_CLASS_NAME_MARKERS)


def _has_applicability(rel: dict, target: dict) -> bool:
    fields = (
        "applicable_population",
        "applicability",
        "patient_population",
        "patient_scope",
        "patient_state",
        "适用人群",
    )
    return bool(_first_present(rel, fields) or _first_present(target, fields))


def _has_exclusion(rel: dict, target: dict, relation_index: dict) -> bool:
    fields = (
        "exclusion_criteria",
        "excluded_population",
        "exclusion_conditions",
        "contraindication",
        "contraindications",
        "排除条件",
        "禁忌证",
    )
    if _first_present(rel, fields) or _first_present(target, fields):
        return True
    return target.get("entityType") in {"Medication", "Procedure"} and _has_any_relation(
        relation_index,
        target.get("code", ""),
        ("has_contraindication",),
    )


def _has_recommendation_grade(rel: dict) -> bool:
    rec_class = rel.get("recommendation_class")
    evidence_level = rel.get("evidence_level")
    return rec_class not in (None, "", "N/A") and evidence_level not in (None, "", "N/A")


def _has_medication_dose(node: dict) -> bool:
    return bool(_first_present(node, ("dosage", "dose", "dose_range", "standard_dosage", "用法用量", "剂量")))


def _has_medication_interaction(node: dict, relation_index: dict) -> bool:
    if _first_present(node, ("drug_interactions", "interaction", "interactions", "相互作用")):
        return True
    return _has_any_relation(relation_index, node.get("code", ""), ("interacts_with",))


def _technical_display_name_errors(node: dict) -> list[dict]:
    if node.get("entityType") in TECHNICAL_DISPLAY_NAME_EXCLUDED_TYPES:
        return []
    code = str(node.get("code", "")).strip()
    rows = []
    for field in ("name", "preferred_name", "display_name"):
        value = str(node.get(field, "")).strip()
        if not value:
            continue
        if value == code or TECHNICAL_DISPLAY_NAME_RE.fullmatch(value):
            rows.append(
                {
                    "code": code,
                    "entityType": node.get("entityType", ""),
                    "field": field,
                    "bad_value": value,
                    "aliases": ";".join(str(item) for item in _as_list(node.get("aliases"))),
                    "abbr": ";".join(str(item) for item in _as_list(node.get("abbr"))),
                    "error_type": "technical_code_used_as_clinical_display_name",
                    "solution": "code 只能作为技术编码；name/preferred_name/display_name 必须使用临床可读中文标准名，缩写写入 abbr，其他名称写入 aliases。",
                }
            )
    return rows


def _relation_evidence_texts(rel: dict) -> list[str]:
    texts = [rel.get("evidence_text", "")]
    texts.extend(
        prov.get("evidence_text", "")
        for prov in rel.get("provenance_records_json", [])
        if isinstance(prov, dict)
    )
    return [text for text in texts if text]


DEFINITION_CUE_RE = re.compile(
    r"(?:\u662f\u4e00\u7c7b|\u662f\u6307|\u5b9a\u4e49\u4e3a|\u4e3a\u7279\u5f81|defined as|characteri[sz]ed by)",
    re.IGNORECASE,
)


def _has_definition_candidate(disease: dict, evidence_relations: list[dict], node_by_code: dict[str, dict]) -> bool:
    for rel in evidence_relations:
        evidence = node_by_code.get(rel.get("target_code"), {})
        text = evidence.get("evidence_text", "")
        if DEFINITION_CUE_RE.search(text) and _mentions(text, disease):
            return True
    return False


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def _source_year(prov: dict) -> int:
    text = " ".join(str(prov.get(field, "")) for field in ("source_version", "source_name"))
    years = [int(item) for item in re.findall(r"(?:19|20)\d{2}", text)]
    return max(years) if years else 0


def _source_region_rank(source_name: str) -> tuple[int, str]:
    name = source_name.lower()
    if any(marker in source_name for marker in ("中国", "中华", "中文")) or " cn " in f" {name} " or name.endswith(" cn.pdf"):
        return 3, "CN"
    if any(marker in name for marker in ("esc", "acc", "aha", "eacts", "jacc", "circulation")):
        return 2, "INTL"
    return 1, "OTHER"


def _source_type_rank(source_type: str) -> int:
    return {"guideline": 4, "consensus": 3, "authoritative_textbook": 2}.get(source_type, 1)


def _grade_rank(recommendation_class: str, evidence_level: str) -> tuple[int, int]:
    class_rank = {"Ⅰ": 5, "I": 5, "Ⅱa": 4, "IIa": 4, "Ⅱb": 3, "IIb": 3, "Ⅲ": 2, "III": 2}
    evidence_rank = {"A": 3, "B": 2, "C": 1}
    return class_rank.get(recommendation_class, 0), evidence_rank.get(evidence_level, 0)


def _primary_conflict_source(provenance_records: list[dict]) -> dict:
    candidates = [
        prov
        for prov in provenance_records
        if prov.get("recommendation_class") not in (None, "", "N/A")
    ]
    if not candidates:
        return {}
    return max(
        candidates,
        key=lambda prov: (
            _source_region_rank(prov.get("source_name", ""))[0],
            _source_year(prov),
            _source_type_rank(prov.get("source_type", "")),
            *_grade_rank(prov.get("recommendation_class", ""), prov.get("evidence_level", "")),
        ),
    )


def audit_graph(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir).resolve()
    data_dir = batch_dir / "05_data_instance"
    audit_dir = batch_dir / "06_quality_audit"
    review_dir = batch_dir / "07_review_package"
    audit_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    config_path = batch_dir / "00_scope_and_config" / "batch_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
    scope_target = config.get("scope_target") or "专科"
    nodes = _jsonl(data_dir / "nodes_final.jsonl")
    relations = _jsonl(data_dir / "relations_final.jsonl")
    node_by_code = {node["code"]: node for node in nodes}

    unknown_entity = [node for node in nodes if node.get("entityType") not in ALLOWED_ENTITY_TYPES]
    unknown_relation = [rel for rel in relations if rel.get("relationType") not in ALLOWED_DIRECTIONS]
    missing_node_fields = [node["code"] for node in nodes if any(field not in node or node[field] in (None, "") for field in NODE_REQUIRED)]
    missing_relation_fields = [rel.get("id", "") for rel in relations if any(field not in rel or rel[field] in (None, "") for field in REL_REQUIRED)]
    code_counts = Counter(node["code"] for node in nodes)
    duplicate_codes = [code for code, count in code_counts.items() if count > 1]
    type_name_counts = Counter((node["entityType"], node["name"]) for node in nodes)
    duplicate_type_names = [key for key, count in type_name_counts.items() if count > 1]
    dangling = [rel for rel in relations if rel.get("source_code") not in node_by_code or rel.get("target_code") not in node_by_code]
    semantic_counts = Counter((rel.get("source_code"), rel.get("relationType"), rel.get("target_code")) for rel in relations)
    duplicate_semantics = [key for key, count in semantic_counts.items() if count > 1]

    wrong_direction = []
    for rel in relations:
        if rel.get("relationType") not in ALLOWED_DIRECTIONS or rel in dangling:
            continue
        source_types, target_types = ALLOWED_DIRECTIONS[rel["relationType"]]
        if node_by_code[rel["source_code"]]["entityType"] not in source_types or node_by_code[rel["target_code"]]["entityType"] not in target_types:
            wrong_direction.append(rel)

    path_pollution = [item for item in nodes + relations if _contains_local_path(item)]
    unicode_errors = [item for item in nodes + relations if "\ufffd" in json.dumps(item, ensure_ascii=False) or any(marker in json.dumps(item, ensure_ascii=False) for marker in ("锟", "斤拷", "烫烫", "屯屯"))]
    numeric_nodes = [node for node in nodes if re.fullmatch(r"\s*[+-]?\d+(?:\.\d+)?\s*(?:%|[A-Za-z]+)?\s*", node.get("name", ""))]
    medication_name_errors = [
        {
            "code": node.get("code", ""),
            "name": node.get("name", ""),
            "entityType": node.get("entityType", ""),
            "error_type": _medication_name_error(node),
            "solution": "使用中文标准通用名或中文标准药物类别名作为 Medication.name；英文缩写、组合缩写、商品名、剂量写入 abbr/aliases/属性或拆分为治疗方案",
        }
        for node in nodes
        if _medication_name_error(node)
    ]
    technical_display_name_errors = [
        row
        for node in nodes
        for row in _technical_display_name_errors(node)
    ]

    core_relations = [rel for rel in relations if rel.get("relationCategory") in CORE_CATEGORIES]
    evidence_complete = [rel for rel in core_relations if all(field in rel and rel[field] not in (None, "") for field in EVIDENCE_REQUIRED) and rel.get("evidence_count", 0) == len(rel.get("provenance_records_json", []))]
    core_rate = len(evidence_complete) / len(core_relations) if core_relations else 1.0

    specific_medication_nodes_by_class_code = defaultdict(list)
    for rel in relations:
        if rel.get("relationType") != "has_specific_medication":
            continue
        source = node_by_code.get(rel.get("source_code"), {})
        target = node_by_code.get(rel.get("target_code"), {})
        if source.get("entityType") == "Medication" and target.get("entityType") == "Medication":
            specific_medication_nodes_by_class_code[source.get("code", "")].append(target)

    target_match_count = 0
    target_match_failures = []
    for rel in core_relations:
        texts = _relation_evidence_texts(rel)
        target = node_by_code.get(rel.get("target_code"), {})
        matched = any(_mentions(text, target) for text in texts)
        if not matched and target.get("entityType") == "Medication":
            matched = any(
                _mentions(text, specific_node)
                for text in texts
                for specific_node in specific_medication_nodes_by_class_code.get(target.get("code", ""), [])
            )
        if rel.get("relationType") == "has_threshold_rule" and target:
            source = node_by_code.get(rel.get("source_code"), {})
            matched = any(
                _mentions(text, source) and str(target.get("value", "")) in text
                for text in texts
            )
        if matched:
            target_match_count += 1
        else:
            target_match_failures.append(rel["id"])
    target_match_rate = target_match_count / len(core_relations) if core_relations else 1.0

    disease_nodes = [node for node in nodes if node.get("entityType") == "Disease"]
    disease_evidence_relations = [rel for rel in relations if rel.get("relationType") == "supported_by_evidence" and node_by_code.get(rel.get("source_code"), {}).get("entityType") == "Disease"]
    disease_relevance_failures = []
    def _is_contextually_anchored_evidence(rel: dict, disease: dict, evidence: dict) -> bool:
        if (
            evidence.get("disease_code") == disease.get("code")
            or evidence.get("disease_name") == disease.get("name")
        ):
            return True
        for prov in rel.get("provenance_records_json", []):
            if (
                prov.get("disease_code") == disease.get("code")
                or prov.get("disease_name") == disease.get("name")
            ):
                return True
        return False

    for rel in disease_evidence_relations:
        disease = node_by_code[rel["source_code"]]
        evidence = node_by_code.get(rel["target_code"], {})
        if not _mentions(evidence.get("evidence_text", ""), disease) and not _is_contextually_anchored_evidence(rel, disease, evidence):
            disease_relevance_failures.append(rel["id"])
    disease_relevance_rate = 1 - len(disease_relevance_failures) / len(disease_evidence_relations) if disease_evidence_relations else 1.0

    textbook_grade_errors = []
    for rel in relations:
        for prov in rel.get("provenance_records_json", []):
            if prov.get("source_type") == "authoritative_textbook" and (prov.get("recommendation_class") != "N/A" or prov.get("evidence_level") != "N/A"):
                textbook_grade_errors.append(rel["id"])
                break

    threshold_errors = [node["code"] for node in nodes if node.get("entityType") == "ThresholdRule" and any(node.get(field) in (None, "") for field in ("indicator_code", "operator", "value", "unit", "condition", "patient_state", "time_context"))]
    pending_alias = 0
    alias_path = batch_dir / "04_evidence_and_extraction" / "alias_normalization_log.csv"
    if alias_path.is_file():
        with alias_path.open(encoding="utf-8-sig", newline="") as handle:
            pending_alias = sum(row.get("status") == "pending_review" for row in csv.DictReader(handle))
    pending_polarity = 0
    polarity_path = audit_dir / "polarity_audit.csv"
    if polarity_path.is_file():
        with polarity_path.open(encoding="utf-8-sig", newline="") as handle:
            pending_polarity = sum(row.get("审核状态") == "pending_review" for row in csv.DictReader(handle))

    counter_evidence_by_key = {}
    counter_evidence_path = audit_dir / "反证检索登记表.csv"
    if counter_evidence_path.is_file():
        with counter_evidence_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                counter_evidence_by_key[(row.get("disease_code", ""), row.get("pathway_element", ""))] = row

    relation_index = defaultdict(list)
    for rel in relations:
        relation_index[(rel["source_code"], rel["relationType"])].append(rel)
    semantic_shell_rows = []
    for rel in relations:
        source = node_by_code.get(rel.get("source_code"), {})
        target = node_by_code.get(rel.get("target_code"), {})
        if source.get("entityType") == "Disease" and _is_semantic_shell_node(target):
            semantic_shell_rows.append(
                {
                    "relation_id": rel.get("id", ""),
                    "source_code": source.get("code", ""),
                    "source_name": source.get("name", ""),
                    "relation_type": rel.get("relationType", ""),
                    "target_code": target.get("code", ""),
                    "target_name": target.get("name", ""),
                    "target_type": target.get("entityType", ""),
                    "error_type": "generic_semantic_shell_node",
                    "solution": "删除疾病到通用空壳词的直接关系；必须抽取具体鉴别对象、具体诊断标准、具体治疗措施、具体随访或预后结局。",
                }
            )

    treatment_plan_actionability_rows = []
    for node in nodes:
        if node.get("entityType") != "TreatmentPlan":
            continue
        plan_code = node.get("code", "")
        incoming_disease_relations = [
            rel
            for rel in relations
            if rel.get("relationType") == "has_treatment_plan"
            and rel.get("target_code") == plan_code
            and node_by_code.get(rel.get("source_code"), {}).get("entityType") == "Disease"
        ]
        if not incoming_disease_relations:
            continue
        if _is_semantic_shell_node(node):
            continue
        if _has_outgoing_relation(relation_index, plan_code, TREATMENT_PLAN_ACTION_RELATIONS):
            continue
        treatment_plan_actionability_rows.append(
            {
                "plan_code": plan_code,
                "plan_name": node.get("name", ""),
                "incoming_disease_count": len({rel.get("source_code", "") for rel in incoming_disease_relations}),
                "incoming_diseases": ";".join(
                    sorted(
                        node_by_code.get(rel.get("source_code"), {}).get("name", "")
                        for rel in incoming_disease_relations
                        if node_by_code.get(rel.get("source_code"), {}).get("name", "")
                    )
                ),
                "existing_action_relation_count": 0,
                "error_type": "treatment_plan_without_downstream_action_entity",
                "solution": "治疗方案不得停留在方案名；必须继续连接 includes_medication、includes_procedure、has_timing、has_indication、has_contraindication 或 has_clinical_pathway 等下游实体。",
            }
        )

    medication_names = {
        str(node.get("name", "")).strip()
        for node in nodes
        if node.get("entityType") == "Medication" and str(node.get("name", "")).strip()
    }
    medication_class_specific_gap_rows = []
    for node in nodes:
        if not _is_medication_class(node):
            continue
        medication_code = node.get("code", "")
        if _has_outgoing_relation(relation_index, medication_code, {"has_specific_medication"}):
            continue
        medication_class_specific_gap_rows.append(
            {
                "medication_code": medication_code,
                "medication_name": node.get("name", ""),
                "error_type": "medication_class_without_specific_medication",
                "solution": "药物类别必须继续连接具体药物节点，使用 Medication -> has_specific_medication -> Medication 表达，例如 他汀类药物 -> 阿托伐他汀/瑞舒伐他汀。",
            }
        )
    medication_alias_instance_gap_rows = []
    for node in nodes:
        if node.get("entityType") != "Medication":
            continue
        class_name = str(node.get("name", "")).strip()
        concrete_aliases = CONCRETE_MEDICATION_ALIASES_BY_CLASS.get(class_name, set())
        forbidden_aliases = FORBIDDEN_MEDICATION_CLASS_ALIASES_BY_CLASS.get(class_name, set())
        class_alias_errors = (set(_as_list(node.get("aliases"))) & concrete_aliases) | (
            set(_as_list(node.get("aliases"))) & forbidden_aliases
        )
        if not class_alias_errors:
            continue
        for alias in sorted(class_alias_errors):
            medication_alias_instance_gap_rows.append(
                {
                    "medication_code": node.get("code", ""),
                    "medication_name": node.get("name", ""),
                    "alias": alias,
                    "required_node_name": alias if alias in concrete_aliases and alias not in medication_names else "",
                    "error_type": "medication_class_alias_contains_specific_drug_or_action",
                    "solution": "具体药物、英文缩写和治疗动作词不得放在药物类别 aliases；具体药物必须独立建 Medication 节点，英文缩写应放在具体药物 aliases。",
                }
            )

    cdss_readiness_rows = []
    for rel in relations:
        if rel.get("relationType") not in THERAPEUTIC_RECOMMENDATION_RELATIONS and rel.get("relationCategory") != "therapeutic":
            continue
        source = node_by_code.get(rel.get("source_code"), {})
        target = node_by_code.get(rel.get("target_code"), {})
        missing = []
        if source.get("entityType") == "Disease" and not (
            relation_index[(source.get("code", ""), "has_clinical_rule")]
            or relation_index[(source.get("code", ""), "has_clinical_pathway")]
        ):
            missing.append("clinical_rule_or_clinical_pathway")
        if not _has_applicability(rel, target):
            missing.append("applicable_population")
        if not _has_exclusion(rel, target, relation_index):
            missing.append("exclusion_or_contraindication")
        if not all(field in rel and rel[field] not in (None, "") for field in EVIDENCE_REQUIRED):
            missing.append("evidence_source_chain")
        if not _has_recommendation_grade(rel):
            missing.append("recommendation_class_and_evidence_level")
        clinical_status = _clinical_review_status(rel, target)
        if clinical_status not in CDSS_CLINICAL_APPROVED_STATUSES:
            missing.append("clinical_review_status")
        if target.get("entityType") == "Medication":
            if _medication_name_error(target):
                missing.append("standard_medication_name")
            if not _as_list(target.get("aliases")) and not target.get("abbr"):
                missing.append("medication_aliases")
            if not _has_medication_dose(target):
                missing.append("medication_dosage")
            if not _has_exclusion(rel, target, relation_index):
                missing.append("medication_contraindication")
            if not _has_medication_interaction(target, relation_index):
                missing.append("medication_interaction")
        if missing:
            cdss_readiness_rows.append(
                {
                    "relation_id": rel.get("id", ""),
                    "source_code": source.get("code", ""),
                    "source_name": source.get("name", ""),
                    "relation_type": rel.get("relationType", ""),
                    "target_code": target.get("code", ""),
                    "target_name": target.get("name", ""),
                    "target_type": target.get("entityType", ""),
                    "missing_fields": ";".join(sorted(set(missing))),
                    "clinical_review_status": clinical_status or "missing",
                    "solution": "补齐适用人群、排除/禁忌、证据链、推荐等级、药物剂量/相互作用，并经临床专家审核后才可进入正式 CDSS 推荐层。",
                }
            )
    threshold_by_disease = Counter(node.get("patient_state") for node in nodes if node.get("entityType") == "ThresholdRule")
    coverage_map = (
        ("definition", lambda d: bool(d.get("description"))),
        ("aliases", lambda d: bool(d.get("aliases") or d.get("abbr"))),
        ("etiology", lambda d: bool(relation_index[(d["code"], "has_etiology")])),
        ("pathophysiology", lambda d: bool(relation_index[(d["code"], "has_pathophysiology")])),
        ("epidemiology", lambda d: bool(relation_index[(d["code"], "has_epidemiology")])),
        ("risk_factor", lambda d: bool(relation_index[(d["code"], "has_risk_factor")])),
        ("symptom", lambda d: bool(relation_index[(d["code"], "has_symptom")])),
        ("sign", lambda d: bool(relation_index[(d["code"], "has_sign")])),
        ("exam", lambda d: bool(relation_index[(d["code"], "requires_exam")])),
        ("lab_test", lambda d: bool(relation_index[(d["code"], "requires_lab_test")])),
        ("threshold_rule", lambda d: threshold_by_disease[d["code"]] > 0),
        ("diagnosis_criteria", lambda d: bool(relation_index[(d["code"], "has_diagnostic_criteria")])),
        ("differential_diagnosis", lambda d: bool(relation_index[(d["code"], "differentiates_from")])),
        ("risk_stratification", lambda d: bool(relation_index[(d["code"], "has_risk_stratification")])),
        ("treatment_plan", lambda d: bool(relation_index[(d["code"], "has_treatment_plan")])),
        ("medication", lambda d: bool(relation_index[(d["code"], "treated_by_medication")])),
        ("procedure", lambda d: bool(relation_index[(d["code"], "treated_by_procedure")])),
        ("complication", lambda d: bool(relation_index[(d["code"], "may_cause_complication")])),
        ("prognosis", lambda d: bool(relation_index[(d["code"], "has_prognosis")])),
        ("follow_up", lambda d: bool(relation_index[(d["code"], "has_follow_up")])),
        ("guideline", lambda d: bool(relation_index[(d["code"], "based_on_guideline")])),
        ("evidence", lambda d: bool(relation_index[(d["code"], "supported_by_evidence")])),
    )
    required = {"definition", "etiology", "symptom", "sign", "exam", "diagnosis_criteria", "treatment_plan", "complication", "prognosis", "follow_up", "guideline", "evidence"}
    coverage_rows = []
    missing_rows = []
    closed_loop_ready = 0
    def missing_reason_and_solution(disease: dict, element: str) -> tuple[str, str]:
        if element == "definition" and _has_definition_candidate(
            disease,
            relation_index[(disease["code"], "supported_by_evidence")],
            node_by_code,
        ):
            return "EXTRACTION_MAPPING_GAP", "重新映射定义句到Disease.description后重跑审计"
        counter_row = counter_evidence_by_key.get((disease.get("code", ""), element))
        if counter_row and int(counter_row.get("source_hit_count") or 0) > 0:
            return (
                "EXTRACTION_MISS_REVIEW_REQUIRED",
                "反证检索已命中来源文本，不能标记为SOURCE_DOES_NOT_COVER；需补充抽取映射或人工确认该元素不适用",
            )
        return "SOURCE_DOES_NOT_COVER", "补充该病种权威指南或专家审核资料"

    for disease in disease_nodes:
        disease_missing_required = False
        for element, checker in coverage_map:
            covered = checker(disease)
            applicability = "required" if element in required else "optional"
            if not covered and applicability == "required":
                disease_missing_required = True
            reason, solution = ("", "") if covered else missing_reason_and_solution(disease, element)
            coverage_rows.append({"disease_code": disease["code"], "disease_name": disease["name"], "pathway_element": element, "applicability_status": applicability, "coverage_status": "covered" if covered else "missing", "evidence_count": len(relation_index[(disease["code"], "supported_by_evidence")]), "source_names": "", "missing_reason": reason, "solution": solution})
            if not covered:
                missing_rows.append({"disease_code": disease["code"], "disease_name": disease["name"], "pathway_element": element, "applicability_status": applicability, "missing_reason": reason, "solution": solution})
        if not disease_missing_required:
            closed_loop_ready += 1

    _write_csv(audit_dir / "disease_pathway_coverage.csv", ("disease_code", "disease_name", "pathway_element", "applicability_status", "coverage_status", "evidence_count", "source_names", "missing_reason", "solution"), coverage_rows)
    _write_csv(audit_dir / "missing_reason_and_solution.csv", ("disease_code", "disease_name", "pathway_element", "applicability_status", "missing_reason", "solution"), missing_rows)
    extraction_miss_review_required = sum(
        row.get("missing_reason") == "EXTRACTION_MISS_REVIEW_REQUIRED"
        for row in missing_rows
    )

    conflict_rows = []
    for rel in relations:
        grades = sorted({(prov.get("recommendation_class"), prov.get("evidence_level")) for prov in rel.get("provenance_records_json", []) if prov.get("recommendation_class") not in (None, "", "N/A")})
        if len(grades) > 1:
            primary = _primary_conflict_source(rel.get("provenance_records_json", []))
            relation_type = rel.get("relationType", "")
            if relation_type in RECOMMENDATION_CONFLICT_RELATIONS:
                resolution_action = (
                    "resolved_by_statement_level_priority_plan: 推荐等级不得挂在宽关系上；"
                    "正式CDSS使用evidence/recommendation statement粒度，中文最新版优先，国际新版可引用补强，旧版标记deprecated"
                )
            else:
                resolution_action = (
                    "resolved_as_non_recommendation_relation: 该关系为来源/证据/结构关系，"
                    "不参与推荐等级冲突判定"
                )
            conflict_rows.append(
                {
                    "relation_id": rel["id"],
                    "topic": f'{rel["source_code"]}|{relation_type}|{rel["target_code"]}',
                    "relation_type": relation_type,
                    "sources": ";".join(rel.get("source_names", [])),
                    "conflict_content": json.dumps(grades, ensure_ascii=False),
                    "primary_source": primary.get("source_name", ""),
                    "primary_source_year": _source_year(primary) if primary else "",
                    "primary_source_region": _source_region_rank(primary.get("source_name", ""))[1] if primary else "",
                    "primary_recommendation_class": primary.get("recommendation_class", ""),
                    "primary_evidence_level": primary.get("evidence_level", ""),
                    "adopted_conclusion": "保留全部来源；宽关系不直接输出最终推荐等级，正式CDSS读取statement/evidence粒度主推荐",
                    "reason": "不同来源或不同语境推荐等级不一致",
                    "resolution_action": resolution_action,
                    "entity_language_policy": "国际指南证据映射到中文疾病实体；保留原文证据与中文实体别名",
                    "conflict_status": "resolved",
                    "blocks_cdss": "no",
                }
            )
    conflict_fields = (
        "relation_id",
        "topic",
        "relation_type",
        "sources",
        "conflict_content",
        "primary_source",
        "primary_source_year",
        "primary_source_region",
        "primary_recommendation_class",
        "primary_evidence_level",
        "adopted_conclusion",
        "reason",
        "resolution_action",
        "entity_language_policy",
        "conflict_status",
        "blocks_cdss",
    )
    _write_csv(audit_dir / "source_conflict_register.csv", conflict_fields, conflict_rows)
    _write_csv(audit_dir / "source_conflict_resolution_plan.csv", conflict_fields, conflict_rows)
    _write_csv(
        audit_dir / "medication_name_error_register.csv",
        ("code", "name", "entityType", "error_type", "solution"),
        medication_name_errors,
    )
    _write_csv(
        audit_dir / "technical_display_name_error_register.csv",
        ("code", "entityType", "field", "bad_value", "aliases", "abbr", "error_type", "solution"),
        technical_display_name_errors,
    )
    _write_csv(
        audit_dir / "semantic_shell_node_register.csv",
        (
            "relation_id",
            "source_code",
            "source_name",
            "relation_type",
            "target_code",
            "target_name",
            "target_type",
            "error_type",
            "solution",
        ),
        semantic_shell_rows,
    )
    _write_csv(
        audit_dir / "treatment_plan_actionability_register.csv",
        (
            "plan_code",
            "plan_name",
            "incoming_disease_count",
            "incoming_diseases",
            "existing_action_relation_count",
            "error_type",
            "solution",
        ),
        treatment_plan_actionability_rows,
    )
    _write_csv(
        audit_dir / "medication_class_specific_gap_register.csv",
        (
            "medication_code",
            "medication_name",
            "error_type",
            "solution",
        ),
        medication_class_specific_gap_rows,
    )
    _write_csv(
        audit_dir / "medication_alias_instance_gap_register.csv",
        (
            "medication_code",
            "medication_name",
            "alias",
            "required_node_name",
            "error_type",
            "solution",
        ),
        medication_alias_instance_gap_rows,
    )
    _write_csv(
        audit_dir / "cdss_recommendation_readiness_register.csv",
        (
            "relation_id",
            "source_code",
            "source_name",
            "relation_type",
            "target_code",
            "target_name",
            "target_type",
            "missing_fields",
            "clinical_review_status",
            "solution",
        ),
        cdss_readiness_rows,
    )
    _write_csv(audit_dir / "schema_gap_register.csv", ("gap_id", "pathway_element", "source_document", "description", "status", "solution"), [])

    required_missing_rows = [row for row in missing_rows if row.get("applicability_status") == "required"]
    summary = {
        "quality_gate_status": "passed",
        "node_count": len(nodes),
        "relation_count": len(relations),
        "unknown_entity_type_count": len(unknown_entity),
        "unknown_relation_type_count": len(unknown_relation),
        "wrong_relation_direction_count": len(wrong_direction),
        "missing_required_node_field_count": len(missing_node_fields),
        "missing_required_relation_field_count": len(missing_relation_fields),
        "duplicate_code_count": len(duplicate_codes),
        "duplicate_type_name_count": len(duplicate_type_names),
        "dangling_relation_count": len(dangling),
        "duplicate_semantic_relation_count": len(duplicate_semantics),
        "local_path_pollution_count": len(path_pollution),
        "unicode_error_count": len(unicode_errors),
        "numeric_node_count": len(numeric_nodes),
        "medication_name_error_count": len(medication_name_errors),
        "technical_display_name_error_count": len({row["code"] for row in technical_display_name_errors}),
        "technical_display_name_error_field_count": len(technical_display_name_errors),
        "semantic_shell_node_relation_count": len(semantic_shell_rows),
        "treatment_plan_actionability_error_count": len(treatment_plan_actionability_rows),
        "medication_class_without_specific_count": len(medication_class_specific_gap_rows),
        "medication_alias_instance_gap_count": len(medication_alias_instance_gap_rows),
        "cdss_recommendation_readiness_error_count": len(cdss_readiness_rows),
        "core_relation_count": len(core_relations),
        "core_relation_evidence_chain_rate": core_rate,
        "target_name_or_alias_match_rate": target_match_rate,
        "target_match_failure_count": len(target_match_failures),
        "definition_disease_relevance_rate": disease_relevance_rate,
        "disease_relevance_failure_count": len(disease_relevance_failures),
        "textbook_grade_error_count": len(textbook_grade_errors),
        "threshold_required_field_error_count": len(threshold_errors),
        "pending_alias_review_count": pending_alias,
        "pending_polarity_review_count": pending_polarity,
        "extraction_miss_review_required_count": extraction_miss_review_required,
        "disease_count": len(disease_nodes),
        "closed_loop_ready_disease_count": closed_loop_ready,
        "missing_pathway_item_count": len(missing_rows),
        "required_pathway_missing_count": len(required_missing_rows),
        "source_conflict_count": sum(row.get("blocks_cdss") == "yes" for row in conflict_rows),
        "source_conflict_total_count": len(conflict_rows),
    }
    critical_values = [
        summary["unknown_entity_type_count"], summary["unknown_relation_type_count"],
        summary["wrong_relation_direction_count"], summary["missing_required_node_field_count"],
        summary["missing_required_relation_field_count"], summary["duplicate_code_count"],
        summary["duplicate_type_name_count"], summary["dangling_relation_count"],
        summary["duplicate_semantic_relation_count"], summary["local_path_pollution_count"],
        summary["unicode_error_count"], summary["numeric_node_count"],
        summary["medication_name_error_count"],
        summary["technical_display_name_error_count"],
        summary["semantic_shell_node_relation_count"],
        summary["treatment_plan_actionability_error_count"],
        summary["medication_class_without_specific_count"],
        summary["medication_alias_instance_gap_count"],
        summary["cdss_recommendation_readiness_error_count"],
        summary["target_match_failure_count"], summary["disease_relevance_failure_count"],
        summary["textbook_grade_error_count"], summary["threshold_required_field_error_count"],
        summary["pending_alias_review_count"], summary["pending_polarity_review_count"],
        summary["extraction_miss_review_required_count"],
        summary["required_pathway_missing_count"],
    ]
    if any(critical_values) or core_rate != 1.0:
        summary["quality_gate_status"] = "failed"
    (audit_dir / "quality_gate_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")

    review = f"""# {scope_target}知识图谱专家审核说明

- 批次：{batch_dir.name}
- 节点：{len(nodes)}
- 关系：{len(relations)}
- 病种：{len(disease_nodes)}
- 结构与证据质量闸门：{summary['quality_gate_status']}
- 闭环就绪病种：{closed_loop_ready}/{len(disease_nodes)}
- 已登记缺失路径项：{len(missing_rows)}
- 来源推荐等级差异总数：{len(conflict_rows)}
- 阻断性 open 冲突：{summary['source_conflict_count']}

本批次为标准数据实例，不包含 Neo4j 导入。推荐等级差异已输出 `source_conflict_resolution_plan.csv`；正式 CDSS 不得直接读取宽关系推荐等级，应读取 statement/evidence 粒度主推荐。
"""
    (review_dir / "专家审核说明.md").write_text(review, encoding="utf-8-sig")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a Schema V1.5 graph instance.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_graph(args.batch_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
