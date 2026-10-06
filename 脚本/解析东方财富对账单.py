# -*- coding: utf-8 -*-
"""从东方财富电子对账单PDF中提取股票买卖明细。

只保留“证券买入”和“证券卖出”两类记录，自动忽略银证转账、
银行转证券、证券转银行、利息归本等非交易流水。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "private"
    / "东方财富对账单_交易明细.csv"
)

TRADE_PATTERN = re.compile(
    r"^(?P<日期>\d{8})\s+"
    r"(?P<业务类型>证券买入|证券卖出)\s+"
    r"(?P<代码>\S+)\s+"
    r"(?P<名称>.+?)\s+"
    r"(?P<数量>\d+)\s+"
    r"(?P<价格>[\d.]+)\s+"
    r"(?P<发生金额>-?[\d.]+)\s+"
    r"(?P<手续费>[\d.]+)\s+"
    r"(?P<印花税>[\d.]+)\s+"
    r"(?P<过户费>[\d.]+)\s+"
    r"(?P<资金余额>-?[\d.]+)$"
)


def parse_args() -> argparse.Namespace:
    """读取命令行参数。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def parse_pdf(path: Path) -> pd.DataFrame:
    """提取PDF中的股票成交记录。"""

    reader = PdfReader(path)
    rows: list[dict[str, object]] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            match = TRADE_PATTERN.match(line.strip())
            if not match:
                continue
            item = match.groupdict()
            rows.append(
                {
                    "交易日期": pd.to_datetime(
                        item["日期"],
                        format="%Y%m%d",
                        errors="coerce",
                    ),
                    "方向": (
                        "买入"
                        if item["业务类型"] == "证券买入"
                        else "卖出"
                    ),
                    "证券代码": item["代码"].split(".")[0].zfill(6),
                    "证券名称": re.sub(r"\s+", "", item["名称"]),
                    "成交数量": int(item["数量"]),
                    "成交价格": float(item["价格"]),
                    "资金发生额": float(item["发生金额"]),
                    "成交金额": abs(float(item["发生金额"])),
                    "手续费": float(item["手续费"]),
                    "印花税": float(item["印花税"]),
                    "过户费": float(item["过户费"]),
                    "原始业务类型": item["业务类型"],
                }
            )

    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError("没有解析到股票买卖记录，请检查PDF格式。")
    result = result.drop_duplicates(
        subset=[
            "交易日期",
            "方向",
            "证券代码",
            "成交数量",
            "成交价格",
            "资金发生额",
        ],
        keep="first",
    )
    return result.sort_values(
        ["交易日期", "证券代码", "方向"]
    ).reset_index(drop=True)


def main() -> None:
    """解析PDF并保存脱敏成交明细。"""

    args = parse_args()
    result = parse_pdf(args.pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(
        args.output,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"解析完成：{len(result)} 条成交记录，"
        f"买入 {(result['方向'] == '买入').sum()} 条，"
        f"卖出 {(result['方向'] == '卖出').sum()} 条"
    )
    print(f"日期范围：{result['交易日期'].min()} 至 "
          f"{result['交易日期'].max()}")
    print(f"输出文件：{args.output}")


if __name__ == "__main__":
    main()
