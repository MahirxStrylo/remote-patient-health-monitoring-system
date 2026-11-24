@echo off
title Remote Health Monitor - ngrok Tunnel (:8000)
color 0E
echo =====================================================================
echo   REMOTE PATIENT HEALTH MONITORING SYSTEM - NGROK TUNNEL
echo   Forwarding public HTTP traffic to local backend port 8000
echo =====================================================================
echo.

:: Verify ngrok executable is available
where ngrok >nul 2>nul
if %ERRORLEVEL% neq 0 (
    color 0C
    echo [ERROR] ngrok was not found in your PATH!
    echo.
    echo To install ngrok:
    echo   1. Download ngrok from https://ngrok.com/download
    echo   2. Extract ngrok.exe and place it in your Windows PATH or WindowsApps
    echo   3. Connect your account: ngrok config add-authtoken ^<YOUR_TOKEN^>
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('ngrok --version 2^>^&1') do echo [INFO] ngrok version: %%v
echo [INFO] Target port: 8000 (FastAPI Backend)
echo [INFO] Using existing authenticated ngrok account configuration.
echo [INFO] Your public URL will appear below (e.g., https://xxxx.ngrok-free.app).
echo.
echo COPY the Forwarding URL and paste it into your Wokwi / ESP32 firmware:
echo   #define SERVER_HOST "xxxx.ngrok-free.app"
echo   #define SERVER_PORT 80
echo =====================================================================
echo.

:: Launch ngrok HTTP tunnel on port 8000 without exposing tokens in batch
ngrok http 8000

:: Keep window open if tunnel stops
echo.
echo [INFO] ngrok tunnel stopped.
pause
