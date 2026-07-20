# 模式2：均线上方大票高开趋势策略
#
# 买入条件:
#   1. 今天高开（开盘 > 前收盘）
#   2. 收盘在MA20上方（close > MA20）
#   3. 趋势向上（MA5 > MA10 > MA20）
#   4. 成交额 >= 10亿（大票）
#   5. 今天未涨停
#
# 操作: 次日开盘看分时找买点，后天9:40卖出

def screen(df, today):
    """输入全市场DataFrame，返回符合趋势高开条件的股票列表"""
    latest = df[df["index"] == today].copy()
    if latest.empty:
        return []

    # 需要MA5、MA10、MA20列（由主程序提前算好）
    required = ["MA5", "MA10", "MA20"]
    for col in required:
        if col not in latest.columns:
            print(f"  缺少 {col} 列，跳过模式2")
            return []

    cond = (
        (latest["close"] > latest["MA20"]) &         # 收盘在MA20上方
        (latest["MA5"] > latest["MA10"]) &            # 短期均线向上
        (latest["MA10"] > latest["MA20"]) &           # 中期均线向上
        (latest["open"] > latest["pre_close"]) &      # 今天高开
        (latest["money"] >= 10_000_000_000) &         # 大票
        (latest["是否涨停"] != 1) &                    # 未涨停
        (latest["涨跌幅"] >= 0.02)                     # 至少涨2%
    )

    result = latest[cond]
    return result[["证券代码", "close", "money", "涨跌幅"]].to_dict("records")
