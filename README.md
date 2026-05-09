# 📊 QuantStock-AI

**中国A股量化预测系统** — Qlib v17 · 9核心特征 · 未来1日收益预测

## 🎯 核心功能

| 功能 | 说明 |
|------|------|
| 🤖 ML预测 | Qlib v17 离线跑批（LightGBM），9 个技术/动量特征，未来1日收益预测 |
| 📈 实时行情 | 新浪财经数据源，5秒刷新，支持沪/深两市/北交所 |
| 📊 技术分析 | MACD / KDJ / RSI / CCI / DMI / 布林带 / VWAP |
| 📡 新闻监控 | 新浪财经 7x24 小时全球实时新闻 |
| 🔍 股票搜索 | 新浪 Suggest API 双层缓存搜索（支持拼音/代码/名称） |
| 🤖 智能研判 | AI 首席分析师报告，提供基本面画像与周一走势预测 |

## 🚀 快速开始

```bash
# 1. 启动 Web 与 API 服务
pip install -r requirements.txt
python app.py
# 打开 http://localhost:5000

# ================================
# 以下为 Qlib 跑批与数据更新命令 (可选)
# 注：Qlib 依赖不在基础 requirements.txt 中，需自行配置独立的 Qlib 环境
# pip install pyqlib
# ================================

# [常规稳定版] Qlib v17
# python train_qlib_v17.py
# python daily_inference.py
# python evaluate_model.py --version v17

# [激进增强版] Qlib v18 (推荐，含特征截面标准化与 22 大高维特征)
# python train_qlib_v18.py
# python daily_inference_v18.py
# python evaluate_model.py --version v18
```

## 🤖 v17 模型

| 指标 | 值 |
|------|-----|
| 模型框架 | Microsoft Qlib |
| 模型类型 | LightGBM |
| 特征数量 | 9个截面特征 |
| 预测目标 | 未来1日收益率 |
| 监控范围 | 沪深 300 核心成分股 |

## 📡 API端点

| 端点 | 说明 |
|------|------|
| `/api/realtime/<code>` | 实时行情 |
| `/api/minute/<code>` | 5分钟K线 |
| `/api/technical/<code>` | 技术指标 |
| `/api/ai_analyze/<code>` | AI 首席研判报告 |
| `/api/ml_predict/<code>` | 离线 JSON 毫秒级返回 |
| `/api/ml_predict_all` | 沪深300批量排序与信号 |
| `/api/model_report` | 离线模型评估报告 |
| `/api/news` | 实时新闻流 |
| `/api/search?q=` | 智能股票搜索 |

## ⚠️ 免责声明

本系统仅供个人学习研究使用，不构成任何投资建议。股市有风险，投资需谨慎。
