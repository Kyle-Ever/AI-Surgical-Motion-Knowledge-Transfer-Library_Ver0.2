@echo off
chcp 65001 >nul
REM ====================================================================
REM AI Surgical Motion Knowledge Transfer Library
REM デュアルngrok起動スクリプト（$20プラン対応）
REM
REM フロントエンド: https://mindmotionai.ngrok-free.dev
REM バックエンド: https://dev.mindmotionai.ngrok-free.dev
REM ====================================================================

echo.
echo ====================================================================
echo   AI Surgical Motion Knowledge Transfer Library
echo   デュアルngrok起動スクリプト（$20プラン対応）
echo ====================================================================
echo.
echo [構成]
echo   フロントエンド: https://mindmotionai.ngrok-free.dev
echo   バックエンド: https://dev.mindmotionai.ngrok-free.dev
echo.
echo [起動順序]
echo   1. バックエンド (Port 8001)
echo   2. フロントエンド (Port 3000)
echo   3. ngrok for Backend (Port 8001)
echo   4. ngrok for Frontend (Port 3000)
echo.
echo ====================================================================
echo.

REM 既存のサーバープロセスをクリーンアップ
echo [1/4] 既存プロセスのクリーンアップ...
call kill_all_servers.bat nopause
timeout /t 2 /nobreak >nul

REM Python 3.11の確認
set PYTHON_PATH=C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_PATH%" (
    echo [エラー] Python 3.11が見つかりません: %PYTHON_PATH%
    echo MediaPipe/OpenCVはPython 3.11が必須です。
    pause
    exit /b 1
)

REM バックエンドの起動（Python 3.11使用）
echo.
echo [2/4] バックエンド起動中 (Port 8001)...
cd backend_experimental

REM venv311が存在しない場合は作成
if not exist venv311 (
    echo [警告] venv311が見つかりません。新規作成します...
    "%PYTHON_PATH%" -m venv venv311
    if errorlevel 1 (
        echo [エラー] 仮想環境の作成に失敗しました
        cd ..
        pause
        exit /b 1
    )
    echo [情報] venv311を作成しました
    call venv311\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv311\Scripts\activate.bat
)

REM サーバーロックファイルを削除（複数起動防止機構）
if exist .server.lock del .server.lock

REM バックエンドサーバーを起動
start "Backend Experimental (Port 8001)" cmd /k "cd /d %CD% && venv311\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"

cd ..
timeout /t 3 /nobreak >nul

REM フロントエンドの起動
echo.
echo [3/4] フロントエンド起動中 (Port 3000)...
cd frontend

REM .nextキャッシュをクリア（環境変数変更を反映）
if exist .next (
    echo [情報] .nextキャッシュをクリアしています...
    rmdir /s /q .next
)

REM node_modulesが存在しない場合はインストール
if not exist node_modules (
    echo [警告] node_modulesが見つかりません。依存関係をインストールします...
    call npm install
    if errorlevel 1 (
        echo [エラー] npm installに失敗しました
        cd ..
        pause
        exit /b 1
    )
)

start "Frontend (Port 3000)" cmd /k "cd /d %CD% && npm run dev"

cd ..
timeout /t 5 /nobreak >nul

REM ngrokの起動確認
where ngrok >nul 2>&1
if errorlevel 1 (
    echo [エラー] ngrokコマンドが見つかりません。
    echo ngrokをインストールしてPATHに追加してください。
    echo https://ngrok.com/download
    pause
    exit /b 1
)

REM ngrok for Backend
echo.
echo [4/4a] ngrok起動中（バックエンド用）...
echo   URL: https://dev.mindmotionai.ngrok-free.dev
start "ngrok - Backend" cmd /k "ngrok http --domain=dev.mindmotionai.ngrok-free.dev 8001"
timeout /t 3 /nobreak >nul

REM ngrok for Frontend
echo.
echo [4/4b] ngrok起動中（フロントエンド用）...
echo   URL: https://mindmotionai.ngrok-free.dev
start "ngrok - Frontend" cmd /k "ngrok http --domain=mindmotionai.ngrok-free.dev 3000"

echo.
echo ====================================================================
echo   起動完了！
echo ====================================================================
echo.
echo [アクセスURL]
echo   ✅ フロントエンド: https://mindmotionai.ngrok-free.dev
echo   ✅ バックエンド: https://dev.mindmotionai.ngrok-free.dev
echo   📊 ローカル（フロントエンド）: http://localhost:3000
echo   📊 ローカル（バックエンド）: http://localhost:8001
echo   📖 バックエンドAPI仕様: http://localhost:8001/docs
echo.
echo [注意事項]
echo   ⚠ 初回アクセス時、ngrokの警告画面が表示される場合があります
echo   ⚠ "Visit Site"をクリックして進んでください
echo   ⚠ フロントエンドは直接バックエンドngrok URLへ接続します
echo.
echo [停止方法]
echo   📛 kill_all_servers.bat を実行してください
echo.
echo ====================================================================
echo.

pause
