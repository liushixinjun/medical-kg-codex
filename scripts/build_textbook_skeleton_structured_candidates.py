from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


NODE_TYPE_BY_SLOT = {
    "definition": "Definition",
    "classification": "DiseaseClassification",
    "etiology": "Etiology",
    "pathogenesis": "Pathophysiology",
    "epidemiology": "Epidemiology",
    "clinical_manifestation": "ClinicalManifestation",
    "symptom": "Symptom",
    "sign": "Sign",
    "exam": "Exam",
    "lab_test": "LabTest",
    "diagnostic_criteria": "DiagnosisCriteriaComponent",
    "differential_diagnosis": "DifferentialDiagnosis",
    "risk_stratification": "RiskStratification",
    "treatment": "TreatmentPlan",
    "follow_up": "FollowUp",
    "prognosis": "Prognosis",
    "complication": "Complication",
    "prevention": "Prevention",
}

REL_TYPE_BY_NODE_TYPE = {
    "Definition": "HAS_DEFINITION",
    "DefinitionComponent": "HAS_DEFINITION_COMPONENT",
    "DiseaseClassification": "HAS_CLASSIFICATION",
    "Etiology": "HAS_ETIOLOGY",
    "RiskFactor": "HAS_RISK_FACTOR",
    "Pathophysiology": "HAS_PATHOPHYSIOLOGY",
    "Epidemiology": "HAS_EPIDEMIOLOGY",
    "ClinicalManifestation": "HAS_CLINICAL_MANIFESTATION",
    "Symptom": "HAS_SYMPTOM",
    "Sign": "HAS_SIGN",
    "Exam": "HAS_EXAM",
    "LabTest": "HAS_LAB_TEST",
    "DiagnosisCriteriaComponent": "HAS_DIAGNOSTIC_COMPONENT",
    "DifferentialDiagnosis": "HAS_DIFFERENTIAL_DIAGNOSIS",
    "RiskStratification": "HAS_RISK_STRATIFICATION",
    "TreatmentPlan": "HAS_TREATMENT_PLAN",
    "Medication": "USES_MEDICATION",
    "Procedure": "HAS_PROCEDURE",
    "FollowUp": "HAS_FOLLOW_UP",
    "Prognosis": "HAS_PROGNOSIS",
    "Complication": "HAS_COMPLICATION",
    "Prevention": "HAS_PREVENTION",
}

DICT_TO_NODE_TYPE = {
    "2_症状同义词表.yaml": "Symptom",
    "3_体征同义词表.yaml": "Sign",
    "4_药物同义词表.yaml": "Medication",
    "5_检查同义词表.yaml": "Exam",
    "6_手术同义词表.yaml": "Procedure",
    "7_危险因素同义词表.yaml": "RiskFactor",
    "8_路径与治疗方案同义词表.yaml": "TreatmentPlan",
}

BUILTIN_TERMS = {
    "Symptom": [
        "胸痛", "胸闷", "呼吸困难", "劳力性呼吸困难", "静息性呼吸困难", "端坐呼吸",
        "夜间阵发性呼吸困难", "心悸", "乏力", "疲乏", "头晕", "晕厥", "黑矇", "咳嗽",
        "咳粉红色泡沫痰", "水肿", "少尿", "尿量减少", "恶心", "呕吐", "出汗", "濒死感",
        "心绞痛", "胸部不适", "活动耐量下降",
    ],
    "Sign": [
        "低血压", "血压下降", "高血压", "心动过速", "心动过缓", "奔马律", "心脏扩大",
        "心界扩大", "心脏杂音", "收缩期杂音", "舒张期杂音", "心音低钝", "心音减弱",
        "肺部啰音", "湿啰音", "颈静脉怒张", "肝大", "肝颈静脉回流征阳性", "下肢水肿",
        "外周水肿", "发绀", "皮肤湿冷", "脉搏细速", "水冲脉",
    ],
    "Exam": [
        "心电图", "动态心电图", "Holter", "超声心动图", "胸部X线", "X线", "冠状动脉造影",
        "冠状动脉CTA", "CT", "MRI", "磁共振成像", "心脏磁共振", "运动负荷试验",
        "心内电生理检查", "血管内超声", "光学相干断层扫描", "OCT", "IVUS",
    ],
    "LabTest": [
        "肌钙蛋白", "心肌肌钙蛋白", "BNP", "NT-proBNP", "B型利钠肽", "血脂", "血糖",
        "D-二聚体", "血常规", "肾功能", "电解质", "肌酸激酶", "CK-MB", "肌红蛋白",
    ],
    "Medication": [
        "阿司匹林", "氯吡格雷", "替格瑞洛", "普拉格雷", "P2Y12受体抑制剂",
        "β受体拮抗剂", "β受体阻滞剂", "美托洛尔", "比索洛尔", "卡维地洛",
        "ACEI", "ARB", "ARNI", "沙库巴曲缬沙坦", "利尿剂", "呋塞米", "螺内酯",
        "硝酸酯类药物", "硝酸甘油", "他汀类药物", "阿托伐他汀", "瑞舒伐他汀",
        "胺碘酮", "地高辛", "华法林", "肝素", "低分子肝素", "多巴胺", "多巴酚丁胺",
        "去甲肾上腺素", "吗啡", "钙通道阻滞剂", "维拉帕米", "地尔硫䓬",
    ],
    "Procedure": [
        "PCI", "经皮冠状动脉介入治疗", "CABG", "冠状动脉旁路移植术", "溶栓治疗",
        "血运重建", "导管消融", "射频消融", "电复律", "电除颤", "同步电复律",
        "起搏器", "心脏起搏器", "ICD", "CRT", "植入型心律转复除颤器",
        "心脏再同步化治疗", "冠状动脉支架植入", "外科手术",
    ],
    "RiskFactor": [
        "高血压", "糖尿病", "血脂异常", "吸烟", "肥胖", "年龄", "家族史", "冠心病",
        "感染", "贫血", "肾功能不全", "心肌梗死", "心肌病", "瓣膜病", "心律失常",
    ],
    "Complication": [
        "心力衰竭", "心源性休克", "心脏骤停", "心脏性猝死", "室性心律失常", "肺水肿",
        "血栓栓塞", "出血", "脑卒中", "肾功能不全",
    ],
}

STOP_TERMS = {
    "治疗", "检查", "诊断", "鉴别", "分类", "表现", "症状", "体征", "病因", "机制",
    "患者", "病人", "疾病", "因素", "方法", "原则", "方案", "药物", "手术", "介入",
    "第一节", "第二节", "第三节", "本章数字资源",
}

FALSE_TREATMENT_PATTERNS = [
    "治疗不当", "不恰当停用", "减用原有治疗", "导致", "诱发", "加重",
]


def stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(str(p) for p in parts)
    return f"{prefix}-{hashlib.md5(raw.encode('utf-8')).hexdigest()[:16].upper()}"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def load_jsonl(path: Path) -> List[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_simple_yaml_terms(path: Path, node_type: str) -> List[dict]:
    if not path.exists():
        return []
    terms: List[dict] = []
    current: dict | None = None
    in_aliases = False
    for raw in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- canonical:"):
            if current:
                terms.append(current)
            canonical = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            current = {"canonical": canonical, "aliases": [], "code": "", "node_type": node_type}
            in_aliases = False
            continue
        if current is None:
            continue
        if stripped.startswith("code:"):
            current["code"] = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            in_aliases = False
        elif stripped.startswith("aliases:"):
            in_aliases = True
        elif in_aliases and stripped.startswith("- "):
            alias = stripped[2:].strip().strip('"').strip("'")
            if alias:
                current["aliases"].append(alias)
        elif re.match(r"^[a-zA-Z_]+:", stripped):
            in_aliases = False
    if current:
        terms.append(current)
    return terms


def build_term_index(dict_dir: Path) -> Dict[str, List[dict]]:
    by_type: Dict[str, List[dict]] = defaultdict(list)
    for filename, node_type in DICT_TO_NODE_TYPE.items():
        for item in load_simple_yaml_terms(dict_dir / filename, node_type):
            by_type[node_type].append(item)
    # Builtins are fallback only; if dictionary has same canonical, merge aliases implicitly by matching name.
    existing = {(t["node_type"], t["canonical"]) for items in by_type.values() for t in items}
    for node_type, names in BUILTIN_TERMS.items():
        for name in names:
            if (node_type, name) not in existing:
                by_type[node_type].append({"canonical": name, "aliases": [], "code": "", "node_type": node_type})
    return by_type


def candidate_names_for_term(term: dict) -> List[str]:
    names = [term["canonical"]] + list(term.get("aliases") or [])
    # Prefer longer aliases first to avoid "水肿" swallowing "下肢水肿".
    return sorted(set(n for n in names if n and len(n) >= 2), key=len, reverse=True)


def split_clauses(text: str) -> List[str]:
    text = normalize_text(text)
    # Preserve semantic separators but split long textbook runs.
    parts = re.split(r"[。；;]|(?=（[一二三四五六七八九十]+）)|(?=\\d+[.．、])|(?=①)|(?=②)|(?=③)|(?=④)|(?=⑤)|(?=⑥)|(?=⑦)|(?=⑧)", text)
    out = []
    for p in parts:
        p = p.strip("，,：:、 ")
        if len(p) >= 4:
            out.append(p)
    return out


def is_false_treatment(text: str) -> bool:
    return any(p in text for p in FALSE_TREATMENT_PATTERNS)


def match_terms(text: str, by_type: Dict[str, List[dict]], allowed_types: Iterable[str]) -> List[dict]:
    text = normalize_text(text)
    hits = []
    seen = set()
    for node_type in allowed_types:
        for term in by_type.get(node_type, []):
            for name in candidate_names_for_term(term):
                if name in STOP_TERMS:
                    continue
                if name and name in text:
                    key = (node_type, term["canonical"])
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append(
                        {
                            "node_type": node_type,
                            "canonical_name": term["canonical"],
                            "matched_text": name,
                            "standard_code": term.get("code", ""),
                            "confidence": "dictionary" if term.get("code") else "builtin_lexicon",
                        }
                    )
                    break
    return hits


def extract_definition_components(text: str) -> List[str]:
    text = normalize_text(text)
    components = []
    patterns = [
        r"是([^。；]{8,80})",
        r"指([^。；]{8,80})",
        r"主要表现为([^。；]{4,60})",
        r"导致([^。；]{4,60})",
        r"引起([^。；]{4,60})",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            comp = m.group(0).strip("，,。；;")
            if 6 <= len(comp) <= 100:
                components.append(comp)
    return list(dict.fromkeys(components))[:8]


def extract_list_like_components(text: str, max_items: int = 12) -> List[str]:
    text = normalize_text(text)
    parts = re.split(r"[；;。]|[①②③④⑤⑥⑦⑧⑨]|(?:\\d+[.．、])|[，,]", text)
    items = []
    for p in parts:
        p = p.strip("：:、.． ")
        if 4 <= len(p) <= 80 and not any(stop == p for stop in STOP_TERMS):
            # Filter obvious narrative fragments.
            if p.startswith(("如", "其中", "包括")) and len(p) < 8:
                continue
            items.append(p)
    return list(dict.fromkeys(items))[:max_items]


def allowed_match_types(slot: str) -> List[str]:
    if slot in {"clinical_manifestation", "symptom"}:
        return ["Symptom", "Sign"]
    if slot == "sign":
        return ["Sign"]
    if slot == "exam":
        return ["Exam", "LabTest"]
    if slot == "lab_test":
        return ["LabTest"]
    if slot == "etiology":
        return ["Etiology", "RiskFactor"]
    if slot == "pathogenesis":
        return ["Pathophysiology", "RiskFactor", "Complication"]
    if slot == "treatment":
        return ["TreatmentPlan", "Medication", "Procedure"]
    if slot == "differential_diagnosis":
        return ["DifferentialDiagnosis", "Exam", "LabTest"]
    if slot == "diagnostic_criteria":
        return ["DiagnosisCriteriaComponent", "Exam", "LabTest"]
    if slot == "risk_stratification":
        return ["RiskStratification", "RiskFactor", "Exam", "LabTest"]
    if slot == "complication":
        return ["Complication"]
    return []


def infer_generic_candidates(evidence: dict) -> List[dict]:
    slot = evidence.get("skeleton_slot", "")
    text = normalize_text(evidence.get("text_excerpt", ""))
    candidates = []
    if slot == "definition":
        candidates.append(
            {
                "node_type": "Definition",
                "canonical_name": f"{evidence['subject_name']}定义",
                "matched_text": "definition_text",
                "standard_code": "",
                "confidence": "textbook_definition_anchor",
                "fragment": text[:180],
            }
        )
        for comp in extract_definition_components(text):
            candidates.append(
                {
                    "node_type": "DefinitionComponent",
                    "canonical_name": comp,
                    "matched_text": comp,
                    "standard_code": "",
                    "confidence": "rule_component",
                    "fragment": comp,
                }
            )
    elif slot == "classification":
        for item in extract_list_like_components(text, 16):
            if any(k in item for k in ["分为", "型", "类", "心衰", "心绞痛", "综合征", "心肌病", "心律失常"]):
                candidates.append(
                    {
                        "node_type": "DiseaseClassification",
                        "canonical_name": item,
                        "matched_text": item,
                        "standard_code": "",
                        "confidence": "rule_classification",
                        "fragment": item,
                    }
                )
    elif slot == "diagnostic_criteria":
        for item in extract_list_like_components(text, 20):
            if any(k in item for k in ["诊断", "可诊断", "标准", "阳性", "升高", "降低", "异常", "厚度", "压差", "心电图", "肌钙蛋白"]):
                candidates.append(
                    {
                        "node_type": "DiagnosisCriteriaComponent",
                        "canonical_name": item,
                        "matched_text": item,
                        "standard_code": "",
                        "confidence": "rule_diagnostic_component",
                        "fragment": item,
                    }
                )
    elif slot == "differential_diagnosis":
        for item in extract_list_like_components(text, 20):
            if any(k in item for k in ["鉴别", "需与", "排除", "冠心病", "心包炎", "肺栓塞", "夹层", "心肌炎", "瓣膜", "高血压", "运动员"]):
                name = re.sub(r"^(需与|需要与|应与|尚需排除)", "", item)
                candidates.append(
                    {
                        "node_type": "DifferentialDiagnosis",
                        "canonical_name": name[:60],
                        "matched_text": item,
                        "standard_code": "",
                        "confidence": "rule_differential",
                        "fragment": item,
                    }
                )
    elif slot in {"etiology", "pathogenesis", "epidemiology", "prognosis", "follow_up", "prevention"}:
        node_type = NODE_TYPE_BY_SLOT.get(slot, "ClinicalConcept")
        for item in extract_list_like_components(text, 10):
            if len(item) >= 8:
                candidates.append(
                    {
                        "node_type": node_type,
                        "canonical_name": item[:80],
                        "matched_text": item[:80],
                        "standard_code": "",
                        "confidence": f"rule_{slot}",
                        "fragment": item[:120],
                    }
                )
    return candidates


def build_candidates(evidence_rows: List[dict], dict_dir: Path, batch_id: str) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    by_type = build_term_index(dict_dir)
    nodes_by_key: Dict[Tuple[str, str, str], dict] = {}
    rels_by_key: Dict[Tuple[str, str, str], dict] = {}
    evidence_links = []
    audit = []

    for ev in evidence_rows:
        subject = ev["subject_name"]
        parent = ev.get("subject_parent", "")
        subject_id = stable_id(f"{batch_id}-SUBJECT", parent, subject)
        slot = ev.get("skeleton_slot", "")
        text = normalize_text(ev.get("text_excerpt", ""))

        if slot == "treatment" and is_false_treatment(text[:120]):
            audit.append(
                {
                    "subject_name": subject,
                    "skeleton_slot": slot,
                    "evidence_id": ev["evidence_id"],
                    "status": "blocked_false_treatment_context",
                    "candidate_count": 0,
                    "note": "疑似治疗不当/诱因语境，未抽治疗实体",
                }
            )
            continue

        candidates = []
        candidates.extend(infer_generic_candidates(ev))

        allowed = allowed_match_types(slot)
        if allowed:
            for hit in match_terms(text, by_type, allowed):
                # Lab terms in exam slot should keep LabTest node type if matched by builtin/dict.
                hit["fragment"] = ""
                candidates.append(hit)

        # If C1 slot is clinical_manifestation, split symptom/sign by dictionary matches only.
        # If no candidates and text is sufficiently meaningful, keep a conservative anchor concept.
        if not candidates and slot in NODE_TYPE_BY_SLOT and len(text) >= 30:
            node_type = NODE_TYPE_BY_SLOT[slot]
            if node_type not in {"TreatmentPlan"}:
                candidates.append(
                    {
                        "node_type": node_type,
                        "canonical_name": f"{subject}-{ev.get('skeleton_slot_zh', slot)}",
                        "matched_text": ev.get("skeleton_slot_zh", slot),
                        "standard_code": "",
                        "confidence": "slot_anchor_only",
                        "fragment": text[:160],
                    }
                )

        cleaned = []
        seen = set()
        for c in candidates:
            name = normalize_text(c.get("canonical_name", ""))
            node_type = c.get("node_type", "")
            if not name or name in STOP_TERMS or len(name) > 120:
                continue
            key = (node_type, name)
            if key in seen:
                continue
            seen.add(key)
            c["canonical_name"] = name
            cleaned.append(c)

        for c in cleaned:
            node_type = c["node_type"]
            name = c["canonical_name"]
            node_key = (node_type, name, c.get("standard_code", ""))
            node_id = stable_id(f"{batch_id}-{node_type.upper()}", node_type, name, c.get("standard_code", ""))
            if node_key not in nodes_by_key:
                nodes_by_key[node_key] = {
                    "node_id": node_id,
                    "node_type": node_type,
                    "name": name,
                    "standard_code": c.get("standard_code", ""),
                    "aliases": [],
                    "source_layer": "textbook_skeleton_structured_candidate",
                    "batch_id": batch_id,
                    "clinical_use_status": "not_for_formal_cdss_until_reviewed",
                    "import_status": "local_candidate_not_imported",
                }
            rel_type = REL_TYPE_BY_NODE_TYPE.get(node_type, f"HAS_{node_type.upper()}")
            rel_key = (subject_id, node_id, rel_type)
            if rel_key not in rels_by_key:
                rels_by_key[rel_key] = {
                    "rel_id": stable_id(f"{batch_id}-REL", *rel_key),
                    "source_id": subject_id,
                    "source_name": subject,
                    "target_id": node_id,
                    "target_name": name,
                    "target_type": node_type,
                    "rel_type": rel_type,
                    "batch_id": batch_id,
                    "evidence_ids": [],
                    "confidence": c.get("confidence", ""),
                    "import_status": "local_candidate_not_imported",
                }
            rels_by_key[rel_key]["evidence_ids"].append(ev["evidence_id"])
            evidence_links.append(
                {
                    "evidence_id": ev["evidence_id"],
                    "node_id": node_id,
                    "node_type": node_type,
                    "node_name": name,
                    "matched_text": c.get("matched_text", ""),
                    "fragment": c.get("fragment") or text[:180],
                    "source_section_path": ev.get("source_section_path", ""),
                    "docx_para_start": ev.get("docx_para_start", ""),
                    "docx_para_end": ev.get("docx_para_end", ""),
                    "pdf_page_approx": ev.get("pdf_page_approx", ""),
                    "confidence": c.get("confidence", ""),
                }
            )

        audit.append(
            {
                "subject_name": subject,
                "skeleton_slot": slot,
                "evidence_id": ev["evidence_id"],
                "status": "ok_with_candidates" if cleaned else "no_structured_candidate",
                "candidate_count": len(cleaned),
                "note": "",
            }
        )

    # Deduplicate evidence IDs on relations.
    for rel in rels_by_key.values():
        rel["evidence_ids"] = list(dict.fromkeys(rel["evidence_ids"]))

    return list(nodes_by_key.values()), list(rels_by_key.values()), evidence_links, audit


def write_jsonl(path: Path, rows: List[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_report(out_dir: Path, nodes: List[dict], rels: List[dict], links: List[dict], audit: List[dict], summary: dict) -> None:
    node_counter = Counter(n["node_type"] for n in nodes)
    audit_counter = Counter(a["status"] for a in audit)
    md = []
    md.append("# 阶段C2执行报告：教材骨架结构化候选抽取")
    md.append("")
    md.append(f"生成时间：{summary['generated_at']}")
    md.append("")
    md.append("## 1. 结论")
    md.append("")
    md.append("- 已从 C1 原文锚点抽取结构化候选实体和关系。")
    md.append("- 本阶段仍然没有写 Neo4j。")
    md.append("- 产物是 `local_candidate_not_imported`，必须经过 G1 深审计后才能进入 delta。")
    md.append("- 已加入反误分规则：疑似“治疗不当/诱因语境”的文本不会抽为治疗方案。")
    md.append("")
    md.append("## 2. 总量")
    md.append("")
    md.append("| 指标 | 数值 |")
    md.append("|---|---:|")
    md.append(f"| 候选实体 | {len(nodes)} |")
    md.append(f"| 候选关系 | {len(rels)} |")
    md.append(f"| 证据-实体链接 | {len(links)} |")
    md.append(f"| 审计行 | {len(audit)} |")
    md.append("")
    md.append("## 3. 候选实体类型分布")
    md.append("")
    md.append("| 实体类型 | 数量 |")
    md.append("|---|---:|")
    for node_type, count in node_counter.most_common():
        md.append(f"| {node_type} | {count} |")
    md.append("")
    md.append("## 4. 审计状态")
    md.append("")
    md.append("| 状态 | 数量 |")
    md.append("|---|---:|")
    for status, count in audit_counter.most_common():
        md.append(f"| {status} | {count} |")
    md.append("")
    md.append("## 5. 下一步")
    md.append("")
    md.append("进入 G1 深审计：检查每个 Disease/章节是否至少具备定义、临床表现、检查、诊断/鉴别、治疗相关结构化实体；不合格项进入人工复核或二次抽取。")
    (out_dir / "阶段C2_执行报告_20260709.md").write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structured candidates from textbook skeleton anchors.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--dict-dir", required=True, type=Path)
    parser.add_argument("--batch-id", default="CARD-SKELETON-20260709")
    parser.add_argument("--input", default="阶段C1_教材骨架原文锚点_evidence_20260709.jsonl")
    args = parser.parse_args()

    input_path = args.out_dir / args.input
    evidence_rows = load_jsonl(input_path)
    nodes, rels, links, audit = build_candidates(evidence_rows, args.dict_dir, args.batch_id)

    write_jsonl(args.out_dir / "阶段C2_结构化候选_nodes_20260709.jsonl", nodes)
    write_jsonl(args.out_dir / "阶段C2_结构化候选_relations_20260709.jsonl", rels)
    write_jsonl(args.out_dir / "阶段C2_结构化候选_evidence_links_20260709.jsonl", links)
    write_csv(args.out_dir / "阶段C2_结构化候选审计_20260709.csv", audit)

    summary = {
        "batch_id": args.batch_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input": str(input_path),
        "dict_dir": str(args.dict_dir),
        "evidence_anchor_count": len(evidence_rows),
        "candidate_node_count": len(nodes),
        "candidate_relation_count": len(rels),
        "evidence_link_count": len(links),
        "audit_count": len(audit),
        "not_imported_to_neo4j": True,
        "import_status": "local_candidate_not_imported",
        "next_required": "G1_deep_audit_then_curated_delta",
    }
    (args.out_dir / "阶段C2_结构化候选_summary_20260709.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    build_report(args.out_dir, nodes, rels, links, audit, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
