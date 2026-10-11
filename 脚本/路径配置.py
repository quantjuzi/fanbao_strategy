# -*- coding: utf-8 -*-
"""项目内统一使用的路径配置。"""

from __future__ import annotations

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "数据"
RESULT_DIR = PROJECT_DIR / "结果"
INTERMEDIATE_DIR = RESULT_DIR / "中间输出"
DEFAULT_FACTOR_FILE = DATA_DIR / "聚宽因子_2026-01-01_2026-09-30.csv"


def ensure_parent(path: Path) -> Path:
    """确保输出文件所在目录存在，并返回原路径。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    return path
