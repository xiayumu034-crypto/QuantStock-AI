@echo off
chcp 65001 >nul
echo ==============================
echo  QuantStock-AI v2.2 (uv)
echo  A股量化预测系统
echo ==============================
echo.

where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 系统中未找到 uv，请先安装 uv (https://docs.astral.sh/uv/getting-started/installation/)
    echo 或者使用原版 Python 运行: python app.py
    pause
    exit /b 1
)

echo [1/3] Syncing dependencies...
call uv sync

echo.
echo [2/3] Running preflight check...
call uv run preflight_check.py
if %errorlevel% neq 0 (
    echo [警告] 核心预检失败，可能无法启动。
)

echo.
echo [3/3] Starting Flask server...
echo Open http://localhost:5000 in your browser
echo.
set TRADE_MODE=mock
call uv run app.py
pause
