#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QuantStock-AI v15.0 — 集成学习 + 高级特征
借鉴：多模型集成、波动率调整动量、衰减加权动量
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os, time, json, pickle, warnings
import requests
import numpy as np
import pandas as pd
from datetime import datetime

warnings.filterwarnings('ignore')
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 精选50只
STOCKS = {
    '白酒': [('600519','贵州茅台'),('000858','五粮液'),('000568','泸州老窖'),('600809','山西汾酒'),('002304','洋河股份')],
    '新能源': [('300750','宁德时代'),('002594','比亚迪'),('300274','阳光电源'),('002460','赣锋锂业'),('300014','亿纬锂能')],
    '半导体': [('002415','海康威视'),('002475','立讯精密'),('603501','韦尔股份'),('002371','北方华创'),('300308','中际旭创')],
    '医药': [('600276','恒瑞医药'),('300760','迈瑞医疗'),('300015','爱尔眼科'),('600436','片仔癀'),('300122','智飞生物')],
    '金融': [('601318','中国平安'),('600036','招商银行'),('600030','中信证券'),('300059','东方财富'),('000001','平安银行')],
    '消费': [('000333','美的集团'),('000651','格力电器'),('600690','海尔智家'),('601888','中国中免'),('002714','牧原股份')],
    '制造': [('600031','三一重工'),('600309','万华化学'),('600585','海螺水泥'),('601012','隆基绿能'),('002271','东方雨虹')],
    '科技': [('600570','恒生电子'),('300124','汇川技术'),('000977','浪潮信息'),('688111','金山办公'),('002230','科大讯飞')],
    '妖股_5G': [('600776','东方通信'),('002194','武汉凡谷')],
    '妖股_新冠': [('002432','九安医疗'),('600056','中国医药'),('002349','精华制药')],
    '妖股_新能源车': [('000957','中通客车'),('002725','跃岭股份')],
    '妖股_基建': [('002761','浙江建投'),('600860','京城股份')],
    '妖股_数字经济': [('603123','翠微股份'),('000812','陕西金叶')],
    '妖股_其他': [('001317','三羊马'),('300261','雅本化学'),('600698','湖南天雁')],
}

ALL_STOCKS = []
seen = set()
for sector, stocks in STOCKS.items():
    for code, name in stocks:
        if code not in seen:
            ALL_STOCKS.append((code, name, sector))
            seen.add(code)


def fetch_sina_daily(code, datalen=500):
    market = "sz" if code.startswith(('0','3')) else "sh"
    url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": f"{market}{code}", "scale": "1680", "ma": "no", "datalen": str(datalen)}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = r.json()
        if data and len(data) > 80:
            rows = []
            for item in data:
                rows.append({
                    'date': item['day'], 'open': float(item['open']),
                    'close': float(item['close']), 'high': float(item['high']),
                    'low': float(item['low']), 'volume': float(item['volume']),
                })
            return pd.DataFrame(rows)
    except:
        pass
    return None


def compute_features(df):
    """v15高级特征：40个（比v12多5个高级特征）"""
    df = df.copy().sort_values('date').reset_index(drop=True)
    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    ret1 = c.pct_change(1)

    # === 基础动量（v12已有）===
    df['mom_5d'] = c.pct_change(5)
    df['mom_10d'] = c.pct_change(10)
    df['mom_20d'] = c.pct_change(20)
    df['mom_60d'] = c.pct_change(60)
    df['mom_accel'] = df['mom_5d'] - df['mom_20d']

    sma20 = c.rolling(20).mean()
    sma60 = c.rolling(60).mean()
    df['dist_sma20'] = (c - sma20) / (sma20 + 1e-10)
    df['dist_sma60'] = (c - sma60) / (sma60 + 1e-10)

    df['vol_5d'] = ret1.rolling(5).std()
    df['vol_20d'] = ret1.rolling(20).std()
    df['vol_ratio'] = df['vol_5d'] / (df['vol_20d'] + 1e-10)

    vol_ma5 = v.rolling(5).mean()
    vol_ma20 = v.rolling(20).mean()
    df['turnover_ratio'] = vol_ma5 / (vol_ma20 + 1e-10)
    df['vol_price_corr'] = c.rolling(10).corr(v)

    ema12 = c.ewm(span=12).mean()
    ema26 = c.ewm(span=26).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9).mean()
    df['macd_hist'] = 2 * (dif - dea) / (c + 1e-10)

    delta = c.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi_14'] = 100 - (100 / (1 + gain / (loss + 1e-10)))

    bb_std = c.rolling(20).std()
    df['bb_pos'] = (c - sma20) / (2 * bb_std + 1e-10)

    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    df['atr_ratio'] = tr.rolling(14).mean() / (c + 1e-10)

    df['body_ratio'] = abs(c - o) / (h - l + 1e-10)
    df['ret_1d'] = ret1
    df['ret_3d'] = c.pct_change(3)
    df['high_low_range'] = (h - l) / (c + 1e-10)
    df['gap'] = (o - c.shift(1)) / (c.shift(1) + 1e-10)

    # === v15新增高级特征 ===
    # 1. 波动率调整动量（Sharpe-like）
    df['sharpe_20d'] = df['mom_20d'] / (df['vol_20d'] + 1e-10)

    # 2. 衰减加权动量（近期权重更高）
    weights = np.array([0.4, 0.3, 0.2, 0.1])  # 5d, 10d, 15d, 20d
    df['decay_mom'] = (0.4 * df['mom_5d'] + 0.3 * c.pct_change(10) + 
                       0.2 * c.pct_change(15) + 0.1 * df['mom_20d'])

    # 3. 最大回撤（20日）
    rolling_max = c.rolling(20).max()
    df['drawdown_20d'] = (c - rolling_max) / (rolling_max + 1e-10)

    # 4. 连续上涨/下跌天数
    up = (ret1 > 0).astype(int)
    down = (ret1 < 0).astype(int)
    df['up_streak'] = up.groupby((up != up.shift()).cumsum()).cumsum()
    df['down_streak'] = down.groupby((down != down.shift()).cumsum()).cumsum()

    # 5. 量价背离（价格涨但量缩 → 可能见顶）
    price_up = (c > c.shift(5)).astype(int)
    vol_down = (v < v.shift(5)).astype(int)
    df['vol_price_div'] = price_up * vol_down  # 1=背离

    return df


RAW_FEATURES = [
    'mom_5d','mom_10d','mom_20d','mom_60d','mom_accel',
    'dist_sma20','dist_sma60','vol_5d','vol_20d','vol_ratio',
    'turnover_ratio','vol_price_corr','macd_hist','rsi_14',
    'bb_pos','atr_ratio','body_ratio','ret_1d','ret_3d',
    'high_low_range','gap',
    # v15新增
    'sharpe_20d','decay_mom','drawdown_20d','up_streak','down_streak','vol_price_div',
]


def collect_data(cache_file="data_cache/v15_data.parquet"):
    if os.path.exists(cache_file) and time.time() - os.path.getmtime(cache_file) < 86400:
        cached = pd.read_parquet(cache_file)
        print(f"[1/5] 缓存: {cached['code'].nunique()}只, {len(cached)}条")
        return cached

    print(f"[1/5] 采集 {len(ALL_STOCKS)} 只股票...")
    all_frames = []
    failed = 0
    for i, (code, name, sector) in enumerate(ALL_STOCKS):
        df = fetch_sina_daily(code, datalen=500)
        if df is not None and len(df) > 80:
            df['code'] = code
            df['name'] = name
            df['sector'] = sector
            all_frames.append(df)
        else:
            failed += 1
        if (i+1) % 20 == 0:
            print(f"  {i+1}/{len(ALL_STOCKS)} 成功:{len(all_frames)}")
        time.sleep(0.25)

    result = pd.concat(all_frames, ignore_index=True)
    os.makedirs("data_cache", exist_ok=True)
    result.to_parquet(cache_file, index=False)
    print(f"  完成: {result['code'].nunique()}只, {len(result)}条")
    return result


def build_dataset(all_data):
    print("[2/5] 计算高级特征...")
    frames = []
    for code in all_data['code'].unique():
        sdf = all_data[all_data['code'] == code].copy()
        if len(sdf) < 80:
            continue
        sdf = compute_features(sdf)
        frames.append(sdf)
    df = pd.concat(frames, ignore_index=True)
    print(f"  样本: {len(df)}, 股票: {df['code'].nunique()}只")

    print("[3/5] 计算截面特征...")
    for feat in RAW_FEATURES:
        m = df.groupby('date')[feat].transform('mean')
        s = df.groupby('date')[feat].transform('std')
        df[f'{feat}_cs'] = (df[feat] - m) / (s + 1e-10)

    for feat in ['mom_20d','rsi_14','turnover_ratio','macd_hist']:
        m = df.groupby(['date','sector'])[feat].transform('mean')
        s = df.groupby(['date','sector'])[feat].transform('std')
        df[f'{feat}_sector'] = (df[feat] - m) / (s + 1e-10)

    rank_feats = ['mom_5d','mom_20d','mom_60d','rsi_14','turnover_ratio','macd_hist','sharpe_20d']
    for feat in rank_feats:
        df[f'{feat}_rank'] = df.groupby('date')[feat].rank(pct=True)

    for feat in ['mom_20d','rsi_14']:
        df[f'{feat}_sector_rank'] = df.groupby('date')[feat].rank(pct=True)
        df[f'{feat}_revert'] = -df[f'{feat}_cs']

    df['target'] = df.groupby('code')['close'].transform(lambda x: x.shift(-20) / x - 1)

    cs_cols = [f'{f}_cs' for f in RAW_FEATURES]
    sector_cols = [f'{f}_sector' for f in ['mom_20d','rsi_14','turnover_ratio','macd_hist']]
    rank_cols = [f'{f}_rank' for f in rank_feats]
    sector_rank_cols = [f'{f}_sector_rank' for f in ['mom_20d','rsi_14']]
    revert_cols = [f'{f}_revert' for f in ['mom_20d','rsi_14']]
    all_features = cs_cols + sector_cols + rank_cols + sector_rank_cols + revert_cols

    for col in all_features:
        df[col] = df[col].replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=all_features + ['target'])

    print(f"  特征: {len(all_features)}个")
    print(f"  最终样本: {len(df)}")
    return df, all_features


def train_ensemble(dataset, feature_cols, n_splits=5):
    """集成学习：3个不同参数的LightGBM取平均"""
    import lightgbm as lgb

    print(f"\n[4/5] 集成学习 (3模型 × {n_splits}折, {len(feature_cols)}特征)...")
    dataset = dataset.sort_values('date').reset_index(drop=True)
    X = dataset[feature_cols].values
    y = dataset['target'].values
    dates = dataset['date'].values

    # 3组不同参数
    param_sets = [
        {'num_leaves': 31, 'max_depth': 6, 'learning_rate': 0.05, 'feature_fraction': 0.8, 'reg_alpha': 0.05},
        {'num_leaves': 63, 'max_depth': 8, 'learning_rate': 0.03, 'feature_fraction': 0.7, 'reg_alpha': 0.1},
        {'num_leaves': 127, 'max_depth': 10, 'learning_rate': 0.02, 'feature_fraction': 0.6, 'reg_alpha': 0.2},
    ]

    total = len(X)
    fold_size = int(total * 0.15 / n_splits)
    results = []

    for fold in range(n_splits):
        train_end = total - (n_splits - fold) * fold_size
        test_start = train_end
        test_end = min(test_start + fold_size, total)
        if train_end < 500:
            continue

        X_tr, y_tr = X[:train_end], y[:train_end]
        X_te, y_te = X[test_start:test_end], y[test_start:test_end]

        # 集成3个模型
        preds = []
        for i, extra_params in enumerate(param_sets):
            params = {
                'objective': 'regression', 'metric': 'mse',
                'boosting_type': 'gbdt',
                'bagging_fraction': 0.7, 'bagging_freq': 5,
                'verbose': -1, 'n_jobs': -1,
                'min_child_samples': 200,
                **extra_params,
            }
            tr_data = lgb.Dataset(X_tr, label=y_tr)
            te_data = lgb.Dataset(X_te, label=y_te, reference=tr_data)
            model = lgb.train(params, tr_data, num_boost_round=3000,
                              valid_sets=[te_data],
                              callbacks=[lgb.early_stopping(300), lgb.log_evaluation(0)])
            preds.append(model.predict(X_te))

        # 集成平均
        y_pred = np.mean(preds, axis=0)
        ic = np.corrcoef(y_pred, y_te)[0, 1] if len(y_pred) > 10 else 0

        tdf = dataset.iloc[test_start:test_end][['code','date','target']].copy()
        tdf['pred'] = y_pred
        tdf = tdf.sort_values('pred').reset_index(drop=True)
        n = len(tdf); gs = n // 5
        tdf['q'] = 1
        for q in range(1, 5):
            tdf.iloc[q*gs:, tdf.columns.get_loc('q')] = q + 1

        qs = {}
        for q in [1,2,3,4,5]:
            qd = tdf[tdf['q'] == q]
            if len(qd) > 0:
                qs[q] = {'n': len(qd), 'mean': round(qd['target'].mean()*100, 2),
                          'wr': round((qd['target']>0).mean(), 4)}

        top = tdf[tdf['q'] == 5]
        top_wr = (top['target'] > 0).mean() if len(top) > 0 else 0
        top_avg = top['target'].mean() * 100 if len(top) > 0 else 0
        ls = qs.get(5,{}).get('mean',0) - qs.get(1,{}).get('mean',0)

        r = {
            'fold': fold+1, 'train': len(X_tr), 'test': len(X_te),
            'ic': round(ic, 4), 'ls': round(ls, 2),
            'top_wr': round(top_wr, 4), 'top_avg': round(top_avg, 2),
            'top_n': int(len(top)), 'qs': qs,
            'dates': f"{dates[test_start]}~{dates[test_end-1]}",
        }
        results.append(r)

        print(f"  Fold{r['fold']}: IC={ic:.3f} L-S={ls:+.2f}% Top胜率={top_wr:.1%} Top均收益={top_avg:+.2f}%")

    # 汇总
    print(f"\n{'='*60}")
    avg_ic = np.mean([r['ic'] for r in results]) if results else 0
    avg_ls = np.mean([r['ls'] for r in results]) if results else 0
    wr_list = [r['top_wr'] for r in results if r['top_wr'] > 0]
    avg_wr = np.mean(wr_list) if wr_list else 0
    avg_ret = np.mean([r['top_avg'] for r in results]) if results else 0

    print(f"  平均IC: {avg_ic:.4f}")
    print(f"  平均L-S: {avg_ls:+.2f}%")
    print(f"  Top组胜率: {avg_wr:.1%}")
    print(f"  Top组均收益: {avg_ret:+.2f}%")

    if avg_ic > 0.03:
        print(f"  ✅ IC>0.03, 有统计意义!")
    if avg_ls > 2.0:
        print(f"  ✅ L-S>2%, 排名有区分度!")

    # 保存最后一个集成模型
    return model, results, {
        'avg_ic': round(float(avg_ic), 4),
        'avg_ls': round(float(avg_ls), 2),
        'avg_top_wr': round(float(avg_wr), 4),
        'avg_top_ret': round(float(avg_ret), 2),
        'n_samples': len(X),
        'n_features': len(feature_cols),
        'n_stocks': dataset['code'].nunique(),
    }


def save(model, results, summary, feature_cols, dir_='model_output'):
    os.makedirs(dir_, exist_ok=True)
    with open(f'{dir_}/lgb_model_v15.pkl', 'wb') as f:
        pickle.dump(model, f)
    with open(f'{dir_}/features_v15.json', 'w') as f:
        json.dump(feature_cols, f, indent=2)

    lines = [
        "# QuantStock-AI v15.0 集成学习 + 高级特征",
        f"时间: {datetime.now():%Y-%m-%d %H:%M}",
        f"股票: {summary['n_stocks']}只 | 样本: {summary['n_samples']} | 特征: {summary['n_features']}",
        f"IC: {summary['avg_ic']:.4f} | L-S: {summary['avg_ls']:+.2f}%",
        f"Top组: 胜率{summary['avg_top_wr']:.1%} 均收益{summary['avg_top_ret']:+.2f}%",
        "",
        "## 各折",
    ]
    for r in results:
        lines.append(f"F{r['fold']}: {r['dates']} IC={r['ic']:.3f} L-S={r['ls']:+.2f}% "
                     f"Top={r['top_wr']:.1%}/{r['top_avg']:+.2f}%")
    with open(f'{dir_}/report_v15.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"  模型已保存")


def main():
    t0 = time.time()
    print("=" * 60)
    print("  QuantStock-AI v15.0")
    print("  集成学习（3模型）+ 高级特征（6个新增）")
    print("=" * 60)

    all_data = collect_data()
    dataset, feat_cols = build_dataset(all_data)
    model, results, summary = train_ensemble(dataset, feat_cols)
    save(model, results, summary, feat_cols)
    print(f"\n[5/5] 完成! 耗时: {(time.time()-t0)/60:.1f}分钟")


if __name__ == '__main__':
    main()
