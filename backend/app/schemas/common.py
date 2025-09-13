"""共通レスポンススキーマ"""

from pydantic import BaseModel
from typing import Optional, Any


class ErrorResponse(BaseModel):
    """エラーレスポンス"""
    detail: str
    status_code: Optional[int] = None
    error_type: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Video not found",
                "status_code": 404,
                "error_type": "NotFoundError"
            }
        }


class SuccessResponse(BaseModel):
    """成功レスポンス"""
    message: str
    data: Optional[Any] = None

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation completed successfully",
                "data": {"id": "123", "status": "completed"}
            }
        }


class ProgressResponse(BaseModel):
    """進捗レスポンス"""
    progress: int  # 0-100
    status: str
    step: str
    message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "progress": 50,
                "status": "processing",
                "step": "frame_extraction",
                "message": "フレームを抽出中..."
            }
        }

