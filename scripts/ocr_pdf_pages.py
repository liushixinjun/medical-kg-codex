from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import fitz


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAGE_AUDIT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def chinese_ratio(text: str) -> float:
    non_space = [char for char in text if not char.isspace()]
    if not non_space:
        return 0.0
    return round(sum("\u4e00" <= char <= "\u9fff" for char in non_space) / len(non_space), 6)


def replace_page_block(clean_text: str, page_number: int, new_text: str) -> str:
    pattern = re.compile(
        rf"(<<<PAGE page={page_number} class=)([^>]+)(>>>\n"
        rf"<<<SECTION section_id=)([^\s>]+)(\s+title=PAGE_{page_number}>>>\n)(.*?)(?=<<<PAGE page=|\Z)",
        re.S,
    )

    def repl(match: re.Match[str]) -> str:
        return (
            f"{match.group(1)}body{match.group(3)}"
            f"{match.group(4)}{match.group(5)}"
            f"{new_text.rstrip()}\n"
        )

    replaced, count = pattern.subn(repl, clean_text, count=1)
    if count != 1:
        raise ValueError(f"PAGE_BLOCK_NOT_FOUND:{page_number}")
    return replaced


def apply_ocr_text_to_batch(batch_dir: Path, ocr_text_by_page: dict[tuple[str, int], str]) -> dict[str, int]:
    batch_dir = Path(batch_dir).resolve()
    page_audit_path = batch_dir / "02_page_audit" / "page_audit.jsonl"
    segment_index_path = batch_dir / "03_clean_text" / "segment_index.jsonl"
    page_rows = read_jsonl(page_audit_path)
    segment_rows = read_jsonl(segment_index_path) if segment_index_path.exists() else []

    updated_pages = 0
    updated_documents: set[str] = set()
    for row in page_rows:
        key = (str(row.get("document_id")), int(row.get("page_number")))
        text = ocr_text_by_page.get(key, "").strip()
        if not text:
            continue
        doc_id, page_number = key
        clean_path = batch_dir / "03_clean_text" / f"{doc_id}.clean.txt"
        clean_text = clean_path.read_text(encoding="utf-8-sig")
        clean_path.write_text(replace_page_block(clean_text, page_number, text), encoding="utf-8-sig")

        row["page_class"] = "body"
        row["parse_method"] = f"{row.get('parse_method') or 'fitz'}+tesseract"
        row["char_count"] = len(text)
        row["engine_b_char_count"] = max(int(row.get("engine_b_char_count") or 0), len(text))
        row["chinese_ratio"] = chinese_ratio(text)
        row["ocr_used"] = True
        row["clinical_keyword_hits"] = sum(text.lower().count(keyword.lower()) for keyword in CLINICAL_KEYWORDS)
        row["status"] = "parsed"
        row["failure_reason"] = ""

        for segment in segment_rows:
            if str(segment.get("document_id")) == doc_id and int(segment.get("page_number") or 0) == page_number:
                segment["page_class"] = "body"
                segment["end_offset"] = len(text)
                segment["content_hash"] = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
                segment["status"] = "parsed"
        updated_pages += 1
        updated_documents.add(doc_id)

    if updated_pages:
        write_jsonl(page_audit_path, page_rows)
        if segment_index_path.exists():
            write_jsonl(segment_index_path, segment_rows)
    return {"updated_page_count": updated_pages, "updated_document_count": len(updated_documents)}


def manifest_by_id(batch_dir: Path) -> dict[str, dict[str, str]]:
    rows = read_csv(batch_dir / "01_source_manifest" / "source_documents_manifest.csv")
    return {row["document_id"]: row for row in rows}


def ocr_pdf_pages(
    *,
    batch_dir: Path,
    document_ids: set[str],
    tesseract_exe: Path,
    work_dir: Path,
    dpi: int = 180,
    lang: str = "chi_sim+eng",
) -> dict[str, Any]:
    batch_dir = Path(batch_dir).resolve()
    tesseract_exe = Path(tesseract_exe)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    page_rows = read_jsonl(batch_dir / "02_page_audit" / "page_audit.jsonl")
    manifest = manifest_by_id(batch_dir)
    targets = [
        row
        for row in page_rows
        if str(row.get("document_id")) in document_ids and str(row.get("status")) == "ocr_required"
    ]
    by_doc: dict[str, list[int]] = {}
    for row in targets:
        by_doc.setdefault(str(row["document_id"]), []).append(int(row["page_number"]))

    ocr_text: dict[tuple[str, int], str] = {}
    failed_pages: list[dict[str, Any]] = []
    for doc_id, pages in by_doc.items():
        pdf_path = Path(manifest[doc_id]["full_path"])
        doc = fitz.open(pdf_path)
        doc_work = work_dir / doc_id
        doc_work.mkdir(parents=True, exist_ok=True)
        for page_number in sorted(set(pages)):
            page = doc.load_page(page_number - 1)
            matrix = fitz.Matrix(dpi / 72, dpi / 72)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = doc_work / f"page_{page_number:04d}.png"
            out_base = doc_work / f"page_{page_number:04d}_ocr"
            pixmap.save(str(image_path))
            proc = subprocess.run(
                [
                    str(tesseract_exe),
                    str(image_path),
                    str(out_base),
                    "-l",
                    lang,
                    "--psm",
                    "6",
                ],
                text=True,
                capture_output=True,
                timeout=180,
            )
            text_path = out_base.with_suffix(".txt")
            text = text_path.read_text(encoding="utf-8", errors="ignore") if text_path.exists() else ""
            if proc.returncode != 0 or len(text.strip()) < 20:
                failed_pages.append(
                    {
                        "document_id": doc_id,
                        "page_number": page_number,
                        "returncode": proc.returncode,
                        "stderr": proc.stderr.strip()[:500],
                        "text_length": len(text.strip()),
                    }
                )
                continue
            ocr_text[(doc_id, page_number)] = text.strip()
        doc.close()

    applied = apply_ocr_text_to_batch(batch_dir, ocr_text)
    summary = {
        "requested_document_count": len(document_ids),
        "target_page_count": len(targets),
        "ocr_success_page_count": len(ocr_text),
        "ocr_failed_page_count": len(failed_pages),
        "failed_pages": failed_pages,
        **applied,
    }
    out_dir = batch_dir / "02_page_audit" / "ocr_recovery"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ocr_recovery_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR selected ocr_required PDF pages and patch batch clean text.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--document-id", action="append", required=True)
    parser.add_argument("--tesseract-exe", type=Path, default=Path(r"D:\Program Files Ai\Tesseract-OCR\tesseract.exe"))
    parser.add_argument("--work-dir", type=Path, default=Path(r"D:\Program Files Ai\ocr_work\medical_kg"))
    parser.add_argument("--dpi", type=int, default=180)
    args = parser.parse_args()
    print(
        json.dumps(
            ocr_pdf_pages(
                batch_dir=args.batch_dir,
                document_ids=set(args.document_id),
                tesseract_exe=args.tesseract_exe,
                work_dir=args.work_dir,
                dpi=args.dpi,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
