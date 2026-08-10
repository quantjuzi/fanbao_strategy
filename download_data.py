# -*- coding: utf-8 -*-
"""从聚宽下载A股日线数据 - 炸板策略因子计算 (试用版)

试用账号: 2025-04-21 ~ 2026-04-28
生成: 日线行情、成交额(亿)、T-1涨停标记、竞价涨跌幅、是否炸板
支持断点续传: 每个批次单独保存到 data/jq_batches/, 额度用完次日重跑自动跳过已完成批次

用法: python download_data.py  (约10分钟, CSV保存到桌面)
"""

import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import jqdatasdk as jq
import pandas as pd

JQ_USER = "19967650001"
JQ_PASS = "Aa000612@"

# 兼容直接运行和从临时目录 exec 两种方式
if os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_data.py")):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
else:
    BASE_DIR = os.getcwd()
BATCH_DIR = os.path.join(BASE_DIR, "data", "jq_batches")
os.makedirs(BATCH_DIR, exist_ok=True)

START_DATE = "2025-04-21"
END_DATE = "2026-04-28"
BATCH_SIZE = 500

print("登录聚宽...", end="", flush=True)
jq.auth(JQ_USER, JQ_PASS)
quota_start = jq.get_query_count()
print(f"OK, 剩余额度: {quota_start}")

stocks = jq.get_all_securities(["stock"])
stock_list = [s for s in stocks.index.tolist() if s.startswith(("0", "3", "6"))]
print(f"A股: {len(stock_list)} 支")
print(f"下载 {START_DATE} ~ {END_DATE}")

batches = [stock_list[i:i + BATCH_SIZE] for i in range(0, len(stock_list), BATCH_SIZE)]
total = len(batches)
print(f"共 {total} 批, 每批 {BATCH_SIZE} 支")

downloaded = 0
for idx, batch in enumerate(batches):
    batch_file = os.path.join(BATCH_DIR, f"batch_{idx:03d}.csv")
    if os.path.exists(batch_file) and os.path.getsize(batch_file) > 0:
        print(f"  [{idx + 1}/{total}] 已存在, 跳过")
        continue
    print(f"  [{idx + 1}/{total}] 下载 {len(batch)} 支...", flush=True)
    try:
        df = jq.get_price(batch, start_date=START_DATE, end_date=END_DATE,
            frequency="daily",
            fields=["open", "close", "high", "low", "volume", "money",
                    "pre_close", "high_limit", "low_limit", "paused"],
            skip_paused=False, fq="pre")
        if df is None or df.empty:
            print("      返回空数据")
            continue
        df.reset_index().to_csv(batch_file, index=False, encoding="utf-8-sig")
        downloaded += 1
        print(f"      已保存 {len(df)} 行, 剩余额度: {jq.get_query_count()}")
    except Exception as e:
        print(f"      下载失败: {e}")
        print(f"      剩余额度: {jq.get_query_count()}")
        break

print()
print(f"本次新增 {downloaded} 批, 剩余额度: {jq.get_query_count()}")

# 合并所有已完成的批次
batch_files = [os.path.join(BATCH_DIR, f) for f in sorted(os.listdir(BATCH_DIR))
               if f.startswith("batch_") and f.endswith(".csv")]
if not batch_files:
    print("没有任何批次数据, 退出")
    sys.exit(1)

print(f"合并 {len(batch_files)}/{total} 批...")
result = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in batch_files], ignore_index=True)
print(f"原始: {len(result)} 行, 股票数: {result['code'].nunique()}")

if len(batch_files) < total:
    print(f"警告: 还缺 {total - len(batch_files)} 批, 数据不完整; 额度恢复后重跑本脚本自动续传")

print("计算衍生因子...")
result["成交额_亿"] = (result["money"] / 1e8).round(2)
result["is_paused"] = result["paused"].fillna(0).astype(int)
result["is_limit_up"] = (result["close"] >= result["high_limit"] * 0.99).astype(int)
result = result.sort_values(["code", "time"]).reset_index(drop=True)
result["prev_limit_up"] = result.groupby("code")["is_limit_up"].shift(1).fillna(0).astype(int)
result["is_zhaban"] = ((result["high"] >= result["high_limit"] * 0.999) &
                       (result["close"] < result["high_limit"]) &
                       (result["is_paused"] == 0)).astype(int)
result["auction_pct"] = ((result["open"].fillna(result["pre_close"]) / result["pre_close"]) - 1) * 100
result = result.sort_values(["time", "code"]).reset_index(drop=True)

zhaban_df = result[result["is_zhaban"] == 1].copy()
print(f"炸板样本: {len(zhaban_df)} 次")
if len(zhaban_df) > 0:
    print(f"  平均竞价涨幅: {zhaban_df['auction_pct'].mean():.2f}%")
    print(f"  平均成交额: {zhaban_df['money'].mean() / 1e8:.2f}亿")

out = os.path.join(BASE_DIR, "data", f"全市场A股_{START_DATE}_{END_DATE}.csv")
result.to_csv(out, index=False, encoding="utf-8-sig")
print(f"全量: {len(result)} 行 -> {out}")

z_out = os.path.join(BASE_DIR, "data", f"炸板样本_{START_DATE}_{END_DATE}.csv")
if len(zhaban_df) > 0:
    zhaban_df.to_csv(z_out, index=False, encoding="utf-8-sig")
    print(f"炸板: {len(zhaban_df)} 行 -> {z_out}")

print(f"股票数: {result['code'].nunique()}")

# 尝试同步一份到桌面, 失败不阻塞
desktop = os.path.expanduser("~/Desktop")
for src in (out, z_out):
    try:
        if os.path.isfile(src) and os.path.isdir(desktop):
            import shutil
            shutil.copy(src, os.path.join(desktop, os.path.basename(src)))
            print(f"桌面副本: {os.path.basename(src)}")
    except Exception as e:
        print(f"桌面副本失败(可忽略): {e}")
