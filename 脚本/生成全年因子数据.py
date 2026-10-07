# -*- coding: utf-8 -*-
"""把近一年日线原始数据整理成研究脚本使用的标准因子表。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


项目目录 = Path(__file__).resolve().parents[1]
原始文件 = Path(
    r"C:\Users\Administrator\Desktop"
    r"\聚宽实盘分类日线_2025-10-01_2026-10-01.csv"
)
输出文件 = 项目目录 / "数据" / "聚宽因子_2025-10-01_2026-09-30.csv"


def 生成标准因子(数据: pd.DataFrame) -> pd.DataFrame:
    """生成回测统一使用的字段。"""

    结果 = 数据.copy()
    结果 = 结果.rename(
        columns={
            "date": "time",
            "avg": "均价原始",
            "is_limit_up": "是否涨停",
        }
    )
    结果["time"] = pd.to_datetime(结果["time"], errors="coerce")
    结果["code"] = 结果["code"].astype(str)

    数值字段 = [
        "open",
        "close",
        "high",
        "low",
        "volume",
        "money",
        "pre_close",
        "high_limit",
        "low_limit",
        "paused",
        "均价原始",
        "是否涨停",
    ]
    for 字段 in 数值字段:
        结果[字段] = pd.to_numeric(结果[字段], errors="coerce")

    结果["paused"] = 结果["paused"].fillna(0)
    结果["是否涨停"] = 结果["是否涨停"].fillna(0).astype(int)
    结果["成交额_亿"] = 结果["money"] / 100_000_000
    结果["竞价涨幅"] = (
        结果["open"] / 结果["pre_close"] - 1
    ) * 100
    结果["均价"] = 结果["money"] / 结果["volume"]

    结果 = 结果.sort_values(["code", "time"]).reset_index(drop=True)
    分组 = 结果.groupby("code", sort=False)["close"]
    结果["M7"] = 分组.transform(
        lambda 序列: 序列.rolling(7, min_periods=7).mean()
    )
    结果["M14"] = 分组.transform(
        lambda 序列: 序列.rolling(14, min_periods=14).mean()
    )
    结果["实体涨幅"] = (
        结果["close"] / 结果["open"] - 1
    ) * 100
    return 结果.drop(columns=["均价原始"])


def 主程序() -> None:
    """读取原始日线并写入全年标准因子表。"""

    if not 原始文件.exists():
        raise FileNotFoundError(f"找不到原始数据：{原始文件}")
    数据 = pd.read_csv(原始文件, encoding="utf-8-sig")
    结果 = 生成标准因子(数据)
    输出文件.parent.mkdir(parents=True, exist_ok=True)
    结果.to_csv(输出文件, index=False, encoding="utf-8-sig")
    print(f"输出：{输出文件}")
    print(f"形状：{结果.shape}")
    print(f"日期：{结果['time'].min()} 到 {结果['time'].max()}")
    print(f"股票数：{结果['code'].nunique()}")


if __name__ == "__main__":
    主程序()
