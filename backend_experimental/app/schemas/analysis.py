from pydantic import BaseModel, field_serializer
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from app.core.config import settings

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

    @field_serializer('created_at', 'completed_at')
    def serialize_datetime_jst(self, dt: Optional[datetime], _info):
        """DateTimeをJSTにシリアライズ"""
        if dt is None:
            return None
        return settings.format_jst(dt, "%Y-%m-%dT%H:%M:%S+09:00")

    class Config:
        from_attributes = True

class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    video_id: str
    video_type: Optional[str] = None  # Add video type for frontend branching
    overall_progress: int
    steps: List[ProcessingStep]
    estimated_time_remaining: Optional[int] = None
    current_step: Optional[str] = None  # Add current step for progress messages

class AnalysisResultResponse(BaseModel):
    id: str
    video_id: str
    video_type: Optional[str] = None  # Add video type
    status: AnalysisStatus

    # 進捗とエラー情報（重要：AnalysisResponseと統一）
    progress: Optional[int] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None

    skeleton_data: Optional[List[Dict[str, Any]]] = None
    instrument_data: Optional[List[Dict[str, Any]]] = None
    motion_analysis: Optional[Dict[str, Any]] = None  # Add motion analysis
    coordinate_data: Optional[Dict[str, Any]] = None
    velocity_data: Optional[Dict[str, Any]] = None
    angle_data: Optional[Dict[str, Any]] = None
    scores: Optional[Dict[str, Any]] = None  # Add scores
    avg_velocity: Optional[float] = None
    max_velocity: Optional[float] = None
    total_distance: Optional[float] = None
    total_frames: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None  # Add completed_at
    video: Optional[Dict[str, Any]] = None  # Add video details

    # Phase 2.1で追加されたフィールド
    tracking_stats: Optional[Dict[str, Any]] = None  # トラッキング統計情報

    # DeepGaze III視線解析データ（eye_gazeタイプのみ）
    gaze_data: Optional[Dict[str, Any]] = None  # 視線解析データ

    @field_serializer('created_at', 'completed_at')
    def serialize_datetime_jst(self, dt: Optional[datetime], _info):
        """DateTimeをJSTにシリアライズ"""
        if dt is None:
            return None
        return settings.format_jst(dt, "%Y-%m-%dT%H:%M:%S+09:00")
    last_error_frame: Optional[int] = None  # 最後のエラーフレーム
    warnings: Optional[List[Dict[str, Any]]] = None  # 警告メッセージリスト

    class Config:
        from_attributes = True