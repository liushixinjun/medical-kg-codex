import unittest

from scripts.global_safety_check import summarize_gate


class GlobalSafetyCheckTests(unittest.TestCase):
    def test_summary_marks_clean_gate_as_passed(self):
        summary = summarize_gate(
            {
                "non_kgnode_node_count": 0,
                "relation_touching_non_kgnode_count": 0,
                "technical_display_name_error_count": 0,
                "treatment_plan_actionability_error_count": 0,
                "medication_class_without_specific_count": 0,
                "duplicate_type_name_count": 0,
                "duplicate_semantic_relation_count": 0,
                "semantic_shell_relation_count": 0,
            }
        )

        self.assertEqual(summary["global_safety_gate_status"], "passed")
        self.assertEqual(summary["blocking_issue_count"], 0)

    def test_summary_marks_any_blocking_gate_as_failed(self):
        summary = summarize_gate(
            {
                "non_kgnode_node_count": 1,
                "relation_touching_non_kgnode_count": 0,
                "technical_display_name_error_count": 0,
                "treatment_plan_actionability_error_count": 0,
                "medication_class_without_specific_count": 0,
                "duplicate_type_name_count": 0,
                "duplicate_semantic_relation_count": 0,
                "semantic_shell_relation_count": 0,
            }
        )

        self.assertEqual(summary["global_safety_gate_status"], "failed")
        self.assertEqual(summary["blocking_issue_count"], 1)
        self.assertEqual(summary["blocking_items"][0]["metric"], "non_kgnode_node_count")


if __name__ == "__main__":
    unittest.main()
