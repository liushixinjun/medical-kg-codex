from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
COLLECTION = ROOT / "心血管内科文献集合"
OUT_DIR = ROOT / "项目管理中心_project_management" / "126_指南PDF精修层全库总检_20260717"
GUIDE_ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南")
EXTERNAL_ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\外部权威")
LEDGER_CSV = ROOT / "项目管理中心_project_management" / "04_批次登记台账_batch_ledger.csv"
LEDGER_MD = COLLECTION / "批次登记台账.md"

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


CATEGORY_KEYWORDS = {
    "冠心病": ["冠心", "冠状动脉", "ACS", "STEMI", "NSTEMI", "心肌梗死", "心绞痛", "PCI", "再灌注", "血运重建"],
    "心肌病": ["心肌病", "HCM", "DCM", "肥厚型", "扩张型", "限制型", "Fabry", "法布雷"],
    "心力衰竭": ["心力衰竭", "心衰", "HF", "射血分数", "ARNI"],
    "心律失常": ["心律失常", "房颤", "心房颤动", "房扑", "室上速", "室性", "传导阻滞", "起搏", "猝死", "ICD"],
    "高血压": ["高血压", "血压", "醛固酮", "肾血管"],
    "瓣膜病": ["瓣膜", "主动脉瓣", "二尖瓣", "三尖瓣", "反流", "狭窄", "TAVI", "TAVR"],
    "肺动脉高压": ["肺动脉高压", "PAH", "CTEPH", "肺高压"],
    "主动脉与外周动脉疾病": ["主动脉", "外周动脉", "PAD", "夹层", "动脉瘤", "下肢动脉"],
    "心肌炎/心包炎/感染性心内膜炎": ["心肌炎", "心包", "心内膜炎", "感染性心内膜炎"],
    "结构性心脏病/先天性心脏病": ["先天性心脏病", "结构性", "房间隔", "室间隔", "卵圆孔", "动脉导管"],
    "血脂异常/动脉粥样硬化": ["血脂", "胆固醇", "动脉粥样硬化", "ASCVD", "LDL"],
}


def normalize_name(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\.(pdf|docx?|txt|csv)$", "", value, flags=re.I)
    value = re.sub(r"[\s　_\-—–（）()【】\\/\[\]《》<>：:，,。.]+", "", value)
    return value


def classify_category(name: str) -> str:
    hits = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in name.lower())
        if score:
            hits.append((score, category))
    if not hits:
        return "待人工归类"
    hits.sort(reverse=True)
    return hits[0][1]


def list_all_pdf_sources():
    rows = []
    for root, source_type in [(GUIDE_ROOT, "诊疗指南目录"), (EXTERNAL_ROOT, "外部权威目录")]:
        if not root.exists():
            continue
        for path in root.rglob("*.pdf"):
            rows.append(
                {
                    "文件名": path.name,
                    "规范名": normalize_name(path.name),
                    "目录": str(path.parent),
                    "来源目录类型": source_type,
                    "建议疾病大类": classify_category(path.name),
                    "文件大小MB": round(path.stat().st_size / 1024 / 1024, 2),
                    "最后修改时间": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
    return rows


def extract_pdf_names_from_text(text: str):
    names = set()
    for match in re.finditer(r"[^`\n\r|，,；;：:]*?\.pdf", text, flags=re.I):
        value = match.group(0).strip(" `|，,；;：:")
        if value:
            names.add(Path(value).name)
    return names


def list_used_pdf_names():
    used = {}
    source_files = []

    # CSV/Markdown source lists already created during previous batches.
    patterns = [
        "*来源清单*.csv",
        "*来源清单*.md",
        "*source*manifest*.csv",
        "*source*manifest*.md",
        "*PDF来源清单*.csv",
        "*PDF来源清单*.md",
    ]
    for pattern in patterns:
        source_files.extend(COLLECTION.rglob(pattern))

    for path in sorted(set(source_files)):
        try:
            if path.suffix.lower() == ".csv":
                with path.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        text = " ".join(str(v) for v in row.values() if v)
                        for name in extract_pdf_names_from_text(text):
                            used.setdefault(normalize_name(name), {"文件名": name, "登记来源": set()})
                            used[normalize_name(name)]["登记来源"].add(str(path))
            else:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for name in extract_pdf_names_from_text(text):
                    used.setdefault(normalize_name(name), {"文件名": name, "登记来源": set()})
                    used[normalize_name(name)]["登记来源"].add(str(path))
        except Exception as exc:  # noqa: BLE001
            used.setdefault(f"__read_error__{path}", {"文件名": path.name, "登记来源": set()})
            used[f"__read_error__{path}"]["登记来源"].add(f"读取失败：{type(exc).__name__}")

    return used


def load_batch_ledger():
    rows = []
    if LEDGER_CSV.exists():
        with LEDGER_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rows.append(row)
    return rows


def summarize_batch_by_category(ledger_rows):
    grouped = defaultdict(list)
    for row in ledger_rows:
        category = row.get("疾病大类") or "未填写"
        grouped[category].append(row)
    out = []
    for category, items in sorted(grouped.items()):
        parsed = [x for x in items if "解析" in (x.get("batch_id", "") + x.get("状态", "") + x.get("备注", ""))]
        imported = [x for x in items if "已写入" in x.get("状态", "") or "已导入" in x.get("状态", "") or "是" == x.get("是否写Neo4j", "")]
        cdss = [x for x in items if "CDSS" in (x.get("batch_id", "") + x.get("疾病大类", "") + x.get("备注", ""))]
        out.append(
            {
                "疾病大类": category,
                "登记批次数": len(items),
                "解析相关批次": len(parsed),
                "已写入Neo4j批次": len(imported),
                "CDSS决策层批次": len(cdss),
                "最新状态摘要": "；".join((x.get("batch_id", "") + ":" + x.get("状态", "")) for x in items[:3]),
            }
        )
    return out


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None):
    if fieldnames is None:
        keys = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_pdfs = list_all_pdf_sources()
    used = list_used_pdf_names()
    ledger_rows = load_batch_ledger()

    pdf_status = []
    for row in all_pdfs:
        matched = used.get(row["规范名"])
        pdf_status.append(
            {
                **row,
                "是否已解析登记": "是" if matched else "否",
                "登记文件名": matched["文件名"] if matched else "",
                "登记来源文件数": len(matched["登记来源"]) if matched else 0,
                "登记来源示例": "；".join(sorted(matched["登记来源"])[:3]) if matched else "",
                "下一步动作": "进入指南精修复核" if matched else "进入未解析PDF候选池",
            }
        )

    category_summary = []
    for category in sorted(set(list(CATEGORY_KEYWORDS.keys()) + [x["建议疾病大类"] for x in pdf_status])):
        related = [x for x in pdf_status if x["建议疾病大类"] == category]
        category_summary.append(
            {
                "疾病大类": category,
                "PDF总数": len(related),
                "已解析登记PDF数": sum(1 for x in related if x["是否已解析登记"] == "是"),
                "未解析PDF数": sum(1 for x in related if x["是否已解析登记"] == "否"),
                "建议处理": "先补未解析PDF" if any(x["是否已解析登记"] == "否" for x in related) else "进入已解析图谱精修",
            }
        )

    batch_summary = summarize_batch_by_category(ledger_rows)

    priority = []
    category_batch_index = {x["疾病大类"]: x for x in batch_summary}
    for row in category_summary:
        category = row["疾病大类"]
        batch = category_batch_index.get(category, {})
        has_import = int(batch.get("已写入Neo4j批次", 0) or 0)
        has_cdss = int(batch.get("CDSS决策层批次", 0) or 0)
        unparsed = int(row["未解析PDF数"])
        if has_import and has_cdss and unparsed == 0:
            action = "精修正式CDSS链路"
            rank = 1
        elif has_import and unparsed > 0:
            action = "先补未解析PDF，再精修CDSS链路"
            rank = 2
        elif has_import:
            action = "补CDSS决策层"
            rank = 3
        elif row["PDF总数"] > 0:
            action = "启动正式解析批次"
            rank = 4
        else:
            action = "暂不处理"
            rank = 9
        priority.append(
            {
                "优先级": rank,
                "疾病大类": category,
                "建议动作": action,
                "PDF总数": row["PDF总数"],
                "已解析登记PDF数": row["已解析登记PDF数"],
                "未解析PDF数": row["未解析PDF数"],
                "登记批次数": batch.get("登记批次数", 0),
                "已写入Neo4j批次": has_import,
                "CDSS决策层批次": has_cdss,
            }
        )
    priority.sort(key=lambda x: (x["优先级"], -int(x["未解析PDF数"]), x["疾病大类"]))

    write_csv(OUT_DIR / "01_PDF使用状态总表_20260717.csv", pdf_status)
    write_csv(OUT_DIR / "02_疾病大类批次状态总表_20260717.csv", batch_summary)
    write_csv(OUT_DIR / "03_指南精修优先级总表_20260717.csv", priority)

    summary = {
        "generated_at": NOW,
        "pdf_total": len(all_pdfs),
        "pdf_used_registered": sum(1 for x in pdf_status if x["是否已解析登记"] == "是"),
        "pdf_unparsed": sum(1 for x in pdf_status if x["是否已解析登记"] == "否"),
        "ledger_batch_count": len(ledger_rows),
        "category_count": len(category_summary),
        "top_priority": priority[:10],
    }
    (OUT_DIR / "00_指南PDF精修层全库总检_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# 指南PDF精修层全库总检报告",
        "",
        f"- 生成时间：{NOW}",
        "- 检查口径：先区分已解析PDF、未解析PDF、已写库批次、CDSS决策层批次，再决定精修顺序。",
        f"- PDF总数：{summary['pdf_total']}",
        f"- 已解析登记PDF数：{summary['pdf_used_registered']}",
        f"- 未解析PDF数：{summary['pdf_unparsed']}",
        f"- 批次台账记录数：{summary['ledger_batch_count']}",
        "",
        "## 下一步总策略",
        "",
        "1. 已解析并入库的大类：直接做正式CDSS链路精修。",
        "2. 已解析但未写库的大类：先核对是否已有替代入库批次，避免重复导入。",
        "3. 未解析PDF：先进入候选池，按疾病大类和权威等级决定是否补批次。",
        "4. 教材骨架不再返工，只作为稳定底座。",
        "",
        "## 优先级前10",
        "",
        "| 优先级 | 疾病大类 | 建议动作 | PDF总数 | 已解析 | 未解析 | 已写库批次 | CDSS批次 |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in priority[:10]:
        lines.append(
            f"| {row['优先级']} | {row['疾病大类']} | {row['建议动作']} | {row['PDF总数']} | {row['已解析登记PDF数']} | {row['未解析PDF数']} | {row['已写入Neo4j批次']} | {row['CDSS决策层批次']} |"
        )
    lines += [
        "",
        "## 输出文件",
        "",
        "- `01_PDF使用状态总表_20260717.csv`：每份PDF是否已解析登记。",
        "- `02_疾病大类批次状态总表_20260717.csv`：台账中每个疾病大类的批次状态。",
        "- `03_指南精修优先级总表_20260717.csv`：下一轮总精修排序。",
    ]
    (OUT_DIR / "00_指南PDF精修层全库总检报告_20260717.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
