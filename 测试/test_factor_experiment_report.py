# -*- coding: utf-8 -*-
"""因子实验汇总脚本的测试。"""

import importlib.util
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "脚本" / "build_factor_experiment_report.py"
SPEC = importlib.util.spec_from_file_location(
    "factor_experiment_report",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FactorExperimentReportTests(unittest.TestCase):
    """验证基准加权和输出结构。"""

    def test_baseline_uses_trade_weight(self) -> None:
        data = pd.DataFrame(
            [
                {
                    "交易数": 100,
                    "净胜率": 50.0,
                    "平均净收益率": 1.0,
                    "平均盈利": 4.0,
                    "平均亏损": -3.0,
                },
                {
                    "交易数": 100,
                    "净胜率": 60.0,
                    "平均净收益率": 3.0,
                    "平均盈利": 6.0,
                    "平均亏损": -4.0,
                },
            ]
        )

        result = MODULE.summarize_baseline(data)

        self.assertEqual(result["交易数"], 200)
        self.assertAlmostEqual(result["净胜率"], 55.0)
        self.assertAlmostEqual(result["平均净收益率"], 2.0)
        self.assertAlmostEqual(result["平均盈利"], 5.090909, places=5)
        self.assertAlmostEqual(result["平均亏损"], -3.444444, places=5)

    def test_report_builds_three_experiments(self) -> None:
        config = MODULE.load_config(MODULE.DEFAULT_CONFIG)
        summary = MODULE.build_summary(config)

        self.assertEqual(summary["实验"].nunique(), 3)
        self.assertIn("只改因子", summary.columns)
        self.assertIn("方向评级", summary.columns)
        self.assertIn("相对基准平均收益变化", summary.columns)
        self.assertTrue(
            summary.loc[
                summary["只改因子"].eq("无，基准"),
                "实验",
            ].notna().all()
        )


if __name__ == "__main__":
    unittest.main()
