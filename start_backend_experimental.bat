@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
echo ========================================
echo AI Surgical Motion Knowledge Transfer Library - Experimental Backend
echo ========================================

set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%backend_experimental"
set "VENV_DIR=%BACKEND_DIR%\venv311"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

echo Backend Directory: %BACKEND_DIR%
echo Python 3.11 Path: %PYTHON_EXE%
echo.

rem Check if Python 3.11 virtual environment exists
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python 3.11 virtual environment not found at: %VENV_DIR%
    echo.
    echo Creating Python 3.11 virtual environment...

    rem Check if Python 3.11 is installed
    set "PYTHON311=C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe"
    if not exist "%PYTHON311%" (
        echo [ERROR] Python 3.11 not found at: %PYTHON311%
        echo Please install Python 3.11 first.
        pause
        exit /b 1
    )

    echo Creating virtual environment with Python 3.11...
    "%PYTHON311%" -m venv "%VENV_DIR%"

    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )

    echo Installing dependencies...
    "%PYTHON_EXE%" -m pip install --upgrade pip
    "%PYTHON_EXE%" -m pip install -r "%BACKEND_DIR%\requirements.txt"

    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )

    echo Virtual environment created successfully.
    echo.
)

rem Verify Python version
echo Verifying Python version...
"%PYTHON_EXE%" --version
if errorlevel 1 (
    echo [ERROR] Failed to run Python
    pause
    exit /b 1
)
echo.

rem Kill existing process on port 8001 if any
echo Checking for existing process on port 8001...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    echo Terminating existing process on port 8001 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)
echo.

rem Change to backend directory
cd /d "%BACKEND_DIR%"

echo Starting Experimental Backend Server on port 8001...
echo API: http://localhost:8001
echo API Docs: http://localhost:8001/docs
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

rem Start uvicorn server
"%PYTHON_EXE%" -m uvicorn app.main:app --reload --port 8001 --host 0.0.0.0

if errorlevel 1 (
    echo.
    echo [ERROR] Server failed to start
    echo.
    echo Common issues:
    echo - Port 8001 is already in use
    echo - Missing dependencies (run: pip install -r requirements.txt)
    echo - Python version mismatch (requires Python 3.11)
    echo.
    pause
    exit /b 1
)

pause
