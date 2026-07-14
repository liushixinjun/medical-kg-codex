from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "批次入库后复测_postcheck.py"


def load_module():
    spec = importlib.util.spec_from_file_location("batch_postimport_postcheck", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BatchPostimportPostcheckTests(unittest.TestCase):
    def test_build_postcheck_paths_uses_chinese_readable_dirs(self) -> None:
        module = load_module()
        paths = module.build_postcheck_paths(Path("批次目录"))

        self.assertEqual(paths.root, Path("批次目录") / "99_入库后复测")
        self.assertEqual(paths.master_data_gate_dir, Path("批次目录") / "99_入库后复测" / "01_主数据质量闸门")
        self.assertEqual(paths.summary_path.name, "00_入库后复测总览.json")
        self.assertEqual(paths.report_path.name, "00_入库后复测报告.md")

    def test_summarize_postcheck_passes_when_master_data_gate_passes(self) -> None:
        module = load_module()
        summary = module.summarize_postcheck(
            batch_id="BATCH-TEST",
            master_data_summary={
                "gate_status": "passed",
                "blocking_issue_count": 0,
                "counts": {
                    "same_disease_same_type_same_name_duplicate_count": 0,
                    "diagnosis_criteria_without_component_count": 0,
                },
            },
        )

        self.assertEqual(summary["batch_id"], "BATCH-TEST")
        self.assertEqual(summary["postcheck_status"], "passed")
        self.assertEqual(summary["blocking_issue_count"], 0)

    def test_summarize_postcheck_fails_when_master_data_gate_fails(self) -> None:
        module = load_module()
        summary = module.summarize_postcheck(
            batch_id="BATCH-TEST",
            master_data_summary={
                "gate_status": "failed",
                "blocking_issue_count": 2,
                "counts": {
                    "same_disease_same_type_same_name_duplicate_count": 1,
                    "diagnosis_criteria_without_component_count": 1,
                },
            },
        )

        self.assertEqual(summary["postcheck_status"], "failed")
        self.assertEqual(summary["blocking_issue_count"], 2)
        self.assertIn("主数据质量闸门", summary["blocking_gates"])


if __name__ == "__main__":
    unittest.main()
