@echo off
REM ========================================
REM 全サーバープロセス強制終了スクリプト
REM ========================================
echo.
echo ========================================
echo 全サーバープロセス強制終了
echo ========================================
echo.

REM 全てのPythonプロセスを終了
echo [1/3] Killing all Python processes...
taskkill /F /IM python.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo    ✓ Python processes killed
) else (
    echo    - No Python processes found
)

REM Node.js/Next.jsプロセスを終了（ポート3000使用）
echo.
echo [2/3] Killing Node.js/Next.js processes (port 3000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo    Killing PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)
echo    ✓ Port 3000 cleared

REM 全てのNode.jsプロセスを終了（念のため）
echo.
echo [3/3] Killing all Node.js processes...
taskkill /F /IM node.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo    ✓ Node.js processes killed
) else (
    echo    - No Node.js processes found
)

echo.
echo ========================================
echo All servers stopped successfully
echo ========================================
echo.

REM 他のスクリプトから呼ばれた場合はpauseしない
if "%1"=="nopause" (
    echo Continuing with parent script...
    exit /b 0
)

echo 次のステップ:
echo   - バックエンド起動: start_backend_py311.bat
echo   - フロントエンド起動: cd frontend ^&^& npm run dev
echo   - 両方起動: start_both.bat
echo.
pause
