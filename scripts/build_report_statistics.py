from __future__ import annotations

import csv
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COLLECTION_ROOT = ROOT / "心血管内科文献集合"
GUIDE_ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\诊疗指南")
TEXTBOOK_ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\心血管内科\书籍教材")
REPORT_SPEC = ROOT / "AI自动化工具-文献指南解析-报告统计.md"

ENTITY_DIMENSIONS = [
    ("Disease", "疾病"),
    ("DiseaseCategory", "疾病大类"),
    ("DiseaseSubcategory", "疾病子类"),
    ("Evidence", "证据"),
    ("Guideline", "指南/来源"),
    ("Symptom", "症状"),
    ("Sign", "体征"),
    ("Etiology", "病因"),
    ("RiskFactor", "危险因素"),
    ("Complication", "并发症"),
    ("Prognosis", "预后"),
    ("Exam", "检查"),
    ("LabTest", "检验"),
    ("DiagnosisCriteria", "诊断标准"),
    ("DifferentialDiagnosis", "鉴别诊断"),
    ("RiskStratification", "风险分层/评分"),
    ("TreatmentPlan", "治疗方案"),
    ("Medication", "药物"),
    ("Procedure", "手术/操作"),
    ("FollowUp", "随访"),
    ("ThresholdRule", "阈值规则"),
]

RELATION_DIMENSIONS = [
    ("has_symptom", "症状"),
    ("has_sign", "体征"),
    ("has_etiology", "病因"),
    ("has_risk_factor", "危险因素"),
    ("may_cause_complication", "并发症"),
    ("requires_exam", "检查"),
    ("requires_lab_test", "检验"),
    ("has_diagnostic_criteria", "诊断标准"),
    ("differentiates_from", "鉴别诊断"),
    ("has_risk_stratification", "风险分层"),
    ("has_treatment_plan", "治疗方案"),
    ("treated_by_medication", "药物治疗"),
    ("treated_by_procedure", "手术/操作"),
    ("has_follow_up", "随访"),
    ("has_threshold_rule", "阈值规则"),
    ("supported_by_evidence", "证据支撑"),
]

COVERAGE_DIMENSIONS = [
    ("定义", "Disease", None),
    ("症状", "Symptom", "has_symptom"),
    ("体征", "Sign", "has_sign"),
    ("病理生理", "Pathophysiology", "has_pathophysiology"),
    ("流行病学", "Epidemiology", "has_epidemiology"),
    ("病因", "Etiology", "has_etiology"),
    ("诊断标准", "DiagnosisCriteria", "has_diagnostic_criteria"),
    ("治疗方案", "TreatmentPlan", "has_treatment_plan"),
    ("随访", "FollowUp", "has_follow_up"),
    ("预后", "Prognosis", "has_prognosis"),
    ("风险分层", "RiskStratification", "has_risk_stratification"),
    ("鉴别诊断", "DifferentialDiagnosis", "differentiates_from"),
    ("并发症", "Complication", "may_cause_complication"),
    ("危险因素", "RiskFactor", "has_risk_factor"),
    ("手术/操作", "Procedure", "treated_by_procedure"),
    ("药物", "Medication", "treated_by_medication"),
    ("检验", "LabTest", "requires_lab_test"),
    ("检查", "Exam", "requires_exam"),
]

DISEASE_CATEGORY_BY_BATCH = {
    "BATCH-CARD-CM-20260622-001": "心肌病",
    "BATCH-CARD-CAD-20260623-001": "冠状动脉粥样硬化性心脏病（冠心病）",
    "BATCH-CARD-HF-20260629-001": "心力衰竭",
    "BATCH-CARD-AF-20260701-001_房颤_AtrialFibrillation": "心律失常",
    "FOUNDATION-CARD-20260624-001": "心血管内科基础骨架",
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_material_name(path_or_name: str) -> str:
    name = Path(path_or_name).stem
    name = unicodedata.normalize("NFKC", name).strip()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[\s_-]*(副本|copy)(\s*\(\d+\))?$", "", name, flags=re.I)
    name = re.sub(r"\s+", "", name)
    return name.lower()


def display_material_name(path_or_name: str) -> str:
    name = unicodedata.normalize("NFKC", Path(path_or_name).stem).strip()
    return re.sub(r"\s+", " ", name)


def iter_jsonl(path: Path):
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def count_source_root(root: Path) -> dict[str, Any]:
    rows = []
    if root.is_dir():
        rows = [path for path in root.rglob("*") if path.is_file()]
    by_ext = Counter(path.suffix.lower() or "<none>" for path in rows)
    grouped: dict[str, dict[str, Any]] = {}
    for path in rows:
        key = normalize_material_name(path.name)
        entry = grouped.setdefault(
            key,
            {
                "name": display_material_name(path.name),
                "formats": set(),
                "paths": [],
            },
        )
        entry["formats"].add(path.suffix.lower().lstrip(".") or "none")
        entry["paths"].append(str(path))
    materials = []
    for entry in grouped.values():
        materials.append(
            {
                "name": entry["name"],
                "formats": sorted(entry["formats"]),
                "path_count": len(entry["paths"]),
                "paths": sorted(entry["paths"]),
            }
        )
    materials = sorted(materials, key=lambda item: item["name"])
    pdf_count = by_ext.get(".pdf", 0)
    docx_count = by_ext.get(".docx", 0)
    doc_count = by_ext.get(".doc", 0)
    txt_count = by_ext.get(".txt", 0)
    return {
        "root": str(root),
        "file_count": len(rows),
        "unique_material_count": len(materials),
        "duplicate_format_count": max(0, len(rows) - len(materials)),
        "pdf_count": pdf_count,
        "docx_count": docx_count,
        "doc_count": doc_count,
        "txt_count": txt_count,
        "supported_count": pdf_count + docx_count + doc_count + txt_count,
        "by_ext": dict(sorted(by_ext.items())),
        "materials": materials,
    }


def count_jsonl_dimensions(batch_dir: Path) -> tuple[Counter, Counter, list[str]]:
    node_path = batch_dir / "05_data_instance" / "nodes_final.jsonl"
    rel_path = batch_dir / "05_data_instance" / "relations_final.jsonl"
    entity_counts: Counter = Counter()
    relation_counts: Counter = Counter()
    disease_names: list[str] = []
    for node in iter_jsonl(node_path) or []:
        entity_type = node.get("entityType", "")
        entity_counts[entity_type] += 1
        if entity_type == "Disease":
            disease_names.append(str(node.get("name") or ""))
    for rel in iter_jsonl(rel_path) or []:
        relation_counts[rel.get("relationType", "")] += 1
    return entity_counts, relation_counts, sorted({name for name in disease_names if name})


def batch_dirs() -> list[Path]:
    dirs = [COLLECTION_ROOT / "00_foundation_skeleton"]
    dirs.extend(sorted(path for path in COLLECTION_ROOT.iterdir() if path.is_dir() and path.name.startswith("BATCH-CARD-")))
    order = {
        "00_foundation_skeleton": 0,
        "BATCH-CARD-CM-20260622-001": 1,
        "BATCH-CARD-CAD-20260623-001": 2,
        "BATCH-CARD-HF-20260629-001": 3,
        "BATCH-CARD-AF-20260701-001_房颤_AtrialFibrillation": 4,
    }
    return sorted(dirs, key=lambda path: order.get(path.name, 99))


def foundation_config() -> dict[str, Any]:
    path = COLLECTION_ROOT / "00_foundation_skeleton" / "00_scope_and_config" / "specialty_foundation_config.yaml"
    if not path.is_file():
        path = COLLECTION_ROOT / "00_foundation_skeleton" / "specialty_foundation_config.yaml"
    data: dict[str, Any] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if ":" in line and not line.startswith(" "):
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()
    return data


def summarize_manifest(batch_dir: Path) -> dict[str, Any]:
    rows = read_csv(batch_dir / "01_source_manifest" / "source_documents_manifest.csv")
    included = [row for row in rows if row.get("inclusion_status") == "included"]
    unique_material_keys = {
        normalize_material_name(row.get("file_name", "") or row.get("full_path", ""))
        for row in included
    }
    included_by_type = Counter(row.get("source_type", "unknown") for row in included)
    included_by_ext = Counter(row.get("extension", "").lower() for row in included)
    guideline_pdf_count = sum(
        1
        for row in included
        if row.get("extension", "").lower() == ".pdf" and row.get("source_type") != "authoritative_textbook"
    )
    textbook_count = sum(1 for row in included if row.get("source_type") == "authoritative_textbook")
    return {
        "manifest_total": len(rows),
        "included_count": len(included),
        "included_unique_material_count": len(unique_material_keys),
        "excluded_count": len(rows) - len(included),
        "included_by_type": dict(sorted(included_by_type.items())),
        "included_by_ext": dict(sorted(included_by_ext.items())),
        "included_pdf_count": included_by_ext.get(".pdf", 0),
        "included_docx_count": included_by_ext.get(".docx", 0),
        "included_guideline_pdf_count": guideline_pdf_count,
        "included_textbook_count": textbook_count,
    }


def coverage_for_batch(item: dict[str, Any]) -> dict[str, Any]:
    entity_counts = item["entity_counts"]
    relation_counts = item["relation_counts"]
    covered = []
    for label, entity_type, relation_type in COVERAGE_DIMENSIONS:
        ok = entity_counts.get(entity_type, 0) > 0
        if relation_type:
            ok = ok or relation_counts.get(relation_type, 0) > 0
        covered.append((label, ok))
    count = sum(1 for _, ok in covered if ok)
    total = len(covered)
    return {
        "covered_count": count,
        "total_count": total,
        "rate": count / total if total else 0,
        "items": covered,
    }


class RawHTML(str):
    pass


def dot_bar(coverage: dict[str, Any]) -> RawHTML:
    dots = []
    for _, ok in coverage["items"]:
        dots.append("<span class='dot on'></span>" if ok else "<span class='dot off'></span>")
    return RawHTML("".join(dots))


def readable_safety_rows(final_safety: dict[str, Any]) -> list[list[Any]]:
    checks = [
        ("是否存在非标准节点", "non_kgnode_node_count", "没有。所有临床节点都带 KGNode 主标签，前端和查询不会混入脏节点。"),
        ("是否存在连到非标准节点的关系", "relation_touching_non_kgnode_count", "没有。关系两端都是标准 KGNode。"),
        ("是否存在技术编码当显示名", "technical_display_name_error_count", "没有。不会再把 EXAM-TTE 这类编码直接显示成临床名称。"),
        ("治疗方案是否还是空壳", "treatment_plan_actionability_error_count", "没有。治疗方案下面已经能继续连到药物、操作或路径。"),
        ("药物类别是否缺具体药物", "medication_class_without_specific_count", "没有。抗凝药物等类别已能继续找到具体药物。"),
        ("是否存在同类型同名重复实体", "duplicate_type_name_count", "没有。同一类型同一名称已经合并，避免前端数量虚高。"),
        ("是否存在重复语义关系", "duplicate_semantic_relation_count", "没有。同一 source-relation-target 不重复。"),
        ("是否存在鉴别诊断/治疗方案等空壳关系", "semantic_shell_relation_count", "没有。未发现把“诊断标准/治疗方案”当作具体实体挂边。"),
    ]
    rows = []
    for title, key, ok_text in checks:
        value = final_safety.get(key, "")
        if value in (0, "0"):
            conclusion = ok_text
        else:
            conclusion = f"有问题：{key}={value}，需要阻断继续导入或上线。"
        rows.append([title, value, conclusion])
    rows.append(["总判断", final_safety.get("global_safety_gate_status", ""), "passed 表示服务器图谱硬质量门通过；不等于正式 CDSS 强推荐已上线。"])
    return rows


def summarize_batch(batch_dir: Path) -> dict[str, Any]:
    config = read_json(batch_dir / "00_scope_and_config" / "batch_config.json")
    if batch_dir.name == "00_foundation_skeleton":
        fconf = foundation_config()
        batch_id = fconf.get("batch_id") or "FOUNDATION-CARD-20260624-001"
        specialty = fconf.get("specialty") or "心血管内科"
        scope_type = "specialty_foundation"
        scope_target = "心血管内科基础骨架库"
        created_time = fconf.get("created_at") or ""
    else:
        batch_id = config.get("batch_id", batch_dir.name)
        specialty = config.get("specialty", "心血管内科")
        scope_type = config.get("scope_type", "")
        scope_target = config.get("scope_target", batch_dir.name)
        created_time = config.get("created_time", "")

    manifest_stats = summarize_manifest(batch_dir)
    quality = read_json(batch_dir / "06_quality_audit" / "quality_gate_summary.json")
    evidence_summary = read_json(batch_dir / "04_evidence_and_extraction" / "guideline_evidence_summary.json")
    graph_summary = read_json(batch_dir / "04_evidence_and_extraction" / "graph_extraction_summary.json")
    import_summary = read_json(batch_dir / "08_neo4j_import" / "neo4j_import_summary.json")
    if batch_dir.name == "00_foundation_skeleton":
        stage_summaries = {
            "foundation_quality": read_json(batch_dir / "06_quality_audit" / "foundation_quality_summary.json"),
            "foundation_enrichment": read_json(batch_dir / "06_quality_audit" / "foundation_enrichment_summary.json"),
            "textbook_deep": read_json(batch_dir / "06_quality_audit" / "textbook_deep_extraction_summary.json"),
            "textbook_fullbook": read_json(batch_dir / "06_quality_audit" / "textbook_fullbook_backfill_summary.json"),
        }
    else:
        stage_summaries = {}

    entity_counts, relation_counts, disease_names = count_jsonl_dimensions(batch_dir)
    if not entity_counts and import_summary.get("node_entity_type_counts"):
        entity_counts = Counter(import_summary.get("node_entity_type_counts", {}))
    if not relation_counts and import_summary.get("relation_type_counts"):
        relation_counts = Counter(import_summary.get("relation_type_counts", {}))

    return {
        "batch_dir": str(batch_dir),
        "batch_name": batch_dir.name,
        "batch_id": batch_id,
        "specialty": specialty,
        "disease_category": DISEASE_CATEGORY_BY_BATCH.get(batch_id, scope_target),
        "scope_type": scope_type,
        "scope_target": scope_target,
        "created_time": created_time,
        "manifest": manifest_stats,
        "quality": quality,
        "evidence_summary": evidence_summary,
        "graph_summary": graph_summary,
        "import_summary": import_summary,
        "stage_summaries": stage_summaries,
        "entity_counts": dict(sorted(entity_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "disease_names": disease_names,
    }


def h(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def td(value: Any, cls: str = "") -> str:
    cls_attr = f' class="{cls}"' if cls else ""
    if isinstance(value, RawHTML):
        return f"<td{cls_attr}>{value}</td>"
    return f"<td{cls_attr}>{h(value)}</td>"


def th(value: Any, cls: str = "") -> str:
    cls_attr = f' class="{cls}"' if cls else ""
    return f"<th{cls_attr}>{h(value)}</th>"


def table(headers: list[str], rows: list[list[Any]], classes: str = "") -> str:
    cls_attr = f' class="{classes}"' if classes else ""
    head = "".join(th(header) for header in headers)
    body = "\n".join("<tr>" + "".join(td(cell, "num" if isinstance(cell, (int, float)) else "") for cell in row) + "</tr>" for row in rows)
    return f"<table{cls_attr}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def fmt_pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return ""


def generate_html(summary: dict[str, Any]) -> str:
    batches = summary["batches"]
    source = summary["source_inventory"]
    final_safety = summary["final_server_safety"]
    now = summary["generated_at"]

    source_rows = [
        ["指南/文献目录", source["guide"]["unique_material_count"], source["guide"]["file_count"], source["guide"]["duplicate_format_count"], source["guide"]["pdf_count"], source["guide"]["docx_count"], source["guide"]["supported_count"], source["guide"]["root"]],
        ["书籍教材目录", source["textbook"]["unique_material_count"], source["textbook"]["file_count"], source["textbook"]["duplicate_format_count"], source["textbook"]["pdf_count"], source["textbook"]["docx_count"], source["textbook"]["supported_count"], source["textbook"]["root"]],
    ]

    batch_rows = []
    for item in batches:
        manifest = item["manifest"]
        quality = item["quality"]
        evidence = item["evidence_summary"]
        import_summary = item["import_summary"]
        batch_rows.append(
            [
                item["specialty"],
                item["disease_category"],
                item["scope_target"],
                item["batch_id"],
                manifest["included_unique_material_count"],
                manifest["included_count"],
                manifest["included_textbook_count"],
                manifest["included_guideline_pdf_count"],
                evidence.get("document_with_evidence_count", ""),
                quality.get("node_count") or import_summary.get("input_node_count") or import_summary.get("database_kg_node_count", ""),
                quality.get("relation_count") or import_summary.get("input_relation_count") or import_summary.get("database_relation_count", ""),
                quality.get("disease_count") or item["entity_counts"].get("Disease", ""),
                quality.get("required_pathway_missing_count", ""),
                quality.get("treatment_plan_actionability_error_count", ""),
                quality.get("medication_class_without_specific_count", ""),
                quality.get("duplicate_type_name_count", ""),
                quality.get("duplicate_semantic_relation_count", ""),
            ]
        )

    category_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in batches:
        if item["batch_name"] == "00_foundation_skeleton":
            continue
        category_groups[item["disease_category"]].append(item)
    category_rows = []
    for category, items in sorted(category_groups.items()):
        disease_count = sum(int(item["quality"].get("disease_count") or item["entity_counts"].get("Disease", 0)) for item in items)
        coverages = [coverage_for_batch(item) for item in items]
        avg_rate = sum(c["rate"] for c in coverages) / len(coverages) if coverages else 0
        merged_items = []
        for idx, (label, _, _) in enumerate(COVERAGE_DIMENSIONS):
            merged_items.append((label, any(c["items"][idx][1] for c in coverages)))
        merged_coverage = {
            "items": merged_items,
            "covered_count": sum(1 for _, ok in merged_items if ok),
            "total_count": len(merged_items),
            "rate": sum(1 for _, ok in merged_items if ok) / len(merged_items) if merged_items else 0,
        }
        category_rows.append(
            [
                category,
                len(items),
                disease_count,
                f"{avg_rate * 100:.0f}%",
                dot_bar(merged_coverage),
            ]
        )

    coverage_rows = []
    for item in batches:
        coverage = coverage_for_batch(item)
        coverage_rows.append(
            [
                item["scope_target"],
                f"{coverage['covered_count']}/{coverage['total_count']}",
                f"{coverage['rate'] * 100:.0f}%",
                dot_bar(coverage),
                "、".join(label for label, ok in coverage["items"] if not ok),
            ]
        )

    dimension_headers = ["批次/范围"] + [label for _, label in ENTITY_DIMENSIONS]
    dimension_rows = []
    for item in batches:
        entity_counts = item["entity_counts"]
        dimension_rows.append([item["scope_target"]] + [entity_counts.get(key, 0) for key, _ in ENTITY_DIMENSIONS])

    relation_headers = ["批次/范围"] + [label for _, label in RELATION_DIMENSIONS]
    relation_rows = []
    for item in batches:
        relation_counts = item["relation_counts"]
        relation_rows.append([item["scope_target"]] + [relation_counts.get(key, 0) for key, _ in RELATION_DIMENSIONS])

    disease_rows = []
    for item in batches:
        names = item["disease_names"]
        disease_rows.append(
            [
                item["disease_category"],
                item["scope_target"],
                len(names),
                "、".join(names[:40]) + (" ..." if len(names) > 40 else ""),
            ]
        )

    foundation = next((item for item in batches if item["batch_name"] == "00_foundation_skeleton"), None)
    foundation_rows: list[list[Any]] = []
    if foundation:
        stages = foundation["stage_summaries"]
        for label, key in [
            ("初版目录骨架", "foundation_quality"),
            ("样板批次增强", "foundation_enrichment"),
            ("教材深层实体化", "textbook_deep"),
            ("全书跨章节回捞", "textbook_fullbook"),
        ]:
            data = stages.get(key, {})
            foundation_rows.append(
                [
                    label,
                    data.get("node_count", ""),
                    data.get("relation_count", ""),
                    data.get("disease_count", ""),
                    data.get("entity_type_counts", {}).get("Symptom", ""),
                    data.get("entity_type_counts", {}).get("Sign", ""),
                    data.get("entity_type_counts", {}).get("Exam", ""),
                    data.get("entity_type_counts", {}).get("Medication", ""),
                    data.get("entity_type_counts", {}).get("TreatmentPlan", ""),
                    data.get("diseases_with_symptom", ""),
                    data.get("diseases_with_sign", ""),
                    data.get("diseases_with_exam", ""),
                    data.get("diseases_with_treatment", ""),
                ]
            )

    cards = [
        ("资料总库", f"{source['guide']['unique_material_count'] + source['textbook']['unique_material_count']} 份唯一资料"),
        ("指南 PDF", f"{source['guide']['pdf_count']} 个文件"),
        ("书籍教材", f"{source['textbook']['unique_material_count']} 份唯一资料"),
        ("已解析批次", f"{len(batches)} 个"),
        ("服务器节点", final_safety.get("kg_node_count", "")),
        ("服务器关系", final_safety.get("kg_relation_count", "")),
        ("服务器安全门", final_safety.get("global_safety_gate_status", "")),
    ]
    card_html = "".join(f"<div class='card'><div class='card-title'>{h(title)}</div><div class='card-value'>{h(value)}</div></div>" for title, value in cards)

    css = """
    body { font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif; margin: 28px; color: #172033; background: #f7f9fc; }
    h1 { margin-bottom: 6px; }
    h2 { margin-top: 34px; border-left: 5px solid #2f6fed; padding-left: 10px; }
    .meta { color: #667085; margin-bottom: 20px; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 18px 0; }
    .card { background: white; border: 1px solid #e6eaf2; border-radius: 10px; padding: 14px; box-shadow: 0 1px 2px rgba(16, 24, 40, .04); }
    .card-title { color: #667085; font-size: 13px; }
    .card-value { font-size: 22px; font-weight: 700; margin-top: 6px; }
    table { border-collapse: collapse; width: 100%; background: white; margin: 12px 0 24px; font-size: 13px; }
    th, td { border: 1px solid #e3e8f0; padding: 8px 10px; vertical-align: top; }
    th { background: #eef4ff; color: #1d3b6d; position: sticky; top: 0; z-index: 1; }
    td.num { text-align: right; font-variant-numeric: tabular-nums; }
    .wide { display: block; overflow-x: auto; white-space: nowrap; }
    .note { background: #fff8e6; border: 1px solid #ffe2a8; border-radius: 8px; padding: 12px; }
    .ok { color: #067647; font-weight: 700; }
    .warn { color: #b54708; font-weight: 700; }
    .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }
    .dot.on { background: #2f6fed; box-shadow: 0 0 0 2px rgba(47,111,237,.12); }
    .dot.off { background: #d0d5dd; }
    details { background: white; border: 1px solid #e3e8f0; border-radius: 8px; padding: 10px 12px; margin: 10px 0; }
    summary { cursor: pointer; font-weight: 700; color: #1d3b6d; }
    code { background: #eef1f5; padding: 2px 5px; border-radius: 4px; }
    """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>AI自动化工具-文献指南解析-统计报告_{h(summary['date_version'])}</title>
  <style>{css}</style>
</head>
<body>
  <h1>AI自动化工具-文献指南解析-统计报告</h1>
  <div class="meta">生成时间：{h(now)} ｜ 日期版本：{h(summary['date_version'])} ｜ 工作目录：<code>{h(str(ROOT))}</code></div>

  <div class="cards">{card_html}</div>

  <div class="note">
    <b>结论：</b>截至本报告，心血管内科已完成基础骨架库、心肌病、冠心病、心力衰竭、房颤 AF 批次。
    服务器最终全局安全门为 <span class="ok">{h(final_safety.get('global_safety_gate_status', ''))}</span>；
    但部分专病仍存在 <code>knowledge_display</code> 或临床正式发布限制，不能等同于正式 CDSS 强推荐上线。
  </div>

  <h2>1. 资料总库统计</h2>
  {table(["资料类别", "唯一资料数", "原始文件数", "同名多格式重复文件数", "PDF文件", "DOCX文件", "支持格式文件", "路径"], source_rows)}

  <details open>
    <summary>书籍教材具体名称（同名 PDF/DOCX 只算一份）</summary>
    {table(["资料名称", "已有格式", "文件数"], [[m["name"], ", ".join(m["formats"]), m["path_count"]] for m in source["textbook"]["materials"]])}
  </details>

  <details>
    <summary>指南/文献具体名称（同名 PDF/DOCX 只算一份）</summary>
    {table(["资料名称", "已有格式", "文件数"], [[m["name"], ", ".join(m["formats"]), m["path_count"]] for m in source["guide"]["materials"]])}
  </details>

  <h2>2. 学科 / 疾病大类 / 疾病批次统计</h2>
  <div class="wide">{table(["学科", "疾病大类", "疾病/范围", "批次", "纳入唯一资料", "纳入原始文件", "书籍教材", "指南/共识PDF", "产生证据文档", "节点", "关系", "疾病数", "required缺口", "空壳治疗", "药物类别缺具体药物", "同名重复", "语义重复关系"], batch_rows)}</div>

  <h2>3. 疾病大类总览</h2>
  <div class="wide">{table(["疾病大类", "已解析专病/批次数", "疾病数", "平均维度覆盖率", "维度覆盖"], category_rows)}</div>

  <h2>4. 心血管内科骨架库阶段统计</h2>
  <div class="wide">{table(["阶段", "节点", "关系", "疾病数", "症状", "体征", "检查", "药物", "治疗方案", "有症状疾病", "有体征疾病", "有检查疾病", "有治疗疾病"], foundation_rows)}</div>

  <h2>5. 18维度覆盖率</h2>
  <div class="wide">{table(["范围", "覆盖维度", "覆盖率", "维度覆盖", "未覆盖维度"], coverage_rows)}</div>

  <h2>6. 专病/骨架图谱实体维度统计</h2>
  <div class="wide">{table(dimension_headers, dimension_rows)}</div>

  <h2>7. 专病/骨架图谱关系维度统计</h2>
  <div class="wide">{table(relation_headers, relation_rows)}</div>

  <h2>8. 疾病清单</h2>
  {table(["疾病大类", "范围", "疾病数", "疾病名称"], disease_rows)}

  <h2>9. 服务器最终安全体检（人话版）</h2>
  {table(["检查项", "数值", "人话结论"], readable_safety_rows(final_safety))}

  <h2>10. 服务器最终安全体检（原始指标）</h2>
  {table(["指标", "数值"], [[key, value] for key, value in final_safety.items()])}

  <h2>11. 这些数字从哪里来（人话版）</h2>
  {table(["统计内容", "读取文件", "说明"], [
    ["资料总数和具体名称", "指南来源目录、教材目录、source_documents_manifest.csv", "按资料名称去重；同一名称同时有 PDF/DOCX 只算一份，但保留格式说明。"],
    ["每个批次用了多少资料", "01_source_manifest/source_documents_manifest.csv", "included 表示本批次真正纳入解析的文件。"],
    ["多少文档真正产生证据", "04_evidence_and_extraction/guideline_evidence_summary.json", "document_with_evidence_count 表示解析后确实抽到证据段的文档数。"],
    ["节点、关系、required 缺口", "06_quality_audit/quality_gate_summary.json", "本地图谱质检结果，判断是否有结构性缺口和硬错误。"],
    ["实体维度和关系维度", "05_data_instance/nodes_final.jsonl / relations_final.jsonl", "逐行统计实体类型和关系类型。"],
    ["服务器最终状态", "最新 01_服务器全库硬闸门_summary.json", "导入服务器后重新检查，最终以服务器为准；优先取所有批次/全局目录中修改时间最新的安全体检文件。"],
  ])}
</body>
</html>
"""


def latest_final_server_safety() -> dict[str, Any]:
    candidates = sorted(COLLECTION_ROOT.glob("**/01_服务器全库硬闸门_summary.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return read_json(candidates[0]) if candidates else {}


def build_summary() -> dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_version = datetime.now().strftime("%Y%m%d")
    batches = [summarize_batch(path) for path in batch_dirs() if path.is_dir()]
    return {
        "generated_at": now,
        "date_version": date_version,
        "source_inventory": {
            "guide": count_source_root(GUIDE_ROOT),
            "textbook": count_source_root(TEXTBOOK_ROOT),
        },
        "batches": batches,
        "final_server_safety": latest_final_server_safety(),
    }


def main() -> None:
    summary = build_summary()
    html_text = generate_html(summary)
    output = ROOT / f"AI自动化工具-文献指南解析-统计报告_{summary['date_version']}.html"
    output.write_text(html_text, encoding="utf-8-sig")
    json_output = ROOT / f"AI自动化工具-文献指南解析-统计报告_{summary['date_version']}.json"
    json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
    print(json.dumps({"html": str(output), "json": str(json_output), "batch_count": len(summary["batches"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
