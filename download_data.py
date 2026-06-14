# ============================================================
# 从聚宽下载A股全市场日线数据
# 
# 用法:
#   1. 把下面用户名和密码改成你的聚宽账号
#   2. 直接运行，10分钟左右下载完
#   3. CSV 会保存到桌面
# ============================================================

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import jqdatasdk as jq
import pandas as pd
import time

# ========== 修改成你的聚宽账号 ==========
JQ_USER = "你的聚宽用户名"
JQ_PASS = "你的聚宽密码"
# =======================================

# 登录
print("正在登录聚宽...")
jq.auth(JQ_USER, JQ_PASS)
print("登录成功")

# 获取所有A股股票列表
print("正在获取股票列表...")
stocks = jq.get_all_securities(["stock"])
stock_list = stocks.index.tolist()
print(f"共 {len(stock_list)} 支股票")

# 设置日期范围
start_date = "2026-05-06"
end_date = "2026-06-12"

print(f"正在下载数据 {start_date} ~ {end_date} ...")

# 分批下载，每批500支，避免内存溢出
batch_size = 500
all_data = []

for i in range(0, len(stock_list), batch_size):
    batch = stock_list[i : i + batch_size]
    print(f"  下载第 {i//batch_size + 1}/{(len(stock_list)-1)//batch_size + 1} 批 ({len(batch)} 支)...")

    df = jq.get_price(
        batch,
        start_date=start_date,
        end_date=end_date,
        frequency="daily",
        fields=["open", "close", "high", "low", "volume", "money",
                "pre_close", "high_limit", "low_limit", "paused"],
        skip_paused=False,
        fq="pre",
    )

    if df is not None and not df.empty:
        df = df.reset_index()
        all_data.append(df)

    time.sleep(1)  # 间隔一下，防止被限流

# 合并数据
print("正在合并数据...")
result = pd.concat(all_data, ignore_index=True)

# 添加是否涨停列
print("正在计算是否涨停...")
result["是否涨停"] = (result["close"] >= result["high_limit"] * 0.99).astype(int)

# 排序
result = result.sort_values(["time", "code"]).reset_index(drop=True)

# 重命名列，跟你之前的CSV保持一致
result = result.rename(columns={
    "time": "index",
    "code": "证券代码",
    "volume": "volume",
    "money": "money",
    "pre_close": "pre_close",
    "high_limit": "high_limit",
    "low_limit": "low_limit",
})

# 保存
import os
desktop = os.path.expanduser("~/Desktop")
out_path = os.path.join(desktop, f"全市场A股_{start_date}_{end_date}.csv")
result.to_csv(out_path, index=False, encoding="utf-8-sig")

print(f"\n下载完成！共 {len(result)} 行数据")
print(f"保存到: {out_path}")
print(f"日期范围: {start_date} ~ {end_date}")
print(f"股票数量: {result['证券代码'].nunique()}")
