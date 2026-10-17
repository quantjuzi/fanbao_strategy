# -*- coding: utf-8 -*-
"""公开的 2026 反包策略研究代码测试。"""

import importlib.util
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "脚本" / "反包策略研究_2026.py"
SPEC = importlib.util.spec_from_file_location(
    "reversal_strategy_research",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ReversalStrategyResearchTests(unittest.TestCase):
    """验证公开脚本不依赖 private 且能独立计算。"""

    def test_markdown_output_has_no_optional_dependency(self) -> None:
        table = MODULE.转Markdown(
            pd.DataFrame(
                [
                    {"分组": "A", "交易数": 2},
                    {"分组": "B", "交易数": 1},
                ]
            )
        )

        self.assertIn("| 分组 | 交易数 |", table)
        self.assertIn("| A | 2 |", table)

    def test_metrics_and_optional_name_map(self) -> None:
        calendar = pd.Series(
            pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-05",
                    "2026-01-06",
                    "2026-01-07",
                ]
            )
        )
        trades = pd.DataFrame(
            [
                {
                    "买入日期": pd.Timestamp("2026-01-02"),
                    "卖出日期": pd.Timestamp("2026-01-05"),
                    "买入成交价": 10.0,
                    "卖出成交价": 10.1,
                    "买入金额": 20_000.0,
                    "净收益率": 1.0,
                    "净盈亏金额": 200.0,
                },
                {
                    "买入日期": pd.Timestamp("2026-01-05"),
                    "卖出日期": pd.Timestamp("2026-01-06"),
                    "买入成交价": 10.0,
                    "卖出成交价": 9.9,
                    "买入金额": 20_000.0,
                    "净收益率": -1.0,
                    "净盈亏金额": -200.0,
                },
            ]
        )

        metrics = MODULE.计算指标(trades, calendar)

        self.assertEqual(metrics["交易数"], 2)
        self.assertEqual(metrics["净胜率"], 50.0)
        self.assertEqual(metrics["最高资金占用"], 40_000.0)
        self.assertEqual(MODULE.读取名称(None), {})


if __name__ == "__main__":
    unittest.main()
