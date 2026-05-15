import json
import os

out_file = "model_output/daily_predictions_v20.json"
stock_pool = {}
if os.path.exists('data/stock_names.json'):
    with open('data/stock_names.json', 'r', encoding='utf-8') as f:
        stock_pool = json.load(f)

# Mock some high confidence stocks
mock_results = {}
candidates = [
    ("000001", 0.021, 0.95),
    ("300059", 0.018, 0.88),
    ("600519", 0.015, 0.76),
    ("000858", 0.012, 0.65),
    ("601318", 0.010, 0.55)
]

for code, ret, meta in candidates:
    name = stock_pool.get(code, stock_pool.get(f"sz{code}", stock_pool.get(f"sh{code}", f"代码-{code}")))
    mock_results[code] = {
        "name": name,
        "predicted_return": ret,
        "meta_score": meta,
        "up_probability": meta * 100
    }

output = {
    "data": mock_results,
    "_meta": {
        "model_version": "AFML v20",
        "stocks": len(mock_results),
        "warning": "此为 AFML V20 的演示预测数据（因为本地未跑批真实训练）。"
    }
}

with open(out_file, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print(f"Generated mock v20 predictions to {out_file}")
