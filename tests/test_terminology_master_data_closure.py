from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "全库术语与标准主数据收口.py"
SPEC = importlib.util.spec_from_file_location("terminology_master_data_closure", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def node(element_id: str, code: str, name: str, entity_type: str, aliases=None) -> dict:
    return {
        "element_id": element_id,
        "labels": ["KGNode", entity_type],
        "properties": {
            "code": code,
            "name": name,
            "entityType": entity_type,
            "aliases": aliases or [],
        },
    }


def audit(
    code: str,
    name: str,
    action: str,
    normalized: str,
    resolved_table: str = "",
    *,
    source: str = "",
    proposed_value: str = "",
    entity_type: str = "",
) -> dict:
    return {
        "kg_node_code": code,
        "kg_node_name": name,
        "recommended_action": action,
        "normalized_name": normalized,
        "resolved_target_table": resolved_table,
        "term_relation": "alias_of" if "别名" in action else "",
        "clinical_qualifiers": "",
        "source": source,
        "proposed_value": proposed_value,
        "entity_type": entity_type,
    }


def test_alias_rename_merges_into_existing_canonical_node() -> None:
    nodes = [
        node("n1", "MED-OLD", "达比加群", "Medication"),
        node("n2", "MED-NEW", "达比加群酯", "Medication"),
    ]
    rows = [audit("MED-OLD", "达比加群", "保留为别名并匹配规范制剂", "达比加群酯")]
    plan = MODULE.build_plan(nodes, rows)
    assert len(plan["merge_nodes"]) == 1
    assert plan["merge_nodes"][0]["duplicate_code"] == "MED-OLD"
    assert plan["merge_nodes"][0]["survivor_code"] == "MED-NEW"
    assert "达比加群" in plan["merge_nodes"][0]["aliases"]


def test_alias_rename_updates_node_when_canonical_node_does_not_exist() -> None:
    nodes = [node("n1", "MED-OLD", "肠溶阿司匹林", "Medication")]
    rows = [audit("MED-OLD", "肠溶阿司匹林", "保留为别名并匹配规范制剂", "阿司匹林肠溶片")]
    plan = MODULE.build_plan(nodes, rows)
    assert plan["rename_nodes"][0]["new_name"] == "阿司匹林肠溶片"
    assert plan["rename_nodes"][0]["aliases"] == ["肠溶阿司匹林"]


def test_lab_item_is_retyped_or_merged_with_existing_subitem() -> None:
    nodes = [
        node("n1", "LAB-OLD", "白细胞计数", "LabItem"),
        node("n2", "LAB-NEW", "白细胞计数", "LabSubitem"),
        node("n3", "LAB-CRP", "C反应蛋白", "LabItem"),
    ]
    rows = [
        audit("LAB-OLD", "白细胞计数", "转为检验细项", "白细胞计数", "K_LAB_SUBITEM_DICT"),
        audit("LAB-CRP", "C反应蛋白", "转为检验细项", "C反应蛋白", "K_LAB_SUBITEM_DICT"),
    ]
    plan = MODULE.build_plan(nodes, rows)
    assert plan["merge_nodes"][0]["survivor_code"] == "LAB-NEW"
    assert plan["retype_nodes"][0]["new_entity_type"] == "LabSubitem"


def test_dictionary_ineligible_knowledge_is_kept_but_blocked_from_order_master_data() -> None:
    nodes = [node("n1", "TRT-1", "最佳药物治疗", "TreatmentItem")]
    rows = [audit("TRT-1", "最佳药物治疗", "保留为治疗方案知识", "最佳药物治疗")]
    plan = MODULE.build_plan(nodes, rows)
    update = plan["metadata_updates"][0]
    assert update["dictionary_eligible"] is False
    assert update["knowledge_role"] == "treatment_strategy"


def test_polluted_or_composite_node_is_blocked_not_silently_deleted() -> None:
    nodes = [node("n1", "SIGN-1", "三尖瓣反流体征", "Sign")]
    rows = [audit("SIGN-1", "三尖瓣反流体征", "退回并拆分为原子项", "三尖瓣反流体征")]
    plan = MODULE.build_plan(nodes, rows)
    assert not plan["physical_delete_nodes"]
    assert plan["cleanup_candidates"][0]["active_for_cdss"] is False


def test_unmatched_graph_code_blocks_apply_gate() -> None:
    plan = MODULE.build_plan([], [audit("MISSING", "胸痛", "保留为别名并匹配规范制剂", "胸痛")])
    gate = MODULE.evaluate_gate(plan)
    assert gate["passed"] is False
    assert gate["blocking"]["unmatched_node_count"] == 1


def test_local_yaml_term_mapping_updates_existing_canonical_node_without_old_graph_node() -> None:
    nodes = [node("n1", "SYM-DYSPNEA", "呼吸困难", "Symptom", aliases=["气促"])]
    rows = [
        audit(
            "SYM-OLD-MISSING",
            "心力衰竭相关症状",
            "保留为别名映射",
            "呼吸困难",
            "K_SYMPTOM_DICT",
            source=r"E:\术语字典\2_症状同义词表.yaml",
            proposed_value='{"aliases":["气短","dyspnea"]}',
            entity_type="Symptom",
        )
    ]
    plan = MODULE.build_plan(nodes, rows)
    assert plan["unmatched_nodes"] == []
    assert plan["term_mapping_updates"] == [
        {
            "element_id": "n1",
            "code": "SYM-DYSPNEA",
            "id": None,
            "name": "呼吸困难",
            "entity_type": "Symptom",
            "aliases": ["气促", "气短", "dyspnea"],
            "source_term": "心力衰竭相关症状",
            "source_code": "SYM-OLD-MISSING",
            "reason": "保留为别名映射",
        }
    ]


def test_redundant_cleanup_row_for_same_missing_local_term_code_is_non_blocking() -> None:
    nodes = [node("n1", "SIGN-BRADY", "心动过缓", "Sign")]
    rows = [
        audit("SIGN-OLD", "心动过缓或房室分离表现", "退回并重分类", "心动过缓或房室分离表现"),
        audit(
            "SIGN-OLD",
            "心动过缓或房室分离表现",
            "保留为别名映射",
            "心动过缓",
            "K_CLINICAL_SIGN_DICT",
            source=r"E:\术语字典\3_体征同义词表.yaml",
            proposed_value='{"aliases":["心率缓慢"]}',
            entity_type="Sign",
        ),
    ]
    plan = MODULE.build_plan(nodes, rows)
    assert plan["unmatched_nodes"] == []
    assert len(plan["stale_audit_rows"]) == 1
    assert len(plan["term_mapping_updates"]) == 1
    assert MODULE.evaluate_gate(plan)["passed"] is True


def test_equally_qualified_duplicate_canonical_targets_block_automatic_merge() -> None:
    nodes = [
        node("n1", "MED-OLD", "达比加群", "Medication"),
        node("n2", "MED-CANON-A", "达比加群酯", "Medication"),
        node("n3", "MED-CANON-B", "达比加群酯", "Medication"),
    ]
    rows = [audit("MED-OLD", "达比加群", "保留为别名并匹配规范制剂", "达比加群酯")]
    plan = MODULE.build_plan(nodes, rows)
    assert plan["merge_nodes"] == []
    assert len(plan["conflicting_canonical_targets"]) == 1
    assert MODULE.evaluate_gate(plan)["passed"] is False


def test_equally_qualified_retype_targets_block_automatic_merge() -> None:
    nodes = [
        node("n1", "LAB-OLD", "白细胞计数", "LabItem"),
        node("n2", "LAB-CANON-A", "白细胞计数", "LabSubitem"),
        node("n3", "LAB-CANON-B", "白细胞计数", "LabSubitem"),
    ]
    rows = [audit("LAB-OLD", "白细胞计数", "转为检验细项", "白细胞计数", "K_LAB_SUBITEM_DICT")]
    plan = MODULE.build_plan(nodes, rows)
    assert plan["merge_nodes"] == []
    assert len(plan["conflicting_canonical_targets"]) == 1


def test_bnp_synonyms_merge_under_chinese_canonical_name_without_nt_probnp_alias() -> None:
    nodes = [
        node("n1", "LAB-BNP", "BNP", "LabSubitem", aliases=["NT-proBNP"]),
        node("n2", "LAB-BNP-CN1", "B型利钠肽", "LabItem"),
        node("n3", "LAB-BNP-CN2", "B型钠尿肽", "LabItem", aliases=["脑钠肽", "NT-proBNP"]),
    ]
    rows = [
        audit("LAB-BNP-CN1", "B型利钠肽", "转为检验细项", "B型利钠肽", "K_LAB_SUBITEM_DICT"),
        audit("LAB-BNP-CN2", "B型钠尿肽", "转为检验细项", "B型钠尿肽", "K_LAB_SUBITEM_DICT"),
    ]
    plan = MODULE.build_plan(nodes, rows)
    assert plan["rename_nodes"][0]["code"] == "LAB-BNP"
    assert plan["rename_nodes"][0]["new_name"] == "B型利钠肽"
    assert {item["duplicate_code"] for item in plan["merge_nodes"]} == {"LAB-BNP-CN1", "LAB-BNP-CN2"}
    for item in plan["merge_nodes"]:
        assert "BNP" in item["aliases"]
        assert "B型钠尿肽" in item["aliases"]
        assert "NT-proBNP" not in item["aliases"]


def test_nt_probnp_synonyms_merge_into_existing_chinese_canonical_node() -> None:
    nodes = [
        node("n1", "LAB-NT-CN", "N末端B型利钠肽原", "LabSubitem", aliases=["NT-proBNP"]),
        node("n2", "LAB-NT-ABBR", "NT-proBNP", "LabSubitem"),
        node("n3", "LAB-NT-OLD", "N末端B型钠尿肽前体", "LabItem"),
    ]
    rows = [audit("LAB-NT-OLD", "N末端B型钠尿肽前体", "转为检验细项", "N末端B型钠尿肽前体")]
    plan = MODULE.build_plan(nodes, rows)
    assert plan["rename_nodes"] == []
    assert {item["duplicate_code"] for item in plan["merge_nodes"]} == {"LAB-NT-ABBR", "LAB-NT-OLD"}
    assert {item["survivor_code"] for item in plan["merge_nodes"]} == {"LAB-NT-CN"}


def test_merge_aliases_is_unique_and_excludes_canonical_name() -> None:
    assert MODULE.merge_aliases(["PCI", "经皮冠脉介入"], ["PCI", "旧名"], exclude="旧名") == [
        "PCI",
        "经皮冠脉介入",
    ]


def test_relation_migration_gate_accepts_a_lossless_plan() -> None:
    plan = MODULE.build_plan([], [])
    relation_plan = {
        "create_relationships": [
            {
                "relationship_type": "has_symptom",
                "source": {"code": "DIS-1"},
                "target": {"code": "SYM-1"},
                "properties": {},
            }
        ],
        "delete_relationship_ids": ["rel-1", "rel-2"],
        "deduplicated_relationship_count": 1,
    }
    gate = MODULE.evaluate_gate(plan, relation_plan)
    assert gate["passed"] is True
    assert gate["blocking"]["relationship_preservation_error_count"] == 0
    assert gate["blocking"]["relationship_self_loop_count"] == 0
    assert gate["blocking"]["invalid_relationship_endpoint_count"] == 0
    assert gate["blocking"]["duplicate_create_relationship_count"] == 0


def test_relation_migration_gate_blocks_self_loop_and_loss() -> None:
    plan = MODULE.build_plan([], [])
    relation_plan = {
        "create_relationships": [
            {
                "relationship_type": "has_symptom",
                "source": {"code": "DIS-1"},
                "target": {"code": "DIS-1"},
                "properties": {},
            },
            {
                "relationship_type": "has_symptom",
                "source": {},
                "target": {"code": "SYM-1"},
                "properties": {},
            },
        ],
        "delete_relationship_ids": ["rel-1"],
        "deduplicated_relationship_count": 0,
    }
    gate = MODULE.evaluate_gate(plan, relation_plan)
    assert gate["passed"] is False
    assert gate["blocking"]["relationship_preservation_error_count"] == 1
    assert gate["blocking"]["relationship_self_loop_count"] == 1
    assert gate["blocking"]["invalid_relationship_endpoint_count"] == 1


def test_term_dictionary_aliases_are_preserved_when_same_survivor_also_receives_a_merge() -> None:
    nodes = [
        node("n1", "SYM-DYSPNEA", "呼吸困难", "Symptom", aliases=["气促"]),
        node("n2", "SYM-REST-DYSPNEA", "静息性呼吸困难", "Symptom"),
    ]
    rows = [
        audit(
            "SYM-OLD-MISSING",
            "心力衰竭相关症状",
            "保留为别名映射",
            "呼吸困难",
            "K_SYMPTOM_DICT",
            source=r"E:\术语字典\2_症状同义词表.yaml",
            proposed_value='{"aliases":["气短","dyspnea"]}',
            entity_type="Symptom",
        ),
        audit(
            "SYM-REST-DYSPNEA",
            "静息性呼吸困难",
            "归一症状主名并保留情境",
            "呼吸困难",
        ),
    ]
    plan = MODULE.build_plan(nodes, rows)
    merge = plan["merge_nodes"][0]
    assert merge["survivor_code"] == "SYM-DYSPNEA"
    assert "气短" in merge["aliases"]
    assert "dyspnea" in merge["aliases"]
