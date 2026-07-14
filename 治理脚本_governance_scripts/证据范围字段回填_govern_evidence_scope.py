from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient  # noqa: E402
from 治理脚本_governance_scripts.生成疾病大类交付验收包_generate_category_delivery_baseline import (  # noqa: E402
    parse_connection_file,
    query,
    write_csv,
)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_evidence_scope(client: Neo4jHttpClient, dry_run: bool, batch_size: int) -> dict[str, Any]:
    before = query(
        client,
        """
        MATCH (:KGNode)-[r:supported_by_evidence]-(e:KGNode)
        WHERE e.entityType IN ['Evidence','Guideline']
        RETURN
          count(r) AS total_supported_by_evidence,
          sum(CASE WHEN coalesce(e.disease_code,'') <> '' THEN 1 ELSE 0 END) AS evidence_has_scope,
          sum(CASE WHEN coalesce(e.disease_code,'') <> '' AND coalesce(r.disease_code,'') = '' THEN 1 ELSE 0 END) AS relation_missing_scope_can_fill,
          sum(CASE WHEN coalesce(e.disease_code,'') = '' AND coalesce(r.disease_code,'') = '' THEN 1 ELSE 0 END) AS relation_and_evidence_missing_scope
        """,
    )[0]

    samples_before = query(
        client,
        """
        MATCH (n:KGNode)-[r:supported_by_evidence]-(e:KGNode)
        WHERE e.entityType IN ['Evidence','Guideline']
          AND coalesce(e.disease_code,'') <> ''
          AND coalesce(r.disease_code,'') = ''
        RETURN n.entityType AS source_type,
               n.code AS source_code,
               n.name AS source_name,
               e.entityType AS evidence_type,
               e.code AS evidence_code,
               coalesce(e.name, e.source_name, e.title, left(coalesce(e.evidence_text, e.original_text, ''), 80)) AS evidence_name,
               e.disease_code AS disease_code_to_fill
        ORDER BY source_type, source_code, evidence_code
        LIMIT 200
        """,
    )

    updated_count = 0
    if not dry_run:
        while True:
            result = query(
                client,
                """
                MATCH (:KGNode)-[r:supported_by_evidence]-(e:KGNode)
                WHERE e.entityType IN ['Evidence','Guideline']
                  AND coalesce(e.disease_code,'') <> ''
                  AND coalesce(r.disease_code,'') = ''
                WITH r, e LIMIT $batch_size
                SET r.disease_code = e.disease_code,
                    r.evidence_scope_code = e.disease_code,
                    r.scope_filter_required = true,
                    r.scope_filter_rule = 'CDSS查询证据时必须按当前疾病或大类过滤 disease_code',
                    r.scope_governance_batch = '20260714_证据范围字段回填',
                    r.updated_by = 'codex',
                    r.updated_at = $updated_at
                RETURN count(r) AS updated_count
                """,
                {
                    "batch_size": batch_size,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
            batch_count = int(result[0]["updated_count"] or 0)
            updated_count += batch_count
            if batch_count == 0:
                break

    after = query(
        client,
        """
        MATCH (:KGNode)-[r:supported_by_evidence]-(e:KGNode)
        WHERE e.entityType IN ['Evidence','Guideline']
        RETURN
          count(r) AS total_supported_by_evidence,
          sum(CASE WHEN coalesce(e.disease_code,'') <> '' THEN 1 ELSE 0 END) AS evidence_has_scope,
          sum(CASE WHEN coalesce(e.disease_code,'') <> '' AND coalesce(r.disease_code,'') = '' THEN 1 ELSE 0 END) AS relation_missing_scope_can_fill,
          sum(CASE WHEN coalesce(e.disease_code,'') = '' AND coalesce(r.disease_code,'') = '' THEN 1 ELSE 0 END) AS relation_and_evidence_missing_scope
        """,
    )[0]

    missing_scope_samples = query(
        client,
        """
        MATCH (n:KGNode)-[r:supported_by_evidence]-(e:KGNode)
        WHERE e.entityType IN ['Evidence','Guideline']
          AND coalesce(e.disease_code,'') = ''
          AND coalesce(r.disease_code,'') = ''
        RETURN n.entityType AS source_type,
               n.code AS source_code,
               n.name AS source_name,
               e.entityType AS evidence_type,
               e.code AS evidence_code,
               coalesce(e.name, e.source_name, e.title, left(coalesce(e.evidence_text, e.original_text, ''), 80)) AS evidence_name
        ORDER BY source_type, source_code, evidence_code
        LIMIT 200
        """,
    )

    return {
        "dry_run": dry_run,
        "before": before,
        "updated_count": updated_count,
        "after": after,
        "fillable_samples_before": samples_before,
        "missing_scope_samples_after": missing_scope_samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="证据范围字段回填：把 Evidence/Guideline 的 disease_code 同步到 supported_by_evidence 关系。")
    parser.add_argument("--dry-run", action="store_true", help="只生成审计，不写 Neo4j")
    parser.add_argument("--batch-size", type=int, default=3000, help="每批回填关系数，避免单次事务过大")
    parser.add_argument("--output-dir", default="心血管内科文献集合/20260714_证据范围字段回填")
    args = parser.parse_args()

    conn = parse_connection_file(ROOT / "图谱数据库链接.txt")
    client = Neo4jHttpClient(conn["uri"], conn["username"], conn["password"], "neo4j")
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    result = normalize_evidence_scope(client, args.dry_run, max(1, args.batch_size))
    write_json(output_dir / "00_证据范围字段回填_summary.json", result)
    write_csv(
        output_dir / "01_可回填样本_before.csv",
        result["fillable_samples_before"],
    )
    write_csv(
        output_dir / "02_仍缺范围样本_after.csv",
        result["missing_scope_samples_after"],
    )

    report = [
        "# 证据范围字段回填报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 是否只读：{args.dry_run}",
        f"- 本轮写入关系数：{result['updated_count']}",
        "",
        "## 1. 回填前",
        "",
        f"- supported_by_evidence 总数：{result['before'].get('total_supported_by_evidence', 0)}",
        f"- Evidence/Guideline 自带疾病范围数：{result['before'].get('evidence_has_scope', 0)}",
        f"- 关系缺范围但可从证据回填数：{result['before'].get('relation_missing_scope_can_fill', 0)}",
        f"- 关系和证据都缺范围数：{result['before'].get('relation_and_evidence_missing_scope', 0)}",
        "",
        "## 2. 回填后",
        "",
        f"- 关系缺范围但可从证据回填数：{result['after'].get('relation_missing_scope_can_fill', 0)}",
        f"- 关系和证据都缺范围数：{result['after'].get('relation_and_evidence_missing_scope', 0)}",
        "",
        "## 3. 使用规则",
        "",
        "前端和 CDSS 后端查询推荐证据时，必须按当前疾病或疾病大类过滤 `supported_by_evidence.disease_code`。",
        "不能只因为推荐节点连了 Evidence/Guideline，就把全部证据展示给医生。",
        "",
    ]
    (output_dir / "03_证据范围字段回填报告.md").write_text("\n".join(report), encoding="utf-8")

    print(json.dumps({k: result[k] for k in ["dry_run", "updated_count", "before", "after"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
