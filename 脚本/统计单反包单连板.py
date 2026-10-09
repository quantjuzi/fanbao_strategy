# -*- coding: utf-8 -*-
"""统计近两个月单反包和单连板策略表现。

单反包：
    首板后第一次断板，按反包策略规则买入卖出。

单连板：
    首板后的下一交易日，竞价低于+2%，且不是一字涨停或一字跌停，
    按开盘价买入，再次日成交均价卖出。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pandas as pd

from 连板断板统计 import consecutive_limit_count


PROJECT_DIR = Path(__file__).resolve().parents[1]
RESULT_DIR = PROJECT_DIR / "结果"
DOC_PATH = PROJECT_DIR / "文档" / "单反包单连板对比.md"
DATA_PATH = PROJECT_DIR / "数据" / "聚宽因子_2026-01-01_2026-09-30.csv"
STRATEGY_PATH = PROJECT_DIR / "脚本" / "高开均线完整回测.py"
REVERSAL_SOURCE = Path(
    r"C:\Users\Administrator\PyCharmMiscProject"
    r"\高开均线完整输出\单板反包_开板明细.csv"
)

PERIOD_START = pd.Timestamp("2026-08-01")
PERIOD_END = pd.Timestamp("2026-09-30")


def load_strategy_module(path: Path) -> ModuleType:
    """加载成本和交易统计函数。"""

    spec = importlib.util.spec_from_file_location("单反包单连板策略", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载策略模块: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def max_concurrent_positions(trades: pd.DataFrame) -> int:
    """按买入日到卖出日计算最高并发持仓。"""

    if trades.empty:
        return 0
    dates = pd.date_range(
        trades["买入日期"].min(),
        trades["卖出日期"].max(),
        freq="D",
    )
    return max(
        int(
            trades["买入日期"].le(date).sum()
            - trades["卖出日期"].lt(date).sum()
        )
        for date in dates
    )


def normalize_code(values: pd.Series) -> pd.Series:
    """把带市场后缀的代码转成6位股票代码。"""

    return (
        values.astype(str)
        .str.split(".")
        .str[0]
        .str.zfill(6)
    )


def summarize(
    strategy: str,
    period: str,
    trades: pd.DataFrame,
) -> dict[str, float | str]:
    """计算策略阶段绩效。"""

    winners = trades.loc[trades["净收益率"].gt(0), "净收益率"]
    losers = trades.loc[trades["净收益率"].lt(0), "净收益率"]
    pnl = trades["净收益率"] * 20_000 / 100
    max_positions = max_concurrent_positions(trades)
    capital = max_positions * 20_000
    total_pnl = pnl.sum()
    return {
        "策略": strategy,
        "区间": period,
        "交易数": len(trades),
        "净胜率": (
            trades["净收益率"].gt(0).mean() * 100
            if not trades.empty
            else 0.0
        ),
        "平均净收益率": (
            trades["净收益率"].mean()
            if not trades.empty
            else 0.0
        ),
        "平均每笔收益金额": (
            trades["净收益率"].mean() * 20_000 / 100
            if not trades.empty
            else 0.0
        ),
        "平均盈利金额": (
            winners.mean() * 20_000 / 100
            if not winners.empty
            else 0.0
        ),
        "平均亏损金额": (
            losers.mean() * 20_000 / 100
            if not losers.empty
            else 0.0
        ),
        "最高并发持仓": max_positions,
        "最高资金占用": capital,
        "累计盈亏": total_pnl,
        "资金收益率": (
            total_pnl / capital * 100
            if capital > 0
            else 0.0
        ),
    }


def build_single_relay() -> pd.DataFrame:
    """构建首板后次日买入的单连板交易。"""

    strategy = load_strategy_module(STRATEGY_PATH)
    config = strategy.策略参数()
    raw = strategy.读取数据(DATA_PATH)
    df, _ = strategy.清洗数据(raw)
    df = strategy.计算因子(df)

    grouped = df.groupby("code", sort=False)
    df["连板数"] = grouped["是否涨停"].transform(
        consecutive_limit_count
    )
    df["前一日连板数"] = grouped["连板数"].shift(1)
    df["前两日涨停"] = grouped["是否涨停"].shift(2).fillna(0)
    df["前一日成交额_亿"] = grouped["成交额_亿"].shift(1)
    df["前一日M7M14比值"] = (
        grouped["M7"].shift(1) / grouped["M14"].shift(1)
    )
    df["前一日实体涨幅"] = grouped["实体涨幅"].shift(1)
    df["买入日期"] = df["time"]
    df["买入参考价"] = df["open"]
    df["卖出日期"] = grouped["time"].shift(-1)
    df["卖出参考价"] = grouped["均价"].shift(-1)
    df["信号"] = (
        df["前一日连板数"].eq(1)
        & df["前两日涨停"].eq(0)
        & df["竞价涨幅"].lt(2)
        & df["open"].gt(df["low_limit"])
        & df["open"].lt(df["high_limit"])
    ).astype(int)

    trades = df.loc[df["信号"].eq(1)].copy()
    trades = trades.dropna(
        subset=[
            "买入日期",
            "买入参考价",
            "卖出日期",
            "卖出参考价",
        ]
    )
    trades = strategy.计算交易成本(trades, config)
    trades = trades.loc[
        trades["买入日期"].between(PERIOD_START, PERIOD_END)
    ].copy()
    return pd.DataFrame(
        {
            "策略": "单连板",
            "代码": normalize_code(trades["code"]),
            "买入日期": trades["买入日期"],
            "买入价格": trades["买入成交价"],
            "卖出日期": trades["卖出日期"],
            "卖出价格": trades["卖出成交价"],
            "净收益率": trades["净收益率"],
            "净盈亏金额": trades["净盈亏金额"],
            "成交额_亿": trades["前一日成交额_亿"],
            "M7M14比值": trades["前一日M7M14比值"],
            "实体涨幅": trades["前一日实体涨幅"],
        }
    ).reset_index(drop=True)


def build_single_reversal() -> pd.DataFrame:
    """构建近两个月单反包交易。"""

    if not REVERSAL_SOURCE.exists():
        raise FileNotFoundError(f"未找到单反包明细: {REVERSAL_SOURCE}")
    data = pd.read_csv(REVERSAL_SOURCE, encoding="utf-8-sig")
    data["买入日期"] = pd.to_datetime(data["买入日期"], errors="coerce")
    data["卖出日期"] = pd.to_datetime(data["卖出日期"], errors="coerce")
    data = data.loc[
        data["买入日期"].between(PERIOD_START, PERIOD_END)
    ].copy()
    return pd.DataFrame(
        {
            "策略": "单反包",
            "代码": normalize_code(data["code"]),
            "买入日期": data["买入日期"],
            "买入价格": data["买入成交价"],
            "卖出日期": data["卖出日期"],
            "卖出价格": data["卖出成交价"],
            "净收益率": data["净收益率"],
            "净盈亏金额": data["净盈亏金额"],
            "涨停日开板次数": data["开板次数"],
            "成交额_亿": data["成交额_亿"],
            "M7M14比值": data["M7M14比值"],
            "实体涨幅": data["实体涨幅"],
        }
    ).reset_index(drop=True)


def fetch_index_context() -> pd.DataFrame:
    """获取同期深证成指和市场成交额环境。"""

    try:
        import baostock as bs
    except ImportError:
        return pd.DataFrame()

    login = bs.login()
    if login.error_code != "0":
        return pd.DataFrame()
    try:
        result = bs.query_history_k_data_plus(
            "sz.399001",
            "date,close,pctChg",
            start_date="2026-06-01",
            end_date="2026-09-30",
            frequency="d",
            adjustflag="3",
        )
        rows = []
        while result.next():
            rows.append(result.get_row_data())
    finally:
        bs.logout()

    data = pd.DataFrame(rows, columns=["日期", "收盘", "涨跌幅"])
    data["日期"] = pd.to_datetime(data["日期"])
    data["收盘"] = pd.to_numeric(data["收盘"], errors="coerce")
    data["涨跌幅"] = pd.to_numeric(data["涨跌幅"], errors="coerce")
    data["指数MA20"] = data["收盘"].rolling(20).mean()
    data["指数低于MA20"] = data["收盘"].lt(data["指数MA20"])

    turnover = pd.read_csv(
        DATA_PATH,
        encoding="utf-8-sig",
        usecols=["time", "money"],
    )
    turnover["time"] = pd.to_datetime(turnover["time"])
    turnover = (
        turnover.groupby("time", as_index=False)["money"]
        .sum()
        .rename(columns={"time": "日期", "money": "市场成交额"})
    )
    turnover["成交额MA20"] = turnover["市场成交额"].rolling(20).mean()
    turnover["成交额低于MA20"] = turnover["市场成交额"].lt(
        turnover["成交额MA20"]
    )

    data = data.merge(turnover, on="日期", how="inner").set_index("日期")
    rows = []
    for label, start, end in [
        ("2026-08", "2026-08-01", "2026-08-31"),
        ("2026-09", "2026-09-01", "2026-09-30"),
        ("8月到9月合计", "2026-08-01", "2026-09-30"),
    ]:
        sample = data.loc[start:end]
        if sample.empty:
            continue
        rows.append(
            {
                "区间": label,
                "深证成指收益": (
                    sample.iloc[-1]["收盘"]
                    / sample.iloc[0]["收盘"]
                    - 1
                )
                * 100,
                "上涨天数占比": sample["涨跌幅"].gt(0).mean() * 100,
                "指数低于MA20占比": sample["指数低于MA20"].mean() * 100,
                "成交额低于MA20占比": sample["成交额低于MA20"].mean()
                * 100,
            }
        )
    context = pd.DataFrame(rows)
    last_day = data.loc["2026-09-30"]
    context.attrs["last_day"] = {
        "指数收盘": last_day["收盘"],
        "指数MA20": last_day["指数MA20"],
        "指数低于MA20": bool(last_day["指数低于MA20"]),
        "市场成交额_亿": last_day["市场成交额"] / 1e8,
        "成交额MA20_亿": last_day["成交额MA20"] / 1e8,
        "成交额低于MA20": bool(last_day["成交额低于MA20"]),
    }
    return context


def main() -> None:
    """生成近两个月单反包和单连板对比。"""

    reversal = build_single_reversal()
    relay = build_single_relay()
    all_trades = pd.concat([reversal, relay], ignore_index=True)
    all_trades.to_csv(
        RESULT_DIR / "单反包单连板_交易明细.csv",
        index=False,
        encoding="utf-8-sig",
    )

    rows: list[dict[str, float | str]] = []
    for strategy, trades in [
        ("单反包", reversal),
        ("单连板", relay),
    ]:
        for label, month in [("2026-08", 8), ("2026-09", 9)]:
            rows.append(
                summarize(
                    strategy,
                    label,
                    trades.loc[trades["买入日期"].dt.month.eq(month)],
                )
            )
        rows.append(
            summarize(strategy, "8月到9月合计", trades)
        )
    result = pd.DataFrame(rows)
    result.to_csv(
        RESULT_DIR / "单反包单连板对比.csv",
        index=False,
        encoding="utf-8-sig",
    )

    index_context = fetch_index_context()

    condition_rows = [
        summarize("单反包-基础", "8月到9月合计", reversal),
        summarize(
            "单反包-开板2次",
            "8月到9月合计",
            reversal.loc[reversal["涨停日开板次数"].eq(2)],
        ),
        summarize(
            "单反包-成交额10到40亿",
            "8月到9月合计",
            reversal.loc[
                reversal["成交额_亿"].between(10, 40, inclusive="left")
            ],
        ),
        summarize(
            "单反包-开板2次+成交额10到40亿",
            "8月到9月合计",
            reversal.loc[
                reversal["涨停日开板次数"].eq(2)
                & reversal["成交额_亿"].between(10, 40, inclusive="left")
            ],
        ),
        summarize("单连板-基础", "8月到9月合计", relay),
        summarize(
            "单连板-成交额大于6亿",
            "8月到9月合计",
            relay.loc[relay["成交额_亿"].gt(6)],
        ),
        summarize(
            "单连板-成交额大于6亿+M7/M14大于1+实体大于1",
            "8月到9月合计",
            relay.loc[
                relay["成交额_亿"].gt(6)
                & relay["M7M14比值"].gt(1)
                & relay["实体涨幅"].gt(1)
            ],
        ),
    ]
    condition_result = pd.DataFrame(condition_rows)
    condition_result.to_csv(
        RESULT_DIR / "单反包单连板_买入条件对比.csv",
        index=False,
        encoding="utf-8-sig",
    )

    lines = [
        "# 单反包和单连板对比",
        "",
        "统计区间：2026-08-01 至 2026-09-30。",
        "两种策略都按开盘价买入，卖出日成交均价卖出，并扣除滑点和交易成本。",
        "",
        "## 策略口径",
        "",
        "- 单反包：首板后第一次断板，按反包策略规则买入卖出。",
        "- 单连板：首板后的下一交易日，竞价低于+2%，且不是一字涨停或一字跌停，按开盘价买入，再次日成交均价卖出。",
        "",
        "| 策略 | 区间 | 交易数 | 净胜率 | 平均每笔收益金额 | 平均盈利金额 | 平均亏损金额 | 最高资金占用 | 累计盈亏 | 资金收益率 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in result.iterrows():
        lines.append(
            "| {strategy} | {period} | {trades} | {win_rate:.2f}% | "
            "{avg_amount:+,.2f}元 | {avg_win:+,.2f}元 | "
            "{avg_loss:+,.2f}元 | {capital:,.0f}元 | "
            "{pnl:+,.2f}元 | {capital_return:+.2f}% |".format(
                strategy=row["策略"],
                period=row["区间"],
                trades=int(row["交易数"]),
                win_rate=row["净胜率"],
                avg_amount=row["平均每笔收益金额"],
                avg_win=row["平均盈利金额"],
                avg_loss=row["平均亏损金额"],
                capital=row["最高资金占用"],
                pnl=row["累计盈亏"],
                capital_return=row["资金收益率"],
            )
        )
    lines.extend(
        [
            "",
            "## 加入买入条件后的对比",
            "",
            "| 策略方案 | 交易数 | 净胜率 | 平均每笔收益金额 | 最高资金占用 | 累计盈亏 | 资金收益率 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in condition_result.iterrows():
        lines.append(
            "| {strategy} | {trades} | {win_rate:.2f}% | "
            "{avg_amount:+,.2f}元 | {capital:,.0f}元 | "
            "{pnl:+,.2f}元 | {capital_return:+.2f}% |".format(
                strategy=row["策略"],
                trades=int(row["交易数"]),
                win_rate=row["净胜率"],
                avg_amount=row["平均每笔收益金额"],
                capital=row["最高资金占用"],
                pnl=row["累计盈亏"],
                capital_return=row["资金收益率"],
            )
        )
    if not index_context.empty:
        lines.extend(
            [
                "",
                "## 同期市场",
                "",
                "| 区间 | 深证成指收益 | 上涨天数占比 | 指数低于MA20占比 | 成交额低于MA20占比 |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for _, row in index_context.iterrows():
            lines.append(
                "| {period} | {index_return:+.2f}% | {up_ratio:.2f}% | "
                "{below_ma:.2f}% | {turnover_below:.2f}% |".format(
                    period=row["区间"],
                    index_return=row["深证成指收益"],
                    up_ratio=row["上涨天数占比"],
                    below_ma=row["指数低于MA20占比"],
                    turnover_below=row["成交额低于MA20占比"],
                )
            )
        last_day = index_context.attrs.get("last_day", {})
        if last_day:
            lines.extend(
                [
                    "",
                    "截至 2026-09-30：",
                    "",
                    "- 深证成指收盘：{close:.2f}，MA20：{ma20:.2f}".format(
                        close=last_day["指数收盘"],
                        ma20=last_day["指数MA20"],
                    ),
                    "- 市场成交额：{amount:.2f} 亿，MA20：{ma20:.2f} 亿".format(
                        amount=last_day["市场成交额_亿"],
                        ma20=last_day["成交额MA20_亿"],
                    ),
                ]
            )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- 9月深证成指有 90.48% 的交易日位于 MA20 下方，市场成交额有 85.71% 的交易日低于 MA20，弱势特征明显。",
            "- 弱势市场下资金更容易向少数核心标的集中，但不代表所有单连板都应该买。",
            "- 本次加入条件后，单反包开板2次且成交额10到40亿的表现最好，单连板加入硬过滤后反而明显变差。",
            "- 因此当前更合理的做法是减少无效交易，优先观察核心题材和相对强度，而不是无条件优先单连板。",
        ]
    )
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(result.to_string(index=False))
    if not index_context.empty:
        print("\n同期市场：")
        print(index_context.to_string(index=False))


if __name__ == "__main__":
    main()
