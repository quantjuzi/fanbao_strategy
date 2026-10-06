# -*- coding: utf-8 -*-
"""把单项因子实验整理成统一口径的CSV和Markdown报告。

本脚本不重新计算行情信号，只负责读取各实验的分组结果，并补上：
基准方案、只改的因子、固定条件、相对基准变化和复现代码。

原始信号和交易成本计算由配置中source_scripts列出的脚本完成。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_DIR / "配置" / "factor_experiments.json"
DEFAULT_OUTPUT = PROJECT_DIR / "结果" / "factor_experiment_summary.csv"
DEFAULT_DOC = PROJECT_DIR / "文档" / "factor_experiment_table.md"

NUMERIC_COLUMNS = [
    "交易数",
    "净胜率",
    "平均净收益率",
    "平均盈利",
    "平均亏损",
    "盈亏比",
    "净利润因子",
    "总盈利_2万每笔",
    "所需周转资金",
    "复利年化收益率",
]

SUMMARY_COLUMNS = [
    "实验",
    "基准方案",
    "只改因子",
    "因子取值",
    "方向评级",
    "保持不变",
    "样本说明",
    "区间",
    "交易数",
    "净胜率",
    "平均净收益率",
    "平均盈利",
    "平均亏损",
    "盈亏比",
    "净利润因子",
    "累计收益金额",
    "周转资金",
    "复利年化",
    "相对基准净胜率变化",
    "相对基准平均收益变化",
    "结论",
    "数据限制",
    "复现代码",
    "是否样本外验证",
]


def load_config(path: Path) -> dict[str, Any]:
    """读取并检查实验配置。"""

    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    for key in ["period", "cost_rule", "position_rule", "experiments"]:
        if key not in config:
            raise ValueError(f"实验配置缺少字段：{key}")

    for experiment in config["experiments"]:
        for key in [
            "name",
            "group_file",
            "baseline",
            "changed_factor",
            "fixed_conditions",
            "sample_note",
            "data_note",
            "source_scripts",
            "ratings",
            "conclusions",
        ]:
            if key not in experiment:
                raise ValueError(
                    f"实验 {experiment.get('name', '未命名')} 缺少字段：{key}"
                )
    return config


def load_group_results(path: Path) -> pd.DataFrame:
    """读取分组结果，并把不同脚本的列名统一成“因子取值”。"""

    data = pd.read_csv(path, encoding="utf-8-sig")

    possible_names = ["分组", "第三日竞价区间", "第二天成交额_亿"]
    value_column = next(
        (name for name in possible_names if name in data.columns),
        None,
    )
    if value_column is None:
        raise ValueError(
            f"{path.name} 缺少分组列，现有字段：{data.columns.tolist()}"
        )
    data = data.rename(columns={value_column: "因子取值"})
    data["因子取值"] = data["因子取值"].astype(str).str.strip()

    for column in NUMERIC_COLUMNS:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    if "净利润因子" not in data.columns:
        data["净利润因子"] = data.apply(calculate_profit_factor, axis=1)
    return data


def calculate_profit_factor(row: pd.Series) -> float:
    """根据胜率、平均盈利和平均亏损推算净利润因子。"""

    trades = float(row.get("交易数", 0))
    win_rate = float(row.get("净胜率", 0)) / 100
    avg_win = float(row.get("平均盈利", 0))
    avg_loss = float(row.get("平均亏损", 0))

    winners = trades * win_rate
    losers = trades - winners
    total_win = winners * avg_win
    total_loss = losers * abs(avg_loss)
    if total_loss <= 0:
        return 0.0
    return total_win / total_loss


def calculate_total_profit(row: pd.Series) -> float:
    """优先使用原脚本的总盈利，否则按两万元本金推算。"""

    if "总盈利_2万每笔" in row.index and pd.notna(row["总盈利_2万每笔"]):
        return float(row["总盈利_2万每笔"])
    return float(row.get("交易数", 0)) * float(
        row.get("平均净收益率", 0)
    ) * 20_000 / 100


def summarize_baseline(data: pd.DataFrame) -> dict[str, float]:
    """按交易数加权，合并所有分组为实验基准。"""

    total_trades = float(data["交易数"].sum())
    if total_trades <= 0:
        raise ValueError("实验分组没有有效交易数。")

    winners = data["交易数"] * data["净胜率"] / 100
    losers = data["交易数"] - winners
    total_winners = float(winners.sum())
    total_losers = float(losers.sum())
    total_win_profit = float((winners * data["平均盈利"]).sum())
    total_loss_profit = float((losers * data["平均亏损"]).sum())

    avg_win = (
        total_win_profit / total_winners
        if total_winners > 0
        else 0.0
    )
    avg_loss = (
        total_loss_profit / total_losers
        if total_losers > 0
        else 0.0
    )
    profit_factor = (
        total_win_profit / abs(total_loss_profit)
        if total_loss_profit < 0
        else 0.0
    )

    return {
        "交易数": total_trades,
        "净胜率": float(
            (data["交易数"] * data["净胜率"]).sum() / total_trades
        ),
        "平均净收益率": float(
            (
                data["交易数"] * data["平均净收益率"]
            ).sum()
            / total_trades
        ),
        "平均盈利": avg_win,
        "平均亏损": avg_loss,
        "盈亏比": (
            avg_win / abs(avg_loss)
            if avg_loss != 0
            else 0.0
        ),
        "净利润因子": profit_factor,
        "累计收益金额": float(data.apply(calculate_total_profit, axis=1).sum()),
    }


def build_summary_row(
    experiment: dict[str, Any],
    factor_value: str,
    metrics: dict[str, float],
    baseline: dict[str, float],
    period: str,
    is_baseline: bool = False,
) -> dict[str, Any]:
    """生成统一格式的一行实验记录。"""

    factor_names = {
        "第三日竞价区间": "第三日竞价涨幅",
        "第二天成交额区间": "第二天成交额",
        "涨停日开板次数": "涨停日开板次数",
    }
    factor_name = experiment.get(
        "changed_factor",
        factor_names.get(experiment["name"], experiment["name"]),
    )
    conclusion = (
        "本行作为该实验的基准，后续分组都只改变一个因子。"
        if is_baseline
        else experiment["conclusions"].get(factor_value, "")
    )

    return {
        "实验": experiment["name"],
        "基准方案": experiment["baseline"],
        "只改因子": "无，基准" if is_baseline else factor_name,
        "因子取值": "全部样本" if is_baseline else factor_value,
        "方向评级": (
            "基准"
            if is_baseline
            else experiment["ratings"].get(factor_value, "未评级")
        ),
        "保持不变": experiment["fixed_conditions"],
        "样本说明": experiment["sample_note"],
        "区间": period,
        "交易数": int(metrics["交易数"]),
        "净胜率": metrics["净胜率"],
        "平均净收益率": metrics["平均净收益率"],
        "平均盈利": metrics["平均盈利"],
        "平均亏损": metrics["平均亏损"],
        "盈亏比": metrics["盈亏比"],
        "净利润因子": metrics["净利润因子"],
        "累计收益金额": metrics["累计收益金额"],
        "周转资金": metrics.get("所需周转资金", ""),
        "复利年化": metrics.get("复利年化收益率", ""),
        "相对基准净胜率变化": metrics["净胜率"] - baseline["净胜率"],
        "相对基准平均收益变化": (
            metrics["平均净收益率"] - baseline["平均净收益率"]
        ),
        "结论": conclusion,
        "数据限制": experiment["data_note"],
        "复现代码": "；".join(experiment["source_scripts"]),
        "是否样本外验证": "否，当前为同一区间研究",
    }


def build_summary(config: dict[str, Any]) -> pd.DataFrame:
    """读取全部实验并生成统一汇总表。"""

    rows: list[dict[str, Any]] = []
    results_dir = PROJECT_DIR / "结果"

    for experiment in config["experiments"]:
        group_path = results_dir / experiment["group_file"]
        data = load_group_results(group_path)
        data["累计收益金额"] = data.apply(calculate_total_profit, axis=1)

        baseline = summarize_baseline(data)
        baseline_row = build_summary_row(
            experiment,
            "全部样本",
            baseline,
            baseline,
            config["period"],
            is_baseline=True,
        )
        if "所需周转资金" not in data.columns:
            baseline_row["周转资金"] = ""
        if "复利年化收益率" not in data.columns:
            baseline_row["复利年化"] = ""
        rows.append(baseline_row)

        for _, source_row in data.iterrows():
            metrics = {
                "交易数": float(source_row["交易数"]),
                "净胜率": float(source_row["净胜率"]),
                "平均净收益率": float(source_row["平均净收益率"]),
                "平均盈利": float(source_row["平均盈利"]),
                "平均亏损": float(source_row["平均亏损"]),
                "盈亏比": float(source_row["盈亏比"]),
                "净利润因子": float(source_row["净利润因子"]),
                "累计收益金额": float(source_row["累计收益金额"]),
                "所需周转资金": (
                    source_row["所需周转资金"]
                    if "所需周转资金" in source_row.index
                    else ""
                ),
                "复利年化收益率": (
                    source_row["复利年化收益率"]
                    if "复利年化收益率" in source_row.index
                    else ""
                ),
            }
            rows.append(
                build_summary_row(
                    experiment,
                    str(source_row["因子取值"]),
                    metrics,
                    baseline,
                    config["period"],
                )
            )

    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def format_number(value: Any, digits: int = 2) -> str:
    """把数值转成适合Markdown阅读的文本。"""

    if value == "" or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"


def build_markdown(config: dict[str, Any], summary: pd.DataFrame) -> str:
    """把统一汇总表转换成可直接阅读的实验记录。"""

    lines = [
        "# 因子实验对照表",
        "",
        "本文件由 `脚本/build_factor_experiment_report.py` 自动生成。",
        "每个实验先列基准，再只改变一个因子，其他条件尽量保持不变。",
        "",
        "## 统一口径",
        "",
        f"- 研究区间：{config['period']}",
        f"- 交易成本：{config['cost_rule']}",
        f"- 仓位和买卖价：{config['position_rule']}",
        "- 当前结果全部来自同一研究区间，属于样本内研究，不应把最优分组直接当成未来收益预期。",
        "",
    ]

    for experiment in config["experiments"]:
        group = summary.loc[summary["实验"].eq(experiment["name"])]
        if group.empty:
            continue

        lines.extend(
            [
                f"## {experiment['name']}",
                "",
                f"- 基准方案：{experiment['baseline']}",
                f"- 只改因子：{experiment['changed_factor']}",
                f"- 固定条件：{experiment['fixed_conditions']}",
                f"- 样本说明：{experiment['sample_note']}",
                f"- 数据限制：{experiment['data_note']}",
                f"- 复现代码：{'、'.join(experiment['source_scripts'])}",
                "",
                "| 因子取值 | 方向评级 | 交易数 | 净胜率 | 平均净收益率 | 盈亏比 | 累计收益金额 | 复利年化 | 相对基准胜率 | 相对基准平均收益 | 结论 |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )

        for _, row in group.iterrows():
            lines.append(
                "| {factor} | {rating} | {trades} | {win_rate}% | {avg_return}% | "
                "{ratio} | {profit}元 | {annual}% | {win_delta} | "
                "{return_delta} | {conclusion} |".format(
                    factor=row["因子取值"],
                    rating=row["方向评级"],
                    trades=int(row["交易数"]),
                    win_rate=format_number(row["净胜率"]),
                    avg_return=format_number(row["平均净收益率"], 4),
                    ratio=format_number(row["盈亏比"], 4),
                    profit=format_number(row["累计收益金额"]),
                    annual=format_number(row["复利年化"], 2),
                    win_delta=(
                        f"{row['相对基准净胜率变化']:+.2f}个百分点"
                    ),
                    return_delta=(
                        f"{row['相对基准平均收益变化']:+.4f}个百分点"
                    ),
                    conclusion=row["结论"],
                )
            )
        lines.append("")

    lines.extend(
        [
            "## 解释边界",
            "",
            "- 这里比较的是单因子分组，不是把多个条件同时优化到最好。",
            "- 样本量较小的分组不能只用高胜率下结论。",
            "- 开板次数、封成比和内外盘这类数据受历史数据权限限制；开板次数目前为5分钟线近似。",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    """读取命令行参数。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="实验配置文件",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="汇总CSV输出路径",
    )
    parser.add_argument(
        "--doc",
        type=Path,
        default=DEFAULT_DOC,
        help="Markdown输出路径",
    )
    return parser.parse_args()


def main() -> None:
    """生成因子实验汇总。"""

    args = parse_args()
    config = load_config(args.config)
    summary = build_summary(config)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.doc.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output, index=False, encoding="utf-8-sig")
    args.doc.write_text(
        build_markdown(config, summary),
        encoding="utf-8",
    )

    print(f"已生成因子实验汇总：{args.output}")
    print(f"已生成因子实验说明：{args.doc}")
    print(
        summary[
            [
                "实验",
                "因子取值",
                "方向评级",
                "交易数",
                "净胜率",
                "平均净收益率",
                "净利润因子",
                "累计收益金额",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
