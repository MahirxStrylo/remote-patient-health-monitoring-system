@echo off
title Remote Health Monitor - Frontend (React :5173)
color 0A
echo =====================================================================
echo   REMOTE PATIENT HEALTH MONITORING SYSTEM - REACT DASHBOARD
echo   Starting development server on http://localhost:5173
echo =====================================================================
echo.

:: Resolve project root and frontend folder relative to this script
set "SCRIPT_DIR=%~dp0"
set "FRONTEND_DIR=%SCRIPT_DIR%..\frontend"

if not exist "%FRONTEND_DIR%" (
    color 0C
    echo [ERROR] Frontend folder not found at: "%FRONTEND_DIR%"
    echo Please make sure this script is located inside the 'hardware' directory.
    echo.
    pause
    exit /b 1
)

:: Change working directory to frontend folder (supports any drive letter)
cd /d "%FRONTEND_DIR%"

:: Verify Node.js / npm is available
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    color 0C
    echo [ERROR] npm was not found in your PATH!
    echo Please install Node.js v18 or higher from https://nodejs.org/
    echo and make sure it is added to your system PATH.
    echo.
    pause
    exit /b 1
)

:: Verify node_modules exists
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [WARN] node_modules not found. Installing frontend dependencies...
    call npm install
    if %ERRORLEVEL% neq 0 (
        color 0C
        echo [ERROR] npm install failed. Please check your internet connection.
        pause
        exit /b 1
    )
)

:: Display node and npm versions
for /f "tokens=*" %%v in ('node -v 2^>^&1') do echo [INFO] Node.js version: %%v
for /f "tokens=*" %%v in ('npm -v 2^>^&1') do echo [INFO] npm version:     %%v
echo [INFO] Working directory: %CD%
echo.
echo [INFO] Starting Vite development server on port 5173...
echo [INFO] Localhost URL:  http://localhost:5173
echo [INFO] Local IPv4 URL: http://127.0.0.1:5173
echo =====================================================================
echo.

:: Launch Vite dev server
call npm run dev

:: Keep window open if process terminates
echo.
echo [INFO] Frontend server stopped.
pause
