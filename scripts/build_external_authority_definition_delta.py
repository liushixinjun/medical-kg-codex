from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威")
SRC = ROOT / "02_结构化候选_structured_candidates" / "心血管内科+剩余10条+外部权威人工候选定义+20260708.csv"
OUT = ROOT / "03_入库delta_import_delta"
TODAY = "20260708"


def main() -> int:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    OUT.mkdir(parents=True, exist_ok=True)
    nodes_path = OUT / f"delta_external_authority_definition_yes_{TODAY}.jsonl"
    audit_path = OUT / f"delta_external_authority_definition_yes_audit_{TODAY}.csv"
    rows: list[dict[str, str]] = []
    with SRC.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("can_import_as_definition") == "yes":
                rows.append(row)

    with nodes_path.open("w", encoding="utf-8", newline="") as f:
        for row in rows:
            node = {
                "code": row["disease_code"],
                "name": row["disease_name"],
                "entityType": "Disease",
                "definition": row["candidate_definition_zh"],
                "description": row["candidate_definition_zh"],
                "definition_source_type": "external_authoritative_source",
                "definition_source_name": row["source_name"],
                "definition_source_section_path": row["evidence_location"],
                "definition_authority_level": row["authority_level"],
                "definition_download_file": row["download_file"],
                "definition_source_basis": row["source_basis"],
                "definition_skeleton_slot": "overview",
                "definition_knowledge_layer": "external_authority_core",
                "definition_import_decision": row["import_decision"],
                "definition_updated_at": generated_at,
                "external_authority_review_status": "machine_curated_source_backed",
                "formal_cdss_ready": False,
            }
            f.write(json.dumps(node, ensure_ascii=False, separators=(",", ":")) + "\n")

    audit_fields = [
        "disease_code",
        "disease_name",
        "candidate_definition_zh",
        "source_name",
        "download_file",
        "evidence_location",
        "source_basis",
        "import_decision",
    ]
    with audit_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=audit_fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in audit_fields})

    summary = {
        "generated_at": generated_at,
        "source": str(SRC),
        "nodes_jsonl": str(nodes_path),
        "audit_csv": str(audit_path),
        "node_count": len(rows),
        "codes": [row["disease_code"] for row in rows],
        "excluded_conditional_or_no_count": sum(1 for _ in csv.DictReader(SRC.open("r", encoding="utf-8-sig", newline=""))) - len(rows),
    }
    summary_path = OUT / f"delta_external_authority_definition_yes_summary_{TODAY}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
