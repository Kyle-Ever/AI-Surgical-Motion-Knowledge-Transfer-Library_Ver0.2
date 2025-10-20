@echo off
REM ========================================
REM 全プロセス強制終了スクリプト（完全版）
REM Python, Node.js, Uvicornの全プロセスを終了
REM ========================================
chcp 65001 >nul
echo.
echo ========================================
echo 全プロセス強制終了（完全版）
echo ========================================
echo.
echo 警告: このスクリプトは以下の全てを終了します:
echo   - 全てのPythonプロセス
echo   - 全てのNode.jsプロセス
echo   - Port 3000, 8000, 8001を使用する全プロセス
echo.
echo 他のPython/Node.jsアプリが実行中の場合は影響を受けます。
echo.
set /p confirm="続行しますか？ (Y/N): "
if /i not "%confirm%"=="Y" (
    echo 中止しました。
    pause
    exit /b 0
)

echo.
echo ========================================
echo [1/6] バックエンドロックファイルを削除中...
echo ========================================

if exist "backend\.server.lock" (
    del /f "backend\.server.lock" 2>nul
    echo    ✓ backend\.server.lock 削除
) else (
    echo    - backend\.server.lock なし
)

if exist "backend_experimental\.server.lock" (
    del /f "backend_experimental\.server.lock" 2>nul
    echo    ✓ backend_experimental\.server.lock 削除
) else (
    echo    - backend_experimental\.server.lock なし
)

echo.
echo ========================================
echo [2/6] Port 3000のプロセスを終了中...
echo ========================================

set "FOUND_3000=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING 2^>nul') do (
    echo    終了中 PID: %%a (Port 3000)
    taskkill /F /PID %%a >nul 2>&1
    set "FOUND_3000=1"
)
if "%FOUND_3000%"=="0" (
    echo    - Port 3000使用中のプロセスなし
) else (
    echo    ✓ Port 3000のプロセス終了完了
)

echo.
echo ========================================
echo [3/6] Port 8000のプロセスを終了中...
echo ========================================

set "FOUND_8000=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    echo    終了中 PID: %%a (Port 8000)
    taskkill /F /PID %%a >nul 2>&1
    set "FOUND_8000=1"
)
if "%FOUND_8000%"=="0" (
    echo    - Port 8000使用中のプロセスなし
) else (
    echo    ✓ Port 8000のプロセス終了完了
)

echo.
echo ========================================
echo [4/6] Port 8001のプロセスを終了中...
echo ========================================

set "FOUND_8001=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING 2^>nul') do (
    echo    終了中 PID: %%a (Port 8001)
    taskkill /F /PID %%a >nul 2>&1
    set "FOUND_8001=1"
)
if "%FOUND_8001%"=="0" (
    echo    - Port 8001使用中のプロセスなし
) else (
    echo    ✓ Port 8001のプロセス終了完了
)

echo.
echo ========================================
echo [5/6] 全てのNode.jsプロセスを終了中...
echo ========================================

tasklist | findstr /I "node.exe" >nul 2>&1
if errorlevel 1 (
    echo    - Node.jsプロセスなし
) else (
    echo    終了中: 全てのNode.jsプロセス
    taskkill /F /IM node.exe >nul 2>&1
    if errorlevel 1 (
        echo    ! Node.jsプロセスの終了に失敗（権限不足の可能性）
    ) else (
        echo    ✓ Node.jsプロセス終了完了
    )
)

echo.
echo ========================================
echo [6/6] 全てのPythonプロセスを終了中...
echo ========================================

tasklist | findstr /I "python.exe" >nul 2>&1
if errorlevel 1 (
    echo    - Pythonプロセスなし
) else (
    echo    終了中: 全てのPythonプロセス
    taskkill /F /IM python.exe >nul 2>&1
    if errorlevel 1 (
        echo    ! Pythonプロセスの終了に失敗（権限不足の可能性）
    ) else (
        echo    ✓ Pythonプロセス終了完了
    )
)

echo.
echo ========================================
echo 完了！ポート解放待機中...
echo ========================================
timeout /t 2 /nobreak >nul

echo.
echo === 最終確認 ===
echo.

REM 最終確認
set "CLEAN=1"

netstat -ano | findstr :3000 | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
    echo ⚠ Port 3000: まだ使用中です
    set "CLEAN=0"
) else (
    echo ✓ Port 3000: 解放されました
)

netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
    echo ⚠ Port 8000: まだ使用中です
    set "CLEAN=0"
) else (
    echo ✓ Port 8000: 解放されました
)

netstat -ano | findstr :8001 | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
    echo ⚠ Port 8001: まだ使用中です
    set "CLEAN=0"
) else (
    echo ✓ Port 8001: 解放されました
)

tasklist | findstr /I "node.exe" >nul 2>&1
if not errorlevel 1 (
    echo ⚠ Node.js: まだ実行中のプロセスがあります
    set "CLEAN=0"
) else (
    echo ✓ Node.js: 全て終了しました
)

tasklist | findstr /I "python.exe" >nul 2>&1
if not errorlevel 1 (
    echo ⚠ Python: まだ実行中のプロセスがあります
    set "CLEAN=0"
) else (
    echo ✓ Python: 全て終了しました
)

echo.
if "%CLEAN%"=="1" (
    echo ========================================
    echo ✅ 全てのプロセスが正常に終了しました
    echo ========================================
    echo.
    echo サーバーを再起動できます:
    echo   start_both_experimental.bat
) else (
    echo ========================================
    echo ⚠ 一部のプロセスが終了できませんでした
    echo ========================================
    echo.
    echo 対処方法:
    echo 1. 管理者権限でこのバッチファイルを実行
    echo 2. タスクマネージャーで手動終了
    echo 3. PCを再起動
)

echo.
pause
exit /b 0
