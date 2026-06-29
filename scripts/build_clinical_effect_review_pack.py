from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


SCENARIO_LABELS = {
    "has_treatment_plan": "治疗方案",
    "treated_by_medication": "药物治疗",
    "includes_medication": "药物治疗",
    "treated_by_procedure": "手术/操作治疗",
    "includes_procedure": "手术/操作治疗",
    "has_follow_up": "随访管理",
    "has_clinical_pathway": "临床路径",
}

FIELD_LABELS = {
    "applicable_population": "适用人群",
    "clinical_review_status": "临床确认",
    "clinical_rule_or_clinical_pathway": "临床规则/路径",
    "exclusion_or_contraindication": "排除/禁忌",
    "recommendation_class_and_evidence_level": "推荐等级/证据等级",
    "evidence_source_chain": "证据链",
    "medication_aliases": "药物别名",
    "medication_contraindication": "药物禁忌",
    "medication_dosage": "药物剂量",
    "medication_interaction": "药物相互作用",
}

MEDICATION_REVIEW_FIELDS = {"medication_aliases", "medication_contraindication", "medication_dosage", "medication_interaction"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def split_missing_fields(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").replace("|", ";").split(";") if part.strip()]


def find_context_diseases(source_code: str, node_by_code: dict[str, dict[str, Any]], incoming: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    source = node_by_code.get(source_code, {})
    if source.get("entityType") == "Disease":
        return [source]
    found: list[dict[str, Any]] = []
    seen = {source_code}
    queue = deque([(source_code, 0)])
    while queue:
        code, depth = queue.popleft()
        if depth >= 3:
            continue
        for rel in incoming.get(code, []):
            upstream_code = str(rel.get("source_code", ""))
            if upstream_code in seen:
                continue
            seen.add(upstream_code)
            upstream = node_by_code.get(upstream_code, {})
            if upstream.get("entityType") == "Disease":
                found.append(upstream)
            else:
                queue.append((upstream_code, depth + 1))
    return found or [source or {"code": source_code, "name": source_code, "entityType": "Unknown"}]


def review_focus_for(fields: list[str]) -> str:
    labels = [FIELD_LABELS.get(field, field) for field in fields]
    if not labels:
        return "确认该场景是否可用于临床辅助推荐。"
    return "重点确认：" + "、".join(labels)


def build_effect_review_pack(batch_dirs: list[Path], out_dir: Path) -> dict[str, Any]:
    disease_counter: Counter[tuple[str, str, str]] = Counter()
    disease_scenarios: defaultdict[tuple[str, str, str], set[tuple[str, str]]] = defaultdict(set)
    scenario_items: defaultdict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    pharmacist_rows: list[dict[str, Any]] = []

    for batch_dir in batch_dirs:
        batch_id = batch_dir.name
        nodes = read_jsonl(batch_dir / "05_data_instance" / "nodes_final.jsonl")
        relations = read_jsonl(batch_dir / "05_data_instance" / "relations_final.jsonl")
        readiness_rows = read_csv(batch_dir / "06_quality_audit" / "cdss_recommendation_readiness_register.csv")
        node_by_code = {str(node.get("code", "")): node for node in nodes}
        rel_by_id = {str(rel.get("id", "")): rel for rel in relations}
        incoming: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for rel in relations:
            incoming[str(rel.get("target_code", ""))].append(rel)

        for row in readiness_rows:
            relation_id = str(row.get("relation_id", ""))
            rel = rel_by_id.get(relation_id, {})
            relation_type = str(row.get("relation_type") or rel.get("relationType") or "")
            target_code = str(row.get("target_code") or rel.get("target_code") or "")
            target = node_by_code.get(target_code, {})
            target_type = str(row.get("target_type") or target.get("entityType") or "")
            target_name = str(row.get("target_name") or target.get("name") or target_code)
            scenario_type = SCENARIO_LABELS.get(relation_type, "其他推荐")
            missing_fields = split_missing_fields(row.get("missing_fields", ""))
            context_diseases = find_context_diseases(str(row.get("source_code") or rel.get("source_code") or ""), node_by_code, incoming)
            for disease in context_diseases:
                disease_key = (batch_id, str(disease.get("code", "")), str(disease.get("name", "")))
                disease_counter[disease_key] += 1
                disease_scenarios[disease_key].add((scenario_type, relation_type))
                scenario_key = (
                    batch_id,
                    str(disease.get("code", "")),
                    str(disease.get("name", "")),
                    scenario_type,
                    relation_type,
                    target_type,
                )
                scenario_items[scenario_key].append(
                    {
                        **row,
                        "target_name": target_name,
                        "target_code": target_code,
                    }
                )
                if target_type == "Medication" or set(missing_fields) & MEDICATION_REVIEW_FIELDS:
                    pharmacist_rows.append(
                        {
                            "batch_id": batch_id,
                            "disease_code": disease.get("code", ""),
                            "disease_name": disease.get("name", ""),
                            "relation_id": relation_id,
                            "relation_type": relation_type,
                            "target_code": target_code,
                            "target_name": target_name,
                            "missing_fields": ";".join(missing_fields),
                            "review_focus": review_focus_for([field for field in missing_fields if field in MEDICATION_REVIEW_FIELDS]),
                            "pharmacist_decision": "",
                            "pharmacist_comment": "",
                        }
                    )

    disease_rows: list[dict[str, Any]] = []
    for (batch_id, disease_code, disease_name), count in sorted(disease_counter.items()):
        scenario_count = len(disease_scenarios[(batch_id, disease_code, disease_name)])
        disease_rows.append(
            {
                "batch_id": batch_id,
                "disease_code": disease_code,
                "disease_name": disease_name,
                "pending_recommendation_count": count,
                "scenario_card_count": scenario_count,
                "clinical_use_question": "从临床使用效果看，该病种图谱是否可作为辅助诊疗参考？",
                "clinical_use_decision": "",
                "overall_risk_level": "",
                "reviewer_name": "",
                "reviewer_role": "",
                "reviewed_at": "",
                "expert_comment": "",
            }
        )

    scenario_rows: list[dict[str, Any]] = []
    for key, items in sorted(scenario_items.items()):
        batch_id, disease_code, disease_name, scenario_type, relation_type, target_type = key
        field_counter: Counter[str] = Counter()
        target_names: list[str] = []
        for item in items:
            for field in split_missing_fields(item.get("missing_fields", "")):
                field_counter[field] += 1
            name = str(item.get("target_name", ""))
            if name and name not in target_names:
                target_names.append(name)
        missing_fields = sorted(field_counter)
        scenario_rows.append(
            {
                "batch_id": batch_id,
                "disease_code": disease_code,
                "disease_name": disease_name,
                "scenario_type": scenario_type,
                "relation_type": relation_type,
                "target_type": target_type,
                "pending_item_count": len(items),
                "sample_targets": "；".join(target_names[:12]),
                "missing_field_summary": "；".join(f"{FIELD_LABELS.get(field, field)}×{field_counter[field]}" for field in missing_fields),
                "review_focus": review_focus_for(missing_fields),
                "clinical_use_decision": "",
                "expert_comment": "",
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        out_dir / "01_疾病级使用效果审核表.csv",
        disease_rows,
        [
            "batch_id",
            "disease_code",
            "disease_name",
            "pending_recommendation_count",
            "scenario_card_count",
            "clinical_use_question",
            "clinical_use_decision",
            "overall_risk_level",
            "reviewer_name",
            "reviewer_role",
            "reviewed_at",
            "expert_comment",
        ],
    )
    write_csv(
        out_dir / "02_场景级推荐审核卡.csv",
        scenario_rows,
        [
            "batch_id",
            "disease_code",
            "disease_name",
            "scenario_type",
            "relation_type",
            "target_type",
            "pending_item_count",
            "sample_targets",
            "missing_field_summary",
            "review_focus",
            "clinical_use_decision",
            "expert_comment",
        ],
    )
    write_csv(
        out_dir / "03_药师专项审核清单.csv",
        pharmacist_rows,
        [
            "batch_id",
            "disease_code",
            "disease_name",
            "relation_id",
            "relation_type",
            "target_code",
            "target_name",
            "missing_fields",
            "review_focus",
            "pharmacist_decision",
            "pharmacist_comment",
        ],
    )
    md_lines = [
        "# 临床使用效果审核说明",
        "",
        "审核不要求专家逐条查看图谱关系。推荐按三层处理：",
        "",
        "1. 先看 `01_疾病级使用效果审核表.csv`：判断每个疾病样板是否可作为辅助诊疗参考。",
        "2. 再看 `02_场景级推荐审核卡.csv`：按治疗、药物、手术、随访等场景确认是否符合临床使用效果。",
        "3. 药物剂量、禁忌、相互作用交给药师查看 `03_药师专项审核清单.csv`。",
        "",
        "建议 decision 填写：可试用 / 仅参考 / 需修改 / 禁用。",
        "",
    ]
    (out_dir / "00_审核说明_先看这个.md").write_text("\n".join(md_lines), encoding="utf-8-sig")
    summary = {
        "disease_review_count": len(disease_rows),
        "scenario_card_count": len(scenario_rows),
        "pharmacist_item_count": len(pharmacist_rows),
        "out_dir": str(out_dir),
    }
    (out_dir / "clinical_effect_review_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build simplified clinical effect review package grouped by disease and scenario.")
    parser.add_argument("--batch-dir", action="append", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = build_effect_review_pack(args.batch_dir, args.out_dir)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
