# -*- coding: utf-8 -*-
"""历史全书回捞候选池可复用性抽样核查。

输入来自上一阶段“疾病名称与章节坐标对齐”产物。
本脚本只做本地 CSV/JSON/MD 输出，不连接 Neo4j，不生成入库 delta。

核心目标：
1. 区分当前骨架质量问题与历史候选池复用风险；
2. 对全部“可进入抽样复核后归并”的候选做机器预审分层；
3. 生成可给人快速查看的分层抽样样本；
4. 判断旧候选池是否值得批量复用，或仅作为重抽取线索。
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = "20260712"

ALIGN_DIR = ROOT / "骨架质量闭环_skeleton_quality_loop" / f"{RUN_DATE}_心血管内科疾病名称与证据坐标对齐"
OUT_DIR = ROOT / "骨架质量闭环_skeleton_quality_loop" / f"{RUN_DATE}_历史候选池复用抽样核查"

EVIDENCE_AUDIT = ALIGN_DIR / f"证据文本质量与坐标审计_{RUN_DATE}.csv"
MERGEABLE_SUMMARY = ALIGN_DIR / f"可归并候选摘要_{RUN_DATE}.csv"
ALIGN_SUMMARY = ALIGN_DIR / f"疾病名称与章节坐标对齐_summary_{RUN_DATE}.json"

OUT_PRECHECK = OUT_DIR / f"历史候选池可复用性机器预审明细_{RUN_DATE}.csv"
OUT_SAMPLE = OUT_DIR / f"历史候选池可复用性分层抽样_{RUN_DATE}.csv"
OUT_RISK_DIST = OUT_DIR / f"历史候选池复用风险分布_{RUN_DATE}.csv"
OUT_REPORT = OUT_DIR / f"历史候选池复用抽样核查报告_{RUN_DATE}.md"
OUT_SUMMARY = OUT_DIR / f"历史候选池复用抽样核查_summary_{RUN_DATE}.json"


NEGATIVE_OR_CONTEXT_ONLY_KEYWORDS = [
    "无下列情况",
    "不使用",
    "不推荐",
    "禁用",
    "禁忌",
    "排除",
    "除外",
    "不适合",
    "危险性增高",
    "等待进行",
    "不能治疗",
    "仅用于",
    "相关的",
]

NON_TARGET_CONTEXT_KEYWORDS = [
    "隐球菌",
    "感染中毒症",
    "sepsis",
    "ICU",
    "肿瘤",
    "脑卒中",
    "慢性阻塞性肺疾病",
]

GENERIC_ENTITY_NAMES = {
    "感染",
    "炎症",
    "手术",
    "出血",
    "休克",
    "水肿",
    "胸痛",
    "呼吸困难",
    "高血压",
    "低血压",
    "心动过速",
    "心动过缓",
    "心律失常",
    "心力衰竭",
    "药物治疗",
    "一般治疗",
    "手术治疗",
    "抗凝治疗",
    "降压治疗",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        seen = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def has_any(text: str, keywords: list[str] | set[str]) -> list[str]:
    return [kw for kw in keywords if kw and kw in text]


def classify_row(row: dict[str, str]) -> dict[str, Any]:
    text = row.get("evidence_text_preview", "")
    source = row.get("source_disease_name", "")
    target = row.get("target_subject_name", "")
    entity = row.get("entity_name", "")
    quality = row.get("evidence_quality", "")
    line_ok = row.get("line_in_target_docx_range") == "yes"

    disease_mentioned = bool((source and source in text) or (target and target in text))
    entity_mentioned = bool(entity and entity in text)
    negative_hits = has_any(text, NEGATIVE_OR_CONTEXT_ONLY_KEYWORDS)
    non_target_hits = has_any(text, NON_TARGET_CONTEXT_KEYWORDS)
    generic_entity = entity in GENERIC_ENTITY_NAMES or len(entity) <= 2

    risk_flags: list[str] = []
    if not line_ok:
        risk_flags.append("章节坐标未对齐")
    if quality == "中等证据文本":
        risk_flags.append("证据未直接出现疾病名")
    if not disease_mentioned:
        risk_flags.append("证据片段缺疾病名")
    if not entity_mentioned:
        risk_flags.append("证据片段缺实体名")
    if negative_hits:
        risk_flags.append("否定/禁忌/上下文限定语")
    if non_target_hits:
        risk_flags.append("疑似非目标章节上下文")
    if generic_entity:
        risk_flags.append("实体过泛需疾病上下文")

    # 这里刻意不输出“可直接入库”。历史候选池即使机器预审通过，也必须进入人工抽样复核。
    if negative_hits or non_target_hits:
        reuse_decision = "不建议复用"
        decision_reason = "证据片段疑似来自禁忌、排除、非目标章节或上下文限定，不适合复用为疾病事实"
    elif line_ok and quality == "强证据文本" and disease_mentioned and entity_mentioned and not generic_entity:
        reuse_decision = "可进入小批量人工复核"
        decision_reason = "疾病名、实体名、证据强度和章节坐标均较好，但仍需人工抽样确认"
    else:
        reuse_decision = "仅作重抽取线索"
        decision_reason = "候选可提示抽取方向，但证据上下文或章节坐标不足以支持自动归并"

    return {
        **row,
        "machine_precheck_decision": reuse_decision,
        "machine_precheck_reason": decision_reason,
        "risk_flags": "；".join(risk_flags),
        "risk_flag_count": len(risk_flags),
        "disease_mentioned_in_evidence": "yes" if disease_mentioned else "no",
        "entity_mentioned_in_evidence": "yes" if entity_mentioned else "no",
        "negative_context_hits": "；".join(negative_hits),
        "non_target_context_hits": "；".join(non_target_hits),
        "generic_entity": "yes" if generic_entity else "no",
    }


def deterministic_sample(rows: list[dict[str, Any]], max_per_group: int = 4, max_total: int = 180) -> list[dict[str, Any]]:
    """按 决策-槽位-证据强度 分层抽样，保证高风险和可复核样本都可见。"""

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("machine_precheck_decision", "")),
            str(row.get("slot", "")),
            str(row.get("evidence_quality", "")),
        )
        groups[key].append(row)

    selected: list[dict[str, Any]] = []
    seen = set()
    for key in sorted(groups):
        group = sorted(
            groups[key],
            key=lambda r: (
                -int(r.get("risk_flag_count") or 0),
                str(r.get("source_disease_name", "")),
                str(r.get("entity_name", "")),
                str(r.get("evidence_code", "")),
            ),
        )
        for row in group[:max_per_group]:
            row_key = row.get("evidence_code", "") + "|" + row.get("entity_code", "")
            if row_key not in seen:
                seen.add(row_key)
                selected.append(row)

    # 补充每个疾病-槽位 mergeable_rows 靠前的代表，避免只抽到少数风险组。
    if len(selected) < max_total:
        top_rows = sorted(
            rows,
            key=lambda r: (
                str(r.get("source_disease_name", "")),
                str(r.get("slot", "")),
                -int(r.get("risk_flag_count") or 0),
                str(r.get("evidence_code", "")),
            ),
        )
        for row in top_rows:
            row_key = row.get("evidence_code", "") + "|" + row.get("entity_code", "")
            if row_key in seen:
                continue
            seen.add(row_key)
            selected.append(row)
            if len(selected) >= max_total:
                break

    return selected[:max_total]


def main() -> int:
    align_summary = json.loads(ALIGN_SUMMARY.read_text(encoding="utf-8"))
    evidence_rows = read_csv(EVIDENCE_AUDIT)

    mergeable = [r for r in evidence_rows if r.get("merge_decision") == "可进入抽样复核后归并"]
    precheck_rows = [classify_row(r) for r in mergeable]

    decision_counter = Counter(r["machine_precheck_decision"] for r in precheck_rows)
    slot_counter = Counter(r["slot"] for r in precheck_rows)
    decision_slot_counter = Counter((r["machine_precheck_decision"], r["slot"]) for r in precheck_rows)
    risk_flag_counter: Counter[str] = Counter()
    for row in precheck_rows:
        for flag in str(row.get("risk_flags", "")).split("；"):
            if flag:
                risk_flag_counter[flag] += 1

    risk_dist_rows = []
    for (decision, slot), count in sorted(decision_slot_counter.items(), key=lambda x: (-x[1], x[0])):
        risk_dist_rows.append(
            {
                "machine_precheck_decision": decision,
                "slot": slot,
                "row_count": count,
                "slot_total": slot_counter[slot],
                "ratio_in_slot": round(count / slot_counter[slot], 4) if slot_counter[slot] else 0,
            }
        )

    sample_rows = deterministic_sample(precheck_rows)

    write_csv(OUT_PRECHECK, precheck_rows)
    write_csv(OUT_SAMPLE, sample_rows)
    write_csv(OUT_RISK_DIST, risk_dist_rows)

    direct_batch_reuse_allowed = False
    small_review_count = decision_counter.get("可进入小批量人工复核", 0)
    clue_count = decision_counter.get("仅作重抽取线索", 0)
    reject_count = decision_counter.get("不建议复用", 0)
    total = len(precheck_rows)

    if total and small_review_count / total >= 0.7:
        reuse_level = "可考虑分病种小批量复核后复用"
    elif total and (clue_count + reject_count) / total >= 0.7:
        reuse_level = "不建议批量复用，仅作为重抽取线索"
    else:
        reuse_level = "可局部复用，但必须按病种和槽位人工抽检"

    summary = {
        "run_date": RUN_DATE,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "neo4j_written": False,
        "delta_generated": False,
        "source_scope": "历史候选池复用审计，不作为当前骨架缺陷",
        "input": {
            "evidence_audit": str(EVIDENCE_AUDIT),
            "mergeable_summary": str(MERGEABLE_SUMMARY),
            "align_summary": str(ALIGN_SUMMARY),
            "backfill_index_scope": align_summary.get("input", {}).get("backfill_index_scope"),
            "d6_matrix_scope": align_summary.get("input", {}).get("d6_matrix_scope"),
        },
        "counts": {
            "mergeable_input_rows": total,
            "sample_rows": len(sample_rows),
            "machine_precheck_decision": dict(decision_counter),
            "risk_flags": dict(risk_flag_counter),
            "slots": dict(slot_counter),
        },
        "decision": {
            "direct_batch_reuse_allowed": direct_batch_reuse_allowed,
            "reuse_level": reuse_level,
            "hard_rule": "历史候选池不得直接生成入库delta；最多作为小批量人工复核或重抽取线索。",
        },
    }
    write_json(OUT_SUMMARY, summary)

    report = f"""# 历史候选池复用抽样核查报告（{RUN_DATE}）

## 1. 本轮边界

- 输入是 2026-06-25 历史全书回捞候选池经上一轮筛出的 `{total}` 条“可进入抽样复核后归并”候选。
- 本轮只做本地机器预审和分层抽样，不连接 Neo4j。
- 本轮不生成入库 delta。
- 本轮发现的问题只代表“旧候选池复用风险”，不作为 2026-07-09 当前骨架缺陷。

## 2. 机器预审结论

```text
可进入小批量人工复核：{small_review_count}
仅作重抽取线索：{clue_count}
不建议复用：{reject_count}
分层抽样样本：{len(sample_rows)}
```

最终判断：`{reuse_level}`。

硬规则：历史候选池不得直接生成入库 delta；最多作为小批量人工复核或重抽取线索。

## 3. 主要风险信号

```text
{json.dumps(dict(risk_flag_counter), ensure_ascii=False, indent=2)}
```

## 4. 如何使用本轮结果

1. 优先查看 `{OUT_SAMPLE.name}`，这是给人快速判断旧候选池质量的抽样表。
2. 如样本确认可用，再按病种/槽位从 `{OUT_PRECHECK.name}` 中筛选 `machine_precheck_decision=可进入小批量人工复核`。
3. 对 `仅作重抽取线索` 的记录，不要复用原候选实体关系，只用来提示后续从教材/PDF原文重新抽取。
4. 对 `不建议复用` 的记录，默认不进入后续归并流程。

## 5. 输出文件

- `{OUT_PRECHECK.name}`
- `{OUT_SAMPLE.name}`
- `{OUT_RISK_DIST.name}`
- `{OUT_SUMMARY.name}`
"""
    write_text(OUT_REPORT, report)

    print("SAMPLE_AUDIT_OK")
    print("mergeable_input_rows=", total)
    print("sample_rows=", len(sample_rows))
    print("machine_precheck_decision=", dict(decision_counter))
    print("reuse_level=", reuse_level)
    print("neo4j_written=false")
    print("delta_generated=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
