@echo off
setlocal enabledelayedexpansion

echo =====================================
echo AI手術モーション解析システム
echo サーバー安全停止スクリプト
echo =====================================
echo.

set BACKEND_STOPPED=false
set FRONTEND_STOPPED=false

echo [1/2] バックエンドサーバー (FastAPI - ポート8000) を確認中...
netstat -aon | findstr :8000 | findstr LISTENING >nul
if %errorlevel% == 0 (
    echo     検出: FastAPIサーバーが稼働中です
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
        echo     停止中... (PID: %%a)
        taskkill /PID %%a /T >nul 2>&1
        timeout /t 1 /nobreak >nul
        taskkill /PID %%a /F >nul 2>&1
        set BACKEND_STOPPED=true
    )
    if !BACKEND_STOPPED! == true (
        echo     ✓ FastAPIサーバーを停止しました
    )
) else (
    echo     - FastAPIサーバーは起動していません
)

echo.
echo [2/2] フロントエンドサーバー (Next.js - ポート3000) を確認中...
netstat -aon | findstr :3000 | findstr LISTENING >nul
if %errorlevel% == 0 (
    echo     検出: Next.jsサーバーが稼働中です
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do (
        echo     停止中... (PID: %%a)
        taskkill /PID %%a /T >nul 2>&1
        timeout /t 1 /nobreak >nul
        taskkill /PID %%a /F >nul 2>&1
        set FRONTEND_STOPPED=true
    )
    if !FRONTEND_STOPPED! == true (
        echo     ✓ Next.jsサーバーを停止しました
    )
) else (
    echo     - Next.jsサーバーは起動していません
)

echo.
echo =====================================
if !BACKEND_STOPPED! == true if !FRONTEND_STOPPED! == true (
    echo ✅ すべてのサーバーを正常に停止しました
) else if !BACKEND_STOPPED! == false if !FRONTEND_STOPPED! == false (
    echo ℹ️  停止するサーバーがありませんでした
) else (
    echo ✅ 稼働中のサーバーを停止しました
)
echo =====================================
echo.

pause