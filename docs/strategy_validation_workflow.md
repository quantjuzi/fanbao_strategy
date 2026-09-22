# 策略验证工作流

## 目标

把每日观察和模拟交易记录转换成可校验、可复现、可分组统计的数据流程。

## 每日流程

1. 在当天 `daily_notes/YYYY-MM-DD.md` 记录观察池和买入条件。
2. 将当日候选追加到 `results/strategy_validation.csv`。
3. 已完成交易填写买入价、卖出日期、卖出均价和收益率。
4. 尚未完成的交易只填写买入信息，收益率留空。
5. 运行统计脚本生成标准化数据和汇总。

```powershell
python scripts/strategy_validation.py
```

## 字段规则

- 字段定义：`config/strategy_validation_schema.json`
- 主键：日期 + 股票代码
- 买入口径：当日开盘价
- 卖出口径：第二个交易日均价
- `模拟买入=是` 且收益率有值：已完成
- `模拟买入=是` 且收益率无值：待卖出
- `模拟买入=否`：未买入

## 输出文件

- `results/strategy_validation_status.csv`
- `results/strategy_validation_summary.csv`
- `results/strategy_validation_strategy_summary.csv`

## 分组原则

- 连板接力：按策略、板数、条件组统计
- 反包：先按策略整体统计，不继续细分
- 两个策略分别统计，不把合计胜率作为主要结论

## 样本结论

- 少于 30 笔：样本不足
- 30-99 笔：初步验证
- 100 笔及以上：样本较充足

## 私有内容

核心参数、具体阈值和完整筛选公式放在本地 `private/` 目录，不提交到公开仓库。
