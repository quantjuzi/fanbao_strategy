# ============================================================
# 每日选股总入口
#
# 收盘后运行，同时跑所有策略，输出明日关注清单
# 你只实盘跑 mode1 反包，mode2 高开趋势做观察
# ============================================================

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os, sys
import pandas as pd

# 把strategies目录加到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "strategies"))
from mode1_fanbao import screen as screen_mode1
from mode2_trend_gap import screen as screen_mode2

CSV_PATH = r"C:\Users\Administrator\Desktop\全市场A股_20260412_20260612.csv"
COL_DATE = "index"

# --- 读数据 ---
df = pd.read_csv(CSV_PATH)
df[COL_DATE] = pd.to_datetime(df[COL_DATE])
df.sort_values(["证券代码", COL_DATE], inplace=True)

# --- 公共计算 ---
df["涨跌幅"] = df.groupby("证券代码")["close"].pct_change()
df["昨收"] = df.groupby("证券代码")["close"].shift(1)
df["昨高"] = df.groupby("证券代码")["high"].shift(1)
df["MA5"] = df.groupby("证券代码")["close"].transform(lambda x: x.rolling(5).mean())
df["MA10"] = df.groupby("证券代码")["close"].transform(lambda x: x.rolling(10).mean())
df["MA20"] = df.groupby("证券代码")["close"].transform(lambda x: x.rolling(20).mean())

today = df[COL_DATE].max()
print(f"\n数据截止: {today.date()}")
print("=" * 60)

# --- 跑模式1：反包 ---
print("\n【模式1】反包策略（实盘跑这个）")
result1 = screen_mode1(df, today)
if result1:
    print(f"{'代码':<14} {'收盘价':>8} {'成交额亿':>9} {'涨幅%':>6}")
    print("-" * 42)
    for r in result1:
        print(f"{r['证券代码']:<14} {r['close']:>8.2f} {r['money']/1e8:>8.2f}  {r['涨跌幅']*100:>+5.2f}")
    print("-" * 42)
    print(f"共 {len(result1)} 支")
else:
    print("  无信号")

# --- 跑模式2：高开趋势（观察用） ---
print(f"\n【模式2】高开趋势策略（仅观察，不实盘）")
result2 = screen_mode2(df, today)
if result2:
    print(f"{'代码':<14} {'收盘价':>8} {'成交额亿':>9} {'涨幅%':>6}")
    print("-" * 42)
    for r in result2:
        print(f"{r['证券代码']:<14} {r['close']:>8.2f} {r['money']/1e8:>8.2f}  {r['涨跌幅']*100:>+5.2f}")
    print("-" * 42)
    print(f"共 {len(result2)} 支")
else:
    print("  无信号")

print(f"\n{'=' * 60}")
print("明天操作: 看分时找买点 -> 买入 -> 后天9:40附近卖出")
print(f"{'=' * 60}")

