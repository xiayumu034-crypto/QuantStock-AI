# QuantStock-AI 算法验证与升级操作文档

生成时间：2026-05-18  
项目路径：`C:\Users\zephyr\.qwenpaw\workspaces\my_agent_zg\QuantStock-AI`

## 目标

当前系统不是“差劲”，而是还没有经过足够严格的量化验证。

本文件的目标是把项目从：

```text
能跑的 AI 量化原型
```

升级为：

```text
能判断是否存在稳定 alpha 的研究系统
```

先不要急着追求实盘。现阶段最重要的是回答四个问题：

1. 模型预测是否真的有信息量？
2. 这种信息量是否稳定？
3. 扣除手续费、滑点、换手之后是否还有收益？
4. 不同市场阶段是否还能站得住？

## 总体路线

建议分 5 个阶段执行：

```text
阶段 1：建立严肃评估指标
阶段 2：防止未来函数和过拟合
阶段 3：引入 Qlib 标准工作流
阶段 4：升级标签和模型体系
阶段 5：策略、风控、组合化
```

不要一次性全改。每个阶段都要能独立验收。

## 阶段 1：建立严肃评估指标

### 1.1 新增信号质量评估脚本

新增文件：

```text
scripts/evaluate_signal_quality.py
```

目标：

对 v17 / v18 / v19 / v20 的预测结果做统一评估。

必须计算：

- IC
- Rank IC
- ICIR
- Top 分层收益
- Bottom 分层收益
- Top-Bottom 多空收益
- 分层胜率
- 分层样本数
- 换手率
- 交易成本前收益
- 交易成本后收益

建议输出：

```text
model_output/signal_quality_v19.json
model_output/signal_quality_v20.json
```

建议 JSON 格式：

```json
{
  "model": "v19_ensemble",
  "period": {
    "start": "2024-01-01",
    "end": "2026-05-18"
  },
  "metrics": {
    "ic_mean": 0.023,
    "rank_ic_mean": 0.031,
    "icir": 0.45,
    "top_quantile_return": 0.0042,
    "bottom_quantile_return": -0.0021,
    "long_short_return": 0.0063,
    "turnover": 0.38,
    "return_after_cost": 0.0038
  },
  "quantiles": [
    {
      "group": "Q1",
      "mean_return": -0.0021,
      "win_rate": 0.46,
      "count": 1200
    },
    {
      "group": "Q5",
      "mean_return": 0.0042,
      "win_rate": 0.56,
      "count": 1200
    }
  ]
}
```

验收标准：

```bash
uv run python scripts/evaluate_signal_quality.py --version v19
uv run python scripts/evaluate_signal_quality.py --version v20
```

能够生成对应 JSON 报告。

### 1.2 前端模型报告增加信号质量指标

涉及文件：

```text
api/routes_model.py
templates/index.html
```

新增接口：

```text
GET /api/signal_quality?version=v19
GET /api/signal_quality?version=v20
```

前端展示：

- IC
- Rank IC
- ICIR
- Top-Bottom 收益
- 换手率
- 成本后收益

验收标准：

- 前端切换模型时可以看到对应信号质量。
- 如果没有报告，显示“未生成”，不要报错。

## 阶段 2：防止未来函数和过拟合

### 2.1 统一训练、验证、测试时间切分

当前问题：

不同脚本里时间切分不统一，有些是最后 30 天，有些是 80/20，有些是指定日期。

建议新增统一配置：

```text
config/experiment_config.json
```

示例：

```json
{
  "train": ["2021-01-01", "2024-12-31"],
  "valid": ["2025-01-01", "2025-06-30"],
  "test": ["2025-07-01", "2026-05-18"],
  "embargo_days": 5,
  "holding_days": 1,
  "cost": {
    "open": 0.0005,
    "close": 0.0015,
    "min_cost": 5,
    "slippage": 0.001
  }
}
```

所有训练、推理、回测脚本都读取这个配置。

验收标准：

- v19、v20、回测脚本使用同一套时间区间。
- 报告里写明 train / valid / test 的具体日期。

### 2.2 加未来函数检查脚本

新增文件：

```text
scripts/check_lookahead_bias.py
```

检查内容：

1. 特征表达式中是否错误使用 `Ref($close, -1)`。
2. label 是否只出现在目标列，不进入 feature。
3. 横截面标准化是否只使用当天截面，不使用未来数据。
4. 推理脚本是否使用了训练时不可见的未来日期。
5. 回测是否用当日收盘信号买入当日收盘收益。

验收标准：

```bash
uv run python scripts/check_lookahead_bias.py
```

输出：

```text
[OK] no obvious lookahead bias detected
```

### 2.3 引入 Walk-forward 验证

新增文件：

```text
scripts/walk_forward_eval.py
```

方式：

```text
窗口 1：2021-2023 训练，2024Q1 测试
窗口 2：2021Q2-2024Q1 训练，2024Q2 测试
窗口 3：2021Q3-2024Q2 训练，2024Q3 测试
...
```

输出：

```text
model_output/walk_forward_v19.json
model_output/walk_forward_v20.json
```

报告内容：

- 每个窗口的 IC。
- 每个窗口的 Rank IC。
- 每个窗口的收益。
- 每个窗口的最大回撤。
- 每个窗口的换手率。

验收标准：

- 至少跑 6 个时间窗口。
- 不能只展示平均值，要展示每个窗口结果。
- 如果某些窗口失效，要明确显示。

## 阶段 3：引入 Qlib 标准工作流

### 3.1 跑通 `research/workflow_lgb_alpha158.yaml`

当前项目已经有：

```text
research/workflow_lgb_alpha158.yaml
```

但它还没有成为主流程。

新增脚本：

```text
scripts/run_qlib_workflow.py
```

目标：

通过 Qlib Workflow 跑通：

- `DatasetH`
- `Alpha158`
- `LGBModel`
- `SignalRecord`
- `SigAnaRecord`
- `PortAnaRecord`

验收命令：

```bash
uv run python scripts/run_qlib_workflow.py research/workflow_lgb_alpha158.yaml
```

验收标准：

- 能生成 Qlib recorder 实验结果。
- 有 signal analysis。
- 有 portfolio analysis。
- 有标准回测输出。

### 3.2 对比自研特征 vs Alpha158

新增实验：

```text
research/workflow_lgb_custom_v19.yaml
research/workflow_lgb_alpha158.yaml
```

比较：

- 自研 26 特征。
- Alpha158。
- 自研特征 + Alpha158 精简组合。

指标：

- IC
- Rank IC
- Long-short return
- Sharpe
- Max drawdown
- Turnover

验收标准：

生成对比报告：

```text
model_output/feature_set_comparison.json
```

必须能回答：

```text
自研特征是否真的强于 Alpha158？
Alpha158 是否能提升稳定性？
两者组合是否过拟合？
```

## 阶段 4：升级标签和模型体系

### 4.1 保留 v19，但补充报告

当前 v19 是 5 个 LightGBM 回归模型集成。

建议保留，因为它是一个不错的 primary model。

需要补充：

- 模型参数记录。
- 特征重要性。
- 每个子模型单独表现。
- ensemble 后表现。
- 样本区间。
- 训练耗时。

输出：

```text
model_output/model_report_v19_ensemble.json
```

验收标准：

- 不是只保存模型文件。
- 每次训练后都有完整报告。

### 4.2 v20 Meta-Labeling 加严格验证

当前 v20 已经有 Triple Barrier / Meta Labeling 思路，这是很好的方向。

但要补：

- meta label 正负样本比例。
- primary signal 原始胜率。
- meta filter 后胜率。
- 被过滤信号的后验表现。
- 不同阈值下表现，比如 0.5 / 0.55 / 0.6 / 0.65 / 0.7。

输出：

```text
model_output/meta_label_report_v20.json
```

验收标准：

必须证明：

```text
v20 不是单纯减少交易次数，而是真的提升了风险收益比。
```

### 4.3 增加 Triple Barrier 参数实验

新增文件：

```text
scripts/tune_triple_barrier.py
```

实验参数：

```text
pt_sl = [1, 1]
pt_sl = [1.5, 1]
pt_sl = [2, 1]
pt_sl = [2, 1.5]
holding_days = 3 / 5 / 10 / 20
target_vol_span = 20 / 50 / 100
```

输出：

```text
model_output/triple_barrier_grid.json
```

验收标准：

- 能看出不同参数下标签分布。
- 能看出不同参数下 meta model 表现。
- 不能只挑一个最好结果，要显示完整网格。

## 阶段 5：策略、风控、组合化

### 5.1 预测分数不能直接等于买卖

当前问题：

模型输出容易被前端直接解释为“强烈看涨/看涨/中性”。

建议改成：

```text
预测分数
  -> 横截面排名
  -> 流动性过滤
  -> 风险过滤
  -> 行业/主题约束
  -> 仓位权重
  -> 交易成本检查
  -> 下单/模拟交易
```

新增模块：

```text
services/portfolio_builder.py
```

输入：

```json
[
  {"code": "300201", "score": 0.82, "risk": 0.31}
]
```

输出：

```json
[
  {"code": "300201", "target_weight": 0.08, "reason": "top score + low risk"}
]
```

验收标准：

- 单票最大仓位可配置。
- 总仓位可配置。
- ST、退市、停牌、涨跌停不可交易过滤。
- 成交额过低过滤。

### 5.2 加真实交易成本和滑点

统一成本参数：

```json
{
  "commission": 0.00025,
  "tax": 0.0005,
  "transfer_fee": 0.00001,
  "slippage": 0.001,
  "min_cost": 5
}
```

所有回测必须同时输出：

- 成本前收益。
- 成本后收益。
- 总手续费。
- 换手率。

验收标准：

- 前端回测报告显示成本前后对比。
- 高频换仓策略如果被成本吃掉，必须明显显示。

### 5.3 增加风险控制指标

每个策略报告至少输出：

- 最大回撤。
- 年化波动。
- Sharpe。
- Sortino。
- Calmar。
- 最大连续亏损天数。
- 单票最大亏损。
- 行业集中度。
- 仓位利用率。

验收标准：

`model_output/backtest_report_v20.json` 中包含这些字段。

## 推荐执行顺序

### 第一周：先证明模型有没有信息量

做：

1. `evaluate_signal_quality.py`
2. `/api/signal_quality`
3. 前端显示 IC / Rank IC / 分层收益

不要做：

- 不要急着加深度学习。
- 不要急着实盘。
- 不要继续堆 AI 解释功能。

### 第二周：防过拟合和未来函数

做：

1. `experiment_config.json`
2. `check_lookahead_bias.py`
3. `walk_forward_eval.py`

目标：

确认模型不是靠偶然时间段赚钱。

### 第三周：Qlib 标准化

做：

1. `run_qlib_workflow.py`
2. 跑通 `Alpha158`
3. 自研特征 vs Alpha158 对比

目标：

把项目拉进标准 Qlib 研究范式。

### 第四周：v20 深化

做：

1. `meta_label_report_v20.json`
2. `tune_triple_barrier.py`
3. v20 阈值敏感性分析

目标：

证明 v20 是否真的提升风控，而不是只减少交易次数。

## 判断算法是否合格的标准

不要只看收益曲线。

最低合格线建议：

```text
Rank IC 均值 > 0.02
ICIR > 0.3
Top 分组收益 > 市场均值
Top-Bottom 多空收益为正
扣成本后仍为正
至少 6 个 walk-forward 窗口中 4 个为正
最大回撤可接受
换手率不过高
```

较好标准：

```text
Rank IC 均值 > 0.04
ICIR > 0.5
Top-Bottom 收益稳定为正
多数年份有效
成本后 Sharpe > 1
V20 能降低回撤并保持主要收益
```

危险信号：

```text
只在一个时间段有效
收益主要来自少数几天
换手极高
扣成本后收益消失
Top 分组和 Bottom 分组没有单调性
Rank IC 长期接近 0
回测收益很好但真实推理表现很差
```

## 可以直接交给另一个 agent 的指令

```text
请按照 ALGORITHM_VALIDATION_UPGRADE_PLAN.md 执行第一阶段：

1. 新增 scripts/evaluate_signal_quality.py。
2. 支持参数 --version v17/v18/v19/v20。
3. 使用 Qlib D.features 获取对应预测日期之后的真实收益。
4. 计算 IC、Rank IC、ICIR、五分位分层收益、Top-Bottom 收益、换手率、交易成本前后收益。
5. 输出 model_output/signal_quality_<version>.json。
6. 新增 GET /api/signal_quality?version=xxx。
7. 前端模型区域展示 IC、Rank IC、ICIR、Top-Bottom 收益、成本后收益。
8. 不要改动实盘交易逻辑，不要重构无关 UI。
9. 完成后运行：
   uv run python -m compileall -q app.py api data utils scripts train_afml_v20.py infer_afml_v20.py backtest_v20_system.py
   uv run python scripts/smoke_test.py
10. 报告生成的指标和测试结果。
```

## 最终验收命令

```bash
uv run python scripts/evaluate_signal_quality.py --version v19
uv run python scripts/evaluate_signal_quality.py --version v20
uv run python scripts/check_lookahead_bias.py
uv run python scripts/walk_forward_eval.py --version v19
uv run python -m compileall -q app.py api data utils scripts train_afml_v20.py infer_afml_v20.py backtest_v20_system.py
uv run python scripts/smoke_test.py
```

## 最重要的原则

从现在开始，所有算法升级都必须回答一句话：

```text
它是否让信号在样本外、扣成本后、多个时间窗口里更稳定？
```

如果不能回答，就先不要把它当成算法升级。

