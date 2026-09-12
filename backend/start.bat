@echo off
title SURVILLENCE TRAFFIC — Local Server
echo.
echo  ============================================================
echo   SURVILLENCE TRAFFIC — Starting Local Application
echo  ============================================================
echo.
echo  Installing backend dependencies...
pip install flask flask-cors --quiet
echo.
echo  Starting server at http://localhost:5000
echo  Press Ctrl+C to stop.
echo.
python "%~dp0server.py"
pause
