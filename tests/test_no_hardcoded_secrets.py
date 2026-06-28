import unittest
from pathlib import Path


class NoHardcodedSecretsTests(unittest.TestCase):
    def test_repository_text_files_do_not_contain_known_secrets(self):
        root = Path(__file__).resolve().parents[1]
        forbidden = {
            "zysoft" + "@" + "2024",
            "liu3348811" + ".0" + "@",
            "ghp" + "_",
            "github" + "_pat" + "_",
        }
        excluded_parts = {
            ".git",
            "__pycache__",
            "99_全局质量体检_global_quality_audit",
            "09_增量补丁_delta",
            "00_foundation_skeleton",
        }
        text_suffixes = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".csv", ".gitignore"}
        offenders: list[str] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in excluded_parts for part in path.parts):
                continue
            if path.suffix and path.suffix.lower() not in text_suffixes:
                continue
            if path.name == "test_no_hardcoded_secrets.py":
                continue
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                continue
            for secret in forbidden:
                if secret in text:
                    offenders.append(str(path.relative_to(root)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
