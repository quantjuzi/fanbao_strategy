# -*- coding: utf-8 -*-
"""检查公开交易明细的字段、日期、价格和收益方向。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
RESULT_DIR = PROJECT_DIR / "结果"

FILES = {
    "策略一": RESULT_DIR / "策略一_连板断板_交易明细.csv",
    "策略二": RESULT_DIR / "策略二_单板反包_交易明细.csv",
    "单反包单连板": RESULT_DIR / "单反包单连板_交易明细.csv",
}


def check_file(name: str, path: Path) -> dict[str, object]:
    """检查一份交易明细并返回质量摘要。"""

    data = pd.read_csv(path, encoding="utf-8-sig")
    required = {
        "代码",
        "买入日期",
        "买入价格",
        "卖出日期",
        "卖出价格",
        "净收益率",
        "净盈亏金额",
    }
    missing_columns = sorted(required - set(data.columns))

    for column in ["买入日期", "卖出日期"]:
        if column in data.columns:
            data[column] = pd.to_datetime(
                data[column],
                errors="coerce",
            )

    key_columns = [
        column
        for column in [
            "代码",
            "买入日期",
            "买入价格",
            "卖出日期",
            "卖出价格",
            "净收益率",
            "净盈亏金额",
        ]
        if column in data.columns
    ]
    missing_rows = int(data[key_columns].isna().any(axis=1).sum())
    invalid_date = int(
        (
            data["买入日期"].isna()
            | data["卖出日期"].isna()
            | data["卖出日期"].le(data["买入日期"])
        ).sum()
    )
    invalid_price = int(
        (
            data["买入价格"].le(0)
            | data["卖出价格"].le(0)
        ).sum()
    )
    duplicate_rows = int(
        data.duplicated(
            subset=["代码", "买入日期", "卖出日期"],
            keep=False,
        ).sum()
    )
    return_sign_mismatch = int(
        (
            data["净收益率"].gt(0)
            != data["净盈亏金额"].gt(0)
        ).sum()
    )
    large_trade = int(data["净收益率"].abs().gt(30).sum())

    issues = sum(
        [
            len(missing_columns),
            missing_rows,
            invalid_date,
            invalid_price,
            duplicate_rows,
            return_sign_mismatch,
            large_trade,
        ]
    )
    return {
        "文件": name,
        "交易数": len(data),
        "股票数": int(data["代码"].nunique()),
        "开始日期": data["买入日期"].min(),
        "结束日期": data["卖出日期"].max(),
        "缺失列": "；".join(missing_columns),
        "关键字段缺失行": missing_rows,
        "日期顺序异常": invalid_date,
        "价格异常": invalid_price,
        "重复交易": duplicate_rows,
        "收益方向异常": return_sign_mismatch,
        "绝对收益超过30%": large_trade,
        "问题数": issues,
    }


def main() -> None:
    """生成交易明细质量检查表。"""

    rows = [
        check_file(name, path)
        for name, path in FILES.items()
    ]
    result = pd.DataFrame(rows)
    output = RESULT_DIR / "交易明细质量检查.csv"
    result.to_csv(output, index=False, encoding="utf-8-sig")
    print(result.to_string(index=False))
    print(f"\n检查结果已保存：{output}")


if __name__ == "__main__":
    main()
