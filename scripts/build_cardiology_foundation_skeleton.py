from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


BATCH_ID = "FOUNDATION-CARD-20260624-001"
SCHEMA_VERSION = "V1.4"
PRIMARY_DOCUMENT_ID = "DOC-CF62B75AEC93F1A6"
PRIMARY_SOURCE_NAME = "《内科学（第10版）》.docx"
CARDIOLOGY_LINE_START = 5339
CARDIOLOGY_LINE_END = 11398


PATHWAY_ELEMENTS = [
    "definition",
    "epidemiology",
    "etiology",
    "risk_factor",
    "pathophysiology",
    "symptom",
    "sign",
    "complication",
    "prognosis",
    "diagnosis_criteria",
    "differential_diagnosis",
    "exam",
    "lab_test",
    "treatment_plan",
    "medication",
    "procedure",
    "follow_up",
]


PATHWAY_PATTERNS = {
    "definition": (r"是指", r"称为", r"定义为"),
    "epidemiology": (r"流行病学", r"发病率", r"患病率", r"病死率"),
    "etiology": (r"病因", r"原因"),
    "risk_factor": (r"危险因素", r"高危因素", r"风险因素"),
    "pathophysiology": (r"病理生理", r"发病机制", r"病理解剖", r"病理"),
    "symptom": (r"症状", r"临床表现"),
    "sign": (r"体征", r"听诊", r"杂音"),
    "complication": (r"并发症"),
    "prognosis": (r"预后", r"死亡率"),
    "diagnosis_criteria": (r"诊断", r"诊断标准"),
    "differential_diagnosis": (r"鉴别诊断", r"鉴别"),
    "exam": (r"辅助检查", r"影像", r"心电图", r"超声心动图", r"CT", r"MRI", r"造影"),
    "lab_test": (r"实验室", r"血清", r"肌钙蛋白", r"BNP", r"NT-proBNP"),
    "treatment_plan": (r"治疗", r"处理", r"管理"),
    "medication": (r"药物", r"β受体", r"利尿", r"抗凝", r"抗血小板", r"ACEI", r"ARB", r"他汀"),
    "procedure": (r"手术", r"介入", r"消融", r"PCI", r"CABG", r"置换", r"植入"),
    "follow_up": (r"随访", r"复查"),
}


TAXONOMY = [
    {
        "category_code": "CAT-CARD-HF",
        "category": "心力衰竭",
        "subcategory": "心力衰竭",
        "diseases": [
            ("DIS-CARD-HF-GENERAL", "心力衰竭", "heart failure", ["HF"]),
            ("DIS-CARD-HF-CHF", "慢性心力衰竭", "chronic heart failure", ["CHF"]),
            ("DIS-CARD-HF-AHF", "急性心力衰竭", "acute heart failure", ["AHF"]),
        ],
    },
    {
        "category_code": "CAT-CARD-ARR",
        "category": "心律失常",
        "subcategory": "心律失常",
        "diseases": [
            ("DIS-CARD-ARR-SINUS", "窦性心律失常", "sinus arrhythmia", []),
            ("DIS-CARD-ARR-AT", "房性心动过速", "atrial tachycardia", []),
            ("DIS-CARD-ARR-AFL", "心房扑动", "atrial flutter", ["房扑"]),
            ("DIS-CARD-ARR-AF", "心房颤动", "atrial fibrillation", ["AF", "房颤"]),
            ("DIS-CARD-ARR-PSVT", "阵发性室上性心动过速", "paroxysmal supraventricular tachycardia", ["PSVT"]),
            ("DIS-CARD-ARR-PVC", "室性期前收缩", "premature ventricular beat", ["室早"]),
            ("DIS-CARD-ARR-VT", "室性心动过速", "ventricular tachycardia", ["室速"]),
            ("DIS-CARD-ARR-VF", "心室扑动与心室颤动", "ventricular flutter and ventricular fibrillation", ["室扑", "室颤", "VF"]),
            ("DIS-CARD-ARR-AVB", "房室传导阻滞", "atrioventricular block", ["AVB"]),
            ("DIS-CARD-ARR-LQTS", "长QT间期综合征", "long-QT syndrome", ["LQTS"]),
            ("DIS-CARD-ARR-BRUGADA", "Brugada综合征", "Brugada syndrome", []),
            ("DIS-CARD-ARR-CPVT", "儿茶酚胺敏感性室性心动过速", "catecholaminergic polymorphic ventricular tachycardia", ["CPVT"]),
            ("DIS-CARD-ARR-ERS", "早期复极综合征", "early repolarization syndrome", ["ERS"]),
        ],
    },
    {
        "category_code": "CAT-CARD-CAD",
        "category": "冠状动脉疾病",
        "subcategory": "冠状动脉粥样硬化性心脏病",
        "diseases": [
            ("DIS-CARD-CAD-ATHEROSCLEROSIS", "动脉粥样硬化", "atherosclerosis", []),
            ("DIS-CARD-CAD-CHD", "冠状动脉粥样硬化性心脏病", "coronary atherosclerotic heart disease", ["冠心病", "CHD", "CAD"]),
            ("DIS-CARD-CAD-CCS", "慢性冠脉综合征", "chronic coronary syndrome", ["CCS", "慢性冠状动脉疾病", "CCD"]),
            ("DIS-CARD-CAD-STABLE-ANGINA", "稳定型心绞痛", "stable angina", []),
            ("DIS-CARD-CAD-ICM", "缺血性心肌病", "ischemic cardiomyopathy", ["ICM"]),
            ("DIS-CARD-CAD-ACS", "急性冠脉综合征", "acute coronary syndrome", ["ACS"]),
            ("DIS-CARD-CAD-UA", "不稳定型心绞痛", "unstable angina", ["UA"]),
            ("DIS-CARD-CAD-AMI", "急性心肌梗死", "acute myocardial infarction", ["AMI", "心梗"]),
            ("DIS-CARD-CAD-STEMI", "ST段抬高型心肌梗死", "ST-segment elevation myocardial infarction", ["STEMI"]),
            ("DIS-CARD-CAD-NSTEMI", "非ST段抬高型心肌梗死", "non-ST-segment elevation myocardial infarction", ["NSTEMI", "NSTE-ACS"]),
            ("DIS-CARD-CAD-SPASM", "冠状动脉痉挛", "coronary artery spasm", []),
            ("DIS-CARD-CAD-POST-MI-SYNDROME", "心肌梗死后综合征", "post-infarction syndrome", []),
        ],
    },
    {
        "category_code": "CAT-CARD-HTN",
        "category": "高血压",
        "subcategory": "高血压",
        "diseases": [
            ("DIS-CARD-HTN-ESSENTIAL", "原发性高血压", "essential hypertension", []),
            ("DIS-CARD-HTN-SECONDARY", "继发性高血压", "secondary hypertension", []),
            ("DIS-CARD-HTN-EMERGENCY", "高血压急症和亚急症", "hypertensive emergencies and urgencies", []),
            ("DIS-CARD-HTN-RENAL-PARENCHYMAL", "肾实质性高血压", "renal parenchymal hypertension", []),
            ("DIS-CARD-HTN-RENOVASCULAR", "肾血管性高血压", "renovascular hypertension", []),
            ("DIS-CARD-HTN-PA", "原发性醛固酮增多症", "primary aldosteronism", []),
            ("DIS-CARD-HTN-PHEO", "嗜铬细胞瘤和副神经节瘤", "pheochromocytoma and paraganglioma", []),
            ("DIS-CARD-HTN-COA", "主动脉缩窄", "coarctation of the aorta", []),
        ],
    },
    {
        "category_code": "CAT-CARD-CM",
        "category": "心肌疾病",
        "subcategory": "心肌病与心肌炎",
        "diseases": [
            ("DIS-CARD-CM-HCM", "肥厚型心肌病", "hypertrophic cardiomyopathy", ["HCM"]),
            ("DIS-CARD-CM-DCM", "扩张型心肌病", "dilated cardiomyopathy", ["DCM"]),
            ("DIS-CARD-CM-NDLVCM", "非扩张型左心室心肌病", "non-dilated left ventricular cardiomyopathy", ["NDLVC"]),
            ("DIS-CARD-CM-ARVC", "致心律失常性右心室心肌病", "arrhythmogenic right ventricular cardiomyopathy", ["ARVC"]),
            ("DIS-CARD-CM-RCM", "限制型心肌病", "restrictive cardiomyopathy", ["RCM"]),
            ("DIS-CARD-CM-MYOCARDITIS", "心肌炎", "myocarditis", []),
        ],
    },
    {
        "category_code": "CAT-CARD-CHD",
        "category": "先天性心血管病",
        "subcategory": "成人先天性心血管病",
        "diseases": [
            ("DIS-CARD-CHD-ASD", "房间隔缺损", "atrial septal defect", ["ASD"]),
            ("DIS-CARD-CHD-VSD", "室间隔缺损", "ventricular septal defect", ["VSD"]),
            ("DIS-CARD-CHD-PDA", "动脉导管未闭", "patent ductus arteriosus", ["PDA"]),
            ("DIS-CARD-CHD-PS", "肺动脉瓣狭窄", "pulmonary valve stenosis", []),
            ("DIS-CARD-CHD-EBSTEIN", "三尖瓣下移畸形", "Ebstein anomaly", []),
            ("DIS-CARD-CHD-BAV", "二叶主动脉瓣", "bicuspid aortic valve", ["BAV"]),
            ("DIS-CARD-CHD-COA", "先天性主动脉缩窄", "congenital coarctation of the aorta", []),
            ("DIS-CARD-CHD-SOVA", "主动脉窦瘤", "sinus of Valsalva aneurysm", []),
            ("DIS-CARD-CHD-CAF", "冠状动脉瘘", "coronary artery fistula", []),
        ],
    },
    {
        "category_code": "CAT-CARD-VHD",
        "category": "心脏瓣膜病",
        "subcategory": "心脏瓣膜病",
        "diseases": [
            ("DIS-CARD-VHD-AS", "主动脉瓣狭窄", "aortic stenosis", ["AS"]),
            ("DIS-CARD-VHD-AR", "主动脉瓣反流", "aortic regurgitation", ["AR"]),
            ("DIS-CARD-VHD-MS", "二尖瓣狭窄", "mitral stenosis", ["MS"]),
            ("DIS-CARD-VHD-MR", "二尖瓣反流", "mitral regurgitation", ["MR"]),
            ("DIS-CARD-VHD-MULTI", "多瓣膜病", "multiple valvular heart disease", []),
        ],
    },
    {
        "category_code": "CAT-CARD-PERICARD",
        "category": "心包疾病",
        "subcategory": "心包疾病",
        "diseases": [
            ("DIS-CARD-PERICARD-ACUTE", "急性心包炎", "acute pericarditis", []),
            ("DIS-CARD-PERICARD-EFFUSION", "心包积液及心脏压塞", "pericardial effusion and cardiac tamponade", []),
            ("DIS-CARD-PERICARD-CONSTRICTIVE", "缩窄性心包炎", "constrictive pericarditis", []),
        ],
    },
    {
        "category_code": "CAT-CARD-IE",
        "category": "感染性心内膜炎",
        "subcategory": "感染性心内膜炎",
        "diseases": [
            ("DIS-CARD-IE", "感染性心内膜炎", "infective endocarditis", ["IE"]),
            ("DIS-CARD-IE-PVE", "人工瓣膜心内膜炎", "prosthetic valve endocarditis", ["PVE"]),
        ],
    },
    {
        "category_code": "CAT-CARD-SCD",
        "category": "心脏骤停与心脏性猝死",
        "subcategory": "心脏骤停与心脏性猝死",
        "diseases": [
            ("DIS-CARD-SCD-ARREST", "心脏骤停", "cardiac arrest", []),
            ("DIS-CARD-SCD-SUDDEN", "心脏性猝死", "sudden cardiac death", ["SCD"]),
        ],
    },
    {
        "category_code": "CAT-CARD-AORTA-PAD",
        "category": "主动脉和周围血管病",
        "subcategory": "主动脉和周围血管病",
        "diseases": [
            ("DIS-CARD-AORTA-AD", "主动脉夹层", "aortic dissection", ["AD"]),
            ("DIS-CARD-AORTA-ANEURYSM", "主动脉瘤", "aortic aneurysm", []),
            ("DIS-CARD-PAD-LEAD", "下肢动脉硬化闭塞症", "lower extremity atherosclerotic disease", []),
            ("DIS-CARD-VTE", "静脉血栓症", "venous thrombosis", []),
        ],
    },
    {
        "category_code": "CAT-CARD-NEUROSIS",
        "category": "心血管神经症",
        "subcategory": "心血管神经症",
        "diseases": [
            ("DIS-CARD-NEUROSIS", "心血管神经症", "cardiovascular neurosis", []),
        ],
    },
]


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest().upper()[:12]
    return f"{prefix}-{digest}"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def clean_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_primary_lines(foundation_dir: Path) -> list[tuple[int, str]]:
    text_path = foundation_dir / "03_clean_text" / f"{PRIMARY_DOCUMENT_ID}.clean.txt"
    lines = text_path.read_text(encoding="utf-8-sig").splitlines()
    return [
        (index, clean_line(line))
        for index, line in enumerate(lines, start=1)
        if CARDIOLOGY_LINE_START <= index <= CARDIOLOGY_LINE_END and clean_line(line)
    ]


def find_evidence(lines: list[tuple[int, str]], disease_name: str, aliases: list[str]) -> list[dict]:
    terms = [disease_name, *aliases]
    matched = [(line_no, text) for line_no, text in lines if any(term and term in text for term in terms)]
    if not matched:
        return []

    rows: list[dict] = []
    used_elements: set[str] = set()
    for line_no, text in matched:
        elements = [
            element
            for element, patterns in PATHWAY_PATTERNS.items()
            if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
        ]
        if not elements and ("是" in text or "为" in text or len(rows) == 0):
            elements = ["definition"]
        for element in elements:
            if element in used_elements:
                continue
            used_elements.add(element)
            rows.append(
                {
                    "pathway_element": element,
                    "line_number": line_no,
                    "evidence_text": text[:500],
                }
            )
        if len(used_elements) >= 8:
            break
    return rows


def node(code: str, name: str, entity_type: str, category: str, **extra) -> dict:
    row = {
        "id": f"KG_{code}",
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": category,
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved",
        "batch_id": BATCH_ID,
        "scope_type": "specialty",
        "scope_target": "心血管内科",
        "merge_status": "validated",
        "source_version": "第10版",
        "conflict_status": "none",
    }
    row.update({key: value for key, value in extra.items() if value not in (None, "", [])})
    return row


def relation(source: str, relation_type: str, target: str, category: str, **extra) -> dict:
    row = {
        "id": stable_id("REL", source, relation_type, target),
        "source_code": source,
        "relationType": relation_type,
        "target_code": target,
        "relationCategory": category,
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved",
    }
    row.update({key: value for key, value in extra.items() if value not in (None, "", [])})
    return row


def build_foundation(foundation_dir: Path) -> dict:
    foundation_dir = foundation_dir.resolve()
    lines = load_primary_lines(foundation_dir)
    nodes: list[dict] = []
    relations: list[dict] = []
    taxonomy_rows: list[dict] = []
    vocabulary_rows: list[dict] = []
    evidence_rows: list[dict] = []
    coverage_rows: list[dict] = []

    specialty_code = "SPEC-CARD"
    nodes.append(node(specialty_code, "心血管内科", "Specialty", "目录", description="心血管内科基础骨架库根节点"))

    evidence_counter = 0
    for category in TAXONOMY:
        category_code = category["category_code"]
        subcategory_code = category_code.replace("CAT-", "SUB-") + "-GENERAL"
        nodes.append(node(category_code, category["category"], "DiseaseCategory", "目录", parentCode=specialty_code))
        nodes.append(node(subcategory_code, category["subcategory"], "DiseaseSubcategory", "目录", parentCode=category_code))
        relations.append(relation(specialty_code, "has_category", category_code, "structural"))
        relations.append(relation(category_code, "has_subcategory", subcategory_code, "structural"))

        for disease_code, disease_name, name_en, aliases in category["diseases"]:
            taxonomy_rows.append(
                {
                    "specialty_code": specialty_code,
                    "specialty_name": "心血管内科",
                    "category_code": category_code,
                    "category_name": category["category"],
                    "subcategory_code": subcategory_code,
                    "subcategory_name": category["subcategory"],
                    "disease_code": disease_code,
                    "disease_name": disease_name,
                    "name_en": name_en,
                    "aliases": ",".join(aliases),
                    "inclusion_status": "included",
                    "inclusion_reason": "authoritative_textbook_cardiology_chapter",
                }
            )
            vocabulary_rows.append(
                {
                    "canonical_name": disease_name,
                    "code": disease_code,
                    "name_en": name_en,
                    "aliases": ",".join(aliases),
                    "entityType": "Disease",
                    "disease_scope": category["category"],
                    "source": PRIMARY_SOURCE_NAME,
                    "status": "approved",
                }
            )
            nodes.append(
                node(
                    disease_code,
                    disease_name,
                    "Disease",
                    "临床",
                    name_en=name_en,
                    aliases=aliases,
                    parentCode=subcategory_code,
                    description=f"{disease_name}基础骨架节点，来源于《内科学（第10版）》循环系统疾病篇。",
                )
            )
            relations.append(relation(subcategory_code, "has_disease", disease_code, "structural"))
            relations.append(relation(disease_code, "belongs_to_subcategory", subcategory_code, "structural"))
            relations.append(relation(disease_code, "belongs_to_category", category_code, "structural"))

            disease_evidence = find_evidence(lines, disease_name, aliases)
            covered_elements = {item["pathway_element"] for item in disease_evidence}
            for item in disease_evidence:
                evidence_counter += 1
                evidence_code = f"EVD-CARD-FOUND-{evidence_counter:05d}"
                evidence = node(
                    evidence_code,
                    f"{disease_name}-{item['pathway_element']}-教材证据",
                    "Evidence",
                    "证据",
                    document_id=PRIMARY_DOCUMENT_ID,
                    segment_id=f"LINE-{item['line_number']}",
                    source_name=PRIMARY_SOURCE_NAME,
                    source_type="authoritative_textbook",
                    source_version="第10版",
                    source_section="第三篇 循环系统疾病",
                    source_page="",
                    evidence_text=item["evidence_text"],
                    guideline_id="",
                    evidence_id=evidence_code,
                    recommendation_class="N/A",
                    evidence_level="N/A",
                    confidence=1.0,
                    disease_code=disease_code,
                    disease_name=disease_name,
                    pathway_element=item["pathway_element"],
                )
                nodes.append(evidence)
                evidence_rows.append(evidence)
                relations.append(
                    relation(
                        disease_code,
                        "supported_by_evidence",
                        evidence_code,
                        "evidence",
                        document_id=PRIMARY_DOCUMENT_ID,
                        segment_id=f"LINE-{item['line_number']}",
                        source_name=PRIMARY_SOURCE_NAME,
                        source_type="authoritative_textbook",
                        source_version="第10版",
                        source_section="第三篇 循环系统疾病",
                        source_page="",
                        evidence_text=item["evidence_text"],
                        guideline_id="",
                        evidence_id=evidence_code,
                        recommendation_class="N/A",
                        evidence_level="N/A",
                        confidence=1.0,
                        evidence_ids=[evidence_code],
                        document_ids=[PRIMARY_DOCUMENT_ID],
                        source_names=[PRIMARY_SOURCE_NAME],
                        source_types=["authoritative_textbook"],
                        evidence_count=1,
                        provenance_records_json=[
                            {
                                "document_id": PRIMARY_DOCUMENT_ID,
                                "segment_id": f"LINE-{item['line_number']}",
                                "source_name": PRIMARY_SOURCE_NAME,
                                "source_type": "authoritative_textbook",
                                "source_version": "第10版",
                                "source_section": "第三篇 循环系统疾病",
                                "source_page": "",
                                "evidence_text": item["evidence_text"],
                                "recommendation_class": "N/A",
                                "evidence_level": "N/A",
                            }
                        ],
                    )
                )

            for element in PATHWAY_ELEMENTS:
                coverage_rows.append(
                    {
                        "disease_code": disease_code,
                        "disease_name": disease_name,
                        "pathway_element": element,
                        "coverage_status": "covered" if element in covered_elements else "pending_deep_extraction",
                        "source": PRIMARY_SOURCE_NAME if element in covered_elements else "",
                        "note": "教材正文关键词命中" if element in covered_elements else "需在下一轮分段语义抽取中补齐实体化证据",
                    }
                )

    data_dir = foundation_dir / "05_data_instance"
    audit_dir = foundation_dir / "06_quality_audit"
    write_jsonl(foundation_dir / "foundation_nodes.jsonl", nodes)
    write_jsonl(foundation_dir / "foundation_relations.jsonl", relations)
    write_jsonl(foundation_dir / "foundation_evidence.jsonl", evidence_rows)
    write_jsonl(data_dir / "nodes_final.jsonl", nodes)
    write_jsonl(data_dir / "relations_final.jsonl", relations)
    write_csv(
        foundation_dir / "foundation_scope_taxonomy.csv",
        [
            "specialty_code",
            "specialty_name",
            "category_code",
            "category_name",
            "subcategory_code",
            "subcategory_name",
            "disease_code",
            "disease_name",
            "name_en",
            "aliases",
            "inclusion_status",
            "inclusion_reason",
        ],
        taxonomy_rows,
    )
    write_csv(
        foundation_dir / "foundation_controlled_vocabulary.csv",
        ["canonical_name", "code", "name_en", "aliases", "entityType", "disease_scope", "source", "status"],
        vocabulary_rows,
    )
    write_csv(
        audit_dir / "foundation_coverage_audit.csv",
        ["disease_code", "disease_name", "pathway_element", "coverage_status", "source", "note"],
        coverage_rows,
    )

    entity_counts = Counter(row["entityType"] for row in nodes)
    relation_counts = Counter(row["relationType"] for row in relations)
    covered_count = sum(row["coverage_status"] == "covered" for row in coverage_rows)
    summary = {
        "status": "foundation_skeleton_built",
        "schema_version": SCHEMA_VERSION,
        "specialty": "心血管内科",
        "source_document": PRIMARY_SOURCE_NAME,
        "source_document_id": PRIMARY_DOCUMENT_ID,
        "cardiology_line_start": CARDIOLOGY_LINE_START,
        "cardiology_line_end": CARDIOLOGY_LINE_END,
        "category_count": len(TAXONOMY),
        "disease_count": len(taxonomy_rows),
        "node_count": len(nodes),
        "relation_count": len(relations),
        "evidence_count": len(evidence_rows),
        "entity_type_counts": dict(entity_counts),
        "relation_type_counts": dict(relation_counts),
        "coverage_item_count": len(coverage_rows),
        "covered_item_count": covered_count,
        "coverage_rate": round(covered_count / len(coverage_rows), 6) if coverage_rows else 0,
        "quality_note": "第一版骨架库已完成疾病三层目录和教材证据锚定；pending_deep_extraction 项需在下一轮语义抽取中实体化为症状、体征、检查、治疗等节点。",
    }
    (audit_dir / "foundation_quality_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    (foundation_dir / "foundation_quality_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cardiology foundation skeleton from parsed textbook text.")
    parser.add_argument("--foundation-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_foundation(args.foundation_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
