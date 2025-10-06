from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, status, Body, Request
from fastapi.responses import FileResponse, StreamingResponse, Response
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import mimetypes
import shutil
import uuid
from pathlib import Path
import cv2
import numpy as np
import base64
import json
import os
import logging

from app.models import get_db
from app.models.video import Video, VideoType
from app.schemas.video import VideoResponse, VideoUploadResponse, VideoCreate
from app.schemas.common import ErrorResponse
from app.core.config import settings
from app.services.video_service import VideoService
from app.ai_engine.processors.sam_tracker import SAMTracker

router = APIRouter()
logger = logging.getLogger(__name__)

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
        
        # バックグラウンドでビデオメタデータを抽出（後で実装）
        # background_tasks.add_task(extract_video_metadata, video_id, db)
        
        return VideoUploadResponse(
            video_id=video_id,
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

    # Check if it's a sample video request
    if video_id in ["sample_reference", "sample_evaluation"]:
        # Use first available video from database as sample
        videos = db.query(Video).limit(2).all()
        if not videos:
            # If no videos in database, return a 404
            raise HTTPException(status_code=404, detail="No sample videos available")

        # Use first video as reference, second as evaluation (or same if only one)
        if video_id == "sample_reference":
            video = videos[0]
        else:
            video = videos[1] if len(videos) > 1 else videos[0]
    else:
        # Regular video lookup by ID
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

    # Convert to absolute path if relative
    video_path = Path(video.file_path)
    if not video_path.is_absolute():
        video_path = Path.cwd() / video_path

    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video file not found at {video_path}")

    # Get file size
    file_size = video_path.stat().st_size

    # Parse Range header
    range_header = request.headers.get('range')

    # Handle filename encoding for Content-Disposition header
    import urllib.parse
    safe_filename = video.original_filename if hasattr(video, 'original_filename') else "video.mp4"
    try:
        safe_filename.encode('ascii')
        content_disposition = f'inline; filename="{safe_filename}"'
    except UnicodeEncodeError:
        encoded_filename = urllib.parse.quote(safe_filename)
        content_disposition = f"inline; filename*=UTF-8''{encoded_filename}"

    # If no range header, return the entire file
    if not range_header:
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": content_disposition,
                "Content-Length": str(file_size),
            }
        )

    # Parse range header
    try:
        # Format: "bytes=start-end"
        range_str = range_header.replace('bytes=', '')
        range_parts = range_str.split('-')

        start = int(range_parts[0]) if range_parts[0] else 0
        end = int(range_parts[1]) if range_parts[1] else file_size - 1

        # Ensure valid range
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))

        # Calculate content length
        content_length = end - start + 1

        # Create generator for streaming
        def iterfile(file_path: Path, start: int, end: int):
            with open(file_path, 'rb') as file:
                file.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk_size = min(8192, remaining)
                    data = file.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        # Return partial content
        return StreamingResponse(
            iterfile(video_path, start, end),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
                "Content-Disposition": content_disposition,
            }
        )
    except Exception as e:
        # If range parsing fails, return the entire file
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": content_disposition,
                "Content-Length": str(file_size),
            }
        )

@router.get(
    "/{video_id}/stream",
    summary="Stream video file",
    responses={404: {"description": "Video not found"}},
)
async def stream_video(
    video_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Stream video file for playback with Range support"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Convert to absolute path if relative
    video_path = Path(video.file_path)
    if not video_path.is_absolute():
        video_path = Path.cwd() / video_path

    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video file not found at {video_path}")

    # Get file size
    file_size = video_path.stat().st_size

    # Parse Range header
    range_header = request.headers.get('range')

    # Handle filename encoding for Content-Disposition header
    import urllib.parse
    safe_filename = video.original_filename
    try:
        safe_filename.encode('ascii')
        content_disposition = f'inline; filename="{safe_filename}"'
    except UnicodeEncodeError:
        encoded_filename = urllib.parse.quote(safe_filename)
        content_disposition = f"inline; filename*=UTF-8''{encoded_filename}"

    # If no range header, return the entire file
    if not range_header:
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": content_disposition,
                "Content-Length": str(file_size),
            }
        )

    # Parse range header
    try:
        # Format: "bytes=start-end"
        range_str = range_header.replace('bytes=', '')
        range_parts = range_str.split('-')

        start = int(range_parts[0]) if range_parts[0] else 0
        end = int(range_parts[1]) if range_parts[1] else file_size - 1

        # Ensure valid range
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))

        # Calculate content length
        content_length = end - start + 1

        # Create generator for streaming
        def iterfile(file_path: Path, start: int, end: int):
            with open(file_path, 'rb') as file:
                file.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk_size = min(8192, remaining)
                    data = file.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        # Return partial content
        return StreamingResponse(
            iterfile(video_path, start, end),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
                "Content-Disposition": content_disposition,
            }
        )
    except Exception as e:
        # If range parsing fails, return the entire file
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": content_disposition,
                "Content-Length": str(file_size),
            }
        )

@router.get(
    "/{video_id}/thumbnail",
    summary="Get video thumbnail (first frame)",
    responses={404: {"description": "Video not found"}},
)
async def get_video_thumbnail(
    video_id: str,
    width: int = 640,
    height: int = 480,
    db: Session = Depends(get_db)
):
    """Get the first frame of the video as a thumbnail"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Convert to absolute path if relative
    video_path = Path(video.file_path)
    if not video_path.is_absolute():
        video_path = Path.cwd() / video_path

    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video file not found at {video_path}")

    # Extract first frame
    try:
        cap = cv2.VideoCapture(str(video_path))
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=500, detail="Failed to extract frame from video")

        # Resize frame
        frame = cv2.resize(frame, (width, height))

        # Convert to JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        img_bytes = buffer.tobytes()

        return Response(content=img_bytes, media_type="image/jpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate thumbnail: {str(e)}")

# Global SAM tracker instance (initialized on first use)
_sam_tracker = None

def get_sam_tracker():
    """Get or initialize SAM tracker"""
    global _sam_tracker
    if _sam_tracker is None:
        _sam_tracker = SAMTracker(
            model_type="vit_b",
            checkpoint_path=None,  # Will use mock mode if not available
            device="cpu",
            use_mock=True  # Start with mock mode
        )
    return _sam_tracker

@router.post(
    "/{video_id}/segment",
    summary="Segment instrument using SAM",
    responses={404: {"description": "Video not found"}},
)
async def segment_instrument(
    video_id: str,
    prompt_type: str = Body(..., description="Type of prompt: 'point' or 'box'"),
    coordinates: List[List[float]] = Body(..., description="Coordinates for the prompt"),
    labels: Optional[List[int]] = Body(None, description="Labels for points (1=foreground, 0=background)"),
    frame_number: int = Body(0, description="Frame number to segment"),
    db: Session = Depends(get_db)
):
    """
    Segment an instrument in the video using SAM

    - For point prompt: coordinates = [[x1, y1], [x2, y2], ...]
    - For box prompt: coordinates = [[x1, y1, x2, y2]]
    """
    logger.info(f"Segment request: type={prompt_type}, coords={coordinates}, labels={labels}")

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(video.file_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    # Extract specified frame
    try:
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=400, detail=f"Failed to extract frame {frame_number}")

        # Resize frame to 640x480 (same as thumbnail)
        frame = cv2.resize(frame, (640, 480))
        logger.info(f"Frame shape after resize: {frame.shape}")

        # Initialize SAM tracker
        tracker = get_sam_tracker()
        tracker.set_image(frame)

        # Perform segmentation
        if prompt_type == "point":
            if labels is None:
                labels = [1] * len(coordinates)  # Default to all foreground

            result = tracker.segment_with_point(
                point_coords=[(int(c[0]), int(c[1])) for c in coordinates],
                point_labels=labels
            )
        elif prompt_type == "box":
            if len(coordinates) != 1 or len(coordinates[0]) != 4:
                raise HTTPException(status_code=400, detail="Box prompt requires exactly one box [x1, y1, x2, y2]")

            box = coordinates[0]
            result = tracker.segment_with_box(
                box=(int(box[0]), int(box[1]), int(box[2]), int(box[3]))
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid prompt_type: {prompt_type}")

        # Convert mask to base64 for transmission
        mask = result["mask"]
        mask_uint8 = (mask * 255).astype(np.uint8)
        _, mask_encoded = cv2.imencode('.png', mask_uint8)
        mask_base64 = base64.b64encode(mask_encoded.tobytes()).decode('utf-8')

        # Create visualization
        vis_frame = tracker.visualize_result(frame, result)
        _, vis_encoded = cv2.imencode('.jpg', vis_frame)
        vis_base64 = base64.b64encode(vis_encoded.tobytes()).decode('utf-8')

        return {
            "mask": mask_base64,
            "visualization": vis_base64,
            "bbox": result["bbox"],
            "score": result["score"],
            "area": result["area"],
            "prompt_type": prompt_type,
            "frame_number": frame_number
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Segmentation failed: {str(e)}")

@router.post(
    "/{video_id}/instruments",
    summary="Register selected instruments",
    responses={404: {"description": "Video not found"}},
)
async def register_instruments(
    video_id: str,
    body: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Register selected instruments for tracking

    Each instrument should have:
    - name: Instrument name
    - mask: Base64 encoded mask
    - bbox: Bounding box [x1, y1, x2, y2]
    - frame_number: Frame where it was selected
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Extract instruments list from body
    instruments = body.get("instruments", [])

    # Save instruments data (could be stored in database or file)
    instruments_file = Path(settings.UPLOAD_DIR) / f"{video_id}_instruments.json"

    try:
        # Prepare instruments data for storage
        instruments_data = []
        for inst in instruments:
            instruments_data.append({
                "name": inst["name"],
                "bbox": inst["bbox"],
                "frame_number": inst.get("frame_number", 0),
                "mask": inst.get("mask", "")  # Base64 encoded mask
            })

        # Save to file
        with instruments_file.open("w") as f:
            json.dump(instruments_data, f)

        return {
            "video_id": video_id,
            "instruments_count": len(instruments_data),
            "message": "Instruments registered successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register instruments: {str(e)}")

@router.get(
    "/{video_id}/instruments",
    summary="Get registered instruments",
    responses={404: {"description": "Video or instruments not found"}},
)
async def get_instruments(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Get registered instruments for a video"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    instruments_file = Path(settings.UPLOAD_DIR) / f"{video_id}_instruments.json"

    if not instruments_file.exists():
        return {"video_id": video_id, "instruments": []}

    try:
        with instruments_file.open("r") as f:
            instruments = json.load(f)

        return {"video_id": video_id, "instruments": instruments}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load instruments: {str(e)}")


