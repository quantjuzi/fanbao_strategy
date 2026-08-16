# ============================================================
# 读代码练习 1：字典（dict）+ setdefault + 格式化输出
#
# 对应仓库文件：strategies/mode1_fanbao.py
# 那里面从东方财富逐笔数据里，按方向累加主动买入/被动买入，
# 用的就是"字典 + 累加"这套思路。
# ============================================================


def count_orders(details: list[str]) -> dict:
    """把每笔成交按方向归类，累加成交额。"""
    result = {}  # 先建一个空字典，准备存"方向 -> 金额"
    for line in details:
        parts = line.split(",")  # 每笔数据用逗号切开
        direction = int(parts[4])  # 第5个字段是买卖方向
        amount = float(parts[1]) * int(parts[2])  # 价格 x 股数 = 成交额

        # setdefault 的作用：如果没有这个 key，就先放进默认值 0
        result.setdefault(direction, 0)
        result[direction] += amount  # 同一方向的金额一直往上加

    return result


def main() -> None:
    # 模拟3笔逐笔数据：时间,价格,股数,笔数,方向(1买2卖)
    details = [
        "09:31:02,10.20,5000,1,1",
        "09:31:05,10.21,3000,1,2",
        "09:32:00,10.25,8000,1,1",
    ]
    result = count_orders(details)

    # 格式化输出：{key} 是占位符，后面 .format() 依次填值
    print("方向1(主动买入)金额: {:.0f}".format(result.get(1, 0)))
    print("方向2(被动买入)金额: {:.0f}".format(result.get(2, 0)))


if __name__ == "__main__":
    main()
