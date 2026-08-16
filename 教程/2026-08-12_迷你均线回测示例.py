# -*- coding: utf-8 -*-
# 2026-08-12 迷你均线回测示例（手机阅读版）
#
# 读代码三步法：
# 1. 先看函数名：名字就是它要干什么
# 2. 再看括号：输入什么数据
# 3. 最后看 ->：返回什么结果
#
# 这个文件串起你最近学的知识点：
# df.copy() 保护原表、df["新列"] 建列、
# 布尔条件 & / |、dataclass(frozen=True) 固定参数、
# 佣金 / 印花税 / 滑点，最后算胜率和最大回撤。

import numpy as np
import pandas as pd
from dataclasses import dataclass


# ============================================================
# 一、配置类：把参数从代码里抽出来，改参数不用翻代码
# ============================================================
@dataclass(frozen=True)
class TradeConfig:
    initial_cash: float = 100_000.0   # 初始资金，单位：元
    commission_rate: float = 0.00025  # 佣金万2.5，买卖都收
    min_commission: float = 5.0       # 佣金最低收5元
    stamp_duty_rate: float = 0.0005   # 印花税万5，只有卖出收
    slippage: float = 0.002          # 滑点0.1%，买入加价卖出减价


# ============================================================
# 二、模拟数据：没有真实行情时，先用随机数造一张表
# ============================================================
def make_sample_data(days: int = 200) -> pd.DataFrame:
    """生成 days 天收盘价，返回一张只有 日期、收盘 的表。"""
    rng = np.random.default_rng(0)       # 固定随机种子，每次结果一样
    prices = 10 + np.cumsum(rng.normal(0, 0.3, days))  # 随机游走，模拟股价波动
    df = pd.DataFrame({
        "日期": pd.date_range("2026-01-01", periods=days, freq="D"),
        "收盘": prices,
    })
    return df


# ============================================================
# 三、策略信号：MA10
#上穿 MA20 买入,下穿卖出
# ============================================================
def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    """给原表加 均线、金叉、死叉 三列，返回新表。"""
    df = df.copy()                        # 复印一张，原表不动
    df["MA10"] = df["收盘"].rolling(5).mean()    # 10日均线，每行是最近10天均价
    df["MA20"] = df["收盘"].rolling(20).mean()  # 20日均线，最近20天均价

    # shift(1) 的意思是"把这一列往下挪一行"，拿到昨天的均线
    df["MA10_昨天"] = df["MA10"].shift(1)
    df["MA20_昨天"] = df["MA20"].shift(1)

    # & 是"并且"：今天10日线在20日线上方，并且昨天还在下方，才是"上穿"
    df["金叉"] = (df["MA10"] > df["MA20"]) & (df["MA10_昨天"] <= df["MA20_昨天"])
    df["死叉"] = (df["MA10"] < df["MA20"]) & (df["MA10_昨天"] >= df["MA20_昨天"])

    # 前20天均线还没算出来，信号是空值，先统一填 False（没有信号）
    df["金叉"] = df["金叉"].fillna(False)
    df["死叉"] = df["死叉"].fillna(False)
    return df


# ============================================================
# 四、手续费：两行小函数，先算单笔费用，再算总账
# ============================================================
def buy_fee(amount: float, cfg: TradeConfig) -> float:
    """买入费用 = 成交额 x 佣金，最少5元。没有印花税。"""
    return max(amount * cfg.commission_rate, cfg.min_commission)


def sell_fee(amount: float, cfg: TradeConfig) -> float:
    """卖出费用 = 佣金 + 印花税。卖出才交印花税。"""
    commission = max(amount * cfg.commission_rate, cfg.min_commission)
    return commission + amount * cfg.stamp_duty_rate


# ============================================================
# 五、回测主循环：每天看一次信号，有信号就交易
# ============================================================
def run_backtest(df: pd.DataFrame, cfg: TradeConfig) -> tuple:
    """按金叉死叉信号买卖，返回（交易明细表, 每日净值表）。"""
    cash = cfg.initial_cash      # 手上的现金，一开始就是全部本金
    shares = 0                   # 持仓股数，一开始空仓
    buy_cost = 0.0               # 本次买入花了多少钱（含费用），算盈亏要用
    trades = []                  # 每笔交易记录放这里
    equity_rows = []             # 每天的账户总资产放这里

    for i, row in df.iterrows():
        # 金叉 + 空仓：用所有现金买股，按100股一手取整
        # 最后一天不买：回测结束要强制清仓，买了又卖没意义
        if row["金叉"] and shares == 0 and i < len(df) - 1:
            fill_price = row["收盘"] * (1 + cfg.slippage)  # 买入实际价 = 参考价加滑点
            lots = int(cash / fill_price / 100)            # 能买几手
            if lots >= 1:
                shares = lots * 100                        # 股数 = 手数 x 100
                amount = fill_price * shares               # 成交额
                fee = buy_fee(amount, cfg)                 # 买入费用
                buy_cost = amount + fee                    # 记住总成本
                cash -= buy_cost                           # 现金减少
                buy_day = row["日期"].date()

        # 死叉 + 有仓位：全部卖出，记得给卖出价减滑点
        elif row["死叉"] and shares > 0:
            fill_price = row["收盘"] * (1 - cfg.slippage)  # 卖出实际价 = 参考价减滑点
            amount = fill_price * shares                   # 卖出成交额
            fee = sell_fee(amount, cfg)                    # 卖出费用
            cash += amount - fee                           # 现金增加
            pnl = (amount - fee) - buy_cost                # 净盈亏 = 到手钱 - 总成本
            trades.append({
                "买入日": buy_day,
                "卖出日": row["日期"].date(),
                "股数": shares,
                "盈亏": round(pnl, 2),
                "收益率%": round(pnl / buy_cost * 100, 2),
            })
            shares = 0                                     # 卖完就空仓

        # 不管有没有交易，每天记一次总资产 = 现金 + 持仓市值
        total_equity = cash + shares * row["收盘"]
        equity_rows.append({"日期": row["日期"].date(), "总资产": total_equity})

    # 回测结束还拿着股票，就用最后一天收盘价强制清仓，不然盈亏算不完
    if shares > 0:
        last = df.iloc[-1]
        fill_price = last["收盘"] * (1 - cfg.slippage)
        amount = fill_price * shares
        fee = sell_fee(amount, cfg)
        cash += amount - fee
        pnl = (amount - fee) - buy_cost
        trades.append({
            "买入日": buy_day,
            "卖出日": last["日期"].date(),
            "股数": shares,
            "盈亏": round(pnl, 2),
            "收益率%": round(pnl / buy_cost * 100, 2),
        })

    return pd.DataFrame(trades), pd.DataFrame(equity_rows)


# ============================================================
# 六、绩效统计：交易次数、胜率、累计收益、最大回撤
# ============================================================
def report(trades: pd.DataFrame, equity: pd.DataFrame, cfg: TradeConfig) -> None:
    """把回测结果打印出来，方便人眼判断策略好坏。"""
    if trades.empty:
        print("这次没有产生交易信号，先换一组随机数再试")
        return

    wins = (trades["盈亏"] > 0).sum()              # 盈利笔数
    win_rate = wins / len(trades) * 100            # 胜率 = 盈利笔数 / 总笔数
    final_equity = equity["总资产"].iloc[-1]       # 最后一天总资产
    total_return = (final_equity / cfg.initial_cash - 1) * 100  # 累计收益率

    # 最大回撤：每天算一次"从历史最高点跌了多少"，取最大的那个
    peak = equity["总资产"].cummax()               # 历史最高资产，cummax是累计最大值
    drawdown = equity["总资产"] / peak - 1         # 每天离最高点跌了多少
    max_drawdown = drawdown.min() * 100            # 最惨的一天

    print(f"交易次数：{len(trades)} 笔")
    print(f"胜率：{win_rate:.1f}%")
    print(f"累计收益率：{total_return:.1f}%")
    print(f"最大回撤：{max_drawdown:.1f}%")
    print("\n每笔交易明细：")
    print(trades)


# ============================================================
# 七、主流程：配置 -> 造数据 -> 加信号 -> 回测 -> 出报告
# ============================================================
if __name__ == "__main__":
    cfg = TradeConfig()                    # 用默认参数创建配置，frozen后改不了
    raw = make_sample_data(120)            # 造120天行情
    df = add_signals(raw)                  # 加均线和买卖信号
    trades_df, equity_df = run_backtest(df, cfg)  # 跑回测
    report(trades_df, equity_df, cfg)      # 打印绩效
