import re
import markdown

class BaseModelAdapter:
    """
    大模型兼容适配器基类
    用于处理不同模型的 Prompt 差异、输出格式乱码修正和 UI 渲染
    """
    def adjust_system_prompt(self, task_type, base_prompt):
        # 基础防呆指令，应对较弱的模型
        if task_type == 'news_reasoning':
            return base_prompt + "\n\n【强制系统指令】：你的“逻辑推演链”必须在一行内输出，请使用 '->' 连接各个推理节点！不要在中途换行！"
        return base_prompt

    def parse_news_reasoning(self, text):
        """图谱正则渲染解析器 (支持 Mermaid 脑图)"""
        # 将 markdown 里的 ```mermaid ... ``` 替换为 <div class="mermaid"> ... </div>
        # 先处理可能的 mermaid 块
        import re
        
        # 匹配 ```mermaid ... ```
        def mermaid_replacer(match):
            content = match.group(1).strip()
            return f'<div class="mermaid" style="background:#1a1a2e; padding:15px; border-radius:10px; margin:15px 0; text-align:center;">\n{content}\n</div>'
            
        text = re.sub(r'```mermaid\s+(.*?)\s+```', mermaid_replacer, text, flags=re.DOTALL)
        
        # 兜底：如果模型依然输出了 -> 的文字链，保留原有的彩色文字切片处理
        lines = text.split('\n')
        for i, line in enumerate(lines):
            # 兼容多种箭头符号 (排除 html 注释等特殊情况)
            if ('->' in line or '➡️' in line or '=>' in line) and not '<div' in line:
                parts = re.split(r'->|➡️|=>', line)
                if len(parts) >= 3:
                    graph_html = '<div class="reasoning-graph mt-3 mb-3" style="display:flex; flex-wrap:wrap; align-items:center; gap:8px;">'
                    for idx, part in enumerate(parts):
                        clean_part = part.strip().replace('**', '').replace('-', '').strip()
                        if not clean_part: continue
                        graph_html += f'<div class="graph-node" style="background:rgba(111,66,193,0.15); border:1px solid #6f42c1; color:#e0c8ff; padding:5px 12px; border-radius:20px; font-weight:bold; font-size:0.9rem;">{clean_part}</div>'
                        if idx < len(parts) - 1:
                            graph_html += '<div class="graph-arrow text-muted" style="font-size:1.2rem;">➔</div>'
                    graph_html += '</div>'
                    lines[i] = "\n" + graph_html + "\n"
        new_text = '\n'.join(lines)
        return markdown.markdown(new_text, extensions=['extra', 'codehilite'])

    def parse_stock_analysis(self, text):
        return markdown.markdown(text, extensions=['extra', 'codehilite'])


class DeepSeekAdapter(BaseModelAdapter):
    """DeepSeek 模型兼容方案"""
    def adjust_system_prompt(self, task_type, base_prompt):
        base_prompt = super().adjust_system_prompt(task_type, base_prompt)
        # DeepSeek 便宜但部分版本喜欢输出啰嗦的思维过程
        return base_prompt + "\n\n【DeepSeek专属指令】：请直接输出最终的 Markdown 结构结果，绝对不要输出任何 <think> 标签或其他无关的思考过程。"


class KimiAdapter(BaseModelAdapter):
    """Kimi (Moonshot) 模型兼容方案"""
    def adjust_system_prompt(self, task_type, base_prompt):
        base_prompt = super().adjust_system_prompt(task_type, base_prompt)
        return base_prompt + "\n\n【Kimi专属指令】：你拥有处理超长上下文的优势，请在分析时尽可能多地引用研报数据，并严格使用最高级别的 Markdown 格式美化排版。"


class QwenAdapter(BaseModelAdapter):
    """阿里通义千问 (Qwen) 模型兼容方案"""
    def parse_news_reasoning(self, text):
        # 阿里千问有时会使用不规范的中文长破折号 "——>"
        text = text.replace('——>', '->').replace('--->', '->')
        return super().parse_news_reasoning(text)


def get_model_adapter(model_name: str) -> BaseModelAdapter:
    """
    工厂模式：根据用户当前配置的模型名称，智能路由到对应的兼容适配器
    """
    name = model_name.lower()
    if 'deepseek' in name:
        return DeepSeekAdapter()
    elif 'moonshot' in name or 'kimi' in name:
        return KimiAdapter()
    elif 'qwen' in name or '通义' in name:
        return QwenAdapter()
    else:
        # MiMo 或其他默认模型走基类
        return BaseModelAdapter()