# ============================================================
# 每日反包选股 + 内外盘比
#
# 流程:
#   1. 读取日线CSV，筛选反包候选
#   2. 对候选股拉东方财富分笔数据，计算外盘/内盘比
#   3. 只保留外盘 > 内盘的股票
#   4. 输出最终清单
#
# 用法: 每天收盘后跑一次
# ============================================================

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import requests
import json
import os
import time

# ========== 配置 ==========
CSV_PATH = r"C:\Users\Administrator\Desktop\全市场A股_20260506_20260605_带日期涨停.csv"
MONEY_MIN = 10_000_000_000      # 成交额 >= 10亿
UP_THRESHOLD = 0.03              # 反包日涨幅 >= 3%
WAIPAN_RATIO_MIN = 1.0           # 外盘/内盘 > 1（买入意愿强于卖出）
# ==========================

# --- 1. 日线筛选反包候选 ---
df = pd.read_csv(CSV_PATH)
df["index"] = pd.to_datetime(df["index"])
df.sort_values(["证券代码", "index"], inplace=True)

df["涨跌幅"] = df.groupby("证券代码")["close"].pct_change()
df["昨收"] = df.groupby("证券代码")["close"].shift(1)
df["昨高"] = df.groupby("证券代码")["high"].shift(1)

cond = (
    (df["close"] > df["open"]) &          # 阳线
    (df["close"] > df["昨高"]) &          # 反包
    (df["昨收"] < df["昨收"].shift(1)) &  # 昨天跌
    (df["money"] >= MONEY_MIN) &          # 大票
    (df["是否涨停"] != 1) &               # 今天未涨停
    (df["涨跌幅"] >= UP_THRESHOLD)        # 涨幅够
)
candidates = df[cond].copy()

today = df["index"].max()
latest = candidates[candidates["index"] == today]

print(f"日线筛选: 共 {len(candidates)} 支历史信号")
print(f"今日候选: {len(latest)} 支")

if len(latest) == 0:
    print("今日无候选，无需拉内外盘数据")
    exit()

# --- 2. 拉内外盘数据 ---
def get_waipan_neipan(code):
    """从东方财富拉分笔数据，返回(外盘, 内盘)"""
    # 代码转换: 000001.XSHE → 0.000001, 600001.XSHG → 1.600001
    if ".XSHE" in code:
        secid = "0." + code.replace(".XSHE", "")
    elif ".XSHG" in code:
        secid = "1." + code.replace(".XSHG", "")
    else:
        return None, None

    url = "https://push2.eastmoney.com/api/qt/stock/details/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4",
        "fields2": "f51,f52,f53,f54,f55",
        "pos": -1,
        "lmt": 5000,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2,
        "invt": 2,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        details = data["data"]["details"]
        waipan, neipan = 0, 0
        for d in details:
            parts = d.split(",")
            vol, direction = int(parts[2]), int(parts[4])
            if direction == 1:
                waipan += vol
            elif direction == 2:
                neipan += vol
        return waipan, neipan
    except Exception as e:
        print(f"  {code} 拉分笔失败: {e}")
        return None, None

print()
print(f"{'代码':<14} {'涨幅%':>6} {'成交额亿':>9} {'外盘':>10} {'内盘':>10} {'内外比':>7} {'结果':>6}")
print("-" * 65)

final_list = []
for _, row in latest.iterrows():
    code = row["证券代码"]
    waipan, neipan = get_waipan_neipan(code)

    if waipan is None or neipan is None or neipan == 0:
        result = "数据异常"
        ratio = 0
    else:
        ratio = waipan / neipan
        result = "入选" if ratio > WAIPAN_RATIO_MIN else "淘汰"

    if result == "入选":
        final_list.append(code)

    money_yi = row["money"] / 1e8
    up_pct = row["涨跌幅"] * 100
    waipan_str = f"{waipan/10000:.0f}万" if waipan else "-"
    neipan_str = f"{neipan/10000:.0f}万" if neipan else "-"
    ratio_str = f"{ratio:.2f}" if ratio else "-"
    print(f"{code:<14} {up_pct:>+5.2f}  {money_yi:>7.2f}  {waipan_str:>10} {neipan_str:>10} {ratio_str:>7} {result}")
    time.sleep(0.5)  # 间隔，避免被限流

print("-" * 65)

if final_list:
    print(f"\n最终入选 {len(final_list)} 支:")
    for c in final_list:
        print(f"  {c}")
    print()
    print("【明日操作】开盘看分时 → 找买点 → 买入 → 后天9:40附近卖出")
else:
    print("\n内外盘筛选后无入选股票")

# --- 3. 保存结果 ---
out_path = os.path.join(os.path.dirname(__file__), "today_signals.csv")
if final_list:
    pd.DataFrame({"代码": final_list}).to_csv(out_path, index=False, encoding="utf-8")
    print(f"\n已保存: {out_path}")
