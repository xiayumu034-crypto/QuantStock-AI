import json
import os
import random
from datetime import datetime

def generate_mock_v19_csi300():
    # 1. 读取最新的成分股列表
    names_file = os.path.join("data", "stock_names.json")
    if not os.path.exists(names_file):
        print("错误：未找到 data/stock_names.json")
        return
        
    with open(names_file, 'r', encoding='utf-8') as f:
        stock_names = json.load(f)
        
    # 2. 生成模拟预测数据
    # 为 300 只股票生成正态分布的预测收益
    # 假设平均收益 0.0005，标准差 0.002
    data = {}
    for code in stock_names.keys():
        pred_return = random.gauss(0.0005, 0.002)
        momentum = random.gauss(0, 1.0)
        
        # 根据收益率打标签
        if pred_return > 0.003: signal = "看涨"
        elif pred_return < -0.003: signal = "看跌"
        else: signal = "中性"
        
        data[code] = {
            "predicted_return": round(pred_return, 4),
            "momentum": round(momentum, 3),
            "signal": signal
        }
        
    # 3. 构造完整格式
    output = {
        "_meta": {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model_version": "v19_ensemble",
            "stocks": len(data),
            "features": 26,
            "expanded_to_csi300": True
        },
        "data": data
    }
    
    # 4. 写入文件
    output_path = os.path.join("model_output", "daily_predictions_v19.json")
    os.makedirs("model_output", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=4)
        
    print(f"成功模拟生成 {len(data)} 只沪深 300 股票的 V19 预测信号。")

if __name__ == "__main__":
    generate_mock_v19_csi300()
