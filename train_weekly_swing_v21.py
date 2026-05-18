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
import time
import traceback

def compute_triple_barrier(row):
    tp = 0.08
    sl = -0.05
    for i in range(1, 6):
        h = row.get(f'H{i}', 0)
        l = row.get(f'L{i}', 0)
        c = row.get(f'C{i}', 0)
        
        # Conservative: if both hit in the same day, assume stop loss hit first
        if h >= tp and l <= sl:
            return 0
        elif h >= tp:
            return 1
        elif l <= sl:
            return 0
            
    # If no barrier hit, check final close return
    c5 = row.get('C5', 0)
    if c5 > 0.005:  # Cover basic costs
        return 1
    return 0

def main():
    os.makedirs("model_output", exist_ok=True)
    status_file = "model_output/v21_train_status.json"
    
    def update_status(status, progress, msg):
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump({"status": status, "progress": progress, "message": msg}, f, ensure_ascii=False)

    try:
        update_status("running", 5, "初始化 Qlib 数据源...")
        provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
        qlib.init(provider_uri=provider_uri, region=REG_CN)
        
        instruments = D.instruments(market='all')
        
        features = {
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

        labels = {
            "H1": "Ref($high, -1)/$close - 1", "L1": "Ref($low, -1)/$close - 1", "C1": "Ref($close, -1)/$close - 1",
            "H2": "Ref($high, -2)/$close - 1", "L2": "Ref($low, -2)/$close - 1", "C2": "Ref($close, -2)/$close - 1",
            "H3": "Ref($high, -3)/$close - 1", "L3": "Ref($low, -3)/$close - 1", "C3": "Ref($close, -3)/$close - 1",
            "H4": "Ref($high, -4)/$close - 1", "L4": "Ref($low, -4)/$close - 1", "C4": "Ref($close, -4)/$close - 1",
            "H5": "Ref($high, -5)/$close - 1", "L5": "Ref($low, -5)/$close - 1", "C5": "Ref($close, -5)/$close - 1"
        }

        all_exprs = list(features.values()) + list(labels.values())
        all_cols = list(features.keys()) + list(labels.keys())

        update_status("running", 15, "提取特征与未来 5 日价格标签数据...")
        start_time = "2021-01-01"
        end_time = "2024-12-31"  # Train period
        
        df = D.features(instruments, all_exprs, start_time=start_time, end_time=end_time, freq='day')
        df.columns = all_cols
        df = df.dropna()
        
        update_status("running", 30, "计算 Triple Barrier 标签...")
        df['target'] = df.apply(compute_triple_barrier, axis=1)

        feature_cols = list(features.keys())
        X = df[feature_cols]
        y = df['target']
        
        update_status("running", 45, "标准化横截面特征...")
        def z_score(x):
            return (x - x.mean()) / x.std().replace(0, 1e-8)
            
        X_norm = X.groupby(level='datetime', group_keys=False).apply(z_score).fillna(0)

        dates = X_norm.index.get_level_values('datetime').unique()
        train_dates = set(dates[:int(len(dates)*0.8)])
        val_dates = set(dates[int(len(dates)*0.8):])
        
        train_mask = X_norm.index.get_level_values('datetime').isin(train_dates)
        val_mask = X_norm.index.get_level_values('datetime').isin(val_dates)

        X_train, y_train = X_norm[train_mask], y[train_mask]
        X_val, y_val = X_norm[val_mask], y[val_mask]

        update_status("running", 60, "训练 Primary Model (LightGBM)...")
        lgb_train = lgb.Dataset(X_train, y_train)
        lgb_val = lgb.Dataset(X_val, y_val, reference=lgb_train)
        
        params_primary = {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'learning_rate': 0.05,
            'num_leaves': 31,
            'max_depth': 5,
            'feature_fraction': 0.8,
            'seed': 42,
            'verbose': -1
        }
        
        model_primary = lgb.train(
            params_primary, lgb_train, num_boost_round=300,
            valid_sets=[lgb_train, lgb_val],
            callbacks=[lgb.early_stopping(stopping_rounds=30)]
        )

        update_status("running", 75, "生成 Primary 预测与训练 Meta Model...")
        pred_train = model_primary.predict(X_train)
        pred_val = model_primary.predict(X_val)
        
        threshold = 0.55
        meta_train_idx = pred_train > threshold
        meta_val_idx = pred_val > threshold
        
        X_meta_train = X_train[meta_train_idx]
        y_meta_train = y_train[meta_train_idx]
        
        X_meta_val = X_val[meta_val_idx]
        y_meta_val = y_val[meta_val_idx]
        
        if len(X_meta_train) > 100:
            meta_lgb_train = lgb.Dataset(X_meta_train, y_meta_train)
            meta_lgb_val = lgb.Dataset(X_meta_val, y_meta_val, reference=meta_lgb_train)
            
            params_meta = params_primary.copy()
            params_meta['learning_rate'] = 0.03
            
            model_meta = lgb.train(
                params_meta, meta_lgb_train, num_boost_round=200,
                valid_sets=[meta_lgb_train, meta_lgb_val],
                callbacks=[lgb.early_stopping(stopping_rounds=20)]
            )
        else:
            model_meta = model_primary  # fallback

        update_status("running", 90, "保存模型与特征...")
        
        with open("model_output/lgb_model_v21_weekly_primary.pkl", "wb") as f:
            pickle.dump(model_primary, f)
            
        with open("model_output/lgb_model_v21_weekly_meta.pkl", "wb") as f:
            pickle.dump(model_meta, f)
            
        with open("model_output/features_v21_weekly.json", "w", encoding='utf-8') as f:
            json.dump(list(features.keys()), f, ensure_ascii=False, indent=4)
            
        report = {
            "model": "v21_weekly",
            "period": {"start": start_time, "end": end_time},
            "primary_auc": model_primary.best_score['valid_1']['auc'] if 'valid_1' in model_primary.best_score else 0,
            "meta_auc": model_meta.best_score['valid_1']['auc'] if model_meta != model_primary and 'valid_1' in model_meta.best_score else 0,
            "primary_threshold": threshold,
            "train_samples": len(X_train),
            "meta_train_samples": len(X_meta_train),
            "target_1_ratio": float(y.mean()),
            "meta_target_1_ratio": float(y_meta_train.mean()) if len(y_meta_train) > 0 else 0
        }
        
        with open("model_output/model_report_v21_weekly.json", "w", encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=4)
            
        update_status("running", 95, "正在生成全市场横截面预测数据...")
        import subprocess
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        subprocess.run(["uv", "run", "python", "infer_weekly_swing_v21.py"], env=env, check=True)
            
        update_status("success", 100, "模型训练与预测全部完成")
        print("Training successfully finished.")
        
    except Exception as e:
        traceback.print_exc()
        update_status("error", 100, f"训练失败: {str(e)}")

if __name__ == "__main__":
    main()