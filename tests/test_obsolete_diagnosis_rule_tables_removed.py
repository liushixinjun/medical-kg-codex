from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TABLES = {
    "K_DIAGNOSIS_RULE",
    "K_DIAGNOSIS_RULE_ITEM",
    "K_DIAGNOSIS_RULE_VERSION",
    "K_DIAGNOSIS_RULE_LOG",
}


def test_oracle_dictionary_ddl_no_longer_creates_obsolete_diagnosis_rule_tables() -> None:
    source = (ROOT / "公共执行层_kg_pipeline" / "Oracle标准字典治理V2.py").read_text(encoding="utf-8")
    for table in FORBIDDEN_TABLES:
        assert f'"{table}":' not in source
        assert f"CREATE TABLE {table}" not in source


def test_standard_dictionary_pipeline_no_longer_writes_obsolete_diagnosis_rule_tables() -> None:
    source = (ROOT / "公共执行层_kg_pipeline" / "标准字典融合与诊断推理V2.py").read_text(encoding="utf-8")
    for table in FORBIDDEN_TABLES:
        assert table not in source


def test_governing_documents_no_longer_define_obsolete_diagnosis_rule_tables() -> None:
    documents = [
        ROOT / "AI自动化工具-文献指南解析.md",
        ROOT / "专科知识图谱Schema标准.md",
        ROOT / "专科知识图谱标准字典与诊断推理执行方案.md",
    ]
    for document in documents:
        text = document.read_text(encoding="utf-8")
        for table in FORBIDDEN_TABLES:
            assert table not in text, f"{document.name} 仍把 {table} 作为正式设计"
