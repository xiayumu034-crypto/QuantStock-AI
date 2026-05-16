from flask import Blueprint, jsonify, request
import os
import json

settings_bp = Blueprint('settings', __name__)
CONFIG_FILE = "data/ai_config.json"

@settings_bp.route('/api/settings/ai', methods=['GET'])
def get_ai_settings():
    config = {
        "api_key": "",
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "model": "mimo-v2.5-pro"
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            try:
                config.update(json.load(f))
            except:
                pass
    return jsonify({"status": "success", "data": config})

@settings_bp.route('/api/settings/ai', methods=['POST'])
def save_ai_settings():
    data = request.json
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return jsonify({"status": "success", "message": "AI 配置保存成功！"})