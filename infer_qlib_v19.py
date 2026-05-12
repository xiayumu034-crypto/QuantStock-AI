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
    print(f"[Infer v19] Qlib 初始化成功.")

    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, as_list=True)

    # 加载白名单股票（限制预测池）
    stock_pool = []
    if os.path.exists('data/curated_stocks_v12.json'):
        with open('data/curated_stocks_v12.json', 'r', encoding='utf-8') as f:
            stock_pool = json.load(f)
    if stock_pool:
        clean_pool = [code[-6:] for code in stock_pool]
        valid_stocks = [s for s in stock_list if s[-6:] in clean_pool]
    else:
        valid_stocks = stock_list[:100]

    print(f"[Infer v19] 预测股票池大小: {len(valid_stocks)}")

    # 2. 加载模型和特征
    model_path = "model_output/lgb_model_v19.pkl"
    features_path = "model_output/features_v19.json"

    if not os.path.exists(model_path) or not os.path.exists(features_path):
        print("[Infer v19] 找不到模型或特征配置，请先运行 train_qlib_v19.py")
        return

    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    
    with open(features_path, 'r', encoding='utf-8') as f:
        feature_cols = json.load(f)

    print(f"[Infer v19] 正在提取最新特征数据...")
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=15)).strftime("%Y-%m-%d")
    
    try:
        features_expr = {
            "MOM_1": "$close / Ref($close, 1) - 1",
            "MOM_3": "$close / Ref($close, 3) - 1",
            "MOM_5": "$close / Ref($close, 5) - 1",
            "MOM_10": "$close / Ref($close, 10) - 1",
            "MOM_20": "$close / Ref($close, 20) - 1",
            "MOM_60": "$close / Ref($close, 60) - 1",
            "MA_5_ratio": "$close / Mean($close, 5)",
            "MA_10_ratio": "$close / Mean($close, 10)",
            "MA_20_ratio": "$close / Mean($close, 20)",
            "MA_60_ratio": "$close / Mean($close, 60)",
            "VOL_5": "Std($close / Ref($close, 1) - 1, 5)",
            "VOL_10": "Std($close / Ref($close, 1) - 1, 10)",
            "VOL_20": "Std($close / Ref($close, 1) - 1, 20)",
            "VOL_60": "Std($close / Ref($close, 1) - 1, 60)",
            "VOLU_RATIO": "$volume / Mean($volume, 5)",
            "VOLU_10_RATIO": "$volume / Mean($volume, 10)",
            "VWAP_ratio": "($high + $low + $close) / 3 / $close",
            "V_STD_10": "Std($volume, 10) / Mean($volume, 10)",
            "V_STD_20": "Std($volume, 20) / Mean($volume, 20)",
            "HIGH_ratio": "$close / Max($high, 20)",
            "LOW_ratio": "$close / Min($low, 20)",
            "O_C_ratio": "$close / $open",
            "CCI_14": "(($close - Mean($close, 14)) / (0.015 * Std($close, 14)))",
            "RSI_14": "100 - 100 / (1 + (Sum(If($close > Ref($close, 1), $close - Ref($close, 1), 0), 14) / Sum(If($close < Ref($close, 1), Ref($close, 1) - $close, 0), 14)))",
            "EMA_12_ratio": "$close / EMA($close, 12)",
            "EMA_26_ratio": "$close / EMA($close, 26)"
        }
        all_exprs = [features_expr[col] for col in feature_cols if col in features_expr]
        
        df = D.features(valid_stocks, all_exprs, start_time=start_date, end_time=end_date, freq='day')
        df.columns = feature_cols
    except Exception as e:
        print(f"[Infer v19] 特征提取失败: {e}")
        return

    df = df.dropna()
    if df.empty:
        print("[Infer v19] 获取的最新数据为空")
        return

    # 取最新的一天截面
    latest_date = df.index.get_level_values('datetime').max()
    print(f"[Infer v19] 最新可用数据日期: {latest_date}")
    df_latest = df.xs(latest_date, level='datetime').copy()

    # ====== 核心修复：必须进行与训练一致的横截面标准化 ======
    lower = df_latest[feature_cols].quantile(0.01)
    upper = df_latest[feature_cols].quantile(0.99)
    clipped = df_latest[feature_cols].clip(lower=lower, upper=upper, axis=1)
    mean = clipped.mean()
    std = clipped.std().replace(0, 1e-8)
    df_latest[feature_cols] = (clipped - mean) / std

    # 预测3日收益率
    X = df_latest[feature_cols]
    preds = model.predict(X)
    
    results = {}
    for i, stock in enumerate(df_latest.index):
        code = stock[-6:]
        ret = float(preds[i])
        
        results[code] = {
            "predicted_return": round(ret, 4), # 回归预测的3日累计收益率
            "signal": "中性", # 交给后端按排名分配
            "momentum": float(df_latest['MOM_5'].iloc[i]) if 'MOM_5' in df_latest else 0.5
        }

    output = {
        "_meta": {
            "model_version": "v19_3d_regression",
            "date": str(latest_date.date()),
            "stocks": len(results),
            "features": len(feature_cols),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "data": results
    }

    os.makedirs("model_output", exist_ok=True)
    out_file = "model_output/daily_predictions_v19.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print(f"[Infer v19] 预测完成，共生成 {len(results)} 只股票的预测结果，保存至 {out_file}")

if __name__ == '__main__':
    main()