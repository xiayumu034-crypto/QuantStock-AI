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
from datetime import datetime

def main():
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    print(f"[Train v19 Ensemble] Qlib 初始化成功.")

    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, as_list=True)

    features = {
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
    
    label = {
        "Label": "Ref($close, -1) / $close - 1"
    }

    all_fields = list(features.values()) + list(label.values())
    all_names = list(features.keys()) + list(label.keys())

    print(f"[Train v19 Ensemble] 正在提取特征和标签...")
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    df = D.features(stock_list, all_fields, start_time="2022-01-01", end_time=end_date, freq='day')
    df.columns = all_names

    df = df.dropna()
    feature_cols = list(features.keys())
    
    def cross_sectional_norm(group):
        group_features = group[feature_cols]
        lower = group_features.quantile(0.01)
        upper = group_features.quantile(0.99)
        clipped = group_features.clip(lower=lower, upper=upper, axis=1)
        mean = clipped.mean()
        std = clipped.std().replace(0, 1e-8)
        group[feature_cols] = (clipped - mean) / std
        return group
    
    df = df.groupby(level='datetime', group_keys=False).apply(cross_sectional_norm)
    df = df.dropna()

    X = df[feature_cols]
    y = df["Label"]
    
    dates = df.index.get_level_values('datetime')
    unique_dates = dates.unique()
    split_date = unique_dates[-30]
    
    train_mask = dates < split_date
    test_mask = dates >= split_date

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    print(f"[Train v19 Ensemble] 训练集样本数: {len(X_train)}, 测试集样本数: {len(X_test)}")

    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    # 训练 5 个模型组成集成，改变不同的超参数和种子以增加差异性
    models = []
    seeds = [42, 888, 2026, 7, 999]
    leaves = [15, 31, 7, 63, 20]
    
    for i in range(5):
        print(f"\n[Train v19 Ensemble] 正在训练子模型 {i+1}/5 ...")
        params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'learning_rate': 0.03,
            'num_leaves': leaves[i],
            'max_depth': -1,
            'feature_fraction': 0.6,
            'bagging_fraction': 0.8,
            'bagging_freq': 3,
            'verbose': -1,
            'seed': seeds[i]
        }
        model = lgb.train(
            params,
            train_data,
            num_boost_round=1000,
            valid_sets=[train_data, valid_data],
            callbacks=[lgb.early_stopping(stopping_rounds=50)]
        )
        models.append(model)

    os.makedirs("model_output", exist_ok=True)
    model_path = "model_output/lgb_model_v19_ensemble.pkl"
    features_path = "model_output/features_v19_ensemble.json"

    with open(model_path, 'wb') as f:
        pickle.dump(models, f) # 存入模型列表
    
    with open(features_path, 'w', encoding='utf-8') as f:
        json.dump(features, f, ensure_ascii=False, indent=4)
        
    print(f"\n[Train v19 Ensemble] 训练完成！集成模型已保存至: {model_path}")

if __name__ == '__main__':
    main()
