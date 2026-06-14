# ============================================================
# 鍙嶅寘绛栫暐鍥炴祴 - 浼樺寲鐗?# 鍏堢畻淇″彿鍐嶈窇鍥炴祴锛岄€熷害蹇?# ============================================================

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import os

# 鍔犺浇寮曟搸
sys.path.insert(0, r"C:\Users\Administrator\Documents\Codex\2026-06-13\start-failed-internal-error-com-intellij\fanbao_strategy\backtest")
from backtest_engine import backtest, plot_result

CSV = r"C:\Users\Administrator\Desktop\鍏ㄥ競鍦篈鑲2026-04-12_2026-06-12.csv"
df = pd.read_csv(CSV)
df["index"] = pd.to_datetime(df["index"])
df.sort_values(["璇佸埜浠ｇ爜", "index"], inplace=True)

# 棰勮绠?df["鏄ㄦ敹"] = df.groupby("璇佸埜浠ｇ爜")["close"].shift(1)
df["鏄ㄩ珮"] = df.groupby("璇佸埜浠ｇ爜")["high"].shift(1)
df["鏄ㄦ定璺?] = df.groupby("璇佸埜浠ｇ爜")["close"].pct_change().shift(1)  # 鏄ㄥぉ娑ㄨ穼骞?df["浠婃定璺?] = df.groupby("璇佸埜浠ｇ爜")["close"].pct_change()
df.dropna(inplace=True)

# 淇″彿鍒楋細涓€琛屼唬鐮佺畻鍑烘墍鏈夊弽鍖呬俊鍙?df["淇″彿"] = (
    (df["close"] > df["open"]) &          # 闃崇嚎
    (df["close"] > df["鏄ㄩ珮"]) &          # 鍙嶅寘
    (df["鏄ㄦ定璺?] < 0) &                   # 鏄ㄥぉ璺?    (df["money"] >= 10_000_000_000) &     # 澶хエ
    (df["浠婃定璺?] >= 0.03) &               # 娑ㄥ箙澶?    (df["鏄惁娑ㄥ仠"] != 1)                  # 鏈定鍋?).astype(int)

# 鍙暀淇″彿鏃?signal_days = df[df["淇″彿"] == 1].groupby("index").size()
print(f"鍙嶅寘淇″彿缁熻:")
print(f"鎬昏淇″彿鏁? {df['淇″彿'].sum()}")
print(f"鏈変俊鍙风殑澶╂暟: {len(signal_days)}")
print()

# 绛栫暐鍑芥暟锛氱洿鎺ヤ粠淇″彿鍒楀彇鍊?def fanbao_strategy(row, hist):
    return int(row["淇″彿"])  # 1=涔板叆, 0=涓嶄拱

print("寮€濮嬪洖娴?..")
result = backtest(fanbao_strategy, df, initial_cash=50000, max_positions=3)
print()
result.print_report()

# 鐢诲浘
img = os.path.join(os.path.dirname(CSV), "fanbao_backtest.png")
plot_result(result, save_path=img)
print(f"\n鍥捐〃宸蹭繚瀛?)

