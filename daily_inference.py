#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import qlib
from qlib.data import D
from qlib.config import REG_CN
import pandas as pd
import numpy as np
import os
import json
import pickle
from datetime import datetime

def main():
    # 1. 初始化 Qlib
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    
    # 2. 加载模型和特征配置
    model_path = "model_output/lgb_model_v17.pkl"
    features_path = "model_output/features_v17.json"
    
    if not os.path.exists(model_path):
        print(f"[Inference] 未找到模型 {model_path}，请先运行 train_qlib_v17.py")
        return
        
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
        
    with open(features_path, 'r') as f:
        feature_names = json.load(f)
        
    features = {
        "CCI": "(($close - Mean($close, 14)) / (0.015 * Std($close, 14)))",
        "RSI_14": "100 - 100 / (1 + (Sum(If($close > Ref($close, 1), $close - Ref($close, 1), 0), 14) / Sum(If($close < Ref($close, 1), Ref($close, 1) - $close, 0), 14)))",
        "VWAP_ratio": "$vwap / $close",
        "MOM_1": "$close / Ref($close, 1) - 1",
        "MOM_3": "$close / Ref($close, 3) - 1",
        "MOM_5": "$close / Ref($close, 5) - 1",
        "VOL_10": "Std($close / Ref($close, 1) - 1, 10)",
        "MA_5_ratio": "$close / Mean($close, 5)",
        "MA_10_ratio": "$close / Mean($close, 10)",
    }
    
    fields = [features[name] for name in feature_names]
    
    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, as_list=True)
    
    print("[Inference] 正在通过 Qlib 极速提取最新特征...")
    df = D.features(stock_list, fields, start_time="2026-04-01", end_time="2026-12-31", freq='day')
    df.columns = feature_names
    df = df.dropna()
    
    if df.empty:
        print("[Inference] 没有足够的最近数据！")
        return
        
    latest_df = df.groupby(level='instrument').tail(1)
    predictions_dict = {}
    
    for index_tuple, row in latest_df.iterrows():
        stock_code_qlib = index_tuple[0]
        pure_code = stock_code_qlib[2:]  # SH600519 -> 600519
        
        X_infer = row[feature_names].values.reshape(1, -1)
        pred_return = float(model.predict(X_infer)[0])
        
        signal = "neutral"
        if pred_return > 0.001:
            signal = "bullish"
        elif pred_return < -0.001:
            signal = "bearish"
            
        predictions_dict[pure_code] = {
            "predicted_return": pred_return,
            "signal": signal,
            "confidence": 0.88,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
    out_file = "model_output/daily_predictions.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(predictions_dict, f, ensure_ascii=False, indent=4)
        
    print(f"[Inference] 批量离线预测完成，共计 {len(predictions_dict)} 只股票。")
    print(f"[Inference] 预测结果已输出至 {out_file}")

if __name__ == "__main__":
    main()
