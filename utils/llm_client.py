import os
import requests
import json
import logging

class XiaomiLLMClient:
    def __init__(self):
        self.api_key = "sk-cqvvnuhso706lj6njtjfl76gfhozwjqpv379ilmbbabgsqwv"
        self.base_url = "https://token-plan-cn.xiaomimimo.com/v1"
        self.model = "mimo-v2.5-pro"

    def chat_completion(self, messages, temperature=0.7):
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            logging.error(f"Xiaomi LLM Error: {e}")
            return None

    def get_trading_advice(self, market_context, news_summary):
        system_prompt = """你是一位顶级的量化交易策略专家和首席分析师，拥有深厚的宏观经济洞察力和敏锐的市场直觉。
你的任务是为用户的模拟交易系统提供「思考型」的决策建议。

### 核心行为准则：
1. **深度思考**：不要只看涨跌幅，要分析背后的逻辑（政策驱动、主力资金流向、板块轮动）。
2. **灵活应变**：当市场风向变化（如国家发布重大政策、突发地缘政治、大宗商品波动）时，主动调整关注重心。
3. **拒绝死板**：如果原定的技术指标失效，要敢于提出反直觉的避险或进攻建议。
4. **风险第一**：始终关注回撤风险，对过热板块提出警示。

### 限制条件：
- 严格基于 A 股规则（T+1，涨跌停限制）。
- 回复必须专业、精炼，具有可执行性。
- 禁止给出虚假的保证收益承诺。
"""
        user_prompt = f"""当前市场上下文：
{market_context}

最近热点新闻摘要：
{news_summary}

请根据以上信息，为我的自动交易引擎提供 3 条核心指导意见，并指出 1 个需要重点关注或回避的潜在机会/风险。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self.chat_completion(messages)
