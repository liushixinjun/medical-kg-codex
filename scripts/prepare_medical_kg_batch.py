from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
OUTPUT_FOLDERS = (
    "00_scope_and_config",
    "01_source_manifest",
    "02_page_audit",
    "03_clean_text",
    "04_evidence_and_extraction",
    "05_data_instance",
    "06_quality_audit",
    "07_review_package",
)

SCOPE_ALIASES = {
    "室上性心动过速及心房扑动": (
        "室上性心动过速",
        "室上速",
        "阵发性室上性心动过速",
        "阵发性室上速",
        "supraventricular tachycardia",
        "svt",
        "psvt",
        "心房扑动",
        "房扑",
        "atrial flutter",
        "flutter",
        "房性心动过速",
        "atrial tachycardia",
        "房室结折返性心动过速",
        "房室结折返",
        "avnrt",
        "房室折返性心动过速",
        "房室折返",
        "avrt",
        "预激综合征",
        "wolff-parkinson-white",
        "wpw",
        "旁路",
        "抗心律失常药物",
    ),
    "室上性心动过速": (
        "室上性心动过速",
        "室上速",
        "阵发性室上性心动过速",
        "阵发性室上速",
        "supraventricular tachycardia",
        "svt",
        "psvt",
        "房性心动过速",
        "atrial tachycardia",
        "房室结折返性心动过速",
        "房室结折返",
        "avnrt",
        "房室折返性心动过速",
        "房室折返",
        "avrt",
        "预激综合征",
        "wolff-parkinson-white",
        "wpw",
        "旁路",
        "抗心律失常药物",
    ),
    "心房扑动": (
        "心房扑动",
        "房扑",
        "atrial flutter",
        "flutter",
        "典型心房扑动",
        "峡部依赖性心房扑动",
        "三尖瓣环峡部",
        "cavotricuspid isthmus",
        "cti",
        "抗心律失常药物",
    ),
    "心房颤动（房颤，AF）": (
        "心房颤动",
        "房颤",
        "atrial fibrillation",
        "fibrillation",
        "af",
        "nvaf",
        "非瓣膜性心房颤动",
        "瓣膜性心房颤动",
        "左心耳",
        "left atrial appendage",
        "laa",
        "抗凝",
        "doac",
        "noac",
        "华法林",
        "warfarin",
        "达比加群",
        "dabigatran",
        "利伐沙班",
        "rivaroxaban",
        "阿哌沙班",
        "apixaban",
        "艾多沙班",
        "edoxaban",
        "节律控制",
        "心室率控制",
    ),
    "房颤": (
        "心房颤动",
        "房颤",
        "atrial fibrillation",
        "fibrillation",
        "af",
        "nvaf",
        "非瓣膜性心房颤动",
        "瓣膜性心房颤动",
        "左心耳",
        "left atrial appendage",
        "laa",
        "抗凝",
        "doac",
        "noac",
        "华法林",
        "warfarin",
        "达比加群",
        "dabigatran",
        "利伐沙班",
        "rivaroxaban",
        "阿哌沙班",
        "apixaban",
        "艾多沙班",
        "edoxaban",
        "节律控制",
        "心室率控制",
    ),
    "心房颤动": (
        "心房颤动",
        "房颤",
        "atrial fibrillation",
        "fibrillation",
        "af",
        "nvaf",
        "非瓣膜性心房颤动",
        "瓣膜性心房颤动",
        "左心耳",
        "left atrial appendage",
        "laa",
        "抗凝",
        "doac",
        "noac",
        "华法林",
        "warfarin",
        "达比加群",
        "dabigatran",
        "利伐沙班",
        "rivaroxaban",
        "阿哌沙班",
        "apixaban",
        "艾多沙班",
        "edoxaban",
        "节律控制",
        "心室率控制",
    ),
    "心肌病": (
        "心肌病",
        "肥厚型",
        "扩张型",
        "限制型",
        "致心律失常",
        "法布雷",
        "fabry",
        "淀粉样",
        "danon",
        "心肌致密化不全",
        "心内膜心肌",
        "moge",
        "左心室肥厚",
    ),
    "冠状动脉粥样硬化性心脏病": (
        "冠状动脉粥样硬化性心脏病",
        "冠心病",
        "冠状动脉疾病",
        "冠脉",
        "冠状动脉",
        "cad",
        "chd",
        "acs",
        "急性冠脉综合征",
        "急性冠状动脉综合征",
        "不稳定型心绞痛",
        "ua",
        "急性心肌梗死",
        "心肌梗死",
        "心梗",
        "ami",
        "stemi",
        "nstemi",
        "慢性冠脉综合征",
        "慢性冠脉疾病",
        "慢性冠状动脉综合征",
        "慢性冠状动脉疾病",
        "ccs",
        "ccd",
        "稳定型心绞痛",
        "隐匿性冠心病",
        "无症状心肌缺血",
        "陈旧性心肌梗死",
        "缺血性心肌病",
        "pci",
        "cabg",
        "血运重建",
    ),
    "冠心病": (
        "冠状动脉粥样硬化性心脏病",
        "冠心病",
        "冠状动脉疾病",
        "冠脉",
        "冠状动脉",
        "cad",
        "chd",
        "acs",
        "急性冠脉综合征",
        "急性冠状动脉综合征",
        "不稳定型心绞痛",
        "ua",
        "急性心肌梗死",
        "心肌梗死",
        "心梗",
        "ami",
        "stemi",
        "nstemi",
        "慢性冠脉综合征",
        "慢性冠脉疾病",
        "慢性冠状动脉综合征",
        "慢性冠状动脉疾病",
        "ccs",
        "ccd",
        "稳定型心绞痛",
        "隐匿性冠心病",
        "无症状心肌缺血",
        "陈旧性心肌梗死",
        "缺血性心肌病",
        "pci",
        "cabg",
        "血运重建",
    ),
}

MANIFEST_FIELDS = (
    "batch_id",
    "document_id",
    "file_name",
    "full_path",
    "relative_path",
    "extension",
    "source_root",
    "source_type",
    "size_bytes",
    "last_write_time",
    "sha256",
    "normalized_title",
    "dedup_group",
    "keep_or_duplicate",
    "duplicate_reason",
    "inclusion_status",
    "inclusion_reason",
)

SCHEMA_FILE = "专科知识图谱Schema标准.md"
SKILL_FILE = "AI自动化工具-文献指南解析.md"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def normalize_title(path: Path) -> str:
    title = unicodedata.normalize("NFKC", path.stem).lower()
    title = re.sub(r"^(?:\d+[_\-. ]+)+", "", title)
    title = re.sub(r"(?:副本|copy)(?:\s*\(\d+\))?$", "", title)
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", title)


def infer_source_type(path: Path, root_kind: str) -> str:
    if root_kind == "textbook":
        return "authoritative_textbook"
    name = path.name.lower()
    if "指南" in name or "guideline" in name:
        return "guideline"
    if "共识" in name or "consensus" in name or "建议" in name:
        return "consensus"
    if path.suffix.lower() == ".txt":
        return "expert_material"
    return "unclassified"


def read_markdown_version(path: Path, default: str = "UNKNOWN") -> str:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    match = re.search(r"^版本[：:]\s*(V[0-9]+(?:\.[0-9]+)*)\s*$", text, re.MULTILINE)
    return match.group(1) if match else default


def is_scope_relevant(path: Path, root: Path, root_kind: str, scope_target: str) -> bool:
    if root_kind == "textbook":
        return True
    relative = str(path.relative_to(root)).lower()
    aliases = SCOPE_ALIASES.get(scope_target, (scope_target,))
    return any(alias.lower() in relative for alias in aliases)


def write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def prepare_batch(
    *,
    specialty: str,
    scope_type: str,
    scope_target: str,
    guide_root: Path,
    textbook_root: Path,
    output_root: Path,
    batch_id: str,
) -> Path:
    guide_root = Path(guide_root).resolve()
    textbook_root = Path(textbook_root).resolve()
    output_root = Path(output_root).resolve()
    standard_root = output_root.parent

    for label, root in (("guide_root", guide_root), ("textbook_root", textbook_root)):
        if not root.is_dir():
            raise FileNotFoundError(f"{label} does not exist: {root}")

    batch_dir = output_root / batch_id
    if batch_dir.exists() and any(batch_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty batch: {batch_dir}")
    batch_dir.mkdir(parents=True, exist_ok=True)
    for folder in OUTPUT_FOLDERS:
        (batch_dir / folder).mkdir(exist_ok=True)

    roots = (("guideline", guide_root), ("textbook", textbook_root))
    rows: list[dict] = []
    for root_kind, root in roots:
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=str):
            extension = path.suffix.lower()
            digest = sha256_file(path)
            relevant = is_scope_relevant(path, root, root_kind, scope_target)
            if extension not in SUPPORTED_EXTENSIONS:
                inclusion_status = "excluded"
                inclusion_reason = "UNSUPPORTED_EXTENSION"
            elif not relevant:
                inclusion_status = "excluded"
                inclusion_reason = "OUT_OF_SCOPE_PATH_AND_NAME"
            else:
                inclusion_status = "included"
                inclusion_reason = "SCOPE_PATH_OR_NAME_MATCH"

            stat = path.stat()
            rows.append(
                {
                    "batch_id": batch_id,
                    "document_id": f"DOC-{digest[:16]}",
                    "file_name": path.name,
                    "full_path": str(path),
                    "relative_path": str(path.relative_to(root)),
                    "extension": extension,
                    "source_root": str(root),
                    "source_type": infer_source_type(path, root_kind),
                    "size_bytes": stat.st_size,
                    "last_write_time": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                    "sha256": digest,
                    "normalized_title": normalize_title(path),
                    "dedup_group": f"SHA-{digest[:16]}",
                    "keep_or_duplicate": "keep",
                    "duplicate_reason": "",
                    "inclusion_status": inclusion_status,
                    "inclusion_reason": inclusion_reason,
                }
            )

    by_hash: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_hash[row["sha256"]].append(row)
    for group in by_hash.values():
        if len(group) < 2:
            continue
        ranked = sorted(
            group,
            key=lambda row: (
                row["inclusion_status"] != "included",
                row["extension"] != ".pdf",
                row["full_path"],
            ),
        )
        for duplicate in ranked[1:]:
            duplicate["keep_or_duplicate"] = "duplicate"
            duplicate["duplicate_reason"] = "EXACT_SHA256_DUPLICATE"
            if duplicate["inclusion_status"] == "included":
                duplicate["inclusion_status"] = "excluded"
                duplicate["inclusion_reason"] = "EXACT_SHA256_DUPLICATE"

    manifest_dir = batch_dir / "01_source_manifest"
    write_csv(manifest_dir / "source_documents_manifest.csv", MANIFEST_FIELDS, rows)

    dedup_rows = []
    for digest, group in sorted(by_hash.items()):
        if len(group) > 1:
            kept = next(row for row in group if row["keep_or_duplicate"] == "keep")
            for duplicate in (row for row in group if row["keep_or_duplicate"] == "duplicate"):
                dedup_rows.append(
                    {
                        "dedup_group": f"SHA-{digest[:16]}",
                        "sha256": digest,
                        "kept_document_id": kept["document_id"],
                        "kept_path": kept["full_path"],
                        "duplicate_path": duplicate["full_path"],
                        "duplicate_reason": duplicate["duplicate_reason"],
                    }
                )
    write_csv(
        manifest_dir / "dedup_index.csv",
        (
            "dedup_group",
            "sha256",
            "kept_document_id",
            "kept_path",
            "duplicate_path",
            "duplicate_reason",
        ),
        dedup_rows,
    )

    summary_counter = Counter(
        (row["source_root"], row["extension"], row["inclusion_status"]) for row in rows
    )
    summary_rows = [
        {
            "source_root": source_root,
            "extension": extension,
            "inclusion_status": status,
            "file_count": count,
        }
        for (source_root, extension, status), count in sorted(summary_counter.items())
    ]
    write_csv(
        manifest_dir / "source_folder_summary.csv",
        ("source_root", "extension", "inclusion_status", "file_count"),
        summary_rows,
    )

    manifest_hash = hashlib.sha256(
        "\n".join(f'{row["sha256"]}|{row["full_path"]}' for row in rows).encode("utf-8")
    ).hexdigest().upper()
    config = {
        "batch_id": batch_id,
        "specialty": specialty,
        "scope_type": scope_type,
        "scope_target": scope_target,
        "guide_root": str(guide_root),
        "textbook_root": str(textbook_root),
        "output_root": str(output_root),
        "schema_file": SCHEMA_FILE,
        "schema_version": read_markdown_version(standard_root / SCHEMA_FILE),
        "skill_file": SKILL_FILE,
        "skill_version": read_markdown_version(standard_root / SKILL_FILE),
        "source_manifest_hash": manifest_hash,
        "included_file_count": sum(row["inclusion_status"] == "included" for row in rows),
        "excluded_file_count": sum(row["inclusion_status"] == "excluded" for row in rows),
        "created_time": datetime.now().astimezone().isoformat(),
    }
    (batch_dir / "00_scope_and_config" / "batch_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig"
    )
    return batch_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare an isolated medical KG extraction batch.")
    parser.add_argument("--specialty", required=True)
    parser.add_argument("--scope-type", choices=("specialty", "category", "disease"), required=True)
    parser.add_argument("--scope-target", required=True)
    parser.add_argument("--guide-root", type=Path, required=True)
    parser.add_argument("--textbook-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    args = parser.parse_args()
    batch_dir = prepare_batch(
        specialty=args.specialty,
        scope_type=args.scope_type,
        scope_target=args.scope_target,
        guide_root=args.guide_root,
        textbook_root=args.textbook_root,
        output_root=args.output_root,
        batch_id=args.batch_id,
    )
    print(batch_dir)


if __name__ == "__main__":
    main()
