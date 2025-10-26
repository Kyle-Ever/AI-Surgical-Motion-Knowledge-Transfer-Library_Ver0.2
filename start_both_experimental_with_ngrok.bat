@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
echo ========================================
echo AI Surgical Motion Knowledge Transfer Library - Start with ngrok
echo ========================================

set "SCRIPT_DIR=%~dp0"

rem Check if ngrok is installed
where ngrok >nul 2>&1
if errorlevel 1 (
    echo ERROR: ngrok is not installed or not in PATH
    echo.
    echo Please install ngrok:
    echo 1. Download from https://ngrok.com/download
    echo 2. Extract to a folder
    echo 3. Add to PATH or place ngrok.exe in this directory
    echo.
    pause
    exit /b 1
)

rem Check if ngrok authtoken is configured
echo Checking ngrok configuration...
echo ngrok is installed and ready to use.
echo.
rem Note: Microsoft Store version of ngrok may show config warnings, but works correctly
rem The authtoken is configured in: %LOCALAPPDATA%\Packages\ngrok.ngrok_1g87z0zv29zzc\LocalCache\Local\ngrok\ngrok.yml

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

rem Kill any existing ngrok processes
tasklist | findstr /I "ngrok.exe" >nul 2>&1
if not errorlevel 1 (
    echo Terminating existing ngrok processes...
    taskkill /F /IM ngrok.exe >nul 2>&1
    if not errorlevel 1 (
        echo ngrok processes terminated successfully.
    )
)

echo.
echo Launching EXPERIMENTAL backend, frontend, and ngrok in separate windows...
echo.

echo Starting EXPERIMENTAL backend server window (Port 8001)...
start "Experimental Backend Server (Port 8001)" cmd /k "%SCRIPT_DIR%start_backend_experimental.bat"

echo Waiting 5 seconds for backend to initialize...
timeout /t 5 /nobreak >nul

echo Starting frontend server window (configured for experimental backend)...
start "Frontend Server (Experimental Mode)" cmd /k "cd /d %SCRIPT_DIR%frontend && npm run dev"

echo Waiting 10 seconds for frontend to initialize...
timeout /t 10 /nobreak >nul

echo Starting ngrok tunnel for frontend (Port 3000)...
echo.
echo IMPORTANT: To use a static domain (free with ngrok account):
echo   1. Sign up at https://ngrok.com/signup
echo   2. Run: ngrok config add-authtoken YOUR_TOKEN
echo   3. Get your static domain from https://dashboard.ngrok.com/cloud-edge/domains
echo   4. Replace YOUR_STATIC_DOMAIN below with your actual domain
echo.

rem ========================================
rem CONFIGURE YOUR STATIC DOMAIN HERE
rem ========================================
rem Static domain configured: attestable-emily-reservedly.ngrok-free.dev
start "ngrok Tunnel (Port 3000)" cmd /k "ngrok http --domain=attestable-emily-reservedly.ngrok-free.dev 3000"

rem Random URL (disabled - using static domain instead)
rem start "ngrok Tunnel (Port 3000)" cmd /k "ngrok http 3000"

echo.
echo Waiting up to 60s for services to listen on ports...
call :wait_port 8001 "Experimental Backend"
call :wait_port 3000 Frontend

echo.
echo ========================================
echo Launch commands issued. Current status above.
echo ========================================
echo Experimental Backend:  http://localhost:8001  (Docs: http://localhost:8001/docs)
echo Frontend (Local):      http://localhost:3000
echo Frontend (Public):     Check the ngrok window for the public URL
echo                        (Usually displayed as "Forwarding" line)
echo.
echo ngrok Web Interface:   http://localhost:4040
echo   - View real-time requests
echo   - Inspect traffic
echo   - Replay requests
echo.
echo Frontend is configured to use EXPERIMENTAL backend (port 8001).
echo Check frontend/.env.local to verify: NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1
echo.
echo Features in Experimental Mode:
echo   - SAM2 Video API with Memory Bank
echo   - Temporal context tracking for instruments
echo   - Single initial specification for instruments
echo.
echo PUBLIC ACCESS:
echo   - Your application is now accessible from anywhere via the ngrok URL
echo   - Share the ngrok URL (shown in ngrok window) with others
echo   - Free accounts have a 2-hour session limit (register for unlimited)
echo   - Static domains available with free account registration
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
