import json
import os

PREDICTIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_output", "daily_predictions.json")
SAMPLE_PREDICTIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_output", "sample_daily_predictions.json")

PREDICTIONS_FILE_V18 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_output", "daily_predictions_v18.json")
PREDICTIONS_FILE_V19 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_output", "daily_predictions_v19.json")
PREDICTIONS_FILE_V20 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_output", "daily_predictions_v20.json")

def read_daily_predictions(version="v17"):
    """读取跑批生成的离线预测结果，Web端目前采用离线O(1)架构"""
    if version == "v20":
        if os.path.exists(PREDICTIONS_FILE_V20):
            with open(PREDICTIONS_FILE_V20, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "data" in data and "_meta" in data:
                    return data["data"], False, data["_meta"]
                return data, False, {}
        # 如果 V20 不存在，降级读取 V19
        if os.path.exists(PREDICTIONS_FILE_V19):
            with open(PREDICTIONS_FILE_V19, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "data" in data and "_meta" in data:
                    return data["data"], False, data["_meta"]
                return data, False, {}
        return {}, False, {}
        
    if version in ("v19", "v19_ensemble"):
        if os.path.exists(PREDICTIONS_FILE_V19):
            with open(PREDICTIONS_FILE_V19, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "data" in data and "_meta" in data:
                    return data["data"], False, data["_meta"]
                return data, False, {}
        return {}, False, {}
        
    if version == "v18":
        if os.path.exists(PREDICTIONS_FILE_V18):
            with open(PREDICTIONS_FILE_V18, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "data" in data and "_meta" in data:
                    return data["data"], False, data["_meta"]
                return data, False, {}
        # v18 没有时返回空
        return {}, False, {}

    # 默认 v17 逻辑
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
