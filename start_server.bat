@echo off
echo ========================================================
echo   Starting Remote Health Monitoring FastAPI Backend
echo ========================================================
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
