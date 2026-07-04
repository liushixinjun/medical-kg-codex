from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


def _load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _disease_patterns(vocabulary: list[dict]) -> list[dict]:
    patterns = []
    for row in vocabulary:
        if row.get("entityType") != "Disease":
            continue
        names = [row.get("canonical_name", ""), row.get("name_en", ""), row.get("abbr", "")]
        names.extend(item.strip() for item in row.get("aliases", "").split(","))
        names = [name for name in names if name]
        regexes = []
        for name in sorted(set(names), key=len, reverse=True):
            escaped = re.escape(name)
            if name.isascii() and len(name) <= 6:
                regexes.append(re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE))
            else:
                regexes.append(re.compile(escaped, re.IGNORECASE))
        patterns.append(
            {
                "disease_code": row["disease_scope"],
                "disease_name": row["canonical_name"],
                "patterns": regexes,
            }
        )
    return patterns


def _pathway_element(text: str) -> str:
    rules = (
        ("follow_up", r"随访|复查|监测疾病进展"),
        ("prognosis", r"预后|死亡率|生存率"),
        ("treatment_plan", r"治疗|推荐使用|推荐.*植入|用药|药物|手术|消融|移植"),
        ("risk_stratification", r"危险分层|风险评估|猝死风险|高危"),
        ("diagnosis_criteria", r"诊断标准|诊断依据|诊断为|疑诊|鉴别诊断|排除"),
        ("exam", r"检查|心电图|超声|磁共振|CMR|活检|基因检测|造影"),
        ("symptom_sign", r"临床表现|症状|体征|呼吸困难|胸痛|晕厥|心悸|水肿"),
        ("pathophysiology", r"发病机制|病理生理|心室重构|纤维化"),
        ("etiology", r"病因|致病基因|基因变异|遗传"),
        ("epidemiology", r"患病率|发病率|流行病学"),
        ("definition", r"定义为|是指|是一类|属于"),
    )
    for element, pattern in rules:
        if re.search(pattern, text, re.IGNORECASE):
            return element
    return "clinical_knowledge"


def _recommendation_grade(text: str) -> tuple[str, str]:
    match = re.search(r"[（(]\s*(Ⅰ{1,3}|Ⅳ|I{1,3}|IV|Ⅱ[ab]?|II[ab]?)\s*[，,]\s*([ABC])\s*[）)]", text, re.IGNORECASE)
    if not match:
        return "N/A", "N/A"
    return match.group(1), match.group(2).upper()


def _paragraphs(body: str) -> list[str]:
    body = re.sub(r"<<<SECTION[^>]+>>>", "", body)
    raw = [re.sub(r"\s*\n\s*", " ", part).strip() for part in re.split(r"\n\s*\n", body)]
    result = []
    for paragraph in (item for item in raw if item):
        if len(paragraph) <= 1200:
            result.append(paragraph)
            continue
        sentences = re.split(r"(?<=[。！？；])", paragraph)
        current = ""
        for sentence in sentences:
            if current and len(current) + len(sentence) > 1000:
                result.append(current.strip())
                current = sentence
            else:
                current += sentence
        if current.strip():
            result.append(current.strip())
    return result


def _iter_text_units(text: str, extension: str):
    page_pattern = re.compile(
        r"<<<PAGE page=(\d+) class=([^>]+)>>>(.*?)(?=<<<PAGE page=|\Z)", re.S
    )
    section_pattern = re.compile(
        r"<<<SECTION section_id=([^\s>]+)(?:\s+title=([^>]+))?>>>(.*?)(?=<<<SECTION\s+section_id=|\Z)",
        re.S,
    )
    if extension == ".pdf" or page_pattern.search(text):
        for page_match in page_pattern.finditer(text):
            yield {
                "source_page": int(page_match.group(1)),
                "page_class": page_match.group(2),
                "section_id": "",
                "source_section": "",
                "body": page_match.group(3),
            }
        return
    for ordinal, section_match in enumerate(section_pattern.finditer(text), start=1):
        section_id = section_match.group(1)
        title = section_match.group(2) or f"SECTION_{ordinal}"
        body = section_match.group(3)
        if body.strip():
            yield {
                "source_page": None,
                "page_class": "body",
                "section_id": section_id,
                "source_section": title,
                "body": body,
            }


def _is_navigation_like(paragraph: str) -> bool:
    """Exclude table-of-contents/index lines that contain disease names but no clinical assertion."""
    text = paragraph.strip()
    lower = text.lower()
    dot_leaders = len(re.findall(r"(?:\.\s*){3,}", text))
    spaced_dot_runs = len(re.findall(r"\.\s+\.\s+\.", text))
    chapter_or_section = bool(
        re.search(r"第[一二三四五六七八九十百]+[章节篇]|contents|table of contents|index", lower, re.IGNORECASE)
    )
    page_refs = len(re.findall(r"\b(?:e?\d{2,4})\b", text, re.IGNORECASE))
    return (chapter_or_section and (dot_leaders or spaced_dot_runs or page_refs >= 3)) or (
        spaced_dot_runs >= 3 and page_refs >= 2
    )


def _is_reference_like(paragraph: str) -> bool:
    """Exclude bibliography entries without discarding clinical prose with citations."""
    text = paragraph.strip()
    lower = text.lower()
    if _is_navigation_like(text):
        return True
    if re.match(r"^(参考文献|references\b)", text, re.IGNORECASE):
        return True
    has_et_al = bool(re.search(r"\bet\s+al\.?\b", lower))
    has_doi = "doi:" in lower or "doi.org/" in lower
    has_year = bool(re.search(r"\b(?:19|20)\d{2}\b", text))
    has_journal_shape = bool(
        re.search(r"\b(?:journal|circulation|cardiology|heart|jacc|eur\s+heart\s+j)\b", lower)
    )
    numbered_entry = bool(re.match(r"^\s*(?:\[?\d{1,3}\]?)[.、)]\s*[A-Z][A-Za-z'-]+", text))
    return (has_et_al and (has_doi or has_year or has_journal_shape)) or (
        numbered_entry and has_doi and has_year
    )


def extract_guideline_evidence(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir).resolve()
    manifest = _load_csv(batch_dir / "01_source_manifest" / "source_documents_manifest.csv")
    vocabulary = _load_csv(batch_dir / "00_scope_and_config" / "controlled_vocabulary.csv")
    disease_patterns = _disease_patterns(vocabulary)
    included = [
        row
        for row in manifest
        if row.get("inclusion_status") == "included" and row.get("extension", "").lower() in {".pdf", ".docx"}
    ]
    evidence_rows: list[dict] = []
    by_disease: dict[str, int] = {}
    by_document: dict[str, int] = {}
    for document in included:
        clean_path = batch_dir / "03_clean_text" / f'{document["document_id"]}.clean.txt'
        if not clean_path.is_file():
            continue
        text = clean_path.read_text(encoding="utf-8-sig")
        extension = document.get("extension", "").lower()
        version_match = re.search(r"(?:19|20)\d{2}", document.get("file_name", ""))
        source_version = document.get("source_version", "") or (version_match.group(0) if version_match else "N/A")
        ordinal = 0
        for unit in _iter_text_units(text, extension):
            page = unit["source_page"]
            page_class = unit["page_class"]
            if page_class in {"contents", "index", "copyright", "blank", "cover"}:
                continue
            for paragraph in _paragraphs(unit["body"]):
                if len(paragraph) < 8:
                    continue
                if _is_reference_like(paragraph):
                    continue
                matched_diseases = [
                    disease
                    for disease in disease_patterns
                    if any(pattern.search(paragraph) for pattern in disease["patterns"])
                ]
                if not matched_diseases:
                    continue
                recommendation_class, evidence_level = _recommendation_grade(paragraph)
                content_hash = hashlib.sha256(paragraph.encode("utf-8")).hexdigest().upper()
                for disease in matched_diseases:
                    ordinal += 1
                    if unit.get("section_id"):
                        segment_id = f'{unit["section_id"]}-GL-{ordinal:05d}-{disease["disease_code"].split("-")[-1]}'
                    else:
                        segment_id = f'SEG-{document["document_id"]}-{page}-GL-{ordinal:05d}-{disease["disease_code"].split("-")[-1]}'
                    evidence_id = f"EVD-{content_hash[:20]}-{disease['disease_code'].split('-')[-1]}"
                    pathway = _pathway_element(paragraph)
                    evidence_rows.append(
                        {
                            "evidence_id": evidence_id,
                            "document_id": document["document_id"],
                            "segment_id": segment_id,
                            "source_name": document["file_name"],
                            "source_type": document.get("source_type", "guideline"),
                            "source_version": source_version,
                            "source_section": pathway,
                            "source_page": page,
                            "disease_code": disease["disease_code"],
                            "disease_name": disease["disease_name"],
                            "pathway_element": pathway,
                            "evidence_text": paragraph,
                            "language": "zh" if re.search(r"[\u4e00-\u9fff]", paragraph) else "en",
                            "content_hash": content_hash,
                            "recommendation_class": recommendation_class,
                            "evidence_level": evidence_level,
                            "review_status": "approved",
                        }
                    )
                    by_disease[disease["disease_code"]] = by_disease.get(disease["disease_code"], 0) + 1
                    by_document[document["document_id"]] = by_document.get(document["document_id"], 0) + 1

    output_dir = batch_dir / "04_evidence_and_extraction"
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "guideline_evidence_index.jsonl").open(
        "w", encoding="utf-8-sig", newline="\n"
    ) as handle:
        for row in evidence_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "document_count": len(included),
        "document_with_evidence_count": len(by_document),
        "disease_count": len(by_disease),
        "evidence_count": len(evidence_rows),
        "evidence_by_disease": by_disease,
    }
    (output_dir / "guideline_evidence_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract disease-anchored guideline evidence.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(extract_guideline_evidence(args.batch_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
