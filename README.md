# fanbao_strategy

A股反包策略每日选股 + 实盘记录

## 策略逻辑

- 大票反包：昨日下跌 + 今日阳线反包昨日最高价
- 成交额 >= 10亿（确保流动性）
- 隔日交易：买入后次日9:40附近卖出

## 文件说明

- daily_screen.py — 每日收盘后选股脚本
- trade_log.csv — 实盘交易记录

## 用法

每天收盘后运行：
python daily_screen.py

输出明日关注清单。
