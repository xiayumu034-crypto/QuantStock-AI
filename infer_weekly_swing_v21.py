#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import qlib
from qlib.data import D
from qlib.config import REG_CN
import pandas as pd
import numpy as np
import lightgbm as lgb
import os
import json
import pickle

def main():
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    
    with open("model_output/lgb_model_v21_weekly_primary.pkl", "rb") as f:
        model_primary = pickle.load(f)
    with open("model_output/lgb_model_v21_weekly_meta.pkl", "rb") as f:
        model_meta = pickle.load(f)
    with open("model_output/features_v21_weekly.json", "r", encoding='utf-8') as f:
        feature_cols = json.load(f)
        
    features_expr = {
        "MOM_3": "$close / Ref($close, 3) - 1",
        "MOM_5": "$close / Ref($close, 5) - 1",
        "MOM_10": "$close / Ref($close, 10) - 1",
        "MOM_20": "$close / Ref($close, 20) - 1",
        "MA_5_ratio": "$close / Mean($close, 5)",
        "MA_10_ratio": "$close / Mean($close, 10)",
        "MA_20_ratio": "$close / Mean($close, 20)",
        "VOL_5": "Std($close / Ref($close, 1) - 1, 5)",
        "VOL_10": "Std($close / Ref($close, 1) - 1, 10)",
        "VOL_20": "Std($close / Ref($close, 1) - 1, 20)",
        "VOLU_RATIO": "$volume / Mean($volume, 5)",
        "VOLU_10_RATIO": "$volume / Mean($volume, 10)",
        "RSI_6": "100 - 100 / (1 + (Sum(If($close > Ref($close, 1), $close - Ref($close, 1), 0), 6) / Sum(If($close < Ref($close, 1), Ref($close, 1) - $close, 0), 6)))",
        "RSI_14": "100 - 100 / (1 + (Sum(If($close > Ref($close, 1), $close - Ref($close, 1), 0), 14) / Sum(If($close < Ref($close, 1), Ref($close, 1) - $close, 0), 14)))",
        "MACD_DIF": "EMA($close, 12) - EMA($close, 26)",
        "MACD_DEA": "EMA(EMA($close, 12) - EMA($close, 26), 9)",
        "HIGH_ratio_20": "$close / Max($high, 20)",
        "HIGH_ratio_60": "$close / Max($high, 60)",
        "AMPLITUDE": "($high - $low) / Ref($close, 1)",
        "VWAP_ratio": "($amount / $volume) / $close"
    }
    
    # 获取 stock names
    stock_names = {}
    if os.path.exists("data/stock_names.json"):
        with open("data/stock_names.json", "r", encoding='utf-8') as f:
            stock_names = json.load(f)
            
    stock_list = []
    if stock_names:
        for code in stock_names.keys():
            prefix = 'sh' if code[-6:].startswith(('6', '8', '9')) else 'sz'
            stock_list.append(f"{prefix}{code[-6:]}".upper())
    else:
        instruments = D.instruments(market='all')
        stock_list = D.list_instruments(instruments=instruments, as_list=True)[:500]

    all_exprs = [features_expr[col] for col in feature_cols if col in features_expr]
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    
    df = D.features(stock_list, all_exprs, start_time=start_date, end_time=end_date, freq='day')
    df.columns = feature_cols
    df = df.dropna()
    
    if df.empty:
        print("[Infer v21 Weekly] 获取的最新数据为空")
        return
        
    latest_date = df.index.get_level_values('datetime').max()
    print(f"[Infer v21 Weekly] 最新可用数据日期: {latest_date}")
    df_latest = df.xs(latest_date, level='datetime').copy()
    
    # 截面标准化
    def z_score(x):
        std_val = x.std()
        if pd.isna(std_val) or std_val == 0:
            std_val = 1e-8
        return (x - x.mean()) / std_val
    df_latest = df_latest.apply(z_score, axis=0)
    
    X = df_latest[feature_cols]
    
    primary_pred = model_primary.predict(X)
    meta_pred = model_meta.predict(X)
    
    results = {}
    for i, stock in enumerate(df_latest.index):
        code = stock.lower()
        pure_code = code[-6:]
        p_score = float(primary_pred[i])
        m_score = float(meta_pred[i])
        
        signal = "中性"
        if p_score > 0.6 and m_score > 0.6:
            signal = "强烈看涨"
        elif p_score > 0.55:
            signal = "看涨"
        elif p_score < 0.4:
            signal = "看跌"
            
        results[code] = {
            "code": pure_code,
            "name": stock_names.get(pure_code, stock_names.get(code, "未知")),
            "expected_5d_return": p_score * 0.08, # 经验估计
            "win_prob": p_score,
            "meta_score": m_score,
            "signal": signal,
            "confidence": "高" if m_score > 0.65 else ("中" if m_score > 0.55 else "低"),
            "take_profit_pct": 8.0,
            "stop_loss_pct": -5.0,
            "max_holding_days": 5,
            "reason_factors": "量价共振/元标签过滤"
        }
        
    output_path = "model_output/daily_predictions_v21_weekly.json"
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump({"data": results, "meta": {"date": str(latest_date), "model": "v21_weekly"}}, f, ensure_ascii=False, indent=4)
        
    print(f"[Infer v21 Weekly] 预测完成，共生成 {len(results)} 只股票的预测结果。")

if __name__ == "__main__":
    main()