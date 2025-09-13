from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.api.routes import videos, analysis
from app.models import Base, engine

# 繝ｭ繧ｮ繝ｳ繧ｰ險ｭ螳・
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 襍ｷ蜍墓凾
    logger.info("Starting up...")
    # 繝・・繧ｿ繝吶・繧ｹ繝・・繝悶Ν繧剃ｽ懈・
    Base.metadata.create_all(bind=engine)
    yield
    # 繧ｷ繝｣繝・ヨ繝繧ｦ繝ｳ譎・
    logger.info("Shutting down...")

# FastAPI繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ菴懈・
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS險ｭ螳・
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 繝ｫ繝ｼ繧ｿ繝ｼ逋ｻ骭ｲ
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

# 繝ｫ繝ｼ繝医お繝ｳ繝峨・繧､繝ｳ繝・
@app.get("/", summary="Service info")
async def root():
    """Basic service information."""
    return {
        "message": "AI謇区橿繝｢繝ｼ繧ｷ繝ｧ繝ｳ莨晄価繝ｩ繧､繝悶Λ繝ｪ API",
        "version": settings.VERSION
    }

# 繝倥Ν繧ｹ繝√ぉ繝・け繧ｨ繝ｳ繝峨・繧､繝ｳ繝・
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
            # 繧ｯ繝ｩ繧､繧｢繝ｳ繝医°繧峨・繝｡繝・そ繝ｼ繧ｸ繧貞ｾ・▽・医く繝ｼ繝励い繝ｩ繧､繝厄ｼ・
            data = await websocket.receive_text()
            
            # 繝｢繝・け縺ｮ騾ｲ謐励ョ繝ｼ繧ｿ繧帝∽ｿ｡・医ユ繧ｹ繝育畑・・
            await websocket.send_json({
                "type": "progress",
                "step": "processing",
                "progress": 50,
                "message": "蜃ｦ逅・ｸｭ..."
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
