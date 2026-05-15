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

def check_trade_limit(code, current_price, yesterday_close, action, ask1_price=None, bid1_price=None):
    """
    判断 A 股涨跌停是否限制交易
    逻辑：1. 价格计算校验 2. 盘口档位校验(最准)
    action: 'buy' or 'sell'
    """
    if not yesterday_close or not current_price:
        return False, ""
    
    # --- 1. 盘口档位深度校验 (Realtime Depth Check) ---
    # 涨停时，卖一价格为0或成交价已经封死且卖一挂单为0
    if action == 'buy':
        if ask1_price is not None and ask1_price <= 0:
            return True, "涨停封死，买入失败 (卖一队列为空)"
    # 跌停时，买一价格为0或成交价已经封死且买一挂单为0
    if action == 'sell':
        if bid1_price is not None and bid1_price <= 0:
            return True, "跌停封死，卖出失败 (买一队列为空)"

    # --- 2. 传统价格区间校验 ---
    limit_pct = 0.10
    if code.startswith(('30', '68')):
        limit_pct = 0.20
    elif code.startswith(('8', '9', '4')):
        limit_pct = 0.30
    
    # 容差处理
    up_limit = round(yesterday_close * (1 + limit_pct) + 0.0001, 2)
    down_limit = round(yesterday_close * (1 - limit_pct) + 0.0001, 2)
    
    if action == 'buy' and current_price >= up_limit:
        return True, f"涨停限制买入 ({current_price} >= {up_limit})"
    if action == 'sell' and current_price <= down_limit:
        return True, f"跌停限制卖出 ({current_price} <= {down_limit})"
    
    return False, ""

def log_trade(account, action, code, name, price, vol, fee, reason="系统自动", pnl=None, duration=None):
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
        "reason": reason,
        "pnl": round(pnl, 2) if pnl is not None else None,
        "duration": duration
    }
    account["logs"].insert(0, log_msg)
    # 保留最近 500 条操作记录
    account["logs"] = account["logs"][:500]

def calc_dynamic_sl_tp(code):
    """
    基于过去40个交易日的数据计算动态止损和止盈点 (ATR与半衰期动态通道算法)
    吸取 Ernie Chan《Quantitative Trading》中 Half-Life 思想：
    通过对价格序列进行线性回归，计算其回归均值的半衰期，以此作为动态均线的窗口期。
    """
    try:
        import akshare as ak
        import pandas as pd
        import numpy as np
        import math
        import scipy.stats
        
        symbol = code
        df = pd.DataFrame()
        import time
        from data.market_data import StockDataAPI
        api_client = StockDataAPI()
        
        for _ in range(3):
            try:
                df = api_client.get_daily_history(stock_code=symbol)
                if not df.empty:
                    break
            except Exception:
                pass
            time.sleep(1)
                
        if not df.empty and len(df) >= 40:
            df = df.tail(40)
            close_prices = df['收盘'].astype(float).values
            
            # --- Ernie Chan Half-Life 算法 ---
            ts = close_prices
            diff = np.diff(ts)
            # 对 ts[:-1] 和 diff 做线性回归，求斜率 rho
            slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(ts[:-1], diff)
            
            # 如果 slope < 0，说明存在均值回归特性，可以计算半衰期
            if slope < -0.01: 
                half_life = int(-math.log(2) / slope)
                # 限制半衰期在 5 到 20 之间，避免极值导致均线失效
                half_life = max(5, min(20, half_life))
            else:
                # 如果 slope >= 0 或者趋近于0，说明呈现极强趋势性（非平稳），退化为默认的趋势追踪窗口 10
                half_life = 10
                
            # print(f"[{code}] Computed Half-Life: {half_life} days (slope: {slope:.4f})")
            
            # 根据半衰期动态提取数据
            close_series = pd.Series(close_prices)
            high_prices = df['最高'].astype(float)
            low_prices = df['最低'].astype(float)
            
            sma_dynamic = close_series.tail(half_life).mean()
            
            tr1 = high_prices - low_prices
            tr2 = (high_prices - df['收盘'].astype(float).shift(1)).abs()
            tr3 = (low_prices - df['收盘'].astype(float).shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.tail(half_life).mean()
            
            stop_loss = round(sma_dynamic - 1.2 * atr, 2)
            take_profit = round(close_prices[-1] + 2.5 * atr, 2)
            return stop_loss, take_profit
    except Exception as e:
        logging.error(f"Error calculating Half-Life SL/TP for {code}: {e}")
    return None, None


@sim_trade_bp.route('/watchlist', methods=['GET'])
def get_watchlist():
    # 动态生成值得关注的潜力股池
    watchlist = []
    
    # 1. 获取机器学习 Top 预测
    try:
        import os
        import json
        from api.model_service import PREDICTIONS_FILE_V19 as PREDICTIONS_FILE
        if os.path.exists(PREDICTIONS_FILE):
            with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
                preds = json.load(f)
                
            sorted_preds = sorted([
                {"code": k, **v} for k, v in preds.items()
                if v.get("predicted_return", 0) > 0 and 
                   not any(x in v.get("name", "").upper() for x in ["ST", "*ST", "退"])
            ], key=lambda x: x.get("predicted_return", 0), reverse=True)
            
            from data.market_data import StockDataAPI
            api_client = StockDataAPI()
            for p in sorted_preds[:3]:
                # 增加深度逻辑描述
                logic_detail = f"【入选逻辑】：底层 V19 (LightGBM 5模型集成) 发出强看涨信号。<br>【数据支撑】：盘前特征计算其胜率高达 {p.get('up_probability',50):.1f}%，预期绝对收益 {p.get('predicted_return',0)*100:.1f}%。<br>【风控判定】：已通过基础 ST 与退市股过滤黑名单，量价齐升概率大。"
                
                change_pct = 0.0
                try:
                    rt_data = api_client.get_realtime_data(p["code"])
                    if rt_data and "change_percent" in rt_data:
                        change_pct = rt_data["change_percent"]
                except Exception:
                    pass

                watchlist.append({
                    "code": p["code"],
                    "name": p.get("name", p["code"]),
                    "reason": logic_detail,
                    "type": "ml",
                    "change_pct": change_pct
                })
    except Exception as e:
        logging.error(f"Error getting ML watchlist: {e}")

    # 2. 获取事件驱动/板块龙头
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
                
                if 2.0 < leader_change < 19.5 and not any(x in leader_name.upper() for x in ["ST", "*ST", "退"]):
                    if not any(w["code"] == pure_code for w in watchlist):
                        logic_detail = f"【入选逻辑】：事件驱动/游资热点打板模型触发。<br>【动能追踪】：今日资金大幅流入 [{sector_name}] 板块，且该股作为日内龙头已领涨 {leader_change:.1f}%。<br>【交易博弈】：由于其涨幅处于 2% - 19.5% 之间，未彻底封死涨停，存在上车博弈涨停溢价的机会。"
                        watchlist.append({
                            "code": pure_code,
                            "name": leader_name,
                            "reason": logic_detail,
                            "type": "event",
                            "change_pct": leader_change
                        })
    except Exception as e:
        pass
        
    return jsonify({"status": "success", "data": watchlist})

@sim_trade_bp.route('/info', methods=['GET'])
def get_info():
    account = load_account()
    
    # 获取持仓的最新实时价格，以计算最新净资产
    if account["holdings"]:
        try:
            from data.market_data import StockDataAPI
            api_client = StockDataAPI()
            for code in list(account["holdings"].keys()):
                rt_data = api_client.get_realtime_data(code)
                if rt_data and rt_data.get("current", 0) > 0:
                    account["holdings"][code]["current_price"] = rt_data["current"]
                    # 如果持仓里没名字，补一下
                    if not account["holdings"][code].get("name") or account["holdings"][code]["name"] == code:
                        account["holdings"][code]["name"] = rt_data.get("name", code)
                else:
                    # 如果获取失败或价格为0，保留上一次的价格，或者使用成本价
                    if "current_price" not in account["holdings"][code]:
                        account["holdings"][code]["current_price"] = account["holdings"][code]["cost_price"]
        except Exception as e:
            logging.error(f"Error updating prices in info: {e}")

    total_asset = account["cash"]
    need_save = False
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for code, pos in account["holdings"].items():
        total_asset += pos["vol"] * pos.get("current_price", pos["cost_price"])
        
        # 补充计算止盈止损以便前端展示 (引入文件缓存机制，防止频繁调用akshare导致IP被封与闪烁)
        if pos.get("sl_tp_date") != today_str or "stop_loss" not in pos:
            sl, tp = calc_dynamic_sl_tp(code)
            if sl is not None: 
                pos["stop_loss"] = float(sl)
                need_save = True
            if tp is not None: 
                pos["take_profit"] = float(tp)
                need_save = True
            pos["sl_tp_date"] = today_str
            need_save = True
            
    if need_save:
        save_account(account)
    
    account["total_asset"] = float(total_asset)
    return jsonify({"status": "success", "data": account})

@sim_trade_bp.route('/logs', methods=['GET'])
def get_logs():
    date_filter = request.args.get('date') # YYYY-MM-DD
    account = load_account()
    logs = account.get("logs", [])
    holdings = account.get("holdings", {})
    now = datetime.now()
    
    # 获取实时价格以计算浮动盈亏
    prices = {}
    if holdings:
        try:
            from data.market_data import StockDataAPI
            api_client = StockDataAPI()
            for code in holdings.keys():
                rt = api_client.get_realtime_data(code)
                if rt and "current" in rt:
                    prices[code] = rt["current"]
        except:
            pass

    # 动态增强 Buy 日志的实时状态
    display_logs = []
    for l in logs:
        new_log = l.copy()
        # 如果是买入日志，且该股票目前还在持仓中，计算实时浮盈和持仓时长
        if l['action'] == 'buy' and l['code'] in holdings:
            code = l['code']
            pos = holdings[code]
            
            # 实时时长
            try:
                buy_time = datetime.strptime(l['time'], "%Y-%m-%d %H:%M:%S")
                delta = now - buy_time
                if delta.days > 0:
                    new_log['duration'] = f"{delta.days}天{delta.seconds//3600}时"
                elif delta.seconds >= 3600:
                    new_log['duration'] = f"{delta.seconds//3600}小时"
                else:
                    new_log['duration'] = f"{delta.seconds//60}分钟"
            except:
                pass
            
            # 实时浮盈 (浮动盈亏 = 当前市值 - 买入成本 - 预估卖出手续费)
            if code in prices:
                current_price = prices[code]
                amount = current_price * l['vol']
                # 预估卖出手续费
                est_fee = max(amount * 0.00025, 5.0) + (amount * 0.00001) + (amount * 0.0005)
                # 浮盈 = 当前价值 - (买入成交额 + 买入手续费) - 预估卖出手续费
                new_log['pnl'] = (amount - est_fee) - (l['amount'] + l.get('fee', 0))
        
        display_logs.append(new_log)

    if date_filter:
        display_logs = [l for l in display_logs if l['time'].startswith(date_filter)]
    
    return jsonify({"status": "success", "data": display_logs})

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
    
    # 兼容非 JSON 请求或空请求体
    data = request.get_json(silent=True) or {}
    is_manual = data.get("force", False)

    # 1. 严格判断是否在交易时间内 (09:30-11:30, 13:00-15:00)
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
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

    # --- 【新增空仓信号逻辑】 ---
    # 1. 绝对收益阈值：即便排名前10%，如果预测收益为负，说明市场整体极差，不买入。
    top_codes = [p["code"] for p in sorted_preds if p["pred"] >= p90_val and p["pred"] > 0]
    
    # --- 新增: 早盘禁追高与全天仓位分散 ---
    today_buys = [log for log in account.get("logs", []) if log["action"] == "buy" and log["time"].startswith(today_str)]
    can_buy_today = (len(today_buys) < 1)  # 每天最多建仓1只
    is_morning_danger = "09:30" <= time_str <= "09:45"
    
    if not can_buy_today or is_morning_danger:
        if is_morning_danger:
            logging.info("Morning danger period (09:30-09:45). Blocked all buying to avoid traps.")
        elif not can_buy_today:
            logging.info("Daily buy limit reached (1/day). Time-distributed position building active.")
        top_codes = []
        
    # 2. 市场整体环境评估 (Market Sentiment)
    # 计算全池平均预测收益，如果均值为负，视为大盘风险期
    avg_pred = sum([p["pred"] for p in sorted_preds]) / n
    is_market_risky = avg_pred < -0.01  # 均值亏损超过1%视为极高风险
    
    if is_market_risky:
        logging.warning(f"Market Sentiment Risk detected (Avg Pred: {avg_pred:.4f}). AI will tilt towards cash (Empty Position).")
        top_codes = [] # 风险期停止一切新开仓动作
    
    # 2.5 接入【新闻与国家大事驱动】逻辑
    event_driven_info = {}
    if not is_market_risky and not is_morning_danger and can_buy_today: # 安全期且在允许买入时间内才追热点
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
    prices = {} # 存储深度行情
    try:
        from data.market_data import StockDataAPI
        api_client = StockDataAPI()
        for code in codes_to_fetch:
            rt_data = api_client.get_realtime_data(code)
            if rt_data and "current" in rt_data:
                prices[code] = {
                    "current": rt_data["current"],
                    "high": rt_data.get("high", rt_data["current"]),
                    "low": rt_data.get("low", rt_data["current"]),
                    "yesterday_close": rt_data.get("yesterday_close", 0),
                    "name": rt_data.get("name", code),
                    "ask1": rt_data.get("ask1"),
                    "bid1": rt_data.get("bid1"),
                    "volume": rt_data.get("volume", 0),
                    "amount": rt_data.get("amount", 0)
                }
                if prices[code]["volume"] > 0:
                    prices[code]["vwap"] = prices[code]["amount"] / prices[code]["volume"]
                else:
                    prices[code]["vwap"] = prices[code]["current"]
    except Exception as e:
        logging.error(f"Error fetching prices for sim: {e}")

    actions_taken = []

    # 4. 卖出逻辑
    codes_to_sell = []
    
    # 获取当前热门板块（用于校验事件驱动标的是否过期）
    current_hot_codes = []
    try:
        import akshare as ak
        sector_df = ak.stock_sector_spot(indicator='新浪行业')
        if not sector_df.empty:
            current_hot_df = sector_df.sort_values(by='涨跌幅', ascending=False).head(5)
            for c in current_hot_df['股票代码'].tolist():
                current_hot_codes.append(c[2:] if c[:2] in ['sh', 'sz', 'bj'] else c)
    except:
        pass

    for code, pos in account["holdings"].items():
        if code in prices:
            pos["current_price"] = prices[code]["current"]
        
        # --- A股 T+1 规则：今天买的不能今天卖 ---
        if pos.get("buy_date") == today_str and not is_manual:
            continue

        # --- 【新增核心规则】涨停不卖：强势股封板必有溢价，封死涨停时绝不抛售 ---
        is_up_limited, _ = check_trade_limit(
            code, prices[code]["current"], prices[code]["yesterday_close"], "buy", 
            ask1_price=prices[code].get("ask1")
        )
        if is_up_limited and not is_manual:
            logging.info(f"Strong hold on {code}: Limit-up detected. Waiting for tomorrow's premium.")
            continue

        pred_val = predictions.get(code, {}).get("predicted_return", 0)
        
        # --- 动态止损与止盈判定 ---
        # 1. 优先读取当天的缓存 (减少 API 请求并防止 None 崩溃)
        if pos.get("sl_tp_date") == today_str and "stop_loss" in pos:
            stop_loss = pos["stop_loss"]
            take_profit = pos.get("take_profit")
        else:
            stop_loss, take_profit = calc_dynamic_sl_tp(code)
            if stop_loss is not None:
                pos["stop_loss"] = float(stop_loss)
                if take_profit is not None:
                    pos["take_profit"] = float(take_profit)
                pos["sl_tp_date"] = today_str
        
        # 2. 极限兜底：如果所有接口全部挂掉且无缓存，使用成本价进行硬性容错，绝不返回 None
        if stop_loss is None:
            stop_loss = pos.get("stop_loss", pos.get("cost_price", 0) * 0.9)
        if take_profit is None:
            take_profit = pos.get("take_profit", pos.get("cost_price", 0) * 1.1)
            
        sl_tp_reason = None
        
        # --- 0. 新增：冲高回落动态止盈 (盘中做T机制) ---
        y_close = prices[code].get("yesterday_close", 0)
        if y_close > 0:
            high_p = prices[code].get("high", pos["current_price"])
            high_pct = (high_p - y_close) / y_close
            
            # 若盘中最高涨幅超过 6%，启动多维回落监控 (防洗盘进阶版)
            if high_pct > 0.06:
                is_20_pct_limit = code.startswith(('30', '68'))
                limit_threshold = 0.18 if is_20_pct_limit else 0.085
                
                # 1. 获取动态分时均价 (VWAP)
                vwap = prices[code].get("vwap", pos["current_price"])
                is_above_vwap = pos["current_price"] > vwap
                
                # 2. 设定基础回撤容忍度 (根据板块特性)
                base_tolerance = 0.04 if is_20_pct_limit else 0.025
                
                # 3. 冲板保护：逼近涨停时，说明处于极强博弈区，容忍度翻倍防烂板洗盘
                if high_pct >= limit_threshold:
                    base_tolerance *= 2.0  # 主板 5%，创业板 8%
                    
                # 4. 分时均价保护：只要价格在分时均线上方运行，说明全天买盘强势，极大可能是洗盘，容忍度再放大1.5倍
                if is_above_vwap:
                    base_tolerance *= 1.5
                    
                # 5. 计算实际回撤，并执行严格的多维判定
                pullback_rate = (high_p - pos["current_price"]) / high_p
                
                # 只有当回撤极大，【并且】跌破了全天分时均价(VWAP)时，才判定主力是真的在出货！
                if pullback_rate > base_tolerance and not is_above_vwap:
                    sl_tp_reason = f"冲高回落破位 (跌穿均价且回撤 {pullback_rate*100:.1f}%)"
                    if code not in codes_to_sell:
                        codes_to_sell.append(code)

        # 1. 触发动态止损 (跌破 10日均线 - 1.2倍ATR)
        if not sl_tp_reason and stop_loss and pos["current_price"] < stop_loss:
            # --- 新增：洗盘甄别器 (长下影线判定) ---
            low_p = prices[code].get("low", pos["current_price"])
            high_p = prices[code].get("high", pos["current_price"])
            shadow_ratio = (pos["current_price"] - low_p) / (high_p - low_p) if high_p > low_p else 0
            
            if shadow_ratio > 0.6:
                logging.info(f"Wash-out detected for {code}: Long lower shadow. Ignoring stop loss temporarily.")
                pos["sl_tp_reason"] = "主力疑似洗盘 (长下影线)，暂缓止损"
            else:
                sl_tp_reason = f"触发动态止损 (当前价跌破支撑线 {stop_loss})"
                if code not in codes_to_sell:
                    codes_to_sell.append(code)
            
        # 2. 触发动态止盈 (高于 收盘价 + 2.5倍ATR 且 V19评分下降，防止强势股被轻易卖飞)
        elif not sl_tp_reason and take_profit and pos["current_price"] > take_profit and pred_val < p30_val:
            sl_tp_reason = f"触发动态止盈 (达到目标区间 {take_profit} 且动能衰退)"
            if code not in codes_to_sell:
                codes_to_sell.append(code)
            
        # 3. 正常轮动卖出
        elif not sl_tp_reason and code in predictions:
            if pred_val < p30_val:
                if code not in codes_to_sell:
                    codes_to_sell.append(code)
        elif not sl_tp_reason:
            # 事件驱动股逻辑：如果不再热门，或者涨幅转负/走弱
            if code not in current_hot_codes:
                if code not in codes_to_sell:
                    codes_to_sell.append(code)
                    
        if sl_tp_reason and code in codes_to_sell:
            pos["sl_tp_reason"] = sl_tp_reason

    for code in codes_to_sell:
        if code not in prices or prices[code]["current"] <= 0:
            continue
            
        # --- 跌停板校验 (加入盘口档位判断) ---
        is_limited, limit_msg = check_trade_limit(code, prices[code]["current"], prices[code]["yesterday_close"], "sell", bid1_price=prices[code].get("bid1"))
        if is_limited:
            logging.info(f"Skip selling {code} due to limit: {limit_msg}")
            continue

        pos = account["holdings"].pop(code)
        sell_price = prices[code]["current"]
        vol = pos["vol"]
        amount = sell_price * vol
        
        # 成本计算 (如果旧持仓没存 buy_fee，设为 0)
        buy_total_cost = pos["cost_price"] * vol + pos.get("buy_fee", 0)
        
        # 东财标准手续费：佣金万2.5(单笔最低5元) + 过户费万0.1 + 印花税万5
        commission = max(amount * 0.00025, 5.0)
        transfer_fee = amount * 0.00001
        stamp_duty = amount * 0.0005
        fee = commission + transfer_fee + stamp_duty
        
        revenue = amount - fee
        account["cash"] += revenue
        
        # 计算盈利与持有时间
        pnl = revenue - buy_total_cost
        duration_str = "未知"
        if "buy_time" in pos:
            try:
                buy_time = datetime.strptime(pos["buy_time"], "%Y-%m-%d %H:%M:%S")
                duration_delta = now - buy_time
                days = duration_delta.days
                hours = duration_delta.seconds // 3600
                duration_str = f"{days}天{hours}时" if days > 0 else f"{hours}小时"
                if days == 0 and hours == 0: duration_str = f"{duration_delta.seconds // 60}分钟"
            except:
                pass

        name = pos.get("name", prices[code]["name"])
        # 修正：根据标的类型记录准确的卖出原因
        if "sl_tp_reason" in pos:
            reason = pos["sl_tp_reason"]
        else:
            reason = "V19评分跌出安全区" if code in predictions else "事件驱动热点退潮/板块轮动"
        log_trade(account, "sell", code, name, sell_price, vol, fee, reason, pnl=pnl, duration=duration_str)
        actions_taken.append(f"卖出 {name}({code})")

    # 5. 买入逻辑 (排名前10%)
    target_pos_value = account.get("total_asset", 100000.0) / MAX_POSITIONS
    
    for code in top_codes:
        if len(account["holdings"]) >= MAX_POSITIONS:
            break
        if code in account["holdings"]:
            continue
        if code not in prices or prices[code]["current"] <= 0:
            continue
            
        # --- 新增全局黑名单：严禁买入 ST、*ST 和退市股 ---
        # 必须综合 event_driven_info, stock_names 和 prices 中的名字，防止某个数据源遗漏 ST 标识
        stock_name = event_driven_info.get(code, {}).get("name", stock_names.get(code, prices[code].get("name", "")))
        if any(x in stock_name.upper() for x in ["ST", "*ST", "退"]):
            logging.info(f"Blacklist filter blocked buying {stock_name} ({code})")
            continue
            
        # --- 新增：涨停板校验 (加入盘口档位判断，最准) ---
        is_limited, limit_msg = check_trade_limit(code, prices[code]["current"], prices[code]["yesterday_close"], "buy", ask1_price=prices[code].get("ask1"))
        if is_limited:
            logging.info(f"Skip buying {code} due to limit: {limit_msg}")
            continue

        buy_price = prices[code]["current"]
        
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
                    # 优先取实时接口返回的名字，如果失败才查本地
                    name = prices[code].get("name") or stock_names.get(code, code)
                    reason = f"V19强共振买入信号"
                
                account["holdings"][code] = {
                    "name": name,
                    "vol": vol,
                    "cost_price": buy_price,
                    "current_price": buy_price,
                    "buy_date": today_str,
                    "buy_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "buy_fee": fee
                }
                log_trade(account, "buy", code, name, buy_price, vol, fee, reason)
                actions_taken.append(f"买入 {name}({code})")

    save_account(account)
    
    msg = f"已执行 {len(actions_taken)} 项交易动作。" if actions_taken else "市场环境稳健，维持当前持仓。"
    if is_market_risky:
        msg = "检测到全市场系统性风险，AI 已执行空仓避险保护。" if not account["holdings"] else "检测到市场风险，停止新开仓，执行防御性策略。"

    return jsonify({
        "status": "success", 
        "actions": actions_taken, 
        "msg": msg
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
        
    # 提取日志(最近10条)
    logs_str = "最近无交易记录"
    if account["logs"]:
        logs_str = ""
        for log in account["logs"][:10]:
            logs_str += f"- [{log['time']}] {log['action']} {log['name']} {log['vol']}股 @ {log['price']}元 (原因: {log['reason']})\n"
            
    # 获取热点
    hot_sectors_str = "暂无数据"
    try:
        import akshare as ak
        sector_df = ak.stock_sector_spot(indicator='新浪行业')
        if not sector_df.empty:
            hot_sectors = sector_df.sort_values(by='涨跌幅', ascending=False).head(5)
            hot_sectors_str = ""
            for _, row in hot_sectors.iterrows():
                hot_sectors_str += f"- {row['板块']}: 涨跌幅 {row['涨跌幅']}%, 领涨股 {row['股票名称']}({row['股票代码']})\n"
    except Exception as e:
        pass
        
    # 调用 LLM
    from api.llm_assistant import generate_ai_analysis
    report_html = generate_ai_analysis(portfolio, logs_str, hot_sectors_str)
    
    return jsonify({"status": "success", "html": report_html})