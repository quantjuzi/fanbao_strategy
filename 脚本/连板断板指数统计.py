# -*- coding: utf-8 -*-
'''在连板后断板策略中加入深证成指上涨条件。'''

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import baostock as bs
import pandas as pd

from 连板断板统计 import consecutive_limit_count, metric_row


PROJECT_DIR = Path(__file__).resolve().parents[1]
STRATEGY_PATH = PROJECT_DIR / '脚本' / '高开均线完整回测.py'
DATA_PATH = PROJECT_DIR / '数据' / '聚宽因子_2025-10-01_2026-09-30.csv'
OUTPUT_PATH = (
    Path(r'C:\Users\Administrator\PyCharmMiscProject')
    / '高开均线完整输出'
    / '连板后断板_深证成指上涨_胜率.csv'
)


def load_strategy_module(path: Path) -> ModuleType:
    '''动态导入主策略模块。'''

    spec = importlib.util.spec_from_file_location('市场过滤实验模块', path)
    if spec is None or spec.loader is None:
        raise ImportError(f'无法导入策略模块：{path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fetch_shenzhen_index() -> pd.DataFrame:
    '''获取深证成指日线。'''

    login = bs.login()
    if login.error_code != '0':
        raise RuntimeError(login.error_msg)
    try:
        result = bs.query_history_k_data_plus(
            'sz.399001',
            'date,open,close,preclose,pctChg',
            start_date='2025-12-01',
            end_date='2026-09-30',
            frequency='d',
            adjustflag='3',
        )
        rows = []
        while result.next():
            rows.append(result.get_row_data())
    finally:
        bs.logout()

    index_df = pd.DataFrame(
        rows,
        columns=['time', '指数开盘', '指数收盘', '指数昨收', '指数涨幅'],
    )
    index_df['time'] = pd.to_datetime(index_df['time'])
    index_df['指数开盘'] = pd.to_numeric(
        index_df['指数开盘'],
        errors='coerce',
    )
    index_df['指数收盘'] = pd.to_numeric(
        index_df['指数收盘'],
        errors='coerce',
    )
    index_df['指数涨幅'] = pd.to_numeric(
        index_df['指数涨幅'],
        errors='coerce',
    )
    index_df['深证成指上涨'] = index_df['指数涨幅'].gt(0).astype(int)
    index_df['深证成指阳线'] = (
        index_df['指数收盘'].gt(index_df['指数开盘'])
    ).astype(int)
    return index_df[
        ['time', '指数涨幅', '深证成指上涨', '深证成指阳线']
    ]


def main() -> None:
    '''运行市场过滤后的断板反包统计。'''

    strategy = load_strategy_module(STRATEGY_PATH)
    config = strategy.策略参数()
    raw = strategy.读取数据(DATA_PATH)
    df, _ = strategy.清洗数据(raw)
    df = strategy.计算因子(df)

    index_df = fetch_shenzhen_index()
    df = df.merge(index_df, on='time', how='left')

    grouped = df.groupby('code', sort=False)
    df['连板数'] = grouped['是否涨停'].transform(consecutive_limit_count)
    df['前一日连板数'] = grouped['连板数'].shift(1)
    df['前一日涨停'] = grouped['是否涨停'].shift(1)

    # 最后涨停日的深证成指状态，信号在断板日收盘后确认。
    df['涨停日深证成指上涨'] = grouped['深证成指上涨'].shift(1)
    df['断板信号'] = (
        df['是否涨停'].eq(0)
        & df['前一日涨停'].eq(1)
        & df['前一日连板数'].ge(2)
    ).astype(int)
    df['信号'] = df['断板信号']

    trades = strategy.确定买卖规则(df)
    trades = strategy.计算交易成本(trades, config)
    trades['断板前连板数'] = trades['前一日连板数']
    trades['涨停日深证成指上涨'] = trades['涨停日深证成指上涨']

    variants = [
        ('全部连板后断板', trades),
        (
            '涨停日深证成指上涨',
            trades.loc[trades['涨停日深证成指上涨'].eq(1)],
        ),
        (
            '涨停日深证成指下跌',
            trades.loc[trades['涨停日深证成指上涨'].eq(0)],
        ),
        (
            '指数上涨+实体大于0',
            trades.loc[
                trades['涨停日深证成指上涨'].eq(1)
                & trades['实体涨幅'].gt(0)
            ],
        ),
        (
            '指数上涨+成交额10到40亿',
            trades.loc[
                trades['涨停日深证成指上涨'].eq(1)
                & trades['成交额_亿'].between(10, 40, inclusive='left')
            ],
        ),
        (
            '指数上涨+实体大于3+成交额20到40亿',
            trades.loc[
                trades['涨停日深证成指上涨'].eq(1)
                & trades['实体涨幅'].gt(3)
                & trades['成交额_亿'].between(20, 40, inclusive='left')
            ],
        ),
    ]

    result = pd.DataFrame(
        metric_row(name, sample)
        for name, sample in variants
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')

    print('\n深证成指过滤后的连板断板统计：')
    print(result.to_string(index=False))
    print(f'\n结果已保存：{OUTPUT_PATH}')


if __name__ == '__main__':
    main()
