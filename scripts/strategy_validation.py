# -*- coding: utf-8 -*-
"""
连板/反包策略验证统计

读取 results/strategy_validation.csv，自动区分已完成和待卖出交易，
按“策略 + 几板 + 设定区间”输出胜率、平均收益和盈亏比。
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "results" / "strategy_validation.csv"
OUTPUT_PATH = ROOT / "results" / "strategy_validation_summary.csv"


def parse_float(value: str) -> float | None:
    """把空值和百分比字段转成 float。"""
    value = (value or "").strip().replace("%", "")
    if not value:
        return None
    return float(value)


def is_yes(value: str) -> bool:
    """兼容“是 / 否 / 按反包规则”等买入标记。"""
    return (value or "").strip() in {"是", "按反包规则"}


def is_completed(row: dict[str, str]) -> bool:
    """模拟买入且已有收益率，才算已完成交易。"""
    return is_yes(row.get("模拟买入", "")) and parse_float(row.get("收益率%", "")) is not None


def is_pending(row: dict[str, str]) -> bool:
    """模拟买入但还没有收益率，视为待卖出。"""
    return is_yes(row.get("模拟买入", "")) and parse_float(row.get("收益率%", "")) is None


def mean(values: Iterable[float]) -> float | None:
    """求平均，空序列返回 None。"""
    values = list(values)
    if not values:
        return None
    return sum(values) / len(values)


def build_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """按策略、板数和条件组生成汇总。"""
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("策略", "").strip(),
            row.get("几板", "").strip(),
            row.get("设定区间", "").strip(),
        )
        groups[key].append(row)

    summary: list[dict[str, object]] = []
    for (strategy, board, condition), group_rows in sorted(groups.items()):
        completed = [row for row in group_rows if is_completed(row)]
        pending = [row for row in group_rows if is_pending(row)]
        if not completed and not pending:
            continue
        returns = [parse_float(row.get("收益率%", "")) for row in completed]
        returns = [value for value in returns if value is not None]
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value <= 0]

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = None if gross_loss == 0 else gross_profit / gross_loss

        summary.append(
            {
                "策略": strategy,
                "几板": board,
                "设定区间": condition,
                "已完成样本": len(returns),
                "盈利笔数": len(wins),
                "亏损笔数": len(losses),
                "胜率%": None if not returns else len(wins) / len(returns) * 100,
                "平均收益率%": mean(returns),
                "平均盈利%": mean(wins),
                "平均亏损%": mean(losses),
                "盈亏比": profit_factor,
                "待卖出样本": len(pending),
            }
        )
    return summary


def format_value(value: object) -> str:
    """把统计值格式化为适合 CSV 显示的字符串。"""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def main() -> None:
    """读取逐笔表，生成汇总表，并打印总览。"""
    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    summary = build_summary(rows)
    columns = [
        "策略",
        "几板",
        "设定区间",
        "已完成样本",
        "盈利笔数",
        "亏损笔数",
        "胜率%",
        "平均收益率%",
        "平均盈利%",
        "平均亏损%",
        "盈亏比",
        "待卖出样本",
    ]

    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in summary:
            writer.writerow({key: format_value(row[key]) for key in columns})

    completed = [row for row in rows if is_completed(row)]
    pending = [row for row in rows if is_pending(row)]
    print(f"逐笔记录: {len(rows)}")
    print(f"已完成: {len(completed)}")
    print(f"待卖出: {len(pending)}")
    print(f"汇总文件: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
