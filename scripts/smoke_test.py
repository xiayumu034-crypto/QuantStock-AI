#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import urllib.error
import json
import time
import sys

BASE_URL = "http://127.0.0.1:5000"

ENDPOINTS = [
    ("/", "HTML"),
    ("/api/ml_predict_all?version=v17", "JSON"),
    ("/api/ml_predict_all?version=v18", "JSON"),
    ("/api/model_report?version=v17", "JSON"),
    ("/api/model_report?version=v18", "JSON"),
    ("/api/news", "JSON"),
    ("/api/search?q=300201", "JSON"),
    ("/api/trade_logs", "JSON")
]

def check_endpoint(endpoint, expected_type):
    url = f"{BASE_URL}{endpoint}"
    start_time = time.time()
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SmokeTest/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            status_code = response.getcode()
            body = response.read().decode('utf-8')
            elapsed = (time.time() - start_time) * 1000
            
            if expected_type == "JSON":
                try:
                    data = json.loads(body)
                    status = data.get("status", "unknown")
                    # v18 报告缺失或者预测缺失的情况，如果 status 是 error 或者虽然 success 但没数据且带 warning，记录为 WARN
                    if status == "error":
                        if "v18" in endpoint or "model_report" in endpoint:
                             return "WARN", elapsed, f"Status: error, Msg: {data.get('message', '')[:40]}"
                        return "FAIL", elapsed, f"API error: {data.get('message', '')}"
                    if status == "success" and data.get("meta", {}).get("warning"):
                        return "WARN", elapsed, f"Status: success (with warning)"
                    return "OK", elapsed, f"Status: {status}, Data Len: {len(str(data))}"
                except json.JSONDecodeError:
                    return "FAIL", elapsed, "Invalid JSON"
            
            return "OK", elapsed, f"Len: {len(body)}"
            
    except urllib.error.URLError as e:
        return "FAIL", 0, str(e)
    except Exception as e:
        return "FAIL", 0, str(e)

def main():
    print("=" * 60)
    print(f"  QuantStock-AI End-to-End Smoke Test")
    print("=" * 60)
    
    # 检查根路径连通性，如果不通直接提示退出
    try:
        urllib.request.urlopen(BASE_URL, timeout=3)
    except urllib.error.URLError:
        print(f"\n[FATAL] 无法连接到 {BASE_URL}！")
        print("请先启动 Web 服务：uv run app.py")
        sys.exit(1)
        
    has_error = False
    
    for endpoint, expected_type in ENDPOINTS:
        res_status, elapsed, msg = check_endpoint(endpoint, expected_type)
        
        status_color = res_status
        if res_status == "OK":
            status_color = "\033[92m[OK]\033[0m"
        elif res_status == "WARN":
            status_color = "\033[93m[WARN]\033[0m"
        else:
            status_color = "\033[91m[FAIL]\033[0m"
            has_error = True
            
        print(f"{status_color} {endpoint:<35} | {elapsed:>5.0f}ms | {msg}")
        
    print("=" * 60)
    if has_error:
        print("\033[91m测试未完全通过，请检查 FAIL 项。\033[0m")
        sys.exit(1)
    else:
        print("\033[92m测试通过！核心链路畅通。\033[0m")

if __name__ == "__main__":
    main()