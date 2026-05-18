import argparse
import os
import json
import warnings
import pandas as pd
import numpy as np
import pickle

warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)

import qlib
from qlib.data import D
from qlib.config import REG_CN

def calculate_ic_metrics(pred_df):
    ic_series = pred_df.groupby(level='datetime').apply(lambda x: x['score'].corr(x['label'], method='pearson'))
    rank_ic_series = pred_df.groupby(level='datetime').apply(lambda x: x['score'].corr(x['label'], method='spearman'))
    
    ic_series = ic_series.dropna()
    rank_ic_series = rank_ic_series.dropna()
    
    ic_mean = ic_series.mean()
    rank_ic_mean = rank_ic_series.mean()
    
    ic_std = ic_series.std()
    icir = ic_mean / ic_std if ic_std > 0 else 0.0
    
    return float(ic_mean), float(rank_ic_mean), float(icir)

def calculate_quantile_returns(pred_df, num_quantiles=5):
    all_quantiles = []
    
    for dt, group in pred_df.groupby(level='datetime'):
        if len(group) < num_quantiles:
            continue
        try:
            labels = [f"Q{i+1}" for i in range(num_quantiles)]
            q = pd.qcut(group['score'], q=num_quantiles, labels=labels, duplicates='drop')
            all_quantiles.append(q)
        except ValueError:
            pass
            
    if not all_quantiles:
        return {"top_quantile_return": 0.0, "bottom_quantile_return": 0.0, "long_short_return": 0.0, "turnover": 0.0, "return_after_cost": 0.0}, []
        
    pred_df['quantile'] = pd.concat(all_quantiles)
    
    quantile_stats = []
    for q_name in sorted(pred_df['quantile'].dropna().unique()):
        q_data = pred_df[pred_df['quantile'] == q_name]
        mean_ret = q_data['label'].mean()
        win_rate = (q_data['label'] > 0).mean()
        count = len(q_data)
        
        quantile_stats.append({
            "group": str(q_name),
            "mean_return": float(mean_ret),
            "win_rate": float(win_rate),
            "count": int(count)
        })
    
    top_q = f"Q{num_quantiles}"
    bottom_q = "Q1"
    
    top_ret = pred_df[pred_df['quantile'] == top_q]['label'].mean() if top_q in pred_df['quantile'].values else 0.0
    bottom_ret = pred_df[pred_df['quantile'] == bottom_q]['label'].mean() if bottom_q in pred_df['quantile'].values else 0.0
    long_short_ret = top_ret - bottom_ret
    
    top_portfolio = pred_df[pred_df['quantile'] == top_q].reset_index()
    turnover_list = []
    
    dates = sorted(top_portfolio['datetime'].unique())
    for i in range(1, len(dates)):
        prev_stocks = set(top_portfolio[top_portfolio['datetime'] == dates[i-1]]['instrument'])
        curr_stocks = set(top_portfolio[top_portfolio['datetime'] == dates[i]]['instrument'])
        if len(prev_stocks) == 0 or len(curr_stocks) == 0:
            continue
        intersection = prev_stocks.intersection(curr_stocks)
        turnover = 1.0 - (len(intersection) / len(curr_stocks))
        turnover_list.append(turnover)
        
    mean_turnover = sum(turnover_list) / len(turnover_list) if turnover_list else 0.0
    
    cost_per_trade = 0.0015 
    daily_cost = mean_turnover * cost_per_trade * 2
    return_after_cost = top_ret - daily_cost
    
    return {
        "top_quantile_return": float(top_ret),
        "bottom_quantile_return": float(bottom_ret),
        "long_short_return": float(long_short_ret),
        "turnover": float(mean_turnover),
        "return_after_cost": float(return_after_cost)
    }, quantile_stats

def get_historical_predictions(version, start_date, end_date):
    print(f"Generating historical predictions for {version} from {start_date} to {end_date}...")
    stock_pool = []
    if os.path.exists('data/stock_names.json'):
        with open('data/stock_names.json', 'r', encoding='utf-8') as f:
            stock_pool = list(json.load(f).keys())
    
    instruments = []
    if stock_pool:
        all_inst = set(D.list_instruments(D.instruments(market='all'), as_list=True))
        for s in stock_pool:
            for prefix in ["SH", "SZ", "BJ"]:
                code = prefix + s if not s.startswith(prefix) else s.upper()
                if code in all_inst:
                    instruments.append(code)
                    break
    else:
        instruments = D.list_instruments(D.instruments(market='all'), as_list=True)[:300]
        
    if version in ["v19", "v20"]:
        v19_path = "model_output/lgb_model_v19_ensemble.pkl"
        v20_path = "model_output/lgb_model_v20_meta.pkl"
        
        with open("model_output/features_v19_ensemble.json", 'r', encoding='utf-8') as f:
            v19_feat_expr = json.load(f)
            
        v19_fields = list(v19_feat_expr.values())
        data = D.features(instruments, v19_fields, start_date, end_date)
        data.dropna(inplace=True)
        
        with open(v19_path, 'rb') as f: v19_model = pickle.load(f)
        
        if isinstance(v19_model, list):
            preds = [m.predict(data) for m in v19_model]
            data['score_v19'] = np.mean(preds, axis=0)
        else:
            data['score_v19'] = v19_model.predict(data)
            
        if version == "v19":
            res = pd.DataFrame({'score': data['score_v19']}, index=data.index)
            return res
        else:
            meta_features = data.copy()
            meta_features.rename(columns={'score_v19': 'Primary_Pred'}, inplace=True)
            with open("model_output/features_v20_meta.json", 'r', encoding='utf-8') as f:
                meta_feat_names = json.load(f)
            
            meta_features.columns = list(v19_feat_expr.keys()) + ['Primary_Pred']
            meta_features = meta_features[meta_feat_names]
            
            with open(v20_path, 'rb') as f: v20_model = pickle.load(f)
            # Use probability for class 1 if available, otherwise just use predictions
            if hasattr(v20_model, "predict_proba"):
                score = v20_model.predict_proba(meta_features)[:, 1]
            else:
                score = v20_model.predict(meta_features)
            res = pd.DataFrame({'score': score}, index=meta_features.index)
            return res
            
    print(f"Version {version} not fully implemented for dynamic prediction, returning empty.")
    return pd.DataFrame()

def main():
    parser = argparse.ArgumentParser(description="Evaluate signal quality")
    parser.add_argument("--version", type=str, required=True, help="Model version to evaluate (e.g., v19, v20)")
    args = parser.parse_args()
    
    version = args.version
    
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    
    print(f"Evaluating signal quality for {version}...")
    
    start_date = "2024-01-01"
    end_date = "2026-05-18"
    pred_df = get_historical_predictions(version, start_date, end_date)
    
    if pred_df.empty:
        print("Failed to generate predictions.")
        return
        
    print(f"Generated {len(pred_df)} prediction records.")
    
    instruments = pred_df.index.get_level_values('instrument').unique().tolist()
    
    print("Fetching future returns (labels) from Qlib...")
    try:
        features = ["Ref($close, -1)/$close - 1"]
        label_df = D.features(
            instruments, 
            features, 
            start_time=start_date, 
            end_time=end_date, 
            freq='day'
        )
        label_df.columns = ['label']
        
        eval_df = pred_df.join(label_df, how='inner')
        eval_df = eval_df.dropna(subset=['score', 'label'])
        
        print(f"Merged data has {len(eval_df)} records with both prediction and label.")
        
        if len(eval_df) == 0:
            print("Error: No overlapping records between predictions and labels.")
            return
            
        print("Calculating IC metrics...")
        ic_mean, rank_ic_mean, icir = calculate_ic_metrics(eval_df)
        
        print("Calculating quantile returns...")
        overall_stats, quantile_stats = calculate_quantile_returns(eval_df)
        
        report = {
            "model": version,
            "period": {
                "start": start_date,
                "end": end_date
            },
            "metrics": {
                "ic_mean": round(ic_mean, 4),
                "rank_ic_mean": round(rank_ic_mean, 4),
                "icir": round(icir, 4),
                "top_quantile_return": round(overall_stats["top_quantile_return"], 4),
                "bottom_quantile_return": round(overall_stats["bottom_quantile_return"], 4),
                "long_short_return": round(overall_stats["long_short_return"], 4),
                "turnover": round(overall_stats["turnover"], 4),
                "return_after_cost": round(overall_stats["return_after_cost"], 4)
            },
            "quantiles": []
        }
        
        for qs in quantile_stats:
            report["quantiles"].append({
                "group": qs["group"],
                "mean_return": round(qs["mean_return"], 4),
                "win_rate": round(qs["win_rate"], 4),
                "count": qs["count"]
            })
            
        os.makedirs("model_output", exist_ok=True)
        out_file = f"model_output/signal_quality_{version}.json"
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
            
        print(f"Evaluation report saved to {out_file}")
        print(json.dumps(report, indent=2))
        
    except Exception as e:
        print(f"Error during evaluation: {e}")

if __name__ == "__main__":
    main()
