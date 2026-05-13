import json
import os

def check():
    path = 'model_output/daily_predictions_v19.json'
    if not os.path.exists(path):
        print("File not found")
        return
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    preds = data['data'] if isinstance(data, dict) and 'data' in data else data
    
    sorted_preds = sorted([
        v.get("predicted_return", 0) for v in preds.values()
    ], reverse=True)
    
    n = len(sorted_preds)
    p30_val = sorted_preds[int(n*0.7)] if n >= 10 else 0.4
    p90_val = sorted_preds[int(n*0.1)] if n >= 10 else 0.6
    
    print(f"P30 threshold: {p30_val}")
    print(f"P90 threshold: {p90_val}")
    
    holdings = ['000601', '000975', '000977', '002179', '300395']
    for code in holdings:
        val = preds.get(code, {}).get("predicted_return", "N/A")
        print(f"Code {code}: {val}")

if __name__ == "__main__":
    check()
