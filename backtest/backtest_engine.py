# ============================================================
# 鍥炴祴寮曟搸 - 閫氱敤妗嗘灦
#
# 鐢ㄦ硶:
#   1. 鍐欎竴涓瓥鐣ュ嚱鏁帮紙鎺ユ敹涓€琛屾暟鎹拰鍘嗗彶鏁版嵁锛岃繑鍥炰俊鍙凤級
#   2. 鍠傜粰 backtest() 杩愯
#   3. 鑷姩杈撳嚭涓氱哗鎶ヨ〃
#
# 绀轰緥:
#   result = backtest(my_strategy, df)
#   result.print_report()
#   plot_result(result)
# ============================================================

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Trade:
    """涓€绗斾氦鏄撶殑瀹屾暣璁板綍"""
    code: str
    buy_date: str
    sell_date: str
    buy_price: float
    sell_price: float
    pnl_pct: float
    hold_days: int


@dataclass
class BacktestResult:
    trades: list
    equity_curve: list

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.pnl_pct > 0)
        return wins / len(self.trades) * 100

    @property
    def total_return(self) -> float:
        if not self.equity_curve:
            return 0.0
        return (self.equity_curve[-1] - 1) * 100

    @property
    def max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        mdd = 0.0
        for v in self.equity_curve:
            if v > peak:
                peak = v
            dd = (v - peak) / peak
            if dd < mdd:
                mdd = dd
        return mdd * 100

    @property
    def avg_return(self) -> float:
        if not self.trades:
            return 0.0
        return np.mean([t.pnl_pct for t in self.trades])

    @property
    def sharp_ratio(self) -> float:
        if not self.trades or len(self.trades) < 2:
            return 0.0
        returns = [t.pnl_pct for t in self.trades]
        std = np.std(returns)
        return np.mean(returns) / std * np.sqrt(252) if std > 0 else 0

    @property
    def report(self) -> str:
        lines = []
        lines.append("=" * 55)
        lines.append("鍥炴祴涓氱哗鎶ヨ〃")
        lines.append("=" * 55)
        lines.append(f"鎬讳氦鏄撴鏁?    {self.total_trades}")
        lines.append(f"鑳滅巼:          {self.win_rate:.1f}%")
        lines.append(f"绱鏀剁泭鐜?    {self.total_return:+.2f}%")
        lines.append(f"骞冲潎姣忕瑪鐩堜簭:  {self.avg_return:+.2f}%")
        lines.append(f"鏈€澶у洖鎾?      {self.max_drawdown:.2f}%")
        lines.append(f"澶忔櫘姣旂巼:      {self.sharp_ratio:.2f}")
        lines.append("-" * 55)
        if self.trades:
            pnls = [t.pnl_pct for t in self.trades]
            win_p = [p for p in pnls if p > 0]
            lose_p = [p for p in pnls if p <= 0]
            lines.append(f"鐩堝埄浜ゆ槗:      {len(win_p)}")
            lines.append(f"浜忔崯浜ゆ槗:      {len(lose_p)}")
            lines.append(f"骞冲潎鐩堝埄:      {np.mean(win_p):+.2f}%" if win_p else "N/A")
            lines.append(f"骞冲潎浜忔崯:      {np.mean(lose_p):+.2f}%" if lose_p else "N/A")
            lines.append(f"鏈€澶х泩鍒?      {max(pnls):+.2f}%")
            lines.append(f"鏈€澶т簭鎹?      {min(pnls):+.2f}%")
        lines.append("=" * 55)
        return "\n".join(lines)

    def print_report(self):
        print(self.report)


def backtest(strategy_fn, df, initial_cash=50000, max_positions=3, commission_rate=0.00025):
    df = df.copy()
    df["index"] = pd.to_datetime(df["index"])
    df.sort_values(["index", "璇佸埜浠ｇ爜"], inplace=True)
    dates = sorted(df["index"].unique())

    trades = []
    equity = [1.0]
    positions = {}
    cash = initial_cash

    for cur_date in dates:
        today = df[df["index"] == cur_date]
        if today.empty:
            continue

        # 1. 鍗栧嚭
        for code in list(positions.keys()):
            row = today[today["璇佸埜浠ｇ爜"] == code]
            if row.empty:
                continue
            r = row.iloc[0]
            sell_p = r["open"]
            buy_p, buy_d, vol = positions[code]
            pnl = (sell_p - buy_p) / buy_p * 100
            days = (cur_date - pd.to_datetime(buy_d)).days
            trades.append(Trade(code, buy_d, str(cur_date.date()), buy_p, sell_p, pnl, days))
            cash += sell_p * vol * (1 - commission_rate)
            del positions[code]

        # 2. 涔板叆
        for _, r in today.iterrows():
            if len(positions) >= max_positions:
                break
            hist = df[df["璇佸埜浠ｇ爜"] == r["璇佸埜浠ｇ爜"]]
            hist = hist[hist["index"] <= cur_date]
            signal = strategy_fn(r, hist)
            if signal != 1:
                continue
            buy_p = r["open"]
            share = cash / (max_positions - len(positions) + 1) * 0.95
            vol = int(share / buy_p / 100) * 100
            if vol < 100 or vol * buy_p * (1 + commission_rate) > cash:
                continue
            positions[r["璇佸埜浠ｇ爜"]] = (buy_p, str(cur_date.date()), vol)
            cash -= vol * buy_p * (1 + commission_rate)

        # 3. 鎬昏祫浜?        total = cash
        for code, (bp, bd, vol) in positions.items():
            row = today[today["璇佸埜浠ｇ爜"] == code]
            cp = row.iloc[0]["close"] if not row.empty else bp
            total += cp * vol
        equity.append(total / initial_cash)

    return BacktestResult(trades, equity)


def plot_result(result, save_path=None):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]})
        fig.suptitle("鍥炴祴缁撴灉", fontsize=14)
        ax1 = axes[0]
        ax1.plot(result.equity_curve, label="鍑€鍊?, color="blue", lw=1.5)
        ax1.axhline(1.0, color="gray", ls="--", alpha=0.5)
        ax1.fill_between(range(len(result.equity_curve)), 1, result.equity_curve, color="red", alpha=0.1)
        ax1.set_ylabel("鍑€鍊?); ax1.legend(loc="upper left"); ax1.grid(True, alpha=0.3)
        info = f"绱鏀剁泭: {result.total_return:+.1f}%\n鑳滅巼: {result.win_rate:.1f}%\n鏈€澶у洖鎾? {result.max_drawdown:.1f}%\n澶忔櫘: {result.sharp_ratio:.2f}"
        ax1.text(0.98, 0.95, info, transform=ax1.transAxes, va="top", ha="right", bbox=dict(boxstyle="round", fc="white", alpha=0.8))
        ax2 = axes[1]
        if result.trades:
            pnls = [t.pnl_pct for t in result.trades]
            colors = ["red" if p > 0 else "green" for p in pnls]
            ax2.bar(range(len(pnls)), pnls, color=colors, alpha=0.7)
            ax2.axhline(0, color="gray", lw=0.5)
            ax2.set_ylabel("鍗曠瑪鐩堜簭%"); ax2.set_xlabel("浜ゆ槗搴忓彿"); ax2.grid(True, alpha=0.3)
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"鍥捐〃宸蹭繚瀛? {save_path}")
        plt.close()
    except ImportError:
        print("璇峰畨瑁?matplotlib: pip install matplotlib")


if __name__ == "__main__":
    print("鍥炴祴寮曟搸鍔犺浇瀹屾垚")
    print()
    print("浣跨敤鏂规硶:")
    print("  1. 鍐欑瓥鐣? def my_strat(row, hist): return 1 or 0")
    print("  2. 鍥炴祴: result = backtest(my_strat, df)")
    print("  3. 鎶ヨ〃: result.print_report()")
    print("  4. 鐢诲浘: plot_result(result)")

