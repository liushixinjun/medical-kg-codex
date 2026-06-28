from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from pathlib import Path


def _normalize(text: str) -> str:
    text = re.sub(r"<<<[^>]+>>>", "", text)
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


def _shingles(text: str, size: int = 48, stride: int = 24) -> set[str]:
    if not text:
        return set()
    if len(text) <= size:
        return {text}
    result = {text[index : index + size] for index in range(0, len(text) - size + 1, stride)}
    result.add(text[-size:])
    return result


def analyze_duplicates(batch_dir: Path, threshold: float = 0.72) -> list[dict]:
    batch_dir = Path(batch_dir).resolve()
    manifest_path = batch_dir / "01_source_manifest" / "source_documents_manifest.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        manifest = [row for row in csv.DictReader(handle) if row.get("inclusion_status") == "included"]

    documents = []
    for row in manifest:
        clean_path = batch_dir / "03_clean_text" / f'{row["document_id"]}.clean.txt'
        if not clean_path.is_file():
            continue
        normalized = _normalize(clean_path.read_text(encoding="utf-8-sig"))
        documents.append(
            {
                "document_id": row["document_id"],
                "file_name": row["file_name"],
                "normalized_length": len(normalized),
                "shingles": _shingles(normalized),
            }
        )

    pairs: list[dict] = []
    for index, first in enumerate(documents):
        for second in documents[index + 1 :]:
            shorter = min(first["normalized_length"], second["normalized_length"])
            longer = max(first["normalized_length"], second["normalized_length"])
            if not shorter or shorter / longer < 0.20:
                continue
            intersection = len(first["shingles"] & second["shingles"])
            if not intersection:
                continue
            union = len(first["shingles"] | second["shingles"])
            minimum = min(len(first["shingles"]), len(second["shingles"]))
            jaccard = intersection / union if union else 0.0
            containment = intersection / minimum if minimum else 0.0
            similarity = max(jaccard, containment)
            if similarity < threshold:
                continue
            pairs.append(
                {
                    "document_id_a": first["document_id"],
                    "file_name_a": first["file_name"],
                    "document_id_b": second["document_id"],
                    "file_name_b": second["file_name"],
                    "normalized_length_a": first["normalized_length"],
                    "normalized_length_b": second["normalized_length"],
                    "jaccard_similarity": round(jaccard, 6),
                    "containment_similarity": round(containment, 6),
                    "suggested_action": "REVIEW_AS_SAME_SOURCE",
                    "review_status": "pending_review",
                }
            )

    pairs.sort(key=lambda row: (-row["containment_similarity"], row["file_name_a"], row["file_name_b"]))
    output_path = batch_dir / "01_source_manifest" / "content_similarity_review.csv"
    fields = (
        "document_id_a",
        "file_name_a",
        "document_id_b",
        "file_name_b",
        "normalized_length_a",
        "normalized_length_b",
        "jaccard_similarity",
        "containment_similarity",
        "suggested_action",
        "review_status",
    )
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(pairs)
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Find near-duplicate clean medical documents.")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.72)
    args = parser.parse_args()
    print(len(analyze_duplicates(args.batch_dir, args.threshold)))


if __name__ == "__main__":
    main()
