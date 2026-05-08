#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 Mock 模型 (轻量级绕过方案)
用于在不进行完整历史数据训练的情况下，直接生成合法的 v16c 模型文件，
让仪表盘的 "ML预测" 模块可以直接跑起来。
"""
import os
import json
import pickle
import numpy as np
import lightgbm as lgb

def generate_mock_model():
    print("开始生成 Mock 模型...")
    os.makedirs("model_output", exist_ok=True)
    
    # 伪造 42 个特征名称 (必须和 app.py 中保持绝对一致)
    raw_features = ['mom_5d','mom_10d','mom_20d','mom_60d','mom_accel',
                    'dist_sma20','dist_sma60','vol_5d','vol_20d','vol_ratio',
                    'turnover_ratio','vol_price_corr','macd_hist','rsi_14',
                    'bb_pos','atr_ratio','body_ratio','ret_1d','ret_3d',
                    'high_low_range','gap','sharpe_20d','decay_mom','drawdown_20d',
                    'up_streak','down_streak','vol_price_div']
    
    cs_cols = [f'{f}_cs' for f in raw_features]
    sector_cols = [f'{f}_sector' for f in ['mom_20d','rsi_14','turnover_ratio','macd_hist']]
    rank_cols = [f'{f}_rank' for f in ['mom_5d','mom_20d','mom_60d','rsi_14','turnover_ratio','macd_hist','sharpe_20d']]
    sector_rank_cols = [f'{f}_sector_rank' for f in ['mom_20d','rsi_14']]
    revert_cols = [f'{f}_revert' for f in ['mom_20d','rsi_14']]
    
    features = cs_cols + sector_cols + rank_cols + sector_rank_cols + revert_cols
    
    # 保存特征文件
    with open('model_output/features_v16.json', 'w') as f:
        json.dump(features, f)
    print(f"OK 生成伪造特征: {len(features)} 个")

    # 训练一个极其简单的伪造 LGBM 模型
    X_dummy = np.random.rand(10, len(features))
    # 目标值制造一些随机波动，让预测结果在 -5% 到 +5% 之间
    y_dummy = np.random.uniform(-0.05, 0.05, 10)
    
    # 模拟 v16c 的 3个集成模型
    models = []
    for _ in range(3):
        model = lgb.LGBMRegressor(n_estimators=2, num_leaves=3)
        model.fit(X_dummy, y_dummy)
        models.append(model)
        
    model_data = {
        'models': models,
        'n_models': 3,
        'feature_cols': features,
        'is_mock': True
    }
    
    with open('model_output/lgb_model_v16.pkl', 'wb') as f:
        pickle.dump(model_data, f)
    print("OK 生成伪造模型: v16c (Mock)")
    print("Done! 现在可以直接运行 python app.py，ML预测面板已经活了。")

if __name__ == "__main__":
    generate_mock_model()
