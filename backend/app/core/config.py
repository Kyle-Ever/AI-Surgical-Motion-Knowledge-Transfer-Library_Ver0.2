from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    # API設定
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AI手技モーション伝承ライブラリ"
    VERSION: str = "0.1.0"

    # CORS設定
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]

    # データベース
    DATABASE_URL: str = "sqlite:///./aimotion.db"

    # ファイルストレージ
    DATA_DIR: Path = Path("./data")
    UPLOAD_DIR: Path = Path("./data/uploads")
    TEMP_DIR: Path = Path("./data/temp")
    MAX_UPLOAD_SIZE: int = 1 * 1024 * 1024 * 1024  # 1GB
    ALLOWED_EXTENSIONS: set = {".mp4", ".mov", ".avi"}
    
    # AI処理設定
    FRAME_EXTRACTION_FPS: int = 5
    YOLO_MODEL: str = "yolov8n.pt"
    MEDIAPIPE_MIN_DETECTION_CONFIDENCE: float = 0.8
    MEDIAPIPE_MIN_TRACKING_CONFIDENCE: float = 0.8
    
    # 開発設定
    DEBUG: bool = True
    RELOAD: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # ディレクトリを作成
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()