from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "153_全库正式CDSS推荐链路核验_20260730" / "03_全库疾病大类正式链路覆盖复核"
URI = "bolt://192.168.3.27:7687"
AUTH = ("neo4j", "zysoft@2024")


QUERY = """
MATCH (cat:DiseaseCategory)-[:has_disease]->(d:Disease)
OPTIONAL MATCH p=(d)-[:has_clinical_pathway|has_pathway_stage|has_clinical_rule|has_recommendation_statement*1..4]->(rs:RecommendationStatement)
OPTIONAL MATCH (d)-[:has_clinical_subtype]->(child:Disease)
OPTIONAL MATCH cp=(child)-[:has_clinical_pathway|has_pathway_stage|has_clinical_rule|has_recommendation_statement*1..4]->(child_rs:RecommendationStatement)
WITH cat, d, collect(DISTINCT rs) AS rs_all, collect(DISTINCT child_rs) AS child_rs_all
WITH cat, d, rs_all, child_rs_all,
     [r IN rs_all
      WHERE coalesce(r.formal_cdss_ready,false)=true
        AND coalesce(r.cdss_use_status,'')='正式推荐'] AS rs_formal
WITH cat, d, rs_all, child_rs_all, rs_formal,
     [r IN child_rs_all
      WHERE coalesce(r.formal_cdss_ready,false)=true
        AND coalesce(r.cdss_use_status,'')='正式推荐'] AS child_rs_formal
RETURN cat.name AS category,
       d.name AS disease,
       d.code AS disease_code,
       coalesce(d.diagnostic_role,'') AS diagnostic_role,
       size(rs_all) AS recommendation_count,
       size(rs_formal) AS direct_formal_recommendation_count,
       size(child_rs_formal) AS subtype_formal_recommendation_count,
       CASE
         WHEN coalesce(d.diagnostic_role,'')='broad_diagnosis'
         THEN size(rs_formal) + size(child_rs_formal)
         ELSE size(rs_formal)
       END AS effective_formal_recommendation_count
ORDER BY category, disease
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        with driver.session() as session:
            rows = [dict(r) for r in session.run(QUERY)]

    category_summary: dict[str, dict] = {}
    for row in rows:
        category = row["category"]
        item = category_summary.setdefault(
            category,
            {
                "category": category,
                "disease_count": 0,
                "disease_with_formal": 0,
                "formal_missing_disease_count": 0,
                "formal_recommendation_count": 0,
            },
        )
        item["disease_count"] += 1
        item["formal_recommendation_count"] += row["effective_formal_recommendation_count"]
        if row["effective_formal_recommendation_count"] > 0:
            item["disease_with_formal"] += 1
        else:
            item["formal_missing_disease_count"] += 1

    for item in category_summary.values():
        item["formal_coverage_rate"] = (
            round(item["disease_with_formal"] / item["disease_count"] * 100, 1)
            if item["disease_count"]
            else 0
        )

    detail_path = OUT_DIR / "疾病级正式推荐链路覆盖明细_20260730.csv"
    summary_path = OUT_DIR / "疾病大类正式推荐链路覆盖汇总_20260730.csv"
    json_path = OUT_DIR / "全库疾病大类正式链路覆盖复核_20260730.json"

    with detail_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "category",
                "disease",
                "disease_code",
                "diagnostic_role",
                "recommendation_count",
                "direct_formal_recommendation_count",
                "subtype_formal_recommendation_count",
                "effective_formal_recommendation_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    summary_rows = sorted(category_summary.values(), key=lambda x: x["category"])
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "category",
                "disease_count",
                "disease_with_formal",
                "formal_missing_disease_count",
                "formal_coverage_rate",
                "formal_recommendation_count",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    focus_rows = [
        r
        for r in rows
        if r["category"] in {"冠心病", "心肌病"}
        or r["disease"] in {"急性心肌梗死", "肥厚型心肌病", "扩张型心肌病"}
    ]
    json_path.write_text(
        json.dumps(
            {
                "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "neo4j_written": False,
                "oracle_written": False,
                "category_count": len(summary_rows),
                "disease_count": len(rows),
                "category_summary": summary_rows,
                "focus_rows": focus_rows,
                "files": {
                    "detail_csv": str(detail_path),
                    "summary_csv": str(summary_path),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "out_dir": str(OUT_DIR),
                "category_count": len(summary_rows),
                "disease_count": len(rows),
                "category_summary": summary_rows,
                "focus_count": len(focus_rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
