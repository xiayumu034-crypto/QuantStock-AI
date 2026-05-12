import pandas as pd
import numpy as np
import lightgbm as lgb
import json
import pickle
import qlib
from qlib.data import D
from qlib.config import REG_CN
import os

def main():
    # Initialize Qlib
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)

    # Load model and features
    with open('model_output/lgb_model_v18.pkl', 'rb') as f:
        model = pickle.load(f)

    with open('model_output/features_v18.json', 'r') as f:
        features = json.load(f)

    # Get all stocks
    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, start_time='2020-01-01', as_list=True)

    # The actual features used in v18 train
    df = D.features(stock_list, features, start_time='2023-01-01', end_time='2026-05-10')
    df_label = D.features(stock_list, ['Ref($close, -1) / $close - 1'], start_time='2023-01-01', end_time='2026-05-10')
    df_label.columns = ['label']

    df = df.join(df_label).dropna()

    # predict
    preds = model.predict(df[features])
    df['predict'] = preds

    # win rate: predict > 0 and label > 0 OR predict < 0 and label < 0
    df['correct'] = np.sign(df['predict']) == np.sign(df['label'])

    total = len(df)
    win_rate = df['correct'].mean()
    print(f"Total samples: {total}")
    print(f"Directional Win Rate: {win_rate * 100:.2f}%")

    # Top 10% prediction win rate
    p90 = df['predict'].quantile(0.9)
    top_df = df[df['predict'] >= p90]
    top_win_rate = (top_df['label'] > 0).mean()
    print(f"Top 10% (Strong Buy) Win Rate (Actual > 0): {top_win_rate * 100:.2f}%")

    # Expected return of top 10%
    print(f"Top 10% Average Next-Day Return: {top_df['label'].mean() * 100:.2f}%")

if __name__ == '__main__':
    main()
