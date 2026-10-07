# -*- coding: utf-8 -*-
'''统计连板后断板的胜率，并按连板数和断板实体涨幅分组。'''

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
STRATEGY_PATH = PROJECT_DIR / '脚本' / '高开均线完整回测.py'
DATA_PATH = PROJECT_DIR / '数据' / '聚宽因子_2025-10-01_2026-09-30.csv'
OUTPUT_DIR = (
    Path(r'C:\Users\Administrator\PyCharmMiscProject')
    / '高开均线完整输出'
)


def load_strategy_module(path: Path) -> ModuleType:
    '''动态导入主策略模块。'''

    spec = importlib.util.spec_from_file_location('断板实验模块', path)
    if spec is None or spec.loader is None:
        raise ImportError(f'无法导入策略模块：{path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def consecutive_limit_count(values: pd.Series) -> pd.Series:
    '''计算连续的涨停天数。'''

    limit = values.fillna(0).astype(int)
    blocks = limit.eq(0).cumsum()
    return limit.groupby(blocks).cumsum()


def metric_row(
    name: str,
    trades: pd.DataFrame,
) -> dict[str, float | str]:
    '''把一组交易转换成统计行。'''

    if trades.empty:
        return {
            '分组': name,
            '交易数': 0,
            '净胜率': 0.0,
            '平均净收益率': 0.0,
            '平均盈利': 0.0,
            '平均亏损': 0.0,
            '盈亏比': 0.0,
            '净利润因子': 0.0,
        }

    winners = trades.loc[trades['净收益率'] > 0, '净收益率']
    losers = trades.loc[trades['净收益率'] < 0, '净收益率']
    profit = winners.sum()
    loss = abs(losers.sum())
    return {
        '分组': name,
        '交易数': int(len(trades)),
        '净胜率': float((trades['净收益率'] > 0).mean() * 100),
        '平均净收益率': float(trades['净收益率'].mean()),
        '平均盈利': float(winners.mean()) if not winners.empty else 0.0,
        '平均亏损': float(losers.mean()) if not losers.empty else 0.0,
        '盈亏比': (
            float(winners.mean() / abs(losers.mean()))
            if not winners.empty and not losers.empty
            else 0.0
        ),
        '净利润因子': float(profit / loss) if loss > 0 else 0.0,
    }


def main() -> None:
    '''执行断板统计。'''

    strategy = load_strategy_module(STRATEGY_PATH)
    config = strategy.策略参数()
    raw = strategy.读取数据(DATA_PATH)
    df, _ = strategy.清洗数据(raw)
    df = strategy.计算因子(df)

    grouped = df.groupby('code', sort=False)
    df['连板数'] = grouped['是否涨停'].transform(consecutive_limit_count)
    df['前一日连板数'] = grouped['连板数'].shift(1)
    df['前一日涨停'] = grouped['是否涨停'].shift(1)

    # 当天断板，前一天是最后一板，且前一天至少有 2 连板。
    df['断板信号'] = (
        df['是否涨停'].eq(0)
        & df['前一日涨停'].eq(1)
        & df['前一日连板数'].ge(2)
    ).astype(int)
    df['信号'] = df['断板信号']

    trades = strategy.确定买卖规则(df)
    trades = strategy.计算交易成本(trades, config)
    trades['断板前连板数'] = trades['前一日连板数']

    board_groups = [
        ('全部连板后断板', trades),
        ('2连板后断板', trades.loc[trades['断板前连板数'].eq(2)]),
        ('3连板后断板', trades.loc[trades['断板前连板数'].eq(3)]),
        ('4连板及以上后断板', trades.loc[trades['断板前连板数'].ge(4)]),
    ]
    board_result = pd.DataFrame(
        metric_row(name, sample)
        for name, sample in board_groups
    )

    entity_bins = [-float('inf'), -5, 0, 3, 6, float('inf')]
    entity_labels = [
        '小于-5%',
        '-5%到0%',
        '0%到3%',
        '3%到6%',
        '大于6%',
    ]
    trades['断板实体区间'] = pd.cut(
        trades['实体涨幅'],
        bins=entity_bins,
        labels=entity_labels,
        right=False,
    )
    entity_result = pd.DataFrame(
        metric_row(name, trades.loc[trades['断板实体区间'].eq(name)])
        for name in entity_labels
    )

    # 只统计断板日实体涨幅大于 0 的样本。
    strong_trades = trades.loc[trades['实体涨幅'].gt(0)].copy()
    strong_trades['成交额区间'] = pd.cut(
        strong_trades['成交额_亿'],
        bins=[-float('inf'), 5, 10, 20, 40, float('inf')],
        labels=['小于5亿', '5到10亿', '10到20亿', '20到40亿', '大于40亿'],
        right=False,
    )
    strong_trades['位置'] = strong_trades['close'] / strong_trades['M14']
    strong_trades['位置区间'] = pd.cut(
        strong_trades['位置'],
        bins=[-float('inf'), 1, 1.03, 1.06, float('inf')],
        labels=['低于M14', 'M14到1.03', '1.03到1.06', '高于1.06'],
        right=False,
    )

    amount_labels = ['小于5亿', '5到10亿', '10到20亿', '20到40亿', '大于40亿']
    position_labels = ['低于M14', 'M14到1.03', '1.03到1.06', '高于1.06']
    amount_result = pd.DataFrame(
        metric_row(name, strong_trades.loc[strong_trades['成交额区间'].eq(name)])
        for name in amount_labels
    )
    position_result = pd.DataFrame(
        metric_row(name, strong_trades.loc[strong_trades['位置区间'].eq(name)])
        for name in position_labels
    )

    # 在实体涨幅大于 0 且成交额 10 到 40 亿的样本中，
    # 再比较 2 连板和 3 连板及以上。
    mid_amount = strong_trades.loc[
        strong_trades['成交额_亿'].between(10, 40, inclusive='left')
    ].copy()
    mid_board_groups = [
        ('10到40亿-2连板后断板', mid_amount.loc[mid_amount['断板前连板数'].eq(2)]),
        ('10到40亿-3连板及以上后断板', mid_amount.loc[mid_amount['断板前连板数'].ge(3)]),
        ('10到40亿-3连板后断板', mid_amount.loc[mid_amount['断板前连板数'].eq(3)]),
        ('10到40亿-4连板及以上后断板', mid_amount.loc[mid_amount['断板前连板数'].ge(4)]),
    ]
    mid_board_result = pd.DataFrame(
        metric_row(name, sample)
        for name, sample in mid_board_groups
    )

    # 断板日实体涨幅大于 +2% 的阳线样本，再按成交额细分。
    plus2_trades = trades.loc[trades['实体涨幅'].gt(2)].copy()
    plus2_trades['成交额区间'] = pd.cut(
        plus2_trades['成交额_亿'],
        bins=[-float('inf'), 5, 10, 20, 40, float('inf')],
        labels=['小于5亿', '5到10亿', '10到20亿', '20到40亿', '大于40亿'],
        right=False,
    )
    plus2_amount_result = pd.DataFrame(
        metric_row(name, plus2_trades.loc[
            plus2_trades['成交额区间'].eq(name)
        ])
        for name in amount_labels
    )

    plus2_trades['实体区间'] = pd.cut(
        plus2_trades['实体涨幅'],
        bins=[2, 3, 6, float('inf')],
        labels=['2%到3%', '3%到6%', '大于6%'],
        right=False,
    )
    plus2_entity_result = pd.DataFrame(
        metric_row(name, plus2_trades.loc[plus2_trades['实体区间'].eq(name)])
        for name in ['2%到3%', '3%到6%', '大于6%']
    )

    plus3_trades = trades.loc[trades['实体涨幅'].gt(3)].copy()
    plus3_trades['成交额区间'] = pd.cut(
        plus3_trades['成交额_亿'],
        bins=[-float('inf'), 5, 10, 20, 40, float('inf')],
        labels=['小于5亿', '5到10亿', '10到20亿', '20到40亿', '大于40亿'],
        right=False,
    )
    plus3_amount_result = pd.DataFrame(
        metric_row(name, plus3_trades.loc[
            plus3_trades['成交额区间'].eq(name)
        ])
        for name in amount_labels
    )

    plus3_trades['实体区间'] = pd.cut(
        plus3_trades['实体涨幅'],
        bins=[3, 6, float('inf')],
        labels=['3%到6%', '大于6%'],
        right=False,
    )
    plus3_entity_result = pd.DataFrame(
        metric_row(name, plus3_trades.loc[plus3_trades['实体区间'].eq(name)])
        for name in ['3%到6%', '大于6%']
    )

    plus3_mid_amount = plus3_trades.loc[
        plus3_trades['成交额_亿'].between(20, 40, inclusive='left')
    ].copy()
    detail_columns = [
        'time',
        'code',
        '断板前连板数',
        '实体涨幅',
        '成交额_亿',
        '买入日期',
        '买入参考价',
        '买入成交价',
        '卖出日期',
        '卖出参考价',
        '卖出成交价',
        '净收益率',
        '净盈亏金额',
    ]
    plus3_mid_amount = plus3_mid_amount[detail_columns].sort_values(
        ['time', 'code']
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    board_path = OUTPUT_DIR / '连板后断板胜率_连板数.csv'
    entity_path = OUTPUT_DIR / '连板后断板胜率_实体涨幅.csv'
    strong_amount_path = OUTPUT_DIR / '连板后断板_实体大于0_成交额.csv'
    strong_position_path = OUTPUT_DIR / '连板后断板_实体大于0_位置.csv'
    mid_board_path = OUTPUT_DIR / '连板后断板_实体大于0_10到40亿_连板数.csv'
    plus2_amount_path = OUTPUT_DIR / '连板后断板_实体大于2_成交额.csv'
    plus2_entity_path = OUTPUT_DIR / '连板后断板_实体大于2_实体细分.csv'
    plus3_amount_path = OUTPUT_DIR / '连板后断板_实体大于3_成交额.csv'
    plus3_entity_path = OUTPUT_DIR / '连板后断板_实体大于3_实体细分.csv'
    plus3_detail_path = (
        OUTPUT_DIR
        / '连板后断板_实体大于3_成交额20到40亿_交易明细.csv'
    )
    board_result.to_csv(board_path, index=False, encoding='utf-8-sig')
    entity_result.to_csv(entity_path, index=False, encoding='utf-8-sig')
    amount_result.to_csv(
        strong_amount_path,
        index=False,
        encoding='utf-8-sig',
    )
    position_result.to_csv(
        strong_position_path,
        index=False,
        encoding='utf-8-sig',
    )
    mid_board_result.to_csv(
        mid_board_path,
        index=False,
        encoding='utf-8-sig',
    )
    plus2_amount_result.to_csv(
        plus2_amount_path,
        index=False,
        encoding='utf-8-sig',
    )
    plus2_entity_result.to_csv(
        plus2_entity_path,
        index=False,
        encoding='utf-8-sig',
    )
    plus3_amount_result.to_csv(
        plus3_amount_path,
        index=False,
        encoding='utf-8-sig',
    )
    plus3_entity_result.to_csv(
        plus3_entity_path,
        index=False,
        encoding='utf-8-sig',
    )
    plus3_mid_amount.to_csv(
        plus3_detail_path,
        index=False,
        encoding='utf-8-sig',
    )

    print('\n按断板前连板数统计：')
    print(board_result.to_string(index=False))
    print('\n按断板日实体涨幅统计：')
    print(entity_result.to_string(index=False))
    print('\n实体涨幅大于0，按成交额统计：')
    print(amount_result.to_string(index=False))
    print('\n实体涨幅大于0，按位置统计：')
    print(position_result.to_string(index=False))
    print('\n实体涨幅大于0，成交额10到40亿，按连板数统计：')
    print(mid_board_result.to_string(index=False))
    print('\n实体涨幅大于2，按实体细分：')
    print(plus2_entity_result.to_string(index=False))
    print('\n实体涨幅大于2，按成交额统计：')
    print(plus2_amount_result.to_string(index=False))
    print('\n实体涨幅大于3，按实体细分：')
    print(plus3_entity_result.to_string(index=False))
    print('\n实体涨幅大于3，按成交额统计：')
    print(plus3_amount_result.to_string(index=False))
    print('\n实体大于3且成交额20到40亿的交易明细：')
    print(plus3_mid_amount.to_string(index=False))
    print(f'\n结果已保存：{board_path}')
    print(f'结果已保存：{entity_path}')
    print(f'结果已保存：{strong_amount_path}')
    print(f'结果已保存：{strong_position_path}')
    print(f'结果已保存：{mid_board_path}')
    print(f'结果已保存：{plus2_amount_path}')
    print(f'结果已保存：{plus2_entity_path}')
    print(f'结果已保存：{plus3_amount_path}')
    print(f'结果已保存：{plus3_entity_path}')
    print(f'结果已保存：{plus3_detail_path}')


if __name__ == '__main__':
    main()
