from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


CAD_DISEASES = (
    ("DIS-CARD-CAD-ACS", "急性冠脉综合征", "Acute coronary syndrome", "ACS", "急性冠状动脉综合征,冠脉综合征", "SUB-CARD-CAD-ACS"),
    ("DIS-CARD-CAD-UA", "不稳定型心绞痛", "Unstable angina", "UA", "不稳定心绞痛", "SUB-CARD-CAD-ACS"),
    ("DIS-CARD-CAD-AMI", "急性心肌梗死", "Acute myocardial infarction", "AMI", "心梗,心肌梗死,急性心梗", "SUB-CARD-CAD-ACS"),
    ("DIS-CARD-CAD-STEMI", "ST段抬高型心肌梗死", "ST-segment elevation myocardial infarction", "STEMI", "ST抬高心梗,ST段抬高性心肌梗死,ST段抬高心肌梗死", "SUB-CARD-CAD-ACS"),
    ("DIS-CARD-CAD-NSTEMI", "非ST段抬高型心肌梗死", "Non-ST-segment elevation myocardial infarction", "NSTEMI", "非ST抬高心梗,非ST段抬高性心肌梗死,非ST段抬高心肌梗死,NSTE-ACS", "SUB-CARD-CAD-ACS"),
    ("DIS-CARD-CAD-CCS", "慢性冠脉综合征", "Chronic coronary syndrome", "CCS", "慢性冠脉疾病,慢性冠状动脉综合征,慢性冠状动脉疾病,CCD", "SUB-CARD-CAD-CHRONIC"),
    ("DIS-CARD-CAD-STABLE-ANGINA", "稳定型心绞痛", "Stable angina", "", "稳定性心绞痛,稳定性冠心病", "SUB-CARD-CAD-CHRONIC"),
    ("DIS-CARD-CAD-SILENT-ISCHEMIA", "隐匿性冠心病", "Silent myocardial ischemia", "", "无症状心肌缺血,无症状性心肌缺血", "SUB-CARD-CAD-CHRONIC"),
    ("DIS-CARD-CAD-OLD-MI", "陈旧性心肌梗死", "Old myocardial infarction", "", "既往心肌梗死,陈旧性心梗", "SUB-CARD-CAD-CHRONIC"),
    ("DIS-CARD-CAD-ICM", "缺血性心肌病", "Ischemic cardiomyopathy", "ICM", "缺血性心肌病变", "SUB-CARD-CAD-CHRONIC"),
)


VOCABULARY = (
    ("胸痛", "", "", "胸骨后疼痛,压榨性疼痛,缺血性胸痛", "Symptom", "ALL"),
    ("胸闷", "", "", "胸部压迫感,胸部紧缩感", "Symptom", "ALL"),
    ("放射痛", "", "", "左肩放射痛,左臂放射痛,颈部放射痛,下颌放射痛,背部放射痛", "Symptom", "ALL"),
    ("呼吸困难", "", "", "气短, dyspnea", "Symptom", "ALL"),
    ("出汗", "", "", "大汗,冷汗", "Symptom", "ALL"),
    ("恶心呕吐", "", "", "恶心,呕吐", "Symptom", "ALL"),
    ("濒死感", "", "", "濒死感觉", "Symptom", "ALL"),
    ("乏力", "", "", "疲乏", "Symptom", "ALL"),
    ("晕厥", "", "", "一过性意识丧失,黑矇,黑蒙", "Symptom", "ALL"),
    ("心悸", "", "", "", "Symptom", "ALL"),
    ("上腹痛", "", "", "上腹部疼痛,腹痛", "Symptom", "ALL"),
    ("低血压", "", "", "血压下降", "Sign", "ALL"),
    ("肺部啰音", "", "", "肺部湿啰音,湿啰音,肺啰音", "Sign", "ALL"),
    ("心动过速", "", "", "心率增快,心率快", "Sign", "ALL"),
    ("心音低钝", "", "", "心音减弱", "Sign", "ALL"),
    ("颈静脉怒张", "", "", "", "Sign", "ALL"),
    ("皮肤湿冷", "", "", "四肢湿冷,冷汗", "Sign", "ALL"),
    ("心脏杂音", "", "", "新发杂音,收缩期杂音", "Sign", "ALL"),
    ("第三心音", "", "S3", "", "Sign", "ALL"),
    ("心电图", "Electrocardiogram", "ECG", "十二导联心电图,12导联心电图", "Exam", "ALL"),
    ("动态心电图", "Holter monitoring", "Holter", "Holter心电图", "Exam", "ALL"),
    ("冠状动脉造影", "Coronary angiography", "CAG", "冠脉造影,冠状动脉血管造影", "Exam", "ALL"),
    ("冠状动脉CT血管成像", "Coronary CT angiography", "CCTA", "冠脉CTA,冠状动脉CTA,CTA", "Exam", "ALL"),
    ("运动负荷试验", "Exercise stress testing", "", "负荷试验,运动试验", "Exam", "ALL"),
    ("心肌肌钙蛋白", "Cardiac troponin", "cTn", "肌钙蛋白,心肌肌钙蛋白I,心肌肌钙蛋白T,cTnI,cTnT,hs-cTn", "LabTest", "ALL"),
    ("肌酸激酶同工酶", "Creatine kinase-MB", "CK-MB", "CKMB,肌酸激酶MB", "LabTest", "ALL"),
    ("低密度脂蛋白胆固醇", "Low-density lipoprotein cholesterol", "LDL-C", "LDL胆固醇,低密度脂蛋白", "LabTest", "ALL"),
    ("经皮冠状动脉介入治疗", "Percutaneous coronary intervention", "PCI", "冠脉介入,介入治疗,支架植入,球囊扩张,PTCA", "Procedure", "ALL"),
    ("冠状动脉旁路移植术", "Coronary artery bypass grafting", "CABG", "冠脉搭桥,搭桥手术,心脏搭桥", "Procedure", "ALL"),
    ("溶栓治疗", "Fibrinolytic therapy", "", "静脉溶栓,纤溶治疗", "Procedure", "ALL"),
    ("再灌注治疗", "Reperfusion therapy", "", "血运重建,早期再灌注", "TreatmentPlan", "ALL"),
    ("抗血小板治疗", "Antiplatelet therapy", "", "双联抗血小板治疗,DAPT", "TreatmentPlan", "ALL"),
    ("阿司匹林", "Aspirin", "ASA", "乙酰水杨酸,拜阿司匹灵", "Medication", "ALL"),
    ("P2Y12受体抑制剂", "P2Y12 inhibitor", "", "P2Y12抑制剂", "Medication", "ALL"),
    ("氯吡格雷", "Clopidogrel", "", "波立维,泰嘉,clopidogrel", "Medication", "ALL"),
    ("替格瑞洛", "Ticagrelor", "", "倍林达,ticagrelor", "Medication", "ALL"),
    ("普拉格雷", "Prasugrel", "", "prasugrel", "Medication", "ALL"),
    ("他汀类药物", "Statin", "", "他汀,高强度他汀", "Medication", "ALL"),
    ("阿托伐他汀", "Atorvastatin", "", "立普妥,atorvastatin", "Medication", "ALL"),
    ("瑞舒伐他汀", "Rosuvastatin", "", "rosuvastatin", "Medication", "ALL"),
    ("β受体拮抗剂", "Beta blocker", "", "β受体阻滞剂,beta blocker", "Medication", "ALL"),
    ("美托洛尔", "Metoprolol", "", "倍他乐克,metoprolol", "Medication", "ALL"),
    ("比索洛尔", "Bisoprolol", "", "bisoprolol", "Medication", "ALL"),
    ("硝酸酯类药物", "Nitrates", "", "硝酸酯,nitrates", "Medication", "ALL"),
    ("硝酸甘油", "Nitroglycerin", "", "nitroglycerin", "Medication", "ALL"),
    ("单硝酸异山梨酯", "Isosorbide mononitrate", "", "isosorbide mononitrate", "Medication", "ALL"),
    ("血管紧张素转换酶抑制剂", "Angiotensin-converting enzyme inhibitor", "ACEI", "ACE抑制剂,普利类药物", "Medication", "ALL"),
    ("血管紧张素Ⅱ受体阻滞剂", "Angiotensin II receptor blocker", "ARB", "血管紧张素受体阻滞剂,沙坦类药物", "Medication", "ALL"),
    ("高血压", "Hypertension", "", "", "RiskFactor", "ALL"),
    ("糖尿病", "Diabetes mellitus", "", "", "RiskFactor", "ALL"),
    ("吸烟", "Smoking", "", "烟草使用", "RiskFactor", "ALL"),
    ("血脂异常", "Dyslipidemia", "", "高脂血症,脂代谢异常", "RiskFactor", "ALL"),
    ("肥胖", "Obesity", "", "", "RiskFactor", "ALL"),
    ("冠心病家族史", "Family history of coronary heart disease", "", "早发冠心病家族史,家族史", "RiskFactor", "ALL"),
    ("冠状动脉痉挛", "Coronary artery spasm", "", "冠脉痉挛", "DifferentialDiagnosis", "ALL"),
    ("主动脉夹层", "Aortic dissection", "", "", "DifferentialDiagnosis", "ALL"),
    ("肺栓塞", "Pulmonary embolism", "", "", "DifferentialDiagnosis", "ALL"),
    ("急性心包炎", "Acute pericarditis", "", "心包炎", "DifferentialDiagnosis", "ALL"),
    ("GRACE评分", "GRACE risk score", "GRACE", "全球急性冠状动脉事件注册评分", "RiskStratification", "ALL"),
    ("TIMI评分", "TIMI risk score", "TIMI", "TIMI风险评分", "RiskStratification", "ALL"),
    ("心力衰竭", "Heart failure", "HF", "心衰", "Complication", "ALL"),
    ("心律失常", "Arrhythmia", "", "室性心律失常,房颤", "Complication", "ALL"),
    ("心源性休克", "Cardiogenic shock", "", "休克", "Complication", "ALL"),
    ("心脏性猝死", "Sudden cardiac death", "SCD", "猝死", "Complication", "ALL"),
    ("ST段抬高", "ST-segment elevation", "", "ST抬高", "ExamIndicator", "ALL"),
    ("ST段压低", "ST-segment depression", "", "ST压低", "ExamIndicator", "ALL"),
    ("发病时间", "Symptom onset time", "", "起病时间,胸痛时间,症状发作时间", "ExamIndicator", "ALL"),
    ("左心室射血分数", "Left ventricular ejection fraction", "LVEF", "射血分数", "ExamIndicator", "ALL"),
)


PATHWAY_RULES = (
    ("definition", r"是指|定义为|是一类|属于"),
    ("etiology", r"危险因素|病因|动脉粥样硬化|斑块|血栓"),
    ("epidemiology", r"发病率|患病率|流行病学"),
    ("symptom_sign", r"胸痛|胸闷|呼吸困难|出汗|症状|体征|临床表现"),
    ("exam", r"心电图|肌钙蛋白|冠状动脉造影|冠脉造影|CTA|检查|标志物"),
    ("diagnosis_criteria", r"诊断|诊断标准|鉴别诊断|排除"),
    ("risk_stratification", r"危险分层|风险评估|GRACE|TIMI|高危|极高危"),
    ("treatment_plan", r"治疗|再灌注|PCI|CABG|溶栓|抗血小板|他汀|用药"),
    ("complication", r"并发症|心力衰竭|心律失常|休克|猝死"),
    ("prognosis", r"预后|死亡率|死亡|复发|再发"),
    ("follow_up", r"随访|复查|二级预防|长期管理"),
)


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _paragraphs(text: str) -> list[tuple[int, str]]:
    page_pattern = re.compile(r"<<<PAGE page=(\d+) class=([^>]+)>>>(.*?)(?=<<<PAGE page=|\Z)", re.S)
    paragraphs: list[tuple[int, str]] = []
    for page_match in page_pattern.finditer(text):
        page = int(page_match.group(1))
        body = re.sub(r"<<<SECTION[^>]+>>>", "", page_match.group(3))
        for raw in re.split(r"\n\s*\n", body):
            paragraph = re.sub(r"\s*\n\s*", " ", raw).strip()
            if len(paragraph) >= 8:
                paragraphs.append((page, paragraph[:1200]))
    return paragraphs


def _is_navigation_like(paragraph: str) -> bool:
    """Exclude table-of-contents/index lines that contain disease names but no clinical assertion."""
    text = paragraph.strip()
    lower = text.lower()
    dot_leaders = len(re.findall(r"(?:\.\s*){3,}", text))
    spaced_dot_runs = len(re.findall(r"\.\s+\.\s+\.", text))
    chapter_or_section = bool(
        re.search(r"第[一二三四五六七八九十百]+[章节篇]|contents|table of contents|index", lower, re.IGNORECASE)
    )
    page_refs = len(re.findall(r"\b(?:e?\d{2,4})\b", text, re.IGNORECASE))
    return (chapter_or_section and (dot_leaders or spaced_dot_runs or page_refs >= 3)) or (
        spaced_dot_runs >= 3 and page_refs >= 2
    )


def _pathway(text: str) -> str:
    for element, pattern in PATHWAY_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return element
    return "clinical_knowledge"


def _disease_matches(text: str) -> list[tuple[str, str]]:
    matches = []
    for code, name, name_en, abbr, aliases, _subcategory in CAD_DISEASES:
        terms = [name, name_en, abbr, *aliases.split(",")]
        for term in (item for item in terms if item):
            if term.isascii() and len(term) <= 8:
                hit = re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, re.IGNORECASE)
            else:
                hit = re.search(re.escape(term), text, re.IGNORECASE)
            if hit:
                matches.append((code, name))
                break
    return matches


def build_foundation(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir).resolve()
    config_path = batch_dir / "00_scope_and_config" / "batch_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
    batch_id = config.get("batch_id", "BATCH-UNKNOWN")

    taxonomy_rows = [
        {
            "specialty_code": "SPEC-CARD",
            "category_code": "",
            "subcategory_code": "",
            "disease_code": "",
            "name": "心血管内科",
            "name_en": "Cardiology",
            "aliases": "",
            "inclusion_status": "included",
            "inclusion_reason": "USER_CONFIRMED_SPECIALTY",
        },
        {
            "specialty_code": "SPEC-CARD",
            "category_code": "CAT-CARD-CAD",
            "subcategory_code": "",
            "disease_code": "",
            "name": "冠状动脉粥样硬化性心脏病",
            "name_en": "Coronary artery disease",
            "aliases": "冠心病,CAD,CHD,冠状动脉疾病",
            "inclusion_status": "included",
            "inclusion_reason": "USER_CONFIRMED_CATEGORY",
        },
        {
            "specialty_code": "SPEC-CARD",
            "category_code": "CAT-CARD-CAD",
            "subcategory_code": "SUB-CARD-CAD-ACS",
            "disease_code": "",
            "name": "急性冠脉综合征谱系",
            "name_en": "Acute coronary syndrome spectrum",
            "aliases": "ACS谱系",
            "inclusion_status": "included",
            "inclusion_reason": "USER_CONFIRMED_SUBCATEGORY",
        },
        {
            "specialty_code": "SPEC-CARD",
            "category_code": "CAT-CARD-CAD",
            "subcategory_code": "SUB-CARD-CAD-CHRONIC",
            "disease_code": "",
            "name": "慢性冠脉疾病谱系",
            "name_en": "Chronic coronary disease spectrum",
            "aliases": "CCS谱系,CCD谱系",
            "inclusion_status": "included",
            "inclusion_reason": "USER_CONFIRMED_SUBCATEGORY",
        },
    ]
    for code, name, name_en, abbr, aliases, subcategory in CAD_DISEASES:
        taxonomy_rows.append(
            {
                "specialty_code": "SPEC-CARD",
                "category_code": "CAT-CARD-CAD",
                "subcategory_code": subcategory,
                "disease_code": code,
                "name": name,
                "name_en": name_en,
                "aliases": ",".join(item for item in (abbr, aliases) if item),
                "inclusion_status": "included",
                "inclusion_reason": "USER_CONFIRMED_DISEASE",
            }
        )
    taxonomy_fields = (
        "specialty_code",
        "category_code",
        "subcategory_code",
        "disease_code",
        "name",
        "name_en",
        "aliases",
        "inclusion_status",
        "inclusion_reason",
    )
    _write_csv(batch_dir / "00_scope_and_config" / "scope_taxonomy.csv", taxonomy_fields, taxonomy_rows)

    vocabulary_rows = []
    for code, name, name_en, abbr, aliases, _subcategory in CAD_DISEASES:
        vocabulary_rows.append(
            {
                "canonical_name": name,
                "name_en": name_en,
                "abbr": abbr,
                "aliases": aliases,
                "entityType": "Disease",
                "disease_scope": code,
                "source": "冠心病批次目录",
            }
        )
    for canonical_name, name_en, abbr, aliases, entity_type, disease_scope in VOCABULARY:
        vocabulary_rows.append(
            {
                "canonical_name": canonical_name,
                "name_en": name_en,
                "abbr": abbr,
                "aliases": aliases,
                "entityType": entity_type,
                "disease_scope": disease_scope,
                "source": "冠心病批次受控词表",
            }
        )
    vocabulary_fields = ("canonical_name", "name_en", "abbr", "aliases", "entityType", "disease_scope", "source")
    _write_csv(batch_dir / "00_scope_and_config" / "controlled_vocabulary.csv", vocabulary_fields, vocabulary_rows)

    manifest_path = batch_dir / "01_source_manifest" / "source_documents_manifest.csv"
    manifest = _load_csv(manifest_path) if manifest_path.is_file() else []
    textbook_docs = [
        row
        for row in manifest
        if row.get("inclusion_status") == "included"
        and row.get("extension", "").lower() == ".pdf"
        and row.get("source_type") == "authoritative_textbook"
    ]
    evidence_rows = []
    for document in textbook_docs:
        clean_path = batch_dir / "03_clean_text" / f'{document["document_id"]}.clean.txt'
        if not clean_path.is_file():
            continue
        ordinal = 0
        for page, paragraph in _paragraphs(clean_path.read_text(encoding="utf-8-sig")):
            if _is_navigation_like(paragraph):
                continue
            matches = _disease_matches(paragraph)
            if not matches:
                continue
            for disease_code, disease_name in matches:
                ordinal += 1
                content_hash = hashlib.sha256(paragraph.encode("utf-8")).hexdigest().upper()
                evidence_rows.append(
                    {
                        "document_id": document["document_id"],
                        "segment_id": f'SEG-{document["document_id"]}-{page}-TB-{ordinal:05d}-{disease_code.split("-")[-1]}',
                        "source_name": document["file_name"],
                        "source_type": "authoritative_textbook",
                        "source_section": "冠心病基础教材证据",
                        "source_page": page,
                        "disease_code": disease_code,
                        "disease_name": disease_name,
                        "pathway_element": _pathway(paragraph),
                        "evidence_text": paragraph,
                        "content_hash": content_hash,
                        "recommendation_class": "N/A",
                        "evidence_level": "N/A",
                        "review_status": "approved",
                    }
                )
    evidence_path = batch_dir / "03_clean_text" / "textbook_evidence_index.jsonl"
    with evidence_path.open("w", encoding="utf-8-sig", newline="\n") as handle:
        for row in evidence_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "batch_id": batch_id,
        "disease_count": len(CAD_DISEASES),
        "vocabulary_count": len(vocabulary_rows),
        "textbook_evidence_count": len(evidence_rows),
    }
    (batch_dir / "04_evidence_and_extraction").mkdir(parents=True, exist_ok=True)
    (batch_dir / "04_evidence_and_extraction" / "coronary_foundation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build coronary artery disease scope and textbook evidence index.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_foundation(args.batch_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
