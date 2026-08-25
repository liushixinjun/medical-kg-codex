from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from pypdf import PdfReader


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "2026年8月专病拓展结构落地"


@dataclass
class Source:
    disease_group: str
    source_role: str
    authority_level: str
    source_name: str
    path: Path
    reason: str
    primary_allowed: str
    terms: list[str]


SOURCES: list[Source] = [
    Source(
        "冠心病/AMI",
        "教材骨架",
        "B",
        "《内科学（第10版）》",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\书籍教材\《内科学（第10版）》.docx"),
        "覆盖 AMI/STEMI 的定义、病因机制、临床表现、检查、诊断鉴别、并发症和治疗总原则。",
        "否，作为骨架依据",
        ["急性 ST 段抬高型心肌梗死", "再灌注", "ST 段抬高", "Killip", "溶栓", "经皮冠状动脉介入术", "梗死部位"],
    ),
    Source(
        "冠心病/AMI",
        "国内/国际指南",
        "A1",
        "ACC/AHA/ACEP/NAEMSP/SCAI 指南：急性冠脉综合征患者的管理 2025",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南\冠脉介入\ACC／AHA／ACEP／NAEMSP ／SCAI指 南：急性冠脉 综合征患者的管理 2025.pdf"),
        "覆盖 ACS/AMI 最新综合管理、推荐等级、证据等级和急诊处置。",
        "是",
        ["acute coronary", "STEMI", "NSTEMI", "reperfusion", "PCI", "troponin", "culprit"],
    ),
    Source(
        "冠心病/AMI",
        "国际指南",
        "A1",
        "ESC 急性冠脉综合征指南 2023",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南\冠脉介入\ESC 急性冠脉综合征指南（2023）.pdf"),
        "覆盖 ACS 统一诊疗框架、STEMI/NSTEMI、再灌注和抗栓治疗。",
        "是",
        ["acute coronary", "STEMI", "NSTEMI", "reperfusion", "PCI", "culprit", "troponin"],
    ),
    Source(
        "冠心病/AMI",
        "国内指南",
        "A1",
        "STEMI CN 2019",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南\CAD\STEMI CN 2019.pdf"),
        "覆盖中国 STEMI 诊断治疗路径、溶栓和 PCI 时间窗。",
        "是",
        ["STEMI", "溶栓", "PCI", "再灌注", "ST段", "12小时", "90 min", "120 min"],
    ),
    Source(
        "冠心病/AMI",
        "国内指南",
        "A1",
        "NSTE-ACS CN 2024",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南\CAD\NSTE-ACS CN 2024.pdf"),
        "覆盖 NSTEMI/UA 风险分层、肌钙蛋白和侵入策略。",
        "是",
        ["NSTE", "NSTEMI", "肌钙蛋白", "GRACE", "侵入", "风险"],
    ),
    Source(
        "冠心病/AMI",
        "专家共识",
        "A2",
        "心肌梗死心电图诊断标准和报告规范中国专家共识",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南\CAD\心肌梗死心电图诊断标准和报告规范中国专家共识.pdf"),
        "覆盖 ST 段、导联、定位诊断等 AMI 心电图特色结构。",
        "补充主依据",
        ["ST段", "导联", "定位", "心肌梗死", "报告规范"],
    ),
    Source(
        "心肌病",
        "教材骨架",
        "B",
        "《内科学（第10版）》",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\书籍教材\《内科学（第10版）》.docx"),
        "覆盖心肌病总论、HCM/DCM/RCM 基础定义、临床表现、检查、诊断、治疗原则。",
        "否，作为骨架依据",
        ["肥厚型心肌病", "基因", "家族", "左室流出道", "猝死", "法布雷", "淀粉样"],
    ),
    Source(
        "心肌病",
        "国内指南",
        "A1",
        "中国心肌病综合管理指南 2025",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南\2_中国心肌病综合管理指南2025.pdf"),
        "覆盖心肌病分类、遗传检测、家系筛查、特殊病因和综合管理。",
        "是",
        ["心肌病", "遗传", "基因", "家系", "法布雷", "淀粉样", "表型", "猝死"],
    ),
    Source(
        "心肌病",
        "国际指南",
        "A1",
        "HCM ESC 2023",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南\心肌病\HCM\HCM  ESC 2023.pdf"),
        "覆盖心肌病 ESC 2023 的遗传、表型、风险分层和 HCM 管理。",
        "是",
        ["hypertrophic cardiomyopathy", "genetic", "family", "LVOT", "sudden cardiac death", "mavacamten"],
    ),
    Source(
        "心肌病",
        "国际指南",
        "A1",
        "HCM AHA 2024",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南\心肌病\HCM\HCM AHA 2024.pdf"),
        "覆盖 HCM 诊疗、家族评估、基因检测、SCD 风险和治疗。",
        "是",
        ["hypertrophic cardiomyopathy", "genetic", "family", "SCD", "LVOT", "myosin inhibitor"],
    ),
    Source(
        "心肌病",
        "专家共识",
        "A2",
        "成人法布雷病心肌病诊断与治疗中国专家共识",
        Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南\心肌病\特殊类型心肌病\成人法布雷病心肌病诊断与治疗中国专家共识.pdf"),
        "覆盖法布雷病心肌病的特殊病因、基因/酶学诊断和治疗。",
        "补充主依据",
        ["法布雷", "GLA", "α", "半乳糖苷酶", "心肌病", "遗传"],
    ),
]


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def read_docx(path: Path) -> list[tuple[str, str]]:
    doc = Document(str(path))
    rows = []
    for idx, p in enumerate(doc.paragraphs, start=1):
        text = clean_text(p.text)
        if text:
            rows.append((f"段落{idx}", text))
    return rows


def read_pdf_limited(path: Path, max_pages: int | None = None) -> list[tuple[str, str]]:
    reader = PdfReader(str(path))
    rows = []
    pages = reader.pages if max_pages is None else reader.pages[:max_pages]
    for idx, page in enumerate(pages, start=1):
        try:
            text = clean_text(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001
            text = f"PDF_EXTRACT_ERROR: {exc}"
        if text:
            rows.append((f"第{idx}页", text))
    return rows


def read_source(path: Path) -> list[tuple[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".pdf":
        return read_pdf_limited(path)
    if suffix in {".html", ".htm"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        return [("HTML", clean_text(text))]
    return []


def snippet(text: str, term: str, radius: int = 70) -> str:
    lower = text.lower()
    pos = lower.find(term.lower())
    if pos < 0:
        return ""
    start = max(0, pos - radius)
    end = min(len(text), pos + len(term) + radius)
    s = text[start:end]
    if start > 0:
        s = "…" + s
    if end < len(text):
        s += "…"
    return s


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_rows = []
    evidence_rows = []
    summary = {
        "source_total": len(SOURCES),
        "missing_sources": [],
        "matched_source_count": 0,
        "matched_term_count": 0,
    }

    for src in SOURCES:
        exists = src.path.exists()
        source_rows.append({
            "疾病大类": src.disease_group,
            "资料角色": src.source_role,
            "权威等级": src.authority_level,
            "资料名称": src.source_name,
            "是否可作主依据": src.primary_allowed,
            "准入理由": src.reason,
            "文件路径": str(src.path),
            "文件存在": "是" if exists else "否",
        })
        if not exists:
            summary["missing_sources"].append(str(src.path))
            continue
        docs = read_source(src.path)
        source_matched = False
        for term in src.terms:
            matched = False
            for loc, text in docs:
                s = snippet(text, term)
                if s:
                    matched = True
                    source_matched = True
                    evidence_rows.append({
                        "疾病大类": src.disease_group,
                        "资料名称": src.source_name,
                        "权威等级": src.authority_level,
                        "关键词": term,
                        "定位": loc,
                        "短证据片段": s[:180],
                        "文件路径": str(src.path),
                    })
                    break
            if matched:
                summary["matched_term_count"] += 1
        if source_matched:
            summary["matched_source_count"] += 1

    with (OUT_DIR / "P7资料权威性准入表_20260811.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(source_rows[0].keys()))
        writer.writeheader()
        writer.writerows(source_rows)

    with (OUT_DIR / "P7定向原文证据矩阵_20260811.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["疾病大类", "资料名称", "权威等级", "关键词", "定位", "短证据片段", "文件路径"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(evidence_rows)

    summary["evidence_rows"] = len(evidence_rows)
    (OUT_DIR / "P7定向原文证据抽取摘要_20260811.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["missing_sources"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
