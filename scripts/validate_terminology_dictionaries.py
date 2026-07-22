from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FIELDS = {"canonical", "code", "aliases", "same_as", "note"}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def validate_file(path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        return [{"file": str(path), "level": "blocking", "issue": "not_utf8", "detail": str(exc)}]

    try:
        data = yaml.safe_load(text) or []
    except yaml.YAMLError as exc:
        return [{"file": str(path), "level": "blocking", "issue": "yaml_parse_error", "detail": str(exc)}]

    if not isinstance(data, list):
        return [{"file": str(path), "level": "blocking", "issue": "root_not_list", "detail": type(data).__name__}]

    if path.name.startswith("9_待审核队列"):
        return validate_review_queue(path, data)

    seen_canonical: dict[str, int] = {}
    seen_code: dict[str, int] = {}
    seen_alias: dict[str, str] = {}

    for index, item in enumerate(data, start=1):
        loc = {"file": str(path), "index": index}
        if not isinstance(item, dict):
            issues.append({**loc, "level": "blocking", "issue": "entry_not_object"})
            continue

        missing = sorted(REQUIRED_FIELDS - set(item.keys()))
        if missing:
            issues.append({**loc, "level": "blocking", "issue": "missing_required_fields", "detail": missing})

        canonical = str(item.get("canonical") or "").strip()
        code = str(item.get("code") or "").strip()
        aliases = as_list(item.get("aliases"))
        same_as = as_list(item.get("same_as"))
        members = as_list(item.get("members"))

        if not canonical:
            issues.append({**loc, "level": "blocking", "issue": "empty_canonical"})
        if not code:
            issues.append({**loc, "level": "blocking", "issue": "empty_code"})
        if not isinstance(item.get("aliases", []), list):
            issues.append({**loc, "level": "blocking", "issue": "aliases_not_list"})
        if not isinstance(item.get("same_as", []), list):
            issues.append({**loc, "level": "blocking", "issue": "same_as_not_list"})
        for relation_field in ("members", "subclasses", "components", "formulations", "brands", "input_aliases"):
            if relation_field in item and not isinstance(item.get(relation_field), list):
                issues.append(
                    {
                        **loc,
                        "level": "blocking",
                        "issue": "drug_relation_field_not_list",
                        "detail": relation_field,
                    }
                )

        if path.name.startswith("4_药物"):
            alias_names = {str(value or "").strip() for value in aliases if str(value or "").strip()}
            member_names = {str(value or "").strip() for value in members if str(value or "").strip()}
            overlap = sorted(alias_names & member_names)
            if overlap:
                issues.append(
                    {
                        **loc,
                        "level": "blocking",
                        "issue": "drug_member_also_used_as_alias",
                        "detail": overlap,
                    }
                )

        if canonical:
            seen_canonical[canonical] = seen_canonical.get(canonical, 0) + 1
        if code:
            seen_code[code] = seen_code.get(code, 0) + 1

        for alias in aliases:
            alias_text = str(alias or "").strip()
            if not alias_text:
                issues.append({**loc, "level": "warning", "issue": "empty_alias"})
                continue
            if alias_text == canonical:
                issues.append({**loc, "level": "warning", "issue": "alias_equals_canonical", "detail": alias_text})
            if code and alias_text == code:
                issues.append({**loc, "level": "blocking", "issue": "alias_equals_code", "detail": alias_text})
            previous = seen_alias.get(alias_text)
            if previous and previous != canonical:
                issues.append(
                    {
                        **loc,
                        "level": "warning",
                        "issue": "alias_used_by_multiple_canonicals",
                        "detail": {"alias": alias_text, "previous": previous, "current": canonical},
                    }
                )
            seen_alias[alias_text] = canonical

        for value in same_as:
            if not str(value or "").strip():
                issues.append({**loc, "level": "warning", "issue": "empty_same_as"})

        if "evidence_match_aliases" in item and not isinstance(item.get("evidence_match_aliases"), list):
            issues.append({**loc, "level": "blocking", "issue": "evidence_match_aliases_not_list"})

    for canonical, count in seen_canonical.items():
        if count > 1:
            issues.append({"file": str(path), "level": "blocking", "issue": "duplicate_canonical", "detail": canonical})
    for code, count in seen_code.items():
        if count > 1:
            issues.append({"file": str(path), "level": "blocking", "issue": "duplicate_code", "detail": code})

    return issues


def validate_review_queue(path: Path, data: list[Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        loc = {"file": str(path), "index": index}
        if not isinstance(item, dict):
            issues.append({**loc, "level": "blocking", "issue": "entry_not_object"})
            continue
        for key in ("entity_a", "entity_b", "question", "suggestion", "status"):
            if key not in item:
                issues.append({**loc, "level": "blocking", "issue": "review_queue_missing_field", "detail": key})
        for side in ("entity_a", "entity_b"):
            value = item.get(side)
            if not isinstance(value, dict) or not value.get("name") or not value.get("code"):
                issues.append({**loc, "level": "blocking", "issue": "review_queue_invalid_entity", "detail": side})
        if str(item.get("status") or "").strip() not in {"pending_review", "approved", "rejected", "merged"}:
            issues.append({**loc, "level": "blocking", "issue": "review_queue_invalid_status", "detail": item.get("status")})
    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate terminology dictionary YAML files.")
    parser.add_argument("--dict-dir", type=Path, default=Path("术语字典"))
    parser.add_argument("--output", type=Path, default=Path("术语字典/terminology_validation_summary.json"))
    args = parser.parse_args()

    files = sorted(args.dict_dir.glob("*.yaml"))
    all_issues: list[dict[str, Any]] = []
    for path in files:
        all_issues.extend(validate_file(path))

    blocking = [item for item in all_issues if item.get("level") == "blocking"]
    warning = [item for item in all_issues if item.get("level") == "warning"]
    summary = {
        "dict_dir": str(args.dict_dir),
        "file_count": len(files),
        "blocking_issue_count": len(blocking),
        "warning_issue_count": len(warning),
        "gate_status": "passed" if not blocking else "failed",
        "issues": all_issues,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    print(json.dumps({k: v for k, v in summary.items() if k != "issues"}, ensure_ascii=False, indent=2))
    if blocking:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
