import json
import os

PREDICTIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_output", "daily_predictions.json")
SAMPLE_PREDICTIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_output", "sample_daily_predictions.json")

def read_daily_predictions():
    """读取 Qlib 跑批生成的离线预测结果，Web端目前采用离线O(1)架构"""
    if os.path.exists(PREDICTIONS_FILE):
        with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 兼容带有 _meta 和 data 层级的新格式
            if isinstance(data, dict) and "data" in data and "_meta" in data:
                return data["data"], False, data["_meta"]
            return data, False, {}
    elif os.path.exists(SAMPLE_PREDICTIONS_FILE):
        with open(SAMPLE_PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and "data" in data and "_meta" in data:
                return data["data"], True, data["_meta"]
            return data, True, {}
    return {}, False, {}
