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
    # 1. 初始化 Qlib
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    print(f"[Train v17] Qlib 初始化成功.")

    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, as_list=True)

    # 2. 定义因子和标签 (Label)
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
    
    # 预测未来 1 天的收益率作为 Label (注意：防止未来函数，是用明天的收盘价除以今天的收盘价)
    label = {
        "Label": "Ref($close, -1) / $close - 1"
    }

    all_fields = list(features.values()) + list(label.values())
    all_names = list(features.keys()) + list(label.keys())

    print("[Train v17] 正在通过 Qlib 提取特征和标签 (2024-01-01 至今)...")
    df = D.features(stock_list, all_fields, start_time="2024-01-01", end_time="2026-12-31", freq='day')
    df.columns = all_names

    # 3. 数据清洗
    df = df.dropna()
    if df.empty:
        print("[Train v17] 错误：清洗后数据为空！请检查数据源或时间范围。")
        return

    # 划分特征和目标
    feature_cols = list(features.keys())
    X = df[feature_cols]
    y = df["Label"]

    # 划分训练集和测试集（按时间简单划分：最后30天为测试集）
    dates = df.index.get_level_values('datetime')
    unique_dates = dates.unique()
    if len(unique_dates) > 30:
        split_date = unique_dates[-30]
    else:
        split_date = unique_dates[-1]
    
    train_mask = dates < split_date
    test_mask = dates >= split_date

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    print(f"[Train v17] 训练集样本数: {len(X_train)}, 测试集样本数: {len(X_test)}")

    # 4. 训练 LightGBM 模型
    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    params = {
        'objective': 'regression',
        'metric': 'rmse',
        'boosting_type': 'gbdt',
        'learning_rate': 0.05,
        'num_leaves': 31,
        'max_depth': -1,
        'verbose': -1,
        'seed': 42
    }

    print("[Train v17] 开始训练 LightGBM 模型...")
    model = lgb.train(
        params,
        train_data,
        num_boost_round=500,
        valid_sets=[train_data, valid_data],
        callbacks=[lgb.early_stopping(stopping_rounds=50)]
    )

    # 5. 保存模型和特征配置
    os.makedirs("model_output", exist_ok=True)
    model_path = "model_output/lgb_model_v17.pkl"
    features_path = "model_output/features_v17.json"

    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    with open(features_path, 'w') as f:
        json.dump(feature_cols, f)

    print(f"\n[Train v17] 训练完成！")
    print(f"[Train v17] 模型已保存至: {model_path}")
    print(f"[Train v17] 特征已保存至: {features_path}")

if __name__ == "__main__":
    main()
