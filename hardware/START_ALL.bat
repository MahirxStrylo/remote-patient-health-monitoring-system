@echo off
title Remote Health Monitor - Master Launcher
color 0F
echo =====================================================================
echo   REMOTE PATIENT HEALTH MONITORING SYSTEM - MASTER LAUNCHER
echo   University Engineering Prototype
echo =====================================================================
echo.
echo This master script will launch all three required services:
echo   1. FastAPI Backend Server       (Port 8000)
echo   2. React Doctor Dashboard       (Port 5173)
echo   3. ngrok Cellular/Wokwi Tunnel  (Port 8000 -^> Public URL)
echo.
echo Each service will open in its own dedicated Command Prompt window.
echo Please keep all three windows open while using the system.
echo =====================================================================
echo.

set "SCRIPT_DIR=%~dp0"

:: 1. Launch FastAPI Backend
echo [*] [1/3] Launching FastAPI Backend Server (Port 8000)...
start "Remote Health Monitor - Backend (:8000)" cmd /k ""%SCRIPT_DIR%START_BACKEND.bat""

:: Short delay to allow backend to bind socket
echo [*] Waiting 3 seconds for backend to initialize...
timeout /t 3 /nobreak >nul

:: 2. Launch React Frontend
echo [*] [2/3] Launching React Doctor Dashboard (Port 5173)...
start "Remote Health Monitor - Frontend (:5173)" cmd /k ""%SCRIPT_DIR%START_FRONTEND.bat""

:: Short delay to allow frontend to start
echo [*] Waiting 3 seconds for frontend to initialize...
timeout /t 3 /nobreak >nul

:: 3. Launch ngrok Tunnel
echo [*] [3/3] Launching ngrok HTTP Tunnel (:8000)...
start "Remote Health Monitor - ngrok Tunnel" cmd /k ""%SCRIPT_DIR%START_NGROK.bat""

:: Short delay before opening browser
timeout /t 2 /nobreak >nul

:: 4. Automatically open Dashboard in default browser
echo [*] Opening Doctor Dashboard in your default web browser...
start http://localhost:5173

echo.
echo =====================================================================
echo   ALL THREE SERVICES ARE RUNNING!
echo =====================================================================
echo.
echo   - Doctor Dashboard:    http://localhost:5173
echo     (Alternative IPv4):  http://127.0.0.1:5173
echo   - Backend Swagger API: http://localhost:8000/docs
echo   - Backend Health:      http://localhost:8000/api/v1/health
echo   - ngrok Public Tunnel: Check the yellow ngrok window for public URL
echo.
echo   Login Credentials:
echo     Username: admin
echo     Password: admin123
echo.
echo   Wokwi ESP32 Simulation:
echo     Open Wokwi in your browser, paste the ngrok URL into firmware,
echo     and click the green Play button.
echo.
echo   To STOP the system:
echo     Simply close the three opened Command Prompt windows.
echo =====================================================================
echo.
echo You may minimize this window or press any key to close this launcher.
pause >nul
