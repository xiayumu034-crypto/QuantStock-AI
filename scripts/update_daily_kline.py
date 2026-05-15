#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AKShare 全市场最新 K 线数据抓取引擎
从 stock_names.json 中读取今日最新活水池，下载历史 K 线，并自动编译为 Qlib 专用的 .bin 格式。
"""
import os
import json
import shutil
import pandas as pd
import akshare as ak
import datetime
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

STATUS_FILE = "data/pipeline_status.json"
CSV_DIR = "data/csv"

def write_status(status, progress, message):
    os.makedirs("data", exist_ok=True)
    state = {
        "status": status,
        "progress": progress,
        "message": message
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=4)

def fetch_single_stock(code, name):
    try:
        # qfq = 前复权，保证价格与技术指标不失真
        # 下载最近 2 年的数据足够推演 V19 的 MA/动量指标
        start_date = (datetime.datetime.now() - datetime.timedelta(days=730)).strftime("%Y%m%d")
        end_date = datetime.datetime.now().strftime("%Y%m%d")
        
        pure_code = code[-6:]
        df = ak.stock_zh_a_hist(symbol=pure_code, period="daily", start_date=start_date, end_date=end_date, adjust="hfq")
        
        if df.empty:
            return False, code
            
        # Qlib 需要的标准化列名
        df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount"
        }, inplace=True)
        
        df["symbol"] = code.upper() # sh600000 -> SH600000
        df["factor"] = 1.0 # 已经使用 hfq，factor设为1
        
        # 只保留需要的列
        cols = ["symbol", "date", "open", "close", "high", "low", "volume", "amount", "factor"]
        df = df[cols]
        
        csv_path = os.path.join(CSV_DIR, f"{code.upper()}.csv")
        df.to_csv(csv_path, index=False)
        return True, code
    except Exception as e:
        # 新浪等源可能偶尔超时
        return False, code

def main():
    write_status("running", 5, "正在清理旧的 K 线缓存...")
    if os.path.exists(CSV_DIR):
        shutil.rmtree(CSV_DIR)
    os.makedirs(CSV_DIR, exist_ok=True)
    
    stock_names_file = "data/stock_names.json"
    if not os.path.exists(stock_names_file):
        write_status("error", 0, "找不到活水股名单，请先运行 V0 海选")
        return
        
    with open(stock_names_file, "r", encoding="utf-8") as f:
        stock_pool = json.load(f)
        
    total_stocks = len(stock_pool)
    write_status("running", 10, f"准备使用 AKShare 多线程拉取 {total_stocks} 只活水股行情数据...")
    
    success_count = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_single_stock, code, name): code for code, name in stock_pool.items()}
        for i, future in enumerate(as_completed(futures)):
            success, code = future.result()
            if success:
                success_count += 1
                
            if i % 10 == 0 or i == total_stocks - 1:
                progress = 10 + int((i / total_stocks) * 50) # 占用进度条 10%-60%
                write_status("running", progress, f"AKShare 数据拉取中... 已下载 {success_count}/{total_stocks} 只标的")
                
    write_status("running", 65, "AKShare 原始 K 线下载完毕，准备编译为 Qlib 格式...")
    
    # 调用 dump_bin.py
    qlib_dir = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    os.makedirs(qlib_dir, exist_ok=True)
    
    dump_cmd = [
        "uv", "run", "python", "dump_bin.py", "dump_all",
        "--csv_path", CSV_DIR,
        "--qlib_dir", qlib_dir,
        "--symbol_field_name", "symbol",
        "--date_field_name", "date",
        "--include_fields", "open,close,high,low,volume,amount,factor"
    ]
    
    try:
        write_status("running", 70, "正在执行 Qlib 底层数据张量编译 (可能需要 1-2 分钟)...")
        subprocess.run(dump_cmd, capture_output=True, text=True, check=True)
        write_status("running", 90, "Qlib 数据更新成功！K 线矩阵已就绪。")
    except subprocess.CalledProcessError as e:
        write_status("error", 0, f"Qlib 编译失败: {e.stderr}")
        return
        
if __name__ == "__main__":
    main()
