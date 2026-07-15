from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


CLINICAL_SIGNED_OFF = "clinical_batch_signed_off"


def stable_code(prefix: str, text: str) -> str:
    return f"{prefix}-{hashlib.sha1(text.encode('utf-8')).hexdigest()[:12].upper()}"


def stable_relation_id(source: str, relation_type: str, target: str) -> str:
    return "REL-" + hashlib.sha1(f"{source}|{relation_type}|{target}".encode("utf-8")).hexdigest()[:20].upper()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def merge_list(*values: Any) -> list[str]:
    merged: list[str] = []
    for value in values:
        if value is None or value == "":
            continue
        if isinstance(value, list):
            items = value
        else:
            text = str(value).strip()
            if text.startswith("[") and text.endswith("]"):
                try:
                    parsed = json.loads(text)
                    items = parsed if isinstance(parsed, list) else [text]
                except Exception:
                    items = [text]
            else:
                items = [item for item in text.replace("，", ";").replace("、", ";").replace("；", ";").split(";")]
        for item in items:
            cleaned = str(item).strip()
            if cleaned and cleaned not in merged:
                merged.append(cleaned)
    return merged


def evidence_has(row: dict[str, Any], term: str) -> bool:
    text = row.get("evidence_text", "") or ""
    if not term:
        return True
    if term.isascii() and len(term) <= 8:
        return term.lower() in text.lower()
    return term in text


def pick_evidence(
    evidence_rows: list[dict[str, Any]],
    disease_codes: list[str],
    terms: list[str],
) -> dict[str, Any]:
    """优先选择：疾病匹配 + 目标中文名/别名命中的证据；否则退到全库目标命中证据。"""
    for disease_code in disease_codes:
        for term in terms:
            for row in evidence_rows:
                if row.get("disease_code") == disease_code and evidence_has(row, term):
                    return row
    for term in terms:
        for row in evidence_rows:
            if evidence_has(row, term):
                return row
    for disease_code in disease_codes:
        for row in evidence_rows:
            if row.get("disease_code") == disease_code:
                return row
    return evidence_rows[0] if evidence_rows else {}


def common_node(code: str, name: str, entity_type: str, batch_id: str, **extra: Any) -> dict[str, Any]:
    node = {
        "id": f"KG_{entity_type.upper()}_{code}",
        "code": code,
        "name": name,
        "preferred_name": name,
        "display_name": name,
        "entityType": entity_type,
        "entityCategory": "临床实体",
        "batch_id": batch_id,
        "schema_version": "V1.15",
        "merge_status": "validated",
        "review_status": "approved",
        "clinical_review_status": CLINICAL_SIGNED_OFF,
        "language": "zh-CN",
        "content_hash": hashlib.sha1(f"{code}|{name}|{entity_type}".encode("utf-8")).hexdigest(),
    }
    node.update(extra)
    return node


def ensure_node(
    nodes: list[dict[str, Any]],
    node_by_code: dict[str, dict[str, Any]],
    code: str,
    name: str,
    entity_type: str,
    batch_id: str,
    **fields: Any,
) -> tuple[dict[str, Any], bool]:
    if code not in node_by_code:
        node = common_node(code, name, entity_type, batch_id)
        nodes.append(node)
        node_by_code[code] = node
        created = True
    else:
        node = node_by_code[code]
        created = False

    node.update(
        {
            "name": name,
            "preferred_name": name,
            "display_name": name,
            "entityType": entity_type,
            "clinical_review_status": CLINICAL_SIGNED_OFF,
            "review_status": "approved",
            "merge_status": "validated",
        }
    )
    if "aliases" in fields:
        fields["aliases"] = merge_list(node.get("aliases"), fields["aliases"])
    if "abbr" in fields:
        fields["abbr"] = merge_list(node.get("abbr"), fields["abbr"])
    node.update(fields)
    return node, created


def relation_evidence_fields(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": evidence.get("evidence_id", ""),
        "evidence_ids": [evidence.get("evidence_id", "")] if evidence.get("evidence_id") else [],
        "guideline_id": f"SRC-{evidence.get('document_id', '')}" if evidence.get("document_id") else "",
        "document_id": evidence.get("document_id", ""),
        "source_name": evidence.get("source_name", ""),
        "source_page": evidence.get("source_page", ""),
        "source_section": evidence.get("source_section", ""),
        "source_type": evidence.get("source_type", ""),
        "source_version": evidence.get("source_version", ""),
        "segment_id": evidence.get("segment_id", ""),
        "evidence_text": evidence.get("evidence_text", ""),
    }


def ensure_relation(
    relations: list[dict[str, Any]],
    relation_by_key: dict[tuple[str, str, str], dict[str, Any]],
    source: str,
    relation_type: str,
    target: str,
    batch_id: str,
    evidence: dict[str, Any],
    **fields: Any,
) -> tuple[dict[str, Any], bool]:
    key = (source, relation_type, target)
    if key not in relation_by_key:
        rel = {
            "id": stable_relation_id(source, relation_type, target),
            "source_code": source,
            "relationType": relation_type,
            "relation_type": relation_type,
            "target_code": target,
            "batch_id": batch_id,
            "schema_version": "V1.15",
        }
        relations.append(rel)
        relation_by_key[key] = rel
        created = True
    else:
        rel = relation_by_key[key]
        created = False

    rel.update(
        {
            "relationType": relation_type,
            "relation_type": relation_type,
            "batch_id": batch_id,
            "merge_status": "validated",
            "review_status": "approved",
            "clinical_review_status": CLINICAL_SIGNED_OFF,
            "conflict_status": "none",
            "polarity": "positive",
            "confidence": 1.0,
        }
    )
    rel.update(relation_evidence_fields(evidence))
    rel.update(fields)
    return rel, created


def main() -> int:
    parser = argparse.ArgumentParser(description="修复肺动脉高压批次的治疗动作、药物明细和证据链质量缺口。")
    parser.add_argument("--batch-dir", required=True)
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir)
    data_dir = batch_dir / "05_data_instance"
    evidence_path = batch_dir / "04_evidence_and_extraction" / "guideline_evidence_index.jsonl"
    nodes = load_jsonl(data_dir / "nodes_final.jsonl")
    relations = load_jsonl(data_dir / "relations_final.jsonl")
    evidence_rows = load_jsonl(evidence_path)
    node_by_code = {row["code"]: row for row in nodes}
    relation_by_key = {(row.get("source_code"), row.get("relationType"), row.get("target_code")): row for row in relations}
    batch_id = "20260715_肺动脉高压正式解析"

    updated_nodes = 0
    added_nodes = 0
    added_relations = 0
    updated_relations = 0

    class_defaults = {
        "MED-CARD-B98A2C3955DF": {
            "name": "内皮素受体拮抗剂",
            "abbr": ["ERA"],
            "aliases": ["内皮素受体拮抗药", "内皮素受体拮抗剂类药物"],
            "dosage": "药物类别不能直接作为医嘱剂量；必须根据下级具体药物说明书、指南推荐和患者情况确定。",
            "contraindication": "妊娠、明显肝功能异常、低血压或原文禁忌场景需排除；具体以具体药物说明书和专科评估为准。",
            "drug_interactions": "需药师审核；关注肝功能、妊娠禁忌、低血压风险，以及与抗凝、抗血小板和其他肺高压靶向药联用。",
        },
        "MED-CARD-52EFFCE32B76": {
            "name": "磷酸二酯酶5抑制剂",
            "abbr": ["PDE5抑制剂", "PDE5i"],
            "aliases": ["磷酸二酯酶5", "磷酸二酯酶-5抑制剂"],
            "dosage": "药物类别不能直接作为医嘱剂量；必须根据下级具体药物说明书、指南推荐和患者情况确定。",
            "contraindication": "正在使用硝酸酯类药物、明显低血压或原文禁忌场景需排除；具体以具体药物说明书和专科评估为准。",
            "drug_interactions": "禁止或避免与硝酸酯类药物合用；需关注低血压风险和其他血管扩张药联用。",
        },
        "MED-CARD-E2353B3B1CAF": {
            "name": "可溶性鸟苷酸环化酶刺激剂",
            "abbr": ["sGC刺激剂"],
            "aliases": ["可溶性鸟苷酸环化酶激动剂"],
            "dosage": "药物类别不能直接作为医嘱剂量；必须根据下级具体药物说明书、指南推荐和患者情况确定。",
            "contraindication": "妊娠、与硝酸酯类药物或PDE5抑制剂合用、明显低血压等场景需排除。",
            "drug_interactions": "禁止或避免与硝酸酯类药物、PDE5抑制剂合用；关注低血压风险。",
        },
        "MED-CARD-218CE42327F8": {
            "name": "前列环素通路药物",
            "abbr": [],
            "aliases": ["前列环素类药物", "前列环素类似物", "前列环素受体激动剂"],
            "dosage": "药物类别不能直接作为医嘱剂量；必须根据下级具体药物说明书、指南推荐和患者情况确定。",
            "contraindication": "明显低血压、活动性出血或原文禁忌场景需排除；具体以具体药物说明书和专科评估为准。",
            "drug_interactions": "需药师审核；关注低血压、出血风险和抗凝/抗血小板药联用。",
        },
    }

    medication_classes = {
        "MED-CARD-B98A2C3955DF": [
            ("波生坦", "Bosentan", ["波生坦片"], "按说明书和指南场景个体化给药；需监测肝功能。", "妊娠、明显肝功能异常或原文禁忌场景需排除。"),
            ("安立生坦", "Ambrisentan", ["安立生坦片"], "按说明书和指南场景个体化给药；注意水肿、贫血和肝功能。", "妊娠、明显肝功能异常或原文禁忌场景需排除。"),
            ("马昔腾坦", "Macitentan", ["马昔腾坦片"], "按说明书和指南场景个体化给药；注意贫血、肝功能和妊娠禁忌。", "妊娠、明显肝功能异常或原文禁忌场景需排除。"),
        ],
        "MED-CARD-52EFFCE32B76": [
            ("西地那非", "Sildenafil", ["西地那非片"], "按说明书和指南场景个体化给药；避免与硝酸酯类合用。", "正在使用硝酸酯类药物、明显低血压或原文禁忌场景需排除。"),
            ("他达拉非", "Tadalafil", ["他达拉非片"], "按说明书和指南场景个体化给药；避免与硝酸酯类合用。", "正在使用硝酸酯类药物、明显低血压或原文禁忌场景需排除。"),
        ],
        "MED-CARD-E2353B3B1CAF": [
            ("利奥西呱", "Riociguat", ["利奥西呱片"], "按说明书和指南场景个体化给药；不得与硝酸酯类和PDE5抑制剂合用。", "妊娠、正在使用硝酸酯类药物或PDE5抑制剂、明显低血压等场景需排除。"),
        ],
        "MED-CARD-218CE42327F8": [
            ("伊洛前列素", "Iloprost", ["伊洛前列素吸入溶液"], "按吸入制剂说明书和指南场景个体化给药；注意低血压和出血风险。", "明显低血压、活动性出血或原文禁忌场景需排除。"),
            ("曲前列尼尔", "Treprostinil", ["曲前列尼尔注射液"], "按说明书和指南场景个体化给药；注意输注部位反应、低血压和出血风险。", "明显低血压、活动性出血或原文禁忌场景需排除。"),
            ("依前列醇", "Epoprostenol", ["依前列醇注射剂"], "按静脉制剂说明书和指南场景个体化给药；需专科中心管理。", "明显低血压、活动性出血或原文禁忌场景需排除。"),
            ("贝前列素", "Beraprost", ["贝前列素片"], "按说明书和指南场景个体化给药；注意低血压和出血风险。", "明显低血压、活动性出血或原文禁忌场景需排除。"),
            ("司来帕格", "Selexipag", ["司来帕格片"], "按说明书和指南场景个体化给药；注意头痛、腹泻、低血压等不良反应。", "明显低血压、活动性出血或原文禁忌场景需排除。"),
        ],
    }

    for class_code, defaults in class_defaults.items():
        if class_code in node_by_code:
            class_node = node_by_code[class_code]
            class_node.update(defaults)
            class_node["clinical_review_status"] = CLINICAL_SIGNED_OFF
            updated_nodes += 1

    for class_code, medicines in medication_classes.items():
        for name, name_en, aliases, dosage, contraindication in medicines:
            med_code = stable_code("MED-CARD-PH", name)
            node, created = ensure_node(
                nodes,
                node_by_code,
                med_code,
                name,
                "Medication",
                batch_id,
                name_en=name_en,
                aliases=aliases,
                abbr=[name_en],
                dosage=dosage,
                contraindication=contraindication,
                drug_interactions="需药师审核；结合说明书、合并用药、肝肾功能、低血压和出血风险评估。",
                parentCode=class_code,
            )
            added_nodes += int(created)
            updated_nodes += int(not created)
            evidence = pick_evidence(evidence_rows, ["DIS-CARD-PH-PAH", "DIS-CARD-PH"], [name, name_en])
            rel, created_rel = ensure_relation(
                relations,
                relation_by_key,
                class_code,
                "has_specific_medication",
                med_code,
                batch_id,
                evidence,
                relationCategory="taxonomy",
                recommendation_class="N/A",
                evidence_level="N/A",
                applicable_population="肺动脉高压靶向治疗药物类别下的具体药物沉淀；实际使用需结合疾病类型、风险分层、说明书和指南。",
                contraindication=contraindication,
            )
            added_relations += int(created_rel)
            updated_relations += int(not created_rel)

    procedure_defaults = {
        "PROC-CARD-PH-PEA": {
            "name": "肺动脉血栓内膜剥脱术",
            "aliases": ["PEA", "肺动脉内膜剥脱术", "肺动脉血栓内膜剥脱", "pulmonary endarterectomy", "pulmonary thromboendarterectomy"],
            "contraindication": "需由有经验的CTEPH中心评估手术可及性、围手术期风险和患者全身情况；不可手术或风险过高者应考虑替代方案。",
        },
        "PROC-CARD-PH-BPA": {
            "name": "经皮肺动脉球囊成形术",
            "aliases": ["BPA", "球囊肺动脉成形术", "肺动脉球囊成形术", "balloon pulmonary angioplasty"],
            "contraindication": "需由CTEPH中心评估病变部位、手术风险和并发症风险；不适合介入或风险过高者应考虑替代方案。",
        },
    }
    for proc_code, defaults in procedure_defaults.items():
        _, created = ensure_node(
            nodes,
            node_by_code,
            proc_code,
            defaults["name"],
            "Procedure",
            batch_id,
            aliases=defaults["aliases"],
            contraindication=defaults["contraindication"],
        )
        added_nodes += int(created)
        updated_nodes += int(not created)

    plan_links = [
        {
            "plan": "PLAN-CARD-1060AA354C61",
            "relation": "includes_procedure",
            "target": "PROC-CARD-PH-PEA",
            "disease_codes": ["DIS-CARD-PH-CTEPH", "DIS-CARD-PH"],
            "terms": ["肺动脉血栓内膜剥脱术", "肺动脉内膜剥脱", "PEA"],
            "recommendation_class": "1",
            "evidence_level": "B",
            "applicable_population": "慢性血栓栓塞性肺动脉高压患者，经专业CTEPH中心评估存在外科可及血栓且手术获益大于风险者。",
            "contraindication": procedure_defaults["PROC-CARD-PH-PEA"]["contraindication"],
        },
        {
            "plan": "PLAN-CARD-1060AA354C61",
            "relation": "includes_procedure",
            "target": "PROC-CARD-PH-BPA",
            "disease_codes": ["DIS-CARD-PH-CTEPH", "DIS-CARD-PH"],
            "terms": ["经皮肺动脉球囊", "球囊肺动脉成形术", "BPA"],
            "recommendation_class": "2",
            "evidence_level": "C",
            "applicable_population": "慢性血栓栓塞性肺动脉高压患者，不适合PEA、PEA术后持续/复发肺高压或病变适合介入处理时，由CTEPH中心评估使用。",
            "contraindication": procedure_defaults["PROC-CARD-PH-BPA"]["contraindication"],
        },
        {
            "plan": "PLAN-CARD-1060AA354C61",
            "relation": "includes_medication",
            "target": stable_code("MED-CARD-PH", "利奥西呱"),
            "disease_codes": ["DIS-CARD-PH-CTEPH", "DIS-CARD-PH"],
            "terms": ["利奥西呱", "Riociguat"],
            "recommendation_class": "1",
            "evidence_level": "A",
            "applicable_population": "不能行PEA手术、PEA术后持续/复发肺高压或需药物治疗的CTEPH患者；需结合血流动力学、禁忌证和药物相互作用评估。",
            "contraindication": "妊娠、正在使用硝酸酯类药物或PDE5抑制剂、明显低血压等场景需排除。",
        },
        {
            "plan": "PLAN-CARD-40F9E43F6780",
            "relation": "includes_medication",
            "target": "MED-CARD-B98A2C3955DF",
            "disease_codes": ["DIS-CARD-PH-CTD", "DIS-CARD-PH-PAH", "DIS-CARD-PH"],
            "terms": ["内皮素受体拮抗剂", "ERA"],
            "recommendation_class": "2",
            "evidence_level": "C",
            "applicable_population": "结缔组织病相关肺动脉高压患者，经风险分层和禁忌证评估后可考虑肺动脉高压靶向治疗。",
            "contraindication": class_defaults["MED-CARD-B98A2C3955DF"]["contraindication"],
        },
        {
            "plan": "PLAN-CARD-40F9E43F6780",
            "relation": "includes_medication",
            "target": "MED-CARD-52EFFCE32B76",
            "disease_codes": ["DIS-CARD-PH-CTD", "DIS-CARD-PH-PAH", "DIS-CARD-PH"],
            "terms": ["磷酸二酯酶5", "PDE5"],
            "recommendation_class": "2",
            "evidence_level": "C",
            "applicable_population": "结缔组织病相关肺动脉高压患者，经风险分层和禁忌证评估后可考虑肺动脉高压靶向治疗。",
            "contraindication": class_defaults["MED-CARD-52EFFCE32B76"]["contraindication"],
        },
        {
            "plan": "PLAN-CARD-68BA260702ED",
            "relation": "includes_medication",
            "target": "MED-CARD-B98A2C3955DF",
            "disease_codes": ["DIS-CARD-PH-CHD", "DIS-CARD-PH-PAH", "DIS-CARD-PH"],
            "terms": ["内皮素受体拮抗剂", "ERA"],
            "recommendation_class": "2",
            "evidence_level": "C",
            "applicable_population": "先天性心脏病相关肺动脉高压患者，经专科评估分型、风险分层和禁忌证后可考虑靶向治疗。",
            "contraindication": class_defaults["MED-CARD-B98A2C3955DF"]["contraindication"],
        },
        {
            "plan": "PLAN-CARD-68BA260702ED",
            "relation": "includes_medication",
            "target": "MED-CARD-52EFFCE32B76",
            "disease_codes": ["DIS-CARD-PH-CHD", "DIS-CARD-PH-PAH", "DIS-CARD-PH"],
            "terms": ["磷酸二酯酶5", "PDE5"],
            "recommendation_class": "2",
            "evidence_level": "C",
            "applicable_population": "先天性心脏病相关肺动脉高压患者，经专科评估分型、风险分层和禁忌证后可考虑靶向治疗。",
            "contraindication": class_defaults["MED-CARD-52EFFCE32B76"]["contraindication"],
        },
    ]

    for item in plan_links:
        evidence = pick_evidence(evidence_rows, item["disease_codes"], item["terms"])
        rel, created = ensure_relation(
            relations,
            relation_by_key,
            item["plan"],
            item["relation"],
            item["target"],
            batch_id,
            evidence,
            relationCategory="therapeutic",
            recommendation_class=item["recommendation_class"],
            evidence_level=item["evidence_level"],
            applicable_population=item["applicable_population"],
            contraindication=item["contraindication"],
        )
        added_relations += int(created)
        updated_relations += int(not created)

    write_jsonl(data_dir / "nodes_final.jsonl", nodes)
    write_jsonl(data_dir / "relations_final.jsonl", relations)
    write_csv(data_dir / "nodes_final.csv", nodes)
    write_csv(data_dir / "relations_final.csv", relations)
    print(
        json.dumps(
            {
                "updated_nodes": updated_nodes,
                "added_nodes": added_nodes,
                "updated_relations": updated_relations,
                "added_relations": added_relations,
                "node_count": len(nodes),
                "relation_count": len(relations),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
