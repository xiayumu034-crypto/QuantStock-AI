from flask import Flask
import os
from api.routes_market import market_bp
from api.routes_model import model_bp
from api.model_service import load_ml_model

app = Flask(__name__)

# Register Blueprints
app.register_blueprint(market_bp)
app.register_blueprint(model_bp)

if __name__ == '__main__':
    # 启动时加载模型
    load_ml_model()
    
    # 从环境变量读取配置，默认开发模式
    is_dev = os.environ.get("FLASK_ENV", "development") == "development"
    server_port = int(os.environ.get("FLASK_PORT", 5000))
    
    print(f"QuantStock-AI 启动于 127.0.0.1:{server_port} | 模式: {'开发(热更新)' if is_dev else '生产'}")
    
    # 启动Flask应用
    app.run(debug=is_dev, host='127.0.0.1', port=server_port)
