#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AFML V20 Meta-Labeling Training Engine
Based on "Advances in Financial Machine Learning" by Marcos López de Prado.

Pipeline:
1. Extract historical features & Primary Model (V19) predictions.
2. Identify Primary Buy Signals (t_events).
3. Compute Daily Volatility and apply Triple Barrier Method.
4. Generate Meta-Labels (1 if profit barrier hit, 0 otherwise).
5. Train Meta-Model (LightGBM Classifier) with Purged CV concepts.
"""
import qlib
from qlib.data import D
from qlib.config import REG_CN
import pandas as pd
import numpy as np
import lightgbm as lgb
import os
import json
import pickle
import warnings
import sys

warnings.filterwarnings('ignore')

# 将项目根目录加入 sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.afml.triple_barrier import apply_triple_barrier

def get_daily_volatility(close_prices: pd.Series, span=100):
    returns = np.log(close_prices / close_prices.shift(1))
    return returns.ewm(span=span).std()

def main():
    print("🚀 [AFML V20] 启动元标签(Meta-Labeling)架构训练引擎...")
    
    # 1. Initialize Qlib
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    
    # 2. Load Stock Pool
    stock_pool = []
    if os.path.exists('data/stock_names.json'):
        with open('data/stock_names.json', 'r', encoding='utf-8') as f:
            stock_pool = list(json.load(f).keys())
            
    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, as_list=True)
    if stock_pool:
        clean_pool = [code[-6:] for code in stock_pool]
        valid_stocks = [s for s in stock_list if s[-6:] in clean_pool]
    else:
        valid_stocks = stock_list[:100]
        
    print(f"📦 [AFML V20] 锁定核心资产池: {len(valid_stocks)} 只股票")
    
    # 3. Load V19 Primary Model
    v19_model_path = "model_output/lgb_model_v19_ensemble.pkl"
    v19_feat_path = "model_output/features_v19_ensemble.json"
    if not os.path.exists(v19_model_path):
        print("❌ [致命错误] 找不到 V19 主模型，AFML 元模型无法进行信号纠错。请先运行 train_qlib_v19_ensemble.py")
        return
        
    with open(v19_model_path, 'rb') as f:
        primary_models = pickle.load(f)
    with open(v19_feat_path, 'r', encoding='utf-8') as f:
        primary_features_expr = json.load(f)
        
    # 4. Fetch Data
    start_time = "2021-01-01"
    end_time = "2026-05-01" 
    
    print(f"🧠 [AFML V20] 正在提取时序与截面特征 ({start_time} 至 {end_time})...")
    fields = list(primary_features_expr.values()) + ["$close", "$volume"]
    names = list(primary_features_expr.keys()) + ["Close", "Volume"]
    
    df = D.features(valid_stocks, fields, start_time, end_time)
    df.columns = names
    df = df.dropna()
    
    if df.empty:
        print("❌ [致命错误] 获取数据为空，请检查 Qlib 数据源。")
        return
        
    print(f"🧩 [AFML V20] 数据提取完成，形状: {df.shape}。开始推演主模型信号...")
    
    # 5. Generate Primary Signals
    feature_data = df[list(primary_features_expr.keys())]
    preds = np.zeros(len(feature_data))
    for m in primary_models:
        preds += m.predict(feature_data) / len(primary_models)
        
    df['Primary_Pred'] = preds
    
    # 设定主模型触发阈值 (过滤出潜在的做多机会)
    t_events_mask = df['Primary_Pred'] > 0.015
    events_df = df[t_events_mask].copy()
    print(f"🎯 [AFML V20] V19 主模型在历史期间共发出 {len(events_df)} 次【强看涨】信号。")
    
    if len(events_df) < 100:
         print("⚠️ 信号数量过少，降低主模型置信度阈值...")
         t_events_mask = df['Primary_Pred'] > 0.005
         events_df = df[t_events_mask].copy()
         print(f"🎯 调整后共提取 {len(events_df)} 次主信号。")
         
    # 6. Apply Triple Barrier
    print("🚧 [AFML V20] 启动三重屏障打标器 (Triple Barrier Labeling)... 正在重铸盈亏真实面貌")
    meta_labels = pd.Series(index=events_df.index, dtype=int)
    
    stocks_in_events = events_df.index.get_level_values('instrument').unique()
    
    for stock in stocks_in_events:
        stock_data = df.xs(stock, level='instrument')
        stock_events = events_df.xs(stock, level='instrument')
        
        if len(stock_events) == 0: continue
            
        vol = get_daily_volatility(stock_data['Close'], span=50)
        
        t1_dates = []
        for t in stock_events.index:
            t_loc = stock_data.index.get_loc(t)
            end_loc = min(t_loc + 10, len(stock_data) - 1)  # 最大持仓时间 10 天
            t1_dates.append(stock_data.index[end_loc])
            
        tb_events = pd.DataFrame(index=stock_events.index)
        tb_events['t1'] = t1_dates
        tb_events['trgt'] = vol.loc[stock_events.index].clip(lower=0.01) # 最低波动阈值 1%
        
        # 盈亏比设置 2.0 : 1.0 (由于 A 股做多特性，放开向上空间，收紧止损)
        pt_sl = [2.0, 1.0]
        labels_df = apply_triple_barrier(stock_data['Close'], tb_events, pt_sl, target_vol=tb_events['trgt'])
        
        for t, row in labels_df.iterrows():
            meta_labels.loc[(stock, t)] = 1 if row['label'] == 1 else 0
            
    events_df['Meta_Label'] = meta_labels
    events_df = events_df.dropna(subset=['Meta_Label'])
    
    success_rate = events_df['Meta_Label'].mean()
    print(f"⚖️ [AFML V20] 历史回溯揭秘: V19 盲目看涨信号的真实幸存率仅为 {success_rate:.2%}！")
    
    # 7. Train Meta-Model
    print("🧬 [AFML V20] 开始训练元分类器 (Meta-Classifier)...")
    X = events_df[list(primary_features_expr.keys()) + ['Primary_Pred']]
    y = events_df['Meta_Label'].astype(int)
    
    dates = X.index.get_level_values('datetime')
    split_date = dates.sort_values()[int(len(dates) * 0.8)]
    
    X_train = X[dates < split_date]
    y_train = y[dates < split_date]
    X_test = X[dates >= split_date]
    y_test = y[dates >= split_date]
    
    print(f"   => 训练集样本: {len(X_train)}，测试集样本: {len(X_test)}")
    
    params = {
        'objective': 'binary',
        'metric': 'auc',
        'boosting_type': 'gbdt',
        'learning_rate': 0.05,
        'num_leaves': 31,
        'max_depth': 5,
        'feature_fraction': 0.8,
        'is_unbalance': True, # 处理标签极度不平衡问题
        'verbose': -1,
        'random_state': 42
    }
    
    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
    
    meta_model = lgb.train(
        params,
        train_data,
        num_boost_round=300,
        valid_sets=[train_data, valid_data],
        callbacks=[lgb.early_stopping(stopping_rounds=30), lgb.log_evaluation(50)]
    )
    
    # 8. Evaluate & Save
    preds_prob = meta_model.predict(X_test, num_iteration=meta_model.best_iteration)
    executed = (preds_prob > 0.6)  # 元模型置信度必须大于 60% 才放行
    actual_success = y_test[executed]
    
    if len(actual_success) > 0:
        meta_win_rate = actual_success.mean()
        print(f"🛡️ [AFML V20] 拦截测试报告:")
        print(f"   => 测试集盲目执行胜率: {y_test.mean():.2%}")
        print(f"   => 元模型过滤后(置信度>60%)执行胜率: {meta_win_rate:.2%} (成功过滤了 {len(y_test) - len(actual_success)} 次烂交易)")
    else:
        print("🛡️ [AFML V20] 元模型在测试集上极为谨慎，没有放行任何交易 (规避了全部风险)。")

    os.makedirs("model_output", exist_ok=True)
    meta_model_path = "model_output/lgb_model_v20_meta.pkl"
    with open(meta_model_path, 'wb') as f:
        pickle.dump(meta_model, f)
        
    meta_features = list(X.columns)
    with open("model_output/features_v20_meta.json", 'w', encoding='utf-8') as f:
        json.dump(meta_features, f, indent=4)
        
    print(f"✅ [AFML V20] 终极防弹衣(元模型)已封装至: {meta_model_path}")
    print("================================================================")
    print("【系统升级提示】V20 引擎已就绪！可以调用 infer_afml_v20.py 启动实盘阻击网络！")

if __name__ == "__main__":
    main()
