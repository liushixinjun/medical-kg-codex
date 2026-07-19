from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "公共执行层_kg_pipeline"))

from CDSS双口径安全审计 import read_db_config  # noqa: E402


BATCH_ID = "20260719_CDSS双口径缺口治理"
OUTPUT_DIR = Path(__file__).resolve().parent
BACKUP_PATH = OUTPUT_DIR / "写库前回滚数据.json"
PREFLIGHT_PATH = OUTPUT_DIR / "写库前检查结果.json"
RESULT_PATH = OUTPUT_DIR / "写库结果.json"

FORMAL_ADJUDICATION_CODE = "SRCADJ-CARD-BULK-A802B56DC69C9AAD"
FORMAL_OLD_EVIDENCE_CODE = "EVD-CARD-DEEP-2E78252BA488DA"
FORMAL_CANONICAL_EVIDENCE_CODE = "EVD-CARD-DEEP-644CBD55A70B89"

BAD_PLAN_PAIRS = [
    {
        "disease_code": "DIS-CARD-CM-GENERAL",
        "plan_code": "PLAN-CARD-1345BFF7172A",
        "reason": "宽口径空方案且证据内容与心肌病治疗不匹配",
    },
    {
        "disease_code": "DIS-CARD-PERICARD-CONSTRICTIVE",
        "plan_code": "CARD-SKELETON-FULL-20260709-TREATMENTPLAN-542F49CC6D03259B",
        "reason": "病因文本误标为治疗方案",
    },
    {
        "disease_code": "DIS-CARD-PERICARD-CONSTRICTIVE",
        "plan_code": "CARD-SKELETON-FULL-20260709-TREATMENTPLAN-D7A188C9B6C12EF5",
        "reason": "临床表现文本误标为治疗方案",
    },
    {
        "disease_code": "DIS-CARD-PERICARD-EFFUSION",
        "plan_code": "CARD-SKELETON-FULL-20260709-TREATMENTPLAN-DAA970FF15656D0D",
        "reason": "病因文本误标为治疗方案",
    },
]

POLLUTED_DIFFERENTIAL_CODES = [
    "DDX-CARD-3D72C415E1F8",
    "DDX-CARD-D9E23DFD1FF7",
]

ORPHAN_MEDICATION_CODES = [
    "CARD-SKELETON-FULL-20260709-MEDICATION-2033F78ED5E94FAB",
    "CARD-SKELETON-FULL-20260709-MEDICATION-67B8149DCE7481E3",
]


DEFINITION_ROWS = [
    ("DIS-CARD-CM-GENERAL", "心肌病", "心肌病是一组病因和表型异质性高的心肌疾病，其心肌结构和/或功能异常不能用前、后负荷增加或心肌缺血等其他疾病充分解释。", "EVD-CARD-DEEP-6DA10DC6E04EF5"),
    ("DIS-CARD-MYOCARDITIS", "心肌炎", "心肌炎是指感染和非感染性心肌炎性疾病。", "EVD-F060803C73AED876F112-MYOCARDITIS"),
    ("DIS-CARD-PH", "肺动脉高压", "肺动脉高压是由多种原因引起的肺动脉压力异常升高的一种病理生理状态。", "EVD-F8B5D618A7E22D61FF71-PH"),
    ("DIS-CARD-FULMINANT-MYOCARDITIS", "暴发性心肌炎", "暴发性心肌炎是急性弥漫性炎症性心肌疾病，其特点是起病急骤、病情进展极其迅速、死亡风险极高。", "EVD-AD94B548D652EB99B7A1-MYOCARDITIS"),
    ("DIS-CARD-PERICARD-ACUTE", "急性心包炎", "急性心包炎是心包脏层和壁层的急性炎症性疾病。", "EVD-CARD-FOUND-00432"),
    ("DIS-CARD-PERICARD-CONSTRICTIVE", "缩窄性心包炎", "缩窄性心包炎是心脏被致密增厚的纤维化或钙化心包包围，使心室舒张期充盈受限并产生循环障碍的疾病，病程多为慢性。", "EVD-E854F8179FBE768E2BC6-PERICARDITIS"),
    ("DIS-CARD-PH-CHD", "先天性心脏病相关肺动脉高压", "先天性心脏病相关肺动脉高压是由体-肺分流型先天性心脏病所引起的肺动脉压力升高。", "EVD-39F2743BAF1BBBBB950B-CHD"),
    ("DIS-CARD-PH-CTD", "结缔组织病相关肺动脉高压", "结缔组织病相关肺动脉高压是以结缔组织病为基础疾病、由肺动脉病变导致的动脉性肺动脉高压。", "EVD-1887C1922DC3078E9313-CTD"),
    ("DIS-CARD-PH-CTEPH", "慢性血栓栓塞性肺动脉高压", "慢性血栓栓塞性肺动脉高压是肺动脉反复血栓栓塞或栓塞后血栓不溶、机化，继发肺血管重塑、肺血管阻力和肺动脉压力进行性升高的疾病。", "EVD-CARD-FULLBOOK-ED25EC0721AF32"),
    ("DIS-CARD-PH-HPAH", "遗传性肺动脉高压", "遗传性肺动脉高压是存在明确遗传致病因素或家族聚集证据的动脉性肺动脉高压。", "EVD-61195B7D213086F2BCFB-HPAH"),
    ("DIS-CARD-PH-IPAH", "特发性肺动脉高压", "特发性肺动脉高压是一种病因不明的肺动脉高压，过去称为原发性肺动脉高压。", "EVD-D75BD8AEEA6611D50537-IPAH"),
    ("DIS-CARD-PH-PAH", "动脉性肺动脉高压", "动脉性肺动脉高压是肺动脉、主要是肺小动脉病变引起肺血管阻力和肺动脉压力升高，而左心充盈压正常的一类肺高压。", "EVD-31A4791BF118D0054FA5-PAH"),
    ("DIS-CARD-AAA", "腹主动脉瘤", "腹主动脉瘤是腹主动脉局部或弥漫性永久扩张；成人腹主动脉最大直径超过30 mm时可临床诊断。", "EVD-CBE4DDCAC81A393259DC-AAA"),
    ("DIS-CARD-AORTA-ANEURYSM", "主动脉瘤", "主动脉瘤是主动脉局部或弥漫性永久性扩张形成的主动脉疾病。", "EVD-CBE4DDCAC81A393259DC-AAA"),
    ("DIS-CARD-AORTIC-DISSECTION", "主动脉夹层", "主动脉夹层是血液经主动脉内膜破口进入中层并沿血管长轴延伸，形成主动脉真假两腔的疾病。", "EVD-CARD-DEEP-8D2D41FF9B91E9"),
    ("DIS-CARD-CHD", "先天性心脏病", "先天性心脏病是胎儿期心脏或大血管发育异常造成、出生时已存在的心血管结构或连接异常。", "EVD-5C7B9495A881422638F6-CHD"),
    ("DIS-CARD-CHD-EBSTEIN", "三尖瓣下移畸形", "先天性三尖瓣下移畸形又称Ebstein畸形，是三尖瓣附着部位异常并向右心室心尖方向移位的少见先天性心脏病。", "EVD-CARD-FOUND-00360"),
    ("DIS-CARD-DYSLIPIDEMIA", "血脂异常", "血脂异常通常指血清胆固醇、甘油三酯、低密度脂蛋白胆固醇水平升高，和/或高密度脂蛋白胆固醇水平降低。", "EVD-0B68C8A888D1B4357741-DYSLIPIDEMIA"),
    ("DIS-CARD-FH", "家族性高胆固醇血症", "家族性高胆固醇血症是由脂蛋白代谢相关致病基因变异导致、以低密度脂蛋白胆固醇显著升高和早发动脉粥样硬化性心血管病风险增高为特征的遗传性疾病。", "EVD-EBB07BC0698265300441-FH"),
    ("DIS-CARD-HTN-PHEO", "嗜铬细胞瘤和副神经节瘤", "嗜铬细胞瘤和副神经节瘤起源于肾上腺髓质、交感神经节或其他嗜铬组织，可间歇或持续释放过多儿茶酚胺。", "EVD-CARD-FOUND-00262"),
    ("DIS-CARD-HYPERCHOLESTEROLEMIA", "高胆固醇血症", "高胆固醇血症是以血清总胆固醇和/或低密度脂蛋白胆固醇升高为主要特征的血脂异常。", "EVD-EBB07BC0698265300441-HYPERCHOLESTEROLEMIA"),
    ("DIS-CARD-IE-PVE", "人工瓣膜心内膜炎", "人工瓣膜心内膜炎是累及人工心脏瓣膜及其周围组织的感染性心内膜炎。", "EVD-CARD-FOUND-00455"),
    ("DIS-CARD-PAD-LEAD", "下肢动脉硬化闭塞症", "下肢动脉硬化闭塞症是动脉粥样硬化累及下肢动脉并导致狭窄或闭塞，引起肢体缺血症状的慢性疾病。", "EVD-CARD-FOUND-00498"),
    ("DIS-CARD-PERICARD-EFFUSION", "心包积液及心脏压塞", "心包积液是液体异常积聚于心包腔的状态；当心包内压力升高并限制心脏充盈，导致心排血量和回心血量明显下降时称为心脏压塞。", "EVD-CARD-FULLBOOK-C70E4325CD9E39"),
    ("DIS-CARD-PFO", "卵圆孔未闭", "卵圆孔是胎儿期房间隔的生理性通道，多数人在出生后一年内闭合；3岁以后仍未闭合称为卵圆孔未闭。", "EVD-91912FE125E256070355-PFO"),
    ("DIS-CARD-TBAD", "Stanford B型主动脉夹层", "Stanford B型主动脉夹层是夹层起源于胸降主动脉且未累及升主动脉的主动脉夹层。", "EVD-82B97F48D90F3A53DFEC-DISSECTION"),
    ("DIS-CARD-VHD-AR", "主动脉瓣反流", "主动脉瓣反流是主动脉瓣关闭不全导致舒张期血液由主动脉反流入左心室的瓣膜病。", "EVD-71284E1DFCB83940F9FF-AR"),
    ("DIS-CARD-VHD-AS", "主动脉瓣狭窄", "主动脉瓣狭窄是主动脉瓣口变窄并导致左心室射血受阻的瓣膜病。", "EVD-33D67DF805F21EB513A9-AS"),
    ("DIS-CARD-VHD-MR", "二尖瓣反流", "二尖瓣反流是二尖瓣结构或其相关心脏结构、功能异常，导致收缩期血液由左心室反流入左心房的瓣膜病。", "EVD-30CF73BE67B865428C97-MR"),
    ("DIS-CARD-VHD-MS", "二尖瓣狭窄", "二尖瓣狭窄是二尖瓣口狭窄导致舒张期血液进入左心室受阻、左心房压力升高的瓣膜病。", "EVD-CARD-DEEP-E1BEBD991C249B"),
    ("DIS-CARD-VHD-MULTI", "多瓣膜病", "多瓣膜病又称联合瓣膜病，是指两个或两个以上心脏瓣膜病变同时存在。", "EVD-CARD-FOUND-00420"),
    ("DIS-CARD-VHD-PS", "肺动脉瓣狭窄", "肺动脉瓣狭窄是肺动脉瓣口狭窄、导致右心室流出阻力增加的先天性心脏病。", "EVD-5FD6B402E333E111AA38-PS"),
    ("DIS-CARD-VHD-RHD", "风湿性心脏瓣膜病", "风湿性心脏瓣膜病是风湿热反复或持续损伤心脏瓣膜并形成永久性瘢痕，导致瓣膜狭窄和/或反流的疾病。", "EVD-CARD-DEEP-C7C3EB4E235A08"),
    ("DIS-CARD-VHD-TR", "三尖瓣反流", "三尖瓣反流是三尖瓣结构复合体闭合功能障碍，导致右心室收缩期血液反流入右心房的瓣膜病。", "EVD-F629AF869917B88B5666-TR"),
    ("DIS-CARD-VSD", "室间隔缺损", "室间隔缺损是室间隔存在异常交通的常见先天性心脏畸形，可单独存在，也可与其他畸形合并。", "EVD-D965C1A647CA609ACBF9-VSD"),
    ("DIS-CARD-VTE", "静脉血栓症", "静脉血栓栓塞症包括深静脉血栓形成和肺血栓栓塞症，是同一疾病过程在不同部位、不同阶段的表现。", "EVD-CARD-FULLBOOK-5FF5D6FEE44D84"),
]


def normalized_definition_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for disease_code, disease_name, definition_text, evidence_code in DEFINITION_ROWS:
        suffix = hashlib.sha1(disease_code.encode("utf-8")).hexdigest()[:16].upper()
        rows.append(
            {
                "disease_code": disease_code,
                "disease_name": disease_name,
                "definition_text": definition_text,
                "evidence_code": evidence_code,
                "new_definition_code": f"DEF-CDSSV2-{suffix}",
            }
        )
    return rows


def dump_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def query_records(session: Any, query: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(record) for record in session.run(query, **params)]


def collect_preflight(session: Any) -> dict[str, Any]:
    definitions = normalized_definition_rows()
    disease_codes = [row["disease_code"] for row in definitions]
    evidence_codes = sorted({row["evidence_code"] for row in definitions})

    disease_rows = query_records(
        session,
        """
        UNWIND $codes AS code
        OPTIONAL MATCH (d:KGNode {entityType:'Disease', code:code})
        RETURN code, count(d) AS node_count, collect(d.name) AS names
        ORDER BY code
        """,
        codes=disease_codes,
    )
    evidence_rows = query_records(
        session,
        """
        UNWIND $codes AS code
        OPTIONAL MATCH (e:KGNode {entityType:'Evidence', code:code})
        RETURN code, count(e) AS node_count, collect(e.source_name) AS sources
        ORDER BY code
        """,
        codes=evidence_codes,
    )
    existing_definitions = query_records(
        session,
        """
        UNWIND $codes AS code
        MATCH (d:KGNode {entityType:'Disease', code:code})
        OPTIONAL MATCH (d)-[:has_definition]->(df:KGNode {entityType:'Definition'})
        RETURN code, collect(DISTINCT {
          code:df.code, name:df.name,
          text:coalesce(df.definition_text,df.description,df.original_text,'')
        }) AS definitions
        ORDER BY code
        """,
        codes=disease_codes,
    )
    formal_rows = query_records(
        session,
        """
        MATCH (a:KGNode {entityType:'SourceAdjudication', code:$code})
        OPTIONAL MATCH (a)-[:derived_from]->(e:KGNode {entityType:'Evidence'})
        RETURN count(DISTINCT a) AS adjudication_count,
               head(collect(DISTINCT a.primary_evidence_code)) AS property_code,
               collect(DISTINCT e.code) AS linked_codes,
               collect(DISTINCT e.merged_from_codes) AS merged_from_codes
        """,
        code=FORMAL_ADJUDICATION_CODE,
    )
    plan_rows = query_records(
        session,
        """
        UNWIND $pairs AS pair
        OPTIONAL MATCH (d:KGNode {entityType:'Disease',code:pair.disease_code})
          -[r:has_treatment_plan]->
          (p:KGNode {entityType:'TreatmentPlan',code:pair.plan_code})
        OPTIONAL MATCH path=(p)-[:has_clinical_pathway|has_pathway_stage|next_pathway_stage|
          has_stage_rule|has_treatment_component|includes_medication|includes_procedure|
          has_recommended_action|recommends_action|
          treated_by_medication|treated_by_procedure*1..5]->(a:KGNode)
        WHERE a.entityType IN ['Medication','Procedure','ExamItem','LabItem','TreatmentItem',
                               'FollowUp','Exam','LabTest']
        RETURN pair, count(DISTINCT r) AS relation_count,
               count(DISTINCT p) AS plan_count,
               collect(DISTINCT a.code) AS action_codes,
               collect(DISTINCT p.name) AS plan_names
        """,
        pairs=BAD_PLAN_PAIRS,
    )
    differential_rows = query_records(
        session,
        """
        MATCH (d:KGNode {entityType:'Disease'})
          -[r:has_differential_diagnosis|differentiates_from]->
          (x:KGNode {entityType:'DifferentialDiagnosis'})
        WHERE x.code IN $codes
        OPTIONAL MATCH (x)-[:has_differential_point|requires_exclusion_exam]->(rule:KGNode)
        RETURN x.code AS differential_code, x.name AS differential_name,
               count(DISTINCT r) AS relation_count,
               collect(DISTINCT d.code) AS disease_codes,
               collect(DISTINCT rule.code) AS rule_codes
        ORDER BY differential_code
        """,
        codes=POLLUTED_DIFFERENTIAL_CODES,
    )
    medication_rows = query_records(
        session,
        """
        UNWIND $codes AS code
        OPTIONAL MATCH (m:KGNode {entityType:'Medication',code:code})
        OPTIONAL MATCH (source:KGNode)-[r]->(m)
        WHERE type(r) IN ['includes_medication','treated_by_medication','recommends_action',
                          'has_recommended_action']
        RETURN code, count(DISTINCT m) AS node_count,
               collect(DISTINCT source.code) AS incoming_clinical_sources
        ORDER BY code
        """,
        codes=ORPHAN_MEDICATION_CODES,
    )

    errors: list[str] = []
    errors.extend(
        f"疾病节点数量异常：{row['code']}={row['node_count']}"
        for row in disease_rows
        if row["node_count"] != 1
    )
    errors.extend(
        f"证据节点数量异常：{row['code']}={row['node_count']}"
        for row in evidence_rows
        if row["node_count"] != 1
    )
    if len(definitions) != 36 or len(disease_codes) != len(set(disease_codes)):
        errors.append("定义修复清单必须恰好包含36个互不重复的疾病。")
    if not formal_rows or formal_rows[0]["adjudication_count"] != 1:
        errors.append("正式推荐来源裁决节点不存在或重复。")
    else:
        formal = formal_rows[0]
        merged = {
            code
            for values in formal.get("merged_from_codes", [])
            for code in (values or [])
        }
        if formal.get("property_code") not in {
            FORMAL_OLD_EVIDENCE_CODE,
            FORMAL_CANONICAL_EVIDENCE_CODE,
        }:
            errors.append("正式推荐主证据属性不是预期的旧编码或规范编码。")
        if FORMAL_CANONICAL_EVIDENCE_CODE not in formal.get("linked_codes", []):
            errors.append("正式推荐没有关系连接到规范证据节点。")
        if (
            formal.get("property_code") == FORMAL_OLD_EVIDENCE_CODE
            and FORMAL_OLD_EVIDENCE_CODE not in merged
        ):
            errors.append("规范证据节点没有记录旧主证据编码，不能自动回填。")
    for row in plan_rows:
        if row["relation_count"] != 1 or row["plan_count"] != 1:
            errors.append(f"待清理治疗方案关系状态异常：{row['pair']}")
        if row.get("action_codes"):
            errors.append(f"待清理治疗方案已有真实动作，不允许删除：{row['pair']}")
    if sum(row["relation_count"] for row in differential_rows) != 16:
        errors.append("历史污染鉴别关系数量不再是已核实的16条。")
    for row in differential_rows:
        if row.get("rule_codes"):
            errors.append(
                f"鉴别诊断节点已存在规则，不允许按污染节点删除：{row['differential_code']}"
            )
    for row in medication_rows:
        if row["node_count"] != 1:
            errors.append(f"孤立药物类别节点数量异常：{row['code']}")
        if row.get("incoming_clinical_sources"):
            errors.append(f"药物类别仍被临床链路使用，不允许删除：{row['code']}")

    return {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "batch_id": BATCH_ID,
        "definition_count": len(definitions),
        "diseases": disease_rows,
        "evidence": evidence_rows,
        "existing_definitions": existing_definitions,
        "formal_recommendation": formal_rows,
        "treatment_plans": plan_rows,
        "polluted_differentials": differential_rows,
        "orphan_medications": medication_rows,
        "errors": errors,
        "ready_to_apply": not errors,
    }


def snapshot_node_and_relationships(session: Any, code: str) -> dict[str, Any] | None:
    rows = query_records(
        session,
        """
        MATCH (n:KGNode {code:$code})
        OPTIONAL MATCH (n)-[r]-(other)
        RETURN labels(n) AS labels, properties(n) AS properties,
               collect(DISTINCT {
                 relationship_id:elementId(r), type:type(r), properties:properties(r),
                 direction:CASE WHEN startNode(r)=n THEN 'outgoing' ELSE 'incoming' END,
                 other_labels:labels(other), other_properties:properties(other)
               }) AS relationships
        """,
        code=code,
    )
    return rows[0] if rows else None


def collect_backup(session: Any, preflight: dict[str, Any]) -> dict[str, Any]:
    existing_definition_codes = sorted(
        {
            item.get("code")
            for row in preflight["existing_definitions"]
            for item in row.get("definitions", [])
            if item.get("code")
        }
    )
    destructive_codes = sorted(
        {pair["plan_code"] for pair in BAD_PLAN_PAIRS}
        | set(POLLUTED_DIFFERENTIAL_CODES)
        | set(ORPHAN_MEDICATION_CODES)
        | set(existing_definition_codes)
        | {FORMAL_ADJUDICATION_CODE}
    )
    return {
        "backup_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "batch_id": BATCH_ID,
        "scope": "本轮会修改或删除的节点及其直接关系；未修改的Evidence节点仅作为关系终点保留快照。",
        "nodes": {
            code: snapshot_node_and_relationships(session, code)
            for code in destructive_codes
        },
    }


def apply_transaction(tx: Any, definitions: list[dict[str, str]], now: str) -> dict[str, Any]:
    formal = tx.run(
        """
        MATCH (a:KGNode {entityType:'SourceAdjudication',code:$adj_code})
        MATCH (a)-[:derived_from]->(e:KGNode {entityType:'Evidence',code:$new_code})
        WHERE a.primary_evidence_code IN [$old_code,$new_code]
        SET a.primary_evidence_code=$new_code,
            a.updated_at=$now,
            a.last_batch_id=$batch_id
        RETURN count(a) AS updated
        """,
        adj_code=FORMAL_ADJUDICATION_CODE,
        old_code=FORMAL_OLD_EVIDENCE_CODE,
        new_code=FORMAL_CANONICAL_EVIDENCE_CODE,
        now=now,
        batch_id=BATCH_ID,
    ).single()
    if not formal or formal["updated"] != 1:
        raise RuntimeError("正式推荐主证据编码修复失败，事务已回滚。")

    definition_updated = 0
    definition_created = 0
    for row in definitions:
        existing = tx.run(
            """
            MATCH (d:KGNode {entityType:'Disease',code:$disease_code})
            OPTIONAL MATCH (d)-[:has_definition]->(df:KGNode {entityType:'Definition'})
            RETURN [x IN collect(DISTINCT df) WHERE x IS NOT NULL | x.code] AS codes
            """,
            disease_code=row["disease_code"],
        ).single()
        existing_codes = existing["codes"] if existing else []
        if len(existing_codes) > 1:
            raise RuntimeError(
                f"疾病存在多个定义节点，拒绝自动覆盖：{row['disease_code']}"
            )
        definition_code = existing_codes[0] if existing_codes else row["new_definition_code"]
        record = tx.run(
            """
            MATCH (d:KGNode {entityType:'Disease',code:$disease_code})
            MATCH (e:KGNode {entityType:'Evidence',code:$evidence_code})
            MERGE (df:KGNode:Definition {code:$definition_code})
            ON CREATE SET df.created_at=$now
            SET df.entityType='Definition',
                df.name=$disease_name+'定义',
                df.display_name=$disease_name+'定义',
                df.preferred_name=$disease_name+'定义',
                df.definition_text=$definition_text,
                df.description=$definition_text,
                df.text_form='规范化定义摘要',
                df.source_verbatim=false,
                df.content_provenance='由权威来源原文规范化提炼，完整原文见supported_by_evidence关系',
                df.source_evidence_code=$evidence_code,
                df.source_name=e.source_name,
                df.source_type=e.source_type,
                df.source_version=e.source_version,
                df.source_page=e.source_page,
                df.source_section=e.source_section,
                df.knowledge_layer=CASE
                  WHEN coalesce(e.source_type,'')='authoritative_textbook'
                    OR coalesce(e.source_name,'') CONTAINS '内科学'
                  THEN '教材骨架' ELSE '指南补强' END,
                df.skeleton_slot='definition',
                df.schema_version='V2.0',
                df.batch_id=$batch_id,
                df.status='active',
                df.review_status='review_ready',
                df.clinical_review_status='not_required',
                df.formal_cdss_ready=false,
                df.updated_at=$now
            MERGE (d)-[:has_definition]->(df)
            MERGE (df)-[:supported_by_evidence]->(e)
            RETURN df.code AS code
            """,
            disease_code=row["disease_code"],
            disease_name=row["disease_name"],
            definition_text=row["definition_text"],
            evidence_code=row["evidence_code"],
            definition_code=definition_code,
            now=now,
            batch_id=BATCH_ID,
        ).single()
        if not record:
            raise RuntimeError(f"定义写入失败：{row['disease_code']}")
        if existing_codes:
            definition_updated += 1
        else:
            definition_created += 1

    plan_deleted_relations = 0
    plan_deleted_nodes = 0
    for pair in BAD_PLAN_PAIRS:
        record = tx.run(
            """
            MATCH (d:KGNode {entityType:'Disease',code:$disease_code})
              -[r:has_treatment_plan]->
              (p:KGNode {entityType:'TreatmentPlan',code:$plan_code})
            DELETE r
            WITH p
            OPTIONAL MATCH ()-[incoming]->(p)
            WITH p,count(incoming) AS incoming_count
            FOREACH (_ IN CASE WHEN incoming_count=0 THEN [1] ELSE [] END | DETACH DELETE p)
            RETURN 1 AS deleted_relation,
                   CASE WHEN incoming_count=0 THEN 1 ELSE 0 END AS deleted_node
            """,
            disease_code=pair["disease_code"],
            plan_code=pair["plan_code"],
        ).single()
        if not record:
            raise RuntimeError(f"治疗方案污染关系清理失败：{pair}")
        plan_deleted_relations += record["deleted_relation"]
        plan_deleted_nodes += record["deleted_node"]

    differential_relations = tx.run(
        """
        MATCH (d:KGNode {entityType:'Disease'})
          -[r:has_differential_diagnosis|differentiates_from]->
          (x:KGNode {entityType:'DifferentialDiagnosis'})
        WHERE x.code IN $codes
        WITH collect(r) AS relationships
        FOREACH (r IN relationships | DELETE r)
        RETURN size(relationships) AS deleted
        """,
        codes=POLLUTED_DIFFERENTIAL_CODES,
    ).single()
    if not differential_relations or differential_relations["deleted"] != 16:
        raise RuntimeError("鉴别诊断污染关系清理数量不是16条，事务已回滚。")

    differential_nodes = tx.run(
        """
        MATCH (x:KGNode {entityType:'DifferentialDiagnosis'})
        WHERE x.code IN $codes
        OPTIONAL MATCH ()-[incoming]->(x)
        WITH x,count(incoming) AS incoming_count
        WHERE incoming_count=0
        WITH collect(x) AS nodes
        FOREACH (x IN nodes | DETACH DELETE x)
        RETURN size(nodes) AS deleted
        """,
        codes=POLLUTED_DIFFERENTIAL_CODES,
    ).single()

    medication_nodes = tx.run(
        """
        MATCH (m:KGNode {entityType:'Medication'})
        WHERE m.code IN $codes
        OPTIONAL MATCH (source:KGNode)-[incoming]->(m)
        WITH m,count(incoming) AS incoming_count
        WHERE incoming_count=0
        WITH collect(m) AS nodes
        FOREACH (m IN nodes | DETACH DELETE m)
        RETURN size(nodes) AS deleted
        """,
        codes=ORPHAN_MEDICATION_CODES,
    ).single()
    if not medication_nodes or medication_nodes["deleted"] != 2:
        raise RuntimeError("孤立药物类别节点未按预期清理2个，事务已回滚。")

    verification = tx.run(
        """
        UNWIND $disease_codes AS code
        MATCH (d:KGNode {entityType:'Disease',code:code})
        OPTIONAL MATCH (d)-[:has_definition]->(df:KGNode {entityType:'Definition'})
        WITH code,collect(df) AS definitions
        WHERE none(x IN definitions WHERE trim(coalesce(x.definition_text,x.description,''))<>'')
        RETURN collect(code) AS missing_codes
        """,
        disease_codes=[row["disease_code"] for row in definitions],
    ).single()
    if not verification or verification["missing_codes"]:
        raise RuntimeError(
            f"事务内定义复核失败：{verification['missing_codes'] if verification else '无结果'}"
        )

    return {
        "formal_primary_evidence_updated": formal["updated"],
        "definition_created": definition_created,
        "definition_updated": definition_updated,
        "plan_relations_deleted": plan_deleted_relations,
        "plan_nodes_deleted": plan_deleted_nodes,
        "differential_relations_deleted": differential_relations["deleted"],
        "differential_nodes_deleted": differential_nodes["deleted"],
        "orphan_medication_nodes_deleted": medication_nodes["deleted"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CDSS双口径审计真实缺口治理")
    parser.add_argument("--apply", action="store_true", help="通过预检后执行单事务写库")
    args = parser.parse_args()

    config = read_db_config(ROOT / "图谱数据库链接.txt")
    with GraphDatabase.driver(
        config["uri"], auth=(config["user"], config["password"])
    ) as driver:
        driver.verify_connectivity()
        with driver.session() as session:
            preflight = collect_preflight(session)
            dump_json(PREFLIGHT_PATH, preflight)
            if preflight["errors"]:
                raise RuntimeError(
                    "写库前检查未通过：\n- " + "\n- ".join(preflight["errors"])
                )
            backup = collect_backup(session, preflight)
            dump_json(BACKUP_PATH, backup)

            if not args.apply:
                print(f"写库前检查通过；未写库。结果：{PREFLIGHT_PATH}")
                print(f"受影响数据回滚备份：{BACKUP_PATH}")
                return

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result = session.execute_write(
                apply_transaction,
                normalized_definition_rows(),
                now,
            )
            payload = {
                "applied_at": now,
                "batch_id": BATCH_ID,
                "transaction": "single_transaction_committed",
                "result": result,
                "backup_path": str(BACKUP_PATH),
            }
            dump_json(RESULT_PATH, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
