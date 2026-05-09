from flask import Blueprint, jsonify, request
import json
import os
import subprocess
from data.market_data import StockDataAPI

model_bp = Blueprint('model', __name__)
stock_api = StockDataAPI()

PREDICTIONS_FILE = "model_output/daily_predictions.json"
TRADE_LOGS_FILE = "model_output/trade_logs.json"

def read_predictions():
    if os.path.exists(PREDICTIONS_FILE):
        with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

@model_bp.route('/api/predict/<stock_code>')
def get_prediction(stock_code):
    return jsonify(stock_api.predict_next_5_minutes(stock_code))

@model_bp.route('/api/trade_logs')
def get_trade_logs():
    if os.path.exists(TRADE_LOGS_FILE):
        with open(TRADE_LOGS_FILE, 'r', encoding='utf-8') as f:
            return jsonify({"status": "success", "data": json.load(f)})
    return jsonify({"status": "success", "data": []})

@model_bp.route('/api/trade/manual', methods=['POST'])
def manual_trade():
    data = request.json
    code = data.get('code', '300201')
    direction = data.get('direction', 'buy')
    price = data.get('price', 0)
    volume = data.get('volume', 100)
    
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = [
            os.path.join(base_dir, ".venv_vnpy", "Scripts", "python.exe"), 
            "trade_manual_executor.py", 
            str(code), 
            str(direction), 
            str(price), 
            str(volume)
        ]
        # 后台异步执行手工交易脚本
        subprocess.Popen(cmd, cwd=base_dir)
        return jsonify({"status": "success", "message": "手工交易指令已发送至实盘网关"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@model_bp.route('/api/ml_predict/<stock_code>')
def get_ml_prediction(stock_code):
    """直接从离线 JSON 中读取预测结果，O(1)响应速度，彻底杜绝线上计算引发的崩溃"""
    predictions = read_predictions()
    
    if stock_code in predictions:
        pred_data = predictions[stock_code]
        return jsonify({
            "status": "success",
            "data": {
                "predicted_return": pred_data["predicted_return"],
                "signal": pred_data["signal"],
                "confidence": pred_data.get("confidence", 0.88),
                "predicted_price": 0  # 前端主要渲染 predicted_return 即可
            }
        })
    else:
        return jsonify({"status": "error", "message": f"暂无 {stock_code} 的离线预测数据，请等待盘后跑批。"})

@model_bp.route('/api/ml_predict_all')
def get_ml_predict_all():
    """获取全量预测结果"""
    predictions = read_predictions()
    
    # 加载股票名称映射
    names_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stock_names.json")
    stock_names = {}
    if os.path.exists(names_file):
        with open(names_file, 'r', encoding='utf-8') as f:
            stock_names = json.load(f)

    results = []
    for code, pred in predictions.items():
        name = stock_names.get(code, f"代码-{code}")
        results.append({
            "code": code,
            "name": name,
            "predicted_return": pred.get("predicted_return", 0),
            "signal": "看涨" if pred.get("predicted_return", 0) > 0.001 else ("看跌" if pred.get("predicted_return", 0) < -0.001 else "中性"),
            "confidence": "高" if pred.get("confidence", 0) > 0.8 else "中",
            "relative_strength": {"momentum": 0.8}
        })
    
    # 排序并返回全量沪深300数据（已增加前端滚动条）
    results.sort(key=lambda x: x['predicted_return'], reverse=True)
            
    return jsonify({
        "status": "success",
        "meta": {"model": "Qlib v17", "stocks": len(results)},
        "data": results
    })
