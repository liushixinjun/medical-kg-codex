from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P


def _iter_blocks(document: DocumentObject):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _read_manifest(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_included_docx(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir).resolve()
    manifest = _read_manifest(batch_dir / "01_source_manifest" / "source_documents_manifest.csv")
    rows = [
        row
        for row in manifest
        if row.get("inclusion_status") == "included" and row.get("extension", "").lower() == ".docx"
    ]
    clean_dir = batch_dir / "03_clean_text"
    audit_dir = batch_dir / "02_page_audit"
    clean_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    segments: list[dict] = []
    audits: list[dict] = []
    for manifest_row in rows:
        document_id = manifest_row["document_id"]
        source_path = Path(manifest_row["full_path"])
        clean_parts = [f"<<<DOCUMENT document_id={document_id}>>>"]
        paragraph_count = 0
        table_count = 0
        char_count = 0
        segment_ordinal = 0
        failure_reason = ""
        try:
            document = Document(source_path)
            for block in _iter_blocks(document):
                if isinstance(block, Paragraph):
                    text = block.text.strip()
                    if not text:
                        continue
                    paragraph_count += 1
                    segment_ordinal += 1
                    style = block.style.name if block.style is not None else ""
                    title = text if style.lower().startswith("heading") else style or f"PARAGRAPH_{paragraph_count}"
                    segment_id = f"SEG-{document_id}-P{paragraph_count:05d}-{segment_ordinal:05d}"
                    clean_parts.append(f"<<<SECTION section_id={segment_id} title={title}>>>")
                    clean_parts.append(text)
                    char_count += len(text)
                    segments.append(
                        {
                            "document_id": document_id,
                            "segment_id": segment_id,
                            "source_section": title,
                            "paragraph_number": paragraph_count,
                            "table_number": None,
                            "row_number": None,
                            "line_start": segment_ordinal,
                            "line_end": segment_ordinal,
                            "start_offset": 0,
                            "end_offset": len(text),
                            "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest().upper(),
                            "status": "parsed",
                        }
                    )
                else:
                    table_count += 1
                    for row_number, table_row in enumerate(block.rows, start=1):
                        text = "\t".join(cell.text.strip().replace("\n", " ") for cell in table_row.cells)
                        if not text.strip("\t "):
                            continue
                        segment_ordinal += 1
                        segment_id = f"SEG-{document_id}-T{table_count:04d}-R{row_number:04d}"
                        clean_parts.append(
                            f"<<<SECTION section_id={segment_id} title=TABLE_{table_count}_ROW_{row_number}>>>"
                        )
                        clean_parts.append(text)
                        char_count += len(text)
                        segments.append(
                            {
                                "document_id": document_id,
                                "segment_id": segment_id,
                                "source_section": f"TABLE_{table_count}",
                                "paragraph_number": None,
                                "table_number": table_count,
                                "row_number": row_number,
                                "line_start": segment_ordinal,
                                "line_end": segment_ordinal,
                                "start_offset": 0,
                                "end_offset": len(text),
                                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest().upper(),
                                "status": "parsed",
                            }
                        )
            status = "parsed"
        except Exception as exc:
            status = "failed"
            failure_reason = f"DOCX_PARSE_FAILED:{type(exc).__name__}:{exc}"

        (clean_dir / f"{document_id}.clean.txt").write_text(
            "\n".join(clean_parts).rstrip() + "\n", encoding="utf-8-sig"
        )
        audits.append(
            {
                "document_id": document_id,
                "file_name": manifest_row["file_name"],
                "source_type": manifest_row.get("source_type", ""),
                "paragraph_count": paragraph_count,
                "table_count": table_count,
                "segment_count": segment_ordinal,
                "char_count": char_count,
                "status": status,
                "failure_reason": failure_reason,
            }
        )

    with (clean_dir / "segment_index_docx.jsonl").open(
        "w", encoding="utf-8-sig", newline="\n"
    ) as handle:
        for segment in segments:
            handle.write(json.dumps(segment, ensure_ascii=False) + "\n")

    fields = (
        "document_id",
        "file_name",
        "source_type",
        "paragraph_count",
        "table_count",
        "segment_count",
        "char_count",
        "status",
        "failure_reason",
    )
    with (audit_dir / "docx_quality_audit.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(audits)

    summary = {
        "document_count": len(rows),
        "segment_count": len(segments),
        "failed_document_count": sum(row["status"] == "failed" for row in audits),
        "character_count": sum(row["char_count"] for row in audits),
    }
    (audit_dir / "docx_parse_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse included DOCX files in a medical KG batch.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(parse_included_docx(args.batch_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
