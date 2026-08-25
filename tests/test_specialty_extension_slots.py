import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = r"D:\Program Files Ai\python-venvs\medical-kg\Scripts\python.exe"
SCRIPT = ROOT / "公共执行层_kg_pipeline" / "专病扩展槽位审计.py"
CONFIG = ROOT / "公共执行层_kg_pipeline" / "专病扩展槽位配置.yaml"


def run_audit():
    result = subprocess.run(
        [PYTHON, str(SCRIPT), "--config", str(CONFIG)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result, json.loads(result.stdout)


def test_specialty_extension_slot_config_passes_audit():
    result, data = run_audit()
    assert result.returncode == 0, result.stdout + result.stderr
    assert data["status"] == "pass"
    assert data["slot_count"] >= 7
    assert data["errors"] == []


def test_specialty_extension_slots_cover_p7_priority_categories():
    _, data = run_audit()
    expected = {
        "心肌病",
        "冠心病",
        "心力衰竭",
        "心律失常",
        "高血压",
        "瓣膜病",
        "肺动脉高压",
        "起搏治疗相关疾病",
    }
    assert expected.issubset(set(data["categories"]))


def test_specialty_extension_slots_keep_cdss_boundary_visible():
    text = CONFIG.read_text(encoding="utf-8")
    assert "不替代标准字典" in text
    assert "正式CDSS推荐" in text
    assert "没有教材、指南、共识或权威网页原文依据，不生成扩展实体" in text
