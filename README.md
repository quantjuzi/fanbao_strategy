# A股短线策略量化研究框架

一个面向 A 股短线策略的数据处理、信号筛选、回测验证和绩效统计项目。项目定位为半量化流程：代码负责数据清洗、条件初筛、交易记录和统计，题材强度、市场情绪和个股相对强度由人工复核。

> 核心策略参数不公开，公开内容主要展示数据处理、回测框架、验证方法和代码工程质量。

## 项目目标

- 将主观短线交易规则拆解为可记录、可验证的条件
- 处理多股票日线、分钟线和交易记录数据
- 输出逐笔交易、胜率、平均收益、盈亏比和最大回撤
- 区分策略结果、模拟交易结果和真实资金收益
- 保留人工判断环节，明确数据和策略边界

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

详见 [连板接力策略.md](./strategies/连板接力策略.md)。

### 反包模式

基于前序涨停、断板调整、成交额和趋势位置构建候选池，再由人工结合题材、情绪和板块强度决定是否参与。

### 半量化说明

- 代码负责客观条件和数据统计
- 人工负责题材抱团、市场情绪和相对强度
- 两种模式分别统计，不混算总收益
- 延迟卖出、无法买入和条件不符样本单独记录

## 验证框架

当前验证流程包含：

- 逐笔交易记录
- 交易状态自动识别
- 连板与反包分组统计
- 样本量分级
- 数据字段校验
- 核心函数单元测试

相关文件：

- [逐笔记录](./results/strategy_validation.csv)
- [标准化状态](./results/strategy_validation_status.csv)
- [分组汇总](./results/strategy_validation_summary.csv)
- [策略汇总](./results/strategy_validation_strategy_summary.csv)
- [统计脚本](./scripts/strategy_validation.py)
- [字段规范](./config/strategy_validation_schema.json)
- [验证工作流](./docs/strategy_validation_workflow.md)
- [短线因子说明](./docs/short_term_factor_guide.md)

## 技术栈

Python | Pandas | NumPy | Matplotlib | SQLite | OpenPyXL | Unittest

## 快速开始

```bash
git clone https://github.com/quantjuzi/fanbao_strategy.git
cd fanbao_strategy
pip install -r requirements.txt

python scripts/strategy_validation.py
python -m unittest discover -s tests -p "test_*.py" -v
```

## 项目结构

```text
config/          配置和字段规范
data_pipeline/   数据清洗与标准化
strategies/      策略逻辑和说明
backtest/        回测与交易成本
scripts/         统计、导出和数据处理脚本
tests/           核心函数测试
docs/            工作流和因子说明
results/         回测和策略验证结果
daily_notes/     日常观察和复盘记录
reports/         绩效图表
private/         私有参数和未公开研究内容，不提交
```

## 数据限制

历史 Tick、L1/L2、封单金额和内外盘成交额受个人数据权限限制。当前项目对这些字段采用人工验证、近似统计或待接入方案，不将估算数据当作精确结果。

## 当前状态

- 已建立数据清洗、回测、交易记录和绩效统计框架
- 已建立连板与反包分开统计的验证流程
- 已增加策略验证单元测试
- 半量化策略的参数和完整执行细节保留在本地私有目录

## 说明

本项目用于策略研究和数据处理流程展示，不构成投资建议。历史表现不代表未来结果。
