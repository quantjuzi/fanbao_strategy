# -*- coding: utf-8 -*-
"""
策略绩效分析报告
读取 trade_log.csv 生成业绩指标 + 图表
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os, sys, json
from datetime import datetime
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(REPO_DIR, "trade_log.csv")
OUTPUT_DIR = os.path.join(REPO_DIR, "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def load_trades():
    df = pd.read_csv(CSV_PATH, encoding='utf-8')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    df['pnl_pct'] = df['pnl_pct'].str.replace('%','').astype(float) / 100
    df['pnl_amount'] = df['qty'] * (df['sell_price'] - df['buy_price'])
    df['trade_value'] = df['qty'] * df['buy_price']
    return df

def calc_metrics(df, initial_capital=50000):
    total_trades = len(df)
    wins = df[df['pnl_pct'] > 0]
    losses = df[df['pnl_pct'] < 0]
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
    avg_win = wins['pnl_pct'].mean() * 100 if len(wins) > 0 else 0
    avg_loss = losses['pnl_pct'].mean() * 100 if len(losses) > 0 else 0
    avg_return = df['pnl_pct'].mean() * 100
    best_trade = df['pnl_pct'].max() * 100
    worst_trade = df['pnl_pct'].min() * 100
    # Cumulative compounded return
    df['cum_return'] = (1 + df['pnl_pct']).cumprod()
    total_return = (df['cum_return'].iloc[-1] - 1) * 100 if len(df) > 0 else 0
    # Max drawdown
    cum = df['cum_return'].values if len(df) > 0 else [1]
    peak = np.maximum.accumulate(cum)
    drawdown = (cum - peak) / peak
    max_dd = drawdown.min() * 100
    # Sharpe ratio (daily, ~0.5% risk-free)
    excess = df['pnl_pct'] - 0.005 / 100
    sharpe = np.sqrt(252) * excess.mean() / excess.std() if excess.std() > 0 and len(df) > 1 else 0
    # Profit factor
    total_profit = wins['pnl_pct'].sum() if len(wins) > 0 else 0
    total_loss = abs(losses['pnl_pct'].sum()) if len(losses) > 0 else 0
    profit_factor = total_profit / total_loss if total_loss > 0 else 0
    # Final equity
    total_pnl = df['pnl_amount'].sum()
    equity = initial_capital + total_pnl
    metrics = {
        '交易总笔数': total_trades,
        '胜率': f'{win_rate:.1f}%',
        '平均每笔收益': f'{avg_return:.2f}%',
        '平均盈利': f'{avg_win:.2f}%',
        '平均亏损': f'{avg_loss:.2f}%',
        '最大单笔盈利': f'{best_trade:.2f}%',
        '最大单笔亏损': f'{worst_trade:.2f}%',
        '累计收益率': f'{total_return:.2f}%',
        '最大回撤': f'{max_dd:.2f}%',
        '夏普比率': f'{sharpe:.2f}',
        '盈亏比': f'{profit_factor:.2f}',
        '总盈亏金额': f'{total_pnl:+,.0f}',
        '期末总资产': f'{equity:,.0f}',
        '初始资金': f'{initial_capital:,}',
    }
    return metrics, df

def save_charts(df):
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    fig.suptitle('反包策略 绩效分析报告', fontsize=14, fontweight='bold')
    # 1. 净值曲线
    ax = axes[0, 0]
    ax.plot(df['date'], df['cum_return'], color='#2196F3', linewidth=1.5)
    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5)
    ax.fill_between(df['date'], 1, df['cum_return'], where=(df['cum_return'] >= 1), color='#4CAF50', alpha=0.15)
    ax.fill_between(df['date'], 1, df['cum_return'], where=(df['cum_return'] < 1), color='#F44336', alpha=0.15)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_title('累计净值曲线', fontsize=11)
    ax.set_ylabel('净值')
    ax.grid(alpha=0.3)
    ax.set_xlim(df['date'].min(), df['date'].max())
    # 2. 月度收益率
    ax = axes[0, 1]
    df['month'] = df['date'].dt.to_period('M').astype(str)
    monthly = df.groupby('month')['pnl_pct'].sum()
    colors = ['#4CAF50' if v >= 0 else '#F44336' for v in monthly.values]
    ax.bar(monthly.index, monthly.values * 100, color=colors, width=0.5)
    ax.set_title('月度收益率', fontsize=11)
    ax.set_ylabel('收益率(%)')
    ax.axhline(y=0, color='gray', linewidth=0.5)
    for tick in ax.get_xticklabels():
        tick.set_rotation(45)
        tick.set_fontsize(8)
    ax.grid(alpha=0.3, axis='y')
    # 3. 盈亏分布
    ax = axes[1, 0]
    bins = np.arange(-0.15, 0.20, 0.025)
    ax.hist(df[df['pnl_pct'] >= 0]['pnl_pct'] * 100, bins=bins*100, color='#4CAF50', alpha=0.7, label='盈利')
    ax.hist(df[df['pnl_pct'] < 0]['pnl_pct'] * 100, bins=bins*100, color='#F44336', alpha=0.7, label='亏损')
    ax.set_title('盈亏分布', fontsize=11)
    ax.set_xlabel('收益率(%)')
    ax.set_ylabel('交易次数')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, axis='y')
    # 4. 每日盈亏
    ax = axes[1, 1]
    colors = ['#4CAF50' if v >= 0 else '#F44336' for v in df['pnl_pct'].values]
    ax.bar(range(len(df)), df['pnl_pct'] * 100, color=colors, width=0.6)
    ax.set_title('每笔交易收益率', fontsize=11)
    ax.set_xlabel('交易序号')
    ax.set_ylabel('收益率(%)')
    ax.axhline(y=0, color='gray', linewidth=0.5)
    ax.grid(alpha=0.3, axis='y')
    plt.tight_layout()
    chart_path = os.path.join(OUTPUT_DIR, 'performance_chart.png')
    fig.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return chart_path

def save_summary_txt(metrics):
    txt_path = os.path.join(REPO_DIR, 'PERFORMANCE_SUMMARY.md')
    lines = [
        '# 策略绩效汇总',
        '',
        f'> 更新日期: {datetime.now().strftime("%Y-%m-%d")}',
        '',
        '## 核心指标',
        '',
        '| 指标 | 数值 |',
        '|---|---|',
    ]
    for k, v in metrics.items():
        lines.append(f'| {k} | {v} |')
    lines.extend(['', '---', ''])
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return txt_path

def main():
    df = load_trades()
    metrics, df = calc_metrics(df)
    chart_path = save_charts(df)
    summary_path = save_summary_txt(metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f'\n图表: {chart_path}')
    print(f'报告: {summary_path}')
    return metrics

if __name__ == '__main__':
    main()
