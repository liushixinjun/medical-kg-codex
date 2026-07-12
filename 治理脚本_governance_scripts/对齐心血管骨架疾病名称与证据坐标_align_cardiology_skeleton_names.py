# -*- coding: utf-8 -*-
"""心血管内科教材骨架：疾病名称与证据坐标对齐审计。

只读读取 D6 教材骨架矩阵和全书回捞候选索引，生成：
1. 疾病名称标准化映射表；
2. 回捞候选证据质量与坐标审计；
3. 可归并候选摘要与阻断原因。

本脚本不连接 Neo4j、不写数据库、不修改历史批次产物。
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = "20260712"
OUT_DIR = ROOT / "骨架质量闭环_skeleton_quality_loop" / f"{RUN_DATE}_心血管内科疾病名称与证据坐标对齐"
CURRENT_BASELINE_DATE = "2026-07-09"

FOUNDATION_ROOT = ROOT / "心血管内科文献集合" / "00_foundation_skeleton"
FULL_DIR = (
    ROOT
    / "心血管内科文献集合"
    / "00_教材骨架库_foundation_skeleton"
    / "心血管内科全章节骨架扩展_CARD-SKELETON-FULL-20260709"
)

D6_MATRIX = FULL_DIR / "阶段D6_来源感知G1全章节审计矩阵_20260709.csv"
BACKFILL_INDEX = FOUNDATION_ROOT / "04_evidence_and_extraction" / "textbook_fullbook_backfill_index.csv"

OUT_NAME_MAP = OUT_DIR / f"疾病名称标准化映射表_{RUN_DATE}.csv"
OUT_REVIEW_MAP = OUT_DIR / f"需人工确认疾病映射_{RUN_DATE}.csv"
OUT_EVIDENCE_AUDIT = OUT_DIR / f"证据文本质量与坐标审计_{RUN_DATE}.csv"
OUT_MERGEABLE = OUT_DIR / f"可归并候选摘要_{RUN_DATE}.csv"
OUT_BLOCKED = OUT_DIR / f"阻断候选原因清单_{RUN_DATE}.csv"
OUT_SUMMARY = OUT_DIR / f"疾病名称与章节坐标对齐_summary_{RUN_DATE}.json"
OUT_REPORT = OUT_DIR / f"疾病名称与章节坐标对齐报告_{RUN_DATE}.md"


ENTITY_SLOT = {
    "Definition": "definition",
    "DefinitionComponent": "definition",
    "Etiology": "etiology_pathogenesis",
    "Pathophysiology": "etiology_pathogenesis",
    "Epidemiology": "etiology_pathogenesis",
    "Symptom": "clinical_manifestation",
    "Sign": "clinical_manifestation",
    "ClinicalManifestation": "clinical_manifestation",
    "RiskFactor": "risk_factor",
    "Complication": "complication",
    "Exam": "exam_lab",
    "LabTest": "exam_lab",
    "ExamIndicator": "exam_lab",
    "ThresholdRule": "exam_lab",
    "DiagnosisCriteria": "diagnosis_differential",
    "DiagnosisCriteriaComponent": "diagnosis_differential",
    "DifferentialDiagnosis": "diagnosis_differential",
    "RiskStratification": "classification_risk",
    "DiseaseClassification": "classification_risk",
    "TreatmentPlan": "treatment",
    "Medication": "treatment",
    "Procedure": "treatment",
    "FollowUp": "follow_up_prognosis",
    "Prognosis": "follow_up_prognosis",
    "Prevention": "follow_up_prognosis",
    "Contraindication": "treatment",
}

NOISE_KEYWORDS = [
    "从事教学工作",
    "发表论文",
    "科学技术进步奖",
    "主编",
    "副主编",
    "编委",
    "ISBN",
    "版权",
    "前言",
    "序言",
    "目录",
    "出版社",
    "参编",
    "审稿",
    "致谢",
    "基金",
    "获奖",
]

CLINICAL_KEYWORDS = [
    "诊断",
    "治疗",
    "临床表现",
    "症状",
    "体征",
    "检查",
    "实验室",
    "危险因素",
    "并发症",
    "预后",
    "随访",
    "病因",
    "发病机制",
    "分型",
    "分类",
    "定义",
    "鉴别",
    "推荐",
    "禁忌",
]

MANUAL_SYNONYM_TARGETS = {
    "ST段抬高型心肌梗死": "急性 ST 段抬高型心肌梗死",
    "非ST段抬高型心肌梗死": "不稳定型心绞痛和非 ST 段抬高型心肌梗死",
    "不稳定型心绞痛": "不稳定型心绞痛和非 ST 段抬高型心肌梗死",
    "慢性冠脉综合征": "慢性冠状动脉综合征",
    "冠状动脉粥样硬化性心脏病": "冠状动脉粥样硬化性心脏病概述",
    "心脏骤停": "心脏骤停与心脏性猝死",
    "心脏性猝死": "心脏骤停与心脏性猝死",
}

MANUAL_REVIEW_TARGETS = {
    "急性心肌梗死": ("急性冠脉综合征", "泛称需按 STEMI/NSTEMI/ACS 章节拆分，不能直接并入单一具体疾病"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        seen = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def safe_int(value: str | None) -> int | None:
    try:
        return int(value or "")
    except Exception:
        return None


def file_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if path.exists() else ""


def artifact_scope(path: Path) -> str:
    if not path.exists():
        return "missing"
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    baseline = datetime.fromisoformat(CURRENT_BASELINE_DATE)
    if mtime.date() >= baseline.date():
        return "当前骨架基线产物"
    return "历史候选池/旧实例产物"


def normalize_name(value: str) -> str:
    s = unicodedata.normalize("NFKC", value or "")
    s = re.sub(r"\s+", "", s)
    s = s.replace("冠脉", "冠状动脉")
    s = s.replace("ST段", "ST段")
    s = s.replace("QT间期", "QT间期")
    s = s.replace("概述", "")
    s = s.replace("总论", "")
    s = s.replace("疾病", "")
    s = s.replace("病", "病")
    s = s.upper()
    return s


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


def load_d6_subjects() -> dict[str, dict[str, Any]]:
    rows = {}
    for row in read_csv(D6_MATRIX):
        name = row.get("subject_name", "").strip()
        if not name:
            continue
        start = safe_int(row.get("docx_start_para"))
        end = safe_int(row.get("docx_end_para"))
        rows[name] = {
            "subject_name": name,
            "parent": row.get("parent", ""),
            "level": row.get("level", ""),
            "subject_kind": row.get("subject_kind", ""),
            "status": row.get("status", ""),
            "docx_start_para": start,
            "docx_end_para": end,
            "source_available_groups": row.get("source_available_groups", ""),
            "present_candidate_groups": row.get("present_candidate_groups", ""),
        }
    return rows


def collect_backfill_disease_stats() -> tuple[dict[str, Counter], Counter]:
    disease_stats: dict[str, Counter] = defaultdict(Counter)
    total = Counter()
    with BACKFILL_INDEX.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            disease = row.get("disease_name", "").strip()
            etype = row.get("entityType", "").strip()
            disease_stats[disease]["row_count"] += 1
            disease_stats[disease][f"entityType::{etype}"] += 1
            total["row_count"] += 1
    return disease_stats, total


def best_d6_candidates(name: str, d6_subjects: dict[str, dict[str, Any]]) -> list[tuple[str, float]]:
    scored: list[tuple[str, float]] = []
    n = normalize_name(name)
    for target in d6_subjects:
        t = normalize_name(target)
        score = similarity(name, target)
        contains = n and t and (n in t or t in n)
        shorter = min(len(n), len(t)) if n and t else 0
        longer = max(len(n), len(t)) if n and t else 1
        # 避免“急性心肌梗死”因包含“心肌”而误配到“心肌疾病”这类短泛化节点。
        safe_containment = contains and shorter >= 4 and (shorter / longer) >= 0.6
        if safe_containment:
            score = max(score, 0.88)
        scored.append((target, score))
    return sorted(scored, key=lambda x: x[1], reverse=True)[:5]


def decide_mapping(name: str, d6_subjects: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if name in d6_subjects:
        return {
            "source_disease_name": name,
            "target_subject_name": name,
            "mapping_type": "exact",
            "mapping_status": "可自动采用",
            "confidence": 1.0,
            "review_reason": "",
            "candidate_targets": name,
        }

    normalized_to_targets: dict[str, list[str]] = defaultdict(list)
    for target in d6_subjects:
        normalized_to_targets[normalize_name(target)].append(target)
    normalized_matches = normalized_to_targets.get(normalize_name(name), [])
    if len(normalized_matches) == 1:
        target = normalized_matches[0]
        return {
            "source_disease_name": name,
            "target_subject_name": target,
            "mapping_type": "normalized_equal",
            "mapping_status": "可自动采用",
            "confidence": 0.98,
            "review_reason": "去空格、简称规范化后完全一致",
            "candidate_targets": target,
        }

    manual_target = MANUAL_SYNONYM_TARGETS.get(name)
    if manual_target and manual_target in d6_subjects:
        return {
            "source_disease_name": name,
            "target_subject_name": manual_target,
            "mapping_type": "manual_synonym_rule",
            "mapping_status": "可自动采用",
            "confidence": 0.95,
            "review_reason": "内置心血管常见章节合并/简称规则",
            "candidate_targets": manual_target,
        }

    review_rule = MANUAL_REVIEW_TARGETS.get(name)
    if review_rule and review_rule[0] in d6_subjects:
        return {
            "source_disease_name": name,
            "target_subject_name": review_rule[0],
            "mapping_type": "manual_review_rule",
            "mapping_status": "需人工确认",
            "confidence": 0.9,
            "review_reason": review_rule[1],
            "candidate_targets": review_rule[0],
        }

    candidates = best_d6_candidates(name, d6_subjects)
    best_name, best_score = candidates[0]
    if best_score >= 0.88:
        return {
            "source_disease_name": name,
            "target_subject_name": best_name,
            "mapping_type": "fuzzy_or_containment",
            "mapping_status": "需人工确认",
            "confidence": round(best_score, 4),
            "review_reason": "名称相似或包含关系成立，但不是明确同义词",
            "candidate_targets": "；".join(f"{n}:{s:.3f}" for n, s in candidates),
        }

    return {
        "source_disease_name": name,
        "target_subject_name": "",
        "mapping_type": "no_candidate",
        "mapping_status": "暂不采用",
        "confidence": round(best_score, 4),
        "review_reason": "未找到足够可靠的 D6 骨架章节/疾病名称",
        "candidate_targets": "；".join(f"{n}:{s:.3f}" for n, s in candidates),
    }


def classify_evidence(row: dict[str, str], target_name: str) -> tuple[str, str]:
    text = row.get("evidence_text", "") or ""
    entity = row.get("entity_name", "") or ""
    source_name = row.get("disease_name", "") or ""

    if any(k in text for k in NOISE_KEYWORDS):
        return "疑似非正文噪声", "命中作者简介/版权/目录/前言等非临床正文关键词"

    has_entity = bool(entity and entity in text)
    has_source_disease = bool(source_name and source_name in text)
    has_target_disease = bool(target_name and target_name in text)
    has_clinical_keyword = any(k in text for k in CLINICAL_KEYWORDS)

    if has_entity and (has_source_disease or has_target_disease) and has_clinical_keyword:
        return "强证据文本", "同时包含疾病名、实体名和临床语义关键词"
    if has_entity and has_clinical_keyword:
        return "中等证据文本", "包含实体名和临床语义关键词，但疾病名未直接出现"
    if has_entity:
        return "弱证据文本", "仅包含实体名，缺少疾病名或临床上下文"
    return "证据文本不足", "原文片段未包含实体名，不能支撑归并"


def preview_text(value: str, limit: int = 180) -> str:
    """生成用于 CSV 审计的文本预览，避免截断后留下尾部空白。"""

    return (value or "").strip()[:limit].strip()


def in_docx_range(line_number: int | None, d6_info: dict[str, Any] | None) -> bool:
    if line_number is None or not d6_info:
        return False
    start = d6_info.get("docx_start_para")
    end = d6_info.get("docx_end_para")
    return bool(start is not None and end is not None and start <= line_number <= end)


def main() -> int:
    d6_subjects = load_d6_subjects()
    backfill_stats, total_counter = collect_backfill_disease_stats()

    name_map_rows: list[dict[str, Any]] = []
    name_map: dict[str, dict[str, Any]] = {}
    for name in sorted(backfill_stats):
        decision = decide_mapping(name, d6_subjects)
        target_info = d6_subjects.get(decision["target_subject_name"], {})
        etype_counts = {
            k.replace("entityType::", ""): v
            for k, v in backfill_stats[name].items()
            if k.startswith("entityType::")
        }
        row = {
            **decision,
            "source_artifact_scope": artifact_scope(BACKFILL_INDEX),
            "source_artifact_mtime": file_mtime(BACKFILL_INDEX),
            "target_artifact_scope": artifact_scope(D6_MATRIX),
            "target_artifact_mtime": file_mtime(D6_MATRIX),
            "source_row_count": backfill_stats[name]["row_count"],
            "source_entity_type_counts": json.dumps(etype_counts, ensure_ascii=False, sort_keys=True),
            "target_parent": target_info.get("parent", ""),
            "target_subject_kind": target_info.get("subject_kind", ""),
            "target_docx_start_para": target_info.get("docx_start_para", ""),
            "target_docx_end_para": target_info.get("docx_end_para", ""),
        }
        name_map_rows.append(row)
        name_map[name] = row

    evidence_rows: list[dict[str, Any]] = []
    aggregate: dict[tuple[str, str, str], dict[str, Any]] = {}
    decision_counter: Counter = Counter()
    evidence_quality_counter: Counter = Counter()
    mapping_status_counter: Counter = Counter(row["mapping_status"] for row in name_map_rows)
    line_range_true = 0
    line_range_false = 0

    with BACKFILL_INDEX.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            source_name = row.get("disease_name", "").strip()
            mapping = name_map.get(source_name, {})
            target_name = mapping.get("target_subject_name", "")
            target_info = d6_subjects.get(target_name, {})
            line_number = safe_int(row.get("line_number"))
            line_ok = in_docx_range(line_number, target_info)
            if line_ok:
                line_range_true += 1
            else:
                line_range_false += 1

            evidence_quality, evidence_reason = classify_evidence(row, target_name)
            evidence_quality_counter[evidence_quality] += 1
            slot = ENTITY_SLOT.get(row.get("entityType", ""), "未映射槽位")

            if mapping.get("mapping_status") == "可自动采用" and evidence_quality in {"强证据文本", "中等证据文本"}:
                merge_decision = "可进入抽样复核后归并"
            elif mapping.get("mapping_status") == "可自动采用" and evidence_quality in {"弱证据文本", "证据文本不足"}:
                merge_decision = "阻断_证据文本不足"
            elif mapping.get("mapping_status") == "可自动采用" and evidence_quality == "疑似非正文噪声":
                merge_decision = "阻断_疑似非正文噪声"
            elif mapping.get("mapping_status") == "需人工确认":
                merge_decision = "阻断_疾病映射需人工确认"
            else:
                merge_decision = "阻断_无可靠骨架疾病映射"
            decision_counter[merge_decision] += 1

            audit_row = {
                "issue_scope": "历史候选池归并风险，不作为当前骨架缺陷",
                "source_artifact_scope": artifact_scope(BACKFILL_INDEX),
                "target_artifact_scope": artifact_scope(D6_MATRIX),
                "source_disease_name": source_name,
                "target_subject_name": target_name,
                "mapping_status": mapping.get("mapping_status", ""),
                "mapping_type": mapping.get("mapping_type", ""),
                "entityType": row.get("entityType", ""),
                "slot": slot,
                "entity_name": row.get("entity_name", ""),
                "entity_code": row.get("entity_code", ""),
                "relationType": row.get("relationType", ""),
                "line_number": row.get("line_number", ""),
                "target_docx_start_para": target_info.get("docx_start_para", ""),
                "target_docx_end_para": target_info.get("docx_end_para", ""),
                "line_in_target_docx_range": "yes" if line_ok else "no",
                "evidence_quality": evidence_quality,
                "evidence_reason": evidence_reason,
                "merge_decision": merge_decision,
                "evidence_code": row.get("evidence_code", ""),
                "evidence_text_preview": preview_text(row.get("evidence_text", ""), 180),
            }
            evidence_rows.append(audit_row)

            key = (source_name, target_name, slot)
            bucket = aggregate.setdefault(
                key,
                {
                    "source_disease_name": source_name,
                    "target_subject_name": target_name,
                    "slot": slot,
                    "mapping_status": mapping.get("mapping_status", ""),
                    "mapping_type": mapping.get("mapping_type", ""),
                    "total_rows": 0,
                    "mergeable_rows": 0,
                    "blocked_rows": 0,
                    "strong_rows": 0,
                    "medium_rows": 0,
                    "noise_rows": 0,
                    "unique_entities": set(),
                    "sample_entities": [],
                    "sample_evidence": [],
                    "decision_counter": Counter(),
                },
            )
            bucket["total_rows"] += 1
            bucket["unique_entities"].add(row.get("entity_name", ""))
            bucket["decision_counter"][merge_decision] += 1
            if merge_decision == "可进入抽样复核后归并":
                bucket["mergeable_rows"] += 1
                if len(bucket["sample_entities"]) < 20:
                    bucket["sample_entities"].append(row.get("entity_name", ""))
                if len(bucket["sample_evidence"]) < 3:
                    bucket["sample_evidence"].append(preview_text(row.get("evidence_text", ""), 100))
            else:
                bucket["blocked_rows"] += 1
            if evidence_quality == "强证据文本":
                bucket["strong_rows"] += 1
            elif evidence_quality == "中等证据文本":
                bucket["medium_rows"] += 1
            elif evidence_quality == "疑似非正文噪声":
                bucket["noise_rows"] += 1

    mergeable_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    for bucket in aggregate.values():
        out = {
            "issue_scope": "历史候选池归并风险，不作为当前骨架缺陷",
            "source_disease_name": bucket["source_disease_name"],
            "target_subject_name": bucket["target_subject_name"],
            "slot": bucket["slot"],
            "mapping_status": bucket["mapping_status"],
            "mapping_type": bucket["mapping_type"],
            "total_rows": bucket["total_rows"],
            "mergeable_rows": bucket["mergeable_rows"],
            "blocked_rows": bucket["blocked_rows"],
            "strong_rows": bucket["strong_rows"],
            "medium_rows": bucket["medium_rows"],
            "noise_rows": bucket["noise_rows"],
            "unique_entity_count": len([x for x in bucket["unique_entities"] if x]),
            "sample_entities": "；".join([x for x in bucket["sample_entities"] if x][:20]),
            "sample_evidence": " || ".join(bucket["sample_evidence"]),
            "decision_counts": json.dumps(dict(bucket["decision_counter"]), ensure_ascii=False, sort_keys=True),
        }
        if bucket["mergeable_rows"] > 0:
            mergeable_rows.append(out)
        if bucket["blocked_rows"] > 0:
            blocked_rows.append(out)

    mergeable_rows.sort(key=lambda r: (-int(r["mergeable_rows"]), r["target_subject_name"], r["slot"]))
    blocked_rows.sort(key=lambda r: (-int(r["blocked_rows"]), r["source_disease_name"], r["slot"]))

    write_csv(OUT_NAME_MAP, name_map_rows)
    write_csv(OUT_REVIEW_MAP, [r for r in name_map_rows if r["mapping_status"] != "可自动采用"])
    write_csv(OUT_EVIDENCE_AUDIT, evidence_rows)
    write_csv(OUT_MERGEABLE, mergeable_rows)
    write_csv(OUT_BLOCKED, blocked_rows)

    summary = {
        "run_date": RUN_DATE,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "neo4j_written": False,
        "input": {
            "d6_matrix": str(D6_MATRIX),
            "d6_matrix_scope": artifact_scope(D6_MATRIX),
            "d6_matrix_mtime": file_mtime(D6_MATRIX),
            "backfill_index": str(BACKFILL_INDEX),
            "backfill_index_scope": artifact_scope(BACKFILL_INDEX),
            "backfill_index_mtime": file_mtime(BACKFILL_INDEX),
        },
        "counts": {
            "d6_subject_count": len(d6_subjects),
            "backfill_disease_count": len(backfill_stats),
            "backfill_row_count": total_counter["row_count"],
            "name_mapping_status": dict(mapping_status_counter),
            "evidence_quality": dict(evidence_quality_counter),
            "merge_decision": dict(decision_counter),
            "line_in_target_docx_range_yes": line_range_true,
            "line_in_target_docx_range_no": line_range_false,
            "mergeable_slot_summary_rows": len(mergeable_rows),
            "blocked_slot_summary_rows": len(blocked_rows),
        },
        "hard_conclusion": [
            "本轮对齐审计针对 2026-06-25 历史全书回捞候选池，目的只是判断其能否安全归并到 2026-07-09 当前 D6 骨架。",
            "本轮发现的问题不作为当前 D6 骨架质量扣分；当前骨架质量仍以 2026-07-09 D6 审计和服务器复核为准。",
            "line_number 与 D6 docx_start_para/docx_end_para 不是同一可靠坐标体系，不能用 line_number 直接归并。",
            "疾病名称可通过 exact/normalized/manual_synonym_rule 先解决一批，但 fuzzy_or_containment 必须人工确认。",
            "只有 merge_decision=可进入抽样复核后归并 的候选，才能进入下一步 delta 生成；本轮不生成入库 delta。",
        ],
    }
    write_json(OUT_SUMMARY, summary)

    report = f"""# 心血管内科教材骨架疾病名称与证据坐标对齐报告（{RUN_DATE}）

## 1. 本轮边界

- 只读读取教材骨架 D6 矩阵和全书回捞候选索引。
- 不连接 Neo4j。
- 不写服务器图谱数据库。
- 不修改历史批次 nodes/relations/audit/report。
- 不生成可直接入库 delta。
- 重要口径：`textbook_fullbook_backfill_index.csv` 是 `{file_mtime(BACKFILL_INDEX)}` 的历史候选池；D6 矩阵是 `{file_mtime(D6_MATRIX)}` 的当前骨架基线。本报告只评估“旧候选池能否安全归并到当前骨架”，不把旧候选池问题算作当前骨架缺陷。

## 2. 核心结论

1. 全书回捞候选共有 `{total_counter["row_count"]}` 行，涉及 `{len(backfill_stats)}` 个来源疾病名。
2. D6 教材骨架共有 `{len(d6_subjects)}` 个章节/疾病/主题名称。
3. 疾病名称映射状态：`{dict(mapping_status_counter)}`。
4. 证据文本质量：`{dict(evidence_quality_counter)}`。
5. 合并决策：`{dict(decision_counter)}`。
6. `line_number` 与 D6 `docx_start_para/docx_end_para` 不在同一可靠坐标体系，本轮确认不能按该字段直接归并。
7. 当前骨架质量口径仍看 2026-07-09 D6 审计；旧候选池中的误映射、噪声、坐标不一致，只影响“能否复用旧候选”，不代表本周调整后骨架仍有这些错误。

## 3. 可以继续推进的内容

- `可归并候选摘要_{RUN_DATE}.csv`：仅代表“可进入抽样复核后归并”，不是正式入库文件。
- 下一步应先抽样复核这些候选的原文证据，再生成骨架深层实体 delta。

## 4. 仍需阻断的内容

- `阻断_疑似非正文噪声`：常见于作者简介、版权、目录、前言等非临床正文。
- `阻断_疾病映射需人工确认`：疾病名相似但可能属于不同章节或不同层级。
- `阻断_证据文本不足`：证据片段无法支撑“某疾病具有某实体”。

## 5. 输出文件

- `{OUT_NAME_MAP.name}`
- `{OUT_REVIEW_MAP.name}`
- `{OUT_EVIDENCE_AUDIT.name}`
- `{OUT_MERGEABLE.name}`
- `{OUT_BLOCKED.name}`
- `{OUT_SUMMARY.name}`
"""
    write_text(OUT_REPORT, report)

    print("ALIGNMENT_OK")
    print("backfill_row_count=", total_counter["row_count"])
    print("backfill_disease_count=", len(backfill_stats))
    print("d6_subject_count=", len(d6_subjects))
    print("name_mapping_status=", dict(mapping_status_counter))
    print("merge_decision=", dict(decision_counter))
    print("mergeable_slot_summary_rows=", len(mergeable_rows))
    print("neo4j_written=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
