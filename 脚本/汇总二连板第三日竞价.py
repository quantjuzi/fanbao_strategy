# -*- coding: utf-8 -*-
'''统计二连板第三日竞价<2%分组下的完整绩效。'''

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pandas as pd

from 资金周转对比 import max_concurrent_positions


PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE = (
    Path(r'C:\Users\Administrator\PyCharmMiscProject')
    / '高开均线完整输出'
    / '二连板及以上低竞价_前两日开板明细.csv'
)
OUTPUT = SOURCE.with_name('二连板低竞价_第三日竞价区间_绩效.csv')
BOTH_OPEN_OUTPUT = SOURCE.with_name(
    '二连板低竞价_两天都开板_第三日竞价区间_绩效.csv'
)
BOTH_OPEN_AMOUNT_OUTPUT = SOURCE.with_name(
    '二连板低竞价_两天都开板_第二天成交额_绩效.csv'
)


def load_strategy_module(path: Path) -> ModuleType:
    '''动态导入主策略模块。'''

    spec = importlib.util.spec_from_file_location('竞价区间统计模块', path)
    if spec is None or spec.loader is None:
        raise ImportError(f'无法导入策略模块：{path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def calculate_metrics(
    name: str,
    trades: pd.DataFrame,
    trading_dates: pd.Series,
) -> dict[str, float | str]:
    """计算一组交易的完整绩效。"""

    if trades.empty:
        return {
            '第三日竞价区间': name,
            '交易数': 0,
        }

    winners = trades.loc[trades['净收益率'] > 0, '净收益率']
    losers = trades.loc[trades['净收益率'] < 0, '净收益率']
    sample = trades.copy()
    sample['盈利金额_2万'] = sample['净收益率'] * 20_000 / 100
    total_profit = float(sample['盈利金额_2万'].sum())
    max_positions = max_concurrent_positions(
        sample,
        trading_dates,
    )
    capital = max_positions * 20_000
    interval_return = total_profit / capital if capital > 0 else 0.0
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
    annual_profit = capital * annual_compound / 100

    return {
        '第三日竞价区间': name,
        '交易数': int(len(sample)),
        '净胜率': float((sample['净收益率'] > 0).mean() * 100),
        '平均净收益率': float(sample['净收益率'].mean()),
        '平均盈利': float(winners.mean()) if not winners.empty else 0.0,
        '平均亏损': float(losers.mean()) if not losers.empty else 0.0,
        '盈亏比': (
            float(winners.mean() / abs(losers.mean()))
            if not winners.empty and not losers.empty
            else 0.0
        ),
        '总盈利_2万每笔': total_profit,
        '最高并发持仓': max_positions,
        '所需周转资金': capital,
        '区间资金收益率': interval_return * 100,
        '简单年化收益率': annual_simple,
        '复利年化收益率': annual_compound,
        '按周转资金年化利润': annual_profit,
    }


def main() -> None:
    """执行竞价区间绩效统计。"""

    strategy = load_strategy_module(
        PROJECT_DIR / '脚本' / '高开均线完整回测.py'
    )
    data = pd.read_csv(SOURCE, encoding='utf-8-sig')
    data = data.loc[data['竞价涨幅'].lt(2)].copy()
    data['第三日竞价区间'] = pd.cut(
        data['竞价涨幅'],
        bins=[-float('inf'), -2, 0, 2],
        labels=['低于-2%', '-2%到0%', '0%到2%'],
        right=False,
    )
    trading_dates = pd.read_csv(
        PROJECT_DIR / '数据' / '聚宽因子_2026-01-01_2026-09-30.csv',
        encoding='utf-8-sig',
        usecols=['time'],
    )['time']

    result = pd.DataFrame(
        calculate_metrics(
            name,
            data.loc[data['第三日竞价区间'].eq(name)],
            trading_dates,
        )
        for name in ['低于-2%', '-2%到0%', '0%到2%']
    )
    result.to_csv(OUTPUT, index=False, encoding='utf-8-sig')
    print(result.to_string(index=False))
    print(f'结果已保存：{OUTPUT}')

    both_open = data.loc[
        data['第一天是否开板'].astype(str).isin(['True', 'true', '1'])
        & data['第二天是否开板'].astype(str).isin(['True', 'true', '1'])
    ].copy()
    both_open_result = pd.DataFrame(
        calculate_metrics(
            name,
            both_open.loc[both_open['第三日竞价区间'].eq(name)],
            trading_dates,
        )
        for name in ['低于-2%', '-2%到0%', '0%到2%']
    )
    both_open_result.to_csv(
        BOTH_OPEN_OUTPUT,
        index=False,
        encoding='utf-8-sig',
    )
    print('\n两天都开板的第三日竞价区间绩效：')
    print(both_open_result.to_string(index=False))
    print(f'结果已保存：{BOTH_OPEN_OUTPUT}')

    both_open['成交额区间'] = pd.cut(
        both_open['第二天成交额_亿'],
        bins=[-float('inf'), 5, 10, 20, 40, float('inf')],
        labels=['小于5亿', '5到10亿', '10到20亿', '20到40亿', '大于40亿'],
        right=False,
    )
    amount_result = pd.DataFrame(
        calculate_metrics(
            name,
            both_open.loc[both_open['成交额区间'].eq(name)],
            trading_dates,
        )
        for name in ['小于5亿', '5到10亿', '10到20亿', '20到40亿', '大于40亿']
    )
    amount_result = amount_result.rename(
        columns={'第三日竞价区间': '第二天成交额区间'}
    )
    amount_result.to_csv(
        BOTH_OPEN_AMOUNT_OUTPUT,
        index=False,
        encoding='utf-8-sig',
    )
    print('\n两天都开板 + 第三日竞价低于2%，按第二天成交额：')
    print(amount_result.to_string(index=False))
    print(f'结果已保存：{BOTH_OPEN_AMOUNT_OUTPUT}')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
