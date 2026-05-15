#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AFML V20 Online Inference Engine
Filters V19 Primary Signals using V20 Meta-Model and generates the final Watchlist.
"""
import qlib
from qlib.data import D
from qlib.config import REG_CN
import pandas as pd
import numpy as np
import os
import json
import pickle
import sys

def main():
    print("🚀 [AFML V20] 启动元模型在线阻击引擎 (Meta-Inference)...")
    
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    
    # 1. 验证双层网络模型是否存在
    primary_model_path = "model_output/lgb_model_v19_ensemble.pkl"
    primary_feat_path = "model_output/features_v19_ensemble.json"
    meta_model_path = "model_output/lgb_model_v20_meta.pkl"
    meta_feat_path = "model_output/features_v20_meta.json"
    
    if not (os.path.exists(primary_model_path) and os.path.exists(meta_model_path)):
        print("❌ [AFML V20] 找不到主模型或元模型，请先运行 train_afml_v20.py")
        return
        
    with open(primary_model_path, 'rb') as f:
        primary_models = pickle.load(f)
    with open(primary_feat_path, 'r', encoding='utf-8') as f:
        primary_features_expr = json.load(f)
        
    with open(meta_model_path, 'rb') as f:
        meta_model = pickle.load(f)
    with open(meta_feat_path, 'r', encoding='utf-8') as f:
        meta_features = json.load(f)
        
    # 2. 划定侦察范围 (过滤停牌与 ST)
    stock_pool = {}
    if os.path.exists('data/stock_names.json'):
        with open('data/stock_names.json', 'r', encoding='utf-8') as f:
            stock_pool = json.load(f)
            
    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, as_list=True)
    valid_stocks = [s for s in stock_list if s[-6:] in [k[-6:] for k in stock_pool.keys()]]
    
    print(f"📦 [AFML V20] 开始提取 {len(valid_stocks)} 只标的最新高维特征...")
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=15)).strftime("%Y-%m-%d")
    
    df = D.features(valid_stocks, list(primary_features_expr.values()), start_date, end_date)
    df.columns = list(primary_features_expr.keys())
    df = df.dropna()
    
    if df.empty:
        print("❌ [AFML V20] 提取特征为空，无法进行预测。")
        return
        
    # 截取最新一天的数据作为当日预测截面
    latest_date = df.index.get_level_values('datetime').max()
    df_latest = df.xs(latest_date, level='datetime').copy()
    
    # 3. 主模型 (V19) 进行初步筛选
    print(f"⏳ [AFML V20] {latest_date.strftime('%Y-%m-%d')} - 主引擎 (V19) 第一遍扫描...")
    preds = np.zeros(len(df_latest))
    for m in primary_models:
        preds += m.predict(df_latest[list(primary_features_expr.keys())]) / len(primary_models)
        
    df_latest['Primary_Pred'] = preds
    df_latest['stock_code'] = df_latest.index
    
    # 4. 元模型 (V20) 进行二次阻击拦截
    # 动态阈值：选取预测收益率排名前 15% 的标的进入元模型雷达
    threshold = np.percentile(df_latest['Primary_Pred'], 85)
    candidates = df_latest[df_latest['Primary_Pred'] >= threshold].copy()
    print(f"🔍 [AFML V20] 动态阈值 ({threshold:.4f}) 初筛发现 {len(candidates)} 只主模型看涨标的，启动元模型 (Meta-Model) 狙击网...")
    
    if len(candidates) > 0:
        meta_X = candidates[meta_features]
        # 元模型输出的是击中“止盈屏障”的概率
        meta_prob = meta_model.predict(meta_X)
        candidates['Meta_Score'] = meta_prob
    else:
        candidates['Meta_Score'] = []
        
    # 5. 格式化并输出到决策 JSON
    results = {}
    for _, row in candidates.iterrows():
        code = row['stock_code']
        pure_code = code[-6:]
        
        # 解析股票名称
        name = pure_code
        for k, v in stock_pool.items():
            if k[-6:] == pure_code:
                name = v
                break
                
        meta_score = float(row.get('Meta_Score', 0))
        # 仅保留元模型置信度超过 40% 的标的
        if meta_score > 0.40:
            results[pure_code] = {
                "name": name,
                "predicted_return": float(row['Primary_Pred']),
                "meta_score": meta_score,
                "up_probability": meta_score * 100 # 将元置信度映射为界面的胜率
            }
        
    # 按 AFML 元置信度 (Meta_Score) 降序排列
    sorted_results = {k: v for k, v in sorted(results.items(), key=lambda item: item[1]['meta_score'], reverse=True)}
    
    # 封装为前端需要的格式
    output_data = {
        "data": sorted_results,
        "_meta": {
            "model_version": "AFML v20",
            "stocks": len(sorted_results)
        }
    }
    
    out_file = "model_output/daily_predictions_v20.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print(f"✅ [AFML V20] 在线推理完成，拦截无效信号，最终剩余 {len(sorted_results)} 只绝佳标的！")
    print(f"📄 结果已保存至: {out_file}")
    
    print("🏆 [AFML V20] 猎物锁定 Top 3:")
    for i, (k, v) in enumerate(list(sorted_results.items())[:3]):
        print(f"  {i+1}. {k} {v['name']} | V19原始动能: {v['predicted_return']*100:.2f}% | AFML元置信度: {v['meta_score']*100:.1f}%")

if __name__ == "__main__":
    main()
