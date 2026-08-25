from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
DEFAULT_OUTPUT_DIR = (
    ROOT / "项目管理中心_project_management" / "20260728_AMI心肌病收口"
)

AMI_CODES = {
    "DIS-CARD-CAD-AMI",
    "DIS-CARD-CAD-STEMI",
    "DIS-CARD-CAD-NSTEMI",
}

CM_CODES = {
    "DIS-CARD-CM-GENERAL",
    "DIS-CARD-CM-HCM",
    "DIS-CARD-CM-DCM",
    "DIS-CARD-CM-RCM",
    "DIS-CARD-CM-NDLVCM",
    "DIS-CARD-CM-ACM",
    "DIS-CARD-CM-ARVC",
    "DIS-CARD-CM-ALVC",
    "DIS-CARD-CM-ABVC",
    "DIS-CARD-CM-ATRIAL",
    "DIS-CARD-CM-FABRY",
    "DIS-CARD-CM-AMYLOID",
}

SCOPE_CODES = AMI_CODES | CM_CODES

STANDARD_PATHS = {
    "检查发现": (
        "has_exam_plan",
        "includes_exam_item",
        "exam_item_has_observation",
    ),
    "检验细项": (
        "has_exam_plan",
        "includes_lab_item",
        "lab_item_has_subitem",
    ),
}

FORBIDDEN_DIRECT_PATHS = {
    ("ExamPlan", "includes_lab_item", "LabSubitem"),
    ("ExamPlan", "*", "ExamObservation"),
}

ROLE_REQUIRED_SLOTS = {
    "broad_diagnosis": (
        "definition",
        "exam_plan",
        "clinical_subtype",
        "standard_diagnosis",
    ),
    "clinical_subtype": (
        "definition",
        "clinical_manifestation",
        "exam_plan",
        "diagnostic_criteria",
        "differential_diagnosis",
        "treatment_plan",
        "standard_diagnosis",
    ),
    "independent_disease": (
        "definition",
        "clinical_manifestation",
        "exam_plan",
        "diagnostic_criteria",
        "differential_diagnosis",
        "treatment_plan",
        "standard_diagnosis",
    ),
}

# 宽口径疾病用于“先识别疾病家族、再继续分型”，不得强行复制某一分型的
# 诊断标准或治疗方案。以下补充项均绑定已入库原文证据，并保留可读的完整规则。
DIFFERENTIAL_REPAIR_SPECS = {
    "DIS-CARD-CM-ABVC": {
        "disease_code": "DIS-CARD-CM-ABVC",
        "node_code": "DDX-CARD-CM-ABVC-PHENOCOPY",
        "rule_code": "RULE-CARD-CM-ABVC-PHENOCOPY",
        "name": "致心律失常性双心室心肌病表型鉴别",
        "rule_text": (
            "致心律失常性双心室心肌病属于致心律失常性心肌病的双心室表型；"
            "评估时应系统排除心肌炎、心脏结节病、右心室梗死、扩张型心肌病、"
            "肺动脉高压、右心容量负荷型先天性心脏病及特发性右心室流出道室速等表型模拟疾病。"
        ),
        "differential_targets": [
            "心肌炎",
            "心脏结节病",
            "右心室梗死",
            "扩张型心肌病",
            "肺动脉高压",
            "右心容量负荷型先天性心脏病",
            "特发性右心室流出道室速",
        ],
        "evidence_id": "EVD-SHARED-4BC0142953B346C1151871A1",
    },
    "DIS-CARD-CM-ATRIAL": {
        "disease_code": "DIS-CARD-CM-ATRIAL",
        "node_code": "DDX-CARD-CM-ATRIAL-SECONDARY",
        "rule_code": "RULE-CARD-CM-ATRIAL-SECONDARY",
        "name": "心房心肌病与继发性心房重构鉴别",
        "rule_text": (
            "诊断心房心肌病时应评估心房颤动持续发作、心力衰竭、瓣膜性心脏病、"
            "心肌炎、高血压和内分泌异常等可继发心房瘢痕或结构重构的病理状态，"
            "结合病因纠正后的结构和电生理变化判断是否为原发性心房心肌病。"
        ),
        "differential_targets": [
            "持续性心房颤动",
            "心力衰竭",
            "瓣膜性心脏病",
            "心肌炎",
            "高血压",
            "内分泌异常",
        ],
        "evidence_id": "EVD-74C08FDA665F90308028-ATRIAL",
    },
    "DIS-CARD-CM-FABRY": {
        "disease_code": "DIS-CARD-CM-FABRY",
        "node_code": "DDX-CARD-CM-FABRY-LVH",
        "rule_code": "RULE-CARD-CM-FABRY-LVH",
        "name": "法布雷病心肌病左心室肥厚表型鉴别",
        "rule_text": (
            "法布雷病心肌病出现左心室肥厚或限制样改变时，应与肥厚型心肌病、"
            "淀粉样变心肌病和高血压性心肌损伤鉴别；少汗、四肢疼痛、蛋白尿等"
            "心外表现以及酶学、基因和组织学检查有助于明确病因。"
        ),
        "differential_targets": [
            "肥厚型心肌病",
            "淀粉样变心肌病",
            "高血压性心肌损伤",
        ],
        "evidence_id": "EVD-00CF1703DDCBA6474E42-FABRY",
    },
    "DIS-CARD-CM-GENERAL": {
        "disease_code": "DIS-CARD-CM-GENERAL",
        "node_code": "DDX-CARD-CM-GENERAL-LOAD-ISCHEMIA",
        "rule_code": "RULE-CARD-CM-GENERAL-LOAD-ISCHEMIA",
        "name": "心肌病宽口径诊断排除条件",
        "rule_text": (
            "将心肌结构或功能异常归入心肌病宽口径诊断前，应先判断该异常是否能够"
            "由前负荷或后负荷增加、心肌缺血或其他系统性疾病充分解释；能够解释者"
            "不能仅凭心肌表型直接归入原发性心肌病，并应继续完成病因和具体表型分型。"
        ),
        "differential_targets": [
            "前负荷增加所致心肌改变",
            "后负荷增加所致心肌改变",
            "缺血性心脏病",
            "系统性疾病心肌受累",
        ],
        "evidence_id": "CARD-SKELETON-20260709-EVID-10DB7A033FEFEC11",
    },
    "DIS-CARD-CM-NDLVCM": {
        "disease_code": "DIS-CARD-CM-NDLVCM",
        "node_code": "DDX-CARD-CM-NDLVCM-SYSTOLIC",
        "rule_code": "RULE-CARD-CM-NDLVCM-SYSTOLIC",
        "name": "非扩张型左心室心肌病鉴别",
        "rule_text": (
            "非扩张型左心室心肌病应与导致心脏收缩功能减低的其他原发性和继发性"
            "心肌病鉴别；诊断前应排除继发性、其他原发性及缺血性心肌病，并结合"
            "无明显左心室扩张、非缺血性瘢痕或脂肪替代等特征判断。"
        ),
        "differential_targets": [
            "其他原发性心肌病",
            "继发性心肌病",
            "缺血性心肌病",
        ],
        "evidence_id": "EVD-105ACC5EF6AEFCD23F73-NDLVCM",
    },
}

FORMAL_RECOMMENDATION_RELATIONS = {
    "recommends_action",
    "recommends_assessment",
    "blocks_action",
}

ACCEPTANCE_DIMENSIONS = (
    "知识内容完整性",
    "标准身份完整性",
    "路径可用性",
    "正式推荐就绪度",
)

LAB_PARENT_POLICIES = {
    "LAB-CARD-1BE2B3C08B76": {
        "code": "LABITEM-CDSS-E5BFABACF8274FC9865D36299A1EC8D6",
        "name": "红细胞沉降率测定",
        "preferred_name": "红细胞沉降率测定",
        "cdss_dict_id": "E5BFABACF8274FC9865D36299A1EC8D6",
        "standard_code": "L104497",
        "source_table": "K_LAB_ITEM_DICT",
        "valid_flag": 1,
        "dictionary_validation_status": "validated",
        "clinical_use_status": "review_ready",
    },
    "LAB-CARD-2E1F4EC42626": {
        "code": "LABITEM-CDSS-AF0AB4EE8D234D009E0E0B74E32D8992",
        "name": "血浆D-二聚体测定",
        "preferred_name": "血浆D-二聚体测定",
        "cdss_dict_id": "AF0AB4EE8D234D009E0E0B74E32D8992",
        "standard_code": "L104828",
        "source_table": "K_LAB_ITEM_DICT",
        "valid_flag": 1,
        "dictionary_validation_status": "validated",
        "clinical_use_status": "review_ready",
    },
    "LAB-CARD-BF2619C772EC": {
        "code": "LABITEM-CARD-CRP-PENDING",
        "name": "C反应蛋白测定",
        "preferred_name": "C反应蛋白测定",
        "source_table": "K_KG_DICT_CHANGE_REVIEW",
        "valid_flag": 0,
        "dictionary_validation_status": "pending_registration",
        "clinical_use_status": "knowledge_display_only",
        "dictionary_review_reason": "CDSS检验项目字典未检出可直接采用的有效项目，禁止伪造字典ID",
    },
}

CONTEXT_PARENT_POLICIES = {
    (
        "CAD",
        "CARD-SKELETON-20260709-LABTEST-AD6A34F25F521595",
    ): "LAB-CARD-CADCD76D40B9",
    (
        "CM",
        "CARD-SKELETON-20260709-LABTEST-AD6A34F25F521595",
    ): "LAB-CARDIAC-BIOMARKERS",
    ("CM", "IND-NT-PROBNP"): "EXAM-CARD-01C3182D129E",
}

STANDARD_DIAGNOSIS_MAPPINGS = {
    "DIS-CARD-CM-ARVC": {
        "cdss_dict_id": "e2f3017ed624228933ae203d12681c25",
        "standard_code": "I42.800x002",
        "name": "致心律失常性右室心肌病",
        "mapping_type": "exact",
        "valid_flag": 1,
        "is_emr_writable": True,
    },
    "DIS-CARD-CM-ALVC": {
        "cdss_dict_id": "e73a5f7a9cf9b894401b8b0cbcd2cf96",
        "standard_code": "I42.800x006",
        "name": "致心律失常性左室心肌病",
        "mapping_type": "exact",
        "valid_flag": 1,
        "is_emr_writable": True,
    },
    "DIS-CARD-CM-RCM": {
        "cdss_dict_id": "b7d272035cf77c861d90a33e00cce0e2",
        "standard_code": "I42.500",
        "name": "限制型心肌病，其他的",
        "mapping_type": "exact",
        "valid_flag": 1,
        "is_emr_writable": True,
    },
    "DIS-CARD-CM-AMYLOID": {
        "cdss_dict_id": "4abaee44db4b2afe2c5e7c4b50306b67",
        "standard_code": "E85.400x028+I43.1*",
        "name": "心脏淀粉样变性",
        "mapping_type": "exact",
        "valid_flag": 1,
        "is_emr_writable": True,
    },
    **{
        disease_code: {
            "cdss_dict_id": "d4c92d7b4031091f475c20c62bffcd04",
            "standard_code": "I42.900",
            "name": "心肌病",
            "mapping_type": "broader_fallback",
            "valid_flag": 1,
            "is_emr_writable": False,
        }
        for disease_code in (
            "DIS-CARD-CM-ABVC",
            "DIS-CARD-CM-ACM",
            "DIS-CARD-CM-ATRIAL",
            "DIS-CARD-CM-FABRY",
            "DIS-CARD-CM-NDLVCM",
        )
    },
}

SCOPE_LAB_ROOT_CODES = {
    "CARD-SKELETON-20260709-LABTEST-AD6A34F25F521595",
    "IND-NT-PROBNP",
    "LAB-CARD-1BE2B3C08B76",
    "LAB-CARD-2E1F4EC42626",
    "LAB-CARD-A9EC1D4DA037",
    "LAB-CARD-BF2619C772EC",
    "LAB-CARD-CADCD76D40B9",
    "LABIND-EXAM-CARD-01C3182D129E-BNP",
    "LABIND-LAB-CARD-CBC-HB-CDSS-白细胞计数",
}

SLOT_RELATIONS = {
    "definition": ("has_definition",),
    "symptom": ("has_symptom",),
    "sign": ("has_sign",),
    "exam_plan": ("has_exam_plan",),
    "diagnostic_criteria": ("has_diagnostic_criteria",),
    "differential_diagnosis": (
        "differentiates_from",
        "has_differential_diagnosis",
    ),
    "risk_stratification": ("has_risk_stratification",),
    "treatment_plan": ("has_treatment_plan",),
    "follow_up": ("has_follow_up",),
    "prognosis": ("has_prognosis",),
    "prevention": ("has_prevention",),
    "clinical_subtype": ("has_clinical_subtype",),
    "standard_diagnosis": ("has_standard_diagnosis",),
}


def classify_parent_candidates(parent_codes: Iterable[str]) -> str:
    unique = {str(code).strip() for code in parent_codes if str(code).strip()}
    if not unique:
        return "blocking_missing_parent"
    if len(unique) > 1:
        return "blocking_ambiguous_parent"
    return "safe_to_migrate"


def disease_family(disease_code: str) -> str:
    if disease_code.startswith("DIS-CARD-CAD-"):
        return "CAD"
    if disease_code.startswith("DIS-CARD-CM-"):
        return "CM"
    return "OTHER"


def resolve_lab_parent(
    disease_code: str,
    subitem_code: str,
    parents: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    parent_rows = [dict(item) for item in parents]
    parent_codes = {
        str(item.get("code") or item.get("element_id") or "").strip()
        for item in parent_rows
        if str(item.get("code") or item.get("element_id") or "").strip()
    }
    if not parent_codes:
        parent_spec = LAB_PARENT_POLICIES.get(subitem_code)
        if parent_spec:
            return {
                "classification": "safe_create_parent",
                "selected_parent_code": parent_spec["code"],
                "parent_spec": dict(parent_spec),
            }
        return {"classification": "blocking_missing_parent"}
    if len(parent_codes) == 1:
        return {
            "classification": "safe_to_migrate",
            "selected_parent_code": next(iter(parent_codes)),
        }
    selected = CONTEXT_PARENT_POLICIES.get(
        (disease_family(disease_code), subitem_code)
    )
    if selected and selected in parent_codes:
        return {
            "classification": "safe_context_resolved",
            "selected_parent_code": selected,
        }
    return {"classification": "blocking_ambiguous_parent"}


def classify_lab_result_statement(name: str) -> str:
    clinical_markers = ("提示", "排除", "鉴别", "风险", "建议", "考虑")
    if any(marker in name for marker in clinical_markers):
        return "ClinicalRule"
    return "ThresholdRule"


def lab_child_repair_strategy(
    source_labels: Iterable[str],
    target_labels: Iterable[str],
    target_name: str,
) -> str:
    source = set(source_labels)
    target = set(target_labels)
    if "LabItem" in source and "LabItem" in target:
        return "create_subitem_shadow"
    if "ThresholdRule" in target:
        return "convert_to_threshold_rule"
    if "ClinicalRule" in target:
        return "convert_to_clinical_rule"
    if "LabSubitem" in source and "LabSubitem" in target:
        return (
            "convert_to_clinical_rule"
            if classify_lab_result_statement(target_name) == "ClinicalRule"
            else "convert_to_threshold_rule"
        )
    return "blocking_unsupported_shape"


def read_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    uri = re.search(r"bolt://[^\s；;，,]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;，,]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;，,]+)", text)
    if not (uri and user and password):
        raise RuntimeError("数据库连接文件无法解析 Bolt 地址、用户名或密码。")
    return {
        "uri": uri.group(0),
        "username": user.group(1),
        "password": password.group(1),
    }


def rows(records: Iterable[Any]) -> list[dict[str, Any]]:
    return [dict(record) for record in records]


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_jsonl(path: Path, payload: Iterable[dict[str, Any]]) -> None:
    text = "\n".join(
        json.dumps(json_safe(item), ensure_ascii=False) for item in payload
    )
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def write_csv(path: Path, payload: list[dict[str, Any]]) -> None:
    fields = list(payload[0]) if payload else [
        "disease_code",
        "disease_name",
        "diagnostic_role",
        "issue",
        "disposition",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload)


def collect_disease_rows(session: Any) -> list[dict[str, Any]]:
    return rows(
        session.run(
            """
            MATCH (d:Disease)
            WHERE d.code IN $codes AND coalesce(d.status,'') <> 'deprecated'
            OPTIONAL MATCH (d)-[mapping:has_standard_diagnosis]->(sd:StandardDiagnosis)
            WITH d,sd,mapping,
                 reduce(value=null, key IN keys(mapping) |
                   CASE WHEN key=$mapping_type_key
                        THEN mapping[key] ELSE value END
                 ) AS mapping_type,
                 reduce(value=null, key IN keys(mapping) |
                   CASE WHEN key=$is_emr_writable_key
                        THEN mapping[key] ELSE value END
                 ) AS is_emr_writable
            WITH d,
                 count(DISTINCT sd) AS standard_diagnosis_count,
                 count(DISTINCT CASE
                   WHEN coalesce(toString(sd.valid_flag),'1')='1'
                    AND coalesce(sd.status,'active') <> 'deprecated'
                   THEN sd END) AS valid_standard_diagnosis_count,
                 count(DISTINCT CASE
                   WHEN coalesce(toString(sd.valid_flag),'1')='1'
                    AND coalesce(sd.status,'active') <> 'deprecated'
                    AND coalesce(mapping_type,'exact')
                        IN ['exact','equivalent']
                   THEN sd END) AS exact_standard_diagnosis_count,
                 count(DISTINCT CASE
                   WHEN coalesce(toString(sd.valid_flag),'1')='1'
                    AND coalesce(sd.status,'active') <> 'deprecated'
                    AND mapping_type='broader_fallback'
                   THEN sd END) AS fallback_standard_diagnosis_count,
                 collect(DISTINCT {
                   code: sd.code,
                   name: coalesce(sd.name,sd.preferred_name,sd.display_name),
                   valid_flag: sd.valid_flag,
                   status: sd.status,
                   mapping_type: mapping_type,
                   is_emr_writable: is_emr_writable
                 }) AS standard_diagnoses
            RETURN d.code AS disease_code,
                   coalesce(d.name,d.preferred_name,d.display_name,d.code) AS disease_name,
                   coalesce(d.diagnostic_role,'independent_disease') AS diagnostic_role,
                   coalesce(d.is_diagnosable,true) AS is_diagnosable,
                   standard_diagnosis_count,
                   valid_standard_diagnosis_count,
                   exact_standard_diagnosis_count,
                   fallback_standard_diagnosis_count,
                   standard_diagnoses
            ORDER BY disease_code
            """,
            codes=sorted(SCOPE_CODES),
            mapping_type_key="mapping_type",
            is_emr_writable_key="is_emr_writable",
        )
    )


def collect_slot_counts(session: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    diseases = rows(
        session.run(
            """
            MATCH (d:Disease)
            WHERE d.code IN $codes AND coalesce(d.status,'') <> 'deprecated'
            RETURN d.code AS disease_code,
                   coalesce(d.name,d.preferred_name,d.display_name,d.code) AS disease_name,
                   coalesce(d.diagnostic_role,'independent_disease') AS diagnostic_role
            ORDER BY disease_code
            """,
            codes=sorted(SCOPE_CODES),
        )
    )
    for disease in diseases:
        counts: dict[str, int] = {}
        for slot, relation_types in SLOT_RELATIONS.items():
            count_record = session.run(
                """
                MATCH (d:Disease {code:$code})
                OPTIONAL MATCH (d)-[r]->(target)
                WHERE type(r) IN $relation_types
                  AND coalesce(target.status,'') <> 'deprecated'
                RETURN count(DISTINCT target) AS count
                """,
                code=disease["disease_code"],
                relation_types=list(relation_types),
            ).single()
            counts[slot] = int(count_record["count"] if count_record else 0)
        counts["clinical_manifestation"] = counts["symptom"] + counts["sign"]
        role = disease["diagnostic_role"]
        required = ROLE_REQUIRED_SLOTS.get(
            role, ROLE_REQUIRED_SLOTS["independent_disease"]
        )
        missing = [slot for slot in required if counts.get(slot, 0) == 0]
        result.append({**disease, **counts, "missing_required_slots": missing})
    return result


def collect_bad_lab_paths(session: Any) -> list[dict[str, Any]]:
    data = rows(
        session.run(
            """
            MATCH (d:Disease)-[:has_exam_plan]->(p:ExamPlan)
                  -[r:includes_lab_item]->(s:LabSubitem)
            WHERE d.code IN $codes
              AND coalesce(d.status,'') <> 'deprecated'
              AND coalesce(p.status,'') <> 'deprecated'
              AND coalesce(s.status,'') <> 'deprecated'
            OPTIONAL MATCH (li:LabItem)-[:lab_item_has_subitem]->(s)
            WITH d,p,r,s,collect(DISTINCT li) AS parents
            RETURN d.code AS disease_code,
                   coalesce(d.name,d.code) AS disease_name,
                   elementId(p) AS plan_element_id,
                   p.code AS plan_code,
                   coalesce(p.name,p.code) AS plan_name,
                   elementId(r) AS old_relation_element_id,
                   properties(r) AS old_relation_properties,
                   elementId(s) AS subitem_element_id,
                   s.code AS subitem_code,
                   coalesce(s.name,s.code) AS subitem_name,
                   [x IN parents | {
                     element_id: elementId(x),
                     code: x.code,
                     name: coalesce(x.name,x.code)
                   }] AS parents
            ORDER BY disease_code, plan_code, subitem_code
            """,
            codes=sorted(SCOPE_CODES),
        )
    )
    for item in data:
        resolution = resolve_lab_parent(
            item["disease_code"],
            item["subitem_code"],
            item.get("parents", []),
        )
        item.update(resolution)
    return data


def collect_invalid_lab_child_relations(
    session: Any, scope_codes: Iterable[str]
) -> list[dict[str, Any]]:
    return rows(
        session.run(
            """
            MATCH (d:Disease)-[:has_exam_plan]->(:ExamPlan)
                  -[:includes_lab_item]->(source)
            WHERE d.code IN $scope_codes
              AND coalesce(d.status,'') <> 'deprecated'
            MATCH (source)-[r:lab_item_has_subitem]->(target)
            WHERE coalesce(source.status,'') <> 'deprecated'
              AND coalesce(target.status,'') <> 'deprecated'
              AND (
                NOT source:LabItem
                OR NOT target:LabSubitem
                OR target:LabItem
              )
            RETURN DISTINCT elementId(source) AS source_element_id,
                   source.code AS source_code,
                   coalesce(source.name,source.code) AS source_name,
                   labels(source) AS source_labels,
                   elementId(r) AS relation_element_id,
                   properties(r) AS relation_properties,
                   elementId(target) AS target_element_id,
                   target.code AS target_code,
                   coalesce(target.name,target.code) AS target_name,
                   labels(target) AS target_labels
            ORDER BY source_code,target_code
            """,
            scope_codes=sorted(set(scope_codes)),
        )
    )


def collect_bad_exam_paths(session: Any) -> list[dict[str, Any]]:
    data = rows(
        session.run(
            """
            MATCH (d:Disease)-[:has_exam_plan]->(p:ExamPlan)-[r]->(o:ExamObservation)
            WHERE d.code IN $codes
              AND coalesce(d.status,'') <> 'deprecated'
              AND coalesce(p.status,'') <> 'deprecated'
              AND coalesce(o.status,'') <> 'deprecated'
            OPTIONAL MATCH (ei:ExamItem)-[:exam_item_has_observation]->(o)
            WITH d,p,r,o,collect(DISTINCT ei) AS parents
            RETURN d.code AS disease_code,
                   coalesce(d.name,d.code) AS disease_name,
                   elementId(p) AS plan_element_id,
                   p.code AS plan_code,
                   coalesce(p.name,p.code) AS plan_name,
                   elementId(r) AS old_relation_element_id,
                   type(r) AS old_relation_type,
                   properties(r) AS old_relation_properties,
                   elementId(o) AS observation_element_id,
                   o.code AS observation_code,
                   coalesce(o.name,o.code) AS observation_name,
                   [x IN parents | {
                     element_id: elementId(x),
                     code: x.code,
                     name: coalesce(x.name,x.code)
                   }] AS parents
            ORDER BY disease_code, plan_code, observation_code
            """,
            codes=sorted(SCOPE_CODES),
        )
    )
    for item in data:
        item["classification"] = classify_parent_candidates(
            parent.get("code") or parent.get("element_id")
            for parent in item.get("parents", [])
        )
    return data


def collect_plan_action_gaps(session: Any) -> list[dict[str, Any]]:
    return rows(
        session.run(
            """
            MATCH (d:Disease)-[:has_treatment_plan]->(p:TreatmentPlan)
            WHERE d.code IN $codes
              AND coalesce(d.status,'') <> 'deprecated'
              AND coalesce(p.status,'') <> 'deprecated'
            OPTIONAL MATCH path=(p)-[:has_treatment_component|includes_medication|
              includes_procedure|includes_treatment_item|has_clinical_pathway|
              has_pathway_stage|next_pathway_stage|stage_has_available_action*1..5]->(a)
            WHERE a:Medication OR a:Procedure OR a:TreatmentItem
               OR a:ExamItem OR a:LabItem OR a:FollowUp
            WITH d,p,collect(DISTINCT a) AS actions
            WHERE size(actions)=0
            RETURN d.code AS disease_code, coalesce(d.name,d.code) AS disease_name,
                   p.code AS plan_code, coalesce(p.name,p.code) AS plan_name
            ORDER BY disease_code, plan_code
            """,
            codes=sorted(SCOPE_CODES),
        )
    )


def collect_formal_recommendation_gaps(session: Any) -> list[dict[str, Any]]:
    return rows(
        session.run(
            """
            MATCH (d:Disease)-[:has_source_adjudication]->(adj:SourceAdjudication)
            WHERE d.code IN $codes
              AND coalesce(adj.formal_cdss_ready,false)=true
              AND coalesce(adj.cdss_use_status,'')='正式推荐'
            OPTIONAL MATCH (adj)-[:decides_recommendation]->(rec:RecommendationStatement)
            OPTIONAL MATCH (rec)-[ar:recommends_action|recommends_assessment|blocks_action]->(a)
            OPTIONAL MATCH (adj)-[:derived_from]->(ev:Evidence)
            OPTIONAL MATCH (adj)-[:uses_primary_guideline]->(gl:Guideline)
            WITH d,adj,collect(DISTINCT rec) AS recs,
                 collect(DISTINCT a) AS actions,
                 collect(DISTINCT type(ar)) AS action_relations,
                 collect(DISTINCT ev.code) AS evidence_codes,
                 collect(DISTINCT gl.code) AS guideline_codes
            WITH d,adj,recs,actions,action_relations,evidence_codes,guideline_codes,
                 [issue IN [
                   CASE WHEN size(recs)=0 THEN '缺推荐陈述' END,
                   CASE WHEN size(actions)=0
                          OR none(x IN action_relations WHERE x IN $allowed_relations)
                        THEN '缺动作或评估目标' END,
                   CASE WHEN trim(coalesce(adj.primary_evidence_code,''))=''
                          OR NOT adj.primary_evidence_code IN evidence_codes
                        THEN '缺主证据' END,
                   CASE WHEN trim(coalesce(adj.primary_guideline_code,''))=''
                          OR NOT adj.primary_guideline_code IN guideline_codes
                        THEN '缺主指南' END,
                   CASE WHEN trim(coalesce(adj.recommendation_class,''))=''
                        THEN '缺推荐等级' END,
                   CASE WHEN trim(coalesce(adj.evidence_level,''))=''
                        THEN '缺证据等级' END,
                   CASE WHEN trim(coalesce(adj.conflict_status,''))=''
                        THEN '缺冲突状态' END,
                   CASE WHEN trim(coalesce(adj.adjudication_reason,''))=''
                        THEN '缺裁决理由' END
                 ] WHERE issue IS NOT NULL] AS issues
            WHERE size(issues)>0
            RETURN d.code AS disease_code, coalesce(d.name,d.code) AS disease_name,
                   adj.code AS adjudication_code,
                   coalesce(adj.name,adj.clinical_question,adj.code) AS adjudication_name,
                   issues
            ORDER BY disease_code, adjudication_code
            """,
            codes=sorted(SCOPE_CODES),
            allowed_relations=sorted(FORMAL_RECOMMENDATION_RELATIONS),
        )
    )


def collect_differential_repair_readiness(session: Any) -> list[dict[str, Any]]:
    readiness: list[dict[str, Any]] = []
    for disease_code, spec in DIFFERENTIAL_REPAIR_SPECS.items():
        record = session.run(
            """
            MATCH (d:Disease {code:$disease_code})
            OPTIONAL MATCH (d)-[:has_differential_diagnosis]->
                           (ddx:DifferentialDiagnosis {code:$node_code})
            OPTIONAL MATCH (e:Evidence)
            WHERE coalesce(e.evidence_id,e.code)=$evidence_id
              AND coalesce(e.status,'') <> 'deprecated'
            RETURN count(DISTINCT d) AS disease_count,
                   count(DISTINCT ddx) AS existing_node_count,
                   count(DISTINCT e) AS evidence_count
            """,
            disease_code=disease_code,
            node_code=spec["node_code"],
            evidence_id=spec["evidence_id"],
        ).single()
        readiness.append(
            {
                **spec,
                "disease_exists": int(record["disease_count"] if record else 0) == 1,
                "already_present": (
                    int(record["existing_node_count"] if record else 0) == 1
                ),
                "evidence_exists": int(record["evidence_count"] if record else 0) == 1,
            }
        )
    return readiness


def build_audit(session: Any) -> dict[str, Any]:
    diseases = collect_disease_rows(session)
    slots = collect_slot_counts(session)
    bad_lab = collect_bad_lab_paths(session)
    bad_exam = collect_bad_exam_paths(session)
    invalid_lab_children = collect_invalid_lab_child_relations(
        session, SCOPE_CODES
    )
    plan_gaps = collect_plan_action_gaps(session)
    formal_gaps = collect_formal_recommendation_gaps(session)
    differential_repairs = collect_differential_repair_readiness(session)
    standard_gaps = [
        {
            "disease_code": item["disease_code"],
            "disease_name": item["disease_name"],
            "diagnostic_role": item["diagnostic_role"],
            "issue": (
                "仅有上位诊断回退，缺精确CDSS标准诊断"
                if int(item.get("fallback_standard_diagnosis_count") or 0) > 0
                else "缺有效CDSS标准诊断"
            ),
            "disposition": (
                "保留知识实体和上位诊断回退；禁止作为具体分型回填EMR"
                if int(item.get("fallback_standard_diagnosis_count") or 0) > 0
                else "查询有效标准字典；无有效记录则阻断正式CDSS落地"
            ),
        }
        for item in diseases
        if item.get("is_diagnosable")
        and int(item.get("exact_standard_diagnosis_count") or 0) == 0
    ]
    content_gaps = [
        {
            "disease_code": item["disease_code"],
            "disease_name": item["disease_name"],
            "diagnostic_role": item["diagnostic_role"],
            "missing_required_slots": item["missing_required_slots"],
        }
        for item in slots
        if item["missing_required_slots"]
    ]
    path_blockers = [
        item
        for item in bad_lab + bad_exam
        if item.get("classification")
        not in {"safe_to_migrate", "safe_context_resolved", "safe_create_parent"}
    ]
    dimensions = {
        "知识内容完整性": {
            "status": "通过" if not content_gaps and not plan_gaps else "不通过",
            "content_gap_count": len(content_gaps),
            "empty_action_plan_count": len(plan_gaps),
        },
        "标准身份完整性": {
            "status": "通过" if not standard_gaps else "不通过",
            "standard_diagnosis_gap_count": len(standard_gaps),
        },
        "路径可用性": {
            "status": (
                "通过"
                if not bad_lab and not bad_exam and not invalid_lab_children
                else "不通过"
            ),
            "bad_direct_lab_path_count": len(bad_lab),
            "bad_direct_exam_path_count": len(bad_exam),
            "invalid_lab_child_relation_count": len(invalid_lab_children),
            "unmigratable_path_count": len(path_blockers),
        },
        "正式推荐就绪度": {
            "status": "通过" if not formal_gaps else "不通过",
            "formal_recommendation_gap_count": len(formal_gaps),
        },
    }
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scope_codes": sorted(SCOPE_CODES),
        "diseases": diseases,
        "slot_counts": slots,
        "content_gaps": content_gaps,
        "standard_diagnosis_gaps": standard_gaps,
        "bad_lab_paths": bad_lab,
        "bad_exam_paths": bad_exam,
        "invalid_lab_child_relations": invalid_lab_children,
        "path_blockers": path_blockers,
        "treatment_plan_action_gaps": plan_gaps,
        "formal_recommendation_gaps": formal_gaps,
        "planned_differential_repairs": differential_repairs,
        "acceptance_dimensions": dimensions,
    }


def build_rollback_rows(audit: dict[str, Any]) -> list[dict[str, Any]]:
    rollback: list[dict[str, Any]] = []
    for item in audit["bad_lab_paths"]:
        if item["classification"] in {
            "safe_to_migrate",
            "safe_context_resolved",
            "safe_create_parent",
        }:
            rollback.append(
                {
                    "rollback_kind": "restore_lab_path",
                    "path_kind": "lab",
                    **item,
                }
            )
    for item in audit["bad_exam_paths"]:
        if item["classification"] == "safe_to_migrate":
            rollback.append(
                {
                    "rollback_kind": "restore_exam_path",
                    "path_kind": "exam",
                    **item,
                }
            )
    for item in audit.get("invalid_lab_child_relations", []):
        rollback.append(
            {
                "rollback_kind": "restore_lab_child_relation",
                "path_kind": "lab_child_semantics",
                **item,
            }
        )
    for item in audit.get("standard_diagnosis_gaps", []):
        mapping = STANDARD_DIAGNOSIS_MAPPINGS.get(item["disease_code"])
        if not mapping:
            continue
        rollback.append(
            {
                "rollback_kind": "remove_standard_diagnosis_mapping",
                "disease_code": item["disease_code"],
                "standard_diagnosis_node_code": (
                    f"STDDX-{mapping['cdss_dict_id']}"
                ),
                "mapping_type": mapping["mapping_type"],
                "remove_standard_node_only_if_orphaned": True,
            }
        )
    for item in audit.get("planned_differential_repairs", []):
        if item["already_present"]:
            continue
        rollback.append(
            {
                "rollback_kind": "remove_differential_repair",
                "disease_code": item["disease_code"],
                "node_code": item["node_code"],
                "rule_code": item["rule_code"],
                "remove_nodes_only_if_created_by_batch": True,
            }
        )
    return rollback


def ensure_lab_parent(
    session: Any, item: dict[str, Any], batch: str, now: str
) -> dict[str, Any]:
    parent_code = item["selected_parent_code"]
    if item["classification"] == "safe_create_parent":
        parent_spec = dict(item["parent_spec"])
        record = session.run(
            """
            MERGE (li:KGNode:LabItem {code:$code})
            ON CREATE SET li.created_at=$now
            SET li += $properties,
                li.entityType='LabItem',
                li.type_label='LabItem',
                li.primary_label='KGNode',
                li.status='active',
                li.schema_version='V2.10',
                li.repair_batch=$batch,
                li.updated_at=$now
            WITH li
            MATCH (s:LabSubitem) WHERE elementId(s)=$subitem_id
            MERGE (li)-[contains:lab_item_has_subitem]->(s)
            SET contains.status='active',
                contains.repair_batch=$batch,
                contains.repair_time=$now
            RETURN elementId(li) AS element_id,li.code AS code
            """,
            code=parent_code,
            properties=parent_spec,
            subitem_id=item["subitem_element_id"],
            batch=batch,
            now=now,
        ).single()
    else:
        record = session.run(
            """
            MATCH (li:LabItem {code:$code})
            MATCH (s:LabSubitem) WHERE elementId(s)=$subitem_id
            MERGE (li)-[contains:lab_item_has_subitem]->(s)
            SET contains.status='active',
                contains.repair_batch=$batch,
                contains.repair_time=$now
            RETURN elementId(li) AS element_id,li.code AS code
            """,
            code=parent_code,
            subitem_id=item["subitem_element_id"],
            batch=batch,
            now=now,
        ).single()
    if not record:
        raise RuntimeError(
            f"无法建立检验项目父级：{item['disease_code']} / "
            f"{item['subitem_code']} / {parent_code}"
        )
    return dict(record)


def apply_safe_path_repairs(session: Any, audit: dict[str, Any]) -> dict[str, int]:
    batch = "20260728-AMI心肌病样板收口"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    counters = {
        "migrated_lab_paths": 0,
        "migrated_exam_paths": 0,
        "deleted_bad_direct_relations": 0,
        "created_lab_subitem_projections": 0,
        "retyped_lab_result_rules": 0,
        "standard_diagnosis_links": 0,
    }
    for item in audit["bad_lab_paths"]:
        if item["classification"] not in {
            "safe_to_migrate",
            "safe_context_resolved",
            "safe_create_parent",
        }:
            continue
        parent = ensure_lab_parent(session, item, batch, now)
        record = session.run(
            """
            MATCH (p:ExamPlan) WHERE elementId(p)=$plan_id
            MATCH (s:LabSubitem) WHERE elementId(s)=$target_id
            MATCH (li:LabItem) WHERE elementId(li)=$parent_id
            MATCH (p)-[old:includes_lab_item]->(s)
            WHERE elementId(old)=$old_relation_id
              AND (li)-[:lab_item_has_subitem]->(s)
            MERGE (p)-[standard:includes_lab_item]->(li)
            ON CREATE SET standard += $old_properties
            SET standard.repair_batch=$batch,
                standard.repair_time=$now,
                standard.repair_reason='检验细项错误直连迁移为方案到检验项目标准路径',
                standard.status='active'
            DELETE old
            RETURN 1 AS migrated
            """,
            plan_id=item["plan_element_id"],
            target_id=item["subitem_element_id"],
            parent_id=parent["element_id"],
            old_relation_id=item["old_relation_element_id"],
            old_properties=item.get("old_relation_properties") or {},
            batch=batch,
            now=now,
        ).single()
        if record:
            counters["migrated_lab_paths"] += 1
            counters["deleted_bad_direct_relations"] += 1
    for item in audit.get("invalid_lab_child_relations", []):
        source_labels = set(item.get("source_labels") or [])
        target_labels = set(item.get("target_labels") or [])
        strategy = lab_child_repair_strategy(
            source_labels,
            target_labels,
            item["target_name"],
        )
        if strategy == "create_subitem_shadow":
            target_code = item.get("target_code") or item["target_element_id"]
            projection_code = f"LABSUB-PROJ-{target_code}"
            record = session.run(
                """
                MATCH (source:LabItem) WHERE elementId(source)=$source_id
                MATCH (target) WHERE elementId(target)=$target_id
                MATCH (source)-[old:lab_item_has_subitem]->(target)
                WHERE elementId(old)=$relation_id
                MERGE (subitem:KGNode:LabSubitem {code:$projection_code})
                ON CREATE SET
                    subitem.name=coalesce(target.name,target.code),
                    subitem.preferred_name=coalesce(
                        target.preferred_name,
                        target.name,
                        target.code
                    ),
                    subitem.aliases=coalesce(target.aliases,[]),
                    subitem.concept_source_code=target.code,
                    subitem.source_entity_type='LabItem',
                    subitem.dictionary_validation_status='pending_registration',
                    subitem.clinical_use_status='knowledge_display_only',
                    subitem.schema_version='V2.10',
                    subitem.status='active',
                    subitem.created_at=$now
                SET subitem.repair_batch=$batch,
                    subitem.updated_at=$now
                WITH source,target,subitem,old
                MERGE (source)-[standard:lab_item_has_subitem]->(subitem)
                ON CREATE SET standard += $old_properties
                SET standard.repair_batch=$batch,
                    standard.repair_time=$now,
                    standard.repair_reason=
                      '保留可开医嘱检验项目并建立独立报告细项',
                    standard.status='active'
                DELETE old
                RETURN elementId(subitem) AS subitem_id
                """,
                source_id=item["source_element_id"],
                target_id=item["target_element_id"],
                relation_id=item["relation_element_id"],
                projection_code=projection_code,
                old_properties=item.get("relation_properties") or {},
                batch=batch,
                now=now,
            ).single()
            if record:
                counters["created_lab_subitem_projections"] += 1
            continue
        if strategy in {
            "convert_to_clinical_rule",
            "convert_to_threshold_rule",
        }:
            rule_type = classify_lab_result_statement(item["target_name"])
            relation_clause = (
                "MERGE (source)-[standard:has_clinical_rule]->(target)"
                if rule_type == "ClinicalRule"
                else "MERGE (source)-[standard:has_threshold_rule]->(target)"
            )
            record = session.run(
                f"""
                MATCH (source) WHERE elementId(source)=$source_id
                MATCH (target) WHERE elementId(target)=$target_id
                MATCH (source)-[old:lab_item_has_subitem]->(target)
                WHERE elementId(old)=$relation_id
                FOREACH (_ IN CASE WHEN $rule_type='ClinicalRule' THEN [1] ELSE [] END |
                  SET target:ClinicalRule
                )
                FOREACH (_ IN CASE WHEN $rule_type='ThresholdRule' THEN [1] ELSE [] END |
                  SET target:ThresholdRule
                )
                REMOVE target:LabSubitem
                SET target.entityType=$rule_type,
                    target.type_label=$rule_type,
                    target.repair_batch=$batch,
                    target.updated_at=$now
                WITH source,target,old
                {relation_clause}
                ON CREATE SET standard += $old_properties
                SET standard.repair_batch=$batch,
                    standard.repair_time=$now,
                    standard.status='active'
                DELETE old
                RETURN elementId(standard) AS relation_id
                """,
                source_id=item["source_element_id"],
                target_id=item["target_element_id"],
                relation_id=item["relation_element_id"],
                rule_type=rule_type,
                old_properties=item.get("relation_properties") or {},
                batch=batch,
                now=now,
            ).single()
            if record:
                counters["retyped_lab_result_rules"] += 1
    for item in audit["bad_exam_paths"]:
        if item["classification"] != "safe_to_migrate":
            continue
        parent = item["parents"][0]
        record = session.run(
            """
            MATCH (p:ExamPlan) WHERE elementId(p)=$plan_id
            MATCH (o:ExamObservation) WHERE elementId(o)=$target_id
            MATCH (ei:ExamItem) WHERE elementId(ei)=$parent_id
            MATCH (p)-[old]->(o)
            WHERE elementId(old)=$old_relation_id
              AND (ei)-[:exam_item_has_observation]->(o)
            MERGE (p)-[standard:includes_exam_item]->(ei)
            ON CREATE SET standard += $old_properties
            SET standard.repair_batch=$batch,
                standard.repair_time=$now,
                standard.repair_reason='检查发现错误直连迁移为方案到检查项目标准路径',
                standard.status='active'
            DELETE old
            RETURN 1 AS migrated
            """,
            plan_id=item["plan_element_id"],
            target_id=item["observation_element_id"],
            parent_id=parent["element_id"],
            old_relation_id=item["old_relation_element_id"],
            old_properties=item.get("old_relation_properties") or {},
            batch=batch,
            now=now,
        ).single()
        if record:
            counters["migrated_exam_paths"] += 1
            counters["deleted_bad_direct_relations"] += 1
    return counters


def apply_standard_diagnosis_mappings(
    session: Any, audit: dict[str, Any]
) -> dict[str, int]:
    batch = "20260728-AMI心肌病样板收口"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    counters = {
        "exact_standard_diagnosis_links": 0,
        "fallback_standard_diagnosis_links": 0,
    }
    for gap in audit["standard_diagnosis_gaps"]:
        mapping = STANDARD_DIAGNOSIS_MAPPINGS.get(gap["disease_code"])
        if not mapping:
            continue
        node_code = f"STDDX-{mapping['cdss_dict_id']}"
        record = session.run(
            """
            MATCH (d:Disease {code:$disease_code})
            MERGE (sd:KGNode:StandardDiagnosis {code:$node_code})
            ON CREATE SET sd.created_at=$now
            SET sd.name=$name,
                sd.preferred_name=$name,
                sd.standard_code=$standard_code,
                sd.cdss_dict_id=$cdss_dict_id,
                sd.valid_flag=$valid_flag,
                sd.source_table='K_ICD10_DICT',
                sd.source_name='国家临床版2.0',
                sd.source_version='国家临床版2.0',
                sd.coding_system='ICD-10（诊断）',
                sd.entityType='StandardDiagnosis',
                sd.type_label='StandardDiagnosis',
                sd.primary_label='KGNode',
                sd.status='active',
                sd.schema_version='V2.10',
                sd.dictionary_validation_status='validated',
                sd.updated_at=$now,
                sd.repair_batch=$batch
            WITH d,sd
            MERGE (d)-[mapping:has_standard_diagnosis]->(sd)
            SET mapping.mapping_type=$mapping_type,
                mapping.is_emr_writable=$is_emr_writable,
                mapping.status='active',
                mapping.repair_batch=$batch,
                mapping.updated_at=$now,
                mapping.mapping_note=CASE
                  WHEN $mapping_type='broader_fallback'
                  THEN '现行CDSS有效字典无该现代心肌病表型精确条目；仅作上位疑似诊断回退，禁止作为具体分型回填'
                  ELSE '疾病名称与CDSS有效标准诊断精确对应'
                END
            SET d.standard_identity_status=CASE
                  WHEN $mapping_type='broader_fallback'
                  THEN 'fallback_not_emr_writable'
                  ELSE 'exact_validated'
                END,
                d.is_emr_writable=$is_emr_writable,
                d.updated_at=$now
            RETURN 1 AS linked
            """,
            disease_code=gap["disease_code"],
            node_code=node_code,
            name=mapping["name"],
            standard_code=mapping["standard_code"],
            cdss_dict_id=mapping["cdss_dict_id"],
            valid_flag=mapping["valid_flag"],
            mapping_type=mapping["mapping_type"],
            is_emr_writable=mapping["is_emr_writable"],
            batch=batch,
            now=now,
        ).single()
        if record:
            key = (
                "fallback_standard_diagnosis_links"
                if mapping["mapping_type"] == "broader_fallback"
                else "exact_standard_diagnosis_links"
            )
            counters[key] += 1
    return counters


def apply_evidence_bound_differential_repairs(
    session: Any, audit: dict[str, Any]
) -> dict[str, int]:
    batch = "20260728-AMI心肌病样板收口"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    counters = {"evidence_bound_differential_repairs": 0}
    for item in audit.get("planned_differential_repairs", []):
        if item["already_present"]:
            continue
        if not item["disease_exists"] or not item["evidence_exists"]:
            raise RuntimeError(
                f"鉴别诊断补充缺疾病或证据：{item['disease_code']} / "
                f"{item['evidence_id']}"
            )
        record = session.run(
            """
            MATCH (d:Disease {code:$disease_code})
            MATCH (e:Evidence)
            WHERE coalesce(e.evidence_id,e.code)=$evidence_id
              AND coalesce(e.status,'') <> 'deprecated'
            MERGE (ddx:KGNode:DifferentialDiagnosis {code:$node_code})
            ON CREATE SET ddx.created_at=$now,
                          ddx.created_by_batch=$batch
            SET ddx.name=$name,
                ddx.preferred_name=$name,
                ddx.description=$rule_text,
                ddx.rule_text=$rule_text,
                ddx.differential_targets=$differential_targets,
                ddx.entityType='DifferentialDiagnosis',
                ddx.type_label='DifferentialDiagnosis',
                ddx.primary_label='KGNode',
                ddx.status='active',
                ddx.schema_version='V2.10',
                ddx.review_status='passed',
                ddx.clinical_review_status='not_required',
                ddx.updated_at=$now,
                ddx.repair_batch=$batch
            MERGE (rule:KGNode:ClinicalRule {code:$rule_code})
            ON CREATE SET rule.created_at=$now,
                          rule.created_by_batch=$batch
            SET rule.name=$name + '规则',
                rule.preferred_name=$name + '规则',
                rule.description=$rule_text,
                rule.rule_text=$rule_text,
                rule.entityType='ClinicalRule',
                rule.type_label='ClinicalRule',
                rule.primary_label='KGNode',
                rule.status='active',
                rule.schema_version='V2.10',
                rule.review_status='passed',
                rule.clinical_review_status='not_required',
                rule.updated_at=$now,
                rule.repair_batch=$batch
            MERGE (d)-[has_ddx:has_differential_diagnosis]->(ddx)
            SET has_ddx.status='active',
                has_ddx.schema_version='V2.10',
                has_ddx.review_status='passed',
                has_ddx.clinical_review_status='not_required',
                has_ddx.repair_batch=$batch,
                has_ddx.updated_at=$now
            MERGE (ddx)-[has_rule:has_differential_rule]->(rule)
            SET has_rule.status='active',
                has_rule.schema_version='V2.10',
                has_rule.repair_batch=$batch,
                has_rule.updated_at=$now
            MERGE (ddx)-[ddx_evidence:supported_by_evidence]->(e)
            SET ddx_evidence.status='active',
                ddx_evidence.schema_version='V2.10',
                ddx_evidence.repair_batch=$batch,
                ddx_evidence.updated_at=$now
            MERGE (rule)-[rule_evidence:supported_by_evidence]->(e)
            SET rule_evidence.status='active',
                rule_evidence.schema_version='V2.10',
                rule_evidence.repair_batch=$batch,
                rule_evidence.updated_at=$now
            RETURN 1 AS repaired
            """,
            **item,
            batch=batch,
            now=now,
        ).single()
        if record:
            counters["evidence_bound_differential_repairs"] += 1
    return counters


def persist_audit(output_dir: Path, audit: dict[str, Any], prefix: str) -> None:
    write_json(output_dir / f"{prefix}.json", audit)
    if prefix == "01_治理前基线":
        path_plan = {
            "bad_lab_paths": audit["bad_lab_paths"],
            "bad_exam_paths": audit["bad_exam_paths"],
            "invalid_lab_child_relations": audit[
                "invalid_lab_child_relations"
            ],
            "path_blockers": audit["path_blockers"],
        }
        write_json(output_dir / "02_路径修复计划.json", path_plan)
        write_csv(
            output_dir / "03_标准诊断缺口.csv",
            audit["standard_diagnosis_gaps"],
        )
        write_jsonl(
            output_dir / "04_写库前回滚关系.jsonl",
            build_rollback_rows(audit),
        )
        rollback_rows = build_rollback_rows(audit)
        safe_path_repair_count = sum(
            row["rollback_kind"]
            in {
                "restore_lab_path",
                "restore_exam_path",
                "restore_lab_child_relation",
            }
            for row in rollback_rows
        )
        standard_mapping_count = sum(
            row["rollback_kind"] == "remove_standard_diagnosis_mapping"
            for row in rollback_rows
        )
        gate = {
            "generated_at": audit["generated_at"],
            "rollback_ready": bool(rollback_rows),
            "unmigratable_path_count": len(audit["path_blockers"]),
            "safe_path_repair_count": safe_path_repair_count,
            "planned_standard_mapping_count": standard_mapping_count,
            "rollback_record_count": len(rollback_rows),
            "write_allowed_for_path_repair": len(audit["path_blockers"]) == 0,
            "write_allowed_for_content_repair": all(
                item["disease_exists"] and item["evidence_exists"]
                for item in audit["planned_differential_repairs"]
            ),
            "full_sample_ready": all(
                value["status"] == "通过"
                for value in audit["acceptance_dimensions"].values()
            ),
            "acceptance_dimensions": audit["acceptance_dimensions"],
        }
        write_json(output_dir / "05_写库前闸门.json", gate)


def render_report(before: dict[str, Any], after: dict[str, Any], write_result: dict[str, Any]) -> str:
    rows_text = "\n".join(
        f"| {name} | {before['acceptance_dimensions'][name]['status']} | "
        f"{after['acceptance_dimensions'][name]['status']} |"
        for name in ACCEPTANCE_DIMENSIONS
    )
    remaining_content = after["content_gaps"]
    remaining_standard = after["standard_diagnosis_gaps"]
    remaining_path = (
        after["bad_lab_paths"]
        + after["bad_exam_paths"]
        + after["invalid_lab_child_relations"]
    )
    remaining_formal = after["formal_recommendation_gaps"]
    conclusion = (
        "四项全部通过，可作为 AMI 与心肌病样板基线。"
        if not (
            remaining_content
            or remaining_standard
            or remaining_path
            or remaining_formal
        )
        else "仍有明确阻断项，不能宣告两个样板 100% 完整。"
    )
    return f"""# AMI 与心肌病样板验收报告（2026-07-28）

## 一、结论

{conclusion}

## 二、修复前后

| 验收维度 | 修复前 | 修复后 |
|---|---|---|
{rows_text}

## 三、本次实际写入

- 迁移检验路径：{write_result.get('migrated_lab_paths', 0)}
- 迁移检查路径：{write_result.get('migrated_exam_paths', 0)}
- 物理删除错误直连：{write_result.get('deleted_bad_direct_relations', 0)}
- 保留可开医嘱项目并建立独立检验细项：{write_result.get('created_lab_subitem_projections', 0)}
- 纠正误标为检验细项的阈值/解释规则：{write_result.get('retyped_lab_result_rules', 0)}
- 新增精确标准诊断关系：{write_result.get('exact_standard_diagnosis_links', 0)}
- 新增上位诊断回退关系：{write_result.get('fallback_standard_diagnosis_links', 0)}
- 补充有原文证据的鉴别诊断及规则：{write_result.get('evidence_bound_differential_repairs', 0)}

## 四、剩余阻断

- 必需知识槽位缺口疾病：{len(remaining_content)}
- 有效标准诊断缺口：{len(remaining_standard)}
- 错误检查/检验直连：{len(remaining_path)}
- 正式推荐链路缺口：{len(remaining_formal)}

详细数据见同目录 JSON、CSV 和回滚文件。
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AMI 与心肌病样板：四维审计、标准路径安全迁移和入库后复测"
    )
    parser.add_argument("--apply", action="store_true", help="执行可回滚的标准路径写库")
    parser.add_argument(
        "--connection-file", type=Path, default=DEFAULT_CONNECTION_FILE
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = read_connection_file(args.connection_file)
    driver = GraphDatabase.driver(
        config["uri"], auth=(config["username"], config["password"])
    )
    try:
        with driver.session() as session:
            before = build_audit(session)
            persist_audit(args.output_dir, before, "01_治理前基线")
            gate = json.loads(
                (args.output_dir / "05_写库前闸门.json").read_text(encoding="utf-8")
            )
            write_result: dict[str, Any] = {
                "apply": args.apply,
                "migrated_lab_paths": 0,
                "migrated_exam_paths": 0,
                "deleted_bad_direct_relations": 0,
                "created_lab_subitem_projections": 0,
                "retyped_lab_result_rules": 0,
                "exact_standard_diagnosis_links": 0,
                "fallback_standard_diagnosis_links": 0,
                "evidence_bound_differential_repairs": 0,
            }
            if args.apply:
                if not gate["write_allowed_for_path_repair"]:
                    raise RuntimeError("存在无法唯一确定父级的错误路径，已阻止写库。")
                if not gate["write_allowed_for_content_repair"]:
                    raise RuntimeError("鉴别诊断补充缺疾病或原文证据，已阻止写库。")
                write_result.update(apply_safe_path_repairs(session, before))
                write_result.update(
                    apply_standard_diagnosis_mappings(session, before)
                )
                write_result.update(
                    apply_evidence_bound_differential_repairs(session, before)
                )
            write_json(args.output_dir / "06_写库结果.json", write_result)
            after = build_audit(session)
            persist_audit(args.output_dir, after, "07_入库后复测")
            report = render_report(before, after, write_result)
            (args.output_dir / "AMI与心肌病样板验收报告_20260728.md").write_text(
                report, encoding="utf-8"
            )
            print(
                json.dumps(
                    {
                        "apply": args.apply,
                        "output_dir": str(args.output_dir),
                        "write_result": write_result,
                        "before": before["acceptance_dimensions"],
                        "after": after["acceptance_dimensions"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
    finally:
        driver.close()


if __name__ == "__main__":
    main()
