# -*- coding: utf-8 -*-
# ============================================================
# 反包策略主代码（逐行注释版）
# ============================================================
# 用法：
#   1. 先运行，看输出
#   2. 再逐行读注释，遮住注释自己说一遍
#   3. 最后做文件底部的 4 个实验
#
# 语法不懂时去查：2026-08-16_Python语法表.py
#
# 学习标准：
#   每一行都能说出"在干什么" + "删掉或改掉会怎样"
# ============================================================

import sys
import io

import numpy as np
import pandas as pd
from pathlib import Path

# 让控制台能正常显示中文
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 找数据文件：当前文件在"教程"文件夹里，
# parents[1] 就是再往上一级，也就是仓库根目录
CSV = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "全市场A股_2026-04-12_2026-06-12.csv"
)

# 读取 CSV 成 DataFrame，相当于把 Excel 表格读进 Python
df = pd.read_csv(CSV)

# "index" 这一列是日期，现在是字符串，转成真正的日期格式
df["index"] = pd.to_datetime(df["index"])

# 按股票代码排序，同一只股票的日期从小到大排列
# inplace=True 表示"直接改这张表本身"
df.sort_values(["证券代码", "index"], inplace=True)

# 对每只股票单独算 7 日均线
# rolling(7).mean() 表示"最近 7 天收盘价的平均"
df["M7"] = df.groupby("证券代码")["close"].transform(
    lambda x: x.rolling(7).mean()
)

# 对每只股票单独算 14 日均线
df["M14"] = df.groupby("证券代码")["close"].transform(
    lambda x: x.rolling(14).mean()
)

# shift(1) 表示"把这一列往下挪一行"
# zt_Tm2 就是"昨天记录的当天是否涨停"，
# 所以 shift(1) 之后等于拿到了 T-2 的涨停状态
df["zt_Tm2"] = df.groupby("证券代码")["是否涨停"].shift(1)

# ======================= 选股条件 =======================

# 实体涨跌幅 = (收盘 - 开盘) / 开盘
# 收盘比开盘高，是阳线；比开盘低，是阴线
df["实体涨跌幅"] = (df["close"] - df["open"]) / df["open"]

# 把五个条件用 & 连起来，同时成立才算 1，否则是 0
df["信号"] = (
    (df["zt_Tm2"] == 1) &              # T-2 涨停过
    (df["是否涨停"] == 0) &             # T-1 没涨停，断板
    (df["money"] > 1_500_000_000) &     # T-1 成交额大于 15 亿
    (df["M7"] / df["M14"] > 1) &        # 短期均线在长期均线上方
    (df["实体涨跌幅"] > -0.03) &         # 实体跌幅不能超过 3%
    df["M14"].notna()                   # M14 有值才算（前面天数不够）
).astype(int)

# ======================= 下面不用改 =======================

# 统计一共多少个信号
print(f"信号总数: {df['信号'].sum()}")
print()

# trades 是空列表，后面把每一笔交易放进来
trades = []

# 只拿信号为 1 的行，一行一行处理
# _ 是"行号我不要"，row 才是这一行数据
for _, row in df[df["信号"] == 1].iterrows():

    # 取出信号日的股票代码和日期
    code = row["证券代码"]
    t1 = row["index"]

    # 找同一只股票、日期在信号日之后的所有行
    td = df[(df["证券代码"] == code) & (df["index"] > t1)]

    # 如果信号日是最后一天，后面没有数据，跳过这单
    if td.empty:
        continue

    # 信号日之后的第一天 = 第二天，
    # 用第二天开盘价作为买入价
    bp = td.iloc[0]["open"]

    # 再找买入日之后的所有行
    tp1 = df[(df["证券代码"] == code) & (df["index"] > td.iloc[0]["index"])]

    # 如果买入日之后没有数据，跳过这单
    if tp1.empty:
        continue

    # 买入日之后的第一天 = 第三天，
    # 用第三天收盘价作为卖出价
    sp = tp1.iloc[0]["close"]

    # 收益率 = (卖出价 - 买入价) / 买入价 * 100
    pnl = (sp - bp) / bp * 100

    # 把这一笔交易存进列表
    trades.append({"code": code, "bp": bp, "sp": sp, "pnl": pnl})

# 取出所有收益率，做成一个新列表
pnls = [t["pnl"] for t in trades]

# 大于 0 算盈利，小于等于 0 算亏损
w_pnls = [p for p in pnls if p > 0]
l_pnls = [p for p in pnls if p <= 0]

# 输出统计结果
print(f"信号总笔数    {len(pnls)}")
print(f"盈利笔数      {len(w_pnls)}")
print(f"亏损笔数      {len(l_pnls)}")
print(f"胜率          {len(w_pnls)}/{len(pnls)} ({len(w_pnls) / len(pnls) * 100:.1f}%)")
print(f"平均盈亏      {np.mean(pnls):+.2f}%")
print(f"平均盈利      {np.mean(w_pnls):+.2f}%")
print(f"平均亏损      {np.mean(l_pnls):+.2f}%")
print(f"盈亏比        {abs(np.mean(w_pnls) / np.mean(l_pnls)):.2f}")
print(f"最大盈利      {max(pnls):+.2f}%")
print(f"最大亏损      {min(pnls):+.2f}%")
print(f"收益标准差    {np.std(pnls):.2f}%")


# ============================================================
# 做完上面这些，再做下面 4 个实验
# ============================================================

# 实验 1：把 15 亿改成 25 亿
#   把 (df["money"] > 1_500_000_000) 改成 (df["money"] > 2_500_000_000)
#   观察：信号数变少，胜率和平均盈亏会怎么变

# 实验 2：把 M7/M14 > 1 改成 > 1.05
#   把 (df["M7"] / df["M14"] > 1) 改成 > 1.05
#   观察：信号数、胜率、平均盈亏、盈亏比的变化

# 实验 3：删掉实体涨跌幅这一行
#   把 (df["实体涨跌幅"] > -0.03) & 这一行删掉
#   观察：信号数变多，胜率和平均盈亏是变好还是变差

# 实验 4：把买入和卖出逻辑反过来
#   想一想：如果第二天收盘买、第三天开盘卖，结果会怎样？
#   再想一想：A 股 T+1 规则下，能不能信号日当天买入？

# 做完一个实验，就把结果记在教程/2026-08-16_学习笔记.md 里
