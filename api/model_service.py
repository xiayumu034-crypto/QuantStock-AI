import os
import pickle
import json

MODEL_PATH = "model_output/lgb_model_v17.pkl"
FEATURE_COLS_PATH = "model_output/features_v17.json"

ml_model = None
ml_features = None

def load_ml_model():
    global ml_model, ml_features
    try:
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, 'rb') as f:
                model_data = pickle.load(f)
            
            if isinstance(model_data, dict) and 'models' in model_data:
                ml_model = model_data
                print(f"[ML] v16集成模型加载成功 ({model_data['n_models']}个模型)")
            else:
                ml_model = model_data
                print("[ML] v15模型加载成功")
            
            if os.path.exists(FEATURE_COLS_PATH):
                with open(FEATURE_COLS_PATH, 'r') as f:
                    ml_features = json.load(f)
                print(f"[ML] 特征加载成功: {len(ml_features)}个")
            return True
    except Exception as e:
        print(f"[ML] 模型加载失败: {e}")
    return False

def get_ml_model():
    return ml_model

def get_ml_features():
    return ml_features
