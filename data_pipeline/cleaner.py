"""
数据清洗模块
处理A股日线数据中的边界情况：停牌、ST、退市、复权、涨跌停
"""

import pandas as pd
import numpy as np
from typing import Optional


def clean_st_stock(df: pd.DataFrame, st_column: Optional[str] = None) -> pd.DataFrame:
    """
    过滤ST/*ST股票
    """
    if st_column and st_column in df.columns:
        return df[~df[st_column].astype(str).str.contains('ST|\\*ST', na=False)]
    if 'name' in df.columns:
        return df[~df['name'].str.contains('ST|\\*ST', na=False)]
    return df


def clean_suspend(df: pd.DataFrame) -> pd.DataFrame:
    """
    过滤停牌期间的数据（当日无成交）
    """
    if 'volume' in df.columns:
        return df[df['volume'] > 0]
    if 'amount' in df.columns:
        return df[df['amount'] > 0]
    return df


def clean_limit_up_down(df: pd.DataFrame) -> pd.DataFrame:
    """
    标记涨停/跌停状态，用于回测时判断是否能买入/卖出
    """
    df = df.copy()
    if 'pct_chg' in df.columns:
        df['is_limit_up'] = df['pct_chg'] >= 9.8
        df['is_limit_down'] = df['pct_chg'] <= -9.8
    return df


def adjust_price_for_split(df: pd.DataFrame, factor_column: str = 'adj_factor') -> pd.DataFrame:
    """
    复权处理：使用复权因子调整价格
    """
    df = df.copy()
    if factor_column in df.columns and 'close' in df.columns:
        df['close_adj'] = df['close'] * df[factor_column]
    return df


def run_data_quality_check(df: pd.DataFrame) -> dict:
    """
    运行数据质量检查，返回报告字典
    """
    report = {
        'total_rows': len(df),
        'null_rows': df.isnull().any(axis=1).sum(),
        'duplicates': df.duplicated().sum(),
        'date_range': (df['date'].min(), df['date'].max()) if 'date' in df.columns else None,
    }
    return report


def clean_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """
    完整清洗流水线
    """
    df = clean_st_stock(df)
    df = clean_suspend(df)
    df = clean_limit_up_down(df)
    df = adjust_price_for_split(df)
    return df
