from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "证据层去重与性能收口.py"


def load_module():
    spec = importlib.util.spec_from_file_location("evidence_cleanup", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_source_name_normalizes_textbook_variants() -> None:
    module = load_module()
    assert module.normalize_source_name("《内科学（第10版）》.docx", "EVD-1") == "《内科学（第10版）》"
    assert module.normalize_source_name(
        ["《内科学（第10版）》.docx", "《内科学（第10版）》"], "EVD-2"
    ) == "《内科学（第10版）》"
    assert module.normalize_source_name("", "EVD-CARD-TEXTBOOK-ABC") == "《内科学（第10版）》"


def test_array_evidence_text_requires_explicit_repair_rule() -> None:
    module = load_module()
    values = ["错误片段", "感染性心内膜炎（infective endocarditis，IE）是感染性疾病。"]
    selected = module.normalize_evidence_text(
        "EVID-DEF-DIS-CARD-INFECTIVE-ENDOCARDITIS", values, None
    )
    assert selected.startswith("感染性心内膜炎")


def test_fingerprint_ignores_formatting_but_not_source_or_page() -> None:
    module = load_module()
    first = module.build_evidence_fingerprint("《指南》", "12", "同一  段\n原文")
    same = module.build_evidence_fingerprint("《指南》", 12, "同一 段 原文")
    other_page = module.build_evidence_fingerprint("《指南》", 13, "同一 段 原文")
    assert first == same
    assert first != other_page


def test_survivor_prefers_formal_reference_then_degree() -> None:
    module = load_module()
    nodes = [
        {"code": "EVD-A", "active": True, "formal_count": 0, "degree": 20},
        {"code": "EVD-B", "active": True, "formal_count": 1, "degree": 2},
        {"code": "EVD-C", "active": True, "formal_count": 0, "degree": 30},
    ]
    assert module.choose_survivor(nodes)["code"] == "EVD-B"


def test_reference_values_are_remapped_and_deduplicated() -> None:
    module = load_module()
    mapping = {"EVD-OLD-1": "EVD-KEEP", "EVD-OLD-2": "EVD-KEEP"}
    assert module.remap_reference_value("EVD-OLD-1", mapping) == "EVD-KEEP"
    assert module.remap_reference_value(
        ["EVD-OLD-1", "EVD-OLD-2", "EVD-X"], mapping
    ) == ["EVD-KEEP", "EVD-X"]


def test_relation_aggregation_maps_endpoints_and_preserves_conflicts() -> None:
    module = load_module()
    rows = [
        {
            "relationship_id": "r1",
            "start_id": "s1",
            "end_id": "dup",
            "relationship_type": "supported_by_evidence",
            "properties": {"evidence_id": "EVD-OLD", "source_page": "1"},
        },
        {
            "relationship_id": "r2",
            "start_id": "s1",
            "end_id": "keep",
            "relationship_type": "supported_by_evidence",
            "properties": {"evidence_id": "EVD-KEEP", "source_page": "2"},
        },
    ]
    aggregated = module.aggregate_relationships(
        rows,
        element_mapping={"dup": "keep"},
        code_mapping={"EVD-OLD": "EVD-KEEP"},
    )
    assert len(aggregated) == 1
    assert aggregated[0]["end_id"] == "keep"
    assert aggregated[0]["properties"]["evidence_id"] == "EVD-KEEP"
    assert "evidence_relation_conflicts_json" in aggregated[0]["properties"]


def test_provenance_properties_keep_old_codes() -> None:
    module = load_module()
    props = {
        "evidence_id": "EVD-OLD",
        "migrated_from_evidence_code": "EVD-OLD",
        "evidence_id_before_migration": "EVD-OLD",
    }
    remapped = module.remap_reference_properties(props, {"EVD-OLD": "EVD-KEEP"})
    assert remapped["evidence_id"] == "EVD-KEEP"
    assert remapped["migrated_from_evidence_code"] == "EVD-OLD"
    assert remapped["evidence_id_before_migration"] == "EVD-OLD"


def test_evidence_relationship_properties_are_compacted() -> None:
    module = load_module()
    props = {
        "evidence_id": "EVD-OLD",
        "target_code": "EVD-OLD",
        "evidence_text": "很长的原文不应重复保存在关系上",
        "provenance_records_json": "[很大的溯源记录]",
        "evidence_relation_conflicts_json": "[很大的冲突记录]",
        "evidence_level": "A",
        "formal_cdss_ready": True,
    }
    result = module.compact_evidence_relationship_properties(props, "EVD-KEEP")
    assert result["evidence_id"] == "EVD-KEEP"
    assert result["target_code"] == "EVD-KEEP"
    assert result["evidence_level"] == "A"
    assert result["formal_cdss_ready"] is True
    assert "evidence_text" not in result
    assert "provenance_records_json" not in result
    assert "evidence_relation_conflicts_json" not in result


def test_single_oversized_evidence_group_is_blocked() -> None:
    module = load_module()
    groups = [
        {
            "survivor_code": "EVD-KEEP",
            "survivor_element_id": "keep",
            "duplicate_element_ids": [f"dup-{index}" for index in range(251)],
        }
    ]
    with pytest.raises(ValueError, match="单组规模超过安全上限"):
        module.build_safe_group_batches(groups, {"keep": []})
