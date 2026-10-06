# -*- coding: utf-8 -*-
"""高开均线策略回测实现。

信号：
    T 日竞价高开、实体涨幅在 -5% 到 5% 之间、收盘价站上 M14。
交易：
    T+1 开盘买入，T+2 全天均价卖出，每日按成交额取前 N 名。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = (
    PROJECT_ROOT
    / "数据"
    / "聚宽因子_2026-01-01_2026-09-30.csv"
)


@dataclass(frozen=True)
class BacktestConfig:
    """策略、成本和仓位参数。"""

    top_n: int = 5
    position_size: float = 20_000.0
    lot_size: int = 100
    commission_rate: float = 0.0001
    min_commission: float = 5.0
    stamp_duty_rate: float = 0.0005
    transfer_fee_rate: float = 0.00001
    slippage_rate: float = 0.001
    min_ma_ratio: float = 0.0


REQUIRED_COLUMNS = {
    "time",
    "code",
    "open",
    "close",
    "volume",
    "money",
    "paused",
    "竞价涨幅",
    "成交额_亿",
    "M7",
    "M14",
}


def load_data(path: Path) -> pd.DataFrame:
    """读取日线数据，并完成类型转换和基础清洗。"""

    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在: {path}")

    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"缺少字段: {sorted(missing)}")

    df = df.rename(
        columns={
            "竞价涨幅": "auction_return",
            "成交额_亿": "turnover_billion",
            "M7": "ma7",
            "M14": "ma14",
        }
    )
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df["code"] = df["code"].astype("string")

    numeric_columns = [
        "open",
        "close",
        "volume",
        "money",
        "paused",
        "auction_return",
        "turnover_billion",
        "ma7",
        "ma14",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(
        subset=[
            "time",
            "code",
            "open",
            "close",
            "volume",
            "money",
            "auction_return",
            "turnover_billion",
            "ma14",
        ]
    )
    df = df[
        df["open"].gt(0)
        & df["close"].gt(0)
        & df["volume"].gt(0)
        & df["money"].gt(0)
        & df["paused"].fillna(0).eq(0)
    ]
    df = df.drop_duplicates(subset=["code", "time"], keep="last")
    return df.sort_values(["code", "time"]).reset_index(drop=True)


def prepare_factors(
    df: pd.DataFrame,
    config: BacktestConfig,
) -> pd.DataFrame:
    """计算信号因子，并标记 T 日是否满足策略条件。"""

    result = df.copy()
    result["body_return"] = (
        result["close"] / result["open"] - 1
    ) * 100
    result["avg_price"] = result["money"] / result["volume"]
    result["ma_ratio"] = result["ma7"] / result["ma14"]

    signal = (
        result["auction_return"].gt(0)
        & result["body_return"].between(-5, 5)
        & result["close"].gt(result["ma14"])
    )
    if config.min_ma_ratio > 0:
        signal &= result["ma_ratio"].gt(config.min_ma_ratio)

    result["signal"] = signal.astype(int)
    return result


def build_trades(df: pd.DataFrame) -> pd.DataFrame:
    """按股票对齐 T+1 买入和 T+2 卖出。"""

    result = df.copy()
    grouped = result.groupby("code", sort=False)

    # shift(-1) 和 shift(-2) 必须在同一只股票内计算。
    result["buy_date"] = grouped["time"].shift(-1)
    result["buy_open"] = grouped["open"].shift(-1)
    result["sell_date"] = grouped["time"].shift(-2)
    result["sell_avg"] = grouped["avg_price"].shift(-2)

    trades = result.loc[result["signal"].eq(1)].copy()
    trades = trades.dropna(
        subset=[
            "buy_date",
            "buy_open",
            "sell_date",
            "sell_avg",
        ]
    )
    trades = trades.loc[
        trades["buy_date"].gt(trades["time"])
        & trades["sell_date"].gt(trades["buy_date"])
    ]
    return trades.reset_index(drop=True)


def apply_costs(
    trades: pd.DataFrame,
    config: BacktestConfig,
) -> pd.DataFrame:
    """计算滑点、整手买入、手续费和净收益。"""

    result = trades.copy()
    result["buy_price"] = result["buy_open"] * (
        1 + config.slippage_rate
    )
    result["sell_price"] = result["sell_avg"] * (
        1 - config.slippage_rate
    )
    result["shares"] = (
        result["buy_price"]
        .rdiv(config.position_size)
        .floordiv(config.lot_size)
        .mul(config.lot_size)
        .astype(int)
    )
    result = result.loc[result["shares"].gt(0)].copy()

    result["buy_amount"] = result["shares"] * result["buy_price"]
    result["sell_amount"] = result["shares"] * result["sell_price"]
    result["buy_commission"] = np.maximum(
        result["buy_amount"] * config.commission_rate,
        config.min_commission,
    )
    result["sell_commission"] = np.maximum(
        result["sell_amount"] * config.commission_rate,
        config.min_commission,
    )
    result["buy_fee"] = (
        result["buy_commission"]
        + result["buy_amount"] * config.transfer_fee_rate
    )
    result["sell_fee"] = (
        result["sell_commission"]
        + result["sell_amount"] * config.transfer_fee_rate
        + result["sell_amount"] * config.stamp_duty_rate
    )
    result["net_pnl"] = (
        result["sell_amount"]
        - result["buy_amount"]
        - result["buy_fee"]
        - result["sell_fee"]
    )
    result["net_return"] = (
        result["net_pnl"] / result["buy_amount"] * 100
    )
    return result


def select_portfolio(
    trades: pd.DataFrame,
    config: BacktestConfig,
) -> pd.DataFrame:
    """每个信号日按成交额选择前 N 名。"""

    result = trades.copy()
    result["daily_rank"] = result.groupby("time")[
        "turnover_billion"
    ].rank(method="first", ascending=False)
    result = result.loc[result["daily_rank"].le(config.top_n)].copy()
    return result.sort_values(
        ["buy_date", "time", "code"]
    ).reset_index(drop=True)


def max_concurrent_positions(
    trades: pd.DataFrame,
    trading_dates: pd.Series,
) -> int:
    """按买入日至卖出日计算最高并发持仓数。"""

    if trades.empty:
        return 0

    calendar = (
        pd.to_datetime(trading_dates)
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    date_index = {date: i for i, date in enumerate(calendar)}
    events = np.zeros(len(calendar) + 1, dtype=int)

    for buy_date, sell_date in zip(
        trades["buy_date"],
        trades["sell_date"],
    ):
        start = date_index[pd.Timestamp(buy_date)]
        end = date_index[pd.Timestamp(sell_date)] + 1
        events[start] += 1
        events[end] -= 1

    return int(np.cumsum(events[:-1]).max())


def calculate_metrics(
    portfolio: pd.DataFrame,
    trading_dates: pd.Series,
    config: BacktestConfig,
) -> dict[str, float]:
    """计算逐笔指标、资金占用、回撤和夏普。"""

    if portfolio.empty:
        raise ValueError("组合中没有可统计的交易。")

    winners = portfolio.loc[
        portfolio["net_return"].gt(0),
        "net_return",
    ]
    losers = portfolio.loc[
        portfolio["net_return"].lt(0),
        "net_return",
    ]
    total_pnl = float(portfolio["net_pnl"].sum())
    max_positions = max_concurrent_positions(
        portfolio,
        trading_dates,
    )
    capital_required = max_positions * config.position_size
    interval_return = (
        total_pnl / capital_required
        if capital_required > 0
        else 0.0
    )

    calendar = (
        pd.to_datetime(trading_dates)
        .drop_duplicates()
        .sort_values()
    )
    first_buy = portfolio["buy_date"].min()
    last_sell = portfolio["sell_date"].max()
    active_dates = calendar.loc[
        calendar.between(first_buy, last_sell)
    ]
    daily_returns = (
        portfolio.groupby("sell_date")["net_return"]
        .mean()
        .div(100)
        .reindex(active_dates, fill_value=0.0)
    )
    equity = (1 + daily_returns).cumprod()
    drawdown = equity / equity.cummax() - 1
    annual_return = (
        equity.iloc[-1] ** (252 / len(daily_returns)) - 1
        if len(daily_returns) > 0 and equity.iloc[-1] > 0
        else np.nan
    )
    sharpe = (
        daily_returns.mean()
        / daily_returns.std(ddof=1)
        * np.sqrt(252)
        if len(daily_returns) > 1
        and daily_returns.std(ddof=1) > 0
        else np.nan
    )

    return {
        "trades": float(len(portfolio)),
        "win_rate": float(portfolio["net_return"].gt(0).mean() * 100),
        "avg_return": float(portfolio["net_return"].mean()),
        "avg_win": float(winners.mean()) if not winners.empty else 0.0,
        "avg_loss": float(losers.mean()) if not losers.empty else 0.0,
        "profit_loss_ratio": (
            float(winners.mean() / abs(losers.mean()))
            if not winners.empty and not losers.empty
            else np.nan
        ),
        "total_pnl": total_pnl,
        "max_positions": float(max_positions),
        "capital_required": float(capital_required),
        "interval_return": float(interval_return * 100),
        "annual_return": float(annual_return * 100),
        "max_drawdown": float(drawdown.min() * 100),
        "sharpe": float(sharpe),
    }


def parse_args() -> argparse.Namespace:
    """读取命令行参数。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-path",
        type=Path,
        default=DEFAULT_DATA_PATH,
    )
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument(
        "--position-size",
        type=float,
        default=20_000.0,
    )
    parser.add_argument(
        "--ma-ratio",
        type=float,
        default=0.0,
        help="M7/M14 最低值，默认不启用。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="可选：保存组合交易明细。",
    )
    return parser.parse_args()


def main() -> None:
    """执行完整回测。"""

    args = parse_args()
    config = BacktestConfig(
        top_n=args.top_n,
        position_size=args.position_size,
        min_ma_ratio=args.ma_ratio,
    )

    df = load_data(args.data_path)
    df = prepare_factors(df, config)
    trades = build_trades(df)
    trades = apply_costs(trades, config)
    portfolio = select_portfolio(trades, config)
    metrics = calculate_metrics(portfolio, df["time"], config)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        portfolio.to_csv(
            args.output,
            index=False,
            encoding="utf-8-sig",
        )
        print(f"交易明细已保存: {args.output}")

    print("回测结果")
    for key, value in metrics.items():
        print(f"{key}: {value:.4f}")


if __name__ == "__main__":
    main()
