from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "心血管内科文献集合"
SOURCE_BATCH = COLLECTION / "BATCH-CARD-CAD-20260623-001"
DEFAULT_OUTPUT = COLLECTION / "BATCH-CARD-CAD-CDSS-20260709-001_冠心病_CDSS决策层升级"
SCHEMA_VERSION = "V1.10"
SKILL_VERSION = "V1.40"
DEFAULT_BATCH_ID = "BATCH-CARD-CAD-CDSS-20260709-001"
CREATED_AT = "2026-07-09 00:00:00"

EVIDENCE_HINTS: dict[str, list[str]] = {
    "ACS:ECG-TROP": ["EVD-9A9489A580AF81E3951A-ACS"],
    "ACS:RISK": ["EVD-1EBE1F965F69378B6891-ACS"],
    "ACS:ANTITHROMBOTIC": ["EVD-A461939A6CD470240837-ACS"],
    "ACS:REVASC": ["EVD-37E0CF7DE9DBA48CF0EE-ACS"],
    "AMI:DIAG": ["EVD-23809B8617D9BDC7270C-ACS"],
    "AMI:REPERFUSION": ["EVD-656552BDE7ECDB150311-STEMI"],
    "AMI:PREVENT": ["EVD-D67B8B5A8FB0C8C69598-AMI"],
    "STEMI:ECG-TROP": ["EVD-192887A1ADE5529AFF5C-STEMI"],
    "STEMI:CONFIRM": ["EVD-75D1A8C9BD1F757657CB-STEMI"],
    "STEMI:PCI": ["EVD-656552BDE7ECDB150311-STEMI"],
    "STEMI:FIB-BLOCK": ["EVD-56AF2340E37314FCA705-AMI"],
    "STEMI:ANTITHROMBOTIC": ["EVD-A0E90401E2081C4E2CE8-STEMI"],
    "STEMI:FOLLOW": ["EVD-2E0A1554DC5CE6BE3BCA-STEMI"],
    "NSTEMI:DIAG": ["EVD-284C4E9C02BA9B546BC7-ACS"],
    "NSTEMI:RISK": ["EVD-37E0CF7DE9DBA48CF0EE-NSTEMI"],
    "NSTEMI:INVASIVE": ["EVD-37E0CF7DE9DBA48CF0EE-NSTEMI"],
    "NSTEMI:ANTITHROMBOTIC": ["EVD-A461939A6CD470240837-ACS"],
    "UA:DIAG": ["EVD-284C4E9C02BA9B546BC7-ACS"],
    "UA:RISK": ["EVD-37E0CF7DE9DBA48CF0EE-ACS"],
    "UA:TREAT": ["EVD-A461939A6CD470240837-ACS"],
    "CCS:ANTIANGINAL": ["EVD-E7859C0330307017B19C-ANGINA"],
    "CCS:PREVENT": ["EVD-9BAE5559CD59D53912E6-ANGINA"],
    "STABLEANGINA:MED": ["EVD-E7859C0330307017B19C-ANGINA"],
    "ICM:REVASC": ["EVD-3AA4B71F665A96D0B0D7-ICM"],
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def kg_id(code: str) -> str:
    return "KG_" + code.replace("-", "_")


def short_hash(value: str, length: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest().upper()[:length]


def rel_id(source: str, rel_type: str, target: str) -> str:
    return "REL-" + short_hash(f"{source}|{rel_type}|{target}", 20)


def text_of(row: dict[str, Any], *keys: str) -> str:
    values: list[str] = []
    for key in keys:
        value = row.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value if item not in (None, ""))
        elif value not in (None, ""):
            values.append(str(value))
    return " ".join(values)


def pick_name(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    for key in ("display_name", "preferred_name", "name", "title", "code"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def parse_recommendation_grade(text: str, source_type: str = "") -> tuple[str, str]:
    compact = re.sub(r"\s+", " ", text or "")
    patterns = [
        r"[（(]\s*(Ⅰ|Ⅱa|Ⅱb|Ⅱ|Ⅲ|I{1,3}a?|III)\s*[,，、]\s*([A-C](?:-EO)?)\s*[）)]",
        r"\b(Class|class)\s*(Ⅰ|Ⅱa|Ⅱb|Ⅱ|Ⅲ|I{1,3}a?|III)\b.*?\b(Level|level)\s*([A-C](?:-EO)?)\b",
        r"\b(I{1,3}a?|III)\s*[,，、]\s*([A-C](?:-EO)?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact)
        if not match:
            continue
        groups = [item for item in match.groups() if item and item.lower() not in {"class", "level"}]
        if len(groups) >= 2:
            return groups[0], groups[1]
    if "共识" in source_type or "共识" in compact or "专家建议" in compact:
        return "未分级/共识意见", "未分级/共识证据"
    return "未分级/指南未显式标注", "未分级/指南未显式标注"


def evidence_score(evidence: dict[str, Any], disease_code: str, tokens: list[str], preferred_sources: list[str]) -> int:
    source_name = str(evidence.get("source_name") or pick_name(evidence))
    source_type = str(evidence.get("source_type") or "")
    text = text_of(evidence, "evidence_text", "name", "source_section", "source_name")
    score = 0
    if evidence.get("disease_code") == disease_code:
        score += 20
    elif disease_code.split("-")[-1] in str(evidence.get("code", "")):
        score += 5
    if source_type in {"guideline", "consensus"}:
        score += 8
    if "authoritative_textbook" in source_type:
        score -= 8
    for preferred in preferred_sources:
        if preferred and preferred in source_name:
            score += 15
    for token in tokens:
        if token and token in text:
            score += 4
        if token and token in source_name:
            score += 3
    if re.search(r"（\s*(Ⅰ|Ⅱa|Ⅱb|Ⅲ|I{1,3}a?|III)\s*[,，、]\s*[A-C]", text):
        score += 7
    for year, bonus in [("2025", 7), ("2024", 6), ("2023", 5), ("2020", 2), ("2019", 2), ("2018", 1)]:
        if year in source_name:
            score += bonus
    # 避免把教材索引页、目录页当推荐证据。
    if "索引" in text or ("　" in text and "第" not in text and len(text) > 1000):
        score -= 30
    return score


class Builder:
    def __init__(self, source_batch: Path, output_dir: Path, batch_id: str) -> None:
        self.source_batch = source_batch
        self.output_dir = output_dir
        self.batch_id = batch_id
        self.created_at = CREATED_AT
        self.old_nodes = load_jsonl(source_batch / "05_data_instance" / "nodes_final.jsonl")
        self.old_relations = load_jsonl(source_batch / "05_data_instance" / "relations_final.jsonl")
        self.node_by_code = {str(row.get("code")): row for row in self.old_nodes if row.get("code")}
        self.nodes_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for node in self.old_nodes:
            self.nodes_by_type[str(node.get("entityType") or "")].append(node)
        self.evidence_nodes = self.nodes_by_type["Evidence"]
        self.new_nodes: dict[str, dict[str, Any]] = {}
        self.new_rels: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.recommendation_rows: list[dict[str, Any]] = []
        self.pathway_rows: list[dict[str, Any]] = []

    def existing_name(self, code: str) -> str:
        return pick_name(self.node_by_code.get(code)) or code

    def common_node_props(
        self,
        code: str,
        name: str,
        entity_type: str,
        disease_code: str,
        disease_name: str,
        scope_target: str,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "id": kg_id(code),
            "code": code,
            "name": name,
            "preferred_name": name,
            "display_name": name,
            "entityType": entity_type,
            "entityCategory": {
                "ClinicalPathway": "临床路径",
                "PathwayStage": "诊疗阶段",
                "ClinicalRule": "临床规则",
                "RecommendationStatement": "推荐陈述",
            }.get(entity_type, "CDSS"),
            "schema_version": SCHEMA_VERSION,
            "skill_version": SKILL_VERSION,
            "batch_id": self.batch_id,
            "scope_type": "disease_category",
            "scope_target": scope_target,
            "disease_code": disease_code,
            "disease_name": disease_name,
            "review_status": "ai_prechecked",
            "clinical_review_status": "pending_clinical_use_effect_review",
            "merge_status": "delta_ready",
            "conflict_status": "none",
            "formal_cdss_ready": False,
            "cdss_release_level": "test_recommendation",
            "ai_evidence_review_status": "ai_prechecked_source_traced",
            "created_at": self.created_at,
            **extra,
        }

    def add_node(self, payload: dict[str, Any]) -> None:
        code = str(payload["code"])
        if code in self.node_by_code:
            # 旧节点不重复创建；只创建决策层新增节点。
            return
        existing = self.new_nodes.get(code)
        if existing and existing != payload:
            raise ValueError(f"duplicate new node with different payload: {code}")
        self.new_nodes[code] = payload

    def add_rel(
        self,
        source: str,
        rel_type: str,
        target: str,
        category: str,
        *,
        evidence_ids: list[str] | None = None,
        clinical_review_status: str = "pending_clinical_use_effect_review",
        recommendation_code: str | None = None,
        rule_code: str | None = None,
    ) -> None:
        key = (source, rel_type, target)
        payload = {
            "id": rel_id(source, rel_type, target),
            "source_code": source,
            "relationType": rel_type,
            "target_code": target,
            "relationCategory": category,
            "schema_version": SCHEMA_VERSION,
            "skill_version": SKILL_VERSION,
            "batch_id": self.batch_id,
            "review_status": "ai_prechecked",
            "clinical_review_status": clinical_review_status,
            "merge_status": "delta_ready",
            "conflict_status": "none",
            "formal_cdss_ready": False,
            "cdss_release_level": "test_recommendation",
            "created_at": self.created_at,
            "evidence_ids": list(dict.fromkeys(evidence_ids or [])),
            "evidence_count": len(list(dict.fromkeys(evidence_ids or []))),
        }
        if recommendation_code:
            payload["recommendation_code"] = recommendation_code
        if rule_code:
            payload["rule_code"] = rule_code
        existing = self.new_rels.get(key)
        if existing:
            merged_ids = list(dict.fromkeys((existing.get("evidence_ids") or []) + payload["evidence_ids"]))
            existing["evidence_ids"] = merged_ids
            existing["evidence_count"] = len(merged_ids)
            return
        self.new_rels[key] = payload

    def select_evidence(
        self,
        disease_code: str,
        tokens: list[str],
        preferred_sources: list[str],
        limit: int = 3,
        evidence_hint_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        hinted: list[dict[str, Any]] = []
        for evidence_id in evidence_hint_ids or []:
            evidence = self.node_by_code.get(evidence_id)
            if evidence and evidence.get("entityType") == "Evidence":
                hinted.append(evidence)
        scored = [
            (evidence_score(evidence, disease_code, tokens, preferred_sources), evidence)
            for evidence in self.evidence_nodes
        ]
        scored = [item for item in scored if item[0] > 0]
        scored.sort(key=lambda item: (item[0], str(item[1].get("source_name")), str(item[1].get("code"))), reverse=True)
        output: list[dict[str, Any]] = []
        seen_sources: set[str] = set()
        for _, evidence in scored:
            code = str(evidence.get("code") or "")
            source = str(evidence.get("source_name") or "")
            if not code:
                continue
            if source in seen_sources and len(output) >= 1:
                continue
            output.append(evidence)
            seen_sources.add(source)
            if len(output) >= limit:
                break
        output = list({str(item["code"]): item for item in hinted + output}.values())
        if not output:
            raise RuntimeError(f"no evidence selected: {disease_code} tokens={tokens}")
        return output[:limit]

    def add_guideline_links(self, recommendation_code: str, evidence_list: list[dict[str, Any]]) -> None:
        for evidence in evidence_list:
            evidence_code = str(evidence["code"])
            self.add_rel(
                recommendation_code,
                "derived_from",
                evidence_code,
                "evidence",
                evidence_ids=[evidence_code],
                recommendation_code=recommendation_code,
                clinical_review_status="not_applicable",
            )
            self.add_rel(
                recommendation_code,
                "supported_by_evidence",
                evidence_code,
                "evidence",
                evidence_ids=[evidence_code],
                recommendation_code=recommendation_code,
                clinical_review_status="not_applicable",
            )
            document_id = evidence.get("document_id")
            guideline_code = f"SRC-{document_id}" if document_id else ""
            if guideline_code and guideline_code in self.node_by_code:
                self.add_rel(
                    recommendation_code,
                    "based_on_guideline",
                    guideline_code,
                    "evidence",
                    evidence_ids=[evidence_code],
                    recommendation_code=recommendation_code,
                    clinical_review_status="not_applicable",
                )

    def build_pathway(self, disease: dict[str, Any], stages: list[dict[str, Any]]) -> None:
        disease_code = disease["code"]
        disease_name = disease["name"]
        scope_target = "冠心病"
        pathway_code = f"PATHWAY-CDSS-CAD-{disease['short']}"
        pathway_name = f"{disease_name}专病动态CDSS路径"
        self.add_node(
            self.common_node_props(
                pathway_code,
                pathway_name,
                "ClinicalPathway",
                disease_code,
                disease_name,
                scope_target,
                pathway_goal="按患者当前状态分阶段触发诊断、鉴别、分层、治疗、随访与证据展示。",
                execution_boundary="图谱维护医学条件、推荐陈述和证据链；流程引擎读取EMR事实后决定是否触发和展示。",
            )
        )
        self.add_rel(disease_code, "has_clinical_pathway", pathway_code, "pathway")
        previous_stage_code = ""
        for stage_index, stage in enumerate(stages, start=1):
            stage_code = f"STAGE-CDSS-CAD-{disease['short']}-{stage_index:02d}-{stage['key']}"
            self.add_node(
                self.common_node_props(
                    stage_code,
                    f"{disease_name}{stage['name']}",
                    "PathwayStage",
                    disease_code,
                    disease_name,
                    scope_target,
                    pathway_code=pathway_code,
                    stage_order=stage_index,
                    stage_key=stage["key"],
                    stage_goal=stage["goal"],
                    trigger_condition=stage["trigger"],
                    exit_condition=stage["exit"],
                    required_patient_facts=stage.get("required_facts", []),
                )
            )
            self.add_rel(pathway_code, "has_pathway_stage", stage_code, "pathway")
            if previous_stage_code:
                self.add_rel(previous_stage_code, "next_pathway_stage", stage_code, "pathway")
            previous_stage_code = stage_code
            for rule_index, rule in enumerate(stage["rules"], start=1):
                self.build_rule_and_recommendation(disease, pathway_code, stage_code, stage_index, rule_index, rule)

    def build_rule_and_recommendation(
        self,
        disease: dict[str, Any],
        pathway_code: str,
        stage_code: str,
        stage_index: int,
        rule_index: int,
        rule: dict[str, Any],
    ) -> None:
        disease_code = disease["code"]
        disease_name = disease["name"]
        scope_target = "冠心病"
        rule_code = f"RULE-CDSS-CAD-{disease['short']}-{stage_index:02d}-{rule_index:02d}-{rule['key']}"
        rec_code = f"REC-CDSS-CAD-{disease['short']}-{stage_index:02d}-{rule_index:02d}-{rule['key']}"
        rule_hint_key = f"{disease['short']}:{rule['key']}"
        evidence_hint_ids = rule.get("evidence_hint_ids") or EVIDENCE_HINTS.get(rule_hint_key, [])
        evidence_list = self.select_evidence(
            disease_code,
            rule.get("evidence_tokens", []) + rule.get("action_names", []),
            rule.get("preferred_sources", []),
            evidence_hint_ids=evidence_hint_ids,
            limit=3,
        )
        primary = evidence_list[0]
        rec_class, evidence_level = parse_recommendation_grade(
            str(primary.get("evidence_text") or ""),
            str(primary.get("source_type") or primary.get("source_name") or ""),
        )
        evidence_ids = [str(item["code"]) for item in evidence_list]
        action_codes = list(dict.fromkeys(rule.get("recommend_actions", [])))
        block_codes = list(dict.fromkeys(rule.get("block_actions", [])))
        action_names = list(dict.fromkeys(self.existing_name(code) for code in action_codes))
        block_names = list(dict.fromkeys(self.existing_name(code) for code in block_codes))
        rule_name = rule["name"]
        statement = rule["statement"]
        structured_summary = rule.get("evidence_summary") or statement
        self.add_node(
            self.common_node_props(
                rule_code,
                rule_name,
                "ClinicalRule",
                disease_code,
                disease_name,
                scope_target,
                pathway_code=pathway_code,
                stage_code=stage_code,
                rule_logic=rule["logic"],
                trigger_condition=rule["trigger"],
                applicable_population=rule.get("applicable_population", f"{disease_name}相关患者"),
                exclusion_criteria=rule.get("exclusion_criteria", "存在禁忌证或证据不足时不自动执行，仅提示补充评估。"),
                required_patient_facts=rule.get("required_facts", []),
                evidence_ids=evidence_ids,
                recommendation_class=rec_class,
                evidence_level=evidence_level,
            )
        )
        self.add_node(
            self.common_node_props(
                rec_code,
                statement,
                "RecommendationStatement",
                disease_code,
                disease_name,
                scope_target,
                pathway_code=pathway_code,
                stage_code=stage_code,
                rule_code=rule_code,
                recommendation_type=rule.get("recommendation_type", "recommend"),
                statement_text=statement,
                display_title=statement,
                applicable_population=rule.get("applicable_population", f"{disease_name}相关患者"),
                exclusion_criteria=rule.get("exclusion_criteria", "存在禁忌证或证据不足时不自动执行，仅提示补充评估。"),
                required_patient_facts=rule.get("required_facts", []),
                recommended_action_codes=action_codes,
                recommended_action_names=action_names,
                blocked_action_codes=block_codes,
                blocked_action_names=block_names,
                recommendation_class=rec_class,
                evidence_level=evidence_level,
                primary_evidence_id=str(primary.get("code")),
                primary_source_name=str(primary.get("source_name") or ""),
                primary_source_page=primary.get("source_page"),
                primary_source_section=str(primary.get("source_section") or ""),
                primary_evidence_summary=structured_summary,
                primary_evidence_raw_excerpt=str(primary.get("evidence_text") or "")[:500],
                evidence_summary_type="structured_summary_with_raw_excerpt",
                evidence_ids=evidence_ids,
                evidence_count=len(evidence_ids),
                guideline_names=list(dict.fromkeys(str(item.get("source_name") or "") for item in evidence_list)),
                front_end_display_rule="推荐卡片只展示本推荐陈述直连主证据；更多证据点击展开，不展示疾病级证据池。",
            )
        )
        self.add_rel(stage_code, "has_stage_rule", rule_code, "rule", evidence_ids=evidence_ids, rule_code=rule_code)
        self.add_rel(stage_code, "has_recommendation_statement", rec_code, "recommendation", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
        self.add_rel(rule_code, "has_recommendation_statement", rec_code, "recommendation", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
        self.add_rel(disease_code, "has_clinical_rule", rule_code, "rule", evidence_ids=evidence_ids, rule_code=rule_code)
        for action_code in action_codes:
            self.add_rel(stage_code, "has_recommended_action", action_code, "pathway", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
            self.add_rel(rule_code, "recommends_action", action_code, "recommendation", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
            self.add_rel(rec_code, "recommends_action", action_code, "recommendation", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
        for action_code in block_codes:
            self.add_rel(rule_code, "blocks_action", action_code, "recommendation", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
            self.add_rel(rec_code, "blocks_action", action_code, "recommendation", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
        self.add_guideline_links(rec_code, evidence_list)
        self.recommendation_rows.append(
            {
                "疾病": disease_name,
                "阶段": self.new_nodes[stage_code]["name"],
                "规则编码": rule_code,
                "推荐陈述编码": rec_code,
                "推荐陈述": statement,
                "触发条件": rule["trigger"],
                "判断逻辑": rule["logic"],
                "推荐动作": "；".join(action_names),
                "阻断动作": "；".join(block_names),
                "推荐等级": rec_class,
                "证据等级": evidence_level,
                "主证据": str(primary.get("code")),
                "指南/来源": str(primary.get("source_name") or ""),
                "页码": primary.get("source_page"),
                "证据摘要": str(primary.get("evidence_text") or "")[:180],
                "结构化推荐摘要": structured_summary,
            }
        )
        self.pathway_rows.append(
            {
                "疾病": disease_name,
                "pathway_code": pathway_code,
                "stage_code": stage_code,
                "rule_code": rule_code,
                "recommendation_code": rec_code,
                "推荐动作codes": ";".join(action_codes),
                "阻断动作codes": ";".join(block_codes),
                "证据ID": ";".join(evidence_ids),
                "前端用法": "先按疾病加载ClinicalPathway，再按PathwayStage顺序匹配ClinicalRule，命中后展示RecommendationStatement。",
            }
        )

    def audit(self) -> dict[str, Any]:
        existing_codes = set(self.node_by_code) | set(self.new_nodes)
        missing_endpoints = [
            {"source_code": rel["source_code"], "relationType": rel["relationType"], "target_code": rel["target_code"]}
            for rel in self.new_rels.values()
            if rel["source_code"] not in existing_codes or rel["target_code"] not in existing_codes
        ]
        duplicate_relation_keys: list[str] = []
        recommendations = [node for node in self.new_nodes.values() if node.get("entityType") == "RecommendationStatement"]
        empty_required = []
        for rec in recommendations:
            for field in [
                "statement_text",
                "applicable_population",
                "exclusion_criteria",
                "recommendation_class",
                "evidence_level",
                "primary_evidence_id",
                "primary_source_name",
                "primary_source_page",
            ]:
                if rec.get(field) in (None, "", []):
                    empty_required.append({"code": rec["code"], "field": field})
        actionless = [
            rec["code"]
            for rec in recommendations
            if not rec.get("recommended_action_codes") and not rec.get("blocked_action_codes")
        ]
        no_evidence = [rec["code"] for rec in recommendations if not rec.get("evidence_ids")]
        stage_plan_name_collision = []
        treatment_names = {pick_name(node) for node in self.nodes_by_type["TreatmentPlan"]}
        for node in self.new_nodes.values():
            if node.get("entityType") == "PathwayStage" and pick_name(node) in treatment_names:
                stage_plan_name_collision.append({"code": node["code"], "name": pick_name(node)})
        mojibake_re = re.compile(r"(娌荤枟|鏂规|涓撶|鍔ㄦ|鑽|妫€|绠″||�)")
        mojibake = []
        for node in self.new_nodes.values():
            text = json.dumps(node, ensure_ascii=False)
            if mojibake_re.search(text):
                mojibake.append(node["code"])
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "batch_id": self.batch_id,
            "source_batch": str(self.source_batch),
            "output_dir": str(self.output_dir),
            "new_node_count": len(self.new_nodes),
            "new_relation_count": len(self.new_rels),
            "recommendation_statement_count": len(recommendations),
            "clinical_rule_count": sum(1 for node in self.new_nodes.values() if node.get("entityType") == "ClinicalRule"),
            "pathway_stage_count": sum(1 for node in self.new_nodes.values() if node.get("entityType") == "PathwayStage"),
            "clinical_pathway_count": sum(1 for node in self.new_nodes.values() if node.get("entityType") == "ClinicalPathway"),
            "missing_endpoint_count": len(missing_endpoints),
            "missing_endpoints": missing_endpoints[:50],
            "duplicate_relation_key_count": len(duplicate_relation_keys),
            "recommendation_required_empty_count": len(empty_required),
            "recommendation_required_empty": empty_required[:50],
            "recommendation_without_action_count": len(actionless),
            "recommendation_without_evidence_count": len(no_evidence),
            "stage_treatment_plan_name_collision_count": len(stage_plan_name_collision),
            "stage_treatment_plan_name_collision": stage_plan_name_collision,
            "mojibake_suspect_node_count": len(mojibake),
            "mojibake_suspect_node_codes": mojibake[:50],
            "hard_gate_pass": not (
                missing_endpoints
                or duplicate_relation_keys
                or empty_required
                or actionless
                or no_evidence
                or stage_plan_name_collision
                or mojibake
            ),
        }

    def write_outputs(self, audit: dict[str, Any]) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "batch_id": self.batch_id,
            "top_specialty": "心血管内科",
            "disease_category": "冠心病",
            "scope": "冠心病全病种CDSS决策层升级",
            "source_batch": str(self.source_batch),
            "schema_version": SCHEMA_VERSION,
            "skill_version": SKILL_VERSION,
            "created_at": self.created_at,
            "note": "只新增CDSS决策层节点/关系，不覆盖旧冠心病事实层。",
        }
        (self.output_dir / "00_config").mkdir(exist_ok=True)
        (self.output_dir / "00_config" / "batch_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_jsonl(self.output_dir / "01_delta" / "delta_nodes_upsert.jsonl", list(self.new_nodes.values()))
        write_jsonl(self.output_dir / "01_delta" / "delta_relations_add.jsonl", list(self.new_rels.values()))
        write_csv(
            self.output_dir / "02_audit" / "cdss_recommendation_statement_matrix.csv",
            self.recommendation_rows,
            ["疾病", "阶段", "规则编码", "推荐陈述编码", "推荐陈述", "触发条件", "判断逻辑", "推荐动作", "阻断动作", "推荐等级", "证据等级", "主证据", "指南/来源", "页码", "结构化推荐摘要", "证据摘要"],
        )
        write_csv(
            self.output_dir / "02_audit" / "cdss_pathway_rule_action_matrix.csv",
            self.pathway_rows,
            ["疾病", "pathway_code", "stage_code", "rule_code", "recommendation_code", "推荐动作codes", "阻断动作codes", "证据ID", "前端用法"],
        )
        (self.output_dir / "02_audit" / "quality_audit_summary.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary_md = f"""# 冠心病 CDSS 决策层升级交付说明

批次：{self.batch_id}

## 本批次做了什么

- 复用旧冠心病事实层节点和证据节点。
- 新增 ClinicalPathway、PathwayStage、ClinicalRule、RecommendationStatement。
- 推荐卡片证据以 RecommendationStatement 直连 Evidence 为准，不从疾病证据池二次推理。

## 可导入文件

- `01_delta/delta_nodes_upsert.jsonl`
- `01_delta/delta_relations_add.jsonl`

## 审计结果

- 新增节点：{audit['new_node_count']}
- 新增关系：{audit['new_relation_count']}
- 推荐陈述：{audit['recommendation_statement_count']}
- 临床规则：{audit['clinical_rule_count']}
- 路径阶段：{audit['pathway_stage_count']}
- 本地硬闸门：{"通过" if audit["hard_gate_pass"] else "未通过"}

## 前端/后端使用方式

1. 按疾病查 `has_clinical_pathway`。
2. 按 `has_pathway_stage` 和 `stage_order` 排序。
3. 根据患者 EMR facts 匹配 `ClinicalRule.trigger_condition/rule_logic`。
4. 命中规则后读取 `has_recommendation_statement`。
5. 推荐卡片只展示 `RecommendationStatement -> derived_from -> Evidence` 的主证据和扩展证据。
"""
        (self.output_dir / "03_reports" / "README_交付说明.md").parent.mkdir(exist_ok=True)
        (self.output_dir / "03_reports" / "README_交付说明.md").write_text(summary_md, encoding="utf-8")


def rule(
    key: str,
    name: str,
    statement: str,
    logic: str,
    trigger: str | list[str],
    recommend_actions: list[str] | None = None,
    *,
    block_actions: list[str] | None = None,
    evidence_tokens: list[str] | None = None,
    preferred_sources: list[str] | None = None,
    required_facts: list[str] | None = None,
    exclusion_criteria: str = "禁忌证、出血风险或关键患者数据缺失时，提示补充评估后再执行。",
    recommendation_type: str = "recommend",
) -> dict[str, Any]:
    if recommend_actions is None and isinstance(trigger, list):
        # 兼容简写：rule(..., logic, recommend_actions, ...)
        recommend_actions = trigger
        trigger = logic
    if recommend_actions is None:
        raise TypeError(f"rule {key} missing recommend_actions")
    return {
        "key": key,
        "name": name,
        "statement": statement,
        "logic": logic,
        "trigger": trigger,
        "recommend_actions": recommend_actions,
        "block_actions": block_actions or [],
        "action_names": [],
        "evidence_tokens": evidence_tokens or [],
        "preferred_sources": preferred_sources or [],
        "required_facts": required_facts or ["主诉", "发病时间", "生命体征", "心电图", "肌钙蛋白", "出血风险", "用药禁忌", "PCI可及性"],
        "exclusion_criteria": exclusion_criteria,
        "recommendation_type": recommendation_type,
    }


def stage(key: str, name: str, goal: str, trigger: str, exit_condition: str, rules: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "goal": goal,
        "trigger": trigger,
        "exit": exit_condition,
        "rules": rules,
    }


def cad_definitions() -> list[dict[str, Any]]:
    p_acs = ["ESC 急性冠脉综合征指南", "ACC／AHA", "ACS  ESC  2023", "NSTE-ACS CN 2024"]
    p_stemi = ["经皮冠状动脉介入治疗指南（2025）", "2018 STEMI院前溶栓治疗中国专家共识", "STEMI CN 2019", "STEMI ESC 2017"]
    p_nste = ["NSTE-ACS CN 2024", "NSTE-ACS ESC 2020", "NSTE-ACS ACC 2014"]
    p_ccs = ["CCS CN 2024", "CCS ESC 2024", "稳定性冠心病诊断与治疗指南 2018"]
    p_dapt = ["冠心病双联抗血小板治疗中国专家共识", "冠状动脉粥样硬化性心脏病患者药物治疗管理路径专家共识"]
    return [
        {
            "short": "ACS",
            "code": "DIS-CARD-CAD-ACS",
            "name": "急性冠脉综合征",
            "stages": [
                stage("ASSESS", "疑诊评估阶段", "急性胸痛或缺血等效症状先补齐心电图和心肌标志物。", "急性胸痛、胸闷、出汗、濒死感或疑似ACS", "完成首份心电图和心肌标志物", [
                    rule("ECG-TROP", "ACS首诊心电图与肌钙蛋白规则", "疑似ACS应优先进行心电图和心肌肌钙蛋白评估。", "疑似ACS或急性胸痛时，需快速完成心电图和肌钙蛋白检测。", "疑似ACS/急性胸痛", ["EXAM-ECG", "LAB-CARD-A9EC1D4DA037", "LAB-CARD-960C7CE8E22B"], evidence_tokens=["ACS", "心电图", "肌钙蛋白", "急性冠脉综合征"], preferred_sources=p_acs),
                ]),
                stage("CLASSIFY", "分型与风险分层阶段", "区分STEMI/NSTEMI/UA并进行早期风险分层。", "已有心电图或肌钙蛋白结果", "明确分型并进入对应治疗路径", [
                    rule("RISK", "ACS分型和风险分层规则", "ACS应结合心电图、肌钙蛋白、GRACE/TIMI评分进行分型和风险分层。", "ST段抬高、肌钙蛋白动态变化和危险评分共同决定后续路径。", "ACS初步成立", ["DXC-CARD-30F656ACB669", "RISK-CARD-118DE6495635", "RISK-CARD-9566F1411AE9", "RISK-CARD-638FD4C2210F"], evidence_tokens=["ACS", "GRACE", "TIMI", "风险分层"], preferred_sources=p_acs + p_nste),
                ]),
                stage("TREAT", "急性治疗决策阶段", "根据分型、时间窗和风险选择抗栓、再灌注或侵入策略。", "ACS分型和风险分层完成", "形成当前治疗推荐", [
                    rule("ANTITHROMBOTIC", "ACS抗栓治疗规则", "ACS抗栓治疗应拆分到抗血小板、P2Y12受体抑制剂和抗凝药物，并核对禁忌证。", "无活动性出血或禁忌证时进入抗栓治疗评估。", ["PLAN-CARD-42FD049DCDB5", "MED-CARD-9F606AC80BFD", "MED-CARD-00A158EBF21E", "MED-CARD-EAA01CFD434E", "PLAN-CARD-A1C4E6332D38"], evidence_tokens=["ACS", "抗血小板", "抗凝", "DAPT"], preferred_sources=p_dapt + p_acs),
                    rule("REVASC", "ACS血运重建评估规则", "ACS患者应按分型、风险和PCI可及性评估冠状动脉造影、PCI或再灌注治疗。", "高危ACS、持续缺血或STEMI时间窗内", ["EXAM-CAG", "PROC-CARD-E9ADC25A25E3", "PLAN-CARD-3972CBC8228B"], evidence_tokens=["ACS", "PCI", "冠状动脉造影", "再灌注"], preferred_sources=p_acs + p_stemi),
                ]),
            ],
        },
        {
            "short": "AMI",
            "code": "DIS-CARD-CAD-AMI",
            "name": "急性心肌梗死",
            "stages": [
                stage("DIAG", "诊断确认阶段", "确认急性心肌损伤和急性心肌缺血证据。", "心肌梗死疑诊或肌钙蛋白异常", "完成AMI诊断/排除", [
                    rule("DIAG", "AMI诊断确认规则", "急性心肌损伤证据合并缺血证据时支持急性心肌梗死诊断。", "肌钙蛋白动态升高/降低并有缺血症状、心电图或影像证据。", ["DXC-CARD-547346EE2FED", "LAB-CARD-A9EC1D4DA037", "EXAM-ECG", "EXAM-TTE"], evidence_tokens=["acute myocardial infarction", "心肌梗死", "肌钙蛋白", "缺血"], preferred_sources=["4TH universal definition of MI", "心肌梗死心电图诊断标准"]),
                ]),
                stage("REPERFUSION", "再灌注决策阶段", "按STEMI/NSTEMI分型、发病时间和PCI可及性选择再灌注或侵入策略。", "AMI诊断成立或高度疑似", "形成再灌注/侵入治疗策略", [
                    rule("REPERFUSION", "AMI再灌注/PCI评估规则", "AMI患者应结合分型、时间窗和PCI可及性评估急诊PCI、溶栓或冠脉造影。", "STEMI时间窗内或持续缺血；NSTEMI按风险决定侵入策略。", ["PLAN-CARD-3972CBC8228B", "PROC-CARD-E9ADC25A25E3", "EXAM-CAG", "PLAN-CARD-FULLBOOK-B87D3F557B"], evidence_tokens=["AMI", "心肌梗死", "PCI", "溶栓", "再灌注"], preferred_sources=p_stemi + p_nste),
                ]),
                stage("PREVENT", "二级预防与随访阶段", "稳定后落实抗栓、他汀、危险因素管理和随访。", "急性期稳定或出院准备", "生成二级预防和随访计划", [
                    rule("PREVENT", "AMI二级预防规则", "AMI稳定后应落实抗血小板、他汀、β受体阻滞剂和随访管理。", "急性期稳定、出院前或门诊随访。", ["PLAN-CARD-42FD049DCDB5", "MED-CARD-DAE0F0B68F1D", "MED-BETA-BLOCKER", "FU-CARD-ED1B0E900769"], evidence_tokens=["心肌梗死", "二级预防", "他汀", "抗血小板"], preferred_sources=p_dapt + ["青年急性心肌梗死诊断和治疗专家建议"]),
                ]),
            ],
        },
        {
            "short": "STEMI",
            "code": "DIS-CARD-CAD-STEMI",
            "name": "ST段抬高型心肌梗死",
            "stages": [
                stage("ASSESS", "疑诊评估阶段", "补齐心电图、肌钙蛋白和发病时间。", "急性胸痛或疑似STEMI", "完成首份心电图和肌钙蛋白", [
                    rule("ECG-TROP", "STEMI疑诊评估规则", "疑似STEMI应优先完成心电图、肌钙蛋白和发病时间评估。", "急性胸痛/缺血等效症状时立即评估ST段抬高和心肌损伤。", ["EXAM-ECG", "LAB-CARD-A9EC1D4DA037", "IND-CARD-F90926124AEA"], evidence_tokens=["STEMI", "心电图", "肌钙蛋白", "发病时间"], preferred_sources=p_stemi),
                ]),
                stage("CONFIRM", "诊断确认阶段", "明确STEMI诊断和是否需鉴别。", "已有心电图或肌钙蛋白结果", "确认STEMI或转入鉴别", [
                    rule("CONFIRM", "STEMI诊断确认规则", "持续ST段抬高或等效心电图表现合并急性心肌损伤支持STEMI诊断。", "ST段抬高/等效改变加肌钙蛋白动态变化。", ["DXC-CARD-36BC5337C93C", "IND-CARD-340F2703D39C", "LAB-CARD-A9EC1D4DA037"], evidence_tokens=["STEMI", "ST段抬高", "诊断", "肌钙蛋白"], preferred_sources=p_stemi + ["4TH universal definition of MI"]),
                ]),
                stage("REPERFUSION", "再灌注决策阶段", "评估急诊PCI可及性和溶栓适应证/禁忌证。", "STEMI已确诊或高度疑似且处于时间窗", "选择PCI、溶栓或转运", [
                    rule("PCI", "STEMI急诊PCI优先规则", "STEMI且处于再灌注时间窗时，应优先评估急诊PCI可及性。", "发病时间窗内、持续缺血或高危STEMI；PCI可及时优先PCI。", ["PLAN-CARD-3972CBC8228B", "PROC-CARD-E9ADC25A25E3", "EXAM-CAG"], evidence_tokens=["STEMI", "PCI", "再灌注", "时间窗"], preferred_sources=p_stemi),
                    rule("FIB-BLOCK", "STEMI溶栓禁忌阻断规则", "疑似主动脉夹层、活动性出血或重大出血风险未排除前，不得把溶栓作为可执行推荐。", "拟溶栓前必须核对禁忌证和出血风险。", [], block_actions=["PLAN-CARD-FULLBOOK-B87D3F557B", "PROC-CARD-DA0F467D4A30"], evidence_tokens=["STEMI", "溶栓", "禁忌", "出血"], preferred_sources=p_stemi, recommendation_type="block", exclusion_criteria="主动脉夹层、活动性出血、近期严重出血/手术等溶栓禁忌未排除。"),
                ]),
                stage("ANTITHROMBOTIC", "抗栓治疗管理阶段", "根据再灌注策略与出血风险推荐抗血小板和抗凝药物。", "拟行PCI/溶栓/保守治疗之一", "完成药物与禁忌核对", [
                    rule("ANTITHROMBOTIC", "STEMI抗栓治疗规则", "STEMI治疗应明确抗血小板、P2Y12受体抑制剂和抗凝药物。", "STEMI治疗过程中需结合再灌注策略和出血风险。", ["PLAN-CARD-42FD049DCDB5", "MED-CARD-9F606AC80BFD", "MED-CARD-00A158EBF21E", "MED-CARD-EAA01CFD434E", "PLAN-CARD-A1C4E6332D38", "MED-CARD-A49408D27901", "MED-CARD-2CCCA76B39F5"], evidence_tokens=["STEMI", "抗血小板", "P2Y12", "肝素"], preferred_sources=p_dapt + p_stemi),
                ]),
                stage("FOLLOW", "二级预防与随访阶段", "出院前后落实二级预防和随访。", "急性期稳定或出院准备", "形成二级预防计划", [
                    rule("FOLLOW", "STEMI二级预防规则", "STEMI稳定后应落实他汀、β受体阻滞剂、抗栓延续和随访。", "出院前/稳定期。", ["MED-CARD-498184546A72", "MED-CARD-DB0416905798", "MED-BETA-BLOCKER", "FU-CARD-CE3E83B4C5CE"], evidence_tokens=["STEMI", "二级预防", "随访", "他汀"], preferred_sources=p_stemi + p_dapt),
                ]),
            ],
        },
        {
            "short": "NSTEMI",
            "code": "DIS-CARD-CAD-NSTEMI",
            "name": "非ST段抬高型心肌梗死",
            "stages": [
                stage("DIAG", "诊断确认阶段", "确认非ST段抬高心肌梗死。", "胸痛或缺血表现且无持续ST段抬高", "完成NSTEMI/UA分层", [
                    rule("DIAG", "NSTEMI诊断确认规则", "无持续ST段抬高但肌钙蛋白升高/动态变化时支持NSTEMI诊断。", "缺血症状、心电图改变和肌钙蛋白动态变化共同判断。", ["DXC-CARD-AD026DED6958", "LAB-CARD-A9EC1D4DA037", "EXAM-ECG"], evidence_tokens=["NSTEMI", "NSTE-ACS", "肌钙蛋白", "诊断"], preferred_sources=p_nste),
                ]),
                stage("RISK", "风险分层阶段", "按GRACE/TIMI和临床高危特征决定侵入时机。", "NSTEMI诊断成立或高度疑似", "完成风险分层", [
                    rule("RISK", "NSTEMI风险分层规则", "NSTEMI应使用GRACE/TIMI及高危临床特征进行风险分层。", "肌钙蛋白、ST-T改变、血流动力学和GRACE/TIMI决定风险层级。", ["RISK-CARD-829873C257A6", "RISK-CARD-9566F1411AE9", "RISK-CARD-638FD4C2210F"], evidence_tokens=["NSTEMI", "GRACE", "TIMI", "风险"], preferred_sources=p_nste),
                ]),
                stage("INVASIVE", "侵入策略决策阶段", "根据风险决定早期侵入、冠脉造影或保守策略。", "风险分层完成", "形成侵入/保守策略", [
                    rule("INVASIVE", "NSTEMI早期侵入策略规则", "高危NSTEMI应评估冠状动脉造影和PCI等侵入策略。", "高危或持续缺血时评估早期侵入策略。", ["EXAM-CAG", "PROC-CARD-E9ADC25A25E3", "PLAN-CARD-TEXT-EEF9C97B59"], evidence_tokens=["NSTEMI", "侵入", "冠状动脉造影", "PCI"], preferred_sources=p_nste + ["经皮冠状动脉介入治疗指南（2025）"]),
                ]),
                stage("PREVENT", "抗栓与二级预防阶段", "落实抗栓、他汀和随访。", "治疗策略确定", "形成长期管理计划", [
                    rule("ANTITHROMBOTIC", "NSTEMI抗栓治疗规则", "NSTEMI抗栓治疗需结合缺血风险和出血风险明确抗血小板及抗凝药物。", "无禁忌证时评估抗血小板和抗凝治疗。", ["PLAN-CARD-42FD049DCDB5", "MED-CARD-9F606AC80BFD", "MED-CARD-00A158EBF21E", "MED-CARD-EAA01CFD434E", "PLAN-CARD-A1C4E6332D38", "FU-CARD-E0E295CC2D2E"], evidence_tokens=["NSTEMI", "抗血小板", "抗凝", "DAPT"], preferred_sources=p_dapt + p_nste),
                ]),
            ],
        },
        {
            "short": "UA",
            "code": "DIS-CARD-CAD-UA",
            "name": "不稳定型心绞痛",
            "stages": [
                stage("DIAG", "诊断与排除心梗阶段", "识别UA并排除NSTEMI。", "胸痛发作但肌钙蛋白未达心肌梗死标准", "完成UA/NSTEMI区分", [
                    rule("DIAG", "UA诊断规则", "不稳定型心绞痛需结合症状、心电图和肌钙蛋白排除NSTEMI。", "缺血性胸痛且心肌坏死标志物未达AMI标准。", ["DXC-CARD-CAD-UA-CURATED-20260628", "EXAM-ECG", "LAB-CARD-A9EC1D4DA037"], evidence_tokens=["不稳定型心绞痛", "NSTE-ACS", "肌钙蛋白", "诊断"], preferred_sources=p_nste),
                ]),
                stage("RISK", "风险分层阶段", "按GRACE/TIMI和持续缺血决定侵入评估。", "UA诊断成立或高度疑似", "形成风险分层", [
                    rule("RISK", "UA风险分层规则", "UA应按GRACE/TIMI及反复缺血症状评估风险。", "持续或复发缺血、高危评分提示需进一步侵入评估。", ["RISK-CARD-38E7349FFEB1", "RISK-CARD-9566F1411AE9", "RISK-CARD-638FD4C2210F"], evidence_tokens=["不稳定型心绞痛", "GRACE", "TIMI"], preferred_sources=p_nste),
                ]),
                stage("TREAT", "治疗决策阶段", "根据风险选择药物治疗、冠脉造影或PCI。", "风险分层完成", "形成治疗计划", [
                    rule("TREAT", "UA抗栓与侵入评估规则", "UA治疗应结合缺血风险和出血风险推荐抗血小板治疗，并对高危患者评估冠脉造影/PCI。", "高危UA或症状反复者进入侵入评估。", ["PLAN-CARD-42FD049DCDB5", "MED-CARD-9F606AC80BFD", "EXAM-CAG", "PROC-CARD-E9ADC25A25E3", "FU-CARD-0F81C23E250E"], evidence_tokens=["不稳定型心绞痛", "抗血小板", "冠状动脉造影", "PCI"], preferred_sources=p_dapt + p_nste),
                ]),
            ],
        },
        {
            "short": "CCS",
            "code": "DIS-CARD-CAD-CCS",
            "name": "慢性冠脉综合征",
            "stages": [
                stage("ASSESS", "症状与缺血评估阶段", "评估慢性胸痛、缺血证据和冠脉解剖风险。", "稳定胸痛或慢性冠脉疾病疑诊", "完成缺血/解剖评估", [
                    rule("TEST", "CCS检查选择规则", "慢性冠脉综合征应根据症状和风险选择心电图、负荷试验、冠脉CTA或冠脉造影。", "稳定胸痛或疑似慢性冠脉疾病。", ["EXAM-ECG", "EXAM-CARD-241B4B0218DF", "EXAM-CARD-F60922D428D5", "EXAM-CAG"], evidence_tokens=["慢性冠脉综合征", "负荷试验", "冠脉CTA", "冠状动脉造影"], preferred_sources=p_ccs),
                ]),
                stage("MED", "药物治疗阶段", "控制症状并进行二级预防。", "CCS诊断成立或高度疑似", "形成药物治疗方案", [
                    rule("ANTIANGINAL", "CCS抗心绞痛治疗规则", "CCS症状控制可评估β受体阻滞剂、硝酸酯类药物和钙通道阻滞剂。", "有心绞痛症状且无禁忌证。", ["MED-BETA-BLOCKER", "MED-CARD-55157DA54154", "MED-CARD-TEXT-28E925C6DE", "MED-CARD-CC1DDBE4EFA8"], evidence_tokens=["慢性冠脉综合征", "心绞痛", "β受体阻滞剂", "硝酸酯"], preferred_sources=p_ccs + ["稳定性冠心病诊断与治疗指南 2018"]),
                    rule("PREVENT", "CCS事件预防规则", "CCS应进行他汀、抗血小板和危险因素控制。", "确诊CCS或既往冠心病患者。", ["MED-CARD-DAE0F0B68F1D", "MED-CARD-9F606AC80BFD", "LAB-CARD-D3BEA3E2BC55", "FU-CARD-0841C3FAD521"], evidence_tokens=["慢性冠脉综合征", "他汀", "抗血小板", "危险因素"], preferred_sources=p_ccs + p_dapt),
                ]),
                stage("REVASC", "血运重建决策阶段", "对高危解剖或药物控制不佳者评估PCI/CABG。", "症状控制不佳或高危解剖/缺血", "形成血运重建决策", [
                    rule("REVASC", "CCS血运重建评估规则", "CCS存在高危缺血、重要冠脉病变或药物治疗仍症状明显时，应评估PCI或CABG。", "高危解剖/缺血或症状控制不佳。", ["PLAN-CARD-TEXT-EEF9C97B59", "PROC-CARD-E9ADC25A25E3", "PROC-CARD-BDB19D2C7A36", "EXAM-CAG"], evidence_tokens=["慢性冠脉综合征", "血运重建", "PCI", "CABG"], preferred_sources=p_ccs + ["2018 ESC EACTS Guidelines on myocardial revascularization"]),
                ]),
            ],
        },
        {
            "short": "STABLEANGINA",
            "code": "DIS-CARD-CAD-STABLE-ANGINA",
            "name": "稳定型心绞痛",
            "stages": [
                stage("DIAG", "诊断评估阶段", "评估典型心绞痛和诱发/缓解特点。", "劳力相关胸痛或稳定胸痛", "完成稳定型心绞痛诊断评估", [
                    rule("DIAG", "稳定型心绞痛诊断规则", "稳定型心绞痛应结合典型胸痛特征、心电图和负荷/影像学检查判断。", "劳力诱发、休息或硝酸甘油缓解的胸痛。", ["DXC-CARD-F0FABEDE13D8", "EXAM-ECG", "EXAM-CARD-241B4B0218DF", "EXAM-CARD-F60922D428D5"], evidence_tokens=["稳定型心绞痛", "心电图", "负荷试验", "冠脉CTA"], preferred_sources=["稳定性冠心病诊断与治疗指南 2018"] + p_ccs),
                ]),
                stage("TREAT", "症状控制和预防阶段", "控制心绞痛并降低事件风险。", "诊断成立或高度疑似", "形成药物和随访计划", [
                    rule("MED", "稳定型心绞痛药物治疗规则", "稳定型心绞痛可评估硝酸酯类、β受体阻滞剂、钙通道阻滞剂，同时进行他汀和抗血小板预防。", "症状需要治疗且无禁忌证。", ["MED-CARD-55157DA54154", "MED-BETA-BLOCKER", "MED-CARD-TEXT-28E925C6DE", "MED-CARD-DAE0F0B68F1D", "MED-CARD-9F606AC80BFD", "FU-CARD-22A2B8A765AC"], evidence_tokens=["稳定型心绞痛", "硝酸酯", "β受体阻滞剂", "他汀"], preferred_sources=["稳定性冠心病诊断与治疗指南 2018"] + p_ccs),
                ]),
            ],
        },
        {
            "short": "ICM",
            "code": "DIS-CARD-CAD-ICM",
            "name": "缺血性心肌病",
            "stages": [
                stage("EVAL", "心功能与冠脉评估阶段", "评估左室功能、心肌存活和冠脉病变。", "缺血性心肌病疑诊或心衰合并冠心病", "完成LVEF、存活心肌和冠脉评估", [
                    rule("EVAL", "ICM结构和缺血评估规则", "缺血性心肌病需评估超声心动图、LVEF、心脏磁共振/存活心肌和冠脉造影。", "心衰、左室功能下降或既往冠心病。", ["DXC-CARD-097806EACD3F", "EXAM-TTE", "IND-LVEF", "EXAM-CMR", "EXAM-CAG"], evidence_tokens=["缺血性心肌病", "存活心肌", "LVEF", "冠状动脉造影"], preferred_sources=["缺血性心肌病血运重建专家共识", "存活心肌无创影像学评价专家共识"]),
                ]),
                stage("TREAT", "药物和血运重建决策阶段", "根据心功能、存活心肌和冠脉病变选择药物/血运重建。", "ICM诊断成立", "形成药物和血运重建计划", [
                    rule("GDMT", "ICM基础药物治疗规则", "缺血性心肌病应进行冠心病二级预防和心功能相关药物管理。", "ICM诊断成立且无禁忌证。", ["MED-CARD-DAE0F0B68F1D", "MED-CARD-9F606AC80BFD", "MED-BETA-BLOCKER", "MED-CARD-E40082221530", "MED-DIURETIC"], evidence_tokens=["缺血性心肌病", "药物治疗", "他汀", "β受体阻滞剂"], preferred_sources=["缺血性心肌病血运重建专家共识"]),
                    rule("REVASC", "ICM血运重建评估规则", "ICM存在可重建冠脉病变和可存活心肌时，应评估PCI或CABG。", "存在可重建冠脉病变、缺血或存活心肌证据。", ["PLAN-CARD-TEXT-EEF9C97B59", "PROC-CARD-E9ADC25A25E3", "PROC-CARD-BDB19D2C7A36"], evidence_tokens=["缺血性心肌病", "血运重建", "PCI", "CABG", "存活心肌"], preferred_sources=["缺血性心肌病血运重建专家共识", "2018 ESC EACTS Guidelines on myocardial revascularization"]),
                ]),
            ],
        },
        {
            "short": "OLDMI",
            "code": "DIS-CARD-CAD-OLD-MI",
            "name": "陈旧性心肌梗死",
            "stages": [
                stage("ASSESS", "远期风险评估阶段", "评估既往心梗后左室功能、缺血和并发症。", "既往心肌梗死病史", "完成远期风险评估", [
                    rule("ASSESS", "陈旧性心梗远期评估规则", "陈旧性心肌梗死应评估心电图、超声心动图、LVEF和缺血/并发症风险。", "既往MI、症状复发或随访。", ["EXAM-ECG", "EXAM-TTE", "IND-LVEF", "EXAM-CAG"], evidence_tokens=["陈旧性心肌梗死", "心肌梗死后", "LVEF", "随访"], preferred_sources=["【医脉通】2020心肌梗死后心力衰竭防治专家共识", "冠状动脉粥样硬化性心脏病患者药物治疗管理路径专家共识"]),
                ]),
                stage("PREVENT", "二级预防阶段", "落实长期抗栓、调脂、心功能和生活方式管理。", "陈旧性心梗诊断成立", "形成长期管理计划", [
                    rule("PREVENT", "陈旧性心梗二级预防规则", "陈旧性心肌梗死需长期进行他汀、抗血小板、β受体阻滞剂和随访管理。", "稳定期或门诊复诊。", ["MED-CARD-DAE0F0B68F1D", "MED-CARD-9F606AC80BFD", "MED-BETA-BLOCKER", "FU-CARD-53E0DA55CCC2"], evidence_tokens=["心肌梗死后", "二级预防", "他汀", "抗血小板"], preferred_sources=p_dapt + ["冠状动脉粥样硬化性心脏病患者药物治疗管理路径专家共识"]),
                ]),
            ],
        },
        {
            "short": "SILENT",
            "code": "DIS-CARD-CAD-SILENT-ISCHEMIA",
            "name": "隐匿性冠心病",
            "stages": [
                stage("SCREEN", "筛查与缺血证据确认阶段", "在高危人群中确认无症状心肌缺血证据。", "高危人群或体检发现缺血线索", "确认缺血证据或排除", [
                    rule("SCREEN", "隐匿性冠心病筛查规则", "隐匿性冠心病应在高危人群中结合心电图、负荷试验、冠脉CTA或冠脉造影确认缺血/冠脉病变。", "无典型症状但存在高危因素或异常检查。", ["DXC-CARD-CAD-SILENT-ISCHEMIA-CURATED-20260628", "EXAM-ECG", "EXAM-CARD-241B4B0218DF", "EXAM-CARD-F60922D428D5", "EXAM-CAG"], evidence_tokens=["隐匿性冠心病", "无症状", "心肌缺血", "冠脉CTA"], preferred_sources=["稳定性冠心病诊断与治疗指南 2018"] + p_ccs),
                ]),
                stage("PREVENT", "风险控制与随访阶段", "降低冠脉事件风险并持续随访。", "隐匿性冠心病诊断成立", "形成预防和随访计划", [
                    rule("PREVENT", "隐匿性冠心病预防规则", "隐匿性冠心病应按冠心病风险管理进行他汀、抗血小板和危险因素控制。", "诊断成立且无用药禁忌证。", ["MED-CARD-DAE0F0B68F1D", "MED-CARD-9F606AC80BFD", "LAB-CARD-D3BEA3E2BC55", "FU-CARD-CAD-SILENT-ISCHEMIA-ANNUAL-FOLLOW-UP"], evidence_tokens=["隐匿性冠心病", "他汀", "抗血小板", "危险因素"], preferred_sources=p_ccs + p_dapt),
                ]),
            ],
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CAD-wide CDSS RecommendationStatement delta.")
    parser.add_argument("--source-batch", type=Path, default=SOURCE_BATCH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-id", default=DEFAULT_BATCH_ID)
    args = parser.parse_args()
    builder = Builder(args.source_batch, args.output_dir, args.batch_id)
    for disease in cad_definitions():
        builder.build_pathway(disease, disease["stages"])
    audit = builder.audit()
    builder.write_outputs(audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if audit["hard_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
