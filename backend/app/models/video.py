from sqlalchemy import Column, String, DateTime, Text, Enum
from sqlalchemy.sql import func
from app.models import Base
import uuid
import enum

class VideoType(str, enum.Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"

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
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())