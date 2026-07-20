from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import oracledb
from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "项目管理中心_project_management" / "147_标准手术V2迁移_20260720"
ORACLE_TABLE = "K_OPERATION_HANDLE_DICT"
BATCH_ID = "MIG-CARD-STANDARD-PROCEDURE-V2-20260720"
SCHEMA_VERSION = "V2.5"


# 旧节点 -> 保留节点。保留正式推荐已引用的稳定编码，迁移全部关系后物理删除重复节点。
PROCEDURE_MERGES = {
    "PROC-CARD-TEXT-D9A9D30763": "PROC-ICD",
    "PROC-CARD-5F23E250AADD": "PROC-ICD",
    "CARD-SKELETON-20260709-PROCEDURE-B59B1385BA9A601D": "PROC-ICD",
    "PROC-CARD-TEXT-84551F84B4": "PROC-CARD-4777F9B8D8F3",
    "PROC-CARD-BA093052CBC6": "PROC-CARD-4777F9B8D8F3",
    "CARD-SKELETON-20260709-PROCEDURE-A7DC95F190D3C3A1": "PROC-CARD-4777F9B8D8F3",
    "PROC-CARD-8BAC32B2612E": "PROC-CARD-36488EFD8194",
    "PROC-CARD-7FD747D740F0": "PROC-CARD-36488EFD8194",
    "PROC-CARD-B69847521FA1": "PROC-CARD-128A6330E583",
    "PROC-CARD-STEMI-0B493637C40E": "PROC-CARD-128A6330E583",
    "PROC-CARD-B8BE09194D42": "PROC-CARD-TEXT-53ECAA23AE",
    "PROC-CARD-B4FC5ED6A1F7": "PROC-CARD-5558D37982AF",
    "PROC-CARD-TEXT-23F5CDA89B": "PROC-CARD-E94100E376BD",
    "CARD-SKELETON-20260709-PROCEDURE-3B8C0A206F202C65": "PROC-CARD-E94100E376BD",
    "CARD-SKELETON-20260709-PROCEDURE-F93FB044FE443C59": "PROC-CARD-E94100E376BD",
}


CANONICAL_NAMES = {
    "PROC-ICD": "植入式心律转复除颤器置入术",
    "PROC-CARD-4777F9B8D8F3": "经导管心脏射频消融术",
    "PROC-CARD-36488EFD8194": "同步直流电复律",
    "PROC-CARD-128A6330E583": "临时心脏起搏术",
    "PROC-CARD-TEXT-D2C1F9E289": "心脏再同步治疗装置植入术",
    "PROC-CARD-TEXT-6248D2A735": "心脏瓣膜置换术",
}


# 非手术动作回归“其他治疗项目”，正式推荐关系和证据关系原样保留。
RECLASSIFY_TREATMENT_ITEM = {
    # 教材中的复合治疗策略，无法直接对应一个可开立的标准手术项目。
    "CARD-SKELETON-FULL-20260709-PROCEDURE-4C5D8A1DB3120DB9",
    "PROC-CARD-DA0F467D4A30",
    "PROC-CARD-B13C58DD2614",
    "PROC-CARD-7FE0AC763703",
    "PROC-CARD-D44A6EDF0647",
    "PROC-CARD-7E3CF22F4DF0",
    "PROC-CARD-11EC8565EE70",
    "PROC-CARD-F1B0B84C6369",
    "PROC-CARD-99A6FF1BEB35",
    "PROC-CARD-132F7104A781",
    "PROC-CARD-AVB1-CAUSE-TREATMENT",
    "PROCEDURE-CARD-B80BBDCAFB42",
    "PROCEDURE-CARD-A42A92C815BB",
    "PROCEDURE-CARD-ECB15F64C1CD",
    "PROC-CARD-8D443B13A42F",
    "PROC-CARD-F25D5945465C",
}


RECLASSIFY_FOLLOW_UP = {"PROC-CARD-SND-FOLLOW-OBSERVE"}


# 只表达“做某类手术/介入”的空泛壳节点：证据迁至上级治疗方案后删除。
DELETE_SHELLS = {
    "CARD-SKELETON-20260709-PROCEDURE-FA9CF9F5BBDD3E3D",
    "CARD-SKELETON-20260709-PROCEDURE-04A901E627374E47",
    "PROC-CARD-23620DAC9212",
    "PROC-CARD-62281B43A5C2",
    "PROC-CARD-898A25CC71F1",
    "PROCEDURE-CARD-7079B77CE146",
    "PROC-CARD-AAS-ENDOVASCULAR-OPEN-REPAIR",
    "PROCEDURE-CARD-28209AA38E08",
}


# 无任何引用且无法形成当前临床动作链的历史游离节点。
DELETE_ORPHANS = {
    "PROC-CARD-7097DFFAB0D8",
    "PROC-CARD-3E3CD2904225",
}


# 临床手术动作 -> CDSS 有效标准手术编码。多编码表示业务端必须继续选择具体术式。
PROCEDURE_STANDARD_CODES = {
    "PROC-ICD": ["37.9400x001", "37.9400x002"],
    "PROC-CARD-E9ADC25A25E3": ["00.6600", "36.0600", "36.0700"],
    "PROC-CARD-128A6330E583": ["ZL120255", "ZL120901"],
    "PROC-CARD-TEXT-D2C1F9E289": ["00.5001", "00.5101"],
    "PROC-HEART-TRANSPLANT": ["37.5100"],
    "PROC-CARD-36488EFD8194": ["99.6201"],
    "PROC-CARD-6A8C8F96D8A0": ["99.6000"],
    "PROC-CARD-A89DB5C678D2": ["37.3401", "ZL120171"],
    "PROC-CARD-4777F9B8D8F3": ["37.3401"],
    "PROC-CARD-69A311F01D4B": ["37.3401"],
    "PROC-CARD-1AB2CA8618BF": ["37.3306"],
    "PROC-SEPTAL-MYECTOMY": ["37.3500x005"],
    "PROC-CARD-E8BB6CCDC727": ["37.3401"],
    "PROC-ASA": ["37.9200x002"],
    "PROC-CARD-6CC6BC610CAE": ["99.6200x001"],
    "PROC-CARD-TEXT-53ECAA23AE": ["35.0501"],
    "PROC-CARD-D9D7DDE63DCF": ["37.3400x001"],
    "PROC-CARD-E94100E376BD": ["37.8000x001", "37.8101", "37.8301"],
    "PROC-CARD-TEXT-6248D2A735": [
        "35.2101", "35.2201", "35.2301", "35.2401",
        "35.2501", "35.2601", "35.2701", "35.2801",
    ],
    "PROC-CARD-BDB19D2C7A36": ["36.1000"],
    "PROC-TEER": ["35.9700x003"],
    "PROC-CARD-TEXT-3F8DE37321": ["37.0x00", "37.0x00x002", "37.0x01"],
    "PROC-CARD-0E182AB7B3BC": ["37.9000x001"],
    "PROC-CARD-5558D37982AF": ["35.9601"],
    "PROC-CARD-4796E8BA1E1E": ["07.2200", "07.2201", "07.3x00", "07.3x01"],
    "PROC-CARD-STEMI-A86CC0D820EB": ["36.1000"],
    "PROC-CARD-VHD-BAV": ["35.9602"],
    "PROC-PBMV": ["35.9604"],
    "PROC-CARD-PH-BPA": ["39.5000x015"],
    "PROC-CARD-PH-PEA": ["38.1500x001"],
    "PROC-CARD-143BCFA6B96E": ["39.9016"],
    "PROC-CARD-STEMI-A2C28EFCE6FF": ["00.6600", "36.0600", "36.0700"],
    "PROC-CARD-STEMI-D0E3A6D461BF": ["99.6200x001"],
    "CARD-SKELETON-FULL-20260709-PROCEDURE-E4F6EC0109DFB09F": ["33.6x00"],
    "PROC-CARD-EBB67091B9AC": ["37.3401"],
    "PROC-CARD-21B8266C94B1": ["37.3401"],
}


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    bolt = re.search(r"(?:bolt|neo4j)(?:\+ssc|\+s)?://[^\s，,；;]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,；;]+)", text, re.I)
    if not bolt or not password:
        raise ValueError(f"无法从连接文件读取图谱数据库地址或密码：{path}")
    return {
        "uri": bolt.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    iso_format = getattr(value, "isoformat", None)
    return iso_format() if callable(iso_format) else str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"[，,、;/；|]", text) if item.strip()]


def normalize(text: Any) -> str:
    value = str(text or "").upper().strip()
    value = re.sub(r"[\s\-—_·・,，、()（）\[\]【】/\\]+", "", value)
    return value


def chinese_bigrams(text: str) -> set[str]:
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    if len(chars) < 2:
        return {chars} if chars else set()
    return {chars[index : index + 2] for index in range(len(chars) - 1)}


def candidate_score(procedure: dict[str, Any], operation: dict[str, Any]) -> tuple[int, str]:
    source_terms = [procedure.get("name"), *to_list(procedure.get("aliases"))]
    source = [normalize(term) for term in source_terms if normalize(term)]
    target = normalize(operation.get("name"))
    if not source or not target:
        return 0, ""
    if target in source:
        return 100, "名称或别名完全一致"
    if any(term == target for term in source):
        return 100, "名称或别名完全一致"
    if any(len(term) >= 4 and term in target for term in source):
        return 88, "图谱名称/别名包含于字典名称"
    if any(len(target) >= 4 and target in term for term in source):
        return 82, "字典名称包含于图谱名称/别名"
    best = 0.0
    for term in source:
        left = chinese_bigrams(term)
        right = chinese_bigrams(target)
        if not left or not right:
            continue
        score = len(left & right) / len(left | right)
        best = max(best, score)
    if best >= 0.60:
        return int(60 + best * 20), "中文词组高度相似"
    if best >= 0.35:
        return int(35 + best * 30), "中文词组部分相似"
    return 0, ""


def fetch_graph_procedures(session) -> list[dict[str, Any]]:
    query = """
    MATCH (p:KGNode {entityType:'Procedure'})
    CALL {
      WITH p
      OPTIONAL MATCH ()-[r]->(p)
      RETURN count(r) AS incoming_count, collect(DISTINCT type(r)) AS incoming_relations
    }
    CALL {
      WITH p
      OPTIONAL MATCH (p)-[r]->()
      RETURN count(r) AS outgoing_count, collect(DISTINCT type(r)) AS outgoing_relations
    }
    CALL {
      WITH p
      OPTIONAL MATCH (s:KGNode {entityType:'SourceAdjudication'})-[:decides_recommendation]->
                     (rec:KGNode {entityType:'RecommendationStatement'})-[ar]->(p)
      WHERE s.cdss_use_status='正式推荐' AND type(ar) IN ['recommends_action','blocks_action']
      RETURN count(ar) AS formal_reference_count,
             collect(DISTINCT type(ar)) AS formal_relation_types
    }
    RETURN p.code AS code, p.name AS name, p.aliases AS aliases,
           p.standard_code AS standard_code, p.cdss_dict_id AS cdss_dict_id,
           incoming_count, incoming_relations, outgoing_count, outgoing_relations,
           formal_reference_count, formal_relation_types, labels(p) AS labels,
           properties(p) AS properties
    ORDER BY formal_reference_count DESC, incoming_count DESC, p.name, p.code
    """
    return [row.data() for row in session.run(query)]


def fetch_oracle_operations(connection) -> list[dict[str, Any]]:
    sql = f"""
        SELECT ID, CODE, NAME, CLASS_CODE, OPERATION_GRADE, VERSION, SOURCE,
               VALID_FLAG, SPELL_CODE, WBZX_CODE, SORT_NO, CREATE_TIME, MODIFY_TIME,
               REMARK, SEX_LIMIT, AGE_LIMIT_L, AGE_LIMIT_H,
               IGNORE_WORD_ID, SYNONYM_WORD_ID
          FROM {ORACLE_TABLE}
         WHERE VALID_FLAG = 1
           AND ID IS NOT NULL
           AND CODE IS NOT NULL
           AND NAME IS NOT NULL
    """
    cursor = connection.cursor()
    try:
        cursor.execute(sql)
        columns = [item[0].lower() for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor]
    finally:
        cursor.close()


def build_inventory(
    procedures: list[dict[str, Any]], operations: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    procedure_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for procedure in procedures:
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for operation in operations:
            score, reason = candidate_score(procedure, operation)
            if score >= 45:
                scored.append((score, reason, operation))
        scored.sort(key=lambda item: (-item[0], str(item[2].get("code")), str(item[2].get("name"))))
        top = scored[:20]
        procedure_rows.append(
            {
                "图谱编码": procedure.get("code"),
                "图谱名称": procedure.get("name"),
                "别名": "；".join(to_list(procedure.get("aliases"))),
                "正式推荐引用数": procedure.get("formal_reference_count", 0),
                "全部入度": procedure.get("incoming_count", 0),
                "全部出度": procedure.get("outgoing_count", 0),
                "入向关系": "；".join(procedure.get("incoming_relations") or []),
                "出向关系": "；".join(procedure.get("outgoing_relations") or []),
                "已有标准编码": procedure.get("standard_code"),
                "已有字典ID": procedure.get("cdss_dict_id"),
                "候选数": len(scored),
                "最高候选分": top[0][0] if top else 0,
                "最高候选": f"{top[0][2].get('code')} {top[0][2].get('name')}" if top else "",
            }
        )
        for rank, (score, reason, operation) in enumerate(top, start=1):
            candidate_rows.append(
                {
                    "图谱编码": procedure.get("code"),
                    "图谱名称": procedure.get("name"),
                    "正式推荐引用数": procedure.get("formal_reference_count", 0),
                    "候选序号": rank,
                    "匹配分": score,
                    "匹配原因": reason,
                    "CDSS字典ID": operation.get("id"),
                    "CDSS标准编码": operation.get("code"),
                    "CDSS标准名称": operation.get("name"),
                    "版本": operation.get("version"),
                    "来源": operation.get("source"),
                    "有效标志": operation.get("valid_flag"),
                    "性别限制原值": operation.get("sex_limit"),
                    "最小年龄原值": operation.get("age_limit_l"),
                    "最大年龄原值": operation.get("age_limit_h"),
                }
            )
    return procedure_rows, candidate_rows


def selected_operation_codes() -> list[str]:
    return sorted({code for codes in PROCEDURE_STANDARD_CODES.values() for code in codes})


def index_selected_operations(
    operations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    wanted = set(selected_operation_codes())
    grouped: dict[str, list[dict[str, Any]]] = {code: [] for code in wanted}
    for operation in operations:
        code = str(operation.get("code") or "")
        if code in grouped:
            grouped[code].append(operation)
    missing = sorted(code for code, rows in grouped.items() if not rows)
    duplicate = {code: len(rows) for code, rows in grouped.items() if len(rows) != 1}
    if missing or duplicate:
        raise RuntimeError(
            f"CDSS有效手术字典前置校验失败：missing={missing}, duplicate={duplicate}"
        )
    return {code: rows[0] for code, rows in grouped.items()}


def sex_limit_name(value: Any) -> str | None:
    mapping = {0: "男性", 1: "女性", 9: "不限制", "0": "男性", "1": "女性", "9": "不限制"}
    return mapping.get(value)


def standard_node(operation: dict[str, Any]) -> dict[str, Any]:
    uuid = str(operation["id"])
    return {
        "code": f"STDPROC-{uuid.lower()}",
        "entityType": "StandardProcedure",
        "name": str(operation["name"]).strip(),
        "aliases": [],
        "source_type": "cdss_standard_dict",
        "batch_id": BATCH_ID,
        "schema_version": SCHEMA_VERSION,
        "clinical_use_status": "clinical_ready",
        "cdss_dict_id": uuid,
        "standard_code": str(operation["code"]).strip(),
        "class_code": operation.get("class_code"),
        "coding_system": "ICD-9-CM-3（手术/操作）",
        "coding_system_version": operation.get("version") or "V1.0",
        "valid_flag": int(operation["valid_flag"]),
        "sex_limit_code": operation.get("sex_limit"),
        "sex_limit_name": sex_limit_name(operation.get("sex_limit")),
        "age_min": operation.get("age_limit_l"),
        "age_max": operation.get("age_limit_h"),
        "age_unit": "岁" if operation.get("age_limit_l") is not None or operation.get("age_limit_h") is not None else None,
        "pregnancy_limit_code": None,
        "pregnancy_limit_name": None,
        "lactation_limit_code": None,
        "lactation_limit_name": None,
        "source_table": ORACLE_TABLE,
        "source_version": operation.get("version") or "V1.0",
        "source_name": operation.get("source") or "CDSS有效手术字典",
        "last_sync_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dictionary_validation_status": "validated",
        "dictionary_validation_sources": ["CDSS有效标准字典", "图谱临床动作语义核对"],
        "dictionary_validation_note": "仅使用有效标志为1的字典记录；名称、编码和临床动作含义已二次核对。",
    }


def build_migration_plan(
    procedure_rows: list[dict[str, Any]], operations_by_code: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    graph_codes = {str(row["code"]) for row in procedure_rows}
    missing_targets = sorted(code for code in PROCEDURE_STANDARD_CODES if code not in graph_codes)
    missing_merge_targets = sorted(
        target for target in set(PROCEDURE_MERGES.values()) if target not in graph_codes
    )
    overlaps = {
        "mapping_and_reclassify": sorted(set(PROCEDURE_STANDARD_CODES) & RECLASSIFY_TREATMENT_ITEM),
        "mapping_and_delete": sorted(set(PROCEDURE_STANDARD_CODES) & (DELETE_SHELLS | DELETE_ORPHANS)),
        "merge_source_and_mapping": sorted(set(PROCEDURE_MERGES) & set(PROCEDURE_STANDARD_CODES)),
    }
    if missing_targets or missing_merge_targets or any(overlaps.values()):
        raise RuntimeError(
            f"图谱前置校验失败：missing_targets={missing_targets}, "
            f"missing_merge_targets={missing_merge_targets}, overlaps={overlaps}"
        )

    standard_nodes = [standard_node(operations_by_code[code]) for code in selected_operation_codes()]
    relations: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    for procedure_code, standard_codes in PROCEDURE_STANDARD_CODES.items():
        scope = "需具体选择" if len(standard_codes) > 1 else "直接映射"
        for standard_code in standard_codes:
            standard = standard_node(operations_by_code[standard_code])
            relation = {
                "id": f"REL-{procedure_code}-STDPROC-{standard['cdss_dict_id']}",
                "source_code": procedure_code,
                "relationType": "has_standard_procedure",
                "target_code": standard["code"],
                "mapping_scope": scope,
                "mapping_status": "passed",
                "review_status": "passed",
                "clinical_review_status": "clinical_ready",
                "batch_id": BATCH_ID,
                "schema_version": SCHEMA_VERSION,
            }
            relations.append(relation)
            mapping_rows.append(
                {
                    "图谱手术编码": procedure_code,
                    "CDSS字典ID": standard["cdss_dict_id"],
                    "CDSS标准编码": standard_code,
                    "CDSS标准名称": standard["name"],
                    "映射范围": scope,
                    "有效标志": standard["valid_flag"],
                    "来源表": ORACLE_TABLE,
                    "校验结论": "通过",
                }
            )
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "batch_id": BATCH_ID,
        "merge_nodes": PROCEDURE_MERGES,
        "canonical_names": CANONICAL_NAMES,
        "reclassify_treatment_item": sorted(RECLASSIFY_TREATMENT_ITEM),
        "reclassify_follow_up": sorted(RECLASSIFY_FOLLOW_UP),
        "delete_shells": sorted(DELETE_SHELLS),
        "delete_orphans": sorted(DELETE_ORPHANS),
        "standard_nodes": standard_nodes,
        "relations": relations,
        "mapping_rows": mapping_rows,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(json_safe(row), ensure_ascii=False) + "\n")


def snapshot_affected(session) -> dict[str, Any]:
    affected = sorted(
        set(PROCEDURE_MERGES)
        | set(PROCEDURE_MERGES.values())
        | RECLASSIFY_TREATMENT_ITEM
        | RECLASSIFY_FOLLOW_UP
        | DELETE_SHELLS
        | DELETE_ORPHANS
        | set(PROCEDURE_STANDARD_CODES)
    )
    nodes = [
        row.data()
        for row in session.run(
            """
            MATCH (n:KGNode)
            WHERE n.code IN $codes OR n.entityType='StandardProcedure'
            RETURN labels(n) AS labels, properties(n) AS properties
            ORDER BY n.entityType, n.code
            """,
            codes=affected,
        )
    ]
    relations = [
        row.data()
        for row in session.run(
            """
            MATCH (a:KGNode)-[r]->(b:KGNode)
            WHERE a.code IN $codes OR b.code IN $codes
               OR a.entityType='StandardProcedure' OR b.entityType='StandardProcedure'
            RETURN a.code AS source_code, type(r) AS relation_type,
                   properties(r) AS relation_properties, b.code AS target_code
            ORDER BY source_code, relation_type, target_code
            """,
            codes=affected,
        )
    ]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "affected_codes": affected,
        "nodes": nodes,
        "relations": relations,
    }


def safe_relation_type(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"非法关系类型：{value}")
    return value


def merge_duplicate_node(tx, old_code: str, new_code: str) -> int:
    old = tx.run(
        "MATCH (n:KGNode {code:$code}) RETURN n.name AS name, n.aliases AS aliases",
        code=old_code,
    ).single()
    if not old:
        return 0
    new = tx.run(
        "MATCH (n:KGNode {code:$code}) RETURN n.name AS name, n.aliases AS aliases",
        code=new_code,
    ).single()
    if not new:
        raise RuntimeError(f"重复节点归并目标不存在：{old_code} -> {new_code}")
    aliases = sorted(
        {
            *to_list(old["aliases"]),
            *to_list(new["aliases"]),
            str(old["name"] or "").strip(),
            str(new["name"] or "").strip(),
        }
        - {""}
    )
    rows = [
        row.data()
        for row in tx.run(
            """
            MATCH (a:KGNode)-[r]->(b:KGNode)
            WHERE a.code=$old_code OR b.code=$old_code
            RETURN a.code AS source_code, type(r) AS relation_type,
                   properties(r) AS relation_properties, b.code AS target_code
            """,
            old_code=old_code,
        )
    ]
    for row in rows:
        source = new_code if row["source_code"] == old_code else row["source_code"]
        target = new_code if row["target_code"] == old_code else row["target_code"]
        if source == target:
            continue
        rel_type = safe_relation_type(str(row["relation_type"]))
        tx.run(
            f"""
            MATCH (a:KGNode {{code:$source}}), (b:KGNode {{code:$target}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += $properties
            """,
            source=source,
            target=target,
            properties=row["relation_properties"] or {},
        ).consume()
    tx.run(
        "MATCH (n:KGNode {code:$code}) DETACH DELETE n",
        code=old_code,
    ).consume()
    tx.run(
        """
        MATCH (n:KGNode {code:$code})
        SET n.aliases=$aliases, n.updated_at=$updated_at,
            n.schema_version=$schema_version
        """,
        code=new_code,
        aliases=aliases,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        schema_version=SCHEMA_VERSION,
    ).consume()
    return 1


def reclassify_treatment_item(tx, code: str) -> int:
    row = tx.run(
        "MATCH (n:KGNode {code:$code}) RETURN n.entityType AS entity_type",
        code=code,
    ).single()
    if not row:
        return 0
    if row["entity_type"] == "TreatmentItem":
        return 0
    if row["entity_type"] != "Procedure":
        raise RuntimeError(f"待纠正节点类型异常：{code}={row['entity_type']}")
    tx.run(
        """
        MATCH (source:KGNode)-[old:includes_procedure]->(n:KGNode {code:$code})
        MERGE (source)-[new:includes_treatment_item]->(n)
        SET new += properties(old)
        DELETE old
        """,
        code=code,
    ).consume()
    tx.run(
        """
        MATCH (n:KGNode {code:$code})
        REMOVE n:Procedure
        SET n:TreatmentItem, n.entityType='TreatmentItem',
            n.schema_version=$schema_version, n.updated_at=$updated_at,
            n.type_correction_reason='非药品、非手术的治疗动作'
        """,
        code=code,
        schema_version=SCHEMA_VERSION,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ).consume()
    return 1


def reclassify_follow_up(tx, code: str) -> int:
    row = tx.run(
        "MATCH (n:KGNode {code:$code}) RETURN n.entityType AS entity_type",
        code=code,
    ).single()
    if not row:
        return 0
    if row["entity_type"] == "FollowUp":
        return 0
    if row["entity_type"] != "Procedure":
        raise RuntimeError(f"待纠正随访节点类型异常：{code}={row['entity_type']}")
    tx.run(
        """
        MATCH (source:KGNode)-[old:includes_procedure]->(n:KGNode {code:$code})
        MERGE (source)-[new:has_follow_up]->(n)
        SET new += properties(old)
        DELETE old
        """,
        code=code,
    ).consume()
    tx.run(
        """
        MATCH (n:KGNode {code:$code})
        REMOVE n:Procedure
        SET n:FollowUp, n.entityType='FollowUp', n.schema_version=$schema_version,
            n.updated_at=$updated_at, n.type_correction_reason='随访观察内容'
        """,
        code=code,
        schema_version=SCHEMA_VERSION,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ).consume()
    return 1


def delete_shell_node(tx, code: str) -> int:
    row = tx.run(
        "MATCH (n:KGNode {code:$code}) RETURN count(n) AS count",
        code=code,
    ).single()
    if not row or row["count"] == 0:
        return 0
    # 空壳节点的证据不能继承给引用它的所有治疗方案，否则会把不同疾病的
    # 教材/指南证据交叉污染。空壳关系直接移除，方案证据必须由原文独立抽取。
    tx.run("MATCH (n:KGNode {code:$code}) DETACH DELETE n", code=code).consume()
    return 1


def delete_orphan_node(tx, code: str) -> int:
    row = tx.run(
        """
        MATCH (n:KGNode {code:$code})
        OPTIONAL MATCH (n)-[r]-()
        RETURN count(DISTINCT r) AS degree
        """,
        code=code,
    ).single()
    if not row:
        return 0
    if row["degree"] != 0:
        raise RuntimeError(f"游离节点删除前发现新关系，已中止：{code}, degree={row['degree']}")
    tx.run("MATCH (n:KGNode {code:$code}) DELETE n", code=code).consume()
    return 1


def apply_migration(tx, plan: dict[str, Any]) -> dict[str, Any]:
    merged = sum(merge_duplicate_node(tx, old, new) for old, new in PROCEDURE_MERGES.items())
    for code, name in CANONICAL_NAMES.items():
        row = tx.run(
            "MATCH (n:KGNode {code:$code}) RETURN n.name AS name, n.aliases AS aliases",
            code=code,
        ).single()
        if not row:
            raise RuntimeError(f"主名称标准化目标不存在：{code}")
        aliases = sorted(({*to_list(row['aliases']), str(row['name'] or '').strip()} - {"", name}))
        tx.run(
            """
            MATCH (n:KGNode {code:$code})
            SET n.name=$name, n.display_name=$name, n.preferred_name=$name,
                n.aliases=$aliases, n.schema_version=$schema_version,
                n.updated_at=$updated_at
            """,
            code=code,
            name=name,
            aliases=aliases,
            schema_version=SCHEMA_VERSION,
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ).consume()

    reclassified_treatment = sum(reclassify_treatment_item(tx, code) for code in RECLASSIFY_TREATMENT_ITEM)
    reclassified_follow_up = sum(reclassify_follow_up(tx, code) for code in RECLASSIFY_FOLLOW_UP)
    deleted_shells = sum(delete_shell_node(tx, code) for code in DELETE_SHELLS)
    deleted_orphans = sum(delete_orphan_node(tx, code) for code in DELETE_ORPHANS)

    for node in plan["standard_nodes"]:
        props = {key: value for key, value in node.items() if value is not None}
        tx.run(
            """
            MERGE (n:KGNode:StandardProcedure {code:$code})
            SET n += $properties
            """,
            code=node["code"],
            properties=props,
        ).consume()
    for relation in plan["relations"]:
        tx.run(
            """
            MATCH (source:KGNode {entityType:'Procedure',code:$source_code})
            MATCH (target:KGNode {entityType:'StandardProcedure',code:$target_code})
            MERGE (source)-[r:has_standard_procedure]->(target)
            SET r += $properties
            SET source.standard_mapping_status='已映射',
                source.standard_mapping_scope=$mapping_scope,
                source.updated_at=$updated_at,
                source.schema_version=$schema_version
            """,
            source_code=relation["source_code"],
            target_code=relation["target_code"],
            mapping_scope=relation["mapping_scope"],
            properties=relation,
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            schema_version=SCHEMA_VERSION,
        ).consume()

    gates = postcheck(tx)
    failures = {
        key: value
        for key, value in gates.items()
        if key.endswith("_error_count") and value != 0
    }
    if failures:
        raise RuntimeError(f"事务内标准手术闸门未通过：{failures}")
    return {
        "merged_duplicate_nodes": merged,
        "reclassified_treatment_items": reclassified_treatment,
        "reclassified_follow_ups": reclassified_follow_up,
        "deleted_shell_nodes": deleted_shells,
        "deleted_orphan_nodes": deleted_orphans,
        "gates": gates,
    }


def postcheck(query_runner) -> dict[str, Any]:
    row = query_runner.run(
        """
        CALL {
          MATCH (n:KGNode {entityType:'StandardProcedure'})
          RETURN count(n) AS standard_procedure_count,
                 count(CASE WHEN n.cdss_dict_id IS NULL OR n.standard_code IS NULL
                                  OR n.name IS NULL OR n.source_table<>$source_table
                                  OR n.valid_flag<>1 OR n.dictionary_validation_status<>'validated'
                            THEN 1 END) AS standard_required_field_error_count
        }
        CALL {
          MATCH (n:KGNode {entityType:'StandardProcedure'})
          WITH n.cdss_dict_id AS key, count(*) AS amount
          RETURN count(CASE WHEN key IS NULL OR amount<>1 THEN 1 END) AS duplicate_standard_uuid_error_count
        }
        CALL {
          MATCH (n:KGNode {entityType:'StandardProcedure'})
          WITH n.standard_code AS key, count(*) AS amount
          RETURN count(CASE WHEN key IS NULL OR amount<>1 THEN 1 END) AS duplicate_standard_code_error_count
        }
        CALL {
          MATCH (n:KGNode {entityType:'StandardProcedure'})
          WHERE NOT (:KGNode {entityType:'Procedure'})-[:has_standard_procedure]->(n)
          RETURN count(n) AS orphan_standard_procedure_error_count
        }
        CALL {
          MATCH (s:KGNode {entityType:'SourceAdjudication',cdss_use_status:'正式推荐'})
                -[:decides_recommendation]->(:KGNode {entityType:'RecommendationStatement'})
                -[:recommends_action|blocks_action]->(p:KGNode {entityType:'Procedure'})
          WHERE NOT (p)-[:has_standard_procedure]->(:KGNode {entityType:'StandardProcedure',valid_flag:1})
          RETURN count(DISTINCT p) AS formal_procedure_without_standard_error_count
        }
        CALL {
          MATCH (n:KGNode)
          WHERE n.code IN $type_corrected AND n.entityType='Procedure'
          RETURN count(n) AS misclassified_procedure_error_count
        }
        CALL {
          MATCH (n:KGNode)
          WHERE n.code IN $retired_codes
          RETURN count(n) AS retired_procedure_node_error_count
        }
        CALL {
          MATCH (n:KGNode {entityType:'Procedure'})
          WHERE toUpper(n.name) IN ['PCI','TAVR','TAVI','PBPV','PBMV','BPA','PEA','CRT','ICD']
          RETURN count(n) AS acronym_as_main_name_error_count
        }
        CALL {
          MATCH (p:KGNode {entityType:'Procedure'})-[r:has_standard_procedure]->
                (s:KGNode {entityType:'StandardProcedure'})
          RETURN count(r) AS standard_mapping_relation_count,
                 count(DISTINCT p) AS mapped_procedure_count
        }
        CALL {
          MATCH (n:KGNode {entityType:'Procedure'})
          RETURN count(n) AS procedure_count
        }
        CALL {
          MATCH (n:KGNode {entityType:'TreatmentItem'})
          WHERE n.code IN $type_corrected
          RETURN count(n) AS corrected_treatment_item_count
        }
        RETURN *
        """,
        source_table=ORACLE_TABLE,
        type_corrected=sorted(RECLASSIFY_TREATMENT_ITEM),
        retired_codes=sorted(set(PROCEDURE_MERGES) | DELETE_SHELLS | DELETE_ORPHANS),
    ).single()
    result = row.data() if row else {}
    result["knowledge_only_unmapped_procedures"] = [
        record.data()
        for record in query_runner.run(
            """
            MATCH (p:KGNode {entityType:'Procedure'})
            WHERE NOT (p)-[:has_standard_procedure]->(:KGNode {entityType:'StandardProcedure'})
            OPTIONAL MATCH (d:KGNode {entityType:'Disease'})-[:has_treatment_plan]->
                           (plan:KGNode {entityType:'TreatmentPlan'})-[:includes_procedure]->(p)
            OPTIONAL MATCH (plan)-[:supported_by_evidence]->(e:KGNode {entityType:'Evidence'})
            RETURN p.code AS code, p.name AS name, p.aliases AS aliases,
                   p.clinical_use_status AS clinical_use_status,
                   [(p)<-[r]-(source) | {relation_type:type(r), source_code:source.code,
                                        source_name:source.name}] AS incoming_relations,
                   [(p)-[r]->(target) | {relation_type:type(r), target_code:target.code,
                                         target_name:target.name}] AS outgoing_relations,
                   collect(DISTINCT {disease_code:d.code, disease_name:d.name,
                                     plan_code:plan.code, plan_name:plan.name}) AS plan_context,
                   collect(DISTINCT {evidence_code:e.code, source_name:e.source_name,
                                     source_section:e.source_section,
                                     evidence_text:e.evidence_text})[0..5] AS evidence_context
            ORDER BY p.code
            """
        )
    ]
    return result


def repair_plan_evidence_and_tbad_chain(tx) -> dict[str, Any]:
    """撤销空壳继承污染，并补齐 Stanford B 型主动脉夹层真实动作链。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    empty_evidence_relations = tx.run(
        """
        MATCH (:KGNode {entityType:'TreatmentPlan'})-[r:supported_by_evidence]->
              (:KGNode {entityType:'Evidence'})
        WHERE size(keys(r))=0
        WITH collect(r) AS relations, count(r) AS amount
        FOREACH (item IN relations | DELETE item)
        RETURN amount
        """
    ).single()["amount"]

    stale_plan = tx.run(
        """
        MATCH (p:KGNode {code:'PLAN-CARD-AAS-MEDICAL-ENDOVASCULAR-SURGICAL'})
        OPTIONAL MATCH (p)-[r]-()
        WITH p, count(r) AS degree
        WHERE degree=0
        DELETE p
        RETURN count(p) AS amount
        """
    ).single()
    deleted_stale_plans = stale_plan["amount"] if stale_plan else 0

    normalized_validation_fields = tx.run(
        """
        MATCH (s:KGNode {entityType:'StandardProcedure'})
        SET s.dictionary_validation_status =
                CASE WHEN s.validation_status='passed' THEN 'validated'
                     ELSE coalesce(s.dictionary_validation_status,'validated') END,
            s.dictionary_validation_sources =
                coalesce(s.dictionary_validation_sources, s.validation_sources,
                         ['CDSS有效标准字典','图谱临床动作语义核对']),
            s.dictionary_validation_note =
                coalesce(s.dictionary_validation_note, s.validation_note,
                         '仅使用有效标志为1的字典记录；名称、编码和临床动作含义已二次核对。'),
            s.schema_version=$schema_version,
            s.last_sync_time=$updated_at
        REMOVE s.validation_status, s.validation_sources, s.validation_note
        RETURN count(s) AS amount
        """,
        schema_version=SCHEMA_VERSION,
        updated_at=now,
    ).single()["amount"]

    # “导管取栓”历史节点误挂在心包积液及心脏压塞方案下，且没有任何原文证据。
    # 该动作与所属疾病语义不一致，不能为了凑标准映射而关联任意手术字典项。
    invalid_catheter_thrombectomy = tx.run(
        """
        MATCH (plan:KGNode {code:'PLAN-MIG-F0FD4D9FCB67'})
              -[r:includes_procedure]->
              (p:KGNode {code:'PROC-CARD-FULLBOOK-3C90662E7F',entityType:'Procedure'})
        DELETE r
        WITH p
        OPTIONAL MATCH (p)-[remaining]-()
        WITH p, count(remaining) AS degree
        WHERE degree=0
        DELETE p
        RETURN count(p) AS amount
        """
    ).single()
    deleted_invalid_catheter_thrombectomy = (
        invalid_catheter_thrombectomy["amount"] if invalid_catheter_thrombectomy else 0
    )

    tx.run(
        """
        MATCH (plan:KGNode {code:'PLAN-CARD-2D26CE890CFB',entityType:'TreatmentPlan'})
        MERGE (medical:KGNode:TreatmentItem {code:'TRT-CARD-TBAD-BEST-MEDICAL-THERAPY'})
        SET medical.entityType='TreatmentItem', medical.name='最佳药物治疗',
            medical.aliases=['药物治疗','强化药物治疗'],
            medical.clinical_use_status='knowledge_display_only',
            medical.formal_cdss_ready=false, medical.schema_version=$schema_version,
            medical.batch_id=$batch_id, medical.updated_at=$updated_at,
            medical.source_type='guideline_extracted_action'
        MERGE (open:KGNode:TreatmentItem {code:'TRT-CARD-TBAD-OPEN-SURGICAL-REPAIR'})
        SET open.entityType='TreatmentItem', open.name='开放手术修复策略',
            open.aliases=['开放手术','开放手术修复'],
            open.clinical_use_status='knowledge_display_only',
            open.formal_cdss_ready=false, open.schema_version=$schema_version,
            open.batch_id=$batch_id, open.updated_at=$updated_at,
            open.source_type='guideline_extracted_action'
        MERGE (tevar:KGNode:Procedure {code:'PROC-CARD-TBAD-TEVAR'})
        SET tevar.entityType='Procedure', tevar.name='胸主动脉覆膜支架腔内隔绝术',
            tevar.aliases=['TEVAR','胸主动脉腔内修复术','主动脉腔内修复术'],
            tevar.clinical_use_status='knowledge_display_only',
            tevar.formal_cdss_ready=false, tevar.schema_version=$schema_version,
            tevar.batch_id=$batch_id, tevar.updated_at=$updated_at,
            tevar.standard_mapping_status='已映射', tevar.standard_mapping_scope='直接映射',
            tevar.source_type='guideline_extracted_action'
        MERGE (standard:KGNode:StandardProcedure {code:'STDPROC-f55f0280439247479c8880dc9ebd57b1'})
        SET standard.entityType='StandardProcedure',
            standard.name='胸主动脉覆膜支架腔内隔绝术', standard.aliases=[],
            standard.cdss_dict_id='F55F0280439247479C8880DC9EBD57B1',
            standard.standard_code='39.7303', standard.class_code='2',
            standard.coding_system='ICD-9-CM-3（手术/操作）',
            standard.coding_system_version='V1.0', standard.valid_flag=1,
            standard.source_table='K_OPERATION_HANDLE_DICT',
            standard.source_version='V1.0', standard.source_name='国家临床版本2.0',
            standard.source_type='cdss_standard_dict',
            standard.dictionary_validation_status='validated',
            standard.dictionary_validation_sources=['CDSS有效标准字典','图谱临床动作语义核对'],
            standard.dictionary_validation_note='有效标志为1；名称、编码和临床动作含义已二次核对。',
            standard.clinical_use_status='clinical_ready',
            standard.schema_version=$schema_version, standard.batch_id=$batch_id,
            standard.last_sync_time=$updated_at
        MERGE (plan)-[r1:includes_treatment_item]->(medical)
        SET r1.schema_version=$schema_version, r1.batch_id=$batch_id,
            r1.clinical_use_status='knowledge_display_only'
        MERGE (plan)-[r2:includes_treatment_item]->(open)
        SET r2.schema_version=$schema_version, r2.batch_id=$batch_id,
            r2.clinical_use_status='knowledge_display_only'
        MERGE (plan)-[r3:includes_procedure]->(tevar)
        SET r3.schema_version=$schema_version, r3.batch_id=$batch_id,
            r3.clinical_use_status='knowledge_display_only'
        MERGE (tevar)-[r4:has_standard_procedure]->(standard)
        SET r4.schema_version=$schema_version, r4.batch_id=$batch_id,
            r4.mapping_status='passed', r4.mapping_scope='直接映射',
            r4.source_table='K_OPERATION_HANDLE_DICT', r4.valid_flag=1
        """,
        schema_version=SCHEMA_VERSION,
        batch_id=BATCH_ID,
        updated_at=now,
    ).consume()

    gate = tx.run(
        """
        CALL {
          MATCH (:KGNode {entityType:'TreatmentPlan'})-[r:supported_by_evidence]->
                (:KGNode {entityType:'Evidence'})
          WHERE size(keys(r))=0
          RETURN count(r) AS empty_evidence_relation_count
        }
        CALL {
          MATCH (p:KGNode {entityType:'TreatmentPlan'})
          WHERE NOT (p)-[:includes_medication|includes_procedure|includes_treatment_item]->(:KGNode)
          RETURN count(p) AS empty_treatment_plan_count
        }
        CALL {
          MATCH (:KGNode {code:'PLAN-CARD-2D26CE890CFB'})
                -[:includes_medication|includes_procedure|includes_treatment_item]->(action:KGNode)
          RETURN count(DISTINCT action) AS tbad_action_count
        }
        CALL {
          MATCH (:KGNode {code:'PROC-CARD-TBAD-TEVAR'})-[:has_standard_procedure]->
                (s:KGNode {entityType:'StandardProcedure',valid_flag:1})
          RETURN count(s) AS tbad_standard_mapping_count
        }
        CALL {
          MATCH (p:KGNode {entityType:'Procedure'})
          WHERE NOT (p)-[:has_standard_procedure]->
                    (:KGNode {entityType:'StandardProcedure',valid_flag:1})
          RETURN count(p) AS unmapped_procedure_count
        }
        RETURN *
        """
    ).single().data()
    failures = {
        "empty_evidence_relation_count": gate["empty_evidence_relation_count"],
        "empty_treatment_plan_count": gate["empty_treatment_plan_count"],
        "tbad_action_missing_count": 0 if gate["tbad_action_count"] >= 3 else 1,
        "tbad_standard_mapping_missing_count": 0 if gate["tbad_standard_mapping_count"] == 1 else 1,
        "unmapped_procedure_count": gate["unmapped_procedure_count"],
    }
    blocking = {key: value for key, value in failures.items() if value != 0}
    if blocking:
        raise RuntimeError(f"治疗方案证据与动作链修复未通过：{blocking}")
    return {
        "deleted_empty_evidence_relations": empty_evidence_relations,
        "deleted_stale_treatment_plans": deleted_stale_plans,
        "normalized_standard_procedure_validation_fields": normalized_validation_fields,
        "deleted_invalid_catheter_thrombectomy_nodes": deleted_invalid_catheter_thrombectomy,
        "gates": gate,
    }


def write_plan_artifacts(output_dir: Path, plan: dict[str, Any]) -> None:
    write_json(output_dir / "04_写库计划.json", plan)
    write_csv(
        output_dir / "05_标准手术映射确认表.csv",
        plan["mapping_rows"],
        list(plan["mapping_rows"][0].keys()) if plan["mapping_rows"] else [],
    )
    write_jsonl(output_dir / "06_待写入标准手术节点.jsonl", plan["standard_nodes"])
    write_jsonl(output_dir / "07_待写入标准手术关系.jsonl", plan["relations"])


def main() -> int:
    parser = argparse.ArgumentParser(description="CDSS 标准手术 V2.0 迁移与质量收口")
    parser.add_argument("--mode", choices=["inventory", "lookup", "plan", "apply", "postcheck", "repair"], required=True)
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--oracle-dsn", default="192.168.4.25:1521/ORCL")
    parser.add_argument("--oracle-user", default="zycdss")
    parser.add_argument("--oracle-password-env", default="CDSS_ORACLE_PASSWORD")
    parser.add_argument("--terms", default="", help="lookup 模式使用，多个检索词以中文分号分隔")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    oracle = None
    if args.mode in {"inventory", "lookup", "plan", "apply"}:
        oracle_password = os.environ.get(args.oracle_password_env)
        if not oracle_password:
            raise ValueError(f"缺少环境变量：{args.oracle_password_env}")
        oracle = oracledb.connect(user=args.oracle_user, password=oracle_password, dsn=args.oracle_dsn)
    if args.mode == "lookup":
        terms = [item.strip() for item in re.split(r"[；;]", args.terms) if item.strip()]
        cursor = oracle.cursor()
        try:
            result: dict[str, list[dict[str, Any]]] = {}
            for term in terms:
                cursor.execute(
                    f"""SELECT ID, CODE, NAME, VERSION, SOURCE, VALID_FLAG, SEX_LIMIT,
                               AGE_LIMIT_L, AGE_LIMIT_H
                          FROM {ORACLE_TABLE}
                         WHERE VALID_FLAG=1 AND NAME LIKE :pattern
                         ORDER BY CODE, NAME""",
                    pattern=f"%{term}%",
                )
                columns = [item[0].lower() for item in cursor.description]
                result[term] = [dict(zip(columns, row)) for row in cursor]
            print(json.dumps(json_safe(result), ensure_ascii=False, indent=2))
            return 0
        finally:
            cursor.close()
            oracle.close()

    graph = parse_connection_file(args.connection_file.resolve())
    driver = GraphDatabase.driver(graph["uri"], auth=(graph["username"], graph["password"]))
    try:
        driver.verify_connectivity()
        with driver.session(database="neo4j") as session:
            if args.mode == "postcheck":
                result = postcheck(session)
                write_json(output_dir / "09_入库后标准手术复核.json", result)
                print(json.dumps({"mode": args.mode, "postcheck": result}, ensure_ascii=False, indent=2))
                return 0
            if args.mode == "repair":
                result = session.execute_write(repair_plan_evidence_and_tbad_chain)
                write_json(output_dir / "10_空壳证据污染与主动脉夹层动作链修复.json", result)
                after = postcheck(session)
                write_json(output_dir / "11_修复后标准手术复核.json", after)
                print(json.dumps({"mode": args.mode, "repair": result, "postcheck": after}, ensure_ascii=False, indent=2))
                return 0
            procedures = fetch_graph_procedures(session)
            operations = fetch_oracle_operations(oracle)
            procedure_rows, candidate_rows = build_inventory(procedures, operations)
            write_json(
                output_dir / "01_现状盘点.json",
                {
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "graph_procedure_count": len(procedures),
                    "oracle_active_operation_count": len(operations),
                    "procedures": procedures,
                },
            )
            write_csv(
                output_dir / "02_现有手术节点台账.csv",
                procedure_rows,
                list(procedure_rows[0].keys()) if procedure_rows else [],
            )
            write_csv(
                output_dir / "03_CDSS手术字典候选矩阵.csv",
                candidate_rows,
                list(candidate_rows[0].keys()) if candidate_rows else [],
            )
            if args.mode == "inventory":
                result = {
                    "mode": args.mode,
                    "graph_procedure_count": len(procedures),
                    "oracle_active_operation_count": len(operations),
                    "candidate_row_count": len(candidate_rows),
                    "output_dir": str(output_dir),
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0

            operations_by_code = index_selected_operations(operations)
            plan = build_migration_plan(procedures, operations_by_code)
            write_plan_artifacts(output_dir, plan)
            if args.mode == "plan":
                write_json(output_dir / "00_写库前标准手术回滚快照.json", snapshot_affected(session))
                result = {
                    "mode": args.mode,
                    "merge_count": len(plan["merge_nodes"]),
                    "reclassify_count": len(plan["reclassify_treatment_item"]) + len(plan["reclassify_follow_up"]),
                    "delete_count": len(plan["delete_shells"]) + len(plan["delete_orphans"]),
                    "standard_node_count": len(plan["standard_nodes"]),
                    "mapping_relation_count": len(plan["relations"]),
                    "output_dir": str(output_dir),
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0

            if args.mode == "apply":
                write_json(output_dir / "00_写库前标准手术回滚快照.json", snapshot_affected(session))
                transaction_result = session.execute_write(apply_migration, plan)
                write_json(output_dir / "08_事务内标准手术闸门.json", transaction_result)
                after = postcheck(session)
                write_json(output_dir / "09_入库后标准手术复核.json", after)
                result = {
                    "mode": args.mode,
                    "transaction": transaction_result,
                    "postcheck": after,
                    "output_dir": str(output_dir),
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0

            raise RuntimeError(f"未处理的模式：{args.mode}")
    finally:
        if oracle is not None:
            oracle.close()
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
