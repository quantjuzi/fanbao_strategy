# -*- coding: utf-8 -*-
"""炸板策略全周期回测 - 2025-04-21 ~ 2026-04-28

交易规则(按用户指定):
  T日  炸板信号(盘中触及涨停但收盘未封住)
  T+1  买入: 次日竞价(开盘价)
  T+1  卖出: 次日收盘价

额外输出阴线炸板(close < open)及其分档, 用于和全样本对比。
输入: data/全市场A股_2025-04-21_2026-04-28.csv
输出: results/zhaban_backtest_results_full.csv
"""

import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, 'data', '全市场A股_2025-04-21_2026-04-28.csv')
OUT_PATH = os.path.join(ROOT, 'results', 'zhaban_backtest_results_full.csv')
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)


def win_stats(grp: pd.DataFrame, label: str) -> None:
    """打印一组样本的胜率、平均收益和盈亏比。"""
    n = len(grp)
    if n == 0:
        print(f'  {label}: 无样本')
        return
    ret = grp['次日收益率_pct']
    win_rate = (ret > 0).mean() * 100
    avg_ret = ret.mean()
    avg_win = ret[ret > 0].mean() if (ret > 0).any() else 0
    avg_loss = ret[ret <= 0].mean() if (ret <= 0).any() else 0
    print(f'  {label}: {n}次, 胜率{win_rate:.1f}%, 平均{avg_ret:+.2f}%, '
          f'平均盈利{avg_win:+.2f}%, 平均亏损{avg_loss:+.2f}%')


print('加载数据...')
df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
df['time'] = pd.to_datetime(df['time'])
df = df.sort_values(['code', 'time']).reset_index(drop=True)
print(f'共 {len(df):,} 行, {df["code"].nunique()} 支股票, '
      f'{df["time"].min().date()} ~ {df["time"].max().date()}')

# 取下一交易日的开盘价和收盘价
df['next_open'] = df.groupby('code')['open'].shift(-1)
df['next_close'] = df.groupby('code')['close'].shift(-1)

# 炸板信号沿用下载脚本标记, 并保留成交额>5000万的规则
signal = (df['is_zhaban'] == 1) & (df['成交额_亿'] > 0.5)
zhaban = df[signal].copy()
zhaban = zhaban.dropna(subset=['next_open', 'next_close'])
zhaban['次日收益率_pct'] = (zhaban['next_close'] / zhaban['next_open'] - 1) * 100
zhaban['is_yin'] = (zhaban['close'] < zhaban['open']).astype(int)
print(f'炸板信号(成交额>0.5亿): {len(zhaban)} 次')

print()
print('=' * 64)
print('  炸板策略回测: T+1竞价买入, T+1收盘卖出')
print('=' * 64)
win_stats(zhaban, '全部炸板')
win_stats(zhaban[zhaban['is_yin'] == 1], '阴线炸板(close<open)')
win_stats(zhaban[zhaban['is_yin'] == 0], '阳线炸板')

print()
print('--- 阴线炸板: 按T-1是否涨停 ---')
yin = zhaban[zhaban['is_yin'] == 1]
win_stats(yin[yin['prev_limit_up'] == 0], 'T-1未涨停')
win_stats(yin[yin['prev_limit_up'] == 1], 'T-1已涨停')

print()
print('--- 阴线炸板: 按竞价涨跌幅分档 ---')
bins = [-99, -3, 0, 2, 5, 99]
labels = ['大幅低开<-3%', '微低开-3~0%', '平开0~2%', '高开2~5%', '大幅高开>5%']
yin['竞价档'] = pd.cut(yin['auction_pct'], bins=bins, labels=labels)
for lbl, grp in yin.groupby('竞价档', observed=False):
    win_stats(grp, lbl)

print()
print('--- 阴线炸板: 按成交额分档 ---')
bins2 = [0.5, 1, 2, 5, 10, 1e9]
labels2 = ['0.5-1亿', '1-2亿', '2-5亿', '5-10亿', '>10亿']
yin['成交额档'] = pd.cut(yin['成交额_亿'], bins=bins2, labels=labels2)
for lbl, grp in yin.groupby('成交额档', observed=False):
    win_stats(grp, lbl)

cols = ['time', 'code', 'open', 'close', 'high', 'high_limit', '成交额_亿',
        'auction_pct', 'prev_limit_up', 'next_open', 'next_close', '次日收益率_pct']
zhaban[cols].sort_values('time').to_csv(OUT_PATH, index=False, encoding='utf-8-sig')
print()
print(f'明细已保存: {OUT_PATH} ({len(zhaban)} 条)')
