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
            
            if status_code != 200:
                print(f"[FAIL] {endpoint} (HTTP {status_code}) - {elapsed:.2f}ms")
                return False
                
            if expected_type == "JSON":
                try:
                    data = json.loads(body)
                    if data.get("status") == "error":
                        # 收紧 WARN 判定：只有 v18 报告找不到时允许 WARN，其他所有 error 都为 FAIL
                        if endpoint == "/api/model_report?version=v18":
                            print(f"[WARN] {endpoint} ({elapsed:.2f}ms) - v18 report missing: {data.get('message', 'error')}")
                            return True
                        
                        print(f"[FAIL] {endpoint} ({elapsed:.2f}ms) - API Error: {data.get('message', 'unknown')}")
                        return False
                    
                    # 补充检查特定 warning (例如 v18 ml_predict_all 降级提示)
                    warning = data.get("meta", {}).get("warning", "") if isinstance(data, dict) and isinstance(data.get("meta"), dict) else ""
                    if warning:
                        print(f"[WARN] {endpoint} ({elapsed:.2f}ms) - warning: {warning}")
                    else:
                        print(f"[OK] {endpoint} ({elapsed:.2f}ms) - status: {data.get('status', 'N/A')}")
                except json.JSONDecodeError:
                    print(f"[FAIL] {endpoint} ({elapsed:.2f}ms) - Not valid JSON")
                    return False
            else:
                print(f"[OK] {endpoint} ({elapsed:.2f}ms) - length: {len(body)}")
                
            return True
            
    except urllib.error.URLError as e:
        if isinstance(e.reason, ConnectionRefusedError):
            print(f"\n[FATAL] Connection refused: {BASE_URL}")
            print(">>> Please start the server first: uv run app.py <<<\n")
            sys.exit(1)
        print(f"[FAIL] {endpoint} - URLError: {e.reason}")
        return False
    except Exception as e:
        print(f"[FAIL] {endpoint} - Exception: {e}")
        return False

def main():
    print("=" * 50)
    print("  QuantStock-AI Smoke Test")
    print("=" * 50)
    
    all_passed = True
    for endpoint, exp_type in ENDPOINTS:
        if not check_endpoint(endpoint, exp_type):
            all_passed = False
            
    print("=" * 50)
    if all_passed:
        print("Smoke Test: PASSED")
    else:
        print("Smoke Test: FAILED (Some endpoints failed)")
        sys.exit(1)

if __name__ == "__main__":
    main()
