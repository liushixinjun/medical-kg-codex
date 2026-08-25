from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase


BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "项目管理中心_project_management" / "2026年8月真实性来源核验"
BATCH_ID = "20260818_全局泛化关系治理与样板核验"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


STRUCTURAL_REL_USAGE = {
    "has_exam_plan": "辅助检查方案入口",
    "includes_exam_item": "辅助检查项目下钻",
    "includes_lab_item": "辅助检验项目下钻",
    "exam_item_has_observation": "检查发现下钻",
    "lab_item_has_subitem": "检验细项下钻",
    "has_treatment_plan": "治疗方案入口",
    "includes_medication": "治疗方案包含药品",
    "includes_procedure": "治疗方案包含手术或操作",
    "includes_treatment_item": "治疗方案包含治疗处置",
    "has_differential_diagnosis": "鉴别诊断对象",
    "has_differential_rule": "鉴别诊断规则",
    "requires_exclusion_exam": "鉴别诊断排除检查",
    "requires_exclusion_lab": "鉴别诊断排除检验",
    "stage_has_available_action": "路径阶段可选动作",
}


SAMPLE_DISEASE_CODES = [
    "DIS-CARD-CAD-AMI",
    "DIS-CARD-CAD-STEMI",
    "DIS-CARD-CAD-NSTEMI",
    "DIS-CARD-CM-GENERAL",
    "DIS-CARD-CM-HCM",
    "DIS-CARD-CM-DCM",
]


def read_conn() -> tuple[str, str, str]:
    text = (BASE_DIR / "图谱数据库链接.txt").read_text(encoding="utf-8", errors="ignore")
    uri = re.search(r"bolt://[^\s；;，,]+", text)
    user = re.search(r"(?:用户名|user|username)\s*[:：]\s*([^\s；;，,]+)", text, re.I)
    pwd = re.search(r"(?:密码|password)\s*[:：]\s*([^\s；;，,]+)", text, re.I)
    if not uri or not user or not pwd:
        raise RuntimeError("图谱数据库链接.txt 缺少 bolt、用户名或密码字段")
    return uri.group(0), user.group(1), pwd.group(1)


def rows(session, cypher: str, **params) -> list[dict]:
    return [dict(r) for r in session.run(cypher, **params)]


def one(session, cypher: str, **params) -> dict:
    record = session.run(cypher, **params).single()
    return dict(record) if record else {}


def relation_stats(session) -> list[dict]:
    return rows(
        session,
        """
        MATCH ()-[r]->()
        WHERE type(r) IN $types OR type(r) = 'recommends_action'
        RETURN type(r) AS relation_type,
               count(r) AS total,
               count(CASE WHEN r.formal_recommendation = 'yes' THEN 1 END) AS formal_yes,
               count(CASE WHEN r.formal_recommendation = 'no' THEN 1 END) AS formal_no,
               count(CASE WHEN coalesce(r.cdss_usage,'') <> '' THEN 1 END) AS has_cdss_usage,
               count(CASE WHEN r.source IS NULL AND r.evidence_id IS NULL AND r.evidence_ids IS NULL THEN 1 END) AS no_relation_source_or_evidence
        ORDER BY relation_type
        """,
        types=list(STRUCTURAL_REL_USAGE.keys()),
    )


def backup_affected_relations(session) -> list[dict]:
    return rows(
        session,
        """
        MATCH (s)-[r]->(t)
        WHERE type(r) IN $types OR type(r) = 'recommends_action'
        RETURN elementId(r) AS rel_element_id,
               type(r) AS relation_type,
               labels(s) AS source_labels,
               coalesce(s.code,'') AS source_code,
               coalesce(s.name,s.display_name,'') AS source_name,
               labels(t) AS target_labels,
               coalesce(t.code,'') AS target_code,
               coalesce(t.name,t.display_name,'') AS target_name,
               properties(r) AS relation_properties
        """,
        types=list(STRUCTURAL_REL_USAGE.keys()),
    )


def govern_structural_relations(session) -> dict[str, int]:
    changed: dict[str, int] = {}
    for rel_type, usage in STRUCTURAL_REL_USAGE.items():
        changed[rel_type] = one(
            session,
            f"""
            MATCH ()-[r:{rel_type}]->()
            SET r.formal_recommendation = 'no',
                r.cdss_usage = $usage,
                r.clinical_support_ready = coalesce(r.clinical_support_ready, 'yes'),
                r.formal_cdss_ready = false,
                r.formal_block_reason = '结构性知识关系，不直接作为正式CDSS推荐；正式推荐必须走 RecommendationStatement 到推荐动作再到证据',
                r.governance_batch = $batch,
                r.updated_at = $now
            RETURN count(r) AS n
            """,
            usage=usage,
            batch=BATCH_ID,
            now=NOW,
        ).get("n", 0)
    return changed


def govern_recommendation_relations(session) -> dict[str, int]:
    ok = one(
        session,
        """
        MATCH (rs:RecommendationStatement)-[r:recommends_action]->(a)
        WHERE (coalesce(rs.evidence_id,'') <> ''
               OR size(coalesce(rs.evidence_ids, [])) > 0
               OR (rs)-[:supported_by_evidence]->(:Evidence))
          AND (coalesce(rs.primary_guideline_id,'') <> ''
               OR coalesce(rs.guideline_id,'') <> ''
               OR (rs)-[:uses_primary_guideline]->(:Guideline)
               OR (rs)-[:based_on_guideline]->(:Guideline))
        SET r.formal_recommendation = 'yes',
            r.cdss_usage = '正式CDSS推荐动作',
            r.clinical_support_ready = 'yes',
            r.formal_cdss_ready = true,
            r.source_binding_location = '推荐陈述节点',
            r.governance_batch = $batch,
            r.updated_at = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).get("n", 0)
    blocked = one(
        session,
        """
        MATCH (rs:RecommendationStatement)-[r:recommends_action]->(a)
        WHERE NOT (
          (coalesce(rs.evidence_id,'') <> ''
           OR size(coalesce(rs.evidence_ids, [])) > 0
           OR (rs)-[:supported_by_evidence]->(:Evidence))
          AND
          (coalesce(rs.primary_guideline_id,'') <> ''
           OR coalesce(rs.guideline_id,'') <> ''
           OR (rs)-[:uses_primary_guideline]->(:Guideline)
           OR (rs)-[:based_on_guideline]->(:Guideline))
        )
        SET r.formal_recommendation = 'no',
            r.cdss_usage = '推荐链路待补证据',
            r.clinical_support_ready = 'no',
            r.formal_cdss_ready = false,
            r.formal_block_reason = '推荐陈述缺主证据或主指南，不能进入正式CDSS推荐',
            r.governance_batch = $batch,
            r.updated_at = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).get("n", 0)
    # 历史脚本曾允许 ClinicalRule 直接 recommends_action，这类关系不作为正式推荐入口。
    rule_direct = one(
        session,
        """
        MATCH (rnode:ClinicalRule)-[r:recommends_action]->(a)
        WHERE NOT rnode:RecommendationStatement
        SET r.formal_recommendation = 'no',
            r.cdss_usage = '规则内部候选动作',
            r.clinical_support_ready = coalesce(r.clinical_support_ready, 'yes'),
            r.formal_cdss_ready = false,
            r.formal_block_reason = '规则直连动作仅用于解释或路径内部计算，正式推荐入口必须是 RecommendationStatement',
            r.governance_batch = $batch,
            r.updated_at = $now
        RETURN count(r) AS n
        """,
        batch=BATCH_ID,
        now=NOW,
    ).get("n", 0)
    return {"recommendation_statement_action_ready": ok, "recommendation_statement_action_blocked": blocked, "clinical_rule_direct_action_downgraded": rule_direct}


def hard_gate(session) -> dict:
    structural_yes = rows(
        session,
        """
        MATCH ()-[r]->()
        WHERE type(r) IN $types AND r.formal_recommendation = 'yes'
        RETURN type(r) AS relation_type, count(r) AS count
        ORDER BY count DESC
        """,
        types=list(STRUCTURAL_REL_USAGE.keys()),
    )
    formal_missing = rows(
        session,
        """
        MATCH (rs:RecommendationStatement)-[r:recommends_action]->(a)
        WHERE r.formal_recommendation = 'yes'
          AND NOT (
            (coalesce(rs.evidence_id,'') <> ''
             OR size(coalesce(rs.evidence_ids, [])) > 0
             OR (rs)-[:supported_by_evidence]->(:Evidence))
            AND
            (coalesce(rs.primary_guideline_id,'') <> ''
             OR coalesce(rs.guideline_id,'') <> ''
             OR (rs)-[:uses_primary_guideline]->(:Guideline)
             OR (rs)-[:based_on_guideline]->(:Guideline))
          )
        RETURN coalesce(rs.code,'') AS recommendation_code,
               coalesce(rs.name, rs.display_name, '') AS recommendation_name,
               coalesce(a.code,'') AS action_code,
               coalesce(a.name,a.display_name,'') AS action_name
        LIMIT 20
        """,
    )
    disease_samples = rows(
        session,
        """
        MATCH (d:Disease)
        WHERE d.code IN $codes
        OPTIONAL MATCH (d)-[:has_recommendation_statement]->(rs:RecommendationStatement)-[ra:recommends_action {formal_recommendation:'yes'}]->(a)
        OPTIONAL MATCH (rs)-[:supported_by_evidence]->(ev:Evidence)
        OPTIONAL MATCH (rs)-[:uses_primary_guideline|based_on_guideline]->(g:Guideline)
        RETURN d.code AS disease_code,
               d.name AS disease_name,
               count(DISTINCT rs) AS formal_recommendation_count,
               count(DISTINCT a) AS action_count,
               count(DISTINCT ev) AS linked_evidence_count,
               count(DISTINCT g) AS linked_guideline_count,
               collect(DISTINCT {
                 recommendation: coalesce(rs.name, rs.display_name, ''),
                 action: coalesce(a.name, a.display_name, ''),
                 guideline: coalesce(g.name, g.display_name, ''),
                 evidence: coalesce(ev.evidence_text, ev.clean_evidence_text, ev.evidence_summary, '')[..160]
               })[..8] AS examples
        ORDER BY disease_code
        """,
        codes=SAMPLE_DISEASE_CODES,
    )
    return {
        "structural_relations_wrongly_marked_formal": structural_yes,
        "formal_recommendation_missing_evidence_or_guideline_sample": formal_missing,
        "ami_cm_formal_chain_samples": disease_samples,
    }


def write_report(payload: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "全局泛化关系治理与样板核验_20260818.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    gate = payload["hard_gate"]
    lines = [
        "# 全局泛化关系治理与 AMI/心肌病样板核验",
        "",
        f"- 执行时间：{NOW}",
        f"- 批次：{BATCH_ID}",
        "",
        "## 本次处理原则",
        "",
        "- 疾病直连检查方案、治疗方案、鉴别诊断、方案包含药品/手术，统一作为知识展示和临床支持，不直接作为正式 CDSS 推荐。",
        "- 正式 CDSS 推荐只允许从“推荐陈述”进入，再连接推荐动作、主指南和证据。",
        "- 不自动补假证据；发现来源不清的旧关系，只降级使用边界，不伪造成正式推荐。",
        "",
        "## 硬闸门结果",
        "",
        f"- 结构性关系误标为正式推荐：{sum(x['count'] for x in gate['structural_relations_wrongly_marked_formal'])}",
        f"- 正式推荐缺主证据或主指南抽样条数：{len(gate['formal_recommendation_missing_evidence_or_guideline_sample'])}",
        "",
        "## AMI/心肌病样板链路抽样",
        "",
    ]
    for item in gate["ami_cm_formal_chain_samples"]:
        lines.append(
            f"- {item['disease_name']}（{item['disease_code']}）：正式推荐 {item['formal_recommendation_count']} 条，动作 {item['action_count']} 个，证据 {item['linked_evidence_count']} 条，指南 {item['linked_guideline_count']} 份。"
        )
        for ex in item["examples"][:3]:
            if ex["recommendation"] or ex["action"]:
                lines.append(f"  - 推荐：{ex['recommendation']}；动作：{ex['action']}；指南：{ex['guideline']}")
                if ex["evidence"]:
                    lines.append(f"    证据摘要：{ex['evidence']}")
    lines.append("")
    lines.append("## 变更统计")
    lines.append("")
    for k, v in payload["updates"].items():
        if isinstance(v, dict):
            lines.append(f"- {k}：{json.dumps(v, ensure_ascii=False, default=str)}")
        else:
            lines.append(f"- {k}：{v}")
    (OUT_DIR / "全局泛化关系治理与样板核验_20260818.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    uri, user, password = read_conn()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session(database="neo4j") as session:
        before = relation_stats(session)
        backup = backup_affected_relations(session)
        backup_file = OUT_DIR / "全局泛化关系治理_关系属性备份_20260818.jsonl"
        with backup_file.open("w", encoding="utf-8") as f:
            for row in backup:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        updates = {
            "结构性关系降级": govern_structural_relations(session),
            "正式推荐关系治理": govern_recommendation_relations(session),
        }
        after = relation_stats(session)
        gate = hard_gate(session)
    driver.close()
    payload = {
        "time": NOW,
        "batch": BATCH_ID,
        "backup_file": str(backup_file),
        "before": before,
        "updates": updates,
        "after": after,
        "hard_gate": gate,
    }
    write_report(payload)
    print(json.dumps({
        "batch": BATCH_ID,
        "backup_file": str(backup_file),
        "structural_wrong_formal_after": sum(x["count"] for x in gate["structural_relations_wrongly_marked_formal"]),
        "formal_missing_sample_after": len(gate["formal_recommendation_missing_evidence_or_guideline_sample"]),
        "report_md": str(OUT_DIR / "全局泛化关系治理与样板核验_20260818.md"),
        "report_json": str(OUT_DIR / "全局泛化关系治理与样板核验_20260818.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
