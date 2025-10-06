"""カスタム例外クラス定義"""

from typing import Optional, Dict, Any
import logging
import traceback

logger = logging.getLogger(__name__)


class BaseAppException(Exception):
    """アプリケーション基底例外クラス"""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

        # Log the exception with details
        logger.error(
            f"Exception occurred: {code} - {message}",
            extra={
                "error_code": code,
                "error_status": status_code,
                "error_details": self.details
            }
        )

        super().__init__(self.message)


class VideoProcessingError(BaseAppException):
    """動画処理関連のエラー"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VIDEO_PROCESSING_ERROR",
            status_code=500,
            details=details
        )


class AnalysisError(BaseAppException):
    """解析処理関連のエラー"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="ANALYSIS_ERROR",
            status_code=500,
            details=details
        )


class ModelInitializationError(BaseAppException):
    """モデル初期化エラー"""

    def __init__(self, message: str, model_name: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="MODEL_INIT_ERROR",
            status_code=500,
            details={**(details or {}), "model_name": model_name}
        )


class DatabaseError(BaseAppException):
    """データベース関連のエラー"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=500,
            details=details
        )


class ValidationError(BaseAppException):
    """バリデーションエラー"""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            details={**(details or {}), "field": field} if field else details
        )


class FileNotFoundError(BaseAppException):
    """ファイル未検出エラー"""

    def __init__(self, message: str, file_path: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="FILE_NOT_FOUND",
            status_code=404,
            details={**(details or {}), "file_path": file_path}
        )


class ResourceLimitError(BaseAppException):
    """リソース制限エラー"""

    def __init__(self, message: str, resource_type: str, limit: Any = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="RESOURCE_LIMIT_ERROR",
            status_code=429,
            details={
                **(details or {}),
                "resource_type": resource_type,
                "limit": limit
            }
        )


class WebSocketError(BaseAppException):
    """WebSocket通信エラー"""

    def __init__(self, message: str, connection_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="WEBSOCKET_ERROR",
            status_code=500,
            details={**(details or {}), "connection_id": connection_id} if connection_id else details
        )