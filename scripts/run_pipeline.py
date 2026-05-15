#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化联合推演流水线 (V19 -> V20)
从 stock_names.json 读取活水股，依次经过 V19 基础动能打分 和 V20 元标签防弹过滤。
"""
import os
import json
import time
import subprocess
import traceback

STATUS_FILE = "data/pipeline_status.json"

def write_status(status, progress, message):
    os.makedirs("data", exist_ok=True)
    state = {
        "status": status,
        "progress": progress,
        "message": message
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=4)

def run_cmd(cmd, desc):
    print(f"Executing: {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', env=env)
    if result.returncode != 0:
        print(f"{desc} Failed: {result.stderr}")
        raise Exception(f"{desc} 失败，请查看后台日志")
    return result.stdout

def main():
    write_status("running", 5, "流水线启动...")
    
    try:
        # Step 0: 使用 AKShare 更新最新 K 线数据
        write_status("running", 10, "正在启动 AKShare 行情抓取引擎...")
        cmd_kline = ["uv", "run", "python", "scripts/update_daily_kline.py"]
        # 直接运行但将输出丢给控制台，状态由 update_daily_kline.py 自己接管写入
        # 但为了避免状态文件被争抢覆盖，我们直接 run 并等待，因为 update_daily_kline 也会写 STATUS_FILE
        # 最好由 update_daily_kline 汇报进度 10 -> 90，然后我们接管 90 -> 100
        run_cmd(cmd_kline, "AKShare 历史 K 线拉取与编译")
        
        # Step 1: 运行 V19 推理
        write_status("running", 60, "正在运行 V19 旗舰版 (5模型集成) 提取量价动能...")
        cmd_v19 = ["uv", "run", "python", "infer_qlib_v19_ensemble.py"]
        run_cmd(cmd_v19, "V19 模型推理")
        
        # Step 2: 运行 V20 推理
        write_status("running", 70, "正在启动 AFML V20 元标签防弹引擎进行假突破拦截...")
        cmd_v20 = ["uv", "run", "python", "infer_afml_v20.py"]
        run_cmd(cmd_v20, "V20 元模型推理")
        
        write_status("finished", 100, "量化联合推演完成！潜力池与 Qlib 信号集已更新。")
        
    except Exception as e:
        traceback.print_exc()
        write_status("error", 0, str(e))

if __name__ == "__main__":
    main()
