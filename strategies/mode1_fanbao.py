# ============================================================
# 模式1：反包策略
#
# 买入条件:
#   1. 昨天下跌（收盘 < 前天收盘）
#   2. 今天阳线反包（收盘 > 昨天最高）
#   3. 成交额 >= 10亿（大票）
#   4. 主动买入大单 / 被动买入大单 > 1
#   5. 今天未涨停，涨幅 >= 3%
#
# 操作: 次日看分时找买点买入，后天9:40卖出
#
# 大单区分说明（东方财富分笔数据）：
#   direction=1（买盘）= 买方主动挂单吃卖一/卖二 → 主动买入大单
#   direction=2（卖盘）= 卖方主动砸买一，买方被动接盘 → 被动买入大单
# ============================================================


import requests
import pandas as pd

# 大单阈值：单笔成交额 >= 50万元算大单
LARGE_THRESHOLD = 500000


def get_large_order_amounts(code):
    """
    返回 (主动买入大单金额, 被动买入大单金额, 比值)

    从东方财富逐笔数据中提取大单（>=50万）：
      - 主动买入大单 = 买方主动吃卖单的成交额（direction=1）
      - 被动买入大单 = 卖方砸买单的成交额，买方被动接盘（direction=2）
    """
    if ".XSHE" in code:
        secid = "0." + code.replace(".XSHE", "")
    elif ".XSHG" in code:
        secid = "1." + code.replace(".XSHG", "")
    else:
        return None, None, None

    url = "https://push2.eastmoney.com/api/qt/stock/details/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4",
        "fields2": "f51,f52,f53,f54,f55",
        "pos": -1,
        "lmt": 5000,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2,
        "invt": 2,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        details = data["data"]["details"]

        active_buy = 0   # direction=1 主动买入
        passive_buy = 0  # direction=2 被动买入

        for d in details:
            parts = d.split(",")
            price = float(parts[1])
            volume = int(parts[2])
            amount = price * volume
            direction = int(parts[4])

            if amount < LARGE_THRESHOLD:
                continue

            if direction == 1:
                active_buy += amount
            elif direction == 2:
                passive_buy += amount

        ratio = (active_buy / passive_buy) if passive_buy > 0 else None
        return active_buy, passive_buy, ratio

    except Exception:
        return None, None, None


def screen(df, today):
    """筛选反包候选+大单买卖比过滤"""
    latest = df[df["index"] == today].copy()
    if latest.empty:
        return []

    cond = (
        (latest["close"] > latest["open"]) &
        (latest["close"] > latest["昨高"]) &
        (latest["昨收"] < latest["昨收"].shift(1)) &
        (latest["money"] >= 10_000_000_000) &
        (latest["是否涨停"] != 1) &
        (latest["涨跌幅"] >= 0.03)
    )
    result = latest[cond]
    if result.empty:
        return []

    # 查大单买卖比
    print("  正在查大单数据（>=50万）...")
    filtered = []
    for _, row in result.iterrows():
        code = row["证券代码"]
        active, passive, ratio = get_large_order_amounts(code)
        if ratio is not None:
            label = "✅主动>被动" if ratio > 1 else "❌主动<被动"
            print(f"    {code}  主动买入大单:{active/1e8:.2f}亿  被动买入大单:{passive/1e8:.2f}亿  比值:{ratio:.2f}  {label}")
            if ratio > 1:
                filtered.append(row)
        else:
            print(f"    {code}  数据异常，跳过")

    if filtered:
        result = pd.DataFrame(filtered)

    return result[["证券代码", "close", "money", "涨跌幅"]].to_dict("records")
