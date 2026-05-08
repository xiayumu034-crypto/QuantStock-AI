import pickle, json, numpy as np
from lightgbm import LGBMRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error
import pandas as pd

# ========== 加载数据 ==========
df = pd.read_parquet('data_cache/v12_data.parquet')
print(f'加载数据: {len(df)} 条, {df["code"].nunique()} 只股票')
df['日期'] = pd.to_datetime(df['日期'])
df = df.sort_values(['code', '日期']).reset_index(drop=True)

# ========== 生成原始特征 ==========
all_frames = []
for code, gdf in df.groupby('code'):
    gdf = gdf.copy()
    c, h, l, o, v = gdf['收盘'].astype(float), gdf['最高'].astype(float), gdf['最低'].astype(float), gdf['开盘'].astype(float), gdf['成交量'].astype(float)
    ret1 = c.pct_change(1)
    
    gdf['mom_5d'] = c.pct_change(5)
    gdf['mom_10d'] = c.pct_change(10)
    gdf['mom_20d'] = c.pct_change(20)
    gdf['mom_60d'] = c.pct_change(60)
    gdf['mom_accel'] = gdf['mom_5d'] - gdf['mom_20d']
    
    sma20 = c.rolling(20).mean()
    sma60 = c.rolling(60).mean()
    gdf['dist_sma20'] = (c - sma20) / (sma20 + 1e-10)
    gdf['dist_sma60'] = (c - sma60) / (sma60 + 1e-10)
    
    gdf['vol_5d'] = ret1.rolling(5).std()
    gdf['vol_20d'] = ret1.rolling(20).std()
    gdf['vol_ratio'] = gdf['vol_5d'] / (gdf['vol_20d'] + 1e-10)
    vol_ma5 = v.rolling(5).mean()
    vol_ma20 = v.rolling(20).mean()
    gdf['turnover_ratio'] = vol_ma5 / (vol_ma20 + 1e-10)
    gdf['vol_price_corr'] = c.rolling(10).corr(v)
    
    ema12 = c.ewm(span=12).mean()
    ema26 = c.ewm(span=26).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9).mean()
    gdf['macd_hist'] = 2 * (dif - dea) / (c + 1e-10)
    
    delta = c.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    gdf['rsi_14'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
    
    bb_std = c.rolling(20).std()
    gdf['bb_pos'] = (c - sma20) / (2 * bb_std + 1e-10)
    
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    gdf['atr_ratio'] = tr.rolling(14).mean() / (c + 1e-10)
    gdf['body_ratio'] = abs(c - o) / (h - l + 1e-10)
    
    gdf['ret_1d'] = ret1
    gdf['ret_3d'] = c.pct_change(3)
    gdf['high_low_range'] = (h - l) / (c + 1e-10)
    gdf['gap'] = (o - c.shift(1)) / (c.shift(1) + 1e-10)
    
    gdf['sharpe_20d'] = gdf['mom_20d'] / (gdf['vol_20d'] + 1e-10)
    gdf['decay_mom'] = 0.4 * gdf['mom_5d'] + 0.3 * c.pct_change(10) + 0.2 * c.pct_change(15) + 0.1 * gdf['mom_20d']
    rolling_max = c.rolling(20).max()
    gdf['drawdown_20d'] = (c - rolling_max) / (rolling_max + 1e-10)
    up = (ret1 > 0).astype(int)
    down = (ret1 < 0).astype(int)
    gdf['up_streak'] = up.groupby((up != up.shift()).cumsum()).cumsum()
    gdf['down_streak'] = down.groupby((down != down.shift()).cumsum()).cumsum()
    price_up = (c > c.shift(5)).astype(int)
    vol_down = (v < v.shift(5)).astype(int)
    gdf['vol_price_div'] = price_up * vol_down
    
    all_frames.append(gdf)

df = pd.concat(all_frames, ignore_index=True)

# ========== 标签 ==========
df['future_ret_20d'] = df.groupby('code')['收盘'].transform(lambda x: x.shift(-20) / x - 1)
df = df.dropna(subset=['future_ret_20d']).copy()
df = df[df['日期'] >= '2024-06-01'].copy()

# ========== 截面特征 ==========
raw_features = ['mom_5d','mom_10d','mom_20d','mom_60d','mom_accel',
                'dist_sma20','dist_sma60','vol_5d','vol_20d','vol_ratio',
                'turnover_ratio','vol_price_corr','macd_hist','rsi_14',
                'bb_pos','atr_ratio','body_ratio','ret_1d','ret_3d',
                'high_low_range','gap',
                'sharpe_20d','decay_mom','drawdown_20d','up_streak','down_streak','vol_price_div']

for feat in raw_features:
    m = df.groupby('日期')[feat].transform('mean')
    s = df.groupby('日期')[feat].transform('std')
    df[f'{feat}_cs'] = (df[feat] - m) / (s + 1e-10)

sector_feats = ['mom_20d','rsi_14','turnover_ratio','macd_hist']
for feat in sector_feats:
    m = df.groupby(['日期','sector'])[feat].transform('mean')
    s = df.groupby(['日期','sector'])[feat].transform('std')
    df[f'{feat}_sector'] = (df[feat] - m) / (s + 1e-10)

rank_feats = ['mom_5d','mom_20d','mom_60d','rsi_14','turnover_ratio','macd_hist','sharpe_20d']
for feat in rank_feats:
    df[f'{feat}_rank'] = df.groupby('日期')[feat].rank(pct=True)

for feat in ['mom_20d','rsi_14']:
    df[f'{feat}_sector_rank'] = df.groupby('日期')[feat].rank(pct=True)
    df[f'{feat}_revert'] = -df[f'{feat}_cs']

cs_cols = [f'{f}_cs' for f in raw_features]
sector_cols = [f'{f}_sector' for f in sector_feats]
rank_cols = [f'{f}_rank' for f in rank_feats]
sector_rank_cols = [f'{f}_sector_rank' for f in ['mom_20d','rsi_14']]
revert_cols = [f'{f}_revert' for f in ['mom_20d','rsi_14']]
FEATURE_COLS = cs_cols + sector_cols + rank_cols + sector_rank_cols + revert_cols

for col in FEATURE_COLS:
    df[col] = df[col].replace([np.inf, -np.inf], np.nan).fillna(0)

print(f'有效样本: {len(df)}, 特征: {len(FEATURE_COLS)}')

# ========== 集成训练 ==========
model_params = [
    {'num_leaves': 31, 'learning_rate': 0.05, 'n_estimators': 200, 'subsample': 0.8, 'colsample_bytree': 0.8},
    {'num_leaves': 50, 'learning_rate': 0.03, 'n_estimators': 300, 'subsample': 0.7, 'colsample_bytree': 0.7},
    {'num_leaves': 20, 'learning_rate': 0.08, 'n_estimators': 150, 'subsample': 0.9, 'colsample_bytree': 0.9},
]

X = df[FEATURE_COLS].values
y = df['future_ret_20d'].values
dates = df['日期'].values
n_splits = 5
unique_dates = np.sort(np.unique(dates))
fold_size = len(unique_dates) // (n_splits + 1)

all_fold_ics = []
all_fold_ls = []
all_fold_top = []

for fold_idx in range(n_splits):
    cutoff = unique_dates[(fold_idx + 1) * fold_size]
    train_mask = dates < cutoff
    test_mask = dates >= cutoff
    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]
    test_dates = dates[test_mask]
    
    ensemble_preds = []
    for params in model_params:
        model = LGBMRegressor(**params, random_state=42, n_jobs=-1, verbose=-1)
        model.fit(X_train, y_train)
        ensemble_preds.append(model.predict(X_test))
    
    avg_pred = np.mean(ensemble_preds, axis=0)
    
    fold_ics = []
    for d in np.unique(test_dates):
        mask = test_dates == d
        if mask.sum() >= 3:
            fold_ics.append(np.corrcoef(avg_pred[mask], y_test[mask])[0, 1])
    mean_ic = np.mean(fold_ics) if fold_ics else 0
    all_fold_ics.append(mean_ic)
    
    top_mask = avg_pred > np.percentile(avg_pred, 80)
    bot_mask = avg_pred < np.percentile(avg_pred, 20)
    ls = y_test[top_mask].mean() - y_test[bot_mask].mean()
    top_avg = y_test[top_mask].mean()
    top_wr = (y_test[top_mask] > 0).mean()
    
    all_fold_ls.append(ls)
    all_fold_top.append(top_avg)
    
    print(f'Fold {fold_idx+1}: IC={mean_ic:.4f}, L-S={ls*100:+.2f}%, TopAvg={top_avg*100:+.2f}%, TopWR={top_wr*100:.1f}%')

print(f'\n=== 集成模型平均 ===')
print(f'IC Avg: {np.mean(all_fold_ics):.4f}')
print(f'L-S:    {np.mean(all_fold_ls)*100:+.2f}%')
print(f'TopAvg: {np.mean(all_fold_top)*100:+.2f}%')

# ========== 全量训练并保存 ==========
final_models = []
for params in model_params:
    model = LGBMRegressor(**params, random_state=42, n_jobs=-1, verbose=-1)
    model.fit(X, y)
    final_models.append(model)

model_data = {'models': final_models, 'n_models': len(final_models), 'feature_cols': FEATURE_COLS}
with open('model_output/lgb_model_v16.pkl', 'wb') as f:
    pickle.dump(model_data, f)

with open('model_output/features_v16.json', 'w') as f:
    json.dump(FEATURE_COLS, f)

print(f'\nv16c 模型已保存: model_output/lgb_model_v16.pkl ({len(final_models)} 个模型)')
print(f'特征已保存: model_output/features_v16.json ({len(FEATURE_COLS)} 个)')
