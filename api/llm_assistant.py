import os
import logging
import markdown
from openai import OpenAI

def generate_ai_analysis(portfolio_str, logs_str, hot_sectors_str):
    api_key = "sk-cqvvnuhso706lj6njtjfl76gfhozwjqpv379ilmbbabgsqwv"
    base_url = "https://token-plan-cn.xiaomimimo.com/v1"
    model = "mimo-v2.5-pro"

    system_prompt = """你是一位精通 A 股市场的资深量化交易员和宏观分析师，现在担任用户的「AI 模拟操盘大脑」。
你的灵魂特质是：**深度思考、极速变通、逻辑严密、言之有物**。

### 你的目标
针对用户的模拟账户现状，结合当前市场热点，给出具有前瞻性和「灵魂」的操盘指导。

### 你的思考维度：
1. **现状诊断**：分析账户持仓是否过于集中，持仓标的是否符合当前市场热点。
2. **变通建议**：如果当前持仓股表现平平，而市场出现了新的爆发性板块，建议如何“腾笼换鸟”。
3. **宏观对齐**：将账户动作与当前最火的「国家大事」（如低空经济、AI、半导体等）联系起来，解释逻辑。
4. **风险预警**：对连续大涨后的回调风险、量价背离等技术陷阱给出具体警示。

### 限制与禁令：
- **A 股常识**：你必须知道 A 股是 T+1 交易，且涨跌停限制（主板10%，双创20%）。
- **杜绝废话**：不要说“股市有风险”这种没营养的套话，要说“当前成交量萎缩，建议收缩战线”这种具体判断。
- **输出格式**：使用 Markdown 语法。

### 结构要求：
1. **【大脑研判】**：一句话概括当前最核心的市场情绪和账户处境。
2. **【持仓体检】**：点评现有持仓的优劣。
3. **【机会捕获】**：基于热点板块建议关注的方向。
4. **【明日推演】**：对下一个交易日的操作预案。
"""

    user_prompt = f"""### 1. 账户现状
{portfolio_str}

### 2. 最近交易日志
{logs_str}

### 3. 当前市场最强行业/板块
{hot_sectors_str}

请基于以上数据，为我生成一份有深度、会变通的操盘研判报告。"""

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8
        )
        ai_text = response.choices[0].message.content
        return markdown.markdown(ai_text, extensions=['extra', 'codehilite'])
    except Exception as e:
        error_str = str(e).lower()
        if "401" in error_str or "invalid_key" in error_str or "unauthorized" in error_str:
            mock_text = """### 🧠 操盘大脑研判（体验模式）

> **⚠️ 系统提示**：当前未配置有效的 API Key (或原 Key 已失效)，正在为您呈现 **AI 脱机模拟报告**。如需真实分析，请在代码中替换您的专属 Key。

**【大脑研判】**：市场轮动加速，资金主要聚焦于科技与低空经济，当前账户持仓处于防御状态。

**【持仓体检】**：目前持仓中规中矩，但缺乏绝对的领涨龙头，建议汰弱留强，释放闲置资金。

**【机会捕获】**：建议密切关注近期突破 20 日均线的强势科技标的，同时警惕高位连板股的突然核按钮补跌。

**【明日推演】**：如果早盘大盘放量上攻，可适当加仓核心标的；若出现缩量阴跌，则严格保持现有仓位观望，切勿盲目抄底。"""
            return markdown.markdown(mock_text, extensions=['extra', 'codehilite'])
            
        logging.error(f"AI Analysis failed: {e}")
        return f"<div class='alert alert-danger'>AI 分析暂时罢工了: {str(e)}</div>"
