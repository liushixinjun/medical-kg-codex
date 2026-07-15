from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import Any


BATCH_ID = "20260715_肺动脉高压正式解析"
SCHEMA_VERSION = "V1.15"

POLLUTED_RULE_CODES = {
    "RULE-CARD-007E3BFEDE80",
    "RULE-CARD-13F8D7C28C62",
    "RULE-CARD-17DC619B9005",
    "RULE-CARD-1B210B9DA745",
    "RULE-CARD-1E72AAEF9AD8",
    "RULE-CARD-21A459EA4ED1",
    "RULE-CARD-35D17D9AC5B4",
    "RULE-CARD-3FD3788781D9",
    "RULE-CARD-414F28E8AE1F",
    "RULE-CARD-4A5B2470CB74",
    "RULE-CARD-57DE30BE8573",
    "RULE-CARD-5C12A67F6CB8",
    "RULE-CARD-66E6E80AB949",
    "RULE-CARD-9FE3D21A1AD2",
    "RULE-CARD-A4615E44AA95",
    "RULE-CARD-B5A4B02A4ED0",
    "RULE-CARD-BEE160A539EA",
    "RULE-CARD-C554DBB0AD0E",
    "RULE-CARD-D9181B00418A",
    "RULE-CARD-DB69D4047328",
    "RULE-CARD-DF18B3653A54",
    "RULE-CARD-DF6352451D09",
    "RULE-CARD-E4640F020467",
    "RULE-CARD-E6944A0E53F7",
    "RULE-CARD-F756FB8F4B32",
}

DIAGNOSIS_COMPONENTS = [
    {
        "criteria_code": "DXC-CARD-6B7C6491A6D0",
        "component_code": "DXCOMP-CARD-PH-HEMODYNAMIC-MPAP",
        "name": "肺动脉高压血流动力学诊断明细",
        "rule_text": "静息状态下经右心导管检查测得平均肺动脉压升高；国内本批次采用指南原文的 mPAP≥25mmHg 标准，并需结合病因和临床分类进一步判断。",
        "evidence_code": "EVD-32AE0BE55B940A16C9F6-PH",
    },
    {
        "criteria_code": "DXC-CARD-BBA204BBB6C9",
        "component_code": "DXCOMP-CARD-PH-PAH-HEMODYNAMIC",
        "name": "动脉性肺动脉高压血流动力学诊断明细",
        "rule_text": "在肺动脉高压基础上，右心导管提示 PAWP≤15mmHg 且 PVR>3WU，符合前毛细血管性肺高压特征时，提示动脉性肺动脉高压可能性大，并需排除其他病因。",
        "evidence_code": "EVD-31A4791BF118D0054FA5-HPAH",
    },
    {
        "criteria_code": "DXC-CARD-066647B0A202",
        "component_code": "DXCOMP-CARD-PH-HPAH-PAH-FAMILY-GENE",
        "name": "遗传性肺动脉高压诊断明细",
        "rule_text": "符合动脉性肺动脉高压血流动力学标准，并结合家族史、遗传背景或相关基因检测线索，支持遗传性肺动脉高压诊断；仍需排除继发病因。",
        "evidence_code": "EVD-31A4791BF118D0054FA5-HPAH",
    },
    {
        "criteria_code": "DXC-CARD-AD2399CBCA8F",
        "component_code": "DXCOMP-CARD-PH-IPAH-EXCLUSION",
        "name": "特发性肺动脉高压诊断明细",
        "rule_text": "符合动脉性肺动脉高压血流动力学标准，且未发现明确相关疾病、药物毒物暴露、遗传或其他继发原因时，支持特发性肺动脉高压诊断。",
        "evidence_code": "EVD-E10D9278F7DD3765D010-IPAH",
    },
    {
        "criteria_code": "DXC-CARD-341738CD8C00",
        "component_code": "DXCOMP-CARD-PH-CHD-PAH",
        "name": "先天性心脏病相关肺动脉高压诊断明细",
        "rule_text": "存在先天性心脏病或体-肺分流相关背景，并在肺高压/动脉性肺动脉高压血流动力学基础上，按成人先天性心脏病相关肺高压分类进行诊断。",
        "evidence_code": "EVD-12EA433B49171AC127AF-CHD",
    },
    {
        "criteria_code": "DXC-CARD-73939668A2C4",
        "component_code": "DXCOMP-CARD-PH-CTD-PAH",
        "name": "结缔组织病相关肺动脉高压诊断明细",
        "rule_text": "存在结缔组织病背景或相关免疫学/临床证据，并符合肺动脉高压或动脉性肺动脉高压血流动力学标准时，支持结缔组织病相关肺动脉高压诊断。",
        "evidence_code": "EVD-E3D10C5C889C96A51478-CTD",
    },
    {
        "criteria_code": "DXC-CARD-A523538ADCED",
        "component_code": "DXCOMP-CARD-PH-CTEPH-IMAGING-RHC",
        "name": "慢性血栓栓塞性肺动脉高压诊断明细",
        "rule_text": "疑似或确诊慢性血栓栓塞性肺动脉高压时，应结合 V/Q 显像、CTPA、右心导管检查和肺动脉造影等系统评估，明确慢性血栓栓塞性病变与血流动力学异常。",
        "evidence_code": "EVD-7F7C12EEFD78B78B074E-CTEPH",
    },
]


def stable_relation_id(source: str, relation_type: str, target: str) -> str:
    return "REL-" + hashlib.sha1(f"{source}|{relation_type}|{target}".encode("utf-8")).hexdigest()[:20].upper()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def common_node(code: str, name: str, entity_type: str, rule_text: str = "") -> dict[str, Any]:
    return {
        "id": f"KG_{entity_type.upper()}_{code}",
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": "临床实体",
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "merge_status": "validated",
        "review_status": "approved",
        "clinical_review_status": "clinical_batch_signed_off",
        "language": "zh-CN",
        "rule_text": rule_text,
        "content_hash": hashlib.sha1(f"{code}|{name}|{entity_type}|{rule_text}".encode("utf-8")).hexdigest(),
    }


def common_relation(source: str, relation_type: str, target: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence = evidence or {}
    return {
        "id": stable_relation_id(source, relation_type, target),
        "source_code": source,
        "relationType": relation_type,
        "relation_type": relation_type,
        "target_code": target,
        "relationCategory": "diagnosis" if relation_type == "has_diagnostic_component" else "evidence",
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "merge_status": "validated",
        "review_status": "approved",
        "clinical_review_status": "clinical_batch_signed_off",
        "conflict_status": "none",
        "polarity": "positive",
        "confidence": 1.0,
        "evidence_id": evidence.get("code") or evidence.get("evidence_id") or "",
        "evidence_ids": [evidence.get("code") or evidence.get("evidence_id")] if (evidence.get("code") or evidence.get("evidence_id")) else [],
        "source_name": evidence.get("source_name", ""),
        "source_page": evidence.get("source_page", ""),
        "source_section": evidence.get("source_section", ""),
        "source_type": evidence.get("source_type", ""),
        "evidence_text": evidence.get("evidence_text", ""),
        "recommendation_class": "N/A",
        "evidence_level": "N/A",
    }


class Neo4jClient:
    def __init__(self, http_root: str, username: str, password: str) -> None:
        self.url = http_root.rstrip("/") + "/db/neo4j/tx/commit"
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        self.headers = {"Content-Type": "application/json", "Authorization": "Basic " + token}

    def run(self, statement: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        payload = json.dumps({"statements": [{"statement": statement, "parameters": parameters or {}}]}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=payload, headers=self.headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if result.get("errors"):
            raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False))
        res = result["results"][0]
        cols = res["columns"]
        return [dict(zip(cols, item["row"])) for item in res["data"]]


def delete_polluted_server_nodes(http_root: str, username: str, password: str) -> int:
    client = Neo4jClient(http_root, username, password)
    rows = client.run(
        """
        MATCH (n:KGNode {batch_id:$batch_id})
        WHERE n.code IN $codes
        WITH collect(n) AS nodes
        FOREACH (n IN nodes | DETACH DELETE n)
        RETURN size(nodes) AS deleted_count
        """,
        {"batch_id": BATCH_ID, "codes": sorted(POLLUTED_RULE_CODES)},
    )
    return int(rows[0]["deleted_count"] or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="肺动脉高压批次入库后质量收口：删除污染规则，补诊断标准明细。")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--apply-db", action="store_true")
    parser.add_argument("--uri", default=os.environ.get("NEO4J_HTTP", "http://192.168.3.27:7474"))
    parser.add_argument("--username", default=os.environ.get("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", ""))
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir)
    data_dir = batch_dir / "05_data_instance"
    nodes_path = data_dir / "nodes_final.jsonl"
    relations_path = data_dir / "relations_final.jsonl"
    nodes = load_jsonl(nodes_path)
    relations = load_jsonl(relations_path)

    before_node_count = len(nodes)
    before_relation_count = len(relations)

    removed_local_nodes = sum(1 for row in nodes if row.get("code") in POLLUTED_RULE_CODES)
    nodes = [row for row in nodes if row.get("code") not in POLLUTED_RULE_CODES]
    removed_local_relations = sum(
        1
        for row in relations
        if row.get("source_code") in POLLUTED_RULE_CODES or row.get("target_code") in POLLUTED_RULE_CODES
    )
    relations = [
        row
        for row in relations
        if row.get("source_code") not in POLLUTED_RULE_CODES and row.get("target_code") not in POLLUTED_RULE_CODES
    ]

    node_by_code = {row["code"]: row for row in nodes}
    relation_by_key = {(row.get("source_code"), row.get("relationType"), row.get("target_code")) for row in relations}

    for item in DIAGNOSIS_COMPONENTS:
        evidence = node_by_code.get(item["evidence_code"], {})
        if item["component_code"] not in node_by_code:
            component = common_node(
                item["component_code"],
                item["name"],
                "DiagnosisCriteriaComponent",
                item["rule_text"],
            )
            component["source_evidence_id"] = item["evidence_code"]
            component["description"] = item["rule_text"]
            nodes.append(component)
            node_by_code[component["code"]] = component

        for source, relation_type, target in [
            (item["criteria_code"], "has_diagnostic_component", item["component_code"]),
            (item["component_code"], "supported_by_evidence", item["evidence_code"]),
        ]:
            key = (source, relation_type, target)
            if key not in relation_by_key:
                relations.append(common_relation(source, relation_type, target, evidence))
                relation_by_key.add(key)

    write_jsonl(nodes_path, nodes)
    write_jsonl(relations_path, relations)
    write_csv(data_dir / "nodes_final.csv", nodes)
    write_csv(data_dir / "relations_final.csv", relations)

    deleted_server_nodes = None
    if args.apply_db:
        if not args.password:
            raise RuntimeError("缺少 Neo4j 密码，禁止空密码写库。")
        deleted_server_nodes = delete_polluted_server_nodes(args.uri, args.username, args.password)

    summary = {
        "batch_id": BATCH_ID,
        "removed_polluted_rule_nodes_local": removed_local_nodes,
        "removed_polluted_relations_local": removed_local_relations,
        "before_node_count": before_node_count,
        "after_node_count": len(nodes),
        "before_relation_count": before_relation_count,
        "after_relation_count": len(relations),
        "polluted_rule_codes_removed": len(POLLUTED_RULE_CODES),
        "diagnosis_components_added_or_kept": len(DIAGNOSIS_COMPONENTS),
        "deleted_server_nodes": deleted_server_nodes,
    }
    out_dir = batch_dir / "99_入库后复测"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "肺动脉高压入库后质量收口_20260715.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
