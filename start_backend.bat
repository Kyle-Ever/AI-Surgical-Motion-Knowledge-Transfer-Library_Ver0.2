@echo off
chcp 65001 >nul
echo ========================================
echo AI Surgical Motion Knowledge Transfer Library - Backend
echo ========================================

cd /d "%~dp0backend"

echo Checking for Python 3.11...
set "PY311_VER="
for /f "delims=" %%v in ('py -3.11 -c "import sys; print(sys.version)" 2^>nul') do set "PY311_VER=%%v"
if defined PY311_VER (
    echo Detected Python 3.11: %PY311_VER%
) else (
    echo Python 3.11 not found via py launcher. Will use default python if needed.
)

echo Checking virtual environment...
rem If venv exists, ensure it uses Python 3.11 (for mediapipe/opencv compatibility)
if exist "venv\Scripts\python.exe" (
    for /f "delims=" %%v in ('venv\Scripts\python.exe -c "import sys; print(str(sys.version_info[0])+'.'+str(sys.version_info[1]))"') do set "VENV_PY=%%v"
    if /i not "%VENV_PY%"=="3.11" (
        echo Existing venv uses Python %VENV_PY%. Recreating with Python 3.11...
        rmdir /s /q venv
    )
)

if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Creating venv...
    if defined PY311_VER (
        py -3.11 -m venv venv
    ) else (
        python -m venv venv
    )
    if errorlevel 1 (
        echo Error: Failed to create Python virtual environment
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)

echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

echo Starting backend server...
echo Server URL: http://localhost:8000
echo API Documentation: http://localhost:8000/docs
echo Press Ctrl+C to stop
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
