# ============================================================
# 读代码练习 5：列表推导（一行写出一个新列表）
#
# 对应仓库文件：backtest/backtest_engine.py
#   pnls = [t.pnl_pct for t in self.trades]
#   win_p = [p for p in pnls if p > 0]
# 就是把 for 循环 + append 缩成一行。
# ============================================================


def main() -> None:
    trades = [
        {"code": "A", "pnl_pct": 5.0},
        {"code": "B", "pnl_pct": -2.0},
        {"code": "C", "pnl_pct": 3.0},
        {"code": "D", "pnl_pct": -1.0},
    ]

    # 普通写法：一个一个 append 进列表
    pnls_old = []
    for t in trades:
        pnls_old.append(t["pnl_pct"])

    # 列表推导：同一件事，一行搞定
    pnls = [t["pnl_pct"] for t in trades]

    # 带 if 的列表推导：只挑出赚钱/亏钱的
    win_p = [p for p in pnls if p > 0]
    lose_p = [p for p in pnls if p <= 0]

    print("全部收益: {}".format(pnls))
    print("盈利的:   {}".format(win_p))
    print("亏损的:   {}".format(lose_p))
    print("平均盈利: {:+.2f}%".format(sum(win_p) / len(win_p)))
    print("平均亏损: {:+.2f}%".format(sum(lose_p) / len(lose_p)))


if __name__ == "__main__":
    main()
