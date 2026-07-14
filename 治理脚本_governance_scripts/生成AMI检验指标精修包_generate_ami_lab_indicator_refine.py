# -*- coding: utf-8 -*-
"""生成 AMI 检验指标精修包。

用途：
- 修复“疾病 -> 检验项目 -> 检验指标”下钻缺口。
- 不新增 LabTestIndicator，按 Schema 使用 ExamIndicator 统一承载检查/检验指标。
- 只生成本地 delta、审计文件和报告；是否导入由公共导入脚本执行。
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "心血管内科文献集合"
OUT_DIR = COLLECTION / "BATCH-CARD-CAD-AMI-LABIND-20260713-001_AMI检验指标精修_lab_indicator_refine"
BATCH_ID = "BATCH-CARD-CAD-AMI-LABIND-20260713-001"
CREATED_AT = "2026-07-13 00:20:00"
SCHEMA_VERSION = "V1.15"
SKILL_VERSION = "V2.1-AMI-lab-indicator-refine"
DISEASE_CODE = "DIS-CARD-CAD-AMI"
DISEASE_NAME = "急性心肌梗死"
SOURCE_NAME = "《内科学（第10版）》"
SOURCE_SECTION = "第三篇 循环系统疾病 / 第四节 急性冠脉综合征 / 二、急性ST段抬高型心肌梗死"


def short_hash(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest().upper()[:n]


def kg_id(code: str) -> str:
    return "KG_" + code.replace("-", "_")


def rel_id(source: str, relation_type: str, target: str) -> str:
    return "REL-" + short_hash(f"{source}|{relation_type}|{target}", 20)


def parse_conn() -> tuple[str, str, str, str]:
    text = (ROOT / "图谱数据库链接.txt").read_text(encoding="utf-8", errors="ignore")
    http = re.search(r"https?://[^\s]+", text)
    bolt = re.search(r"bolt://[^\s]+", text)
    user = re.search(r"用户名\s*[:：]\s*([^\s]+)", text)
    pwd = re.search(r"密码\s*[:：]\s*([^\s]+)", text)
    if not (http and bolt and user and pwd):
        raise RuntimeError("图谱数据库链接.txt 缺少 http/bolt/用户名/密码字段")
    return http.group(0), bolt.group(0), user.group(1), pwd.group(1)


def base_node(entity_type: str, code: str, name: str, **props: Any) -> dict[str, Any]:
    node = {
        "id": kg_id(code),
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": props.pop("entityCategory", ""),
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "scope_type": "disease",
        "scope_target": DISEASE_NAME,
        "disease_code": DISEASE_CODE,
        "disease_name": DISEASE_NAME,
        "source_type": "authoritative_textbook",
        "source_authority": SOURCE_NAME,
        "source_name": SOURCE_NAME,
        "source_section": SOURCE_SECTION,
        "clinical_review_status": "pending_clinical_use_effect_review",
        "review_status": "ai_prechecked",
        "merge_status": "delta_ready",
        "formal_cdss_ready": False,
        "cdss_release_level": "test_recommendation",
        "created_at": CREATED_AT,
    }
    node.update({k: v for k, v in props.items() if v not in (None, "")})
    return node


def relation(source_code: str, relation_type: str, target_code: str, evidence_codes: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": rel_id(source_code, relation_type, target_code),
        "source_code": source_code,
        "relationType": relation_type,
        "target_code": target_code,
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "batch_id": BATCH_ID,
        "source_type": "authoritative_textbook",
        "source_authority": SOURCE_NAME,
        "disease_code": DISEASE_CODE,
        "disease_name": DISEASE_NAME,
        "formal_cdss_ready": False,
        "clinical_review_status": "pending_clinical_use_effect_review",
        "created_at": CREATED_AT,
        "evidence_ids": evidence_codes or [],
        "evidence_count": len(evidence_codes or []),
    }


EVIDENCE_SPECS = {
    "myocardial_biomarker": {
        "code": "EVD-CARD-AMI-LABIND-MYOCARDIAL-BIOMARKER",
        "name": "急性心肌梗死-心肌坏死标志物检验指标-教材证据",
        "page": "251",
        "text": (
            "血清心肌坏死标志物增高水平与心肌坏死范围及预后明显相关。肌红蛋白起病后2小时内升高，"
            "12小时内达高峰，24～48小时内恢复正常；cTnI或cTnT起病3～4小时后升高，cTnI于11～24小时达高峰，"
            "7～10天降至正常，cTnT于24～48小时达高峰，10～14天降至正常；CK-MB起病后4小时内增高，"
            "16～24小时达高峰，3～4天恢复正常。以往沿用的肌酸激酶（CK）、AST、LDH特异性及敏感性均远不如上述心肌坏死标志物，"
            "已不再用于诊断AMI。"
        ),
    },
    "inflammation": {
        "code": "EVD-CARD-AMI-LABIND-INFLAMMATION",
        "name": "急性心肌梗死-炎症和血常规检验指标-教材证据",
        "page": "251",
        "text": (
            "急性心肌梗死起病24～48小时后白细胞可增至（10～20）×10^9/L，中性粒细胞增多，"
            "嗜酸性粒细胞减少或消失；红细胞沉降率增快；C反应蛋白增高，均可持续1～3周。"
        ),
    },
    "differential": {
        "code": "EVD-CARD-AMI-LABIND-DIFFERENTIAL",
        "name": "急性心肌梗死-鉴别诊断相关检验指标-教材证据",
        "page": "252",
        "text": (
            "主动脉夹层可有D-二聚体升高但血清心肌坏死标志物一般正常或仅轻度升高；"
            "急性肺动脉栓塞也可发生胸痛、休克和低氧血症，需结合影像和心电图表现鉴别。"
        ),
    },
    "lipid": {
        "code": "EVD-CARD-AMI-LABIND-LIPID",
        "name": "急性心肌梗死-血脂管理相关检验指标-教材证据",
        "page": "256-257",
        "text": "急性心肌梗死治疗和二级预防中需要调脂治疗，调脂药物使用参照UA/NSTEMI部分和冠心病二级预防策略。",
    },
}


INDICATOR_SPECS = [
    {
        "name": "心肌肌钙蛋白升高",
        "parents": ["心肌肌钙蛋白", "肌钙蛋白"],
        "evidence": "myocardial_biomarker",
        "direction": "升高",
        "clinical_use": "急性心肌梗死核心诊断指标；需结合动态变化和临床表现。",
        "time_window": "起病3～4小时后升高，cTnI 11～24小时达高峰，cTnT 24～48小时达高峰。",
    },
    {
        "name": "肌酸激酶同工酶升高",
        "parents": ["肌酸激酶同工酶", "CK-MB"],
        "evidence": "myocardial_biomarker",
        "direction": "升高",
        "clinical_use": "反映心肌梗死范围；恢复较快，可辅助判断再梗死。",
        "time_window": "起病后4小时内升高，16～24小时达高峰，3～4天恢复正常。",
    },
    {
        "name": "肌酸激酶升高",
        "parents": ["肌酸激酶"],
        "evidence": "myocardial_biomarker",
        "direction": "升高",
        "clinical_use": "历史心肌酶指标；教材明确提示特异性和敏感性不如心肌坏死标志物，已不再用于AMI诊断。",
    },
    {
        "name": "肌红蛋白升高",
        "parents": ["肌红蛋白"],
        "evidence": "myocardial_biomarker",
        "direction": "升高",
        "clinical_use": "出现早、敏感性高但特异性不强，不能单独确诊AMI。",
        "time_window": "起病后2小时内升高，12小时内达高峰，24～48小时恢复正常。",
    },
    {
        "name": "白细胞计数升高",
        "parents": ["血常规", "白细胞计数"],
        "evidence": "inflammation",
        "direction": "升高",
        "clinical_use": "坏死物质吸收相关炎症反应指标，不作为AMI特异性诊断指标。",
        "reference_range_note": "起病24～48小时后可增至（10～20）×10^9/L。",
    },
    {
        "name": "中性粒细胞增多",
        "parents": ["血常规"],
        "evidence": "inflammation",
        "direction": "升高",
        "clinical_use": "坏死物质吸收相关炎症反应指标。",
    },
    {
        "name": "嗜酸性粒细胞减少或消失",
        "parents": ["血常规"],
        "evidence": "inflammation",
        "direction": "降低",
        "clinical_use": "AMI后炎症反应相关变化。",
    },
    {
        "name": "红细胞沉降率增快",
        "parents": ["红细胞沉降率", "血沉"],
        "evidence": "inflammation",
        "direction": "增快",
        "clinical_use": "AMI后炎症反应相关变化。",
    },
    {
        "name": "C反应蛋白升高",
        "parents": ["C反应蛋白", "CRP"],
        "evidence": "inflammation",
        "direction": "升高",
        "clinical_use": "AMI后炎症反应相关变化，可持续1～3周。",
    },
    {
        "name": "D-二聚体升高",
        "parents": ["D-二聚体"],
        "evidence": "differential",
        "direction": "升高",
        "clinical_use": "主要用于主动脉夹层、肺动脉栓塞等胸痛鉴别线索；不能作为AMI特异性诊断指标。",
    },
    {
        "name": "低密度脂蛋白胆固醇升高",
        "parents": ["低密度脂蛋白胆固醇", "血脂检查", "血脂"],
        "evidence": "lipid",
        "direction": "升高",
        "clinical_use": "冠心病风险管理和二级预防相关指标，不作为AMI急性确诊指标。",
    },
]


def fetch_ami_labs() -> list[dict[str, str]]:
    _, bolt, user, password = parse_conn()
    query = """
    MATCH (:KGNode {code:$code})-[:requires_lab_test]->(l:KGNode)
    RETURN DISTINCT l.code AS code, l.name AS name, coalesce(l.entityType,'') AS entityType
    ORDER BY name, code
    """
    with GraphDatabase.driver(bolt, auth=(user, password)) as driver:
        with driver.session() as session:
            return [dict(r) for r in session.run(query, code=DISEASE_CODE)]


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    labs = fetch_ami_labs()
    labs_by_name: dict[str, list[dict[str, str]]] = {}
    for lab in labs:
        labs_by_name.setdefault(lab["name"], []).append(lab)

    nodes: dict[str, dict[str, Any]] = {}
    rels: dict[tuple[str, str, str], dict[str, Any]] = {}
    adopted: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    for key, ev in EVIDENCE_SPECS.items():
        node = base_node(
            "Evidence",
            ev["code"],
            ev["name"],
            entityCategory="证据",
            evidence_role="textbook_lab_indicator_original",
            evidence_slot="exam_lab",
            evidence_text=ev["text"],
            original_text=ev["text"],
            evidence_summary=ev["text"],
            source_page=ev["page"],
            source_location=f"{SOURCE_NAME} 第{ev['page']}页；{SOURCE_SECTION}",
            recommendation_class="N/A",
            evidence_level="N/A",
            knowledge_strength="high",
            clinical_applicability="general",
        )
        nodes[node["code"]] = node

    for spec in INDICATOR_SPECS:
        indicator_code = f"IND-CARD-AMI-LAB-{short_hash(spec['name'])}"
        evidence_code = EVIDENCE_SPECS[spec["evidence"]]["code"]
        node = base_node(
            "ExamIndicator",
            indicator_code,
            spec["name"],
            entityCategory="检查/检验指标",
            indicator_category="检验指标",
            indicator_domain="lab_test",
            value_direction=spec.get("direction"),
            clinical_use=spec.get("clinical_use"),
            time_window=spec.get("time_window"),
            reference_range_note=spec.get("reference_range_note"),
            description=spec.get("clinical_use"),
        )
        nodes[node["code"]] = node
        rels[(indicator_code, "supported_by_evidence", evidence_code)] = relation(
            indicator_code, "supported_by_evidence", evidence_code, [evidence_code]
        )

        matched = []
        for parent_name in spec["parents"]:
            for lab in labs_by_name.get(parent_name, []):
                matched.append(lab)
        if not matched:
            gaps.append(
                {
                    "指标": spec["name"],
                    "期望父级检验项目": "；".join(spec["parents"]),
                    "缺口原因": "AMI当前requires_lab_test未找到对应检验项目",
                }
            )
            continue
        seen_parent_codes = set()
        for lab in matched:
            if lab["code"] in seen_parent_codes:
                continue
            seen_parent_codes.add(lab["code"])
            rels[(lab["code"], "lab_test_has_indicator", indicator_code)] = relation(
                lab["code"], "lab_test_has_indicator", indicator_code, [evidence_code]
            )
            adopted.append(
                {
                    "疾病编码": DISEASE_CODE,
                    "疾病名称": DISEASE_NAME,
                    "检验项目编码": lab["code"],
                    "检验项目名称": lab["name"],
                    "指标编码": indicator_code,
                    "指标名称": spec["name"],
                    "证据编码": evidence_code,
                    "临床用途": spec.get("clinical_use", ""),
                }
            )

    return list(nodes.values()), list(rels.values()), adopted, gaps


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


def local_audit(nodes: list[dict[str, Any]], rels: list[dict[str, Any]]) -> dict[str, Any]:
    node_codes = [n["code"] for n in nodes]
    rel_keys = [(r["source_code"], r["relationType"], r["target_code"]) for r in rels]
    missing_required = [
        n.get("code")
        for n in nodes
        if not n.get("code") or not n.get("name") or not n.get("entityType")
    ]
    duplicate_node_codes = sorted({c for c in node_codes if node_codes.count(c) > 1})
    duplicate_rel_keys = sorted({"|".join(k) for k in rel_keys if rel_keys.count(k) > 1})
    missing_rel_endpoint = [
        "|".join(k)
        for k in rel_keys
        if k[0].startswith("IND-") and k[0] not in node_codes or k[2].startswith("IND-") and k[2] not in node_codes
    ]
    evidence_without_text = [
        n["code"]
        for n in nodes
        if n.get("entityType") == "Evidence" and not str(n.get("evidence_text") or "").strip()
    ]
    return {
        "batch_id": BATCH_ID,
        "created_at": CREATED_AT,
        "node_count": len(nodes),
        "relation_count": len(rels),
        "lab_indicator_node_count": sum(1 for n in nodes if n.get("entityType") == "ExamIndicator"),
        "lab_test_has_indicator_relation_count": sum(1 for r in rels if r.get("relationType") == "lab_test_has_indicator"),
        "missing_required": missing_required,
        "duplicate_node_codes": duplicate_node_codes,
        "duplicate_relation_keys": duplicate_rel_keys,
        "missing_rel_endpoint": missing_rel_endpoint,
        "evidence_without_text": evidence_without_text,
        "local_hard_gate_pass": not (
            missing_required or duplicate_node_codes or duplicate_rel_keys or missing_rel_endpoint or evidence_without_text
        ),
    }


def main() -> int:
    for sub in ["00_config", "02_delta", "03_audit", "04_reports"]:
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)

    nodes, rels, adopted, gaps = build()
    audit = local_audit(nodes, rels)

    write_jsonl(OUT_DIR / "02_delta" / "delta_nodes_upsert.jsonl", nodes)
    write_jsonl(OUT_DIR / "02_delta" / "delta_relations_add.jsonl", rels)
    write_csv(
        OUT_DIR / "03_audit" / "AMI检验指标精修采纳明细.csv",
        adopted,
        ["疾病编码", "疾病名称", "检验项目编码", "检验项目名称", "指标编码", "指标名称", "证据编码", "临床用途"],
    )
    write_csv(OUT_DIR / "03_audit" / "AMI检验指标缺口.csv", gaps, ["指标", "期望父级检验项目", "缺口原因"])
    (OUT_DIR / "03_audit" / "quality_audit_summary.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "00_config" / "batch_config.json").write_text(
        json.dumps(
            {
                "batch_id": BATCH_ID,
                "scope_type": "disease",
                "scope_target": DISEASE_NAME,
                "disease_code": DISEASE_CODE,
                "source": SOURCE_NAME,
                "purpose": "补全AMI检验项目到检验指标的下钻关系",
                "schema_rule": "LabTest --lab_test_has_indicator--> ExamIndicator",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report = [
        "# AMI检验指标精修报告",
        "",
        f"- 批次：`{BATCH_ID}`",
        f"- 节点：{audit['node_count']} 个",
        f"- 关系：{audit['relation_count']} 条",
        f"- 检验指标节点：{audit['lab_indicator_node_count']} 个",
        f"- `lab_test_has_indicator`：{audit['lab_test_has_indicator_relation_count']} 条",
        f"- 本地硬闸门：{'通过' if audit['local_hard_gate_pass'] else '未通过'}",
        "",
        "## 说明",
        "",
        "本批次不新增 `LabTestIndicator`。检验指标仍使用 Schema 标准实体 `ExamIndicator`，",
        "通过 `LabTest -> lab_test_has_indicator -> ExamIndicator` 区分为检验指标。",
    ]
    (OUT_DIR / "04_reports" / "AMI检验指标精修报告_20260713.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if audit["local_hard_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
