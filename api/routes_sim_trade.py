import os
import json
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
import akshare as ak

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

def log_trade(account, action, code, name, price, vol, reason="手工操作"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    amount = price * vol
    log_msg = {
        "time": timestamp,
        "action": action,
        "code": code,
        "name": name,
        "price": price,
        "vol": vol,
        "amount": amount,
        "reason": reason
    }
    account["logs"].insert(0, log_msg)
    # Keep only last 50 logs
    account["logs"] = account["logs"][:50]

@sim_trade_bp.route('/info', methods=['GET'])
def get_info():
    account = load_account()
    
    # Calculate total asset
    total_asset = account["cash"]
    holdings_value = 0
    
    # In a real scenario we'd batch fetch prices, but for simplicity here we assume the frontend might fetch or we use last known.
    # To be fast, let's just use cost_price if current is unknown, but we should update it.
    try:
        if account["holdings"]:
            # Need to get realtime prices for holdings to calculate net worth
            # But AKShare realtime API might be slow for all. Let's do it if needed, or rely on a background task.
            # We'll just return the account directly for now.
            pass
    except Exception as e:
        pass

    # Quick estimate without real-time price fetch to keep API fast
    for code, pos in account["holdings"].items():
        total_asset += pos["vol"] * pos.get("current_price", pos["cost_price"])
    
    account["total_asset"] = total_asset
    return jsonify({"status": "success", "data": account})

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
    if not account.get("auto_trade", False):
        return jsonify({"status": "skip", "msg": "Auto trade is disabled"})

    # 1. Fetch ML predictions
    from api.routes_model import read_daily_predictions
    predictions, _, _ = read_daily_predictions("v19")
    if not predictions:
        return jsonify({"status": "error", "msg": "No V19 predictions available"})
    
    # Sort predictions by probability (descending)
    sorted_preds = sorted([
        {"code": k, "pred": v.get("predicted_return", 0)} for k, v in predictions.items()
    ], key=lambda x: x["pred"], reverse=True)

    n = len(sorted_preds)
    if n == 0:
        return jsonify({"status": "error", "msg": "Empty predictions"})
        
    p90_val = sorted_preds[int(n*0.1)]["pred"] if n >= 10 else 0.6
    p30_val = sorted_preds[int(n*0.7)]["pred"] if n >= 10 else 0.4

    top_codes = [p["code"] for p in sorted_preds if p["pred"] >= p90_val]
    
    names_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stock_names.json")
    stock_names = {}
    if os.path.exists(names_file):
        with open(names_file, 'r', encoding='utf-8') as f:
            stock_names = json.load(f)

    # 2. Get real-time prices for holdings and top candidates
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

    # 3. Sell Logic: if holding's pred is < p30_val (bottom 30%) or missing
    # To avoid day-trading lock (T+1), we ideally check hold days, but for simple simulation we'll just sell.
    codes_to_sell = []
    for code, pos in account["holdings"].items():
        if code in prices:
            pos["current_price"] = prices[code] # Update current price
        
        pred_val = predictions.get(code, {}).get("predicted_return", 0)
        if pred_val < p30_val:
            codes_to_sell.append(code)

    for code in codes_to_sell:
        if code not in prices or prices[code] <= 0:
            continue
        pos = account["holdings"].pop(code)
        sell_price = prices[code]
        vol = pos["vol"]
        revenue = sell_price * vol * 0.999 # 0.1% fee
        account["cash"] += revenue
        name = stock_names.get(code, code)
        reason = f"V19评分下降 (仅{(predictions.get(code, {}).get('predicted_return', 0)*100):.1f}%)"
        log_trade(account, "sell", code, name, sell_price, vol, reason)
        actions_taken.append(f"卖出 {name}({code})")

    # 4. Buy Logic: Buy top_codes if not holding, and cash > 0
    target_pos_value = account["total_asset"] / MAX_POSITIONS if "total_asset" in account else 20000.0
    
    for code in top_codes:
        if len(account["holdings"]) >= MAX_POSITIONS:
            break
        if code in account["holdings"]:
            continue
        
        if code not in prices or prices[code] <= 0:
            continue
            
        buy_price = prices[code]
        # Calculate how many shares we can buy (lots of 100)
        invest_amount = min(account["cash"], target_pos_value)
        vol = int((invest_amount / buy_price) // 100) * 100
        cost = buy_price * vol * 1.001 # 0.1% fee
        
        if vol > 0 and account["cash"] >= cost:
            account["cash"] -= cost
            name = stock_names.get(code, code)
            account["holdings"][code] = {
                "name": name,
                "vol": vol,
                "cost_price": buy_price,
                "current_price": buy_price
            }
            pred_val = predictions.get(code, {}).get("predicted_return", 0)
            reason = f"V19强烈看涨 ({(pred_val*100):.1f}%)"
            log_trade(account, "buy", code, name, buy_price, vol, reason)
            actions_taken.append(f"买入 {name}({code})")

    save_account(account)
    
    return jsonify({
        "status": "success", 
        "actions": actions_taken, 
        "msg": f"Step completed. {len(actions_taken)} actions taken." if actions_taken else "No actions taken."
    })
