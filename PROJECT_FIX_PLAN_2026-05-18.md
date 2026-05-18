# QuantStock-AI 修改问题清单与执行方案

生成时间：2026-05-18  
项目路径：`C:\Users\zephyr\.qwenpaw\workspaces\my_agent_zg\QuantStock-AI`

## 当前结论

当前项目核心链路可运行，`compileall` 和 `scripts/smoke_test.py` 均已通过，说明不是语法级不可用状态。

但项目已经进入功能快速膨胀阶段，存在三类主要问题：

- 运行态文件污染 Git 工作区。
- 回测、模拟交易、AI 推理等功能缺少工程边界。
- 数据源、HTML 渲染、安全控制、测试覆盖还不够稳。

本文件用于指导后续修复，不建议一次性重构全项目，应按优先级逐步处理。

## 验证记录

已执行：

```bash
uv run python -m compileall -q app.py api data utils scripts train_afml_v20.py infer_afml_v20.py backtest_v20_system.py
uv run python scripts\smoke_test.py
```

结果：

- Python 编译通过。
- Smoke Test 通过。
- `/`、`/api/ml_predict_all`、`/api/model_report`、`/api/news`、`/api/search`、`/api/trade_logs` 等核心接口均为 OK。

## P0：提交前必须处理

### 1. 运行态文件不应进入提交

涉及文件：

- `server_log.txt`
- `data/sim_account.json`
- `data/screener_status_ai.json`

问题：

这些文件是运行日志、模拟账户状态、AI 筛选任务状态。它们会随着运行不断变化，不应和功能代码一起提交，否则每次运行都会污染 Git diff。

当前现象：

- `server_log.txt` 增加了大量日志内容。
- `data/sim_account.json` 记录了实时持仓价格、止盈止损日期等运行状态。
- `data/screener_status_ai.json` 从完成状态变成了运行中状态。

建议修改：

1. 将运行态文件从本次提交中排除。
2. 保留必要的 sample 文件，例如：
   - `data/sim_account.sample.json`
   - `data/screener_status_ai.sample.json`
3. 应用启动时，如果运行态文件不存在，再从 sample 初始化。
4. 将实际运行态文件加入 `.gitignore`。

建议 `.gitignore` 增加：

```gitignore
server_log.txt
llm_error.log
data/sim_account.json
data/screener_status_ai.json
data/screener_status_tech.json
data/pipeline_status.json
model_output/trade_logs.json
```

验收标准：

- `git diff --name-only` 中不再出现运行态 JSON 和日志文件。
- 删除本地运行态 JSON 后，项目能自动从 sample 初始化。
- Smoke Test 仍然通过。

## P1：核心稳定性修复

### 2. `/api/run_backtest` 不应同步阻塞 Flask 请求

涉及文件：

- `api/routes_model.py`
- `templates/index.html`

问题：

当前 `/api/run_backtest` 使用 `subprocess.run(...)` 在 Flask 请求线程内同步等待回测结束。

风险：

- 回测时间变长时，前端请求会卡住。
- Flask worker 被占用，其他请求响应变慢。
- 多人或多次点击会并发启动多个回测进程。

建议修改：

改成任务式接口：

- `POST /api/backtest/start`：启动回测，返回 `task_id`。
- `GET /api/backtest/status?task_id=xxx`：查询进度和状态。
- `GET /api/backtest_report`：继续返回最终报告。

最小可行方案：

- 后端用一个全局任务状态 JSON 文件保存状态。
- 启动时使用 `subprocess.Popen`。
- 前端轮询任务状态，不再长时间等待单个请求。

验收标准：

- 点击“重新运行回测”后，接口立即返回。
- 前端显示“运行中”状态。
- 回测完成后自动刷新报告。
- 连续点击不会启动多个重复任务。

### 3. 模拟交易账户读写需要文件锁

涉及文件：

- `api/routes_sim_trade.py`
- `data/sim_account.json`

问题：

模拟账户当前使用 JSON 文件直接读写。如果多个接口同时触发，例如自动交易、手动交易、前端轮询刷新，可能出现覆盖写或 JSON 文件损坏。

建议修改：

短期方案：

- 在 `load_account()` / `save_account()` 外层增加文件锁。
- Windows 可使用 `filelock` 库。

长期方案：

- 将模拟账户、持仓、交易日志迁移到 SQLite。

建议数据表：

- `sim_account`
- `sim_holdings`
- `sim_trade_logs`
- `sim_orders`

验收标准：

- 连续快速点击交易按钮，不会写坏 JSON。
- 自动交易和手动交易同时执行时，账户金额、持仓、日志一致。
- 异常中断后文件仍可读取。

### 4. 实盘交易路径需要更硬的安全边界

涉及文件：

- `api/routes_model.py`
- `api/routes_sim_trade.py`
- `trade_vnpy_executor.py`

问题：

项目存在 `TRADE_MODE=live` 或 `mode=real` 相关路径，会触发真实交易脚本。当前安全边界不够明确。

建议修改：

1. 默认强制 `mock` / `sim`。
2. 实盘模式必须同时满足：
   - 环境变量 `TRADE_MODE=live`
   - 配置文件中 `live_trading_enabled=true`
   - 前端二次确认
   - 单笔最大金额限制
   - 单日最大成交金额限制
   - 股票代码白名单或黑名单
3. 所有真实交易指令先进入 dry-run 预览。

验收标准：

- 默认环境无法触发真实交易。
- 未配置白名单时，真实交易请求被拒绝。
- 实盘请求日志完整记录参数、时间、来源和结果。

## P1：安全与前端渲染

### 5. AI/新闻 HTML 输出需要清洗，避免 XSS

涉及文件：

- `api/llm_assistant.py`
- `api/model_adapters.py`
- `templates/index.html`

问题：

前端大量使用 `innerHTML` 渲染后端返回内容。AI 输出、新闻内容、错误消息、股票名称等如果包含恶意 HTML，可能被浏览器执行。

高风险位置：

- AI 账户诊断结果。
- 个股 AI 分析。
- 新闻 AI 推演结果。
- 搜索结果和新闻标题。

建议修改：

后端：

- Markdown 转 HTML 后使用白名单清洗。
- 可选库：`bleach`。
- 只允许安全标签，如 `p`、`strong`、`em`、`ul`、`ol`、`li`、`h1-h4`、`blockquote`、`code`、`pre`、`table`。
- 禁止 `script`、`style`、`iframe`、事件属性 `onclick`、`onerror` 等。

前端：

- 普通文本使用 `textContent`。
- 只有经过后端清洗的 HTML 才允许进入 `innerHTML`。

验收标准：

- LLM 返回 `<script>alert(1)</script>` 时，前端不会执行。
- 新闻标题包含 HTML 时，只按普通文本显示。
- AI Markdown 格式仍能正常渲染。

### 6. ECharts 推理图谱解析需要补测试

涉及文件：

- `api/model_adapters.py`

当前优点：

本轮改动增强了 LLM 输出兼容性，能解析：

- 标准 ```json 代码块。
- 无代码块裸 JSON。
- 尾随逗号。
- Python 风格单引号字典。
- 列表包裹的图谱结果。
- 空响应兜底。

问题：

没有测试覆盖，后续改 prompt 或换模型时容易静默坏掉。

建议新增测试：

文件建议：

- `tests/test_model_adapters.py`

测试场景：

1. 标准 JSON 代码块。
2. 无代码块裸 JSON。
3. JSON 带尾随逗号。
4. Python 单引号 dict。
5. 返回 list 包裹 dict。
6. 空字符串。
7. 非法 JSON。

验收标准：

```bash
uv run pytest tests/test_model_adapters.py
```

能够通过，并且 graph_data 的 `name` 字段稳定存在。

## P2：数据源稳定性

### 7. 行情数据源需要统一 DataProvider 层

涉及文件：

- `data/market_data.py`
- `api/routes_market.py`
- `api/routes_sim_trade.py`

问题：

当前数据源分散在多个文件中：

- 新浪实时行情。
- AKShare 历史行情。
- AKShare 财务数据。
- 本地 CSV 缓存。
- 新闻接口。

这会导致：

- 被拦截时难以统一降级。
- 缓存策略不一致。
- 接口返回缺少统一的 `source`、`cached`、`stale` 信息。

建议新增目录：

```text
data_providers/
  __init__.py
  base.py
  akshare_provider.py
  sina_provider.py
  cache.py
  fallback_provider.py
```

统一接口：

```python
get_realtime_quote(code)
get_daily_history(code, start_date=None, end_date=None)
get_stock_basic()
get_news(code=None)
get_financial_summary(code)
```

统一返回：

```json
{
  "status": "success",
  "source": "akshare",
  "cached": false,
  "stale": false,
  "updated_at": "2026-05-18 10:30:00",
  "data": {}
}
```

降级顺序建议：

```text
本地缓存
  -> AKShare
  -> 新浪
  -> efinance
  -> 旧缓存 stale
```

验收标准：

- AKShare 请求失败时，系统自动尝试新浪或旧缓存。
- 前端能显示数据是否为缓存。
- Smoke Test 不依赖某一个单点数据源。

### 8. 请求限速、重试和缓存 TTL 需要统一

问题：

东财、AKShare、新浪接口都可能限流或偶发失败。现在各处请求没有统一退避策略。

建议：

- 请求失败后指数退避：`1s -> 3s -> 8s`。
- 对日线数据设置较长缓存。
- 对实时行情设置短 TTL。
- 对新闻设置中等 TTL。

建议 TTL：

```text
实时行情：5-30 秒
日线数据：交易日收盘后更新，盘中 5-30 分钟
财务数据：1 天
股票基础信息：1 天
新闻数据：5-15 分钟
```

验收标准：

- 网络失败不会导致页面整体崩溃。
- 接口返回明确的错误信息或 stale 缓存。
- 日志里能看到数据源降级过程。

## P2：算法与评估质量

### 9. 模型评估不能只看接口可用，需要补 IC / Rank IC / 分层收益

涉及方向：

- v17 / v18 / v19 / v20 模型输出。
- `model_output/model_report_*.json`
- 训练和推理脚本。

问题：

当前页面能显示模型预测，但评估维度还偏工程可用性。量化模型更需要看信号质量。

建议新增指标：

- IC
- Rank IC
- ICIR
- Top/Bottom 分层收益
- 换手率
- 最大回撤
- 胜率
- 平均持有收益
- 交易成本后收益

验收标准：

- 每次训练或推理后生成统一报告。
- 前端模型报告 badge 不只显示唯一值，也显示 IC / Rank IC。
- v17/v18/v19/v20 可横向比较。

### 10. 标签和验证切分需要防未来函数

建议：

- 引入 Triple Barrier Labeling。
- 引入 Purged K-Fold + Embargo。
- 引入 Walk-forward 验证。

优先级：

1. 先做 Walk-forward。
2. 再做 Purged K-Fold。
3. 最后引入 Triple Barrier Labeling。

验收标准：

- 训练集、验证集、测试集时间边界明确。
- 特征构造不使用未来数据。
- 报告中输出样本区间和验证方式。

## P3：代码结构与可维护性

### 11. 后端路由文件职责过重

问题：

`api/routes_market.py` 和 `api/routes_sim_trade.py` 已经承担了太多职责：

- HTTP 路由。
- 数据抓取。
- 指标计算。
- AI 调用。
- 交易逻辑。
- 文件读写。

建议拆分：

```text
services/
  ai_service.py
  backtest_service.py
  sim_trade_service.py
  market_service.py
  screener_service.py
```

路由层只负责：

- 取参数。
- 调 service。
- 返回 JSON。

验收标准：

- 路由文件显著变薄。
- 核心逻辑可单元测试。
- 新增功能不再直接堆到 Flask route 里。

### 12. 中文编码显示需要统一

问题：

PowerShell 输出里大量中文显示为乱码。虽然 Python 编译通过，说明文件不一定损坏，但开发体验和日志排查会受影响。

建议：

- 所有 `.py` 文件保留 UTF-8。
- 启动脚本设置：

```powershell
$env:PYTHONIOENCODING="utf-8"
chcp 65001
uv run python app.py
```

- 日志文件统一 UTF-8。

验收标准：

- 控制台中文正常显示。
- `server_log.txt` 中文正常显示。
- 前端接口返回中文正常。

## 建议提交拆分

不要把所有改动打成一个大提交。建议拆成：

### Commit 1

```text
chore: ignore runtime state files and add sample data
```

内容：

- `.gitignore`
- sample JSON
- 初始化逻辑

### Commit 2

```text
test: add model adapter parsing coverage
```

内容：

- `tests/test_model_adapters.py`

### Commit 3

```text
fix: sanitize AI markdown rendering
```

内容：

- AI HTML 清洗
- 前端普通文本 escape

### Commit 4

```text
feat: run backtest as async task
```

内容：

- 回测任务化
- 前端轮询

### Commit 5

```text
feat: add fallback market data provider
```

内容：

- DataProvider 层
- 缓存与降级

## 当前不建议直接提交的内容

以下文件当前不建议直接提交：

- `server_log.txt`
- `data/sim_account.json`
- `data/screener_status_ai.json`

以下改动可以保留，但需要配套测试或安全处理后再提交：

- `api/model_adapters.py` 的图谱 JSON 解析增强。
- `api/llm_assistant.py` 的新闻推理 prompt 优化。
- `templates/index.html` 中避免 onclick 传长文本的改动。
- `data/market_data.py` 中补充 SMA5 / RSI / MACD DIF 的改动。

## 推荐给执行 agent 的下一步指令

可以直接把下面这段交给另一个 agent：

```text
请按照 PROJECT_FIX_PLAN_2026-05-18.md 执行第一阶段修复：
1. 不要提交 server_log.txt、data/sim_account.json、data/screener_status_ai.json 的运行态变化。
2. 增加 .gitignore 规则，并提供 sample JSON 初始化方案。
3. 为 api/model_adapters.py 增加 tests/test_model_adapters.py，覆盖标准 JSON、裸 JSON、尾随逗号、单引号 dict、list 包裹、空字符串、非法 JSON。
4. 保留现有 ECharts 图谱解析增强，但不要扩大无关重构。
5. 修复后运行 uv run python -m compileall 和 uv run python scripts/smoke_test.py，并报告结果。
```

## 最终验收命令

```bash
uv run python -m compileall -q app.py api data utils scripts train_afml_v20.py infer_afml_v20.py backtest_v20_system.py
uv run python scripts\smoke_test.py
uv run pytest
git status --short
```

期望结果：

- 编译通过。
- Smoke Test 通过。
- 测试通过。
- `git status` 只显示本轮真正要提交的源码、测试和配置文件。

