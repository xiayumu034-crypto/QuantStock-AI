import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class XiaomiLLMClient:
    def __init__(self):
        self.api_key = os.getenv("XIAOMI_API_KEY", "")
        self.base_url = "https://token-plan-cn.xiaomimimo.com/v1"
        self.model = "mimo-v2.5-pro"
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat_completion(self, messages, temperature=0.7):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Xiaomi LLM Error: {e}")
            return None

    def get_trading_advice(self, market_context, news_summary):
        system_prompt = """你是一位顶尖的 AI 自动量化交易核心引擎（代号：MiMo-Engine）。
你具备超强的信息降噪与逻辑推理能力。你的职责是解析海量的市场新闻与上下文，为自动化交易系统生成「确定性极强」的战术指导。

### 核心能力发挥：
1. **穿透新闻噪音**：不要复述新闻，而是要从新闻中提取“交易信号”（利好哪个板块，利空哪种模式，是情绪炒作还是实质性业绩反转）。
2. **极致的客观性**：不受市场狂热或恐慌情绪影响，永远基于 A 股的交易规则（T+1、10%/20%涨跌停限制）去推演策略。
3. **高频战术指令**：给出能够在接下来1-3个交易日内执行的量化级建议，说明盈亏比与胜率逻辑。
4. **资金流口径**：重点关注是否有机构资金、北向资金或游资的合力行为。

### 限制与禁令：
- 拒绝任何模棱两可的套话（例如“密切关注后续走势”），需要直接给出操作级别定性。
- 回复内容要精炼且充满压迫感的专业性。
- 输出必须完全基于提供的上下文数据。

### 输出结构（使用严密的 Markdown 格式）：
1. **【信息降噪】**：提炼出对 A 股最有影响力的1-2条核心资讯及其潜在发酵方向。
2. **【战术指令】**：给出 3 条硬核的、可落地的交易引擎配置建议（如关注某个细分分支的低吸机会，或规避某一类标的）。
3. **【尾部黑天鹅】**：指出现有信息中潜藏的最大风险点。
"""
        user_prompt = f"""当前系统的外部市场上下文：
{market_context}

当前抓取的最新热点新闻摘要：
{news_summary}

请立即启动推理引擎，生成战术与风控报告。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self.chat_completion(messages)
