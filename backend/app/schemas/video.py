from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class VideoType(str, Enum):
    internal = "internal"
    external = "external"

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
    id: str
    filename: str
    message: str = "Upload successful"