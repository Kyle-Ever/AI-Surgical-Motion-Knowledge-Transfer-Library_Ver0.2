@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

REM ====================================================================
REM MindMotionAI - run.bat / run.bat ngrok
REM ====================================================================

set "SCRIPT_DIR=%~dp0"
set "MODE=local"
if /i "%1"=="ngrok" set "MODE=ngrok"

echo.
echo ====================================================================
if "%MODE%"=="ngrok" goto :header_ngrok
echo   MindMotionAI - Local Dev
goto :header_done
:header_ngrok
echo   MindMotionAI - ngrok Public
:header_done
echo ====================================================================
echo.

REM --- Cleanup ---
echo [1/4] Cleanup...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1
if "%MODE%"=="ngrok" taskkill /F /IM ngrok.exe >nul 2>&1
echo    Done
echo.

REM --- Backend ---
set "BACKEND_DIR=%SCRIPT_DIR%backend_experimental"
set "VENV_DIR=%BACKEND_DIR%\venv311"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PYTHON311=C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe"

if exist "%PYTHON_EXE%" goto :venv_ready
echo Creating venv311...
if not exist "%PYTHON311%" (
    echo ERROR: Python 3.11 not found: %PYTHON311%
    pause
    exit /b 1
)
"%PYTHON311%" -m venv "%VENV_DIR%"
"%PYTHON_EXE%" -m pip install --upgrade pip
"%PYTHON_EXE%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
:venv_ready

echo [2/4] Starting Backend (Port 8001)...
start "Backend-8001" cmd /k "cd /d "%BACKEND_DIR%" && "%PYTHON_EXE%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"
timeout /t 3 /nobreak >nul

REM --- Frontend ---
echo [3/4] Starting Frontend (Port 3000)...
start "Frontend-3000" cmd /k "cd /d "%SCRIPT_DIR%frontend" && npm run dev"

REM --- Wait for ports ---
echo [4/4] Waiting for services...
call :wait_port 8001 Backend
call :wait_port 3000 Frontend

REM --- ngrok ---
if not "%MODE%"=="ngrok" goto :skip_ngrok
where ngrok >nul 2>&1
if errorlevel 1 (
    echo ERROR: ngrok not found
    pause
    exit /b 1
)
echo.
echo Starting ngrok tunnels...
start "ngrok-Backend" cmd /k "ngrok http --domain=dev.mindmotionai.ngrok-free.dev 8001"
timeout /t 3 /nobreak >nul
start "ngrok-Frontend" cmd /k "ngrok http --domain=mindmotionai.ngrok-free.dev 3000"
:skip_ngrok

REM --- Done ---
echo.
echo ====================================================================
echo   Ready
echo ====================================================================
echo.
echo   Backend:   http://localhost:8001
echo   Frontend:  http://localhost:3000
echo   API Docs:  http://localhost:8001/docs
if not "%MODE%"=="ngrok" goto :skip_ngrok_info
echo.
echo   Public Frontend: https://mindmotionai.ngrok-free.dev
echo   Public Backend:  https://dev.mindmotionai.ngrok-free.dev
:skip_ngrok_info
echo.
echo   Stop: kill.bat
echo.
echo ====================================================================
echo.

pause
exit /b 0

:wait_port
set "PORT=%~1"
set "NAME=%~2"
for /l %%I in (1,1,30) do (
    netstat -ano | findstr /C:":%PORT%" | findstr /C:"LISTENING" >nul
    if not errorlevel 1 (
        echo    %NAME% ready on port %PORT%
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)
echo    WARNING: %NAME% not ready after 30s on port %PORT%
exit /b 0
