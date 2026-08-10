# -*- coding: utf-8 -*-
"""阴线炸板策略月度收益测算。

规则: 炸板日(触及涨停但未封住)收阴线, 次日竞价买入, 次日收盘卖出。
数据窗口: 2026-04-12 ~ 2026-06-12 (信号集中在5/6~6/12, 共27个交易日)。
"""

import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_file(folder: str, fragment: str, exclude: str = "") -> str:
    """按文件名片段定位CSV文件。"""
    candidates = os.listdir(os.path.join(ROOT, folder))
    for name in candidates:
        if (
            fragment in name
            and name.endswith(".csv")
            and (not exclude or exclude not in name)
        ):
            return os.path.join(ROOT, folder, name)
    raise FileNotFoundError(f"{folder} 下未找到包含 {fragment} 的文件")


def scenario(sub: pd.DataFrame, label: str) -> None:
    """等权持有并逐日复利, 输出毛收益和扣成本后的收益。"""
    daily = sub.groupby("次日日期")["盈亏(%)"].mean()
    gross = (np.prod(1 + daily / 100) - 1) * 100
    cost = 0.025 * 2 + 0.1 * 2 + 0.05  # 佣金万2.5双边 + 滑点0.1%双边 + 印花税0.05%
    net = (np.prod(1 + (daily - cost) / 100) - 1) * 100
    print(f"{label}: {len(sub)}笔/{len(daily)}天, "
          f"日均毛收益{gross / len(daily):.2f}%, "
          f"月度毛收益{gross:.1f}% (10万毛赚{100000 * gross / 100:,.0f}元)")
    print(f"  扣成本(万2.5+滑点0.1%+印花税): 月度净收益{net:.1f}% "
          f"(10万净赚{100000 * net / 100:,.0f}元)")


def main() -> None:
    df = pd.read_csv(
        find_file("data", "2026-04-12_2026-06-12", exclude="_clean"),
        encoding="utf-8-sig",
    )
    df["index"] = pd.to_datetime(df["index"])
    df = df.sort_values(["证券代码", "index"]).reset_index(drop=True)

    df["成交额(亿)"] = (df["money"] / 1e8).round(4)
    df["is_zhaban"] = (
        (df["high"] >= df["high_limit"] * 0.9999)
        & (df["close"] < df["high_limit"])
        & (df["成交额(亿)"] > 0.5)
    ).astype(int)

    grp = df.groupby("证券代码")
    df["次日日期"] = grp["index"].shift(-1).dt.strftime("%Y-%m-%d")
    df["next_open"] = grp["open"].shift(-1)
    df["next_close"] = grp["close"].shift(-1)

    sig = df[(df["is_zhaban"] == 1) & (df["close"] < df["open"])].copy()
    sig = sig.dropna(subset=["next_open", "next_close"])
    sig["盈亏(%)"] = (sig["next_close"] / sig["next_open"] - 1) * 100
    sig["炸板日期"] = sig["index"].dt.strftime("%Y-%m-%d")
    sig["竞价买入价"] = sig["next_open"]
    sig["尾盘卖出价"] = sig["next_close"]
    # 与已有明细表保持一致: 只统计5/6 ~ 6/11的炸板信号
    sig = sig[sig["index"] >= "2026-05-06"].reset_index(drop=True)

    # 和已有明细表核对, 防止筛选口径出错
    detail = pd.read_csv(
        find_file("results", "阴线炸板明细表"), encoding="utf-8-sig"
    )
    d = detail.set_index(["日期", "代码"])["盈亏(%)"]
    s = sig.set_index(["炸板日期", "证券代码"])["盈亏(%)"]
    common = d.index.intersection(s.index)
    diff = (d.loc[common] - s.loc[common]).abs()
    print(f"核对明细: 共{len(common)}条, 完全一致{diff.lt(1e-9).sum()}条, "
          f"最大偏差{diff.max():.6f}")
    print(f"全部阴线炸板: {len(sig)}笔, 胜率{(sig['盈亏(%)'] > 0).mean() * 100:.1f}%, "
          f"平均每笔{sig['盈亏(%)'].mean():+.2f}%")
    print()

    scenario(sig, "全部信号等权")
    for topn in (1, 2, 3):
        top = sig.sort_values("成交额(亿)", ascending=False).groupby("次日日期").head(topn)
        scenario(top, f"每日按成交额Top{topn}等权")


if __name__ == "__main__":
    main()
