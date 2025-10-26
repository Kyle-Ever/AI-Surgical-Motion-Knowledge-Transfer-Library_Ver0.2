"""グローバルエラーハンドラー"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import traceback
from typing import Union

from app.core.exceptions import BaseAppException

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    """カスタム例外のハンドラー"""
    logger.error(
        f"Application error: {exc.code} - {exc.message}",
        extra={
            "code": exc.code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """バリデーションエラーのハンドラー"""
    # 詳細エラー情報をコンソールに出力
    error_details = exc.errors()
    logger.warning(f"Validation error on {request.url.path}")
    logger.warning(f"Error details: {error_details}")
    logger.warning(f"Request body: {exc.body}")

    # extra付きログ（構造化ログ用）
    logger.warning(
        f"Validation error on {request.url.path}",
        extra={
            "errors": error_details,
            "body": exc.body,
            "path": request.url.path,
            "method": request.method
        }
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "入力データの検証に失敗しました",
                "details": {
                    "errors": exc.errors(),
                    "body": str(exc.body)[:500]  # 長すぎる場合は切り詰め
                }
            }
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """HTTPException のハンドラー"""
    logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "details": {}
            }
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """一般的な例外のハンドラー"""
    # スタックトレースを取得
    tb_str = traceback.format_exception(type(exc), exc, exc.__traceback__)
    tb_str = "".join(tb_str)

    logger.error(
        f"Unhandled exception: {type(exc).__name__} - {str(exc)}",
        extra={
            "exception_type": type(exc).__name__,
            "traceback": tb_str,
            "path": request.url.path,
            "method": request.method
        }
    )

    # 開発環境では詳細を返す
    import os
    is_dev = os.getenv("ENVIRONMENT", "development") == "development"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "内部サーバーエラーが発生しました",
                "details": {
                    "exception": str(exc),
                    "type": type(exc).__name__,
                    "traceback": tb_str if is_dev else None
                }
            }
        }
    )


def setup_exception_handlers(app):
    """FastAPIアプリケーションにエラーハンドラーを登録"""
    app.add_exception_handler(BaseAppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)