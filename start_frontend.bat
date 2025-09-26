@echo off
chcp 65001 >nul
echo ========================================
echo AI Surgical Motion Knowledge Transfer Library - Frontend
echo ========================================

cd /d "%~dp0frontend"

echo Checking Node.js version...
node --version
if errorlevel 1 (
    echo Error: Node.js is not installed
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

echo Checking npm version...
call npm --version
if errorlevel 1 (
    echo Error: npm is not installed
    pause
    exit /b 1
)

echo.
echo Installing dependencies...
call npm install
if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo Starting frontend development server...
echo Application URL: http://localhost:3000
echo Press Ctrl+C to stop
echo ========================================
echo.

call npm run dev

pause
