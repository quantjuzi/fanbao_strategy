# -*- coding: utf-8 -*-
'''比较几个反包候选版本的固定2万元资金收益和周转需求。'''

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pandas as pd

from 连板断板统计 import consecutive_limit_count
from 连板断板指数统计 import fetch_shenzhen_index


PROJECT_DIR = Path(__file__).resolve().parents[1]
STRATEGY_PATH = PROJECT_DIR / '脚本' / '高开均线完整回测.py'
DATA_PATH = PROJECT_DIR / '数据' / '聚宽因子_2026-01-01_2026-09-30.csv'
OUTPUT_PATH = (
    Path(r'C:\Users\Administrator\PyCharmMiscProject')
    / '高开均线完整输出'
    / '反包核心版本_固定2万资金对比.csv'
)


def load_strategy_module(path: Path) -> ModuleType:
    '''动态导入主策略模块。'''

    spec = importlib.util.spec_from_file_location('资金对比实验模块', path)
    if spec is None or spec.loader is None:
        raise ImportError(f'无法导入策略模块：{path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def max_concurrent_positions(
    trades: pd.DataFrame,
    trading_dates: pd.Series,
) -> int:
    '''按买入日到卖出日占用资金，计算最高并发持仓数。'''

    if trades.empty:
        return 0

    starts = pd.to_datetime(trades['买入日期'])
    ends = pd.to_datetime(trades['卖出日期'])
    calendar = (
        pd.to_datetime(trading_dates)
        .drop_duplicates()
        .sort_values()
    )
    max_count = 0
    for date in calendar:
        count = int(
            (starts.le(date) & ends.ge(date)).sum()
        )
        max_count = max(max_count, count)
    return max_count


def main() -> None:
    '''生成资金周转对比结果。'''

    strategy = load_strategy_module(STRATEGY_PATH)
    config = strategy.策略参数()
    raw = strategy.读取数据(DATA_PATH)
    df, _ = strategy.清洗数据(raw)
    df = strategy.计算因子(df)
    df = df.merge(fetch_shenzhen_index(), on='time', how='left')

    grouped = df.groupby('code', sort=False)
    df['连板数'] = grouped['是否涨停'].transform(consecutive_limit_count)
    df['前一日连板数'] = grouped['连板数'].shift(1)
    df['前一日涨停'] = grouped['是否涨停'].shift(1)
    df['涨停日深证成指上涨'] = grouped['深证成指上涨'].shift(1)
    df['涨停日深证成指阳线'] = grouped['深证成指阳线'].shift(1)
    df['信号'] = (
        df['前一日涨停'].eq(1)
        & df['是否涨停'].eq(0)
    ).astype(int)

    trades = strategy.确定买卖规则(df)
    trades = strategy.计算交易成本(trades, config)
    trades['前一日连板数'] = trades['前一日连板数'].fillna(0).astype(int)

    base_index = trades['涨停日深证成指上涨'].eq(1)
    base_index_bullish = trades['涨停日深证成指阳线'].eq(1)
    core_amount = trades['成交额_亿'].between(10, 40, inclusive='left')
    best_amount = trades['成交额_亿'].between(20, 40, inclusive='left')
    mid_index = trades['指数涨幅'].between(-1, 2, inclusive='left')

    variants = [
        (
            '191版：全市场+指数上涨+实体>3+20到40亿',
            trades.loc[
                base_index
                & trades['实体涨幅'].gt(3)
                & best_amount
            ],
        ),
        (
            '142版：191版+断板日指数-1%到2%',
            trades.loc[
                base_index
                & trades['实体涨幅'].gt(3)
                & best_amount
                & mid_index
            ],
        ),
        (
            '67版：2连板以上+实体>3+20到40亿',
            trades.loc[
                trades['前一日连板数'].ge(2)
                & trades['实体涨幅'].gt(3)
                & best_amount
            ],
        ),
        (
            '实体>2版：2连板以上+实体>2+20到40亿',
            trades.loc[
                trades['前一日连板数'].ge(2)
                & trades['实体涨幅'].gt(2)
                & best_amount
            ],
        ),
        (
            '67版+深证成指上涨：2连板以上+实体>3+20到40亿',
            trades.loc[
                trades['前一日连板数'].ge(2)
                & trades['实体涨幅'].gt(3)
                & best_amount
                & base_index
            ],
        ),
        (
            '67版+深证成指阳线：2连板以上+实体>3+20到40亿',
            trades.loc[
                trades['前一日连板数'].ge(2)
                & trades['实体涨幅'].gt(3)
                & best_amount
                & base_index_bullish
            ],
        ),
        (
            '67版+指数上涨+指数阳线',
            trades.loc[
                trades['前一日连板数'].ge(2)
                & trades['实体涨幅'].gt(3)
                & best_amount
                & base_index
                & base_index_bullish
            ],
        ),
        (
            '45版：2连板以上+指数环境+阳线+20到40亿',
            trades.loc[
                trades['前一日连板数'].ge(2)
                & base_index
                & trades['实体涨幅'].gt(0)
                & best_amount
                & mid_index
            ],
        ),
        (
            '29版：2连板以上+指数环境+实体>3+20到40亿',
            trades.loc[
                trades['前一日连板数'].ge(2)
                & base_index
                & trades['实体涨幅'].gt(3)
                & best_amount
                & mid_index
            ],
        ),
    ]

    rows: list[dict[str, float | str]] = []
    trading_dates = df['time']
    for name, sample in variants:
        sample = sample.copy()
        sample['盈利金额_2万'] = sample['净收益率'] * 20_000 / 100
        total_profit = float(sample['盈利金额_2万'].sum())
        max_positions = max_concurrent_positions(
            sample,
            trading_dates,
        )
        capital = max_positions * 20_000
        interval_return = (
            total_profit / capital
            if capital > 0
            else 0.0
        )
        first_buy = pd.to_datetime(sample['买入日期']).min()
        last_sell = pd.to_datetime(sample['卖出日期']).max()
        trading_days = int(
            pd.to_datetime(trading_dates)
            .drop_duplicates()
            .loc[lambda values: values.between(first_buy, last_sell)]
            .nunique()
        )
        annual_simple = (
            interval_return * 252 / trading_days * 100
            if trading_days > 0
            else 0.0
        )
        annual_compound = (
            ((1 + interval_return) ** (252 / trading_days) - 1) * 100
            if trading_days > 0
            else 0.0
        )
        rows.append(
            {
                '版本': name,
                '交易数': int(len(sample)),
                '净胜率': float((sample['净收益率'] > 0).mean() * 100),
                '平均净收益率': float(sample['净收益率'].mean()),
                '总盈利_2万每笔': total_profit,
                '最高并发持仓': max_positions,
                '所需周转资金': capital,
                '资金回报率': (
                    interval_return * 100
                ),
                '区间交易日数': trading_days,
                '简单年化收益率': annual_simple,
                '复利年化收益率': annual_compound,
            }
        )

    result = pd.DataFrame(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')

    print('\n固定2万元资金版本对比：')
    print(result.to_string(index=False))
    print(f'\n结果已保存：{OUTPUT_PATH}')


if __name__ == '__main__':
    main()
