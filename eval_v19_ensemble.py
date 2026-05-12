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

    with open('model_output/lgb_model_v19_ensemble.pkl', 'rb') as f:
        models = pickle.load(f)
    
    with open('model_output/features_v19_ensemble.json', 'r') as f:
        all_names = json.load(f)

    # Reconstruct the feature dict
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
    label = {"Label": "Ref($close, -1) / $close - 1"}

    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, as_list=True)

    all_fields = list(features.values()) + list(label.values())
    all_names_with_label = list(features.keys()) + list(label.keys())

    df = D.features(stock_list, all_fields, start_time="2026-03-01", end_time="2026-05-10", freq='day')
    df.columns = all_names_with_label
    df = df.dropna()

    def cross_sectional_norm(group):
        group_features = group[all_names]
        lower = group_features.quantile(0.01)
        upper = group_features.quantile(0.99)
        clipped = group_features.clip(lower=lower, upper=upper, axis=1)
        mean = clipped.mean()
        std = clipped.std().replace(0, 1e-8)
        group[all_names] = (clipped - mean) / std
        return group

    df_norm = df.groupby(level='datetime', group_keys=False).apply(cross_sectional_norm)
    df[all_names] = df_norm[all_names]

    # 集成预测：将5个模型的预测结果平均
    preds = np.zeros(len(df))
    for m in models:
        preds += m.predict(df[all_names])
    preds /= len(models)
    
    df['Predict'] = preds

    total_samples = len(df)
    
    # 2. Top 10% predictions
    p90 = df['Predict'].quantile(0.9)
    top_df = df[df['Predict'] >= p90]
    top_win = (top_df['Label'] > 0).mean()
    top_mean_ret = top_df['Label'].mean()

    # 3. Top 30% predictions
    p70 = df['Predict'].quantile(0.7)
    mid_df = df[(df['Predict'] >= p70) & (df['Predict'] < p90)]
    mid_win = (mid_df['Label'] > 0).mean()

    print(f"--- V19 Ensemble 近期测试集评估 (2026-03-01 至今) ---")
    print(f"总评估样本: {total_samples}")
    print(f"前 10%「强烈看涨」信号胜率: {top_win * 100:.2f}%")
    print(f"前 10%「强烈看涨」平均次日收益: {top_mean_ret * 100:.4f}%")
    print(f"前 10%-30%「看涨」信号胜率: {mid_win * 100:.2f}%")

if __name__ == '__main__':
    main()