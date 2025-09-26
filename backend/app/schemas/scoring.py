from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

# Enums
class ReferenceType(str, Enum):
    expert = "expert"
    standard = "standard"
    custom = "custom"

class ComparisonStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

# Reference Model Schemas
class ReferenceModelCreate(BaseModel):
    name: str
    description: Optional[str] = None
    analysis_id: str
    reference_type: ReferenceType = ReferenceType.expert
    surgeon_name: Optional[str] = None
    surgery_type: Optional[str] = None
    surgery_date: Optional[datetime] = None
    weights: Optional[Dict[str, float]] = None

class ReferenceModelResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    analysis_id: str
    reference_type: ReferenceType
    surgeon_name: Optional[str] = None
    surgery_type: Optional[str] = None
    surgery_date: Optional[datetime] = None
    weights: Dict[str, float]
    avg_speed_score: Optional[float] = None
    avg_smoothness_score: Optional[float] = None
    avg_stability_score: Optional[float] = None
    avg_efficiency_score: Optional[float] = None
    created_at: datetime
    is_active: int

    class Config:
        from_attributes = True

class ReferenceModelListResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    surgeon_name: Optional[str] = None
    surgery_type: Optional[str] = None
    surgery_date: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Comparison Schemas
class ComparisonCreate(BaseModel):
    reference_model_id: str
    learner_analysis_id: str

class ComparisonResponse(BaseModel):
    id: str
    reference_model_id: str
    learner_analysis_id: str
    status: ComparisonStatus
    progress: int
    overall_score: Optional[float] = None
    speed_score: Optional[float] = None
    smoothness_score: Optional[float] = None
    stability_score: Optional[float] = None
    efficiency_score: Optional[float] = None
    dtw_distance: Optional[float] = None
    feedback: Optional[Dict[str, Any]] = None
    metrics_comparison: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ComparisonDetailResponse(ComparisonResponse):
    comparison_data: Optional[Dict[str, Any]] = None
    temporal_alignment: Optional[Dict[str, Any]] = None
    reference_model: Optional[ReferenceModelResponse] = None

    class Config:
        from_attributes = True

# Feedback Schema
class FeedbackItem(BaseModel):
    category: str  # "strength" or "weakness" or "suggestion"
    title: str
    description: str
    importance: float  # 0.0 to 1.0
    specific_time: Optional[float] = None  # 特定の時間点での指摘

class DetailedFeedback(BaseModel):
    strengths: List[FeedbackItem]
    weaknesses: List[FeedbackItem]
    suggestions: List[FeedbackItem]
    overall_summary: str
    improvement_priority: List[str]  # 改善優先度リスト

# Report Schema
class ComparisonReport(BaseModel):
    comparison_id: str
    learner_name: Optional[str] = None
    reference_name: str
    comparison_date: datetime
    overall_score: float
    detailed_scores: Dict[str, float]
    feedback: DetailedFeedback
    improvement_plan: List[str]
    graphs_data: Optional[Dict[str, Any]] = None  # グラフ用データ