from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

class AnalysisStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class ProcessingStep(BaseModel):
    name: str
    status: str
    progress: Optional[int] = None
    message: Optional[str] = None

class AnalysisCreate(BaseModel):
    video_id: str
    instruments: Optional[List[Dict[str, Any]]] = None
    sampling_rate: int = 5

class AnalysisResponse(BaseModel):
    id: str
    video_id: str
    status: AnalysisStatus
    progress: int
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    video_id: str
    overall_progress: int
    steps: List[ProcessingStep]
    estimated_time_remaining: Optional[int] = None

class AnalysisResultResponse(BaseModel):
    id: str
    video_id: str
    status: AnalysisStatus
    coordinate_data: Optional[Dict[str, Any]] = None
    velocity_data: Optional[Dict[str, Any]] = None
    angle_data: Optional[Dict[str, Any]] = None
    avg_velocity: Optional[float] = None
    max_velocity: Optional[float] = None
    total_distance: Optional[float] = None
    total_frames: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True