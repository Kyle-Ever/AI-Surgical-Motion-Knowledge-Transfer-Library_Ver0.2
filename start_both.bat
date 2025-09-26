@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
echo ========================================
echo AI Surgical Motion Knowledge Transfer Library - Start All
echo ========================================

set "SCRIPT_DIR=%~dp0"

echo Checking for existing processes on ports 3000 and 8000...
echo.

rem Kill any process using port 3000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo Terminating existing process on port 3000 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if not errorlevel 1 (
        echo Process on port 3000 terminated successfully.
    )
)

rem Kill any process using port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo Terminating existing process on port 8000 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if not errorlevel 1 (
        echo Process on port 8000 terminated successfully.
    )
)

echo.
echo Launching both backend and frontend in separate windows...
echo.

echo Starting backend server window (Python 3.11)...
start "Backend Server (Python 3.11)" cmd /k "%SCRIPT_DIR%start_backend_py311.bat"

echo Waiting 3 seconds for backend window to initialize...
timeout /t 3 /nobreak >nul

echo Starting frontend server window...
start "Frontend Server" cmd /k "%SCRIPT_DIR%start_frontend.bat"

echo.
echo Waiting up to 60s for services to listen on ports...
call :wait_port 8000 Backend
call :wait_port 3000 Frontend

echo.
echo ========================================
echo Launch commands issued. Current status above.
echo ========================================
echo Backend:  http://localhost:8000  (Docs: http://localhost:8000/docs)
echo Frontend: http://localhost:3000
echo.
echo If a service did not reach LISTENING state, fix the errors in its window.
echo IMPORTANT: Backend requires Python 3.11 (NOT 3.13). MediaPipe/OpenCV compatibility issue.
echo If backend fails, ensure Python 3.11 is installed at: C:\Users\ajksk\AppData\Local\Programs\Python\Python311
echo.

pause
exit /b 0

:wait_port
set "PORT=%~1"
set "NAME=%~2"
set "UP=0"
for /l %%I in (1,1,60) do (
  rem Check both IPv4/IPv6 LISTENING entries
  netstat -ano | findstr /C:":%PORT%" | findstr /C:"LISTENING" >nul
  if not errorlevel 1 (
    set "UP=1"
    goto :port_ok
  )
  timeout /t 1 /nobreak >nul
)
:port_ok
if "%UP%"=="1" (
  echo %NAME% is up (port %PORT% LISTENING).
) else (
  echo WARNING: %NAME% not LISTENING on port %PORT% after 60s.
)
exit /b 0