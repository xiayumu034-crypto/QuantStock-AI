#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上线前全面检查"""
import sys, os

print("=" * 50)
print("  监控系统上线前检查")
print("=" * 50)

errors = []

# 1. Python环境
print(f"\n[1] Python: {sys.version}")

# 2. 依赖检查
try:
    import flask; print(f"[2] Flask: {flask.__version__}")
except Exception as e:
    errors.append(f"Flask: {e}")
    print(f"[2] Flask: FAILED - {e}")

try:
    import pandas; print(f"[3] Pandas: {pandas.__version__}")
except Exception as e:
    errors.append(f"Pandas: {e}")
    print(f"[3] Pandas: FAILED - {e}")

try:
    import requests; print(f"[4] Requests: {requests.__version__}")
except Exception as e:
    errors.append(f"Requests: {e}")
    print(f"[4] Requests: FAILED - {e}")

try:
    import numpy; print(f"[5] Numpy: {numpy.__version__}")
except Exception as e:
    errors.append(f"Numpy: {e}")
    print(f"[5] Numpy: FAILED - {e}")

try:
    import lightgbm; print(f"[6] LightGBM: {lightgbm.__version__}")
except Exception as e:
    errors.append(f"LightGBM: {e}")
    print(f"[6] LightGBM: FAILED - {e}")

try:
    import akshare; print(f"[7] AKShare: {akshare.__version__}")
except Exception as e:
    errors.append(f"AKShare: {e}")
    print(f"[7] AKShare: FAILED - {e}")

# 3. 文件检查
files = {
    "app.py": "app.py",
    "templates/index.html": "templates/index.html",
    "model_output/lgb_model_v16.pkl": "model_output/lgb_model_v16.pkl",
    "model_output/features_v16.json": "model_output/features_v16.json",
}
for name, path in files.items():
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"[8] {name}: OK ({size:,} bytes)")
    else:
        errors.append(f"{name} not found")
        print(f"[8] {name}: MISSING!")

# 4. 语法检查
try:
    with open("app.py", encoding="utf-8") as f:
        compile(f.read(), "app.py", "exec")
    print("[9] app.py syntax: OK")
except SyntaxError as e:
    errors.append(f"app.py syntax: {e}")
    print(f"[9] app.py syntax: FAILED - {e}")

# 5. 新浪财经数据源测试
try:
    import requests as req
    r = req.get("http://hq.sinajs.cn/list=sz300201",
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"},
                timeout=5)
    if r.status_code == 200 and "300201" in r.text:
        print("[10] Sina Finance API: OK")
    else:
        errors.append("Sina Finance API failed")
        print(f"[10] Sina Finance API: FAILED ({r.status_code})")
except Exception as e:
    errors.append(f"Sina Finance API: {e}")
    print(f"[10] Sina Finance API: FAILED - {e}")

# 总结
print("\n" + "=" * 50)
if errors:
    print(f"  结果: {len(errors)} 个问题")
    for e in errors:
        print(f"  ! {e}")
else:
    print("  结果: 全部通过! ✅")
print("=" * 50)
