from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


VA_SCD_DISEASES = (
    (
        "DIS-CARD-ARR-VA",
        "室性心律失常",
        "Ventricular arrhythmia",
        "",
        "室性心律失常谱系,ventricular arrhythmias",
        "SUB-CARD-ARR-VA",
    ),
    (
        "DIS-CARD-ARR-PVC",
        "室性期前收缩",
        "Premature ventricular complex",
        "PVC",
        "室性早搏,室早,室性期前搏动,premature ventricular contraction",
        "SUB-CARD-ARR-VA",
    ),
    (
        "DIS-CARD-ARR-NSVT",
        "非持续性室性心动过速",
        "Non-sustained ventricular tachycardia",
        "NSVT",
        "非持续性室速,短阵室速,non-sustained VT",
        "SUB-CARD-ARR-VA",
    ),
    (
        "DIS-CARD-ARR-VT",
        "持续性室性心动过速",
        "Sustained ventricular tachycardia",
        "VT",
        "室性心动过速,室速,持续性室速,ventricular tachycardia",
        "SUB-CARD-ARR-VA",
    ),
    (
        "DIS-CARD-ARR-TDP",
        "尖端扭转型室性心动过速",
        "Torsades de pointes",
        "TdP",
        "尖端扭转型室速,尖端扭转,多形性室性心动过速,torsades",
        "SUB-CARD-ARR-VA",
    ),
    (
        "DIS-CARD-ARR-VF",
        "心室扑动与心室颤动",
        "Ventricular flutter and ventricular fibrillation",
        "VF",
        "心室颤动,室颤,心室扑动,室扑,ventricular fibrillation,ventricular flutter",
        "SUB-CARD-ARR-VA",
    ),
    (
        "DIS-CARD-SCD-SUDDEN",
        "心脏性猝死",
        "Sudden cardiac death",
        "SCD",
        "心源性猝死,猝死,sudden cardiac death",
        "SUB-CARD-ARR-SCD",
    ),
    (
        "DIS-CARD-SCD-ARREST",
        "心脏骤停",
        "Cardiac arrest",
        "CA",
        "心搏骤停,循环骤停,cardiac arrest",
        "SUB-CARD-ARR-SCD",
    ),
    (
        "DIS-CARD-ARR-LQTS",
        "长QT间期综合征",
        "Long QT syndrome",
        "LQTS",
        "长QT综合征,QT间期延长,long-QT syndrome",
        "SUB-CARD-ARR-INHERITED",
    ),
    (
        "DIS-CARD-ARR-SQTS",
        "短QT间期综合征",
        "Short QT syndrome",
        "SQTS",
        "短QT综合征,QT间期缩短,short-QT syndrome",
        "SUB-CARD-ARR-INHERITED",
    ),
    (
        "DIS-CARD-ARR-BRUGADA",
        "Brugada综合征",
        "Brugada syndrome",
        "Brugada",
        "布鲁加达综合征,Brugada pattern,1型Brugada心电图",
        "SUB-CARD-ARR-INHERITED",
    ),
    (
        "DIS-CARD-ARR-CPVT",
        "儿茶酚胺敏感性多形性室性心动过速",
        "Catecholaminergic polymorphic ventricular tachycardia",
        "CPVT",
        "儿茶酚胺敏感性室速,儿茶酚胺敏感性室性心动过速",
        "SUB-CARD-ARR-INHERITED",
    ),
)


VOCABULARY = (
    ("心悸", "", "", "心慌,palpitation,palpitations", "Symptom", "ALL"),
    ("晕厥", "Syncope", "", "黑朦,黑蒙,一过性意识丧失", "Symptom", "ALL"),
    ("头晕", "Dizziness", "", "眩晕", "Symptom", "ALL"),
    ("胸闷", "", "", "胸部不适", "Symptom", "ALL"),
    ("胸痛", "", "", "", "Symptom", "ALL"),
    ("呼吸困难", "Dyspnea", "", "气短", "Symptom", "ALL"),
    ("乏力", "", "", "疲乏", "Symptom", "ALL"),
    ("抽搐", "Convulsion", "", "癫痫样发作", "Symptom", "ALL"),
    ("心动过速", "Tachycardia", "", "心率增快,心率快", "Sign", "ALL"),
    ("脉搏不齐", "Irregular pulse", "", "脉律不齐", "Sign", "ALL"),
    ("低血压", "Hypotension", "", "血压下降", "Sign", "ALL"),
    ("意识丧失", "Loss of consciousness", "", "昏迷", "Sign", "ALL"),
    ("无脉搏", "Pulselessness", "", "大动脉搏动消失", "Sign", "ALL"),
    ("呼吸停止", "Apnea", "", "无自主呼吸", "Sign", "ALL"),
    ("皮肤湿冷", "", "", "冷汗,大汗", "Sign", "ALL"),
    ("器质性心脏病", "Structural heart disease", "", "结构性心脏病", "RiskFactor", "ALL"),
    ("冠心病", "Coronary heart disease", "CHD", "冠状动脉疾病,冠状动脉粥样硬化性心脏病", "RiskFactor", "ALL"),
    ("心肌病", "Cardiomyopathy", "", "", "RiskFactor", "ALL"),
    ("心力衰竭", "Heart failure", "HF", "心衰", "RiskFactor", "ALL"),
    ("急性心肌梗死", "Acute myocardial infarction", "AMI", "心梗,心肌梗死", "RiskFactor", "ALL"),
    ("左心室射血分数降低", "Reduced left ventricular ejection fraction", "reduced LVEF", "射血分数降低,LVEF降低", "RiskFactor", "ALL"),
    ("电解质紊乱", "Electrolyte disturbance", "", "", "RiskFactor", "ALL"),
    ("低钾血症", "Hypokalemia", "", "血钾降低", "RiskFactor", "ALL"),
    ("低镁血症", "Hypomagnesemia", "", "血镁降低", "RiskFactor", "ALL"),
    ("QT延长药物", "QT-prolonging drugs", "", "致QT延长药物", "RiskFactor", "ALL"),
    ("家族猝死史", "Family history of sudden cardiac death", "", "猝死家族史", "RiskFactor", "ALL"),
    ("遗传因素", "Genetic factor", "", "基因突变,致病基因变异", "RiskFactor", "ALL"),
    ("心电图", "Electrocardiogram", "ECG", "十二导联心电图,12导联心电图", "Exam", "ALL"),
    ("动态心电图", "Holter monitoring", "Holter", "Holter心电图,24小时动态心电图", "Exam", "ALL"),
    ("心脏电生理检查", "Electrophysiological study", "EPS", "电生理检查,心内电生理检查", "Exam", "ALL"),
    ("超声心动图", "Echocardiography", "TTE", "心脏超声", "Exam", "ALL"),
    ("心脏磁共振成像", "Cardiac magnetic resonance", "CMR", "心脏MRI", "Exam", "ALL"),
    ("冠状动脉造影", "Coronary angiography", "CAG", "冠脉造影", "Exam", "ALL"),
    ("基因检测", "Genetic testing", "", "基因筛查", "Exam", "ALL"),
    ("运动试验", "Exercise test", "", "运动负荷试验", "Exam", "ALL"),
    ("血钾", "Serum potassium", "K+", "钾离子,血清钾", "LabTest", "ALL"),
    ("血镁", "Serum magnesium", "Mg2+", "镁离子,血清镁", "LabTest", "ALL"),
    ("心肌肌钙蛋白", "Cardiac troponin", "cTn", "肌钙蛋白,cTnI,cTnT", "LabTest", "ALL"),
    ("宽QRS波心动过速", "Wide QRS complex tachycardia", "", "宽QRS心动过速", "ExamIndicator", "ALL"),
    ("室性早搏负荷", "PVC burden", "", "早搏负荷,PVC负荷", "ExamIndicator", "ALL"),
    ("QT间期", "QT interval", "QT", "", "ExamIndicator", "ALL"),
    ("校正QT间期", "Corrected QT interval", "QTc", "QTc间期", "ExamIndicator", "ALL"),
    ("J点抬高", "J-point elevation", "", "", "ExamIndicator", "ALL"),
    ("Brugada 1型心电图", "Type 1 Brugada ECG pattern", "", "1型Brugada,穹隆型ST段抬高", "ExamIndicator", "ALL"),
    ("R-on-T现象", "R-on-T phenomenon", "", "", "ExamIndicator", "ALL"),
    ("左心室射血分数", "Left ventricular ejection fraction", "LVEF", "射血分数", "ExamIndicator", "ALL"),
    ("猝死风险评估", "Sudden death risk assessment", "", "心脏性猝死风险评估,SCD风险评估", "RiskStratification", "ALL"),
    ("ICD适应证评估", "ICD indication assessment", "", "除颤器适应证评估", "RiskStratification", "ALL"),
    ("急救复苏", "Resuscitation", "", "复苏治疗", "TreatmentPlan", "ALL"),
    ("电复律除颤", "Cardioversion and defibrillation", "", "电复律,电除颤,除颤", "TreatmentPlan", "ALL"),
    ("抗心律失常药物治疗", "Antiarrhythmic drug therapy", "", "抗心律失常药物,抗心律失常治疗", "TreatmentPlan", "ALL"),
    ("射频消融治疗", "Radiofrequency catheter ablation", "", "导管消融治疗,消融治疗", "TreatmentPlan", "ALL"),
    ("ICD治疗", "Implantable cardioverter defibrillator therapy", "ICD", "除颤器治疗", "TreatmentPlan", "ALL"),
    ("诱因纠正", "Trigger correction", "", "纠正诱因,纠正电解质紊乱", "TreatmentPlan", "ALL"),
    ("抗心律失常药物", "Antiarrhythmic drugs", "", "抗心律失常药", "Medication", "ALL"),
    ("β受体阻滞剂", "Beta blocker", "", "β受体拮抗剂,beta blocker", "Medication", "ALL"),
    ("美托洛尔", "Metoprolol", "", "metoprolol", "Medication", "ALL"),
    ("比索洛尔", "Bisoprolol", "", "bisoprolol", "Medication", "ALL"),
    ("普萘洛尔", "Propranolol", "", "propranolol", "Medication", "ALL"),
    ("胺碘酮", "Amiodarone", "", "amiodarone", "Medication", "ALL"),
    ("利多卡因", "Lidocaine", "", "lidocaine", "Medication", "ALL"),
    ("索他洛尔", "Sotalol", "", "sotalol", "Medication", "ALL"),
    ("普罗帕酮", "Propafenone", "", "propafenone", "Medication", "ALL"),
    ("奎尼丁", "Quinidine", "", "quinidine", "Medication", "ALL"),
    ("硫酸镁", "Magnesium sulfate", "", "镁剂,magnesium", "Medication", "ALL"),
    ("钾剂", "Potassium supplement", "", "补钾", "Medication", "ALL"),
    ("氯化钾", "Potassium chloride", "", "potassium chloride,KCl", "Medication", "ALL"),
    ("心肺复苏", "Cardiopulmonary resuscitation", "CPR", "CPR", "Procedure", "ALL"),
    ("电除颤", "Defibrillation", "", "除颤,非同步电除颤", "Procedure", "ALL"),
    ("同步电复律", "Synchronized cardioversion", "", "电复律", "Procedure", "ALL"),
    ("导管消融", "Catheter ablation", "", "射频消融,射频导管消融", "Procedure", "ALL"),
    ("埋藏式心脏转复除颤器", "Implantable cardioverter defibrillator", "ICD", "植入型心律转复除颤器,植入式心律转复除颤器", "Procedure", "ALL"),
    ("可穿戴式除颤器", "Wearable cardioverter defibrillator", "WCD", "穿戴式除颤器", "Procedure", "ALL"),
    ("临时起搏", "Temporary pacing", "", "临时心脏起搏", "Procedure", "ALL"),
    ("室上性心动过速伴差异传导", "", "", "室上速伴差传", "DifferentialDiagnosis", "ALL"),
    ("预激综合征伴心房颤动", "", "", "预激伴房颤", "DifferentialDiagnosis", "ALL"),
    ("癫痫", "Epilepsy", "", "癫痫发作", "DifferentialDiagnosis", "ALL"),
    ("血管迷走性晕厥", "Vasovagal syncope", "", "", "DifferentialDiagnosis", "ALL"),
    ("心脏性猝死", "Sudden cardiac death", "SCD", "心源性猝死,猝死", "Complication", "ALL"),
    ("心脏骤停", "Cardiac arrest", "CA", "心搏骤停", "Complication", "ALL"),
    ("心源性休克", "Cardiogenic shock", "", "", "Complication", "ALL"),
    ("脑缺氧损伤", "Hypoxic brain injury", "", "", "Complication", "ALL"),
)


PATHWAY_RULES = (
    ("definition", r"是指|定义为|是一类|属于|称为|defined as"),
    ("etiology", r"病因|诱因|基础心脏病|遗传|基因|缺血|电解质|低钾|低镁|QT延长药物"),
    ("epidemiology", r"发病率|患病率|流行病学"),
    ("symptom_sign", r"心悸|晕厥|头晕|胸闷|胸痛|呼吸困难|意识丧失|无脉搏|症状|体征|临床表现"),
    ("exam", r"心电图|Holter|动态心电图|电生理|超声|磁共振|CMR|冠脉造影|基因检测|QT|QRS|J点|Brugada"),
    ("diagnosis_criteria", r"诊断|鉴别|宽QRS|室速|室颤|QTc|Brugada|排除"),
    ("risk_stratification", r"危险分层|风险评估|猝死风险|高危|ICD适应证|LVEF"),
    ("treatment_plan", r"治疗|复苏|除颤|电复律|消融|ICD|药物|胺碘酮|利多卡因|索他洛尔|β受体|硫酸镁|起搏"),
    ("complication", r"并发|心脏骤停|猝死|休克|脑缺氧|死亡"),
    ("prognosis", r"预后|死亡率|复发|再发|生存"),
    ("follow_up", r"随访|复查|监测|长期管理"),
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


def _term_hit(text: str, term: str) -> bool:
    if not term:
        return False
    if term.isascii() and len(term) <= 12:
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, re.IGNORECASE))
    return bool(re.search(re.escape(term), text, re.IGNORECASE))


def _disease_matches(text: str) -> list[tuple[str, str]]:
    matches = []
    for code, name, name_en, abbr, aliases, _subcategory in VA_SCD_DISEASES:
        terms = [name, name_en, abbr, *aliases.split(",")]
        for term in (item.strip() for item in terms if item.strip()):
            if _term_hit(text, term):
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
            "category_code": "CAT-CARD-ARR",
            "subcategory_code": "",
            "disease_code": "",
            "name": "心律失常",
            "name_en": "Arrhythmia",
            "aliases": "心律失常疾病谱,arrhythmia",
            "inclusion_status": "included",
            "inclusion_reason": "USER_CONFIRMED_CATEGORY",
        },
        {
            "specialty_code": "SPEC-CARD",
            "category_code": "CAT-CARD-ARR",
            "subcategory_code": "SUB-CARD-ARR-VA",
            "disease_code": "",
            "name": "室性心律失常谱系",
            "name_en": "Ventricular arrhythmia spectrum",
            "aliases": "室速室颤谱系",
            "inclusion_status": "included",
            "inclusion_reason": "USER_CONFIRMED_SUBCATEGORY",
        },
        {
            "specialty_code": "SPEC-CARD",
            "category_code": "CAT-CARD-ARR",
            "subcategory_code": "SUB-CARD-ARR-SCD",
            "disease_code": "",
            "name": "心脏骤停与心脏性猝死",
            "name_en": "Cardiac arrest and sudden cardiac death",
            "aliases": "猝死谱系",
            "inclusion_status": "included",
            "inclusion_reason": "USER_CONFIRMED_SUBCATEGORY",
        },
        {
            "specialty_code": "SPEC-CARD",
            "category_code": "CAT-CARD-ARR",
            "subcategory_code": "SUB-CARD-ARR-INHERITED",
            "disease_code": "",
            "name": "遗传性原发性心律失常综合征",
            "name_en": "Inherited primary arrhythmia syndromes",
            "aliases": "遗传性心律失常",
            "inclusion_status": "included",
            "inclusion_reason": "USER_CONFIRMED_SUBCATEGORY",
        },
    ]
    for code, name, name_en, abbr, aliases, subcategory in VA_SCD_DISEASES:
        taxonomy_rows.append(
            {
                "specialty_code": "SPEC-CARD",
                "category_code": "CAT-CARD-ARR",
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
    for code, name, name_en, abbr, aliases, _subcategory in VA_SCD_DISEASES:
        vocabulary_rows.append(
            {
                "canonical_name": name,
                "name_en": name_en,
                "abbr": abbr,
                "aliases": aliases,
                "entityType": "Disease",
                "disease_scope": code,
                "source": "室性心律失常及心脏性猝死批次目录",
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
                "source": "室性心律失常及心脏性猝死批次受控词表",
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
        and row.get("extension", "").lower() in {".pdf", ".docx"}
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
                        "source_section": "室性心律失常及心脏性猝死基础教材证据",
                        "source_page": page if page is not None else "N/A",
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
        "disease_count": len(VA_SCD_DISEASES),
        "vocabulary_count": len(vocabulary_rows),
        "textbook_evidence_count": len(evidence_rows),
    }
    output_dir = batch_dir / "04_evidence_and_extraction"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "ventricular_arrhythmia_foundation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build ventricular arrhythmia and sudden cardiac death taxonomy, vocabulary, and textbook evidence."
    )
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_foundation(args.batch_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
