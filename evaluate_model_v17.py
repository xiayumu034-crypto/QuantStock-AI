#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from datetime import datetime

def evaluate_predictions():
    # 强制优先使用真实数据进行评估
    pred_path = "model_output/daily_predictions.json"
    is_sample = False
    
    if not os.path.exists(pred_path):
        pred_path = "model_output/sample_daily_predictions.json"
        is_sample = True
        print("[Evaluate] 未找到真实业务预测数据，将基于 sample 数据生成评估报告 (WARNING ONLY)")
        
    if not os.path.exists(pred_path):
        print("[Evaluate] 找不到任何预测数据(连 sample 也没有)！无法生成评估报告。")
        return
        
    with open(pred_path, 'r', encoding='utf-8') as f:
        try:
            preds = json.load(f)
        except Exception as e:
            print(f"[Evaluate] 解析 JSON 失败: {e}")
            return
            
    if not preds:
        print("[Evaluate] 预测数据为空！")
        return

    # 提取特征
    returns = []
    signals = {"看涨": 0, "强烈看涨": 0, "中性": 0, "看跌": 0}
    
    # 因为历史代码有些英文有些中文，做一下容错统一
    signal_map = {"bullish": "看涨", "bearish": "看跌", "neutral": "中性"}
    
    # 如果预测数据包了一层 {"status": "success", "data": ...} 需要解包
    # 虽然目前架构不这样，但容错
    items = preds.items()
    if "data" in preds and isinstance(preds["data"], dict) and "status" in preds:
        items = preds["data"].items()

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
        print("[Evaluate] 未提取到任何有效收益率预测值。")
        return
        
    # 计算统计指标
    n_stocks = len(returns)
    unique_returns = len(set(returns))
    min_ret = min(returns)
    max_ret = max(returns)
    mean_ret = sum(returns) / n_stocks
    std_ret = (sum((x - mean_ret)**2 for x in returns) / n_stocks) ** 0.5
    
    # 排序计算 Top / Bottom (仅记录 code, name 取不到先用 code)
    sorted_items = sorted(items, key=lambda x: x[1].get("predicted_return", 0.0), reverse=True)
    top_5 = [{"code": k, "pred": v.get("predicted_return", 0)} for k,v in sorted_items[:5]]
    bottom_5 = [{"code": k, "pred": v.get("predicted_return", 0)} for k,v in sorted_items[-5:]]
    
    report = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_sample": is_sample,
        "stock_count": n_stocks,
        "prediction_distribution": {
            "min": round(min_ret, 6),
            "max": round(max_ret, 6),
            "mean": round(mean_ret, 6),
            "std": round(std_ret, 6),
            "unique_values": unique_returns
        },
        "signal_stats": signals,
        "top_5": top_5,
        "bottom_5": bottom_5
    }
    
    out_path = "model_output/model_report_v17.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=4)
        
    print("=======================================")
    print(f"评估完成！报告已生成 -> {out_path}")
    print(f"【摘要】包含 {n_stocks} 只股票。唯一预测值 {unique_returns} 个。")
    print(f"信号分布: {json.dumps(signals, ensure_ascii=False)}")
    print(f"最大预期收益: {max_ret:.4f}, 最小预期收益: {min_ret:.4f}")
    print("=======================================")

if __name__ == "__main__":
    evaluate_predictions()