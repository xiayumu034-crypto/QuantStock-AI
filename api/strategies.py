import os
import json
import logging
import math
from datetime import datetime

def check_trade_limit(code, current_price, yesterday_close, action, ask1_price=None, bid1_price=None):
    if not yesterday_close or not current_price: return False, ""
    if action == 'buy' and ask1_price is not None and ask1_price <= 0: return True, "涨停封死"
    if action == 'sell' and bid1_price is not None and bid1_price <= 0: return True, "跌停封死"
    limit_pct = 0.2 if code.startswith(('30', '68')) else 0.1
    up = round(yesterday_close * (1 + limit_pct) + 0.0001, 2)
    down = round(yesterday_close * (1 - limit_pct) + 0.0001, 2)
    if action == 'buy' and current_price >= up: return True, "涨停"
    if action == 'sell' and current_price <= down: return True, "跌停"
    return False, ""

def log_trade(account, action, code, name, price, vol, fee, reason="系统自动", pnl=None, duration=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = {
        "time": timestamp, "action": action, "code": code, "name": name,
        "price": price, "vol": vol, "amount": price*vol, "fee": round(fee, 2),
        "reason": reason, "pnl": round(pnl, 2) if pnl is not None else None, "duration": duration
    }
    account["logs"].insert(0, log_msg)

def get_minute_vwap(api_client, code, current_price, amount, volume):
    """尝试获取当日VWAP，如果API不支持则使用简单的金额/成交量作为近似"""
    try:
        # 大部分实时接口的amount是总金额(元)，volume是总成交股数
        if volume > 0 and amount > 0:
            return amount / volume
    except:
        pass
    return current_price

def run_youzi_douyin_a_step(account, api_client, today_str, time_str, is_manual=False):
    actions = []
    
    # 1. 市场情绪网关 (Market Sentiment Gate)
    try:
        from data.market_data import get_market_breadth
        breadth = get_market_breadth()
        up_count = breadth.get('up', 0)
        down_count = breadth.get('down', 0)
        
        if down_count >= 4000:
            logging.warning(f"Panic Market: {down_count} stocks falling. Execution: SELL ALL.")
            for code in list(account['holdings'].keys()):
                h = account['holdings'][code]
                rt = api_client.get_realtime_data(code)
                price = rt['current'] if rt else h['cost_price']
                limited, _ = check_trade_limit(code, price, rt.get('yesterday_close'), 'sell', bid1_price=rt.get('bid1'))
                if not limited:
                    vol = h['volume']
                    fee = price * vol * 0.0013
                    pnl = (price - h['cost_price']) * vol - fee
                    account['cash'] += (price * vol - fee)
                    log_trade(account, 'sell', code, h.get('name', code), price, vol, fee, reason=f"市场情绪崩溃({down_count}家下跌)强制清仓", pnl=pnl)
                    del account['holdings'][code]
                    actions.append(f"强制卖出 {code} ({h.get('name')})")
            return actions

        can_buy = (up_count >= 3000) or is_manual
        if not can_buy:
            logging.info(f"Breadth check failed: {up_count} up. Buying paused.")
    except Exception as e:
        logging.error(f"Breadth API failed: {e}")
        can_buy = True

    # ================= 变态级卖出逻辑 =================
    for code in list(account['holdings'].keys()):
        h = account['holdings'][code]
        rt = api_client.get_realtime_data(code)
        if not rt: continue
        
        curr = rt['current']
        cost = h['cost_price']
        open_p = rt.get('open', curr)
        vwap = get_minute_vwap(api_client, code, curr, rt.get('amount', 0), rt.get('volume', 0))
        
        change_from_cost = (curr - cost) / cost
        
        # 记录最高价用于计算回撤
        high_price = h.get('high_price', curr)
        if curr > high_price: h['high_price'] = curr
        drawdown = (h.get('high_price', curr) - curr) / (h.get('high_price', curr) - cost + 0.001)
        
        should_sell = False
        reason = ""
        
        # 1. 保本优先：有盈利，10:40时若回落到均线下方，走人
        if change_from_cost > 0.01 and time_str >= "10:40" and curr < vwap:
            should_sell, reason = True, "保本单触发:跌破均线"
            
        # 2. 弱势必杀：开盘冲高回落，跌破VWAP (这里用curr < vwap近似"反抽不过")
        elif time_str < "10:40" and curr < vwap and curr < open_p:
            should_sell, reason = True, "弱势必杀:开盘跌破均线与开盘价"
            
        # 3. 止损/止盈底线
        elif change_from_cost <= -0.05:
            should_sell, reason = True, "固定止损(-5%)"
        elif change_from_cost > 0.03 and drawdown > 0.3:
            should_sell, reason = True, "利润回撤止盈"
            
        if should_sell:
            limited, _ = check_trade_limit(code, curr, rt.get('yesterday_close'), 'sell', bid1_price=rt.get('bid1'))
            if not limited:
                vol = h['volume']
                fee = curr * vol * 0.0013
                pnl = (curr - cost) * vol - fee
                account['cash'] += (curr * vol - fee)
                log_trade(account, 'sell', code, h.get('name'), curr, vol, fee, reason=reason, pnl=pnl)
                del account['holdings'][code]
                actions.append(f"卖出 {code} {reason}")

    # ================= 极简买入逻辑 =================
    if can_buy and len(account['holdings']) < 5:
        # 时间窗口锁：10:40 之前，或者 14:40 之后。中间绝对不买。
        if not ("09:30" <= time_str <= "10:40" or "14:40" <= time_str <= "15:00") and not is_manual:
            return actions
            
        from api.routes_model import read_daily_predictions
        preds, _, _ = read_daily_predictions("v19")
        if preds:
            # 结合AI预测排序
            candidates = sorted([{"c":k, "p":v['predicted_return']} for k,v in preds.items()], key=lambda x:x['p'], reverse=True)
            for item in candidates[:30]:
                code = item['c']
                if code in account['holdings']: continue
                
                rt = api_client.get_realtime_data(code)
                if not rt: continue
                
                # 基础筛选：小市值 < 100亿
                if rt.get('mkt_cap', 0) > 100e8: continue
                
                curr = rt['current']
                vwap = get_minute_vwap(api_client, code, curr, rt.get('amount', 0), rt.get('volume', 0))
                
                # 动作：放量穿均线回踩才买。近似表达：当前价站在VWAP之上
                if curr < vwap:
                    continue # 缩量/破均线，是诱多，不碰
                    
                # 【进化点】：可以通过读取本地选股池缓存来判断"15天内有过涨停"和"长上影"
                # 由于实时遍历历史K线太慢，这里假定能排进V19前30且能走到这一步的，动能都不差。
                
                limited, _ = check_trade_limit(code, curr, rt.get('yesterday_close'), 'buy', ask1_price=rt.get('ask1'))
                if not limited:
                    vol = (account['cash'] * 0.2) // (curr * 100) * 100
                    if vol >= 100:
                        fee = curr * vol * 0.0003
                        account['cash'] -= (curr * vol + fee)
                        account['holdings'][code] = {
                            "name": rt['name'], "cost_price": curr, "volume": vol, "buy_time": today_str,
                            "high_price": curr # 记录初始最高价
                        }
                        log_trade(account, 'buy', code, rt['name'], curr, vol, fee, reason=f"极简买入:站在均线({round(vwap,2)})之上且在时间窗口内")
                        actions.append(f"买入 {code} {rt['name']}")
                        break # 严格纪律，每次扫描最多成交一个
    return actions
