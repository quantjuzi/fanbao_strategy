# -*- coding: utf-8 -*-
"""用 baostock 下载全市场 A 股日线数据。

聚宽试用账号只能取到 2026-04-30 之前的数据，7 月数据改用 baostock。
输出列包含 isST、tradestatus，方便回测脚本自己计算涨停价和炸板信号。

用法:
    python scripts/download_baostock_daily.py --start 2026-07-01 --end 2026-07-31
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import os
import sys
import time
from typing import List

import baostock as bs
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELDS = "date,code,open,high,low,close,preclose,volume,amount,turn,tradestatus,pctChg,isST"


def is_a_share(code: str) -> bool:
    """判断 baostock 代码是否属于沪深北 A 股。"""
    return (
        code.startswith("sh.6")
        or code.startswith("sz.0")
        or code.startswith("sz.3")
        or code.startswith("bj.4")
        or code.startswith("bj.8")
        or code.startswith("bj.9")
    )


def fetch_stock_list() -> List[str]:
    """返回全部 A 股代码列表（含 7 月新上市股票）。"""
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    rs = bs.query_stock_basic()
    codes: List[str] = []
    while rs.next():
        row = rs.get_row_data()
        code, _name, _ipo, _out, _type, _status = row
        if _type == "1" and is_a_share(code):
            codes.append(code)
    bs.logout()
    return sorted(codes)


def fetch_one(code: str, start: str, end: str) -> pd.DataFrame:
    """下载单只股票在区间内的日线，失败时返回空表。"""
    try:
        rs = bs.query_history_k_data_plus(
            code,
            FIELDS,
            start_date=start,
            end_date=end,
            frequency="d",
            adjustflag="3",  # 不复权
        )
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        return pd.DataFrame(rows, columns=FIELDS.split(","))
    except Exception:
        return pd.DataFrame()


def worker_init() -> None:
    """每个子进程独立登录 baostock，避免共享全局 socket。"""
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"worker baostock 登录失败: {lg.error_msg}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-07-31")
    args = parser.parse_args()

    codes = fetch_stock_list()
    print(f"A 股数量: {len(codes)}，区间: {args.start} ~ {args.end}")

    parts: List[pd.DataFrame] = []
    total = len(codes)
    done = 0
    t0 = time.time()
    with cf.ProcessPoolExecutor(max_workers=6, initializer=worker_init) as pool:
        futures = {pool.submit(fetch_one, c, args.start, args.end): c for c in codes}
        for fut in cf.as_completed(futures):
            part = fut.result()
            if not part.empty:
                parts.append(part)
            done += 1
            if done % 500 == 0 or done == total:
                el = time.time() - t0
                print(f"进度: {done}/{total}，用时 {el:.0f}s")

    out_path = os.path.join(ROOT, "data", f"全市场A股_{args.start}_{args.end}_baostock.csv")
    df = pd.concat(parts, ignore_index=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"完成: {len(df)} 行, {df['code'].nunique()} 支 -> {out_path}")


if __name__ == "__main__":
    main()
