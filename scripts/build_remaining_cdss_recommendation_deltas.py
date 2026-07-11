from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.build_cad_cdss_recommendation_delta as cad


COLLECTION = ROOT / "心血管内科文献集合"
SCHEMA_VERSION = cad.SCHEMA_VERSION
SKILL_VERSION = cad.SKILL_VERSION
CREATED_AT = "2026-07-09 00:00:00"


BATCH_CONFIGS: dict[str, dict[str, Any]] = {
    "HF": {
        "order": 3,
        "source_batch": COLLECTION / "BATCH-CARD-HF-20260629-001",
        "batch_id": "BATCH-CARD-HF-CDSS-20260709-001",
        "output_dir": COLLECTION / "BATCH-CARD-HF-CDSS-20260709-001_心力衰竭_CDSS决策层升级",
        "scope_target": "心力衰竭",
        "prefix": "HF",
        "preferred_sources": ["中国心力衰竭诊断和治疗指南", "心力衰竭", "ESC", "ACC", "专家共识"],
    },
    "AF": {
        "order": 4,
        "source_batch": COLLECTION / "BATCH-CARD-AF-20260701-001_房颤_AtrialFibrillation",
        "batch_id": "BATCH-CARD-AF-CDSS-20260709-001",
        "output_dir": COLLECTION / "BATCH-CARD-AF-CDSS-20260709-001_房颤_AF_CDSS决策层升级",
        "scope_target": "房颤",
        "prefix": "AF",
        "preferred_sources": ["心房颤动", "房颤", "ESC", "ACC", "中国", "专家共识"],
    },
    "SVT_AFL": {
        "order": 5,
        "source_batch": COLLECTION / "BATCH-CARD-SVT-AFL-20260703-001_室上速房扑_SVT_AtrialFlutter",
        "batch_id": "BATCH-CARD-SVT-AFL-CDSS-20260709-001",
        "output_dir": COLLECTION / "BATCH-CARD-SVT-AFL-CDSS-20260709-001_室上速房扑_CDSS决策层升级",
        "scope_target": "室上性心动过速及心房扑动",
        "prefix": "SVTAFL",
        "preferred_sources": ["室上性心动过速", "心房扑动", "SVT", "Atrial Flutter", "ESC", "中国", "专家共识"],
    },
    "VA_SCD": {
        "order": 6,
        "source_batch": COLLECTION / "BATCH-CARD-VA-SCD-20260704-001_室性心律失常心脏性猝死_VA_SCD",
        "batch_id": "BATCH-CARD-VA-SCD-CDSS-20260709-001",
        "output_dir": COLLECTION / "BATCH-CARD-VA-SCD-CDSS-20260709-001_室性心律失常心脏性猝死_CDSS决策层升级",
        "scope_target": "室性心律失常及心脏性猝死",
        "prefix": "VASCD",
        "preferred_sources": ["室性心律失常", "心脏性猝死", "猝死", "ICD", "ESC", "中国", "专家共识"],
    },
    "BRADY_AVB": {
        "order": 7,
        "source_batch": COLLECTION / "BATCH-CARD-BRADY-AVB-20260705-001_缓慢性心律失常传导阻滞_Bradyarrhythmia_AVBlock",
        "batch_id": "BATCH-CARD-BRADY-AVB-CDSS-20260709-001",
        "output_dir": COLLECTION / "BATCH-CARD-BRADY-AVB-CDSS-20260709-001_缓慢性心律失常传导阻滞_CDSS决策层升级",
        "scope_target": "缓慢性心律失常及传导阻滞",
        "prefix": "BRADYAVB",
        "preferred_sources": ["缓慢性心律失常", "传导阻滞", "Brady", "AV block"],
    },
}


STAGE_SPECS = [
    {
        "key": "DIAG",
        "name": "诊断确认阶段",
        "goal": "补齐诊断依据、关键检查和必要的鉴别信息。",
        "types": ["DiagnosisCriteria", "Exam", "LabTest", "ExamIndicator", "DifferentialDiagnosis"],
        "max_per_type": {"DiagnosisCriteria": 2, "Exam": 4, "LabTest": 3, "ExamIndicator": 3, "DifferentialDiagnosis": 2},
        "tokens": ["诊断", "检查", "心电图", "超声", "磁共振", "实验室", "鉴别"],
    },
    {
        "key": "RISK",
        "name": "风险分层阶段",
        "goal": "识别危险因素、风险分层和需要升级处理的高危状态。",
        "types": ["RiskStratification", "RiskFactor", "Complication"],
        "max_per_type": {"RiskStratification": 3, "RiskFactor": 5, "Complication": 3},
        "tokens": ["风险", "危险因素", "分层", "猝死", "卒中", "并发症"],
    },
    {
        "key": "TREAT",
        "name": "治疗决策阶段",
        "goal": "根据病情、禁忌证和患者事实选择治疗方案、药物或操作。",
        "types": ["TreatmentPlan", "Medication", "Procedure"],
        "max_per_type": {"TreatmentPlan": 3, "Medication": 6, "Procedure": 4},
        "tokens": ["治疗", "药物", "手术", "操作", "介入", "起搏", "消融", "抗凝", "ICD", "CRT"],
    },
    {
        "key": "FOLLOW",
        "name": "随访管理阶段",
        "goal": "复评症状、检查结果、风险变化和长期管理计划。",
        "types": ["FollowUp", "Prognosis"],
        "max_per_type": {"FollowUp": 2, "Prognosis": 2},
        "tokens": ["随访", "复查", "预后", "长期", "复评"],
    },
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def short_hash(value: str, length: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest().upper()[:length]


def kg_id(code: str) -> str:
    return "KG_" + code.replace("-", "_")


def rel_id(source: str, rel_type: str, target: str) -> str:
    return "REL-" + short_hash(f"{source}|{rel_type}|{target}", 20)


def pick_name(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    for key in ("display_name", "preferred_name", "name", "title", "code"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def text_of(row: dict[str, Any], *keys: str) -> str:
    values: list[str] = []
    for key in keys:
        value = row.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value if item not in (None, ""))
        elif value not in (None, ""):
            values.append(str(value))
    return " ".join(values)


def safe_code_fragment(code: str) -> str:
    token = re.sub(r"^DIS-CARD-", "", code)
    token = re.sub(r"[^A-Za-z0-9]+", "-", token).strip("-")
    return token[:40] or short_hash(code, 10)


class RemainingCdssBuilder:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.source_batch: Path = config["source_batch"]
        self.output_dir: Path = config["output_dir"]
        self.batch_id: str = config["batch_id"]
        self.prefix: str = config["prefix"]
        self.scope_target: str = config["scope_target"]
        self.preferred_sources: list[str] = config.get("preferred_sources", [])
        self.old_nodes = load_jsonl(self.source_batch / "05_data_instance" / "nodes_final.jsonl")
        self.old_relations = load_jsonl(self.source_batch / "05_data_instance" / "relations_final.jsonl")
        self.node_by_code = {str(row.get("code")): row for row in self.old_nodes if row.get("code")}
        self.nodes_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.related_by_disease: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        self.direct_targets_by_disease: dict[str, set[str]] = defaultdict(set)
        for node in self.old_nodes:
            entity_type = str(node.get("entityType") or "")
            self.nodes_by_type[entity_type].append(node)
            disease_code = str(node.get("disease_code") or "")
            if disease_code:
                self.related_by_disease[disease_code][entity_type].append(node)
        for rel in self.old_relations:
            src = str(rel.get("source_code") or rel.get("source") or "")
            tgt = str(rel.get("target_code") or rel.get("target") or "")
            if src and tgt:
                self.direct_targets_by_disease[src].add(tgt)
        self.evidence_nodes = self.nodes_by_type["Evidence"]
        self.new_nodes: dict[str, dict[str, Any]] = {}
        self.new_rels: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.recommendation_rows: list[dict[str, Any]] = []
        self.pathway_rows: list[dict[str, Any]] = []

    def existing_name(self, code: str) -> str:
        return pick_name(self.node_by_code.get(code)) or code

    def common_node_props(self, code: str, name: str, entity_type: str, disease: dict[str, Any], **extra: Any) -> dict[str, Any]:
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
            "scope_target": self.scope_target,
            "disease_code": disease["code"],
            "disease_name": disease["name"],
            "review_status": "ai_prechecked",
            "clinical_review_status": "pending_clinical_use_effect_review",
            "merge_status": "delta_ready",
            "conflict_status": "none",
            "formal_cdss_ready": False,
            "cdss_release_level": "test_recommendation",
            "ai_evidence_review_status": "ai_prechecked_source_traced",
            "created_at": CREATED_AT,
            **extra,
        }

    def add_node(self, payload: dict[str, Any]) -> None:
        code = str(payload["code"])
        if code in self.node_by_code:
            return
        existing = self.new_nodes.get(code)
        if existing and existing != payload:
            raise ValueError(f"duplicate new node with different payload: {code}")
        self.new_nodes[code] = payload

    def add_rel(self, source: str, rel_type: str, target: str, category: str, *, evidence_ids: list[str] | None = None, recommendation_code: str | None = None, rule_code: str | None = None, clinical_review_status: str = "pending_clinical_use_effect_review") -> None:
        ids = list(dict.fromkeys(evidence_ids or []))
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
            "created_at": CREATED_AT,
            "evidence_ids": ids,
            "evidence_count": len(ids),
        }
        if recommendation_code:
            payload["recommendation_code"] = recommendation_code
        if rule_code:
            payload["rule_code"] = rule_code
        existing = self.new_rels.get(key)
        if existing:
            merged = list(dict.fromkeys((existing.get("evidence_ids") or []) + ids))
            existing["evidence_ids"] = merged
            existing["evidence_count"] = len(merged)
            return
        self.new_rels[key] = payload

    def disease_nodes(self) -> list[dict[str, Any]]:
        diseases = [row for row in self.nodes_by_type["Disease"] if row.get("code")]
        diseases.sort(key=lambda row: str(row.get("code")))
        return [{"code": str(row["code"]), "name": pick_name(row)} for row in diseases]

    def collect_actions(self, disease_code: str, entity_types: list[str], max_per_type: dict[str, int]) -> list[str]:
        output: list[str] = []
        seen_names: set[tuple[str, str]] = set()
        direct_targets = self.direct_targets_by_disease.get(disease_code, set())
        for entity_type in entity_types:
            candidates: list[dict[str, Any]] = []
            for node in self.related_by_disease.get(disease_code, {}).get(entity_type, []):
                candidates.append(node)
            for code in direct_targets:
                node = self.node_by_code.get(code)
                if node and node.get("entityType") == entity_type:
                    candidates.append(node)
            unique: dict[str, dict[str, Any]] = {}
            for node in candidates:
                code = str(node.get("code") or "")
                if code:
                    unique[code] = node
            scored = []
            for code, node in unique.items():
                name = pick_name(node)
                if not name or self.is_shell_name(name):
                    continue
                score = 0
                if code in direct_targets:
                    score += 4
                if str(node.get("disease_code") or "") == disease_code:
                    score += 3
                score += {
                    "DiagnosisCriteria": 10,
                    "TreatmentPlan": 9,
                    "RiskStratification": 8,
                    "FollowUp": 8,
                    "Exam": 7,
                    "Medication": 6,
                    "Procedure": 6,
                    "LabTest": 5,
                    "ExamIndicator": 4,
                    "DifferentialDiagnosis": 3,
                    "RiskFactor": 2,
                    "Complication": 2,
                    "Prognosis": 1,
                }.get(entity_type, 0)
                scored.append((score, name, code))
            scored.sort(key=lambda item: (-item[0], item[1], item[2]))
            picked = 0
            for _, name, code in scored:
                key = (entity_type, name)
                if key in seen_names:
                    continue
                output.append(code)
                seen_names.add(key)
                picked += 1
                if picked >= max_per_type.get(entity_type, 3):
                    break
        return output

    @staticmethod
    def is_shell_name(name: str) -> bool:
        shells = {"诊断标准", "鉴别诊断", "治疗方案", "药物治疗", "一般治疗", "随访方案", "预后", "预后良好", "预后不良"}
        return name.strip() in shells

    def select_evidence(self, disease: dict[str, Any], tokens: list[str], preferred_sources: list[str], limit: int = 3) -> list[dict[str, Any]]:
        disease_code = disease["code"]
        disease_name = disease["name"]
        token_list = [disease_name, *tokens]
        scored: list[tuple[int, dict[str, Any]]] = []
        for evidence in self.evidence_nodes:
            source_name = str(evidence.get("source_name") or "")
            source_type = str(evidence.get("source_type") or "")
            text = text_of(evidence, "evidence_text", "name", "source_section", "source_name")
            score = 0
            if evidence.get("disease_code") == disease_code:
                score += 25
            if disease_name and disease_name in text:
                score += 15
            if source_type in {"guideline", "consensus"}:
                score += 8
            if "authoritative_textbook" in source_type:
                score -= 4
            for preferred in preferred_sources:
                if preferred and preferred in source_name:
                    score += 10
            for token in token_list:
                if token and token in text:
                    score += 3
                if token and token in source_name:
                    score += 2
            if re.search(r"（\s*(Ⅰ|Ⅱa|Ⅱb|Ⅲ|I{1,3}a?|III)\s*[,，、]\s*[A-C]", text):
                score += 5
            for year, bonus in [("2025", 7), ("2024", 6), ("2023", 5), ("2020", 2), ("2019", 2), ("2018", 1)]:
                if year in source_name:
                    score += bonus
            if score > 0:
                scored.append((score, evidence))
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
        if not output:
            raise RuntimeError(f"no evidence selected: {disease_code} {disease_name} tokens={tokens}")
        return output

    def add_guideline_links(self, rec_code: str, evidence_list: list[dict[str, Any]]) -> None:
        for evidence in evidence_list:
            evidence_code = str(evidence["code"])
            self.add_rel(rec_code, "derived_from", evidence_code, "evidence", evidence_ids=[evidence_code], recommendation_code=rec_code, clinical_review_status="not_applicable")
            self.add_rel(rec_code, "supported_by_evidence", evidence_code, "evidence", evidence_ids=[evidence_code], recommendation_code=rec_code, clinical_review_status="not_applicable")
            document_id = evidence.get("document_id")
            guideline_code = f"SRC-{document_id}" if document_id else ""
            if guideline_code and guideline_code in self.node_by_code:
                self.add_rel(rec_code, "based_on_guideline", guideline_code, "evidence", evidence_ids=[evidence_code], recommendation_code=rec_code, clinical_review_status="not_applicable")

    def build(self) -> dict[str, Any]:
        for disease in self.disease_nodes():
            self.build_disease_pathway(disease)
        audit = self.audit()
        self.write_outputs(audit)
        return audit

    def build_disease_pathway(self, disease: dict[str, Any]) -> None:
        disease_code = disease["code"]
        disease_name = disease["name"]
        short = safe_code_fragment(disease_code)
        pathway_code = f"PATHWAY-CDSS-{self.prefix}-{short}"
        self.add_node(
            self.common_node_props(
                pathway_code,
                f"{disease_name}专病动态CDSS路径",
                "ClinicalPathway",
                disease,
                pathway_goal="按患者当前状态分阶段触发诊断、风险分层、治疗、随访与证据展示。",
                execution_boundary="图谱维护医学条件、推荐陈述和证据链；流程引擎读取EMR事实后决定是否触发和展示。",
            )
        )
        self.add_rel(disease_code, "has_clinical_pathway", pathway_code, "pathway")
        previous_stage_code = ""
        stage_index = 0
        for stage_spec in STAGE_SPECS:
            actions = self.collect_actions(disease_code, stage_spec["types"], stage_spec["max_per_type"])
            if not actions:
                continue
            stage_index += 1
            stage_code = f"STAGE-CDSS-{self.prefix}-{short}-{stage_index:02d}-{stage_spec['key']}"
            self.add_node(
                self.common_node_props(
                    stage_code,
                    f"{disease_name}{stage_spec['name']}",
                    "PathwayStage",
                    disease,
                    pathway_code=pathway_code,
                    stage_order=stage_index,
                    stage_key=stage_spec["key"],
                    stage_goal=stage_spec["goal"],
                    trigger_condition=self.stage_trigger(disease_name, stage_spec["key"]),
                    exit_condition=self.stage_exit(disease_name, stage_spec["key"]),
                    required_patient_facts=self.required_facts(stage_spec["key"]),
                )
            )
            self.add_rel(pathway_code, "has_pathway_stage", stage_code, "pathway")
            if previous_stage_code:
                self.add_rel(previous_stage_code, "next_pathway_stage", stage_code, "pathway")
            previous_stage_code = stage_code
            self.build_rule_and_recommendation(disease, short, pathway_code, stage_code, stage_index, stage_spec, actions)

    @staticmethod
    def stage_trigger(disease_name: str, key: str) -> str:
        if key == "DIAG":
            return f"疑似{disease_name}、症状/体征/检查提示异常或需排除该病。"
        if key == "RISK":
            return f"{disease_name}诊断成立或高度疑似，需要判断危险分层和并发症风险。"
        if key == "TREAT":
            return f"{disease_name}诊断成立，且需要根据病情、禁忌证和患者偏好制定治疗。"
        return f"{disease_name}稳定期、出院后、治疗调整后或需要长期管理。"

    @staticmethod
    def stage_exit(disease_name: str, key: str) -> str:
        if key == "DIAG":
            return f"完成{disease_name}诊断、排除或转入鉴别诊断。"
        if key == "RISK":
            return "完成风险分层并识别高危状态。"
        if key == "TREAT":
            return "形成当前治疗建议、禁忌排除和后续复评计划。"
        return "形成随访周期、复查项目和再次触发条件。"

    @staticmethod
    def required_facts(key: str) -> list[str]:
        base = ["主诉", "现病史", "既往史", "用药史", "生命体征"]
        if key == "DIAG":
            return base + ["心电图", "超声心动图", "实验室检查", "影像检查"]
        if key == "RISK":
            return base + ["诊断结果", "危险因素", "并发症", "评分/分层结果"]
        if key == "TREAT":
            return base + ["诊断结果", "禁忌证", "肝肾功能", "出血风险", "患者偏好"]
        return base + ["治疗方案", "复查结果", "症状变化", "不良事件"]

    def build_rule_and_recommendation(self, disease: dict[str, Any], short: str, pathway_code: str, stage_code: str, stage_index: int, stage_spec: dict[str, Any], action_codes: list[str]) -> None:
        disease_name = disease["name"]
        key = stage_spec["key"]
        rule_code = f"RULE-CDSS-{self.prefix}-{short}-{stage_index:02d}-01-{key}"
        rec_code = f"REC-CDSS-{self.prefix}-{short}-{stage_index:02d}-01-{key}"
        action_names = [self.existing_name(code) for code in action_codes]
        tokens = [disease_name, key, *stage_spec["tokens"], *action_names]
        evidence_list = self.select_evidence(disease, tokens, self.preferred_sources, limit=3)
        primary = evidence_list[0]
        rec_class, evidence_level = cad.parse_recommendation_grade(str(primary.get("evidence_text") or ""), str(primary.get("source_type") or primary.get("source_name") or ""))
        evidence_ids = [str(row["code"]) for row in evidence_list]
        statement = self.statement_for_stage(disease_name, key, action_names)
        logic = self.logic_for_stage(disease_name, key, action_names)
        trigger = self.stage_trigger(disease_name, key)
        exclusion = self.exclusion_for_stage(key)
        primary_page = primary.get("source_page") if primary.get("source_page") not in (None, "") else "N/A-非分页来源"
        self.add_node(
            self.common_node_props(
                rule_code,
                f"{disease_name}{stage_spec['name']}规则",
                "ClinicalRule",
                disease,
                pathway_code=pathway_code,
                stage_code=stage_code,
                rule_logic=logic,
                trigger_condition=trigger,
                applicable_population=f"{disease_name}相关患者",
                exclusion_criteria=exclusion,
                required_patient_facts=self.required_facts(key),
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
                disease,
                pathway_code=pathway_code,
                stage_code=stage_code,
                rule_code=rule_code,
                recommendation_type="recommend",
                statement_text=statement,
                display_title=statement,
                applicable_population=f"{disease_name}相关患者",
                exclusion_criteria=exclusion,
                required_patient_facts=self.required_facts(key),
                recommended_action_codes=action_codes,
                recommended_action_names=action_names,
                blocked_action_codes=[],
                blocked_action_names=[],
                recommendation_class=rec_class,
                evidence_level=evidence_level,
                primary_evidence_id=str(primary.get("code")),
                primary_source_name=str(primary.get("source_name") or ""),
                primary_source_page=primary_page,
                primary_source_section=str(primary.get("source_section") or ""),
                primary_evidence_summary=statement,
                primary_evidence_raw_excerpt=str(primary.get("evidence_text") or "")[:500],
                evidence_summary_type="structured_summary_with_raw_excerpt",
                evidence_ids=evidence_ids,
                evidence_count=len(evidence_ids),
                guideline_names=list(dict.fromkeys(str(row.get("source_name") or "") for row in evidence_list)),
                front_end_display_rule="推荐卡片只展示本推荐陈述直连主证据；更多证据点击展开，不展示疾病级证据池。",
            )
        )
        self.add_rel(stage_code, "has_stage_rule", rule_code, "rule", evidence_ids=evidence_ids, rule_code=rule_code)
        self.add_rel(stage_code, "has_recommendation_statement", rec_code, "recommendation", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
        self.add_rel(rule_code, "has_recommendation_statement", rec_code, "recommendation", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
        self.add_rel(disease["code"], "has_clinical_rule", rule_code, "rule", evidence_ids=evidence_ids, rule_code=rule_code)
        for action_code in action_codes:
            self.add_rel(stage_code, "has_recommended_action", action_code, "pathway", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
            self.add_rel(rule_code, "recommends_action", action_code, "recommendation", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
            self.add_rel(rec_code, "recommends_action", action_code, "recommendation", evidence_ids=evidence_ids, recommendation_code=rec_code, rule_code=rule_code)
        self.add_guideline_links(rec_code, evidence_list)
        self.recommendation_rows.append(
            {
                "疾病": disease_name,
                "阶段": self.new_nodes[stage_code]["name"],
                "规则编码": rule_code,
                "推荐陈述编码": rec_code,
                "推荐陈述": statement,
                "触发条件": trigger,
                "判断逻辑": logic,
                "推荐动作": "；".join(action_names),
                "阻断动作": "",
                "推荐等级": rec_class,
                "证据等级": evidence_level,
                "主证据": str(primary.get("code")),
                "指南/来源": str(primary.get("source_name") or ""),
                "页码": primary_page,
                "结构化推荐摘要": statement,
                "证据摘要": str(primary.get("evidence_text") or "")[:180],
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
                "阻断动作codes": "",
                "证据ID": ";".join(evidence_ids),
                "前端用法": "先按疾病加载ClinicalPathway，再按PathwayStage顺序匹配ClinicalRule，命中后展示RecommendationStatement。",
            }
        )

    @staticmethod
    def statement_for_stage(disease_name: str, key: str, action_names: list[str]) -> str:
        names = "、".join(action_names[:5])
        if len(action_names) > 5:
            names += "等"
        if key == "DIAG":
            return f"疑似{disease_name}时，应结合{names}进行诊断确认和必要鉴别。"
        if key == "RISK":
            return f"{disease_name}确诊或高度疑似后，应结合{names}进行风险分层和高危因素识别。"
        if key == "TREAT":
            return f"{disease_name}治疗应根据病情严重程度、禁忌证和患者特征选择{names}。"
        return f"{disease_name}稳定期或治疗后，应按{names}进行随访和复评。"

    @staticmethod
    def logic_for_stage(disease_name: str, key: str, action_names: list[str]) -> str:
        if key == "DIAG":
            return f"当患者症状、体征或检查提示{disease_name}可能时，先补齐诊断标准、关键检查和鉴别诊断依据。"
        if key == "RISK":
            return f"在{disease_name}诊断成立或高度疑似后，结合危险因素、评分/分层和并发症决定后续处理强度。"
        if key == "TREAT":
            return f"在诊断和风险评估基础上，结合禁忌证、合并症和患者状态触发治疗推荐。"
        return f"治疗后或稳定期按照随访计划复评疗效、不良事件和风险变化。"

    @staticmethod
    def exclusion_for_stage(key: str) -> str:
        if key == "DIAG":
            return "关键检查缺失、诊断条件不足或存在更紧急鉴别诊断时，不自动确认诊断。"
        if key == "RISK":
            return "诊断尚未成立、关键风险指标缺失或评分适用条件不满足时，不自动给出高危结论。"
        if key == "TREAT":
            return "存在禁忌证、药物过敏、严重肝肾功能异常、妊娠/出血等风险或患者关键事实缺失时，不自动执行推荐。"
        return "未完成初始治疗、病情不稳定或缺少复查结果时，提示补充评估后再随访分层。"

    def audit(self) -> dict[str, Any]:
        existing_codes = set(self.node_by_code) | set(self.new_nodes)
        missing_endpoints = [
            {"source_code": rel["source_code"], "relationType": rel["relationType"], "target_code": rel["target_code"]}
            for rel in self.new_rels.values()
            if rel["source_code"] not in existing_codes or rel["target_code"] not in existing_codes
        ]
        recommendations = [node for node in self.new_nodes.values() if node.get("entityType") == "RecommendationStatement"]
        empty_required = []
        for rec in recommendations:
            for field in ["statement_text", "applicable_population", "exclusion_criteria", "recommendation_class", "evidence_level", "primary_evidence_id", "primary_source_name", "primary_source_page", "primary_evidence_summary", "primary_evidence_raw_excerpt"]:
                if rec.get(field) in (None, "", []):
                    empty_required.append({"code": rec["code"], "field": field})
        actionless = [rec["code"] for rec in recommendations if not rec.get("recommended_action_codes") and not rec.get("blocked_action_codes")]
        no_evidence = [rec["code"] for rec in recommendations if not rec.get("evidence_ids")]
        treatment_names = {pick_name(node) for node in self.nodes_by_type["TreatmentPlan"]}
        stage_plan_name_collision = [
            {"code": node["code"], "name": pick_name(node)}
            for node in self.new_nodes.values()
            if node.get("entityType") == "PathwayStage" and pick_name(node) in treatment_names
        ]
        mojibake_re = re.compile(r"(娌荤枟|鏂规|涓撶|鍔ㄦ|鑽|妫€|绠″||�)")
        mojibake = [node["code"] for node in self.new_nodes.values() if mojibake_re.search(json.dumps(node, ensure_ascii=False))]
        disease_count = len(self.disease_nodes())
        pathway_count = sum(1 for node in self.new_nodes.values() if node.get("entityType") == "ClinicalPathway")
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "batch_id": self.batch_id,
            "source_batch": str(self.source_batch),
            "output_dir": str(self.output_dir),
            "scope_target": self.scope_target,
            "disease_count": disease_count,
            "new_node_count": len(self.new_nodes),
            "new_relation_count": len(self.new_rels),
            "recommendation_statement_count": len(recommendations),
            "clinical_rule_count": sum(1 for node in self.new_nodes.values() if node.get("entityType") == "ClinicalRule"),
            "pathway_stage_count": sum(1 for node in self.new_nodes.values() if node.get("entityType") == "PathwayStage"),
            "clinical_pathway_count": pathway_count,
            "missing_endpoint_count": len(missing_endpoints),
            "missing_endpoints": missing_endpoints[:50],
            "recommendation_required_empty_count": len(empty_required),
            "recommendation_required_empty": empty_required[:50],
            "recommendation_without_action_count": len(actionless),
            "recommendation_without_evidence_count": len(no_evidence),
            "stage_treatment_plan_name_collision_count": len(stage_plan_name_collision),
            "stage_treatment_plan_name_collision": stage_plan_name_collision,
            "mojibake_suspect_node_count": len(mojibake),
            "mojibake_suspect_node_codes": mojibake[:50],
            "hard_gate_pass": not (missing_endpoints or empty_required or actionless or no_evidence or stage_plan_name_collision or mojibake or pathway_count != disease_count),
        }

    def write_outputs(self, audit: dict[str, Any]) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "batch_id": self.batch_id,
            "top_specialty": "心血管内科",
            "disease_category": self.scope_target,
            "scope": f"{self.scope_target} CDSS决策层升级",
            "source_batch": str(self.source_batch),
            "schema_version": SCHEMA_VERSION,
            "skill_version": SKILL_VERSION,
            "created_at": CREATED_AT,
            "note": f"只新增{self.scope_target} CDSS决策层节点/关系，不覆盖旧事实层。",
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
        readme = f"""# {self.scope_target} CDSS 决策层升级交付说明

批次：{self.batch_id}

## 本批次做了什么

- 复用旧事实层节点和证据节点。
- 新增 ClinicalPathway、PathwayStage、ClinicalRule、RecommendationStatement。
- 推荐卡片证据以 RecommendationStatement 直连 Evidence 为准，不从疾病证据池二次推理。

## 可导入文件

- `01_delta/delta_nodes_upsert.jsonl`
- `01_delta/delta_relations_add.jsonl`

## 审计结果

- 覆盖疾病：{audit['disease_count']}
- 新增节点：{audit['new_node_count']}
- 新增关系：{audit['new_relation_count']}
- 推荐陈述：{audit['recommendation_statement_count']}
- 临床规则：{audit['clinical_rule_count']}
- 路径阶段：{audit['pathway_stage_count']}
- 本地硬闸门：{"通过" if audit["hard_gate_pass"] else "未通过"}
"""
        (self.output_dir / "03_reports").mkdir(exist_ok=True)
        (self.output_dir / "03_reports" / "README_交付说明.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="all", help="all or one of: " + ",".join(BATCH_CONFIGS))
    args = parser.parse_args()
    if args.target == "all":
        keys = [key for key, cfg in sorted(BATCH_CONFIGS.items(), key=lambda item: item[1]["order"])]
    else:
        keys = [args.target]
    summaries = []
    for key in keys:
        if key not in BATCH_CONFIGS:
            raise SystemExit(f"unknown target: {key}")
        builder = RemainingCdssBuilder(BATCH_CONFIGS[key])
        audit = builder.build()
        summaries.append(audit)
        print(json.dumps({
            "target": key,
            "batch_id": audit["batch_id"],
            "scope_target": audit["scope_target"],
            "disease_count": audit["disease_count"],
            "new_node_count": audit["new_node_count"],
            "new_relation_count": audit["new_relation_count"],
            "recommendation_statement_count": audit["recommendation_statement_count"],
            "hard_gate_pass": audit["hard_gate_pass"],
            "output_dir": audit["output_dir"],
        }, ensure_ascii=False, indent=2))
        if not audit["hard_gate_pass"]:
            raise SystemExit(2)
    summary_path = COLLECTION / "99_CDSS决策层批量升级_summary_20260709.json"
    summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
