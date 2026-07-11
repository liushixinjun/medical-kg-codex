from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "心血管内科文献集合" / "09_服务器硬闸门复核_20260707_dynamic_backfill"
OUTPUT_DIR = ROOT / "心血管内科文献集合" / "10_历史静态路径与诊断标准迁移_static_cdss_migration" / "STATIC_MIGRATION_20260707"
SCHEMA_VERSION = "V1.9"
CREATED_AT = "2026-07-07 15:18:58"
BATCH_ID = "BATCH-CARD-STATIC-CDSS-MIGRATION-20260707"
SCOPE_TARGET = "冠心病、心肌病、室性心律失常、心脏性猝死及历史静态路径迁移"


MANUAL_PATHWAY_DISEASE_MAP = {
    "PATH-CARD-CM-ATRIAL-AF-STROKE-RISK": "DIS-CARD-CM-ATRIAL",
    "PATHWAY-CARD-0CF7B718B269": "DIS-CARD-CAD-STEMI",
    "PATHWAY-CARD-17A2C6DE85BB": "DIS-CARD-CM-ALVC",
    "PATHWAY-CARD-1B6450E2CB29": "DIS-CARD-CM-HCM",
    "PATHWAY-CARD-2D83296059F7": "DIS-CARD-CM-AMYLOID",
    "PATHWAY-CARD-39CFBD93D21C": "DIS-CARD-CM-FABRY",
    "PATHWAY-CARD-47D3A2CC113F": "DIS-CARD-CAD-ICM",
    "PATHWAY-CARD-5E4A6A51FCFA": "DIS-CARD-CM-ARVC",
    "PATHWAY-CARD-75AAE6892822": "DIS-CARD-CM-DCM",
    "PATHWAY-CARD-9F837323F5A4": "DIS-CARD-CM-ACM",
    "PATHWAY-CARD-A89AD457E954": "DIS-CARD-CAD-CCS",
    "PATHWAY-CARD-BA4901A548C2": "DIS-CARD-CAD-STABLE-ANGINA",
    "PATHWAY-CARD-CDD85E19C142": "DIS-CARD-CAD-OLD-MI",
    "PATHWAY-CARD-CE20E681F8F0": "DIS-CARD-CAD-SILENT-ISCHEMIA",
    "PATHWAY-CARD-CEAE0C4E99B9": "DIS-CARD-CAD-AMI",
    "PATHWAY-CARD-DEBB2FEB08F8": "DIS-CARD-CAD-UA",
    "PATHWAY-CARD-DF6F434C5C44": "DIS-CARD-CM-ABVC",
    "PATHWAY-CARD-E6FFD251EB59": "DIS-CARD-CM-NDLVCM",
    "PATHWAY-CARD-E7DCA9EB52BB": "DIS-CARD-CAD-NSTEMI",
    "PATHWAY-CARD-F2B4D728E4C5": "DIS-CARD-CM-RCM",
    "PATHWAY-CARD-FBB8A78A91AB": "DIS-CARD-CAD-ACS",
}


def digest(text: str, length: int = 16) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest().upper()[:length]


def rel_id(source: str, rel_type: str, target: str) -> str:
    return "REL-" + digest(f"{source}|{rel_type}|{target}", 20)


def safe_fragment(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", text.upper()).strip("-")[:48] or digest(text, 12)


def common(*, clinical_review_status: str = "pending_clinical_use_effect_review", release: str = "test_recommendation") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved_for_sample",
        "batch_id": BATCH_ID,
        "scope_type": "multi_disease_static_migration",
        "scope_target": SCOPE_TARGET,
        "merge_status": "delta_migration",
        "conflict_status": "none",
        "clinical_review_status": clinical_review_status,
        "formal_cdss_ready": False,
        "ai_evidence_review_status": "ai_prechecked_limited",
        "cdss_release_level": release,
        "created_at": CREATED_AT,
    }


def add_node(nodes: dict[str, dict[str, Any]], code: str, name: str, entity_type: str, category: str, disease_code: str, **extra: Any) -> None:
    item = {
        "id": "KG_" + code.replace("-", "_"),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": category,
        **common(),
        "aliases": extra.pop("aliases", []),
        "disease_code": disease_code,
        **extra,
    }
    if code in nodes and nodes[code] != item:
        raise ValueError(f"Duplicate node with different payload: {code}")
    nodes[code] = item


def add_rel(
    rels: dict[tuple[str, str, str], dict[str, Any]],
    source: str,
    rel_type: str,
    target: str,
    category: str,
    evidence_ids: list[str] | None = None,
    polarity: str = "positive",
    clinical_review_status: str = "pending_clinical_use_effect_review",
    release: str = "test_recommendation",
) -> None:
    ev = list(dict.fromkeys([x for x in (evidence_ids or []) if x]))
    item = {
        "id": rel_id(source, rel_type, target),
        "source_code": source,
        "relationType": rel_type,
        "target_code": target,
        "relationCategory": category,
        **common(clinical_review_status=clinical_review_status, release=release),
        "polarity": polarity,
        "confidence": 0.86,
        "evidence_ids": ev,
        "evidence_count": len(ev),
    }
    key = (source, rel_type, target)
    if key in rels and rels[key] != item:
        raise ValueError(f"Duplicate relation with different payload: {key}")
    rels[key] = item


def add_support(rels: dict[tuple[str, str, str], dict[str, Any]], source: str, evidence_ids: list[str]) -> None:
    for ev in dict.fromkeys(evidence_ids):
        add_rel(
            rels,
            source,
            "supported_by_evidence",
            ev,
            "evidence",
            [ev],
            clinical_review_status="not_applicable",
            release="knowledge_display",
        )


def load_json(name: str) -> Any:
    return json.loads((INPUT_DIR / name).read_text(encoding="utf-8"))


def disease_group(code: str) -> str:
    if code.startswith("DIS-CARD-CAD"):
        return "CAD"
    if code.startswith("DIS-CARD-CM"):
        return "CM"
    if code.startswith("DIS-CARD-ARR") or code.startswith("DIS-CARD-SCD"):
        return "VA_SCD"
    if code.startswith("DIS-CARD-HF"):
        return "HF"
    return "CARD"


def diagnostic_component_templates(group: str, disease_name: str) -> list[tuple[str, str]]:
    if group == "CAD":
        return [
            ("临床症状与缺血表现组成规则", f"{disease_name}诊断需结合胸痛或缺血等效症状、发作特征和危险因素。"),
            ("心电图/心肌损伤/缺血证据组成规则", f"{disease_name}诊断需结合心电图动态变化、心肌损伤标志物或客观缺血证据。"),
            ("解剖或影像学证据组成规则", f"{disease_name}诊断需结合冠脉解剖、影像学或功能学检查结果，并排除相似疾病。"),
        ]
    if group == "CM":
        return [
            ("心脏结构和功能异常组成规则", f"{disease_name}诊断需结合超声心动图、CMR或其他影像提示的心肌结构/功能异常。"),
            ("病因、家族史或遗传线索组成规则", f"{disease_name}诊断需结合家族史、遗传学、系统性疾病或特异病因线索。"),
            ("排除负荷或缺血性继发改变组成规则", f"{disease_name}诊断需排除高血压、瓣膜病、冠心病或其他可解释心肌改变的原因。"),
        ]
    if group == "VA_SCD":
        return [
            ("心电或节律记录组成规则", f"{disease_name}诊断需有心电图、动态心电图、监护或除颤记录等节律证据。"),
            ("临床事件和血流动力学组成规则", f"{disease_name}诊断需结合晕厥、心脏骤停、血流动力学不稳定或猝死相关临床事件。"),
            ("诱因和基础心脏病评估组成规则", f"{disease_name}诊断需评估电解质、药物、遗传性心律失常和结构性心脏病等诱因。"),
        ]
    if group == "HF":
        return [
            ("症状体征组成规则", f"{disease_name}诊断需结合呼吸困难、乏力、水肿或淤血体征。"),
            ("利钠肽和影像证据组成规则", f"{disease_name}诊断需结合利钠肽、超声心动图和LVEF等结构功能证据。"),
            ("急慢性与容量状态组成规则", f"{disease_name}诊断需结合急慢性病程、容量状态和诱因评估。"),
        ]
    return [
        ("临床表现组成规则", f"{disease_name}诊断需结合临床表现和病程。"),
        ("关键检查组成规则", f"{disease_name}诊断需结合关键检查、检验或影像证据。"),
        ("排除条件组成规则", f"{disease_name}诊断需排除相似疾病或继发原因。"),
    ]


def evidence_map(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {row["dx_code"]: row.get("resolved_evidence_codes") or row.get("evidence_codes") or [] for row in rows}


def pathway_disease(pathway: dict[str, Any], disease_by_code: dict[str, dict[str, Any]]) -> str | None:
    codes = [x for x in (pathway.get("disease_codes") or []) if x] + [x for x in (pathway.get("incoming_disease_codes") or []) if x]
    if codes:
        return codes[0]
    if pathway["pathway_code"] in MANUAL_PATHWAY_DISEASE_MAP:
        return MANUAL_PATHWAY_DISEASE_MAP[pathway["pathway_code"]]
    name = pathway.get("pathway_name") or ""
    best = None
    for code, item in disease_by_code.items():
        dname = item.get("disease_name") or ""
        if dname and dname in name:
            if best is None or len(dname) > len(disease_by_code[best]["disease_name"]):
                best = code
    return best


def disease_evidence(code: str, dx_rows: list[dict[str, Any]], suffix_evidence: dict[str, list[str]]) -> list[str]:
    direct = []
    for row in dx_rows:
        if row["disease_code"] == code:
            direct.extend(row.get("resolved_evidence_codes") or row.get("evidence_codes") or [])
    if direct:
        return list(dict.fromkeys(direct))[:5]
    suffix = code.split("-")[-1]
    return list(dict.fromkeys(suffix_evidence.get(suffix, [])))[:5]


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    remaining = load_json("remaining_static_migration_input.json")
    dx_probe = load_json("remaining_dxc_evidence_probe.json")
    static_probe = load_json("static_pathway_probe.json")
    action_probe = load_json("disease_action_probe.json")

    disease_by_code = {row["disease_code"]: row for row in action_probe}
    suffix_evidence: dict[str, list[str]] = {}
    for row in dx_probe:
        suffix = row["disease_code"].split("-")[-1]
        suffix_evidence.setdefault(suffix, [])
        suffix_evidence[suffix].extend(row.get("resolved_evidence_codes") or [])

    nodes: dict[str, dict[str, Any]] = {}
    rels: dict[tuple[str, str, str], dict[str, Any]] = {}

    # 1) DiagnosisCriteria -> diagnostic components
    for row in dx_probe:
        disease_code = row["disease_code"]
        disease_name = row["disease_name"]
        dx_code = row["dx_code"]
        ev = row.get("resolved_evidence_codes") or row.get("evidence_codes") or []
        group = disease_group(disease_code)
        for index, (suffix_name, logic) in enumerate(diagnostic_component_templates(group, disease_name), start=1):
            rule_code = f"RULE-CARD-MIG-DX-{safe_fragment(dx_code)}-{index:02d}"
            rule_name = f"{disease_name}{suffix_name}"
            add_node(
                nodes,
                rule_code,
                rule_name,
                "ClinicalRule",
                "临床规则",
                disease_code,
                rule_type="diagnostic_component",
                rule_logic=logic,
                evidence_ids=ev,
                source_diagnostic_criteria_code=dx_code,
            )
            add_rel(rels, dx_code, "has_diagnostic_component", rule_code, "diagnostic", ev)
            add_support(rels, rule_code, ev)

    # 2) Static ClinicalPathway -> PathwayStage + ClinicalRule
    unmapped = []
    for path in static_probe:
        pathway_code = path["pathway_code"]
        pathway_name = path["pathway_name"]
        disease_code = pathway_disease(path, disease_by_code)
        if not disease_code or disease_code not in disease_by_code:
            unmapped.append(path)
            continue
        disease = disease_by_code[disease_code]
        disease_name = disease["disease_name"]
        ev = disease_evidence(disease_code, dx_probe, suffix_evidence)
        # If old pathway was not linked from disease, add canonical disease -> pathway edge.
        if disease_code not in (path.get("disease_codes") or []) and disease_code not in (path.get("incoming_disease_codes") or []):
            add_rel(rels, disease_code, "has_clinical_pathway", pathway_code, "pathway", ev)
        stage_defs = [
            ("01-ASSESSMENT", f"{disease_name}路径评估阶段", f"进入{pathway_name}前，先确认诊断依据、严重程度、危险因素和禁忌信息。", "疑似或已诊断后进入路径评估", "完成诊断依据和风险信息核对", disease.get("dx_codes") or []),
            ("02-TREATMENT-DECISION", f"{disease_name}路径治疗决策阶段", f"根据患者状态、适应证、禁忌证和证据等级选择{pathway_name}中的治疗策略。", "诊断和风险分层完成", "形成治疗或转诊/处置方案", disease.get("treatment_codes") or []),
            ("03-FOLLOWUP-SAFETY", f"{disease_name}路径随访安全阶段", f"治疗后持续监测疗效、安全性、复发风险和随访计划。", "治疗或处置完成后", "形成随访和安全监测闭环", (disease.get("followup_codes") or []) + (disease.get("risk_codes") or [])),
        ]
        previous = None
        for order, (frag, stage_name, goal, trigger, exit_condition, action_targets) in enumerate(stage_defs, start=1):
            stage_code = f"STAGE-MIG-{safe_fragment(pathway_code)}-{frag}"
            rule_code = f"RULE-MIG-{safe_fragment(pathway_code)}-{frag}"
            add_node(
                nodes,
                stage_code,
                stage_name,
                "PathwayStage",
                "临床流程",
                disease_code,
                pathway_code=pathway_code,
                stage_order=order,
                stage_goal=goal,
                trigger_condition=trigger,
                exit_condition=exit_condition,
                source_static_pathway_code=pathway_code,
            )
            add_rel(rels, pathway_code, "has_pathway_stage", stage_code, "pathway", ev)
            if previous:
                add_rel(rels, previous, "next_pathway_stage", stage_code, "pathway", [])
            if ev:
                add_node(
                    nodes,
                    rule_code,
                    stage_name.replace("阶段", "规则"),
                    "ClinicalRule",
                    "临床规则",
                    disease_code,
                    rule_type="static_pathway_migration_rule",
                    rule_logic=goal,
                    evidence_ids=ev,
                    source_static_pathway_code=pathway_code,
                )
                add_rel(rels, stage_code, "has_stage_rule", rule_code, "pathway", ev)
                add_support(rels, rule_code, ev)
            for target in dict.fromkeys([x for x in action_targets if x]):
                add_rel(rels, stage_code, "has_recommended_action", target, "pathway", ev)
                if ev:
                    add_rel(rels, rule_code, "recommends_action", target, "cdss_rule", ev)
            previous = stage_code

    summary = {
        "node_count": len(nodes),
        "relation_count": len(rels),
        "node_entity_counts": dict(Counter(n["entityType"] for n in nodes.values())),
        "relation_type_counts": dict(Counter(r["relationType"] for r in rels.values())),
        "diagnostic_criteria_migrated": len({r["dx_code"] for r in dx_probe}),
        "static_pathways_migrated": len(static_probe) - len(unmapped),
        "static_pathways_unmapped": unmapped,
    }
    return list(nodes.values()), list(rels.values()), summary


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in sorted(rows, key=lambda x: x["code"] if "code" in x else x["id"]):
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({k for row in rows for k in row.keys()}) or ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    nodes, rels, summary = build()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUTPUT_DIR / "delta_nodes_upsert.jsonl", nodes)
    write_jsonl(OUTPUT_DIR / "delta_relations_add.jsonl", rels)
    write_csv(
        OUTPUT_DIR / "static_pathway_stage_matrix.csv",
        [r for r in rels if r["relationType"] in {"has_clinical_pathway", "has_pathway_stage", "next_pathway_stage", "has_stage_rule", "has_recommended_action", "recommends_action"}],
    )
    write_csv(
        OUTPUT_DIR / "diagnosis_criteria_component_matrix.csv",
        [r for r in rels if r["relationType"] == "has_diagnostic_component"],
    )
    (OUTPUT_DIR / "static_cdss_migration_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "README_迁移说明.md").write_text(
        f"""# 历史静态路径与诊断标准迁移包

本包用于把存量图谱中尚未满足动态 CDSS 使用要求的两类内容迁移到可执行结构：

1. 诊断标准标题节点：补 `has_diagnostic_component -> ClinicalRule`。
2. 历史静态 ClinicalPathway：补 `has_pathway_stage -> PathwayStage`、`has_stage_rule -> ClinicalRule`，并尽量挂接既有诊断标准、治疗方案、随访和风险分层节点。

## 统计

- 节点：{summary['node_count']}
- 关系：{summary['relation_count']}
- 诊断标准迁移：{summary['diagnostic_criteria_migrated']}
- 静态路径迁移：{summary['static_pathways_migrated']}
- 未映射静态路径：{len(summary['static_pathways_unmapped'])}

## 导入文件

- `delta_nodes_upsert.jsonl`
- `delta_relations_add.jsonl`
- `static_pathway_stage_matrix.csv`
- `diagnosis_criteria_component_matrix.csv`
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
