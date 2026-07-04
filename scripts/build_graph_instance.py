from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


ENTITY_CATEGORY = {
    "Specialty": "目录",
    "DiseaseCategory": "目录",
    "DiseaseSubcategory": "目录",
    "Disease": "临床",
    "Symptom": "临床",
    "Sign": "临床",
    "Etiology": "临床",
    "Pathophysiology": "临床",
    "Epidemiology": "临床",
    "RiskFactor": "临床",
    "Complication": "临床",
    "Prognosis": "临床",
    "Exam": "诊断",
    "LabTest": "诊断",
    "ExamIndicator": "诊断",
    "ThresholdRule": "规则",
    "DiagnosisCriteria": "诊断",
    "DifferentialDiagnosis": "诊断",
    "RiskStratification": "风险",
    "ScoringScale": "风险",
    "ClinicalRule": "规则",
    "PatientState": "临床",
    "ClassificationStage": "临床",
    "TreatmentPlan": "治疗",
    "Medication": "治疗",
    "Procedure": "治疗",
    "Indication": "治疗",
    "Contraindication": "治疗",
    "FollowUp": "治疗",
    "Guideline": "证据",
    "Evidence": "证据",
}

ENTITY_TYPE_CANONICALIZATION = {
    "ClinicalProblem": "Complication",
}

TYPE_PREFIX = {
    "Symptom": "SYM",
    "Sign": "SIGN",
    "Etiology": "ETI",
    "Pathophysiology": "PATH",
    "Epidemiology": "EPI",
    "RiskFactor": "RF",
    "Complication": "COMP",
    "Prognosis": "PROG",
    "Exam": "EXAM",
    "LabTest": "LAB",
    "ExamIndicator": "IND",
    "ThresholdRule": "THR",
    "DiagnosisCriteria": "DXC",
    "DifferentialDiagnosis": "DDX",
    "RiskStratification": "RISK",
    "TreatmentPlan": "PLAN",
    "Medication": "MED",
    "Procedure": "PROC",
    "FollowUp": "FU",
}

EXPLICIT_CODES = {
    "心电图": "EXAM-ECG",
    "动态心电图": "EXAM-HOLTER",
    "超声心动图": "EXAM-TTE",
    "心脏磁共振成像": "EXAM-CMR",
    "心内膜心肌活检": "EXAM-EMB",
    "基因检测": "EXAM-GENETIC",
    "冠状动脉造影": "EXAM-CAG",
    "左心室射血分数": "IND-LVEF",
    "左室流出道压差": "IND-LVOT-GRADIENT",
    "最大室壁厚度": "IND-MAX-WALL-THICKNESS",
    "钆延迟增强": "IND-LGE",
    "N末端B型利钠肽原": "IND-NT-PROBNP",
    "肌钙蛋白": "IND-CARDIAC-TROPONIN",
    "β受体阻滞剂": "MED-BETA-BLOCKER",
    "β受体拮抗剂": "MED-BETA-BLOCKER",
    "非二氢吡啶类钙通道阻滞剂": "MED-NDHP-CCB",
    "利尿剂": "MED-DIURETIC",
    "胺碘酮": "MED-AMIODARONE",
    "室间隔切除术": "PROC-SEPTAL-MYECTOMY",
    "酒精室间隔消融术": "PROC-ASA",
    "埋藏式心脏复律除颤器": "PROC-ICD",
    "心脏移植": "PROC-HEART-TRANSPLANT",
}

RELATION_CATEGORY = {
    "has_category": "structural",
    "has_subcategory": "structural",
    "has_disease": "structural",
    "belongs_to_subcategory": "structural",
    "belongs_to_category": "structural",
    "has_etiology": "clinical",
    "has_pathophysiology": "clinical",
    "has_epidemiology": "clinical",
    "has_risk_factor": "clinical",
    "has_symptom": "clinical",
    "has_sign": "clinical",
    "may_cause_complication": "clinical",
    "has_prognosis": "clinical",
    "requires_exam": "diagnostic",
    "requires_lab_test": "diagnostic",
    "exam_has_indicator": "diagnostic",
    "lab_test_has_indicator": "diagnostic",
    "has_threshold_rule": "rule",
    "has_diagnostic_criteria": "diagnostic",
    "differentiates_from": "diagnostic",
    "has_risk_stratification": "risk",
    "has_treatment_plan": "therapeutic",
    "treated_by_medication": "therapeutic",
    "treated_by_procedure": "therapeutic",
    "has_follow_up": "therapeutic",
    "based_on_guideline": "evidence",
    "guideline_has_evidence": "evidence",
    "supported_by_evidence": "evidence",
}


def _load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _slug_code(entity_type: str, name: str) -> str:
    entity_type = _canonical_entity_type(entity_type)
    if name in EXPLICIT_CODES:
        return EXPLICIT_CODES[name]
    digest = hashlib.sha1(f"{entity_type}|{name}".encode("utf-8")).hexdigest()[:12].upper()
    return f"{TYPE_PREFIX.get(entity_type, 'ENT')}-CARD-{digest}"


def _canonical_entity_type(entity_type: str) -> str:
    return ENTITY_TYPE_CANONICALIZATION.get(str(entity_type).strip(), str(entity_type).strip())


def _node_id(code: str) -> str:
    return "KG_" + re.sub(r"[^A-Za-z0-9]+", "_", code).strip("_")


def _common_node(code: str, name: str, entity_type: str, batch_id: str, **extra) -> dict:
    node = {
        "id": _node_id(code),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": ENTITY_CATEGORY.get(entity_type, "临床"),
        "schema_version": "V1.4",
        "review_status": "approved",
        "batch_id": batch_id,
        "scope_type": "category",
        "scope_target": "心肌病",
        "merge_status": "validated",
        "conflict_status": "none",
    }
    node.update({key: value for key, value in extra.items() if value not in (None, "")})
    return node


def _manifest_source_type(row: dict) -> str:
    source_type = row.get("source_type", "")
    if source_type in {"guideline", "consensus", "authoritative_textbook", "expert_material", "curated_web_text"}:
        return source_type
    name = row.get("file_name", "")
    if re.search(r"指南|AHA|ESC|WHO|ACC", name, re.IGNORECASE):
        return "guideline"
    if re.search(r"共识|建议", name):
        return "consensus"
    return "expert_material"


def _provenance(evidence: dict) -> dict:
    return {
        "document_id": evidence["document_id"],
        "segment_id": evidence["segment_id"],
        "source_name": evidence["source_name"],
        "source_type": evidence["source_type"],
        "source_version": evidence.get("source_version", "N/A"),
        "source_section": evidence.get("source_section", "N/A"),
        "source_page": evidence.get("source_page", "N/A"),
        "disease_code": evidence.get("disease_code", ""),
        "disease_name": evidence.get("disease_name", ""),
        "evidence_text": evidence["evidence_text"],
        "recommendation_class": evidence.get("recommendation_class", "N/A"),
        "evidence_level": evidence.get("evidence_level", "N/A"),
    }


DEFINITION_CUE_RE = re.compile(
    r"(?:\u662f\u4e00\u7c7b|\u662f\u6307|\u5b9a\u4e49\u4e3a|\u4e3a\u7279\u5f81|defined as|characteri[sz]ed by)",
    re.IGNORECASE,
)


def _text_mentions_alias(text: str, alias: str) -> bool:
    if not alias:
        return False
    if alias.isascii() and len(alias) <= 12:
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, re.IGNORECASE))
    return alias.lower() in text.lower()


def _normalize_definition_sentence(sentence: str) -> str:
    sentence = sentence.strip()
    if re.search(r"[\u4e00-\u9fff]", sentence):
        sentence = re.sub(r"\s+", " ", sentence)
        sentence = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", sentence)
        sentence = re.sub(r"(?<=[，。；、（）()/])\s+|\s+(?=[，。；、（）()/])", "", sentence)
    else:
        sentence = re.sub(r"\s+", " ", sentence)
    return sentence.strip()


def _extract_definition_sentence(text: str, aliases: set[str]) -> str:
    if not text or not DEFINITION_CUE_RE.search(text):
        return ""
    chunks = re.split(r"(?<=[\u3002.!?])|\u3010", text)
    for chunk in chunks:
        sentence = _normalize_definition_sentence(chunk.strip("】 "))
        cue_match = DEFINITION_CUE_RE.search(sentence)
        if (
            sentence
            and cue_match
            and any(_text_mentions_alias(sentence[:cue_match.start()], alias) for alias in aliases)
        ):
            return sentence
    return ""


def _definition_candidate_score(definition_text: str, evidence: dict) -> tuple[int, int]:
    score = 0
    if re.search(r"[\u4e00-\u9fff]", definition_text):
        score += 100
    if evidence.get("source_type") == "authoritative_textbook":
        score += 30
    if "\u5185\u79d1\u5b66" in evidence.get("source_name", ""):
        score += 20
    if evidence.get("pathway_element") == "definition":
        score += 10
    return score, -len(definition_text)


def _terminology_definition(node: dict, scope_target: str, parent_name: str = "") -> str:
    name = node.get("name", "")
    name_en = node.get("name_en", "")
    aliases = node.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [item for item in aliases.split(",") if item]
    abbr = next((item for item in aliases if item.isascii() and 2 <= len(item) <= 15), "")
    english_part = ""
    if name_en and abbr:
        english_part = f"（{abbr}，{name_en}）"
    elif name_en:
        english_part = f"（{name_en}）"
    elif abbr:
        english_part = f"（{abbr}）"
    parent_part = f"，属于{parent_name}" if parent_name else ""
    scope_part = f"{scope_target}范围内" if scope_target else "本批次范围内"
    return f"{name}{english_part}为{scope_part}的疾病或临床亚型{parent_part}。"


def _serialize_csv_value(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _serialize_csv_value(row.get(key, "")) for key in fields})


def build_graph_instance(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir).resolve()
    config_path = batch_dir / "00_scope_and_config" / "batch_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
    batch_id = config.get("batch_id", "BATCH-UNKNOWN")
    schema_version = config.get("schema_version", "V1.4")
    scope_type = config.get("scope_type", "category")
    scope_target = config.get("scope_target", "心肌病")
    taxonomy = _load_csv(batch_dir / "00_scope_and_config" / "scope_taxonomy.csv")
    vocabulary = _load_csv(batch_dir / "00_scope_and_config" / "controlled_vocabulary.csv")
    manifest = [row for row in _load_csv(batch_dir / "01_source_manifest" / "source_documents_manifest.csv") if row.get("inclusion_status") == "included"]
    evidence = _load_jsonl(batch_dir / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl")
    textbook = _load_jsonl(batch_dir / "03_clean_text" / "textbook_evidence_index.jsonl")
    for row in textbook:
        digest = row.get("content_hash") or hashlib.sha256(row["evidence_text"].encode("utf-8")).hexdigest().upper()
        row.setdefault("evidence_id", f"EVD-TB-{digest[:20]}-{row['disease_code'].split('-')[-1]}")
        row.setdefault("source_version", "第10版")
    evidence.extend(textbook)

    nodes: dict[str, dict] = {}
    relations: dict[tuple[str, str, str], dict] = {}
    alias_log: dict[tuple, dict] = {}
    definition_scores: dict[str, tuple[int, int]] = {}

    def add_node(node: dict) -> dict:
        existing = nodes.get(node["code"])
        if existing:
            for key, value in node.items():
                if key not in existing or existing[key] in (None, "", []):
                    existing[key] = value
            return existing
        nodes[node["code"]] = node
        return node

    def add_relation(source: str, relation_type: str, target: str, evidence_row: dict | None = None, polarity: str = "positive", **extra) -> dict:
        key = (source, relation_type, target)
        relation = relations.get(key)
        if relation is None:
            digest = hashlib.sha1("|".join(key).encode("utf-8")).hexdigest()[:20].upper()
            relation = {
                "id": f"REL-{digest}",
                "source_code": source,
                "relationType": relation_type,
                "target_code": target,
                "relationCategory": RELATION_CATEGORY[relation_type],
                "batch_id": batch_id,
                "schema_version": "V1.4",
                "review_status": "approved",
                "polarity": polarity,
                "scope_type": "category",
                "scope_target": "心肌病",
                "merge_status": "validated",
                "conflict_status": "none",
                "provenance_records_json": [],
                "evidence_ids": [],
                "document_ids": [],
                "source_names": [],
                "source_types": [],
                "evidence_count": 0,
            }
            relation.update(extra)
            relations[key] = relation
        if evidence_row:
            prov = _provenance(evidence_row)
            marker = (prov["document_id"], prov["segment_id"])
            existing_markers = {(item["document_id"], item["segment_id"]) for item in relation["provenance_records_json"]}
            if marker not in existing_markers:
                relation["provenance_records_json"].append(prov)
                for field, value in (
                    ("evidence_ids", evidence_row["evidence_id"]),
                    ("document_ids", prov["document_id"]),
                    ("source_names", prov["source_name"]),
                    ("source_types", prov["source_type"]),
                ):
                    if value not in relation[field]:
                        relation[field].append(value)
                relation["evidence_count"] = len(relation["provenance_records_json"])
                for field in ("document_id", "segment_id", "source_name", "source_type", "source_version", "source_section", "source_page", "evidence_text", "recommendation_class", "evidence_level"):
                    relation.setdefault(field, prov.get(field, "N/A"))
                relation.setdefault("guideline_id", f"SRC-{prov['document_id']}")
                relation.setdefault("evidence_id", evidence_row["evidence_id"])
                relation.setdefault("confidence", 1.0)
        return relation

    specialty_code = "SPEC-CARD"
    category_code = "CAT-CARD-CM"
    subcategories: set[str] = set()
    disease_names: dict[str, str] = {}
    for row in taxonomy:
        if row.get("inclusion_status") != "included":
            continue
        if row.get("disease_code"):
            code, entity_type = row["disease_code"], "Disease"
            disease_names[code] = row["name"]
            extra = {"name_en": row.get("name_en", ""), "aliases": [item for item in row.get("aliases", "").split(",") if item], "parentCode": row.get("subcategory_code", "")}
        elif row.get("subcategory_code"):
            code, entity_type = row["subcategory_code"], "DiseaseSubcategory"
            subcategories.add(code)
            extra = {"parentCode": row.get("category_code", "")}
        elif row.get("category_code"):
            code, entity_type = row["category_code"], "DiseaseCategory"
            category_code = code
            extra = {"parentCode": row.get("specialty_code", "")}
        else:
            code, entity_type = row["specialty_code"], "Specialty"
            specialty_code = code
            extra = {}
        add_node(_common_node(code, row["name"], entity_type, batch_id, **extra))

    if category_code in nodes and specialty_code in nodes:
        add_relation(specialty_code, "has_category", category_code)
    for subcategory in subcategories:
        add_relation(category_code, "has_subcategory", subcategory)
    for row in taxonomy:
        if row.get("disease_code") and row.get("inclusion_status") == "included":
            add_relation(row["subcategory_code"], "has_disease", row["disease_code"])
            add_relation(row["disease_code"], "belongs_to_subcategory", row["subcategory_code"], classification_role="primary")
            add_relation(row["disease_code"], "belongs_to_category", category_code, classification_role="primary")

    manifest_by_id = {row["document_id"]: row for row in manifest}
    for row in manifest:
        code = f'SRC-{row["document_id"]}'
        year_match = re.search(r"(?:19|20)\d{2}", row.get("file_name", ""))
        add_node(
            _common_node(
                code,
                row["file_name"],
                "Guideline",
                batch_id,
                document_id=row["document_id"],
                title=row["file_name"],
                source_type=_manifest_source_type(row),
                publication_year=year_match.group(0) if year_match else "N/A",
                version=year_match.group(0) if year_match else "N/A",
                language="zh/en",
                sha256=row.get("sha256", ""),
            )
        )

    compiled_vocab = []
    vocabulary_by_code: dict[str, dict] = {}
    for raw_row in vocabulary:
        row = dict(raw_row)
        row["entityType"] = _canonical_entity_type(row.get("entityType", ""))
        if row.get("entityType") == "Disease":
            continue
        vocabulary_by_code[_slug_code(row["entityType"], row["canonical_name"])] = row
        names = [row.get("canonical_name", ""), row.get("abbr", "")]
        names.extend(item.strip() for item in row.get("aliases", "").split(","))
        regexes = []
        for name in sorted({item for item in names if item}, key=len, reverse=True):
            escaped = re.escape(name)
            regex = re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE) if name.isascii() and len(name) <= 8 else re.compile(escaped, re.IGNORECASE)
            regexes.append((name, regex))
        compiled_vocab.append((row, regexes))

    lab_code = "LAB-CARDIAC-BIOMARKERS"
    add_node(_common_node(lab_code, "心脏生物标志物检测", "LabTest", batch_id))

    disease_aliases: dict[str, set[str]] = {code: {name} for code, name in disease_names.items()}
    for row in taxonomy:
        if row.get("disease_code") in disease_aliases:
            if row.get("name_en"):
                disease_aliases[row["disease_code"]].add(row["name_en"])
            disease_aliases[row["disease_code"]].update(
                item for item in row.get("aliases", "").split(",") if item
            )
    for row in vocabulary:
        if row.get("entityType") == "Disease" and row.get("disease_scope") in disease_aliases:
            disease_aliases[row["disease_scope"]].update(
                item
                for item in (
                    row.get("canonical_name", ""),
                    row.get("name_en", ""),
                    row.get("abbr", ""),
                    *row.get("aliases", "").split(","),
                )
                if item
            )

    def evidence_mentions_disease(disease_code: str, text: str) -> bool:
        for alias in disease_aliases.get(disease_code, set()):
            if alias.isascii() and len(alias) <= 8:
                if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, re.IGNORECASE):
                    return True
            elif alias.lower() in text.lower():
                return True
        return False

    indicator_parent = {
        "左心室射血分数": ("EXAM-TTE", "exam_has_indicator"),
        "左室流出道压差": ("EXAM-TTE", "exam_has_indicator"),
        "最大室壁厚度": ("EXAM-TTE", "exam_has_indicator"),
        "钆延迟增强": ("EXAM-CMR", "exam_has_indicator"),
        "ST段抬高": ("EXAM-ECG", "exam_has_indicator"),
        "ST段压低": ("EXAM-ECG", "exam_has_indicator"),
        "发病时间": ("EXAM-CLINICAL-HISTORY", "exam_has_indicator"),
        "N末端B型利钠肽原": (lab_code, "lab_test_has_indicator"),
        "肌钙蛋白": (lab_code, "lab_test_has_indicator"),
    }
    parent_fallback = {
        "EXAM-ECG": ("心电图", "Exam"),
        "EXAM-CLINICAL-HISTORY": ("病史采集", "Exam"),
        lab_code: ("心脏生物标志物检测", "LabTest"),
    }

    generic_pathways = {
        "definition": (None, None),
        "etiology": ("Etiology", "has_etiology"),
        "pathophysiology": ("Pathophysiology", "has_pathophysiology"),
        "epidemiology": ("Epidemiology", "has_epidemiology"),
        "diagnosis_criteria": ("DiagnosisCriteria", "has_diagnostic_criteria"),
        "risk_stratification": ("RiskStratification", "has_risk_stratification"),
        "treatment_plan": ("TreatmentPlan", "has_treatment_plan"),
        "follow_up": ("FollowUp", "has_follow_up"),
        "prognosis": ("Prognosis", "has_prognosis"),
    }
    generic_aliases = {
        "Etiology": ["病因", "致病基因", "遗传", "危险因素", "动脉粥样硬化", "斑块", "血栓"],
        "Pathophysiology": ["发病机制", "病理生理", "纤维化"],
        "Epidemiology": ["流行病学", "患病率", "发病率"],
        "DiagnosisCriteria": ["诊断", "诊断标准", "诊断依据", "鉴别", "鉴别诊断"],
        "RiskStratification": ["风险", "危险分层", "高危"],
        "TreatmentPlan": ["治疗", "治疗方案", "推荐使用", "推荐植入", "用药", "药物", "手术", "消融", "移植", "植入", "ICD"],
        "FollowUp": ["随访", "复查"],
        "Prognosis": ["预后", "死亡率", "生存率"],
    }

    threshold_patterns = {
        "左心室射血分数": re.compile(r"(?:LVEF|左心?室射血分数|射血分数)\s*(≤|≥|<|>|=|<=|>=)\s*(\d+(?:\.\d+)?)\s*(%)", re.IGNORECASE),
        "左室流出道压差": re.compile(r"(?:LVOT[^，。；]{0,12}(?:压差|梯度)|左室流出道压差)\s*(≤|≥|<|>|=|<=|>=)\s*(\d+(?:\.\d+)?)\s*(mmHg)", re.IGNORECASE),
        "最大室壁厚度": re.compile(r"(?:最大)?室壁厚度\s*(≤|≥|<|>|=|<=|>=)\s*(\d+(?:\.\d+)?)\s*(mm)", re.IGNORECASE),
        "钆延迟增强": re.compile(r"(?:LGE|钆延迟增强)[^，。；]{0,15}(≤|≥|<|>|=|<=|>=)\s*(\d+(?:\.\d+)?)\s*(%)", re.IGNORECASE),
        "ST段抬高": re.compile(r"(?:ST\s*段?抬高|STEMI)[^，。；]{0,30}(≤|≥|<|>|=|<=|>=)\s*(\d+(?:\.\d+)?)\s*(mm|mV)", re.IGNORECASE),
        "ST段压低": re.compile(r"(?:ST\s*段?压低|ST\s*depression)[^，。；]{0,30}(≤|≥|<|>|=|<=|>=)\s*(\d+(?:\.\d+)?)\s*(mm|mV)", re.IGNORECASE),
        "发病时间": re.compile(r"(?:发病|起病|症状发作|胸痛)[^，。；]{0,12}(≤|≥|<|>|=|<=|>=)?\s*(\d+(?:\.\d+)?)\s*(h|小时)", re.IGNORECASE),
    }
    operator_map = {"≤": "<=", "≥": ">=", "<": "<", ">": ">", "=": "=", "<=": "<=", ">=": ">="}

    for ev in evidence:
        if ev.get("disease_code") not in disease_names:
            continue
        ev.setdefault("source_type", "authoritative_textbook" if ev.get("recommendation_class") == "N/A" and "内科学" in ev.get("source_name", "") else "guideline")
        ev.setdefault("source_version", "N/A")
        ev.setdefault("evidence_id", f"EVD-{hashlib.sha1(ev['segment_id'].encode()).hexdigest()[:20].upper()}")
        disease_code = ev["disease_code"]
        disease_name = disease_names[disease_code]
        text = ev["evidence_text"]
        contextual_disease_anchor = ev.get("source_type") == "authoritative_textbook" and bool(
            ev.get("disease_code") and ev.get("disease_name")
        )
        if not evidence_mentions_disease(disease_code, text) and not contextual_disease_anchor:
            continue
        source_code = f'SRC-{ev["document_id"]}'
        if source_code not in nodes:
            source_row = manifest_by_id.get(ev["document_id"], {})
            add_node(_common_node(source_code, ev["source_name"], "Guideline", batch_id, document_id=ev["document_id"], title=ev["source_name"], source_type=ev["source_type"], version=ev.get("source_version", "N/A"), language="zh/en", sha256=source_row.get("sha256", "")))
        evidence_code = ev["evidence_id"]
        evidence_name = (
            f'{ev["source_name"]} 第{ev.get("source_page", "N/A")}页证据'
            f'（{ev["segment_id"]}）'
        )
        add_node(_common_node(evidence_code, evidence_name, "Evidence", batch_id, evidence_id=evidence_code, document_id=ev["document_id"], segment_id=ev["segment_id"], source_name=ev["source_name"], source_type=ev["source_type"], source_section=ev.get("source_section", "N/A"), source_page=ev.get("source_page", "N/A"), disease_code=ev.get("disease_code", ""), disease_name=ev.get("disease_name", ""), evidence_text=text, language=ev.get("language", "zh"), content_hash=ev.get("content_hash", "")))
        add_relation(source_code, "guideline_has_evidence", evidence_code)
        add_relation(disease_code, "based_on_guideline", source_code, ev)
        add_relation(disease_code, "supported_by_evidence", evidence_code, ev)

        pathway = ev.get("pathway_element", "clinical_knowledge")
        definition_text = _extract_definition_sentence(text, disease_aliases.get(disease_code, {disease_name}))
        if not definition_text and pathway == "definition" and evidence_mentions_disease(disease_code, text):
            definition_text = _normalize_definition_sentence(text)
        definition_score = _definition_candidate_score(definition_text, ev) if definition_text else (-1, 0)
        if definition_text and definition_score > definition_scores.get(disease_code, (-1, 0)):
            nodes[disease_code]["description"] = definition_text
            nodes[disease_code]["definition_evidence_text"] = definition_text
            definition_scores[disease_code] = definition_score
        entity_type, relation_type = generic_pathways.get(pathway, (None, None))
        if entity_type and relation_type:
            generic_name = f"{disease_name}{ {'Etiology':'病因','Pathophysiology':'病理生理机制','Epidemiology':'流行病学','DiagnosisCriteria':'诊断标准','RiskStratification':'风险分层','TreatmentPlan':'治疗方案','FollowUp':'随访方案','Prognosis':'预后'}[entity_type] }"
            generic_code = _slug_code(entity_type, generic_name)
            add_node(_common_node(generic_code, generic_name, entity_type, batch_id, aliases=generic_aliases[entity_type]))
            add_relation(disease_code, relation_type, generic_code, ev)
            add_relation(generic_code, "supported_by_evidence", evidence_code, ev)

        negative_context = bool(re.search(r"不推荐|不建议|不应|禁用|禁忌|避免|无须|无需", text))
        for vocab_row, patterns in compiled_vocab:
            matched_alias = next((alias for alias, pattern in patterns if pattern.search(text)), None)
            if not matched_alias:
                continue
            entity_type = vocab_row["entityType"]
            canonical_name = vocab_row["canonical_name"]
            entity_code = _slug_code(entity_type, canonical_name)
            add_node(_common_node(entity_code, canonical_name, entity_type, batch_id, name_en=vocab_row.get("name_en", ""), aliases=[item for item in vocab_row.get("aliases", "").split(",") if item], abbr=vocab_row.get("abbr", "")))
            add_relation(entity_code, "supported_by_evidence", evidence_code, ev)
            if matched_alias != canonical_name:
                marker = (matched_alias, canonical_name, entity_type, ev["document_id"], ev["segment_id"])
                alias_log[marker] = {"original_name": matched_alias, "canonical_name": canonical_name, "entityType": entity_type, "document_id": ev["document_id"], "segment_id": ev["segment_id"], "action": "replaced", "reason": "CONTROLLED_VOCABULARY_MATCH", "status": "approved"}

            direct_relation = None
            if entity_type == "Symptom" and (pathway == "symptom_sign" or re.search(r"症状|表现为", text)):
                direct_relation = "has_symptom"
            elif entity_type == "Sign" and (pathway == "symptom_sign" or re.search(r"体征|可见|闻及", text)):
                direct_relation = "has_sign"
            elif entity_type == "Exam" and not negative_context:
                direct_relation = "requires_exam"
            elif entity_type == "LabTest" and not negative_context:
                direct_relation = "requires_lab_test"
            elif entity_type == "RiskFactor" and (
                pathway in {"etiology", "pathophysiology", "clinical_knowledge"}
                or re.search(r"危险因素|风险因素|家族史|基因|吸烟|糖尿病|高血压|血脂|肥胖|感染|自身免疫|饮酒|毒性", text)
            ):
                direct_relation = "has_risk_factor"
            elif entity_type == "DifferentialDiagnosis" and (
                pathway == "diagnosis_criteria" or re.search(r"鉴别|需与|排除|除外", text)
            ):
                direct_relation = "differentiates_from"
            elif entity_type == "RiskStratification" and pathway == "risk_stratification" and not negative_context:
                direct_relation = "has_risk_stratification"
            elif entity_type == "Medication" and pathway == "treatment_plan" and not negative_context:
                direct_relation = "treated_by_medication"
            elif entity_type == "Procedure" and pathway in {"treatment_plan", "risk_stratification"} and not negative_context:
                direct_relation = "treated_by_procedure"
            elif entity_type == "TreatmentPlan" and pathway == "treatment_plan" and not negative_context:
                direct_relation = "has_treatment_plan"
            elif entity_type == "Complication" and re.search(r"并发|发生|风险|导致|预后", text):
                direct_relation = "may_cause_complication"
            if direct_relation:
                add_relation(disease_code, direct_relation, entity_code, ev)

            if entity_type == "ExamIndicator" and canonical_name in indicator_parent:
                parent_code, indicator_relation = indicator_parent[canonical_name]
                if parent_code not in nodes:
                    parent_vocab = vocabulary_by_code.get(parent_code)
                    if parent_vocab:
                        add_node(
                            _common_node(
                                parent_code,
                                parent_vocab["canonical_name"],
                                parent_vocab["entityType"],
                                batch_id,
                                name_en=parent_vocab.get("name_en", ""),
                                aliases=[item for item in parent_vocab.get("aliases", "").split(",") if item],
                                abbr=parent_vocab.get("abbr", ""),
                            )
                        )
                    else:
                        parent_name, parent_type = parent_fallback.get(parent_code, (parent_code, "Exam"))
                        add_node(_common_node(parent_code, parent_name, parent_type, batch_id))
                add_relation(parent_code, indicator_relation, entity_code, ev)
                pattern = threshold_patterns.get(canonical_name)
                if pattern:
                    for match in pattern.finditer(text):
                        operator = operator_map[match.group(1) or "<="]
                        raw_value = float(match.group(2))
                        value = int(raw_value) if raw_value.is_integer() else raw_value
                        unit = match.group(3)
                        rule_key = f"{disease_code}|{entity_code}|{operator}|{value}|{unit}"
                        rule_code = f"THR-{hashlib.sha1(rule_key.encode()).hexdigest()[:16].upper()}"
                        rule_name = f"{canonical_name} {operator} {value}{unit}（{disease_name}）"
                        add_node(_common_node(rule_code, rule_name, "ThresholdRule", batch_id, indicator_code=entity_code, operator=operator, value=value, unit=unit, condition=text[:500], patient_state=disease_code, time_context="N/A"))
                        add_relation(entity_code, "has_threshold_rule", rule_code, ev)
                        add_relation(rule_code, "supported_by_evidence", evidence_code, ev)

    for disease_code in disease_names:
        disease_node = nodes.get(disease_code)
        if not disease_node or disease_node.get("description"):
            continue
        parent = nodes.get(disease_node.get("parentCode", ""), {})
        disease_node["description"] = _terminology_definition(
            disease_node,
            scope_target,
            parent.get("name", ""),
        )
        disease_node["definition_evidence_text"] = disease_node["description"]
        disease_node["definition_source_type"] = "controlled_vocabulary"
        disease_node["definition_source"] = "scope_taxonomy.csv;controlled_vocabulary.csv"

    for node in nodes.values():
        node["schema_version"] = schema_version
        node["scope_type"] = scope_type
        node["scope_target"] = scope_target
    for relation in relations.values():
        relation["schema_version"] = schema_version
        relation["scope_type"] = scope_type
        relation["scope_target"] = scope_target

    node_rows = sorted(nodes.values(), key=lambda row: (row["entityType"], row["code"]))
    relation_rows = sorted(relations.values(), key=lambda row: (row["relationType"], row["source_code"], row["target_code"]))
    output_dir = batch_dir / "05_data_instance"
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "nodes_final.jsonl").open("w", encoding="utf-8-sig", newline="\n") as handle:
        for row in node_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output_dir / "relations_final.jsonl").open("w", encoding="utf-8-sig", newline="\n") as handle:
        for row in relation_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    _write_csv(output_dir / "nodes_final.csv", node_rows)
    _write_csv(output_dir / "relations_final.csv", relation_rows)
    (output_dir / "graph_final.json").write_text(json.dumps({"schema_version": schema_version, "batch_id": batch_id, "nodes": node_rows, "relations": relation_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")

    extraction_dir = batch_dir / "04_evidence_and_extraction"
    alias_rows = sorted(alias_log.values(), key=lambda row: (row["entityType"], row["canonical_name"], row["original_name"]))
    fields = ("original_name", "canonical_name", "entityType", "document_id", "segment_id", "action", "reason", "status")
    with (extraction_dir / "alias_normalization_log.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(alias_rows)
    polarity_fields = ("relation_id", "source_code", "relationType", "target_code", "polarity", "condition_text", "evidence_text", "审核状态")
    with (batch_dir / "06_quality_audit" / "polarity_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=polarity_fields); writer.writeheader()
        for relation in relation_rows:
            if relation.get("polarity") in {"negative", "conditional"}:
                writer.writerow({"relation_id": relation["id"], "source_code": relation["source_code"], "relationType": relation["relationType"], "target_code": relation["target_code"], "polarity": relation["polarity"], "condition_text": relation.get("condition_text", ""), "evidence_text": relation.get("evidence_text", ""), "审核状态": "pending_review"})

    summary = {"node_count": len(node_rows), "relation_count": len(relation_rows), "evidence_node_count": sum(row["entityType"] == "Evidence" for row in node_rows), "threshold_rule_count": sum(row["entityType"] == "ThresholdRule" for row in node_rows), "alias_normalization_count": len(alias_rows)}
    (extraction_dir / "graph_extraction_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Schema V1.4 medical graph instance.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_graph_instance(args.batch_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
