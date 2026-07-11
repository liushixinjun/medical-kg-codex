from __future__ import annotations

import csv
import html
import json
import re
from datetime import datetime
from pathlib import Path

from lxml import html as lxml_html
from pypdf import PdfReader


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威")
RAW = ROOT / "01_原始下载_raw_downloads"
OUT = ROOT / "02_结构化候选_structured_candidates"
TODAY = "20260708"


def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def read_html_text(path: Path) -> tuple[str, dict[str, str]]:
    raw = path.read_bytes()
    doc = lxml_html.fromstring(raw)
    text = clean(doc.text_content())
    meta: dict[str, str] = {}
    for m in doc.xpath("//meta[@name or @property]"):
        key = m.get("name") or m.get("property")
        val = m.get("content")
        if key and val:
            meta[key] = clean(val)
    title = doc.xpath("string(//title)")
    if title:
        meta["title"] = clean(title)
    return text, meta


def extract_window(text: str, patterns: list[str], radius: int = 450) -> str:
    positions = [text.lower().find(p.lower()) for p in patterns]
    positions = [p for p in positions if p >= 0]
    if not positions:
        return ""
    pos = min(positions)
    return clean(text[max(0, pos - radius): pos + radius])


def extract_pdf_windows(path: Path, patterns: list[str], radius: int = 500) -> list[dict[str, object]]:
    reader = PdfReader(str(path))
    hits: list[dict[str, object]] = []
    for i, page in enumerate(reader.pages):
        try:
            text = clean(page.extract_text() or "")
        except Exception:
            text = ""
        if not text:
            continue
        low = text.lower()
        if any(p.lower() in low for p in patterns):
            hits.append({
                "page": i + 1,
                "excerpt": extract_window(text, patterns, radius=radius)[:1200],
            })
    return hits


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def file_by_contains(*parts: str) -> Path | None:
    for p in RAW.iterdir():
        if all(part in p.name for part in parts):
            return p
    return None


def main() -> int:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    candidate_rows: list[dict[str, object]] = []
    alias_rows: list[dict[str, object]] = []
    source_rows: list[dict[str, object]] = []

    def add_candidate(code: str, disease: str, source: str, stype: str, level: str, file: Path | None, definition: str, excerpt: str, can_import: str, reason: str, url: str = ""):
        candidate_rows.append({
            "generated_at": generated_at,
            "disease_code": code,
            "disease_name": disease,
            "source_name": source,
            "source_type": stype,
            "authority_level": level,
            "download_file": file.name if file else "",
            "source_url": url,
            "candidate_definition": clean(definition),
            "source_excerpt": clean(excerpt)[:800],
            "can_import_as_definition": can_import,
            "reason": reason,
        })

    def add_alias(code: str, disease: str, standard_name: str, alias: str, alias_type: str, source: str, file: Path | None):
        alias_rows.append({
            "generated_at": generated_at,
            "disease_code": code,
            "disease_name": disease,
            "standard_name": standard_name,
            "alias": alias,
            "alias_type": alias_type,
            "source_name": source,
            "download_file": file.name if file else "",
            "write_to_dictionary": "candidate",
        })

    # 法布雷病：国家罕见病指南 + GeneReviews + 百度健康医典
    fabry_pdf = file_by_contains("法布雷病", "国家罕见病")
    fabry_gene = file_by_contains("法布雷病", "GeneReviews")
    fabry_baidu = file_by_contains("法布雷病", "百度健康医典")
    if fabry_pdf:
        hits = extract_pdf_windows(fabry_pdf, ["法布雷", "法布里", "Fabry", "半乳糖苷酶", "GLA"], radius=600)
        source_rows.append({"source_name": "国家罕见病诊疗指南2019", "download_file": fabry_pdf.name, "hit_count": len(hits), "hit_pages": ";".join(str(h["page"]) for h in hits[:20])})
        if hits:
            add_candidate("DIS-CARD-CM-FABRY", "法布雷病心肌病", "国家罕见病诊疗指南2019", "government_guideline", "A", fabry_pdf, "", hits[0]["excerpt"], "needs_manual_definition_extract", "已定位国家指南页，需要从原文段落精确截取定义后转正式definition")
    if fabry_gene:
        text, meta = read_html_text(fabry_gene)
        desc = meta.get("description", "")
        definition = "Fabry disease is the most common of the lysosomal storage disorders and results from deficient activity of alpha-galactosidase A, leading to progressive lysosomal deposition of globotriaosylceramide and derivatives in cells throughout the body."
        add_candidate("DIS-CARD-CM-FABRY", "法布雷病心肌病", "GeneReviews", "expert_reviewed_medical_reference", "B", fabry_gene, definition, desc or extract_window(text, ["Fabry disease is the most common"], 500), "conditional", "遗传病/罕见病定义可作为正式definition候选；中文正式入库仍优先国家指南")
        for alias, typ in [
            ("Fabry disease", "english_name"),
            ("Alpha-Galactosidase A Deficiency", "english_alias"),
            ("Anderson-Fabry Disease", "english_alias"),
            ("GLA", "gene_symbol"),
            ("α-Gal A", "enzyme_alias"),
            ("globotriaosylceramide", "substrate"),
        ]:
            add_alias("DIS-CARD-CM-FABRY", "法布雷病心肌病", "法布雷病", alias, typ, "GeneReviews", fabry_gene)
    if fabry_baidu:
        text, meta = read_html_text(fabry_baidu)
        desc = meta.get("seo.description") or meta.get("description", "")
        excerpt = extract_window(text, ["法布雷病", "Fabry Disease", "α-Gal A"], 500)
        add_candidate("DIS-CARD-CM-FABRY", "法布雷病心肌病", "百度健康医典", "public_medical_reference_reviewed", "D", fabry_baidu, "法布雷病是一种因α-半乳糖苷酶A活性不足引起的遗传代谢病。", desc or excerpt, "no", "仅作候选定义、别名、患者教育；不能标专家共识")
        for alias, typ in [("法布里病", "chinese_alias"), ("安德森-法布里病", "chinese_alias"), ("Fabry Disease", "english_name")]:
            add_alias("DIS-CARD-CM-FABRY", "法布雷病心肌病", "法布雷病", alias, typ, "百度健康医典", fabry_baidu)

    # 心房心肌病：EHRA/HRS/APHRS/SOLAECE consensus
    atrial_pmc = file_by_contains("心房心肌病", "PMC")
    if atrial_pmc:
        text, meta = read_html_text(atrial_pmc)
        excerpt = extract_window(text, ["Atrial cardiomyopathy is defined", "any complex of structural"], 700)
        definition = "Atrial cardiomyopathy is any complex of structural, architectural, contractile or electrophysiological changes affecting the atria with the potential to produce clinically relevant manifestations."
        add_candidate("DIS-CARD-CM-ATRIAL", "心房心肌病", "EHRA/HRS/APHRS/SOLAECE专家共识2016", "expert_consensus", "A", atrial_pmc, definition, excerpt, "yes", "专家共识正式定义，可转中文后写入definition")
        for alias, typ in [("Atrial cardiomyopathy", "english_name"), ("atrial cardiomyopathies", "english_alias")]:
            add_alias("DIS-CARD-CM-ATRIAL", "心房心肌病", "心房心肌病", alias, typ, "EHRA/HRS/APHRS/SOLAECE专家共识2016", atrial_pmc)

    # 淀粉样变心肌病：ESC position statement
    amyloid_pmc = file_by_contains("淀粉样变心肌病", "PMC")
    amyloid_pdf = file_by_contains("淀粉样变心肌病", "开放PDF")
    if amyloid_pmc:
        text, meta = read_html_text(amyloid_pmc)
        excerpt = extract_window(text, ["Cardiac amyloidosis is", "amyloid fibrils"], 700)
        definition = "Cardiac amyloidosis is an infiltrative cardiomyopathy caused by the deposition or accumulation of amyloid fibrils in the myocardium or cardiac tissues."
        add_candidate("DIS-CARD-CM-AMYLOID", "淀粉样变心肌病", "ESC心脏淀粉样变立场声明2021", "expert_consensus", "A", amyloid_pmc, definition, excerpt, "yes", "ESC工作组立场声明，可转中文后写入definition")
        for alias, typ in [("Cardiac amyloidosis", "english_name"), ("amyloid cardiomyopathy", "english_alias"), ("ATTR-CM", "english_abbreviation"), ("AL amyloidosis", "subtype")]:
            add_alias("DIS-CARD-CM-AMYLOID", "淀粉样变心肌病", "淀粉样变心肌病", alias, typ, "ESC心脏淀粉样变立场声明2021", amyloid_pmc)
    if amyloid_pdf:
        hits = extract_pdf_windows(amyloid_pdf, ["cardiac amyloidosis", "Definitions and classifications", "amyloid fibrils"], radius=600)
        source_rows.append({"source_name": "ESC心脏淀粉样变立场声明2021 PDF", "download_file": amyloid_pdf.name, "hit_count": len(hits), "hit_pages": ";".join(str(h["page"]) for h in hits[:20])})

    # 致心律失常性心肌病谱系：ESC 2023 cardiomyopathy page / PubMed page
    esc_page = file_by_contains("致心律失常性心肌病", "ESC心肌病指南页面")
    pubmed_page = file_by_contains("致心律失常性心肌病", "PubMed")
    if esc_page:
        text, meta = read_html_text(esc_page)
        excerpt = extract_window(text, ["arrhythmogenic", "cardiomyopathy"], 800)
        add_candidate("DIS-CARD-CM-ACM", "致心律失常性心肌病", "ESC心肌病指南页面2023", "guideline", "A", esc_page, "", excerpt, "needs_full_guideline_text", "当前下载为指南页面，不是全文；需下载ESC全文PDF/HTML后提取ACM定义")
        for code, disease in [("DIS-CARD-CM-ACM", "致心律失常性心肌病"), ("DIS-CARD-CM-ALVC", "致心律失常性左心室心肌病"), ("DIS-CARD-CM-ABVC", "致心律失常性双心室心肌病")]:
            for alias, typ in [("arrhythmogenic cardiomyopathy", "english_name"), ("ACM", "english_abbreviation")]:
                add_alias(code, disease, disease, alias, typ, "ESC心肌病指南页面2023", esc_page)
    if pubmed_page:
        text, meta = read_html_text(pubmed_page)
        excerpt = extract_window(text, ["cardiomyopathies", "ESC Guidelines"], 600)
        source_rows.append({"source_name": "PubMed ESC心肌病指南2023", "download_file": pubmed_page.name, "hit_count": 1 if excerpt else 0, "hit_pages": ""})

    # 仍未有足够定义的疾病
    blocked = [
        ("DIS-CARD-HF-POST-MI", "心肌梗死后心力衰竭", "需心梗后心衰指南/心衰指南定义，当前外部权威未下载到可用定义。"),
        ("DIS-CARD-HF-DIALYSIS-CHF", "透析患者慢性心力衰竭", "需KDIGO/肾脏病或心衰合并CKD/透析资料。"),
        ("DIS-CARD-ARR-VA", "室性心律失常", "可能应作为疾病大类而非单病种；需ESC室性心律失常指南判断。"),
        ("DIS-CARD-ARR-BRADY", "缓慢性心律失常", "需ACC/AHA/HRS缓慢性心律失常指南。"),
        ("DIS-CARD-CM-ABVC", "致心律失常性双心室心肌病", "需ESC心肌病全文或心肌病谱系文献明确分型定义。"),
        ("DIS-CARD-CM-ALVC", "致心律失常性左心室心肌病", "需ESC心肌病全文或心肌病谱系文献明确分型定义。"),
    ]
    for code, disease, reason in blocked:
        add_candidate(code, disease, "", "", "", None, "", "", "no", reason)

    cand_path = OUT / f"心血管内科+剩余10条+候选定义抽取+{TODAY}.csv"
    alias_path = OUT / f"心血管内科+剩余10条+别名候选抽取+{TODAY}.csv"
    source_path = OUT / f"心血管内科+剩余10条+来源命中页码登记+{TODAY}.csv"
    summary_path = OUT / f"心血管内科+剩余10条+外部权威抽取摘要+{TODAY}.json"
    write_csv(cand_path, candidate_rows, ["generated_at", "disease_code", "disease_name", "source_name", "source_type", "authority_level", "download_file", "source_url", "candidate_definition", "source_excerpt", "can_import_as_definition", "reason"])
    write_csv(alias_path, alias_rows, ["generated_at", "disease_code", "disease_name", "standard_name", "alias", "alias_type", "source_name", "download_file", "write_to_dictionary"])
    write_csv(source_path, source_rows, ["source_name", "download_file", "hit_count", "hit_pages"])
    summary = {
        "generated_at": generated_at,
        "candidate_definition_rows": len(candidate_rows),
        "alias_candidate_rows": len(alias_rows),
        "source_hit_rows": len(source_rows),
        "can_import_yes": sum(1 for r in candidate_rows if r["can_import_as_definition"] == "yes"),
        "conditional": sum(1 for r in candidate_rows if r["can_import_as_definition"] == "conditional"),
        "needs_full_guideline_text": sum(1 for r in candidate_rows if r["can_import_as_definition"] == "needs_full_guideline_text"),
        "blocked_or_no": sum(1 for r in candidate_rows if r["can_import_as_definition"] == "no"),
        "outputs": {
            "candidate_definition_csv": str(cand_path),
            "alias_candidate_csv": str(alias_path),
            "source_hit_csv": str(source_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
