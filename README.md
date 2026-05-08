# 📊 QuantStock-AI

**中国A股量化预测系统** — v16c集成学习模型 · 42特征 · 实时技术分析面板

## 🎯 核心功能

| 功能 | 说明 |
|------|------|
| 🤖 ML预测 | v16c集成学习（3×LightGBM），42截面特征，20日收益预测 |
| 📈 实时行情 | 新浪财经数据源，5秒刷新，支持沪/深两市 |
| 📊 技术分析 | MACD / KDJ / RSI / CCI / DMI / 布林带 / VWAP |
| 📡 新闻监控 | 财联社 + 东方财富 + 同花顺，关键词情绪分析 |
| 🔍 股票搜索 | 东方财富 + 腾讯双源搜索，支持代码/名称 |
| ⏸️ 时间感知 | 收盘后自动切换为"已收盘"模式 |

## 🚀 快速开始

```bash
pip install -r requirements.txt
python app.py
# 打开 http://localhost:5000
```

## 🤖 v16c 模型

| 指标 | 值 |
|------|-----|
| 模型类型 | 3×LightGBM集成 |
| 特征数量 | 42个截面特征 |
| L-S收益 | +11.13% |
| Top组收益 | +12.79% |

## 📡 API端点

| 端点 | 说明 |
|------|------|
| `/api/realtime/<code>` | 实时行情 |
| `/api/minute/<code>` | 5分钟K线 |
| `/api/technical/<code>` | 技术指标 |
| `/api/predict/<code>` | 技术面评估 |
| `/api/ml_predict/<code>` | ML单股预测 |
| `/api/ml_predict_all` | ML批量预测 |
| `/api/news` | 实时新闻 |
| `/api/search?q=` | 股票搜索 |

## ⚠️ 免责声明

本系统仅供个人学习研究使用，不构成任何投资建议。股市有风险，投资需谨慎。
