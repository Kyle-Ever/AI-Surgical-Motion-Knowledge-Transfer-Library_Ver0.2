@echo off
chcp 65001 >nul
echo ========================================
echo AI Surgical Motion Knowledge Transfer Library - Start All
echo ========================================

echo Starting both backend and frontend servers...
echo.

echo Starting backend server...
start "Backend Server" cmd /k "start_backend.bat"

echo Waiting 3 seconds...
timeout /t 3 /nobreak >nul

echo Starting frontend server...
start "Frontend Server" cmd /k "start_frontend.bat"

echo.
echo ========================================
echo Both servers have been started
echo ========================================
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo API Documentation: http://localhost:8000/docs
echo.
echo To stop each server, press Ctrl+C in the corresponding command window
echo.

pause

