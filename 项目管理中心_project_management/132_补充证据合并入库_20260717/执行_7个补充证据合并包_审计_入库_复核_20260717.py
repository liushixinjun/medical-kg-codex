#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
7 个补充指南批次的证据合并包生成、本地审计、服务器入库和服务器复核。

设计原则：
1. 这 7 个批次是“补充证据”，不是完整新病种重建包。
2. 入库前必须先生成本地合并包并审计；审计有阻断项时不写 Neo4j。
3. Evidence 节点保留证据原文；关系只保留轻量索引，避免把大段证据数组重复写入每条关系。
4. 不物理删除服务器节点，不改历史批次文件。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


WORKDIR = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
SOURCE_ROOT = WORKDIR / "心血管内科文献集合"
OUT_DIR = WORKDIR / "项目管理中心_project_management" / "132_补充证据合并入库_20260717"
DB_LINK_FILE = WORKDIR / "图谱数据库链接.txt"
PACKAGE_ID = "SUPP-EVIDENCE-MERGE-20260717-001"
SCHEMA_VERSION = "V1.16"

BATCHES = [
    "20260717_冠心病ACS2025补充解析",
    "20260717_瓣膜病指南补充解析",
    "20260717_心律失常指南补充解析",
    "20260717_心肌病ESC2023补充解析",
    "20260717_结构性先心病介入补充解析",
    "20260717_心衰LVAD右心衰补充解析",
    "20260717_高血压LVAD补充解析",
]

DIRECTORY_ENTITY_TYPES = {"Specialty", "DiseaseCategory", "DiseaseSubcategory", "DiseaseClassification"}
SAFE_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]*$")
SAFE_LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
SAFE_REL_RE = re.compile(r"^[a-z][a-z0-9_]*$")

SKIP_NODE_KEYS = {
    "raw_text",
    "full_text",
    "ocr_text",
}

SKIP_REL_KEYS = {
    # 大数组已由 Evidence 节点承接，关系层只保留 evidence_ids/source_names 等轻量索引。
    "provenance_records_json",
    "evidence_text",
    "raw_text",
    "full_text",
    "ocr_text",
}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def is_local_path_text(value: str) -> bool:
    return bool(re.search(r"[A-Za-z]:\\", value)) or value.startswith("file:/")


def normalize_value(value: Any, *, max_json_len: int = 8000) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and is_local_path_text(value):
            return None
        return value
    if isinstance(value, list):
        if all(isinstance(x, (str, int, float, bool)) or x is None for x in value):
            cleaned = [x for x in value if x is not None and not (isinstance(x, str) and is_local_path_text(x))]
            return cleaned
        text = json.dumps(value, ensure_ascii=False)
        return text if len(text) <= max_json_len else None
    if isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False)
        return text if len(text) <= max_json_len else None
    return str(value)


def clean_props(row: dict[str, Any], *, is_relation: bool) -> dict[str, Any]:
    skip = SKIP_REL_KEYS if is_relation else SKIP_NODE_KEYS
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        if key in skip:
            continue
        normalized = normalize_value(value)
        if normalized is not None:
            cleaned[key] = normalized
    return cleaned


def merge_node(existing: dict[str, Any] | None, incoming: dict[str, Any], batch_name: str) -> dict[str, Any]:
    node = dict(existing or {})
    incoming = dict(incoming)
    incoming["last_merge_package_id"] = PACKAGE_ID
    incoming["last_merge_batch_name"] = batch_name
    incoming["merge_import_scope"] = "补充证据合并"
    incoming["schema_version"] = incoming.get("schema_version") or SCHEMA_VERSION
    incoming["review_status"] = incoming.get("review_status") or "approved"

    if not node:
        node.update(incoming)
    else:
        # 不用补充指南覆盖既有主数据名称；只补空字段和证据来源字段。
        for key, value in incoming.items():
            if key in {"name", "preferred_name", "display_name"} and node.get(key):
                continue
            if key == "aliases":
                old_aliases = node.get("aliases") or []
                if isinstance(old_aliases, str):
                    old_aliases = [old_aliases]
                new_aliases = value if isinstance(value, list) else ([value] if value else [])
                node["aliases"] = sorted({str(x) for x in old_aliases + new_aliases if str(x).strip()})
                continue
            if not node.get(key):
                node[key] = value
        node["last_merge_package_id"] = PACKAGE_ID
        node["merge_import_scope"] = "补充证据合并"

    source_batches = node.get("source_batch_ids") or []
    if isinstance(source_batches, str):
        source_batches = [source_batches]
    source_batches.append(batch_name)
    if node.get("batch_id"):
        source_batches.append(str(node["batch_id"]))
    node["source_batch_ids"] = sorted({x for x in source_batches if x})
    return clean_props(node, is_relation=False)


def merge_relation(existing: dict[str, Any] | None, incoming: dict[str, Any], batch_name: str) -> dict[str, Any]:
    rel = dict(existing or {})
    incoming = clean_props(incoming, is_relation=True)
    incoming["last_merge_package_id"] = PACKAGE_ID
    incoming["last_merge_batch_name"] = batch_name
    incoming["merge_import_scope"] = "补充证据合并"
    incoming["schema_version"] = incoming.get("schema_version") or SCHEMA_VERSION
    incoming["review_status"] = incoming.get("review_status") or "approved"

    if not rel:
        rel.update(incoming)
    else:
        for key, value in incoming.items():
            if key in {"evidence_ids", "document_ids", "source_names", "source_types"}:
                old = rel.get(key) or []
                if isinstance(old, str):
                    old = [old]
                new = value if isinstance(value, list) else ([value] if value else [])
                rel[key] = sorted({str(x) for x in old + new if str(x).strip()})
            elif not rel.get(key):
                rel[key] = value
        rel["last_merge_package_id"] = PACKAGE_ID
        rel["merge_import_scope"] = "补充证据合并"

    source_batches = rel.get("source_batch_ids") or []
    if isinstance(source_batches, str):
        source_batches = [source_batches]
    source_batches.append(batch_name)
    if rel.get("batch_id"):
        source_batches.append(str(rel["batch_id"]))
    rel["source_batch_ids"] = sorted({x for x in source_batches if x})
    rel["id"] = rel.get("id") or stable_id("REL", rel.get("source_code", ""), rel.get("relationType", ""), rel.get("target_code", ""))
    return clean_props(rel, is_relation=True)


def build_package_for_batches(batch_names: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes_by_code: dict[str, dict[str, Any]] = {}
    relations_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    summary_rows: list[dict[str, Any]] = []

    for batch_name in batch_names:
        batch_dir = SOURCE_ROOT / batch_name / "05_data_instance"
        nodes = read_jsonl(batch_dir / "nodes_final.jsonl")
        rels = read_jsonl(batch_dir / "relations_final.jsonl")

        for node in nodes:
            code = str(node.get("code") or "").strip()
            if not code:
                continue
            nodes_by_code[code] = merge_node(nodes_by_code.get(code), node, batch_name)

        for rel in rels:
            source = str(rel.get("source_code") or "").strip()
            rel_type = str(rel.get("relationType") or "").strip()
            target = str(rel.get("target_code") or "").strip()
            if not source or not rel_type or not target:
                continue
            key = (source, rel_type, target)
            relations_by_key[key] = merge_relation(relations_by_key.get(key), rel, batch_name)

        summary_rows.append(
            {
                "批次": batch_name,
                "原始节点数": len(nodes),
                "原始关系数": len(rels),
                "原始Evidence节点数": sum(1 for n in nodes if n.get("entityType") == "Evidence"),
                "原始Guideline节点数": sum(1 for n in nodes if n.get("entityType") == "Guideline"),
            }
        )

    nodes_out = sorted(nodes_by_code.values(), key=lambda x: str(x.get("code", "")))
    rels_out = sorted(relations_by_key.values(), key=lambda x: (str(x.get("source_code", "")), str(x.get("relationType", "")), str(x.get("target_code", ""))))
    return nodes_out, rels_out, summary_rows


def audit_package(nodes: list[dict[str, Any]], rels: list[dict[str, Any]], *, scope: str) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    node_codes = [str(n.get("code") or "").strip() for n in nodes]
    code_counts = Counter(node_codes)
    node_by_code = {str(n.get("code") or "").strip(): n for n in nodes if str(n.get("code") or "").strip()}

    for node in nodes:
        code = str(node.get("code") or "").strip()
        etype = str(node.get("entityType") or "").strip()
        display = str(node.get("display_name") or node.get("preferred_name") or node.get("name") or "").strip()
        if not code:
            issues.append({"级别": "阻断", "类型": "节点缺code", "对象": display, "说明": "节点没有唯一编码"})
        elif not SAFE_CODE_RE.match(code):
            issues.append({"级别": "阻断", "类型": "节点code格式非法", "对象": code, "说明": "code 不能使用中文或空格"})
        if not etype:
            issues.append({"级别": "阻断", "类型": "节点缺实体类型", "对象": code, "说明": "entityType 为空"})
        elif not SAFE_LABEL_RE.match(etype):
            issues.append({"级别": "阻断", "类型": "实体类型格式非法", "对象": f"{code}/{etype}", "说明": "实体类型必须能作为 Neo4j 标签"})
        if not display:
            issues.append({"级别": "阻断", "类型": "节点缺中文展示名", "对象": code, "说明": "name/preferred_name/display_name 全空"})
        if etype in DIRECTORY_ENTITY_TYPES and code and not SAFE_CODE_RE.match(code):
            issues.append({"级别": "阻断", "类型": "目录节点编码异常", "对象": code, "说明": "目录节点不得用中文名称当编码"})
        for key, value in node.items():
            if isinstance(value, str) and is_local_path_text(value):
                issues.append({"级别": "阻断", "类型": "节点含本地路径", "对象": code, "说明": key})

    for code, count in code_counts.items():
        if code and count > 1:
            issues.append({"级别": "阻断", "类型": "节点code重复", "对象": code, "说明": f"重复 {count} 次"})

    rel_keys = Counter()
    for rel in rels:
        source = str(rel.get("source_code") or "").strip()
        rel_type = str(rel.get("relationType") or "").strip()
        target = str(rel.get("target_code") or "").strip()
        rel_keys[(source, rel_type, target)] += 1
        if not source or not target or not rel_type:
            issues.append({"级别": "阻断", "类型": "关系端点或类型为空", "对象": rel.get("id", ""), "说明": f"{source}-{rel_type}->{target}"})
        if rel_type and not SAFE_REL_RE.match(rel_type):
            issues.append({"级别": "阻断", "类型": "关系类型格式非法", "对象": rel_type, "说明": "关系类型必须为小写字母、数字、下划线"})
        if source and source not in node_by_code:
            issues.append({"级别": "阻断", "类型": "关系源节点缺失", "对象": source, "说明": f"{source}-{rel_type}->{target}"})
        if target and target not in node_by_code:
            issues.append({"级别": "阻断", "类型": "关系目标节点缺失", "对象": target, "说明": f"{source}-{rel_type}->{target}"})
        for key, value in rel.items():
            if isinstance(value, str) and is_local_path_text(value):
                issues.append({"级别": "阻断", "类型": "关系含本地路径", "对象": rel.get("id", ""), "说明": key})

    for (source, rel_type, target), count in rel_keys.items():
        if source and target and rel_type and count > 1:
            issues.append({"级别": "阻断", "类型": "关系重复", "对象": f"{source}-{rel_type}->{target}", "说明": f"重复 {count} 次"})

    evidence_nodes = [n for n in nodes if n.get("entityType") == "Evidence"]
    evidence_missing_text = [
        n.get("code")
        for n in evidence_nodes
        if not str(n.get("evidence_text") or n.get("summary") or n.get("text") or "").strip()
    ]
    for code in evidence_missing_text[:200]:
        issues.append({"级别": "阻断", "类型": "Evidence缺证据原文", "对象": code, "说明": "证据节点缺 evidence_text/summary/text"})

    type_counter = Counter(str(n.get("entityType") or "") for n in nodes)
    rel_counter = Counter(str(r.get("relationType") or "") for r in rels)
    blockers = [i for i in issues if i.get("级别") == "阻断"]
    return {
        "scope": scope,
        "generated_at": now_text(),
        "package_id": PACKAGE_ID,
        "node_count": len(nodes),
        "relation_count": len(rels),
        "entity_type_counts": dict(sorted(type_counter.items())),
        "relation_type_counts": dict(sorted(rel_counter.items())),
        "evidence_node_count": len(evidence_nodes),
        "evidence_missing_text_count": len(evidence_missing_text),
        "issue_count": len(issues),
        "blocking_count": len(blockers),
        "import_allowed": len(blockers) == 0,
        "issues": issues,
    }


def create_packages() -> dict[str, Any]:
    per_batch_root = OUT_DIR / "01_单批次补充证据合并包"
    global_root = OUT_DIR / "02_全量补充证据合并包"
    audit_root = OUT_DIR / "03_本地审计"
    per_batch_root.mkdir(parents=True, exist_ok=True)
    global_root.mkdir(parents=True, exist_ok=True)
    audit_root.mkdir(parents=True, exist_ok=True)

    all_summary: list[dict[str, Any]] = []
    per_batch_audits: list[dict[str, Any]] = []
    for batch in BATCHES:
        nodes, rels, summary_rows = build_package_for_batches([batch])
        safe_dir = per_batch_root / batch
        write_jsonl(safe_dir / "nodes_merge_delta.jsonl", nodes)
        write_jsonl(safe_dir / "relations_merge_delta.jsonl", rels)
        audit = audit_package(nodes, rels, scope=batch)
        per_batch_audits.append(audit)
        (safe_dir / "local_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        write_csv(
            safe_dir / "local_audit_issues.csv",
            audit["issues"],
            ["级别", "类型", "对象", "说明"],
        )
        row = summary_rows[0]
        row.update({"合并后节点数": len(nodes), "合并后关系数": len(rels), "本地审计阻断数": audit["blocking_count"]})
        all_summary.append(row)

    global_nodes, global_rels, _ = build_package_for_batches(BATCHES)
    write_jsonl(global_root / "nodes_merge_delta.jsonl", global_nodes)
    write_jsonl(global_root / "relations_merge_delta.jsonl", global_rels)
    global_audit = audit_package(global_nodes, global_rels, scope="7个补充批次全量合并")
    (audit_root / "local_audit_global.json").write_text(json.dumps(global_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(audit_root / "local_audit_global_issues.csv", global_audit["issues"], ["级别", "类型", "对象", "说明"])
    write_csv(
        OUT_DIR / "00_7个补充证据合并包_summary.csv",
        all_summary,
        ["批次", "原始节点数", "原始关系数", "原始Evidence节点数", "原始Guideline节点数", "合并后节点数", "合并后关系数", "本地审计阻断数"],
    )
    return {
        "generated_at": now_text(),
        "package_id": PACKAGE_ID,
        "per_batch": all_summary,
        "global_node_count": len(global_nodes),
        "global_relation_count": len(global_rels),
        "global_blocking_count": global_audit["blocking_count"],
        "global_import_allowed": global_audit["import_allowed"],
        "per_batch_blocking_count": sum(a["blocking_count"] for a in per_batch_audits),
    }


def parse_db_link() -> tuple[str, str, str]:
    text = DB_LINK_FILE.read_text(encoding="utf-8")
    bolt_match = re.search(r"bolt://[^\s，,;；]+", text, re.I)
    if not bolt_match:
        raise RuntimeError("图谱数据库链接.txt 未解析到 bolt 地址")
    username_match = re.search(r"(?:用户名|username|NEO4J_USERNAME)\s*[:：=]\s*([^\s，,;；]+)", text, re.I)
    password_match = re.search(r"(?:密码|password|NEO4J_PASSWORD)\s*[:：=]\s*([^\s，,;；]+)", text, re.I)
    username = username_match.group(1) if username_match else os.environ.get("NEO4J_USERNAME", "neo4j")
    password = password_match.group(1) if password_match else os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        raise RuntimeError("未解析到 Neo4j 密码")
    return bolt_match.group(0), username, password


def import_to_neo4j() -> dict[str, Any]:
    global_root = OUT_DIR / "02_全量补充证据合并包"
    audit_path = OUT_DIR / "03_本地审计" / "local_audit_global.json"
    if not audit_path.exists():
        raise RuntimeError("缺少本地审计结果，请先运行 --mode prepare")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if not audit.get("import_allowed"):
        raise RuntimeError(f"本地审计未通过，阻断数={audit.get('blocking_count')}")

    nodes = read_jsonl(global_root / "nodes_merge_delta.jsonl")
    rels = read_jsonl(global_root / "relations_merge_delta.jsonl")
    bolt, username, password = parse_db_link()

    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError("项目 Python 环境缺少 neo4j 包，请安装到 D:\\Program Files Ai\\python-venvs\\medical-kg") from exc

    node_imported = 0
    rel_imported = 0
    rel_skipped_missing_endpoint = 0
    before_counts: dict[str, Any] = {}
    after_counts: dict[str, Any] = {}

    with GraphDatabase.driver(bolt, auth=(username, password)) as driver:
        with driver.session(database="neo4j") as session:
            # 性能硬前提：所有节点合并和关系端点匹配都依赖 KGNode.code。
            # 没有索引时，MERGE/MATCH 会随图谱变大显著变慢。
            session.run("CREATE INDEX kg_node_code IF NOT EXISTS FOR (n:KGNode) ON (n.code)").consume()
            try:
                session.run("CALL db.awaitIndexes(300)").consume()
            except Exception:
                # 兼容旧版 Neo4j：索引创建请求已提交，后续 MERGE 仍可继续。
                pass

            before_counts = session.run(
                """
                MATCH (n:KGNode)
                WITH count(n) AS nodes
                MATCH ()-[r]->()
                RETURN nodes, count(r) AS rels
                """
            ).single().data()

            node_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for node in nodes:
                code = str(node.get("code") or "").strip()
                etype = str(node.get("entityType") or "").strip()
                if not code or not etype or not SAFE_LABEL_RE.match(etype):
                    continue
                node_groups[etype].append({"code": code, "props": clean_props(node, is_relation=False)})

            for etype, rows in node_groups.items():
                if etype == "Disease":
                    query = f"""
                    UNWIND $rows AS row
                    MERGE (n:KGNode {{code:row.code}})
                    ON CREATE SET n += row.props
                    SET n:`{etype}`
                    SET n.last_merge_package_id = $package_id,
                        n.merge_import_scope = '补充证据合并'
                    RETURN count(n) AS c
                    """
                else:
                    query = f"""
                    UNWIND $rows AS row
                    MERGE (n:KGNode {{code:row.code}})
                    SET n:`{etype}`
                    SET n += row.props
                    SET n.last_merge_package_id = $package_id,
                        n.merge_import_scope = '补充证据合并'
                    RETURN count(n) AS c
                    """
                for i in range(0, len(rows), 500):
                    rec = session.run(query, rows=rows[i:i + 500], package_id=PACKAGE_ID).single()
                    node_imported += int(rec["c"]) if rec else 0

            rel_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for rel in rels:
                source = str(rel.get("source_code") or "").strip()
                target = str(rel.get("target_code") or "").strip()
                rel_type = str(rel.get("relationType") or "").strip()
                if not source or not target or not rel_type or not SAFE_REL_RE.match(rel_type):
                    continue
                rel_groups[rel_type].append(
                    {
                        "source": source,
                        "target": target,
                        "props": clean_props(rel, is_relation=True),
                    }
                )

            for rel_type, rows in rel_groups.items():
                query = f"""
                UNWIND $rows AS row
                MATCH (a:KGNode {{code:row.source}})
                MATCH (b:KGNode {{code:row.target}})
                MERGE (a)-[r:`{rel_type}`]->(b)
                REMOVE r.evidence_text, r.provenance_records_json, r.raw_text, r.full_text, r.ocr_text
                SET r += row.props
                SET r.last_merge_package_id = $package_id,
                    r.merge_import_scope = '补充证据合并'
                RETURN count(r) AS c
                """
                for i in range(0, len(rows), 500):
                    batch = rows[i:i + 500]
                    rec = session.run(query, rows=batch, package_id=PACKAGE_ID).single()
                    count = int(rec["c"]) if rec else 0
                    rel_imported += count
                    rel_skipped_missing_endpoint += len(batch) - count

            after_counts = session.run(
                """
                MATCH (n:KGNode)
                WITH count(n) AS nodes
                MATCH ()-[r]->()
                RETURN nodes, count(r) AS rels
                """
            ).single().data()

    result = {
        "generated_at": now_text(),
        "package_id": PACKAGE_ID,
        "neo4j_written": True,
        "node_rows_processed": node_imported,
        "relation_rows_processed": rel_imported,
        "relation_rows_skipped_missing_endpoint": rel_skipped_missing_endpoint,
        "before_counts": before_counts,
        "after_counts": after_counts,
    }
    (OUT_DIR / "04_入库结果_import_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def verify_server() -> dict[str, Any]:
    bolt, username, password = parse_db_link()
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError("项目 Python 环境缺少 neo4j 包") from exc

    with GraphDatabase.driver(bolt, auth=(username, password)) as driver:
        with driver.session(database="neo4j") as session:
            row = session.run(
                """
                MATCH (n:KGNode)
                WHERE n.last_merge_package_id = $package_id
                WITH count(n) AS imported_nodes,
                     sum(CASE WHEN n.entityType IS NULL OR n.entityType = '' THEN 1 ELSE 0 END) AS missing_entity_type,
                     sum(CASE WHEN coalesce(n.display_name,n.preferred_name,n.name,'') = '' THEN 1 ELSE 0 END) AS missing_name,
                     sum(CASE WHEN n.entityType = 'Evidence' AND coalesce(n.evidence_text,'') = '' THEN 1 ELSE 0 END) AS evidence_missing_text
                MATCH ()-[r]->()
                WHERE r.last_merge_package_id = $package_id
                RETURN imported_nodes, missing_entity_type, missing_name, evidence_missing_text, count(r) AS imported_relations
                """,
                package_id=PACKAGE_ID,
            ).single().data()

            duplicate_codes = session.run(
                """
                MATCH (n:KGNode)
                WHERE n.last_merge_package_id = $package_id
                WITH n.code AS code, count(n) AS c
                WHERE code IS NOT NULL AND c > 1
                RETURN count(*) AS duplicate_code_groups
                """,
                package_id=PACKAGE_ID,
            ).single()["duplicate_code_groups"]

            rel_by_type = session.run(
                """
                MATCH ()-[r]->()
                WHERE r.last_merge_package_id = $package_id
                RETURN type(r) AS relation_type, count(r) AS count
                ORDER BY count DESC
                LIMIT 30
                """,
                package_id=PACKAGE_ID,
            ).data()

            relation_evidence_text_count = session.run(
                """
                MATCH ()-[r]->()
                WHERE r.last_merge_package_id = $package_id
                  AND r.evidence_text IS NOT NULL
                RETURN count(r) AS count
                """,
                package_id=PACKAGE_ID,
            ).single()["count"]

            node_by_type = session.run(
                """
                MATCH (n:KGNode)
                WHERE n.last_merge_package_id = $package_id
                RETURN n.entityType AS entity_type, count(n) AS count
                ORDER BY count DESC
                LIMIT 30
                """,
                package_id=PACKAGE_ID,
            ).data()

            index_status = session.run(
                """
                SHOW INDEXES
                YIELD name, state, labelsOrTypes, properties
                WHERE name = 'kg_node_code'
                RETURN name, state, labelsOrTypes, properties
                """
            ).data()

    blockers = []
    if row.get("missing_entity_type"):
        blockers.append("存在缺实体类型的入库节点")
    if row.get("missing_name"):
        blockers.append("存在缺中文展示名的入库节点")
    if row.get("evidence_missing_text"):
        blockers.append("存在缺证据原文的 Evidence 节点")
    if duplicate_codes:
        blockers.append("存在重复 code 节点")
    if relation_evidence_text_count:
        blockers.append("本轮关系层仍残留 evidence_text 大字段")

    result = {
        "generated_at": now_text(),
        "package_id": PACKAGE_ID,
        "server_verify_passed": not blockers,
        "blockers": blockers,
        "summary": row,
        "duplicate_code_groups": duplicate_codes,
        "relation_evidence_text_count": relation_evidence_text_count,
        "kg_node_code_index": index_status,
        "node_by_type_top30": node_by_type,
        "relation_by_type_top30": rel_by_type,
    }
    (OUT_DIR / "05_服务器复核_server_verify.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def write_markdown_report(prepare_result: dict[str, Any], import_result: dict[str, Any] | None, server_result: dict[str, Any] | None) -> None:
    lines = [
        "# 7个补充证据合并入库执行报告",
        "",
        f"- 生成时间：{now_text()}",
        f"- 合并包编号：{PACKAGE_ID}",
        f"- 全量合并节点数：{prepare_result.get('global_node_count')}",
        f"- 全量合并关系数：{prepare_result.get('global_relation_count')}",
        f"- 本地审计阻断数：{prepare_result.get('global_blocking_count')}",
        f"- 本地是否允许入库：{'是' if prepare_result.get('global_import_allowed') else '否'}",
        "",
        "## 7个单批次合并包",
        "",
        "| 批次 | 原始节点 | 原始关系 | 合并后节点 | 合并后关系 | 本地审计阻断 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in prepare_result.get("per_batch", []):
        lines.append(
            f"| {row.get('批次')} | {row.get('原始节点数')} | {row.get('原始关系数')} | "
            f"{row.get('合并后节点数')} | {row.get('合并后关系数')} | {row.get('本地审计阻断数')} |"
        )
    if import_result:
        lines.extend(
            [
                "",
                "## 服务器写入结果",
                "",
                f"- 是否写库：{'是' if import_result.get('neo4j_written') else '否'}",
                f"- 处理节点行数：{import_result.get('node_rows_processed')}",
                f"- 处理关系行数：{import_result.get('relation_rows_processed')}",
                f"- 因端点缺失跳过关系：{import_result.get('relation_rows_skipped_missing_endpoint')}",
                f"- 写入前：{import_result.get('before_counts')}",
                f"- 写入后：{import_result.get('after_counts')}",
            ]
        )
    if server_result:
        lines.extend(
            [
                "",
                "## 服务器复核",
                "",
                f"- 复核是否通过：{'是' if server_result.get('server_verify_passed') else '否'}",
                f"- 阻断项：{server_result.get('blockers')}",
                f"- 服务器统计：{server_result.get('summary')}",
                f"- 本轮关系层残留 evidence_text 大字段：{server_result.get('relation_evidence_text_count')}",
                f"- KGNode.code 索引状态：{server_result.get('kg_node_code_index')}",
            ]
        )
    (OUT_DIR / "07_执行报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["prepare", "apply", "verify", "all"], default="prepare")
    args = parser.parse_args()

    prepare_result: dict[str, Any] | None = None
    import_result: dict[str, Any] | None = None
    server_result: dict[str, Any] | None = None

    if args.mode in {"prepare", "all"}:
        prepare_result = create_packages()
        (OUT_DIR / "06_prepare_result.json").write_text(json.dumps(prepare_result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        prepare_result_path = OUT_DIR / "06_prepare_result.json"
        if prepare_result_path.exists():
            prepare_result = json.loads(prepare_result_path.read_text(encoding="utf-8"))
        import_result_path = OUT_DIR / "04_入库结果_import_result.json"
        if import_result_path.exists():
            import_result = json.loads(import_result_path.read_text(encoding="utf-8"))

    if args.mode in {"apply", "all"}:
        import_result = import_to_neo4j()
        server_result = verify_server()
    elif args.mode == "verify":
        server_result = verify_server()

    if prepare_result:
        write_markdown_report(prepare_result, import_result, server_result)

    print(json.dumps(
        {
            "mode": args.mode,
            "package_id": PACKAGE_ID,
            "prepare": prepare_result,
            "import": import_result,
            "server_verify": server_result,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
