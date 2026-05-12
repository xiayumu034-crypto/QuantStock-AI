import os
import requests
import logging
import markdown

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

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.8
    }

    try:
        response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=40)
        response.raise_for_status()
        res_data = response.json()
        ai_text = res_data['choices'][0]['message']['content']
        
        # 将 Markdown 转换为 HTML
        html_output = markdown.markdown(ai_text, extensions=['extra', 'codehilite'])
        return html_output
    except Exception as e:
        logging.error(f"AI Analysis failed: {e}")
        return f"<div class='alert alert-danger'>AI 分析暂时罢工了: {str(e)}</div>"
