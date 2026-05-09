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
    model_path = "model_output/lgb_model_v18.pkl"
    features_path = "model_output/features_v18.json"
    
    if not os.path.exists(model_path):
        print(f"[Inference v18] 未找到模型 {model_path}，请先运行 train_qlib_v18.py")
        return
        
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
        
    with open(features_path, 'r') as f:
        feature_names = json.load(f)
        
    # v18 全量特征配置 (必须与训练时一致)
    features = {
        "MOM_1": "$close / Ref($close, 1) - 1",
        "MOM_3": "$close / Ref($close, 3) - 1",
        "MOM_5": "$close / Ref($close, 5) - 1",
        "MOM_10": "$close / Ref($close, 10) - 1",
        "MOM_20": "$close / Ref($close, 20) - 1",
        "MA_5_ratio": "$close / Mean($close, 5)",
        "MA_10_ratio": "$close / Mean($close, 10)",
        "MA_20_ratio": "$close / Mean($close, 20)",
        "MA_60_ratio": "$close / Mean($close, 60)",
        "VOL_5": "Std($close / Ref($close, 1) - 1, 5)",
        "VOL_10": "Std($close / Ref($close, 1) - 1, 10)",
        "VOL_20": "Std($close / Ref($close, 1) - 1, 20)",
        "VOLU_RATIO": "$volume / Mean($volume, 5)",
        "VWAP_ratio": "$vwap / $close",
        "CCI_14": "(($close - Mean($close, 14)) / (0.015 * Std($close, 14)))",
        "RSI_14": "100 - 100 / (1 + (Sum(If($close > Ref($close, 1), $close - Ref($close, 1), 0), 14) / Sum(If($close < Ref($close, 1), Ref($close, 1) - $close, 0), 14)))",
        "EMA_12_ratio": "$close / EMA($close, 12)",
        "EMA_26_ratio": "$close / EMA($close, 26)",
        "HIGH_ratio": "$close / Max($high, 20)",
        "LOW_ratio": "$close / Min($low, 20)",
        "O_C_ratio": "$close / $open",
        "V_STD_10": "Std($volume, 10) / Mean($volume, 10)"
    }
    
    # 动态匹配模型需要的特征
    fields = [features[name] for name in feature_names]
    
    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, as_list=True)
    
    print("[Inference v18] 正在通过 Qlib 极速提取最新特征...")
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    df = D.features(stock_list, fields, start_time="2024-01-01", end_time=end_date, freq='day')
    df.columns = feature_names
    df = df.dropna()
    
    if df.empty:
        print("[Inference v18] 没有足够的最近数据！")
        return
        
    # v18 推理时同样需要进行截面标准化，否则特征量纲不对
    print("[Inference v18] 执行横截面标准化 (Z-score, winsorize)...")
    def cross_sectional_norm(group):
        group_features = group[feature_names]
        lower = group_features.quantile(0.01)
        upper = group_features.quantile(0.99)
        clipped = group_features.clip(lower=lower, upper=upper, axis=1)
        mean = clipped.mean()
        std = clipped.std().replace(0, 1e-8)
        group[feature_names] = (clipped - mean) / std
        return group
        
    df = df.groupby(level='datetime', group_keys=False).apply(cross_sectional_norm)
    df = df.dropna()

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
            "momentum": float(row.get("MOM_10", 0.5))  # v18 直接从因子里读取动量
        }
        
    final_output = {
        "_meta": {
            "model_version": "v18",
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stock_count": len(predictions_dict),
            "feature_count": len(feature_names),
            "end_date": end_date,
            "is_sample": False
        },
        "data": predictions_dict
    }
        
    out_file = "model_output/daily_predictions_v18.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)
        
    print(f"[Inference v18] 批量离线预测完成，共计 {len(predictions_dict)} 只股票。")
    print(f"[Inference v18] 预测结果已输出至 {out_file}")

if __name__ == "__main__":
    main()