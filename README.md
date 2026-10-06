# A股短线事件与因子验证

本项目研究 A 股短线交易中的涨停、连板断板、反包、竞价强弱、成交额和开板行为。重点不是固定一套历史最优参数，而是建立一套可以反复复核的因子比较流程。

研究围绕三个问题展开：

- 连板后断板，哪些量价特征会改善次日开盘买入、再次日均价卖出的收益
- 二连板低竞价样本中，第三日竞价和第二天成交额是否存在稳定的分组差异
- 涨停日的开板行为与后续承接之间是什么关系，是否存在非线性

代码负责数据清洗、信号对齐、交易成本、组合约束和绩效统计；题材强度、市场情绪和个股相对强度保留人工判断，不把主观信息伪装成可自动计算的因子。

## 研究设计

整个研究按同一套流程推进：

1. 先定义事件样本，例如连板断板、单板反包或二连板低竞价
2. 固定一个基准方案，避免每改一个条件就同时改变样本和结论
3. 每次只改变一个因子，比较分组后的胜率、平均收益、盈亏比和样本量
4. 所有交易加入佣金、印花税、过户费和滑点，买入和卖出时点保持一致
5. 结果分为正向、中性、负向和样本不足，不把高胜率的小样本直接当成结论
6. 从市场行为解释结果，例如竞价强弱代表开盘承接，成交额代表流动性和关注度，开板次数反映封板稳定性

详细方法见 [研究设计](./文档/研究设计.md)。

## 核心实现

[高开均线策略回测](./回测/trend_gap_backtest.py) 保留完整核心链路：

```text
读取数据 -> 计算信号 -> 对齐买卖日期 -> 计算交易成本 -> 每日组合 -> 绩效统计
```

默认条件为竞价高开、实体涨幅在 `-5%` 到 `5%`、收盘价站上 `M14`；T+1 开盘买入，T+2 均价卖出，每日按成交额取前 5 名。

```bash
python 回测/trend_gap_backtest.py
```

## 系统架构

```text
数据获取
  -> 数据清洗与字段标准化
  -> 信号初筛
  -> 人工题材与情绪复筛
  -> 模拟/实盘交易记录
  -> 收益率与绩效统计
  -> 分组验证与报告
```

## 策略模块

### 连板接力

基于连板层级、竞价表现、题材共振和盘口承接进行候选股筛选。代码完成基础条件过滤，最终候选股结合题材强度和同题材个股相对强弱人工确认。

详见 [连板接力策略.md](./策略/连板接力策略.md)。

### 反包模式

基于前序涨停、断板调整、成交额和趋势位置构建候选池，再由人工结合题材、情绪和板块强度决定是否参与。

### 半量化说明

- 代码负责客观条件和数据统计
- 人工负责题材抱团、市场情绪和相对强度
- 两种模式分别统计，不混算总收益
- 延迟卖出、无法买入和条件不符样本单独记录

## 因子研究

围绕连板断板、单板反包、竞价区间、成交额和分钟级开板行为，补充了一组实验记录。日线用于信号和交易规则，5 分钟数据用于判断涨停日是否存在开板行为。

当前结论：

- 第三日竞价 `0% 到 2%` 和 `低于 -2%` 相对基准为正，`-2% 到 0%` 明确偏弱
- 第二天成交额 `5 亿到 10 亿` 相对基准为正，`20 亿到 40 亿` 反而偏弱
- 单板反包中，开板 `2 次` 表现较好，但样本只有 87 笔；开板 `0 次` 偏弱
- 涨停后断板需要结合成交额和指数环境，单独使用不够稳定
- 开板次数来自 5 分钟近似判断，不是 Tick/L1/L2 精确统计

详细记录：

- [因子研究记录](./文档/因子研究记录.md)
- [因子实验对照表](./文档/因子实验对照表.md)
- [因子实验汇总](./结果/factor_experiment_summary.csv)
- [第三日竞价分组数据](./结果/factor_auction_groups.csv)
- [成交额分组数据](./结果/factor_amount_groups.csv)
- [开板次数分组数据](./结果/factor_open_count_groups.csv)
- [已复核交易清单](./结果/public_strategy_trades.xlsx)
- [已复核交易明细 CSV](./结果/public_strategy_trades.csv)
- [因子实验汇总脚本](./脚本/build_factor_experiment_report.py)

复现入口：

- 竞价分组：[compare_two_board_open_flags.py](./脚本/compare_two_board_open_flags.py)、[summarize_two_board_third_day_auction.py](./脚本/summarize_two_board_third_day_auction.py)
- 成交额分组：[summarize_all_two_board_second_day.py](./脚本/summarize_all_two_board_second_day.py)
- 开板次数：[fetch_limit_open_counts.py](./脚本/fetch_limit_open_counts.py)、[compare_single_board_open_counts.py](./脚本/compare_single_board_open_counts.py)
- 汇总和方向评级：[build_factor_experiment_report.py](./脚本/build_factor_experiment_report.py)

交易清单保留代码、买卖日期、买卖价、净收益率和收益金额，便于逐笔复核；不把净值曲线作为唯一结论。

## 验证框架

当前验证流程包含：

- 逐笔交易记录
- 交易状态自动识别
- 连板与反包分组统计
- 样本量分级
- 数据字段校验
- 核心函数单元测试

相关文件：

- [逐笔记录](./结果/strategy_validation.csv)
- [标准化状态](./结果/strategy_validation_status.csv)
- [分组汇总](./结果/strategy_validation_summary.csv)
- [策略汇总](./结果/strategy_validation_strategy_summary.csv)
- [统计脚本](./脚本/strategy_validation.py)
- [字段规范](./配置/strategy_validation_schema.json)
- [验证工作流](./文档/策略验证流程.md)
- [短线因子说明](./文档/短线因子说明.md)

## 技术栈

Python | Pandas | NumPy | Matplotlib | SQLite | OpenPyXL | Unittest

## 快速开始

```bash
git clone https://github.com/quantjuzi/fanbao_strategy.git
cd fanbao_strategy
pip install -r requirements.txt

python 脚本/strategy_validation.py
python -m unittest discover -s 测试 -p "test_*.py" -v
```

## 项目结构

```text
配置/            因子配置和字段规范
回测/            核心回测、交易成本和绩效统计
脚本/            因子研究和结果复现脚本
测试/            核心函数测试
文档/            研究设计、因子说明和验证流程
结果/            因子分组、交易清单和验证结果
策略/            策略说明和市场逻辑
数据/            原始数据和本地缓存
每日复盘/        日常观察和复盘记录
```

## 数据限制

历史 Tick、L1/L2、封单金额和内外盘成交额受个人数据权限限制。当前项目对这些字段采用人工验证、近似统计或待接入方案，不将估算数据当作精确结果。

## 当前状态

- 已建立数据清洗、回测、交易记录和绩效统计框架
- 已建立连板与反包分开统计的验证流程
- 已增加策略验证单元测试
- 已补充竞价、成交额、指数环境和分钟级开板行为的因子实验
- 半量化策略的参数和完整执行细节保留在本地私有目录

## 说明

本项目用于策略研究和数据处理流程复现，不构成投资建议。历史表现不代表未来结果。
