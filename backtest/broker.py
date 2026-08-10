"""A股交易成本模型：佣金、印花税、过户费、滑点。

任务：把 TODO 函数补完，让 tests/test_broker.py 全部通过。
完成标准：运行 `python tests/test_broker.py` 输出全部 OK。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerConfig:
    """交易成本参数，已配置好，不需要改。"""

    commission_rate: float = 0.00025   # 佣金费率：万2.5
    min_commission: float = 5.0        # 单笔最低佣金 5 元
    stamp_duty_rate: float = 0.0005    # 卖出印花税：0.05%
    transfer_fee_rate: float = 0.00001 # 过户费：0.001%，买卖双向
    slippage_rate: float = 0.001       # 滑点：0.1%


class Broker:
    """模拟真实成交：买入滑点向上，卖出滑点向下，并计算各项费用。"""

    def __init__(self, config: BrokerConfig | None = None) -> None:
        self.config = config or BrokerConfig()

    def buy_fill_price(self, reference_price: float) -> float:
        """买入实际成交价 = 参考价 * (1 + 滑点率)。示例已写好。"""
        return reference_price * (1 + self.config.slippage_rate)

    def sell_fill_price(self, reference_price: float) -> float:
        """卖出实际成交价 = 参考价 * (1 - 滑点率)。"""
        # TODO: 参考 buy_fill_price 补完
        raise NotImplementedError("请补完 sell_fill_price")

    def commission(self, amount: float) -> float:
        """佣金 = max(成交额 * 费率, 最低佣金)。"""
        # TODO: 补完
        raise NotImplementedError("请补完 commission")

    def transfer_fee(self, amount: float) -> float:
        """过户费 = 成交额 * 过户费率。"""
        # TODO: 补完
        raise NotImplementedError("请补完 transfer_fee")

    def buy_fee(self, price: float, qty: int) -> float:
        """买入费用 = 佣金 + 过户费（买入不收印花税）。"""
        # TODO: 先算 amount = price * qty，再组合上面两个函数
        raise NotImplementedError("请补完 buy_fee")

    def sell_fee(self, price: float, qty: int) -> float:
        """卖出费用 = 佣金 + 过户费 + 印花税。"""
        # TODO: 参考 buy_fee，加上 amount * stamp_duty_rate
        raise NotImplementedError("请补完 sell_fee")

    def round_trip_fee(self, buy_price: float, sell_price: float, qty: int) -> float:
        """一次完整买卖的总费用 = 买入费用 + 卖出费用。"""
        # TODO: 补完
        raise NotImplementedError("请补完 round_trip_fee")

    def net_pnl(self, buy_ref: float, sell_ref: float, qty: int) -> float:
        """扣掉滑点和费用后的实际盈亏。"""
        # TODO:
        # 1. buy_fill = self.buy_fill_price(buy_ref)
        # 2. sell_fill = self.sell_fill_price(sell_ref)
        # 3. gross = (sell_fill - buy_fill) * qty
        # 4. fees = self.round_trip_fee(buy_fill, sell_fill, qty)
        # 5. 返回 gross - fees
        raise NotImplementedError("请补完 net_pnl")

    def round_trip_cost_pct(self, price: float, qty: int) -> float:
        """往返成本占成交额的百分比，判断一笔交易至少要涨多少才不亏。"""
        # TODO:
        # 1. buy_fill = self.buy_fill_price(price)
        # 2. sell_fill = self.sell_fill_price(price)
        # 3. slippage_loss = (buy_fill - sell_fill) * qty
        # 4. fees = self.round_trip_fee(buy_fill, sell_fill, qty)
        # 5. 返回 (slippage_loss + fees) / (price * qty) * 100
        raise NotImplementedError("请补完 round_trip_cost_pct")
