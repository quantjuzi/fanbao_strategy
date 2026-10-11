# -*- coding: utf-8 -*-
"""把近一年日线原始数据整理成研究脚本使用的标准因子表。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


项目目录 = Path(__file__).resolve().parents[1]
环境原始目录 = os.environ.get("FANBAO_RAW_DATA_DIR")
输出文件 = 项目目录 / "数据" / "聚宽因子_2026-01-01_2026-09-30.csv"
研究起始 = pd.Timestamp("2026-01-01")
研究结束 = pd.Timestamp("2026-09-30")


def 定位原始文件(原始目录: Path | None = None) -> Path:
    """从指定目录选择最新的聚宽日线原始文件。"""

    候选文件: list[Path] = []
    if 原始目录 is not None and 原始目录.is_file():
        候选文件 = [原始目录]
    elif 原始目录 is not None:
        候选目录 = [原始目录]
    elif 环境原始目录:
        候选目录 = [Path(环境原始目录)]
    else:
        候选目录 = [
            项目目录 / "数据" / "原始",
            Path.home() / "Desktop",
            项目目录 / "数据",
        ]

    if not 候选文件:
        候选文件 = sorted(
            (
                文件路径
                for 目录 in 候选目录
                for 文件路径 in 目录.glob("聚宽实盘分类日线_*.csv")
                if 文件路径.is_file()
            ),
            key=lambda 文件路径: 文件路径.stat().st_mtime,
            reverse=True,
        )
    if not 候选文件:
        已检查目录 = "\n".join(str(目录) for 目录 in 候选目录)
        raise FileNotFoundError(
            "没有找到聚宽原始日线："
            f"\n{已检查目录}\n"
            "请把聚宽实盘分类日线 CSV 放到该目录，"
            "或通过 FANBAO_RAW_DATA_DIR 环境变量/第一个参数指定目录。"
        )
    return 候选文件[0]


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
    结果 = 结果.loc[
        结果["time"].between(研究起始, 研究结束)
    ].copy()
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

    指定目录 = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    原始文件 = 定位原始文件(指定目录)
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
