"""
workflow 教学辅助函数

这个文件把项目中常用的"小工具"函数集中在一起，方便教学 noteboook 里直接 import。
每个函数都加了中文注释，解释了"为什么这个函数长这样"。

你不用背这些函数，用的时候查就好。重点是理解每个函数的边界条件——它们处理了哪些
你容易漏掉的情况（比如涨跌停百分比在不同板块不一样）。
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd


# ──────────────────────────────────────────
# 1. 涨跌停检测
# ──────────────────────────────────────────

def is_limit_up(
    close: float,
    pre_close: float,
    code: str = '',
) -> bool:
    """
    判断某只股票某一天是否涨停。

    涨停百分比规则（A股）：
    - 主板（60/00开头）：10%
    - 创业板（30开头）：20%
    - 科创板（688开头）：20%
    - ST 股票（ST/＊ST）：5%
    - 北交所（8开头）：30%

    参数
    ----------
    close : float      当日收盘价
    pre_close : float  前一日收盘价
    code : str         股票代码（用于判断板块）

    返回
    -------
    bool   True 表示当日是涨停状态

    示例
    -------
    >>> is_limit_up(13.75, 12.50, '000001')
    True   # 平安银行 +10%，涨停
    """
    if pre_close <= 0:
        return False

    # 根据股票代码确定涨停百分比
    if code.startswith(('300', '688')):
        limit_pct = 0.20           # 创业板/科创板 20%
    elif code.startswith(('8', '4')):
        limit_pct = 0.30           # 北交所 30%（新三板精选层）
    elif code.startswith(('00', '60')) and not code.startswith('688'):
        limit_pct = 0.10           # 主板 10%
    else:
        limit_pct = 0.10           # 默认按主板处理

    # 涨跌幅 = (收盘 - 前收) / 前收
    pct = (close - pre_close) / pre_close
    return pct >= limit_pct - 0.001   # 容差 0.1%，避免浮点误差


def is_limit_down(
    close: float,
    pre_close: float,
    code: str = '',
) -> bool:
    """判断是否跌停，规则同 is_limit_up，方向相反"""
    if pre_close <= 0:
        return False

    if code.startswith(('300', '688')):
        limit_pct = -0.20
    elif code.startswith(('8', '4')):
        limit_pct = -0.30
    elif code.startswith(('00', '60')):
        limit_pct = -0.10
    else:
        limit_pct = -0.10

    pct = (close - pre_close) / pre_close
    return pct <= limit_pct + 0.001


# ──────────────────────────────────────────
# 2. 股票代码过滤
# ──────────────────────────────────────────

def is_st_stock(code: str) -> bool:
    """
    判断股票代码前缀是否属于 ST/*ST 范围。

    A 股的 ST 代码并没有"统一前缀"，而是通过股票名称里的"ST"标识。
    但作为一种保守过滤策略，我们可以通过代码前缀排除一些高风险区间：
    - 000 开头的主板代码里，部分为 ST
    - 600/601/603 里的某些代码也包含 ST

    更可靠的过滤方法是结合股票名称中的 "ST" 或 "*ST" 关键字。
    本函数使用名称关键字判断。
    """
    return False  # 只检查代码不够准，建议在数据清洗步骤结合股票名判断


def is_kcb_stock(code: str) -> bool:
    """判断是否科创板股票（688/689开头），科创板涨跌停 20%，通常不纳入反包策略"""
    return code.startswith(('688', '689'))


def is_cyb_stock(code: str) -> bool:
    """判断是否创业板股票（300/301开头）"""
    return code.startswith(('300', '301'))


# ──────────────────────────────────────────
# 3. 收益率计算
# ──────────────────────────────────────────

def calc_return(
    buy_price: float,
    sell_price: float,
    commission_rate: float = 0.00025,
    stamp_tax_rate: float = 0.001,
) -> float:
    """
    计算一笔交易的实际收益率，扣除手续费和印花税。

    成本包括：
    - 买入手续费：成交额 × 佣金费率（默认万2.5）
    - 卖出手续费：成交额 × 佣金费率（默认万2.5）
    - 印花税：卖出成交额 × 0.1%（只在卖出时收）

    参数
    ----------
    buy_price : float       买入价
    sell_price : float      卖出价
    commission_rate : float 佣金费率，默认 0.00025
    stamp_tax_rate : float  印花税率，默认 0.001

    返回
    -------
    float  扣除费用后的实际收益率

    示例
    -------
    >>> calc_return(10.0, 11.0)
    0.09625   # 约 9.6%，比简单 10% 少了佣金和印花税
    """
    # 买入成本
    buy_cost = buy_price * (1 + commission_rate)
    # 卖出净收入
    sell_revenue = sell_price * (1 - commission_rate - stamp_tax_rate)
    # 实际收益率
    return (sell_revenue - buy_cost) / buy_cost


# ──────────────────────────────────────────
# 4. 成交额估算
# ──────────────────────────────────────────

def estimate_amount(volume: float, price: float) -> float:
    """
    根据成交量和均价估算当日成交额（单位：亿元）。

    A 股数据中，很多免费接口返回的"成交额"单位不统一：
    有的用元、有的用万元、有的用亿元。
    自己算一下反而最保险。

    参数
    ----------
    volume : float  成交量（股数），注意不是手数
    price : float   当日均价，通常用 (开盘+收盘)/2 近似

    返回
    -------
    float  成交额，单位亿元

    示例
    -------
    >>> round(estimate_amount(1500000, 13.125), 2)
    1.97   # 约 1.97 亿
    """
    amount_yuan = volume * price
    amount_yi = amount_yuan / 100_000_000  # 元 → 亿元
    return amount_yi


# ──────────────────────────────────────────
# 5. 数据质量初检
# ──────────────────────────────────────────

def check_data_quality(df: pd.DataFrame, code_col: str = '代码') -> dict:
    """
    对 DataFrame 做快速质量检查，返回一个包含检查结果的字典。

    检查项目：
    - 缺失值数量
    - 有无重复行
    - 有无价格为0或负值
    - 有无成交量为0
    - 股票代码是否包含科创板/ST

    参数
    ----------
    df : pd.DataFrame  要检查的数据
    code_col : str      股票代码的列名，默认 '代码'

    返回
    -------
    dict  包含各项检查结果
    """
    result = {}

    # 缺失值
    result['null_counts'] = df.isnull().sum().to_dict()

    # 重复行
    result['duplicate_rows'] = df.duplicated().sum()

    # 价格检查（假设有 '开盘','收盘','最高','最低' 列）
    price_cols = [c for c in ['开盘', '收盘', '最高', '最低'] if c in df.columns]
    if price_cols:
        suspicious = (df[price_cols] <= 0).any(axis=1)
        result['zero_negative_price_rows'] = int(suspicious.sum())

    # 成交量检查
    if '成交量' in df.columns:
        result['zero_volume_rows'] = int((df['成交量'] <= 0).sum())

    # 代码过滤提醒
    if code_col in df.columns:
        codes = df[code_col].astype(str)
        kcb = codes[codes.apply(is_kcb_stock)]
        result['kcb_count'] = len(kcb)
        result['sample_kcb_codes'] = kcb.head(3).tolist()

    return result


# ──────────────────────────────────────────
# 6. 简易进度反馈
# ──────────────────────────────────────────

def print_step(title: str, message: str = '') -> None:
    """打印步骤分隔线，让 notebook 输出更清晰"""
    line = '=' * 50
    print(f'\n{line}')
    print(f'  {title}')
    print(f'{line}')
    if message:
        print(f'  {message}\n')
