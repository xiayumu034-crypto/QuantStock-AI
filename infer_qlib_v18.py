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
    print(f"[Infer v18] Qlib 初始化成功.")

    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, as_list=True)

    # 加载白名单股票（限制预测池）
    stock_pool = []
    if os.path.exists('data/curated_stocks_v12.json'):
        with open('data/curated_stocks_v12.json', 'r', encoding='utf-8') as f:
            stock_pool = json.load(f)
    if stock_pool:
        # 兼容 sh / sz 前缀
        clean_pool = [code[-6:] for code in stock_pool]
        # 从 Qlib 的 stock_list 里筛选出 SH / SZ 开头的匹配项
        valid_stocks = [s for s in stock_list if s[-6:] in clean_pool]
    else:
        valid_stocks = stock_list[:100]  # 没有白名单则默认测 100 个

    print(f"[Infer v18] 预测股票池大小: {len(valid_stocks)}")

    # 2. 加载模型和特征
    model_path = "model_output/lgb_model_v18.pkl"
    features_path = "model_output/features_v18.json"

    if not os.path.exists(model_path) or not os.path.exists(features_path):
        print("[Infer v18] 找不到模型或特征配置，请先运行 train_qlib_v18.py")
        return

    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    
    with open(features_path, 'r', encoding='utf-8') as f:
        feature_cols = json.load(f)

    # 我们需要获取最新一天的特征，Qlib中我们可以提取最近几天的数据，取最后一天
    # 为了计算 MA_60 这种长周期指标，Qlib 底层会自动取够历史数据
    print(f"[Infer v18] 正在提取最新特征数据...")
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    # 为了拿到今天的数据，我们 start_time 设置为 7 天前，然后取最后一天的截面
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=15)).strftime("%Y-%m-%d")
    
    try:
        # 重构 Qlib 表达式字典（因为 D.features 接受表达式列表）
        # 特征必须跟训练时完全一样。为了避免重写，我们直接去读训练脚本里的 features 定义
        # 为了简便，我们把那些表达式重新列一次：
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
        # 如果模型添加了横截面处理，可以在这里对应
        # 这里只读取模型里需要的列
        all_exprs = [features_expr[col] for col in feature_cols if col in features_expr]
        
        df = D.features(valid_stocks, all_exprs, start_time=start_date, end_time=end_date, freq='day')
        df.columns = feature_cols
    except Exception as e:
        print(f"[Infer v18] 特征提取失败: {e}")
        return

    df = df.dropna()
    if df.empty:
        print("[Infer v18] 获取的最新数据为空")
        return

    # 取最新的一天截面
    latest_date = df.index.get_level_values('datetime').max()
    print(f"[Infer v18] 最新可用数据日期: {latest_date}")
    df_latest = df.xs(latest_date, level='datetime')

    # 预测
    X = df_latest[feature_cols]
    preds = model.predict(X)
    
    # 构建结果
    results = {}
    for i, stock in enumerate(df_latest.index):
        code = stock[-6:] # 转为 6 位数字代码
        pred_val = float(preds[i])
        
        # 将连续的收益率预测转换为信号
        signal = "中性"
        if pred_val > 0.015: signal = "强烈看涨"
        elif pred_val > 0.005: signal = "看涨"
        elif pred_val < -0.01: signal = "看跌"
        
        results[code] = {
            "predicted_return": round(pred_val, 4),
            "signal": signal,
            "momentum": float(df_latest['MOM_5'].iloc[i]) if 'MOM_5' in df_latest else 0.5
        }

    # 包装元数据
    output = {
        "_meta": {
            "model_version": "v18",
            "date": str(latest_date.date()),
            "stocks": len(results),
            "features": len(feature_cols),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "data": results
    }

    os.makedirs("model_output", exist_ok=True)
    out_file = "model_output/daily_predictions_v18.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print(f"[Infer v18] 预测完成，共生成 {len(results)} 只股票的预测结果，保存至 {out_file}")

if __name__ == "__main__":
    main()
