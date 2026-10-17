# -*- coding: utf-8 -*-
"""反包因子研究通用版测试。"""

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "脚本" / "反包因子研究_通用版.py"
SPEC = importlib.util.spec_from_file_location(
    "generic_reversal_research",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenericReversalResearchTests(unittest.TestCase):
    """验证信号日、T+1 和 T+2 的对齐。"""

    def sample_data(self) -> pd.DataFrame:
        dates = pd.to_datetime(
            [
                "2026-01-05",
                "2026-01-06",
                "2026-01-07",
                "2026-01-08",
                "2026-01-09",
            ]
        )
        return pd.DataFrame(
            {
                "time": dates,
                "code": ["000001.XSHE"] * len(dates),
                "open": [10.0, 10.2, 10.5, 10.8, 11.0],
                "close": [11.0, 10.1, 10.7, 11.1, 11.2],
                "high": [11.0, 10.5, 10.8, 11.2, 11.3],
                "low": [10.0, 9.9, 10.2, 10.6, 10.9],
                "volume": [1e8] * len(dates),
                "money": [
                    1.05e9,
                    1.01e9,
                    1.07e9,
                    1.11e9,
                    1.12e9,
                ],
                "pre_close": [10.0, 11.0, 10.1, 10.7, 11.1],
                "paused": [0] * len(dates),
                "是否涨停": [1, 0, 0, 0, 0],
                "成交额_亿": [10.5, 10.1, 10.7, 11.1, 11.2],
                "竞价涨幅": [1.0, -2.0, 1.0, 1.0, 1.0],
            }
        )

    def test_signal_alignment_and_costs(self) -> None:
        data = MODULE.清洗数据(self.sample_data())
        trades = MODULE.构建反包交易(data)
        result = MODULE.计算交易成本(
            trades,
            MODULE.研究参数(),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result.iloc[0]["买入日期"],
            pd.Timestamp("2026-01-07"),
        )
        self.assertEqual(
            result.iloc[0]["卖出日期"],
            pd.Timestamp("2026-01-08"),
        )
        self.assertGreater(result.iloc[0]["股数"], 0)

    def test_only_2026_signals_are_kept(self) -> None:
        trades = pd.DataFrame(
            [
                {"time": pd.Timestamp("2025-12-31")},
                {"time": pd.Timestamp("2026-01-05")},
            ]
        )

        result = MODULE.限定研究区间(trades)

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result.iloc[0]["time"],
            pd.Timestamp("2026-01-05"),
        )


if __name__ == "__main__":
    unittest.main()
