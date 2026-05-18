#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest Engine for V19/V20 System Validation.
Compares the performance of the Primary Model (V19) alone 
against the V19 + V20 Meta-Filtering system.
"""
import qlib
from qlib.data import D
from qlib.config import REG_CN
import pandas as pd
import numpy as np
import pickle
import json
import os
import sys
from datetime import datetime

# 设置编码，防止 Windows 下 emoji 导致崩溃
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def calculate_portfolio_returns(signals, price_df, top_n=5):
    """
    signals: DataFrame with MultiIndex [instrument, datetime], column 'score'
    price_df: DataFrame with MultiIndex [instrument, datetime], column 'next_ret'
    """
    # Swap levels to get datetime first for iteration
    signals = signals.swaplevel().sort_index()
    price_df = price_df.swaplevel().sort_index()
    
    portfolio_rets = []
    dates = signals.index.get_level_values(0).unique().sort_values()
    
    for date in dates:
        day_signals = signals.loc[date].sort_values('score', ascending=False)
        top_stocks = day_signals.head(top_n).index.tolist()
        
        if not top_stocks:
            portfolio_rets.append(0)
            continue
            
        # Get next day returns for these stocks
        try:
            day_rets = price_df.loc[date].loc[top_stocks]['next_ret']
            portfolio_rets.append(day_rets.mean())
        except:
            portfolio_rets.append(0)
            
    return pd.Series(portfolio_rets, index=dates)

def main():
    print("🚀 [系统验证] 启动 V19 vs V20 历史性能对冲验证...")
    
    # 1. Init
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    
    # 2. Models
    v19_path = "model_output/lgb_model_v19_ensemble.pkl"
    v20_path = "model_output/lgb_model_v20_meta.pkl"
    if not (os.path.exists(v19_path) and os.path.exists(v20_path)):
        print("❌ 错误: 找不到模型文件。请先运行模型训练。")
        return

    with open(v19_path, 'rb') as f: v19_model = pickle.load(f)
    with open(v20_path, 'rb') as f: v20_model = pickle.load(f)
    
    # 3. Test Period
    start_date = "2024-01-01"
    end_date = "2025-01-01"
    
    import sys
    if len(sys.argv) >= 3:
        start_date = sys.argv[1]
        end_date = sys.argv[2]
        print(f"🔧 自定义回测区间: {start_date} 至 {end_date}")
    
    # 4. Fetch Data (Subsample for speed)
    print(f"📈 正在提取 {start_date} 至 {end_date} 的回测数据...")
    
    # 使用 all 市场但限制在 stock_names.json 里的票
    stock_pool = []
    if os.path.exists('data/stock_names.json'):
        with open('data/stock_names.json', 'r', encoding='utf-8') as f:
            stock_pool = list(json.load(f).keys())
    
    if stock_pool:
        # qlib instruments list format: Uppercase with prefix
        all_inst = set(D.list_instruments(D.instruments(market='all'), as_list=True))
        instruments = []
        for s in stock_pool:
            # Try adding SH/SZ
            for prefix in ["SH", "SZ", "BJ"]:
                code = prefix + s if not s.startswith(prefix) else s.upper()
                if code in all_inst:
                    instruments.append(code)
                    break
    else:
        instruments = D.list_instruments(D.instruments(market='all'), as_list=True)[:50]
    
    if not instruments:
        print("❌ 错误: 资产池为空，无法进行回测。")
        return
        
    fields = ["Ref($close, -1)/$close - 1", "$close", "$volume"]
    df = D.features(instruments, fields, start_date, end_date)
    df.columns = ["next_ret", "close", "volume"]
    df = df.dropna()
    
    # Simple Technical Features for Meta Model (matches training)
    df['mom_5'] = df['close'].groupby('instrument').transform(lambda x: x.pct_change(5))
    df['vol_10'] = df['close'].groupby('instrument').transform(lambda x: x.pct_change().rolling(10).std())
    df = df.dropna()
    
    # 5. Generate Predictions
    print("🧠 正在生成历史预测轨迹...")
    # Read V19 Feature expressions
    with open("model_output/features_v19_ensemble.json", 'r', encoding='utf-8') as f:
        v19_feat_expr = json.load(f)
    
    v19_fields = list(v19_feat_expr.values())
    v19_data = D.features(instruments, v19_fields, start_date, end_date)
    v19_data = v19_data.loc[df.index]
    
    # Predict V19 (Handle ensemble)
    if isinstance(v19_model, list):
        v19_preds = []
        for m in v19_model:
            v19_preds.append(m.predict(v19_data))
        df['Primary_Pred'] = np.mean(v19_preds, axis=0)
    else:
        df['Primary_Pred'] = v19_model.predict(v19_data)
    
    # Predict V20 (Meta)
    # v19_data contains the 26 features. We need to add Primary_Pred to match the 27 training features.
    meta_features = v19_data.copy()
    meta_features['Primary_Pred'] = df['Primary_Pred']
    
    # The order of columns in meta_features MUST match features_v20_meta.json
    with open("model_output/features_v20_meta.json", 'r', encoding='utf-8') as f:
        meta_feat_names = json.load(f)
    
    # Map the current column names to the expected ones if they differ
    # Looking at train_afml_v20.py, it used names from primary_features_expr.keys()
    # Let's ensure column names match exactly.
    meta_features.columns = list(v19_feat_expr.keys()) + ['Primary_Pred']
    meta_features = meta_features[meta_feat_names]
    
    df['v20_prob'] = v20_model.predict(meta_features)
    
    # 6. Backtest Strategies
    print("📊 模拟账户运行中...")
    
    # Strategy 1: V19 Only (Baseline)
    v19_signals = df[['Primary_Pred']].rename(columns={'Primary_Pred': 'score'})
    v19_rets = calculate_portfolio_returns(v19_signals, df[['next_ret']])
    
    # Strategy 2: V19 + V20 Filter
    # Only consider stocks where V20 thinks the primary model is correct (prob > 0.6)
    v20_filtered = df.copy()
    v20_filtered.loc[df['v20_prob'] < 0.55, 'Primary_Pred'] = -999
    v20_signals = v20_filtered[['Primary_Pred']].rename(columns={'Primary_Pred': 'score'})
    v20_rets = calculate_portfolio_returns(v20_signals, df[['next_ret']])
    
    # Benchmark (Market mean)
    mkt_rets = df['next_ret'].groupby('datetime').mean()
    
    # 7. Metrics
    def get_stats(rets, name):
        cum_ret = (1 + rets).prod() - 1
        ann_ret = (1 + cum_ret) ** (252 / len(rets)) - 1
        sharpe = np.sqrt(252) * rets.mean() / rets.std() if rets.std() != 0 else 0
        mdd = (1 - (1 + rets).cumprod() / (1 + rets).cumprod().cummax()).max()
        return {"name": name, "cum_ret": f"{cum_ret:.2%}", "sharpe": f"{sharpe:.2f}", "mdd": f"{mdd:.2%}"}

    results = [
        get_stats(v19_rets, "V19 (Primary Only)"),
        get_stats(v20_rets, "V20 (AFML Meta-Labeling)"),
        get_stats(mkt_rets, "Market (HS300 Mean)")
    ]
    
    # Chart Data
    chart_data = {
        "dates": pd.to_datetime(v19_rets.index).strftime("%Y-%m-%d").tolist(),
        "v19": ((1 + v19_rets).cumprod() - 1).tolist(),
        "v20": ((1 + v20_rets).cumprod() - 1).tolist(),
        "market": ((1 + mkt_rets).cumprod() - 1).tolist()
    }
    
    report = {
        "summary": results,
        "chart": chart_data,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    os.makedirs("model_output", exist_ok=True)
    with open("model_output/backtest_report_v20.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=4)
        
    print("\n✅ [验证完成] 回测报告已生成至 model_output/backtest_report_v20.json")
    for r in results:
        print(f"🔹 {r['name']}: 收益 {r['cum_ret']}, 夏普 {r['sharpe']}, 最大回撤 {r['mdd']}")

if __name__ == "__main__":
    main()
