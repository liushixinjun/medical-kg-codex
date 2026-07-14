from __future__ import annotations

import base64
import csv
import json
import os
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_definition_delta_curated"
READY25 = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_definition_delta" / "delta_disease_definition_update_ready25_20260708.jsonl"
INCREMENTAL3 = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_definition_delta_incremental" / "delta_disease_definition_update_incremental3_20260708.jsonl"
CURATED30 = OUT / "delta_disease_definition_update_curated30_20260708.jsonl"
BLOCKED10 = OUT / "blocked_after_curated30_20260708.csv"


def read_delta_codes(path: Path) -> set[str]:
    codes: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if "match" in item:
                codes.add(str(item["match"]["value"]))
            elif "code" in item:
                codes.add(str(item["code"]))
    return codes


def read_blocked_codes(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {row["disease_code"] for row in csv.DictReader(f) if row.get("disease_code")}


def neo4j_post(statement: str, parameters: dict[str, object]) -> dict[str, object]:
    # 生产环境这里应复用统一连接解析；本脚本用于当前服务器复核。
    http_root = os.environ.get("NEO4J_HTTP", "http://192.168.3.27:7474").rstrip("/")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("缺少 NEO4J_PASSWORD 环境变量，禁止在脚本中硬编码数据库密码。")
    url = f"{http_root}/db/neo4j/tx/commit"
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        url,
        data=json.dumps({"statements": [{"statement": statement, "parameters": parameters}]}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Basic " + token},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False))
    return result


def rows(result: dict[str, object]) -> list[dict[str, object]]:
    res = result["results"][0]  # type: ignore[index]
    columns = res["columns"]  # type: ignore[index]
    return [dict(zip(columns, item["row"])) for item in res["data"]]  # type: ignore[index]


def main() -> int:
    codes = sorted(read_delta_codes(READY25) | read_delta_codes(INCREMENTAL3) | read_delta_codes(CURATED30) | read_blocked_codes(BLOCKED10))
    if len(codes) != 68:
        raise SystemExit(f"priority68 code reconstruction failed: {len(codes)} codes")

    detail_stmt = """
    UNWIND $codes AS code
    OPTIONAL MATCH (d:Disease {code: code})
    RETURN
      code,
      d.name AS name,
      CASE WHEN d IS NULL THEN 'missing'
           WHEN coalesce(d.definition,'')='' THEN 'definition_empty'
           ELSE 'definition_present' END AS definition_status,
      d.definition_confidence AS definition_confidence,
      d.external_authority_review_status AS external_authority_review_status,
      d.definition_source_type AS definition_source_type,
      d.definition_source_name AS definition_source_name,
      left(coalesce(d.definition,''), 120) AS definition_preview
    ORDER BY code
    """
    detail_rows = rows(neo4j_post(detail_stmt, {"codes": codes}))

    summary = {
        "checked_count": len(codes),
        "missing_count": sum(1 for r in detail_rows if r["definition_status"] == "missing"),
        "definition_empty_count": sum(1 for r in detail_rows if r["definition_status"] == "definition_empty"),
        "definition_nonempty_count": sum(1 for r in detail_rows if r["definition_status"] == "definition_present"),
        "high_confidence_count": sum(1 for r in detail_rows if r.get("definition_confidence") == "high"),
        "conditional_count": sum(1 for r in detail_rows if r.get("definition_confidence") == "conditional"),
        "external_authority_count": sum(1 for r in detail_rows if str(r.get("definition_source_type") or "").startswith("external_authoritative_source")),
        "empty_codes": [r["code"] for r in detail_rows if r["definition_status"] != "definition_present"],
        "source_type_distribution": {},
        "status": "passed" if all(r["definition_status"] == "definition_present" for r in detail_rows) else "failed",
    }
    dist: dict[str, int] = {}
    for r in detail_rows:
        key = str(r.get("definition_source_type") or "")
        dist[key] = dist.get(key, 0) + 1
    summary["source_type_distribution"] = dist

    out_summary = OUT / "server_priority68_definition_status_after_external_authority_fixed_20260709.json"
    out_detail = OUT / "server_priority68_definition_detail_after_external_authority_fixed_20260709.csv"
    out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with out_detail.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = list(detail_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(detail_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
