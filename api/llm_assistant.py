import os
from openai import OpenAI
import logging

XIAOMI_API_KEY = "sk-cqvvnuhso706lj6njtjfl76gfhozwjqpv379ilmbbabgsqwv"
XIAOMI_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MODEL_NAME = "mimo-v2.5-pro"

def generate_ai_analysis(portfolio, logs, hot_sectors):
    try:
        client = OpenAI(api_key=XIAOMI_API_KEY, base_url=XIAOMI_BASE_URL)
        
        system_prompt = """你是一个专业的AI量化交易与市场研判助手，你是系统的“操盘大脑”。
你的核心任务是根据用户的持仓数据、历史交易操作以及当前市场的热点板块，提供深度、专业、富有洞察力的分析报告。

【分析维度要求】
1. 资产与持仓诊断：评估当前现金比例和持仓股票的合理性，是否有过度集中的风险。
2. 交易动作复盘：点评近期买卖记录的逻辑（结合你所看到的 V19模型评分、新闻热点驱动等原因），夸奖或提示潜在风险。
3. 市场热点嗅觉：结合当前市场强势领涨的行业板块，提示可能的机会或者资金轮动的风险。
4. 综合操作建议：给用户下一步的操作定个基调（如：持股待涨、果断止盈、防守反击等）。

【回复格式要求】
请使用 HTML 格式返回（因为将展示在前端悬浮弹窗中）。不要带有 Markdown 的 ```html 代码块包裹，直接返回合法的 HTML 片段即可。
尽量使用 Bootstrap 5 的类名（如 text-success, text-danger, card, badge 等）进行排版，保持界面的炫酷和暗黑风格兼容（文本建议使用 text-light 等）。"""

        user_prompt = f"""请对以下数据进行研判：

【1. 当前持仓情况】
{portfolio}

【2. 近期交易记录】
{logs}

【3. 今日全市场强势板块（部分）】
{hot_sectors}

请根据以上信息，为我出具一份专业的AI分析报告。"""

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error calling Xiaomi AI: {e}")
        return f"<div class='text-danger'>AI研判助手暂时不可用，请稍后再试。错误信息：{str(e)}</div>"
