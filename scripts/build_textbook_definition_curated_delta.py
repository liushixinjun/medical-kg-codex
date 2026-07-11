from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_anchor_matrix" / "textbook_skeleton_matrix_priority_four_20260708.csv"
OUT = ROOT / "心血管内科文献集合" / "00_教材骨架库_foundation_skeleton" / "20260708_textbook_definition_delta_curated"
TEXTBOOK = "《内科学（第10版）》"


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"N\s*O\s*T\s*E\s*S", "", text, flags=re.IGNORECASE).strip()
    return text


CURATED: dict[str, dict[str, object]] = {
    "DIS-CARD-CAD-UA": {
        "definition": "不稳定型心绞痛（UA）属于非ST段抬高型急性冠脉综合征，是有新发心肌缺血（包括静息状态下缺血）但不伴有心肌坏死的临床状态。",
        "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 急性冠脉综合征 > 不稳定型心绞痛和非ST段抬高型心肌梗死",
        "docx_paragraph_start": 5128,
        "docx_paragraph_end": 5129,
        "pdf_page_start": 242,
        "pdf_page_end": 242,
    },
    "DIS-CARD-CAD-NSTEMI": {
        "definition": "非ST段抬高型心肌梗死（NSTEMI）属于非ST段抬高型急性冠脉综合征，表现为较严重心肌缺血，并伴有心肌损害和心肌坏死标志物升高。",
        "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 急性冠脉综合征 > 不稳定型心绞痛和非ST段抬高型心肌梗死",
        "docx_paragraph_start": 5128,
        "docx_paragraph_end": 5129,
        "pdf_page_start": 242,
        "pdf_page_end": 242,
    },
    "DIS-CARD-CAD-AMI": {
        "definition": "急性心肌梗死（AMI）是急性冠脉综合征的重要类型，临床上分为5型，其中最常见的是原发冠脉不稳定斑块破裂、糜烂或侵蚀继发血栓形成导致的自发性AMI。",
        "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 急性冠脉综合征",
        "docx_paragraph_start": 5122,
        "docx_paragraph_end": 5127,
        "pdf_page_start": 242,
        "pdf_page_end": 242,
    },
    "DIS-CARD-CAD-POST-MI-SYNDROME": {
        "definition": "心肌梗死后综合征也称Dressler综合征，是AMI后数周至数月内出现、可反复发生的综合征。",
        "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 急性冠脉综合征 > 急性ST段抬高型心肌梗死",
        "docx_paragraph_start": 5340,
        "docx_paragraph_end": 5340,
        "pdf_page_start": 255,
        "pdf_page_end": 255,
    },
    "DIS-CARD-CAD-OLD-MI": {
        "definition": "陈旧性心肌梗死是急性心肌梗死坏死组织逐渐纤维化，并在6～8周形成瘢痕愈合后的状态。",
        "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 急性冠脉综合征 > 急性ST段抬高型心肌梗死 > 病理",
        "docx_paragraph_start": 5221,
        "docx_paragraph_end": 5222,
        "pdf_page_start": 247,
        "pdf_page_end": 247,
    },
    "DIS-CARD-CAD-SILENT-ISCHEMIA": {
        "definition": "隐匿型冠心病或无症状性冠心病是指没有心绞痛症状，但有心肌缺血客观证据的冠心病。",
        "source_section_path": "动脉粥样硬化和冠状动脉粥样硬化性心脏病 > 慢性冠状动脉综合征 > 隐匿型冠心病",
    },
    "DIS-CARD-HF-LEFT": {
        "definition": "左心衰竭是左心室代偿功能不全所致的心力衰竭，临床上较为常见。",
        "source_section_path": "心力衰竭 > 心力衰竭总论 > 类型",
        "docx_paragraph_start": 3913,
        "docx_paragraph_end": 3913,
        "pdf_page_start": 176,
        "pdf_page_end": 176,
    },
    "DIS-CARD-HF-RIGHT": {
        "definition": "右心衰竭是右心室代偿功能不全所致的心力衰竭。",
        "source_section_path": "心力衰竭 > 心力衰竭总论 > 类型",
        "docx_paragraph_start": 3913,
        "docx_paragraph_end": 3913,
        "pdf_page_start": 176,
        "pdf_page_end": 176,
    },
    "DIS-CARD-HF-BIVENTRICULAR": {
        "definition": "全心衰竭是左心衰竭和右心衰竭同时存在的心力衰竭。",
        "source_section_path": "心力衰竭 > 心力衰竭总论 > 类型",
        "docx_paragraph_start": 3913,
        "docx_paragraph_end": 3913,
        "pdf_page_start": 176,
        "pdf_page_end": 176,
    },
    "DIS-CARD-HF-HFrEF": {
        "definition": "射血分数降低的心力衰竭（HFrEF）是指左心室射血分数≤40%的心力衰竭，即传统概念中的收缩性心衰。",
        "source_section_path": "心力衰竭 > 心力衰竭总论 > 按左心室射血分数分类",
        "docx_paragraph_start": 3917,
        "docx_paragraph_end": 3917,
        "pdf_page_start": 176,
        "pdf_page_end": 176,
    },
    "DIS-CARD-HF-HFmrEF": {
        "definition": "射血分数轻度降低型心力衰竭（HFmrEF）是指左心室射血分数为41%～49%的心力衰竭，以轻度收缩功能障碍为主。",
        "source_section_path": "心力衰竭 > 心力衰竭总论 > 按左心室射血分数分类",
        "docx_paragraph_start": 3917,
        "docx_paragraph_end": 3917,
        "pdf_page_start": 176,
        "pdf_page_end": 176,
    },
    "DIS-CARD-HF-HFpEF": {
        "definition": "射血分数保留型心力衰竭（HFpEF）是指左心室射血分数≥50%的心力衰竭，通常存在充盈压升高、舒张功能受损的表现。",
        "source_section_path": "心力衰竭 > 心力衰竭总论 > 按左心室射血分数分类",
        "docx_paragraph_start": 3917,
        "docx_paragraph_end": 3917,
        "pdf_page_start": 176,
        "pdf_page_end": 176,
    },
    "DIS-CARD-HF-CHF": {
        "definition": "慢性心力衰竭是一个缓慢发展的心力衰竭过程，一般有代偿性心脏扩大或肥厚及其他代偿机制参与。",
        "source_section_path": "心力衰竭 > 心力衰竭总论 > 类型",
        "docx_paragraph_start": 3914,
        "docx_paragraph_end": 3916,
        "pdf_page_start": 176,
        "pdf_page_end": 176,
    },
    "DIS-CARD-ARR-AVB1": {
        "definition": "一度房室传导阻滞是房室传导时间延长，但全部心房冲动仍能传导至心室的房室传导阻滞。",
        "source_section_path": "心律失常 > 心脏传导阻滞 > 房室传导阻滞",
        "docx_paragraph_start": 4652,
        "docx_paragraph_end": 4652,
        "pdf_page_start": 213,
        "pdf_page_end": 213,
    },
    "DIS-CARD-ARR-AVB2": {
        "definition": "二度房室传导阻滞是部分心房冲动不能传导至心室的房室传导阻滞，可分为Ⅰ型（文氏阻滞）和Ⅱ型。",
        "source_section_path": "心律失常 > 心脏传导阻滞 > 房室传导阻滞",
        "docx_paragraph_start": 4652,
        "docx_paragraph_end": 4652,
        "pdf_page_start": 213,
        "pdf_page_end": 213,
    },
    "DIS-CARD-ARR-AVB3": {
        "definition": "三度房室传导阻滞又称完全性房室传导阻滞，是全部心房冲动不能传导至心室，心房和心室节律由各自独立起搏点控制的房室传导阻滞。",
        "source_section_path": "心律失常 > 心脏传导阻滞 > 房室传导阻滞",
        "docx_paragraph_start": 4652,
        "docx_paragraph_end": 4652,
        "pdf_page_start": 213,
        "pdf_page_end": 213,
    },
    "DIS-CARD-ARR-SVT": {
        "definition": "室上性心动过速简称室上速，是临床上统称的阵发性室上性心动过速，表现为规律而快速、突然发作与终止、心电图多为QRS波群形态正常且RR间期规则的快速心律。",
        "source_section_path": "心律失常 > 房室交界性心律失常 > 房室交界区相关的折返性心动过速",
    },
    "DIS-CARD-ARR-PSVT": {
        "definition": "阵发性室上性心动过速（PSVT）是房室交界区相关折返性心动过速在临床上的统称，呈规律快速心动过速，突然发作与终止。",
        "source_section_path": "心律失常 > 房室交界性心律失常 > 房室交界区相关的折返性心动过速",
    },
    "DIS-CARD-ARR-AVNRT": {
        "definition": "房室结折返性心动过速（AVNRT）是折返环路位于房室结内的房室交界区相关折返性心动过速。",
        "source_section_path": "心律失常 > 房室交界性心律失常 > 房室结折返性心动过速",
        "docx_paragraph_start": 4478,
        "docx_paragraph_end": 4493,
        "pdf_page_start": 204,
        "pdf_page_end": 205,
    },
    "DIS-CARD-ARR-AVRT": {
        "definition": "房室折返性心动过速（AVRT）是通过旁道产生的心动过速，可由房室交界区、旁道与心房、心室共同组成折返环路。",
        "source_section_path": "心律失常 > 房室交界性心律失常 > 房室折返性心动过速",
        "docx_paragraph_start": 4506,
        "docx_paragraph_end": 4509,
        "pdf_page_start": 205,
        "pdf_page_end": 205,
    },
    "DIS-CARD-ARR-WPW": {
        "definition": "预激综合征是心室预激引发房室折返性心动过速的综合征，其中由Kent束引发者称为Wolf-Parkinson-White综合征或典型预激综合征。",
        "source_section_path": "心律失常 > 房室交界性心律失常 > 房室折返性心动过速",
        "docx_paragraph_start": 4508,
        "docx_paragraph_end": 4510,
        "pdf_page_start": 205,
        "pdf_page_end": 205,
    },
    "DIS-CARD-ARR-TDP": {
        "definition": "尖端扭转型室性心动过速（TdP）是多形性室速的特殊类型，发作时QRS波群振幅与波峰呈周期性改变，宛如围绕等电位线连续扭转。",
        "source_section_path": "心律失常 > 室性心律失常 > 特殊类型的室性心动过速",
        "docx_paragraph_start": 4601,
        "docx_paragraph_end": 4602,
        "pdf_page_start": 210,
        "pdf_page_end": 210,
    },
    "DIS-CARD-ARR-NSVT": {
        "definition": "非持续性室性心动过速是发作时间短于30秒、能自行终止的室性心动过速。",
        "source_section_path": "心律失常 > 室性心律失常 > 室性心动过速",
        "docx_paragraph_start": 4573,
        "docx_paragraph_end": 4576,
        "pdf_page_start": 209,
        "pdf_page_end": 209,
    },
    "DIS-CARD-ARR-LQTS": {
        "definition": "长QT间期综合征（LQTS）是可分为先天性和获得性的离子通道病，表现为QT间期延长，并可导致晕厥和/或猝死。",
        "source_section_path": "心律失常 > 遗传性心律失常综合征",
        "docx_paragraph_start": 4624,
        "docx_paragraph_end": 4626,
        "pdf_page_start": 212,
        "pdf_page_end": 212,
    },
    "DIS-CARD-ARR-BRUGADA": {
        "definition": "Brugada综合征是与钠离子通道和钙离子通道基因突变相关的遗传性心律失常综合征，临床可表现为反复晕厥，是中青年非器质性心脏病猝死的重要原因。",
        "source_section_path": "心律失常 > 遗传性心律失常综合征",
        "docx_paragraph_start": 4627,
        "docx_paragraph_end": 4633,
        "pdf_page_start": 212,
        "pdf_page_end": 212,
    },
    "DIS-CARD-ARR-CPVT": {
        "definition": "儿茶酚胺敏感性室性心动过速（CPVT）是一种罕见的遗传性室速，病人常无明显结构性心脏病，症状多在运动或情绪激动时发生。",
        "source_section_path": "心律失常 > 遗传性心律失常综合征",
        "docx_paragraph_start": 4637,
        "docx_paragraph_end": 4637,
        "pdf_page_start": 212,
        "pdf_page_end": 212,
    },
    "DIS-CARD-ARR-SQTS": {
        "definition": "短QT间期综合征（SQTS）是单基因突变引起的常染色体显性遗传离子通道病，可表现为心悸、头晕及反复发作的晕厥和/或心脏性猝死。",
        "source_section_path": "心律失常 > 遗传性心律失常综合征",
        "docx_paragraph_start": 4638,
        "docx_paragraph_end": 4638,
        "pdf_page_start": 213,
        "pdf_page_end": 213,
    },
    "DIS-CARD-ARR-ERS": {
        "definition": "早期复极综合征是心电复极异常的一种，为生理性心电图变异；在有心搏骤停史或记录到多形性室速、特发性室颤时，可诊断早期复极综合征。",
        "source_section_path": "心律失常 > 遗传性心律失常综合征",
        "docx_paragraph_start": 4639,
        "docx_paragraph_end": 4639,
        "pdf_page_start": 213,
        "pdf_page_end": 213,
    },
    "DIS-CARD-SCD-ARREST": {
        "definition": "心脏骤停（CA）是指心脏射血功能突然终止，造成全身血液循环中断、呼吸停止和意识丧失。",
        "source_section_path": "心脏骤停与心脏性猝死",
        "docx_paragraph_start": 7006,
        "docx_paragraph_end": 7010,
        "pdf_page_start": 328,
        "pdf_page_end": 328,
    },
    "DIS-CARD-SCD-SUDDEN": {
        "definition": "心脏性猝死（SCD）是指急性症状发作后1小时内发生的以意识突然丧失为特征、由心脏原因引起的自然死亡。",
        "source_section_path": "心脏骤停与心脏性猝死",
        "docx_paragraph_start": 7011,
        "docx_paragraph_end": 7011,
        "pdf_page_start": 328,
        "pdf_page_end": 328,
    },
}


def read_matrix() -> dict[str, dict[str, str]]:
    with MATRIX.open("r", encoding="utf-8-sig", newline="") as f:
        return {r["disease_code"]: r for r in csv.DictReader(f)}


def int_value(value: object, fallback: str | None = None) -> int:
    if value is None or str(value).strip() == "":
        value = fallback
    if value is None or str(value).strip() == "":
        raise ValueError("missing integer field")
    return int(str(value).strip())


def build_item(code: str, spec: dict[str, object], matrix: dict[str, dict[str, str]], generated_at: str) -> dict[str, object]:
    row = matrix.get(code, {})
    definition = clean_text(str(spec["definition"]))
    if len(definition) < 12:
        raise ValueError(f"{code}: definition too short")
    if "N O T E S" in definition or "本章数字资源" in definition:
        raise ValueError(f"{code}: noisy definition")
    section = str(spec.get("source_section_path") or row.get("source_section_path") or "").strip()
    if not section:
        raise ValueError(f"{code}: missing source_section_path")
    return {
        "op": "update_disease_textbook_definition",
        "match": {"label": "Disease", "property": "code", "value": code},
        "set": {
            "definition": definition,
            "description": definition,
            "definition_source_type": "authoritative_textbook",
            "definition_source_name": TEXTBOOK,
            "definition_source_section_path": section,
            "definition_docx_paragraph_start": int_value(spec.get("docx_paragraph_start"), row.get("docx_paragraph_start")),
            "definition_docx_paragraph_end": int_value(spec.get("docx_paragraph_end"), row.get("docx_paragraph_end")),
            "definition_pdf_page_start": int_value(spec.get("pdf_page_start"), row.get("pdf_page_start")),
            "definition_pdf_page_end": int_value(spec.get("pdf_page_end"), row.get("pdf_page_end")),
            "definition_skeleton_slot": "overview",
            "definition_knowledge_layer": "textbook_core",
            "textbook_anchor_status": "curated_from_textbook_after_manual_anchor_review",
            "textbook_anchor_generated_at": generated_at,
        },
        "source_matrix": {
            "match_type": row.get("match_type", "manual_external_textbook_anchor"),
            "match_score": row.get("match_score", ""),
            "hit_text": row.get("hit_text", ""),
            "source_section_path": row.get("source_section_path", ""),
            "curated_reason": "教材原文锚点人工校准，自动候选不足或落点不准。",
        },
    }


def main() -> int:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    OUT.mkdir(parents=True, exist_ok=True)
    matrix = read_matrix()
    items = [build_item(code, spec, matrix, generated_at) for code, spec in CURATED.items()]
    codes = [i["match"]["value"] for i in items]
    duplicates = sorted({c for c in codes if codes.count(c) > 1})
    if duplicates:
        raise SystemExit(f"duplicate codes: {duplicates}")

    delta_path = OUT / "delta_disease_definition_update_curated30_20260708.jsonl"
    with delta_path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    detail_path = OUT / "preimport_validation_detail_curated30_20260708.csv"
    with detail_path.open("w", encoding="utf-8-sig", newline="") as f:
        fields = [
            "disease_code", "disease_name", "definition", "source_section_path",
            "docx_paragraph_start", "docx_paragraph_end", "pdf_page_start", "pdf_page_end", "validation_status",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for item in items:
            s = item["set"]
            code = item["match"]["value"]
            w.writerow({
                "disease_code": code,
                "disease_name": matrix.get(code, {}).get("disease_name", code),
                "definition": s["definition"],
                "source_section_path": s["definition_source_section_path"],
                "docx_paragraph_start": s["definition_docx_paragraph_start"],
                "docx_paragraph_end": s["definition_docx_paragraph_end"],
                "pdf_page_start": s["definition_pdf_page_start"],
                "pdf_page_end": s["definition_pdf_page_end"],
                "validation_status": "passed",
            })

    blocked = [
        {"disease_code": "DIS-CARD-HF-POST-MI", "disease_name": "心肌梗死后心力衰竭", "reason": "教材仅说明心肌梗死可导致心衰，未给出独立疾病定义。"},
        {"disease_code": "DIS-CARD-HF-DIALYSIS-CHF", "disease_name": "透析患者慢性心力衰竭", "reason": "教材未定位到独立定义，需要肾脏病/透析或心衰专项指南补充。"},
        {"disease_code": "DIS-CARD-ARR-BRADY", "disease_name": "缓慢性心律失常", "reason": "教材未以该名称给出总论定义，需作为疾病大类或从指南补充。"},
        {"disease_code": "DIS-CARD-ARR-VA", "disease_name": "室性心律失常", "reason": "教材为章节类目，未给出独立疾病定义；下级室早、室速、室扑/室颤已可分别维护。"},
        {"disease_code": "DIS-CARD-CM-ATRIAL", "disease_name": "心房心肌病", "reason": "教材未定位到定义，需指南/共识补充。"},
        {"disease_code": "DIS-CARD-CM-FABRY", "disease_name": "法布雷病心肌病", "reason": "教材心肌病章节仅在鉴别诊断列表出现，不能作为定义。"},
        {"disease_code": "DIS-CARD-CM-AMYLOID", "disease_name": "淀粉样变心肌病", "reason": "教材心肌病章节仅在鉴别诊断列表出现，不能作为定义。"},
        {"disease_code": "DIS-CARD-CM-ABVC", "disease_name": "致心律失常性双心室心肌病", "reason": "教材未定位到定义，需心肌病专项指南补充。"},
        {"disease_code": "DIS-CARD-CM-ALVC", "disease_name": "致心律失常性左心室心肌病", "reason": "教材未定位到定义，需心肌病专项指南补充。"},
        {"disease_code": "DIS-CARD-CM-ACM", "disease_name": "致心律失常性心肌病", "reason": "教材未定位到定义，需心肌病专项指南补充。"},
    ]
    blocked_path = OUT / "blocked_after_curated30_20260708.csv"
    with blocked_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["disease_code", "disease_name", "reason"])
        w.writeheader()
        w.writerows(blocked)

    summary = {
        "generated_at": generated_at,
        "delta_count": len(items),
        "blocked_count": len(blocked),
        "preimport_gate_status": "passed",
        "outputs": {
            "delta_jsonl": str(delta_path),
            "validation_detail_csv": str(detail_path),
            "blocked_csv": str(blocked_path),
        },
    }
    (OUT / "preimport_validation_summary_curated30_20260708.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
