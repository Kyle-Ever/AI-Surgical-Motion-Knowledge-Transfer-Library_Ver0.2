@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
echo ========================================
echo AI Surgical Motion Knowledge Transfer Library - Start Experimental Version
echo ========================================

set "SCRIPT_DIR=%~dp0"

echo Checking for existing processes on ports 3000 and 8001...
echo.

rem Kill any process using port 3000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo Terminating existing process on port 3000 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if not errorlevel 1 (
        echo Process on port 3000 terminated successfully.
    )
)

rem Kill any process using port 8001 (Experimental Backend)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    echo Terminating existing process on port 8001 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if not errorlevel 1 (
        echo Process on port 8001 terminated successfully.
    )
)

echo.
echo Launching EXPERIMENTAL backend and frontend in separate windows...
echo.

echo Starting EXPERIMENTAL backend server window (Port 8001)...
start "Experimental Backend Server (Port 8001)" cmd /k "%SCRIPT_DIR%start_backend_experimental.bat"

echo Waiting 3 seconds for backend window to initialize...
timeout /t 3 /nobreak >nul

echo Starting frontend server window (configured for experimental backend)...
start "Frontend Server (Experimental Mode)" cmd /k "cd /d %SCRIPT_DIR%frontend && npm run dev"

echo.
echo Waiting up to 60s for services to listen on ports...
call :wait_port 8001 "Experimental Backend"
call :wait_port 3000 Frontend

echo.
echo ========================================
echo Launch commands issued. Current status above.
echo ========================================
echo Experimental Backend:  http://localhost:8001  (Docs: http://localhost:8001/docs)
echo Frontend:              http://localhost:3000
echo.
echo Frontend is configured to use EXPERIMENTAL backend (port 8001).
echo Check frontend/.env.local to verify: NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1
echo.
echo Features in Experimental Mode:
echo   - SAM2 Video API with Memory Bank
echo   - Temporal context tracking for instruments
echo   - Single initial specification for instruments
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
