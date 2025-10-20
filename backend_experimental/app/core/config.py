from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

class Settings(BaseSettings):
    # API設定
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "MindモーションAI"
    VERSION: str = "0.1.0"
    PORT: int = 8000  # サーバーポート（実験版は8001）

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

    # 🧪 実験版: SAM2 Video API設定
    USE_SAM2_VIDEO_API: bool = True  # SAM2 Video APIを使用（Memory Bank + Temporal Context）
    SAM2_VIDEO_MODEL_TYPE: str = "large"  # tiny, small, base_plus, large (🆕 Phase 3)
    ENVIRONMENT: str = "development"  # development, experimental, production

    # 🎯 SAM2 Video API 精度優先設定
    SAM2_MASK_THRESHOLD: float = 0.7  # バイナリ化閾値（高精度: 0.0-1.0、推奨0.5-0.7）
    SAM2_MIN_MASK_AREA: int = 100  # 最小マスク面積（ピクセル、ノイズ除去用）
    SAM2_ENABLE_TEMPORAL_SMOOTHING: bool = True  # 時間的平滑化を有効化
    SAM2_SMOOTHING_WINDOW: int = 5  # 平滑化ウィンドウサイズ（3-7推奨）

    # 🎯 Phase 4: 動的閾値調整設定（動き速度に応じて閾値を自動調整）
    SAM2_ENABLE_DYNAMIC_THRESHOLD: bool = True  # 動的閾値調整を有効化
    SAM2_DYNAMIC_THRESHOLD_MIN: float = 0.4  # 高速移動時の最小閾値（追跡優先）
    SAM2_DYNAMIC_THRESHOLD_MAX: float = 0.7  # 静止時の最大閾値（精度優先）
    SAM2_MOTION_THRESHOLD_SLOW: float = 20.0  # 低速判定閾値（ピクセル）
    SAM2_MOTION_THRESHOLD_FAST: float = 50.0  # 高速判定閾値（ピクセル）

    # 開発設定
    DEBUG: bool = True
    RELOAD: bool = True

    # タイムゾーン設定
    TIMEZONE: str = "Asia/Tokyo"  # JST
    TIMEZONE_OFFSET_HOURS: int = 9  # UTC+9
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # ディレクトリを作成
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def PROJECT_ROOT(self) -> Path:
        """プロジェクトルート（backend_experimental/）を取得"""
        return Path(__file__).parent.parent.parent

    def get_sam2_video_checkpoint(self, model_type: Optional[str] = None) -> Path:
        """
        SAM2 Video APIのチェックポイントパスを取得

        Args:
            model_type: モデルタイプ（tiny, small, base_plus, large）

        Returns:
            チェックポイントファイルのPath
        """
        mt = model_type or self.SAM2_VIDEO_MODEL_TYPE
        filenames = {
            "tiny": "sam2.1_hiera_tiny.pt",
            "small": "sam2.1_hiera_small.pt",
            "base_plus": "sam2.1_hiera_base_plus.pt",
            "large": "sam2.1_hiera_large.pt"
        }

        # プロジェクトルートから探す
        checkpoint = self.PROJECT_ROOT / filenames[mt]
        if not checkpoint.exists():
            # フォールバック：models/ディレクトリ
            checkpoint = self.PROJECT_ROOT / "models" / filenames[mt]

        return checkpoint

    def get_sam2_video_config(self, model_type: Optional[str] = None) -> str:
        """
        SAM2 Video APIのconfigパスを取得（パッケージ内相対パス）

        Args:
            model_type: モデルタイプ（tiny, small, base_plus, large）

        Returns:
            Configファイルの相対パス（sam2パッケージからの相対）
        """
        mt = model_type or self.SAM2_VIDEO_MODEL_TYPE
        configs = {
            "tiny": "configs/sam2.1/sam2.1_hiera_t.yaml",
            "small": "configs/sam2.1/sam2.1_hiera_s.yaml",
            "base_plus": "configs/sam2.1/sam2.1_hiera_b+.yaml",
            "large": "configs/sam2.1/sam2.1_hiera_l.yaml"
        }
        return configs[mt]

    def now_jst(self) -> datetime:
        """現在時刻をJSTで取得"""
        jst = timezone(timedelta(hours=self.TIMEZONE_OFFSET_HOURS))
        return datetime.now(jst)

    def to_jst(self, dt: datetime) -> datetime:
        """UTC datetime を JST に変換"""
        if dt is None:
            return None

        # タイムゾーン情報がない場合、UTCとして扱う
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # JSTに変換
        jst = timezone(timedelta(hours=self.TIMEZONE_OFFSET_HOURS))
        return dt.astimezone(jst)

    def format_jst(self, dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S JST") -> str:
        """datetime を JST フォーマット文字列に変換"""
        if dt is None:
            return None

        jst_dt = self.to_jst(dt)
        return jst_dt.strftime(format_str)

settings = Settings()