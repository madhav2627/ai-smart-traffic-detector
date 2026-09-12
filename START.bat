@echo off
title SURVILLENCE TRAFFIC
echo.
echo  ============================================================
echo   SURVILLENCE TRAFFIC — AI Traffic Surveillance Platform
echo  ============================================================
echo.
echo  [1/3] Installing detector dependencies...
cd /d "%~dp0traffic_ai_complete_improved"
pip install -r requirements.txt --quiet
echo.
echo  [2/3] Installing backend dependencies...
cd /d "%~dp0backend"
pip install flask flask-cors --quiet
echo.
echo  [3/3] Starting SURVILLENCE TRAFFIC at http://localhost:5000
echo.
echo  Open your browser and go to: http://localhost:5000
echo  Press Ctrl+C to stop.
echo.
python server.py
pause
