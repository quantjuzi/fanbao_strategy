# ============================================================
# 每日收盘后选股 -- 大票反包策略
#
# 用法:
#   每天收盘后跑一次，输出第二天的关注清单
#   第二天开盘后手动看分时图找买点
#   买入后次日9:40附近卖出
# ============================================================

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import os

CSV_PATH = r"C:\Users\Administrator\Desktop\全市场A股_20260506_20260605_带日期涨停.csv"
COL_DATE = "index"
COL_OPEN = "open"
COL_CLOSE = "close"
COL_HIGH = "high"
COL_LOW = "low"
COL_MONEY = "money"
COL_CODE = "证券代码"
COL_ZT = "是否涨停"

MONEY_MIN = 10_000_000_000
UP_THRESHOLD = 0.03

df = pd.read_csv(CSV_PATH)
df[COL_DATE] = pd.to_datetime(df[COL_DATE])
df.sort_values([COL_CODE, COL_DATE], inplace=True)

df["涨跌幅"] = df.groupby(COL_CODE)[COL_CLOSE].pct_change()
df["昨收"] = df.groupby(COL_CODE)[COL_CLOSE].shift(1)
df["昨高"] = df.groupby(COL_CODE)[COL_HIGH].shift(1)

cond = (
    (df[COL_CLOSE] > df[COL_OPEN]) &
    (df[COL_CLOSE] > df["昨高"]) &
    (df["昨收"] < df["昨收"].shift(1)) &
    (df[COL_MONEY] >= MONEY_MIN) &
    (df[COL_ZT] != 1) &
    (df["涨跌幅"] >= UP_THRESHOLD)
)
signals = df[cond].copy()

signals["今日涨幅%"] = signals["涨跌幅"] * 100
signals["成交额(亿)"] = signals[COL_MONEY] / 1e8

today = df[COL_DATE].max()
print("=" * 60)
print(f"反包策略选股结果  数据截止: {today.date()}")
print(f"共选出 {len(signals)} 支")
print("=" * 60)

if len(signals) > 0:
    latest = signals[signals[COL_DATE] == today].copy()
    if len(latest) > 0:
        print()
        print(f"今日 ({today.date()}) 反包信号（明天关注）:")
        print(f"{'代码':<14} {'涨幅%':>7} {'成交额亿':>9} {'收盘':>7}")
        print("-" * 42)
        for _, r in latest.iterrows():
            print(f"{r[COL_CODE]:<14} {r['今日涨幅%']:>+6.2f}  {r['成交额(亿)']:>7.2f}   {r[COL_CLOSE]:>7.2f}")
        print("-" * 42)
        print()
        print("明天操作: 开盘看分时 -> 找买点 -> 买入 -> 后天9:40附近卖出")
    else:
        print(f"今日 ({today.date()}) 无信号")
else:
    print("无信号")

    # --- 保存 ---
out_path = os.path.join(os.path.dirname(__file__), "fanbao_signals.csv")
if len(signals) > 0:
    cols_out = [COL_DATE, COL_CODE, "今日涨幅%", "成交额(亿)", COL_CLOSE]
    signals[cols_out].to_csv(out_path, index=False, encoding="utf-8")
    print(f"保存: {out_path}")
else:
    print("无信号，跳过保存")
