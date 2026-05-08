@echo off
echo ==============================
echo  QuantStock-AI v2.2
echo  A股量化预测系统
echo ==============================
echo.
echo [1/2] Running preflight check...
python preflight_check.py
echo.
echo [2/2] Starting Flask server...
echo Open http://localhost:5000 in your browser
echo.
python app.py
pause
