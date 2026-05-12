import os
import logging
import markdown
from openai import OpenAI

def generate_ai_analysis(portfolio_str, logs_str, hot_sectors_str):
    api_key = "tp-crye0n3ju9erc0j12npxv3e7cdi7a86phag35y9ypccmpspz"
    base_url = "https://token-plan-cn.xiaomimimo.com/v1"
    model = "mimo-v2.5-pro"

    system_prompt = """你是一位处于内测阶段的顶尖 AI 投资总监（代号：MiMo-Quant）。
你拥有强大的多维推理能力，精通 A 股市场（T+1、涨跌停板机制），擅长将【量化因子】与【宏观逻辑】和【市场情绪】相融合。
你的任务是对用户的模拟账户现状进行“骨灰级”诊断，并给出极具实战指导意义的操盘建议。

### 核心能力展现要求：
1. **深度逻辑拆解**：不能仅仅停留在“涨跌”表面。必须分析为什么涨（资金驱动、政策共振、超跌反弹还是业绩兑现）？结合传入的热点行业数据，挖掘潜在的暗线逻辑。
2. **苛刻的风险嗅觉**：作为量化大脑，你必须对风险极度敏感。严厉指出账户中存在的“高位追涨”、“弱势死扛”、“仓位过度集中”或“资金利用率低下”等致命问题。
3. **资金与周期管理**：在建议“腾笼换鸟”或“调仓换股”时，必须说明操作的节奏（如：分批建仓、打板确认、均线低吸等），体现出专业的交易素养。
4. **反套话机制**：绝对禁止使用“股市有风险，投资需谨慎”、“可能涨也可能跌”这种毫无信息量的废话。用数据和逻辑说话，给出确定的观点（即便观点带有条件前提）。

### 你的输出必须严格遵循以下 Markdown 结构，并使用丰富的排版（加粗、列表、引用等）：

# 🧠 MiMo-Quant 核心研判
> 💡 一句话定调当前账户的健康度与市场生存状态。

### 📊 账户体检与持仓穿透
（对当前持仓进行逐一深度点评。不仅要看成本，还要结合当下的板块热点，判断持仓股票是“持股待涨”、“逢高减仓”还是“无情割肉”。）

### 🔭 宏观与暗线追踪
（结合给定的市场热点，指出主力资金的攻击方向。不要仅仅罗列热点，要分析热点之间的轮动规律或延伸的炒作分支。）

### ⚔️ 次日操盘推演
（提供3个具体的交易预案，涵盖加仓、减仓、防守三种情境，必须具体到策略层面，如：若标的跌破 5 日线如何处理，若早盘放量如何处理。）
"""

    user_prompt = f"""以下是系统的输入数据，请发挥你最大的推理能力进行研判：

### 1. 账户现状与持仓结构
{portfolio_str}

### 2. 最近交易日志（观察操作节奏）
{logs_str}

### 3. 当前市场最强行业/板块（资金风向标）
{hot_sectors_str}

请基于上述数据，立即生成深度研判报告。"""

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2048
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
