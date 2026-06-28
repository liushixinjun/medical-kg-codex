from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


DISEASES = (
    ("DIS-CARD-CM-HCM", "肥厚型心肌病", "Hypertrophic cardiomyopathy", "HCM", "肥厚性心肌病", "SUB-CARD-CM-PHENOTYPE"),
    ("DIS-CARD-CM-DCM", "扩张型心肌病", "Dilated cardiomyopathy", "DCM", "充血型心肌病", "SUB-CARD-CM-PHENOTYPE"),
    ("DIS-CARD-CM-NDLVCM", "非扩张型左心室心肌病", "Non-dilated left ventricular cardiomyopathy", "NDLVCM", "非扩张型左室心肌病", "SUB-CARD-CM-PHENOTYPE"),
    ("DIS-CARD-CM-ACM", "致心律失常性心肌病", "Arrhythmogenic cardiomyopathy", "ACM", "心律失常相关心肌病", "SUB-CARD-CM-ARRHYTHMIC"),
    ("DIS-CARD-CM-ARVC", "致心律失常性右心室心肌病", "Arrhythmogenic right ventricular cardiomyopathy", "ARVC", "右心室发育不良型心肌病", "SUB-CARD-CM-ARRHYTHMIC"),
    ("DIS-CARD-CM-ALVC", "致心律失常性左心室心肌病", "Arrhythmogenic left ventricular cardiomyopathy", "ALVC", "", "SUB-CARD-CM-ARRHYTHMIC"),
    ("DIS-CARD-CM-ABVC", "致心律失常性双心室心肌病", "Arrhythmogenic biventricular cardiomyopathy", "ABVC", "", "SUB-CARD-CM-ARRHYTHMIC"),
    ("DIS-CARD-CM-RCM", "限制型心肌病", "Restrictive cardiomyopathy", "RCM", "", "SUB-CARD-CM-PHENOTYPE"),
    ("DIS-CARD-CM-ATRIAL", "心房心肌病", "Atrial cardiomyopathy", "AtCM", "", "SUB-CARD-CM-ATRIAL"),
    ("DIS-CARD-CM-FABRY", "法布雷病心肌病", "Fabry cardiomyopathy", "", "Fabry病心肌病", "SUB-CARD-CM-SPECIAL"),
    ("DIS-CARD-CM-AMYLOID", "淀粉样变心肌病", "Amyloid cardiomyopathy", "", "心脏淀粉样变,ATTR-CM,AL-CM", "SUB-CARD-CM-SPECIAL"),
    ("DIS-CARD-CM-ICM", "缺血性心肌病", "Ischemic cardiomyopathy", "ICM", "", "SUB-CARD-CM-SPECIAL"),
)

TEXTBOOK_HEADINGS = (
    (re.compile(r"肥厚型心肌病"), "DIS-CARD-CM-HCM", "肥厚型心肌病"),
    (re.compile(r"扩张型心肌病"), "DIS-CARD-CM-DCM", "扩张型心肌病"),
    (re.compile(r"非扩张型左心室心肌病"), "DIS-CARD-CM-NDLVCM", "非扩张型左心室心肌病"),
    (re.compile(r"致心律失常性右心室心肌病"), "DIS-CARD-CM-ARVC", "致心律失常性右心室心肌病"),
    (re.compile(r"限制型心肌病"), "DIS-CARD-CM-RCM", "限制型心肌病"),
)

VOCABULARY = (
    ("劳力性呼吸困难", "", "", "劳力性气短,活动后呼吸困难,活动后气短", "Symptom", "ALL"),
    ("静息性呼吸困难", "", "", "静息呼吸困难,静息性气短,静息气短", "Symptom", "ALL"),
    ("夜间阵发性呼吸困难", "", "PND", "夜间阵发呼吸困难", "Symptom", "ALL"),
    ("端坐呼吸", "", "", "", "Symptom", "ALL"),
    ("胸痛", "", "", "心前区疼痛,胸部疼痛", "Symptom", "ALL"),
    ("胸闷", "", "", "胸部闷痛,胸闷痛,劳力性胸闷痛", "Symptom", "ALL"),
    ("晕厥", "", "", "一过性意识丧失", "Symptom", "ALL"),
    ("黑矇", "", "", "黑蒙,眼前发黑", "Symptom", "ALL"),
    ("心悸", "", "", "", "Symptom", "ALL"),
    ("乏力", "", "", "疲乏", "Symptom", "ALL"),
    ("头晕", "", "", "眩晕", "Symptom", "ALL"),
    ("耐力下降", "", "", "运动耐量下降,活动耐量下降", "Symptom", "ALL"),
    ("水肿", "", "", "下肢水肿,外周水肿", "Sign", "ALL"),
    ("心脏扩大", "", "", "心界扩大,心腔扩大", "Sign", "ALL"),
    ("心脏杂音", "", "", "收缩期杂音,胸骨左缘收缩期喷射性杂音,心尖部收缩期吹风样杂音", "Sign", "ALL"),
    ("第三心音", "", "S3", "", "Sign", "ALL"),
    ("第四心音", "", "S4", "", "Sign", "ALL"),
    ("奔马律", "", "", "", "Sign", "ALL"),
    ("心音减弱", "", "", "心音低钝", "Sign", "ALL"),
    ("低血压", "", "", "持续顽固低血压", "Sign", "ALL"),
    ("肺淤血", "", "", "肺充血", "Sign", "ALL"),
    ("肺水肿", "", "", "", "Sign", "ALL"),
    ("胸腔积液", "", "", "", "Sign", "ALL"),
    ("家族史", "Family history", "", "家族性发病,家族遗传史", "RiskFactor", "ALL"),
    ("基因突变", "Genetic mutation", "", "遗传因素,致病基因,致病变异,基因变异", "RiskFactor", "ALL"),
    ("病毒感染", "Viral infection", "", "病毒性心肌炎", "RiskFactor", "DCM"),
    ("自身免疫", "Autoimmunity", "", "免疫反应,自身免疫反应", "RiskFactor", "DCM"),
    ("酒精暴露", "Alcohol exposure", "", "饮酒,嗜酒,酒精", "RiskFactor", "DCM"),
    ("心肌毒性药物暴露", "Cardiotoxic drug exposure", "", "心肌毒物,蒽环类药物,化疗药物", "RiskFactor", "DCM"),
    ("高血压性心脏病", "Hypertensive heart disease", "", "高血压心脏病", "DifferentialDiagnosis", "ALL"),
    ("冠心病", "Coronary heart disease", "CHD", "冠状动脉疾病,冠状动脉粥样硬化性心脏病", "DifferentialDiagnosis", "ALL"),
    ("心肌炎", "Myocarditis", "", "炎症性心肌病", "DifferentialDiagnosis", "ALL"),
    ("瓣膜性心脏病", "Valvular heart disease", "", "瓣膜病", "DifferentialDiagnosis", "ALL"),
    ("心电图", "Electrocardiography", "ECG", "12导联心电图", "Exam", "ALL"),
    ("动态心电图", "Holter monitoring", "Holter", "动态心电监测", "Exam", "ALL"),
    ("超声心动图", "Echocardiography", "TTE", "经胸超声心动图", "Exam", "ALL"),
    ("心脏磁共振成像", "Cardiac magnetic resonance", "CMR", "心脏磁共振,MRI", "Exam", "ALL"),
    ("心内膜心肌活检", "Endomyocardial biopsy", "EMB", "心肌活检", "Exam", "ALL"),
    ("基因检测", "Genetic testing", "", "遗传检测", "Exam", "ALL"),
    ("冠状动脉造影", "Coronary angiography", "CAG", "冠脉造影", "Exam", "ALL"),
    ("左心室射血分数", "Left ventricular ejection fraction", "LVEF", "左室射血分数,射血分数", "ExamIndicator", "ALL"),
    ("左室流出道压差", "Left ventricular outflow tract gradient", "LVOT压差", "LVOT梗阻压差", "ExamIndicator", "HCM"),
    ("最大室壁厚度", "Maximum wall thickness", "", "室壁厚度", "ExamIndicator", "HCM"),
    ("钆延迟增强", "Late gadolinium enhancement", "LGE", "延迟钆增强", "ExamIndicator", "ALL"),
    ("N末端B型利钠肽原", "N-terminal pro-B-type natriuretic peptide", "NT-proBNP", "NT-proBNP", "ExamIndicator", "ALL"),
    ("肌钙蛋白", "Cardiac troponin", "cTn", "cTnI,cTnT", "ExamIndicator", "ALL"),
    ("β受体拮抗剂", "Beta blocker", "", "β受体阻滞剂", "Medication", "ALL"),
    ("非二氢吡啶类钙通道阻滞剂", "Non-dihydropyridine calcium channel blocker", "", "维拉帕米,地尔硫䓬", "Medication", "HCM,RCM"),
    ("利尿剂", "Diuretic", "", "", "Medication", "ALL"),
    ("胺碘酮", "Amiodarone", "", "", "Medication", "ALL"),
    ("抗凝治疗", "Anticoagulation", "", "抗凝药物", "TreatmentPlan", "ALL"),
    ("室间隔切除术", "Septal myectomy", "", "Morrow手术,外科室间隔减容术", "Procedure", "HCM"),
    ("酒精室间隔消融术", "Alcohol septal ablation", "ASA", "TASH,室间隔消融", "Procedure", "HCM"),
    ("埋藏式心脏复律除颤器", "Implantable cardioverter defibrillator", "ICD", "植入式心律转复除颤器", "Procedure", "ALL"),
    ("心脏移植", "Heart transplantation", "", "心脏移植术", "Procedure", "ALL"),
    ("心力衰竭", "Heart failure", "HF", "心衰", "Complication", "ALL"),
    ("心房颤动", "Atrial fibrillation", "AF", "房颤", "Complication", "ALL"),
    ("心脏性猝死", "Sudden cardiac death", "SCD", "猝死", "Complication", "ALL"),
    ("血栓栓塞", "Thromboembolism", "", "栓塞", "Complication", "ALL"),
)


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _pathway_element(text: str, previous: str) -> str:
    mapping = (
        ("病因", "etiology"),
        ("发病机制", "pathophysiology"),
        ("临床表现", "symptom_sign"),
        ("辅助检查", "exam"),
        ("检查", "exam"),
        ("诊断与鉴别诊断", "diagnosis_criteria"),
        ("诊断", "diagnosis_criteria"),
        ("治疗", "treatment_plan"),
        ("预后", "prognosis"),
    )
    for marker, value in mapping:
        if f"【{marker}】" in text:
            return value
    return previous


def build_foundation(
    *, batch_dir: Path, textbook_document_id: str, textbook_start_page: int, textbook_end_page: int
) -> dict:
    batch_dir = Path(batch_dir).resolve()
    clean_path = batch_dir / "03_clean_text" / f"{textbook_document_id}.clean.txt"
    text = clean_path.read_text(encoding="utf-8-sig")

    taxonomy_rows = [
        {"specialty_code": "SPEC-CARD", "category_code": "", "subcategory_code": "", "disease_code": "", "name": "心血管内科", "name_en": "Cardiology", "aliases": "心内科", "inclusion_status": "included", "inclusion_reason": "USER_CONFIRMED_SPECIALTY"},
        {"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CM", "subcategory_code": "", "disease_code": "", "name": "心肌病", "name_en": "Cardiomyopathies", "aliases": "心肌疾病", "inclusion_status": "included", "inclusion_reason": "USER_CONFIRMED_CATEGORY"},
    ]
    subcategories = (
        ("SUB-CARD-CM-PHENOTYPE", "心室表型心肌病"),
        ("SUB-CARD-CM-ARRHYTHMIC", "心律失常表型心肌病"),
        ("SUB-CARD-CM-ATRIAL", "心房心肌病"),
        ("SUB-CARD-CM-SPECIAL", "特殊病因及继发性心肌病"),
    )
    for code, name in subcategories:
        taxonomy_rows.append({"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CM", "subcategory_code": code, "disease_code": "", "name": name, "name_en": "", "aliases": "", "inclusion_status": "included", "inclusion_reason": "SOURCE_CLASSIFICATION_2025_GUIDELINE"})
    for code, name, name_en, abbr, aliases, subcategory in DISEASES:
        taxonomy_rows.append({"specialty_code": "SPEC-CARD", "category_code": "CAT-CARD-CM", "subcategory_code": subcategory, "disease_code": code, "name": name, "name_en": name_en, "aliases": ",".join(item for item in (abbr, aliases) if item), "inclusion_status": "included", "inclusion_reason": "AUTHORITATIVE_SOURCE_SCOPE"})
    _write_csv(batch_dir / "00_scope_and_config" / "scope_taxonomy.csv", ("specialty_code", "category_code", "subcategory_code", "disease_code", "name", "name_en", "aliases", "inclusion_status", "inclusion_reason"), taxonomy_rows)

    vocab_rows = []
    for code, name, name_en, abbr, aliases, _ in DISEASES:
        vocab_rows.append({"canonical_name": name, "name_en": name_en, "abbr": abbr, "aliases": aliases, "entityType": "Disease", "disease_scope": code, "source": "2025指南/内科学第10版"})
    for canonical, name_en, abbr, aliases, entity_type, scope in VOCABULARY:
        vocab_rows.append({"canonical_name": canonical, "name_en": name_en, "abbr": abbr, "aliases": aliases, "entityType": entity_type, "disease_scope": scope, "source": "指南/教材受控初始化"})
    _write_csv(batch_dir / "00_scope_and_config" / "controlled_vocabulary.csv", ("canonical_name", "name_en", "abbr", "aliases", "entityType", "disease_scope", "source"), vocab_rows)

    page_pattern = re.compile(r"<<<PAGE page=(\d+) class=[^>]+>>>\s*<<<SECTION[^>]+>>>\s*(.*?)(?=<<<PAGE page=|\Z)", re.S)
    evidence_rows = []
    current_code = ""
    current_name = ""
    pathway = "definition"
    ordinal = 0
    stopped = False
    heading_pattern = re.compile(
        r"(第[一二三四五六]节\s*[|｜]?\s*(?:肥厚型心肌病|扩张型心肌病|非扩张型左心室心肌病|致心律失常性右心室心肌病|限制型心肌病|心肌炎))"
    )
    for match in page_pattern.finditer(text):
        page = int(match.group(1))
        if page < textbook_start_page or page > textbook_end_page or stopped:
            continue
        body = match.group(2).strip()
        tokens = heading_pattern.split(body)
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            if re.search(r"第六节\s*[|｜]?\s*心肌炎", token):
                stopped = True
                break
            for pattern, disease_code, disease_name in TEXTBOOK_HEADINGS:
                if pattern.search(token) and re.search(r"第[一二三四五]节", token):
                    current_code, current_name, pathway = disease_code, disease_name, "definition"
                    break
            else:
                if not current_code:
                    continue
                paragraphs = [
                    re.sub(r"\s*\n\s*", " ", part).strip()
                    for part in re.split(r"\n\s*\n", token)
                    if part.strip()
                ]
                for paragraph in paragraphs:
                    pathway = _pathway_element(paragraph, pathway)
                    ordinal += 1
                    segment_id = f"SEG-{textbook_document_id}-{page}-TB-{ordinal:05d}"
                    evidence_rows.append({"document_id": textbook_document_id, "segment_id": segment_id, "source_name": "《内科学》第10版", "source_type": "authoritative_textbook", "source_section": f"第三篇第六章/{current_name}", "source_page": page, "disease_code": current_code, "disease_name": current_name, "pathway_element": pathway, "evidence_text": paragraph, "content_hash": hashlib.sha256(paragraph.encode("utf-8")).hexdigest().upper(), "recommendation_class": "N/A", "evidence_level": "N/A", "review_status": "approved"})
                continue

    output = batch_dir / "03_clean_text" / "textbook_evidence_index.jsonl"
    with output.open("w", encoding="utf-8-sig", newline="\n") as handle:
        for row in evidence_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"textbook_segment_count": len(evidence_rows), "textbook_disease_count": len({row["disease_code"] for row in evidence_rows})}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cardiomyopathy scope and textbook evidence index.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--textbook-document-id", required=True)
    parser.add_argument("--start-page", type=int, required=True)
    parser.add_argument("--end-page", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(build_foundation(batch_dir=args.batch_dir, textbook_document_id=args.textbook_document_id, textbook_start_page=args.start_page, textbook_end_page=args.end_page), ensure_ascii=False))


if __name__ == "__main__":
    main()
