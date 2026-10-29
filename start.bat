@echo off
title Ultron Desktop Assistant
echo ===================================================
echo             ULTRON DESKTOP AI ASSISTANT            
echo ===================================================

cd /d "%~dp0"

:: 1. Start Python Backend
echo [*] Launching Ultron Backend service...
if "%1"=="--console" (
    start "Ultron Backend" /d "%~dp0ultron-backend" "%~dp0venv\Scripts\python.exe" "%~dp0ultron-backend\server.py"
) else (
    start "Ultron Backend" /d "%~dp0ultron-backend" "%~dp0venv\Scripts\pythonw.exe" "%~dp0ultron-backend\server.py"
)


:: Wait 2 seconds for WebSocket server to bind
ping 127.0.0.1 -n 3 >nul

:: 2. Start Electron UI
echo [*] Launching Ultron Holographic Overlay...
cd "%~dp0ultron-ui"
start "" "%~dp0ultron-ui\node_modules\.bin\electron.cmd" .

echo [OK] Ultron is active and running in system tray.
