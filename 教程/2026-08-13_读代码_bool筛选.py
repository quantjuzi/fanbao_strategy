# ============================================================
# 读代码练习 2：DataFrame 布尔筛选 + df[cond]
#
# 对应仓库文件：strategies/mode1_fanbao.py 的 screen()
# cond 就是一长串"是/否"条件，df[cond] 只留下 True 的行。
# ============================================================

import pandas as pd


def main() -> None:
    # 造一张模拟股票表
    df = pd.DataFrame({
        "股票": ["A", "B", "C"],
        "收盘": [10.0, 11.0, 9.5],
        "昨高": [9.8, 10.5, 9.9],
        "昨收": [9.6, 10.2, 9.7],
        "是否涨停": [0, 0, 1],
    })

    # 反包条件：今天收盘 > 昨天最高，而且今天没涨停
    cond = (df["收盘"] > df["昨高"]) & (df["是否涨停"] == 0)

    # cond 打印出来就是一列 True/False
    print("条件结果：")
    print(cond)

    # df[cond] 只留下条件为 True 的股票
    result = df[cond]
    print("\n筛选出来的股票：")
    print(result)


if __name__ == "__main__":
    main()
