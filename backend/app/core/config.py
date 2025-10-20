from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    # API設定
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AI手技モーションライブラリ"
    VERSION: str = "0.1.0"

    # CORS設定
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:3001", "http://localhost:8000"]

    # データベース
    DATABASE_URL: str = "sqlite:///./aimotion.db"

    # ファイルストレージ
    DATA_DIR: Path = Path("./data")
    UPLOAD_DIR: Path = Path("./data/uploads")
    TEMP_DIR: Path = Path("./data/temp")
    MAX_UPLOAD_SIZE: int = 1 * 1024 * 1024 * 1024  # 1GB
    ALLOWED_EXTENSIONS: set = {".mp4", ".mov", ".avi"}
    
    # AI処理設定
    FRAME_EXTRACTION_FPS: int = 15  # フレーム抽出レート（5=高速/低精度, 15=バランス, 30=低速/高精度）
    YOLO_MODEL: str = "yolov8n.pt"
    MEDIAPIPE_MIN_DETECTION_CONFIDENCE: float = 0.8
    MEDIAPIPE_MIN_TRACKING_CONFIDENCE: float = 0.8

    # 手袋検出設定
    USE_ADVANCED_GLOVE_DETECTION: bool = False  # 高性能な手袋検出器を使用するか（デフォルト無効で後方互換性維持）

    # SAM器具追跡設定
    SAM_USE_MOCK: bool = False  # モックモードを無効化して実際の追跡を使用
    SAM_DEVICE: str = "auto"  # GPU/CPU自動検出 ("auto", "cuda", "cpu")
    SAM_REDETECTION_INTERVAL: int = 30  # 再検出間隔（フレーム数）
    SAM_CONFIDENCE_THRESHOLD: float = 0.7  # 信頼度閾値
    SAM_USE_PROACTIVE_REDETECTION: bool = True  # プロアクティブ再検出を有効化

    # SAMトラッカーモード設定
    SAM_TRACKER_MODE: str = "enhanced"  # "enhanced" (マルチポイント+カルマン), "full_sam" (毎フレームSAM), "hybrid" (部分SAM), "legacy" (OpenCV併用)
    SAM_FRAME_SKIP: int = 1  # SAM検出の頻度 (1=毎フレーム, 5=5フレームごと)
    SAM_BATCH_SIZE: int = 10  # バッチ処理サイズ
    SAM_USE_CACHE: bool = True  # 検出結果のキャッシュを使用

    # Enhanced SAMトラッカー詳細パラメータ
    SAM_ENHANCED_CONFIDENCE_THRESHOLD: float = 0.3  # 検出の信頼度閾値（低めに設定）
    SAM_ENHANCED_MAX_LOST_FRAMES: int = 50  # ロストを許容する最大フレーム数
    SAM_ENHANCED_SEARCH_EXPANSION: float = 2.0  # 探索範囲の拡張倍率
    SAM_ENHANCED_MAX_SIZE_CHANGE: float = 3.0  # 許容するサイズ変化倍率
    SAM_ENHANCED_ENABLE_KALMAN: bool = True  # カルマンフィルター使用
    SAM_ENHANCED_ENABLE_MULTIPOINT: bool = True  # マルチポイントプロンプト使用
    SAM_ENHANCED_ENABLE_BOX_PROMPT: bool = True  # ボックスプロンプト使用
    SAM_ENHANCED_REDETECTION_INTERVAL: int = 15  # 定期的な再検出の間隔（フレーム数）

    # SAM2設定
    USE_SAM2: bool = True  # SAM2を有効化（高精度、JPEG一時保存方式）
    SAM2_MODEL_TYPE: str = "small"  # tiny, small, base_plus, large
    SAM2_TEMP_DIR: Path = Path("./temp_frames")  # JPEG一時保存ディレクトリ

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