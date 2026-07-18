from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "项目管理中心_project_management" / "134_推荐来源裁决层落地_20260717"
OUT = WORK / "05_正式delta入库_20260717"
OUT.mkdir(parents=True, exist_ok=True)

BATCH_ID = "AMI推荐来源裁决正式入库_20260717"
SCHEMA_VERSION = "V1.17"
RUN_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_db_config() -> Dict[str, str]:
    text = (ROOT / "图谱数据库链接.txt").read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text)
    password = re.search(r"密码[:：]\s*([^\s；;]+)", text)
    if not (uri and user and password):
        raise RuntimeError("图谱数据库链接.txt 无法解析 Bolt、用户名或密码")
    return {"uri": uri.group(0), "user": user.group(1), "password": password.group(1)}


def flat(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return " ".join(flat(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def rel_query(rel_type: str) -> str:
    allowed = {
        "has_source_adjudication",
        "uses_primary_guideline",
        "decides_recommendation",
        "derived_from",
        "recommends_action",
        "blocks_action",
        "based_on_guideline",
    }
    if rel_type not in allowed:
        raise ValueError(f"不允许的关系类型: {rel_type}")
    return (
        f"MATCH (s) WHERE elementId(s)=$sid "
        f"MATCH (t) WHERE elementId(t)=$tid "
        f"MERGE (s)-[r:`{rel_type}`]->(t) "
        f"SET r += $props "
        f"RETURN elementId(r) AS rid"
    )


def source_adjudication_props(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "code": row["source_adjudication_code"],
        "name": row["source_adjudication_name"],
        "display_name": row["source_adjudication_name"],
        "preferred_name": row["source_adjudication_name"],
        "entityType": "SourceAdjudication",
        "中文名称": "推荐来源裁决",
        "disease_code": row["disease_code"],
        "disease_name": row["disease_name"],
        "applies_to_subtype_codes": row.get("applies_to_subtype_codes", []),
        "clinical_question": row["clinical_question"],
        "clinical_scenario": row["clinical_scenario"],
        "final_recommendation": row["final_recommendation"],
        "action_code": row["action_code"],
        "action_name": row["action_name"],
        "action_type": row["action_type"],
        "action_relation": row["action_relation"],
        "primary_guideline_code": row["primary_guideline_code"],
        "primary_guideline_name": row["primary_guideline_name"],
        "primary_evidence_code": row["primary_evidence_code"],
        "recommendation_class": row["recommendation_class"],
        "evidence_level": row["evidence_level"],
        "grade_note": row["grade_note"],
        "supporting_guidelines": row["supporting_guidelines"],
        "conflict_status": row["conflict_status"],
        "adjudication_reason": row["adjudication_reason"],
        "cdss_use_status": "正式推荐",
        "clinical_use_status": "clinical_ready",
        "clinical_review_status": "clinical_ready",
        "review_status": "passed",
        "formal_cdss_ready": True,
        "schema_version": SCHEMA_VERSION,
        "batch_id": BATCH_ID,
        "created_at": RUN_AT,
        "updated_at": RUN_AT,
    }


def recommendation_statement_props(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "code": row["recommendation_statement_code"],
        "name": row["recommendation_statement_name"],
        "display_name": row["recommendation_statement_name"],
        "preferred_name": row["recommendation_statement_name"],
        "entityType": "RecommendationStatement",
        "中文名称": "推荐陈述",
        "disease_code": row["disease_code"],
        "disease_name": row["disease_name"],
        "applies_to_subtype_codes": row.get("applies_to_subtype_codes", []),
        "clinical_question": row["clinical_question"],
        "clinical_scenario": row["clinical_scenario"],
        "recommendation_text": row["final_recommendation"],
        "final_recommendation": row["final_recommendation"],
        "action_code": row["action_code"],
        "action_name": row["action_name"],
        "action_type": row["action_type"],
        "action_relation": row["action_relation"],
        "primary_guideline_code": row["primary_guideline_code"],
        "primary_guideline_name": row["primary_guideline_name"],
        "primary_evidence_code": row["primary_evidence_code"],
        "source_adjudication_code": row["source_adjudication_code"],
        "recommendation_class": row["recommendation_class"],
        "evidence_level": row["evidence_level"],
        "grade_note": row["grade_note"],
        "conflict_status": row["conflict_status"],
        "cdss_use_status": "正式推荐",
        "clinical_use_status": "clinical_ready",
        "clinical_review_status": "clinical_ready",
        "review_status": "passed",
        "formal_cdss_ready": True,
        "schema_version": SCHEMA_VERSION,
        "batch_id": BATCH_ID,
        "created_at": RUN_AT,
        "updated_at": RUN_AT,
    }


FORMAL_ROWS: List[Dict[str, Any]] = [
    {
        "source_adjudication_code": "SRCADJ-CARD-AMI-DX-001",
        "source_adjudication_name": "AMI诊断标准来源裁决",
        "recommendation_statement_code": "RECST-CARD-AMI-SRCADJ-DX-20260717",
        "recommendation_statement_name": "AMI诊断标准推荐陈述",
        "disease_code": "DIS-CARD-CAD-AMI",
        "disease_name": "急性心肌梗死",
        "applies_to_subtype_codes": ["DIS-CARD-CAD-STEMI", "DIS-CARD-CAD-NSTEMI"],
        "clinical_question": "AMI诊断标准",
        "clinical_scenario": "疑似急性心肌缺血或急性胸痛患者",
        "final_recommendation": "结合缺血症状、心电图缺血改变、心肌坏死标志物动态变化和影像学证据进行急性心肌梗死诊断。",
        "action_code": "DXC-CARD-547346EE2FED",
        "action_name": "急性心肌梗死诊断标准",
        "action_type": "DiagnosisCriteria",
        "action_relation": "recommends_action",
        "primary_guideline_code": "SRC-DOC-174B3BDD2451501A",
        "primary_guideline_name": "4TH universal definition of MI.pdf",
        "primary_evidence_code": "EVD-BFD8DF56E0886EF186D8-AMI",
        "recommendation_class": "定义标准",
        "evidence_level": "国际通用定义标准",
        "grade_note": "诊断定义类证据原文无I/A等治疗推荐分级，按定义标准入正式诊断依据。",
        "supporting_guidelines": ["《内科学（第10版）》.pdf", "2018 STEMI院前溶栓治疗中国专家共识.pdf"],
        "conflict_status": "无冲突",
        "adjudication_reason": "第四版通用定义为AMI诊断定义主依据，教材作为中文基础骨架支持。",
    },
    {
        "source_adjudication_code": "SRCADJ-CARD-AMI-ECG-001",
        "source_adjudication_name": "AMI首诊心电图来源裁决",
        "recommendation_statement_code": "RECST-CARD-AMI-SRCADJ-ECG-20260717",
        "recommendation_statement_name": "AMI首诊心电图推荐陈述",
        "disease_code": "DIS-CARD-CAD-AMI",
        "disease_name": "急性心肌梗死",
        "applies_to_subtype_codes": ["DIS-CARD-CAD-STEMI", "DIS-CARD-CAD-NSTEMI"],
        "clinical_question": "首诊心电图检查",
        "clinical_scenario": "疑似ACS或急性胸痛患者",
        "final_recommendation": "首次医疗接触后尽快记录并判读12导联心电图，用于识别ST段抬高、压低、T波改变或异常Q波。",
        "action_code": "EXAM-CARD-A80B855C8C77",
        "action_name": "12导联心电图",
        "action_type": "Exam",
        "action_relation": "recommends_action",
        "primary_guideline_code": "SRC-DOC-866065446A7A5F65",
        "primary_guideline_name": "2018 STEMI院前溶栓治疗中国专家共识.pdf",
        "primary_evidence_code": "EVD-9A1C41BB38E3029E07C5-STEMI",
        "recommendation_class": "专家共识推荐",
        "evidence_level": "专家共识证据",
        "grade_note": "专家共识原文未结构化为I/A等分级，保留来源类型和原文证据。",
        "supporting_guidelines": ["《内科学（第10版）》.pdf"],
        "conflict_status": "无冲突",
        "adjudication_reason": "心电图是AMI/STEMI早期诊断和处理的首要动作，专家共识给出10分钟内完成和判读要求。",
    },
    {
        "source_adjudication_code": "SRCADJ-CARD-AMI-PCI-001",
        "source_adjudication_name": "STEMI直接PCI来源裁决",
        "recommendation_statement_code": "RECST-CARD-AMI-SRCADJ-PCI-20260717",
        "recommendation_statement_name": "STEMI直接PCI推荐陈述",
        "disease_code": "DIS-CARD-CAD-AMI",
        "disease_name": "急性心肌梗死",
        "applies_to_subtype_codes": ["DIS-CARD-CAD-STEMI"],
        "clinical_question": "STEMI再灌注策略",
        "clinical_scenario": "STEMI确诊或高度疑似，需选择再灌注策略",
        "final_recommendation": "能在规定时间窗内完成直接经皮冠状动脉介入治疗时，应优先选择直接PCI；明显延误时进入溶栓评估。",
        "action_code": "PROC-CARD-E9ADC25A25E3",
        "action_name": "经皮冠状动脉介入治疗",
        "action_type": "Procedure",
        "action_relation": "recommends_action",
        "primary_guideline_code": "SRC-DOC-866065446A7A5F65",
        "primary_guideline_name": "2018 STEMI院前溶栓治疗中国专家共识.pdf",
        "primary_evidence_code": "EVD-C29D798C2C4AA7DB70EA-STEMI",
        "recommendation_class": "专家共识推荐",
        "evidence_level": "专家共识证据",
        "grade_note": "专家共识原文未结构化为I/A等分级，保留来源类型和原文证据。",
        "supporting_guidelines": ["《内科学（第10版）》.pdf", "STEMI CN 2019.pdf"],
        "conflict_status": "无冲突",
        "adjudication_reason": "区域协同救治流程明确在120分钟内完成PPCI时优先转运直接PCI。",
    },
    {
        "source_adjudication_code": "SRCADJ-CARD-AMI-FIB-001",
        "source_adjudication_name": "STEMI溶栓治疗来源裁决",
        "recommendation_statement_code": "RECST-CARD-AMI-SRCADJ-FIB-20260717",
        "recommendation_statement_name": "STEMI溶栓治疗推荐陈述",
        "disease_code": "DIS-CARD-CAD-AMI",
        "disease_name": "急性心肌梗死",
        "applies_to_subtype_codes": ["DIS-CARD-CAD-STEMI"],
        "clinical_question": "STEMI溶栓治疗",
        "clinical_scenario": "STEMI发病早期，预计不能在120分钟内完成PPCI且无溶栓禁忌",
        "final_recommendation": "符合STEMI溶栓适应证且不能在120分钟内完成PPCI时，可行溶栓治疗，并在溶栓后评估再通及补救PCI。",
        "action_code": "PROC-CARD-DA0F467D4A30",
        "action_name": "溶栓治疗",
        "action_type": "Procedure",
        "action_relation": "recommends_action",
        "primary_guideline_code": "SRC-DOC-866065446A7A5F65",
        "primary_guideline_name": "2018 STEMI院前溶栓治疗中国专家共识.pdf",
        "primary_evidence_code": "EVD-56AF2340E37314FCA705-AMI",
        "recommendation_class": "专家共识推荐",
        "evidence_level": "专家共识证据",
        "grade_note": "专家共识原文未结构化为I/A等分级，保留来源类型和原文证据。",
        "supporting_guidelines": ["《内科学（第10版）》.pdf"],
        "conflict_status": "无冲突",
        "adjudication_reason": "共识明确溶栓适应证包括急性胸痛、ST段抬高、发病时间、年龄和不能120分钟内完成PPCI。",
    },
    {
        "source_adjudication_code": "SRCADJ-CARD-AMI-FIB-CONTRA-001",
        "source_adjudication_name": "STEMI溶栓禁忌来源裁决",
        "recommendation_statement_code": "RECST-CARD-AMI-SRCADJ-FIB-CONTRA-20260717",
        "recommendation_statement_name": "STEMI溶栓禁忌阻断推荐陈述",
        "disease_code": "DIS-CARD-CAD-AMI",
        "disease_name": "急性心肌梗死",
        "applies_to_subtype_codes": ["DIS-CARD-CAD-STEMI"],
        "clinical_question": "溶栓禁忌证",
        "clinical_scenario": "拟行溶栓治疗前",
        "final_recommendation": "存在出血性脑卒中、近期脑血管事件、活动性内脏出血、未排除主动脉夹层、严重未控制高血压等情况时，应阻断溶栓治疗。",
        "action_code": "PROC-CARD-DA0F467D4A30",
        "action_name": "溶栓治疗",
        "action_type": "Procedure",
        "action_relation": "blocks_action",
        "primary_guideline_code": "SRC-DOC-866065446A7A5F65",
        "primary_guideline_name": "2018 STEMI院前溶栓治疗中国专家共识.pdf",
        "primary_evidence_code": "EVD-B9B303B0E1B921BC095F-AMI",
        "recommendation_class": "禁忌阻断规则",
        "evidence_level": "专家共识证据",
        "grade_note": "禁忌阻断类规则不使用治疗推荐等级，按原文禁忌清单入正式阻断逻辑。",
        "supporting_guidelines": ["《内科学（第10版）》.pdf"],
        "conflict_status": "无冲突",
        "adjudication_reason": "共识溶栓筛查表列出主动脉夹层、高血压、抗凝药、长时间复苏等禁忌或高风险条件。",
    },
]


def resolve_node_id(tx, code: str, *, name: Optional[str] = None, entity_type: Optional[str] = None) -> Optional[str]:
    hit = tx.run(
        "MATCH (n:KGNode) WHERE n.code = $code RETURN elementId(n) AS id LIMIT 1",
        code=code,
    ).single()
    if hit:
        return hit["id"]
    if name and entity_type:
        hit = tx.run(
            """
            MATCH (n:KGNode)
            WHERE n.entityType=$entity_type AND n.name=$name
            RETURN elementId(n) AS id
            ORDER BY CASE WHEN n.code=$code THEN 0 ELSE 1 END
            LIMIT 1
            """,
            code=code,
            name=name,
            entity_type=entity_type,
        ).single()
        if hit:
            return hit["id"]
    return None


def verify_existing_nodes(tx, row: Dict[str, Any]) -> Dict[str, Any]:
    checks = {
        "disease": (row["disease_code"], row["disease_name"], "Disease"),
        "guideline": (row["primary_guideline_code"], row["primary_guideline_name"], "Guideline"),
        "evidence": (row["primary_evidence_code"], None, "Evidence"),
        "action": (row["action_code"], row["action_name"], row["action_type"]),
    }
    resolved = {}
    for key, (code, name, entity_type) in checks.items():
        resolved[key] = resolve_node_id(tx, code, name=name, entity_type=entity_type)
    return resolved


def merge_node(tx, label: str, props: Dict[str, Any]) -> str:
    if label not in {"SourceAdjudication", "RecommendationStatement"}:
        raise ValueError(label)
    q = (
        f"MERGE (n:KGNode:{label} {{code:$code}}) "
        f"SET n += $props "
        f"RETURN elementId(n) AS id"
    )
    return tx.run(q, code=props["code"], props=props).single()["id"]


def merge_relation(tx, sid: str, rel_type: str, tid: str, props: Dict[str, Any]) -> str:
    return tx.run(rel_query(rel_type), sid=sid, tid=tid, props=props).single()["rid"]


def import_rows() -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    rels: List[Dict[str, Any]] = []
    evidence_selection: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    import_records: List[Dict[str, Any]] = []

    cfg = read_db_config()
    with GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"])) as driver:
        with driver.session() as session:
            for row in FORMAL_ROWS:
                resolved = session.execute_write(verify_existing_nodes, row)
                unresolved = [k for k, v in resolved.items() if not v]
                if unresolved:
                    missing.append(
                        {
                            "source_adjudication_code": row["source_adjudication_code"],
                            "missing": "；".join(unresolved),
                            "action_code": row["action_code"],
                            "primary_evidence_code": row["primary_evidence_code"],
                        }
                    )
                    continue

                src_props = source_adjudication_props(row)
                rec_props = recommendation_statement_props(row)
                src_id = session.execute_write(merge_node, "SourceAdjudication", src_props)
                rec_id = session.execute_write(merge_node, "RecommendationStatement", rec_props)
                nodes.extend([src_props, rec_props])

                rel_base = {
                    "batch_id": BATCH_ID,
                    "schema_version": SCHEMA_VERSION,
                    "created_at": RUN_AT,
                    "updated_at": RUN_AT,
                    "clinical_use_status": "clinical_ready",
                    "clinical_review_status": "clinical_ready",
                    "cdss_use_status": "正式推荐",
                    "formal_cdss_ready": True,
                    "recommendation_class": row["recommendation_class"],
                    "evidence_level": row["evidence_level"],
                    "primary_evidence_code": row["primary_evidence_code"],
                    "primary_guideline_code": row["primary_guideline_code"],
                    "source_adjudication_code": row["source_adjudication_code"],
                    "recommendation_statement_code": row["recommendation_statement_code"],
                }
                rel_specs = [
                    (resolved["disease"], "has_source_adjudication", src_id),
                    (src_id, "uses_primary_guideline", resolved["guideline"]),
                    (src_id, "decides_recommendation", rec_id),
                    (src_id, "derived_from", resolved["evidence"]),
                    (src_id, row["action_relation"], resolved["action"]),
                    (rec_id, "based_on_guideline", resolved["guideline"]),
                    (rec_id, "derived_from", resolved["evidence"]),
                    (rec_id, row["action_relation"], resolved["action"]),
                ]
                for sid, rel_type, tid in rel_specs:
                    rid = session.execute_write(merge_relation, sid, rel_type, tid, rel_base)
                    rels.append(
                        {
                            "source_code": row["source_adjudication_code"] if sid == src_id else row["recommendation_statement_code"],
                            "relationship": rel_type,
                            "target_code": row["primary_evidence_code"],
                            "rid": rid,
                        }
                    )

                evidence_selection.append(
                    {
                        "裁决编码": row["source_adjudication_code"],
                        "临床问题": row["clinical_question"],
                        "主依据指南编码": row["primary_guideline_code"],
                        "主依据指南": row["primary_guideline_name"],
                        "主证据编码": row["primary_evidence_code"],
                        "推荐等级": row["recommendation_class"],
                        "证据等级": row["evidence_level"],
                        "动作编码": row["action_code"],
                        "动作名称": row["action_name"],
                        "动作关系": row["action_relation"],
                        "分级说明": row["grade_note"],
                    }
                )
                import_records.append(
                    {
                        "source_adjudication_code": row["source_adjudication_code"],
                        "recommendation_statement_code": row["recommendation_statement_code"],
                        "status": "imported",
                    }
                )

            verify = session.run(
                """
                MATCH (n:KGNode)
                WHERE n.batch_id=$batch_id
                WITH collect(n) AS ns
                RETURN
                  size([n IN ns WHERE n.entityType='SourceAdjudication']) AS source_adjudication_count,
                  size([n IN ns WHERE n.entityType='RecommendationStatement']) AS recommendation_statement_count,
                  size([n IN ns WHERE n.primary_evidence_code IS NULL OR n.primary_evidence_code='']) AS missing_primary_evidence_count,
                  size([n IN ns WHERE n.recommendation_class IS NULL OR n.recommendation_class='']) AS missing_recommendation_class_count,
                  size([n IN ns WHERE n.evidence_level IS NULL OR n.evidence_level='']) AS missing_evidence_level_count,
                  size([n IN ns WHERE n.action_code IS NULL OR n.action_code='']) AS missing_action_code_count,
                  size([n IN ns WHERE n.cdss_use_status <> '正式推荐']) AS non_formal_cdss_count
                """,
                batch_id=BATCH_ID,
            ).single().data()

            rel_verify = [
                dict(r)
                for r in session.run(
                    """
                    MATCH ()-[r]->()
                    WHERE r.batch_id=$batch_id
                    RETURN type(r) AS relationship, count(r) AS count
                    ORDER BY relationship
                    """,
                    batch_id=BATCH_ID,
                )
            ]

    write_jsonl(OUT / "nodes_delta_final.jsonl", nodes)
    write_jsonl(OUT / "relations_delta_final.jsonl", rels)
    write_csv(OUT / "AMI正式推荐主证据动作编码补齐表_20260717.csv", evidence_selection)
    write_csv(OUT / "AMI正式推荐入库缺失检查_20260717.csv", missing)
    result = {
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "run_at": RUN_AT,
        "planned_formal_rows": len(FORMAL_ROWS),
        "imported_rows": len(import_records),
        "missing_rows": len(missing),
        "nodes_written": len(nodes),
        "relations_written": len(rels),
        "verify": verify,
        "relationship_verify": rel_verify,
        "missing": missing,
    }
    (OUT / "AMI来源裁决正式入库结果_20260717.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = [
        "# AMI 来源裁决正式入库报告（2026-07-17）",
        "",
        f"- 批次：{BATCH_ID}",
        f"- Schema：{SCHEMA_VERSION}",
        f"- 执行时间：{RUN_AT}",
        f"- 计划正式推荐：{len(FORMAL_ROWS)} 条",
        f"- 成功入库：{len(import_records)} 条",
        f"- 未入库缺失：{len(missing)} 条",
        f"- 写入节点：{len(nodes)} 个（SourceAdjudication + RecommendationStatement）",
        f"- 写入/合并关系：{len(rels)} 条",
        "",
        "## 服务器复核",
        "",
        f"- 推荐来源裁决节点：{verify.get('source_adjudication_count')}",
        f"- 推荐陈述节点：{verify.get('recommendation_statement_count')}",
        f"- 缺主证据编码：{verify.get('missing_primary_evidence_count')}",
        f"- 缺推荐等级：{verify.get('missing_recommendation_class_count')}",
        f"- 缺证据等级：{verify.get('missing_evidence_level_count')}",
        f"- 缺动作编码：{verify.get('missing_action_code_count')}",
        f"- 非正式 CDSS 状态：{verify.get('non_formal_cdss_count')}",
        "",
        "## 关系复核",
        "",
    ]
    for item in rel_verify:
        report.append(f"- {item['relationship']}：{item['count']}")
    if missing:
        report.extend(["", "## 未入库原因", ""])
        for item in missing:
            report.append(f"- {item['source_adjudication_code']}：{item['missing']}")
    (OUT / "AMI来源裁决正式入库报告_20260717.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(import_rows(), ensure_ascii=False, indent=2))
