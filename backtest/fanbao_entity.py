# ============================================================
# 反包策略回测 - 小白版
# 新增条件：实体涨跌幅 > -3%
# ============================================================
import pandas as pd, numpy as np
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 数据路径（改成你自己的）
CSV = r"C:\Users\Administrator\Desktop\全市场A股_2026-04-12_2026-06-12.csv"
df = pd.read_csv(CSV)
df["index"] = pd.to_datetime(df["index"])
df.sort_values(["证券代码", "index"], inplace=True)

# 算均线
df["M7"] = df.groupby("证券代码")["close"].transform(lambda x: x.rolling(7).mean())
df["M14"] = df.groupby("证券代码")["close"].transform(lambda x: x.rolling(14).mean())

# T-2 涨停
df["zt_Tm2"] = df.groupby("证券代码")["是否涨停"].shift(1)

# ======================= 选股条件 =======================

# 实体涨跌幅 = (收盘 - 开盘) / 开盘
# 比如：开盘10块，收盘10.3 → +3%    开盘10块，收盘9.7 → -3%
df["实体涨跌幅"] = (df["close"] - df["open"]) / df["open"]

df["信号"] = (
    (df["zt_Tm2"] == 1) &                      # T-2涨停过
    (df["是否涨停"] == 0) &                     # T-1没涨停
    (df["money"] > 1_500_000_000) &             # T-1成交额>15亿
    (df["M7"] / df["M14"] > 1) &                # M7/M14 > 1
    (df["实体涨跌幅"] > -0.03) &                 # 实体涨跌幅 > -3%
    df["M14"].notna()
).astype(int)

# 下面不用改
df["买入信号"] = df.groupby("证券代码")["信号"].shift(1)
print(f"信号总数: {df['信号'].sum()}")

cash = 50000; positions = {}; trades = []
for cur_date in sorted(df["index"].unique()):
    today = df[df["index"] == cur_date]
    if today.empty: continue
    for code in list(positions.keys()):
        row = today[today["证券代码"] == code]
        if row.empty: continue
        bp = positions[code]; sp = row.iloc[0]["close"]
        pnl = (sp - bp) / bp * 100
        cash += sp * 100 * 0.99975; trades.append(pnl); del positions[code]
    for _, row in today[today["买入信号"] == 1].iterrows():
        if len(positions) >= 3: break
        bp = row["open"]; vol = int(cash / 4 / bp / 100) * 100
        if vol < 100: continue
        if vol * bp * 1.00025 > cash: continue
        positions[row["证券代码"]] = bp; cash -= vol * bp * 1.00025

pnls = trades; w = sum(1 for p in pnls if p > 0)
print(f"交易: {len(pnls)}笔 | 胜率: {w}/{len(pnls)} ({w/len(pnls)*100:.1f}%) | 平均: {np.mean(pnls):+.2f}% | 最大赚: {max(pnls):+.2f}% | 最大亏: {min(pnls):+.2f}%")