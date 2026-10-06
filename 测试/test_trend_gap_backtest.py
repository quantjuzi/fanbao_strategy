# -*- coding: utf-8 -*-
"""高开均线核心回测测试。"""

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "回测" / "trend_gap_backtest.py"
SPEC = importlib.util.spec_from_file_location(
    "trend_gap_backtest",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TrendGapBacktestTests(unittest.TestCase):
    """验证信号、交易对齐和成本计算。"""

    def sample_data(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "time": pd.to_datetime(
                    ["2026-01-05", "2026-01-06", "2026-01-07"]
                ),
                "code": ["000001.XSHE"] * 3,
                "open": [10.0, 10.5, 10.8],
                "close": [10.2, 10.7, 11.0],
                "volume": [100_000_000.0] * 3,
                "money": [
                    1_020_000_000.0,
                    1_070_000_000.0,
                    1_100_000_000.0,
                ],
                "paused": [0.0] * 3,
                "auction_return": [1.0, -1.0, -1.0],
                "turnover_billion": [10.0, 11.0, 12.0],
                "ma7": [10.0, 10.1, 10.2],
                "ma14": [9.5, 9.6, 9.7],
            }
        )

    def test_signal_and_trade_alignment(self) -> None:
        config = MODULE.BacktestConfig()
        data = MODULE.prepare_factors(self.sample_data(), config)
        trades = MODULE.build_trades(data)

        self.assertEqual(int(data["signal"].sum()), 1)
        self.assertEqual(len(trades), 1)
        self.assertEqual(
            trades.iloc[0]["buy_date"],
            pd.Timestamp("2026-01-06"),
        )
        self.assertEqual(
            trades.iloc[0]["sell_date"],
            pd.Timestamp("2026-01-07"),
        )

    def test_costs_are_applied(self) -> None:
        config = MODULE.BacktestConfig()
        data = MODULE.prepare_factors(self.sample_data(), config)
        trades = MODULE.build_trades(data)
        result = MODULE.apply_costs(trades, config)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["shares"], 1_900)
        self.assertGreater(result.iloc[0]["net_pnl"], 0)
        self.assertLess(
            result.iloc[0]["net_return"],
            (11.0 / 10.5 - 1) * 100,
        )


if __name__ == "__main__":
    unittest.main()
