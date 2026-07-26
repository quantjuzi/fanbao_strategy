"""
A 股数据清洗模块

处理停牌、ST / *ST 过滤、复权验证、涨跌停标识、次新股过滤、
数据质量检查等边界情况。

用法::

    from data_pipeline import DataCleaner

    cleaner = DataCleaner()
    df_clean = cleaner.run(df)
    print(cleaner.report.summary())

每个清洗步骤也可独立调用:

    cleaner = DataCleaner()
    df = cleaner.detect_suspensions(df)
    df = cleaner.filter_st_stocks(df)
"""

from __future__ import annotations

import re
import sys
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import settings


# ---------------------------------------------------------------------------
# 常量 —— 沪深交易所股票代码模式
# ---------------------------------------------------------------------------

# ST / *ST 在聚宽数据中无名称字段，以下模式用于从代码推断
# 实际上 A 股 ST 标识靠名称而非代码前缀，所以这里留空做占位。
# 真正靠 behaviour (连续跌停) 检测。
ST_CODE_PATTERNS: List[str] = []

# 代码 → 交易所映射
EXCHANGE_MAP = {
    ".XSHE": "深交所",
    ".XSHG": "上交所",
    ".XBJ":  "北交所",
}


# ---------------------------------------------------------------------------
# 数据质量报告
# ---------------------------------------------------------------------------

@dataclass
class QualityReport:
    """数据质量检查报告"""

    total_rows: int = 0
    total_stocks: int = 0
    date_range: Tuple[str, str] = ("", "")
    duplicates: int = 0
    missing_vals: int = 0
    suspended_days: int = 0
    st_stocks_detected: int = 0
    abnormal_rows: int = 0
    null_cols: Dict[str, int] = field(default_factory=dict)
    details: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """返回格式化的摘要文本"""
        lines = [
            "=" * 54,
            "数据质量报告",
            "=" * 54,
            f"  日期范围:      {self.date_range[0]} ~ {self.date_range[1]}",
            f"  总行数:        {self.total_rows:,}",
            f"  股票数:        {self.total_stocks:,}",
            f"  重复行:        {self.duplicates:,}",
            f"  缺失值:        {self.missing_vals:,}",
            f"  停牌记录:      {self.suspended_days:,}",
            f"  ST 股检测:     {self.st_stocks_detected:,}",
            f"  异常行:        {self.abnormal_rows:,}",
            "-" * 54,
        ]
        if self.null_cols:
            lines.append("  各列缺失值:")
            for col, cnt in self.null_cols.items():
                if cnt > 0:
                    lines.append(f"    {col}: {cnt:,}")
        if self.details:
            lines.append("-" * 54)
            lines.extend(f"  {d}" for d in self.details[:10])
            if len(self.details) > 10:
                lines.append(f"  ... 还有 {len(self.details) - 10} 条")
        lines.append("=" * 54)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 数据清洗器
# ---------------------------------------------------------------------------

class DataCleaner:
    """A 股数据清洗器

    提供一套可组合的清洗流水线，每个步骤可独立调用。

    Parameters
    ----------
    config : dict, optional
        覆盖 ``config/settings.yaml`` 中 ``data_pipeline`` 段的配置。
    st_codes : set of str, optional
        手动指定的 ST / *ST 股代码集合（聚宽格式如 ``600519.XSHG``）。
    """

    # 预期必须包含的列
    REQUIRED_COLS: Set[str] = {
        "index", "open", "high", "low", "close", "volume", "money",
        "pre_close", "high_limit", "low_limit", "证券代码", "是否涨停",
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        st_codes: Optional[Set[str]] = None,
    ) -> None:
        self.cfg = config or settings.get("data_pipeline", {})
        self._st_codes = st_codes or set()
        self.report = QualityReport()

    # ------------------------------------------------------------------
    # 完整流水线
    # ------------------------------------------------------------------

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行完整清洗流程（6 个步骤依次执行）

        Parameters
        ----------
        df : pd.DataFrame
            原始数据，必须包含 :attr:`REQUIRED_COLS` 中的列。

        Returns
        -------
        pd.DataFrame
            清洗后的数据（新增 ``is_suspended``、``is_limit_down``、
            ``is_abnormal`` 等标记列）。
        """
        self._validate_columns(df)

        df = df.copy()
        n0 = len(df)
        self._collect_initial_stats(df)

        # 步骤 1: 去除重复
        df = self.drop_duplicates(df)

        # 步骤 2: 停牌检测
        df = self.detect_suspensions(df)

        # 步骤 3: 涨跌停标记
        df = self.detect_limit_up_down(df)

        # 步骤 4: ST 过滤
        df = self.filter_st_stocks(df)

        # 步骤 5: 复权验证
        df = self.verify_adjustment(df)

        # 步骤 6: 异常值检测
        df = self.detect_abnormal(df)

        # 最终报告
        n1 = len(df)
        self.report.details.insert(0, f"清洗前 {n0:,} 行 → 清洗后 {n1:,} 行（移除 {n0 - n1:,} 行）")
        return df

    # ------------------------------------------------------------------
    # 步骤 1: 重复行
    # ------------------------------------------------------------------

    def drop_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """移除完全重复的行"""
        before = len(df)
        df = df.drop_duplicates()
        dupes = before - len(df)
        self.report.duplicates = dupes
        if dupes:
            self.report.details.append(f"移除 {dupes} 行完全重复数据")
        return df

    # ------------------------------------------------------------------
    # 步骤 2: 停牌检测
    # ------------------------------------------------------------------

    def detect_suspensions(self, df: pd.DataFrame) -> pd.DataFrame:
        """检测停牌交易日并标记

        判断逻辑（满足任一即标记为停牌）:
        1. ``volume == 0``（显式停牌）
        2. ``open == close == pre_close`` 且成交量极低（疑似全天无交易）
        """
        cfg_sus = self.cfg.get("suspension", {})
        vol_threshold = cfg_sus.get("volume_threshold", 0)
        use_price = cfg_sus.get("detect_by_price", True)

        cond_susp = df["volume"] <= vol_threshold

        if use_price:
            cond_price = (
                (df["open"] == df["close"])
                & (df["close"] == df["pre_close"])
                & (df["volume"] < 1000)
            )
            cond_susp = cond_susp | cond_price

        df["is_suspended"] = cond_susp.astype(int)
        self.report.suspended_days = int(cond_susp.sum())

        if self.report.suspended_days:
            self.report.details.append(
                f"标记 {self.report.suspended_days} 条停牌记录"
            )
        return df

    # ------------------------------------------------------------------
    # 步骤 3: 涨跌停标识
    # ------------------------------------------------------------------

    def detect_limit_up_down(self, df: pd.DataFrame) -> pd.DataFrame:
        """补充跌停标记，并验证已有涨停标记

        新增列:
        - ``is_limit_up``: 1 表示涨停（close >= high_limit * threshold）
        - ``is_limit_down``: 1 表示跌停（close <= low_limit / threshold）
        """
        lc = self.cfg.get("limit_check", {})
        up_th  = lc.get("up_threshold", 0.99)
        dn_th  = lc.get("down_threshold", 1.01)

        df["is_limit_up"] = (
            (df["close"] >= df["high_limit"] * up_th) & (df["high_limit"] > 0)
        ).astype(int)

        df["is_limit_down"] = (
            (df["close"] <= df["low_limit"] * dn_th) & (df["low_limit"] > 0)
        ).astype(int)

        # 与已有标记对比
        mismatch = (df["是否涨停"] != df["is_limit_up"]).sum()
        if mismatch:
            self.report.details.append(
                f"涨停标记不一致 {mismatch} 行（已有列 vs 重算）"
            )

        limit_down_cnt = int(df["is_limit_down"].sum())
        if limit_down_cnt:
            self.report.details.append(
                f"跌停标记: {limit_down_cnt} 条"
            )
        return df

    # ------------------------------------------------------------------
    # 步骤 4: ST 股票过滤
    # ------------------------------------------------------------------

    def filter_st_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """移除 ST / *ST 股数据

        检测方法:
        1. ``manual_codes`` — 用户手动指定的 ST 代码
        2. 行为特征 — 连续 3+ 个跌停且成交额极低（常见 ST 特征）

        Returns
        -------
        pd.DataFrame
            移除 ST 股票后的数据（可通过 ``self.report.st_stocks_detected``
            查看移除数量）。
        """
        cfg_st = self.cfg.get("st_detection", {})
        if not cfg_st.get("enabled", True):
            return df

        st_set: Set[str] = set()

        # 1) 手动代码列表
        st_set.update(self._st_codes)
        st_set.update(cfg_st.get("manual_codes", []))

        # 2) 行为特征检测：连续 3+ 天跌停 + 低成交额
        if "code_pattern" in cfg_st.get("method", "code_pattern"):
            behavioral = self._detect_st_by_behavior(df)
            st_set.update(behavioral)

        if not st_set:
            return df

        before = len(df)
        df = df[~df["证券代码"].isin(st_set)].copy()
        removed = before - len(df)
        self.report.st_stocks_detected = len(st_set)

        if removed:
            codes_str = ", ".join(sorted(st_set)[:10])
            more = f" ... 共 {len(st_set)} 支" if len(st_set) > 10 else ""
            self.report.details.append(
                f"移除 {len(st_set)} 支 ST 股（{codes_str}{more}），合计 {removed} 行"
            )
        return df

    def _detect_st_by_behavior(self, df: pd.DataFrame) -> Set[str]:
        """通过连续跌停 + 低成交额推测 ST 股票"""
        threshold = self.cfg.get("limit_check", {}).get("down_threshold", 1.01)

        # 按股票 + 日期排序（在 df 上做排序，后续计算用 df_sorted）
        df_sorted = df.sort_values(["证券代码", "index"])

        # 在排序后的 DataFrame 上重新计算跌停标记
        limit_down_sorted = (
            (df_sorted["close"] <= df_sorted["low_limit"] * threshold)
            & (df_sorted["low_limit"] > 0)
        )

        if not limit_down_sorted.any():
            return set()

        # 计算每个股票连续跌停天数
        mask = limit_down_sorted.astype(int)
        groups = df_sorted.groupby("证券代码")["index"].transform(
            lambda x: x.diff().dt.days.ne(1).cumsum()
        )

        consecutive = (
            df_sorted[limit_down_sorted]
            .groupby(["证券代码", groups[limit_down_sorted]])
            .size()
        )

        # 连续 3+ 跌停且成交额偏低视为 ST
        st_codes: Set[str] = set()
        for (code, _), cnt in consecutive.items():
            if cnt >= 3:
                stock_data = df[df["证券代码"] == code]
                avg_money = stock_data["money"].mean()
                if avg_money < 5_000_000:  # 日均成交额 < 500 万
                    st_codes.add(code)

        return st_codes

    # ------------------------------------------------------------------
    # 步骤 5: 复权验证
    # ------------------------------------------------------------------

    def verify_adjustment(self, df: pd.DataFrame) -> pd.DataFrame:
        """验证前复权数据的连续性

        检查 ``pre_close`` 是否等于前一日 ``close``，输出不一致记录。
        数据使用 ``fq="pre"``（前复权）下载，理论应一致；不一致说明
        除权除息或数据拼接问题。
        """
        df_sorted = df.sort_values(["证券代码", "index"]).copy()
        expected_pre = df_sorted.groupby("证券代码")["close"].shift(1)
        df_sorted["adj_error"] = (
            (df_sorted["pre_close"] - expected_pre).abs() > 0.01
        ).astype(int)

        errors = int(df_sorted["adj_error"].sum())
        if errors:
            self.report.details.append(
                f"复权不一致: {errors} 行（可能为除权除息日）"
            )

        # 恢复原始顺序
        df_sorted.drop(columns="adj_error", inplace=True)
        return df_sorted

    # ------------------------------------------------------------------
    # 步骤 6: 异常值检测
    # ------------------------------------------------------------------

    def detect_abnormal(self, df: pd.DataFrame) -> pd.DataFrame:
        """标记可能存在数据异常的行

        检测条件（满足任一）:
        - 单日涨跌幅 > ``max_price_ratio``（默认 50%，含除权）
        - ``high < low``
        - ``open / close`` 超出当日高低范围
        - 成交额 <= 0
        """
        max_ratio = self.cfg.get("max_price_ratio", 0.5)

        cond_vol = df["volume"] < 0
        cond_money = df["money"] <= 0
        cond_hl = df["high"] < df["low"]
        cond_oc = (df["open"] > df["high"]) | (df["open"] < df["low"])
        cond_cc = (df["close"] > df["high"]) | (df["close"] < df["low"])

        # 涨跌幅异常（含除权日）
        pct = df["close"] / df["pre_close"] - 1
        cond_pct = pct.abs() > max_ratio

        df["is_abnormal"] = (
            cond_vol | cond_money | cond_hl | cond_oc | cond_cc | cond_pct
        ).astype(int)

        cnt = int(df["is_abnormal"].sum())
        self.report.abnormal_rows = cnt
        if cnt:
            self.report.details.append(
                f"异常数据行: {cnt} 条"
            )
        return df

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """检查必要列是否存在"""
        missing = self.REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(
                f"数据缺少必要列: {missing}. "
                f"现有列: {list(df.columns)}"
            )

    def _collect_initial_stats(self, df: pd.DataFrame) -> None:
        """收集清洗前的基本统计"""
        self.report.total_rows = len(df)
        self.report.total_stocks = int(df["证券代码"].nunique())
        dates = df["index"].sort_values()
        self.report.date_range = (
            str(dates.iloc[0]),
            str(dates.iloc[-1]),
        )
        # 缺失值统计
        null_counts = df.isnull().sum()
        self.report.missing_vals = int(null_counts.sum())
        self.report.null_cols = {
            col: int(cnt)
            for col, cnt in null_counts.items()
            if cnt > 0
        }


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def load_and_clean(
    csv_path: str,
    config: Optional[Dict[str, Any]] = None,
    st_codes: Optional[Set[str]] = None,
) -> Tuple[pd.DataFrame, QualityReport]:
    """一键加载 CSV 并清洗

    Parameters
    ----------
    csv_path : str
        CSV 文件路径。
    config : dict, optional
        清洗配置。
    st_codes : set of str, optional
        手动 ST 代码。

    Returns
    -------
    tuple of (DataFrame, QualityReport)
    """
    df = pd.read_csv(csv_path, parse_dates=["index"])
    cleaner = DataCleaner(config=config, st_codes=st_codes)
    df_clean = cleaner.run(df)
    return df_clean, cleaner.report


if __name__ == "__main__":
    # 命令行入口：python -m data_pipeline.cleaner
    import sys
    csv = sys.argv[1] if len(sys.argv) > 1 else settings["data"]["csv_path"]
    cleaned, report = load_and_clean(csv)
    print(report.summary())
    out = csv.replace(".csv", "_clean.csv")
    cleaned.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n清洗后数据已保存: {out}")

