@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

REM ====================================================================
REM MindMotionAI - Kill All
REM ====================================================================

echo.
echo ====================================================================
echo   MindMotionAI - Kill All
echo ====================================================================
echo.

echo [1/4] Port 3000 (Frontend)...
set "FOUND=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
    set "FOUND=1"
)
if "!FOUND!"=="1" (echo    Killed) else (echo    Not running)

echo [2/4] Port 8001 (Backend)...
set "FOUND=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
    set "FOUND=1"
)
if "!FOUND!"=="1" (echo    Killed) else (echo    Not running)

echo [3/4] Node.js...
tasklist | findstr /I "node.exe" >nul 2>&1
if not errorlevel 1 (taskkill /F /IM node.exe >nul 2>&1 & echo    Killed) else (echo    Not running)

echo [4/4] Python...
tasklist | findstr /I "python.exe" >nul 2>&1
if not errorlevel 1 (taskkill /F /IM python.exe >nul 2>&1 & echo    Killed) else (echo    Not running)

REM --- ngrok ---
tasklist | findstr /I "ngrok.exe" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo Killing ngrok...
    taskkill /F /IM ngrok.exe >nul 2>&1
    echo    Killed
)

REM --- Lock file ---
if exist "backend_experimental\.server.lock" del /f "backend_experimental\.server.lock" 2>nul

REM --- Verify ---
timeout /t 2 /nobreak >nul
echo.
echo === Status ===

set "CLEAN=1"
netstat -ano | findstr :3000 | findstr LISTENING >nul 2>&1
if not errorlevel 1 (echo    Port 3000: Still in use & set "CLEAN=0") else (echo    Port 3000: OK)

netstat -ano | findstr :8001 | findstr LISTENING >nul 2>&1
if not errorlevel 1 (echo    Port 8001: Still in use & set "CLEAN=0") else (echo    Port 8001: OK)

echo.
if "!CLEAN!"=="1" (echo All processes stopped.) else (echo Some processes remain. Try running as admin.)
echo.

if "%1"=="nopause" exit /b 0
pause
exit /b 0
