# -*- coding: utf-8 -*-
"""反包因子研究通用版。

用途：
1. 从标准日线数据构建“涨停后断板”的反包事件；
2. 按下一交易日开盘买入、再下一交易日均价卖出；
3. 加入整手、佣金、印花税、过户费和滑点；
4. 对单个因子做分组统计，输出 Markdown 和 CSV。

这个脚本只用于历史研究，不包含当前实盘使用的核心策略条件。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


项目目录 = Path(__file__).resolve().parents[1]
# 研究入口只读取 2026 标准数据，均线字段由数据准备阶段提前计算。
默认数据文件 = 项目目录 / "数据" / "聚宽因子_2026-01-01_2026-09-30.csv"
默认输出目录 = 项目目录 / "结果" / "反包因子研究_通用版"
研究开始 = pd.Timestamp("2026-01-01")
研究结束 = pd.Timestamp("2026-09-30")


@dataclass(frozen=True)
class 研究参数:
    """交易成本和仓位参数。"""

    每笔资金: float = 20_000.0
    每手股数: int = 100
    佣金费率: float = 0.0001
    最低佣金: float = 5.0
    印花税费率: float = 0.0005
    过户费率: float = 0.00001
    滑点率: float = 0.001
    分组数量: int = 5


必需字段 = {
    "time",
    "code",
    "open",
    "close",
    "high",
    "low",
    "volume",
    "money",
    "pre_close",
    "paused",
    "是否涨停",
    "成交额_亿",
    "竞价涨幅",
}


def 读取数据(文件路径: Path) -> pd.DataFrame:
    """读取标准日线，并检查必要字段。"""

    if not 文件路径.exists():
        raise FileNotFoundError(f"数据文件不存在：{文件路径}")
    数据 = pd.read_csv(文件路径, encoding="utf-8-sig")
    缺失字段 = 必需字段 - set(数据.columns)
    if 缺失字段:
        raise ValueError(f"缺少字段：{sorted(缺失字段)}")
    return 数据


def 清洗数据(原始数据: pd.DataFrame) -> pd.DataFrame:
    """统一类型、交易日序号和基础行情字段。"""

    数据 = 原始数据.copy()
    数据["time"] = pd.to_datetime(数据["time"], errors="coerce")
    数据["code"] = 数据["code"].astype("string").str.strip()

    数值字段 = [
        "open",
        "close",
        "high",
        "low",
        "volume",
        "money",
        "pre_close",
        "paused",
        "是否涨停",
        "成交额_亿",
        "竞价涨幅",
    ]
    for 字段 in 数值字段:
        数据[字段] = pd.to_numeric(数据[字段], errors="coerce")

    交易日历 = (
        数据["time"].dropna().drop_duplicates().sort_values()
    )
    日期位置 = {日期: 位置 for 位置, 日期 in enumerate(交易日历)}
    数据["交易日序号"] = 数据["time"].map(日期位置)

    有效 = (
        数据["time"].notna()
        & 数据["code"].notna()
        & 数据["open"].gt(0)
        & 数据["close"].gt(0)
        & 数据["volume"].gt(0)
        & 数据["money"].gt(0)
        & 数据["paused"].fillna(0).eq(0)
    )
    数据 = 数据.loc[有效].copy()
    数据 = 数据.drop_duplicates(["code", "time"], keep="last")
    数据["实体涨幅"] = (数据["close"] / 数据["open"] - 1) * 100
    数据["成交均价"] = 数据["money"] / 数据["volume"]
    数据["断板日涨跌幅"] = (
        数据["close"] / 数据["pre_close"] - 1
    ) * 100
    return 数据.sort_values(["code", "time"]).reset_index(drop=True)


def 构建反包交易(数据: pd.DataFrame) -> pd.DataFrame:
    """构建断板信号、T+1 买入和 T+2 卖出。"""

    结果 = 数据.copy()
    分组 = 结果.groupby("code", sort=False)

    涨停 = 结果["是否涨停"].fillna(0).astype(int)
    相邻交易日 = 分组["交易日序号"].diff().eq(1)
    连续段 = (~涨停.eq(1) | ~相邻交易日).cumsum()
    结果["连板数"] = 涨停.groupby(连续段).cumsum()

    结果["前一日涨停"] = 分组["是否涨停"].shift(1)
    结果["前一日连板数"] = 分组["连板数"].shift(1)
    结果.loc[
        ~分组["交易日序号"].diff().eq(1),
        ["前一日涨停", "前一日连板数"],
    ] = np.nan
    结果["信号"] = (
        结果["前一日涨停"].eq(1) & 结果["是否涨停"].eq(0)
    ).astype(int)

    候选 = 结果.loc[结果["信号"].eq(1)].copy()
    候选["买入序号"] = 候选["交易日序号"] + 1
    候选["卖出序号"] = 候选["交易日序号"] + 2

    查询表 = 结果[
        ["code", "交易日序号", "time", "open", "成交均价"]
    ].copy()
    买入表 = 查询表.rename(
        columns={
            "交易日序号": "买入序号",
            "time": "买入日期",
            "open": "买入参考价",
        }
    )[["code", "买入序号", "买入日期", "买入参考价"]]
    卖出表 = 查询表.rename(
        columns={
            "交易日序号": "卖出序号",
            "time": "卖出日期",
            "成交均价": "卖出参考价",
        }
    )[["code", "卖出序号", "卖出日期", "卖出参考价"]]

    买入行 = 候选[["code", "买入序号"]].merge(
        买入表,
        on=["code", "买入序号"],
        how="left",
        sort=False,
    )
    卖出行 = 候选[["code", "卖出序号"]].merge(
        卖出表,
        on=["code", "卖出序号"],
        how="left",
        sort=False,
    )
    候选 = pd.concat(
        [
            候选.reset_index(drop=True),
            买入行[
                ["买入日期", "买入参考价"]
            ].reset_index(drop=True),
            卖出行[
                ["卖出日期", "卖出参考价"]
            ].reset_index(drop=True),
        ],
        axis=1,
    )
    return 候选.dropna(
        subset=["买入日期", "买入参考价", "卖出日期", "卖出参考价"]
    ).reset_index(drop=True)


def 计算交易成本(
    交易: pd.DataFrame,
    参数: 研究参数,
) -> pd.DataFrame:
    """按整手、佣金、税费和滑点计算净收益。"""

    结果 = 交易.copy()
    结果["买入价格"] = 结果["买入参考价"] * (1 + 参数.滑点率)
    结果["卖出价格"] = 结果["卖出参考价"] * (1 - 参数.滑点率)
    结果["股数"] = (
        结果["买入价格"]
        .rdiv(参数.每笔资金)
        .floordiv(参数.每手股数)
        .mul(参数.每手股数)
        .astype(int)
    )
    结果 = 结果.loc[结果["股数"].gt(0)].copy()
    结果["买入金额"] = 结果["股数"] * 结果["买入价格"]
    结果["卖出金额"] = 结果["股数"] * 结果["卖出价格"]
    结果["买入佣金"] = np.maximum(
        结果["买入金额"] * 参数.佣金费率,
        参数.最低佣金,
    )
    结果["卖出佣金"] = np.maximum(
        结果["卖出金额"] * 参数.佣金费率,
        参数.最低佣金,
    )
    结果["买入费用"] = (
        结果["买入佣金"] + 结果["买入金额"] * 参数.过户费率
    )
    结果["卖出费用"] = (
        结果["卖出佣金"]
        + 结果["卖出金额"] * 参数.过户费率
        + 结果["卖出金额"] * 参数.印花税费率
    )
    结果["净盈亏"] = (
        结果["卖出金额"]
        - 结果["买入金额"]
        - 结果["买入费用"]
        - 结果["卖出费用"]
    )
    结果["净收益率"] = 结果["净盈亏"] / 结果["买入金额"] * 100
    return 结果


def 限定研究区间(交易: pd.DataFrame) -> pd.DataFrame:
    """只保留 2026 年内的信号交易。"""

    return 交易.loc[
        交易["time"].between(研究开始, 研究结束)
    ].copy()


def 计算资金占用(
    交易: pd.DataFrame,
    交易日历: pd.Series,
    参数: 研究参数,
) -> tuple[float, float]:
    """计算最高资金占用和平均交易日占用资金。"""

    日期位置 = {
        日期: 位置
        for 位置, 日期 in enumerate(
            pd.to_datetime(交易日历).sort_values().drop_duplicates()
        )
    }
    事件 = np.zeros(len(日期位置) + 1, dtype=int)
    for _, 行 in 交易.iterrows():
        买入日 = pd.Timestamp(行["买入日期"]).normalize()
        卖出日 = pd.Timestamp(行["卖出日期"]).normalize()
        if 买入日 not in 日期位置 or 卖出日 not in 日期位置:
            raise ValueError("买卖日期不在交易日历内。")
        事件[日期位置[买入日]] += 1
        事件[日期位置[卖出日] + 1] -= 1
    每日持仓 = np.cumsum(事件[:-1])
    return (
        float(每日持仓.max() * 参数.每笔资金),
        float(每日持仓.mean() * 参数.每笔资金),
    )


def 计算分组指标(
    名称: str,
    样本: pd.DataFrame,
    交易日历: pd.Series,
    参数: 研究参数,
) -> dict[str, object]:
    """计算一个因子分组的核心指标。"""

    if 样本.empty:
        return {"分组": 名称, "交易数": 0}
    盈利 = 样本.loc[样本["净收益率"].gt(0), "净收益率"]
    亏损 = 样本.loc[样本["净收益率"].lt(0), "净收益率"]
    总盈亏 = float(样本["净盈亏"].sum())
    最高资金占用, 平均资金占用 = 计算资金占用(
        样本,
        交易日历,
        参数,
    )
    交易天数 = int(pd.to_datetime(交易日历).nunique())
    最高资金收益率 = (
        总盈亏 / 最高资金占用 if 最高资金占用 > 0 else 0.0
    )
    平均资金收益率 = (
        总盈亏 / 平均资金占用 if 平均资金占用 > 0 else 0.0
    )

    def 年化(收益率: float) -> float:
        if 交易天数 <= 0 or 收益率 <= -1:
            return np.nan
        return ((1 + 收益率) ** (252 / 交易天数) - 1) * 100

    return {
        "分组": 名称,
        "交易数": len(样本),
        "净胜率": float(样本["净收益率"].gt(0).mean() * 100),
        "平均净收益率": float(样本["净收益率"].mean()),
        "平均盈利": float(盈利.mean()) if not 盈利.empty else 0.0,
        "平均亏损": float(亏损.mean()) if not 亏损.empty else 0.0,
        "盈亏比": (
            float(盈利.mean() / abs(亏损.mean()))
            if not 盈利.empty and not 亏损.empty
            else np.nan
        ),
        "累计净盈亏": 总盈亏,
        "最高资金占用": 最高资金占用,
        "平均资金占用": 平均资金占用,
        "最高资金年化": 年化(最高资金收益率),
        "平均资金年化": 年化(平均资金收益率),
    }


def 因子分组(
    交易: pd.DataFrame,
    因子: str,
    参数: 研究参数,
) -> list[tuple[str, pd.DataFrame]]:
    """按因子生成分组。连板数直接分档，连续因子按分位数分箱。"""

    if 因子 not in 交易.columns:
        raise ValueError(f"交易数据没有因子列：{因子}")
    if 因子 == "连板数":
        数据 = 交易.copy()
        数据["分组"] = pd.cut(
            数据[因子],
            bins=[-np.inf, 2, 3, 4, np.inf],
            labels=["1板", "2板", "3板", "4板及以上"],
            right=False,
        )
        return [
            (str(名称), 数据.loc[数据["分组"].eq(名称)])
            for 名称 in ["1板", "2板", "3板", "4板及以上"]
        ]

    数据 = 交易.dropna(subset=[因子]).copy()
    try:
        数据["分组"] = pd.qcut(
            数据[因子],
            q=参数.分组数量,
            duplicates="drop",
        )
    except ValueError:
        数据["分组"] = 数据[因子]
    结果 = []
    for 分组值, 样本 in 数据.groupby("分组", observed=True, sort=True):
        名称 = (
            f"{分组值.left:.2f} 到 {分组值.right:.2f}"
            if hasattr(分组值, "left")
            else str(分组值)
        )
        结果.append((名称, 样本))
    return 结果


def 写Markdown(数据: pd.DataFrame) -> str:
    """不依赖额外库，把结果写成 Markdown 表格。"""

    列名 = [str(列) for 列 in 数据.columns]
    内容 = [
        "| " + " | ".join(列名) + " |",
        "| " + " | ".join("---" for _ in 列名) + " |",
    ]
    for 行 in 数据.itertuples(index=False, name=None):
        单元格 = [
            "" if pd.isna(值) else str(值)
            for 值 in 行
        ]
        内容.append("| " + " | ".join(单元格) + " |")
    return "\n".join(内容)


def 解析参数() -> argparse.Namespace:
    """读取命令行参数。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factor-file", type=Path, default=默认数据文件)
    parser.add_argument("--output-dir", type=Path, default=默认输出目录)
    parser.add_argument(
        "--factor",
        default="成交额_亿",
        choices=[
            "成交额_亿",
            "实体涨幅",
            "断板日涨跌幅",
            "竞价涨幅",
            "连板数",
        ],
    )
    return parser.parse_args()


def main() -> None:
    """执行反包因子分组研究。"""

    参数值 = 解析参数()
    参数 = 研究参数()
    原始数据 = 读取数据(参数值.factor_file)
    数据 = 清洗数据(原始数据)
    交易 = 构建反包交易(数据)
    交易 = 限定研究区间(交易)
    交易 = 计算交易成本(交易, 参数)

    if 交易.empty:
        print("没有可统计的反包交易。")
        return

    交易日历 = (
        数据.loc[
            数据["time"].between(研究开始, 研究结束),
            "time",
        ]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    汇总行 = [
        计算分组指标(名称, 样本, 交易日历, 参数)
        for 名称, 样本 in 因子分组(交易, 参数值.factor, 参数)
    ]
    汇总 = pd.DataFrame(汇总行)

    参数值.output_dir.mkdir(parents=True, exist_ok=True)
    csv路径 = 参数值.output_dir / f"{参数值.factor}_分组统计.csv"
    md路径 = 参数值.output_dir / f"{参数值.factor}_分组统计.md"
    汇总.to_csv(csv路径, index=False, encoding="utf-8-sig")
    md路径.write_text(
        f"# 反包因子分组：{参数值.factor}\n\n"
        "- 研究区间：2026-01-01 至 2026-09-30\n"
        f"- 研究样本：{len(交易)} 笔\n"
        f"- 成本：整手、佣金、印花税、过户费、滑点\n\n"
        + 写Markdown(汇总),
        encoding="utf-8",
    )
    print(汇总.to_string(index=False))
    print(f"\n输出：{csv路径}")
    print(f"输出：{md路径}")


if __name__ == "__main__":
    main()
