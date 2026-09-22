# -*- coding: utf-8 -*-
"""策略验证脚本的核心函数测试。"""

import importlib.util
import csv
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "strategy_validation.py"
SPEC = importlib.util.spec_from_file_location("strategy_validation", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class StrategyValidationTests(unittest.TestCase):
    """验证数据转换、状态判断和分组统计。"""

    def test_parse_float_handles_percent_and_blank(self) -> None:
        self.assertEqual(MODULE.parse_float("10.74%"), 10.74)
        self.assertIsNone(MODULE.parse_float(""))

    def test_completed_and_pending_status(self) -> None:
        completed = {"模拟买入": "是", "收益率%": "10.74"}
        pending = {"模拟买入": "是", "卖出日期": "2026-09-23", "收益率%": ""}
        self.assertTrue(MODULE.is_completed(completed))
        self.assertTrue(MODULE.is_pending(pending))
        self.assertEqual(MODULE.trade_status(completed), "已完成")
        self.assertEqual(MODULE.trade_status(pending), "待卖出")

    def test_validate_rows_rejects_duplicate_key(self) -> None:
        schema = MODULE.load_schema()
        with (ROOT / "results" / "strategy_validation.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:
            row = next(csv.DictReader(file))
        rows = [row, row.copy()]
        issues = MODULE.validate_rows(rows, schema)
        self.assertTrue(any("重复" in issue for issue in issues))

    def test_sample_conclusion_thresholds(self) -> None:
        self.assertEqual(MODULE.sample_conclusion(2), "样本不足")
        self.assertEqual(MODULE.sample_conclusion(30), "初步验证")
        self.assertEqual(MODULE.sample_conclusion(100), "样本较充足")

    def test_max_drawdown(self) -> None:
        drawdown = MODULE.max_drawdown([10.0, -20.0, 5.0])
        self.assertAlmostEqual(drawdown, -20.0, places=6)


if __name__ == "__main__":
    unittest.main()
