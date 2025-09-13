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
from app.core.config import settings
from app.services.video_service import VideoService

router = APIRouter()

@router.post("/upload", response_model=VideoUploadResponse)
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
    
    # 繝輔ぃ繧､繝ｫ諡｡蠑ｵ蟄舌メ繧ｧ繝・け
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
    
    # 繝輔ぃ繧､繝ｫ繧ｵ繧､繧ｺ繝√ぉ繝・け・育ｰ｡譏鍋沿・・    if file.size and file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds limit")
    
    # 繝ｦ繝九・繧ｯ縺ｪ繝輔ぃ繧､繝ｫ蜷阪ｒ逕滓・
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
    
    # 繝・・繧ｿ繝吶・繧ｹ縺ｫ菫晏ｭ・    try:
        # 譌･莉倥・繝代・繧ｹ
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
        
        # 繝舌ャ繧ｯ繧ｰ繝ｩ繧ｦ繝ｳ繝峨〒繝薙ョ繧ｪ繝｡繧ｿ繝・・繧ｿ繧呈歓蜃ｺ・亥ｾ後〒螳溯｣・ｼ・        # background_tasks.add_task(extract_video_metadata, video_id, db)
        
        return VideoUploadResponse(
            id=video_id,
            filename=filename,
            message="Upload successful"
        )
        
    except Exception as e:
        # 繧ｨ繝ｩ繝ｼ譎ゅ・繝輔ぃ繧､繝ｫ繧貞炎髯､
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Get video"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.get("/", response_model=list[VideoResponse])
async def list_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List videos"""
    videos = db.query(Video).offset(skip).limit(limit).all()
    return videos
