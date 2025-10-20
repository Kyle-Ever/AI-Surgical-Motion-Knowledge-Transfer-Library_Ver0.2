from sqlalchemy import Column, String, DateTime, Text, Enum
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

class VideoType(str, enum.Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"  # 外部器具なし（後方互換性のため残す）
    EXTERNAL_NO_INSTRUMENTS = "external_no_instruments"  # 外部器具なし
    EXTERNAL_WITH_INSTRUMENTS = "external_with_instruments"  # 外部器具あり
    EYE_GAZE = "eye_gaze"  # 視線解析（DeepGaze III）

class Video(Base):
    __tablename__ = "videos"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    video_type = Column(Enum(VideoType), nullable=False)
    surgery_name = Column(String(255), nullable=True)
    surgery_date = Column(DateTime, nullable=True)
    surgeon_name = Column(String(255), nullable=True)
    memo = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=False)
    duration = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=get_jst_now)
    updated_at = Column(DateTime, default=get_jst_now, onupdate=get_jst_now)