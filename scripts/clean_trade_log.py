# -*- coding: utf-8 -*-
"""
trade_log.csv encoding fix + standardization
"""
import csv
import re
import os
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(REPO_DIR, "trade_log.csv")
MEMO_MAP = {
    "2026-06-17_002733": "T+1操作: 昨日追高被套, 竞价低开全仓止损",
    "2026-06-17_002203": "T+1操作: 海亮股份低开拉升至24.46小盈出局",
    "2026-06-18_002428": "T+1反包: 云南锗业竞价高开获利了结",
    "2026-06-18_003036": "T+1反包: 泰坦股份小幅盈利出局",
    "2026-06-18_301217": "T+1操作: 铜冠铜箔盘中走强高位止盈",
    "2026-06-22_600549": "T+2操作: 厦门钨业持有两天获利了结",
    "2026-06-22_600500": "T+2操作: 中化国际下挫止损",
    "2026-06-22_603078": "T+2操作: 江化微冲高回落止损",
    "2026-06-23_600105": "T+1操作: 永鼎股份小幅止损",
    "2026-06-23_601636": "T+1操作: 旗滨集团低开止损",
    "2026-06-24_002897": "T+1操作: 意华股份冲高回落止损",
    "2026-06-24_300319": "T+1操作: 麦捷科技小幅盈利出局",
    "2026-06-25_002491": "T+1操作: 通鼎互联早盘涨停高位出局",
    "2026-06-25_002297": "T+1操作: 博云新材盘中拉升大幅盈利",
    "2026-06-25_002407": "T+1操作: 多氟多低开高走大幅盈利",
    "2026-06-26_000070": "T+1操作: 特发信息利空跌停止损",
    "2026-06-26_300721": "T+1操作: 怡达股份小幅盈利出局",
    "2026-06-26_600397": "T+1操作: 安源煤业板块大涨盈利",
    "2026-06-30_002536": "T+1操作: 飞龙股份冲高回落止损",
    "2026-06-30_002491": "T+1操作: 通鼎互联大幅止损",
    "2026-06-30_002842": "T+1操作: 翔鹭钨业低开下挫止损",
    "2026-06-30_600888": "T+1操作: 新疆众和低开破位止损",
    "2026-07-01_603678": "T+1操作: 火炬电子拉升大幅盈利",
    "2026-07-01_000823": "T+1操作: 超声电子竞价高开大幅盈利",
    "2026-07-01_002579": "T+1操作: 中京电子拉升大幅盈利",
}
def main():
    rows = []
    with open(CSV_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for row in reader:
            key = f"{row['date']}_{row['code']}"
            if key in MEMO_MAP:
                row["strategy_memo"] = MEMO_MAP[key]
            memo = row.get("strategy_memo", "")
            row["strategy_memo"] = re.sub(r"[锟斤拷���]", "", memo)
            rows.append(row)
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"修复完成: 共处理 {len(rows)} 行数据")
if __name__ == "__main__":
    main()
