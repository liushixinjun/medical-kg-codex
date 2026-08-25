from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader
from docx import Document


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT = ROOT / "项目管理中心_project_management" / "2026年8月专病拓展结构落地"
CARD_DIR = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科")
GUIDE_DIR = CARD_DIR / "诊疗指南" / "心肌病"
TEXTBOOK = CARD_DIR / "书籍教材" / "《内科学（第10版）》.docx"
TODAY = "20260812"


@dataclass(frozen=True)
class CoreSourceRule:
    source_name: str
    expected_file: str
    source_role: str
    mandatory_reason: str
    key_terms: tuple[str, ...]


CORE_SOURCES = [
    CoreSourceRule(
        "《内科学（第10版）》心肌病章节",
        "《内科学（第10版）》.docx",
        "教材骨架",
        "心血管内科骨架基础，必须提供疾病定义、病因机制、临床表现、检查、诊断、治疗原则。",
        ("肥厚型心肌病", "扩张型心肌病", "限制型心肌病", "心肌病", "临床表现", "诊断", "治疗"),
    ),
    CoreSourceRule(
        "中国心肌病综合管理指南2025",
        "2_中国心肌病综合管理指南2025.pdf",
        "医生指定核心指南",
        "医生明确指定核心资料，覆盖心肌病综合管理、分类、遗传、病理和特殊病因。",
        ("心肌病", "综合管理", "遗传", "基因", "表型", "病理", "心内膜心肌活检", "法布雷", "淀粉样"),
    ),
    CoreSourceRule(
        "心肌病心内膜心肌活检及病理检查临床应用指南",
        "心肌病心内膜心肌活检及病理检查临床应用指南.pdf",
        "医生指定核心技术指南",
        "医生明确指定核心资料；直接决定心肌病活检、病理检查、诊断适应证和鉴别诊断扩展槽位。",
        ("心内膜心肌活检", "病理检查", "适应证", "禁忌证", "心肌病", "病理", "免疫组化", "电镜"),
    ),
    CoreSourceRule(
        "肥厚型心肌病激发/负荷超声心动图临床应用指南2024",
        "肥厚型心肌病激发_负荷超声心动图临床应用指南(2024版).pdf",
        "医生指定核心技术指南",
        "医生明确指定核心资料；直接决定 HCM 动态梗阻、负荷/激发超声、阈值规则和治疗决策扩展槽位。",
        ("肥厚型心肌病", "激发", "负荷超声", "左室流出道", "LVOTO", "压差", "Valsalva", "运动"),
    ),
]


SUPPLEMENT_HINTS = {
    "ESC指南：心肌病的管理2023.pdf": ("国际指南", "ESC 2023 心肌病管理，作为国际补充证据。"),
    "心肌病  ESC  2023.pdf": ("国际指南", "ESC 2023 心肌病管理，作为国际补充证据。"),
    "HCM  ESC 2023.pdf": ("国际指南", "HCM 诊疗、遗传、表型、风险分层补充证据。"),
    "HCM AHA 2024.pdf": ("国际指南", "HCM 诊疗、家族评估、SCD 风险和治疗补充证据。"),
    "HCM CN 2023.pdf": ("国内指南", "国内 HCM 诊疗补充证据。"),
    "中国 成人肥厚型心肌病诊断与治疗指南2023.pdf": ("国内指南", "国内成人 HCM 诊断治疗补充证据。"),
    "中国 扩张型心肌病诊断和治疗指南2018.pdf": ("国内指南", "国内 DCM 诊断治疗补充证据。"),
    "成人法布雷病心肌病诊断与治疗中国专家共识.pdf": ("专家共识", "法布雷病心肌病专病特色补充证据。"),
    "DCM CN 2018.pdf": ("国内指南", "DCM 诊疗补充证据。"),
    "DCM ESC 2016.pdf": ("国际指南", "DCM 诊疗国际补充证据。"),
    "DCM  AHA  2016.pdf": ("国际指南", "DCM 诊疗国际补充证据。"),
}


SPECIALTY_SLOTS = [
    {
        "专病特色点": "心内膜心肌活检",
        "建议结构": "Procedure/StandardProcedure + ClinicalRule + Evidence",
        "临床用途": "用于明确部分心肌病病因、炎症性/浸润性/储积性心肌病诊断和鉴别诊断。",
        "必须资料": "心肌病心内膜心肌活检及病理检查临床应用指南; 中国心肌病综合管理指南2025; 《内科学（第10版）》",
        "结论": "必须纳入专病特色槽位；不得只当普通检查标题。",
    },
    {
        "专病特色点": "病理检查与病理发现",
        "建议结构": "ExamObservation/PathologyFinding候选 + DiagnosisCriteriaComponent + Evidence",
        "临床用途": "表达心肌细胞肥大、间质纤维化、炎症、淀粉样沉积、储积病改变等可诊断或鉴别的病理发现。",
        "必须资料": "心肌病心内膜心肌活检及病理检查临床应用指南; 中国心肌病综合管理指南2025",
        "结论": "现有通用结构可先落在检查发现，后续若多病种复用再评估是否新增病理发现专门实体。",
    },
    {
        "专病特色点": "HCM 激发/负荷超声心动图",
        "建议结构": "ExamItem + ExamObservation + ThresholdRule + ClinicalRule + Evidence",
        "临床用途": "用于识别静息状态未显示的动态 LVOTO，影响 HCM 分型、风险评估和治疗策略。",
        "必须资料": "肥厚型心肌病激发/负荷超声心动图临床应用指南2024; 中国心肌病综合管理指南2025; HCM指南",
        "结论": "必须纳入专病特色槽位；不能只保留超声心动图通用检查。",
    },
    {
        "专病特色点": "LVOTO 动态梗阻阈值",
        "建议结构": "ExamObservation + ThresholdRule + RiskStratification/ClinicalRule",
        "临床用途": "用于判断梗阻型 HCM、动态梗阻、治疗选择和运动/负荷试验解释。",
        "必须资料": "肥厚型心肌病激发/负荷超声心动图临床应用指南2024; HCM指南",
        "结论": "必须纳入阈值规则，不能只写左室流出道梗阻节点。",
    },
    {
        "专病特色点": "遗传检测与家系筛查",
        "建议结构": "GeneticTest候选 + FamilyHistory/ScreeningRule + Evidence",
        "临床用途": "用于 HCM/DCM/特殊类型心肌病的病因识别、亲属筛查和风险管理。",
        "必须资料": "中国心肌病综合管理指南2025; HCM指南; DCM指南",
        "结论": "作为心肌病专病扩展重点；暂不为所有病种强行新增基因实体，先按槽位配置启用。",
    },
    {
        "专病特色点": "特殊病因心肌病",
        "建议结构": "Etiology + DifferentialDiagnosis + StandardDiagnosis + Evidence",
        "临床用途": "覆盖法布雷病、淀粉样变、Danon病、Pompe病、铁过载、线粒体病等特殊病因识别。",
        "必须资料": "中国心肌病综合管理指南2025; 成人法布雷病心肌病专家共识; 权威外部资料",
        "结论": "必须和标准诊断/别名/证据链联动，不能只当并发症或病因词。",
    },
    {
        "专病特色点": "HCM 猝死风险分层",
        "建议结构": "RiskStratification + ClinicalRule + ThresholdRule + Evidence",
        "临床用途": "用于 ICD 适应证、运动建议、随访强度和正式 CDSS 风险提示。",
        "必须资料": "中国心肌病综合管理指南2025; HCM ESC/AHA指南; 《内科学（第10版）》",
        "结论": "作为正式 CDSS 风险提示候选，必须带触发条件和证据。",
    },
]


def norm_title(path: Path) -> str:
    name = path.stem
    name = re.sub(r"^\d+_", "", name)
    name = re.sub(r"[（）()\\s]+", "", name)
    name = name.replace("（2025年）", "2025").replace("2025年", "2025")
    return name.lower()


def file_size_mb(path: Path) -> str:
    return f"{path.stat().st_size / 1024 / 1024:.2f}"


def read_pdf_pages(path: Path, max_pages: int | None = None) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    try:
        reader = PdfReader(str(path))
        for idx, page in enumerate(reader.pages):
            if max_pages is not None and idx >= max_pages:
                break
            text = page.extract_text() or ""
            text = re.sub(r"\s+", " ", text).strip()
            pages.append((idx + 1, text))
    except Exception as exc:
        pages.append((0, f"__PDF_EXTRACT_ERROR__ {exc}"))
    return pages


def read_docx_paragraphs(path: Path) -> list[tuple[int, str]]:
    paragraphs: list[tuple[int, str]] = []
    try:
        doc = Document(str(path))
        for idx, p in enumerate(doc.paragraphs, start=1):
            text = re.sub(r"\s+", " ", p.text or "").strip()
            if text:
                paragraphs.append((idx, text))
    except Exception as exc:
        paragraphs.append((0, f"__DOCX_EXTRACT_ERROR__ {exc}"))
    return paragraphs


def find_file(rule: CoreSourceRule) -> Path | None:
    if rule.expected_file == TEXTBOOK.name and TEXTBOOK.exists():
        return TEXTBOOK
    candidates = list(GUIDE_DIR.rglob(rule.expected_file))
    if candidates:
        return candidates[0]
    # also search parent guideline folder because some legacy docs were copied one level above
    candidates = list((CARD_DIR / "诊疗指南").rglob(rule.expected_file))
    return candidates[0] if candidates else None


def make_inventory_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_norm: dict[str, Path] = {}

    for rule in CORE_SOURCES:
        path = find_file(rule)
        rows.append(
            {
                "疾病大类": "心肌病",
                "资料名称": rule.source_name,
                "资料角色": rule.source_role,
                "是否医生指定核心资料": "是" if "医生指定" in rule.source_role else "否",
                "是否必须纳入": "是",
                "准入结论": "已纳入" if path and path.exists() else "缺失阻断",
                "文件路径": "" if path is None else str(path),
                "文件大小MB": "" if path is None or not path.exists() else file_size_mb(path),
                "去重标题": norm_title(path) if path else norm_title(Path(rule.expected_file)),
                "准入原因": rule.mandatory_reason,
                "处理要求": "必须进入本轮心肌病 P7.1 论证，缺失则本轮不得通过。",
            }
        )
        if path:
            seen_norm[norm_title(path)] = path

    for path in sorted(GUIDE_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".docx", ".epub"}:
            continue
        n = norm_title(path)
        duplicate_of = ""
        if n in seen_norm and seen_norm[n] != path:
            duplicate_of = str(seen_norm[n])
        else:
            seen_norm[n] = path
        role, reason = SUPPLEMENT_HINTS.get(path.name, ("补充资料", "未列为医生指定核心资料，需按主题相关性作为补充或历史资料。"))
        rows.append(
            {
                "疾病大类": "心肌病",
                "资料名称": path.stem,
                "资料角色": role,
                "是否医生指定核心资料": "否",
                "是否必须纳入": "否",
                "准入结论": "重复保留不重复计数" if duplicate_of else "补充纳入候选",
                "文件路径": str(path),
                "文件大小MB": file_size_mb(path),
                "去重标题": n,
                "准入原因": reason,
                "处理要求": "若支持专病特色槽位则纳入证据矩阵；历史分类资料只保留来源线索，不直接建临床节点。",
            }
        )
    return rows


def make_evidence_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rule in CORE_SOURCES:
        path = find_file(rule)
        if not path or not path.exists():
            rows.append(
                {
                    "疾病大类": "心肌病",
                    "资料名称": rule.source_name,
                    "资料角色": rule.source_role,
                    "页码/段落": "",
                    "命中主题": "资料缺失",
                    "原文片段": "",
                    "结构化影响": "阻断",
                }
            )
            continue
        records = read_docx_paragraphs(path) if path.suffix.lower() == ".docx" else read_pdf_pages(path)
        hit_count = 0
        for pos, text in records:
            if not text or text.startswith("__"):
                continue
            for term in rule.key_terms:
                if term.lower() in text.lower():
                    idx = text.lower().find(term.lower())
                    start = max(0, idx - 80)
                    end = min(len(text), idx + 180)
                    snippet = text[start:end]
                    rows.append(
                        {
                            "疾病大类": "心肌病",
                            "资料名称": rule.source_name,
                            "资料角色": rule.source_role,
                            "页码/段落": f"{'段落' if path.suffix.lower()=='.docx' else '页'}{pos}",
                            "命中主题": term,
                            "原文片段": snippet,
                            "结构化影响": classify_impact(term, rule.source_name),
                        }
                    )
                    hit_count += 1
                    break
            if hit_count >= 12:
                break
    return rows


def classify_impact(term: str, source_name: str) -> str:
    if "活检" in term or "病理" in term or "免疫组化" in term or "电镜" in term:
        return "补强 Procedure/ExamObservation/DiagnosisCriteria/DifferentialDiagnosis"
    if "负荷" in term or "激发" in term or "LVOTO" in term or "左室流出道" in term or "压差" in term:
        return "补强 ExamItem/ExamObservation/ThresholdRule/ClinicalRule"
    if "基因" in term or "遗传" in term or "家系" in term:
        return "补强 GeneticTest候选/FamilyHistory/ScreeningRule"
    if "猝死" in term:
        return "补强 RiskStratification/ClinicalRule"
    return "补强心肌病基础骨架或专病特色证据"


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(inv_rows: list[dict[str, str]], ev_rows: list[dict[str, str]]) -> None:
    mandatory = [r for r in inv_rows if r["是否必须纳入"] == "是"]
    missing = [r for r in mandatory if r["准入结论"] != "已纳入"]
    doctor_core = [r for r in inv_rows if r["是否医生指定核心资料"] == "是"]
    doctor_in = [r for r in doctor_core if r["准入结论"] == "已纳入"]

    md = [
        "# P7.1 心肌病专病特色节点关系扩展论证方案（修正版）",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 1. 修正结论",
        "",
        "上一版 P7.1 心肌病论证存在资料准入缺陷：资料来源采用脚本白名单，未先全量扫描心肌病目录，也未把医生指定核心资料作为强制准入条件。因此上一版只能作为初步草案，不能作为心肌病完整专病特色论证结论。",
        "",
        f"本轮修正后，医生指定核心资料纳入 {len(doctor_in)}/{len(doctor_core)}；必须资料缺失 {len(missing)} 项。",
        "",
        "## 2. 本轮必须纳入资料",
        "",
        "| 资料名称 | 角色 | 结果 | 说明 |",
        "|---|---|---|---|",
    ]
    for r in mandatory:
        md.append(f"| {r['资料名称']} | {r['资料角色']} | {r['准入结论']} | {r['准入原因']} |")
    md += [
        "",
        "## 3. 关键影响",
        "",
        "- 心内膜心肌活检及病理检查指南必须影响 Procedure/诊断操作、病理检查、诊断标准组件、鉴别诊断和证据链；不能只显示为普通检查标题。",
        "- 肥厚型心肌病激发/负荷超声指南必须影响 ExamItem、ExamObservation、ThresholdRule 和 ClinicalRule；不能只显示为普通超声心动图。",
        "- 心肌病综合管理指南 2025 是心肌病综合管理主资料，负责连接分类、遗传、家系、特殊病因、病理和综合治疗。",
        "",
        "## 4. 专病特色扩展槽位修正矩阵",
        "",
        "| 专病特色点 | 建议结构 | 临床用途 | 必须资料 | 结论 |",
        "|---|---|---|---|---|",
    ]
    for row in SPECIALTY_SLOTS:
        md.append(f"| {row['专病特色点']} | {row['建议结构']} | {row['临床用途']} | {row['必须资料']} | {row['结论']} |")
    md += [
        "",
        "## 5. 新硬闸门",
        "",
        "后续任何专病特色论证必须满足：先全量扫描病种目录，再标注医生指定核心资料、教材骨架、最新国内指南、专项技术指南、国际补充指南。医生指定核心资料未 100% 纳入时，本轮论证不得通过。",
        "",
        "## 6. 本轮不做",
        "",
        "- 不写 Neo4j。",
        "- 不写 Oracle。",
        "- 不扩正式 Schema 主体。",
        "- 不把历史分类资料直接转成临床节点。",
    ]
    (OUT / f"P7.1心肌病专病特色节点关系扩展论证方案_修正版_{TODAY}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    handoff = [
        "# P7.1 心肌病资料准入修正交接记录",
        "",
        f"记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 本次处理",
        "",
        "- 已确认上一版 P7.1 心肌病资料筛选采用手工白名单，存在漏纳医生核心资料的问题。",
        "- 已按心肌病目录全量扫描，重新生成资料完整性准入表。",
        "- 已把医生提供的 3 份核心 PDF 与《内科学（第10版）》列为必须纳入。",
        "- 已重新生成核心资料证据矩阵和专病特色扩展候选矩阵。",
        "",
        "## 输出文件",
        "",
        f"- P7心肌病资料完整性准入表_{TODAY}.csv",
        f"- P7心肌病核心资料证据矩阵_{TODAY}.csv",
        f"- P7心肌病专病特色扩展候选矩阵_修正版_{TODAY}.csv",
        f"- P7.1心肌病专病特色节点关系扩展论证方案_修正版_{TODAY}.md",
        f"- P7.1心肌病资料筛选缺陷踩坑记录_{TODAY}.md",
        "",
        "## 当前结论",
        "",
        f"医生核心资料纳入 {len(doctor_in)}/{len(doctor_core)}；必须资料缺失 {len(missing)} 项。若缺失数为 0，可进入下一轮心肌病特色槽位结构化抽取；否则先补齐资料。",
        "",
        "## 下一执行口径",
        "",
        "心肌病后续结构化抽取必须以本修正版资料准入表为入口，不能再使用旧版 P7资料权威性准入表作为完整准入结论。",
    ]
    (OUT / f"P7.1心肌病资料准入修正交接记录_{TODAY}.md").write_text("\n".join(handoff) + "\n", encoding="utf-8")

    pitfall = [
        "# P7.1 心肌病资料筛选缺陷踩坑记录",
        "",
        f"记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 错误事实",
        "",
        "上一版 P7.1 心肌病论证没有先全量扫描心肌病目录，也没有把医生指定核心资料作为强制准入条件，导致“心肌病心内膜心肌活检及病理检查临床应用指南”和“肥厚型心肌病激发/负荷超声心动图临床应用指南(2024版)”未进入准入表。",
        "",
        "## 风险",
        "",
        "- 活检、病理检查、病理发现、鉴别诊断扩展论证不足。",
        "- HCM 负荷/激发超声、动态 LVOTO、阈值规则和治疗决策扩展论证不足。",
        "- 如果继续使用旧论证，前端和 CDSS 会误以为心肌病专病特色已经完整覆盖。",
        "",
        "## 固化规则",
        "",
        "医生指定核心资料未 100% 纳入时，不得输出“完整论证通过”；病种目录必须先全量扫描，再去重、分级、准入、抽证据。",
        "",
        "错误指纹：P7-CM-CORE-SOURCE-MISSING-037",
    ]
    (OUT / f"P7.1心肌病资料筛选缺陷踩坑记录_{TODAY}.md").write_text("\n".join(pitfall) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inv_rows = make_inventory_rows()
    ev_rows = make_evidence_rows()
    cand_rows = [
        {
            "疾病大类": "心肌病",
            **row,
            "是否进入正式Schema": "否，本轮为专病槽位候选；结构稳定后再评估主Schema",
            "是否写库": "否",
        }
        for row in SPECIALTY_SLOTS
    ]

    write_csv(OUT / f"P7心肌病资料完整性准入表_{TODAY}.csv", inv_rows)
    write_csv(OUT / f"P7心肌病核心资料证据矩阵_{TODAY}.csv", ev_rows)
    write_csv(OUT / f"P7心肌病专病特色扩展候选矩阵_修正版_{TODAY}.csv", cand_rows)
    write_markdown(inv_rows, ev_rows)

    mandatory = [r for r in inv_rows if r["是否必须纳入"] == "是"]
    doctor_core = [r for r in inv_rows if r["是否医生指定核心资料"] == "是"]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inventory_rows": len(inv_rows),
        "evidence_rows": len(ev_rows),
        "candidate_rows": len(cand_rows),
        "mandatory_total": len(mandatory),
        "mandatory_included": sum(1 for r in mandatory if r["准入结论"] == "已纳入"),
        "doctor_core_total": len(doctor_core),
        "doctor_core_included": sum(1 for r in doctor_core if r["准入结论"] == "已纳入"),
        "wrote_neo4j": False,
        "wrote_oracle": False,
    }
    (OUT / f"P7心肌病资料准入修正摘要_{TODAY}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
