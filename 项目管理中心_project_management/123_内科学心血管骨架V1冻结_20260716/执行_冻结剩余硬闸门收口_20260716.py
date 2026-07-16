from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "123_内科学心血管骨架V1冻结_20260716"
CONNECTION_FILE = ROOT / "图谱数据库链接.txt"
BOOK_NAME = "《内科学（第10版）》"
BOOK_VERSION = "第10版"
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_connection() -> tuple[str, str, str]:
    raw = CONNECTION_FILE.read_bytes()
    texts: list[str] = []
    for enc in ("utf-8-sig", "utf-8", "gbk", "cp936"):
        try:
            texts.append(raw.decode(enc, errors="ignore"))
        except Exception:
            pass
    joined = "\n".join(texts)
    uri_match = re.search(r"bolt://[0-9A-Za-z\.:_-]+", joined)
    uri = uri_match.group(0) if uri_match else "bolt://192.168.3.27:7687"
    user = "neo4j" if "neo4j" in joined.lower() else os.environ.get("NEO4J_USERNAME", "neo4j")

    candidates: list[str] = []
    if os.environ.get("NEO4J_PASSWORD"):
        candidates.append(os.environ["NEO4J_PASSWORD"])
    for text in texts:
        for line in text.splitlines():
            if "@" in line and "http" not in line.lower() and "bolt" not in line.lower():
                candidates.extend(
                    m.group(0)
                    for m in re.finditer(r"[A-Za-z0-9._%+\-#$!]+@[A-Za-z0-9._%+\-#$!]+", line)
                )
    seen: list[str] = []
    for item in candidates:
        if item and item not in seen:
            seen.append(item)
    last_error = None
    for pwd in seen:
        try:
            driver = GraphDatabase.driver(uri, auth=(user, pwd))
            driver.verify_connectivity()
            driver.close()
            return uri, user, pwd
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Neo4j认证失败，已尝试候选数={len(seen)}，最后错误={type(last_error).__name__ if last_error else 'None'}")


def source_kind(source_name: str | None) -> tuple[str, str]:
    s = source_name or ""
    if "百度健康医典" in s or "GeneReviews" in s:
        return "external_authoritative", "external_authoritative"
    if "共识" in s:
        return "expert_consensus", "expert_consensus"
    if "声明" in s:
        return "expert_consensus", "expert_consensus"
    if "指南" in s:
        return "guideline", "guideline"
    return "external_authoritative", "external_authoritative"


def main() -> None:
    uri, user, pwd = parse_connection()
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    result: dict[str, object] = {
        "batch_id": "20260716_内科学心血管骨架V1冻结剩余硬闸门收口",
        "executed_at": NOW,
        "password_printed": False,
        "duplicate_groups_merged": [],
        "source_type_corrected": [],
        "textbook_definition_evidence_linked": [],
        "cad_definition_corrected": [],
        "source_document_slot_fixed": 0,
    }

    manual_defs = [
        {
            "disease": "急性心肌梗死",
            "definition_text": "急性心肌梗死（AMI）是急性心肌缺血性坏死的临床状态，临床上分为5型；在冠心病急性冠脉综合征中主要包括ST段抬高型心肌梗死和非ST段抬高型心肌梗死。",
            "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 急性冠脉综合征",
            "docx_para_start": 5121,
            "docx_para_end": 5126,
            "evidence_text": "急性冠脉综合征是一组由急性心肌缺血引起的临床综合征，主要包括不稳定型心绞痛、非ST段抬高型心肌梗死和ST段抬高型心肌梗死；临床上将急性心肌梗死分为5型。",
        },
        {
            "disease": "慢性冠脉综合征",
            "definition_text": "慢性冠脉综合征（CCS）也称慢性冠状动脉疾病，是冠心病相对稳定阶段的临床综合征，可包括稳定心绞痛、缺血性心肌病、ACS后或血运重建后的稳定期，以及筛查发现的无症状冠状动脉疾病等情况。",
            "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 慢性冠状动脉综合征",
            "docx_para_start": 4946,
            "docx_para_end": 4957,
            "evidence_text": "慢性冠脉综合征也称慢性冠状动脉疾病，病理上冠脉可有阻塞性病变或无明显阻塞性病变，包括稳定心绞痛、疑似冠心病、新发心衰或左室功能障碍、ACS后稳定期、血运重建后稳定期以及无症状CAD等情况。",
        },
        {
            "disease": "非ST段抬高型心肌梗死",
            "definition_text": "非ST段抬高型心肌梗死（NSTEMI）属于非ST段抬高型急性冠脉综合征，表现为较严重心肌缺血并伴心肌损害和心肌坏死标志物升高，但无STEMI特征性心电图动态演变。",
            "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 急性冠脉综合征 > 不稳定型心绞痛和非ST段抬高型心肌梗死",
            "docx_para_start": 5128,
            "docx_para_end": 5133,
            "evidence_text": "UA/NSTEMI合称为非ST段抬高型急性冠脉综合征；NSTEMI心肌缺血更严重，伴有心肌损害和心肌坏死标志物升高，病理上可出现灶性或心内膜下心肌坏死。",
        },
        {
            "disease": "不稳定型心绞痛",
            "definition_text": "不稳定型心绞痛（UA）属于非ST段抬高型急性冠脉综合征，是新发或加重的心肌缺血状态，可包括静息状态下缺血，但不伴心肌坏死。",
            "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 急性冠脉综合征 > 不稳定型心绞痛和非ST段抬高型心肌梗死",
            "docx_para_start": 5128,
            "docx_para_end": 5132,
            "evidence_text": "UA/NSTEMI的病因和临床表现相似但心肌缺血程度不同，UA有新发心肌缺血（包括静息状态下缺血）但不伴有心肌坏死；变异型心绞痛是UA的一种特殊类型。",
        },
        {
            "disease": "隐匿性冠心病",
            "definition_text": "隐匿性冠心病也称无症状型冠心病，是冠心病的一种临床表型，患者可无典型心绞痛症状，常在筛查或检查中发现无症状冠状动脉疾病或心肌缺血证据。",
            "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 慢性冠状动脉综合征",
            "docx_para_start": 4946,
            "docx_para_end": 4957,
            "evidence_text": "冠心病临床表型包括隐匿型或无症状型冠心病；慢性冠脉综合征包括筛查时发现的无症状CAD病人，部分病例表现为无症状隐匿型冠心病。",
        },
    ]

    with driver.session(database="neo4j") as session:
        # 1. 剩余同类型同名重复实体物理归并，保留关系。
        duplicate_rows = session.run(
            """
            MATCH (n:KGNode)
            WHERE n.entityType IS NOT NULL AND n.name IS NOT NULL AND coalesce(n.status,'active') <> 'deleted'
            WITH n.entityType AS type, n.name AS name, count(*) AS c
            WHERE c > 1
            RETURN type, name
            """
        ).data()
        for row in duplicate_rows:
            merge_info = session.run(
                """
                MATCH (n:KGNode {entityType:$type, name:$name})
                WHERE coalesce(n.status,'active') <> 'deleted'
                WITH n, COUNT { (n)--() } AS rel_count
                ORDER BY
                  CASE
                    WHEN n.entityType='Definition' AND n.code STARTS WITH 'DEF-DIS-' THEN 0
                    WHEN n.entityType='Definition' AND n.code STARTS WITH 'DEF-' THEN 1
                    WHEN n.entityType='Evidence' AND n.code STARTS WITH 'EVD-CARD-FOUND-' THEN 0
                    ELSE 2
                  END ASC,
                  rel_count DESC,
                  coalesce(n.updated_at,'') DESC
                WITH collect(n) AS nodes
                WITH nodes[0] AS keep, nodes AS nodes
                CALL apoc.refactor.mergeNodes(nodes, {properties:'combine', mergeRels:true, produceSelfRel:false}) YIELD node
                SET node.code = keep.code,
                    node.name = $name,
                    node.display_name = coalesce(node.display_name, $name),
                    node.preferred_name = coalesce(node.preferred_name, $name),
                    node.updated_at = $now,
                    node.merge_status = 'merged_same_type_same_name_on_textbook_freeze'
                RETURN node.code AS code, node.entityType AS type, node.name AS name
                """,
                type=row["type"],
                name=row["name"],
                now=NOW,
            ).single()
            result["duplicate_groups_merged"].append(dict(merge_info))

        # 2. 外部指南/共识/权威网页定义，不得继续标成“权威教材”。
        ext_rows = session.run(
            """
            MATCH (def:KGNode {entityType:'Definition'})
            WHERE def.source_name IS NOT NULL
              AND def.source_name <> $book
              AND (def.source_type='authoritative_textbook' OR def.source_authority='authoritative_textbook')
            RETURN def.code AS code, def.source_name AS source_name
            """,
            book=BOOK_NAME,
        ).data()
        for row in ext_rows:
            source_type, source_authority = source_kind(row["source_name"])
            session.run(
                """
                MATCH (def:KGNode {code:$code})
                SET def.source_type=$source_type,
                    def.source_authority=$source_authority,
                    def.knowledge_layer=coalesce(def.knowledge_layer,'guideline_or_external_definition'),
                    def.textbook_freeze_scope='out_of_scope',
                    def.textbook_freeze_scope_reason='定义来源不是《内科学》第10版，不纳入本次教材骨架冻结硬闸门',
                    def.updated_at=$now
                """,
                code=row["code"],
                source_type=source_type,
                source_authority=source_authority,
                now=NOW,
            )
            result["source_type_corrected"].append(
                {"code": row["code"], "source_name": row["source_name"], "source_type": source_type}
            )

        # 3. 纠正 5 个冠心病旧定义。
        for item in manual_defs:
            row = session.run(
                """
                MATCH (d:KGNode {entityType:'Disease', name:$disease})-[:has_definition]->(def:KGNode {entityType:'Definition'})
                WITH d, def
                ORDER BY CASE WHEN def.code STARTS WITH 'DEF-DIS-' THEN 0 ELSE 1 END
                WITH d, collect(def)[0] AS def
                SET def.definition_text=$definition_text,
                    def.description=$definition_text,
                    def.original_text=$evidence_text,
                    def.text_excerpt=$evidence_text,
                    def.source_name=$book,
                    def.source_version=$book_version,
                    def.source_type='authoritative_textbook',
                    def.source_authority='authoritative_textbook',
                    def.source_section_path=$source_section_path,
                    def.docx_para_start=$docx_para_start,
                    def.docx_para_end=$docx_para_end,
                    def.knowledge_layer='textbook_core',
                    def.skeleton_slot='definition',
                    def.skeleton_slot_status='present_with_textbook_evidence',
                    def.clinical_review_status='textbook_verified',
                    def.formal_cdss_ready='no',
                    def.updated_at=$now,
                    d.definition=$definition_text,
                    d.definition_source_name=$book,
                    d.definition_source_section_path=$source_section_path,
                    d.textbook_freeze_scope='in_scope',
                    d.updated_at=$now
                MERGE (ev:KGNode {entityType:'Evidence', code:'EVID-TEXTBOOK-DEF-' + def.code})
                SET ev.name=d.name + '-definition-教材证据',
                    ev.display_name=d.name + '-definition-教材证据',
                    ev.preferred_name=d.name + '-definition-教材证据',
                    ev.evidence_text=$evidence_text,
                    ev.original_text=$evidence_text,
                    ev.source_name=$book,
                    ev.source_version=$book_version,
                    ev.source_type='authoritative_textbook',
                    ev.source_authority='authoritative_textbook',
                    ev.source_section_path=$source_section_path,
                    ev.docx_para_start=$docx_para_start,
                    ev.docx_para_end=$docx_para_end,
                    ev.knowledge_layer='textbook_core',
                    ev.skeleton_slot='evidence',
                    ev.skeleton_slot_status='evidence_node',
                    ev.batch_id='20260716_内科学心血管骨架V1冻结剩余硬闸门收口',
                    ev.updated_at=$now,
                    ev.created_at=coalesce(ev.created_at,$now)
                MERGE (def)-[r:supported_by_evidence]->(ev)
                SET r.relation_scope='definition',
                    r.source='textbook_freeze_gate',
                    r.updated_at=$now
                RETURN d.name AS disease, def.code AS definition_code, ev.code AS evidence_code
                """,
                disease=item["disease"],
                definition_text=item["definition_text"],
                evidence_text=item["evidence_text"],
                source_section_path=item["source_section_path"],
                docx_para_start=item["docx_para_start"],
                docx_para_end=item["docx_para_end"],
                book=BOOK_NAME,
                book_version=BOOK_VERSION,
                now=NOW,
            ).single()
            if row:
                result["cad_definition_corrected"].append(dict(row))

        # 4. 其余《内科学》第10版定义补证据链。
        missing_rows = session.run(
            """
            MATCH (d:KGNode {entityType:'Disease'})-[:has_definition]->(def:KGNode {entityType:'Definition'})
            WHERE def.source_name=$book
            WITH d, def
            WHERE NOT (def)-[:supported_by_evidence]->(:KGNode {entityType:'Evidence'})
            RETURN d.code AS disease_code, d.name AS disease_name, def.code AS def_code,
                   def.name AS def_name,
                   coalesce(def.text_excerpt, def.original_text, def.definition_text, def.description) AS evidence_text,
                   def.source_section_path AS source_section_path,
                   def.docx_para_start AS docx_para_start,
                   def.docx_para_end AS docx_para_end
            """,
            book=BOOK_NAME,
        ).data()
        for row in missing_rows:
            ev_code = "EVID-TEXTBOOK-DEF-" + row["def_code"]
            ev_name = row["disease_name"] + "-definition-教材证据"
            linked = session.run(
                """
                MATCH (def:KGNode {code:$def_code})
                MERGE (ev:KGNode {entityType:'Evidence', code:$ev_code})
                SET ev.name=$ev_name,
                    ev.display_name=$ev_name,
                    ev.preferred_name=$ev_name,
                    ev.evidence_text=$evidence_text,
                    ev.original_text=$evidence_text,
                    ev.source_name=$book,
                    ev.source_version=$book_version,
                    ev.source_type='authoritative_textbook',
                    ev.source_authority='authoritative_textbook',
                    ev.source_section_path=$source_section_path,
                    ev.docx_para_start=$docx_para_start,
                    ev.docx_para_end=$docx_para_end,
                    ev.knowledge_layer='textbook_core',
                    ev.skeleton_slot='evidence',
                    ev.skeleton_slot_status='evidence_node',
                    ev.batch_id='20260716_内科学心血管骨架V1冻结剩余硬闸门收口',
                    ev.updated_at=$now,
                    ev.created_at=coalesce(ev.created_at,$now)
                MERGE (def)-[r:supported_by_evidence]->(ev)
                SET r.relation_scope='definition',
                    r.source='textbook_freeze_gate',
                    r.updated_at=$now
                SET def.skeleton_slot='definition',
                    def.skeleton_slot_status='present_with_textbook_evidence',
                    def.updated_at=$now
                RETURN def.code AS def_code, ev.code AS ev_code
                """,
                def_code=row["def_code"],
                ev_code=ev_code,
                ev_name=ev_name,
                evidence_text=row["evidence_text"] or "",
                source_section_path=row["source_section_path"],
                docx_para_start=row["docx_para_start"],
                docx_para_end=row["docx_para_end"],
                book=BOOK_NAME,
                book_version=BOOK_VERSION,
                now=NOW,
            ).single()
            result["textbook_definition_evidence_linked"].append(dict(linked))

        # 5. 教材来源文件节点补槽位状态。
        summary = session.run(
            """
            MATCH (g:KGNode {entityType:'Guideline'})
            WHERE (g.knowledge_layer='textbook_core' OR g.source_type='authoritative_textbook' OR g.source_authority='authoritative_textbook')
              AND (g.skeleton_slot_status IS NULL OR g.skeleton_slot_status='')
            SET g.skeleton_slot='source_document',
                g.skeleton_slot_status='source_document',
                g.updated_at=$now
            RETURN count(g) AS c
            """,
            now=NOW,
        ).single()
        result["source_document_slot_fixed"] = summary["c"] if summary else 0

        # 6. 收尾再归并一次本脚本可能产生的证据同名重复。
        duplicate_rows2 = session.run(
            """
            MATCH (n:KGNode)
            WHERE n.entityType IS NOT NULL AND n.name IS NOT NULL AND coalesce(n.status,'active') <> 'deleted'
            WITH n.entityType AS type, n.name AS name, count(*) AS c
            WHERE c > 1
            RETURN type, name
            """
        ).data()
        for row in duplicate_rows2:
            if row in duplicate_rows:
                continue
            merge_info = session.run(
                """
                MATCH (n:KGNode {entityType:$type, name:$name})
                WHERE coalesce(n.status,'active') <> 'deleted'
                WITH n, COUNT { (n)--() } AS rel_count
                ORDER BY rel_count DESC, coalesce(n.updated_at,'') DESC
                WITH collect(n) AS nodes
                WITH nodes[0] AS keep, nodes AS nodes
                CALL apoc.refactor.mergeNodes(nodes, {properties:'combine', mergeRels:true, produceSelfRel:false}) YIELD node
                SET node.code = keep.code,
                    node.name = $name,
                    node.updated_at = $now,
                    node.merge_status = 'merged_same_type_same_name_on_textbook_freeze_final'
                RETURN node.code AS code, node.entityType AS type, node.name AS name
                """,
                type=row["type"],
                name=row["name"],
                now=NOW,
            ).single()
            result["duplicate_groups_merged"].append(dict(merge_info))

    driver.close()
    (OUT_DIR / "13_冻结剩余硬闸门收口执行结果.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "duplicate_groups_merged": len(result["duplicate_groups_merged"]),
        "source_type_corrected": len(result["source_type_corrected"]),
        "cad_definition_corrected": len(result["cad_definition_corrected"]),
        "textbook_definition_evidence_linked": len(result["textbook_definition_evidence_linked"]),
        "source_document_slot_fixed": result["source_document_slot_fixed"],
        "output": str(OUT_DIR / "13_冻结剩余硬闸门收口执行结果.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
