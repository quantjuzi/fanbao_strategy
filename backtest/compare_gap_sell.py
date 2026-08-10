# -*- coding: utf-8 -*-
"""炸板策略 vs 反包策略：高开/低开 × 卖出方式对比（2026-04 ~ 2026-07）。

统一交易规则（A股 T+1）：
  信号日 S    收盘后确认信号
  S+1 次日竞价买入（以开盘价成交）
  S+2 第三日开盘卖出 / 第三日收盘卖出，两个口径分别统计

炸板信号：当日最高触板但收盘未封板，且成交额 > 5000 万；
          信号日 S，S+1 买入，S+2 卖出。
反包信号：前天(S-2)涨停、昨天(S-1)未涨停，信号日即 S-1；
          S 日买入，S+1 日卖出。

输出：
  results/高开低开_卖出方式对比.csv    汇总表
  results/炸板_高开低开明细.csv        炸板逐笔明细
  results/反包_高开低开明细.csv        反包逐笔明细
"""

from __future__ import annotations

import glob
import io
import os
import sys
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import pandas as pd
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILES = sorted(glob.glob(os.path.join(ROOT, "data", "*baostock*.csv")))


def _round_price(value: float, pct: float) -> float:
    """按交易所规则把涨跌幅换算成精确到分的涨停价。"""
    return float(
        (Decimal(str(value)) * Decimal(str(1 + pct))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )


def limit_pct(code: str, is_st: int) -> float:
    """按板块和 ST 状态返回涨跌幅限制。"""
    if code.startswith("bj."):
        return 0.30
    if code.startswith("sz.3") or code.startswith("sh.688"):
        return 0.20
    if is_st == 1:
        return 0.05
    return 0.10


def load_data() -> pd.DataFrame:
    """合并 baostock 全市场日线，并计算涨停价、涨停标记等基础因子。"""
    if not DATA_FILES:
        raise FileNotFoundError("data/ 下没有 baostock 数据文件")

    frames = []
    for path in DATA_FILES:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    for col in ["open", "high", "low", "close", "preclose", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "close", "high", "preclose", "amount"])
    df = df[df["tradestatus"] == 1].copy()

    df["date"] = pd.to_datetime(df["date"])
    df["成交额_亿"] = df["amount"] / 1e8
    df["high_limit"] = [
        _round_price(row.preclose, limit_pct(row.code, int(row.isST)))
        for row in df.itertuples(index=False)
    ]
    df["is_limit_up"] = (df["close"] >= df["high_limit"] * 0.99).astype(int)

    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    grp = df.groupby("code", sort=False)
    df["prev_limit_up"] = grp["is_limit_up"].shift(1).fillna(0).astype(int)
    df["prev2_limit_up"] = grp["is_limit_up"].shift(2).fillna(0).astype(int)
    df["buy_date"] = grp["date"].shift(-1)
    df["buy_open"] = grp["open"].shift(-1)
    df["buy_preclose"] = grp["preclose"].shift(-1)
    df["sell_date"] = grp["date"].shift(-2)
    df["sell_open"] = grp["open"].shift(-2)
    df["sell_close"] = grp["close"].shift(-2)
    return df


def build_trades(df: pd.DataFrame, signal_col: str) -> pd.DataFrame:
    """把信号行转成逐笔交易：次日开盘买入，第三日开盘/收盘卖出。"""
    signal = df[df[signal_col] == 1].copy()
    signal = signal.dropna(subset=["buy_open", "buy_preclose", "sell_open", "sell_close"])

    out = pd.DataFrame(
        {
            "策略": signal_col,
            "信号日": signal["date"].dt.strftime("%Y-%m-%d"),
            "代码": signal["code"],
            "买入日": signal["buy_date"].dt.strftime("%Y-%m-%d"),
            "买入价": signal["buy_open"].round(2),
            "买入日竞价涨幅%": ((signal["buy_open"] / signal["buy_preclose"] - 1) * 100).round(2),
            "卖出日": signal["sell_date"].dt.strftime("%Y-%m-%d"),
            "第3日开盘价": signal["sell_open"].round(2),
            "第3日收盘价": signal["sell_close"].round(2),
        }
    )
    out["开盘卖收益%"] = ((signal["sell_open"] / signal["buy_open"] - 1) * 100).round(2)
    out["收盘卖收益%"] = ((signal["sell_close"] / signal["buy_open"] - 1) * 100).round(2)
    gap = signal["buy_open"] / signal["buy_preclose"] - 1
    out["高开低开"] = np.select(
        [gap < -1e-6, gap > 1e-6],
        ["低开", "高开"],
        default="平开",
    )
    return out


def summary_table(details: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """按策略 × 高开低开汇总两种卖出方式的平均收益和差值。"""
    rows: list[dict[str, object]] = []
    for label, detail in details.items():
        for gap, grp in detail.groupby("高开低开", observed=True):
            open_avg = grp["开盘卖收益%"].mean()
            close_avg = grp["收盘卖收益%"].mean()
            rows.append(
                {
                    "策略": label,
                    "买入时": gap,
                    "样本数": len(grp),
                    "第3日开盘卖平均%": round(open_avg, 2),
                    "第3日收盘卖平均%": round(close_avg, 2),
                    "差值(收盘-开盘)%": round(close_avg - open_avg, 2),
                }
            )
        all_grp = detail
        open_avg = all_grp["开盘卖收益%"].mean()
        close_avg = all_grp["收盘卖收益%"].mean()
        rows.append(
            {
                "策略": label,
                "买入时": "全部",
                "样本数": len(all_grp),
                "第3日开盘卖平均%": round(open_avg, 2),
                "第3日收盘卖平均%": round(close_avg, 2),
                "差值(收盘-开盘)%": round(close_avg - open_avg, 2),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    df = load_data()
    print(f"数据范围: {df['date'].min().date()} ~ {df['date'].max().date()}, "
          f"{len(df):,} 行, {df['code'].nunique()} 只股票")

    # 炸板：最高触板、收盘未封板、成交额 > 5000 万
    df["炸板"] = (
        (df["high"] >= df["high_limit"] * 0.999)
        & (df["close"] < df["high_limit"])
        & (df["成交额_亿"] > 0.5)
    ).astype(int)
    # 反包：信号日(昨日)未涨停、前一日(前天)涨停，次日买入
    df["反包"] = ((df["prev_limit_up"] == 1) & (df["is_limit_up"] == 0)).astype(int)

    details = {
        "炸板策略": build_trades(df, "炸板"),
        "反包策略": build_trades(df, "反包"),
    }

    summary = summary_table(details)
    print()
    print("=" * 78)
    print("  炸板 vs 反包：买入日高开/低开 × 第3日卖出方式对比（2026-04 ~ 2026-07）")
    print("  买入：信号次日开盘价  卖出：第3日开盘价 / 第3日收盘价")
    print("=" * 78)
    print(summary.to_string(index=False))

    out_dir = os.path.join(ROOT, "results")
    os.makedirs(out_dir, exist_ok=True)
    summary.to_csv(
        os.path.join(out_dir, "高开低开_卖出方式对比.csv"),
        index=False,
        encoding="utf-8-sig",
    )
    for label, detail in details.items():
        name = "炸板" if label == "炸板策略" else "反包"
        detail.to_csv(
            os.path.join(out_dir, f"{name}_高开低开明细.csv"),
            index=False,
            encoding="utf-8-sig",
        )
    print(f"\n结果已保存: {out_dir}")


if __name__ == "__main__":
    main()
