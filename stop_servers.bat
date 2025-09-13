@echo off
echo =====================================
echo AI手術モーション解析システム
echo サーバー停止スクリプト
echo =====================================
echo.

echo [1/3] FastAPIサーバー (ポート8000) を停止中...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
    if !errorlevel! == 0 (
        echo     ✓ FastAPIサーバーを停止しました (PID: %%a)
    )
)

echo [2/3] Next.jsサーバー (ポート3000) を停止中...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
    if !errorlevel! == 0 (
        echo     ✓ Next.jsサーバーを停止しました (PID: %%a)
    )
)

echo [3/3] Node.jsプロセスをクリーンアップ中...
taskkill /F /IM node.exe >nul 2>&1
if %errorlevel% == 0 (
    echo     ✓ Node.jsプロセスを終了しました
) else (
    echo     - Node.jsプロセスは実行されていません
)

echo.
echo =====================================
echo ✅ すべてのサーバーを停止しました
echo =====================================
echo.

pause