import os
import logging
import markdown
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

import json
from api.model_adapters import get_model_adapter

def get_llm_client():
    config_file = "data/ai_config.json"
    api_key = os.getenv("XIAOMI_API_KEY", "")
    base_url = "https://token-plan-cn.xiaomimimo.com/v1"
    model = "mimo-v2.5-pro"
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                api_key = config.get("api_key") or api_key
                base_url = config.get("base_url") or base_url
                model = config.get("model") or model
        except Exception as e:
            logging.error(f"Failed to load ai_config.json: {e}")
            
    return api_key, base_url, model

def generate_ai_analysis(portfolio_str, logs_str, hot_sectors_str):
    api_key, base_url, model = get_llm_client()
    adapter = get_model_adapter(model)

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

    system_prompt = adapter.adjust_system_prompt('portfolio_analysis', system_prompt)

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
        return adapter.parse_stock_analysis(ai_text)
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

def generate_stock_ai_analysis(code, name, info_dict, is_monster=False):
    """单只股票的AI深度分析（基本面+成妖逻辑）"""
    api_key, base_url, model = get_llm_client()
    adapter = get_model_adapter(model)
    
    system_prompt = """你是一位顶尖的 A 股游资和基本面分析师双栖专家。
你的任务是对单只个股进行极其犀利、一针见血的分析。
不要罗列枯燥的数据，你要把数据翻译成“人话”和“操盘逻辑”。
必须采用 Markdown 格式排版。"""

    monster_req = ""
    if is_monster:
        monster_req = "\n**特别要求**：这是一只【连板妖股】。你需要重点分析它【为什么能成妖】？背后的炒作暗线、政策预期或情绪溢价是什么？以及目前连板后的博弈风险提示。"

    user_prompt = f"""请分析以下股票：
【代码】：{code}
【名称】：{name}
【基本面数据】：
{info_dict}

要求：
1. **行业地位与核心产品**：公司是干嘛的？在产业链中是龙头还是边缘跟风？
2. **年报/业绩亮点（或隐患）**：有没有业绩雷？或者有没有困境反转的预期？
3. **资金面与博弈逻辑**：结合上述信息，当前市场资金为什么选择它？{monster_req}
4. **后市推演**：给出简短有力的短线及中线推演。"""

    system_prompt = adapter.adjust_system_prompt('portfolio_analysis', system_prompt)

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
        return adapter.parse_stock_analysis(ai_text)
    except Exception as e:
        error_str = str(e).lower()
        if "401" in error_str or "invalid_key" in error_str or "unauthorized" in error_str:
            mock_text = f"""### 🤖 {name} ({code}) 深度研判 (体验模式)
> **⚠️ 提示**: API Key 无效，以下为离线模拟生成。

**1. 行业地位与产品**：
主营业务覆盖相关赛道，在近期风口中表现活跃。属于资金青睐的高弹性品种。

**2. 业绩简评**：
营收及利润呈现一定波动，短期内基本面退居次位，资金主要博弈的是预期差。

**3. 博弈逻辑与成妖探讨**：
该股近期获得游资爆炒，主要因沾边热门概念。接力情绪浓厚，但也累积了庞大的获利盘。

**4. 后市推演**：
短线：不进则退，若断板容易遭遇核按钮，需观察承接力度。
中线：题材炒作结束后将回归基本面，建议控制仓位。"""
            return markdown.markdown(mock_text, extensions=['extra', 'codehilite'])
        
        logging.error(f"Stock AI Analysis failed: {e}")
        return f"<div class='alert alert-danger'>AI 个股分析失败: {str(e)}</div>"

def generate_news_reasoning(news_text):
    """
    事件驱动：基于新闻进行多跳图谱推理
    """
    api_key, base_url, model = get_llm_client()
    adapter = get_model_adapter(model)
    
    system_prompt = """你是一位顶尖的量化私募基金经理，精通“事件驱动策略”与多跳逻辑推理。
你的任务是将一条新闻资讯转化为 A 股市场的交易逻辑。
请按照“知识图谱多跳推理”的模式，剥丝抽茧地分析：新闻事件 -> 宏观影响 -> 对应的A股板块 -> 可能利好的龙头个股特征。

请严格使用 Markdown 格式，并包含以下模块：
1. **📌 事件定性**：一句话总结该事件的本质。
2. **🕸️ 逻辑推演链图谱**：请务必提供一个 Mermaid 语法的思维导图（mindmap），用于展示多跳推理过程。必须以 ````mermaid` 开始，```` 结束。
格式参考：
````mermaid
mindmap
  root((事件名称))
    宏观影响A
      受益板块A
        相关标的1
        相关标的2
    宏观影响B
      受益板块B
        相关标的3
````
3. **🎯 关联板块与个股画像**：指出最直接受益的 A 股板块，并描述该板块中哪类股票最容易成为资金龙头（如：盘子小、有叠加概念等），如果能举例 1-2 只大家熟知的行业中军更好。
"""

    user_prompt = f"请对以下新闻进行深度量化多跳推理：\n【新闻内容】：{news_text}"
    system_prompt = adapter.adjust_system_prompt('news_reasoning', system_prompt)

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        ai_text = response.choices[0].message.content
        return adapter.parse_news_reasoning(ai_text)
    except Exception as e:
        error_str = str(e).lower()
        if "401" in error_str or "invalid_key" in error_str or "unauthorized" in error_str:
            mock_text = """### 🧠 MiMo 事件驱动推理 (体验模式)
> **⚠️ 提示**: API Key 无效，以下为离线推理演示。

**1. 📌 事件定性**
当前宏观事件对特定大宗商品或局部地缘政治产生了强烈刺激。

**2. 🕸️ 逻辑推演链图谱**
```mermaid
mindmap
  root((突发重大事件))
    供给侧缩减预期
      产品涨价
        资源类板块受益
          中国海油
          紫金矿业
    避险情绪升温
      航运板块受益
        中远海控
```

**3. 🎯 关联板块与个股画像**
- **核心板块**：资源开采、航运运输。
- **个股画像**：建议重点关注具有实际产能释放预期、市值在 100-300亿之间、机构资金介入较深的行业中军（如中国海油等逻辑标的）。"""
            return adapter.parse_news_reasoning(mock_text)
            
        logging.error(f"News Reasoning failed: {e}")
        return f"<div class='alert alert-danger'>AI 推理引擎罢工了: {str(e)}</div>"