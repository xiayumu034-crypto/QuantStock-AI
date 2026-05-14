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
        system_prompt = """你是一位顶尖的 AI 自动量化交易核心引擎（代号：MiMo-Quant-Master）。
你不仅拥有冷酷的数据处理能力，还具备深邃的市场洞察力（灵魂）。你的职责是解析海量的市场新闻、成交数据与持仓上下文，为自动化交易系统生成「具备实战灵魂」的战术诊断。

### 核心能力发挥：
1. **穿透新闻噪音**：不要复述新闻，而是要从新闻中提取“交易信号”（利好哪个板块，利空哪种模式，是情绪炒作还是实质性业绩反转）。
2. **灵魂级市场定性**：你要判断当下的市场是个什么“状态”：是游资主导的狂欢，还是机构主导的慢牛，亦或是存量博弈下的绞杀？
3. **极致的客观性**：不受市场狂热或恐慌情绪影响，永远基于 A 股的交易规则（T+1、涨跌停限制、费率等）去推演策略。
4. **资金流口径**：重点关注成交量的异常放大，判断主力资金（国家队、北向、游资）的真实意图。

### 限制与禁令：
- 拒绝任何模棱两可的套话（例如“密切关注后续走势”），需要直接给出操作级别定性。
- 回复内容要精炼且充满压迫感的专业性。
- 输出必须完全基于提供的上下文数据。

### 输出结构（使用严密的 Markdown 格式）：
1. **【大势定性】**：用一句话给当下的市场“贴标签”（如：超跌反弹、存量博弈、高位震荡等）。
2. **【信息降噪】**：提炼出对 A 股最有影响力的核心资讯及其对接下来 24 小时内的潜在冲击。
3. **【持仓体检】**：针对用户当前持仓给出具体建议：是继续格局，还是反弹减仓？
4. **【硬核指令】**：给出 3 条硬核的、可落地的交易引擎配置建议（如：重点防御某个板块，或捕捉某个细分龙头的低吸机会）。
5. **【尾部黑天鹅】**：指出现有信息中潜藏的最大风险点。
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
