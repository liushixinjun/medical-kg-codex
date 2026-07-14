from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "主数据质量闸门_master_data_gate.py"


def load_gate_module():
    spec = importlib.util.spec_from_file_location("master_data_gate", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MasterDataGateTests(unittest.TestCase):
    def test_summary_passes_when_all_counts_are_zero(self):
        gate = load_gate_module()
        counts = {check.metric: 0 for check in gate.CHECKS}

        summary = gate.summarize_counts(counts)

        self.assertEqual(summary["gate_status"], "passed")
        self.assertEqual(summary["blocking_issue_count"], 0)

    def test_summary_fails_when_any_metric_is_positive(self):
        gate = load_gate_module()
        counts = {check.metric: 0 for check in gate.CHECKS}
        counts["treatment_plan_without_downstream_count"] = 1

        summary = gate.summarize_counts(counts)

        self.assertEqual(summary["gate_status"], "failed")
        self.assertEqual(summary["blocking_issue_count"], 1)
        self.assertEqual(summary["blocking_items"][0]["metric"], "treatment_plan_without_downstream_count")


if __name__ == "__main__":
    unittest.main()
