from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    ROOT
    / "项目管理中心_project_management"
    / "148_标准字典融合V2_20260721"
    / "04_融合执行计划"
    / "04_Oracle现有字典变更待审清单.csv"
)
DEFAULT_OUTPUT = (
    ROOT
    / "项目管理中心_project_management"
    / "148_标准字典融合V2_20260721"
    / "07_批量审核"
)


TABLE_NAMES = {
    "K_SYMPTOM_DICT": "症状标准字典",
    "K_CLINICAL_SIGN_DICT": "体征标准字典",
    "K_EXAM_ITEM_DICT": "检查项目标准字典",
    "K_EXAM_OBSERVATION_DICT": "检查发现标准字典",
    "K_LAB_ITEM_DICT": "检验项目标准字典",
    "K_LAB_SUBITEM_DICT": "检验细项标准字典",
    "K_DRUG_DICT": "药品标准字典",
    "K_TREATMENT_DICT": "治疗项目标准字典",
}

GROUP_GUIDANCE = {
    "K_SYMPTOM_DICT": "只登记患者可主诉的原子症状；章节标题、疾病概括和复合描述已自动退回。",
    "K_CLINICAL_SIGN_DICT": "只登记医生可观察或查体获得的原子体征；疾病壳节点和复合体征已自动退回。",
    "K_EXAM_ITEM_DICT": "只登记可开立或可执行的检查项目；疾病专属“某病检查”标题已自动退回。",
    "K_EXAM_OBSERVATION_DICT": "只登记检查产生的可观察结果；诊断推理句和规则条件已自动转出。",
    "K_LAB_ITEM_DICT": "只登记可开立的检验项目，例如血常规；检验结果和规则不进入本表。",
    "K_LAB_SUBITEM_DICT": "只登记检验报告中的细项指标，例如白细胞计数；异常状态和阈值规则不进入本表。",
    "K_DRUG_DICT": "只登记具体药品中文通用名；药物类别、联合方案和治疗策略已自动转出。",
    "K_TREATMENT_DICT": "登记非药品、非手术的标准治疗项目；宽泛治疗标题仍需在执行前做证据核验。",
}


HEADING_PATTERN = re.compile(
    r"^(?:第[一二三四五六七八九十百0-9]+(?:章|节|部分)|[一二三四五六七八九十]+[、.．]|\([一二三四五六七八九十]+\)|（[一二三四五六七八九十]+）)"
)
DISEASE_TERMS = (
    "心肌病",
    "心肌梗死",
    "心律失常",
    "房室传导阻滞",
    "主动脉夹层",
    "主动脉瘤",
    "心力衰竭",
    "心衰",
    "高血压",
    "心绞痛",
    "冠心病",
    "冠状动脉",
    "瓣膜病",
    "肺动脉高压",
    "心包炎",
    "心内膜炎",
    "房颤",
    "心房颤动",
    "心房扑动",
    "室上性心动过速",
    "室性心动过速",
    "室颤",
    "STEMI",
    "NSTEMI",
    "AMI",
    "VTE",
    "三尖瓣反流",
    "主动脉瓣反流",
    "主动脉瓣狭窄",
    "二尖瓣反流",
    "二尖瓣狭窄",
    "先天性心脏病",
    "动脉导管未闭",
    "卵圆孔未闭",
    "外周动脉疾病",
    "室间隔缺损",
    "房间隔缺损",
    "家族性高胆固醇血症",
    "血脂异常",
    "高胆固醇血症",
    "窦性心动过缓",
    "窦房传导阻滞",
    "窦房结功能障碍",
    "肺动脉瓣狭窄",
    "心脏性猝死",
    "急性冠脉综合征",
    "束支传导阻滞",
)
SHELL_SUFFIXES = ("症状", "体征", "检查", "检验", "治疗", "手术")
RULE_TERMS = ("提示", "可诊断", "可排除", "支持诊断", "诊断为", "应考虑", "风险增加", "风险降低")
DRUG_CLASS_PATTERN = re.compile(
    r"(?:类药物|药物$|抑制剂$|拮抗剂$|阻滞剂$|利尿剂$|抗凝剂$|抗凝药$|抗凝药物$|抗血小板药$|抗血小板药物$|降压药$|调脂药$|正性肌力药$|血管扩张剂$|溶栓药$)"
)
LAB_RESULT_STATE_PATTERN = re.compile(
    r"(?:升高|降低|增高|减低|增快|减慢|增多|减少|消失|异常|阳性|阴性|超标|达标)$"
)
NON_OBSERVATION_CONTEXTS = {"发病时间", "家族遗传证据", "病原体证据"}
NON_ATOMIC_SIGN_NAMES = {"左心室肥厚", "心功能不全", "肺水肿", "肺淤血", "胸腔积液", "靶器官损害"}


BASE_FIELDS = [
    "id",
    "entity_type",
    "kg_node_code",
    "kg_node_name",
    "target_table",
    "issue_type",
    "reason",
    "proposed_value",
    "current_value",
    "source",
    "target_id",
    "target_code",
    "target_name",
]
CLASSIFICATION_FIELDS = [
    "review_layer",
    "recommended_action",
    "classification_reason",
    "group_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def is_heading_pollution(name: str) -> bool:
    text = name.strip()
    return bool(HEADING_PATTERN.search(text) or re.search(r"[-—]\s*(?:症状|体征|检查|检验|治疗|手术)$", text))


def is_disease_shell(name: str) -> bool:
    text = name.strip()
    return text.endswith(SHELL_SUFFIXES) and any(term.lower() in text.lower() for term in DISEASE_TERMS)


def is_rule_expression(name: str) -> bool:
    text = name.strip()
    return any(term in text for term in RULE_TERMS)


def is_drug_category(name: str, target_table: str) -> bool:
    return target_table == "K_DRUG_DICT" and bool(DRUG_CLASS_PATTERN.search(name.strip()))


def is_non_atomic_sign(name: str, target_table: str) -> bool:
    if target_table != "K_CLINICAL_SIGN_DICT":
        return False
    text = name.strip()
    return (
        text.endswith(("体征", "表现"))
        or text in NON_ATOMIC_SIGN_NAMES
        or "不匹配" in text
        or "、" in text
        or "或" in text
    )


def is_non_observation_context(name: str, target_table: str) -> bool:
    return target_table == "K_EXAM_OBSERVATION_DICT" and name.strip() in NON_OBSERVATION_CONTEXTS


def is_lab_result_state(name: str, target_table: str) -> bool:
    if target_table != "K_LAB_SUBITEM_DICT":
        return False
    text = name.strip()
    return bool(
        LAB_RESULT_STATE_PATTERN.search(text)
        or re.search(r"[<>＜＞≤≥]=?\s*\d", text)
        or "临界值" in text
        or re.search(r"可.*排除", text)
    )


def is_non_atomic_symptom(name: str, target_table: str) -> bool:
    if target_table != "K_SYMPTOM_DICT":
        return False
    text = name.strip()
    return text.endswith("相关症状") or "、" in text or "或" in text


def classify_review_row(source_row: dict[str, Any]) -> dict[str, Any]:
    row = dict(source_row)
    issue_type = str(row.get("issue_type") or "").strip()
    name = str(row.get("kg_node_name") or "").strip()
    target_table = str(row.get("target_table") or "").strip()
    row["group_id"] = ""

    if issue_type == "WRONG_TYPE_OR_COMPOSITE":
        row.update(
            review_layer="无需人工审核",
            recommended_action="退回并重分类",
            classification_reason="原队列已确认类型错误或不是原子项；不进入Oracle注册。",
        )
    elif issue_type == "RULE_OR_WRONG_TYPE":
        row.update(
            review_layer="无需人工审核",
            recommended_action="转入临床规则",
            classification_reason="该内容属于条件或推理结论，不是标准字典实体。",
        )
    elif issue_type == "ALIAS_TO_TERM_CANDIDATE":
        row.update(
            review_layer="无需人工审核",
            recommended_action="保留为别名映射",
            classification_reason="保留在图谱别名和术语映射层，不改既有Oracle标准字典主记录。",
        )
    elif issue_type == "AMBIGUOUS_MATCH":
        row.update(
            review_layer="逐条人工裁决",
            recommended_action="选择唯一标准记录",
            classification_reason="现有Oracle存在多个候选，必须明确选择、暂缓或退回治理。",
        )
    elif issue_type == "MISSING_IN_EXISTING_DICTIONARY":
        if is_heading_pollution(name):
            row.update(
                review_layer="无需人工审核",
                recommended_action="退回并清理污染",
                classification_reason="名称含章节序号、标题结构或人工拼接后缀，不是可注册的临床原子项。",
            )
        elif is_disease_shell(name):
            row.update(
                review_layer="无需人工审核",
                recommended_action="退回并拆分为原子项",
                classification_reason="名称是疾病加维度形成的壳节点，应回到原文拆出真实临床项。",
            )
        elif is_non_atomic_sign(name, target_table):
            row.update(
                review_layer="无需人工审核",
                recommended_action="退回并拆分为原子项",
                classification_reason="该名称是疾病体征标题、复合表现或其他临床维度，不是可独立登记的原子体征。",
            )
        elif is_non_atomic_symptom(name, target_table):
            row.update(
                review_layer="无需人工审核",
                recommended_action="退回并拆分为原子项",
                classification_reason="该名称合并多个症状或只是疾病相关症状概括，应拆成可独立匹配的原子症状。",
            )
        elif is_non_observation_context(name, target_table):
            row.update(
                review_layer="无需人工审核",
                recommended_action="转入临床规则",
                classification_reason="该名称是病史、遗传或病原证据条件，不是检查项目产生的观察结果。",
            )
        elif is_lab_result_state(name, target_table):
            row.update(
                review_layer="无需人工审核",
                recommended_action="拆分为检验细项与结果状态",
                classification_reason="名称把检验细项和升高、异常或阈值条件混在一起，应由标准细项加结果/规则表达。",
            )
        elif is_rule_expression(name):
            row.update(
                review_layer="无需人工审核",
                recommended_action="转入临床规则",
                classification_reason="名称包含诊断或风险推理，不应注册为普通标准字典实体。",
            )
        elif is_drug_category(name, target_table):
            row.update(
                review_layer="无需人工审核",
                recommended_action="转为药物类别",
                classification_reason="这是药物类别或药理类别，不是可开立的具体药品通用名。",
            )
        else:
            row.update(
                review_layer="分组批量确认",
                recommended_action="候选注册",
                classification_reason="通过标题污染、疾病壳、推理句和药物类别初筛，进入同类批量确认。",
                group_id=f"GROUP-{target_table}",
            )
    else:
        row.update(
            review_layer="逐条人工裁决",
            recommended_action="核对未知问题",
            classification_reason=f"未识别问题类型：{issue_type or '空'}。",
        )
    return row


def _parse_json(value: Any, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def build_review_package(rows: list[dict[str, Any]]) -> dict[str, Any]:
    classified = [classify_review_row(row) for row in rows]
    automatic = [row for row in classified if row["review_layer"] == "无需人工审核"]
    group_candidates = [row for row in classified if row["review_layer"] == "分组批量确认"]
    manual = [row for row in classified if row["review_layer"] == "逐条人工裁决"]

    groups: list[dict[str, Any]] = []
    by_table: dict[str, list[dict[str, Any]]] = {}
    for row in group_candidates:
        by_table.setdefault(str(row.get("target_table") or "未指定"), []).append(row)
    for table in sorted(by_table):
        items = by_table[table]
        groups.append(
            {
                "group_id": f"GROUP-{table}",
                "target_table": table,
                "table_name": TABLE_NAMES.get(table, table),
                "candidate_count": len(items),
                "sample_names": [str(item.get("kg_node_name") or "") for item in items[:12]],
                "guidance": GROUP_GUIDANCE.get(table, "按原子性、可执行性和标准名称进行批量确认。"),
                "default_decision": "PENDING",
            }
        )

    for row in manual:
        row["candidate_options"] = _parse_json(row.get("proposed_value"), [])

    layer_counts = Counter(row["review_layer"] for row in classified)
    action_counts = Counter(row["recommended_action"] for row in classified)
    table_counts = Counter(str(row.get("target_table") or "未指定") for row in classified)
    summary = {
        "total": len(classified),
        "automatic_count": len(automatic),
        "group_candidate_count": len(group_candidates),
        "group_count": len(groups),
        "manual_count": len(manual),
        "layer_counts": dict(sorted(layer_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "table_counts": dict(sorted(table_counts.items())),
        "row_conservation_passed": len(classified) == len(automatic) + len(group_candidates) + len(manual),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "oracle_write_performed": False,
    }
    return {
        "summary": summary,
        "automatic": automatic,
        "group_candidates": group_candidates,
        "manual": manual,
        "groups": groups,
    }


def build_decision_template(package: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in package["groups"]:
        rows.append(
            {
                "decision_scope": "GROUP",
                "group_id": group["group_id"],
                "review_id": "",
                "target_table": group["target_table"],
                "candidate_name": f"{group['table_name']}（{group['candidate_count']}条）",
                "decision": "PENDING",
                "selected_target_id": "",
                "reviewer": "",
                "review_time": "",
                "note": "",
                "execution_authorized": 0,
            }
        )
    for item in package["manual"]:
        rows.append(
            {
                "decision_scope": "ITEM",
                "group_id": "",
                "review_id": item.get("id", ""),
                "target_table": item.get("target_table", ""),
                "candidate_name": item.get("kg_node_name", ""),
                "decision": "PENDING",
                "selected_target_id": "",
                "reviewer": "",
                "review_time": "",
                "note": "",
                "execution_authorized": 0,
            }
        )
    return rows


def write_review_html(path: Path, package: dict[str, Any]) -> None:
    payload = json.dumps(package, ensure_ascii=False).replace("</", "<\\/")
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oracle字典批量审核</title>
<style>
:root{{--blue:#175cd3;--ink:#162033;--muted:#667085;--line:#d8dee9;--bg:#f3f6fa;--good:#067647;--warn:#b54708}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);font-family:"Microsoft YaHei",Arial,sans-serif;color:var(--ink)}}
header{{padding:22px 28px;background:#102a43;color:white}}header h1{{margin:0 0 8px;font-size:24px}}header p{{margin:4px 0;color:#d9e7f5}}
main{{padding:20px 28px;max-width:1500px;margin:auto}}.cards{{display:grid;grid-template-columns:repeat(4,minmax(180px,1fr));gap:12px;margin-bottom:18px}}
.card,.section{{background:white;border:1px solid var(--line);border-radius:12px;padding:16px}}.metric{{font-size:28px;font-weight:800;color:var(--blue)}}
.label{{color:var(--muted);font-size:13px;margin-top:4px}}.section{{margin:14px 0}}.section h2{{margin:0 0 8px;font-size:20px}}
.notice{{padding:12px;border-left:4px solid var(--blue);background:#eef4ff;border-radius:6px;margin:12px 0}}.good{{color:var(--good)}}.warn{{color:var(--warn)}}
.group{{border:1px solid var(--line);border-radius:10px;padding:14px;margin:10px 0}}.group-head{{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}}
.group h3{{margin:0}}select,input,button,textarea{{font:inherit;padding:8px 10px;border:1px solid #b9c3d1;border-radius:6px}}button{{background:var(--blue);color:white;border:0;cursor:pointer}}
button.secondary{{background:#475467}}details{{margin-top:10px}}table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}}th,td{{border:1px solid var(--line);padding:7px;text-align:left;vertical-align:top}}th{{background:#eef2f7}}
.pill{{display:inline-block;padding:2px 7px;border-radius:10px;background:#e7f0ff;color:#1849a9;font-size:12px}}.manual{{border-left:4px solid #f79009}}
.footer-actions{{position:sticky;bottom:0;background:rgba(243,246,250,.95);padding:12px 0;display:flex;gap:10px;align-items:center}}@media(max-width:900px){{.cards{{grid-template-columns:1fr 1fr}}main{{padding:14px}}}}
</style></head><body>
<header><h1>Oracle 标准字典批量审核</h1><p>您不需要逐条查看全部候选，只需确认分组决策和少量歧义项。</p><p>本页面只导出审核结果，不连接、不修改 Oracle。</p></header>
<main><div class="cards" id="cards"></div>
<div class="notice"><strong>审核方法：</strong>先看每组说明和样例；同意后只生成拟执行清单。真正修改既有 Oracle 字典仍要求 <code>execution_authorized=1</code>，并另做快照和回滚。</div>
<section class="section"><h2>一、无需您审核</h2><div id="automaticSummary"></div><details><summary>查看自动退回、重分类和别名映射明细</summary><div id="automaticTable"></div></details></section>
<section class="section"><h2>二、按字典分组批量确认</h2><p class="label">每组一次选择；可展开查看全部候选。</p><div id="groups"></div></section>
<section class="section"><h2>三、逐条裁决歧义项</h2><p class="label">这里只保留无法自动确定唯一 Oracle 记录的少量项目。</p><div id="manual"></div></section>
<div class="footer-actions"><button id="export">导出审核结果CSV</button><button class="secondary" id="reset">重置本页选择</button><span class="label" id="status"></span></div></main>
<script>
const pkg={payload};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
document.querySelector('#cards').innerHTML=[['原始待审',pkg.summary.total],['无需人工审核',pkg.summary.automatic_count],['分组候选',pkg.summary.group_candidate_count],['逐条裁决',pkg.summary.manual_count]].map(x=>`<div class="card"><div class="metric">${{x[1]}}</div><div class="label">${{x[0]}}</div></div>`).join('');
const ac=Object.entries(pkg.summary.action_counts).filter(x=>['退回并重分类','转入临床规则','保留为别名映射','退回并清理污染','退回并拆分为原子项','拆分为检验细项与结果状态','转为药物类别'].includes(x[0]));
document.querySelector('#automaticSummary').innerHTML=ac.map(x=>`<span class="pill">${{esc(x[0])}}：${{x[1]}}</span>`).join(' ');
function table(rows){{return `<table><thead><tr><th>名称</th><th>目标字典</th><th>处理</th><th>原因</th></tr></thead><tbody>${{rows.map(r=>`<tr><td>${{esc(r.kg_node_name)}}</td><td>${{esc(r.target_table)}}</td><td>${{esc(r.recommended_action)}}</td><td>${{esc(r.classification_reason)}}</td></tr>`).join('')}}</tbody></table>`}}
document.querySelector('#automaticTable').innerHTML=table(pkg.automatic);
document.querySelector('#groups').innerHTML=pkg.groups.map(g=>{{const items=pkg.group_candidates.filter(x=>x.group_id===g.group_id);return `<div class="group" data-group="${{esc(g.group_id)}}"><div class="group-head"><div><h3>${{esc(g.table_name)}} <span class="pill">${{g.candidate_count}}条</span></h3><div class="label">${{esc(g.guidance)}}</div></div><select class="group-decision"><option value="PENDING">请选择</option><option value="APPROVE_PREPARE">同意生成拟执行清单</option><option value="HOLD">整组暂缓</option><option value="RETURN_CLEAN">退回重新清洗</option></select></div><div class="label">样例：${{g.sample_names.map(esc).join('、')}}</div><details><summary>查看本组全部${{g.candidate_count}}条</summary>${{table(items)}}</details></div>`}}).join('');
document.querySelector('#manual').innerHTML=pkg.manual.map(m=>`<div class="group manual" data-review="${{esc(m.id)}}"><h3>${{esc(m.kg_node_name)}}</h3><div class="label">现有候选：${{m.candidate_options.length}} 个。请选择唯一记录，或暂缓治理。</div><select class="item-decision"><option value="PENDING">请选择</option>${{m.candidate_options.map(o=>`<option value="SELECT:${{esc(o.id)}}">${{esc(o.code)}}｜${{esc(o.name)}}｜${{esc(o.id)}}</option>`).join('')}}<option value="HOLD">暂缓，不改</option><option value="RETURN_CLEAN">退回字典治理</option></select></div>`).join('');
function decisions(){{const now=new Date().toISOString();const rows=[];document.querySelectorAll('[data-group]').forEach(el=>rows.push({{decision_scope:'GROUP',group_id:el.dataset.group,review_id:'',target_table:el.dataset.group.replace('GROUP-',''),candidate_name:'整组候选',decision:el.querySelector('select').value,selected_target_id:'',reviewer:'',review_time:now,note:'',execution_authorized:0}}));document.querySelectorAll('[data-review]').forEach(el=>{{const value=el.querySelector('select').value;rows.push({{decision_scope:'ITEM',group_id:'',review_id:el.dataset.review,target_table:'K_SYMPTOM_DICT',candidate_name:el.querySelector('h3').textContent,decision:value.startsWith('SELECT:')?'SELECT_TARGET':value,selected_target_id:value.startsWith('SELECT:')?value.slice(7):'',reviewer:'',review_time:now,note:'',execution_authorized:0}})}});return rows}}
document.querySelector('#export').onclick=()=>{{const rows=decisions(),pending=rows.filter(x=>x.decision==='PENDING').length;if(pending&&!confirm(`还有 ${{pending}} 项未选择，仍要导出吗？`))return;const keys=Object.keys(rows[0]);const csv='\ufeff'+[keys.join(','),...rows.map(r=>keys.map(k=>'"'+String(r[k]??'').replaceAll('"','""')+'"').join(','))].join('\\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));a.download='Oracle字典审核结果.csv';a.click();document.querySelector('#status').textContent=`已导出 ${{rows.length}} 项决策；未授权写库。`}};
document.querySelector('#reset').onclick=()=>{{document.querySelectorAll('select').forEach(x=>x.value='PENDING');document.querySelector('#status').textContent='已重置。'}};
</script></body></html>"""
    path.write_text(html, encoding="utf-8")


def write_package(output_dir: Path, package: dict[str, Any], date_text: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "01_审核压缩汇总.json"
    automatic_path = output_dir / "02_无需人工审核清单.csv"
    group_path = output_dir / "03_分组批量审核清单.csv"
    detail_path = output_dir / "04_分组候选明细.csv"
    manual_path = output_dir / "05_人工裁决清单.csv"
    result_path = output_dir / "06_审核结果回写模板.csv"
    html_path = output_dir / f"Oracle字典批量审核页_{date_text}.html"

    summary_path.write_text(json.dumps(package["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    detail_fields = BASE_FIELDS + CLASSIFICATION_FIELDS
    write_csv(automatic_path, package["automatic"], detail_fields)
    write_csv(
        group_path,
        package["groups"],
        ["group_id", "target_table", "table_name", "candidate_count", "sample_names", "guidance", "default_decision"],
    )
    write_csv(detail_path, package["group_candidates"], detail_fields)
    manual_rows = []
    for item in package["manual"]:
        copied = dict(item)
        copied["candidate_options"] = json.dumps(copied.get("candidate_options", []), ensure_ascii=False)
        manual_rows.append(copied)
    write_csv(manual_path, manual_rows, detail_fields + ["candidate_options"])
    write_csv(
        result_path,
        build_decision_template(package),
        ["decision_scope", "group_id", "review_id", "target_table", "candidate_name", "decision", "selected_target_id", "reviewer", "review_time", "note", "execution_authorized"],
    )
    write_review_html(html_path, package)
    return {
        "summary": str(summary_path),
        "automatic": str(automatic_path),
        "groups": str(group_path),
        "details": str(detail_path),
        "manual": str(manual_path),
        "result_template": str(result_path),
        "html": str(html_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将Oracle字典逐条待审队列压缩为自动处理、分组确认和少量人工裁决。")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="原始待审CSV")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="审核资产输出目录")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="输出文件日期")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = read_csv(args.input)
    package = build_review_package(rows)
    paths = write_package(args.output, package, args.date)
    result = {"summary": package["summary"], "outputs": paths}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if package["summary"]["row_conservation_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
