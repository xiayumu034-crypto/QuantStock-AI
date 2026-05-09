#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上线前全面检查"""
import sys, os
import shutil

print("=" * 50)
print("  监控系统上线前检查 (uv 环境)")
print("=" * 50)

errors = []

# 0. 环境路径和配置
print(f"\n[0] Executable: {sys.executable}")
print(f"    TRADE_MODE: {os.environ.get('TRADE_MODE', '未设置 (默认 mock)')}")
uv_path = shutil.which("uv")
print(f"    UV Path: {uv_path if uv_path else '未找到'}")

# 1. Python环境
print(f"\n[1] Python: {sys.version.split(' ')[0]}")

# 2. 依赖检查
try:
    import flask; print(f"[2] Flask: {flask.__version__}")
except Exception as e:
    errors.append(f"Flask 缺失: {e}")
    print(f"[2] Flask: FAILED - {e}")

try:
    import pandas; print(f"[3] Pandas: {pandas.__version__}")
except Exception as e:
    errors.append(f"Pandas 缺失: {e}")
    print(f"[3] Pandas: FAILED - {e}")

try:
    import requests; print(f"[4] Requests: {requests.__version__}")
except Exception as e:
    errors.append(f"Requests 缺失: {e}")
    print(f"[4] Requests: FAILED - {e}")

# 可选依赖检查 (不报错)
print("\n[可选依赖检查 (WARNING ONLY)]")
try:
    import qlib
    print("  [OK] pyqlib 已安装")
except ImportError:
    print("  [WARN] pyqlib 未安装 (仅影响离线训练/推理，Web大屏仍可运行)")

try:
    import vnpy
    print("  [OK] vnpy 已安装")
except ImportError:
    print("  [WARN] vnpy 未安装 (仅影响实盘自动交易)")

# 3. 核心文件检查
print("\n[5] 核心资源检查...")
files = {
    "app.py": "app.py",
    "templates/index.html": "templates/index.html",
    "data/stock_names.json": "data/stock_names.json",
    "model_output/sample_daily_predictions.json": "model_output/sample_daily_predictions.json"
}
for name, path in files.items():
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"  [OK] {name}: OK ({size:,} bytes)")
    else:
        errors.append(f"核心文件缺失: {name}")
        print(f"  [FAIL] {name}: MISSING!")

# 附加警告检查：真实预跑批产物
print("\n[6] 跑批产物检查 (WARNING ONLY)...")
runtime_files = [
    "model_output/daily_predictions.json",
    "model_output/daily_predictions_v18.json",
    "model_output/trade_logs.json"
]
for p in runtime_files:
    if not os.path.exists(p):
        print(f"  [WARN] 缺少运行时数据: {p} (系统将降级使用 sample 数据或静默忽略)")
    else:
        print(f"  [OK] 发现数据: {p}")

# 4. 网络检查 (仅警告)
print("\n[7] 网络连通性测试 (WARNING ONLY)...")
try:
    import requests as req
    r = req.get("http://hq.sinajs.cn/list=sz300201",
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"},
                timeout=3)
    if r.status_code == 200 and "300201" in r.text:
        print("  [OK] 新浪财经行情接口: OK")
    else:
        print(f"  [WARN] 新浪财经接口异常 (HTTP {r.status_code})")
except Exception as e:
    print(f"  [WARN] 新浪财经接口无法连接: {e}")

# 总结
print("\n" + "=" * 50)
if errors:
    print(f"  结果: {len(errors)} 个致命错误 (阻断启动)")
    for e in errors:
        print(f"  ! {e}")
    sys.exit(1)
else:
    print("  结果: 核心检查全部通过! [OK] 可以安全启动。")
print("=" * 50)
