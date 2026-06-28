from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_graph_instance import CONCRETE_MEDICATION_ALIASES_BY_CLASS, SEMANTIC_SHELL_NAMES


NOISE_PHRASES = {
    "从事教学工作至今",
    "作者简介",
    "主编简介",
}
INCIDENTAL_ANCHOR_PATTERNS = {
    "一开始即表现为",
    "表现为休克或",
    "易误诊为",
    "需要与",
    "鉴别诊断",
    "不能缓解",
}
THERAPEUTIC_ANCHOR_PATTERNS = {
    "用于",
    "治疗",
    "推荐",
    "应",
    "首选",
    "可使用",
    "可给予",
    "主要用于",
    "适用于",
}
MEDICATION_CLASS_MENTION_ALIASES = {
    "抗凝药物": {"抗凝药物", "抗凝药", "口服抗凝药", "直接口服抗凝药", "抗凝剂"},
    "溶栓药物": {"溶栓药物", "溶栓药", "纤溶药物", "溶栓剂"},
    "抗血小板药物": {"抗血小板药物", "抗血小板药", "抗血小板剂"},
    "硝酸酯类药物": {"硝酸酯类药物", "硝酸酯类", "硝酸酯"},
    "β受体阻滞剂": {"β受体阻滞剂", "β受体拮抗剂"},
    "血管紧张素转换酶抑制剂": {"血管紧张素转换酶抑制剂", "ACEI"},
    "血管紧张素Ⅱ受体阻滞剂": {"血管紧张素Ⅱ受体阻滞剂", "ARB"},
    "钙通道阻滞剂": {"钙通道阻滞剂", "钙拮抗剂"},
    "他汀类药物": {"他汀类药物", "他汀"},
}


def has_strong_disease_anchor(disease_name: str, evidence_text: str) -> bool:
    disease_name = str(disease_name or "").strip()
    evidence_text = str(evidence_text or "").strip()
    if not disease_name or disease_name not in evidence_text:
        return False
    disease_pos = evidence_text.find(disease_name)
    window = evidence_text[max(0, disease_pos - 40): disease_pos + len(disease_name) + 80]
    if any(pattern in window for pattern in INCIDENTAL_ANCHOR_PATTERNS):
        return False
    return any(pattern in window for pattern in THERAPEUTIC_ANCHOR_PATTERNS)


def disease_anchor_window(disease_name: str, evidence_text: str, before: int = 80, after: int = 160) -> str:
    disease_name = str(disease_name or "").strip()
    evidence_text = str(evidence_text or "").strip()
    if not disease_name or disease_name not in evidence_text:
        return ""
    disease_pos = evidence_text.find(disease_name)
    return evidence_text[max(0, disease_pos - before): disease_pos + len(disease_name) + after]


def medication_target_mentions(entity_name: str) -> set[str]:
    entity_name = str(entity_name or "").strip()
    mentions = {entity_name} if entity_name else set()
    mentions.update(MEDICATION_CLASS_MENTION_ALIASES.get(entity_name, set()))
    mentions.update(CONCRETE_MEDICATION_ALIASES_BY_CLASS.get(entity_name, set()))
    return {mention for mention in mentions if mention}


def has_relation_semantic_support(row: dict) -> bool:
    entity_type = str(row.get("entityType", "")).strip()
    relation_type = str(row.get("relationType", "")).strip()
    entity_name = str(row.get("entity_name") or row.get("name") or "").strip()
    disease_name = str(row.get("disease_name", "")).strip()
    evidence_text = str(row.get("evidence_text", "")).strip()
    if entity_type == "Medication" and relation_type == "treated_by_medication":
        window = disease_anchor_window(disease_name, evidence_text)
        if not window:
            return False
        return any(mention in window for mention in medication_target_mentions(entity_name))
    return True


def classify_candidate(row: dict, already_covered: bool) -> str:
    entity_type = str(row.get("entityType", "")).strip()
    entity_name = str(row.get("entity_name") or row.get("name") or "").strip()
    disease_name = str(row.get("disease_name", "")).strip()
    evidence_text = str(row.get("evidence_text", "")).strip()

    if entity_name in SEMANTIC_SHELL_NAMES.get(entity_type, set()):
        return "REJECT_SEMANTIC_SHELL"
    if already_covered:
        return "ALREADY_COVERED"
    if len(evidence_text) < 20 or any(phrase in evidence_text for phrase in NOISE_PHRASES):
        return "REJECT_NO_EVIDENCE"
    if entity_type in {"Medication", "TreatmentPlan", "Procedure"} and not has_strong_disease_anchor(disease_name, evidence_text):
        return "NEEDS_DISEASE_ANCHOR_REVIEW"
    if not has_relation_semantic_support(row):
        return "NEEDS_RELATION_SEMANTIC_REVIEW"
    return "ACCEPT_CANDIDATE"


def read_csv_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def existing_relation_keys(batch_dir: Path) -> set[tuple[str, str, str]]:
    nodes = read_jsonl(batch_dir / "05_data_instance" / "nodes_final.jsonl")
    relations = read_jsonl(batch_dir / "05_data_instance" / "relations_final.jsonl")
    node_by_code = {node.get("code"): node for node in nodes}
    keys: set[tuple[str, str, str]] = set()
    for rel in relations:
        source = node_by_code.get(rel.get("source_code"), {})
        target = node_by_code.get(rel.get("target_code"), {})
        if source.get("entityType") == "Disease" and target.get("entityType"):
            keys.add((
                str(source.get("code")),
                str(rel.get("relationType")),
                str(target.get("name")),
            ))
    return keys


def classify_index_rows(index_paths: list[Path], batch_dir: Path | None = None) -> list[dict]:
    covered = existing_relation_keys(batch_dir) if batch_dir else set()
    output: list[dict] = []
    for path in index_paths:
        for row in read_csv_rows(path):
            key = (
                str(row.get("disease_code", "")),
                str(row.get("relationType", "")),
                str(row.get("entity_name", "")),
            )
            status = classify_candidate(row, key in covered)
            out = dict(row)
            out["classification"] = status
            out["source_index_file"] = str(path)
            output.append(out)
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("classification", ""))
        counts[status] = counts.get(status, 0) + 1
    return {
        "total": len(rows),
        "classification_counts": counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify textbook/Trae evidence backfill candidates without mutating graph data.")
    parser.add_argument("--index", action="append", type=Path, required=True)
    parser.add_argument("--batch-dir", type=Path)
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    args = parser.parse_args()

    rows = classify_index_rows(args.index, args.batch_dir)
    write_csv(args.out_csv, rows)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summarize(rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    print(json.dumps(summarize(rows), ensure_ascii=False))


if __name__ == "__main__":
    main()
