# -*- coding: utf-8 -*-
'''统计二连板及以上，第三天竞价低于+2%买入时，前两个涨停日是否开板。'''

from __future__ import annotations

import concurrent.futures as futures
import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType

import baostock as bs
import pandas as pd

from 连板断板统计 import metric_row
from 资金周转对比 import max_concurrent_positions
from 抓取开板次数 import (
    count_open_episodes,
    fetch_minutes,
    to_baostock_code,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_DIR / '数据' / '聚宽因子_2026-01-01_2026-09-30.csv'
CACHE_DIRS = [
    PROJECT_DIR / '数据' / 'single_board_minute_cache',
    PROJECT_DIR / '数据' / 'minute_cache',
]
NEW_CACHE_DIR = PROJECT_DIR / '数据' / 'two_board_minute_cache'
OUTPUT_DIR = (
    Path(r'C:\Users\Administrator\PyCharmMiscProject')
    / '高开均线完整输出'
)
WORKERS = 4
REQUEST_DELAY = 0.3


def load_strategy_module(path: Path) -> ModuleType:
    '''动态导入主策略模块。'''

    spec = importlib.util.spec_from_file_location('二连板开板实验模块', path)
    if spec is None or spec.loader is None:
        raise ImportError(f'无法导入策略模块：{path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def worker_init() -> None:
    '''子进程登录 Baostock。'''

    login = bs.login()
    if login.error_code != '0':
        raise RuntimeError(login.error_msg)


def cached_minutes(code: str) -> pd.DataFrame | None:
    '''优先从已有分钟缓存读取。'''

    for directory in CACHE_DIRS + [NEW_CACHE_DIR]:
        path = directory / f'{code}.csv'
        if path.exists():
            return pd.read_csv(path, encoding='utf-8-sig')
    return None


def process_stock(
    item: tuple[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    '''处理一只股票在多个交易日的开板状态。'''

    code, events = item
    try:
        minutes = cached_minutes(code)
        if minutes is None:
            minutes = fetch_minutes(
                to_baostock_code(code),
                '2026-01-01',
                '2026-09-30',
            )
            if not minutes.empty:
                NEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                minutes.to_csv(
                    NEW_CACHE_DIR / f'{code}.csv',
                    index=False,
                    encoding='utf-8-sig',
                )
                time.sleep(REQUEST_DELAY)
    except Exception:
        return []

    if minutes.empty:
        return []
    minutes['date'] = pd.to_datetime(minutes['date'])
    minute_by_date = {
        date: group
        for date, group in minutes.groupby('date')
    }

    rows: list[dict[str, object]] = []
    for event in events:
        row: dict[str, object] = {'trade_id': event['trade_id']}
        for number in [1, 2]:
            day = pd.to_datetime(event[f'涨停日{number}'])
            minute_rows = minute_by_date.get(day)
            if minute_rows is None:
                row[f'开板次数{number}'] = None
                continue
            open_count, _, _ = count_open_episodes(
                minute_rows,
                float(event[f'涨停价{number}']),
            )
            row[f'开板次数{number}'] = open_count
        rows.append(row)
    return rows


def build_candidates() -> pd.DataFrame:
    '''构建二连板及以上、第三天低竞价买入的候选交易。'''

    df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
    df['time'] = pd.to_datetime(df['time'])
    df['实体涨幅'] = (df['close'] / df['open'] - 1) * 100
    df['均价'] = df['money'] / df['volume']
    df = df.sort_values(['code', 'time'])
    grouped = df.groupby('code', sort=False)

    df['前1涨停'] = grouped['是否涨停'].shift(1).fillna(0)
    df['前2涨停'] = grouped['是否涨停'].shift(2).fillna(0)
    df['涨停日1'] = grouped['time'].shift(2)
    df['涨停日2'] = grouped['time'].shift(1)
    df['涨停价1'] = grouped['high_limit'].shift(2)
    df['涨停价2'] = grouped['high_limit'].shift(1)
    df['第一天实体涨幅'] = grouped['实体涨幅'].shift(2)
    df['第二天实体涨幅'] = grouped['实体涨幅'].shift(1)
    df['第二天成交额_亿'] = grouped['成交额_亿'].shift(1)
    df['第一天竞价涨幅'] = grouped['竞价涨幅'].shift(2)
    df['第二天竞价涨幅'] = grouped['竞价涨幅'].shift(1)
    df['买入日期'] = df['time']
    df['买入参考价'] = df['open']
    df['卖出日期'] = grouped['time'].shift(-1)
    df['卖出参考价'] = grouped['均价'].shift(-1)

    mask = (
        df['前1涨停'].eq(1)
        & df['前2涨停'].eq(1)
        & df['竞价涨幅'].lt(2)
    )
    candidates = df.loc[mask].copy().reset_index(drop=True)
    candidates = candidates.dropna(
        subset=[
            '涨停日1',
            '涨停日2',
            '涨停价1',
            '涨停价2',
            '第二天成交额_亿',
            '买入参考价',
            '卖出参考价',
        ]
    )
    candidates['trade_id'] = candidates.index
    return candidates


def add_open_flags(candidates: pd.DataFrame) -> pd.DataFrame:
    '''批量读取开板状态并合并。'''

    grouped = (
        candidates.groupby('code', sort=False)
        .apply(
            lambda frame: frame[
                [
                    'trade_id',
                    '涨停日1',
                    '涨停日2',
                    '涨停价1',
                    '涨停价2',
                ]
            ].to_dict('records'),
            include_groups=False,
        )
        .to_dict()
    )
    items = list(grouped.items())

    login = bs.login()
    if login.error_code != '0':
        raise RuntimeError(login.error_msg)
    try:
        with futures.ProcessPoolExecutor(
            max_workers=WORKERS,
            initializer=worker_init,
        ) as pool:
            rows: list[dict[str, object]] = []
            completed = 0
            for chunk in pool.map(process_stock, items):
                rows.extend(chunk)
                completed += 1
                if completed % 25 == 0 or completed == len(items):
                    print(
                        f'进度：{completed}/{len(items)} 只股票',
                        flush=True,
                    )
    finally:
        bs.logout()

    minute_result = pd.DataFrame(rows)
    return candidates.merge(
        minute_result,
        on='trade_id',
        how='inner',
    )


def capital_summary(
    name: str,
    trades: pd.DataFrame,
    trading_dates: pd.Series,
) -> dict[str, object]:
    '''统计开板组合的收益和资金。'''

    metrics = metric_row(name, trades)
    if trades.empty:
        return {
            **metrics,
            '总盈利_2万每笔': 0.0,
            '最高并发持仓': 0,
            '所需周转资金': 0,
            '区间资金收益率': 0.0,
            '复利年化收益率': 0.0,
        }

    sample = trades.copy()
    sample['盈利金额_2万'] = sample['净收益率'] * 20_000 / 100
    total_profit = float(sample['盈利金额_2万'].sum())
    max_positions = max_concurrent_positions(sample, trading_dates)
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
    annual = (
        ((1 + interval_return) ** (252 / trading_days) - 1) * 100
        if trading_days > 0
        else 0.0
    )
    return {
        **metrics,
        '总盈利_2万每笔': total_profit,
        '最高并发持仓': max_positions,
        '所需周转资金': capital,
        '区间资金收益率': interval_return * 100,
        '复利年化收益率': annual,
    }


def main() -> None:
    '''执行二连板前两日开板组合统计。'''

    strategy = load_strategy_module(
        PROJECT_DIR / '脚本' / '高开均线完整回测.py'
    )
    candidates = build_candidates()
    print(
        f'候选事件：{len(candidates)}，股票数：'
        f'{candidates["code"].nunique()}',
        flush=True,
    )
    trades = add_open_flags(candidates)
    trades = strategy.计算交易成本(trades, strategy.策略参数())
    trades = trades.dropna(
        subset=['开板次数1', '开板次数2', '净收益率']
    )
    trades['第一天是否开板'] = trades['开板次数1'].gt(0)
    trades['第二天是否开板'] = trades['开板次数2'].gt(0)

    groups = [
        ('第一天不开板+第二天不开板', False, False),
        ('第一天不开板+第二天开板', False, True),
        ('第一天开板+第二天不开板', True, False),
        ('第一天开板+第二天开板', True, True),
    ]
    result = pd.DataFrame(
        capital_summary(
            name,
            trades.loc[
                trades['第一天是否开板'].eq(first)
                & trades['第二天是否开板'].eq(second)
            ],
            trades['time'],
        )
        for name, first, second in groups
    )

    both_open = trades.loc[
        trades['第一天是否开板'].eq(True)
        & trades['第二天是否开板'].eq(True)
    ].copy()
    both_open['第二天实体区间'] = pd.cut(
        both_open['第二天实体涨幅'],
        bins=[-float('inf'), -5, 0, 3, 6, float('inf')],
        labels=['小于-5%', '-5%到0%', '0%到3%', '3%到6%', '大于6%'],
        right=False,
    )
    both_open['第二天竞价区间'] = pd.cut(
        both_open['第二天竞价涨幅'],
        bins=[-float('inf'), -2, 0, 2, float('inf')],
        labels=['低于-2%', '-2%到0%', '0%到2%', '大于2%'],
        right=False,
    )
    entity_result = pd.DataFrame(
        capital_summary(
            name,
            both_open.loc[both_open['第二天实体区间'].eq(name)],
            trades['time'],
        )
        for name in ['小于-5%', '-5%到0%', '0%到3%', '3%到6%', '大于6%']
    )
    auction_result = pd.DataFrame(
        capital_summary(
            name,
            both_open.loc[both_open['第二天竞价区间'].eq(name)],
            trades['time'],
        )
        for name in ['低于-2%', '-2%到0%', '0%到2%', '大于2%']
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    detail_path = OUTPUT_DIR / '二连板及以上低竞价_前两日开板明细.csv'
    result_path = OUTPUT_DIR / '二连板及以上低竞价_前两日开板统计.csv'
    entity_path = OUTPUT_DIR / '二连板低竞价_两天都开板_第二天实体涨幅.csv'
    auction_path = OUTPUT_DIR / '二连板低竞价_两天都开板_第二天竞价涨幅.csv'
    trades.to_csv(detail_path, index=False, encoding='utf-8-sig')
    result.to_csv(result_path, index=False, encoding='utf-8-sig')
    entity_result.to_csv(entity_path, index=False, encoding='utf-8-sig')
    auction_result.to_csv(auction_path, index=False, encoding='utf-8-sig')
    print('\n二连板及以上低竞价，前两日开板组合：')
    print(result.to_string(index=False))
    print('\n两天都开板，按第二天实体涨幅：')
    print(entity_result.to_string(index=False))
    print('\n两天都开板，按第二天竞价涨幅：')
    print(auction_result.to_string(index=False))
    print(f'\n结果已保存：{result_path}')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
