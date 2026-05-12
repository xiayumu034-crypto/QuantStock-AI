import os
import json
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request

sim_trade_bp = Blueprint('sim_trade', __name__)

ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'sim_account.json')
INITIAL_CASH = 100000.0
MAX_POSITIONS = 5

def load_account():
    if os.path.exists(ACCOUNT_FILE):
        try:
            with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load account: {e}")
    return {
        "cash": INITIAL_CASH,
        "holdings": {},
        "logs": [],
        "auto_trade": False
    }

def save_account(account):
    os.makedirs(os.path.dirname(ACCOUNT_FILE), exist_ok=True)
    with open(ACCOUNT_FILE, 'w', encoding='utf-8') as f:
        json.dump(account, f, ensure_ascii=False, indent=4)

def log_trade(account, action, code, name, price, vol, fee, reason="系统自动"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    amount = price * vol
    log_msg = {
        "time": timestamp,
        "action": action,
        "code": code,
        "name": name,
        "price": price,
        "vol": vol,
        "amount": amount,
        "fee": round(fee, 2),
        "reason": reason
    }
    account["logs"].insert(0, log_msg)
    # 保留最近 500 条操作记录
    account["logs"] = account["logs"][:500]

@sim_trade_bp.route('/info', methods=['GET'])
def get_info():
    account = load_account()
    total_asset = account["cash"]
    for code, pos in account["holdings"].items():
        total_asset += pos["vol"] * pos.get("current_price", pos["cost_price"])
    
    account["total_asset"] = total_asset
    return jsonify({"status": "success", "data": account})

@sim_trade_bp.route('/logs', methods=['GET'])
def get_logs():
    date_filter = request.args.get('date') # YYYY-MM-DD
    account = load_account()
    logs = account.get("logs", [])
    
    if date_filter:
        logs = [l for l in logs if l['time'].startswith(date_filter)]
    
    return jsonify({"status": "success", "data": logs})

@sim_trade_bp.route('/ai_advice', methods=['GET'])
def ai_advice():
    """获取小米大模型提供的策略指导"""
    try:
        from utils.llm_client import XiaomiLLMClient
        client = XiaomiLLMClient()
        
        # 准备上下文
        account = load_account()
        holdings = [f"{v['name']}({k})" for k, v in account['holdings'].items()]
        market_ctx = f"账户净资产: {account.get('total_asset', 100000):.0f}, 当前持仓: {', '.join(holdings) if holdings else '空仓'}"
        
        # 获取最新新闻作为背景
        from data.news_data import fetch_all_news
        news_data = fetch_all_news()
        news_summary = ""
        if news_data:
            news_summary = "\n".join([f"- {n['title']}" for n in news_data[:8]])
            
        advice = client.get_trading_advice(market_ctx, news_summary)
        return jsonify({"status": "success", "data": advice})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@sim_trade_bp.route('/toggle_auto', methods=['POST'])
def toggle_auto():
    data = request.json
    account = load_account()
    account["auto_trade"] = bool(data.get("auto_trade", False))
    save_account(account)
    return jsonify({"status": "success", "auto_trade": account["auto_trade"]})

@sim_trade_bp.route('/step', methods=['POST'])
def sim_step():
    """Execute one step of AI auto trading (sell bad, buy good)"""
    account = load_account()
    
    is_manual = request.json and request.json.get("force", False)

    # 1. 严格判断是否在交易时间内 (09:30-11:30, 13:00-15:00)
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    is_weekday = now.weekday() < 5
    is_open = is_weekday and (("09:30" <= time_str <= "11:30") or ("13:00" <= time_str <= "15:00"))
    
    if not is_open and not is_manual:
        return jsonify({"status": "skip", "msg": "当前为休市时间，停止自动交易"})

    if not account.get("auto_trade", False) and not is_manual:
        return jsonify({"status": "skip", "msg": "自动交易已暂停"})

    # 2. 获取预测信号
    from api.routes_model import read_daily_predictions
    predictions, _, _ = read_daily_predictions("v19")
    if not predictions:
        return jsonify({"status": "error", "msg": "No V19 predictions available"})
    
    sorted_preds = sorted([
        {"code": k, "pred": v.get("predicted_return", 0)} for k, v in predictions.items()
    ], key=lambda x: x["pred"], reverse=True)

    n = len(sorted_preds)
    if n == 0:
        return jsonify({"status": "error", "msg": "Empty predictions"})
        
    p90_val = sorted_preds[int(n*0.1)]["pred"] if n >= 10 else 0.6
    p30_val = sorted_preds[int(n*0.7)]["pred"] if n >= 10 else 0.4

    top_codes = [p["code"] for p in sorted_preds if p["pred"] >= p90_val]
    
    # 2.5 接入【新闻与国家大事驱动】逻辑（超越原本监控池）
    event_driven_info = {}
    try:
        import akshare as ak
        sector_df = ak.stock_sector_spot(indicator='新浪行业')
        if not sector_df.empty:
            hot_sectors = sector_df.sort_values(by='涨跌幅', ascending=False).head(3)
            for _, row in hot_sectors.iterrows():
                sector_name = row['板块']
                leader_code = str(row['股票代码']) 
                leader_name = str(row['股票名称'])
                leader_change = float(row['个股-涨跌幅'])
                
                pure_code = leader_code[2:] if leader_code[:2] in ['sh', 'sz', 'bj'] else leader_code
                
                # 寻找有动能的票，排除封死20%涨停的极端情况
                if 2.0 < leader_change < 19.5:
                    if pure_code not in top_codes:
                        top_codes.insert(0, pure_code) # 优先买入热点
                    event_driven_info[pure_code] = {
                        "name": leader_name,
                        "reason": f"新闻热点驱动: [{sector_name}]板块强势领涨"
                    }
    except Exception as e:
        logging.error(f"Error fetching event driven stocks: {e}")

    names_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stock_names.json")
    stock_names = {}
    if os.path.exists(names_file):
        with open(names_file, 'r', encoding='utf-8') as f:
            stock_names = json.load(f)

    # 3. 抓取实时行情
    codes_to_fetch = list(set(list(account["holdings"].keys()) + top_codes[:10]))
    prices = {}
    try:
        from data.market_data import StockDataAPI
        api_client = StockDataAPI()
        for code in codes_to_fetch:
            rt_data = api_client.get_realtime_data(code)
            if rt_data and "current" in rt_data:
                prices[code] = rt_data["current"]
    except Exception as e:
        logging.error(f"Error fetching prices for sim: {e}")

    actions_taken = []

    # 4. 卖出逻辑 (排名跌出前70%)
    codes_to_sell = []
    for code, pos in account["holdings"].items():
        if code in prices:
            pos["current_price"] = prices[code]
        
        pred_val = predictions.get(code, {}).get("predicted_return", 0)
        if pred_val < p30_val:
            codes_to_sell.append(code)

    for code in codes_to_sell:
        if code not in prices or prices[code] <= 0:
            continue
        pos = account["holdings"].pop(code)
        sell_price = prices[code]
        vol = pos["vol"]
        amount = sell_price * vol
        
        # 东财标准手续费：佣金万2.5(单笔最低5元) + 过户费万0.1 + 印花税万5
        commission = max(amount * 0.00025, 5.0)
        transfer_fee = amount * 0.00001
        stamp_duty = amount * 0.0005
        fee = commission + transfer_fee + stamp_duty
        
        revenue = amount - fee
        account["cash"] += revenue
        name = stock_names.get(code, code)
        reason = f"V19评分跌出安全区"
        log_trade(account, "sell", code, name, sell_price, vol, fee, reason)
        actions_taken.append(f"卖出 {name}({code})")

    # 5. 买入逻辑 (排名前10%)
    target_pos_value = account.get("total_asset", 100000.0) / MAX_POSITIONS
    
    for code in top_codes:
        if len(account["holdings"]) >= MAX_POSITIONS:
            break
        if code in account["holdings"]:
            continue
        if code not in prices or prices[code] <= 0:
            continue
            
        buy_price = prices[code]
        
        # 预估最高可买金额，预留5元保底佣金
        max_invest = min(account["cash"] - 5.0, target_pos_value)
        if max_invest <= 0:
            continue
            
        vol = int((max_invest / buy_price) // 100) * 100
        if vol > 0:
            amount = buy_price * vol
            
            # 东财买入手续费：佣金万2.5(单笔最低5元) + 过户费万0.1
            commission = max(amount * 0.00025, 5.0)
            transfer_fee = amount * 0.00001
            fee = commission + transfer_fee
            cost = amount + fee
            
            if account["cash"] >= cost:
                account["cash"] -= cost
                if code in event_driven_info:
                    name = event_driven_info[code]["name"]
                    reason = event_driven_info[code]["reason"]
                else:
                    name = stock_names.get(code, code)
                    reason = f"V19强共振买入信号"
                
                account["holdings"][code] = {
                    "name": name,
                    "vol": vol,
                    "cost_price": buy_price,
                    "current_price": buy_price
                }
                log_trade(account, "buy", code, name, buy_price, vol, fee, reason)
                actions_taken.append(f"买入 {name}({code})")

    save_account(account)
    
    return jsonify({
        "status": "success", 
        "actions": actions_taken, 
        "msg": f"Step completed. {len(actions_taken)} actions taken." if actions_taken else "No actions taken."
    })

@sim_trade_bp.route('/analyze', methods=['GET'])
def ai_analyze():
    account = load_account()
    
    # 提取持仓
    portfolio = f"总资产: {account.get('total_asset', account['cash'])}, 可用资金: {account['cash']}\n"
    if account["holdings"]:
        for code, pos in account["holdings"].items():
            portfolio += f"- {pos['name']}({code}): {pos['vol']}股, 成本价: {pos['cost_price']}\n"
    else:
        portfolio += "当前空仓\n"
        
    # 提取日志(最近5条)
    logs_str = "最近无交易记录"
    if account["logs"]:
        logs_str = ""
        for log in account["logs"][:5]:
            logs_str += f"- [{log['time']}] {log['action']} {log['name']} {log['vol']}股 @ {log['price']}元 (原因: {log['reason']})\n"
            
    # 获取热点
    hot_sectors_str = "暂无数据"
    try:
        import akshare as ak
        sector_df = ak.stock_sector_spot(indicator='新浪行业')
        if not sector_df.empty:
            hot_sectors = sector_df.sort_values(by='涨跌幅', ascending=False).head(3)
            hot_sectors_str = ""
            for _, row in hot_sectors.iterrows():
                hot_sectors_str += f"- {row['板块']}: 涨跌幅 {row['涨跌幅']}%, 领涨股 {row['股票名称']}\n"
    except Exception as e:
        pass
        
    # 调用 LLM
    from api.llm_assistant import generate_ai_analysis
    report_html = generate_ai_analysis(portfolio, logs_str, hot_sectors_str)
    
    return jsonify({"status": "success", "html": report_html})