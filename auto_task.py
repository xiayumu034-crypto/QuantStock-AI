import time
import subprocess
import sys
import os

def run_pipeline():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始全自动量化流水线...")
    
    # 1. 抓取最新数据
    print("Step 1: 抓取最新数据...")
    subprocess.run([sys.executable, "fetch_hs300_qlib.py"])
    
    # 2. 运行模型推理
    print("Step 2: 运行 AI 模型推理...")
    subprocess.run([sys.executable, "daily_inference.py"])
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 流水线执行完毕，预测结果已更新。")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        print("进入循环监控模式，每日 15:15 自动触发...")
        while True:
            now = time.localtime()
            # 每天 15:15 触发（数据同步后）
            if now.tm_hour == 15 and now.tm_min == 15:
                run_pipeline()
                time.sleep(60) # 防止在一分钟内多次触发
            time.sleep(30)
    else:
        run_pipeline()
