from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "V1.4"
BATCH_ID = "FOUNDATION-CARD-DEEP-20260625-001"
PRIMARY_DOCUMENT_ID = "DOC-CF62B75AEC93F1A6"
PRIMARY_GUIDELINE_ID = PRIMARY_DOCUMENT_ID
PRIMARY_SOURCE_NAME = "《内科学（第10版）》.docx"
PRIMARY_SOURCE_VERSION = "第10版"
PRIMARY_SOURCE_SECTION = "第三篇 循环系统疾病"
CARDIOLOGY_LINE_START = 5339
CARDIOLOGY_LINE_END = 11398


TYPE_PREFIX = {
    "Symptom": "SYM",
    "Sign": "SIGN",
    "Exam": "EXAM",
    "LabTest": "LAB",
    "Medication": "MED",
    "Procedure": "PROC",
    "TreatmentPlan": "PLAN",
    "RiskFactor": "RF",
    "Etiology": "ETI",
    "Complication": "COMP",
    "Prognosis": "PROG",
    "DiagnosisCriteria": "DXC",
    "DifferentialDiagnosis": "DDX",
    "FollowUp": "FU",
}

ENTITY_CATEGORY = {
    "Symptom": "临床表现",
    "Sign": "临床表现",
    "Exam": "检查",
    "LabTest": "检验",
    "Medication": "治疗",
    "Procedure": "治疗",
    "TreatmentPlan": "治疗",
    "RiskFactor": "临床",
    "Etiology": "基础医学",
    "Complication": "临床",
    "Prognosis": "临床",
    "DiagnosisCriteria": "诊断",
    "DifferentialDiagnosis": "诊断",
    "FollowUp": "随访",
}

RELATION_FOR_TYPE = {
    "Symptom": ("has_symptom", "clinical"),
    "Sign": ("has_sign", "clinical"),
    "Exam": ("requires_exam", "diagnostic"),
    "LabTest": ("requires_lab_test", "diagnostic"),
    "Medication": ("treated_by_medication", "therapeutic"),
    "Procedure": ("treated_by_procedure", "therapeutic"),
    "TreatmentPlan": ("has_treatment_plan", "therapeutic"),
    "RiskFactor": ("has_risk_factor", "clinical"),
    "Etiology": ("has_etiology", "clinical"),
    "Complication": ("may_cause_complication", "clinical"),
    "Prognosis": ("has_prognosis", "clinical"),
    "DiagnosisCriteria": ("has_diagnostic_criteria", "diagnostic"),
    "DifferentialDiagnosis": ("differentiates_from", "diagnostic"),
    "FollowUp": ("has_follow_up", "therapeutic"),
}


TERM_SPECS: list[dict[str, Any]] = [
    # 症状
    {"type": "Symptom", "name": "呼吸困难", "aliases": ["气急", "气促", "喘憋"]},
    {"type": "Symptom", "name": "劳力性呼吸困难", "aliases": ["活动后气急"]},
    {"type": "Symptom", "name": "端坐呼吸", "aliases": []},
    {"type": "Symptom", "name": "夜间阵发性呼吸困难", "aliases": []},
    {"type": "Symptom", "name": "胸痛", "aliases": ["心前区疼痛"]},
    {"type": "Symptom", "name": "胸闷", "aliases": []},
    {"type": "Symptom", "name": "心悸", "aliases": []},
    {"type": "Symptom", "name": "乏力", "aliases": ["疲乏", "易疲劳", "易疲乏"]},
    {"type": "Symptom", "name": "头晕", "aliases": []},
    {"type": "Symptom", "name": "晕厥", "aliases": ["昏厥"]},
    {"type": "Symptom", "name": "黑矇", "aliases": ["黑蒙"]},
    {"type": "Symptom", "name": "咳嗽", "aliases": []},
    {"type": "Symptom", "name": "咯血", "aliases": ["咳血"]},
    {"type": "Symptom", "name": "恶心呕吐", "aliases": ["恶心", "呕吐"]},
    {"type": "Symptom", "name": "上腹痛", "aliases": []},
    {"type": "Symptom", "name": "出汗", "aliases": ["大汗"]},
    {"type": "Symptom", "name": "濒死感", "aliases": []},
    {"type": "Symptom", "name": "发热", "aliases": ["低热", "高热"]},
    {"type": "Symptom", "name": "水肿感", "aliases": ["肿胀"]},
    {"type": "Symptom", "name": "紫绀", "aliases": ["青紫"]},
    # 体征
    {"type": "Sign", "name": "水肿", "aliases": ["下肢水肿"]},
    {"type": "Sign", "name": "颈静脉怒张", "aliases": ["颈静脉充盈", "颈静脉充盈或怒张"]},
    {"type": "Sign", "name": "肺部啰音", "aliases": ["湿啰音", "干湿啰音", "肺部干湿啰音"]},
    {"type": "Sign", "name": "心脏杂音", "aliases": ["收缩期杂音", "舒张期杂音", "叹气样舒张期杂音", "喷射性杂音", "吹风样杂音"]},
    {"type": "Sign", "name": "第三心音", "aliases": ["S3"]},
    {"type": "Sign", "name": "第四心音", "aliases": ["S4"]},
    {"type": "Sign", "name": "奔马律", "aliases": []},
    {"type": "Sign", "name": "心动过速", "aliases": ["心率增快"]},
    {"type": "Sign", "name": "心动过缓", "aliases": ["心率减慢"]},
    {"type": "Sign", "name": "低血压", "aliases": ["血压下降", "下肢血压下降"]},
    {"type": "Sign", "name": "高血压", "aliases": ["血压升高"]},
    {"type": "Sign", "name": "心脏扩大", "aliases": ["心界扩大", "心室扩大", "心腔扩大", "左心室扩大", "左心房扩大", "右心室扩大"]},
    {"type": "Sign", "name": "发绀", "aliases": ["紫绀", "青紫"]},
    {"type": "Sign", "name": "杵状指", "aliases": ["杵状指（趾）"]},
    {"type": "Sign", "name": "皮肤黏膜瘀点", "aliases": ["瘀点"]},
    {"type": "Sign", "name": "Osler结节", "aliases": ["Osler 结节"]},
    {"type": "Sign", "name": "Janeway损害", "aliases": ["Janeway 点"]},
    # 检查
    {"type": "Exam", "name": "心电图", "aliases": ["ECG"]},
    {"type": "Exam", "name": "动态心电图", "aliases": ["Holter"]},
    {"type": "Exam", "name": "超声心动图", "aliases": ["心脏超声", "床旁心脏超声"]},
    {"type": "Exam", "name": "胸部X线检查", "aliases": ["X 线", "X线", "胸片"]},
    {"type": "Exam", "name": "冠状动脉造影", "aliases": ["冠脉造影"]},
    {"type": "Exam", "name": "冠状动脉CTA", "aliases": ["CTA"]},
    {"type": "Exam", "name": "磁共振成像", "aliases": ["MRI", "MRA", "磁共振显像"]},
    {"type": "Exam", "name": "CT检查", "aliases": ["CT"]},
    {"type": "Exam", "name": "电生理检查", "aliases": ["心内电生理检查"]},
    {"type": "Exam", "name": "心内膜心肌活检", "aliases": ["心肌活检", "心内膜和心肌活检"]},
    {"type": "Exam", "name": "心脏导管检查", "aliases": ["导管检查"]},
    # 检验
    {"type": "LabTest", "name": "心肌肌钙蛋白", "aliases": ["肌钙蛋白", "血肌钙蛋白"]},
    {"type": "LabTest", "name": "脑钠肽", "aliases": ["BNP", "NT-proBNP"]},
    {"type": "LabTest", "name": "D-二聚体", "aliases": ["D - 二聚体"]},
    {"type": "LabTest", "name": "血脂检查", "aliases": ["血脂"]},
    {"type": "LabTest", "name": "血糖", "aliases": ["血糖检查"]},
    {"type": "LabTest", "name": "肾功能", "aliases": ["肌酐"]},
    {"type": "LabTest", "name": "血培养", "aliases": ["微生物培养"]},
    {"type": "LabTest", "name": "C反应蛋白", "aliases": ["C 反应蛋白", "CRP"]},
    {"type": "LabTest", "name": "红细胞沉降率", "aliases": ["血沉"]},
    {"type": "LabTest", "name": "血常规", "aliases": []},
    # 治疗方案和药物
    {"type": "TreatmentPlan", "name": "抗凝治疗", "aliases": []},
    {"type": "TreatmentPlan", "name": "抗血小板治疗", "aliases": []},
    {"type": "TreatmentPlan", "name": "血运重建", "aliases": ["再灌注治疗"]},
    {"type": "TreatmentPlan", "name": "降压治疗", "aliases": ["控制血压"]},
    {"type": "TreatmentPlan", "name": "控制心室率", "aliases": []},
    {"type": "TreatmentPlan", "name": "复律治疗", "aliases": ["复律"]},
    {"type": "Medication", "name": "血管紧张素转换酶抑制剂", "aliases": ["ACEI"]},
    {"type": "Medication", "name": "血管紧张素Ⅱ受体拮抗剂", "aliases": ["ARB"]},
    {"type": "Medication", "name": "β受体阻滞剂", "aliases": ["β 受体阻滞剂"]},
    {"type": "Medication", "name": "利尿剂", "aliases": []},
    {"type": "Medication", "name": "醛固酮受体拮抗剂", "aliases": ["MRA"]},
    {"type": "Medication", "name": "硝酸酯类药物", "aliases": ["硝酸酯"]},
    {"type": "Medication", "name": "他汀类药物", "aliases": ["他汀"]},
    {"type": "Medication", "name": "抗血小板药物", "aliases": ["抗血小板剂"]},
    {"type": "Medication", "name": "抗凝药物", "aliases": ["抗凝剂"]},
    {"type": "Medication", "name": "胺碘酮", "aliases": []},
    {"type": "Medication", "name": "洋地黄类药物", "aliases": ["地高辛", "洋地黄"]},
    {"type": "Medication", "name": "钙通道阻滞剂", "aliases": ["钙拮抗剂"]},
    {"type": "Medication", "name": "溶栓药物", "aliases": ["纤溶药物"]},
    # 操作/手术
    {"type": "Procedure", "name": "经皮冠状动脉介入治疗", "aliases": ["PCI", "介入治疗"]},
    {"type": "Procedure", "name": "冠状动脉旁路移植术", "aliases": ["CABG"]},
    {"type": "Procedure", "name": "射频消融术", "aliases": ["导管消融", "消融术"]},
    {"type": "Procedure", "name": "起搏器植入", "aliases": ["起搏治疗"]},
    {"type": "Procedure", "name": "植入式心律转复除颤器", "aliases": ["ICD"]},
    {"type": "Procedure", "name": "心脏再同步治疗", "aliases": ["CRT"]},
    {"type": "Procedure", "name": "心脏移植", "aliases": []},
    {"type": "Procedure", "name": "瓣膜置换术", "aliases": ["瓣膜置换"]},
    {"type": "Procedure", "name": "经导管主动脉瓣置换术", "aliases": ["TAVR"]},
    {"type": "Procedure", "name": "心包穿刺", "aliases": ["心包引流"]},
    # 其他基础画像
    {"type": "RiskFactor", "name": "吸烟", "aliases": []},
    {"type": "RiskFactor", "name": "糖尿病", "aliases": []},
    {"type": "RiskFactor", "name": "高脂血症", "aliases": ["高胆固醇血症"]},
    {"type": "RiskFactor", "name": "肥胖", "aliases": []},
    {"type": "RiskFactor", "name": "家族史", "aliases": []},
    {"type": "RiskFactor", "name": "感染", "aliases": []},
    {"type": "Etiology", "name": "动脉粥样硬化", "aliases": []},
    {"type": "Etiology", "name": "遗传因素", "aliases": ["遗传性"]},
    {"type": "Etiology", "name": "炎症", "aliases": ["炎症反应"]},
    {"type": "Complication", "name": "心力衰竭", "aliases": ["心功能不全", "心衰"]},
    {"type": "Complication", "name": "心律失常", "aliases": []},
    {"type": "Complication", "name": "感染性心内膜炎", "aliases": []},
    {"type": "Complication", "name": "脑卒中", "aliases": ["脑血管意外"]},
    {"type": "Complication", "name": "猝死", "aliases": ["心脏性猝死"]},
]


def stable_hash(*parts: str, length: int = 12) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest().upper()[:length]


def relation_id(source: str, relation_type: str, target: str) -> str:
    return f"REL-{stable_hash(source, relation_type, target)}"


def entity_code(entity_type: str, name: str) -> str:
    return f"{TYPE_PREFIX[entity_type]}-CARD-TEXT-{stable_hash(entity_type, name, length=10)}"


def evidence_code(disease_code: str, entity_type: str, name: str, line_number: int) -> str:
    return f"EVD-CARD-DEEP-{stable_hash(disease_code, entity_type, name, str(line_number), length=14)}"


def matches_term(text: str, term: str) -> bool:
    if not term:
        return False
    if term.isascii():
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, re.IGNORECASE))
    return term in text


def extract_mentions(text: str) -> list[tuple[str, str]]:
    mentions: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for spec in TERM_SPECS:
        terms = [spec["name"], *spec.get("aliases", [])]
        if any(matches_term(text, term) for term in terms):
            item = (spec["type"], spec["name"])
            if item not in seen:
                mentions.append(item)
                seen.add(item)
    return mentions


def term_aliases(entity_type: str, name: str) -> list[str]:
    for spec in TERM_SPECS:
        if spec["type"] == entity_type and spec["name"] == name:
            return spec.get("aliases", [])
    return []


def merge_aliases(node: dict[str, Any], aliases: list[str]) -> None:
    existing = node.get("aliases", [])
    if isinstance(existing, str):
        existing = [item.strip() for item in existing.split(",") if item.strip()]
    merged: list[str] = []
    for alias in [*existing, *aliases]:
        if alias and alias not in merged and alias != node.get("name"):
            merged.append(alias)
    if merged:
        node["aliases"] = merged


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_taxonomy(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_cardiology_lines(foundation_dir: Path) -> list[tuple[int, str]]:
    text_path = foundation_dir / "03_clean_text" / f"{PRIMARY_DOCUMENT_ID}.clean.txt"
    rows: list[tuple[int, str]] = []
    for index, line in enumerate(text_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if CARDIOLOGY_LINE_START <= index <= CARDIOLOGY_LINE_END:
            cleaned = re.sub(r"\s+", " ", line).strip()
            if cleaned and not cleaned.startswith("<<<SECTION"):
                rows.append((index, cleaned))
    return rows


def is_heading(text: str) -> bool:
    return bool(re.match(r"^第[一二三四五六七八九十百]+[章节]\b", text) or text.startswith("【"))


def heading_ranges(lines: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    headings = [(line_no, text) for line_no, text in lines if is_heading(text)]
    ranges: list[tuple[int, int, str]] = []
    for index, (line_no, title) in enumerate(headings):
        end = headings[index + 1][0] - 1 if index + 1 < len(headings) else CARDIOLOGY_LINE_END
        ranges.append((line_no, end, title))
    return ranges


def disease_terms(row: dict[str, str]) -> list[str]:
    terms = [row["disease_name"]]
    aliases = [item.strip() for item in (row.get("aliases") or "").split(",") if item.strip()]
    for alias in aliases:
        if not alias.isascii() or len(alias) >= 3:
            terms.append(alias)
    return terms


def context_lines_for_disease(lines: list[tuple[int, str]], ranges: list[tuple[int, int, str]], disease: dict[str, str]) -> list[tuple[int, str]]:
    terms = disease_terms(disease)
    by_line = {line_no: text for line_no, text in lines}
    selected: dict[int, str] = {}

    matched_ranges = [
        (start, end)
        for start, end, title in ranges
        if any(matches_term(title, term) for term in terms)
    ]
    for start, end in matched_ranges:
        for line_no, text in lines:
            if start <= line_no <= end:
                selected[line_no] = text

    hit_lines = [line_no for line_no, text in lines if any(matches_term(text, term) for term in terms)]
    for hit in hit_lines:
        for line_no in range(max(CARDIOLOGY_LINE_START, hit - 2), min(CARDIOLOGY_LINE_END, hit + 3) + 1):
            if line_no in by_line:
                selected[line_no] = by_line[line_no]

    return sorted(selected.items())


def base_node(code: str, name: str, entity_type: str, **extra: Any) -> dict[str, Any]:
    row = {
        "id": f"KG_{code}",
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": ENTITY_CATEGORY[entity_type],
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved",
        "batch_id": BATCH_ID,
        "scope_type": "specialty",
        "scope_target": "心血管内科",
        "merge_status": "validated",
        "source_type": "authoritative_textbook",
    }
    row.update({key: value for key, value in extra.items() if value not in (None, "", [])})
    return row


def evidence_node(code: str, disease_code: str, disease_name: str, line_number: int, evidence_text: str, entity_type: str, target_name: str) -> dict[str, Any]:
    return {
        "id": f"KG_{code}",
        "code": code,
        "name": f"{disease_name}-{target_name}-教材证据-{line_number}-{code[-6:]}",
        "preferred_name": f"{disease_name}-{target_name}-教材证据-{line_number}-{code[-6:]}",
        "display_name": f"{disease_name}-{target_name}-教材证据-{line_number}-{code[-6:]}",
        "entityType": "Evidence",
        "entityCategory": "证据",
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved",
        "batch_id": BATCH_ID,
        "document_id": PRIMARY_DOCUMENT_ID,
        "segment_id": f"LINE-{line_number}",
        "source_name": PRIMARY_SOURCE_NAME,
        "source_type": "authoritative_textbook",
        "source_version": PRIMARY_SOURCE_VERSION,
        "source_section": PRIMARY_SOURCE_SECTION,
        "source_page": "N/A",
        "line_start": line_number,
        "line_end": line_number,
        "evidence_text": evidence_text,
        "language": "zh-CN",
        "translation_text": "",
        "translation_method": "N/A",
        "content_hash": stable_hash(evidence_text, length=16),
        "guideline_id": PRIMARY_GUIDELINE_ID,
        "evidence_id": code,
        "recommendation_class": "N/A",
        "evidence_level": "N/A",
        "confidence": 1.0,
        "disease_code": disease_code,
        "disease_name": disease_name,
        "pathway_element": entity_type,
    }


def provenance(disease_code: str, disease_name: str, line_number: int, evidence_text: str, evidence_id_value: str) -> dict[str, Any]:
    return {
        "document_id": PRIMARY_DOCUMENT_ID,
        "segment_id": f"LINE-{line_number}",
        "source_name": PRIMARY_SOURCE_NAME,
        "source_type": "authoritative_textbook",
        "source_version": PRIMARY_SOURCE_VERSION,
        "source_section": PRIMARY_SOURCE_SECTION,
        "source_page": "N/A",
        "line_start": line_number,
        "line_end": line_number,
        "evidence_text": evidence_text,
        "guideline_id": PRIMARY_GUIDELINE_ID,
        "evidence_id": evidence_id_value,
        "recommendation_class": "N/A",
        "evidence_level": "N/A",
        "confidence": 1.0,
        "disease_code": disease_code,
        "disease_name": disease_name,
    }


def build_evidence_backed_relation(
    disease_code: str,
    disease_name: str,
    target_code: str,
    target_name: str,
    relation_type: str,
    relation_category: str,
    evidence_code: str,
    line_number: int,
    evidence_text: str,
) -> dict[str, Any]:
    prov = provenance(disease_code, disease_name, line_number, evidence_text, evidence_code)
    return {
        "id": relation_id(disease_code, relation_type, target_code),
        "source_code": disease_code,
        "relationType": relation_type,
        "target_code": target_code,
        "relationCategory": relation_category,
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved",
        "document_id": PRIMARY_DOCUMENT_ID,
        "segment_id": f"LINE-{line_number}",
        "source_name": PRIMARY_SOURCE_NAME,
        "source_type": "authoritative_textbook",
        "source_version": PRIMARY_SOURCE_VERSION,
        "source_section": PRIMARY_SOURCE_SECTION,
        "source_page": "N/A",
        "evidence_text": evidence_text,
        "guideline_id": PRIMARY_GUIDELINE_ID,
        "evidence_id": evidence_code,
        "recommendation_class": "N/A",
        "evidence_level": "N/A",
        "confidence": 1.0,
        "evidence_ids": [evidence_code],
        "document_ids": [PRIMARY_DOCUMENT_ID],
        "source_names": [PRIMARY_SOURCE_NAME],
        "source_types": ["authoritative_textbook"],
        "evidence_count": 1,
        "provenance_records_json": [prov],
        "disease_code": disease_code,
        "disease_name": disease_name,
        "target_name": target_name,
    }


def supported_by_evidence_relation(disease_code: str, disease_name: str, evidence_code_value: str, line_number: int, evidence_text: str) -> dict[str, Any]:
    prov = provenance(disease_code, disease_name, line_number, evidence_text, evidence_code_value)
    return {
        "id": relation_id(disease_code, "supported_by_evidence", evidence_code_value),
        "source_code": disease_code,
        "relationType": "supported_by_evidence",
        "target_code": evidence_code_value,
        "relationCategory": "evidence",
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved",
        "provenance_records_json": [prov],
        "evidence_ids": [evidence_code_value],
        "document_ids": [PRIMARY_DOCUMENT_ID],
        "source_names": [PRIMARY_SOURCE_NAME],
        "source_types": ["authoritative_textbook"],
        "evidence_count": 1,
    }


def merge_provenance(rel: dict[str, Any], evidence_code_value: str, line_number: int, evidence_text: str, disease_code: str, disease_name: str) -> None:
    existing_ids = set(rel.get("evidence_ids") or [])
    if evidence_code_value in existing_ids:
        return
    prov = provenance(disease_code, disease_name, line_number, evidence_text, evidence_code_value)
    rel.setdefault("provenance_records_json", []).append(prov)
    rel.setdefault("evidence_ids", []).append(evidence_code_value)
    rel.setdefault("document_ids", [])
    if PRIMARY_DOCUMENT_ID not in rel["document_ids"]:
        rel["document_ids"].append(PRIMARY_DOCUMENT_ID)
    rel.setdefault("source_names", [])
    if PRIMARY_SOURCE_NAME not in rel["source_names"]:
        rel["source_names"].append(PRIMARY_SOURCE_NAME)
    rel.setdefault("source_types", [])
    if "authoritative_textbook" not in rel["source_types"]:
        rel["source_types"].append("authoritative_textbook")
    rel["evidence_count"] = len(rel["provenance_records_json"])


def enrich_foundation(foundation_dir: Path, max_context_lines_per_disease: int = 260) -> dict[str, Any]:
    foundation_dir = foundation_dir.resolve()
    data_dir = foundation_dir / "05_data_instance"
    audit_dir = foundation_dir / "06_quality_audit"
    review_dir = foundation_dir / "07_review_package"
    extraction_dir = foundation_dir / "04_evidence_and_extraction"

    nodes = load_jsonl(data_dir / "nodes_final.jsonl")
    relations = load_jsonl(data_dir / "relations_final.jsonl")
    taxonomy = read_taxonomy(foundation_dir / "foundation_scope_taxonomy.csv")
    lines = read_cardiology_lines(foundation_dir)
    ranges = heading_ranges(lines)

    for row in nodes:
        row["schema_version"] = SCHEMA_VERSION
        if row.get("entityType") == "Evidence" and str(row.get("code", "")).startswith("EVD-CARD-DEEP-"):
            row["guideline_id"] = PRIMARY_GUIDELINE_ID
            row["source_page"] = row.get("source_page") or "N/A"
            row["source_type"] = "authoritative_textbook"
            row["recommendation_class"] = "N/A"
            row["evidence_level"] = "N/A"
            line_number = row.get("line_start") or str(row.get("segment_id", "")).replace("LINE-", "")
            disease_name = row.get("disease_name", "疾病")
            target_name = row.get("name", "教材证据").split("-教材证据", 1)[0].split("-", 1)[-1]
            unique_name = f"{disease_name}-{target_name}-教材证据-{line_number}-{str(row['code'])[-6:]}"
            row["name"] = unique_name
            row["preferred_name"] = unique_name
            row["display_name"] = unique_name
    for row in relations:
        row["schema_version"] = SCHEMA_VERSION
        if row.get("source_type") == "authoritative_textbook" or any(str(eid).startswith("EVD-CARD-DEEP-") for eid in row.get("evidence_ids", []) or []):
            row["guideline_id"] = row.get("guideline_id") or PRIMARY_GUIDELINE_ID
            row["source_page"] = row.get("source_page") or "N/A"
        for prov in row.get("provenance_records_json", []) or []:
            if isinstance(prov, dict) and prov.get("source_type") == "authoritative_textbook":
                prov["guideline_id"] = prov.get("guideline_id") or PRIMARY_GUIDELINE_ID
                prov["source_page"] = prov.get("source_page") or "N/A"

    node_by_code = {row["code"]: row for row in nodes}
    code_by_type_name = {(row.get("entityType"), row.get("name")): row["code"] for row in nodes}
    for spec in TERM_SPECS:
        existing_code = code_by_type_name.get((spec["type"], spec["name"]))
        if existing_code:
            merge_aliases(node_by_code[existing_code], spec.get("aliases", []))
    relation_by_semantic = {(row["source_code"], row["relationType"], row["target_code"]): row for row in relations}
    evidence_codes = {row["code"] for row in nodes if row.get("entityType") == "Evidence"}

    extraction_rows: list[dict[str, Any]] = []
    disease_coverage: dict[str, Counter] = {}
    added_nodes = 0
    added_relations = 0
    added_evidence = 0

    for disease in taxonomy:
        disease_code = disease["disease_code"]
        disease_name = disease["disease_name"]
        contexts = context_lines_for_disease(lines, ranges, disease)[:max_context_lines_per_disease]
        disease_counter: Counter = Counter()
        for line_number, text in contexts:
            mentions = extract_mentions(text)
            if not mentions:
                continue
            for entity_type, name in mentions:
                relation_type, relation_category = RELATION_FOR_TYPE[entity_type]
                code = code_by_type_name.get((entity_type, name))
                if not code:
                    code = entity_code(entity_type, name)
                    node = base_node(
                        code,
                        name,
                        entity_type,
                        aliases=term_aliases(entity_type, name),
                        description=f"{name}（教材深层实体化抽取）",
                    )
                    nodes.append(node)
                    node_by_code[code] = node
                    code_by_type_name[(entity_type, name)] = code
                    added_nodes += 1

                ev_code = evidence_code(disease_code, entity_type, name, line_number)
                if ev_code not in evidence_codes:
                    nodes.append(evidence_node(ev_code, disease_code, disease_name, line_number, text, entity_type, name))
                    evidence_codes.add(ev_code)
                    added_evidence += 1

                semantic = (disease_code, relation_type, code)
                rel = relation_by_semantic.get(semantic)
                if not rel:
                    rel = build_evidence_backed_relation(
                        disease_code=disease_code,
                        disease_name=disease_name,
                        target_code=code,
                        target_name=name,
                        relation_type=relation_type,
                        relation_category=relation_category,
                        evidence_code=ev_code,
                        line_number=line_number,
                        evidence_text=text,
                    )
                    relations.append(rel)
                    relation_by_semantic[semantic] = rel
                    added_relations += 1
                else:
                    merge_provenance(rel, ev_code, line_number, text, disease_code, disease_name)

                evidence_semantic = (disease_code, "supported_by_evidence", ev_code)
                if evidence_semantic not in relation_by_semantic:
                    evidence_rel = supported_by_evidence_relation(disease_code, disease_name, ev_code, line_number, text)
                    relations.append(evidence_rel)
                    relation_by_semantic[evidence_semantic] = evidence_rel
                    added_relations += 1

                disease_counter[entity_type] += 1
                extraction_rows.append(
                    {
                        "disease_code": disease_code,
                        "disease_name": disease_name,
                        "entityType": entity_type,
                        "entity_name": name,
                        "entity_code": code,
                        "relationType": relation_type,
                        "line_number": line_number,
                        "evidence_code": ev_code,
                        "evidence_text": text,
                    }
                )
        disease_coverage[disease_code] = disease_counter

    write_jsonl(data_dir / "nodes_final.jsonl", nodes)
    write_jsonl(data_dir / "relations_final.jsonl", relations)
    write_jsonl(foundation_dir / "foundation_nodes_deep_enriched.jsonl", nodes)
    write_jsonl(foundation_dir / "foundation_relations_deep_enriched.jsonl", relations)
    write_csv(
        extraction_dir / "textbook_deep_extraction_index.csv",
        ["disease_code", "disease_name", "entityType", "entity_name", "entity_code", "relationType", "line_number", "evidence_code", "evidence_text"],
        extraction_rows,
    )
    coverage_rows = []
    for disease in taxonomy:
        counter = disease_coverage[disease["disease_code"]]
        coverage_rows.append(
            {
                "disease_code": disease["disease_code"],
                "disease_name": disease["disease_name"],
                "symptom_count": counter["Symptom"],
                "sign_count": counter["Sign"],
                "exam_count": counter["Exam"],
                "lab_test_count": counter["LabTest"],
                "treatment_plan_count": counter["TreatmentPlan"],
                "medication_count": counter["Medication"],
                "procedure_count": counter["Procedure"],
                "risk_factor_count": counter["RiskFactor"],
                "complication_count": counter["Complication"],
                "prognosis_count": counter["Prognosis"],
                "total_extracted_mentions": sum(counter.values()),
            }
        )
    write_csv(
        audit_dir / "textbook_deep_extraction_coverage.csv",
        [
            "disease_code",
            "disease_name",
            "symptom_count",
            "sign_count",
            "exam_count",
            "lab_test_count",
            "treatment_plan_count",
            "medication_count",
            "procedure_count",
            "risk_factor_count",
            "complication_count",
            "prognosis_count",
            "total_extracted_mentions",
        ],
        coverage_rows,
    )

    summary = {
        "status": "textbook_deep_extraction_completed",
        "schema_version": SCHEMA_VERSION,
        "source_document_id": PRIMARY_DOCUMENT_ID,
        "source_name": PRIMARY_SOURCE_NAME,
        "disease_count": len(taxonomy),
        "node_count": len(nodes),
        "relation_count": len(relations),
        "added_node_count": added_nodes,
        "added_evidence_node_count": added_evidence,
        "added_or_updated_relation_count": added_relations,
        "extraction_row_count": len(extraction_rows),
        "entity_type_counts": dict(Counter(row.get("entityType", "") for row in nodes)),
        "relation_type_counts": dict(Counter(row.get("relationType", "") for row in relations)),
        "diseases_with_symptom": sum(1 for row in coverage_rows if int(row["symptom_count"]) > 0),
        "diseases_with_sign": sum(1 for row in coverage_rows if int(row["sign_count"]) > 0),
        "diseases_with_exam": sum(1 for row in coverage_rows if int(row["exam_count"]) > 0),
        "diseases_with_treatment": sum(1 for row in coverage_rows if int(row["treatment_plan_count"]) + int(row["medication_count"]) + int(row["procedure_count"]) > 0),
    }
    (audit_dir / "textbook_deep_extraction_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    report = f"""# 教材深层实体化抽取报告

生成批次：{BATCH_ID}
来源：{PRIMARY_SOURCE_NAME}

## 结果摘要

- 疾病数：{summary['disease_count']}
- 新增普通实体节点：{summary['added_node_count']}
- 新增证据节点：{summary['added_evidence_node_count']}
- 新增关系：{summary['added_or_updated_relation_count']}
- 抽取命中行：{summary['extraction_row_count']}
- 当前总节点：{summary['node_count']}
- 当前总关系：{summary['relation_count']}

## 覆盖摘要

- 有症状抽取的疾病：{summary['diseases_with_symptom']}
- 有体征抽取的疾病：{summary['diseases_with_sign']}
- 有检查抽取的疾病：{summary['diseases_with_exam']}
- 有治疗相关抽取的疾病：{summary['diseases_with_treatment']}

## 文件

- 抽取明细：`04_evidence_and_extraction/textbook_deep_extraction_index.csv`
- 覆盖矩阵：`06_quality_audit/textbook_deep_extraction_coverage.csv`
- 质量摘要：`06_quality_audit/textbook_deep_extraction_summary.json`
"""
    (review_dir / "教材深层实体化抽取报告.md").write_text(report, encoding="utf-8-sig")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Deep extract cardiology textbook entities into the foundation graph.")
    parser.add_argument("--foundation-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(enrich_foundation(args.foundation_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
