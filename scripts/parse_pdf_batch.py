from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

import fitz
from pypdf import PdfReader


PAGE_AUDIT_FIELDS = (
    "batch_id",
    "document_id",
    "page_number",
    "page_class",
    "parse_method",
    "char_count",
    "engine_b_char_count",
    "chinese_ratio",
    "replacement_char_count",
    "mojibake_score",
    "image_count",
    "ocr_used",
    "table_detected",
    "clinical_keyword_hits",
    "status",
    "failure_reason",
)

CLINICAL_KEYWORDS = (
    "诊断",
    "治疗",
    "推荐",
    "剂量",
    "禁忌",
    "随访",
    "预后",
    "症状",
    "体征",
    "检查",
    "diagnosis",
    "treatment",
    "recommendation",
    "follow-up",
)


def _read_manifest(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _chinese_ratio(text: str) -> float:
    non_space = [char for char in text if not char.isspace()]
    if not non_space:
        return 0.0
    chinese = sum("\u4e00" <= char <= "\u9fff" for char in non_space)
    return round(chinese / len(non_space), 6)


def _mojibake_score(text: str) -> int:
    markers = ("锟", "斤拷", "烫烫", "屯屯", "ï¿½", "Ã", "Â")
    return text.count("\ufffd") * 10 + sum(text.count(marker) for marker in markers)


def _is_section_divider(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 80:
        return False
    return bool(
        re.search(r"第[一二三四五六七八九十百]+篇", stripped)
        or re.search(r"\bpart\s+[ivxlcdm0-9]+\b", stripped, re.IGNORECASE)
    )


def _classify_page(
    text: str, page_number: int, total_pages: int, image_count: int
) -> tuple[str, str, str]:
    stripped = text.strip()
    if not stripped and image_count == 0:
        return "blank", "accounted_nonclinical", ""
    if _is_section_divider(stripped):
        return "section_divider", "accounted_nonclinical", ""
    if not stripped and image_count > 0 and (page_number <= 20 or page_number == total_pages):
        return "cover", "accounted_nonclinical", ""
    if len(stripped) < 20 and image_count > 0:
        return "unreadable", "ocr_required", "IMAGE_ONLY_OR_LOW_TEXT"

    lowered = stripped.lower()
    if page_number <= 30 and ("目录" in stripped or "contents" in lowered):
        return "contents", "accounted_nonclinical", ""
    if re.search(r"参考文献|references", lowered, re.IGNORECASE):
        return "body", "parsed", ""
    if re.search(r"推荐|recommendation|class\s+[i1v]+", lowered, re.IGNORECASE):
        return "recommendation", "parsed", ""
    if "\t" in stripped or re.search(r"(?:^|\n)\s*(?:表|table)\s*\d+", stripped, re.IGNORECASE):
        return "table", "parsed", ""
    return "body", "parsed", ""


def _render_samples(document: fitz.Document, output_dir: Path, extra_pages: list[int]) -> None:
    if document.page_count == 0:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_indexes = {0, document.page_count // 2, document.page_count - 1}
    sample_indexes.update(extra_pages[:3])
    matrix = fitz.Matrix(1.25, 1.25)
    for index in sorted(i for i in sample_indexes if 0 <= i < document.page_count):
        pixmap = document.load_page(index).get_pixmap(matrix=matrix, alpha=False)
        pixmap.save(output_dir / f"page_{index + 1:04d}.png")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_included_pdfs(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir).resolve()
    manifest_path = batch_dir / "01_source_manifest" / "source_documents_manifest.csv"
    manifest = _read_manifest(manifest_path)
    pdf_rows = [
        row
        for row in manifest
        if row.get("inclusion_status") == "included" and row.get("extension", "").lower() == ".pdf"
    ]

    audit_dir = batch_dir / "02_page_audit"
    clean_dir = batch_dir / "03_clean_text"
    audit_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)
    render_root = audit_dir / "render_samples"

    page_audit: list[dict] = []
    document_audit: list[dict] = []
    segment_rows: list[dict] = []

    for manifest_row in pdf_rows:
        document_id = manifest_row["document_id"]
        pdf_path = Path(manifest_row["full_path"])
        batch_id = manifest_row.get("batch_id", "")
        clean_parts = [f"<<<DOCUMENT document_id={document_id}>>>"]
        document_rows: list[dict] = []
        document_error = ""
        try:
            document = fitz.open(pdf_path)
            try:
                reader = PdfReader(str(pdf_path), strict=False)
                engine_b_count = len(reader.pages)
            except Exception as exc:  # a failed cross-check must not lose engine A output
                reader = None
                engine_b_count = -1
                document_error = f"PYPDF_OPEN_FAILED:{type(exc).__name__}"

            ocr_page_indexes: list[int] = []
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                text = page.get_text("text", sort=True) or ""
                image_count = len(page.get_images(full=True))
                engine_b_text = ""
                engine_b_error = ""
                if reader is not None and page_index < engine_b_count:
                    try:
                        engine_b_text = reader.pages[page_index].extract_text() or ""
                    except Exception as exc:
                        engine_b_error = f"PYPDF_PAGE_FAILED:{type(exc).__name__}"

                page_number = page_index + 1
                page_class, status, failure_reason = _classify_page(
                    text, page_number, document.page_count, image_count
                )
                if status == "ocr_required" and not text.strip():
                    neighbor_texts = []
                    if page_index > 0:
                        neighbor_texts.append(document.load_page(page_index - 1).get_text("text", sort=True))
                    if page_index + 1 < document.page_count:
                        neighbor_texts.append(document.load_page(page_index + 1).get_text("text", sort=True))
                    if any(_is_section_divider(neighbor) for neighbor in neighbor_texts):
                        page_class, status, failure_reason = "blank", "accounted_nonclinical", ""
                if status == "ocr_required":
                    ocr_page_indexes.append(page_index)
                if engine_b_error:
                    failure_reason = ";".join(item for item in (failure_reason, engine_b_error) if item)

                keyword_hits = sum(text.lower().count(keyword.lower()) for keyword in CLINICAL_KEYWORDS)
                row = {
                    "batch_id": batch_id,
                    "document_id": document_id,
                    "page_number": page_number,
                    "page_class": page_class,
                    "parse_method": "fitz+pypdf" if not engine_b_error and reader is not None else "fitz",
                    "char_count": len(text),
                    "engine_b_char_count": len(engine_b_text),
                    "chinese_ratio": _chinese_ratio(text),
                    "replacement_char_count": text.count("\ufffd"),
                    "mojibake_score": _mojibake_score(text),
                    "image_count": image_count,
                    "ocr_used": False,
                    "table_detected": page_class == "table",
                    "clinical_keyword_hits": keyword_hits,
                    "status": status,
                    "failure_reason": failure_reason,
                }
                page_audit.append(row)
                document_rows.append(row)

                segment_id = f"SEG-{document_id}-{page_number}-PAGE-0-{len(text)}"
                clean_parts.append(f"<<<PAGE page={page_number} class={page_class}>>>")
                clean_parts.append(f"<<<SECTION section_id={segment_id} title=PAGE_{page_number}>>>")
                clean_parts.append(text.rstrip())
                segment_rows.append(
                    {
                        "document_id": document_id,
                        "segment_id": segment_id,
                        "page_number": page_number,
                        "page_class": page_class,
                        "start_offset": 0,
                        "end_offset": len(text),
                        "content_hash": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest().upper(),
                        "status": status,
                    }
                )

            _render_samples(document, render_root / document_id, ocr_page_indexes)
            fitz_count = document.page_count
            document.close()
        except Exception as exc:
            fitz_count = 0
            engine_b_count = -1
            document_error = f"FITZ_DOCUMENT_FAILED:{type(exc).__name__}:{exc}"

        (clean_dir / f"{document_id}.clean.txt").write_text(
            "\n".join(clean_parts).rstrip() + "\n", encoding="utf-8-sig"
        )

        parsed = sum(row["status"] == "parsed" for row in document_rows)
        nonclinical = sum(row["status"] == "accounted_nonclinical" for row in document_rows)
        ocr_required = sum(row["status"] == "ocr_required" for row in document_rows)
        accounted = len(document_rows)
        eligible = parsed + ocr_required
        document_audit.append(
            {
                "document_id": document_id,
                "file_name": manifest_row["file_name"],
                "source_type": manifest_row.get("source_type", ""),
                "fitz_page_count": fitz_count,
                "pypdf_page_count": engine_b_count,
                "page_count_match": fitz_count == engine_b_count,
                "accounted_page_count": accounted,
                "parsed_page_count": parsed,
                "nonclinical_page_count": nonclinical,
                "ocr_required_page_count": ocr_required,
                "page_accounting_rate": round(accounted / fitz_count, 6) if fitz_count else 0.0,
                "eligible_content_pass_rate": round(parsed / eligible, 6) if eligible else 1.0,
                "status": "parsed" if not document_error else "parsed_with_warning",
                "failure_reason": document_error,
            }
        )

    _write_jsonl(audit_dir / "page_audit.jsonl", page_audit)
    document_fields = (
        "document_id",
        "file_name",
        "source_type",
        "fitz_page_count",
        "pypdf_page_count",
        "page_count_match",
        "accounted_page_count",
        "parsed_page_count",
        "nonclinical_page_count",
        "ocr_required_page_count",
        "page_accounting_rate",
        "eligible_content_pass_rate",
        "status",
        "failure_reason",
    )
    _write_csv(audit_dir / "document_quality_audit.csv", document_fields, document_audit)
    _write_jsonl(clean_dir / "segment_index.jsonl", segment_rows)

    total_pages = sum(row["fitz_page_count"] for row in document_audit)
    accounted_pages = sum(row["accounted_page_count"] for row in document_audit)
    eligible_pages = sum(row["parsed_page_count"] + row["ocr_required_page_count"] for row in document_audit)
    passed_pages = sum(row["parsed_page_count"] for row in document_audit)
    summary = {
        "document_count": len(pdf_rows),
        "page_count": total_pages,
        "accounted_page_count": accounted_pages,
        "page_accounting_rate": accounted_pages / total_pages if total_pages else 1.0,
        "eligible_content_pass_rate": passed_pages / eligible_pages if eligible_pages else 1.0,
        "ocr_required_page_count": sum(row["ocr_required_page_count"] for row in document_audit),
        "document_warning_count": sum(bool(row["failure_reason"]) for row in document_audit),
    }
    (audit_dir / "pdf_parse_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse all included PDFs in a medical KG batch.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(parse_included_pdfs(args.batch_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
