@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
echo ========================================
echo Backend Server Restart (Python 3.11)
echo ========================================

set "SCRIPT_DIR=%~dp0"

echo Checking for existing backend process on port 8000...
echo.

rem Kill any process using port 8000
set "KILLED=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo Terminating existing backend process PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if not errorlevel 1 (
        echo Backend process terminated successfully.
        set "KILLED=1"
    )
)

if "%KILLED%"=="0" (
    echo No existing backend process found on port 8000.
)

echo.
echo Waiting 2 seconds for port to be released...
timeout /t 2 /nobreak >nul

echo.
echo Starting backend server (Python 3.11)...
start "Backend Server (Python 3.11)" cmd /k "%SCRIPT_DIR%start_backend_py311.bat"

echo.
echo Waiting up to 30s for backend to start listening...
set "UP=0"
for /l %%I in (1,1,30) do (
  netstat -ano | findstr /C:":8000" | findstr /C:"LISTENING" >nul
  if not errorlevel 1 (
    set "UP=1"
    goto :backend_ok
  )
  timeout /t 1 /nobreak >nul
)

:backend_ok
echo.
if "%UP%"=="1" (
  echo ========================================
  echo Backend server restarted successfully!
  echo ========================================
  echo Backend: http://localhost:8000
  echo API Docs: http://localhost:8000/docs
  echo.
  echo VERIFICATION STEPS:
  echo 1. Check the Backend Server window for any errors
  echo 2. Verify Uvicorn shows "Watching for file changes..."
  echo 3. Test API health: curl http://localhost:8000/api/v1/health
  echo 4. If issues persist, check backend\app\services\ for syntax errors
) else (
  echo ========================================
  echo WARNING: Backend not listening after 30s
  echo ========================================
  echo TROUBLESHOOTING:
  echo 1. Check Backend Server window for error messages
  echo 2. Verify Python 3.11 is installed at: C:\Users\ajksk\AppData\Local\Programs\Python\Python311
  echo 3. Check for syntax errors in recently modified files
  echo 4. Run manually: cd backend ^&^& ./venv311/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
)

echo.
pause
exit /b 0
