# ============================================================
# 读代码练习 6：元组解包（一个变量里装三个值）
#
# 对应仓库文件：backtest/backtest_engine.py
#   持仓字典里每个股票存一个元组 (买入价, 买入日, 股数)
#   卖的时候 buy_p, buy_d, vol = positions[code] 一次取出来
# ============================================================


def main() -> None:
    # 持仓字典：股票代码 -> (买入价, 买入日期, 股数)
    positions = {
        "600000": (10.0, "2026-08-12", 1000),
        "000001": (20.0, "2026-08-13", 500),
    }

    # 遍历字典：items() 同时拿出 key 和 value
    for code, (buy_p, buy_d, vol) in positions.items():
        print("股票 {} 买于 {}，成本 {}，{} 股".format(code, buy_d, buy_p, vol))

    # 卖出时解包：把元组里的三个值分别装进三个变量
    code = "600000"
    buy_p, buy_d, vol = positions[code]
    sell_p = 10.5
    pnl = (sell_p - buy_p) * vol
    print("\n卖出 {}：买入价 {}，卖出价 {}，盈利 {:.0f} 元".format(code, buy_p, sell_p, pnl))

    # 卖出后从持仓里删掉
    del positions[code]
    print("剩余持仓: {}".format(positions))


if __name__ == "__main__":
    main()
