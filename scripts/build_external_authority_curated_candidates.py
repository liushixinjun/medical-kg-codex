from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威")
RAW = ROOT / "01_原始下载_raw_downloads"
OUT = ROOT / "02_结构化候选_structured_candidates"
TODAY = "20260708"


def file_name(*parts: str) -> str:
    hits = [p for p in RAW.iterdir() if p.is_file() and all(part in p.name for part in parts)]
    return hits[0].name if hits else ""


def main() -> int:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        {
            "disease_code": "DIS-CARD-ARR-VA",
            "disease_name": "室性心律失常",
            "candidate_definition_zh": "起源于心室的异常心律谱系，主要包括室性早搏、非持续性或持续性室性心动过速、尖端扭转型室速、室颤、电风暴等类型。",
            "source_name": "2022 ESC室性心律失常与心脏性猝死预防指南",
            "source_type": "guideline",
            "authority_level": "A",
            "download_file": file_name("室性心律失常", "GuardHeart备份"),
            "evidence_location": "PDF page 15, section 3.1 Ventricular arrhythmia subtypes",
            "source_basis": "定义章节逐项列出PVC、VT、NSVT、SMVT/SPVT、TdP、VF、电风暴等室性心律失常亚型。",
            "can_import_as_definition": "yes",
            "import_decision": "可作为疾病/大类定义；同时建议把PVC、VT、VF、电风暴作为下级实体或子类型维护。",
        },
        {
            "disease_code": "DIS-CARD-ARR-BRADY",
            "disease_name": "缓慢性心律失常",
            "candidate_definition_zh": "以窦性心动过缓、异位房性心动过缓、窦房传导阻滞或停搏、房室传导阻滞等导致心率过慢或传导延迟为主要表现的一组心律失常。",
            "source_name": "2018 ACC/AHA/HRS缓慢性心律失常与传导延迟指南摘要",
            "source_type": "guideline_summary",
            "authority_level": "A",
            "download_file": file_name("缓慢性心律失常", "ACC_AHA_HRS"),
            "evidence_location": "PDF page 8, section 2.1 Definitions, Table 3",
            "source_basis": "定义表列出窦房结功能障碍、窦性心动过缓、异位房性心动过缓、窦房传导阻滞、窦性停搏、慢快综合征、变时功能不全等。",
            "can_import_as_definition": "yes",
            "import_decision": "可作为疾病大类定义；具体传导阻滞和窦房结疾病应保留下级实体。",
        },
        {
            "disease_code": "DIS-CARD-CM-ACM",
            "disease_name": "致心律失常性心肌病",
            "candidate_definition_zh": "以心肌结构和功能异常，并伴室性心律失常为核心特征的一组心肌病谱系，可表现为右室、左室或双心室受累。",
            "source_name": "2023 ESC心肌病管理指南",
            "source_type": "guideline",
            "authority_level": "A",
            "download_file": file_name("致心律失常性心肌病", "ESC心肌病指南全文"),
            "evidence_location": "PDF page 12, section 3.2 classification discussion",
            "source_basis": "指南说明arrhythmogenic cardiomyopathies指一组具有心肌结构/功能异常和室性心律失常特征的情况。",
            "can_import_as_definition": "yes",
            "import_decision": "可作为谱系定义；下级ARVC/ALVC/双心室型需按表型分别维护。",
        },
        {
            "disease_code": "DIS-CARD-CM-ARVC",
            "disease_name": "致心律失常性右心室心肌病",
            "candidate_definition_zh": "以右心室扩张和/或功能障碍为主，并结合组织学受累和/或心电异常等诊断标准的一种致心律失常性心肌病表型，可伴左室受累。",
            "source_name": "2023 ESC心肌病管理指南",
            "source_type": "guideline",
            "authority_level": "A",
            "download_file": file_name("致心律失常性心肌病", "ESC心肌病指南全文"),
            "evidence_location": "PDF page 14, section 3.2.4 Arrhythmogenic right ventricular cardiomyopathy",
            "source_basis": "指南明确ARVC定义为以右室扩张和/或功能障碍为主，并依据已发表标准结合组织学/心电异常。",
            "can_import_as_definition": "yes",
            "import_decision": "可正式补充ARVC定义；如当前缺口不含ARVC，也可作为同谱系质量增强。",
        },
        {
            "disease_code": "DIS-CARD-CM-ALVC",
            "disease_name": "致心律失常性左心室心肌病",
            "candidate_definition_zh": "以左心室为主的致心律失常性心肌病表型，常表现为非缺血性左室瘢痕或脂肪替代，可伴区域或整体运动异常；在ESC指南中多归入非扩张型左室心肌病表型管理。",
            "source_name": "2023 ESC心肌病管理指南",
            "source_type": "guideline",
            "authority_level": "A",
            "download_file": file_name("致心律失常性心肌病", "ESC心肌病指南全文"),
            "evidence_location": "PDF page 13, NDLVC phenotype definition and ALVC naming discussion",
            "source_basis": "指南说明NDLVC表型包括过去被称为ALVC、左优势ARVC或arrhythmogenic DCM的情况。",
            "can_import_as_definition": "conditional",
            "import_decision": "可作为中文说明候选；正式入库前应标注与NDLVC/ACM谱系的关系，避免把历史命名当独立标准病种。",
        },
        {
            "disease_code": "DIS-CARD-CM-ABVC",
            "disease_name": "致心律失常性双心室心肌病",
            "candidate_definition_zh": "致心律失常性心肌病中同时累及左、右心室的表型，表现为双心室结构或功能异常并伴室性心律失常风险。",
            "source_name": "2023 ESC心肌病管理指南",
            "source_type": "guideline",
            "authority_level": "A",
            "download_file": file_name("致心律失常性心肌病", "ESC心肌病指南全文"),
            "evidence_location": "PDF page 14, ARVC broader concept includes biventricular disease",
            "source_basis": "指南说明ARVC概念已扩展到可包括双心室或左优势疾病。",
            "can_import_as_definition": "conditional",
            "import_decision": "可作为ACM谱系分型候选；需在图谱中用subtype_of连接ACM，避免孤立疾病化。",
        },
        {
            "disease_code": "DIS-CARD-CM-FABRY",
            "disease_name": "法布雷病心肌病",
            "candidate_definition_zh": "由GLA基因致病变异导致α-半乳糖苷酶A活性不足，引起糖鞘脂在多器官细胞内蓄积；累及心脏时可表现为左室肥厚、心肌纤维化、心律失常或心力衰竭等心肌病表现。",
            "source_name": "国家罕见病诊疗指南2019 + GeneReviews + 百度健康医典",
            "source_type": "government_guideline_and_expert_reference",
            "authority_level": "A/B/D",
            "download_file": file_name("法布雷病", "国家罕见病") + ";" + file_name("法布雷病", "GeneReviews") + ";" + file_name("法布雷病", "百度健康医典"),
            "evidence_location": "NHC PDF hit pages; GeneReviews disease summary; Baidu Health reviewed patient encyclopedia",
            "source_basis": "三类来源均支持GLA/α-半乳糖苷酶A缺陷和多器官蓄积病本质；心肌病表述需结合心内教材/指南。",
            "can_import_as_definition": "conditional",
            "import_decision": "可补基础定义，但需要保留source_priority，百度健康仅作辅助别名/患者教育，不作为推荐证据。",
        },
        {
            "disease_code": "DIS-CARD-CM-ATRIAL",
            "disease_name": "心房心肌病",
            "candidate_definition_zh": "影响心房结构、构筑、收缩或电生理特性的改变所构成的综合状态，并可能产生临床相关表现。",
            "source_name": "EHRA/HRS/APHRS/SOLAECE心房心肌病专家共识2016",
            "source_type": "expert_consensus",
            "authority_level": "A",
            "download_file": file_name("心房心肌病", "PMC"),
            "evidence_location": "Consensus definition section",
            "source_basis": "专家共识给出心房心肌病正式定义。",
            "can_import_as_definition": "yes",
            "import_decision": "可作为正式定义候选，需中文翻译入库并保留英文原文摘要。",
        },
        {
            "disease_code": "DIS-CARD-CM-AMYLOID",
            "disease_name": "淀粉样变心肌病",
            "candidate_definition_zh": "由淀粉样蛋白纤维沉积或蓄积于心肌或心脏组织所致的浸润性心肌病，可导致心室壁增厚、舒张/收缩功能受损和心律失常等表现。",
            "source_name": "ESC心脏淀粉样变诊断与治疗立场声明2021",
            "source_type": "expert_consensus",
            "authority_level": "A",
            "download_file": file_name("淀粉样变心肌病", "PMC") + ";" + file_name("淀粉样变心肌病", "开放PDF"),
            "evidence_location": "PMC/PDF definition and classification sections",
            "source_basis": "ESC工作组立场声明支持心脏淀粉样变的浸润性心肌病属性。",
            "can_import_as_definition": "yes",
            "import_decision": "可作为正式定义候选，并区分ATTR-CM、AL amyloidosis等下级/别名。",
        },
        {
            "disease_code": "DIS-CARD-HF-POST-MI",
            "disease_name": "心肌梗死后心力衰竭",
            "candidate_definition_zh": "心肌梗死后因心肌细胞死亡、瘢痕形成、心室重构、持续缺血或神经体液激活等机制导致或加重的心力衰竭临床状态，可发生于住院期间或远期随访阶段。",
            "source_name": "2022 AHA/ACC/HFSA心衰指南 + 2023 ESC急性冠脉综合征指南 + PMC综述",
            "source_type": "guideline_and_review",
            "authority_level": "A/B",
            "download_file": file_name("心肌梗死后心力衰竭", "AHA_ACC_HFSA") + ";" + file_name("心肌梗死后心力衰竭", "ESC急性冠脉综合征") + ";" + file_name("心肌梗死后心力衰竭", "PMC综述"),
            "evidence_location": "HF guideline stage B/post-MI references; ACS long-term management; PMC mechanism summary",
            "source_basis": "指南支持MI后HF风险与管理，综述支持MI后HF发生机制；该项更适合作为临床状态/并发症，不宜孤立为标准疾病。",
            "can_import_as_definition": "conditional",
            "import_decision": "建议入库为ClinicalCondition或Complication，不建议作为独立Disease闭环病种。",
        },
        {
            "disease_code": "DIS-CARD-HF-DIALYSIS-CHF",
            "disease_name": "透析患者慢性心力衰竭",
            "candidate_definition_zh": "维持性透析患者合并的慢性心力衰竭临床状态，通常由容量负荷、结构性心脏病、冠心病、高血压、贫血及尿毒症相关心肌损害等多因素共同影响。",
            "source_name": "KDOQI透析患者心血管病指南页面 + KDIGO CKD心衰指南页面",
            "source_type": "guideline_page",
            "authority_level": "B",
            "download_file": file_name("透析患者慢性心力衰竭", "KDOQI") + ";" + file_name("透析患者慢性心力衰竭", "KDIGO"),
            "evidence_location": "KDOQI cardiovascular disease in dialysis patients; KDIGO HF in CKD guideline landing page",
            "source_basis": "当前仅有指南入口/页面，尚未取得可独立引用的定义全文。",
            "can_import_as_definition": "no",
            "import_decision": "暂不补正式definition；应转为合并症/人群条件模型，继续补肾脏病或透析心血管指南全文。",
        },
    ]

    out_path = OUT / f"心血管内科+剩余10条+外部权威人工候选定义+{TODAY}.csv"
    fields = [
        "generated_at",
        "disease_code",
        "disease_name",
        "candidate_definition_zh",
        "source_name",
        "source_type",
        "authority_level",
        "download_file",
        "evidence_location",
        "source_basis",
        "can_import_as_definition",
        "import_decision",
    ]
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({"generated_at": generated_at, **row})

    summary = {
        "generated_at": generated_at,
        "output": str(out_path),
        "rows": len(rows),
        "yes": sum(1 for r in rows if r["can_import_as_definition"] == "yes"),
        "conditional": sum(1 for r in rows if r["can_import_as_definition"] == "conditional"),
        "no": sum(1 for r in rows if r["can_import_as_definition"] == "no"),
    }
    summary_path = OUT / f"心血管内科+剩余10条+外部权威人工候选定义摘要+{TODAY}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
