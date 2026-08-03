from __future__ import annotations

import csv
import json
import re
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
LINK_FILE = ROOT / "图谱数据库链接.txt"
OUT_DIR = ROOT / "项目管理中心_project_management" / "152_标准字典闭环硬闸门_20260730"


字典必需实体 = {
    "StandardDiagnosis": "K_ICD10_DICT",
    "StandardProcedure": "K_OPERATION_HANDLE_DICT",
    "Medication": "K_DRUG_DICT",
    "ExamItem": "K_EXAM_ITEM_DICT",
    "LabItem": "K_LAB_ITEM_DICT",
    "LabSubitem": "K_LAB_SUBITEM_DICT",
    "Symptom": "K_SYMPTOM_DICT",
    "Sign": "K_CLINICAL_SIGN_DICT",
    "ExamObservation": "K_EXAM_OBSERVATION_DICT",
    "VitalSignItem": "K_VITAL_SIGN_ITEM_DICT",
    "LabSample": "K_LAB_SAMPLE_DICT",
    "LabSpecimen": "K_LAB_SAMPLE_DICT",
    "TreatmentItem": "K_TREATMENT_DICT",
}

字典ID字段 = [
    "cdss_dict_id",
    "source_dict_id",
    "dict_id",
    "standard_dict_id",
    "oracle_id",
    "oracle_uuid",
    "cdss_uuid",
]

字典编码字段 = [
    "standard_code",
    "dictionary_code",
    "cdss_dict_code",
    "dict_code",
    "cdss_code",
]

字典来源表字段 = [
    "source_table",
    "dictionary_source_table",
    "dict_table",
    "standard_table",
]

待处理状态 = {
    "pending",
    "pending_registration",
    "register_pending",
    "review_pending",
    "candidate",
    "unverified",
    "conflict",
    "ambiguous",
    "rejected",
}

仅知识展示状态 = {
    "knowledge_only",
    "knowledge_display",
    "reference_only",
    "non_orderable",
    "category_only",
}


def 读连接配置() -> dict[str, str]:
    text = LINK_FILE.read_text(encoding="utf-8-sig", errors="ignore")
    bolt = re.search(r"bolt://[^\s；;]+", text, re.I)
    user = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s；;]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s；;]+)", text, re.I)
    if not (bolt and user and password):
        raise RuntimeError(f"无法从 {LINK_FILE} 解析 Neo4j 连接信息")
    return {"uri": bolt.group(0), "user": user.group(1), "password": password.group(1)}


def 写_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


def first_present(row: dict[str, Any], fields: list[str]) -> Any:
    for field in fields:
        value = row.get(field)
        if value is not None and str(value).strip() != "":
            return value
    return ""


def main(out_dir: Path | None = None) -> int:
    output_dir = out_dir or OUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = 读连接配置()

    summary_rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []

    query = """
    MATCH (n)
    WHERE (n.entityType = $entity_type OR $entity_type IN labels(n))
      AND coalesce(n.status, '') <> 'deprecated'
    RETURN elementId(n) AS element_id, labels(n) AS labels, properties(n) AS props
    ORDER BY coalesce(n.name, n.display_name, n.preferred_name, n.code, '')
    """

    with GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"])) as driver:
        with driver.session() as session:
            for entity_type, expected_table in 字典必需实体.items():
                records = session.run(query, entity_type=entity_type).data()
                total = len(records)
                bound = 0
                formal_total = 0
                formal_missing_identity = 0
                knowledge_only_missing_identity = 0
                formal_pending = 0
                knowledge_only_pending = 0
                source_table_missing = 0
                status_missing = 0

                identity_groups: dict[tuple[str, str], list[str]] = {}

                for record in records:
                    props: dict[str, Any] = record["props"]
                    dict_id = first_present(props, 字典ID字段)
                    dict_code = first_present(props, 字典编码字段)
                    source_table = first_present(props, 字典来源表字段)
                    status_value = str(
                        props.get("dictionary_validation_status")
                        or props.get("dictionary_status")
                        or props.get("standardization_status")
                        or ""
                    ).strip()

                    node_name = props.get("name") or props.get("display_name") or props.get("preferred_name") or ""
                    node_code = props.get("code") or ""
                    is_knowledge_only = status_value in 仅知识展示状态

                    has_identity = bool(str(dict_id).strip()) and bool(str(dict_code).strip())
                    if not is_knowledge_only:
                        formal_total += 1

                    if has_identity:
                        bound += 1
                        identity_groups.setdefault((str(dict_id), str(dict_code)), []).append(str(node_code))
                    else:
                        if is_knowledge_only:
                            knowledge_only_missing_identity += 1
                            issue_type = "仅知识展示未绑定标准字典"
                            requirement = "不进入正式CDSS推荐或回填；后续应改为类别/知识节点，或下钻到具体标准字典项目。"
                        else:
                            formal_missing_identity += 1
                            issue_type = "正式可用实体缺少标准字典ID或标准编码"
                            requirement = "阻断：必须绑定有效CDSS标准字典，或进入待注册审核后再回写；未闭环前不得进入正式CDSS推荐或回填。"
                        issue_rows.append(
                            {
                                "问题类型": issue_type,
                                "实体类型": entity_type,
                                "期望字典表": expected_table,
                                "图谱编码": node_code,
                                "图谱名称": node_name,
                                "当前状态": status_value,
                                "处理要求": requirement,
                            }
                        )

                    if status_value in 待处理状态:
                        if is_knowledge_only:
                            knowledge_only_pending += 1
                            issue_type = "仅知识展示仍处于待处理/待注册/冲突状态"
                            requirement = "治理提醒：确认是否应转为类别/知识节点；不得作为正式主数据。"
                        else:
                            formal_pending += 1
                            issue_type = "正式可用实体仍处于待处理/待注册/冲突状态"
                            requirement = "阻断：先完成字典注册、歧义裁决或类型纠正；未闭环前不得作为正式主数据。"
                        issue_rows.append(
                            {
                                "问题类型": issue_type,
                                "实体类型": entity_type,
                                "期望字典表": expected_table,
                                "图谱编码": node_code,
                                "图谱名称": node_name,
                                "当前状态": status_value,
                                "处理要求": requirement,
                            }
                        )

                    if has_identity and not str(source_table).strip():
                        source_table_missing += 1
                        issue_rows.append(
                            {
                                "问题类型": "已绑定字典但缺少来源表",
                                "实体类型": entity_type,
                                "期望字典表": expected_table,
                                "图谱编码": node_code,
                                "图谱名称": node_name,
                                "当前状态": status_value,
                                "处理要求": "补齐来源表，避免不同字典体系编码冲突。",
                            }
                        )

                    if has_identity and not status_value:
                        status_missing += 1

                duplicate_count = 0
                for (dict_id, dict_code), codes in identity_groups.items():
                    if len(codes) > 1:
                        duplicate_count += 1
                        duplicate_rows.append(
                            {
                                "实体类型": entity_type,
                                "期望字典表": expected_table,
                                "字典ID": dict_id,
                                "字典编码": dict_code,
                                "重复图谱节点数": len(codes),
                                "图谱编码列表": "；".join(codes),
                                "处理要求": "同一字典身份只能保留一个标准主数据节点；迁移关系后合并重复节点。",
                            }
                        )

                summary_rows.append(
                    {
                        "实体类型": entity_type,
                        "期望字典表": expected_table,
                        "总数": total,
                        "正式可用节点数": formal_total,
                        "已绑定标准字典ID和编码": bound,
                        "正式可用缺少标准字典ID或编码": formal_missing_identity,
                        "仅知识展示缺少标准字典ID或编码": knowledge_only_missing_identity,
                        "正式可用待处理或待注册": formal_pending,
                        "仅知识展示待处理或待注册": knowledge_only_pending,
                        "已绑定但缺少来源表": source_table_missing,
                        "已绑定但缺少校验状态": status_missing,
                        "同一字典身份重复组": duplicate_count,
                    }
                )

    blocking_total = sum(
        int(row["正式可用缺少标准字典ID或编码"])
        + int(row["正式可用待处理或待注册"])
        + int(row["已绑定但缺少来源表"])
        + int(row["同一字典身份重复组"])
        for row in summary_rows
    )

    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "gate_name": "标准字典闭环硬闸门",
        "gate_status": "passed" if blocking_total == 0 else "failed",
        "blocking_total": blocking_total,
        "scope": list(字典必需实体.keys()),
        "summary": summary_rows,
    }

    (output_dir / "01_标准字典闭环硬闸门_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    写_csv(
        output_dir / "02_标准字典闭环硬闸门_汇总.csv",
        summary_rows,
        [
            "实体类型",
            "期望字典表",
            "总数",
            "正式可用节点数",
            "已绑定标准字典ID和编码",
            "正式可用缺少标准字典ID或编码",
            "仅知识展示缺少标准字典ID或编码",
            "正式可用待处理或待注册",
            "仅知识展示待处理或待注册",
            "已绑定但缺少来源表",
            "已绑定但缺少校验状态",
            "同一字典身份重复组",
        ],
    )
    写_csv(
        output_dir / "03_标准字典闭环硬闸门_问题清单.csv",
        issue_rows,
        ["问题类型", "实体类型", "期望字典表", "图谱编码", "图谱名称", "当前状态", "处理要求"],
    )
    写_csv(
        output_dir / "04_同一字典身份重复清单.csv",
        duplicate_rows,
        ["实体类型", "期望字典表", "字典ID", "字典编码", "重复图谱节点数", "图谱编码列表", "处理要求"],
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if blocking_total == 0 else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="标准字典闭环硬闸门")
    parser.add_argument("--out-dir", type=Path, default=None, help="输出目录；不传则使用脚本默认目录")
    args = parser.parse_args()
    raise SystemExit(main(args.out_dir))
