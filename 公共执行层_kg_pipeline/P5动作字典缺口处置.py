#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
P5动作字典缺口处置

用途：
1. 读取 P5 样板终验输出的“正式推荐动作标准字典缺口”。
2. 只读 Oracle CDSS 标准字典，生成候选矩阵。
3. 对 17 个唯一动作节点做处置分类。
4. 可选写 Neo4j：仅写处置状态，不写 Oracle，不伪造字典 ID。

说明：
本脚本解决的是“宽口径动作/类别/多候选字典项不能被误当成普通缺口”的问题。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import oracledb
from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_P5_DIR = ROOT / "项目管理中心_project_management" / "2026年8月P5样板终验" / "02_当前标准专项终验_20260803"


DICT_TABLES_BY_TYPE = {
    "ExamItem": ["K_EXAM_ITEM_DICT"],
    "LabItem": ["K_LAB_ITEM_DICT", "K_LAB_SUBITEM_DICT"],
    "Medication": ["K_DRUG_DICT", "K_DRUG_CLASS_DICT"],
    "Procedure": ["K_OPERATION_HANDLE_DICT"],
    "TreatmentItem": ["K_TREATMENT_DICT"],
}


RESOLUTION_RULES: dict[str, dict[str, str]] = {
    "EXAM-ECG": {
        "resolution_status": "needs_specific_exam",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "心电图为宽口径检查动作；需按原文场景区分常规心电图、动态心电图、急诊心电图等，不能只按名称硬映射。",
        "required_action": "回原文证据确认具体检查项目；若为普通十二导联/常规心电图，可映射到常规心电图检查。",
    },
    "EXAM-TTE": {
        "resolution_status": "needs_specific_exam",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "超声心动图为宽口径检查动作；Oracle 中存在 M 型、二维、多普勒、经食管、负荷等多种项目。",
        "required_action": "回原文证据确认具体超声类型；不能直接把宽口径名称当医嘱项目。",
    },
    "EXAM-CMR": {
        "resolution_status": "needs_specific_exam",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "心脏磁共振需区分平扫、增强、延迟强化等项目。",
        "required_action": "回原文证据确认具体 CMR 项目。",
    },
    "EXAM-GENETIC": {
        "resolution_status": "needs_specific_exam",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "基因检测为宽口径检查动作，不同疾病对应检测范围不同。",
        "required_action": "按疾病和原文证据确定基因检测类型或进入待注册。",
    },
    "LAB-CARD-CADCD76D40B9": {
        "resolution_status": "needs_lab_subitem_drilldown",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "心肌损伤标志物是组合检验概念，应下钻到肌钙蛋白、CK-MB、肌红蛋白等检验项目/细项。",
        "required_action": "补具体检验项目和检验细项后再参与正式医嘱。",
    },
    "LAB-CARDIAC-BIOMARKERS": {
        "resolution_status": "needs_lab_subitem_drilldown",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "心脏生物标志物检测是组合检验概念，应下钻到 BNP、NT-proBNP、肌钙蛋白等项目。",
        "required_action": "补具体检验项目和检验细项后再参与正式医嘱。",
    },
    "MED-BETA-BLOCKER": {
        "resolution_status": "medication_class_not_orderable",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "β受体阻滞剂是药物类别，不是具体可开立药品。",
        "required_action": "保留为推荐类别；正式医嘱需下钻到美托洛尔等具体药品和剂型。",
    },
    "MED-CARD-DAE0F0B68F1D": {
        "resolution_status": "medication_class_not_orderable",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "他汀类药物是药物类别，不是具体可开立药品。",
        "required_action": "保留为推荐类别；正式医嘱需下钻到阿托伐他汀、瑞舒伐他汀等具体药品和剂型。",
    },
    "MED-CARD-2CCCA76B39F5": {
        "resolution_status": "medication_class_not_orderable",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "低分子量肝素是药物类别/族，不是唯一具体药品。",
        "required_action": "按指南原文和本院药品字典确认具体药品。",
    },
    "MED-CARD-A49408D27901": {
        "resolution_status": "medication_class_not_orderable",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "普通肝素需区分具体药品、剂型和给药途径。",
        "required_action": "按指南原文和本院药品字典确认具体药品。",
    },
    "MED-DIURETIC": {
        "resolution_status": "medication_class_not_orderable",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "利尿剂是药物类别，不是具体可开立药品。",
        "required_action": "正式医嘱需下钻到呋塞米、托拉塞米等具体药品和剂型。",
    },
    "MED-AMIODARONE": {
        "resolution_status": "needs_drug_form_route",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "胺碘酮虽是具体药名，但 Oracle 存在片剂、胶囊、注射液等多剂型。",
        "required_action": "按急性/长期用药场景确认剂型和给药途径。",
    },
    "PROC-CARD-TEXT-D2C1F9E289": {
        "resolution_status": "needs_procedure_variant",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "心脏再同步治疗装置植入术需区分 CRT-P、CRT-D、置入、置换等操作。",
        "required_action": "按原文和临床场景确认具体手术/操作字典项。",
    },
    "PROC-ICD": {
        "resolution_status": "needs_procedure_variant",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "植入式心律转复除颤器置入术需区分单腔、双腔、置入、置换等操作。",
        "required_action": "按原文和临床场景确认具体手术/操作字典项。",
    },
    "PROC-SEPTAL-MYECTOMY": {
        "resolution_status": "needs_oracle_registration_or_mapping",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "室间隔切除术未发现可唯一命中的 CDSS 手术字典项。",
        "required_action": "进入待字典融合；不得伪造标准编码。",
    },
    "PROC-ASA": {
        "resolution_status": "needs_oracle_registration_or_mapping",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "酒精室间隔消融术存在近似术语，但不能直接确认等同于 Oracle 字典项。",
        "required_action": "进入待字典融合；需要确认是否等同于经皮室间隔心肌消融术。",
    },
    "PROC-CARD-DA0F467D4A30": {
        "resolution_status": "needs_disease_scenario_split",
        "order_ready": "false",
        "display_ready": "true",
        "resolution_note": "溶栓治疗是共享宽口径治疗动作；不能把全局共享节点硬映射为 AMI 专属溶栓治疗。",
        "required_action": "按疾病/场景拆成具体推荐动作，再映射 CDSS 治疗字典。",
    },
}


def parse_neo4j_connection(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    bolt = re.search(r"bolt://[0-9.]+:\d+", text)
    user = re.search(r"(?:用户名|用户|user|username)\s*[:：]\s*([^\s，,;]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s，,;]+)", text, re.I)
    if not bolt or not user or not password:
        raise RuntimeError(f"无法从连接文件解析 Neo4j 信息：{path}")
    return {"uri": bolt.group(0), "user": user.group(1), "password": password.group(1)}


def read_gaps(path: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    by_code: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = row["node_code"]
        item = by_code.setdefault(
            code,
            {
                "entity_type": row["entity_type"],
                "node_code": code,
                "node_name": row["node_name"],
                "diseases": set(),
                "recommendations": set(),
                "ref_count": 0,
            },
        )
        item["diseases"].add(row["disease_name"])
        item["recommendations"].add(row["recommendation_name"])
        item["ref_count"] += 1
    return rows, by_code


def candidate_terms(name: str, code: str) -> list[str]:
    terms = [name]
    if "心电图" in name:
        terms += ["常规心电图", "十二导联心电图"]
    if "超声心动图" in name:
        terms += ["二维超声心动图", "多普勒超声心动图", "经胸超声心动图"]
    if "心脏磁共振" in name:
        terms += ["心脏磁共振", "心脏MRI", "心脏磁共振增强"]
    if "心肌损伤标志物" in name:
        terms += ["肌钙蛋白", "肌酸激酶同工酶", "肌红蛋白"]
    if "心脏生物标志物" in name:
        terms += ["BNP", "NT-proBNP", "脑钠肽", "肌钙蛋白"]
    if "β受体阻滞剂" in name:
        terms += ["美托洛尔", "比索洛尔", "卡维地洛"]
    if "他汀" in name:
        terms += ["阿托伐他汀", "瑞舒伐他汀"]
    if "低分子量肝素" in name:
        terms += ["依诺肝素", "低分子肝素"]
    if "普通肝素" in name:
        terms += ["肝素"]
    if "利尿剂" in name:
        terms += ["呋塞米", "托拉塞米"]
    if "胺碘酮" in name:
        terms += ["盐酸胺碘酮"]
    if "心脏再同步" in name:
        terms += ["CRT", "再同步"]
    if "转复除颤器" in name:
        terms += ["ICD", "除颤器"]
    if "酒精室间隔" in name:
        terms += ["室间隔心肌消融", "PTSMA"]
    if "溶栓" in name:
        terms += ["急性心肌梗死溶栓", "溶栓"]
    return list(dict.fromkeys(terms))


def fetch_candidates(cursor: oracledb.Cursor, entity_type: str, name: str, code: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for table in DICT_TABLES_BY_TYPE.get(entity_type, []):
        for term in candidate_terms(name, code):
            sql = f"""
                select id, code, name
                from {table}
                where valid_flag = 1
                  and name like :kw
                  fetch first 20 rows only
            """
            try:
                rows = cursor.execute(sql, kw=f"%{term}%").fetchall()
            except Exception:
                continue
            for id_, standard_code, standard_name in rows:
                candidates.append(
                    {
                        "source_table": table,
                        "term": term,
                        "candidate_id": str(id_),
                        "candidate_code": str(standard_code),
                        "candidate_name": str(standard_name),
                    }
                )
    seen = set()
    unique = []
    for c in candidates:
        key = (c["source_table"], c["candidate_id"], c["candidate_code"], c["candidate_name"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    return unique


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_neo4j_resolution(driver, matrix_rows: list[dict[str, Any]]) -> int:
    payload = [
        {
            "code": r["node_code"],
            "status": r["resolution_status"],
            "note": r["resolution_note"],
            "required_action": r["required_action"],
            "order_ready": r["cdss_order_ready"] == "true",
            "display_ready": r["cdss_display_ready"] == "true",
        }
        for r in matrix_rows
    ]
    cypher = """
    UNWIND $rows AS row
    MATCH (n:KGNode {code: row.code})
    SET n.cdss_dictionary_resolution_status = row.status,
        n.cdss_dictionary_resolution_note = row.note,
        n.cdss_dictionary_required_action = row.required_action,
        n.cdss_order_ready = row.order_ready,
        n.cdss_display_ready = row.display_ready,
        n.emr_write_allowed = false,
        n.dictionary_resolution_batch = 'P5_ACTION_DICT_GAP_20260803',
        n.updated_at = datetime()
    RETURN count(n) AS updated
    """
    with driver.session() as session:
        return session.run(cypher, rows=payload).single()["updated"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p5-dir", type=Path, default=DEFAULT_P5_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_P5_DIR / "08_动作字典缺口处置_20260803")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--oracle-user", default="zycdss")
    parser.add_argument("--oracle-password", required=True)
    parser.add_argument("--oracle-dsn", default="192.168.4.25:1521/ORCL")
    parser.add_argument("--write-neo4j", action="store_true")
    args = parser.parse_args()

    gap_file = args.p5_dir / "06_标准字典缺口明细.csv"
    _, by_code = read_gaps(gap_file)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    connection = oracledb.connect(user=args.oracle_user, password=args.oracle_password, dsn=args.oracle_dsn)
    cursor = connection.cursor()

    matrix_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for code, item in sorted(by_code.items(), key=lambda kv: (kv[1]["entity_type"], kv[1]["node_name"])):
        rule = RESOLUTION_RULES.get(code, {
            "resolution_status": "needs_manual_review",
            "order_ready": "false",
            "display_ready": "true",
            "resolution_note": "未配置自动处置规则。",
            "required_action": "进入待审核。",
        })
        candidates = fetch_candidates(cursor, item["entity_type"], item["node_name"], code)
        matrix_rows.append({
            "node_code": code,
            "node_name": item["node_name"],
            "entity_type": item["entity_type"],
            "ref_count": item["ref_count"],
            "diseases": "；".join(sorted(item["diseases"])),
            "recommendation_count": len(item["recommendations"]),
            "resolution_status": rule["resolution_status"],
            "cdss_display_ready": rule["display_ready"],
            "cdss_order_ready": rule["order_ready"],
            "resolution_note": rule["resolution_note"],
            "required_action": rule["required_action"],
            "candidate_count": len(candidates),
            "generated_at": now,
        })
        for c in candidates:
            candidate_rows.append({
                "node_code": code,
                "node_name": item["node_name"],
                "entity_type": item["entity_type"],
                **c,
            })

    connection.close()

    write_csv(
        output_dir / "01_17项动作字典缺口处置矩阵.csv",
        matrix_rows,
        [
            "node_code", "node_name", "entity_type", "ref_count", "diseases", "recommendation_count",
            "resolution_status", "cdss_display_ready", "cdss_order_ready", "resolution_note",
            "required_action", "candidate_count", "generated_at",
        ],
    )
    write_csv(
        output_dir / "02_Oracle候选明细.csv",
        candidate_rows,
        ["node_code", "node_name", "entity_type", "source_table", "term", "candidate_id", "candidate_code", "candidate_name"],
    )

    summary = {
        "generated_at": now,
        "unique_gap_count": len(matrix_rows),
        "candidate_count": len(candidate_rows),
        "resolution_status_count": dict(defaultdict(int)),
        "write_neo4j": bool(args.write_neo4j),
        "neo4j_updated": 0,
    }
    counts: dict[str, int] = defaultdict(int)
    for r in matrix_rows:
        counts[r["resolution_status"]] += 1
    summary["resolution_status_count"] = dict(counts)

    if args.write_neo4j:
        cfg = parse_neo4j_connection(args.connection_file)
        driver = GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))
        try:
            summary["neo4j_updated"] = write_neo4j_resolution(driver, matrix_rows)
        finally:
            driver.close()

    (output_dir / "00_处置摘要.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# P5 正式推荐动作字典缺口处置说明",
        "",
        f"生成时间：{now}",
        "",
        "## 结论",
        "",
        f"- 唯一缺口节点：{len(matrix_rows)} 个。",
        f"- Oracle 候选记录：{len(candidate_rows)} 条。",
        f"- 是否写 Neo4j：{'是' if args.write_neo4j else '否'}。",
        f"- Neo4j 更新节点：{summary['neo4j_updated']} 个。",
        "",
        "## 处置原则",
        "",
        "1. 宽口径检查、检验组合、药物类别、共享治疗动作不直接映射为 Oracle 具体医嘱项目。",
        "2. 能用于医生知识展示的，标记为可展示；不能直接生成医嘱或回填的，标记为不可直接下医嘱。",
        "3. 多候选项目必须回到原文证据和 CDSS 字典一起确认，不能按名称相似强行写标准 ID。",
        "",
        "## 输出文件",
        "",
        "- `01_17项动作字典缺口处置矩阵.csv`",
        "- `02_Oracle候选明细.csv`",
        "- `00_处置摘要.json`",
    ]
    (output_dir / "03_处置说明.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
