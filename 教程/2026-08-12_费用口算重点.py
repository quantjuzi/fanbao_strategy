# -*- coding: utf-8 -*-
# 2026-08-12 费用口算重点（手机复习版）
# 四笔钱：佣金、过户费、印花税、滑点

def commission(amount: float) -> float:
    fee = amount * 0.00025          # 万2.5
    return max(fee, 5.0)            # 最低 5 元

def transfer_fee(amount: float) -> float:
    return amount * 0.00001         # 万0.1，买卖都收

def stamp_duty(amount: float) -> float:
    return amount * 0.0005          # 万5，只有卖出收

def buy_fill(reference: float) -> float:
    return reference * (1 + 0.001)  # 买入：参考价 × (1 + 滑点)

def sell_fill(reference: float) -> float:
    return reference * (1 - 0.001)  # 卖出：参考价 × (1 - 滑点)

# 口算：股价 10 元，买 1000 股 = 成交额 10000 元
amount = 10 * 1000
buy_fee = commission(amount) + transfer_fee(amount)              # 5 + 0.1 = 5.1
sell_fee = commission(amount) + transfer_fee(amount) + stamp_duty(amount)  # 5 + 0.1 + 5 = 10.1
total_fee = buy_fee + sell_fee                                   # 15.2
print(buy_fee, sell_fee, total_fee)

# 重点公式：
# 买入费用 = 佣金 + 过户费（没有印花税）
# 卖出费用 = 佣金 + 过户费 + 印花税
# 保本涨幅 ≈ 一买一卖总费用 / 成交额
print(total_fee / amount)   # 0.00152 = 约 0.15%

# 滑点口诀：买贵一点，卖便宜一点
# 1 + 滑点：买入价往上加
# 1 - 滑点：卖出价往下减
# 想算真实盈亏，先算带滑点的成交价，再减所有费用
