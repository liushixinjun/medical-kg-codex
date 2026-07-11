from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from build_textbook_definition_delta import build_delta, validate_row, REQUIRED_STATUS


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_anchor_matrix" / "textbook_skeleton_matrix_priority_four_20260708.csv"
DEFAULT_OUT = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_definition_delta_incremental"


def read_matrix(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def query_existing_definitions(codes: list[str]) -> dict[str, str]:
    http = os.environ.get("NEO4J_HTTP") or os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USERNAME") or "neo4j"
    password = os.environ.get("NEO4J_PASSWORD")
    if http and http.startswith("bolt://"):
        http = http.replace("bolt://", "http://").replace(":7687", ":7474")
    if not http or not password:
        raise RuntimeError("missing Neo4j env")
    cypher = """
UNWIND $codes AS code
OPTIONAL MATCH (d:Disease {code: code})
RETURN code, coalesce(collect(d.definition)[0], '') AS definition
ORDER BY code
"""
    payload = json.dumps({"statements": [{"statement": cypher, "parameters": {"codes": codes}}]}).encode("utf-8")
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(http.rstrip("/") + "/db/neo4j/tx/commit", data=payload, headers={"Content-Type": "application/json", "Authorization": "Basic " + token})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))
    return {row["row"][0]: row["row"][1] for row in data["results"][0]["data"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build incremental strict textbook definition delta for ready rows still empty on server.")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [r for r in read_matrix(args.matrix) if r.get("match_status") == REQUIRED_STATUS]
    existing = query_existing_definitions([r["disease_code"] for r in rows])
    selected = [r for r in rows if not str(existing.get(r["disease_code"], "")).strip()]

    errors = []
    deltas = []
    for row in selected:
        row_errors = validate_row(row)
        if row_errors:
            errors.append({"disease_code": row["disease_code"], "disease_name": row["disease_name"], "errors": row_errors})
        else:
            deltas.append(build_delta(row, generated_at))

    args.out.mkdir(parents=True, exist_ok=True)
    delta_path = args.out / "delta_disease_definition_update_incremental3_20260708.jsonl"
    with delta_path.open("w", encoding="utf-8") as f:
        for item in deltas:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    summary = {
        "generated_at": generated_at,
        "ready_count": len(rows),
        "already_nonempty_count": len(rows) - len(selected),
        "selected_empty_count": len(selected),
        "delta_count": len(deltas),
        "blocking_error_count": len(errors),
        "preimport_gate_status": "passed" if not errors and len(deltas) == len(selected) else "failed",
        "delta_jsonl": str(delta_path),
        "errors": errors,
        "selected_codes": [r["disease_code"] for r in selected],
    }
    (args.out / "preimport_validation_summary_incremental3_20260708.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["preimport_gate_status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
