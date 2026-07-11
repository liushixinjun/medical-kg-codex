from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

import yaml


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
    "08_neo4j_import",
)
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


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def _write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _normalize_title(path: Path) -> str:
    title = unicodedata.normalize("NFKC", path.stem).lower()
    title = re.sub(r"^(?:\d+[_\-. ]+)+", "", title)
    title = re.sub(r"(?:副本|copy)(?:\s*\(\d+\))?$", "", title)
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", title)


def _infer_source_type(path: Path, root_kind: str) -> str:
    if root_kind == "textbook":
        return "authoritative_textbook"
    if root_kind == "external_authority":
        return "external_authority"
    name = path.name.lower()
    if "指南" in name or "guideline" in name or any(item in name for item in ("acc", "aha", "esc", "ccs")):
        return "guideline"
    if "共识" in name or "consensus" in name or "建议" in name:
        return "consensus"
    if path.suffix.lower() == ".txt":
        return "expert_material"
    return "unclassified"


def _markdown_version(path: Path, default: str = "UNKNOWN") -> str:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    match = re.search(r"^版本[：:]\s*(V[0-9]+(?:\.[0-9]+)*)\s*$", text, re.MULTILINE)
    return match.group(1) if match else default


def _matches_alias(text: str, alias: str) -> bool:
    alias = str(alias).strip()
    if not alias:
        return False
    if alias.isascii() and len(alias) <= 12:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text, re.IGNORECASE))
    return alias.lower() in text.lower()


def _is_relevant(path: Path, root: Path, root_kind: str, aliases: list[str]) -> tuple[bool, str]:
    if root_kind == "textbook":
        return True, "TEXTBOOK_BASELINE_INCLUDED"
    relative = str(path.relative_to(root))
    haystack = f"{relative}\n{path.name}"
    matched = [alias for alias in aliases if _matches_alias(haystack, alias)]
    if matched:
        return True, "SCOPE_ALIAS_MATCH:" + "|".join(matched[:5])
    return False, "OUT_OF_SCOPE_PATH_AND_NAME"


def _rank_row(row: dict) -> tuple:
    preferred_ext = {".pdf": 0, ".docx": 1, ".doc": 2, ".txt": 3}
    return (
        row["inclusion_status"] != "included",
        preferred_ext.get(row["extension"], 9),
        row["full_path"],
    )


def _mark_duplicate(row: dict, reason: str) -> None:
    row["keep_or_duplicate"] = "duplicate"
    row["duplicate_reason"] = reason
    if row["inclusion_status"] == "included":
        row["inclusion_status"] = "excluded"
        row["inclusion_reason"] = reason


def _copy_config_and_write_scope_files(config_path: Path, batch_dir: Path, config: dict) -> None:
    scope_dir = batch_dir / "00_scope_and_config"
    shutil.copyfile(config_path, scope_dir / "batch_config.yaml")

    taxonomy_rows = config.get("taxonomy_rows", []) or []
    vocabulary_rows = config.get("controlled_vocabulary_rows", []) or []
    if taxonomy_rows:
        _write_csv(
            scope_dir / "scope_taxonomy.csv",
            (
                "specialty_code",
                "category_code",
                "subcategory_code",
                "disease_code",
                "name",
                "name_en",
                "aliases",
                "inclusion_status",
            ),
            taxonomy_rows,
        )
    if vocabulary_rows:
        _write_csv(
            scope_dir / "controlled_vocabulary.csv",
            ("canonical_name", "name_en", "abbr", "aliases", "entityType", "disease_scope", "source"),
            vocabulary_rows,
        )


def _validate_config(config: dict, standard_root: Path) -> list[dict]:
    blockers: list[dict] = []
    required_paths = {
        "batch.batch_id": config.get("batch", {}).get("batch_id"),
        "scope.top_specialty": config.get("scope", {}).get("top_specialty"),
        "scope.disease_category": config.get("scope", {}).get("disease_category"),
        "scope.scope_type": config.get("scope", {}).get("scope_type"),
        "scope.scope_target": config.get("scope", {}).get("scope_target"),
        "output.output_root": config.get("output", {}).get("output_root"),
    }
    for field, value in required_paths.items():
        if value in (None, "", []):
            blockers.append({"blocker_type": "required_field_missing", "blocker_message": field, "suggested_action": "补齐 batch_config.yaml", "allow_continue": "no"})

    roots = config.get("source_roots", {}) or {}
    for group in ("guideline_roots", "textbook_roots"):
        values = roots.get(group) or []
        if not values:
            blockers.append({"blocker_type": "source_root_missing", "blocker_message": group, "suggested_action": "补齐资料路径", "allow_continue": "no"})
        for value in values:
            if not Path(value).is_dir():
                blockers.append({"blocker_type": "source_root_not_found", "blocker_message": value, "suggested_action": "确认路径是否存在", "allow_continue": "no"})

    for value in roots.get("terminology_roots") or []:
        if not Path(value).exists():
            blockers.append({"blocker_type": "optional_root_not_found", "blocker_message": value, "suggested_action": "确认术语字典路径", "allow_continue": "no"})

    permissions = config.get("execution_permissions", {}) or {}
    if permissions.get("allow_neo4j_write") is True:
        blockers.append({"blocker_type": "unsafe_g0_permission", "blocker_message": "G0 阶段不允许 allow_neo4j_write=true", "suggested_action": "改为 false，导入阶段另开 G2/G3", "allow_continue": "no"})
    if permissions.get("allow_run_import_scripts") is True:
        blockers.append({"blocker_type": "unsafe_g0_permission", "blocker_message": "G0 阶段不允许 allow_run_import_scripts=true", "suggested_action": "改为 false", "allow_continue": "no"})

    if not (standard_root / SCHEMA_FILE).is_file():
        blockers.append({"blocker_type": "standard_file_missing", "blocker_message": SCHEMA_FILE, "suggested_action": "确认 Schema 标准文件", "allow_continue": "no"})
    if not (standard_root / SKILL_FILE).is_file():
        blockers.append({"blocker_type": "standard_file_missing", "blocker_message": SKILL_FILE, "suggested_action": "确认 SKILL 文件", "allow_continue": "no"})
    return blockers


def prepare_from_config(config_path: Path) -> dict:
    config_path = Path(config_path).resolve()
    config = _read_yaml(config_path)
    output_root = Path(config.get("output", {}).get("output_root", "")).resolve()
    standard_root = output_root.parent
    blockers = _validate_config(config, standard_root)

    batch_id = config.get("batch", {}).get("batch_id", "BATCH-UNKNOWN")
    batch_dir = output_root / batch_id
    if batch_dir.exists() and any(batch_dir.iterdir()):
        blockers.append({"blocker_type": "output_dir_not_empty", "blocker_message": str(batch_dir), "suggested_action": "更换批次号或人工确认", "allow_continue": "no"})

    if blockers:
        output_root.mkdir(parents=True, exist_ok=True)
        blocker_path = output_root / f"{batch_id}_G0_startup_gate_blockers.csv"
        _write_csv(blocker_path, ("blocker_type", "blocker_message", "suggested_action", "allow_continue"), blockers)
        return {"status": "blocked", "batch_dir": str(batch_dir), "blocker_count": len(blockers), "blocker_file": str(blocker_path)}

    batch_dir.mkdir(parents=True, exist_ok=True)
    for folder in OUTPUT_FOLDERS:
        (batch_dir / folder).mkdir(exist_ok=True)
    _copy_config_and_write_scope_files(config_path, batch_dir, config)

    scope = config.get("scope", {}) or {}
    source_policy = config.get("source_policy", {}) or {}
    aliases = []
    targets = scope.get("scope_target") or []
    if isinstance(targets, str):
        targets = [targets]
    aliases.extend(targets)
    aliases.extend(scope.get("source_aliases") or [])
    aliases.extend(source_policy.get("source_scope_aliases") or [])
    aliases = sorted({str(item).strip() for item in aliases if str(item).strip()}, key=len, reverse=True)

    roots_config = config.get("source_roots", {}) or {}
    roots: list[tuple[str, Path]] = []
    roots.extend(("guideline", Path(item).resolve()) for item in roots_config.get("guideline_roots") or [])
    roots.extend(("textbook", Path(item).resolve()) for item in roots_config.get("textbook_roots") or [])
    roots.extend(("external_authority", Path(item).resolve()) for item in roots_config.get("external_authority_roots") or [] if Path(item).is_dir())

    rows: list[dict] = []
    for root_kind, root in roots:
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=str):
            extension = path.suffix.lower()
            supported = extension in SUPPORTED_EXTENSIONS
            digest = _sha256_file(path) if supported else ""
            relevant, reason = _is_relevant(path, root, root_kind, aliases) if supported else (False, "UNSUPPORTED_EXTENSION")
            inclusion_status = "included" if supported and relevant else "excluded"
            stat = path.stat()
            rows.append(
                {
                    "batch_id": batch_id,
                    "document_id": f"DOC-{digest[:16]}" if digest else "",
                    "file_name": path.name,
                    "full_path": str(path),
                    "relative_path": str(path.relative_to(root)),
                    "extension": extension,
                    "source_root": str(root),
                    "source_type": _infer_source_type(path, root_kind),
                    "size_bytes": stat.st_size,
                    "last_write_time": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                    "sha256": digest,
                    "normalized_title": _normalize_title(path),
                    "dedup_group": f"SHA-{digest[:16]}" if digest else "",
                    "keep_or_duplicate": "keep",
                    "duplicate_reason": "",
                    "inclusion_status": inclusion_status,
                    "inclusion_reason": reason if inclusion_status == "included" else reason,
                }
            )

    by_hash: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["sha256"]:
            by_hash[row["sha256"]].append(row)
    for digest, group in by_hash.items():
        if len(group) < 2:
            continue
        ranked = sorted(group, key=_rank_row)
        for duplicate in ranked[1:]:
            duplicate["dedup_group"] = f"SHA-{digest[:16]}"
            _mark_duplicate(duplicate, "EXACT_SHA256_DUPLICATE")

    by_title: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        if row["keep_or_duplicate"] == "keep" and row["normalized_title"]:
            by_title[(row["source_type"], row["normalized_title"])].append(row)
    for (_source_type, title), group in by_title.items():
        extensions = {row["extension"] for row in group}
        if len(group) < 2 or not ({".pdf", ".docx", ".doc"} & extensions):
            continue
        ranked = sorted(group, key=_rank_row)
        kept = ranked[0]
        kept["dedup_group"] = f"TITLE-{hashlib.sha1(title.encode('utf-8')).hexdigest()[:16].upper()}"
        for duplicate in ranked[1:]:
            duplicate["dedup_group"] = kept["dedup_group"]
            _mark_duplicate(duplicate, "NORMALIZED_TITLE_DUPLICATE")

    manifest_dir = batch_dir / "01_source_manifest"
    _write_csv(manifest_dir / "source_documents_manifest.csv", MANIFEST_FIELDS, rows)

    dedup_rows = []
    for group in list(by_hash.values()) + list(by_title.values()):
        if len(group) < 2:
            continue
        kept_rows = [row for row in group if row["keep_or_duplicate"] == "keep"]
        kept = sorted(kept_rows or group, key=_rank_row)[0]
        for duplicate in (row for row in group if row is not kept and row["keep_or_duplicate"] == "duplicate"):
            dedup_rows.append(
                {
                    "dedup_group": duplicate["dedup_group"],
                    "sha256": duplicate["sha256"],
                    "kept_document_id": kept["document_id"],
                    "kept_path": kept["full_path"],
                    "duplicate_path": duplicate["full_path"],
                    "duplicate_reason": duplicate["duplicate_reason"],
                }
            )
    _write_csv(
        manifest_dir / "dedup_index.csv",
        ("dedup_group", "sha256", "kept_document_id", "kept_path", "duplicate_path", "duplicate_reason"),
        dedup_rows,
    )

    summary_rows = [
        {"source_root": source_root, "extension": extension, "inclusion_status": status, "file_count": count}
        for (source_root, extension, status), count in sorted(
            Counter((row["source_root"], row["extension"], row["inclusion_status"]) for row in rows).items()
        )
    ]
    _write_csv(manifest_dir / "source_folder_summary.csv", ("source_root", "extension", "inclusion_status", "file_count"), summary_rows)

    included_count = sum(row["inclusion_status"] == "included" for row in rows)
    checklist_rows = [
        {"check_item": "scope_defined", "status": "PASS", "detail": ",".join(targets)},
        {"check_item": "source_roots_exist", "status": "PASS", "detail": str(len(roots))},
        {"check_item": "output_dir_safe", "status": "PASS", "detail": str(batch_dir)},
        {"check_item": "neo4j_write_disabled", "status": "PASS", "detail": "G0 不写库"},
        {"check_item": "included_documents", "status": "PASS" if included_count else "BLOCK", "detail": str(included_count)},
    ]
    _write_csv(batch_dir / "00_scope_and_config" / "G0_startup_gate_checklist.csv", ("check_item", "status", "detail"), checklist_rows)

    manifest_hash = hashlib.sha256(
        "\n".join(f'{row["sha256"]}|{row["full_path"]}|{row["inclusion_status"]}' for row in rows).encode("utf-8")
    ).hexdigest().upper()
    json_config = {
        "batch_id": batch_id,
        "specialty": scope.get("top_specialty", ""),
        "disease_category": scope.get("disease_category", ""),
        "scope_type": scope.get("scope_type", ""),
        "scope_target": "、".join(targets),
        "guide_root": ";".join(str(item) for item in roots_config.get("guideline_roots") or []),
        "textbook_root": ";".join(str(item) for item in roots_config.get("textbook_roots") or []),
        "output_root": str(output_root),
        "schema_file": SCHEMA_FILE,
        "schema_version": _markdown_version(standard_root / SCHEMA_FILE),
        "skill_file": SKILL_FILE,
        "skill_version": _markdown_version(standard_root / SKILL_FILE),
        "source_manifest_hash": manifest_hash,
        "included_file_count": included_count,
        "excluded_file_count": sum(row["inclusion_status"] == "excluded" for row in rows),
        "created_time": datetime.now().astimezone().isoformat(),
    }
    (batch_dir / "00_scope_and_config" / "batch_config.json").write_text(
        json.dumps(json_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig"
    )

    result = {
        "status": "passed" if included_count else "blocked",
        "batch_id": batch_id,
        "batch_dir": str(batch_dir),
        "included_file_count": included_count,
        "excluded_file_count": json_config["excluded_file_count"],
        "dedup_count": len(dedup_rows),
        "source_manifest_hash": manifest_hash,
        "created_time": json_config["created_time"],
    }
    (batch_dir / "00_scope_and_config" / "G0_startup_gate_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="G0 startup gate and source manifest generator for kg_pipeline batches.")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_from_config(args.config), ensure_ascii=False))


if __name__ == "__main__":
    main()
