from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威")
RAW = ROOT / "01_原始下载_raw_downloads"
OUT = ROOT / "03_入库delta_import_delta"
TODAY = "20260708"


def find_file() -> str:
    hits = [p.name for p in RAW.iterdir() if p.is_file() and "透析患者慢性心力衰竭" in p.name and "中国透析患者慢性心衰管理指南" in p.name]
    return hits[0] if hits else ""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    node = {
        "code": "DIS-CARD-HF-DIALYSIS-CHF",
        "name": "透析患者慢性心力衰竭",
        "entityType": "Disease",
        "definition": "发生于维持性透析患者的慢性心力衰竭临床状态，需结合心力衰竭的症状体征、心电图、胸部影像、利钠肽、心肌损伤标志物、超声心动图和透析容量状态进行综合诊断与管理。",
        "description": "发生于维持性透析患者的慢性心力衰竭临床状态，需结合心力衰竭的症状体征、心电图、胸部影像、利钠肽、心肌损伤标志物、超声心动图和透析容量状态进行综合诊断与管理。",
        "definition_source_type": "external_authoritative_source_conditional",
        "definition_source_name": "中国透析患者慢性心力衰竭管理指南",
        "definition_source_section_path": "指南摘要与诊断/评估章节；页面提示指南系统介绍心力衰竭诊断、危险因素管理、HD管理、PD管理、药物管理及其他管理",
        "definition_authority_level": "A",
        "definition_download_file": find_file(),
        "definition_source_basis": "中华肾脏病杂志指南页面说明该指南系统介绍透析患者心力衰竭诊断、危险因素管理、血液透析管理、腹膜透析管理、药物管理及其他管理；因此该实体按“透析人群+慢性心衰临床状态”条件性入库。",
        "definition_skeleton_slot": "overview",
        "definition_knowledge_layer": "external_authority_condition_core",
        "definition_import_decision": "条件性补齐definition；后续建议从Disease调整为ClinicalCondition或DiseaseContext，避免把人群限定状态当普通独立病种。",
        "definition_confidence": "conditional",
        "definition_updated_at": generated_at,
        "external_authority_review_status": "machine_curated_conditional",
    }
    path = OUT / f"delta_external_authority_definition_dialysis_hf_{TODAY}.jsonl"
    path.write_text(json.dumps(node, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    summary = {"generated_at": generated_at, "nodes_jsonl": str(path), "node_count": 1, "code": node["code"]}
    summary_path = OUT / f"delta_external_authority_definition_dialysis_hf_summary_{TODAY}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
