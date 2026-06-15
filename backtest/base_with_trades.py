# ============================================================
# 反包策略 - 基础版（无条件）
# 无仓位限制，每笔交易明细都打印
# ============================================================
import pandas as pd, numpy as np
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CSV = r"C:\Users\Administrator\Desktop\全市场A股_2026-04-12_2026-06-12.csv"
df = pd.read_csv(CSV)
df["index"] = pd.to_datetime(df["index"])
df.sort_values(["证券代码", "index"], inplace=True)

df["M7"] = df.groupby("证券代码")["close"].transform(lambda x: x.rolling(7).mean())
df["M14"] = df.groupby("证券代码")["close"].transform(lambda x: x.rolling(14).mean())
df["zt_Tm2"] = df.groupby("证券代码")["是否涨停"].shift(1)

df["信号"] = (
    (df["zt_Tm2"] == 1) & (df["是否涨停"] == 0) &
    (df["money"] > 1_500_000_000) & (df["M7"] / df["M14"] > 1) &
    df["M14"].notna()
).astype(int)

print("条件：T-2涨停 + T-1断板 + 成交额>15亿 + M7/M14>1")
print(f"信号总数: {df['信号'].sum()}")
print()

trades = []
for _, row in df[df["信号"] == 1].iterrows():
    code = row["证券代码"]
    t1 = row["index"]
    td = df[(df["证券代码"] == code) & (df["index"] > t1)]
    if td.empty: continue
    bp = td.iloc[0]["open"]
    tp1 = df[(df["证券代码"] == code) & (df["index"] > td.iloc[0]["index"])]
    if tp1.empty: continue
    sp = tp1.iloc[0]["close"]
    pnl = (sp - bp) / bp * 100
    trades.append({"code": code, "bp": bp, "sp": sp, "pnl": pnl, "买入日": str(td.iloc[0]["index"].date()), "卖出日": str(tp1.iloc[0]["index"].date())})

pnls = [t["pnl"] for t in trades]
w_pnls = [p for p in pnls if p > 0]
l_pnls = [p for p in pnls if p <= 0]

print(f"{"":<8}  基础版")
print(f"{"":<8}  {'─'*20}")
print(f"信号总笔数    {len(pnls)}")
print(f"盈利笔数      {len(w_pnls)}")
print(f"亏损笔数      {len(l_pnls)}")
print(f"胜率          {len(w_pnls)}/{len(pnls)} ({len(w_pnls)/len(pnls)*100:.1f}%)")
print(f"平均盈亏      {np.mean(pnls):+.2f}%")
print(f"平均盈利      {np.mean(w_pnls):+.2f}%")
print(f"平均亏损      {np.mean(l_pnls):+.2f}%")
print(f"盈亏比        {abs(np.mean(w_pnls)/np.mean(l_pnls)):.2f}")
print(f"最大盈利      {max(pnls):+.2f}%")
print(f"最大亏损      {min(pnls):+.2f}%")
print(f"收益标准差    {np.std(pnls):.2f}%")
print()
print("逐笔交易明细:")
for t in trades:
    tag = "赚" if t["pnl"] > 0 else "亏"
    print(f"  {t["买入日"]}→{t["卖出日"]}  {t["code"]}  买入{t["bp"]:>8.2f}  卖出{t["sp"]:>8.2f}  {tag}{abs(t["pnl"]):>6.2f}%")
