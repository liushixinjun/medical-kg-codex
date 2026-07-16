from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document
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
DOCX_FILE = ROOT.parent / "心血管内科" / "书籍教材" / "《内科学（第10版）》.docx"
BATCH_ID = "20260716_内科学教材定义缺口补齐"


def parse_conn() -> tuple[str, str, str]:
    text = CONN_FILE.read_text(encoding="utf-8")
    uri = re.search(r"bolt://[^\s；;]+", text).group(0)
    user = re.search(r"用户名[:：]\s*([^\s；;]+)", text).group(1)
    pwd = re.search(r"密码[:：]\s*([^\s；;]+)", text).group(1)
    return uri, user, pwd


def normalize(s: str | None) -> str:
    if not s:
        return ""
    s = str(s).replace(" ", "").replace("\u3000", "")
    s = re.sub(r"^第[一二三四五六七八九十百]+[章节篇]", "", s)
    s = re.sub(r"^[一二三四五六七八九十]+[、.．]", "", s)
    return s.strip()


def content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16].upper()


def load_rows() -> list[dict[str, str]]:
    with CHAPTER_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        # 修正早期目录抽取中的父级错误：主动脉和周围血管病被挂到了心脏骤停与心脏性猝死下。
        if r.get("标题") in {"主动脉夹层", "下肢动脉硬化闭塞症", "静脉血栓症"}:
            r["父级"] = "主动脉和周围血管病"
            r["路径"] = f"主动脉和周围血管病 > {r.get('标题')}"
        r["_norm_title"] = normalize(r.get("标题"))
    return rows


def best_row_for_disease(name: str, rows: list[dict[str, str]]) -> dict[str, str] | None:
    nn = normalize(name)
    aliases = {
        "高血压": "原发性高血压",
        "心包炎": "急性心包炎",
        "外周动脉疾病": "下肢动脉硬化闭塞症",
        "急性主动脉综合征": "主动脉夹层",
    }
    targets = [nn]
    if name in aliases:
        targets.insert(0, normalize(aliases[name]))
    for target in targets:
        exact = [r for r in rows if r["_norm_title"] == target]
        if exact:
            return exact[0]
    return None


def extract_docx_candidate(name: str, aliases: list[str], paras: list[str]) -> dict[str, Any] | None:
    terms = [name] + [a for a in aliases if a and len(a) >= 2]
    best = None
    for idx, text in enumerate(paras, start=1):
        if not text or not (3500 <= idx <= 7600):
            continue
        compact = text.replace(" ", "")
        for term in terms:
            if not term or term not in text:
                continue
            score = 0
            nt = re.escape(term)
            if re.search(nt + r"（[^）]{0,80}）?(是指|是|为|称为|又称)", compact):
                score += 100
            if compact.startswith(term):
                score += 60
            if "是指" in compact or "定义为" in compact:
                score += 30
            if "基础骨架节点" in compact:
                score -= 100
            if score >= 90:
                excerpt = text.strip()
                if len(excerpt) > 700:
                    excerpt = excerpt[:700]
                cand = {"text": excerpt, "para_start": idx, "para_end": idx, "score": score, "term": term}
                if not best or cand["score"] > best["score"]:
                    best = cand
    return best


def listify(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x]
    if isinstance(v, str):
        return [v] if v.strip() else []
    return [str(v)]


def run() -> dict[str, Any]:
    rows = load_rows()
    doc = Document(str(DOCX_FILE))
    paras = [p.text.strip() for p in doc.paragraphs]
    uri, user, pwd = parse_conn()
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result: dict[str, Any] = {"batch_id": BATCH_ID, "executed_at": now}

    with driver.session() as s:
        missing = [
            dict(r)
            for r in s.run(
                """
                MATCH (d:KGNode {entityType:'Disease'})
                WHERE NOT (d)-[:has_definition]->(:KGNode {entityType:'Definition'})
                RETURN d.code AS code, d.name AS name, d.aliases AS aliases, d.description AS description
                ORDER BY d.name
                """
            )
        ]
        import_items = []
        marked_source_not_cover = []
        out_of_scope = []
        candidates_report = []

        for d in missing:
            name = d["name"]
            aliases = listify(d.get("aliases"))
            row = best_row_for_disease(name, rows)
            candidate = None
            source_method = None
            if row and "definition" in (row.get("可用槽位") or "") and row.get("概述预览"):
                candidate = {
                    "text": row["概述预览"].strip(),
                    "para_start": int(row["docx_start_para"]) if row.get("docx_start_para") else None,
                    "para_end": int(row["docx_end_para"]) if row.get("docx_end_para") else None,
                    "path": row.get("路径"),
                    "source_method": "章节目录definition槽位",
                }
                source_method = "chapter_csv"
            else:
                docx_cand = extract_docx_candidate(name, aliases, paras)
                if docx_cand:
                    candidate = {
                        "text": docx_cand["text"],
                        "para_start": docx_cand["para_start"],
                        "para_end": docx_cand["para_end"],
                        "path": row.get("路径") if row else None,
                        "source_method": f"DOCX原文定位:{docx_cand['term']}",
                    }
                    source_method = "docx_search"

            if candidate and candidate["text"] and len(candidate["text"]) >= 12:
                import_items.append(
                    {
                        "disease_code": d["code"],
                        "disease_name": name,
                        "def_code": f"DEF-{d['code']}",
                        "evidence_code": f"EVID-DEF-{d['code']}",
                        "definition": candidate["text"],
                        "content_hash": content_hash(candidate["text"]),
                        "source_section_path": candidate.get("path"),
                        "para_start": candidate.get("para_start"),
                        "para_end": candidate.get("para_end"),
                        "source_method": candidate.get("source_method"),
                    }
                )
                candidates_report.append({"name": name, "decision": "import_definition", "method": source_method, **candidate})
            elif row:
                marked_source_not_cover.append(
                    {
                        "disease_code": d["code"],
                        "disease_name": name,
                        "source_section_path": row.get("路径"),
                        "docx_start_para": int(row["docx_start_para"]) if row.get("docx_start_para") else None,
                        "docx_end_para": int(row["docx_end_para"]) if row.get("docx_end_para") else None,
                        "reason": "教材章节存在，但目录槽位未判定为独立definition，且未识别到高置信定义句",
                    }
                )
                candidates_report.append({"name": name, "decision": "source_not_cover_independent_definition", "row": row.get("路径")})
            else:
                out_of_scope.append(
                    {
                        "disease_code": d["code"],
                        "disease_name": name,
                        "reason": "未匹配到《内科学》第10版心血管章节目录中的独立疾病条目",
                    }
                )
                candidates_report.append({"name": name, "decision": "not_in_textbook_freeze_scope"})

        if import_items:
            imported = s.run(
                """
                UNWIND $items AS item
                MATCH (d:KGNode {code:item.disease_code})
                MERGE (def:KGNode {code:item.def_code})
                SET def:Definition,
                    def.id=item.def_code,
                    def.name=item.disease_name + '定义',
                    def.display_name=item.disease_name + '定义',
                    def.preferred_name=item.disease_name + '定义',
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
                    def.source_name='《内科学（第10版）》',
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
                    def.content_hash=item.content_hash,
                    def.review_status='review_ready',
                    def.clinical_review_status='not_required',
                    def.formal_cdss_ready=true,
                    def.batch_id=$batch_id,
                    def.schema_version='V1.1',
                    def.created_at=coalesce(def.created_at,$now),
                    def.updated_at=$now,
                    def.updated_by=$batch_id
                MERGE (ev:KGNode {code:item.evidence_code})
                SET ev:Evidence,
                    ev.id=item.evidence_code,
                    ev.name=item.disease_name + '-definition-教材证据',
                    ev.display_name=item.disease_name + '-definition-教材证据',
                    ev.preferred_name=item.disease_name + '-definition-教材证据',
                    ev.entityType='Evidence',
                    ev.type_label='循证证据',
                    ev.primary_label='Evidence',
                    ev.canonical_labels=['KGNode','Evidence'],
                    ev.evidence_text=item.definition,
                    ev.original_text=item.definition,
                    ev.text_excerpt=item.definition,
                    ev.source_name='《内科学（第10版）》',
                    ev.source_version='第10版',
                    ev.source_type='authoritative_textbook',
                    ev.source_authority='authoritative_textbook',
                    ev.knowledge_layer='textbook_core',
                    ev.source_layer='textbook',
                    ev.skeleton_slot='evidence',
                    ev.skeleton_slot_status='evidence_node',
                    ev.source_section_path=item.source_section_path,
                    ev.docx_para_start=item.para_start,
                    ev.docx_para_end=item.para_end,
                    ev.content_hash=item.content_hash,
                    ev.review_status='review_ready',
                    ev.clinical_review_status='not_required',
                    ev.formal_cdss_ready=true,
                    ev.batch_id=$batch_id,
                    ev.schema_version='V1.1',
                    ev.created_at=coalesce(ev.created_at,$now),
                    ev.updated_at=$now,
                    ev.updated_by=$batch_id
                MERGE (d)-[:has_definition]->(def)
                MERGE (def)-[:supported_by_evidence]->(ev)
                MERGE (d)-[:supported_by_evidence]->(ev)
                SET d.definition=item.definition,
                    d.description=CASE WHEN d.description IS NULL OR d.description CONTAINS '基础骨架节点' THEN item.definition ELSE d.description END,
                    d.definition_source_name='《内科学（第10版）》',
                    d.definition_source_type='authoritative_textbook',
                    d.definition_source_section_path=item.source_section_path,
                    d.definition_docx_paragraph_start=item.para_start,
                    d.definition_docx_paragraph_end=item.para_end,
                    d.definition_skeleton_slot='definition',
                    d.definition_knowledge_layer='textbook_core',
                    d.updated_at=$now,
                    d.updated_by=$batch_id
                RETURN count(DISTINCT d) AS imported
                """,
                items=import_items,
                now=now,
                batch_id=BATCH_ID,
            ).single()["imported"]
        else:
            imported = 0

        if marked_source_not_cover:
            marked = s.run(
                """
                UNWIND $items AS item
                MATCH (d:KGNode {code:item.disease_code})
                SET d.definition_slot_status='source_not_cover_by_textbook',
                    d.definition_source_section_path=coalesce(d.definition_source_section_path,item.source_section_path),
                    d.definition_docx_paragraph_start=coalesce(d.definition_docx_paragraph_start,item.docx_start_para),
                    d.definition_docx_paragraph_end=coalesce(d.definition_docx_paragraph_end,item.docx_end_para),
                    d.definition_gap_reason=item.reason,
                    d.updated_at=$now,
                    d.updated_by=$batch_id
                RETURN count(d) AS marked
                """,
                items=marked_source_not_cover,
                now=now,
                batch_id=BATCH_ID,
            ).single()["marked"]
        else:
            marked = 0

        if out_of_scope:
            out_scope_count = s.run(
                """
                UNWIND $items AS item
                MATCH (d:KGNode {code:item.disease_code})
                SET d.textbook_freeze_scope='out_of_scope',
                    d.textbook_freeze_scope_reason=item.reason,
                    d.updated_at=$now,
                    d.updated_by=$batch_id
                RETURN count(d) AS marked
                """,
                items=out_of_scope,
                now=now,
                batch_id=BATCH_ID,
            ).single()["marked"]
        else:
            out_scope_count = 0

    driver.close()
    result["missing_before"] = len(missing)
    result["definition_imported"] = imported
    result["definition_source_not_cover_marked"] = marked
    result["out_of_textbook_freeze_scope_marked"] = out_scope_count
    result["import_items"] = import_items
    result["source_not_cover"] = marked_source_not_cover
    result["out_of_scope"] = out_of_scope
    result["candidates_report"] = candidates_report
    (OUT_DIR / "10_教材定义缺口补齐执行结果.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
