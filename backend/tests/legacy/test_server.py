"""
簡易テストサーバー - MediaPipe依存を回避してAPIテストを実行
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# MediaPipeをモック
sys.modules['mediapipe'] = type(sys)('mediapipe')

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
import json

# 簡易FastAPIアプリ
app = FastAPI(title="Test API Server")

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "AI手技モーション伝承ライブラリ API (Test Mode)",
        "version": "0.1.0",
        "status": "running"
    }

@app.get("/api/v1/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/v1/videos/upload")
async def upload_video(file: UploadFile = File(...)):
    """動画アップロードのモック"""
    if not file.filename.endswith(('.mp4', '.mov', '.avi')):
        raise HTTPException(status_code=400, detail="Invalid file format")

    return {
        "id": "test-video-001",
        "filename": file.filename,
        "status": "uploaded",
        "message": "Upload successful (test mode)"
    }

@app.get("/api/v1/videos")
async def list_videos():
    """動画リストのモック"""
    return [
        {
            "id": "test-video-001",
            "filename": "test_surgery.mp4",
            "upload_date": "2025-01-13T10:00:00",
            "duration": 600,
            "status": "analyzed"
        }
    ]

@app.post("/api/v1/analysis/start")
async def start_analysis(video_id: str):
    """解析開始のモック"""
    return {
        "id": "analysis-001",
        "video_id": video_id,
        "status": "processing",
        "message": "Analysis started (test mode)"
    }

@app.get("/docs")
async def docs_redirect():
    """Swagger UIへのリダイレクト"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    print("Starting test server on http://localhost:8000")
    print("Swagger UI available at http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)