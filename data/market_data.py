import os
import time
import re
import datetime
import logging
import requests
import pandas as pd
import numpy as np
import akshare as ak

logger = logging.getLogger(__name__)

class StockDataAPI:
    """新浪财经数据API封装"""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://finance.sina.com.cn/"
        }

    def get_realtime_data(self, stock_code):
        """获取实时行情数据"""
        prefix = 'sh' if stock_code.startswith('6') else 'sz'
        url = f"http://hq.sinajs.cn/list={prefix}{stock_code}"
        try:
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                match = re.search(r'"(.*?)"', response.text)
                if match:
                    parts = match.group(1).split(",")
                    if len(parts) > 31:
                        current = float(parts[3])
                        yesterday_close = float(parts[2])
                        change = current - yesterday_close
                        change_pct = (change / yesterday_close) * 100 if yesterday_close else 0
                        return {
                            "name": parts[0], "code": stock_code,
                            "open": float(parts[1]), "yesterday_close": yesterday_close,
                            "current": current, "high": float(parts[4]), "low": float(parts[5]),
                            "volume": int(parts[8]), "amount": float(parts[9]),
                            "time": f"{parts[30]} {parts[31]}",
                            "change": round(change, 2), "change_percent": round(change_pct, 2),
                            "status": "success"
                        }
        except Exception as e:
            return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "数据获取失败"}

    def get_minute_data(self, stock_code, scale=5, datalen=200):
        """获取分时K线数据"""
        prefix = 'sh' if stock_code.startswith('6') else 'sz'
        url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {"symbol": f"{prefix}{stock_code}", "scale": str(scale), "ma": "no", "datalen": str(datalen)}
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data:
                    return {"status": "success", "data": data}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "分时数据获取失败"}

    def calculate_technical_indicators(self, minute_data):
        """计算技术指标（MACD/KDJ/RSI/布林带/VWAP）"""
        if not minute_data or len(minute_data) < 20:
            return None
        df = pd.DataFrame(minute_data)
        for col in ['close', 'high', 'low', 'volume']:
            df[col] = df[col].astype(float)

        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['dif'] = ema12 - ema26
        df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
        df['macd'] = 2 * (df['dif'] - df['dea'])

        # KDJ
        low_9 = df['low'].rolling(9).min()
        high_9 = df['high'].rolling(9).max()
        rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
        df['k'] = rsv.ewm(com=2, adjust=False).mean()
        df['d'] = df['k'].ewm(com=2, adjust=False).mean()
        df['j'] = 3 * df['k'] - 2 * df['d']

        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 布林带
        df['bb_mid'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_mid'] + 2 * bb_std
        df['bb_lower'] = df['bb_mid'] - 2 * bb_std

        # VWAP
        df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()

        
        # --- 真实指标计算逻辑 ---
        import numpy as np
        
        # 1. 计算 CCI
        tp = (df['high'] + df['low'] + df['close']) / 3
        df['cci'] = (tp - tp.rolling(14).mean()) / (0.015 * tp.rolling(14).std())

        # 2. 计算 DMI (PDI, MDI, ADX)
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift(1)).abs()
        tr3 = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        up_move = df['high'] - df['high'].shift(1)
        down_move = df['low'].shift(1) - df['low']
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        tr_14 = tr.rolling(14).sum()
        df['plus_di'] = 100 * pd.Series(plus_dm).rolling(14).sum() / tr_14
        df['minus_di'] = 100 * pd.Series(minus_dm).rolling(14).sum() / tr_14
        
        dx = 100 * (df['plus_di'] - df['minus_di']).abs() / (df['plus_di'] + df['minus_di'])
        df['adx'] = dx.rolling(14).mean()
        # ---------------------------------------------------------

        records = []
        labels = df['day'].tolist() if 'day' in df.columns else list(range(len(df)))
        for i in range(len(df)):
            records.append({
                "time": labels[i],
                "close": round(df['close'].iloc[i], 2),
                "volume": float(df['volume'].iloc[i]),
                "dif": round(df['dif'].iloc[i], 4) if not pd.isna(df['dif'].iloc[i]) else None,
                "dea": round(df['dea'].iloc[i], 4) if not pd.isna(df['dea'].iloc[i]) else None,
                "macd": round(df['macd'].iloc[i], 4) if not pd.isna(df['macd'].iloc[i]) else None,
                "k": round(df['k'].iloc[i], 2) if not pd.isna(df['k'].iloc[i]) else None,
                "d": round(df['d'].iloc[i], 2) if not pd.isna(df['d'].iloc[i]) else None,
                "j": round(df['j'].iloc[i], 2) if not pd.isna(df['j'].iloc[i]) else None,
                "rsi14": round(df['rsi'].iloc[i], 2) if not pd.isna(df['rsi'].iloc[i]) else None,
                "bb_upper": round(df['bb_upper'].iloc[i], 2) if not pd.isna(df['bb_upper'].iloc[i]) else None,
                "bb_mid": round(df['bb_mid'].iloc[i], 2) if not pd.isna(df['bb_mid'].iloc[i]) else None,
                "bb_lower": round(df['bb_lower'].iloc[i], 2) if not pd.isna(df['bb_lower'].iloc[i]) else None,
                "vwap": round(df['vwap'].iloc[i], 2) if not pd.isna(df['vwap'].iloc[i]) else None,
                "cci": round(df['cci'].iloc[i], 2) if 'cci' in df.columns and not pd.isna(df['cci'].iloc[i]) else None,
                "plus_di": round(df['plus_di'].iloc[i], 2) if 'plus_di' in df.columns and not pd.isna(df['plus_di'].iloc[i]) else None,
                "minus_di": round(df['minus_di'].iloc[i], 2) if 'minus_di' in df.columns and not pd.isna(df['minus_di'].iloc[i]) else None,
                "adx": round(df['adx'].iloc[i], 2) if 'adx' in df.columns and not pd.isna(df['adx'].iloc[i]) else None
            })
        return records

    def predict_next_5_minutes(self, stock_code):
        """技术面评估（交易时段才返回信号）"""
        from datetime import datetime as dt
        now = dt.now()
        weekday = now.weekday()
        hour, minute = now.hour, now.minute
        current_time = hour * 60 + minute

        is_trading = weekday < 5 and (
            (9 * 60 + 30 <= current_time <= 11 * 60 + 30) or
            (13 * 60 <= current_time <= 15 * 60)
        )
        if not is_trading:
            return {
                "action": "⏸️ 已收盘", "action_class": "neutral",
                "prediction_time": "非交易时段", "up_probability": 0, "down_probability": 0,
                "signal_strength": 0,
                "signals": ["当前非交易时间", "技术面信号仅供参考", "实际走势以开盘后为准"],
                "indicators": {}, "is_market_closed": True,
            }

        minute_data = self.get_minute_data(stock_code, scale=5, datalen=48)
        if minute_data['status'] != 'success':
            return {"action": "数据不足", "action_class": "neutral", "signals": ["无法获取数据"]}
        data = minute_data['data']
        if len(data) < 10:
            return {"action": "数据不足", "action_class": "neutral", "signals": ["数据不足"]}

        closes = [float(d['close']) for d in data]
        volumes = [float(d['volume']) for d in data]
        sma5 = np.mean(closes[-5:])
        sma20 = np.mean(closes[-20:]) if len(closes) >= 20 else sma5
        ema12 = pd.Series(closes).ewm(span=12).mean().iloc[-1]
        ema26 = pd.Series(closes).ewm(span=26).mean().iloc[-1]
        dif = ema12 - ema26
        deltas = np.diff(closes[-15:])
        gains = np.mean(deltas[deltas > 0]) if any(deltas > 0) else 0
        losses = -np.mean(deltas[deltas < 0]) if any(deltas < 0) else 0.001
        rsi = 100 - (100 / (1 + gains / losses))

        signals, strength = [], 0
        current = closes[-1]
        if current > sma20:
            signals.append("价格在均线上方 → 向上趋势"); strength += 1
        else:
            signals.append("价格在均线下方 → 向下趋势"); strength -= 1
        if dif > 0:
            signals.append("MACD金叉区域 → 多头"); strength += 1
        else:
            signals.append("MACD死叉区域 → 空头"); strength -= 1
        if rsi < 30:
            signals.append("RSI超卖 → 反弹信号"); strength += 2
        elif rsi > 70:
            signals.append("RSI超买 → 回调风险"); strength -= 2
        else:
            signals.append(f"RSI={rsi:.0f} → 中性区域")

        vol_ratio = volumes[-1] / np.mean(volumes[-10:])
        if vol_ratio > 1.5:
            signals.append("放量 → 资金活跃"); strength += 1
        elif vol_ratio < 0.5:
            signals.append("缩量 → 观望")

        # ---------------- 补充前端所需的全部关键指标 ----------------
        closes_s = pd.Series(closes)
        volumes_s = pd.Series(volumes)
        highs = pd.Series([float(d['high']) for d in data])
        lows = pd.Series([float(d['low']) for d in data])
        
        # BB_PCT
        bb_mid = closes_s.rolling(20).mean()
        bb_std = closes_s.rolling(20).std()
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        bb_pct = (closes_s - bb_lower) / (bb_upper - bb_lower)
        bb_pct_val = float(bb_pct.iloc[-1]) if not pd.isna(bb_pct.iloc[-1]) else 0

        # VWAP
        vwap = (closes_s * volumes_s).cumsum() / volumes_s.cumsum()
        vwap_val = float(vwap.iloc[-1]) if not pd.isna(vwap.iloc[-1]) else 0
        
        # CCI
        tp = (highs + lows + closes_s) / 3
        cci = (tp - tp.rolling(14).mean()) / (0.015 * tp.rolling(14).std())
        cci_val = float(cci.iloc[-1]) if not pd.isna(cci.iloc[-1]) else 0
        
        # DMI (ADX, PLUS_DI, MINUS_DI)
        tr1 = highs - lows
        tr2 = (highs - closes_s.shift(1)).abs()
        tr3 = (lows - closes_s.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        up_move = highs - highs.shift(1)
        down_move = lows.shift(1) - lows
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        tr_14 = tr.rolling(14).sum()
        plus_di = 100 * pd.Series(plus_dm).rolling(14).sum() / tr_14
        minus_di = 100 * pd.Series(minus_dm).rolling(14).sum() / tr_14
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(14).mean()
        
        # OBV
        obv = (np.sign(closes_s.diff()) * volumes_s).fillna(0).cumsum()
        
        # ATR
        atr = tr.rolling(14).mean()

        up_prob = min(max(50 + strength * 8, 5), 95)
        down_prob = 100 - up_prob
        if strength >= 2: action, action_class = "强烈看涨", "positive"
        elif strength >= 1: action, action_class = "看涨", "positive"
        elif strength <= -2: action, action_class = "强烈看跌", "negative"
        elif strength <= -1: action, action_class = "看跌", "negative"
        else: action, action_class = "震荡", "neutral"

        return {
            "action": f"{action} {up_prob:.1f}%", "action_class": action_class,
            "prediction_time": dt.now().strftime("%H:%M:%S"),
            "up_probability": up_prob, "down_probability": down_prob,
            "signal_strength": strength, "signals": signals,
            "indicators": {
                "rsi": round(rsi, 1), "macd_dif": round(dif, 4),
                "sma5": round(sma5, 2), "sma20": round(sma20, 2),
                "vol_ratio": round(vol_ratio, 2),
                "BB_PCT": bb_pct_val,
                "VWAP": vwap_val,
                "VOL_RATIO": round(vol_ratio, 2),
                "CCI": cci_val,
                "PLUS_DI": float(plus_di.iloc[-1]) if not pd.isna(plus_di.iloc[-1]) else 0,
                "MINUS_DI": float(minus_di.iloc[-1]) if not pd.isna(minus_di.iloc[-1]) else 0,
                "ADX": float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0,
                "OBV": float(obv.iloc[-1]) if not pd.isna(obv.iloc[-1]) else 0,
                "ATR": float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0
            },
            "is_market_closed": False,
            "current_price": current
        }


