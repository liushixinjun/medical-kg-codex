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

import scripts.build_cad_cdss_recommendation_delta as cad

COLLECTION = ROOT / "心血管内科文献集合"
SOURCE_BATCH = COLLECTION / "BATCH-CARD-CM-20260622-001"
DEFAULT_OUTPUT = COLLECTION / "BATCH-CARD-CM-CDSS-20260709-001_心肌病_CDSS决策层升级"
DEFAULT_BATCH_ID = "BATCH-CARD-CM-CDSS-20260709-001"
SCHEMA_VERSION = cad.SCHEMA_VERSION
SKILL_VERSION = cad.SKILL_VERSION
CREATED_AT = "2026-07-09 00:00:00"


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


def rule(
    key: str,
    name: str,
    statement: str,
    logic: str,
    trigger: str,
    recommend_actions: list[str] | None = None,
    *,
    block_actions: list[str] | None = None,
    evidence_tokens: list[str] | None = None,
    preferred_sources: list[str] | None = None,
    evidence_hint_ids: list[str] | None = None,
    required_facts: list[str] | None = None,
    exclusion_criteria: str = "存在禁忌证、关键患者事实缺失或诊断证据不足时，不自动执行，仅提示补充评估。",
    recommendation_type: str = "recommend",
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "statement": statement,
        "logic": logic,
        "trigger": trigger,
        "recommend_actions": recommend_actions or [],
        "block_actions": block_actions or [],
        "action_names": [],
        "evidence_tokens": evidence_tokens or [],
        "preferred_sources": preferred_sources or [],
        "evidence_hint_ids": evidence_hint_ids or [],
        "required_facts": required_facts
        or ["主诉", "家族史", "生命体征", "心电图", "超声心动图", "心脏磁共振", "心功能", "用药禁忌"],
        "exclusion_criteria": exclusion_criteria,
        "recommendation_type": recommendation_type,
        "evidence_summary": statement,
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


class CmBuilder(cad.Builder):
    def __init__(self, source_batch: Path, output_dir: Path, batch_id: str) -> None:
        super().__init__(source_batch, output_dir, batch_id)
        self.created_at = CREATED_AT

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
        payload = super().common_node_props(code, name, entity_type, disease_code, disease_name, scope_target, **extra)
        payload["schema_version"] = SCHEMA_VERSION
        payload["skill_version"] = SKILL_VERSION
        payload["created_at"] = self.created_at
        return payload

    def build_pathway(self, disease: dict[str, Any], stages: list[dict[str, Any]]) -> None:
        disease_code = disease["code"]
        disease_name = disease["name"]
        scope_target = "心肌病"
        pathway_code = f"PATHWAY-CDSS-CM-{disease['short']}"
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
        for stage_index, item in enumerate(stages, start=1):
            stage_code = f"STAGE-CDSS-CM-{disease['short']}-{stage_index:02d}-{item['key']}"
            self.add_node(
                self.common_node_props(
                    stage_code,
                    f"{disease_name}{item['name']}",
                    "PathwayStage",
                    disease_code,
                    disease_name,
                    scope_target,
                    pathway_code=pathway_code,
                    stage_order=stage_index,
                    stage_key=item["key"],
                    stage_goal=item["goal"],
                    trigger_condition=item["trigger"],
                    exit_condition=item["exit"],
                    required_patient_facts=item.get("required_facts", []),
                )
            )
            self.add_rel(pathway_code, "has_pathway_stage", stage_code, "pathway")
            if previous_stage_code:
                self.add_rel(previous_stage_code, "next_pathway_stage", stage_code, "pathway")
            previous_stage_code = stage_code
            for rule_index, item_rule in enumerate(item["rules"], start=1):
                self.build_rule_and_recommendation(disease, pathway_code, stage_code, stage_index, rule_index, item_rule)

    def build_rule_and_recommendation(
        self,
        disease: dict[str, Any],
        pathway_code: str,
        stage_code: str,
        stage_index: int,
        rule_index: int,
        item: dict[str, Any],
    ) -> None:
        disease_code = disease["code"]
        disease_name = disease["name"]
        scope_target = "心肌病"
        rule_code = f"RULE-CDSS-CM-{disease['short']}-{stage_index:02d}-{rule_index:02d}-{item['key']}"
        rec_code = f"REC-CDSS-CM-{disease['short']}-{stage_index:02d}-{rule_index:02d}-{item['key']}"
        evidence_list = self.select_evidence(
            disease_code,
            item.get("evidence_tokens", []) + item.get("action_names", []),
            item.get("preferred_sources", []),
            evidence_hint_ids=item.get("evidence_hint_ids") or [],
            limit=3,
        )
        primary = evidence_list[0]
        rec_class, evidence_level = cad.parse_recommendation_grade(
            str(primary.get("evidence_text") or ""),
            str(primary.get("source_type") or primary.get("source_name") or ""),
        )
        evidence_ids = [str(row["code"]) for row in evidence_list]
        action_codes = list(dict.fromkeys(item.get("recommend_actions", [])))
        block_codes = list(dict.fromkeys(item.get("block_actions", [])))
        action_names = list(dict.fromkeys(self.existing_name(code) for code in action_codes))
        block_names = list(dict.fromkeys(self.existing_name(code) for code in block_codes))
        statement = item["statement"]
        structured_summary = item.get("evidence_summary") or statement
        self.add_node(
            self.common_node_props(
                rule_code,
                item["name"],
                "ClinicalRule",
                disease_code,
                disease_name,
                scope_target,
                pathway_code=pathway_code,
                stage_code=stage_code,
                rule_logic=item["logic"],
                trigger_condition=item["trigger"],
                applicable_population=item.get("applicable_population", f"{disease_name}相关患者"),
                exclusion_criteria=item.get("exclusion_criteria", "存在禁忌证或证据不足时不自动执行，仅提示补充评估。"),
                required_patient_facts=item.get("required_facts", []),
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
                recommendation_type=item.get("recommendation_type", "recommend"),
                statement_text=statement,
                display_title=statement,
                applicable_population=item.get("applicable_population", f"{disease_name}相关患者"),
                exclusion_criteria=item.get("exclusion_criteria", "存在禁忌证或证据不足时不自动执行，仅提示补充评估。"),
                required_patient_facts=item.get("required_facts", []),
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
                guideline_names=list(dict.fromkeys(str(row.get("source_name") or "") for row in evidence_list)),
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
                "触发条件": item["trigger"],
                "判断逻辑": item["logic"],
                "推荐动作": "；".join(action_names),
                "阻断动作": "；".join(block_names),
                "推荐等级": rec_class,
                "证据等级": evidence_level,
                "主证据": str(primary.get("code")),
                "指南/来源": str(primary.get("source_name") or ""),
                "页码": primary.get("source_page"),
                "结构化推荐摘要": structured_summary,
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
                "阻断动作codes": ";".join(block_codes),
                "证据ID": ";".join(evidence_ids),
                "前端用法": "先按疾病加载ClinicalPathway，再按PathwayStage顺序匹配ClinicalRule，命中后展示RecommendationStatement。",
            }
        )

    def write_outputs(self, audit: dict[str, Any]) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "batch_id": self.batch_id,
            "top_specialty": "心血管内科",
            "disease_category": "心肌病",
            "scope": "心肌病全病种CDSS决策层升级",
            "source_batch": str(self.source_batch),
            "schema_version": SCHEMA_VERSION,
            "skill_version": SKILL_VERSION,
            "created_at": self.created_at,
            "note": "只新增CDSS决策层节点/关系，不覆盖旧心肌病事实层。",
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
        summary_md = f"""# 心肌病 CDSS 决策层升级交付说明

批次：{self.batch_id}

## 本批次做了什么

- 复用旧心肌病事实层节点和证据节点。
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
        (self.output_dir / "03_reports").mkdir(exist_ok=True)
        (self.output_dir / "03_reports" / "README_交付说明.md").write_text(summary_md, encoding="utf-8")


def cm_definitions() -> list[dict[str, Any]]:
    p_cm = ["中国心肌病综合管理指南2025", "ESC指南：心肌病的管理2023", "心肌病  ESC  2023", "心肌病诊断与治疗建议"]
    p_hcm = ["中国 成人肥厚型心肌病诊断与治疗指南2023", "HCM AHA 2024", "HCM  ESC 2023", "肥厚型心肌病激发"]
    p_dcm = ["中国 扩张型心肌病诊断和治疗指南2018", "DCM  AHA  2016", "DCM ESC 2016"]
    p_acm = ["ESC指南：心肌病的管理2023", "中国心肌病综合管理指南2025", "心肌病MOGE(S)"]
    p_fabry = ["成人法布雷病心肌病诊断与治疗中国专家共识", "中国心肌病综合管理指南2025"]
    p_icm = ["缺血性心肌病血运重建专家共识", "经皮冠状动脉介入治疗指南", "中国心肌病综合管理指南2025"]

    common_diag_actions = ["EXAM-ECG", "EXAM-TTE", "EXAM-CMR", "LAB-CARDIAC-BIOMARKERS"]
    family_actions = ["EXAM-GENETIC", "EXAM-HOLTER", "EXAM-CMR"]
    return [
        {
            "short": "HCM",
            "code": "DIS-CARD-CM-HCM",
            "name": "肥厚型心肌病",
            "stages": [
                stage("DIAG", "诊断确认阶段", "确认室壁厚度、排除负荷性肥厚并进行鉴别诊断。", "疑似HCM、室壁增厚、家族史或猝死风险", "完成HCM诊断/排除", [
                    rule("DIAG", "HCM诊断确认规则", "疑似肥厚型心肌病应结合超声心动图、心脏磁共振、最大室壁厚度和家族史确认诊断。", "室壁增厚、家族史、心电图异常或影像提示HCM。", "疑似HCM", ["DXC-CARD-4335F6498D1C", "EXAM-TTE", "EXAM-CMR", "IND-MAX-WALL-THICKNESS", "EXAM-GENETIC"], evidence_tokens=["肥厚型心肌病", "HCM", "室壁厚度", "诊断", "基因"], preferred_sources=p_hcm),
                ]),
                stage("RISK", "风险分层阶段", "评估猝死风险、心律失常和LVOTO。", "HCM诊断成立或高度疑似", "形成猝死风险和LVOTO评估结果", [
                    rule("SCD-RISK", "HCM猝死风险分层规则", "HCM确诊后应评估猝死风险并判断ICD适应证。", "HCM确诊后存在晕厥、家族猝死史、NSVT、室壁显著增厚或LGE等风险因素。", "HCM已确诊", ["RISK-CARD-C72CDDDDE658", "EXAM-HOLTER", "IND-LGE", "PROC-ICD"], evidence_tokens=["HCM", "猝死", "ICD", "风险分层", "Holter"], preferred_sources=p_hcm),
                ]),
                stage("TREAT", "治疗决策阶段", "根据梗阻、症状和风险选择药物、间隔减容或ICD。", "HCM已确诊并完成风险评估", "形成治疗推荐", [
                    rule("MED", "HCM症状控制药物规则", "有症状HCM患者应优先评估β受体阻滞剂或非二氢吡啶类钙通道阻滞剂。", "劳力性呼吸困难、胸痛、心悸或LVOTO相关症状。", "有症状HCM", ["PLAN-CARD-C73CCA666CCA", "MED-BETA-BLOCKER", "MED-NDHP-CCB"], evidence_tokens=["肥厚型心肌病", "β受体阻滞剂", "非二氢吡啶", "症状"], preferred_sources=p_hcm),
                    rule("SRT", "HCM间隔减容治疗规则", "药物治疗后仍有重度症状且存在显著LVOTO时，可评估室间隔切除术或酒精室间隔消融术。", "优化药物治疗后仍NYHA Ⅲ-Ⅳ级或症状明显且LVOTO显著。", "梗阻型HCM症状未控制", ["PROC-SEPTAL-MYECTOMY", "PROC-ASA"], evidence_tokens=["HCM", "室间隔切除", "酒精室间隔消融", "LVOTO"], preferred_sources=p_hcm),
                ]),
                stage("FOLLOW", "随访管理阶段", "定期复评症状、心律失常、影像和家系风险。", "HCM稳定期或出院后", "形成随访计划", [
                    rule("FOLLOW", "HCM随访复评规则", "HCM应定期复评症状、心电/动态心电图、影像学和家系风险。", "HCM稳定期、治疗调整后或家系筛查。", "HCM随访", ["FU-CARD-B30DF4D6DE67", "EXAM-ECG", "EXAM-HOLTER", "EXAM-TTE", "EXAM-CMR"], evidence_tokens=["HCM", "随访", "家族", "心电图", "超声"], preferred_sources=p_hcm),
                ]),
            ],
        },
        {
            "short": "DCM",
            "code": "DIS-CARD-CM-DCM",
            "name": "扩张型心肌病",
            "stages": [
                stage("DIAG", "诊断确认阶段", "确认左室扩大和收缩功能下降，排除缺血、瓣膜等继发原因。", "心衰、心腔扩大或LVEF下降", "完成DCM诊断/排除", [
                    rule("DIAG", "DCM诊断确认规则", "疑似扩张型心肌病应结合超声心动图、心脏磁共振、LVEF和病因排查确认诊断。", "左室扩大、LVEF下降或心衰表现。", "疑似DCM", ["DXC-CARD-16CFF57650C6", "EXAM-TTE", "EXAM-CMR", "IND-LVEF", "EXAM-CAG"], evidence_tokens=["扩张型心肌病", "DCM", "LVEF", "诊断", "排除冠心病"], preferred_sources=p_dcm + p_cm),
                ]),
                stage("TREAT", "治疗决策阶段", "按心衰规范药物、器械和移植评估。", "DCM诊断成立并有心衰或LVEF下降", "形成治疗推荐", [
                    rule("GDMT", "DCM心衰规范药物规则", "DCM合并心衰或LVEF下降时，应评估ACEI/ARB、β受体阻滞剂、利尿剂和醛固酮受体拮抗剂。", "DCM合并心衰症状、容量负荷或LVEF下降。", "DCM伴心衰", ["PLAN-CARD-EF123C1AB63F", "MED-CARD-E40082221530", "MED-CARD-TEXT-B905AF3E59", "MED-BETA-BLOCKER", "MED-DIURETIC", "MED-CARD-TEXT-4E1713BBBA"], evidence_tokens=["扩张型心肌病", "心力衰竭", "ACEI", "β受体阻滞剂", "利尿剂"], preferred_sources=p_dcm),
                    rule("DEVICE", "DCM器械治疗评估规则", "DCM经规范治疗后仍有低LVEF或高危心律失常时，应评估ICD或心脏再同步治疗。", "DCM规范治疗后仍LVEF下降、宽QRS、室性心律失常或猝死风险。", "DCM器械评估", ["PROC-ICD", "PROC-CARD-TEXT-D2C1F9E289", "EXAM-ECG", "EXAM-HOLTER"], evidence_tokens=["扩张型心肌病", "ICD", "CRT", "心脏再同步", "猝死"], preferred_sources=p_dcm),
                ]),
                stage("FOLLOW", "随访管理阶段", "复评心功能、心律失常、家系和终末期治疗。", "DCM稳定期或出院后", "形成随访和升级治疗计划", [
                    rule("FOLLOW", "DCM随访复评规则", "DCM应定期复评心功能、心律失常、遗传风险和是否需要高级心衰治疗。", "DCM稳定期、治疗调整后或心衰反复。", "DCM随访", ["FU-CARD-9B799CB8CABF", "EXAM-TTE", "EXAM-HOLTER", "EXAM-GENETIC", "PROC-HEART-TRANSPLANT"], evidence_tokens=["扩张型心肌病", "随访", "心脏移植", "基因"], preferred_sources=p_dcm + p_cm),
                ]),
            ],
        },
        {
            "short": "RCM",
            "code": "DIS-CARD-CM-RCM",
            "name": "限制型心肌病",
            "stages": [
                stage("DIAG", "诊断确认阶段", "确认限制性充盈和病因，重点排查浸润、炎症和心内膜疾病。", "舒张性心衰、心房增大或限制性充盈", "完成RCM诊断/排除", [
                    rule("DIAG", "RCM诊断确认规则", "疑似限制型心肌病应结合超声、心脏磁共振和必要时心内膜心肌活检明确病因。", "限制性充盈、双房增大或不明原因心衰。", "疑似RCM", ["DXC-CARD-F68ECA7670AB", "EXAM-TTE", "EXAM-CMR", "EXAM-EMB"], evidence_tokens=["限制型心肌病", "RCM", "心内膜心肌活检", "限制性充盈"], preferred_sources=p_cm),
                ]),
                stage("TREAT", "治疗与随访阶段", "以病因治疗、容量管理和高级心衰评估为主。", "RCM诊断成立", "形成治疗与随访计划", [
                    rule("TREAT", "RCM治疗管理规则", "RCM治疗应围绕病因治疗、容量控制、心律失常管理和必要时高级心衰治疗评估。", "RCM合并心衰、容量负荷或心律失常。", "RCM治疗", ["PLAN-CARD-8419002B35F1", "MED-DIURETIC", "FU-CARD-1231E09FC493", "PROC-HEART-TRANSPLANT"], evidence_tokens=["限制型心肌病", "治疗", "利尿剂", "心脏移植"], preferred_sources=p_cm),
                ]),
            ],
        },
        {
            "short": "ACM",
            "code": "DIS-CARD-CM-ACM",
            "name": "致心律失常性心肌病",
            "stages": [
                stage("DIAG", "诊断与分型阶段", "确认ACM谱系、心室受累范围和遗传背景。", "室性心律失常、晕厥、家族史或CMR异常", "完成ACM诊断/分型", [
                    rule("DIAG", "ACM诊断和谱系分型规则", "疑似致心律失常性心肌病应结合心电图、动态心电图、CMR和基因检测进行谱系分型。", "室性心律失常、晕厥、家族史或右/左室受累。", "疑似ACM", ["DXC-CARD-E0CC534A2482", "EXAM-ECG", "EXAM-HOLTER", "EXAM-CMR", "EXAM-GENETIC"], evidence_tokens=["致心律失常性心肌病", "ACM", "CMR", "基因", "诊断"], preferred_sources=p_acm),
                ]),
                stage("RISK", "猝死风险与运动限制阶段", "评估室性心律失常和猝死风险。", "ACM已确诊或高度疑似", "形成猝死风险和运动建议", [
                    rule("RISK", "ACM猝死风险规则", "ACM应进行猝死风险分层，必要时评估ICD，并避免高强度竞技运动。", "ACM确诊伴室性心律失常、晕厥、家族猝死或心室功能下降。", "ACM风险分层", ["RISK-CARD-341E5DDF79BA", "PROC-ICD", "EXAM-HOLTER"], evidence_tokens=["ACM", "猝死", "ICD", "运动", "风险分层"], preferred_sources=p_acm),
                ]),
                stage("TREAT", "治疗与随访阶段", "处理心律失常、心衰和长期复评。", "ACM已确诊", "形成治疗与随访计划", [
                    rule("TREAT", "ACM治疗与随访规则", "ACM治疗应结合心律失常控制、ICD适应证、心衰治疗和定期随访复评。", "ACM合并心律失常或心室功能异常。", "ACM治疗", ["PLAN-CARD-8BABC3547777", "MED-AMIODARONE", "PROC-ICD", "FU-CARD-CM-ACM-ROUTINE-FOLLOW-UP"], evidence_tokens=["ACM", "治疗", "心律失常", "随访"], preferred_sources=p_acm),
                ]),
            ],
        },
        {
            "short": "ARVC",
            "code": "DIS-CARD-CM-ARVC",
            "name": "致心律失常性右心室心肌病",
            "stages": [
                stage("DIAG", "诊断确认阶段", "确认右室受累、室性心律失常和家族/遗传证据。", "右室异常、室速、晕厥或家族史", "完成ARVC诊断", [
                    rule("DIAG", "ARVC诊断确认规则", "疑似ARVC应结合心电图、动态心电图、CMR、基因检测和诊断标准确认诊断。", "右室异常、室性心律失常、晕厥或家族史。", "疑似ARVC", ["DXC-CARD-C8CFD05F6624", "EXAM-ECG", "EXAM-HOLTER", "EXAM-CMR", "EXAM-GENETIC"], evidence_tokens=["ARVC", "右心室", "诊断", "CMR", "基因"], preferred_sources=p_acm),
                ]),
                stage("RISK", "风险与治疗阶段", "评估猝死风险、ICD和抗心律失常治疗。", "ARVC诊断成立", "形成治疗与随访计划", [
                    rule("TREAT", "ARVC风险和治疗规则", "ARVC应进行猝死风险分层，必要时评估ICD、抗心律失常药物和长期随访。", "ARVC合并室性心律失常、晕厥、右室功能下降或家族猝死史。", "ARVC治疗", ["RISK-CARD-B8562DBAE6B8", "PLAN-CARD-A998492DDF0E", "MED-AMIODARONE", "PROC-ICD", "FU-CARD-ABD01AB929A0"], evidence_tokens=["ARVC", "猝死", "ICD", "胺碘酮", "随访"], preferred_sources=p_acm),
                ]),
            ],
        },
        {
            "short": "ALVC",
            "code": "DIS-CARD-CM-ALVC",
            "name": "致心律失常性左心室心肌病",
            "stages": [
                stage("DIAG", "诊断确认阶段", "确认左室受累、非缺血性瘢痕和遗传背景。", "室性心律失常、LGE或左室功能异常", "完成ALVC诊断", [
                    rule("DIAG", "ALVC诊断确认规则", "疑似ALVC应结合CMR-LGE、心电/动态心电图和基因检测评估左室受累。", "左室非缺血性LGE、室性心律失常或家族史。", "疑似ALVC", ["DXC-CARD-CM-ALVC-PADUA-LV", "EXAM-CMR", "IND-LGE", "EXAM-HOLTER", "EXAM-GENETIC"], evidence_tokens=["ALVC", "左心室", "LGE", "Padua", "诊断"], preferred_sources=p_acm),
                ]),
                stage("TREAT", "风险治疗阶段", "评估猝死风险、ICD和心衰治疗。", "ALVC诊断成立", "形成治疗与随访计划", [
                    rule("TREAT", "ALVC风险和治疗规则", "ALVC应进行猝死风险复评，必要时评估ICD、抗心律失常治疗和心衰治疗。", "ALVC合并LVEF下降、NSVT、晕厥或LGE范围较大。", "ALVC治疗", ["RISK-CARD-D82F521AFD8B", "PLAN-CARD-501677A0810C", "PROC-ICD", "MED-AMIODARONE", "FU-CARD-54FDCA736767"], evidence_tokens=["ALVC", "猝死", "ICD", "治疗", "随访"], preferred_sources=p_acm),
                ]),
            ],
        },
        {
            "short": "ABVC",
            "code": "DIS-CARD-CM-ABVC",
            "name": "致心律失常性双心室心肌病",
            "stages": [
                stage("DIAG", "诊断确认阶段", "确认左右心室双心室受累。", "左右室异常、LGE或室性心律失常", "完成ABVC诊断", [
                    rule("DIAG", "ABVC诊断确认规则", "疑似ABVC应结合CMR、心电/动态心电图、双心室受累证据和基因检测确认诊断。", "左右室受累、室性心律失常或家族史。", "疑似ABVC", ["DXC-CARD-CM-ABVC-PADUA-BIVENTRICULAR", "EXAM-CMR", "EXAM-HOLTER", "EXAM-GENETIC"], evidence_tokens=["ABVC", "双心室", "Padua", "诊断", "CMR"], preferred_sources=p_acm),
                ]),
                stage("TREAT", "风险治疗阶段", "按ACM谱系进行猝死风险、ICD和随访管理。", "ABVC诊断成立", "形成治疗与随访计划", [
                    rule("TREAT", "ABVC风险和治疗规则", "ABVC应按致心律失常性心肌病谱系进行猝死风险分层、ICD评估和长期随访。", "ABVC伴室性心律失常、晕厥、心室功能异常或家族猝死史。", "ABVC治疗", ["RISK-CARD-73C4D46DAD92", "PLAN-CARD-75D805FA2D42", "PROC-ICD", "FU-CARD-CM-ACM-ROUTINE-FOLLOW-UP"], evidence_tokens=["ABVC", "双心室", "猝死", "ICD", "随访"], preferred_sources=p_acm),
                ]),
            ],
        },
        {
            "short": "AMYLOID",
            "code": "DIS-CARD-CM-AMYLOID",
            "name": "淀粉样变心肌病",
            "stages": [
                stage("DIAG", "诊断确认阶段", "识别淀粉样变心肌受累和分型。", "室壁增厚、心衰、低电压或限制性表现", "完成淀粉样变诊断/分型", [
                    rule("DIAG", "淀粉样变心肌病诊断规则", "疑似淀粉样变心肌病应结合超声、CMR、心脏生物标志物和必要时心肌活检进行诊断和分型。", "室壁增厚、心衰、低电压、LGE或限制性充盈表现。", "疑似淀粉样变心肌病", ["DXC-CARD-C5CD88A6E22B", "EXAM-TTE", "EXAM-CMR", "EXAM-EMB", "LAB-CARDIAC-BIOMARKERS"], evidence_tokens=["淀粉样变心肌病", "amyloid", "CMR", "心肌活检", "诊断"], preferred_sources=p_cm),
                ]),
                stage("TREAT", "治疗与随访阶段", "按分型进行病因治疗、心衰管理和随访。", "淀粉样变心肌病诊断成立", "形成治疗和随访计划", [
                    rule("TREAT", "淀粉样变心肌病治疗管理规则", "淀粉样变心肌病应按分型进行病因治疗评估，并进行心衰管理和长期随访。", "淀粉样变心肌病确诊或高度疑似。", "淀粉样变治疗", ["PLAN-CARD-BE44DFBB5552", "MED-DIURETIC", "FU-CARD-94C8AE220B62"], evidence_tokens=["淀粉样变心肌病", "治疗", "随访", "心衰"], preferred_sources=p_cm),
                ]),
            ],
        },
        {
            "short": "FABRY",
            "code": "DIS-CARD-CM-FABRY",
            "name": "法布雷病心肌病",
            "stages": [
                stage("DIAG", "诊断确认阶段", "通过酶活性、基因和心脏受累证据确认诊断。", "左室肥厚、肾/神经/皮肤表现或家族史", "完成法布雷病心肌病诊断", [
                    rule("DIAG", "法布雷病心肌病诊断规则", "疑似法布雷病心肌病应结合α-半乳糖苷酶A活性、基因检测、CMR和必要时心肌活检确认诊断。", "左室肥厚伴多系统表现、家族史或男性早发病例。", "疑似法布雷病心肌病", ["DXC-CARD-CM-FABRY-ENZYME-GENE-EMB", "EXAM-GENETIC", "EXAM-CMR", "EXAM-EMB"], evidence_tokens=["法布雷", "Fabry", "酶活性", "基因", "心肌活检"], preferred_sources=p_fabry),
                ]),
                stage("TREAT", "治疗与随访阶段", "评估酶替代治疗和长期心脏随访。", "法布雷病心肌病诊断成立", "形成治疗和随访计划", [
                    rule("TREAT", "法布雷病心肌病治疗规则", "法布雷病心肌病应评估酶替代治疗，并长期监测心脏结构、心律和功能。", "法布雷病心肌病确诊或高度疑似。", "法布雷病心肌病治疗", ["PLAN-CARD-D8661B4FB4B1", "MED-CARD-4FB23383386F", "MED-CARD-B89F68FD48F2", "FU-CARD-CM-FABRY-REGULAR-CARDIAC-FOLLOW-UP"], evidence_tokens=["法布雷", "酶替代", "阿加糖酶", "随访"], preferred_sources=p_fabry),
                ]),
            ],
        },
        {
            "short": "ATRIAL",
            "code": "DIS-CARD-CM-ATRIAL",
            "name": "心房心肌病",
            "stages": [
                stage("DIAG", "诊断分型阶段", "识别心房结构、电生理和组织学异常。", "房性心律失常、房颤、左房扩大或卒中风险", "完成心房心肌病评估", [
                    rule("DIAG", "心房心肌病诊断分型规则", "心房心肌病应结合房性心律失常、心房结构/功能异常和EHRA组织学分型框架进行评估。", "房颤、房扑、左房扩大、卒中风险或心房结构异常。", "疑似心房心肌病", ["DXC-CARD-CM-ATRIAL-EHRA-CLASS", "EXAM-ECG", "EXAM-HOLTER", "EXAM-TTE"], evidence_tokens=["心房心肌病", "atrial cardiomyopathy", "EHRA", "房颤", "分型"], preferred_sources=p_cm),
                ]),
                stage("TREAT", "卒中与心律管理阶段", "评估抗凝、心室率控制和房性心律失常随访。", "心房心肌病伴房颤/房扑或卒中风险", "形成抗凝和随访计划", [
                    rule("TREAT", "心房心肌病抗凝和心律管理规则", "心房心肌病合并房性心律失常时，应评估抗凝、心室率控制和长期随访。", "合并房颤/房扑、CHA2DS2-VASc风险或左房结构异常。", "心房心肌病治疗", ["PLAN-CARD-CM-ATRIAL-AF-STROKE-RISK-MANAGEMENT", "PLAN-CARD-A1C4E6332D38", "PLAN-CARD-TEXT-655F4B37BC", "FU-CARD-4F0F5C00E92E"], evidence_tokens=["心房心肌病", "抗凝", "卒中", "房颤", "随访"], preferred_sources=p_cm),
                ]),
            ],
        },
        {
            "short": "NDLVCM",
            "code": "DIS-CARD-CM-NDLVCM",
            "name": "非扩张型左心室心肌病",
            "stages": [
                stage("DIAG", "诊断确认阶段", "识别非扩张左室心肌病表型、LGE和遗传背景。", "非缺血性LGE、室性心律失常或左室功能异常", "完成NDLVCM诊断", [
                    rule("DIAG", "NDLVCM诊断规则", "疑似非扩张型左心室心肌病应结合CMR-LGE、左室功能、心电/动态心电图和基因检测进行诊断。", "左室不扩张但存在非缺血性瘢痕、室性心律失常或LVEF下降。", "疑似NDLVCM", ["DXC-CARD-CM-NDLVCM-CMR-LGE", "EXAM-CMR", "IND-LGE", "EXAM-HOLTER", "EXAM-GENETIC"], evidence_tokens=["NDLVCM", "非扩张型左心室心肌病", "LGE", "CMR", "诊断"], preferred_sources=p_acm),
                ]),
                stage("RISK", "风险治疗阶段", "评估猝死风险、ICD和随访。", "NDLVCM诊断成立", "形成风险和随访计划", [
                    rule("RISK", "NDLVCM风险和随访规则", "NDLVCM应长期复评表型、LGE、心律失常和猝死风险，必要时评估ICD。", "存在LGE、室性心律失常、LVEF下降或家族猝死史。", "NDLVCM风险评估", ["PLAN-CARD-0E0B6D3DD944", "PROC-ICD", "FU-CARD-CM-NDLVCM-LIFELONG-SCD-RISK"], evidence_tokens=["NDLVCM", "猝死", "ICD", "随访", "LGE"], preferred_sources=p_acm),
                ]),
            ],
        },
        {
            "short": "ICM",
            "code": "DIS-CARD-CAD-ICM",
            "name": "缺血性心肌病",
            "stages": [
                stage("DIAG", "诊断确认阶段", "确认缺血性病因、心肌瘢痕、心功能和血运重建可行性。", "既往心梗、冠心病、LVEF下降或心衰", "完成ICM诊断和血运重建评估", [
                    rule("DIAG", "ICM诊断确认规则", "疑似缺血性心肌病应结合冠状动脉造影、超声心动图、CMR和LVEF评估确认缺血性病因。", "冠心病/心梗病史、心衰、LVEF下降或心肌瘢痕。", "疑似ICM", ["DXC-CARD-097806EACD3F", "EXAM-CAG", "EXAM-TTE", "EXAM-CMR", "IND-LVEF"], evidence_tokens=["缺血性心肌病", "冠状动脉造影", "LVEF", "血运重建"], preferred_sources=p_icm, evidence_hint_ids=["EVD-C8250F84A40E395A69D0-ICM"]),
                ]),
                stage("TREAT", "治疗决策阶段", "按心衰规范治疗并评估血运重建。", "ICM诊断成立", "形成治疗和随访计划", [
                    rule("REVASC", "ICM血运重建评估规则", "缺血性心肌病应在规范药物治疗基础上评估冠状动脉造影、PCI或其他血运重建策略。", "ICM合并可干预冠脉病变、缺血证据或心功能下降。", "ICM血运重建", ["PLAN-CARD-260280003FF2", "EXAM-CAG", "PROC-CARD-E9ADC25A25E3", "FU-CARD-AF9070949AB7"], evidence_tokens=["缺血性心肌病", "血运重建", "PCI", "冠状动脉造影"], preferred_sources=p_icm, evidence_hint_ids=["EVD-3AA4B71F665A96D0B0D7-ICM"]),
                ]),
            ],
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-batch", type=Path, default=SOURCE_BATCH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-id", default=DEFAULT_BATCH_ID)
    args = parser.parse_args()

    builder = CmBuilder(args.source_batch, args.output_dir, args.batch_id)
    for disease in cm_definitions():
        if disease["code"] not in builder.node_by_code:
            raise RuntimeError(f"missing disease node in source batch: {disease['code']} {disease['name']}")
        builder.build_pathway(disease, disease["stages"])
    audit = builder.audit()
    builder.write_outputs(audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    if not audit["hard_gate_pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
