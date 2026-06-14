# ============================================================
# 新策略：T-2涨停 → T-1放量+均线多头 → T日开盘买入 → T+1收盘卖出
# 每个信号单独算盈亏，不限仓位
# ============================================================

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd, numpy as np

CSV = r"C:\Users\Administrator\Desktop\全市场A股_2026-04-12_2026-06-12.csv"

df = pd.read_csv(CSV)
df["index"] = pd.to_datetime(df["index"])
df.sort_values(["证券代码", "index"], inplace=True)

# 算均线
df["M7"] = df.groupby("证券代码")["close"].transform(lambda x: x.rolling(7).mean())
df["M14"] = df.groupby("证券代码")["close"].transform(lambda x: x.rolling(14).mean())

# T-2涨停（上一行数据）
df["zt_Tm2"] = df.groupby("证券代码")["是否涨停"].shift(1)

# 信号在T-1收盘确认
# 15亿 = 1_500_000_000
df["信号"] = (
    (df["zt_Tm2"] == 1) & (df["是否涨停"] == 0) &
    (df["money"] > 1_500_000_000) &
    (df["M7"] / df["M14"] > 1.08) & df["M14"].notna()
).astype(int)

signals = df[df["信号"] == 1]
print(f"信号总数: {len(signals)}")

# 每个信号单独算：T日开盘买入，T+1收盘卖出
trades = []
for _, row in signals.iterrows():
    code = row["证券代码"]
    t_minus_1 = row["index"]
    
    t_data = df[(df["证券代码"] == code) & (df["index"] > t_minus_1)]
    if t_data.empty: continue
    t_day = t_data.iloc[0]
    buy_price = t_day["open"]
    
    tp1_data = df[(df["证券代码"] == code) & (df["index"] > t_day["index"])]
    if tp1_data.empty: continue
    sell_price = tp1_data.iloc[0]["close"]
    
    pnl = (sell_price - buy_price) / buy_price * 100
    trades.append((str(t_minus_1.date()), code, buy_price, sell_price, pnl))

pnls = [t[4] for t in trades]
w = sum(1 for p in pnls if p > 0)
print(f"实际交易: {len(trades)}笔")
print(f"胜率: {w}/{len(trades)} ({w/len(trades)*100:.1f}%)")
print(f"平均: {np.mean(pnls):+.2f}%")
print(f"最大赚: {max(pnls):+.2f}%")
print(f"最大亏: {min(pnls):+.2f}%")
