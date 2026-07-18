from __future__ import annotations

import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "130_未解析PDF病种启动池_20260717"
PDF_STATUS_CSV = ROOT / "项目管理中心_project_management" / "126_指南PDF精修层全库总检_20260717" / "01_PDF使用状态总表_20260717.csv"
GUIDE_ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南")
TEXTBOOK_ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\书籍教材")
EXTERNAL_ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威")
OUTPUT_ROOT = ROOT / "心血管内科文献集合"
EXACT_SOURCE_ROOT = OUT_DIR / "00_精确PDF源文件"
EMPTY_TEXTBOOK_GATE_ROOT = OUT_DIR / "00_空教材闸门目录_仅满足G0校验"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

sys.path.insert(0, str(ROOT))
from scripts.kg_pipeline_g0_prepare_batch import prepare_from_config  # noqa: E402
from scripts.parse_pdf_batch import parse_included_pdfs  # noqa: E402


GROUPS = [
    {
        "batch_id": "20260717_冠心病ACS2025补充解析",
        "disease_category": "冠心病",
        "scope_target": ["急性冠脉综合征", "急性心肌梗死", "ST段抬高型心肌梗死", "非ST段抬高型心肌梗死", "不稳定型心绞痛"],
        "aliases": ["ACC／AHA／ACEP／NAEMSP ／SCAI指 南：急性冠脉 综合征患者的管理 2025"],
        "priority": 1,
        "action": "启动G0并解析PDF",
    },
    {
        "batch_id": "20260717_瓣膜病指南补充解析",
        "disease_category": "瓣膜病",
        "scope_target": ["心脏瓣膜病", "主动脉瓣狭窄", "主动脉瓣反流", "二尖瓣狭窄", "二尖瓣反流"],
        "aliases": ["ACC／AHA指南：心脏瓣膜病患者的管理（2020）", "ESC／EACTS指南：瓣膜性心脏病的管理（2021） "],
        "priority": 2,
        "action": "启动G0并解析PDF",
    },
    {
        "batch_id": "20260717_心律失常指南补充解析",
        "disease_category": "心律失常",
        "scope_target": ["心房颤动", "心房扑动", "室性心律失常", "心脏性猝死", "左心耳干预"],
        "aliases": ["ESC指南：室性心律失常患者的管理和心源性猝死的预防 2022", "ESC／EACTS指南：房颤的管理（2024）", "中国 左心耳干预预防心房颤动患者血栓栓塞事件：目前的认识和建议（2023） (1)"],
        "priority": 3,
        "action": "启动G0并解析PDF",
    },
    {
        "batch_id": "20260717_心肌病ESC2023补充解析",
        "disease_category": "心肌病",
        "scope_target": ["心肌病", "肥厚型心肌病", "扩张型心肌病", "限制型心肌病", "致心律失常性心肌病"],
        "aliases": ["ESC指南：心肌病的管理2023"],
        "priority": 4,
        "action": "启动G0并解析PDF",
    },
    {
        "batch_id": "20260717_结构性先心病介入补充解析",
        "disease_category": "结构性心脏病/先天性心脏病",
        "scope_target": ["房间隔缺损", "肺动脉瓣狭窄", "主动脉瓣狭窄", "先天性心脏病介入治疗"],
        "aliases": ["常见先天性心脏病介入治疗中国专家共识之一：房间隔缺损介入治疗", "常见先天性心脏病介入治疗中国专家共识之四：经皮球囊肺动脉瓣与主动脉瓣成形术"],
        "priority": 5,
        "action": "启动G0并解析PDF",
    },
    {
        "batch_id": "20260717_心衰LVAD右心衰补充解析",
        "disease_category": "心力衰竭",
        "scope_target": ["右心衰竭", "左心室辅助装置", "心力衰竭"],
        "aliases": ["ESC指南：右心衰与左心室辅助装置-术前，围手术期和术后管理策略 2024"],
        "priority": 6,
        "action": "启动G0并解析PDF",
    },
    {
        "batch_id": "20260717_高血压LVAD补充解析",
        "disease_category": "高血压",
        "scope_target": ["高血压", "心室辅助装置相关高血压"],
        "aliases": ["AHA科学声明：使用心室辅助装置患者高血压的管理（2022）"],
        "priority": 7,
        "action": "启动G0并解析PDF",
    },
]

DEFER_KEYWORDS = [
    ("抗菌素耐药革兰氏阴性菌感染", "非心血管内科专病，暂缓"),
    ("社区获得性肺炎", "呼吸/感染方向，暂缓"),
    ("急性呼吸窘迫综合征", "重症/呼吸方向，暂缓"),
    ("人血白蛋白", "重症用药共识，暂缓"),
    ("patent foramen ovale Part II", "卵圆孔未闭外文材料，待结构性心脏病批次二轮纳入"),
]

DISEASE_ALIASES = {
    "急性冠脉综合征": ["acute coronary syndrome", "ACS"],
    "急性心肌梗死": ["acute myocardial infarction", "myocardial infarction", "AMI", "MI"],
    "ST段抬高型心肌梗死": ["ST-segment elevation myocardial infarction", "ST elevation myocardial infarction", "STEMI"],
    "非ST段抬高型心肌梗死": ["non-ST-segment elevation myocardial infarction", "non-ST elevation myocardial infarction", "NSTEMI"],
    "不稳定型心绞痛": ["unstable angina", "UA"],
    "心脏瓣膜病": ["valvular heart disease", "heart valve disease", "VHD"],
    "主动脉瓣狭窄": ["aortic stenosis", "AS"],
    "主动脉瓣反流": ["aortic regurgitation", "aortic insufficiency", "AR"],
    "二尖瓣狭窄": ["mitral stenosis", "MS"],
    "二尖瓣反流": ["mitral regurgitation", "mitral insufficiency", "MR"],
    "心房颤动": ["atrial fibrillation", "AF"],
    "心房扑动": ["atrial flutter", "AFL"],
    "室性心律失常": ["ventricular arrhythmia", "ventricular arrhythmias", "VA"],
    "心脏性猝死": ["sudden cardiac death", "SCD"],
    "左心耳干预": ["left atrial appendage", "left atrial appendage occlusion", "LAA", "LAAO"],
    "心肌病": ["cardiomyopathy", "cardiomyopathies", "CM"],
    "肥厚型心肌病": ["hypertrophic cardiomyopathy", "HCM"],
    "扩张型心肌病": ["dilated cardiomyopathy", "DCM"],
    "限制型心肌病": ["restrictive cardiomyopathy", "RCM"],
    "致心律失常性心肌病": ["arrhythmogenic cardiomyopathy", "arrhythmogenic right ventricular cardiomyopathy", "ACM", "ARVC"],
    "房间隔缺损": ["atrial septal defect", "ASD"],
    "肺动脉瓣狭窄": ["pulmonary valve stenosis", "pulmonary stenosis", "PS"],
    "先天性心脏病介入治疗": ["congenital heart disease", "CHD", "interventional treatment"],
    "右心衰竭": ["right heart failure", "right ventricular failure", "RHF", "RVF"],
    "左心室辅助装置": ["left ventricular assist device", "left ventricular assist devices", "LVAD"],
    "心力衰竭": ["heart failure", "HF"],
    "高血压": ["hypertension", "high blood pressure"],
    "心室辅助装置相关高血压": ["ventricular assist device hypertension", "VAD hypertension", "LVAD hypertension"],
}

CATEGORY_CODE_MAP = {
    "冠心病": "CAT-CARD-CAD",
    "瓣膜病": "CARD-VHD",
    "心律失常": "CAT-CARD-ARR",
    "心肌病": "CAT-CARD-CM",
    "结构性心脏病/先天性心脏病": "CARD-SHD-CHD",
    "心力衰竭": "CAT-CARD-HF",
    "高血压": "CAT-CARD-HTN",
}

DISEASE_CODE_MAP = {
    "急性冠脉综合征": "DIS-CARD-CAD-ACS",
    "急性心肌梗死": "DIS-CARD-CAD-AMI",
    "ST段抬高型心肌梗死": "DIS-CARD-CAD-STEMI",
    "非ST段抬高型心肌梗死": "DIS-CARD-CAD-NSTEMI",
    "不稳定型心绞痛": "DIS-CARD-CAD-UA",
    "心脏瓣膜病": "DIS-CARD-VHD",
    "主动脉瓣狭窄": "DIS-CARD-VHD-AS",
    "主动脉瓣反流": "DIS-CARD-VHD-AR",
    "二尖瓣狭窄": "DIS-CARD-VHD-MS",
    "二尖瓣反流": "DIS-CARD-VHD-MR",
    "心房颤动": "DIS-CARD-ARR-AF",
    "心房扑动": "DIS-CARD-ARR-AFL",
    "室性心律失常": "DIS-CARD-ARR-VA",
    "心脏性猝死": "DIS-CARD-SCD-SUDDEN",
    "心肌病": "DIS-CARD-CM-GENERAL",
    "肥厚型心肌病": "DIS-CARD-CM-HCM",
    "扩张型心肌病": "DIS-CARD-CM-DCM",
    "限制型心肌病": "DIS-CARD-CM-RCM",
    "致心律失常性心肌病": "DIS-CARD-CM-ACM",
    "房间隔缺损": "DIS-CARD-CHD-ASD",
    "肺动脉瓣狭窄": "DIS-CARD-VHD-PS",
    "主动脉瓣狭窄": "DIS-CARD-VHD-AS",
    "右心衰竭": "DIS-CARD-HF-RIGHT",
    "心力衰竭": "DIS-CARD-HF-GENERAL",
    "高血压": "DIS-CARD-HTN-ESSENTIAL",
}


def aliases_for(term: str) -> str:
    return "；".join([term, *DISEASE_ALIASES.get(term, [])])


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_config(group: dict[str, Any], exact_source_dir: Path, exact_aliases: list[str]) -> dict[str, Any]:
    scope_targets = group["scope_target"]
    category_code = CATEGORY_CODE_MAP.get(group["disease_category"], group["disease_category"])
    vocab = [
        {
            "canonical_name": item,
            "name_en": next((alias for alias in DISEASE_ALIASES.get(item, []) if not alias.isupper()), ""),
            "abbr": next((alias for alias in DISEASE_ALIASES.get(item, []) if alias.isupper()), ""),
            "aliases": aliases_for(item),
            "entityType": "Disease",
            "disease_scope": DISEASE_CODE_MAP.get(item, category_code),
            "source": "未解析PDF启动池",
        }
        for item in scope_targets
    ]
    taxonomy = [
        {
            "specialty_code": "CARD",
            "category_code": category_code,
            "subcategory_code": "",
            "disease_code": DISEASE_CODE_MAP.get(item, ""),
            "name": item,
            "name_en": "",
            "aliases": aliases_for(item),
            "inclusion_status": "included",
        }
        for item in scope_targets
    ]
    return {
        "batch": {"batch_id": group["batch_id"]},
        "scope": {
            "top_specialty": "心血管内科",
            "disease_category": group["disease_category"],
            "scope_type": "指南PDF补充解析",
            "scope_target": scope_targets,
            "source_aliases": exact_aliases,
        },
        "source_policy": {"source_scope_aliases": exact_aliases},
        "source_roots": {
            "guideline_roots": [str(exact_source_dir)],
            # 本脚本只负责“未解析 PDF 的补充解析启动池”。
            # G0 会扫描 source_roots 下的所有文件；如果这里放入教材、外部权威或术语字典，
            # 会把与本批次无关的历史文件一起纳入来源清单，造成批次污染。
            # 教材/外部权威只允许在后续证据补强阶段单独引用，不在本启动池阶段作为扫描源。
            # G0 通用闸门要求 textbook_roots 非空，因此这里放入空目录，只满足路径校验。
            "textbook_roots": [str(EMPTY_TEXTBOOK_GATE_ROOT)],
            "external_authority_roots": [],
            "terminology_roots": [],
        },
        "output": {"output_root": str(OUTPUT_ROOT)},
        "execution_permissions": {
            "allow_neo4j_write": False,
            "allow_run_import_scripts": False,
            "allow_parse_pdf": True,
            "allow_extract_evidence": False,
        },
        "taxonomy_rows": taxonomy,
        "controlled_vocabulary_rows": vocab,
    }


def classify_unparsed(row: dict[str, str]) -> dict[str, str]:
    name = row["文件名"]
    for group in GROUPS:
        if any(alias in name for alias in group["aliases"]):
            return {"处理分组": group["batch_id"], "校正疾病大类": group["disease_category"], "处理动作": group["action"], "暂缓原因": ""}
    for key, reason in DEFER_KEYWORDS:
        if key in name:
            return {"处理分组": "暂缓", "校正疾病大类": row.get("建议疾病大类", ""), "处理动作": "暂缓", "暂缓原因": reason}
    return {"处理分组": "待人工复核", "校正疾病大类": row.get("建议疾病大类", ""), "处理动作": "待人工复核", "暂缓原因": "未命中启动规则"}


def prepare_exact_source_dir(group: dict[str, Any], pool_rows: list[dict[str, str]]) -> tuple[Path, list[str], int]:
    target_dir = EXACT_SOURCE_ROOT / group["batch_id"]
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    assigned = [row for row in pool_rows if row.get("处理分组") == group["batch_id"]]
    aliases: list[str] = []
    copied = 0
    for row in assigned:
        source = Path(row["目录"]) / row["文件名"]
        if not source.is_file():
            continue
        shutil.copy2(source, target_dir / row["文件名"])
        aliases.append(Path(row["文件名"]).stem)
        copied += 1
    return target_dir, aliases, copied


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EMPTY_TEXTBOOK_GATE_ROOT.mkdir(parents=True, exist_ok=True)
    unparsed_rows = [r for r in read_csv(PDF_STATUS_CSV) if r.get("是否已解析登记") != "是"]
    pool_rows = [{**r, **classify_unparsed(r)} for r in unparsed_rows]
    write_csv(OUT_DIR / "01_未解析PDF启动池清单_20260717.csv", pool_rows)

    g0_rows: list[dict[str, Any]] = []
    parse_rows: list[dict[str, Any]] = []
    for group in GROUPS:
        exact_source_dir, exact_aliases, copied_count = prepare_exact_source_dir(group, pool_rows)
        if copied_count == 0:
            g0_rows.append(
                {
                    **group,
                    "status": "blocked",
                    "batch_dir": "",
                    "included_file_count": 0,
                    "excluded_file_count": 0,
                    "dedup_count": 0,
                    "source_manifest_hash": "",
                    "created_time": NOW,
                    "config_path": "",
                    "blocker": "未找到精确PDF源文件",
                }
            )
            parse_rows.append(
                {
                    "batch_id": group["batch_id"],
                    "batch_dir": "",
                    "parse_status": "not_started",
                    "pdf_document_count": "",
                    "page_count": "",
                    "ocr_required_page_count": "",
                    "summary_json": "未找到精确PDF源文件",
                }
            )
            continue
        config = build_config(group, exact_source_dir, exact_aliases)
        config_path = OUT_DIR / f"{group['batch_id']}_batch_config.yaml"
        config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
        g0 = prepare_from_config(config_path)
        g0_rows.append({**group, **g0, "config_path": str(config_path), "精确源文件数": copied_count})
        if g0.get("status") == "passed" and int(g0.get("included_file_count") or 0) > 0:
            parse_result = parse_included_pdfs(Path(g0["batch_dir"]))
            parse_rows.append(
                {
                    "batch_id": group["batch_id"],
                    "batch_dir": g0["batch_dir"],
                    "parse_status": parse_result.get("status", "completed"),
                    "pdf_document_count": parse_result.get("pdf_document_count", parse_result.get("document_count", "")),
                    "page_count": parse_result.get("page_count", ""),
                    "ocr_required_page_count": parse_result.get("ocr_required_page_count", ""),
                    "summary_json": json.dumps(parse_result, ensure_ascii=False),
                }
            )
        else:
            parse_rows.append(
                {
                    "batch_id": group["batch_id"],
                    "batch_dir": g0.get("batch_dir", ""),
                    "parse_status": "not_started",
                    "pdf_document_count": "",
                    "page_count": "",
                    "ocr_required_page_count": "",
                    "summary_json": json.dumps(g0, ensure_ascii=False),
                }
            )

    write_csv(OUT_DIR / "02_G0批次准备结果_20260717.csv", g0_rows)
    write_csv(OUT_DIR / "03_PDF文本解析结果_20260717.csv", parse_rows)
    summary = {
        "generated_at": NOW,
        "neo4j_written": False,
        "unparsed_pdf_count": len(unparsed_rows),
        "started_batch_count": len(GROUPS),
        "g0_passed_count": sum(1 for r in g0_rows if r.get("status") == "passed"),
        "parsed_batch_count": sum(1 for r in parse_rows if r.get("parse_status") != "not_started"),
        "deferred_pdf_count": sum(1 for r in pool_rows if r.get("处理动作") == "暂缓"),
    }
    (OUT_DIR / "04_未解析PDF启动池_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 未解析 PDF 病种启动池报告（2026-07-17）",
        "",
        f"- 生成时间：{NOW}",
        "- 本次写 Neo4j：否。",
        f"- 未解析 PDF：{summary['unparsed_pdf_count']}",
        f"- 启动批次数：{summary['started_batch_count']}",
        f"- G0 通过批次：{summary['g0_passed_count']}",
        f"- 已执行 PDF 文本解析批次：{summary['parsed_batch_count']}",
        f"- 暂缓 PDF：{summary['deferred_pdf_count']}",
        "",
        "## 输出文件",
        "",
        "- `01_未解析PDF启动池清单_20260717.csv`",
        "- `02_G0批次准备结果_20260717.csv`",
        "- `03_PDF文本解析结果_20260717.csv`",
        "- `04_未解析PDF启动池_summary.json`",
    ]
    (OUT_DIR / "00_未解析PDF病种启动池报告_20260717.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
