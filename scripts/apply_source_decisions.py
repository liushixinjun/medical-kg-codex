from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def apply_decisions(batch_dir: Path, decisions_path: Path) -> dict:
    batch_dir = Path(batch_dir).resolve()
    decisions_path = Path(decisions_path).resolve()
    manifest_path = batch_dir / "01_source_manifest" / "source_documents_manifest.csv"
    config_path = batch_dir / "00_scope_and_config" / "batch_config.json"

    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    with decisions_path.open(encoding="utf-8-sig", newline="") as handle:
        decisions = {row["document_id"]: row for row in csv.DictReader(handle)}

    known_ids = {row["document_id"] for row in rows}
    unknown = sorted(set(decisions) - known_ids)
    if unknown:
        raise ValueError(f"Unknown document IDs in decisions: {unknown}")

    for row in rows:
        decision = decisions.get(row["document_id"])
        if not decision:
            continue
        action = decision["decision"].strip().lower()
        reason = decision["reason"].strip()
        primary = decision.get("primary_document_id", "").strip()
        if action == "exclude":
            row["inclusion_status"] = "excluded"
            row["inclusion_reason"] = reason
            if primary:
                row["keep_or_duplicate"] = "duplicate"
                row["duplicate_reason"] = reason
                row["dedup_group"] = f"PRIMARY-{primary}"
        elif action == "include":
            row["inclusion_status"] = "included"
            row["inclusion_reason"] = reason
            row["keep_or_duplicate"] = "keep"
            row["duplicate_reason"] = ""
        else:
            raise ValueError(f"Unsupported decision for {row['document_id']}: {action}")

    with manifest_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    config["included_file_count"] = sum(row["inclusion_status"] == "included" for row in rows)
    config["excluded_file_count"] = sum(row["inclusion_status"] == "excluded" for row in rows)
    config["source_review_decision_count"] = len(decisions)
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig"
    )
    return {
        "included_file_count": config["included_file_count"],
        "excluded_file_count": config["excluded_file_count"],
        "decision_count": len(decisions),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply reviewed source inclusion decisions.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(apply_decisions(args.batch_dir, args.decisions), ensure_ascii=False))


if __name__ == "__main__":
    main()
