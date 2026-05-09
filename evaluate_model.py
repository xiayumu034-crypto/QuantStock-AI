#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import argparse
from datetime import datetime

def evaluate_predictions(version="v17"):
    # 强制优先使用真实数据进行评估
    if version == "v18":
        pred_path = "model_output/daily_predictions_v18.json"
        out_path = "model_output/model_report_v18.json"
    else:
        pred_path = "model_output/daily_predictions.json"
        out_path = "model_output/model_report_v17.json"
        
    is_sample = False
    
    if not os.path.exists(pred_path):
        if version == "v18":
            print(f"[Evaluate {version}] 找不到任何预测数据！无法生成评估报告。")
            return
        else:
            pred_path = "model_output/sample_daily_predictions.json"
            is_sample = True
            print(f"[Evaluate {version}] 未找到真实业务预测数据，将基于 sample 数据生成评估报告 (WARNING ONLY)")
            if not os.path.exists(pred_path):
                print(f"[Evaluate {version}] 找不到任何预测数据(连 sample 也没有)！无法生成评估报告。")
                return
        
    with open(pred_path, 'r', encoding='utf-8') as f:
        try:
            preds = json.load(f)
        except Exception as e:
            print(f"[Evaluate {version}] 解析 JSON 失败: {e}")
            return
            
    if not preds:
        print(f"[Evaluate {version}] 预测数据为空！")
        return

    # 提取特征
    returns = []
    signals = {"看涨": 0, "强烈看涨": 0, "中性": 0, "看跌": 0}
    
    # 因为历史代码有些英文有些中文，做一下容错统一
    signal_map = {"bullish": "看涨", "bearish": "看跌", "neutral": "中性"}
    
    # 兼容新的 _meta 结构
    if "_meta" in preds and "data" in preds:
        items = preds["data"].items()
    elif "data" in preds and isinstance(preds["data"], dict) and "status" in preds:
        items = preds["data"].items()
    else:
        items = preds.items()

    for code, data in items:
        # 有些是 dict，有些可能因为格式乱掉是其他，做个安全判断
        if not isinstance(data, dict): continue
            
        ret = data.get("predicted_return", 0.0)
        sig = data.get("signal", "中性")
        if sig in signal_map: sig = signal_map[sig] # 英文转中文统计
        
        returns.append(ret)
        
        if sig in signals:
            signals[sig] += 1
        else:
            signals[sig] = 1

    if not returns:
        print(f"[Evaluate {version}] 未提取到任何有效收益率预测值。")
        return
        
    # 计算统计指标
    n_stocks = len(returns)
    unique_returns = len(set(returns))
    min_ret = min(returns)
    max_ret = max(returns)
    mean_ret = sum(returns) / n_stocks
    std_ret = (sum((x - mean_ret)**2 for x in returns) / n_stocks) ** 0.5
    
    # 加载股票名称映射
    names_file = "data/stock_names.json"
    stock_names = {}
    if os.path.exists(names_file):
        with open(names_file, 'r', encoding='utf-8') as f:
            stock_names = json.load(f)

    # 排序计算 Top / Bottom
    sorted_items = sorted(items, key=lambda x: x[1].get("predicted_return", 0.0), reverse=True)
    
    # 根据版本决定 top 数量
    top_n = 10 if version == "v18" else 5
    
    top_list = [{"code": k, "name": stock_names.get(k, f"代码-{k}"), "pred": v.get("predicted_return", 0)} for k,v in sorted_items[:top_n]]
    bottom_list = [{"code": k, "name": stock_names.get(k, f"代码-{k}"), "pred": v.get("predicted_return", 0)} for k,v in sorted_items[-top_n:]]
    
    duplicate_ratio = 1.0 - unique_returns / n_stocks if n_stocks > 0 else 0
    top_spread = max_ret - min_ret
    
    warnings = []
    if duplicate_ratio > 0.7:  # unique_values/stock_count < 0.3
        warnings.append("预测离散度偏低，重复值过多，建议扩展特征或调整模型参数")

    report = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model_version": version,
        "is_sample": is_sample,
        "health_check": {
            "warnings": warnings,
            "duplicate_ratio": round(duplicate_ratio, 4),
            "top_spread": round(top_spread, 6)
        },
        "stock_count": n_stocks,
        "prediction_distribution": {
            "min": round(min_ret, 6),
            "max": round(max_ret, 6),
            "mean": round(mean_ret, 6),
            "std": round(std_ret, 6),
            "unique_values": unique_returns
        },
        "signal_stats": signals,
        f"top_{top_n}": top_list,
        f"bottom_{top_n}": bottom_list
    }
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=4)
        
    print("=======================================")
    print(f"评估完成！报告已生成 -> {out_path}")
    print(f"【摘要】包含 {n_stocks} 只股票。唯一预测值 {unique_returns} 个。")
    print(f"信号分布: {json.dumps(signals, ensure_ascii=False)}")
    print(f"最大预期收益: {max_ret:.4f}, 最小预期收益: {min_ret:.4f}")
    print("=======================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, default="v17", help="指定要评估的模型版本，如 v17 或 v18")
    args = parser.parse_args()
    evaluate_predictions(version=args.version)