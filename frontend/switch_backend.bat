@echo off
echo ============================================
echo Backend Environment Switcher
echo ============================================
echo.
echo Select backend environment:
echo 1. Stable (Port 8000)
echo 2. Experimental (Port 8001)
echo.

set /p choice="Enter your choice (1 or 2): "

if "%choice%"=="1" (
    echo.
    echo Switching to STABLE backend...
    copy /Y .env.local.stable .env.local
    echo.
    echo ============================================
    echo Switched to STABLE backend
    echo API URL: http://localhost:8000/api/v1
    echo ============================================
    echo.
    echo Please restart the frontend server:
    echo   npm run dev
    echo.
) else if "%choice%"=="2" (
    echo.
    echo Switching to EXPERIMENTAL backend...
    copy /Y .env.local.experimental .env.local
    echo.
    echo ============================================
    echo Switched to EXPERIMENTAL backend
    echo API URL: http://localhost:8001/api/v1
    echo ============================================
    echo.
    echo Please restart the frontend server:
    echo   npm run dev
    echo.
) else (
    echo.
    echo Invalid choice. Please run the script again.
    echo.
)

pause
