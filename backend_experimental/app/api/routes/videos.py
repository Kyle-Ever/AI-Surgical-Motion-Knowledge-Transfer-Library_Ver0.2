"""
動画CRUD エンドポイント

アップロード、メタデータ取得、ストリーミング、サムネイル取得を提供。
器具セグメンテーション関連は segmentation.py に分離。
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, status, Request
from fastapi.responses import FileResponse, StreamingResponse, Response
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import uuid
from pathlib import Path
import cv2
import logging

from app.models import get_db
from app.models.video import Video, VideoType
from app.schemas.video import VideoResponse, VideoUploadResponse
from app.schemas.common import ErrorResponse
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _stream_video_with_range(
    video_path: Path,
    file_size: int,
    range_header: Optional[str],
    content_disposition: str,
) -> Response:
    """Stream a video file with HTTP Range support.

    Shared helper used by both ``stream_video_or_sample`` and
    ``stream_video`` to avoid duplicating the Range-header parsing and
    chunked-streaming logic.

    Args:
        video_path: Absolute path to the video file on disk.
        file_size: Size of the file in bytes.
        range_header: Raw ``Range`` request header value, or *None*.
        content_disposition: Pre-built ``Content-Disposition`` header value.

    Returns:
        A ``FileResponse`` (full file) or ``StreamingResponse`` (206 partial).
    """

    base_headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": content_disposition,
        "Content-Length": str(file_size),
    }

    if not range_header:
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            headers=base_headers,
        )

    try:
        range_str = range_header.replace("bytes=", "")
        range_parts = range_str.split("-")

        start = int(range_parts[0]) if range_parts[0] else 0
        end = int(range_parts[1]) if range_parts[1] else file_size - 1

        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        content_length = end - start + 1

        def _iterfile() -> bytes:
            with open(video_path, "rb") as fh:
                fh.seek(start)
                remaining = content_length
                while remaining:
                    chunk = fh.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            _iterfile(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
                "Content-Disposition": content_disposition,
            },
        )
    except Exception:
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            headers=base_headers,
        )


def _build_content_disposition(filename: str) -> str:
    """Build a Content-Disposition header value, handling non-ASCII filenames."""
    import urllib.parse

    try:
        filename.encode("ascii")
        return f'inline; filename="{filename}"'
    except UnicodeEncodeError:
        encoded = urllib.parse.quote(filename)
        return f"inline; filename*=UTF-8''{encoded}"


def fix_encoding(text: Optional[str]) -> Optional[str]:
    """
    文字エンコーディングの修正（安全版）
    文字化け検出 → 検出された場合のみ変換

    Args:
        text: 修正対象のテキスト（Shift-JIS/CP932がUTF-8として誤解釈された可能性）

    Returns:
        修正後のテキスト（修正不要または失敗時は元のテキスト）
    """
    if not text:
        return text

    # 文字化け検出: 制御文字・無効文字の存在確認
    suspicious_chars = sum(1 for c in text if ord(c) < 32 or (ord(c) > 126 and ord(c) < 0x3000))

    # 30%未満なら正常と判断（誤検出を避ける）
    if suspicious_chars < len(text) * 0.3:
        logger.debug(f"[ENCODING] Text appears valid UTF-8: {text[:50]}...")
        return text

    logger.warning(f"[ENCODING] Suspicious characters detected ({suspicious_chars}/{len(text)}): {text[:50]}...")

    # 複数エンコーディング試行（優先度順）
    encodings = ['shift-jis', 'cp932', 'euc-jp', 'iso-2022-jp']
    for encoding in encodings:
        try:
            bytes_data = text.encode('latin-1')
            decoded = bytes_data.decode(encoding)

            has_japanese = any(
                '\u3040' <= c <= '\u309F' or  # ひらがな
                '\u30A0' <= c <= '\u30FF' or  # カタカナ
                '\u4E00' <= c <= '\u9FFF'     # 漢字
                for c in decoded
            )

            if has_japanese:
                logger.info(f"[ENCODING] Successfully decoded with {encoding}: {decoded[:50]}...")
                return decoded
        except (UnicodeDecodeError, UnicodeEncodeError) as e:
            logger.debug(f"[ENCODING] Failed to decode with {encoding}: {e}")
            continue

    logger.warning(f"[ENCODING] All decoding attempts failed, returning original text")
    return text


@router.post(
    "/upload",
    response_model=VideoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a video",
    responses={
        400: {"description": "Invalid input or file type not allowed", "model": ErrorResponse},
        413: {"description": "File too large", "model": ErrorResponse},
    },
)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    video_type: str = Form(...),
    surgery_name: Optional[str] = Form(None),
    surgery_date: Optional[str] = Form(None),
    surgeon_name: Optional[str] = Form(None),
    memo: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a video file"""

    # 文字エンコーディングの修正
    surgery_name = fix_encoding(surgery_name)
    surgeon_name = fix_encoding(surgeon_name)
    memo = fix_encoding(memo)

    # ファイル拡張子チェック
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {file_extension} not allowed")

    # video_type validation
    try:
        _ = VideoType(video_type)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid video_type: {video_type}")
    # ensure size attr exists for safe check
    if not hasattr(file, "size"):
        try:
            setattr(file, "size", None)
        except Exception:
            pass

    # ファイルサイズチェック（簡易版）
    if file.size and file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds limit")

    # ユニークなファイル名を生成
    video_id = str(uuid.uuid4())
    filename = f"{video_id}{file_extension}"
    file_path = settings.UPLOAD_DIR / filename

    # ファイル保存
    try:
        bytes_written = 0
        chunk_size = 1024 * 1024  # 1MB
        with file_path.open("wb") as buffer:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > settings.MAX_UPLOAD_SIZE:
                    buffer.close()
                    if file_path.exists():
                        try:
                            file_path.unlink()
                        except Exception:
                            pass
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File size exceeds limit")
                buffer.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # データベースに保存
    try:
        parsed_date = None
        if surgery_date:
            try:
                parsed_date = datetime.fromisoformat(surgery_date)
            except (ValueError, TypeError):
                logger.warning(f"Failed to parse surgery_date: {surgery_date}")

        video = Video(
            id=video_id,
            filename=filename,
            original_filename=fix_encoding(file.filename),
            video_type=VideoType(video_type),
            surgery_name=surgery_name,
            surgery_date=parsed_date,
            surgeon_name=surgeon_name,
            memo=memo,
            file_path=str(file_path)
        )

        db.add(video)
        db.commit()
        db.refresh(video)

        return VideoUploadResponse(
            video_id=video_id,
            filename=filename,
            message="Upload successful"
        )

    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Get video metadata",
    responses={404: {"description": "Video not found", "model": ErrorResponse}},
)
async def get_video(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Get video"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.get(
    "/",
    response_model=list[VideoResponse],
    summary="List videos",
)
async def list_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List videos"""
    videos = db.query(Video).offset(skip).limit(limit).all()
    return videos


@router.get(
    "/stream/{video_id}",
    summary="Stream video file (sample or database)",
    responses={404: {"description": "Video not found"}},
)
async def stream_video_or_sample(
    video_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Stream video file for playback with Range support (handles sample videos)"""

    if video_id in ["sample_reference", "sample_evaluation"]:
        videos = db.query(Video).limit(2).all()
        if not videos:
            raise HTTPException(status_code=404, detail="No sample videos available")

        if video_id == "sample_reference":
            video = videos[0]
        else:
            video = videos[1] if len(videos) > 1 else videos[0]
    else:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(video.file_path)
    if not video_path.is_absolute():
        video_path = Path.cwd() / video_path

    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video file not found at {video_path}")

    safe_filename = video.original_filename if hasattr(video, 'original_filename') else "video.mp4"
    content_disposition = _build_content_disposition(safe_filename)

    return _stream_video_with_range(
        video_path=video_path,
        file_size=video_path.stat().st_size,
        range_header=request.headers.get("range"),
        content_disposition=content_disposition,
    )


@router.api_route(
    "/{video_id}/stream",
    methods=["GET", "HEAD"],
    summary="Stream video file",
    responses={404: {"description": "Video not found"}},
)
async def stream_video(
    video_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Stream video file for playback with Range support (GET and HEAD methods)"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(video.file_path)
    if not video_path.is_absolute():
        video_path = Path.cwd() / video_path

    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video file not found at {video_path}")

    content_disposition = _build_content_disposition(video.original_filename)

    return _stream_video_with_range(
        video_path=video_path,
        file_size=video_path.stat().st_size,
        range_header=request.headers.get("range"),
        content_disposition=content_disposition,
    )


@router.get(
    "/{video_id}/thumbnail",
    summary="Get video thumbnail (first frame)",
    responses={404: {"description": "Video not found"}},
)
async def get_video_thumbnail(
    video_id: str,
    width: int = None,
    height: int = None,
    db: Session = Depends(get_db)
):
    """Get the first frame of the video as a thumbnail (original size for coordinate consistency)"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(video.file_path)
    if not video_path.is_absolute():
        video_path = Path.cwd() / video_path

    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video file not found at {video_path}")

    try:
        cap = cv2.VideoCapture(str(video_path))
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=500, detail="Failed to extract frame from video")

        logger.info(f"[THUMBNAIL] Original frame shape: {frame.shape}")
        if width and height:
            frame = cv2.resize(frame, (width, height))
            logger.info(f"[THUMBNAIL] Resized to: {width}x{height}")
        else:
            logger.info(f"[THUMBNAIL] Returning original size: {frame.shape[1]}x{frame.shape[0]}")

        _, buffer = cv2.imencode('.jpg', frame)
        img_bytes = buffer.tobytes()

        return Response(content=img_bytes, media_type="image/jpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate thumbnail: {str(e)}")
