# -*- coding: utf-8 -*-
"""对比近三个月反包策略与阴线炸板策略的统计指标。"""

import glob
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULT_DIR = os.path.join(ROOT, "results")


def load_recent_fanbao() -> pd.DataFrame:
    """加载近三个月反包实体明细表。"""
    path = glob.glob(os.path.join(RESULT_DIR, "*_2026-05-01_2026-07-31.csv"))[0]
    return pd.read_csv(path, encoding="utf-8-sig")


def load_recent_zhaban() -> pd.DataFrame:
    """合并 5~6 月与 7 月阴线炸板明细表。"""
    parts = []
    for pattern in ["*_2026-05_2026-06.csv", "*_2026-07-01_2026-07-31.csv"]:
        matches = glob.glob(os.path.join(RESULT_DIR, pattern))
        if matches:
            parts.append(pd.read_csv(matches[0], encoding="utf-8-sig"))
    return pd.concat(parts, ignore_index=True)


def load_full_fanbao() -> pd.DataFrame:
    """加载全年反包实体明细表。"""
    path = glob.glob(os.path.join(RESULT_DIR, "*反包*_2025-04-21_2026-04-28.csv"))[0]
    return pd.read_csv(path, encoding="utf-8-sig")


def load_full_zhaban() -> pd.DataFrame:
    """加载全年阴线炸板明细表。"""
    path = glob.glob(os.path.join(RESULT_DIR, "*阴线炸板*_2025-04-21_2026-04-28.csv"))[0]
    return pd.read_csv(path, encoding="utf-8-sig")


def print_stats(df: pd.DataFrame, label: str) -> None:
    """打印一笔一算的胜率、平均收益、盈亏比。"""
    ret = pd.to_numeric(df["盈亏(%)"], errors="coerce").dropna()
    n = len(ret)
    if n == 0:
        print(f"{label}: 无样本")
        return
    win = (ret > 0).mean() * 100
    avg = ret.mean()
    avg_win = ret[ret > 0].mean() if (ret > 0).any() else 0.0
    avg_loss = ret[ret <= 0].mean() if (ret <= 0).any() else 0.0
    print(
        f"{label}: {n}笔, 胜率{win:.1f}%, 平均{avg:+.2f}%, "
        f"平均赚{avg_win:+.2f}%, 平均亏{avg_loss:+.2f}%, "
        f"盈亏比{abs(avg_win / avg_loss) if avg_loss else 0:.2f}"
    )


def main() -> None:
    """对比输出。"""
    print_stats(load_recent_fanbao(), "反包 5~7月")
    print_stats(load_recent_zhaban(), "炸板 5~7月")
    print()
    print_stats(load_full_fanbao(), "反包 全年")
    print_stats(load_full_zhaban(), "炸板 全年")


if __name__ == "__main__":
    main()
