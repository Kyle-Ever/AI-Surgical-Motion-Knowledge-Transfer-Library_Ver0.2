from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import os
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.error_handler import setup_exception_handlers
from app.api.routes import videos, analysis, annotation, library, scoring, instrument_tracking, segmentation
from app.models import Base, engine

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# サーバーロックファイルのパス
LOCK_FILE = Path(__file__).parent.parent / ".server.lock"

def acquire_server_lock():
    """サーバーロックを取得（既に起動中なら終了）"""
    try:
        if LOCK_FILE.exists():
            # 既存のロックファイルをチェック
            with open(LOCK_FILE, 'r') as f:
                old_pid = f.read().strip()

            # プロセスが生きているか確認（Windows互換）
            try:
                old_pid_int = int(old_pid)
                # Windowsではtasklist確認
                import subprocess
                result = subprocess.run(
                    ['tasklist', '/FI', f'PID eq {old_pid_int}'],
                    capture_output=True,
                    text=True
                )
                if str(old_pid_int) in result.stdout:
                    port = os.getenv("PORT", "8001")
                    logger.error(f"❌ Backend already running (PID: {old_pid})")
                    logger.error(f"   Port {port} is in use by another instance")
                    logger.error(f"   Please stop the existing server first")
                    sys.exit(1)
                else:
                    # プロセスが死んでいる → 古いロック削除
                    logger.warning(f"Removing stale lock file (dead process PID: {old_pid})")
                    LOCK_FILE.unlink()
            except (ValueError, subprocess.SubprocessError) as e:
                logger.warning(f"Lock file check failed: {e}, removing lock")
                LOCK_FILE.unlink()

        # 新しいロック作成
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))

        logger.info(f"✅ Server lock acquired (PID: {os.getpid()})")

    except Exception as e:
        logger.error(f"⚠️ Lock acquisition failed: {e}")

def release_server_lock():
    """サーバーロック解放"""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
            logger.info("🔓 Server lock released")
    except Exception as e:
        logger.warning(f"Failed to release lock: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時
    acquire_server_lock()  # ロック取得
    logger.info("Starting up...")
    # データベーステーブルを作成
    Base.metadata.create_all(bind=engine)
    yield
    # シャットダウン時
    logger.info("Shutting down...")
    release_server_lock()  # ロック解放

# FastAPIアプリケーション作成
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# エラーハンドラー設定
setup_exception_handlers(app)

# UTF-8エンコーディング強制ミドルウェア
class UTF8EnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # JSONレスポンスに明示的にcharset=utf-8を設定
        if response.headers.get("content-type", "").startswith("application/json"):
            response.headers["content-type"] = "application/json; charset=utf-8"
        return response

app.add_middleware(UTF8EnforcementMiddleware)

# CORS設定
# ngrokデュアルドメイン構成対応
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mindmotionai.ngrok-free.dev",  # フロントエンド
        "https://dev.mindmotionai.ngrok-free.dev",  # バックエンド（自己参照）
        "http://localhost:3000",  # ローカル開発用
        "http://localhost:8001",  # ローカルバックエンド
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
# 注意: libraryルーターを最初に登録（特定のパスを優先）
app.include_router(
    library.router,
    prefix=f"{settings.API_V1_STR}/library",
    tags=["library"]
)
app.include_router(
    videos.router,
    prefix=f"{settings.API_V1_STR}/videos",
    tags=["videos"]
)
app.include_router(
    analysis.router,
    prefix=f"{settings.API_V1_STR}/analysis",
    tags=["analysis"]
)
app.include_router(
    annotation.router,
    prefix=f"{settings.API_V1_STR}/annotations",
    tags=["annotations"]
)
app.include_router(
    scoring.router,
    prefix=f"{settings.API_V1_STR}/scoring",
    tags=["scoring"]
)
app.include_router(
    instrument_tracking.router,
    prefix=f"{settings.API_V1_STR}/instrument-tracking",
    tags=["instrument-tracking"]
)
app.include_router(
    segmentation.router,
    prefix=f"{settings.API_V1_STR}/videos",
    tags=["segmentation"]
)

# V2 APIルーター（新しいクリーンアーキテクチャ実装）
# from app.api.routes import analysis_v2
# app.include_router(
#     analysis_v2.router,
#     tags=["analysis_v2"]
# )

# ルートエンドポイント
@app.get("/", summary="Service info")
async def root():
    """Basic service information."""
    return {
        "message": "AI Surgical Motion Knowledge Transfer Library API",
        "version": settings.VERSION
    }

# ヘルスチェックエンドポイント
@app.get(f"{settings.API_V1_STR}/health", summary="Health check")
async def health_check():
    """Health status for monitoring."""
    return {"status": "healthy", "version": settings.VERSION}


from app.core.websocket import manager

@app.websocket("/ws/analysis/{analysis_id}")
async def websocket_endpoint(websocket: WebSocket, analysis_id: str):
    await manager.connect(websocket, analysis_id)
    try:
        while True:
            # クライアントからのメッセージを待つ（キープアライブ）
            data = await websocket.receive_text()

            # モックの進捗データを送信（テスト用）
            await websocket.send_json({
                "type": "progress",
                "step": "processing",
                "progress": 50,
                "message": "処理中..."
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket, analysis_id)

if __name__ == "__main__":
    import uvicorn
    # 環境変数PORTを使用（デフォルトは8001）
    port = int(os.getenv("PORT", "8001"))
    logger.info(f"🚀 Starting server on port {port}")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.RELOAD
    )