# -*- coding: utf-8 -*-
'''用 5 分钟线统计涨停日的近似开板次数和是否炸板后回封。

说明：
- 日线只能判断收盘是否涨停。
- 5 分钟线可以判断涨停后是否出现过低于涨停价的时段。
- 它不是 Tick/L2，不能精确统计同一分钟内反复开板。
'''

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import baostock as bs
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DAILY_PATH = PROJECT_DIR / '数据' / '聚宽因子_2026-01-01_2026-09-30.csv'
OUTPUT_PATH = (
    Path(r'C:\Users\Administrator\PyCharmMiscProject')
    / '高开均线完整输出'
    / '涨停开板次数样本.csv'
)


def to_baostock_code(code: str) -> str:
    '''把聚宽代码转换成 Baostock 代码。'''

    if code.endswith('.XSHE'):
        return 'sz.' + code.removesuffix('.XSHE')
    if code.endswith('.XSHG'):
        return 'sh.' + code.removesuffix('.XSHG')
    return code


def fetch_minutes(code: str, start: str, end: str) -> pd.DataFrame:
    '''下载单只股票的 5 分钟数据。'''

    result = bs.query_history_k_data_plus(
        code,
        'date,time,open,high,low,close',
        start_date=start,
        end_date=end,
        frequency='5',
        adjustflag='3',
    )
    rows = []
    while result.next():
        rows.append(result.get_row_data())
    if not rows:
        return pd.DataFrame(
            columns=['date', 'time', 'open', 'high', 'low', 'close']
        )
    return pd.DataFrame(rows, columns=result.fields)


def count_open_episodes(
    minutes: pd.DataFrame,
    limit_price: float,
) -> tuple[int, str | None, bool]:
    '''统计一次涨停日的近似开板次数。'''

    if minutes.empty:
        return 0, None, False

    work = minutes.copy()
    for column in ['high', 'low', 'close']:
        work[column] = pd.to_numeric(work[column], errors='coerce')

    tolerance = 0.001
    # 必须是完整的封板 5 分钟：最高价和最低价都接近涨停价。
    # 这样可以避免把“第一次触板当根就下探”误判成开板。
    sealed = (
        work['high'].ge(limit_price - tolerance)
        & work['low'].ge(limit_price - tolerance)
    )
    below_limit = work['low'].lt(limit_price - tolerance)
    sealed_rows = work.loc[sealed]
    if sealed_rows.empty:
        return 0, None, False

    first_index = sealed_rows.index[0]
    after_first = below_limit.loc[
        below_limit.index > first_index
    ]
    episode_starts = (
        after_first
        & ~after_first.shift(1, fill_value=False)
    )
    open_episodes = int(episode_starts.sum())
    first_time = str(work.loc[first_index, 'time'])
    reclosed = bool(
        work['close'].iloc[-1] >= limit_price - tolerance
    )
    return open_episodes, first_time, reclosed


def main() -> None:
    '''按股票批量统计，默认只跑前 5 只做验证。'''

    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--start', default='2026-01-01')
    parser.add_argument('--end', default='2026-09-30')
    parser.add_argument(
        '--mode',
        choices=['touched', 'closed'],
        default='touched',
        help='touched=所有摸到涨停；closed=收盘涨停',
    )
    args = parser.parse_args()

    daily = pd.read_csv(DAILY_PATH, encoding='utf-8-sig')
    if args.mode == 'closed':
        events = daily.loc[daily['是否涨停'].eq(1)].copy()
    else:
        events = daily.loc[
            daily['high'].ge(daily['high_limit'] - 0.001)
            & daily['paused'].fillna(0).eq(0)
        ].copy()
    events['time'] = pd.to_datetime(events['time'])

    codes = events['code'].drop_duplicates().tolist()
    if args.limit > 0:
        codes = codes[: args.limit]

    login = bs.login()
    if login.error_code != '0':
        raise RuntimeError(login.error_msg)

    rows: list[dict[str, object]] = []
    try:
        for index, code in enumerate(codes, start=1):
            stock_daily = events.loc[events['code'].eq(code)]
            minutes = fetch_minutes(
                to_baostock_code(code),
                args.start,
                args.end,
            )
            if minutes.empty:
                continue

            minutes['date'] = pd.to_datetime(minutes['date'])
            minutes_by_date = {
                date: group
                for date, group in minutes.groupby('date')
            }

            for record in stock_daily.itertuples(index=False):
                day = record.time
                minute_rows = minutes_by_date.get(day)
                if minute_rows is None:
                    continue
                open_count, first_time, reclosed = count_open_episodes(
                    minute_rows,
                    float(record.high_limit),
                )
                rows.append(
                    {
                        '日期': day.date(),
                        '代码': code,
                        '开板次数': open_count,
                        '首次触板时间': first_time,
                        '收盘回封': reclosed,
                        '炸板后回封': bool(open_count > 0 and reclosed),
                    }
                )
            print(
                f'进度 {index}/{len(codes)}：{code}',
                flush=True,
            )
    finally:
        bs.logout()

    output = pd.DataFrame(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
    print(f'完成：{len(output)} 行 -> {OUTPUT_PATH}')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
