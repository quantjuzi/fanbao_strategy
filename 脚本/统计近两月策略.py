# -*- coding: utf-8 -*-
"""统计最近两个月连板断板和单板反包的阶段表现。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = PROJECT_ROOT / "结果"
DOC_PATH = PROJECT_ROOT / "文档" / "近两月策略对比.md"

STRATEGIES = {
    "连板断板承接": RESULT_DIR / "策略一_连板断板_交易明细.csv",
    "单板反包开板2次": RESULT_DIR / "策略二_单板反包_交易明细.csv",
}

PERIOD_START = pd.Timestamp("2026-08-01")
PERIOD_END = pd.Timestamp("2026-09-30")


def summarize(
    strategy: str,
    period: str,
    trades: pd.DataFrame,
) -> dict[str, float | str]:
    """计算一个策略在某个月份的绩效。"""

    winners = trades.loc[trades["净收益率"].gt(0), "净收益率"]
    losers = trades.loc[trades["净收益率"].lt(0), "净收益率"]
    normalized_pnl = trades["净收益率"] * 20_000 / 100
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
        "平均盈利": winners.mean() if not winners.empty else 0.0,
        "平均亏损": losers.mean() if not losers.empty else 0.0,
        "盈亏比": (
            winners.mean() / abs(losers.mean())
            if not winners.empty and not losers.empty
            else 0.0
        ),
        "按两万元每笔累计盈亏": normalized_pnl.sum(),
        "最大单笔盈利": (
            trades["净收益率"].max()
            if not trades.empty
            else 0.0
        ),
        "最大单笔亏损": (
            trades["净收益率"].min()
            if not trades.empty
            else 0.0
        ),
    }


def fetch_index_context() -> pd.DataFrame:
    """获取同期深证成指表现，失败时不影响策略统计。"""

    try:
        import baostock as bs
    except ImportError:
        return pd.DataFrame()

    login = bs.login()
    if login.error_code != '0':
        return pd.DataFrame()
    try:
        result = bs.query_history_k_data_plus(
            'sz.399001',
            'date,close,pctChg',
            start_date='2026-07-31',
            end_date='2026-09-30',
            frequency='d',
            adjustflag='3',
        )
        rows = []
        while result.next():
            rows.append(result.get_row_data())
    finally:
        bs.logout()

    index_data = pd.DataFrame(
        rows,
        columns=['日期', '收盘', '涨跌幅'],
    )
    index_data['日期'] = pd.to_datetime(index_data['日期'])
    index_data['收盘'] = pd.to_numeric(
        index_data['收盘'],
        errors='coerce',
    )
    index_data['涨跌幅'] = pd.to_numeric(
        index_data['涨跌幅'],
        errors='coerce',
    )
    index_data = index_data.set_index('日期')

    rows = []
    for label, start, end in [
        ('2026-08', '2026-08-01', '2026-08-31'),
        ('2026-09', '2026-09-01', '2026-09-30'),
        ('8月到9月合计', '2026-08-01', '2026-09-30'),
    ]:
        sample = index_data.loc[start:end]
        if sample.empty:
            continue
        index_return = (
            sample.iloc[-1]['收盘'] / sample.iloc[0]['收盘'] - 1
        ) * 100
        rows.append(
            {
                '区间': label,
                '深证成指收益': index_return,
                '上涨天数占比': sample['涨跌幅'].gt(0).mean() * 100,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    """生成近两个月策略对比。"""

    rows: list[dict[str, float | str]] = []
    for strategy, path in STRATEGIES.items():
        trades = pd.read_csv(path, encoding="utf-8-sig")
        trades["买入日期"] = pd.to_datetime(
            trades["买入日期"],
            errors="coerce",
        )
        trades = trades.loc[
            trades["买入日期"].between(PERIOD_START, PERIOD_END)
        ].copy()
        rows.append(summarize(strategy, "2026-08", trades.loc[
            trades["买入日期"].dt.month.eq(8)
        ]))
        rows.append(summarize(strategy, "2026-09", trades.loc[
            trades["买入日期"].dt.month.eq(9)
        ]))
        rows.append(summarize(strategy, "8月到9月合计", trades))

    result = pd.DataFrame(rows)
    result.to_csv(
        RESULT_DIR / "近两月策略对比.csv",
        index=False,
        encoding="utf-8-sig",
    )
    index_context = fetch_index_context()

    lines = [
        "# 近两月策略对比",
        "",
        "统计区间：2026-08-01 至 2026-09-30。",
        "卖出价格沿用两个策略原始回测口径，即卖出日成交均价并扣除滑点。",
        "",
        "## 两种模式简写",
        "",
        "- 连板断板承接：2连板以上断板后，下一交易日开盘买入，再次日成交均价卖出。",
        "- 单板反包开板2次：首板后断板，按反包模式下一交易日开盘买入，再次日成交均价卖出。",
        "",
        "这里不额外叠加题材、情绪或新的过滤条件，只比较两种模式在不同市场月份下的整体统计变化。",
        "",
        "| 策略 | 区间 | 交易数 | 净胜率 | 平均净收益率 | 盈亏比 | 按两万元每笔累计盈亏 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in result.iterrows():
        lines.append(
            "| {strategy} | {period} | {trades} | {win_rate:.2f}% | "
            "{avg_return:+.4f}% | {ratio:.4f} | {pnl:+,.2f}元 |".format(
                strategy=row["策略"],
                period=row["区间"],
                trades=int(row["交易数"]),
                win_rate=row["净胜率"],
                avg_return=row["平均净收益率"],
                ratio=row["盈亏比"],
                pnl=row["按两万元每笔累计盈亏"],
            )
        )
    lines.extend(
        [
            "",
            "## 大白比较",
            "",
            "| 区间 | 深证成指 | 连板断板平均收益 | 单板反包平均收益 | 相对更好 |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for period in ["2026-08", "2026-09", "8月到9月合计"]:
        period_rows = result.loc[result["区间"].eq(period)]
        stock_row = period_rows.loc[
            period_rows["策略"].eq("连板断板承接")
        ].iloc[0]
        reversal_row = period_rows.loc[
            period_rows["策略"].eq("单板反包开板2次")
        ].iloc[0]
        if index_context.empty:
            index_return = 0.0
        else:
            index_return = index_context.loc[
                index_context["区间"].eq(period),
                "深证成指收益",
            ].iloc[0]
        better = (
            "连板断板承接"
            if stock_row["平均净收益率"] > reversal_row["平均净收益率"]
            else "单板反包开板2次"
        )
        lines.append(
            "| {period} | {index_return:+.2f}% | {stock_return:+.4f}% | "
            "{reversal_return:+.4f}% | {better} |".format(
                period=period,
                index_return=index_return,
                stock_return=stock_row["平均净收益率"],
                reversal_return=reversal_row["平均净收益率"],
                better=better,
            )
        )
    if not index_context.empty:
        lines.extend(
            [
                "",
                "## 同期市场环境",
                "",
                "| 区间 | 深证成指收益 | 上涨天数占比 |",
                "|---|---:|---:|",
            ]
        )
        for _, row in index_context.iterrows():
            lines.append(
                "| {period} | {index_return:+.2f}% | {up_ratio:.2f}% |".format(
                    period=row['区间'],
                    index_return=row['深证成指收益'],
                    up_ratio=row['上涨天数占比'],
                )
            )
    lines.extend(
        [
            "",
            "## 解读边界",
            "",
            "- 这是近两个月的阶段样本，不能替代完整区间和样本外验证。",
            "- 市场环境偏弱时，短线情绪轮动会更快，策略表现需要按月拆开看。",
            "- 单月样本较少，交易数和平均收益需要同时看。",
            "- 两个月合计连板断板承接优于单板反包，但 9 月单月优势还不明显，不能只凭一个阶段下结论。",
        ]
    )
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(result.to_string(index=False))
    if not index_context.empty:
        print("\n同期市场环境：")
        print(index_context.to_string(index=False))
    print(f"\n结果已保存：{RESULT_DIR / '近两月策略对比.csv'}")
    print(f"说明已保存：{DOC_PATH}")


if __name__ == "__main__":
    main()
