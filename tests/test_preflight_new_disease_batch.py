import tempfile
import unittest
from pathlib import Path

from scripts.preflight_new_disease_batch import build_preflight_report


class PreflightNewDiseaseBatchTests(unittest.TestCase):
    def test_preflight_passes_with_required_inputs_and_existing_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "指南"
            textbook = root / "教材"
            output = root / "输出"
            source.mkdir()
            textbook.mkdir()
            output.mkdir()

            report = build_preflight_report(
                specialty="心血管内科",
                scope_type="疾病大类",
                scope_target="冠心病",
                source_roots=[source],
                textbook_roots=[textbook],
                output_root=output,
            )

            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["missing_required_fields"], [])

    def test_preflight_fails_when_specialty_or_source_path_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "输出"
            output.mkdir()

            report = build_preflight_report(
                specialty="",
                scope_type="疾病大类",
                scope_target="冠心病",
                source_roots=[root / "不存在"],
                textbook_roots=[],
                output_root=output,
            )

            self.assertEqual(report["status"], "fail")
            self.assertIn("specialty", report["missing_required_fields"])
            self.assertIn(str(root / "不存在"), report["missing_paths"])


if __name__ == "__main__":
    unittest.main()
