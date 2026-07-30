# -*- coding: utf-8 -*-
"""从聚宽下载A股日线数据 - 炸板策略因子计算 (试用版)

试用账号: 2025-04-21 ~ 2026-04-28
生成: 日线行情、成交额(亿)、T-1涨停标记、竞价涨跌幅、是否炸板

用法: python download_data.py  (约10分钟, CSV保存到桌面)
"""

import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import jqdatasdk as jq
import pandas as pd

JQ_USER = "19967650001"
JQ_PASS = "Aa000612@"

print("登录聚宽...", end="", flush=True)
jq.auth(JQ_USER, JQ_PASS)
print(f"OK, 额度: {jq.get_query_count()}")

stocks = jq.get_all_securities(["stock"])
stock_list = [s for s in stocks.index.tolist() if s.startswith(("0","3","6"))]
print(f"A股: {len(stock_list)} 支")

start_date = "2025-04-21"
end_date = "2026-04-28"
print(f"下载 {start_date} ~ {end_date}")

all_data = []
batch_size = 500
total = (len(stock_list)-1)//batch_size + 1

for i in range(0, len(stock_list), batch_size):
    batch = stock_list[i:i+batch_size]
    print(f"  [{i//batch_size+1}/{total}] {len(batch)} 支")
    df = jq.get_price(batch, start_date=start_date, end_date=end_date,
        frequency="daily",
        fields=["open","close","high","low","volume","money",
                "pre_close","high_limit","low_limit","paused"],
        skip_paused=False, fq="pre")
    if df is not None and not df.empty:
        all_data.append(df.reset_index())

result = pd.concat(all_data, ignore_index=True)
print(f"原始: {len(result)} 行")

print("计算衍生因子...")
result["成交额_亿"] = (result["money"]/1e8).round(2)
result["is_paused"] = result["paused"].fillna(0).astype(int)
result["is_limit_up"] = (result["close"] >= result["high_limit"]*0.99).astype(int)
result = result.sort_values(["code","time"]).reset_index(drop=True)
result["prev_limit_up"] = result.groupby("code")["is_limit_up"].shift(1).fillna(0).astype(int)
result["is_zhaban"] = ((result["high"] >= result["high_limit"]*0.999) &
                       (result["close"] < result["high_limit"]) &
                       (result["is_paused"]==0)).astype(int)
result["auction_pct"] = ((result["open"].fillna(result["pre_close"])/result["pre_close"]) - 1) * 100
result = result.sort_values(["time","code"]).reset_index(drop=True)

zhaban_df = result[result["is_zhaban"]==1].copy()
print(f"炸板样本: {len(zhaban_df)} 次")
if len(zhaban_df) > 0:
    print(f"  平均竞价涨幅: {zhaban_df['auction_pct'].mean():.2f}%")
    print(f"  平均成交额: {zhaban_df['money'].mean()/1e8:.2f}亿")

desktop = os.path.expanduser("~/Desktop")
out = os.path.join(desktop, f"全市场A股_{start_date}_{end_date}.csv")
result.to_csv(out, index=False, encoding="utf-8-sig")
print(f"全量: {len(result)} 行 -> {out}")

z_out = os.path.join(desktop, f"炸板样本_{start_date}_{end_date}.csv")
if len(zhaban_df) > 0:
    zhaban_df.to_csv(z_out, index=False, encoding="utf-8-sig")
    print(f"炸板: {len(zhaban_df)} 行 -> {z_out}")

print(f"股票数: {result['code'].nunique()}")
