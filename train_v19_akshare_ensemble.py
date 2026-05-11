#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v19: AKShare 原生数据 + 28个核心因子 + 三树集成 (Ensemble) + 截面超额 Label
彻底剥离笨重的 Qlib cn_data 依赖，通过 AKShare 实时获取数据计算因子。
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
import lightgbm as lgb
from datetime import datetime
import akshare as ak
import warnings
warnings.filterwarnings('ignore')

def get_stock_data(code, start_date="20240101"):
    try:
        # AKShare A股日线数据
        prefix = "sh" if code.startswith("6") else "sz"
        df = ak.stock_zh_a_daily(symbol=f"{prefix}{code}", start_date=start_date, adjust="qfq")
        df.rename(columns={'date': 'datetime'}, inplace=True)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        df = df[['open', 'high', 'low', 'close', 'volume', 'amount']]
        # 转换列类型
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['code'] = code
        return df
    except Exception as e:
        print(f"获取 {code} 失败: {e}")
        return None

def calc_features(df):
    df = df.copy()
    # === 动量特征 ===
    for d in [1, 3, 5, 10, 20, 60]:
        df[f'MOM_{d}'] = df['close'] / df['close'].shift(d) - 1
        
    # === 均线偏离 ===
    for d in [5, 10, 20, 60]:
        df[f'MA_{d}_ratio'] = df['close'] / df['close'].rolling(d).mean()
        
    # === 波动率 ===
    ret_1 = df['close'].pct_change()
    for d in [5, 10, 20, 60]:
        df[f'VOL_{d}'] = ret_1.rolling(d).std()
        
    # === 量价特征 ===
    for d in [5, 10]:
        df[f'VOLU_{d}_RATIO'] = df['volume'] / df['volume'].rolling(d).mean()
    df.rename(columns={'VOLU_5_RATIO': 'VOLU_RATIO'}, inplace=True)
    
    vwap = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
    df['VWAP_ratio'] = vwap / df['close']
    
    for d in [10, 20]:
        df[f'V_STD_{d}'] = df['volume'].rolling(d).std() / df['volume'].rolling(d).mean()
        
    # === 反转与位置 ===
    df['HIGH_ratio'] = df['close'] / df['high'].rolling(20).max()
    df['LOW_ratio'] = df['close'] / df['low'].rolling(20).min()
    df['O_C_ratio'] = df['close'] / df['open']
    
    # === 传统技术指标 ===
    tp = (df['high'] + df['low'] + df['close']) / 3
    df['CCI_14'] = (tp - tp.rolling(14).mean()) / (0.015 * tp.rolling(14).std())
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    df['EMA_12_ratio'] = df['close'] / df['close'].ewm(span=12, adjust=False).mean()
    df['EMA_26_ratio'] = df['close'] / df['close'].ewm(span=26, adjust=False).mean()
    
    # Label: 明天的收益率
    df['Label_raw'] = df['close'].shift(-1) / df['close'] - 1
    
    return df

def main():
    print("[Train v19] 开始下载并构建特征数据集...")
    stock_pool = []
    if os.path.exists('data/curated_stocks_v12.json'):
        with open('data/curated_stocks_v12.json', 'r', encoding='utf-8') as f:
            stock_pool = json.load(f)
            stock_pool = [c[-6:] for c in stock_pool]
    
    if not stock_pool:
        print("[Train v19] 找不到精选池，使用测试代码: 300201, 000001")
        stock_pool = ["300201", "000001"]

    dfs = []
    for code in stock_pool:
        df = get_stock_data(code)
        if df is not None and not df.empty:
            df = calc_features(df)
            dfs.append(df)
            print(f"  处理完成: {code} ({len(df)} 行)")
            
    if not dfs:
        print("[Train v19] 没有获取到有效数据！")
        return
        
    full_df = pd.concat(dfs)
    full_df.reset_index(inplace=True)
    full_df = full_df.dropna()
    
    print(f"\n[Train v19] 全量数据拼接完成，共 {len(full_df)} 条样本")
    
    # === 横截面超额 Label 优化 (Point 3) ===
    # 每天对所有股票的 Label 进行横截面 Z-score 处理
    full_df['Label'] = full_df.groupby('datetime')['Label_raw'].transform(
        lambda x: (x - x.mean()) / (x.std() + 1e-8)
    )
    
    features = [
        "MOM_1", "MOM_3", "MOM_5", "MOM_10", "MOM_20", "MOM_60",
        "MA_5_ratio", "MA_10_ratio", "MA_20_ratio", "MA_60_ratio",
        "VOL_5", "VOL_10", "VOL_20", "VOL_60",
        "VOLU_RATIO", "VOLU_10_RATIO", "VWAP_ratio", "V_STD_10", "V_STD_20",
        "HIGH_ratio", "LOW_ratio", "O_C_ratio",
        "CCI_14", "RSI_14", "EMA_12_ratio", "EMA_26_ratio"
    ]
    
    # 时间划分
    dates = np.sort(full_df['datetime'].unique())
    split_date = dates[-30] if len(dates) > 30 else dates[-1]
    
    train_mask = full_df['datetime'] < split_date
    test_mask = full_df['datetime'] >= split_date
    
    X_train, y_train = full_df.loc[train_mask, features], full_df.loc[train_mask, 'Label']
    X_test, y_test = full_df.loc[test_mask, features], full_df.loc[test_mask, 'Label']
    
    print(f"[Train v19] 训练集: {len(X_train)} | 测试集: {len(X_test)}")
    
    # === 三树集成模型 (Point 2) ===
    print("[Train v19] 开始训练三树集成模型 (Ensemble)...")
    models = []
    configs = [
        {'num_leaves': 31, 'learning_rate': 0.05, 'num_boost_round': 200, 'name': '平缓型'},
        {'num_leaves': 50, 'learning_rate': 0.03, 'num_boost_round': 300, 'name': '深度型'},
        {'num_leaves': 20, 'learning_rate': 0.08, 'num_boost_round': 150, 'name': '激进型'}
    ]
    
    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
    
    for cfg in configs:
        print(f"  -> 训练 {cfg['name']} 模型 (leaves={cfg['num_leaves']}, lr={cfg['learning_rate']})...")
        params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'learning_rate': cfg['learning_rate'],
            'num_leaves': cfg['num_leaves'],
            'verbose': -1,
            'seed': 42
        }
        model = lgb.train(
            params,
            train_data,
            num_boost_round=cfg['num_boost_round'],
            valid_sets=[train_data, valid_data],
            callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
        )
        models.append(model)
    
    # 评估集成结果
    test_df = full_df.loc[test_mask].copy()
    preds_list = [m.predict(X_test) for m in models]
    test_df['pred_ensemble'] = np.mean(preds_list, axis=0)
    
    rmse = np.sqrt(np.mean((test_df['pred_ensemble'] - test_df['Label']) ** 2))
    
    # 截面 IC 评估
    ic_list = test_df.groupby('datetime').apply(lambda x: x['pred_ensemble'].corr(x['Label'], method='spearman'))
    mean_ic = ic_list.mean()
    
    print(f"\n[Train v19] 评估完成！集成 RMSE: {rmse:.4f}, 截面 Rank IC: {mean_ic:.4f}")
    
    # 预测最近一天的结果 (离线跑批写入 JSON)
    print(f"\n[Train v19] 生成最新一日离线预测报告 (供Web使用)...")
    latest_date = dates[-1]
    latest_df = full_df[full_df['datetime'] == latest_date].copy()
    
    if not latest_df.empty:
        X_latest = latest_df[features]
        preds_latest = np.mean([m.predict(X_latest) for m in models], axis=0)
        latest_df['pred'] = preds_latest
        
        # 将 Z-score 放缩回大概的实际涨跌幅范围 (经验值缩放)
        latest_df['pred_raw_est'] = latest_df['pred'] * 0.015
        
        results = {}
        for _, row in latest_df.iterrows():
            code = str(row['code'])
            pred_val = float(row['pred_raw_est'])
            
            signal = "中性"
            if pred_val > 0.015: signal = "强烈看涨"
            elif pred_val > 0.005: signal = "看涨"
            elif pred_val < -0.01: signal = "看跌"
            
            results[code] = {
                "predicted_return": round(pred_val, 4),
                "signal": signal,
                "momentum": float(row['MOM_5']) if not pd.isna(row['MOM_5']) else 0.5
            }
            
        output = {
            "_meta": {
                "model_version": "v19_ensemble",
                "date": str(latest_date)[:10],
                "stocks": len(results),
                "features": len(features),
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "data": results
        }
        os.makedirs("model_output", exist_ok=True)
        with open("model_output/daily_predictions_v19.json", 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)
        print(f"  -> 生成完毕! 涉及股票数: {len(results)}")
        
    # 保存模型
    with open("model_output/lgb_model_v19_ensemble.pkl", 'wb') as f:
        pickle.dump(models, f)
    with open("model_output/features_v19.json", 'w') as f:
        json.dump(features, f)
        
    print("[Train v19] 完美收工！")

if __name__ == "__main__":
    main()
