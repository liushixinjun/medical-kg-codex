from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DELTA = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_definition_delta" / "delta_disease_definition_update_ready25_20260708.jsonl"
DEFAULT_OUT = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_definition_delta"


def env_value(name: str) -> str | None:
    return os.environ.get(name)


def load_delta(path: Path) -> list[dict[str, object]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                row = {"disease_code": item["match"]["value"]}
                row.update(item["set"])
                rows.append(row)
    return rows


def post(url: str, user: str, password: str, statements: list[dict[str, object]]) -> dict[str, object]:
    payload = json.dumps({"statements": statements}, ensure_ascii=False).encode("utf-8")
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        url.rstrip("/") + "/db/neo4j/tx/commit",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Basic " + token},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Import strict textbook definition delta into Neo4j.")
    parser.add_argument("--delta", type=Path, default=DEFAULT_DELTA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--execute", action="store_true", help="Actually write to Neo4j. Without this flag, only validates input.")
    args = parser.parse_args()

    http = env_value("NEO4J_HTTP") or env_value("NEO4J_URI")
    user = env_value("NEO4J_USERNAME") or "neo4j"
    password = env_value("NEO4J_PASSWORD")
    if http and http.startswith("bolt://"):
        http = http.replace("bolt://", "http://").replace(":7687", ":7474")
    if not http or not password:
        print(json.dumps({"status": "failed", "reason": "missing_neo4j_env"}, ensure_ascii=False, indent=2))
        return 2

    rows = load_delta(args.delta)
    codes = [r["disease_code"] for r in rows]
    duplicate_codes = sorted({c for c in codes if codes.count(c) > 1})
    if len(rows) == 0 or duplicate_codes:
        print(json.dumps({"status": "failed", "reason": "delta_input_invalid", "row_count": len(rows), "duplicate_codes": duplicate_codes}, ensure_ascii=False, indent=2))
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tag = args.delta.stem.replace("delta_disease_definition_update_", "")

    if not args.execute:
        result = {"status": "dry_run_passed", "row_count": len(rows), "execute": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    update_cypher = """
UNWIND $rows AS row
MATCH (d:Disease {code: row.disease_code})
SET d.definition = row.definition,
    d.description = CASE WHEN row.description IS NOT NULL AND trim(row.description) <> '' THEN row.description ELSE d.description END,
    d.definition_source_type = row.definition_source_type,
    d.definition_source_name = row.definition_source_name,
    d.definition_source_section_path = row.definition_source_section_path,
    d.definition_docx_paragraph_start = row.definition_docx_paragraph_start,
    d.definition_docx_paragraph_end = row.definition_docx_paragraph_end,
    d.definition_pdf_page_start = row.definition_pdf_page_start,
    d.definition_pdf_page_end = row.definition_pdf_page_end,
    d.definition_skeleton_slot = row.definition_skeleton_slot,
    d.definition_knowledge_layer = row.definition_knowledge_layer,
    d.textbook_anchor_status = row.textbook_anchor_status,
    d.textbook_anchor_generated_at = row.textbook_anchor_generated_at,
    d.definition_updated_at = $generated_at
RETURN count(d) AS updated_count, collect(d.code) AS updated_codes
"""
    update_result = post(http, user, password, [{"statement": update_cypher, "parameters": {"rows": rows, "generated_at": generated_at}}])
    if update_result.get("errors"):
        out = {"status": "failed", "phase": "update", "errors": update_result["errors"]}
        (args.out / f"server_import_result_{tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    postcheck_cypher = """
UNWIND $codes AS code
OPTIONAL MATCH (d:Disease {code: code})
WITH code, collect(d) AS ds
RETURN
  count(*) AS checked_count,
  sum(CASE WHEN size(ds)=0 THEN 1 ELSE 0 END) AS missing_count,
  sum(CASE WHEN size(ds)>1 THEN 1 ELSE 0 END) AS duplicate_match_count,
  sum(CASE WHEN size(ds)=1 AND coalesce(ds[0].definition,'')='' THEN 1 ELSE 0 END) AS definition_empty_count,
  sum(CASE WHEN size(ds)=1 AND coalesce(ds[0].definition_source_type,'') <> 'authoritative_textbook' THEN 1 ELSE 0 END) AS source_type_error_count,
  sum(CASE WHEN size(ds)=1 AND coalesce(ds[0].definition_source_section_path,'')='' THEN 1 ELSE 0 END) AS source_section_missing_count,
  sum(CASE WHEN size(ds)=1 AND coalesce(ds[0].definition_skeleton_slot,'') <> 'overview' THEN 1 ELSE 0 END) AS skeleton_slot_error_count,
  sum(CASE WHEN size(ds)=1 AND coalesce(ds[0].definition_knowledge_layer,'') <> 'textbook_core' THEN 1 ELSE 0 END) AS knowledge_layer_error_count,
  sum(CASE WHEN size(ds)=1 AND (ds[0].definition_pdf_page_start IS NULL OR ds[0].definition_pdf_page_end IS NULL) THEN 1 ELSE 0 END) AS pdf_page_missing_count,
  sum(CASE WHEN size(ds)=1 AND (ds[0].definition_docx_paragraph_start IS NULL OR ds[0].definition_docx_paragraph_end IS NULL) THEN 1 ELSE 0 END) AS docx_anchor_missing_count,
  sum(CASE WHEN size(ds)=1 AND (ds[0].definition CONTAINS '本章数字资源' OR ds[0].definition CONTAINS 'N O T E S' OR ds[0].definition STARTS WITH '第') THEN 1 ELSE 0 END) AS definition_noise_count
"""
    postcheck_result = post(http, user, password, [{"statement": postcheck_cypher, "parameters": {"codes": codes}}])
    if postcheck_result.get("errors"):
        out = {"status": "failed", "phase": "postcheck", "errors": postcheck_result["errors"]}
        (args.out / f"server_postimport_gate_{tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    update_row = update_result["results"][0]["data"][0]["row"]
    gate_row = postcheck_result["results"][0]["data"][0]["row"]
    gate_cols = postcheck_result["results"][0]["columns"]
    gate = dict(zip(gate_cols, gate_row))
    blocking_keys = [k for k in gate if k.endswith("_count") and k not in {"checked_count"}]
    blocking_total = sum(int(gate[k] or 0) for k in blocking_keys)
    out = {
        "generated_at": generated_at,
        "status": "passed" if update_row[0] == len(rows) and blocking_total == 0 else "failed",
        "execute": True,
        "delta_count": len(rows),
        "updated_count": update_row[0],
        "updated_codes": update_row[1],
        "postimport_gate": gate,
        "blocking_total": blocking_total,
    }
    (args.out / f"server_import_result_{tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / f"server_postimport_gate_{tag}.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
