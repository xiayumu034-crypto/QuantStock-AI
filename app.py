#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask股票监控后端 v2.1
新增：ML多因子预测模型集成
"""

from flask import Flask, jsonify, request, render_template
import requests
import re
import json
import os
import pickle
from datetime import datetime
import pandas as pd
import numpy as np

app = Flask(__name__)

# 加载ML模型
MODEL_PATH = "model_output/lgb_model_v16.pkl"
FEATURE_COLS_PATH = "model_output/features_v16.json"

ml_model = None
ml_features = None

def load_ml_model():
    global ml_model, ml_features
    try:
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, 'rb') as f:
                model_data = pickle.load(f)
            
            # 兼容v15和v16格式
            if isinstance(model_data, dict) and 'models' in model_data:
                ml_model = model_data  # v16格式: dict with 'models' list
                print(f"[ML] v16集成模型加载成功 ({model_data['n_models']}个模型)")
            else:
                ml_model = model_data  # v15格式: 单个模型
                print("[ML] v15模型加载成功")
            
            with open(FEATURE_COLS_PATH, 'r') as f:
                ml_features = json.load(f)
            print(f"[ML] 特征加载成功: {len(ml_features)}个")
            return True
    except Exception as e:
        print(f"[ML] 模型加载失败: {e}")
    return False


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

    def get_minute_data(self, stock_code, scale=5, datalen=48):
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

        return {
            "labels": df['day'].tolist() if 'day' in df.columns else list(range(len(df))),
            "close": df['close'].round(2).tolist(),
            "volume": df['volume'].tolist(),
            "macd": {"dif": df['dif'].round(4).tolist(), "dea": df['dea'].round(4).tolist(), "macd": df['macd'].round(4).tolist()},
            "kdj": {"k": df['k'].round(2).tolist(), "d": df['d'].round(2).tolist(), "j": df['j'].round(2).tolist()},
            "rsi": df['rsi'].round(2).tolist(),
            "bollinger": {"upper": df['bb_upper'].round(2).tolist(), "mid": df['bb_mid'].round(2).tolist(), "lower": df['bb_lower'].round(2).tolist()},
            "vwap": df['vwap'].round(2).tolist(),
        }

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

        up_prob = min(max(50 + strength * 8, 5), 95)
        down_prob = 100 - up_prob
        if strength >= 2: action, action_class = "强烈看涨", "positive"
        elif strength >= 1: action, action_class = "看涨", "positive"
        elif strength <= -2: action, action_class = "强烈看跌", "negative"
        elif strength <= -1: action, action_class = "看跌", "negative"
        else: action, action_class = "震荡", "neutral"

        return {
            "action": f"{action} {up_prob:.1f}%", "action_class": action_class,
            "prediction_time": datetime.now().strftime("%H:%M:%S"),
            "up_probability": up_prob, "down_probability": down_prob,
            "signal_strength": strength, "signals": signals,
            "indicators": {"rsi": round(rsi, 1), "macd_dif": round(dif, 4),
                           "sma5": round(sma5, 2), "sma20": round(sma20, 2),
                           "vol_ratio": round(vol_ratio, 2)},
            "is_market_closed": False,
        }


stock_api = StockDataAPI()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stocks')
def get_stock_list():
    stocks = [
        {"code": "300201", "name": "海伦哲"},
        {"code": "000001", "name": "平安银行"},
        {"code": "600519", "name": "贵州茅台"},
        {"code": "300750", "name": "宁德时代"},
        {"code": "002594", "name": "比亚迪"}
    ]
    return jsonify({"status": "success", "data": stocks})

@app.route('/api/realtime/<stock_code>')
def get_realtime(stock_code):
    return jsonify(stock_api.get_realtime_data(stock_code))

@app.route('/api/minute/<stock_code>')
def get_minute(stock_code):
    scale = request.args.get('scale', 5, type=int)
    datalen = request.args.get('datalen', 48, type=int)
    return jsonify(stock_api.get_minute_data(stock_code, scale, datalen))

@app.route('/api/technical/<stock_code>')
def get_technical(stock_code):
    minute_data = stock_api.get_minute_data(stock_code, scale=5, datalen=100)
    if minute_data['status'] == 'success':
        technical_data = stock_api.calculate_technical_indicators(minute_data['data'])
        if technical_data:
            return jsonify({"status": "success", "data": technical_data})
    return jsonify({"status": "error", "message": "技术指标计算失败"})

@app.route('/api/predict/<stock_code>')
def get_prediction(stock_code):
    return jsonify(stock_api.predict_next_5_minutes(stock_code))

@app.route('/api/ml_predict/<stock_code>')
def get_ml_prediction(stock_code):
    """单股票ML预测"""
    if ml_model is None:
        return jsonify({"status": "error", "message": "ML模型未加载"})
    try:
        market = "sh" if stock_code.startswith('6') else "sz"
        url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {"symbol": f"{market}{stock_code}", "scale": "1680", "ma": "no", "datalen": "200"}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        if not data or len(data) == 0:
            return jsonify({"status": "error", "message": "日K线数据获取失败"})

        rows = [{'日期': item['day'], '开盘': float(item['open']), '收盘': float(item['close']),
                 '最高': float(item['high']), '最低': float(item['low']), '成交量': float(item['volume'])}
                for item in data]
        df = pd.DataFrame(rows).sort_values('日期').reset_index(drop=True)
        if len(df) < 60:
            return jsonify({"status": "error", "message": "数据不足（需要至少60天）"})

        name_map = {'300201': '海伦哲', '000001': '平安银行', '600519': '贵州茅台',
                    '300750': '宁德时代', '002594': '比亚迪'}
        df['code'] = stock_code
        df['name'] = name_map.get(stock_code, stock_code)

        # 与 ml_predict_all 相同的特征计算逻辑
        c, h, l, o, v = [df[col].astype(float) for col in ['收盘','最高','最低','开盘','成交量']]
        ret1 = c.pct_change(1)
        df['mom_5d'] = c.pct_change(5); df['mom_10d'] = c.pct_change(10)
        df['mom_20d'] = c.pct_change(20); df['mom_60d'] = c.pct_change(60)
        df['mom_accel'] = df['mom_5d'] - df['mom_20d']
        sma20 = c.rolling(20).mean(); sma60 = c.rolling(60).mean()
        df['dist_sma20'] = (c - sma20) / (sma20 + 1e-10)
        df['dist_sma60'] = (c - sma60) / (sma60 + 1e-10)
        df['vol_5d'] = ret1.rolling(5).std(); df['vol_20d'] = ret1.rolling(20).std()
        df['vol_ratio'] = df['vol_5d'] / (df['vol_20d'] + 1e-10)
        vol_ma5 = v.rolling(5).mean(); vol_ma20 = v.rolling(20).mean()
        df['turnover_ratio'] = vol_ma5 / (vol_ma20 + 1e-10)
        df['vol_price_corr'] = c.rolling(10).corr(v)
        ema12 = c.ewm(span=12).mean(); ema26 = c.ewm(span=26).mean()
        dif = ema12 - ema26; dea = dif.ewm(span=9).mean()
        df['macd_hist'] = 2 * (dif - dea) / (c + 1e-10)
        delta = c.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi_14'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
        bb_std = c.rolling(20).std()
        df['bb_pos'] = (c - sma20) / (2 * bb_std + 1e-10)
        tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
        df['atr_ratio'] = tr.rolling(14).mean() / (c + 1e-10)
        df['body_ratio'] = abs(c - o) / (h - l + 1e-10)
        df['ret_1d'] = ret1; df['ret_3d'] = c.pct_change(3)
        df['high_low_range'] = (h - l) / (c + 1e-10)
        df['gap'] = (o - c.shift(1)) / (c.shift(1) + 1e-10)
        df['sharpe_20d'] = df['mom_20d'] / (df['vol_20d'] + 1e-10)
        df['decay_mom'] = 0.4 * df['mom_5d'] + 0.3 * c.pct_change(10) + 0.2 * c.pct_change(15) + 0.1 * df['mom_20d']
        rolling_max = c.rolling(20).max()
        df['drawdown_20d'] = (c - rolling_max) / (rolling_max + 1e-10)
        up = (ret1 > 0).astype(int); down = (ret1 < 0).astype(int)
        df['up_streak'] = up.groupby((up != up.shift()).cumsum()).cumsum()
        df['down_streak'] = down.groupby((down != down.shift()).cumsum()).cumsum()
        price_up = (c > c.shift(5)).astype(int); vol_down = (v < v.shift(5)).astype(int)
        df['vol_price_div'] = price_up * vol_down

        raw_features = ['mom_5d','mom_10d','mom_20d','mom_60d','mom_accel',
                        'dist_sma20','dist_sma60','vol_5d','vol_20d','vol_ratio',
                        'turnover_ratio','vol_price_corr','macd_hist','rsi_14',
                        'bb_pos','atr_ratio','body_ratio','ret_1d','ret_3d',
                        'high_low_range','gap','sharpe_20d','decay_mom','drawdown_20d',
                        'up_streak','down_streak','vol_price_div']
        for feat in raw_features:
            rm = df[feat].rolling(60, min_periods=20).mean()
            rs = df[feat].rolling(60, min_periods=20).std()
            df[f'{feat}_cs'] = (df[feat] - rm) / (rs + 1e-10)
        sector_feats = ['mom_20d','rsi_14','turnover_ratio','macd_hist']
        for feat in sector_feats:
            df[f'{feat}_sector'] = 0
        rank_feats = ['mom_5d','mom_20d','mom_60d','rsi_14','turnover_ratio','macd_hist','sharpe_20d']
        for feat in rank_feats:
            df[f'{feat}_rank'] = df[feat].rolling(120, min_periods=30).rank(pct=True)
        for feat in ['mom_20d','rsi_14']:
            df[f'{feat}_sector_rank'] = df[feat].rolling(120, min_periods=30).rank(pct=True)
            df[f'{feat}_revert'] = -df[f'{feat}_cs']

        cs_cols = [f'{f}_cs' for f in raw_features]
        sector_cols = [f'{f}_sector' for f in sector_feats]
        rank_cols = [f'{f}_rank' for f in rank_feats]
        sector_rank_cols = [f'{f}_sector_rank' for f in ['mom_20d','rsi_14']]
        revert_cols = [f'{f}_revert' for f in ['mom_20d','rsi_14']]
        ml_features_list = cs_cols + sector_cols + rank_cols + sector_rank_cols + revert_cols
        for col in ml_features_list:
            df[col] = df[col].replace([np.inf, -np.inf], np.nan).fillna(0)

        latest = df.tail(1).copy()
        X = latest[ml_features_list].values
        if isinstance(ml_model, dict) and 'models' in ml_model:
            predictions = np.mean([m.predict(X) for m in ml_model['models']], axis=0)
        else:
            predictions = ml_model.predict(X)
        pred = float(predictions[0])
        signal = "看涨" if pred > 0.02 else ("看跌" if pred < -0.02 else "中性")
        confidence = "高" if abs(pred) > 0.05 else ("中" if abs(pred) > 0.02 else "低")
        cs_mom = float(latest['mom_5d_cs'].iloc[0]) if 'mom_5d_cs' in latest.columns else 0
        cs_rsi = float(latest['rsi_14_cs'].iloc[0]) if 'rsi_14_cs' in latest.columns else 0

        return jsonify({"status": "success", "data": {
            "code": stock_code, "name": name_map.get(stock_code, stock_code),
            "current_price": float(latest['收盘'].iloc[0]),
            "predicted_return": round(pred * 100, 2), "signal": signal, "confidence": confidence,
            "relative_strength": {"momentum": round(cs_mom, 2), "rsi": round(cs_rsi, 2)},
            "model_version": "v16c",
        }})
    except Exception as e:
        import traceback
        return jsonify({"status": "error", "message": str(e), "trace": traceback.format_exc()})


@app.route('/api/ml_predict_all')
def get_ml_predict_all():
    """v9截面相对强弱批量预测 - 所有股票"""
    if ml_model is None:
        return jsonify({"status": "error", "message": "ML模型未加载"})
    
    try:
        stocks = [
            ("300201","海伦哲"),("000001","平安银行"),("600519","贵州茅台"),
            ("300750","宁德时代"),("002594","比亚迪"),
        ]
        
        # 1. 拉所有股票的日K线（用新浪财经，东方财富被限流）
        all_frames = []
        for code, name in stocks:
            market = "sz" if code.startswith(('0','3')) else "sh"
            url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                "symbol": f"{market}{code}",
                "scale": "1680",
                "ma": "no",
                "datalen": "200",
            }
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r = requests.get(url, params=params, headers=headers, timeout=10)
            data = r.json()
            
            if data and len(data) > 0:
                rows = []
                for item in data:
                    rows.append({
                        '日期': item['day'], '开盘': float(item['open']), '收盘': float(item['close']),
                        '最高': float(item['high']), '最低': float(item['low']), '成交量': float(item['volume']),
                    })
                df = pd.DataFrame(rows)
                df['code'] = code
                df['name'] = name
                # v12: 添加行业分类
                sector_map = {
                    '300201': '制造', '000001': '金融', '600519': '白酒',
                    '300750': '新能源', '002594': '新能源',
                    '600776': '妖股_5G通信', '002432': '妖股_新冠药物',
                }
                df['sector'] = sector_map.get(code, '其他')
                all_frames.append(df)
        
        if not all_frames:
            return jsonify({"status": "error", "message": "数据获取失败"})
        
        # 2. 计算技术面特征
        for i in range(len(all_frames)):
            df = all_frames[i]
            c, h, l, o, v = [df[col].astype(float) for col in ['收盘','最高','最低','开盘','成交量']]
            ret1 = c.pct_change(1)
            
            # v10: 多周期动量
            df['mom_5d'] = c.pct_change(5)
            df['mom_10d'] = c.pct_change(10)
            df['mom_20d'] = c.pct_change(20)
            df['mom_60d'] = c.pct_change(60)
            df['mom_accel'] = df['mom_5d'] - df['mom_20d']
            
            sma20 = c.rolling(20).mean()
            sma60 = c.rolling(60).mean()
            df['dist_sma20'] = (c - sma20) / (sma20 + 1e-10)
            df['dist_sma60'] = (c - sma60) / (sma60 + 1e-10)
            
            df['vol_5d'] = ret1.rolling(5).std()
            df['vol_20d'] = ret1.rolling(20).std()
            df['vol_ratio'] = df['vol_5d'] / (df['vol_20d'] + 1e-10)
            
            vol_ma5 = v.rolling(5).mean()
            vol_ma20 = v.rolling(20).mean()
            df['turnover_ratio'] = vol_ma5 / (vol_ma20 + 1e-10)
            df['vol_price_corr'] = c.rolling(10).corr(v)
            
            ema12 = c.ewm(span=12).mean()
            ema26 = c.ewm(span=26).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9).mean()
            df['macd_hist'] = 2 * (dif - dea) / (c + 1e-10)
            
            delta = c.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['rsi_14'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
            
            bb_std = c.rolling(20).std()
            df['bb_pos'] = (c - sma20) / (2 * bb_std + 1e-10)
            
            tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
            df['atr_ratio'] = tr.rolling(14).mean() / (c + 1e-10)
            
            df['body_ratio'] = abs(c - o) / (h - l + 1e-10)
            
            # v15高级特征
            df['ret_1d'] = ret1
            df['ret_3d'] = c.pct_change(3)
            df['high_low_range'] = (h - l) / (c + 1e-10)
            df['gap'] = (o - c.shift(1)) / (c.shift(1) + 1e-10)
            
            # v15新增
            df['sharpe_20d'] = df['mom_20d'] / (df['vol_20d'] + 1e-10)
            df['decay_mom'] = 0.4 * df['mom_5d'] + 0.3 * c.pct_change(10) + 0.2 * c.pct_change(15) + 0.1 * df['mom_20d']
            rolling_max = c.rolling(20).max()
            df['drawdown_20d'] = (c - rolling_max) / (rolling_max + 1e-10)
            up = (ret1 > 0).astype(int)
            down = (ret1 < 0).astype(int)
            df['up_streak'] = up.groupby((up != up.shift()).cumsum()).cumsum()
            df['down_streak'] = down.groupby((down != down.shift()).cumsum()).cumsum()
            price_up = (c > c.shift(5)).astype(int)
            vol_down = (v < v.shift(5)).astype(int)
            df['vol_price_div'] = price_up * vol_down
            
            all_frames[i] = df
        
        all_df = pd.concat(all_frames, ignore_index=True)
        
        # v15: 全市场截面 + 行业内截面 + 排名 + 均值回归
        raw_features = ['mom_5d','mom_10d','mom_20d','mom_60d','mom_accel',
                        'dist_sma20','dist_sma60','vol_5d','vol_20d','vol_ratio',
                        'turnover_ratio','vol_price_corr','macd_hist','rsi_14',
                        'bb_pos','atr_ratio','body_ratio','ret_1d','ret_3d',
                        'high_low_range','gap',
                        'sharpe_20d','decay_mom','drawdown_20d','up_streak','down_streak','vol_price_div']
        
        for feat in raw_features:
            m = all_df.groupby('日期')[feat].transform('mean')
            s = all_df.groupby('日期')[feat].transform('std')
            all_df[f'{feat}_cs'] = (all_df[feat] - m) / (s + 1e-10)
        
        # v11: 行业内Z-score（如果没有sector列则跳过）
        sector_feats = ['mom_20d','rsi_14','turnover_ratio','macd_hist']
        if 'sector' in all_df.columns:
            for feat in sector_feats:
                m = all_df.groupby(['日期','sector'])[feat].transform('mean')
                s = all_df.groupby(['日期','sector'])[feat].transform('std')
                all_df[f'{feat}_sector'] = (all_df[feat] - m) / (s + 1e-10)
        else:
            for feat in sector_feats:
                all_df[f'{feat}_sector'] = 0
        
        rank_feats = ['mom_5d','mom_20d','mom_60d','rsi_14','turnover_ratio','macd_hist','sharpe_20d']
        for feat in rank_feats:
            all_df[f'{feat}_rank'] = all_df.groupby('日期')[feat].rank(pct=True)
        
        for feat in ['mom_20d','rsi_14']:
            all_df[f'{feat}_sector_rank'] = all_df.groupby('日期')[feat].rank(pct=True)
            all_df[f'{feat}_revert'] = -all_df[f'{feat}_cs']
        
        cs_cols = [f'{f}_cs' for f in raw_features]
        sector_cols = [f'{f}_sector' for f in sector_feats]
        rank_cols = [f'{f}_rank' for f in rank_feats]
        sector_rank_cols = [f'{f}_sector_rank' for f in ['mom_20d','rsi_14']]
        revert_cols = [f'{f}_revert' for f in ['mom_20d','rsi_14']]
        ml_features = cs_cols + sector_cols + rank_cols + sector_rank_cols + revert_cols
        
        for col in ml_features:
            all_df[col] = all_df[col].replace([np.inf, -np.inf], np.nan).fillna(0)
        
        latest = all_df.groupby('code').tail(1).copy()
        X = latest[ml_features].values
        
        # v16集成预测
        if isinstance(ml_model, dict) and 'models' in ml_model:
            all_preds = [model.predict(X) for model in ml_model['models']]
            predictions = np.mean(all_preds, axis=0)
        else:
            predictions = ml_model.predict(X)
        
        # 5. 格式化结果
        results = []
        for i, (_, row) in enumerate(latest.iterrows()):
            pred = float(predictions[i])
            signal = "看涨" if pred > 0.02 else ("看跌" if pred < -0.02 else "中性")
            confidence = "高" if abs(pred) > 0.05 else ("中" if abs(pred) > 0.02 else "低")
            
            # v10相对强弱
            cs_mom = row.get('mom_5d_cs', 0)
            cs_rsi = row.get('rsi_14_cs', 0)
            
            results.append({
                "code": row['code'],
                "name": row['name'],
                "current_price": float(row['收盘']),
                "predicted_return": round(pred * 100, 2),
                "signal": signal,
                "confidence": confidence,
                "relative_strength": {
                    "momentum": round(float(cs_mom), 2),
                    "rsi": round(float(cs_rsi), 2),
                },
                "model_version": "v16c",
            })
        
        results.sort(key=lambda x: x['predicted_return'], reverse=True)
        
        return jsonify({
            "status": "success",
            "data": results,
            "meta": {
                "model": "v16c 集成学习",
                "features": len(ml_features),
                "stocks": len(results),
                "prediction_horizon": "20日",
            }
        })
        
    except Exception as e:
        import traceback
        return jsonify({"status": "error", "message": str(e), "trace": traceback.format_exc()})


@app.route('/api/search')
def search_stocks():
    """股票搜索 - 支持代码和名称"""
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return jsonify({"status": "error", "message": "请输入搜索关键词"})
    
    try:
        import re
        results = []
        
        # 东方财富搜索
        try:
            em_url = "https://searchapi.eastmoney.com/api/suggest/get"
            em_params = {
                'input': keyword,
                'type': 14,
                'token': 'D43BF722C8E33BDC906FB84D85E326E8',
                'count': 10,
            }
            em_r = requests.get(em_url, params=em_params, timeout=5)
            em_data = em_r.json()
            if 'QuotationCodeTable' in em_data and 'Data' in em_data['QuotationCodeTable']:
                for item in em_data['QuotationCodeTable']['Data']:
                    code = item.get('Code', '')
                    name = item.get('Name', '')
                    market = item.get('MktNum', '')
                    stype = item.get('SecurityTypeName', '')
                    # 只保留A股
                    if code and name and len(code) == 6 and ('A' in stype or '股' in stype):
                        prefix = 'sh' if code.startswith('6') else 'sz'
                        results.append({
                            'code': code,
                            'name': name,
                            'market': prefix,
                            'full_code': f"{prefix}{code}",
                            'type': stype,
                            'source': 'eastmoney',
                        })
        except:
            pass
        
        # 腾讯搜索 (补充)
        try:
            tx_url = f"https://smartbox.gtimg.cn/s3/?v=2&q={keyword}&t=all"
            tx_r = requests.get(tx_url, timeout=5)
            match = re.search(r'"(.+)"', tx_r.text)
            if match:
                items = match.group(1).split('^')
                existing_codes = {r['code'] for r in results}
                for item in items:
                    parts = item.split('~')
                    if len(parts) >= 4:
                        code = parts[1]
                        name = parts[2]
                        market = parts[0]
                        # 只保留A股且不在已有结果中
                        if code and name and len(code) == 6 and market in ['sh', 'sz'] and code not in existing_codes:
                            results.append({
                                'code': code,
                                'name': name,
                                'market': market,
                                'full_code': f"{market}{code}",
                                'type': 'A股',
                                'source': 'tencent',
                            })
        except:
            pass
        
        return jsonify({
            "status": "success",
            "data": results[:20],
            "keyword": keyword,
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/api/stock_info/<code>')
def get_stock_info(code):
    """获取单只股票详细信息"""
    try:
        # 根据代码判断市场
        prefix = 'sh' if code.startswith('6') else 'sz'
        symbol = f"{prefix}{code}"
        
        # 获取实时行情
        api = StockDataAPI()
        realtime = api.get_realtime(symbol)
        
        if 'error' in realtime:
            return jsonify({"status": "error", "message": realtime['error']})
        
        return jsonify({
            "status": "success",
            "data": {
                "code": code,
                "name": realtime.get('name', ''),
                "price": realtime.get('price', 0),
                "change": realtime.get('change', 0),
                "change_pct": realtime.get('change_pct', 0),
                "volume": realtime.get('volume', 0),
                "amount": realtime.get('amount', 0),
                "high": realtime.get('high', 0),
                "low": realtime.get('low', 0),
                "open": realtime.get('open', 0),
            }
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/api/news')
def get_news():
    """实时新闻监控 - 返回所有新闻"""
    try:
        import akshare as ak
        
        # 情绪关键词
        POSITIVE_KEYWORDS = [
            '利好', '大涨', '涨停', '突破', '创新高', '增长', '盈利', '超预期',
            '订单', '中标', '签约', '合作', '回购', '增持', '业绩预增', '新高',
        ]
        NEGATIVE_KEYWORDS = [
            '利空', '大跌', '跌停', '暴跌', '亏损', '下滑', '减持', '质押',
            '违规', '处罚', '调查', '退市', '风险', '警告', '业绩预减', '暴雷',
        ]
        
        # 监控股票关键词
        STOCK_KEYWORDS = {
            '300201': ['海伦哲', '300201'],
            '000001': ['平安银行', '000001'],
            '600519': ['贵州茅台', '600519', '茅台', '白酒'],
            '300750': ['宁德时代', '300750', '宁德', '锂电'],
            '002594': ['比亚迪', '002594', '比亚迪', '新能源车'],
        }
        
        all_news = []
        
        # 财联社
        try:
            cls_df = ak.stock_info_global_cls()
            if cls_df is not None:
                for _, row in cls_df.iterrows():
                    all_news.append({
                        'source': '财联社',
                        'title': str(row.get('标题', '')),
                        'content': str(row.get('内容', '')),
                        'time': f"{row.get('发布日期', '')} {row.get('发布时间', '')}",
                    })
        except:
            pass
        
        # 东方财富
        try:
            em_df = ak.stock_info_global_em()
            if em_df is not None:
                for _, row in em_df.head(50).iterrows():
                    all_news.append({
                        'source': '东方财富',
                        'title': str(row.get('标题', '')),
                        'content': str(row.get('摘要', '')),
                        'time': str(row.get('发布时间', '')),
                    })
        except:
            pass
        
        # 同花顺
        try:
            ths_df = ak.stock_info_global_ths()
            if ths_df is not None:
                for _, row in ths_df.iterrows():
                    all_news.append({
                        'source': '同花顺',
                        'title': str(row.get('内容', '')),
                        'content': str(row.get('内容', '')),
                        'time': str(row.get('发布时间', '')),
                    })
        except:
            pass
        
        # 对所有新闻进行分析
        analyzed = []
        for news in all_news:
            text = f"{news['title']} {news['content']}"
            
            # 情绪分析
            pos_hits = [kw for kw in POSITIVE_KEYWORDS if kw in text]
            neg_hits = [kw for kw in NEGATIVE_KEYWORDS if kw in text]
            score = len(pos_hits) - len(neg_hits)
            
            # 股票关联
            related_stocks = []
            for code, kws in STOCK_KEYWORDS.items():
                hits = [kw for kw in kws if kw in text]
                if hits:
                    related_stocks.append({'code': code, 'keywords': hits})
            
            # 所有新闻都返回，标记重要性
            is_important = abs(score) >= 2 or len(related_stocks) > 0
            
            news['sentiment_score'] = score
            news['sentiment_keywords'] = pos_hits + neg_hits
            news['sentiment'] = '利好' if score > 0 else ('利空' if score < 0 else '中性')
            news['related_stocks'] = related_stocks
            news['is_stock_related'] = len(related_stocks) > 0
            news['is_important'] = is_important
            analyzed.append(news)
        
        # 排序：重要的在前，然后按时间倒序
        analyzed.sort(key=lambda x: (x['is_important'], len(x['related_stocks']), abs(x['sentiment_score'])), reverse=True)
        
        return jsonify({
            "status": "success",
            "data": analyzed[:50],
            "meta": {
                "total_fetched": len(all_news),
                "important_count": sum(1 for n in analyzed if n['is_important']),
                "sources": ['财联社', '东方财富', '同花顺'],
            }
        })
        
    except Exception as e:
        import traceback
        return jsonify({"status": "error", "message": str(e), "trace": traceback.format_exc()})


if __name__ == '__main__':
    load_ml_model()
    app.run(debug=True, host='0.0.0.0', port=5000)
