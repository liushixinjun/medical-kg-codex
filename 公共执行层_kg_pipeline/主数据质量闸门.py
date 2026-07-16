from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("主数据质量闸门_master_data_gate.py")), run_name="__main__")
