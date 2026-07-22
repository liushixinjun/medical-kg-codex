from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_terminology_dictionaries.py"
SPEC = importlib.util.spec_from_file_location("validate_terminology_dictionaries", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_drug_class_member_cannot_also_be_alias(tmp_path: Path) -> None:
    path = tmp_path / "4_药物同义词表.yaml"
    path.write_text(
        """
- canonical: P2Y12受体抑制剂
  code: MED-CLASS
  aliases: [氯吡格雷]
  members: [氯吡格雷]
  same_as: []
  note: 测试
""".lstrip(),
        encoding="utf-8",
    )
    issues = MODULE.validate_file(path)
    assert any(item["issue"] == "drug_member_also_used_as_alias" for item in issues)


def test_drug_class_member_field_is_valid_when_separate_from_alias(tmp_path: Path) -> None:
    path = tmp_path / "4_药物同义词表.yaml"
    path.write_text(
        """
- canonical: P2Y12受体抑制剂
  code: MED-CLASS
  aliases: [P2Y12抑制剂]
  members: [氯吡格雷]
  same_as: []
  note: 测试
""".lstrip(),
        encoding="utf-8",
    )
    issues = MODULE.validate_file(path)
    assert not any(item["level"] == "blocking" for item in issues)
