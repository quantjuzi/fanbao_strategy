# -*- coding: utf-8 -*-
"""临时诊断: 核对 600188 在反包明细里的收益计算。"""

import glob
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    """输出 600188 明细与原始日线。"""
    fb_path = glob.glob(os.path.join(ROOT, "results", "*_2026-05-01_2026-07-31.csv"))[0]
    fb = pd.read_csv(fb_path, encoding="utf-8-sig")
    print("=== 反包明细 600188 ===")
    sub = fb[fb["代码"].astype(str).str.contains("600188")]
    print(sub.to_string(index=False) if len(sub) else "无记录")

    bs_path = glob.glob(
        os.path.join(ROOT, "data", "*_2026-04-01_2026-06-30_baostock.csv")
    )[0]
    bs = pd.read_csv(bs_path, encoding="utf-8-sig")
    bs["date"] = pd.to_datetime(bs["date"])
    x = bs[bs["code"] == "sh.600188"]
    x = x[(x["date"] >= "2026-05-28") & (x["date"] <= "2026-06-15")]
    print()
    print("=== baostock 原始日线 sh.600188 ===")
    print(x.to_string(index=False))


if __name__ == "__main__":
    main()
