# -*- coding: utf-8 -*-
'''统计首板后第二日断板、成交额大于6亿、M7/M14大于1、实体大于1%的开板情况。'''

from __future__ import annotations

import concurrent.futures as futures
import sys
import time
from pathlib import Path

import baostock as bs
import pandas as pd

from 连板断板统计 import metric_row
from 抓取开板次数 import (
    count_open_episodes,
    fetch_minutes,
    to_baostock_code,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_DIR / '数据' / '聚宽因子_2025-10-01_2026-09-30.csv'
OUTPUT_DIR = (
    Path(r'C:\Users\Administrator\PyCharmMiscProject')
    / '高开均线完整输出'
)
WORKERS = 4
REQUEST_DELAY = 0.3
MINUTE_CACHE_DIR = PROJECT_DIR / '数据' / 'single_board_minute_cache'


def worker_init() -> None:
    '''每个子进程独立登录 Baostock。'''

    login = bs.login()
    if login.error_code != '0':
        raise RuntimeError(login.error_msg)


def process_stock(
    item: tuple[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    '''处理一只股票的多个候选涨停日。'''

    code, events = item
    cache_path = MINUTE_CACHE_DIR / f'{code}.csv'
    try:
        if cache_path.exists():
            minutes = pd.read_csv(cache_path, encoding='utf-8-sig')
        else:
            minutes = fetch_minutes(
                to_baostock_code(code),
                '2025-10-01',
                '2026-09-30',
            )
            if not minutes.empty:
                MINUTE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                minutes.to_csv(
                    cache_path,
                    index=False,
                    encoding='utf-8-sig',
                )
                time.sleep(REQUEST_DELAY)
    except Exception:
        return []

    if minutes.empty:
        return []
    minutes['date'] = pd.to_datetime(minutes['date'])
    result: list[dict[str, object]] = []
    for event in events:
        day = pd.to_datetime(event['涨停日日期'])
        minute_rows = minutes.loc[minutes['date'].eq(day)]
        if minute_rows.empty:
            continue
        open_count, first_time, reclosed = count_open_episodes(
            minute_rows,
            float(event['涨停日涨停价']),
        )
        result.append(
            {
                'trade_id': event['trade_id'],
                '开板次数': open_count,
                '首次封板时间': first_time,
                '收盘回封': reclosed,
            }
        )
    return result


def build_candidates() -> pd.DataFrame:
    '''构建首板后第二日断板的候选交易。'''

    df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
    df['time'] = pd.to_datetime(df['time'])
    df['实体涨幅'] = (df['close'] / df['open'] - 1) * 100
    df['均价'] = df['money'] / df['volume']
    df['M7M14比值'] = df['M7'] / df['M14']
    df = df.sort_values(['code', 'time'])
    grouped = df.groupby('code', sort=False)

    df['前一日涨停'] = grouped['是否涨停'].shift(1).fillna(0)
    df['前两日涨停'] = grouped['是否涨停'].shift(2).fillna(0)
    df['涨停日日期'] = grouped['time'].shift(1)
    df['涨停日涨停价'] = grouped['high_limit'].shift(1)
    df['买入日期'] = grouped['time'].shift(-1)
    df['买入参考价'] = grouped['open'].shift(-1)
    df['卖出日期'] = grouped['time'].shift(-2)
    df['卖出参考价'] = grouped['均价'].shift(-2)

    mask = (
        df['前一日涨停'].eq(1)
        & df['前两日涨停'].eq(0)
        & df['是否涨停'].eq(0)
        & df['成交额_亿'].gt(6)
        & df['M7M14比值'].gt(1)
        & df['实体涨幅'].gt(1)
    )
    candidates = df.loc[mask].copy().reset_index(drop=True)
    candidates = candidates.dropna(
        subset=[
            '买入日期',
            '买入参考价',
            '卖出日期',
            '卖出参考价',
            '涨停日日期',
            '涨停日涨停价',
        ]
    )
    candidates['trade_id'] = candidates.index
    return candidates


def add_open_counts(candidates: pd.DataFrame) -> pd.DataFrame:
    '''批量下载分钟数据并合并开板次数。'''

    grouped = (
        candidates.groupby('code', sort=False)
        .apply(
            lambda frame: frame[
                ['trade_id', '涨停日日期', '涨停日涨停价']
            ].to_dict('records'),
            include_groups=False,
        )
        .to_dict()
    )
    items = list(grouped.items())

    bs.login()
    try:
        with futures.ProcessPoolExecutor(
            max_workers=WORKERS,
            initializer=worker_init,
        ) as pool:
            result_rows: list[dict[str, object]] = []
            completed = 0
            for rows in pool.map(process_stock, items):
                result_rows.extend(rows)
                completed += 1
                if completed % 25 == 0 or completed == len(items):
                    print(
                        f'进度：{completed}/{len(items)} 只股票',
                        flush=True,
                    )
    finally:
        bs.logout()

    minute_result = pd.DataFrame(result_rows)
    merged = candidates.merge(
        minute_result,
        on='trade_id',
        how='inner',
    )
    return merged


def summarize(name: str, trades: pd.DataFrame) -> dict[str, float | str]:
    '''输出统计表。'''

    return metric_row(name, trades)


def main() -> None:
    '''执行全量筛选和开板统计。'''

    candidates = build_candidates()
    print(
        f'候选事件：{len(candidates)}，股票数：'
        f'{candidates["code"].nunique()}',
        flush=True,
    )
    trades = add_open_counts(candidates)

    # 使用主策略的成本函数。
    import importlib.util

    strategy_path = PROJECT_DIR / '脚本' / '高开均线完整回测.py'
    spec = importlib.util.spec_from_file_location('单板开板统计模块', strategy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f'无法导入策略模块：{strategy_path}')
    strategy = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = strategy
    spec.loader.exec_module(strategy)
    trades = strategy.计算交易成本(trades, strategy.策略参数())
    trades['炸板后回封'] = (
        trades['开板次数'].gt(0)
        & trades['收盘回封'].eq(True)
    )

    open_count_result = pd.DataFrame(
        summarize(
            f'开板{name}',
            trades.loc[
                trades['开板次数'].eq(value)
                if value < 3
                else trades['开板次数'].ge(3)
            ],
        )
        for name, value in [
            ('0次', 0),
            ('1次', 1),
            ('2次', 2),
            ('3次及以上', 3),
        ]
    )
    reseal_result = pd.DataFrame(
        [
            summarize(
                '炸板后回封',
                trades.loc[trades['炸板后回封'].eq(True)],
            ),
            summarize(
                '未检测回封',
                trades.loc[trades['炸板后回封'].eq(False)],
            ),
        ]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    trades.to_csv(
        OUTPUT_DIR / '单板反包_开板明细.csv',
        index=False,
        encoding='utf-8-sig',
    )
    open_count_result.to_csv(
        OUTPUT_DIR / '单板反包_开板次数统计.csv',
        index=False,
        encoding='utf-8-sig',
    )
    reseal_result.to_csv(
        OUTPUT_DIR / '单板反包_回封统计.csv',
        index=False,
        encoding='utf-8-sig',
    )

    print('\n按开板次数：')
    print(open_count_result.to_string(index=False))
    print('\n按是否回封：')
    print(reseal_result.to_string(index=False))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
