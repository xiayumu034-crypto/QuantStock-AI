import os
import subprocess
import time
import json
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
        print(f"{desc} Failed:\n{result.stderr}")
        raise Exception(f"{desc} 失败，请查看后台日志")
    return result.stdout

def main():
    try:
        write_status("running", 10, "Starting Daily Ingestion Pipeline: download_ak_csv.py")
        
        # 1. 下载 CSV 数据
        run_cmd(["uv", "run", "python", "download_ak_csv.py"], "AKShare 数据下载")
        
        write_status("running", 50, "Data downloaded. Starting dump_bin.py")
        
        # 2. 编译为 Qlib 格式
        qlib_dir = os.path.expanduser("~/.qlib/qlib_data/cn_data")
        os.makedirs(qlib_dir, exist_ok=True)
        
        # note: download_ak_csv.py does not add a 'symbol' column, it just names the file properly
        dump_cmd = [
            "uv", "run", "python", "dump_bin.py", "dump_all",
            "--data_path", "csv_data",
            "--qlib_dir", qlib_dir,
            "--date_field_name", "date",
            "--include_fields", "open,close,high,low,volume,amount"
        ]
        
        run_cmd(dump_cmd, "Qlib 数据编译")
        
        write_status("finished", 100, "Daily Ingestion Pipeline Completed Successfully")
        print("Pipeline Completed Successfully")
        
    except Exception as e:
        traceback.print_exc()
        write_status("error", 0, str(e))

if __name__ == "__main__":
    main()
