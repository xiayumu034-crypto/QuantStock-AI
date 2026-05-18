from flask import Blueprint, jsonify, request
import json
import os
import subprocess
import time
from data.market_data import StockDataAPI
from api.model_service import read_daily_predictions

model_bp = Blueprint('model', __name__)
stock_api = StockDataAPI()

TRADE_LOGS_FILE = "model_output/trade_logs.json"
SAMPLE_TRADE_LOGS_FILE = "model_output/sample_trade_logs.json"

@model_bp.route('/api/run_backtest', methods=['POST'])
def run_backtest():
    data = request.json
    start_date = data.get('start_date', '2024-01-01')
    end_date = data.get('end_date', '2025-01-01')
    
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backtest_v20_system.py")
    cwd_path = os.path.dirname(os.path.dirname(__file__))
    try:
        # 运行回测脚本，由于抽样了数据，通常耗时在几秒内，这里阻塞等待
        import sys
        python_exe = sys.executable
        subprocess.run([python_exe, script_path, start_date, end_date], check=True, cwd=cwd_path)
        return jsonify({"status": "success", "message": "回测执行完成"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": f"回测执行失败: {str(e)}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@model_bp.route('/api/backtest_report')
def get_backtest_report():
    report_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "model_output", "backtest_report_v20.json")
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            return jsonify({"status": "success", "data": json.load(f)})
    return jsonify({"status": "error", "message": "回测报告尚未生成"})

@model_bp.route('/api/model_report')
def get_model_report():
    version = request.args.get('version', 'v18')
    report_file = f"model_output/model_report_{version}.json"
    if os.path.exists(report_file):
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                return jsonify({"status": "success", "data": json.load(f)})
        except Exception as e:
            return jsonify({"status": "error", "message": f"解析评估报告失败: {str(e)}"})
    return jsonify({"status": "error", "message": f"暂无离线模型评估报告，请先运行 evaluate_model.py --version {version}"})

@model_bp.route('/api/signal_quality')
def get_signal_quality():
    version = request.args.get('version', 'v19')
    report_file = f"model_output/signal_quality_{version}.json"
    if os.path.exists(report_file):
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                return jsonify({"status": "success", "data": json.load(f)})
        except Exception as e:
            return jsonify({"status": "error", "message": f"解析信号质量报告失败: {str(e)}"})
    return jsonify({"status": "error", "message": "未生成"})

@model_bp.route('/api/predict/<stock_code>')
def get_prediction(stock_code):
    clean_code = stock_code[-6:]
    result = stock_api.predict_next_5_minutes(clean_code)
    return jsonify({"status": "success", "data": result})

@model_bp.route('/api/trade_logs')
def get_trade_logs():
    if os.path.exists(TRADE_LOGS_FILE):
        with open(TRADE_LOGS_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                # Ensure we extract the list if it's wrapped
                logs = data.get("data", []) if isinstance(data, dict) else data
                return jsonify({"status": "success", "data": logs})
            except:
                pass
    if os.path.exists(SAMPLE_TRADE_LOGS_FILE):
        with open(SAMPLE_TRADE_LOGS_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                logs = data.get("data", []) if isinstance(data, dict) else data
                return jsonify({"status": "success", "data": logs})
            except:
                pass
    return jsonify({"status": "success", "data": []})

@model_bp.route('/api/trade/manual', methods=['POST'])
def manual_trade():
    data = request.json
    code = data.get('code', '')
    direction = data.get('direction', '')
    price = data.get('price', 0)
    volume = data.get('volume', 0)
    
    # P2级别修复：严格校验输入参数
    if not code or len(str(code)) != 6 or not str(code).isdigit():
        return jsonify({"status": "error", "message": "无效的股票代码，必须为6位数字"})
    if direction not in ['buy', 'sell']:
        return jsonify({"status": "error", "message": "交易方向只能为 buy 或 sell"})
    if not isinstance(volume, int) or volume <= 0 or volume % 100 != 0:
        return jsonify({"status": "error", "message": "交易数量必须是100的整数倍"})
    if float(price) < 0:
        return jsonify({"status": "error", "message": "价格不能为负数"})
    
    # 模拟鉴权及环境变量判断
    trade_mode = os.environ.get("TRADE_MODE", "mock")
    if trade_mode == "mock":
        # 追加一条 mock 日志到真实的运行时 TRADE_LOGS_FILE，不要弄脏被 tracked 的 sample
        mock_log = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "direction": direction,
            "direction_label": f"手工{'买入' if direction == 'buy' else '卖出'}",
            "source": "manual",
            "code": code,
            "price": price,
            "volume": volume,
            "status": "已成交(Mock)"
        }
        
        logs = []
        if os.path.exists(TRADE_LOGS_FILE):
            try:
                with open(TRADE_LOGS_FILE, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    logs = file_data.get("data", []) if isinstance(file_data, dict) else file_data
            except:
                pass
        else:
            # 如果运行时文件还不存在，先从 sample 复制打底
            if os.path.exists(SAMPLE_TRADE_LOGS_FILE):
                try:
                    with open(SAMPLE_TRADE_LOGS_FILE, 'r', encoding='utf-8') as f:
                        sample_data = json.load(f)
                        logs = sample_data.get("data", []) if isinstance(sample_data, dict) else sample_data
                except:
                    pass

        logs.insert(0, mock_log)
        
        with open(TRADE_LOGS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"status": "success", "data": logs}, f, ensure_ascii=False, indent=4)
            
        return jsonify({"status": "success", "message": f"[Mock模式] 模拟指令发送成功: {direction} {code} {volume}股"})

    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        vnpy_python = os.environ.get("VNPY_PYTHON", os.path.join(base_dir, ".venv_vnpy", "Scripts", "python.exe"))
        
        cmd = [
            vnpy_python, 
            "trade_manual_executor.py", 
            str(code), 
            str(direction), 
            str(price), 
            str(volume)
        ]
        subprocess.Popen(cmd, cwd=base_dir)
        return jsonify({"status": "success", "message": f"实盘交易指令已发送: {direction} {code}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@model_bp.route('/api/ml_predict/<stock_code>')
def get_ml_prediction(stock_code):
    """直接从离线 JSON 中读取预测结果，支持带前缀的代码"""
    version = request.args.get('version', 'v18')
    clean_code = stock_code[-6:]
    predictions, is_sample, meta = read_daily_predictions(version)
    
    if clean_code in predictions:
        pred_data = predictions[clean_code]
        # 对齐全量接口的 signal 判定逻辑
        pred_val = pred_data.get("predicted_return", 0)
        momentum = pred_data.get("momentum", 0.8)
        
        signal = "中性"
        if pred_val > 0.015: signal = "强烈看涨" if momentum > 0.5 else "看涨"
        elif pred_val > 0.005: signal = "看涨"
        elif pred_val < -0.01: signal = "看跌"

        return jsonify({
            "status": "success",
            "data": {
                "predicted_return": pred_val,
                "signal": signal,
                "confidence": "高" if pred_val > 0.02 else "中"
            },
            "meta": {"sample": is_sample, "model": meta.get("model_version", version)}
        })
    else:
        return jsonify({"status": "error", "message": f"暂无 {clean_code} 的离线预测数据"})

@model_bp.route('/api/ml_predict_all')
def get_ml_predict_all():
    """获取全量预测结果"""
    version = request.args.get('version', 'v18')
    predictions, is_sample, meta = read_daily_predictions(version)
    
    # v18/v19 没有预测数据时，直接返回空列表和提示，不要 fallback 给 v17 的伪装
    if version in ("v18", "v19", "v19_ensemble", "v20") and not predictions:
        model_name_map = {
            "v18": "Qlib v18",
            "v19": "v19 Ensemble",
            "v19_ensemble": "v19 Ensemble",
            "v20": "AFML v20"
        }
        return jsonify({
            "status": "success",
            "meta": {
                "model": model_name_map.get(version, version),
                "stocks": 0,
                "sample": False,
                "warning": f"{version} 模型预测数据不存在，请在服务器上运行对应的训练或推理脚本。"
            },
            "data": []
        })
    
    # 加载股票名称映射
    names_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stock_names.json")
    stock_names = {}
    if os.path.exists(names_file):
        with open(names_file, 'r', encoding='utf-8') as f:
            stock_names = json.load(f)

    results = []
    all_returns = [pred.get("predicted_return", 0) for pred in predictions.values()]
    if all_returns and version in ("v18", "v19", "v19_ensemble", "v20"):
        all_returns_sorted = sorted(all_returns)
        n = len(all_returns_sorted)
        p90 = all_returns_sorted[int(n * 0.9)] if n > 0 else 0.015
        p70 = all_returns_sorted[int(n * 0.7)] if n > 0 else 0.005
        p30 = all_returns_sorted[int(n * 0.3)] if n > 0 else -0.01
    else:
        p90, p70, p30 = 0.015, 0.005, -0.01

    for code, pred in predictions.items():
        name = stock_names.get(code, f"代码-{code}")
        
        # 融合逻辑：AI收益 + 动量强度 + 信号共振
        pred_val = pred.get("predicted_return", 0)
        momentum = pred.get("momentum", 0.8) # 默认动量
        
        # 对于 V20 元模型，直接通过置信度(meta_score)判别信号
        if version == "v20":
            meta_score = pred.get("meta_score", 0)
            if meta_score >= 0.6:
                signal = "强烈看涨"
            elif meta_score >= 0.4:
                signal = "看涨中"
            else:
                signal = "中性"
        else:
            # 动态分位数融合算法（适配不同模型的数值缩放）
            signal = "中性"
            if pred_val >= p90:
                signal = "强烈看涨" if momentum > 0.5 else "看涨"
            elif pred_val >= p70:
                signal = "看涨"
            elif pred_val <= p30:
                signal = "看跌"
            
        results.append({
            "code": code,
            "name": name,
            "predicted_return": pred.get("meta_score", pred_val) if version == "v20" else pred_val, # 前端按这个排序
            "raw_return": pred_val,
            "signal": signal,
            "confidence": "高" if signal == "强烈看涨" else "中",
            "relative_strength": {"momentum": momentum}
        })
    
    # 排序并返回全量沪深300数据（已增加前端滚动条）
    results.sort(key=lambda x: x['predicted_return'], reverse=True)
            
    return jsonify({
        "status": "success",
        "meta": {"model": meta.get("model_version", f"Qlib {version}"), "stocks": len(results), "sample": is_sample},
        "data": results
    })

# =================================================================================
# V21 Weekly Swing Module APIs
# =================================================================================

@model_bp.route('/api/weekly_predict_all', methods=['GET'])
def get_weekly_predictions():
    pred_path = "model_output/daily_predictions_v21_weekly.json"
    if not os.path.exists(pred_path):
        return jsonify({"status": "error", "message": "暂无 V21 预测结果，请先运行推理脚本或等待生成"})
    try:
        with open(pred_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"status": "success", "data": data.get("data", {}), "meta": data.get("meta", {})})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@model_bp.route('/api/weekly_model_report', methods=['GET'])
def get_weekly_model_report():
    report_path = "model_output/model_report_v21_weekly.json"
    if not os.path.exists(report_path):
        return jsonify({"status": "error", "message": "暂无 V21 模型报告"})
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@model_bp.route('/api/weekly_backtest_report', methods=['GET'])
def get_weekly_backtest_report():
    report_path = "model_output/backtest_report_v21_weekly.json"
    if not os.path.exists(report_path):
        return jsonify({"status": "error", "message": "暂无 V21 回测报告"})
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@model_bp.route('/api/weekly_train/start', methods=['POST'])
def start_weekly_train():
    status_file = "model_output/v21_train_status.json"
    try:
        # Prevent multiple runs
        if os.path.exists(status_file):
            with open(status_file, "r", encoding="utf-8") as f:
                st = json.load(f)
                if st.get("status") == "running":
                    return jsonify({"status": "error", "message": "训练任务已在运行中"})
        
        # Start async process
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        subprocess.Popen(["uv", "run", "python", "train_weekly_swing_v21.py"], env=env)
        
        # Initial status
        os.makedirs("model_output", exist_ok=True)
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump({"status": "running", "progress": 0, "message": "正在启动训练进程..."}, f, ensure_ascii=False)
            
        return jsonify({"status": "success", "message": "已在后台启动 V21 训练任务"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@model_bp.route('/api/weekly_train/status', methods=['GET'])
def get_weekly_train_status():
    status_file = "model_output/v21_train_status.json"
    if not os.path.exists(status_file):
        return jsonify({"status": "success", "data": {"status": "idle", "progress": 0, "message": "尚未启动训练"}})
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
