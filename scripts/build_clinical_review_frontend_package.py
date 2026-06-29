from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DECISION_OPTIONS = {
    "clinical_use_decision": ["可试用", "仅参考", "需修改", "禁用"],
    "pharmacist_decision": ["通过", "需修改", "禁用"],
    "detail_decision": ["approve", "revise", "reject"],
}

DECISION_TEMPLATE_COLUMNS = [
    "review_level",
    "review_id",
    "batch_id",
    "disease_code",
    "disease_name",
    "scenario_type",
    "relation_type",
    "target_type",
    "relation_id",
    "target_code",
    "target_name",
    "review_decision",
    "overall_risk_level",
    "reviewer_name",
    "reviewer_role",
    "reviewed_at",
    "expert_comment",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")


def safe_id_part(value: str) -> str:
    return str(value or "").strip().replace(" ", "_").replace("/", "_").replace("\\", "_") or "NA"


def disease_review_id(row: dict[str, str]) -> str:
    return f"DISEASE-{safe_id_part(row.get('batch_id', ''))}-{safe_id_part(row.get('disease_code', ''))}"


def scenario_review_id(row: dict[str, str]) -> str:
    return (
        "SCENARIO-"
        f"{safe_id_part(row.get('batch_id', ''))}-"
        f"{safe_id_part(row.get('disease_code', ''))}-"
        f"{safe_id_part(row.get('relation_type', ''))}-"
        f"{safe_id_part(row.get('target_type', ''))}"
    )


def pharmacist_review_id(row: dict[str, str]) -> str:
    return f"PHARM-{safe_id_part(row.get('batch_id', ''))}-{safe_id_part(row.get('relation_id', ''))}-{safe_id_part(row.get('target_code', ''))}"


def detail_review_id(row: dict[str, str]) -> str:
    return f"DETAIL-{safe_id_part(row.get('batch_id', ''))}-{safe_id_part(row.get('relation_id', ''))}"


def index_scenario_by_context(scenario_cards: list[dict[str, str]]) -> dict[tuple[str, str, str, str], str]:
    return {
        (
            row.get("batch_id", ""),
            row.get("disease_code", ""),
            row.get("relation_type", ""),
            row.get("target_type", ""),
        ): scenario_review_id(row)
        for row in scenario_cards
    }


def attach_review_ids(
    disease_rows: list[dict[str, str]],
    scenario_rows: list[dict[str, str]],
    pharmacist_rows: list[dict[str, str]],
    detail_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    diseases = [{**row, "review_id": disease_review_id(row)} for row in disease_rows]
    scenarios = [{**row, "review_id": scenario_review_id(row), "parent_review_id": disease_review_id(row)} for row in scenario_rows]
    scenario_index = index_scenario_by_context(scenario_rows)
    pharmacists = [
        {
            **row,
            "review_id": pharmacist_review_id(row),
            "parent_review_id": scenario_index.get(
                (row.get("batch_id", ""), row.get("disease_code", ""), row.get("relation_type", ""), "Medication"),
                disease_review_id(row),
            ),
        }
        for row in pharmacist_rows
    ]
    details: list[dict[str, Any]] = []
    disease_by_batch_and_relation: dict[tuple[str, str], dict[str, str]] = {
        (row.get("batch_id", ""), row.get("relation_id", "")): row for row in pharmacist_rows
    }
    for row in detail_rows:
        context = disease_by_batch_and_relation.get((row.get("batch_id", ""), row.get("relation_id", "")), {})
        disease_code = context.get("disease_code", "")
        disease_name = context.get("disease_name", "")
        target_type = row.get("target_type", "")
        scenario_id = scenario_index.get(
            (row.get("batch_id", ""), disease_code, row.get("relation_type", ""), target_type),
            "",
        )
        details.append(
            {
                **row,
                "review_id": detail_review_id(row),
                "disease_code": disease_code,
                "disease_name": disease_name,
                "scenario_review_id": scenario_id,
            }
        )
    return diseases, scenarios, pharmacists, details


def decision_template_rows(
    diseases: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    pharmacists: list[dict[str, Any]],
    details: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for level, items in (
        ("disease", diseases),
        ("scenario", scenarios),
        ("pharmacist", pharmacists),
        ("detail", details),
    ):
        for item in items:
            rows.append(
                {
                    "review_level": level,
                    "review_id": item.get("review_id", ""),
                    "batch_id": item.get("batch_id", ""),
                    "disease_code": item.get("disease_code", ""),
                    "disease_name": item.get("disease_name", ""),
                    "scenario_type": item.get("scenario_type", ""),
                    "relation_type": item.get("relation_type", ""),
                    "target_type": item.get("target_type", ""),
                    "relation_id": item.get("relation_id", ""),
                    "target_code": item.get("target_code", ""),
                    "target_name": item.get("target_name", ""),
                }
            )
    return rows


def build_frontend_package(effect_review_dir: Path, detail_review_dir: Path, out_dir: Path) -> dict[str, Any]:
    disease_rows = read_csv(effect_review_dir / "01_疾病级使用效果审核表.csv")
    scenario_rows = read_csv(effect_review_dir / "02_场景级推荐审核卡.csv")
    pharmacist_rows = read_csv(effect_review_dir / "03_药师专项审核清单.csv")
    detail_rows = read_csv(detail_review_dir / "clinical_review_items.csv")
    effect_summary = read_json(effect_review_dir / "clinical_effect_review_summary.json")
    detail_summary = read_json(detail_review_dir / "clinical_review_summary.json")
    diseases, scenarios, pharmacists, details = attach_review_ids(disease_rows, scenario_rows, pharmacist_rows, detail_rows)

    payload = {
        "schema_version": "clinical-review-frontend-v1",
        "review_scope": "CAD_CM_required_closure_and_pending_cdss_review",
        "decision_options": DECISION_OPTIONS,
        "summary": {
            "disease_review_count": len(diseases),
            "scenario_card_count": len(scenarios),
            "pharmacist_item_count": len(pharmacists),
            "detail_item_count": len(details),
            "source_effect_summary": effect_summary,
            "source_detail_summary": detail_summary,
        },
        "disease_reviews": diseases,
        "scenario_cards": scenarios,
        "pharmacist_items": pharmacists,
        "detail_items": details,
        "rules": [
            "Trae 前端只允许导出审核结果文件，不得直接写 Neo4j。",
            "疾病级/场景级审核确认临床使用效果；detail 级 approve 才能进入 Codex 回写脚本。",
            "formal_cdss_ready 不允许由前端置为 true。",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "clinical_review_frontend_data.json", payload)
    write_csv(
        out_dir / "clinical_review_decision_export_template.csv",
        decision_template_rows(diseases, scenarios, pharmacists, details),
        DECISION_TEMPLATE_COLUMNS,
    )
    manifest = {
        "schema_version": payload["schema_version"],
        "frontend_data": str(out_dir / "clinical_review_frontend_data.json"),
        "decision_export_template": str(out_dir / "clinical_review_decision_export_template.csv"),
        "disease_review_count": len(diseases),
        "scenario_card_count": len(scenarios),
        "pharmacist_item_count": len(pharmacists),
        "detail_item_count": len(details),
        "trae_write_boundary": "export_file_only_no_neo4j_no_jsonl_direct_write",
    }
    write_json(out_dir / "clinical_review_frontend_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build frontend-ready clinical review JSON package for Trae review pages.")
    parser.add_argument("--effect-review-dir", type=Path, required=True)
    parser.add_argument("--detail-review-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = build_frontend_package(args.effect_review_dir, args.detail_review_dir, args.out_dir)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
