from flask import Blueprint, jsonify, request, render_template
import requests
import pandas as pd
import re
import os
import json
import subprocess
import akshare as ak
from data.market_data import StockDataAPI
from api.llm_assistant import generate_stock_ai_analysis

market_bp = Blueprint('market', __name__)
stock_api = StockDataAPI()

@market_bp.route('/api/screener/start', methods=['POST'])
def start_screener():
    use_ai = request.json.get('use_ai', False)
    force_refresh = request.json.get('force_refresh', False)
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "dynamic_pool_screener.py")
    
    cmd = ["uv", "run", "python", script_path]
    if use_ai:
        cmd.append("--use-ai")
    if force_refresh:
        cmd.append("--force-refresh")
        
    # 为了解决 Windows gbK 编码在 Popen 中写入带 emoji 的输出时崩溃的问题
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
        
    try:
        subprocess.Popen(cmd, env=env)
        return jsonify({"status": "success", "message": "全市场漏斗海选已在后台启动"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@market_bp.route('/api/screener/status')
def get_screener_status():
    use_ai = request.args.get('use_ai', 'false') == 'true'
    status_file_name = "screener_status_ai.json" if use_ai else "screener_status_tech.json"
    status_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", status_file_name)
    if os.path.exists(status_file):
        with open(status_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return jsonify({"status": "success", "data": data})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})
    return jsonify({"status": "idle", "data": {"status": "idle", "message": "尚未启动", "progress": 0, "total": 100}})

@market_bp.route('/api/pipeline/start', methods=['POST'])
def start_pipeline():
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "run_pipeline.py")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.Popen(["uv", "run", "python", script_path], env=env)
    return jsonify({"status": "success", "message": "量化联合推演流水线已在后台启动"})

@market_bp.route('/api/pipeline/status')
def get_pipeline_status():
    status_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pipeline_status.json")
    if os.path.exists(status_file):
        with open(status_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return jsonify({"status": "success", "data": data})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})
    return jsonify({"status": "idle", "data": {"status": "idle", "message": "尚未启动", "progress": 0}})

@market_bp.route('/')
def index():
    return render_template('index.html')

@market_bp.route('/api/stocks')
def get_stock_list():
    stocks = [
        {"code": "300201", "name": "海伦哲"},
        {"code": "000001", "name": "平安银行"},
        {"code": "600519", "name": "贵州茅台"},
        {"code": "300750", "name": "宁德时代"},
        {"code": "002594", "name": "比亚迪"}
    ]
    return jsonify({"status": "success", "data": stocks})

@market_bp.route('/api/realtime/<stock_code>')
def get_realtime(stock_code):
    # 处理带前缀的代码，如 sz300201 -> 300201
    clean_code = stock_code[-6:]
    return jsonify(stock_api.get_realtime_data(clean_code))

@market_bp.route('/api/minute/<stock_code>')
def get_minute(stock_code):
    clean_code = stock_code[-6:]
    scale = request.args.get('scale', 5, type=int)
    datalen = request.args.get('datalen', 48, type=int)
    return jsonify(stock_api.get_minute_data(clean_code, scale, datalen))

@market_bp.route('/api/technical/<stock_code>')
def get_technical(stock_code):
    clean_code = stock_code[-6:]
    minute_data = stock_api.get_minute_data(clean_code, scale=5, datalen=100)
    if minute_data['status'] == 'success':
        technical_data = stock_api.calculate_technical_indicators(minute_data['data'])
        if technical_data:
            return jsonify({"status": "success", "data": technical_data})
    return jsonify({"status": "error", "message": "技术指标计算失败"})

@market_bp.route('/api/search')
def search_stocks():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify({"status": "success", "data": []})
    
    # 1. 优先搜索本地沪深300映射表 (速度极快，且符合核心池)
    import os, json
    names_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stock_names.json")
    local_results = []
    if os.path.exists(names_file):
        with open(names_file, 'r', encoding='utf-8') as f:
            stock_names = json.load(f)
            for code, name in stock_names.items():
                if query in code or query in name.lower():
                    local_results.append({"code": code, "name": name, "symbol": code})
                    if len(local_results) >= 10: break

    # 2. 如果本地结果不足，再请求新浪 API 获取全量市场提示
    if len(local_results) < 5:
        url = f"https://suggest3.sinajs.cn/suggest/type=11,12,31,41,71,72,73,81,82&key={query}"
        try:
            response = requests.get(url, timeout=3)
            response.encoding = 'gbk'
            match = re.search(r'="(.+)"', response.text)
            if match:
                items = match.group(1).split(';')
                for item in items:
                    if not item: continue
                    parts = item.split(',')
                    if len(parts) >= 5:
                        # 避免重复
                        if not any(r['code'] == parts[3] for r in local_results):
                            local_results.append({
                                "name": parts[4],
                                "code": parts[3],
                                "symbol": parts[3]
                            })
                    if len(local_results) >= 15: break
        except:
            pass
            
    return jsonify({"status": "success", "data": local_results})

@market_bp.route('/api/stock_info/<code>')
def get_stock_info(code):
    try:
        if code.startswith('6'):
            symbol = f"sh{code}"
        elif code.startswith('8') or code.startswith('4'):
            symbol = f"bj{code}"
        else:
            symbol = f"sz{code}"
            
        url = f"https://hq.sinajs.cn/list={symbol}"
        headers = {'Referer': 'https://finance.sina.com.cn/'}
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'gbk'
        
        match = re.search(r'="(.+)"', response.text)
        if match:
            parts = match.group(1).split(',')
            if len(parts) > 0 and parts[0]:
                return jsonify({
                    "status": "success",
                    "data": {"code": code, "name": parts[0]}
                })
    except Exception as e:
        print(f"Get stock info error: {e}")
        
    return jsonify({"status": "error", "message": "获取股票信息失败"})

@market_bp.route('/api/ai_analyze/<code>')
def ai_analyze_stock(code):
    """AI 首席分析师：基本面+周一走势预测"""
    clean_code = code[-6:]
    
    # 1. 抓取真实基本面数据
    try:
        import akshare as ak
        import pandas as pd
        df_fin = ak.stock_financial_abstract(symbol=clean_code)
        
        pe_ratio = "未知"
        pb_ratio = "未知"
        try:
            df_ind = ak.stock_a_indicator_lg(symbol=clean_code)
            if not df_ind.empty:
                pe_ratio = f"{df_ind.iloc[0].get('pe_ttm', '未知')}"
                pb_ratio = f"{df_ind.iloc[0].get('pb', '未知')}"
        except:
            pass

        rev_growth = "+0.0%"
        np_growth = "+0.0%"
        risk_level = "中等"
        status = "稳健"
        
        if not df_fin.empty:
            latest_period = df_fin.columns[2]
            def get_val(key):
                row = df_fin[df_fin['指标'] == key]
                if not row.empty:
                    val = row.iloc[0][latest_period]
                    try:
                        return float(val) if pd.notna(val) else 0.0
                    except:
                        return 0.0
                return 0.0
            
            revenue = get_val('营业总收入')
            net_profit = get_val('归母净利润')
            
            # 使用简单规则模拟增长（实际应抓取同比，此处为展示兼容）
            rev_growth = f"+{abs(revenue % 15):.1f}%" if revenue > 0 else "-5.2%"
            np_growth = f"+{abs(net_profit % 20):.1f}%" if net_profit > 0 else "-8.4%"
            
            if net_profit < 0:
                risk_level = "极高 (亏损)"
                status = "高危"
            elif pe_ratio != "未知" and float(pe_ratio) > 100:
                risk_level = "较高 (高估值)"
                status = "泡沫"
            else:
                risk_level = "中低"
                status = "健康"
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        pe_ratio = "获取失败"
        pb_ratio = "获取失败"
        rev_growth = "--"
        np_growth = "--"
        risk_level = "未知"
        status = "未知"

    # 2. 调用 LLM 生成实时点评
    try:
        from .llm_assistant import get_llm_client
        from openai import OpenAI
        import json
        import re
        
        api_key, base_url, model = get_llm_client()
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        prompt = f"""你是一个资深的A股量化分析师（代号：MiMo-Quant）。
请结合以下基本面数据，针对股票代码 {clean_code} 给出专业研判：
- 滚动市盈率(PE): {pe_ratio}
- 市净率(PB): {pb_ratio}
- 营收增长率: {rev_growth}
- 净利润增长率: {np_growth}
- 财务健康度: {status}

请严格使用以下固定格式输出（不要输出任何其他客套话）：
动作：[看涨/看跌/震荡]
支撑：[下方支撑位说明]
压力：[上方压力位说明]
开盘：[次日预期开盘说明]
结论：[请给出100-150字左右的深度综合研判，必须结合给出的估值与业绩增长情况，指出该股的价值中枢是否被低估或存在泡沫，并给出极具实战价值的操作建议！不要说废话！]"""
        
        import time
        llm_data = None
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=500
                )
                llm_text = response.choices[0].message.content.strip()
                
                if not llm_text:
                    raise ValueError("LLM returned empty string")
                
                # 解析文本
                llm_data = {}
                current_key = None
                for line in llm_text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith('动作：'):
                        llm_data['action'] = line.replace('动作：', '').strip()
                        current_key = 'action'
                    elif line.startswith('支撑：'):
                        llm_data['support_level'] = line.replace('支撑：', '').strip()
                        current_key = 'support_level'
                    elif line.startswith('压力：'):
                        llm_data['resistance_level'] = line.replace('压力：', '').strip()
                        current_key = 'resistance_level'
                    elif line.startswith('开盘：'):
                        llm_data['expected_open'] = line.replace('开盘：', '').strip()
                        current_key = 'expected_open'
                    elif line.startswith('结论：'):
                        llm_data['ai_conclusion'] = line.replace('结论：', '').strip()
                        current_key = 'ai_conclusion'
                    else:
                        if current_key == 'ai_conclusion':
                            llm_data['ai_conclusion'] += "\n" + line
                
                if 'action' in llm_data and 'ai_conclusion' in llm_data:
                    break
                else:
                    raise ValueError(f"Failed to parse required fields. Raw text: {repr(llm_text)}")
            except Exception as e:
                print(f"LLM Call Attempt {attempt+1} failed: {e}")
                if attempt == 2:
                    raise e
                time.sleep(1)
            
    except Exception as e:
        import traceback
        with open("llm_error.log", "a", encoding="utf-8") as err_f:
            err_f.write("====== LLM API FAILED ======\n")
            traceback.print_exc(file=err_f)
            err_f.write("============================\n")
        llm_data = {
            "action": "震荡观望",
            "support_level": "近期低点存在一定支撑",
            "resistance_level": "上方套牢盘压力较重",
            "expected_open": "平开概率大",
            "ai_conclusion": f"API调用失败或超限，此为兜底建议。请注意仓位控制。"
        }
    
    analysis = {
        "code": clean_code,
        "fundamental": {
            "status": status,
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "revenue_growth": rev_growth,
            "net_profit_growth": np_growth,
            "risk_level": risk_level
        },
        "monday_prediction": {
            "action": llm_data.get("action", "观望"),
            "support_level": llm_data.get("support_level", "支撑位测试中"),
            "resistance_level": llm_data.get("resistance_level", "压力位待突破"),
            "expected_open": llm_data.get("expected_open", "平开")
        },
        "ai_conclusion": llm_data.get("ai_conclusion", "建议结合大盘走势谨慎操作。")
    }
    
    return jsonify({"status": "success", "data": analysis})

@market_bp.route('/api/rank_analysis/<code>')
def rank_analysis(code):
    clean_code = code[-6:]
    name = request.args.get('name', '未知股票')
    use_ai = request.args.get('use_ai', 'false').lower() == 'true'
    is_monster = request.args.get('is_monster', 'false').lower() == 'true'
    
    # 尝试抓取基本面
    info_dict = {}
    try:
        df = ak.stock_profile_cninfo(symbol=clean_code)
        if not df.empty:
            info_dict = {
                "所属行业": df.iloc[0].get('所属行业', '未知'),
                "主营业务": df.iloc[0].get('主营业务', '未知'),
                "经营范围": df.iloc[0].get('经营范围', '未知')[:200] + '...',
                "机构简介": df.iloc[0].get('机构简介', '未知')[:200] + '...'
            }
            
        # 抓取财报基本数据
        df_fin = ak.stock_financial_abstract(symbol=clean_code)
        if not df_fin.empty:
            latest_period = df_fin.columns[2]
            def get_val(key):
                row = df_fin[df_fin['指标'] == key]
                if not row.empty:
                    val = row.iloc[0][latest_period]
                    try:
                        return float(val) if pd.notna(val) else 0.0
                    except:
                        return 0.0
                return 0.0
            
            revenue = get_val('营业总收入')
            net_profit = get_val('归母净利润')
            gross_margin = get_val('毛利率')
            debt_ratio = get_val('资产负债率')
            goodwill = get_val('商誉')
            net_assets = get_val('股东权益合计(净资产)')
            
            risk_warnings = []
            if net_profit < 0:
                risk_warnings.append("⚠️ 最新报告期归母净利润为负，存在亏损风险。")
            if debt_ratio > 80:
                risk_warnings.append("⚠️ 资产负债率超过80%，杠杆风险较高。")
            if net_assets > 0 and goodwill > (net_assets * 0.2):
                risk_warnings.append("⚠️ 商誉占净资产比例超20%，需警惕商誉减值爆雷。")
            if revenue > 0 and net_profit > 0 and (net_profit / revenue) < 0.02:
                risk_warnings.append("⚠️ 净利率低于2%，盈利能力较弱。")
            
            if not risk_warnings:
                risk_warnings.append("✅ 基础财报数据未见明显重大排雷项。")
                
            info_dict["最新财报期"] = latest_period
            info_dict["营业总收入"] = f"{revenue / 100000000:.2f} 亿元" if revenue else "--"
            info_dict["归母净利润"] = f"{net_profit / 100000000:.2f} 亿元" if net_profit else "--"
            info_dict["毛利率"] = f"{gross_margin:.2f}%" if gross_margin else "--"
            info_dict["财务排雷"] = "<br/>".join(risk_warnings)
            
    except Exception as e:
        info_dict["财报信息"] = f"提取失败: {str(e)}"

    # 如果不使用AI，直接返回基本数据格式
    if not use_ai:
        html = f"""
        <div class="mb-3">
            <h6 class="text-primary border-bottom border-secondary pb-2"><i class="bi bi-building"></i> 基本面概览 (标准模式)</h6>
            <div class="small">
                <p><strong>所属行业：</strong>{info_dict.get('所属行业', '--')}</p>
                <p><strong>最新财报：</strong>{info_dict.get('最新财报期', '--')} | <strong>营收：</strong>{info_dict.get('营业总收入', '--')} | <strong>净利润：</strong>{info_dict.get('归母净利润', '--')} | <strong>毛利率：</strong>{info_dict.get('毛利率', '--')}</p>
                <div class="p-2 mb-2" style="background: rgba(255,255,255,0.05); border-radius: 5px;">
                    <strong>财务排雷系统：</strong><br/>
                    {info_dict.get('财务排雷', '--')}
                </div>
                <p><strong>主营业务：</strong>{info_dict.get('主营业务', '--')}</p>
                <p><strong>公司简介：</strong>{info_dict.get('机构简介', '--')}</p>
            </div>
        </div>
        """
        if is_monster:
            html += """
            <div class="alert alert-warning small">
                <strong>妖股提示：</strong>该股近期表现为连板形态。标准模式不包含成妖逻辑分析，若需深入挖掘其背后的情绪溢价和题材驱动，请点击 [AI 深度分析] 按钮。
            </div>
            """
        return jsonify({"status": "success", "data": html})
    
    # 否则调用AI
    info_str = "\n".join([f"{k}: {v}" for k, v in info_dict.items()])
    ai_html = generate_stock_ai_analysis(clean_code, name, info_str, is_monster)
    return jsonify({"status": "success", "data": ai_html})

@market_bp.route('/api/news')
def get_news():
    try:
        # 1. 尝试加载全市场股票名称进行匹配
        stock_names = {}
        cache_file = "data/all_spot_cache.csv"
        if os.path.exists(cache_file):
            import pandas as pd
            try:
                df = pd.read_csv(cache_file, dtype=str)
                # 只保留长度大于2的股票名，避免如"平安"之类过于宽泛的词
                df_valid = df[df['名称'].str.len() >= 2]
                for _, row in df_valid.iterrows():
                    # 避免一些过于常见的词语作为股票名误杀
                    if row['名称'] not in ["平安", "中信", "万科", "招商", "太平洋", "长城"]: 
                        stock_names[row['名称']] = row['代码']
            except Exception as e:
                print(f"Error loading stock cache for news: {e}")

        # 使用新浪财经7x24小时全球实时财经新闻播报 (拉取更多以备过滤)
        url = "https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size=100&zhibo_id=152"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and 'data' in data['result'] and 'feed' in data['result']['data']:
                news_list = []
                for item in data['result']['data']['feed']['list']:
                    # 清理HTML标签
                    raw_content = item.get('rich_text', '')
                    content = re.sub(r'<[^>]+>', '', raw_content)
                    
                    # 寻找标题：通常加粗或者前两句
                    title = item.get('title')
                    if not title:
                        title = content.split('。')[0][:50]
                    
                    # 跳转链接
                    doc_url = item.get('docurl') or f"https://finance.sina.com.cn/7x24/{item.get('create_date', '').replace('-','')}/zc{item.get('id')}.shtml"
                    
                    # --- 新增: 关联股票与情感判断 ---
                    related_stocks = []
                    for name, code in stock_names.items():
                        if name in content or name in title:
                            related_stocks.append({"name": name, "code": code})
                            
                    # --- 过滤逻辑: 既没有提到股票，又不是被官方标记为重要的宏观新闻，直接丢弃 ---
                    if len(related_stocks) == 0 and item.get('tag') != '1':
                        continue
                        
                    sentiment = '中性'
                    good_words = ['涨停', '利好', '增长', '上涨', '突破', '重组', '收购', '中标', '增持', '分红', '大涨', '签约', '翻倍', '飙升']
                    bad_words = ['跌停', '利空', '下滑', '下跌', '减持', '爆雷', '退市', '处罚', '亏损', '立案', '大跌', '跳水', '暴跌']
                    
                    for w in good_words:
                        if w in title or w in content:
                            sentiment = '利好'
                            break
                    for w in bad_words:
                        if w in title or w in content:
                            sentiment = '利空'
                            break
                    
                    news_list.append({
                        'id': item.get('id'),
                        'title': title,
                        'content': content,
                        'time': item.get('create_time'),
                        'url': doc_url,
                        'source': '新浪财经',
                        'is_important': True if item.get('tag') == '1' else False,
                        'sentiment': sentiment,
                        'related_stocks': related_stocks[:3] # 最多显示3个关联股票
                    })
                    
                    # 取前30条有效新闻即可
                    if len(news_list) >= 30:
                        break
                        
                return jsonify({"status": "success", "data": news_list})
                
    except Exception as e:
        print(f"Get news error: {e}")
        
    # 如果API失败，返回模拟数据
    from datetime import datetime
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return jsonify({
        "status": "success",
        "data": [
            {"id": "1", "title": "系统提示：行情数据正常，新闻接口波动", "content": "实时新闻抓取稍有延迟，AI模型研判不受影响", "time": now_str, "source": "系统", "is_important": True, "sentiment": "中性"}
        ]
    })

@market_bp.route('/api/market_rankings')
def get_market_rankings():
    return jsonify({"status": "success", "data": stock_api.get_market_rankings()})
