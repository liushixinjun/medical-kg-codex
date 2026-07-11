from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.global_safety_check import parse_connection_file
from scripts.import_neo4j_test_db import Neo4jHttpClient, cleaned_node_props, first_row


BATCH_ID = "RECOMMENDATION-STATEMENT-MIGRATION-20260707"
SCHEMA_VERSION = "V1.10"
DETAIL_CHUNK_SIZE = 10
ACTION_TYPE_LABELS = {
    "TreatmentPlan": "治疗方案",
    "Procedure": "操作/手术",
    "Drug": "药物",
    "Medication": "药物",
    "DrugClass": "药物类别",
    "Exam": "检查",
    "LabTest": "检验",
    "Surgery": "手术",
    "DiagnosisCriteria": "诊断标准",
    "DifferentialDiagnosis": "鉴别诊断",
    "FollowUp": "随访",
    "RiskStratification": "风险分层",
}


def rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    columns = result["results"][0]["columns"]
    return [
        {column: item["row"][index] for index, column in enumerate(columns)}
        for item in result["results"][0]["data"]
    ]


def text_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return "；".join(str(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value).strip()


def pick_name(props: dict[str, Any] | None) -> str:
    if not props:
        return ""
    for key in ("display_name", "preferred_name", "name", "title", "code"):
        value = text_value(props.get(key))
        if value:
            return value
    return ""


def normalize_level(value: Any) -> str:
    level = text_value(value, "未结构化")
    if not level or level.upper() in {"N/A", "NA", "NULL", "NONE"}:
        return "未结构化"
    return level


def parse_recommendation_and_evidence(text: str) -> tuple[str, str]:
    compact = re.sub(r"\s+", " ", text or "")
    patterns = [
        r"(?:推荐等级|推荐级别|class|Class|CLASS)\s*[:：]?\s*(I{1,3}a?|III|IV|A|B|C)",
        r"\b(I{1,3}a?|III)\s*[,，/ ]+\s*([ABC])\b",
    ]
    recommendation_class = "未结构化"
    evidence_level = "未结构化"
    for pattern in patterns:
        match = re.search(pattern, compact)
        if not match:
            continue
        if len(match.groups()) >= 2:
            recommendation_class = match.group(1)
            evidence_level = match.group(2)
        else:
            recommendation_class = match.group(1)
        break
    evidence_match = re.search(r"(?:证据等级|证据级别|level|Level|LEVEL)\s*[:：]?\s*([ABC])", compact)
    if evidence_match:
        evidence_level = evidence_match.group(1)
    return recommendation_class, evidence_level


def score_evidence(evidence: dict[str, Any], rule: dict[str, Any], action: dict[str, Any]) -> int:
    text = " ".join(
        [
            pick_name(evidence),
            text_value(evidence.get("evidence_text")),
            text_value(evidence.get("source_section")),
            text_value(evidence.get("source_name")),
        ]
    )
    action_name = pick_name(action)
    rule_text = " ".join([pick_name(rule), text_value(rule.get("rule_logic"))])
    score = 0
    if action_name and action_name in text:
        score += 5
    for token in re.split(r"[、，,；;\s/]+", action_name):
        if len(token) >= 2 and token in text:
            score += 1
    if normalize_level(evidence.get("recommendation_class")) != "未结构化":
        score += 3
    if normalize_level(evidence.get("evidence_level")) != "未结构化":
        score += 3
    if re.search(r"指南|Guideline|ESC|ACC|AHA|共识|专家共识", text, re.I):
        score += 2
    if "内科学" in text:
        score -= 1
    for token in re.split(r"[、，,；;\s/]+", rule_text):
        if len(token) >= 3 and token in text:
            score += 1
    return score


def choose_primary_evidence(
    evidence_list: list[dict[str, Any]], rule: dict[str, Any], action: dict[str, Any]
) -> dict[str, Any] | None:
    cleaned = [item for item in evidence_list if item and item.get("code")]
    if not cleaned:
        return None
    return sorted(
        cleaned,
        key=lambda item: (
            score_evidence(item, rule, action),
            normalize_level(item.get("recommendation_class")) != "未结构化",
            normalize_level(item.get("evidence_level")) != "未结构化",
            text_value(item.get("code")),
        ),
        reverse=True,
    )[0]


def make_code(rule_code: str, relation_type: str, action_code: str) -> str:
    seed = f"{rule_code}|{relation_type}|{action_code}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest().upper()[:16]
    return f"REC-{digest}"


def display_level(recommendation_type: str, recommendation_class: str) -> str:
    if recommendation_type == "block":
        return "block"
    if recommendation_class in {"I", "Ⅰ", "IIa", "Ⅱa", "A"}:
        return "recommendation"
    if recommendation_class in {"IIb", "Ⅱb", "III", "Ⅲ"}:
        return "caution"
    return "knowledge_display"


def safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item not in (None, "")]
        except json.JSONDecodeError:
            pass
        return [stripped]
    return [str(value)]


def build_statement(row: dict[str, Any], now: str) -> dict[str, Any]:
    rule = row["rule"] or {}
    action = row["action"] or {}
    stages = [item for item in row.get("stages") or [] if item and item.get("code")]
    pathways = [item for item in row.get("pathways") or [] if item and item.get("code")]
    evidences = [item for item in row.get("evidences") or [] if item and item.get("code")]
    guidelines = [item for item in row.get("guidelines") or [] if item and item.get("code")]

    relation_type = row["relation_type"]
    recommendation_type = "block" if relation_type == "blocks_action" else "recommend"
    verb = "阻断/暂不推荐" if recommendation_type == "block" else "推荐"

    rule_code = text_value(rule.get("code"))
    action_code = text_value(action.get("code"))
    code = make_code(rule_code, recommendation_type, action_code)

    action_name = pick_name(action)
    rule_name = pick_name(rule)
    stage = stages[0] if stages else {}
    pathway = pathways[0] if pathways else {}
    primary_evidence = choose_primary_evidence(evidences, rule, action) or {}
    guideline = {}
    if primary_evidence:
        primary_doc_id = primary_evidence.get("document_id")
        guideline = next(
            (
                item
                for item in guidelines
                if item.get("document_id") == primary_doc_id
                or item.get("code") == text_value(primary_doc_id).replace("DOC-", "SRC-DOC-")
            ),
            guidelines[0] if guidelines else {},
        )

    recommendation_class = normalize_level(rule.get("recommendation_class"))
    evidence_level = normalize_level(rule.get("evidence_level"))
    if recommendation_class == "未结构化":
        recommendation_class = normalize_level(primary_evidence.get("recommendation_class"))
    if evidence_level == "未结构化":
        evidence_level = normalize_level(primary_evidence.get("evidence_level"))
    if recommendation_class == "未结构化" or evidence_level == "未结构化":
        parsed_rec, parsed_ev = parse_recommendation_and_evidence(
            " ".join(
                [
                    text_value(primary_evidence.get("evidence_text")),
                    text_value(primary_evidence.get("source_section")),
                ]
            )
        )
        if recommendation_class == "未结构化":
            recommendation_class = parsed_rec
        if evidence_level == "未结构化":
            evidence_level = parsed_ev

    statement_summary = f"满足“{rule_name}”时，{verb}：{action_name}"
    statement_text = text_value(rule.get("rule_logic")) or statement_summary
    display_suffix = "阻断" if recommendation_type == "block" else "推荐"
    display_prefix = rule_name or pick_name(stage) or text_value(rule.get("scope_target"), "")
    action_type_label = ACTION_TYPE_LABELS.get(text_value(action.get("entityType")), text_value(action.get("entityType")))
    action_display = f"{action_name}（{action_type_label}）" if action_type_label else action_name
    display_name = (
        f"{display_prefix}｜{action_display}{display_suffix}"
        if display_prefix
        else f"{action_display}{display_suffix}"
    )

    props = {
        "id": f"KG_{code.replace('-', '_')}",
        "code": code,
        "name": display_name,
        "display_name": display_name,
        "preferred_name": display_name,
        "entityType": "RecommendationStatement",
        "entityCategory": "CDSS推荐陈述",
        "primary_label": "KGNode",
        "type_label": "RecommendationStatement",
        "canonical_labels": ["KGNode", "RecommendationStatement"],
        "statement_text": statement_text,
        "statement_summary": statement_summary,
        "recommendation_type": recommendation_type,
        "scope_type": text_value(rule.get("scope_type"), "disease"),
        "scope_target": text_value(rule.get("scope_target")) or text_value(action.get("scope_target")),
        "scope_disease_code": text_value(rule.get("disease_code"), "N/A"),
        "pathway_code": text_value(pathway.get("code")) or text_value(stage.get("pathway_code"), "N/A"),
        "pathway_name": pick_name(pathway) or "N/A",
        "stage_code": text_value(stage.get("code"), "N/A"),
        "stage_name": pick_name(stage) or "N/A",
        "stage_order": stage.get("stage_order", "N/A"),
        "rule_code": rule_code,
        "rule_name": rule_name,
        "action_code": action_code,
        "action_name": action_name,
        "action_entity_type": text_value(action.get("entityType"), "N/A"),
        "required_patient_data": safe_list(rule.get("required_patient_data")),
        "applicable_population": text_value(rule.get("applicable_population"))
        or text_value(rule.get("scope_target"), "N/A"),
        "indication_conditions": text_value(rule.get("trigger_condition"))
        or text_value(rule.get("condition_text"))
        or text_value(rule.get("rule_logic"), "N/A"),
        "contraindication_conditions": text_value(rule.get("contraindication_conditions"))
        or text_value(rule.get("exclusion_criteria"))
        or ("见阻断规则" if recommendation_type == "block" else "N/A"),
        "recommendation_class": recommendation_class,
        "evidence_level": evidence_level,
        "primary_evidence_code": text_value(primary_evidence.get("code"), "N/A"),
        "primary_guideline_code": text_value(guideline.get("code"), "N/A"),
        "primary_guideline_name": pick_name(guideline) or text_value(primary_evidence.get("source_name"), "N/A"),
        "evidence_count": len(evidences),
        "guideline_count": len(guidelines),
        "cdss_display_level": display_level(recommendation_type, recommendation_class),
        "clinical_review_status": text_value(
            rule.get("clinical_review_status"), "pending_clinical_use_effect_review"
        ),
        "formal_cdss_ready": bool(rule.get("formal_cdss_ready") is True),
        "review_status": text_value(rule.get("review_status"), "approved_for_sample"),
        "merge_status": "validated_migrated",
        "conflict_status": text_value(rule.get("conflict_status"), "none"),
        "source_rule_relation_type": relation_type,
        "batch_id": BATCH_ID,
        "source_batch_id": text_value(rule.get("batch_id")),
        "schema_version": SCHEMA_VERSION,
        "created_by": "codex_recommendation_statement_migration",
        "created_at": now,
        "updated_at": now,
    }
    return {
        "props": cleaned_node_props(props),
        "rule_code": rule_code,
        "action_code": action_code,
        "stage_code": props["stage_code"],
        "pathway_code": props["pathway_code"],
        "evidence_codes": sorted({text_value(item.get("code")) for item in evidences if item.get("code")}),
        "guideline_codes": sorted({text_value(item.get("code")) for item in guidelines if item.get("code")}),
        "recommendation_relation": "blocks_action" if recommendation_type == "block" else "recommends_action",
    }


def fetch_candidates(client: Neo4jHttpClient) -> list[dict[str, Any]]:
    triples = rows(
        client.run(
            """
            MATCH (rule:KGNode {entityType:'ClinicalRule'})-[rel:recommends_action|blocks_action|has_recommended_action]->(action:KGNode)
            WHERE (rule)-[:supported_by_evidence]->(:KGNode {entityType:'Evidence'})
            RETURN rule.code AS rule_code, type(rel) AS relation_type, action.code AS action_code
            ORDER BY rule_code, relation_type, action_code
            """
        )
    )
    detail_query = """
    UNWIND $triples AS target
    MATCH (rule:KGNode {entityType:'ClinicalRule'})-[rel:recommends_action|blocks_action|has_recommended_action]->(action:KGNode)
    WHERE rule.code = target.rule_code
      AND action.code = target.action_code
      AND type(rel) = target.relation_type
    MATCH (rule)-[:supported_by_evidence]->(ev:KGNode {entityType:'Evidence'})
    WITH rule, rel, action, collect(DISTINCT ev{
      .code,
      .name,
      .display_name,
      .preferred_name,
      .document_id,
      .source_name,
      source_section: left(coalesce(ev.source_section, ''), 500),
      .recommendation_class,
      .evidence_level,
      evidence_text: ''
    }) AS evidences
    OPTIONAL MATCH (stage:KGNode)-[:has_stage_rule|has_diagnostic_component|has_differential_point]->(rule)
    OPTIONAL MATCH (pathway:KGNode {entityType:'ClinicalPathway'})-[:has_pathway_stage]->(stage)
    WITH rule, rel, action, evidences,
         collect(DISTINCT stage{
           .code,
           .name,
           .display_name,
           .preferred_name,
           .pathway_code,
           .stage_order,
           .trigger_condition,
           .exit_condition
         }) AS stages,
         collect(DISTINCT pathway{
           .code,
           .name,
           .display_name,
           .preferred_name
         }) AS pathways
    RETURN rule{
             .code,
             .name,
             .display_name,
             .preferred_name,
             .rule_logic,
             .disease_code,
             .scope_type,
             .scope_target,
             .recommendation_class,
             .evidence_level,
             .required_patient_data,
             .applicable_population,
             .trigger_condition,
             .condition_text,
             .contraindication_conditions,
             .exclusion_criteria,
             .clinical_review_status,
             .formal_cdss_ready,
             .review_status,
             .conflict_status,
             .batch_id
           } AS rule,
           type(rel) AS relation_type,
           action{
             .code,
             .name,
             .display_name,
             .preferred_name,
             .entityType,
             .scope_target
           } AS action,
           stages,
           pathways,
           evidences,
           [] AS guidelines
    ORDER BY coalesce(rule.disease_code,''), coalesce(rule.code,''), relation_type, coalesce(action.code,'')
    """
    output: list[dict[str, Any]] = []
    for start in range(0, len(triples), DETAIL_CHUNK_SIZE):
        batch = triples[start : start + DETAIL_CHUNK_SIZE]
        output.extend(rows(client.run(detail_query, {"triples": batch})))
    return output


def fetch_guidelines(client: Neo4jHttpClient) -> list[dict[str, Any]]:
    return rows(
        client.run(
            """
            MATCH (g:KGNode {entityType:'Guideline'})
            RETURN g{
              .code,
              .name,
              .display_name,
              .preferred_name,
              .title,
              .document_id
            } AS guideline
            """
        )
    )


def attach_guidelines(candidates: list[dict[str, Any]], guideline_rows: list[dict[str, Any]]) -> None:
    index: dict[str, dict[str, Any]] = {}
    for row in guideline_rows:
        guideline = row.get("guideline") or {}
        for key in (
            text_value(guideline.get("document_id")),
            text_value(guideline.get("code")),
            text_value(guideline.get("name")),
            text_value(guideline.get("title")),
        ):
            if key:
                index.setdefault(key, guideline)
    for row in candidates:
        matched: dict[str, dict[str, Any]] = {}
        for evidence in row.get("evidences") or []:
            if not evidence:
                continue
            keys = [
                text_value(evidence.get("document_id")),
                text_value(evidence.get("document_id")).replace("DOC-", "SRC-DOC-"),
                text_value(evidence.get("source_name")),
            ]
            for key in keys:
                guideline = index.get(key)
                if guideline and guideline.get("code"):
                    matched[text_value(guideline.get("code"))] = guideline
        row["guidelines"] = list(matched.values())


def write_statements(client: Neo4jHttpClient, statements: list[dict[str, Any]], chunk_size: int = 50) -> None:
    query = """
    UNWIND $rows AS row
    MERGE (rs:KGNode:RecommendationStatement {code: row.props.code})
    SET rs += row.props
    WITH row, rs
    MATCH (rule:KGNode {code: row.rule_code})
    MATCH (action:KGNode {code: row.action_code})
    MERGE (rule)-[:has_recommendation_statement]->(rs)
    FOREACH (_ IN CASE WHEN row.recommendation_relation = 'recommends_action' THEN [1] ELSE [] END |
      MERGE (rs)-[:recommends_action]->(action)
    )
    FOREACH (_ IN CASE WHEN row.recommendation_relation = 'blocks_action' THEN [1] ELSE [] END |
      MERGE (rs)-[:blocks_action]->(action)
    )
    WITH row, rs
    CALL {
      WITH row, rs
      UNWIND row.evidence_codes AS evidence_code
      MATCH (ev:KGNode {code: evidence_code})
      MERGE (rs)-[:derived_from]->(ev)
      RETURN count(ev) AS evidence_link_count
    }
    CALL {
      WITH row, rs
      UNWIND CASE WHEN size(row.guideline_codes) = 0 THEN [null] ELSE row.guideline_codes END AS guideline_code
      OPTIONAL MATCH (g:KGNode {code: guideline_code})
      FOREACH (_ IN CASE WHEN g IS NULL THEN [] ELSE [1] END |
        MERGE (rs)-[:based_on_guideline]->(g)
      )
      RETURN count(g) AS guideline_link_count
    }
    OPTIONAL MATCH (stage:KGNode {code: row.stage_code})
    FOREACH (_ IN CASE WHEN stage IS NULL THEN [] ELSE [1] END |
      MERGE (stage)-[:has_recommendation_statement]->(rs)
    )
    WITH row, rs, evidence_link_count, guideline_link_count
    OPTIONAL MATCH (pathway:KGNode {code: row.pathway_code})
    FOREACH (_ IN CASE WHEN pathway IS NULL THEN [] ELSE [1] END |
      MERGE (pathway)-[:has_recommendation_statement]->(rs)
    )
    SET rs.evidence_link_count = evidence_link_count,
        rs.guideline_link_count = guideline_link_count,
        rs.guideline_match_status = CASE
          WHEN guideline_link_count > 0 THEN 'matched_to_guideline_node'
          ELSE 'not_matched_to_guideline_node'
        END
    """
    for start in range(0, len(statements), chunk_size):
        client.run(query, {"rows": statements[start : start + chunk_size]})


def validation(client: Neo4jHttpClient) -> dict[str, int]:
    checks = {
        "recommendation_statement_count": "MATCH (n:KGNode {entityType:'RecommendationStatement'}) RETURN count(n)",
        "orphan_without_action_count": """
            MATCH (n:KGNode {entityType:'RecommendationStatement'})
            WHERE NOT (n)-[:recommends_action|blocks_action]->(:KGNode)
            RETURN count(n)
        """,
        "orphan_without_evidence_count": """
            MATCH (n:KGNode {entityType:'RecommendationStatement'})
            WHERE NOT (n)-[:derived_from]->(:KGNode {entityType:'Evidence'})
            RETURN count(n)
        """,
        "candidate_without_statement_count": """
            MATCH (rule:KGNode {entityType:'ClinicalRule'})-[rel:recommends_action|blocks_action|has_recommended_action]->(action:KGNode)
            WHERE (rule)-[:supported_by_evidence]->(:KGNode {entityType:'Evidence'})
              AND NOT EXISTS {
                MATCH (rule)-[:has_recommendation_statement]->(rs:KGNode {entityType:'RecommendationStatement'})
                WHERE rs.rule_code = rule.code AND rs.action_code = action.code
            }
            RETURN count(DISTINCT rel)
        """,
        "duplicate_statement_triplet_count": """
            MATCH (rs:KGNode {entityType:'RecommendationStatement'})
            WITH rs.rule_code AS rule_code, rs.action_code AS action_code, rs.recommendation_type AS type, count(rs) AS c
            WHERE c > 1
            RETURN count(*)
        """,
        "technical_prefix_display_count": """
            MATCH (rs:KGNode {entityType:'RecommendationStatement'})
            WHERE rs.display_name STARTS WITH 'AMI诊断明细'
               OR rs.display_name STARTS WITH 'AMI鉴别'
               OR rs.display_name STARTS WITH 'STEMI诊断明细'
            RETURN count(rs)
        """,
    }
    output: dict[str, int] = {}
    for name, query in checks.items():
        output[name] = int(first_row(client.run(query))[0] or 0)
    return output


def write_csv(path: Path, statements: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "code",
        "scope_disease_code",
        "scope_target",
        "pathway_name",
        "stage_name",
        "rule_name",
        "recommendation_type",
        "action_name",
        "recommendation_class",
        "evidence_level",
        "primary_guideline_name",
        "primary_evidence_code",
        "cdss_display_level",
        "clinical_review_status",
        "formal_cdss_ready",
        "statement_summary",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in statements:
            props = item["props"]
            writer.writerow({field: props.get(field, "") for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate rule-action CDSS edges to RecommendationStatement nodes.")
    parser.add_argument("--connection-file", type=Path, default=Path("图谱数据库链接.txt"))
    parser.add_argument("--output-dir", type=Path, default=Path("心血管内科文献集合") / "_migration_20260707")
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = parse_connection_file(args.connection_file)
    client = Neo4jHttpClient(conn["uri"], conn["username"], conn["password"], args.database, 5, 1)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    candidates = fetch_candidates(client)
    attach_guidelines(candidates, fetch_guidelines(client))
    statements = [build_statement(row, now) for row in candidates]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "cdss_recommendation_statement_matrix.csv", statements)
    (args.output_dir / "recommendation_statement_payload.json").write_text(
        json.dumps(
            {
                "batch_id": BATCH_ID,
                "schema_version": SCHEMA_VERSION,
                "dry_run": args.dry_run,
                "candidate_count": len(candidates),
                "statement_count": len(statements),
                "statements": statements,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8-sig",
    )

    before = validation(client)
    if not args.dry_run:
        write_statements(client, statements)
    after = validation(client)
    summary = {
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "dry_run": args.dry_run,
        "candidate_count": len(candidates),
        "statement_count": len(statements),
        "before": before,
        "after": after,
        "output_dir": str(args.output_dir.resolve()),
        "matrix_file": str((args.output_dir / "cdss_recommendation_statement_matrix.csv").resolve()),
    }
    (args.output_dir / "recommendation_statement_migration_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
