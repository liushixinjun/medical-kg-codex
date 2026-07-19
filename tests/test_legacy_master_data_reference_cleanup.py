from __future__ import annotations

from 公共执行层_kg_pipeline.历史主数据引用收口 import (
    build_neutral_evidence_title,
    merge_property_values,
    neo4j_property_safe,
    parse_bolt_connection,
    select_primary_code,
)


def test_select_primary_code_prefers_explicit_replacement() -> None:
    codes = ["PROC-CARD-TEXT-53ECAA23AE", "PROC-CARD-B8BE09194D42"]
    assert (
        select_primary_code("Procedure", "经导管主动脉瓣置换术", codes, codes[0])
        == "PROC-CARD-TEXT-53ECAA23AE"
    )


def test_select_primary_code_prefers_stable_definition_and_evidence_codes() -> None:
    assert select_primary_code(
        "Definition",
        "心脏瓣膜病定义",
        ["CARD-SKELETON-FULL-20260709-DEFINITION-X", "DEF-DIS-CARD-VHD"],
        None,
    ) == "DEF-DIS-CARD-VHD"
    assert select_primary_code(
        "Evidence",
        "心脏瓣膜病-definition-教材证据",
        ["EVD-CARD-FOUND-00367", "EVID-DEF-DIS-CARD-VHD"],
        None,
    ) == "EVID-DEF-DIS-CARD-VHD"


def test_select_primary_code_prefers_reusable_indicator_code() -> None:
    assert select_primary_code(
        "ExamIndicator",
        "ST段抬高",
        [
            "IND-CARD-340F2703D39C",
            "IND-EXAM-CARD-A80B855C8C77-ST段抬高",
            "IND-EXAM-ECG-ST段抬高",
        ],
        None,
    ) == "IND-EXAM-ECG-ST段抬高"


def test_merge_property_values_unions_lists_without_losing_scalar_conflicts() -> None:
    merged, conflicts = merge_property_values(
        {
            "evidence_ids": ["E1"],
            "source_name": "指南A",
            "confidence": 0.9,
        },
        {
            "evidence_ids": ["E2", "E1"],
            "source_name": "指南B",
            "confidence": 0.8,
        },
    )
    assert merged["evidence_ids"] == ["E1", "E2"]
    assert merged["source_name"] == "指南A"
    assert merged["confidence"] == 0.9
    assert conflicts["source_name"] == ["指南A", "指南B"]
    assert conflicts["confidence"] == [0.9, 0.8]


def test_build_neutral_evidence_title_does_not_reuse_extraction_slot_name() -> None:
    assert build_neutral_evidence_title("《内科学（第10版）》.docx", None) == "《内科学（第10版）》.docx 原文证据"
    assert build_neutral_evidence_title("ESC指南.pdf", 12) == "ESC指南.pdf 第12页原文证据"


def test_parse_bolt_connection_uses_bolt_instead_of_http(tmp_path) -> None:
    connection_file = tmp_path / "连接.txt"
    connection_file.write_text(
        "Web界面 http://192.168.3.27:7474\nBolt连接 bolt://192.168.3.27:7687\n用户名：neo4j\n密码：secret",
        encoding="utf-8",
    )
    assert parse_bolt_connection(connection_file) == {
        "uri": "bolt://192.168.3.27:7687",
        "username": "neo4j",
        "password": "secret",
    }


def test_neo4j_property_safe_preserves_supported_values_and_serializes_nested_values() -> None:
    assert neo4j_property_safe(["E1", "E2", None]) == ["E1", "E2"]
    assert neo4j_property_safe([1, 2.5]) == [1.0, 2.5]
    assert neo4j_property_safe(["第1页", 2]) == '["第1页", 2]'
    assert neo4j_property_safe({"来源": "指南", "页码": 12}) == '{"来源": "指南", "页码": 12}'
