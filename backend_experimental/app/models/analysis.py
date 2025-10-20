from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models import Base
import uuid
import enum
from datetime import datetime
import pytz

def get_jst_now():
    """日本時間（JST）の現在時刻を返す（タイムゾーン情報なし）"""
    jst = pytz.timezone('Asia/Tokyo')
    return datetime.now(jst).replace(tzinfo=None)

class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False)
    
    # 解析データ（JSONとして保存）
    skeleton_data = Column(JSON, nullable=True)  # 骨格検出データ
    instrument_data = Column(JSON, nullable=True)  # 器具検出データ
    motion_analysis = Column(JSON, nullable=True)  # モーション解析結果
    gaze_data = Column(JSON, nullable=True)  # 視線解析データ（DeepGaze III）
    scores = Column(JSON, nullable=True)  # スコア情報
    
    # 旧フィールド（互換性のため残す）
    coordinate_data = Column(JSON, nullable=True)
    velocity_data = Column(JSON, nullable=True)
    angle_data = Column(JSON, nullable=True)
    
    # 統計情報
    avg_velocity = Column(Float, nullable=True)
    max_velocity = Column(Float, nullable=True)
    total_distance = Column(Float, nullable=True)
    total_frames = Column(Integer, nullable=True)
    
    # 進捗情報
    progress = Column(Integer, default=0)
    current_step = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    # トラッキング詳細情報（Phase 2.1追加）
    tracking_stats = Column(JSON, nullable=True)  # {"instrument_0": {"lost_frames": 10, "re_detections": 2}, ...}
    last_error_frame = Column(Integer, nullable=True)  # 最後にエラーが発生したフレーム番号
    warnings = Column(JSON, nullable=True)  # [{"frame": 100, "message": "..."}, ...]

    created_at = Column(DateTime, default=get_jst_now)
    completed_at = Column(DateTime, nullable=True)
    
    # リレーション
    video = relationship("Video", backref="analysis_results")