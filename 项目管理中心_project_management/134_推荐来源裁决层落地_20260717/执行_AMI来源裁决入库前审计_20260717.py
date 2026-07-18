import csv
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
SAMPLE = BASE / "01_AMI样板包" / "AMI推荐来源裁决样板_20260717.csv"
AUDIT_DIR = BASE / "02_入库前审计"
FRONT_DIR = BASE / "03_前端字段对齐"
DELTA_DIR = BASE / "04_delta候选包_不可直接入库"

for d in [AUDIT_DIR, FRONT_DIR, DELTA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DISEASE_CODE = "DIS-CARD-CAD-AMI"
SCHEMA_VERSION = "V1.17"
BATCH_ID = "SRCADJ-AMI-SAMPLE-20260717"

GUIDELINE_CODE_MAP = {
    "4TH universal definition of MI.pdf": "GL-CARD-MI-UDMI-4",
    "ACC/AHA/ACEP/NAEMSP/SCAI指南：急性冠脉综合征患者的管理2025.pdf": "GL-CARD-ACS-2025",
    "ACS 2025指南": "GL-CARD-ACS-2025",
    "STEMI CN 2019.pdf": "GL-CARD-STEMI-CN-2019",
    "2018 STEMI院前溶栓治疗中国专家共识.pdf": "GL-CARD-STEMI-PREHOSPITAL-FIB-2018",
    "NSTE-ACS CN 2024.pdf": "GL-CARD-NSTEACS-CN-2024",
    "内科学第10版": "GL-CARD-INTERNALMED-10",
}

ACTION_NAME_MAP = {
    "SRCADJ-CARD-AMI-DX-001": "AMI诊断标准判断",
    "SRCADJ-CARD-AMI-ECG-001": "心电图检查",
    "SRCADJ-CARD-AMI-PCI-001": "经皮冠状动脉介入治疗",
    "SRCADJ-CARD-AMI-FIB-001": "溶栓治疗",
    "SRCADJ-CARD-AMI-FIB-CONTRA-001": "阻断溶栓治疗",
    "SRCADJ-CARD-AMI-ANTIPLATELET-001": "抗血小板治疗",
}

REQUIRED_COLUMNS = [
    "裁决编码",
    "疾病",
    "临床问题",
    "适用场景",
    "最终推荐",
    "主依据",
    "支持依据",
    "冲突状态",
    "CDSS使用状态",
    "医生端默认展示",
    "备注",
]

FORMAL_STATUS = "正式推荐"
ALLOWED_CONFLICT_FOR_FORMAL = {"无冲突", "有冲突已处理"}


def split_supporting(value: str) -> list[str]:
    if not value:
        return []
    parts = []
    for raw in value.replace("；", ";").split(";"):
        item = raw.strip()
        if item:
            parts.append(item)
    return parts


def read_rows() -> list[dict]:
    with SAMPLE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"样板表缺少字段: {missing}")
        return list(reader)


def main() -> None:
    rows = read_rows()
    audit_rows = []
    blocked_rows = []
    frontend_rows = []
    delta_nodes = []
    delta_relations = []

    for row in rows:
        code = row["裁决编码"].strip()
        status = row["CDSS使用状态"].strip()
        conflict = row["冲突状态"].strip()
        primary_name = row["主依据"].strip()
        primary_code = GUIDELINE_CODE_MAP.get(primary_name, "")
        support_names = split_supporting(row["支持依据"].strip())
        support_codes = [GUIDELINE_CODE_MAP.get(x, "") for x in support_names]
        action_name = ACTION_NAME_MAP.get(code, "")

        issues = []
        blockers = []

        for c in REQUIRED_COLUMNS:
            if not row[c].strip():
                issues.append(f"字段为空:{c}")

        if not primary_code:
            blockers.append("主依据指南未匹配到标准指南编码")
        if status == FORMAL_STATUS and conflict not in ALLOWED_CONFLICT_FOR_FORMAL:
            blockers.append("正式推荐存在未处理冲突")
        if status != FORMAL_STATUS:
            blockers.append("非正式推荐，不得进入医生端主动推荐区")

        # 样板包用于架构验证，尚未回到原文证据补齐以下字段；这些是正式入库硬缺口。
        if status == FORMAL_STATUS:
            blockers.extend([
                "缺主证据编码",
                "缺推荐等级",
                "缺证据等级",
                "缺标准推荐动作编码",
            ])

        can_front_preview = bool(code and row["最终推荐"].strip() and primary_name)
        import_ready = len(blockers) == 0

        audit_rows.append({
            "裁决编码": code,
            "疾病": row["疾病"],
            "临床问题": row["临床问题"],
            "CDSS使用状态": status,
            "冲突状态": conflict,
            "主依据": primary_name,
            "主依据编码": primary_code,
            "支持依据编码": ";".join([x for x in support_codes if x]),
            "前端预览可用": "是" if can_front_preview else "否",
            "可直接入库": "是" if import_ready else "否",
            "问题": "；".join(issues),
            "阻断": "；".join(blockers),
        })

        if blockers:
            blocked_rows.append({
                "裁决编码": code,
                "临床问题": row["临床问题"],
                "阻断原因": "；".join(blockers),
                "处理建议": "回到原文证据补齐主证据、推荐等级、证据等级、动作编码；冲突待裁决项先拆分分型后再入库",
            })

        frontend_rows.append({
            "adjudication_code_裁决编码": code,
            "disease_name_疾病名称": row["疾病"],
            "clinical_question_临床问题": row["临床问题"],
            "clinical_scenario_适用场景": row["适用场景"],
            "final_recommendation_综合推荐": row["最终推荐"],
            "primary_guideline_name_主依据指南": primary_name,
            "supporting_guideline_names_支持依据": row["支持依据"],
            "conflict_status_冲突状态": conflict,
            "cdss_use_status_CDSS状态": status,
            "default_display_默认展示": row["医生端默认展示"],
            "action_name_推荐动作名称": action_name,
            "frontend_area_前端区域": "正式推荐区" if import_ready else ("预览区" if status == FORMAL_STATUS else "冲突/阻断区"),
        })

        node = {
            "code": code,
            "entityType": "SourceAdjudication",
            "name": f"{row['临床问题']}来源裁决",
            "disease_code": DISEASE_CODE,
            "disease_name": row["疾病"],
            "clinical_question": row["临床问题"],
            "clinical_scenario": row["适用场景"],
            "final_recommendation": row["最终推荐"],
            "primary_guideline_code": primary_code,
            "primary_guideline_name": primary_name,
            "supporting_guideline_codes": [x for x in support_codes if x],
            "supporting_guideline_names": support_names,
            "conflict_status": conflict,
            "cdss_use_status": status,
            "default_display": row["医生端默认展示"],
            "source_type": "guideline",
            "batch_id": BATCH_ID,
            "schema_version": SCHEMA_VERSION,
            "clinical_use_status": "review_ready" if status == FORMAL_STATUS else "blocked",
            "import_ready": import_ready,
            "not_import_ready_reason": "；".join(blockers),
        }
        delta_nodes.append(node)

        # 只生成端点明确的候选关系；仍标记 import_ready=false，防止被误当正式包。
        delta_relations.append({
            "id": f"REL-{code}-DISEASE",
            "source_code": DISEASE_CODE,
            "relationType": "has_source_adjudication",
            "target_code": code,
            "batch_id": BATCH_ID,
            "schema_version": SCHEMA_VERSION,
            "review_status": "pending",
            "clinical_review_status": "pending" if status == FORMAL_STATUS else "blocked",
            "import_ready": False,
            "not_import_ready_reason": "样板包尚未补齐主证据、推荐等级、证据等级和动作编码，禁止直接导入",
        })
        if primary_code:
            delta_relations.append({
                "id": f"REL-{code}-PRIMARY-GUIDELINE",
                "source_code": code,
                "relationType": "uses_primary_guideline",
                "target_code": primary_code,
                "batch_id": BATCH_ID,
                "schema_version": SCHEMA_VERSION,
                "review_status": "pending",
                "clinical_review_status": "pending" if status == FORMAL_STATUS else "blocked",
                "import_ready": False,
                "not_import_ready_reason": "需服务器确认指南节点存在并补齐主证据后再入库",
            })

    def write_csv(path: Path, fieldnames: list[str], data: list[dict]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    write_csv(AUDIT_DIR / "AMI来源裁决入库前审计结果_20260717.csv", list(audit_rows[0].keys()), audit_rows)
    write_csv(AUDIT_DIR / "AMI来源裁决阻断清单_20260717.csv", list(blocked_rows[0].keys()), blocked_rows)
    write_csv(FRONT_DIR / "AMI来源裁决前端字段对齐表_20260717.csv", list(frontend_rows[0].keys()), frontend_rows)

    with (DELTA_DIR / "nodes_delta_candidate.jsonl").open("w", encoding="utf-8") as f:
        for node in delta_nodes:
            f.write(json.dumps(node, ensure_ascii=False) + "\n")
    with (DELTA_DIR / "relations_delta_candidate.jsonl").open("w", encoding="utf-8") as f:
        for rel in delta_relations:
            f.write(json.dumps(rel, ensure_ascii=False) + "\n")

    summary = {
        "sample_rows": len(rows),
        "formal_status_rows": sum(1 for r in rows if r["CDSS使用状态"].strip() == FORMAL_STATUS),
        "blocked_rows": len(blocked_rows),
        "import_ready_rows": sum(1 for r in audit_rows if r["可直接入库"] == "是"),
        "frontend_preview_rows": sum(1 for r in audit_rows if r["前端预览可用"] == "是"),
        "delta_candidate_nodes": len(delta_nodes),
        "delta_candidate_relations": len(delta_relations),
        "neo4j_written": False,
    }
    (AUDIT_DIR / "AMI来源裁决入库前审计摘要_20260717.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    front_doc = """# AMI 来源裁决前端/后端字段对齐说明

## 读取目标

前端不要再从疾病下直接捞一堆指南和证据。正式推荐卡片应读取“推荐来源裁决”结果。

## 推荐卡片字段

| 页面字段 | 后端字段 | 说明 |
|---|---|---|
| 综合推荐 | final_recommendation_综合推荐 | 医生默认看到的推荐语 |
| 适用场景 | clinical_scenario_适用场景 | 推荐适用于哪类患者 |
| 主依据指南 | primary_guideline_name_主依据指南 | 默认展示的一份主依据 |
| 支持依据 | supporting_guideline_names_支持依据 | 展开后显示 |
| 冲突状态 | conflict_status_冲突状态 | 决定是否进入正式推荐区 |
| CDSS状态 | cdss_use_status_CDSS状态 | 正式推荐、冲突待裁决等 |
| 推荐动作 | action_name_推荐动作名称 | 用于和医嘱/路径动作对接 |

## 展示规则

1. `CDSS状态=正式推荐` 且 `冲突状态=无冲突/有冲突已处理`，才允许进入正式推荐区。
2. `冲突待裁决` 只能进入冲突/阻断区，不能主动推荐。
3. 本轮 AMI 样板包用于字段对齐；由于缺主证据编码、推荐等级、证据等级和动作编码，不能直接导入 Neo4j。
"""
    (FRONT_DIR / "AMI来源裁决前端字段对齐说明_20260717.md").write_text(front_doc, encoding="utf-8")

    report = f"""# AMI 来源裁决入库前审计报告 2026-07-17

## 审计结论

- 样板行数：{summary['sample_rows']}
- 标记为正式推荐的行数：{summary['formal_status_rows']}
- 前端预览可用行数：{summary['frontend_preview_rows']}
- 可直接入库行数：{summary['import_ready_rows']}
- 阻断行数：{summary['blocked_rows']}

## 关键判断

本轮 AMI 样板包可以用于 Trae/后端字段对齐，但不能直接作为正式 Neo4j 入库包。原因是样板包尚未补齐主证据编码、推荐等级、证据等级和标准推荐动作编码；抗血小板治疗还存在“冲突待裁决”，需要按 STEMI/NSTEMI/出血风险进一步拆分。

## 已生成文件

- `02_入库前审计/AMI来源裁决入库前审计结果_20260717.csv`
- `02_入库前审计/AMI来源裁决阻断清单_20260717.csv`
- `03_前端字段对齐/AMI来源裁决前端字段对齐表_20260717.csv`
- `03_前端字段对齐/AMI来源裁决前端字段对齐说明_20260717.md`
- `04_delta候选包_不可直接入库/nodes_delta_candidate.jsonl`
- `04_delta候选包_不可直接入库/relations_delta_candidate.jsonl`

## 下一步

回到 AMI 原文证据，补齐每条正式推荐的主证据编码、推荐等级、证据等级和动作编码；完成后再生成正式可入库 delta 包。
"""
    (AUDIT_DIR / "AMI来源裁决入库前审计报告_20260717.md").write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
