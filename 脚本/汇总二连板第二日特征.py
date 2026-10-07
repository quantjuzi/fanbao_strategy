# -*- coding: utf-8 -*-
'''统计所有二连板及以上、第三天低竞价买入样本的第二天特征。'''

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from 汇总二连板第三日竞价 import calculate_metrics


PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE = (
    Path(r'C:\Users\Administrator\PyCharmMiscProject')
    / '高开均线完整输出'
    / '二连板及以上低竞价_前两日开板明细.csv'
)
TRADING_DATES_PATH = (
    PROJECT_DIR / '数据' / '聚宽因子_2025-10-01_2026-09-30.csv'
)


def save_group(
    data: pd.DataFrame,
    column: str,
    bins: list[float],
    labels: list[str],
    output_name: str,
    trading_dates: pd.Series,
) -> pd.DataFrame:
    """按指定字段分组并保存绩效。"""

    data[column] = pd.cut(
        data[column],
        bins=bins,
        labels=labels,
        right=False,
    )
    result = pd.DataFrame(
        calculate_metrics(
            name,
            data.loc[data[column].eq(name)],
            trading_dates,
        )
        for name in labels
    ).rename(columns={'第三日竞价区间': column})
    result.to_csv(
        SOURCE.with_name(output_name),
        index=False,
        encoding='utf-8-sig',
    )
    return result


def main() -> None:
    """执行第二天特征统计。"""

    data = pd.read_csv(SOURCE, encoding='utf-8-sig')
    data = data.loc[data['竞价涨幅'].lt(2)].copy()
    trading_dates = pd.read_csv(
        TRADING_DATES_PATH,
        encoding='utf-8-sig',
        usecols=['time'],
    )['time']

    overall = pd.DataFrame(
        [
            calculate_metrics(
                '所有二连板及以上+第三日竞价低于2%',
                data,
                trading_dates,
            )
        ]
    )
    entity = save_group(
        data,
        '第二天实体涨幅',
        [-float('inf'), 0, 3, 6, float('inf')],
        ['小于0%', '0%到3%', '3%到6%', '大于6%'],
        '所有二连板_第二天实体涨幅_绩效.csv',
        trading_dates,
    )
    auction = save_group(
        data,
        '第二天竞价涨幅',
        [-float('inf'), -2, 0, 2, float('inf')],
        ['低于-2%', '-2%到0%', '0%到2%', '大于2%'],
        '所有二连板_第二天竞价涨幅_绩效.csv',
        trading_dates,
    )
    amount = save_group(
        data,
        '第二天成交额_亿',
        [-float('inf'), 5, 10, 20, 40, float('inf')],
        ['小于5亿', '5到10亿', '10到20亿', '20到40亿', '大于40亿'],
        '所有二连板_第二天成交额_绩效.csv',
        trading_dates,
    )

    print('全部样本：')
    print(overall.to_string(index=False))
    print('\n按第二天实体涨幅：')
    print(entity.to_string(index=False))
    print('\n按第二天竞价涨幅：')
    print(auction.to_string(index=False))
    print('\n按第二天成交额：')
    print(amount.to_string(index=False))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
