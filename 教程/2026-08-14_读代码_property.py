# ============================================================
# 读代码练习 4：@property 装饰器（属性当函数用）
#
# 对应仓库文件：backtest/backtest_engine.py
# BacktestResult 里的 win_rate、max_drawdown 都是 @property，
# 外部写 result.win_rate 就能拿到计算结果，不用加括号。
# ============================================================

from dataclasses import dataclass


@dataclass
class Trade:
    """一笔交易的记录。"""
    code: str
    pnl_pct: float  # 这笔赚/亏几个点


class BacktestResult:
    """回测结果：保存交易列表，指标现算现给。"""

    def __init__(self, trades: list[Trade]) -> None:
        self.trades = trades

    @property
    def total_trades(self) -> int:
        """交易笔数：列表里有几条就是几笔。"""
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        """胜率：赚钱的笔数 / 总笔数 x 100。"""
        if not self.trades:
            return 0.0
        wins = 0
        for t in self.trades:
            if t.pnl_pct > 0:
                wins += 1
        return wins / len(self.trades) * 100

    @property
    def avg_return(self) -> float:
        """平均每笔收益。"""
        if not self.trades:
            return 0.0
        total = sum(t.pnl_pct for t in self.trades)
        return total / len(self.trades)


def main() -> None:
    trades = [
        Trade("A", 5.0),
        Trade("B", -2.0),
        Trade("C", 3.0),
        Trade("D", -1.0),
    ]
    result = BacktestResult(trades)

    # 关键：win_rate 后面没有括号，但会自动执行上面的函数
    print("总交易笔数: {}".format(result.total_trades))
    print("胜率: {:.1f}%".format(result.win_rate))
    print("平均每笔: {:+.2f}%".format(result.avg_return))


if __name__ == "__main__":
    main()
