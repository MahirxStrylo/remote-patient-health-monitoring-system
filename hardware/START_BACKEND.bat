@echo off
title Remote Health Monitor - Backend (FastAPI :8000)
color 0B
echo =====================================================================
echo   REMOTE PATIENT HEALTH MONITORING SYSTEM - FASTAPI BACKEND
echo   Starting server on http://localhost:8000
echo =====================================================================
echo.

:: Resolve project root and backend folder relative to this script
set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%..\backend"

if not exist "%BACKEND_DIR%" (
    color 0C
    echo [ERROR] Backend folder not found at: "%BACKEND_DIR%"
    echo Please make sure this script is located inside the 'hardware' directory.
    echo.
    pause
    exit /b 1
)

:: Change working directory to backend folder (supports any drive letter)
cd /d "%BACKEND_DIR%"

:: Check for existing Python virtual environments (local or root)
if exist "%BACKEND_DIR%\.venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment .venv...
    call "%BACKEND_DIR%\.venv\Scripts\activate.bat"
) else if exist "%BACKEND_DIR%\venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment venv...
    call "%BACKEND_DIR%\venv\Scripts\activate.bat"
) else if exist "%SCRIPT_DIR%..\.venv\Scripts\activate.bat" (
    echo [INFO] Activating root virtual environment .venv...
    call "%SCRIPT_DIR%..\.venv\Scripts\activate.bat"
) else if exist "%SCRIPT_DIR%..\venv\Scripts\activate.bat" (
    echo [INFO] Activating root virtual environment venv...
    call "%SCRIPT_DIR%..\venv\Scripts\activate.bat"
) else (
    echo [INFO] Using system Python environment...
)

:: Verify python executable is available
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    color 0C
    echo [ERROR] Python was not found in your PATH or virtual environment!
    echo Please install Python 3.11+ from https://www.python.org/
    echo and ensure "Add Python to PATH" is checked during installation.
    echo.
    pause
    exit /b 1
)

:: Display active python interpreter version
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [INFO] Python version: %%v
echo [INFO] Working directory: %CD%
echo.
echo [INFO] Starting Uvicorn ASGI server on port 8000...
echo [INFO] Localhost URL:      http://localhost:8000
echo [INFO] Local IPv4 URL:     http://127.0.0.1:8000
echo [INFO] API Documentation:  http://localhost:8000/docs
echo [INFO] Health Check:       http://localhost:8000/api/v1/health
echo [INFO] Telemetry Ingest:   http://localhost:8000/api/v1/ingest
echo =====================================================================
echo.

:: Launch FastAPI server with auto-reload enabled
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

:: Keep window open if server stops or crashes
echo.
echo [INFO] Server stopped.
pause
