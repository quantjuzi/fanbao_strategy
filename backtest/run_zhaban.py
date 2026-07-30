# -*- coding: utf-8 -*-
"""
炸板策略回测 - 使用已有CSV数据

策略:
  T-1日筛选: 当日最高>涨停价*0.999 AND 收盘<涨停价 AND 成交额>5000万
  T日卖出:   方案B - 次日开盘价卖出

输入: data/全市场A股_2026-04-12_2026-06-12.csv
输出: results/backtest_results.csv (控制台也会打印绩效)
"""

import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', '全市场A股_2026-04-12_2026-06-12.csv')
OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'results', 'zhaban_backtest_results.csv')
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

# 1. 加载数据
print('加载数据...')
df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
df['index'] = pd.to_datetime(df['index'])
df = df.sort_values(['证券代码', 'index']).reset_index(drop=True)
print(f'共 {len(df):,} 行, {df["证券代码"].nunique()} 支股票, ', end='')
print(f'{df["index"].min().date()} ~ {df["index"].max().date()}')

# 2. 计算炸板相关因子
print('计算因子...')
df['成交额_亿'] = (df['money'] / 1e8).round(2)

# 是否炸板: 最高>涨停价*0.999 AND 收盘<涨停价
df['is_zhaban'] = (
    (df['high'] >= df['high_limit'] * 0.9999) &
    (df['close'] < df['high_limit']) &
    (df['成交额_亿'] > 0.5)
).astype(int)

# 竞价涨跌幅
df['auction_pct'] = ((df['open'] / df['pre_close']) - 1) * 100

# T-1日涨停标记
df['prev_limit_up'] = df.groupby('证券代码')['是否涨停'].shift(1).fillna(0).astype(int)

# 3. 炸板次日表现
print('计算炸板次日收益...')
df['next_open'] = df.groupby('证券代码')['open'].shift(-1)

zhaban = df[df['is_zhaban'] == 1].copy()
print(f'炸板信号: {len(zhaban)} 次')
zhaban = zhaban.dropna(subset=['next_open'])
print(f'有次日数据: {len(zhaban)} 次')
zhaban['次日收益率_pct'] = ((zhaban['next_open'] / zhaban['close']) - 1) * 100

# 4. 绩效统计
print()
print('=' * 60)
print('                炸板策略回测结果')
print('=' * 60)

total = len(zhaban)
win = (zhaban['次日收益率_pct'] > 0).sum()
loss = (zhaban['次日收益率_pct'] <= 0).sum()
win_rate = win / total * 100 if total > 0 else 0
avg_return = zhaban['次日收益率_pct'].mean()

print(f'样本数:          {total}')
print(f'胜次数/负次数:   {win}/{loss}')
print(f'胜率:            {win_rate:.1f}%')
print(f'平均次日收益:    {avg_return:.2f}%')
print(f'最大盈利:        {zhaban["次日收益率_pct"].max():.2f}%')
print(f'最大亏损:        {zhaban["次日收益率_pct"].min():.2f}%')

# 按成交额分档
print()
print('--- 按成交额分档 ---')
bins = [0.5, 1, 2, 5, 10, 999]
labels = ['0.5-1亿', '1-2亿', '2-5亿', '5-10亿', '>10亿']
zhaban['成交额档'] = pd.cut(zhaban['成交额_亿'], bins=bins, labels=labels)
for lbl, grp in zhaban.groupby('成交额档', observed=False):
    wr = (grp['次日收益率_pct'] > 0).mean() * 100
    ar = grp['次日收益率_pct'].mean()
    print(f'  {lbl}: {len(grp)}次, 胜率{wr:.0f}%, 平均{ar:.2f}%')

# 按竞价涨跌幅分档
print()
print('--- 按竞价涨跌幅分档 ---')
bins2 = [-20, -3, 0, 2, 5, 20]
labels2 = ['大幅低开<-3%', '微低开-3~0%', '平开0~2%', '高开2~5%', '大幅高开>5%']
zhaban['竞价档'] = pd.cut(zhaban['auction_pct'], bins=bins2, labels=labels2)
for lbl, grp in zhaban.groupby('竞价档', observed=False):
    if len(grp) > 0:
        wr = (grp['次日收益率_pct'] > 0).mean() * 100
        ar = grp['次日收益率_pct'].mean()
        print(f'  {lbl}: {len(grp)}次, 胜率{wr:.0f}%, 平均{ar:.2f}%')

# 按T-1是否涨停分档
print()
print('--- 按T-1是否涨停分档 ---')
for val, grp in zhaban.groupby('prev_limit_up'):
    label = 'T-1已涨停' if val == 1 else 'T-1未涨停'
    wr = (grp['次日收益率_pct'] > 0).mean() * 100
    ar = grp['次日收益率_pct'].mean()
    print(f'  {label}: {len(grp)}次, 胜率{wr:.0f}%, 平均{ar:.2f}%')

# 5. 保存结果
cols_out = ['index', '证券代码', 'open', 'close', 'high', 'high_limit',
            '成交额_亿', 'auction_pct', 'prev_limit_up', 'next_open', '次日收益率_pct']
zhaban_out = zhaban[cols_out].sort_values('index')
zhaban_out.to_csv(OUT_PATH, index=False, encoding='utf-8-sig')
print()
print(f'结果已保存: {OUT_PATH}')
print(f'共 {len(zhaban_out)} 条记录')