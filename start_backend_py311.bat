@echo off
echo ========================================
echo Starting Backend Server (Python 3.11)
echo ========================================

cd backend

REM Check if Python 3.11 is available
if exist "C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe" (
    echo Using Python 3.11 from: C:\Users\ajksk\AppData\Local\Programs\Python\Python311
    set PYTHON_PATH=C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe
) else (
    echo Error: Python 3.11 not found at expected location
    echo Please install Python 3.11 or update the path in this script
    pause
    exit /b 1
)

REM Check if venv311 exists and has correct Python version
if exist venv311 (
    echo Checking existing venv311...
    venv311\Scripts\python.exe --version 2>nul | findstr "3.11" >nul
    if errorlevel 1 (
        echo Existing venv311 is not using Python 3.11. Recreating...
        rmdir /s /q venv311
        "%PYTHON_PATH%" -m venv venv311
    ) else (
        echo Using existing venv311 with Python 3.11
    )
) else (
    echo Creating new virtual environment with Python 3.11...
    "%PYTHON_PATH%" -m venv venv311
)

REM Activate virtual environment
call venv311\Scripts\activate

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install requirements if needed
if not exist venv311\Lib\site-packages\fastapi (
    echo Installing requirements...
    pip install -r requirements.txt
)

echo.
echo ========================================
echo Starting FastAPI server...
echo ========================================
echo Server will run at: http://localhost:8000
echo API docs available at: http://localhost:8000/docs
echo Press Ctrl+C to stop
echo ========================================
echo.

REM Start the server
python -m uvicorn app.main:app --reload --port 8000

pause