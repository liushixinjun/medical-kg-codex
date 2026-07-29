from __future__ import annotations

import argparse
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
DEFAULT_OUTPUT_DIR = ROOT / "项目管理中心_project_management" / "150_已解析疾病扩展收口_20260729"
AMI_CM_SCRIPT = ROOT / "公共执行层_kg_pipeline" / "AMI与心肌病样板收口.py"


def read_graph_connection(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    uri_match = re.search(r"bolt://[^\s;；]+", text)
    user_match = re.search(r"(?:用户名|user|username)\s*[:：]\s*([^\s;；]+)", text, re.I)
    pwd_match = re.search(r"(?:密码|password)\s*[:：]\s*([^\s;；]+)", text, re.I)
    if not (uri_match and user_match and pwd_match):
        raise RuntimeError(f"无法从连接文件解析 bolt、用户名、密码：{path}")
    return {
        "uri": uri_match.group(0),
        "username": user_match.group(1),
        "password": pwd_match.group(1),
    }


def run_list(tx: Any, query: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(record) for record in tx.run(query, **params)]


def load_differential_specs() -> dict[str, dict[str, Any]]:
    spec = importlib.util.spec_from_file_location("ami_cm_sample_closure", AMI_CM_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载样板脚本：{AMI_CM_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(getattr(module, "DIFFERENTIAL_REPAIR_SPECS"))


def collect_audit(session: Any) -> dict[str, Any]:
    return session.execute_read(
        lambda tx: {
            "graph": run_list(
                tx,
                """
                MATCH (n)
                WITH count(n) AS node_count
                MATCH ()-[r]->()
                RETURN node_count, count(r) AS relation_count
                """,
            )[0],
            "wrong_recommendation_to_lab_subitem": run_list(
                tx,
                """
                MATCH (src:KGNode)-[r:recommends_action]->(ls:KGNode {entityType:'LabSubitem'})
                WHERE src.entityType IN ['RecommendationStatement','ClinicalRule']
                OPTIONAL MATCH (li:KGNode {entityType:'LabItem'})-[:lab_item_has_subitem]->(ls)
                RETURN src.entityType AS source_type,
                       src.code AS source_code,
                       coalesce(src.name, src.display_name, src.preferred_name, src.code) AS source_name,
                       ls.code AS subitem_code,
                       coalesce(ls.name, ls.display_name, ls.preferred_name, ls.code) AS subitem_name,
                       collect(DISTINCT {
                           code: li.code,
                           name: coalesce(li.name, li.display_name, li.preferred_name, li.code)
                       }) AS parent_lab_items
                ORDER BY source_type, source_code, subitem_code
                """,
            ),
            "differential_without_rule": run_list(
                tx,
                """
                MATCH (d:KGNode {entityType:'Disease'})-[:has_differential_diagnosis|differentiates_from]->
                      (x:KGNode {entityType:'DifferentialDiagnosis'})
                WHERE coalesce(x.status,'active') <> 'deprecated'
                  AND NOT (x)-[:has_differential_point|requires_exclusion_exam]->(:KGNode)
                RETURN d.code AS disease_code,
                       coalesce(d.name,d.display_name,d.preferred_name,d.code) AS disease_name,
                       x.code AS differential_code,
                       coalesce(x.name,x.display_name,x.preferred_name,x.code) AS differential_name
                ORDER BY disease_code, differential_code
                """,
            ),
            "parsed_category_summary": run_list(
                tx,
                """
                MATCH (d:KGNode {entityType:'Disease'})
                WHERE coalesce(d.status,'active') <> 'deprecated'
                OPTIONAL MATCH (cat:KGNode {entityType:'DiseaseCategory'})<-[:belongs_to_category]-(d)
                OPTIONAL MATCH (d)-[:has_definition]->(:KGNode {entityType:'Definition'})
                WITH d, cat, count(*) AS definition_count
                OPTIONAL MATCH (d)-[:has_exam_plan]->(:KGNode {entityType:'ExamPlan'})
                WITH d, cat, definition_count, count(*) AS exam_plan_count
                OPTIONAL MATCH (d)-[:has_treatment_plan]->(:KGNode {entityType:'TreatmentPlan'})
                WITH d, cat, definition_count, exam_plan_count, count(*) AS treatment_plan_count
                OPTIONAL MATCH (d)-[:has_standard_diagnosis]->(:KGNode {entityType:'StandardDiagnosis'})
                WITH d, cat, definition_count, exam_plan_count, treatment_plan_count, count(*) AS standard_diagnosis_count
                RETURN coalesce(
                       cat.name,
                       CASE
                         WHEN d.code STARTS WITH 'DIS-CARD-CAD-' THEN '冠心病'
                         WHEN d.code STARTS WITH 'DIS-CARD-CM-' THEN '心肌病'
                         WHEN d.code STARTS WITH 'DIS-CARD-HF-' THEN '心力衰竭'
                         WHEN d.code STARTS WITH 'DIS-CARD-ARR-' THEN '心律失常'
                         WHEN d.code STARTS WITH 'DIS-CARD-HT-' THEN '高血压'
                         WHEN d.code STARTS WITH 'DIS-CARD-VHD-' THEN '瓣膜病'
                         WHEN d.code STARTS WITH 'DIS-CARD-PAH-' THEN '肺动脉高压'
                         WHEN d.code STARTS WITH 'DIS-CARD-PACING-' THEN '起搏治疗相关疾病'
                         ELSE '未归类'
                       END
                     ) AS disease_category,
                       count(d) AS disease_count,
                       sum(CASE WHEN definition_count > 0 THEN 1 ELSE 0 END) AS with_definition,
                       sum(CASE WHEN exam_plan_count > 0 THEN 1 ELSE 0 END) AS with_exam_plan,
                       sum(CASE WHEN treatment_plan_count > 0 THEN 1 ELSE 0 END) AS with_treatment_plan,
                       sum(CASE WHEN standard_diagnosis_count > 0 THEN 1 ELSE 0 END) AS with_standard_diagnosis
                ORDER BY disease_category
                """,
            ),
            "process_residue": run_list(
                tx,
                """
                CALL {
                  MATCH (n:KGNode)
                  WHERE n.entityType IN ['SourceAdjudication','AuditFinding','CandidateNode','CandidateRelation']
                  RETURN n.entityType AS item, count(n) AS cnt
                  UNION ALL
                  MATCH ()-[r:has_source_adjudication|decides_recommendation]->()
                  RETURN type(r) AS item, count(r) AS cnt
                }
                RETURN item, cnt
                ORDER BY item
                """,
            ),
        }
    )


def repair_wrong_recommendation_endpoints(session: Any, now: str, batch_id: str) -> dict[str, Any]:
    def _write(tx: Any) -> dict[str, Any]:
        initial_unresolved = run_list(
            tx,
            """
            MATCH (src:KGNode)-[r:recommends_action]->(ls:KGNode {entityType:'LabSubitem'})
            WHERE src.entityType IN ['RecommendationStatement','ClinicalRule']
            OPTIONAL MATCH (li:KGNode {entityType:'LabItem'})-[:lab_item_has_subitem]->(ls)
            WITH src, r, ls, collect(DISTINCT li) AS parents
            WHERE size(parents) = 0
            RETURN src.entityType AS source_type,
                   src.code AS source_code,
                   coalesce(src.name,src.display_name,src.preferred_name,src.code) AS source_name,
                   ls.code AS subitem_code,
                   coalesce(ls.name,ls.display_name,ls.preferred_name,ls.code) AS subitem_name
            ORDER BY source_type, source_code, subitem_code
            """,
        )

        created_parent_lab_items = 0
        for item in initial_unresolved:
            # 国际标准化比值（INR）是凝血功能检查的检验细项，不是可直接下医嘱的检验项目。
            # 如果图谱缺少上级检验项目，补齐“凝血功能检查 -> 国际标准化比值”结构，再迁移推荐动作到上级项目。
            if item.get("subitem_name") == "国际标准化比值":
                existing_parent = run_list(
                    tx,
                    """
                    MATCH (li:KGNode {entityType:'LabItem'})
                    WHERE coalesce(li.name, li.display_name, li.preferred_name, '') IN
                          ['凝血功能检查','凝血功能','凝血四项','凝血功能测定','凝血试验']
                    RETURN li.code AS code
                    ORDER BY CASE coalesce(li.name, li.display_name, li.preferred_name, '')
                               WHEN '凝血功能检查' THEN 0
                               WHEN '凝血功能' THEN 1
                               ELSE 2
                             END
                    LIMIT 1
                    """,
                )
                parent_code = existing_parent[0]["code"] if existing_parent else "LABITEM-CARD-COAGULATION-FUNCTION"
                run_list(
                    tx,
                    """
                    MATCH (ls:KGNode {entityType:'LabSubitem', code:$subitem_code})
                    MERGE (li:KGNode:LabItem {code:$parent_code})
                    ON CREATE SET li.entityType='LabItem',
                                  li.type_label='LabItem',
                                  li.name='凝血功能检查',
                                  li.display_name='凝血功能检查',
                                  li.preferred_name='凝血功能检查',
                                  li.aliases=['凝血功能','凝血四项','凝血功能测定','凝血试验'],
                                  li.dictionary_validation_status='pending_registration',
                                  li.clinical_use_status='review_ready',
                                  li.source_table='K_KG_DICT_CHANGE_REVIEW',
                                  li.status='active',
                                  li.created_at=$now,
                                  li.repair_batch=$batch_id,
                                  li.repair_reason='国际标准化比值为检验细项，需补齐上级检验项目后才能作为正式推荐动作入口。'
                    SET li.updated_at=$now
                    MERGE (li)-[r:lab_item_has_subitem]->(ls)
                    SET r.status='active',
                        r.repair_batch=$batch_id,
                        r.repair_time=$now,
                        r.repair_reason='补齐凝血功能检查与国际标准化比值的项目-细项关系。'
                    RETURN li.code AS code
                    """,
                    subitem_code=item["subitem_code"],
                    parent_code=parent_code,
                    now=now,
                    batch_id=batch_id,
                )
                if not existing_parent:
                    created_parent_lab_items += 1

        rows = run_list(
            tx,
            """
            MATCH (src:KGNode)-[old:recommends_action]->(ls:KGNode {entityType:'LabSubitem'})
            WHERE src.entityType IN ['RecommendationStatement','ClinicalRule']
            MATCH (li:KGNode {entityType:'LabItem'})-[:lab_item_has_subitem]->(ls)
            WITH src, old, ls, head(collect(DISTINCT li)) AS li
            MERGE (src)-[new:recommends_action]->(li)
            SET new += properties(old),
                new.status = coalesce(new.status, 'active'),
                new.repair_batch = $batch_id,
                new.repair_time = $now,
                new.repair_reason = '正式推荐动作不得直接落到检验细项；迁移到上级检验项目，细项通过 LabItem->LabSubitem 保留。',
                new.migrated_from_lab_subitem_code = ls.code,
                new.migrated_from_lab_subitem_name = coalesce(ls.name, ls.display_name, ls.preferred_name, ls.code)
            WITH old, src, li, ls
            DELETE old
            RETURN count(*) AS migrated_count
            """,
            now=now,
            batch_id=batch_id,
        )
        final_unresolved = run_list(
            tx,
            """
            MATCH (src:KGNode)-[r:recommends_action]->(ls:KGNode {entityType:'LabSubitem'})
            WHERE src.entityType IN ['RecommendationStatement','ClinicalRule']
            OPTIONAL MATCH (li:KGNode {entityType:'LabItem'})-[:lab_item_has_subitem]->(ls)
            WITH src, r, ls, collect(DISTINCT li) AS parents
            WHERE size(parents) = 0
            RETURN src.entityType AS source_type,
                   src.code AS source_code,
                   coalesce(src.name,src.display_name,src.preferred_name,src.code) AS source_name,
                   ls.code AS subitem_code,
                   coalesce(ls.name,ls.display_name,ls.preferred_name,ls.code) AS subitem_name
            ORDER BY source_type, source_code, subitem_code
            """,
        )
        return {
            "migrated": rows[0]["migrated_count"],
            "created_parent_lab_items": created_parent_lab_items,
            "initial_unresolved": initial_unresolved,
            "unresolved": final_unresolved,
            "status": "blocked" if final_unresolved else "ok",
        }

    return session.execute_write(_write)


def repair_differential_rule_gate(session: Any, now: str, batch_id: str) -> dict[str, Any]:
    specs = load_differential_specs()

    def _write(tx: Any) -> dict[str, Any]:
        bridge = run_list(
            tx,
            """
            MATCH (ddx:KGNode {entityType:'DifferentialDiagnosis'})-[old:has_differential_rule]->
                  (rule:KGNode {entityType:'ClinicalRule'})
            WHERE NOT (ddx)-[:has_differential_point]->(rule)
            MERGE (ddx)-[new:has_differential_point]->(rule)
            SET new.status='active',
                new.repair_batch=$batch_id,
                new.repair_time=$now,
                new.repair_reason='兼容既有 has_differential_rule，补齐硬闸门识别的 has_differential_point。'
            RETURN count(new) AS created
            """,
            now=now,
            batch_id=batch_id,
        )[0]["created"]

        remaining = run_list(
            tx,
            """
            MATCH (d:KGNode {entityType:'Disease'})-[:has_differential_diagnosis|differentiates_from]->
                  (x:KGNode {entityType:'DifferentialDiagnosis'})
            WHERE coalesce(x.status,'active') <> 'deprecated'
              AND NOT (x)-[:has_differential_point|requires_exclusion_exam]->(:KGNode)
            RETURN d.code AS disease_code, x.code AS differential_code
            ORDER BY disease_code, differential_code
            """,
        )

        created_from_specs = 0
        blocked: list[dict[str, Any]] = []
        for row in remaining:
            disease_code = row["disease_code"]
            differential_code = row["differential_code"]
            spec = specs.get(disease_code)
            if not spec or spec.get("node_code") != differential_code:
                blocked.append(
                    {
                        "disease_code": disease_code,
                        "differential_code": differential_code,
                        "reason": "样板规则中没有对应补充规范，不能自动生成。",
                    }
                )
                continue

            precheck = run_list(
                tx,
                """
                MATCH (d:KGNode {entityType:'Disease', code:$disease_code})
                OPTIONAL MATCH (ev:KGNode {entityType:'Evidence'})
                WHERE ev.code=$evidence_id OR ev.evidence_id=$evidence_id OR ev.id=$evidence_id
                RETURN count(DISTINCT d) AS disease_count, count(DISTINCT ev) AS evidence_count
                """,
                disease_code=disease_code,
                evidence_id=spec["evidence_id"],
            )[0]
            if precheck["disease_count"] == 0 or precheck["evidence_count"] == 0:
                blocked.append(
                    {
                        "disease_code": disease_code,
                        "differential_code": differential_code,
                        "reason": "缺疾病节点或原文证据节点，不能自动生成鉴别规则。",
                        "disease_count": precheck["disease_count"],
                        "evidence_count": precheck["evidence_count"],
                    }
                )
                continue

            rows = run_list(
                tx,
                """
                MATCH (d:KGNode {entityType:'Disease', code:$disease_code})
                MATCH (ev:KGNode {entityType:'Evidence'})
                WHERE ev.code=$evidence_id OR ev.evidence_id=$evidence_id OR ev.id=$evidence_id
                MERGE (ddx:KGNode:DifferentialDiagnosis {code:$node_code})
                SET ddx.entityType='DifferentialDiagnosis',
                    ddx.type_label='DifferentialDiagnosis',
                    ddx.name=$name,
                    ddx.display_name=$name,
                    ddx.preferred_name=$name,
                    ddx.status='active',
                    ddx.differential_targets=$differential_targets,
                    ddx.updated_at=$now,
                    ddx.repair_batch=$batch_id
                MERGE (rule:KGNode:ClinicalRule {code:$rule_code})
                SET rule.entityType='ClinicalRule',
                    rule.type_label='ClinicalRule',
                    rule.name=$name,
                    rule.display_name=$name,
                    rule.preferred_name=$name,
                    rule.rule_text=$rule_text,
                    rule.description=$rule_text,
                    rule.status='active',
                    rule.updated_at=$now,
                    rule.repair_batch=$batch_id
                MERGE (d)-[:has_differential_diagnosis]->(ddx)
                MERGE (ddx)-[:has_differential_rule]->(rule)
                MERGE (ddx)-[:has_differential_point]->(rule)
                MERGE (rule)-[:supported_by_evidence]->(ev)
                RETURN count(rule) AS cnt
                """,
                disease_code=disease_code,
                node_code=spec["node_code"],
                rule_code=spec["rule_code"],
                name=spec["name"],
                rule_text=spec["rule_text"],
                differential_targets=spec["differential_targets"],
                evidence_id=spec["evidence_id"],
                now=now,
                batch_id=batch_id,
            )
            created_from_specs += rows[0]["cnt"]

        return {
            "bridged_existing_rules": bridge,
            "created_from_specs": created_from_specs,
            "blocked": blocked,
            "status": "blocked" if blocked else "ok",
        }

    return session.execute_write(_write)


def write_report(out_dir: Path, before: dict[str, Any], write_result: dict[str, Any], after: dict[str, Any]) -> None:
    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "before": before,
        "write_result": write_result,
        "after": after,
    }
    (out_dir / "14_已解析疾病扩展收口执行结果.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    wrong_before = len(before["wrong_recommendation_to_lab_subitem"])
    wrong_after = len(after["wrong_recommendation_to_lab_subitem"])
    ddx_before = len(before["differential_without_rule"])
    ddx_after = len(after["differential_without_rule"])
    md = [
        "# 已解析疾病扩展收口执行结果",
        "",
        f"- 生成时间：{result['generated_at']}",
        f"- 写库批次：{write_result['batch_id']}",
        "",
        "## 1. 本轮处理范围",
        "",
        "本轮不是只处理 AMI。脚本按全库 Disease 扫描，覆盖已入库的冠心病、心肌病、心力衰竭、心律失常、高血压、瓣膜病、肺动脉高压、起搏治疗相关疾病等已解析/已入库疾病节点。",
        "",
        "## 2. 修复结果",
        "",
        f"- 推荐动作误连检验细项：{wrong_before} → {wrong_after}",
        f"- 鉴别诊断无规则：{ddx_before} → {ddx_after}",
        f"- 迁移到上级检验项目的推荐动作关系：{write_result['recommendation_endpoint_repair'].get('migrated', 0)}",
        f"- 补齐既有鉴别规则识别关系：{write_result['differential_rule_repair'].get('bridged_existing_rules', 0)}",
        f"- 从样板规范补建鉴别规则：{write_result['differential_rule_repair'].get('created_from_specs', 0)}",
        "",
        "## 3. 阻断",
        "",
    ]
    blocks = write_result["recommendation_endpoint_repair"].get("unresolved", []) + write_result[
        "differential_rule_repair"
    ].get("blocked", [])
    if blocks:
        md.append("仍有阻断项，见 JSON 明细。")
    else:
        md.append("无阻断项。")
    md.extend(["", "## 4. 已解析大类概况", ""])
    md.append("| 疾病大类 | 疾病数 | 有定义 | 有辅助检查方案 | 有治疗方案 | 有标准诊断 |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for row in after["parsed_category_summary"]:
        md.append(
            f"| {row['disease_category']} | {row['disease_count']} | {row['with_definition']} | "
            f"{row['with_exam_plan']} | {row['with_treatment_plan']} | {row['with_standard_diagnosis']} |"
        )
    (out_dir / "14_已解析疾病扩展收口执行报告.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="已解析疾病扩展收口：修复正式推荐终点和鉴别规则识别关系")
    parser.add_argument("--connection-file", type=Path, default=DEFAULT_CONNECTION_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cfg = read_graph_connection(args.connection_file)
    batch_id = "20260729-已解析疾病扩展收口"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with GraphDatabase.driver(cfg["uri"], auth=(cfg["username"], cfg["password"])) as driver:
        with driver.session() as session:
            before = collect_audit(session)
            write_result: dict[str, Any] = {
                "batch_id": batch_id,
                "apply": args.apply,
                "recommendation_endpoint_repair": {"migrated": 0, "unresolved": [], "status": "not_applied"},
                "differential_rule_repair": {
                    "bridged_existing_rules": 0,
                    "created_from_specs": 0,
                    "blocked": [],
                    "status": "not_applied",
                },
            }
            if args.apply:
                write_result["recommendation_endpoint_repair"] = repair_wrong_recommendation_endpoints(
                    session, now, batch_id
                )
                write_result["differential_rule_repair"] = repair_differential_rule_gate(session, now, batch_id)
            after = collect_audit(session)

    write_report(args.output_dir, before, write_result, after)
    print(json.dumps({"before": {
        "wrong_recommendation_to_lab_subitem": len(before["wrong_recommendation_to_lab_subitem"]),
        "differential_without_rule": len(before["differential_without_rule"]),
    }, "write_result": write_result, "after": {
        "wrong_recommendation_to_lab_subitem": len(after["wrong_recommendation_to_lab_subitem"]),
        "differential_without_rule": len(after["differential_without_rule"]),
    }}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
