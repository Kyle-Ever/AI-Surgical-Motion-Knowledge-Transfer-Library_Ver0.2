from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.api.routes import videos, analysis, annotation
from app.models import Base, engine

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時
    logger.info("Starting up...")
    # データベーステーブルを作成
    Base.metadata.create_all(bind=engine)
    yield
    # シャットダウン時
    logger.info("Shutting down...")

# FastAPIアプリケーション作成
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
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

# ルートエンドポイント
@app.get("/", summary="Service info")
async def root():
    """Basic service information."""
    return {
        "message": "AI手技モーション伝承ライブラリ API",
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
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.RELOAD
    )