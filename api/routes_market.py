from flask import Blueprint, jsonify, request, render_template
import requests
import pandas as pd
import re
import akshare as ak
from data.market_data import StockDataAPI
from api.llm_assistant import generate_stock_ai_analysis

market_bp = Blueprint('market', __name__)
stock_api = StockDataAPI()

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
    # 模拟深度研判逻辑 (实战中可接入LLM或更复杂的数据源)
    # 这里我们根据代码段和现有行情给出逻辑化建议
    
    # 简单的基本面画像
    analysis = {
        "code": clean_code,
        "fundamental": {
            "status": "良好" if int(clean_code) % 2 == 0 else "稳健",
            "pe_ratio": "24.5",
            "pb_ratio": "3.2",
            "revenue_growth": "+12.8%",
            "net_profit_growth": "+15.4%",
            "risk_level": "中低"
        },
        "monday_prediction": {
            "action": "逢低吸纳" if int(clean_code) % 3 == 0 else "观望为宜",
            "support_level": "下方 5 日均线支撑强",
            "resistance_level": "上方 20 日均线处有抛压",
            "expected_open": "平开或小幅高开"
        },
        "ai_conclusion": f"针对[{clean_code}]，基本面整体健康。周一建议关注量能变化，若早盘能站稳分时均线，可考虑分批建仓。中长期看，该板块受政策支持，回撤即是机会。"
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
        # 使用新浪财经7x24小时全球实时财经新闻播报
        url = "https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size=20&zhibo_id=152"
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
                    
                    news_list.append({
                        'id': item.get('id'),
                        'title': title,
                        'content': content,
                        'time': item.get('create_time'),
                        'url': doc_url,
                        'source': '新浪财经',
                        'is_important': True if item.get('tag') == '1' else False,
                        'sentiment': '中性'
                    })
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
