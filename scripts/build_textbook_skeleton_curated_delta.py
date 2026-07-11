from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_neo4j_test_db import Neo4jHttpClient


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(long_path(path), "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def long_path(path: Path) -> str:
    text = str(path.resolve())
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return "\\\\?\\" + text
    return text


def write_text(path: Path, text: str) -> None:
    with open(long_path(path), "w", encoding="utf-8") as f:
        f.write(text)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def stable_code(prefix: str, *parts: str) -> str:
    import hashlib

    raw = "|".join(str(p) for p in parts)
    return f"{prefix}-{hashlib.md5(raw.encode('utf-8')).hexdigest()[:16].upper()}"


def parse_connection_file(path: Path) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    http = re.search(r"https?://[^\s\r\n]+", text)
    user = re.search(r"用户名\s*[:：]\s*([^\s\r\n]+)", text)
    password = re.search(r"密码\s*[:：]\s*([^\s\r\n]+)", text)
    if not (http and user and password):
        # tolerate mojibake labels by positional extraction
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        http_value = next((m.group(0) for line in lines for m in [re.search(r"https?://[^\s\r\n]+", line)] if m), "")
        user_value = ""
        pass_value = ""
        for line in lines:
            if line.startswith("3.") and "neo4j" in line:
                user_value = "neo4j"
            if line.startswith("4."):
                # last non-space token is password in the known connection file
                pass_value = re.sub(r"^.*?[：:]", "", line).strip()
        if not (http_value and user_value and pass_value):
            raise RuntimeError("Cannot parse Neo4j connection file.")
        return http_value, user_value, pass_value
    return http.group(0), user.group(1).strip(), password.group(1).strip()


def result_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    cols = result["results"][0]["columns"]
    return [{col: item["row"][idx] for idx, col in enumerate(cols)} for item in result["results"][0]["data"]]


def load_server_name_map(connection_file: Path) -> dict[str, list[dict[str, str]]]:
    uri, username, password = parse_connection_file(connection_file)
    client = Neo4jHttpClient(uri, username, password, "neo4j", 3, 1)
    result = client.run(
        """
        MATCH (n:KGNode)
        WHERE n.name IS NOT NULL
        RETURN n.name AS name, n.code AS code, n.entityType AS entityType, labels(n) AS labels
        """
    )
    mapping: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in result_rows(result):
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        mapping[name].append(
            {
                "code": str(row.get("code") or ""),
                "entityType": str(row.get("entityType") or ""),
                "labels": ",".join(row.get("labels") or []),
            }
        )
    return mapping


def entity_type_for_subject(kind: str) -> str:
    if kind == "category_container":
        return "DiseaseCategory"
    if kind == "therapy_or_management_section":
        return "TextbookSection"
    if kind in {"chapter", "overview_section"}:
        return "TextbookSection"
    # Unmatched concrete disease-like subjects are kept as TextbookSection to avoid duplicate Disease nodes.
    return "TextbookSection"


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", "", name or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build stable-id curated delta from C4 textbook skeleton candidates.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--connection-file", required=True, type=Path)
    parser.add_argument("--batch-id", default="CARD-SKELETON-20260709")
    parser.add_argument("--scope", default="cardiology_priority_four_textbook_skeleton")
    parser.add_argument("--nodes-file", default="阶段C4_合并结构化候选_nodes_20260709.jsonl")
    parser.add_argument("--relations-file", default="阶段C4_合并结构化候选_relations_20260709.jsonl")
    parser.add_argument("--audit-file", default="阶段C4_精修后G1深审计矩阵_20260709.csv")
    parser.add_argument(
        "--evidence-link-files",
        nargs="*",
        default=[
            "阶段C2_结构化候选_evidence_links_20260709.jsonl",
            "阶段C3_缺口定向补抽_evidence_links_20260709.jsonl",
            "阶段C4_剩余缺口精修_evidence_links_20260709.jsonl",
        ],
    )
    args = parser.parse_args()

    c4_nodes = read_jsonl(args.out_dir / args.nodes_file)
    c4_rels = read_jsonl(args.out_dir / args.relations_file)
    links = []
    for filename in args.evidence_link_files:
        path = args.out_dir / filename
        if path.exists():
            links.extend(read_jsonl(path))

    audit_rows = read_csv(args.out_dir / args.audit_file)
    subject_meta = {row["subject_name"]: row for row in audit_rows}

    server_map = load_server_name_map(args.connection_file)
    server_exact_by_type_name: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    server_codes: set[str] = set()
    for name, matches in server_map.items():
        for match in matches:
            entity_type = match.get("entityType", "")
            if match.get("code"):
                server_codes.add(match["code"])
            if entity_type:
                server_exact_by_type_name[(entity_type, name)].append(match)

    delta_nodes_by_code: dict[str, dict[str, Any]] = {}
    subject_code_by_name: dict[str, str] = {}
    subject_mapping_rows: list[dict[str, Any]] = []

    for subject_name, meta in sorted(subject_meta.items()):
        matches = server_map.get(subject_name, [])
        disease_matches = [m for m in matches if m.get("entityType") == "Disease" or "Disease" in m.get("labels", "")]
        category_matches = [m for m in matches if m.get("entityType") == "DiseaseCategory" or "DiseaseCategory" in m.get("labels", "")]
        if len(disease_matches) == 1:
            code = disease_matches[0]["code"]
            mapped = "server_existing_disease"
            entity_type = "Disease"
            node_upsert = False
        elif len(category_matches) == 1:
            code = category_matches[0]["code"]
            mapped = "server_existing_disease_category"
            entity_type = "DiseaseCategory"
            node_upsert = False
        else:
            kind = meta.get("subject_kind", "")
            entity_type = entity_type_for_subject(kind)
            code = stable_code("TXTSEC-CARD", meta.get("parent", ""), subject_name, kind)
            mapped = "local_textbook_subject"
            node_upsert = True
            delta_nodes_by_code[code] = {
                "code": code,
                "id": code,
                "name": subject_name,
                "entityType": entity_type,
                "description": f"《内科学（第10版）》心血管内科教材骨架对象：{subject_name}",
                "source_layer": "textbook_skeleton",
                "knowledge_layer": "textbook_skeleton",
                "skeleton_scope": args.scope,
                "subject_kind": kind,
                "parent_name": meta.get("parent", ""),
                "docx_start_para": meta.get("docx_start_para", ""),
                "docx_end_para": meta.get("docx_end_para", ""),
                "pdf_page_approx": meta.get("pdf_page_approx", ""),
                "batch_id": args.batch_id,
                "clinical_use_status": "knowledge_display_only",
                "formal_cdss_ready": False,
                "graph_version": "CARD-SKELETON-20260709-C5",
            }
        subject_code_by_name[subject_name] = code
        subject_mapping_rows.append(
            {
                "subject_name": subject_name,
                "parent": meta.get("parent", ""),
                "subject_kind": meta.get("subject_kind", ""),
                "mapped_code": code,
                "mapped_entityType": entity_type,
                "mapping_status": mapped,
                "node_upsert": str(node_upsert),
                "server_match_count": len(matches),
            }
        )

    # Clinical candidate nodes. Reuse existing same entityType+name server nodes to avoid duplicates.
    candidate_code_map: dict[str, str] = {}
    clinical_mapping_rows: list[dict[str, Any]] = []
    for node in c4_nodes:
        original_code = node.get("node_id") or stable_code("NODE-CARD", node.get("node_type", ""), node.get("name", ""))
        entity_type = node.get("node_type") or "ClinicalConcept"
        name = normalize_name(node.get("name", ""))
        if not name:
            continue
        server_matches = server_exact_by_type_name.get((entity_type, name), [])
        if len(server_matches) == 1:
            code = server_matches[0]["code"]
            mapping_status = "server_existing_same_type_name"
            node_upsert = False
        else:
            code = original_code
            mapping_status = "local_new_candidate"
            node_upsert = True
            delta_nodes_by_code.setdefault(
                code,
                {
                    "code": code,
                    "id": code,
                    "name": name,
                    "entityType": entity_type,
                    "standard_code": node.get("standard_code", ""),
                    "source_layer": "textbook_skeleton",
                    "knowledge_layer": "textbook_skeleton",
                    "skeleton_scope": args.scope,
                    "batch_id": args.batch_id,
                    "clinical_use_status": "knowledge_display_only",
                    "formal_cdss_ready": False,
                    "graph_version": "CARD-SKELETON-20260709-C5",
                },
            )
        candidate_code_map[original_code] = code
        clinical_mapping_rows.append(
            {
                "original_code": original_code,
                "name": name,
                "entityType": entity_type,
                "mapped_code": code,
                "mapping_status": mapping_status,
                "node_upsert": str(node_upsert),
                "server_match_count": len(server_matches),
            }
        )

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for link in links:
        evidence_id = link.get("evidence_id")
        if not evidence_id:
            continue
        evidence_by_id.setdefault(
            evidence_id,
            {
                "code": evidence_id,
                "id": evidence_id,
                "name": f"教材证据-{evidence_id[-8:]}",
                "entityType": "Evidence",
                "source_type": "authoritative_textbook",
                "source_name": "《内科学（第10版）》",
                "source_section_path": link.get("source_section_path", ""),
                "docx_para_start": link.get("docx_para_start", ""),
                "docx_para_end": link.get("docx_para_end", ""),
                "pdf_page_approx": link.get("pdf_page_approx", ""),
                "text_excerpt": link.get("fragment", ""),
                "source_layer": "textbook_skeleton",
                "knowledge_layer": "evidence",
                "batch_id": args.batch_id,
                "clinical_use_status": "evidence_trace_only",
                "formal_cdss_ready": False,
                "graph_version": "CARD-SKELETON-20260709-C5",
            },
        )

    for evidence in evidence_by_id.values():
        delta_nodes_by_code.setdefault(evidence["code"], evidence)

    delta_relations_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped_relations = []
    for rel in c4_rels:
        subject_name = rel.get("source_name", "")
        source_code = subject_code_by_name.get(subject_name)
        target_code = candidate_code_map.get(rel.get("target_id", ""), rel.get("target_id", ""))
        rel_type = rel.get("rel_type", "")
        if not (source_code and target_code and rel_type):
            skipped_relations.append({"reason": "missing_endpoint_or_type", "relation": rel})
            continue
        if target_code not in delta_nodes_by_code and target_code not in server_codes:
            # target is a curated candidate and should be in delta nodes; if not, skip and report.
            skipped_relations.append({"reason": "target_node_missing_from_delta", "relation": rel})
            continue
        key = (source_code, rel_type, target_code)
        delta_relations_by_key[key] = {
            "id": stable_code("REL-CARD-SKEL", *key),
            "source_code": source_code,
            "target_code": target_code,
            "relationType": rel_type,
            "source_name": subject_name,
            "target_name": rel.get("target_name", ""),
            "target_entityType": rel.get("target_type", ""),
            "evidence_ids": rel.get("evidence_ids", []),
            "source_layer": "textbook_skeleton",
            "knowledge_layer": "textbook_skeleton",
            "skeleton_scope": args.scope,
            "batch_id": args.batch_id,
            "clinical_use_status": "knowledge_display_only",
            "formal_cdss_ready": False,
            "graph_version": "CARD-SKELETON-20260709-C5",
        }

    # Evidence edges: clinical node -> Evidence
    for link in links:
        node_code = candidate_code_map.get(link.get("node_id", ""), link.get("node_id", ""))
        evidence_id = link.get("evidence_id", "")
        if not node_code or not evidence_id:
            continue
        key = (node_code, "HAS_EVIDENCE", evidence_id)
        delta_relations_by_key.setdefault(
            key,
            {
                "id": stable_code("REL-CARD-SKEL", *key),
                "source_code": node_code,
                "target_code": evidence_id,
                "relationType": "HAS_EVIDENCE",
                "source_name": link.get("node_name", ""),
                "target_name": f"教材证据-{evidence_id[-8:]}",
                "target_entityType": "Evidence",
                "source_layer": "textbook_skeleton",
                "knowledge_layer": "evidence",
                "skeleton_scope": args.scope,
                "batch_id": args.batch_id,
                "clinical_use_status": "evidence_trace_only",
                "formal_cdss_ready": False,
                "graph_version": "CARD-SKELETON-20260709-C5",
            },
        )

    delta_nodes = list(delta_nodes_by_code.values())
    delta_relations = list(delta_relations_by_key.values())
    evidence_nodes = list(evidence_by_id.values())

    write_jsonl(args.out_dir / "阶段C5_curated_delta_nodes_20260709.jsonl", delta_nodes)
    write_jsonl(args.out_dir / "阶段C5_curated_delta_relations_20260709.jsonl", delta_relations)
    write_jsonl(args.out_dir / "阶段C5_curated_delta_evidence_20260709.jsonl", evidence_nodes)

    with open(long_path(args.out_dir / "阶段C5_subject_mapping_20260709.csv"), "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(subject_mapping_rows[0].keys()))
        writer.writeheader()
        writer.writerows(subject_mapping_rows)
    if clinical_mapping_rows:
        with open(long_path(args.out_dir / "阶段C5_clinical_node_mapping_20260709.csv"), "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(clinical_mapping_rows[0].keys()))
            writer.writeheader()
            writer.writerows(clinical_mapping_rows)

    manifest = {
        "batch_id": args.batch_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scope": args.scope,
        "source_candidates": {
            "c4_nodes": len(c4_nodes),
            "c4_relations": len(c4_rels),
            "evidence_links": len(links),
        },
        "delta": {
            "nodes": len(delta_nodes),
            "relations": len(delta_relations),
            "evidence_nodes": len(evidence_nodes),
            "subject_mappings": len(subject_mapping_rows),
            "clinical_node_mappings": len(clinical_mapping_rows),
            "skipped_relations": len(skipped_relations),
        },
        "neo4j_written": False,
        "import_allowed": False,
        "next_required": "G2_preimport_audit",
        "files": [
            "阶段C5_curated_delta_nodes_20260709.jsonl",
            "阶段C5_curated_delta_relations_20260709.jsonl",
            "阶段C5_curated_delta_evidence_20260709.jsonl",
            "阶段C5_subject_mapping_20260709.csv",
            "阶段C5_clinical_node_mapping_20260709.csv",
        ],
    }
    write_text(args.out_dir / "阶段C5_curated_delta_manifest_20260709.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    if skipped_relations:
        write_text(args.out_dir / "阶段C5_skipped_relations_20260709.json", json.dumps(skipped_relations, ensure_ascii=False, indent=2))
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
