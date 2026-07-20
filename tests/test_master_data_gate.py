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
    def test_disease_directory_closure_checks_are_mandatory(self):
        gate = load_gate_module()
        metrics = {check.metric for check in gate.CHECKS}

        self.assertIn("noncanonical_disease_category_count", metrics)
        self.assertIn("disease_unreachable_from_canonical_category_count", metrics)
        self.assertIn("clinical_subtype_multiple_parent_count", metrics)
        self.assertIn("clinical_subtype_parent_role_error_count", metrics)

    def test_standard_procedure_checks_are_mandatory(self):
        gate = load_gate_module()
        metrics = {check.metric for check in gate.CHECKS}

        self.assertIn("standard_procedure_required_field_error_count", metrics)
        self.assertIn("standard_procedure_duplicate_uuid_count", metrics)
        self.assertIn("standard_procedure_duplicate_code_count", metrics)
        self.assertIn("orphan_standard_procedure_count", metrics)
        self.assertIn("formal_procedure_without_standard_count", metrics)

        required_fields = next(
            item for item in gate.CHECKS
            if item.metric == "standard_procedure_required_field_error_count"
        )
        self.assertIn("dictionary_validation_status", required_fields.count_query)
        self.assertIn("dictionary_validation_sources", required_fields.count_query)

    def test_treatment_plan_gate_recognizes_other_treatment_items(self):
        gate = load_gate_module()
        check = next(
            item for item in gate.CHECKS
            if item.metric == "treatment_plan_without_downstream_count"
        )

        self.assertIn("includes_treatment_item", check.count_query)
        self.assertIn("includes_treatment_item", check.detail_query)

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
