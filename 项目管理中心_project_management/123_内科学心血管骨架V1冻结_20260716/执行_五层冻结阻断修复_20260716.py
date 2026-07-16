from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent
CONN_FILE = ROOT / "图谱数据库链接.txt"
CHAPTER_CSV = (
    ROOT
    / "心血管内科文献集合"
    / "00_教材骨架库_foundation_skeleton"
    / "心血管内科全章节骨架扩展_CARD-SKELETON-FULL-20260709"
    / "心血管内科教材章节目录_20260709.csv"
)
BATCH_ID = "20260716_内科学心血管骨架V1冻结修复"


def parse_conn() -> tuple[str, str, str]:
    text = CONN_FILE.read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text).group(0)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text).group(1)
    pwd = re.search(r"密码[:：]\s*([^\s；;]+)", text).group(1)
    return uri, user, pwd


def normalize_title(s: str | None) -> str:
    if not s:
        return ""
    s = str(s)
    s = s.replace(" ", "").replace("\u3000", "")
    s = re.sub(r"^第[一二三四五六七八九十百]+[章节篇]\s*", "", s)
    s = re.sub(r"^[一二三四五六七八九十]+[、.．]\s*", "", s)
    s = re.sub(r"^\(?[一二三四五六七八九十]+\)?\s*", "", s)
    return s.strip()


def load_chapter_rows() -> list[dict[str, str]]:
    with CHAPTER_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["_norm_title"] = normalize_title(r.get("标题"))
        r["_norm_parent"] = normalize_title(r.get("父级"))
    return rows


def best_chapter_match(name: str, parent_name: str | None, rows: list[dict[str, str]]) -> dict[str, str] | None:
    nn = normalize_title(name)
    pn = normalize_title(parent_name)
    candidates = []
    for r in rows:
        score = 0
        if r["_norm_title"] == nn:
            score += 100
        elif nn and (r["_norm_title"] in nn or nn in r["_norm_title"]):
            score += 60
        else:
            continue
        if pn:
            if r["_norm_parent"] == pn:
                score += 40
            elif pn and pn in normalize_title(r.get("路径")):
                score += 20
        candidates.append((score, len(r.get("路径", "")), r))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def parent_chapter_fallback(name: str, parent_name: str | None, rows: list[dict[str, str]]) -> dict[str, Any] | None:
    """章节内小标题没有独立目录行时，挂到父章节范围下。"""
    pn = normalize_title(parent_name)
    if not pn:
        return None
    parent_candidates = []
    for r in rows:
        score = 0
        if r["_norm_title"] == pn:
            score += 100
        elif pn and (r["_norm_title"] in pn or pn in r["_norm_title"]):
            score += 60
        if score:
            parent_candidates.append((score, len(r.get("路径", "")), r))
    if not parent_candidates:
        return None
    parent_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    p = parent_candidates[0][2]
    child = normalize_title(name)
    item = dict(p)
    item["路径"] = f"{p.get('路径')} > {child}" if child else p.get("路径")
    item["标题"] = child or name
    item["父级"] = p.get("标题")
    item["层级"] = "章节内小标题"
    item["_fallback"] = "parent_section_range"
    return item


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16].upper()


def run() -> dict[str, Any]:
    rows = load_chapter_rows()
    uri, user, pwd = parse_conn()
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result: dict[str, Any] = {"batch_id": BATCH_ID, "executed_at": now}

    with driver.session() as s:
        # 1. 修正此前已改 entityType 但标签仍残留 DiseaseCategory 的来源章节节点。
        label_fix = s.run(
            """
            MATCH (ss:KGNode {entityType:'SourceSection'})
            WHERE ss:DiseaseCategory
            REMOVE ss:DiseaseCategory
            SET ss:SourceSection,
                ss.updated_at=$now,
                ss.updated_by=$batch_id,
                ss.correction_reason=coalesce(ss.correction_reason,'') + '; 同步修正SourceSection标签'
            RETURN count(ss) AS updated
            """,
            now=now,
            batch_id=BATCH_ID,
        ).single()["updated"]
        result["source_section_label_fixed"] = label_fix

        # 2. 按教材目录给 SourceSection 补章节路径、段落范围和槽位状态。
        source_sections = [
            dict(r)
            for r in s.run(
                """
                MATCH (ss:KGNode {entityType:'SourceSection'})
                RETURN ss.code AS code, ss.name AS name, ss.parent_name AS parent_name
                """
            )
        ]
        matched_sections = []
        unmatched_sections = []
        for ss in source_sections:
            m = best_chapter_match(ss["name"], ss.get("parent_name"), rows)
            if not m:
                m = parent_chapter_fallback(ss["name"], ss.get("parent_name"), rows)
            if not m:
                unmatched_sections.append(ss)
                continue
            matched_sections.append(
                {
                    "code": ss["code"],
                    "source_section_path": m.get("路径"),
                    "docx_start_para": int(m["docx_start_para"]) if m.get("docx_start_para") else None,
                    "docx_end_para": int(m["docx_end_para"]) if m.get("docx_end_para") else None,
                    "chapter_level": m.get("层级"),
                    "chapter_title": m.get("标题"),
                    "chapter_parent": m.get("父级"),
                    "anchor_note": "父章节范围锚点" if m.get("_fallback") == "parent_section_range" else "章节目录精确锚点",
                }
            )
        if matched_sections:
            updated = s.run(
                """
                UNWIND $items AS item
                MATCH (ss:KGNode {code:item.code})
                SET ss.source_section_path=item.source_section_path,
                    ss.docx_start_para=item.docx_start_para,
                    ss.docx_end_para=item.docx_end_para,
                    ss.chapter_level=item.chapter_level,
                    ss.chapter_title=item.chapter_title,
                    ss.chapter_parent=item.chapter_parent,
                    ss.anchor_note=item.anchor_note,
                    ss.source_name='《内科学（第10版）》',
                    ss.source_version='第10版',
                    ss.source_type='authoritative_textbook',
                    ss.knowledge_layer='textbook_core',
                    ss.skeleton_slot='source_section',
                    ss.skeleton_slot_status='covered_from_textbook',
                    ss.updated_at=$now,
                    ss.updated_by=$batch_id
                RETURN count(ss) AS updated
                """,
                items=matched_sections,
                now=now,
                batch_id=BATCH_ID,
            ).single()["updated"]
        else:
            updated = 0
        result["source_section_metadata_updated"] = updated
        result["source_section_unmatched_count"] = len(unmatched_sections)
        result["source_section_unmatched_sample"] = unmatched_sections[:20]

        # 3. 疾病定义字段已存在但缺 Definition 节点：补节点和 has_definition 关系。
        def_candidates = [
            dict(r)
            for r in s.run(
                """
                MATCH (d:KGNode {entityType:'Disease'})
                WHERE d.definition IS NOT NULL
                  AND trim(d.definition) <> ''
                  AND NOT (d)-[:has_definition]->(:KGNode {entityType:'Definition'})
                RETURN d.code AS disease_code,
                       d.name AS disease_name,
                       d.definition AS definition,
                       d.definition_source_section_path AS source_section_path,
                       d.definition_source_name AS source_name,
                       d.definition_docx_paragraph_start AS para_start,
                       d.definition_docx_paragraph_end AS para_end,
                       d.definition_pdf_page_start AS page_start,
                       d.definition_pdf_page_end AS page_end
                """
            )
        ]
        def_items = []
        for d in def_candidates:
            definition = d["definition"].strip()
            if len(definition) < 8:
                continue
            if "基础骨架节点" in definition:
                continue
            def_code = f"DEF-{d['disease_code']}"
            def_items.append(
                {
                    "def_code": def_code,
                    "def_id": def_code,
                    "def_name": f"{d['disease_name']}定义",
                    "disease_code": d["disease_code"],
                    "disease_name": d["disease_name"],
                    "definition": definition,
                    "content_hash": text_hash(definition),
                    "source_section_path": d.get("source_section_path"),
                    "source_name": d.get("source_name") or "《内科学（第10版）》",
                    "para_start": d.get("para_start"),
                    "para_end": d.get("para_end"),
                    "page_start": d.get("page_start"),
                    "page_end": d.get("page_end"),
                }
            )
        if def_items:
            created_defs = s.run(
                """
                UNWIND $items AS item
                MATCH (d:KGNode {code:item.disease_code})
                MERGE (def:KGNode {code:item.def_code})
                SET def:Definition,
                    def.id=item.def_id,
                    def.name=item.def_name,
                    def.display_name=item.def_name,
                    def.preferred_name=item.def_name,
                    def.entityType='Definition',
                    def.type_label='疾病定义',
                    def.primary_label='Definition',
                    def.canonical_labels=['KGNode','Definition'],
                    def.entityCategory='医学事实层',
                    def.definition_text=item.definition,
                    def.description=item.definition,
                    def.text_excerpt=item.definition,
                    def.original_text=item.definition,
                    def.disease_code=item.disease_code,
                    def.disease_name=item.disease_name,
                    def.source_name=item.source_name,
                    def.source_version='第10版',
                    def.source_type='authoritative_textbook',
                    def.source_authority='authoritative_textbook',
                    def.knowledge_layer='textbook_core',
                    def.source_layer='textbook',
                    def.skeleton_slot='definition',
                    def.skeleton_slot_status='covered_from_textbook',
                    def.source_section_path=item.source_section_path,
                    def.docx_para_start=item.para_start,
                    def.docx_para_end=item.para_end,
                    def.pdf_page_start=item.page_start,
                    def.pdf_page_end=item.page_end,
                    def.content_hash=item.content_hash,
                    def.review_status='review_ready',
                    def.clinical_review_status='not_required',
                    def.formal_cdss_ready=true,
                    def.batch_id=$batch_id,
                    def.schema_version='V1.1',
                    def.created_at=coalesce(def.created_at,$now),
                    def.updated_at=$now,
                    def.updated_by=$batch_id
                MERGE (d)-[:has_definition]->(def)
                RETURN count(def) AS n
                """,
                items=def_items,
                now=now,
                batch_id=BATCH_ID,
            ).single()["n"]
        else:
            created_defs = 0
        result["definition_nodes_linked_from_disease_property"] = created_defs
        result["definition_candidates"] = len(def_candidates)
        result["definition_skipped"] = len(def_candidates) - len(def_items)

        # 4. 疾病和定义节点补 derived_from 来源章节关系。
        #    先按 source_section_path 精确匹配，再按末级标题兜底匹配。
        diseases = [
            dict(r)
            for r in s.run(
                """
                MATCH (d:KGNode {entityType:'Disease'})
                RETURN d.code AS code, d.name AS name, d.definition_source_section_path AS path
                """
            )
        ]
        source_rows = [
            dict(r)
            for r in s.run(
                """
                MATCH (ss:KGNode {entityType:'SourceSection'})
                RETURN ss.code AS code, ss.name AS name, ss.parent_name AS parent_name, ss.source_section_path AS path
                """
            )
        ]
        by_path = {r["path"]: r for r in source_rows if r.get("path")}
        source_link_items = []
        source_unmatched = []
        for d in diseases:
            path = d.get("path")
            if not path:
                source_unmatched.append(d)
                continue
            ss = by_path.get(path)
            if not ss:
                segments = [seg.strip() for seg in path.split(">") if seg.strip()]
                m = None
                best_score = -1
                for cand in source_rows:
                    score = 0
                    for idx, seg in enumerate(reversed(segments)):
                        # 末级如果是“类型/分型/分类”等槽位名，允许用上一级章节作为来源。
                        if normalize_title(cand.get("name")) == normalize_title(seg):
                            score += 100 - idx * 15
                        elif normalize_title(seg) and normalize_title(seg) in normalize_title(cand.get("name")):
                            score += 60 - idx * 10
                    if len(segments) >= 2 and normalize_title(segments[-2]) in normalize_title(cand.get("parent_name")):
                        score += 30
                    if score > best_score:
                        m = cand
                        best_score = score
                ss = m if best_score >= 60 else None
            if ss:
                source_link_items.append(
                    {
                        "disease_code": d["code"],
                        "source_code": ss["code"],
                        "source_section_path": path,
                    }
                )
            else:
                source_unmatched.append(d)
        if source_link_items:
            linked = s.run(
                """
                UNWIND $items AS item
                MATCH (d:KGNode {code:item.disease_code})
                MATCH (ss:KGNode {code:item.source_code})
                MERGE (d)-[r:derived_from]->(ss)
                SET r.source='textbook_section_anchor',
                    r.batch_id=$batch_id,
                    r.updated_at=$now
                SET d.source_section_path=coalesce(d.source_section_path,item.source_section_path),
                    d.source_type=coalesce(d.source_type,'authoritative_textbook'),
                    d.source_name=coalesce(d.source_name,'《内科学（第10版）》'),
                    d.source_version=coalesce(d.source_version,'第10版'),
                    d.knowledge_layer=coalesce(d.knowledge_layer,'textbook_core'),
                    d.updated_at=$now,
                    d.updated_by=$batch_id
                WITH d, ss
                OPTIONAL MATCH (d)-[:has_definition]->(def:KGNode {entityType:'Definition'})
                FOREACH (_ IN CASE WHEN def IS NULL THEN [] ELSE [1] END |
                    MERGE (def)-[:derived_from]->(ss)
                )
                RETURN count(*) AS linked
                """,
                items=source_link_items,
                now=now,
                batch_id=BATCH_ID,
            ).single()["linked"]
        else:
            linked = 0
        result["disease_source_section_derived_from_linked"] = linked
        result["disease_source_unmatched_count"] = len(source_unmatched)
        result["disease_source_unmatched_sample"] = source_unmatched[:30]

        # 5. 教材核心节点补槽位和槽位状态。
        slot_map = {
            "Disease": "disease_index",
            "DiseaseCategory": "disease_directory",
            "DiseaseSubcategory": "disease_directory",
            "SourceSection": "source_section",
            "Definition": "definition",
            "DefinitionComponent": "definition",
            "Etiology": "etiology_pathogenesis",
            "Pathophysiology": "etiology_pathogenesis",
            "Pathology": "etiology_pathogenesis",
            "Epidemiology": "epidemiology",
            "Symptom": "clinical_manifestation",
            "Sign": "clinical_manifestation",
            "ClinicalManifestation": "clinical_manifestation",
            "RiskFactor": "risk_factor",
            "Exam": "exam_lab",
            "LabTest": "exam_lab",
            "ExamIndicator": "exam_lab",
            "ThresholdRule": "exam_lab",
            "DiagnosisCriteria": "diagnosis_differential",
            "DiagnosisCriteriaComponent": "diagnosis_differential",
            "DifferentialDiagnosis": "diagnosis_differential",
            "ClinicalRule": "diagnosis_differential",
            "DiseaseClassification": "classification_risk",
            "RiskStratification": "classification_risk",
            "TreatmentPlan": "treatment",
            "Medication": "treatment",
            "Procedure": "treatment",
            "ClinicalPathway": "treatment",
            "PathwayStage": "treatment",
            "RecommendationStatement": "treatment",
            "FollowUp": "followup",
            "Prognosis": "prognosis",
            "Prevention": "prevention",
            "Contraindication": "contraindication",
            "Complication": "complication",
        }
        slot_items = [{"entityType": k, "slot": v} for k, v in slot_map.items()]
        slot_updated = s.run(
            """
            UNWIND $items AS item
            MATCH (n:KGNode {entityType:item.entityType})
            WHERE (n.knowledge_layer='textbook_core' OR n.source_type='authoritative_textbook' OR n.source_authority='authoritative_textbook')
              AND (n.skeleton_slot IS NULL OR n.skeleton_slot='')
            SET n.skeleton_slot=item.slot,
                n.skeleton_slot_status='covered_from_textbook',
                n.updated_at=$now,
                n.updated_by=$batch_id
            RETURN count(n) AS updated
            """,
            items=slot_items,
            now=now,
            batch_id=BATCH_ID,
        ).single()["updated"]
        status_updated = s.run(
            """
            MATCH (n:KGNode)
            WHERE (n.knowledge_layer='textbook_core' OR n.source_type='authoritative_textbook' OR n.source_authority='authoritative_textbook')
              AND n.skeleton_slot IS NOT NULL
              AND (n.skeleton_slot_status IS NULL OR n.skeleton_slot_status='')
            SET n.skeleton_slot_status='covered_from_textbook',
                n.updated_at=$now,
                n.updated_by=$batch_id
            RETURN count(n) AS updated
            """,
            now=now,
            batch_id=BATCH_ID,
        ).single()["updated"]
        result["skeleton_slot_filled"] = slot_updated
        result["skeleton_slot_status_filled"] = status_updated

        # 6. 药物类别：教材未给具体药物时，不硬造药品；标记为教材未覆盖，供后续指南层补充。
        med_status = s.run(
            """
            MATCH (m:KGNode {entityType:'Medication'})
            WHERE NOT (m)-[:has_specific_medication]->(:KGNode {entityType:'Medication'})
              AND (m.name IN ['苯二氮䓬类抗焦虑药','选择性5-羟色胺再摄取抑制剂'])
            SET m.specific_medication_status='source_not_cover_by_textbook',
                m.specific_medication_note='《内科学》第10版相关段落只给药物类别，未列具体药品；不得硬造，后续由指南或药典补充。',
                m.updated_at=$now,
                m.updated_by=$batch_id
            RETURN count(m) AS updated
            """,
            now=now,
            batch_id=BATCH_ID,
        ).single()["updated"]
        result["medication_class_source_not_cover_marked"] = med_status

        # 7. 心肌损伤标志物补常用下级检验指标连接，使用已有节点，不硬造新概念。
        lab_linked = s.run(
            """
            MATCH (parent:KGNode {entityType:'LabTest', name:'心肌损伤标志物'})
            MATCH (child:KGNode)
            WHERE child.entityType IN ['LabTest','ExamIndicator','ThresholdRule']
              AND child.name IN ['肌钙蛋白','心肌肌钙蛋白','肌酸激酶同工酶（CK-MB）','肌酸激酶','肌红蛋白']
            MERGE (parent)-[r:lab_test_has_indicator]->(child)
            SET r.batch_id=$batch_id,
                r.updated_at=$now,
                r.note='心肌损伤标志物下级项目补链'
            RETURN count(DISTINCT child) AS linked
            """,
            now=now,
            batch_id=BATCH_ID,
        ).single()["linked"]
        result["myocardial_injury_marker_children_linked"] = lab_linked

    driver.close()
    out = OUT_DIR / "07_五层冻结阻断修复执行结果.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
