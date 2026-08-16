# -*- coding: utf-8 -*-
# 2026-08-12 类型标注、self 与 dataclass（手机复习版）
#
# def run(self, df: pd.DataFrame) -> pd.DataFrame:
#   def   = 定义一个函数
#   run   = 函数名
#   self  = 我自己，调用时 Python 自动填
#   df    = 参数
#   : pd.DataFrame = 参数类型标注
#   ->    = 返回箭头
#   -> pd.DataFrame = 返回一张表

from dataclasses import dataclass

# ============================================================
# 一、普通 class：__init__ 自己写
# ============================================================
class Person:
    def __init__(self, name: str, age: int) -> None:
        self.name = name   # 把传进来的 name 存到对象里
        self.age = age

p = Person("小明", 30)
print(p.name)   # 小明

# ============================================================
# 二、dataclass：自动生成 __init__ 和 __repr__
# ============================================================
@dataclass
class Person2:
    name: str
    age: int

p2 = Person2("小红", 28)
print(p2)       # Person2(name='小红', age=28)，这就是 repr

# ============================================================
# 三、frozen=True：数据固定，防止中途改费率
# ============================================================
@dataclass(frozen=True)
class BrokerConfig:
    commission_rate: float = 0.00025   # 佣金 万2.5

config = BrokerConfig()
# config.commission_rate = 0.001   # 取消注释会报错，这就是保护

# ============================================================
# 四、默认参数陷阱：None 占位，函数里再建
# ============================================================
@dataclass
class Broker:
    config: BrokerConfig | None = None

    def get_config(self) -> BrokerConfig:
        return self.config or BrokerConfig()

b1 = Broker()
b2 = Broker()
print(b1.get_config() is b2.get_config())  # False，每次都是新配置

# 重点：
# 1. self 调用时不用写
# 2. -> 只是给人看的类型提示，不强制
# 3. dataclass 省掉 __init__ / __repr__ 模板代码
# 4. frozen=True 是防改，不是防新建
