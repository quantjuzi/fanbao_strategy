# -*- coding: utf-8 -*-
'''统计二连板低竞价样本中，第二天成交额5到10亿的竞价分布。'''

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
TRADING_DATES = pd.read_csv(
    PROJECT_DIR / '数据' / '聚宽因子_2025-10-01_2026-09-30.csv',
    encoding='utf-8-sig',
    usecols=['time'],
)['time']


def summarize(
    data: pd.DataFrame,
    column: str,
    labels: list[str],
    bins: list[float],
) -> pd.DataFrame:
    """按指定竞价字段统计。"""

    data = data.copy()
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
            TRADING_DATES,
        )
        for name in labels
    ).rename(columns={'第三日竞价区间': column})
    return result


def main() -> None:
    """执行竞价分层统计。"""

    data = pd.read_csv(SOURCE, encoding='utf-8-sig')
    data = data.loc[
        data['第二天成交额_亿'].between(5, 10, inclusive='left')
        & data['竞价涨幅'].lt(2)
    ].copy()

    second_auction = summarize(
        data,
        '第二天竞价涨幅',
        ['低于-2%', '-2%到0%', '0%到2%', '大于2%'],
        [-float('inf'), -2, 0, 2, float('inf')],
    )
    third_auction = summarize(
        data,
        '竞价涨幅',
        ['低于-2%', '-2%到0%', '0%到2%'],
        [-float('inf'), -2, 0, 2],
    )

    second_path = SOURCE.with_name(
        '二连板_第二天成交额5到10亿_第二天竞价涨幅.csv'
    )
    third_path = SOURCE.with_name(
        '二连板_第二天成交额5到10亿_第三日竞价涨幅.csv'
    )
    second_auction.to_csv(second_path, index=False, encoding='utf-8-sig')
    third_auction.to_csv(third_path, index=False, encoding='utf-8-sig')

    print('第二天成交额5到10亿，按第二天竞价涨幅：')
    print(second_auction.to_string(index=False))
    print('\n第二天成交额5到10亿，按第三日竞价涨幅：')
    print(third_auction.to_string(index=False))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
