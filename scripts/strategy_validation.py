# -*- coding: utf-8 -*-
"""
连板/反包策略验证工具

功能：
1. 校验逐笔记录字段和交易状态；
2. 生成带“交易状态”的标准化表；
3. 按策略、板数和条件组生成分组统计；
4. 单独生成连板/反包策略汇总，避免混算。
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "results" / "strategy_validation.csv"
SCHEMA_PATH = ROOT / "config" / "strategy_validation_schema.json"
DETAIL_SUMMARY_PATH = ROOT / "results" / "strategy_validation_summary.csv"
STRATEGY_SUMMARY_PATH = ROOT / "results" / "strategy_validation_strategy_summary.csv"
STATUS_PATH = ROOT / "results" / "strategy_validation_status.csv"


def parse_float(value: str) -> float | None:
    """把空值和百分比字段转成 float。"""
    value = (value or "").strip().replace("%", "")
    if not value:
        return None
    return float(value)


def parse_date(value: str) -> datetime | None:
    """解析 YYYY-MM-DD 日期，空值返回 None。"""
    value = (value or "").strip()
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d")


def is_yes(value: str) -> bool:
    """兼容“是”和“按反包规则”等买入标记。"""
    return (value or "").strip() in {"是", "按反包规则"}


def is_completed(row: dict[str, str]) -> bool:
    """模拟买入且已有收益率，才算已完成交易。"""
    return is_yes(row.get("模拟买入", "")) and parse_float(row.get("收益率%", "")) is not None


def is_pending(row: dict[str, str]) -> bool:
    """模拟买入但还没有收益率，视为待卖出。"""
    return is_yes(row.get("模拟买入", "")) and parse_float(row.get("收益率%", "")) is None


def trade_status(row: dict[str, str]) -> str:
    """根据买入、卖出和收益字段推导交易状态。"""
    if not is_yes(row.get("模拟买入", "")):
        return "未买入"
    if parse_float(row.get("收益率%", "")) is not None:
        return "已完成"
    if (row.get("卖出日期", "") or "").strip():
        return "待卖出"
    return "待处理"


def mean(values: Iterable[float]) -> float | None:
    """求平均，空序列返回 None。"""
    values = list(values)
    if not values:
        return None
    return sum(values) / len(values)


def max_drawdown(returns: list[float]) -> float | None:
    """按交易收益率序列计算简化最大回撤，单位 %。"""
    if not returns:
        return None
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for value in returns:
        equity *= 1 + value / 100
        peak = max(peak, equity)
        drawdown = (equity - peak) / peak * 100
        max_dd = min(max_dd, drawdown)
    return max_dd


def load_schema() -> dict[str, object]:
    """读取字段配置。"""
    with SCHEMA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_rows(rows: list[dict[str, str]], schema: dict[str, object]) -> list[str]:
    """检查字段、数值、日期、枚举值和关键交易关系。"""
    issues: list[str] = []
    required_columns = list(schema.get("required_columns", []))
    numeric_columns = set(schema.get("numeric_columns", []))
    date_columns = set(schema.get("date_columns", []))
    allowed_values = dict(schema.get("allowed_values", {}))
    unique_key = list(schema.get("unique_key", []))

    if rows:
        missing_columns = [column for column in required_columns if column not in rows[0]]
        if missing_columns:
            issues.append(f"缺少字段: {', '.join(missing_columns)}")
            return issues

    seen_keys: set[tuple[str, ...]] = set()
    for line_number, row in enumerate(rows, start=2):
        key = tuple((row.get(column, "") or "").strip() for column in unique_key)
        if key in seen_keys:
            issues.append(f"第 {line_number} 行重复: {key}")
        seen_keys.add(key)

        for column in numeric_columns:
            value = (row.get(column, "") or "").strip()
            if not value:
                continue
            try:
                parse_float(value)
            except ValueError:
                issues.append(f"第 {line_number} 行 {column} 不是数字: {value}")

        for column in date_columns:
            value = (row.get(column, "") or "").strip()
            if not value:
                continue
            try:
                parse_date(value)
            except ValueError:
                issues.append(f"第 {line_number} 行 {column} 日期格式错误: {value}")

        for column, allowed in allowed_values.items():
            value = (row.get(column, "") or "").strip()
            if value not in allowed:
                issues.append(f"第 {line_number} 行 {column} 非法值: {value}")

        buy_date = parse_date(row.get("日期", ""))
        sell_date = parse_date(row.get("卖出日期", ""))
        if buy_date and sell_date and sell_date < buy_date:
            issues.append(f"第 {line_number} 行卖出日期早于买入日期")

        profit = (row.get("是否盈利", "") or "").strip()
        return_pct = parse_float(row.get("收益率%", ""))
        if return_pct is not None:
            expected_profit = "是" if return_pct > 0 else "否"
            if profit != expected_profit:
                issues.append(
                    f"第 {line_number} 行收益率与是否盈利不一致: "
                    f"{return_pct} / {profit or '空'}"
                )

        if is_completed(row) and not sell_date:
            issues.append(f"第 {line_number} 行已完成但缺少卖出日期")

    return issues


def calc_metrics(rows: list[dict[str, str]]) -> dict[str, object]:
    """计算一组交易的核心指标。"""
    completed = [row for row in rows if is_completed(row)]
    pending = [row for row in rows if is_pending(row)]
    returns = [parse_float(row.get("收益率%", "")) for row in completed]
    returns = [value for value in returns if value is not None]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value <= 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = None if gross_loss == 0 else gross_profit / gross_loss

    return {
        "候选记录": len(rows),
        "符合条件": sum(
            1
            for row in rows
            if is_yes(row.get("是否满足条件", ""))
        ),
        "模拟买入": sum(1 for row in rows if is_yes(row.get("模拟买入", ""))),
        "已完成样本": len(returns),
        "盈利笔数": len(wins),
        "亏损笔数": len(losses),
        "胜率%": None if not returns else len(wins) / len(returns) * 100,
        "平均收益率%": mean(returns),
        "平均盈利%": mean(wins),
        "平均亏损%": mean(losses),
        "盈亏比": profit_factor,
        "最大回撤%": max_drawdown(returns),
        "待卖出样本": len(pending),
    }


def build_detail_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
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
        if not any(is_yes(row.get("模拟买入", "")) for row in group_rows):
            continue
        summary.append(
            {
                "策略": strategy,
                "几板": board,
                "设定区间": condition,
                **calc_metrics(group_rows),
            }
        )
    return summary


def build_strategy_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """按策略生成独立汇总，连板和反包不混算。"""
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row.get("策略", "").strip()].append(row)

    summary: list[dict[str, object]] = []
    for strategy, group_rows in sorted(groups.items()):
        if not any(is_yes(row.get("模拟买入", "")) for row in group_rows):
            continue
        summary.append({"策略": strategy, **calc_metrics(group_rows)})
    return summary


def format_value(value: object) -> str:
    """把统计值格式化为适合 CSV 显示的字符串。"""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    """写出 UTF-8 BOM CSV，方便 Excel 直接打开。"""
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: format_value(row.get(key)) for key in columns})


def main() -> None:
    """执行校验、标准化和汇总。"""
    schema = load_schema()
    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    issues = validate_rows(rows, schema)
    if issues:
        print("数据校验失败:")
        for issue in issues:
            print(f"- {issue}")
        sys.exit(1)

    status_rows = [{**row, "交易状态": trade_status(row)} for row in rows]
    status_columns = list(schema["required_columns"]) + ["交易状态"]
    write_csv(STATUS_PATH, status_rows, status_columns)

    detail_summary = build_detail_summary(rows)
    detail_columns = [
        "策略",
        "几板",
        "设定区间",
        "候选记录",
        "符合条件",
        "模拟买入",
        "已完成样本",
        "盈利笔数",
        "亏损笔数",
        "胜率%",
        "平均收益率%",
        "平均盈利%",
        "平均亏损%",
        "盈亏比",
        "最大回撤%",
        "待卖出样本",
    ]
    write_csv(DETAIL_SUMMARY_PATH, detail_summary, detail_columns)

    strategy_summary = build_strategy_summary(rows)
    strategy_columns = [
        "策略",
        "候选记录",
        "符合条件",
        "模拟买入",
        "已完成样本",
        "盈利笔数",
        "亏损笔数",
        "胜率%",
        "平均收益率%",
        "平均盈利%",
        "平均亏损%",
        "盈亏比",
        "最大回撤%",
        "待卖出样本",
    ]
    write_csv(STRATEGY_SUMMARY_PATH, strategy_summary, strategy_columns)

    completed = [row for row in rows if is_completed(row)]
    pending = [row for row in rows if is_pending(row)]
    print("数据校验通过")
    print(f"逐笔记录: {len(rows)}")
    print(f"已完成: {len(completed)}")
    print(f"待卖出: {len(pending)}")
    print(f"标准化数据: {STATUS_PATH}")
    print(f"明细汇总: {DETAIL_SUMMARY_PATH}")
    print(f"策略汇总: {STRATEGY_SUMMARY_PATH}")


if __name__ == "__main__":
    main()
