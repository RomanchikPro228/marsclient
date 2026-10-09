@echo off
title MarsClient Web Portal Server
color 0b
echo ===================================================
echo     MARSCLIENT OFFICIAL WEB PORTAL LAUNCHER
echo ===================================================
echo.
cd /d "%~dp0"
echo [INFO] Starting FastAPI server on http://localhost:8000 ...
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause
