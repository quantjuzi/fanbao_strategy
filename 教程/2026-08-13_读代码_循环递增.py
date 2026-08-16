# ============================================================
# 读代码练习 3：for/while 循环 + 计数器
#
# 对应思路：统计"连续上涨天数"，和反包/炸板策略里
# 数连续涨停、数连续红K是一个套路。
# ============================================================


def max_consecutive_up(closes: list[float]) -> int:
    """返回连续上涨的最高天数。"""
    best = 0  # 到目前为止最长的一段
    cur = 0   # 当前正在数的一段

    for i in range(1, len(closes)):  # 从第2天开始和前一天比
        if closes[i] > closes[i - 1]:
            cur += 1  # 今天比昨天高，计数器+1
        else:
            cur = 0   # 断了，计数器清零重来

        if cur > best:
            best = cur  # 刷新历史最长纪录

    return best


def main() -> None:
    prices = [10.0, 10.3, 10.2, 10.5, 10.7, 10.6]
    days = max_consecutive_up(prices)
    print("连续上涨最高天数：{}".format(days))


if __name__ == "__main__":
    main()
