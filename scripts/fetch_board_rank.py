#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fetch THS industry/concept board pct change for one trading day.

Usage:
    python scripts/fetch_board_rank.py --date 2026-03-13

Output:
    results/板块排行_2026-03-13.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time

import py_mini_racer
import requests

from akshare.datasets import get_ths_js
from akshare.stock_feature.stock_board_concept_ths import (
    _get_stock_board_concept_name_ths,
)
from akshare.stock_feature.stock_board_industry_ths import (
    _get_stock_board_industry_name_ths,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36"
)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


def get_v_code() -> str:
    """Generate the THS anti-crawler v cookie."""
    js_code = py_mini_racer.MiniRacer()
    with open(get_ths_js("ths.js"), encoding="utf-8") as f:
        js_code.eval(f.read())
    return js_code.call("v")


def fetch_year_rows(code: str, year: int, v_code: str) -> list[list[str]]:
    """Fetch one board's full-year daily lines from THS."""
    url = f"https://d.10jqka.com.cn/v4/line/bk_{code}/01/{year}.js"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "http://q.10jqka.com.cn",
        "Host": "d.10jqka.com.cn",
        "Cookie": f"v={v_code}",
    }
    for attempt in range(3):
        try:
            r = SESSION.get(url, headers=headers, timeout=12)
            if r.status_code != 200:
                time.sleep(0.3 * (attempt + 1))
                continue
            start = r.text.find("{")
            end = r.text.rfind("}")
            if start == -1 or end <= start:
                time.sleep(0.3 * (attempt + 1))
                continue
            obj = json.loads(r.text[start : end + 1])
            rows = []
            for line in (obj.get("data") or "").split(";"):
                parts = line.split(",")
                if len(parts) >= 5 and parts[0].isdigit():
                    rows.append(parts)
            if rows:
                return rows
        except Exception:
            pass
        time.sleep(0.3 * (attempt + 1))
    return []


def pct_on_date(rows: list[list[str]], target: str) -> float | None:
    """Compute pct change of one day using the previous trading day's close."""
    target = target.replace("-", "")
    for i, parts in enumerate(rows):
        if parts[0] == target and i > 0:
            prev_close = float(rows[i - 1][4])
            close = float(parts[4])
            if prev_close:
                return round((close / prev_close - 1) * 100, 2)
    return None


def save_results(
    rows: list[tuple[str, str, str, str, float]], target: str, out_path: str
) -> None:
    """Write ranking rows to CSV, best first."""
    sorted_rows = sorted(rows, key=lambda row: row[4], reverse=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["日期", "代码", "名称", "类型", "涨跌幅"])
        writer.writerows(sorted_rows)


def collect_boards() -> list[tuple[str, str, str]]:
    """Return (code, name, board_type) for industry and concept boards."""
    items = []
    for name, code in _get_stock_board_industry_name_ths().items():
        items.append((code, name, "行业"))
    for name, code in _get_stock_board_concept_name_ths().items():
        items.append((code, name, "概念"))
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="拉取同花顺板块某日涨跌幅排行")
    parser.add_argument("--date", default="2026-03-13", help="交易日期，如 2026-03-13")
    parser.add_argument("--delay", type=float, default=0.08, help="每个请求间隔秒数")
    args = parser.parse_args()

    target = args.date
    year = int(target[:4])
    boards = collect_boards()
    v_code = get_v_code()
    print(f"boards={len(boards)} v_ok", flush=True)

    results: list[tuple[str, str, str, str, float]] = []
    done = 0

    def work(item: tuple[str, str, str]) -> tuple[str, str, str, float | None]:
        code, name, board_type = item
        rows = fetch_year_rows(code, year, v_code)
        time.sleep(args.delay)
        return code, name, board_type, pct_on_date(rows, target)

    for item in boards:
        code, name, board_type, pct = work(item)
        done += 1
        if pct is not None:
            results.append((target, code, name, board_type, pct))
        if done % 50 == 0:
            print(f"progress {done}/{len(boards)} ok={len(results)}", flush=True)

    os.makedirs("results", exist_ok=True)
    out_path = os.path.join("results", f"板块排行_{target}.csv")
    if done % 100 == 0:
        save_results(results, target, out_path)

    save_results(results, target, out_path)
    print(f"saved {out_path} rows={len(results)}", flush=True)
    for row in sorted(results, key=lambda r: r[4], reverse=True)[:20]:
        print(f"{row[3]} {row[2]} {row[4]:+.2f}%", flush=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
