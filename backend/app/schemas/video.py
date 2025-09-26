from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class VideoType(str, Enum):
    internal = "internal"
    external = "external"  # 後方互換性のため残す
    external_no_instruments = "external_no_instruments"  # 外部器具なし
    external_with_instruments = "external_with_instruments"  # 外部器具あり

class VideoBase(BaseModel):
    surgery_name: Optional[str] = None
    surgery_date: Optional[datetime] = None
    surgeon_name: Optional[str] = None
    memo: Optional[str] = None
    video_type: VideoType

class VideoCreate(VideoBase):
    pass

class VideoResponse(VideoBase):
    id: str
    filename: str
    original_filename: str
    duration: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class VideoUploadResponse(BaseModel):
    video_id: str
    filename: str
    message: str = "Upload successful"