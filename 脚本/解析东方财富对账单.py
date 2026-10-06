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
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
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


def write_excel(path: Path, data: pd.DataFrame) -> None:
    """输出成交明细、汇总和月度统计。"""

    summary = pd.DataFrame(
        [
            {"指标": "成交记录", "值": len(data)},
            {"指标": "买入笔数", "值": data["方向"].eq("买入").sum()},
            {"指标": "卖出笔数", "值": data["方向"].eq("卖出").sum()},
            {
                "指标": "买入金额",
                "值": data.loc[
                    data["方向"].eq("买入"), "成交金额"
                ].sum(),
            },
            {
                "指标": "卖出金额",
                "值": data.loc[
                    data["方向"].eq("卖出"), "成交金额"
                ].sum(),
            },
            {"指标": "手续费合计", "值": data["手续费"].sum()},
            {"指标": "印花税合计", "值": data["印花税"].sum()},
            {"指标": "过户费合计", "值": data["过户费"].sum()},
            {
                "指标": "资金发生额合计",
                "值": data["资金发生额"].sum(),
            },
        ]
    )
    monthly = data.copy()
    monthly["月份"] = monthly["交易日期"].dt.to_period("M").astype(str)
    monthly = (
        monthly.groupby("月份")
        .agg(
            买入笔数=("方向", lambda values: values.eq("买入").sum()),
            卖出笔数=("方向", lambda values: values.eq("卖出").sum()),
            买入金额=(
                "成交金额",
                lambda values: 0.0,
            ),
            卖出金额=(
                "成交金额",
                lambda values: 0.0,
            ),
            手续费=("手续费", "sum"),
            印花税=("印花税", "sum"),
            过户费=("过户费", "sum"),
        )
        .reset_index()
    )
    for index, row in monthly.iterrows():
        month = row["月份"]
        sample = data.loc[
            data["交易日期"].dt.to_period("M").astype(str).eq(month)
        ]
        monthly.loc[index, "买入金额"] = sample.loc[
            sample["方向"].eq("买入"), "成交金额"
        ].sum()
        monthly.loc[index, "卖出金额"] = sample.loc[
            sample["方向"].eq("卖出"), "成交金额"
        ].sum()

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        data.to_excel(writer, sheet_name="成交明细", index=False)
        summary.to_excel(writer, sheet_name="汇总", index=False)
        monthly.to_excel(writer, sheet_name="月度统计", index=False)

    workbook = load_workbook(path)
    detail = workbook["成交明细"]
    detail.freeze_panes = "A2"
    detail.auto_filter.ref = detail.dimensions
    for cell in detail[1]:
        cell.fill = PatternFill("solid", fgColor="24445C")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")

    headers = {cell.value: cell.column for cell in detail[1]}
    for row in detail.iter_rows(min_row=2):
        row[headers["交易日期"] - 1].number_format = "yyyy-mm-dd"
        row[headers["成交数量"] - 1].number_format = "#,##0"
        row[headers["成交价格"] - 1].number_format = "0.0000"
        for name in ["资金发生额", "成交金额", "手续费", "印花税", "过户费"]:
            row[headers[name] - 1].number_format = "#,##0.00"
        direction = row[headers["方向"] - 1].value
        color = "C00000" if direction == "买入" else "2E7D32"
        row[headers["方向"] - 1].font = Font(
            color=color,
            bold=True,
        )

    widths = {
        "交易日期": 12,
        "方向": 8,
        "证券代码": 12,
        "证券名称": 14,
        "成交数量": 12,
        "成交价格": 12,
        "资金发生额": 14,
        "成交金额": 14,
        "手续费": 10,
        "印花税": 10,
        "过户费": 10,
        "原始业务类型": 14,
    }
    for name, width in widths.items():
        detail.column_dimensions[
            chr(64 + headers[name])
        ].width = width

    for sheet in ["汇总", "月度统计"]:
        current = workbook[sheet]
        current.freeze_panes = "A2"
        current.auto_filter.ref = current.dimensions
        for cell in current[1]:
            cell.fill = PatternFill("solid", fgColor="24445C")
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center")
        for column_cells in current.columns:
            width = max(
                len(str(cell.value)) if cell.value is not None else 0
                for cell in column_cells
            )
            current.column_dimensions[
                column_cells[0].column_letter
            ].width = min(max(width + 2, 10), 18)

    workbook.save(path)


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
    excel_path = args.output.with_suffix(".xlsx")
    write_excel(excel_path, result)

    print(
        f"解析完成：{len(result)} 条成交记录，"
        f"买入 {(result['方向'] == '买入').sum()} 条，"
        f"卖出 {(result['方向'] == '卖出').sum()} 条"
    )
    print(f"日期范围：{result['交易日期'].min()} 至 "
          f"{result['交易日期'].max()}")
    print(f"输出文件：{args.output}")
    print(f"Excel文件：{excel_path}")


if __name__ == "__main__":
    main()
