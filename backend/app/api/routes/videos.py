from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import shutil
import uuid
from pathlib import Path

from app.models import get_db
from app.models.video import Video, VideoType
from app.schemas.video import VideoResponse, VideoUploadResponse, VideoCreate
from app.schemas.common import ErrorResponse
from app.core.config import settings
from app.services.video_service import VideoService

router = APIRouter()

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
    
    # ファイルサイズチェック（簡易版）    if file.size and file.size > settings.MAX_UPLOAD_SIZE:
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
    
    # データベースに保存    try:
        # 日付のパース
        parsed_date = None
        if surgery_date:
            try:
                parsed_date = datetime.fromisoformat(surgery_date)
            except:
                pass
        
        video = Video(
            id=video_id,
            filename=filename,
            original_filename=file.filename,
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
        
        # バックグラウンドでビデオメタデータを抽出（後で実装）        # background_tasks.add_task(extract_video_metadata, video_id, db)
        
        return VideoUploadResponse(
            id=video_id,
            filename=filename,
            message="Upload successful"
        )
        
    except Exception as e:
        # エラー時はファイルを削除
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
