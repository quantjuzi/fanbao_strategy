# -*- coding: utf-8 -*-
"""全年标准因子表的滚动均线测试。"""

import importlib.util
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "脚本" / "生成全年因子数据.py"
SPEC = importlib.util.spec_from_file_location(
    "factor_data_generator",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FactorDataGeneratorTests(unittest.TestCase):
    """验证研究期前历史会参与滚动均线计算。"""

    def test_rolling_uses_pre_period_history(self) -> None:
        dates = pd.bdate_range("2025-12-01", "2026-01-15")
        data = pd.DataFrame(
            {
                "date": dates,
                "code": ["000001.XSHE"] * len(dates),
                "open": [1.0] * len(dates),
                "close": [1.0] * len(dates),
                "high": [1.0] * len(dates),
                "low": [1.0] * len(dates),
                "volume": [1.0] * len(dates),
                "money": [1.0] * len(dates),
                "pre_close": [1.0] * len(dates),
                "high_limit": [1.1] * len(dates),
                "low_limit": [0.9] * len(dates),
                "paused": [0] * len(dates),
                "is_limit_up": [0] * len(dates),
                "avg": [1.0] * len(dates),
            }
        )

        result = MODULE.生成标准因子(data)
        january_fifth = result.loc[
            result["time"].eq(pd.Timestamp("2026-01-05")),
            "M14",
        ].iloc[0]

        self.assertEqual(january_fifth, 1.0)


if __name__ == "__main__":
    unittest.main()
