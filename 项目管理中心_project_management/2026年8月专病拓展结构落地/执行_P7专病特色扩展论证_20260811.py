from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from docx import Document


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT_DIR = ROOT / "项目管理中心_project_management" / "2026年8月专病拓展结构落地"
TEXTBOOK = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\书籍教材\《内科学（第10版）》.docx")


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", (text or "")).lower()


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def find_heading(paragraphs: list[str], *phrases: str) -> int | None:
    targets = [normalize(x) for x in phrases]
    for index, text in enumerate(paragraphs):
        n = normalize(text)
        if any(t in n for t in targets):
            return index
    return None


def extract_snippets(paragraphs: list[str], start: int, end: int, terms: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for term in terms:
        nt = normalize(term)
        for index in range(start, min(end, len(paragraphs))):
            text = clean(paragraphs[index])
            if nt in normalize(text):
                rows.append(
                    {
                        "疾病范围": "",
                        "章节范围": "",
                        "关键词": term,
                        "教材段落": f"段落{index + 1}",
                        "章节内原文片段": text[:260],
                    }
                )
                break
    return rows


def build_textbook_rows() -> tuple[list[dict[str, str]], dict[str, int | str | None]]:
    doc = Document(str(TEXTBOOK))
    paragraphs = [clean(p.text) for p in doc.paragraphs if clean(p.text)]

    ami_start = find_heading(paragraphs, "二、急性 ST 段抬高型心肌梗死", "二、急性ST段抬高型心肌梗死")
    ami_end = find_heading(paragraphs, "三、非 ST 段抬高型心肌梗死", "三、非ST段抬高型心肌梗死")
    if ami_start is not None and (ami_end is None or ami_end <= ami_start):
        ami_end = min(ami_start + 180, len(paragraphs))

    hcm_start = find_heading(paragraphs, "第一节 肥厚型心肌病", "第一节肥厚型心肌病", "第一节 | 肥厚型心肌病")
    hcm_end = find_heading(paragraphs, "第二节 扩张型心肌病", "第二节扩张型心肌病", "第二节 | 扩张型心肌病")
    if hcm_start is not None and (hcm_end is None or hcm_end <= hcm_start):
        hcm_end = min(hcm_start + 120, len(paragraphs))

    rows: list[dict[str, str]] = []
    if ami_start is not None and ami_end is not None:
        ami_terms = ["STEMI", "再灌注", "溶栓", "经皮冠状动脉介入术", "Killip", "梗死部位", "心电图", "肌钙蛋白", "禁忌证"]
        for row in extract_snippets(paragraphs, ami_start, ami_end, ami_terms):
            row["疾病范围"] = "冠心病-急性心肌梗死/STEMI"
            row["章节范围"] = f"《内科学》第10版 段落{ami_start + 1}-段落{ami_end}"
            rows.append(row)

    if hcm_start is not None and hcm_end is not None:
        hcm_terms = ["肥厚型心肌病", "基因", "家族", "左室流出道", "猝死", "ICD", "mavacamten", "家系", "运动"]
        for row in extract_snippets(paragraphs, hcm_start, hcm_end, hcm_terms):
            row["疾病范围"] = "心肌病-肥厚型心肌病"
            row["章节范围"] = f"《内科学》第10版 段落{hcm_start + 1}-段落{hcm_end}"
            rows.append(row)

    meta = {
        "textbook_exists": "yes" if TEXTBOOK.exists() else "no",
        "ami_start": None if ami_start is None else ami_start + 1,
        "ami_end": ami_end,
        "hcm_start": None if hcm_start is None else hcm_start + 1,
        "hcm_end": hcm_end,
        "textbook_rows": len(rows),
    }
    return rows, meta


def candidate_rows() -> list[dict[str, str]]:
    rows = [
        {
            "疾病大类": "冠心病",
            "样板疾病": "急性心肌梗死/急性ST段抬高型心肌梗死",
            "专病特色点": "再灌注时间窗",
            "建议结构": "复用 ClinicalRule/ThresholdRule，不新增实体类型；关系挂在正式推荐陈述或治疗方案下",
            "临床用途": "决定直接PCI、转运PCI、溶栓、补救PCI的优先级",
            "准入结论": "准入",
            "依据类型": "教材章节 + STEMI/ACS指南",
            "落地要求": "必须有触发条件、禁忌/排除条件、推荐动作、主证据",
        },
        {
            "疾病大类": "冠心病",
            "样板疾病": "急性心肌梗死/STEMI",
            "专病特色点": "心电图导联定位与ST段动态变化",
            "建议结构": "复用 ExamObservation；必要时增加取值属性，不新增实体类型",
            "临床用途": "支持STEMI诊断、梗死部位判断和急诊路径触发",
            "准入结论": "准入",
            "依据类型": "教材章节 + 心电图诊断共识",
            "落地要求": "检查发现必须能下钻到具体观察点，不能只保留“诊断标准”标题",
        },
        {
            "疾病大类": "冠心病",
            "样板疾病": "急性心肌梗死/STEMI/NSTEMI",
            "专病特色点": "肌钙蛋白动态变化",
            "建议结构": "复用 LabSubitem + ThresholdRule；关系从检验项目到检验细项再到阈值",
            "临床用途": "区分AMI、NSTEMI、非缺血性肌钙蛋白升高",
            "准入结论": "准入",
            "依据类型": "教材章节 + ACS指南",
            "落地要求": "血清心肌坏死标志物不能只建检验项目，必须有细项与动态规则",
        },
        {
            "疾病大类": "冠心病",
            "样板疾病": "急性心肌梗死",
            "专病特色点": "Killip分级/心源性休克分层",
            "建议结构": "复用 RiskStratification；分级明细作为组件或阈值规则",
            "临床用途": "判断预后、监护级别和急诊处置风险",
            "准入结论": "准入",
            "依据类型": "教材章节 + 指南",
            "落地要求": "分层节点必须有下级分级说明，不能只保留分层标题",
        },
        {
            "疾病大类": "心肌病",
            "样板疾病": "肥厚型心肌病/扩张型心肌病/法布雷病心肌病",
            "专病特色点": "遗传方式、家族史、家系筛查",
            "建议结构": "复用 RiskFactor/ClinicalRule；新增专病槽位 family_screening_rule，不新增通用实体类型",
            "临床用途": "决定一级亲属筛查、遗传咨询和疑似分型",
            "准入结论": "准入",
            "依据类型": "教材章节 + 心肌病指南",
            "落地要求": "必须区分教材概述、指南推荐和需专家确认的遗传检测建议",
        },
        {
            "疾病大类": "心肌病",
            "样板疾病": "肥厚型心肌病/法布雷病心肌病",
            "专病特色点": "基因/变异/酶学证据",
            "建议结构": "新增专病扩展实体 Gene；变异先作为 Gene 属性或证据片段，暂不扩成全局 Variant 实体",
            "临床用途": "支持特殊病因识别、精准治疗和家族筛查",
            "准入结论": "有条件准入",
            "依据类型": "心肌病指南 + 法布雷病专家共识/权威外部资料",
            "落地要求": "只有影响诊断、治疗或家系管理时才结构化；纯背景知识保留在证据摘要",
        },
        {
            "疾病大类": "心肌病",
            "样板疾病": "肥厚型心肌病",
            "专病特色点": "左室流出道梗阻与运动风险",
            "建议结构": "复用 ExamObservation/ThresholdRule/ClinicalRule",
            "临床用途": "影响HCM分型、用药、手术/介入和运动建议",
            "准入结论": "准入",
            "依据类型": "教材章节 + HCM指南",
            "落地要求": "必须带检查发现、阈值或临床规则，不能只建“左室流出道梗阻”名词",
        },
        {
            "疾病大类": "心肌病",
            "样板疾病": "肥厚型心肌病/扩张型心肌病",
            "专病特色点": "猝死风险与ICD适应证",
            "建议结构": "复用 RiskStratification + RecommendationStatement + StandardProcedure",
            "临床用途": "决定ICD预防植入等正式CDSS推荐",
            "准入结论": "准入",
            "依据类型": "HCM/心肌病指南",
            "落地要求": "正式推荐必须连接主指南、推荐等级、适用人群、排除条件",
        },
        {
            "疾病大类": "全专科通用",
            "样板疾病": "所有后续疾病",
            "专病特色点": "仅描述性病理/机制",
            "建议结构": "默认进入 Pathophysiology/Evidence 摘要，不新增专病实体",
            "临床用途": "知识展示，不直接触发CDSS推荐",
            "准入结论": "限制准入",
            "依据类型": "教材/指南",
            "落地要求": "若不影响诊断、治疗、风险或路径，不进入正式推荐链路",
        },
    ]
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_report(textbook_rows: list[dict[str, str]], meta: dict[str, int | str | None], candidates: list[dict[str, str]]) -> None:
    accepted = sum(1 for x in candidates if x["准入结论"] == "准入")
    conditional = sum(1 for x in candidates if x["准入结论"] == "有条件准入")
    limited = sum(1 for x in candidates if x["准入结论"] == "限制准入")
    lines = [
        "# P7.1 专病特色节点/关系扩展论证方案（2026-08-11）",
        "",
        "## 结论",
        "",
        "本轮不直接扩 Schema、不写 Neo4j、不写 Oracle。先用 AMI 和心肌病做样板，验证“哪些内容必须结构化、哪些只作为证据摘要保留”。结论是：通用 Schema 仍作为主结构；专病差异通过“专病扩展槽位”管理，只有影响诊断、分型、风险分层、治疗推荐或 CDSS 触发条件的内容，才允许进入结构化实体/关系。",
        "",
        "## 为什么不能只靠通用 Schema",
        "",
        "AMI 的关键差异是时间窗、心电图定位、心肌坏死标志物动态、再灌注策略和风险分层；心肌病的关键差异是遗传/家系、表型、猝死风险、特殊病因和精准治疗。它们不能只用“症状、检查、药物、治疗方案”几个宽泛节点表达，否则前端看得到节点，但 CDSS 不知道什么时候触发、推荐什么、依据哪条指南。",
        "",
        "## 权威资料准入结果",
        "",
        f"- 教材章节定向抽取：{meta.get('textbook_rows')} 条，已限制在 AMI/STEMI 与 HCM 对应章节内。",
        f"- AMI 教材范围：段落 {meta.get('ami_start')} 至 {meta.get('ami_end')}。",
        f"- HCM 教材范围：段落 {meta.get('hcm_start')} 至 {meta.get('hcm_end')}。",
        "- 指南/共识：采用已登记的 ACS/STEMI/NSTE-ACS/HCM/心肌病/法布雷病资料作为主证据或补充证据。",
        "",
        "## 扩展准入规则",
        "",
        "1. 能影响诊断、分型、风险分层、治疗路径或随访管理，才进入结构化扩展。",
        "2. 只解释疾病机制、历史背景或一般描述的内容，保留为定义、机制或证据摘要，不新增实体。",
        "3. 能复用通用实体时必须复用，例如检查发现、检验细项、阈值规则、治疗方案、药物、手术。",
        "4. 只有通用结构无法表达且临床确实需要下钻时，才新增专病扩展槽位。",
        "5. 所有正式 CDSS 推荐必须具备：适用场景、触发条件、禁忌/排除条件、推荐动作、主证据、主指南。",
        "",
        "## 样板候选矩阵汇总",
        "",
        f"- 准入：{accepted} 项。",
        f"- 有条件准入：{conditional} 项。",
        f"- 限制准入：{limited} 项。",
        "",
        "| 疾病大类 | 专病特色点 | 建议结构 | 准入结论 | 临床用途 |",
        "|---|---|---|---|---|",
    ]
    for row in candidates:
        lines.append(
            f"| {row['疾病大类']} | {row['专病特色点']} | {row['建议结构']} | {row['准入结论']} | {row['临床用途']} |"
        )
    lines.extend(
        [
            "",
            "## 对后续 PDF 解析的要求",
            "",
            "后续解析某个疾病时，必须先完成资料权威性准入，再判断疾病是否存在专病特色槽位。解析结果不得因为文献里出现某个词就自动建节点，必须同时满足“来源可信、属于本疾病章节或指南适用范围、临床上可用于诊断/分型/推荐/风险判断”。",
            "",
            "## 当前边界",
            "",
            "本文件是结构论证和准入依据，不是入库数据包。后续若要写库，需要把已准入候选转换为标准三元组、本地审计通过后再执行。",
        ]
    )
    (OUT_DIR / "P7专病特色节点关系扩展论证方案_20260811.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    textbook_rows, meta = build_textbook_rows()
    candidates = candidate_rows()
    write_csv(OUT_DIR / "P7教材章节定向证据_20260811.csv", textbook_rows)
    write_csv(OUT_DIR / "P7专病特色扩展候选矩阵_20260811.csv", candidates)
    write_report(textbook_rows, meta, candidates)
    summary = {
        **meta,
        "candidate_rows": len(candidates),
        "accepted": sum(1 for x in candidates if x["准入结论"] == "准入"),
        "conditional": sum(1 for x in candidates if x["准入结论"] == "有条件准入"),
        "limited": sum(1 for x in candidates if x["准入结论"] == "限制准入"),
        "wrote_neo4j": False,
        "wrote_oracle": False,
    }
    (OUT_DIR / "P7专病特色扩展论证摘要_20260811.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["textbook_rows"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
