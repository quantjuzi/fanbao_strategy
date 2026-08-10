# broker.py 逐行翻译（学习用）

## 读法

1. 先只看“代码”和“中文意思”两列，不搜单词。
2. 看到 `: float`、`-> float` 这种，先当成“标签”，跳过，不影响理解。
3. 每天只读 1~2 个函数，读完后遮住中文，自己再说一遍。

## 固定开头（记一次就行）

| 代码 | 中文意思 |
|---|---|
| `from __future__ import annotations` | 让类型注解延迟解析，先当成固定开头，不用深究 |
| `from dataclasses import dataclass` | 导入标准库的 dataclass，用来少写初始化代码 |
| `@dataclass(frozen=True)` | 自动生成类的初始化方法；frozen=True 表示参数定好后不能改 |
| `class BrokerConfig:` | 定义一个“配置”类，专门装交易成本参数 |

## 配置参数（不用改，只要看懂数值）

| 代码 | 中文意思 |
|---|---|
| `commission_rate: float = 0.00025` | 佣金费率，万 2.5 |
| `min_commission: float = 5.0` | 单笔最低佣金 5 元 |
| `stamp_duty_rate: float = 0.0005` | 卖出印花税 0.05% |
| `transfer_fee_rate: float = 0.00001` | 过户费 0.001%，买卖双向收 |
| `slippage_rate: float = 0.001` | 滑点 0.1% |

## Broker 类

| 代码 | 中文意思 |
|---|---|
| `class Broker:` | 定义一个“券商”类，模拟真实成交 |
| `def __init__(self, config: BrokerConfig \| None = None) -> None:` | 创建券商时，参数可传可不传 |
| `self.config = config or BrokerConfig()` | 没传配置就用默认配置；self 指“这个券商自己” |

## 已写好的示例（先看懂这一个）

| 代码 | 中文意思 |
|---|---|
| `def buy_fill_price(self, reference_price: float) -> float:` | 定义一个方法：算买入实际成交价 |
| `return reference_price * (1 + self.config.slippage_rate)` | 买入价 = 参考价 × (1 + 滑点)，买贵一点 |

## 8 个 TODO（自己补，先补第一个）

| 代码 | 中文意思 |
|---|---|
| `def sell_fill_price(self, reference_price: float) -> float:` | 卖出实际成交价（TODO） |
| `# 参考 buy_fill_price 补完` | 卖出价 = 参考价 × (1 - 滑点)，卖便宜一点 |
| `def commission(self, amount: float) -> float:` | 佣金（TODO） |
| `# 佣金 = max(成交额 * 费率, 最低佣金)` | 取成交额×费率 和 5 元中更大的那个 |
| `def transfer_fee(self, amount: float) -> float:` | 过户费（TODO） |
| `# 过户费 = 成交额 * 过户费率` | 直接相乘 |
| `def buy_fee(self, price: float, qty: int) -> float:` | 买入费用（TODO） |
| `# 买入费用 = 佣金 + 过户费` | 买入不收印花税 |
| `def sell_fee(self, price: float, qty: int) -> float:` | 卖出费用（TODO） |
| `# 卖出费用 = 佣金 + 过户费 + 印花税` | 比买入多一项印花税 |
| `def round_trip_fee(self, buy_price, sell_price, qty) -> float:` | 一次完整买卖的总费用（TODO） |
| `# 总费用 = 买入费用 + 卖出费用` | 把上面两个加起来 |
| `def net_pnl(self, buy_ref, sell_ref, qty) -> float:` | 扣掉滑点和费用后的实际盈亏（TODO） |
| `# 5 步：成交价 → 毛盈亏 → 减费用` | 先算买卖价差赚多少，再扣成本 |
| `def round_trip_cost_pct(self, price, qty) -> float:` | 往返成本占成交额的百分比（TODO） |
| `# 判断一笔交易至少涨多少才不亏` | 成本 ÷ 成交额 × 100 |

## 一句话总结

这个文件就是在算一件事：**一笔买卖，除了涨跌，还亏在佣金、印花税、过户费、滑点上**。每个函数都是“算其中一种成本”，TODO 就是让你把这些成本公式自己写出来。
