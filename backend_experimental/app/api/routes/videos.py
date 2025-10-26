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
            # latin-1として受信したデータを正しいエンコーディングでデコード
            bytes_data = text.encode('latin-1')
            decoded = bytes_data.decode(encoding)

            # 有効な日本語文字が含まれるか確認
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

    # すべて失敗した場合は元のテキストを返す
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
            original_filename=fix_encoding(file.filename),  # ファイル名も修正
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
    width: int = None,  # 元サイズを使用
    height: int = None,  # 元サイズを使用
    db: Session = Depends(get_db)
):
    """Get the first frame of the video as a thumbnail (original size for coordinate consistency)"""
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

        # 元サイズのまま使用（SAM2との座標系統一のため）
        # リサイズが指定された場合のみリサイズ（後方互換性）
        logger.info(f"[THUMBNAIL] Original frame shape: {frame.shape}")
        if width and height:
            frame = cv2.resize(frame, (width, height))
            logger.info(f"[THUMBNAIL] Resized to: {width}x{height}")
        else:
            logger.info(f"[THUMBNAIL] Returning original size: {frame.shape[1]}x{frame.shape[0]}")

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

        # 元のサイズのまま使用（SAM2 Video APIと座標系を統一）
        # SAM2は元動画を読み込むため、セグメンテーションも元サイズで実行
        logger.info(f"Frame shape (original): {frame.shape}")

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

# Global ToolDetector instance
_tool_detector = None

def get_tool_detector():
    """Get or initialize Tool Detector"""
    global _tool_detector
    if _tool_detector is None:
        from app.ai_engine.processors.tool_detector import ToolDetector, YOLOModel
        _tool_detector = ToolDetector(
            model_size=YOLOModel.NANO,
            confidence_threshold=0.3,  # 低めの閾値で多めに検出
            force_mock=False  # 実YOLO使用
        )
    return _tool_detector

@router.post(
    "/{video_id}/detect-instruments",
    summary="Detect surgical instruments using YOLO",
    responses={404: {"description": "Video not found"}},
)
async def detect_instruments(
    video_id: str,
    request_body: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Detect surgical instruments in a video frame using YOLOv8

    Returns list of detected instruments with bounding boxes and confidence scores
    """
    frame_number = request_body.get("frame_number", 0)
    logger.info(f"[DETECT] Starting instrument detection for video {video_id}, frame {frame_number}")

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(video.file_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    try:
        # Extract specified frame
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=400, detail=f"Failed to extract frame {frame_number}")

        logger.info(f"[DETECT] Frame extracted: {frame.shape}")

        # Initialize detector
        detector = get_tool_detector()

        # Perform detection
        detection_result = detector.detect_from_frame(frame)

        logger.info(f"[DETECT] Detected {len(detection_result['instruments'])} instruments")

        # Format response
        instruments = []
        for inst in detection_result["instruments"]:
            bbox = inst["bbox"]
            instruments.append({
                "id": inst["id"],
                "bbox": [bbox["x_min"], bbox["y_min"], bbox["x_max"], bbox["y_max"]],
                "confidence": inst["confidence"],
                "class_name": inst["type"],
                "suggested_name": _translate_tool_name(inst["type"]),
                "center": inst["center"]
            })

        return {
            "video_id": video_id,
            "frame_number": frame_number,
            "instruments": instruments,
            "model_info": detection_result["model_info"]
        }

    except Exception as e:
        logger.error(f"[DETECT] Detection failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

def _translate_tool_name(tool_type: str) -> str:
    """Translate tool type to Japanese name"""
    translations = {
        "knife": "メス",
        "scalpel": "メス",
        "scissors": "ハサミ",
        "forceps": "鉗子",
        "needle_holder": "持針器",
        "retractor": "開創器",
        "suction": "吸引器",
        "electrocautery": "電気メス",
        "clip_applier": "クリップ鉗子",
        "grasper": "把持鉗子",
        "dissector": "剥離子",
        "bowl": "ボウル",
        "cup": "カップ"
    }
    return translations.get(tool_type, f"器具_{tool_type}")

@router.post(
    "/{video_id}/segment-from-detection",
    summary="Generate SAM mask from YOLO detection",
    responses={404: {"description": "Video not found"}},
)
async def segment_from_detection(
    video_id: str,
    request_body: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Generate precise segmentation mask from YOLO detection bounding box

    Uses SAM2 to create accurate mask from detected instrument bbox
    """
    bbox = request_body.get("bbox")
    detection_id = request_body.get("detection_id")
    frame_number = request_body.get("frame_number", 0)

    logger.info(f"[SEGMENT-DETECT] Generating mask from detection {detection_id} for video {video_id}")

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(video.file_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    try:
        # Extract frame
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=400, detail=f"Failed to extract frame {frame_number}")

        # Initialize SAM tracker
        tracker = get_sam_tracker()
        tracker.set_image(frame)

        # Segment with bounding box
        x1, y1, x2, y2 = bbox
        result = tracker.segment_with_box(
            box=(int(x1), int(y1), int(x2), int(y2))
        )

        # Convert mask to base64
        mask = result["mask"]
        mask_uint8 = (mask * 255).astype(np.uint8)
        _, mask_encoded = cv2.imencode('.png', mask_uint8)
        mask_base64 = base64.b64encode(mask_encoded.tobytes()).decode('utf-8')

        # Create visualization
        vis_frame = tracker.visualize_result(frame, result)
        _, vis_encoded = cv2.imencode('.jpg', vis_frame)
        vis_base64 = base64.b64encode(vis_encoded.tobytes()).decode('utf-8')

        logger.info(f"[SEGMENT-DETECT] Mask generated successfully")

        return {
            "mask": mask_base64,
            "visualization": vis_base64,
            "bbox": result["bbox"],
            "score": result["score"],
            "area": result["area"],
            "detection_id": detection_id,
            "frame_number": frame_number
        }

    except Exception as e:
        logger.error(f"[SEGMENT-DETECT] Segmentation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Segmentation failed: {str(e)}")


# Global SAM2 Auto Mask Generator instance
_sam2_auto_generator = None

def get_sam2_auto_generator():
    """Get or initialize SAM2 Auto Mask Generator"""
    global _sam2_auto_generator
    if _sam2_auto_generator is None:
        from app.ai_engine.processors.sam2_auto_mask_generator import SAM2AutoMaskGenerator
        _sam2_auto_generator = SAM2AutoMaskGenerator(min_mask_area=500)
    return _sam2_auto_generator


@router.post(
    "/{video_id}/detect-instruments-sam2",
    summary="Detect surgical instruments using SAM2 automatic mask generation",
    responses={404: {"description": "Video not found"}},
)
async def detect_instruments_sam2(
    video_id: str,
    request_body: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    SAM2の自動マスク生成を使用した器具検出

    YOLOとの違い:
    - より高精度なセグメンテーション
    - 細長い物体の検出に優れる
    - クラス分類なし（すべてのオブジェクトを検出）

    Returns:
        検出されたマスクのリスト（バウンディングボックス、信頼度付き）
    """
    frame_number = request_body.get("frame_number", 0)
    min_confidence = request_body.get("min_confidence", 0.5)
    max_results = request_body.get("max_results", 10)

    logger.info(f"[DETECT-SAM2] Starting SAM2 auto detection for video {video_id}, frame {frame_number}")

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(video.file_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    try:
        # Extract specified frame
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=400, detail=f"Failed to extract frame {frame_number}")

        logger.info(f"[DETECT-SAM2] Frame extracted: {frame.shape}")

        # Initialize SAM2 auto mask generator
        generator = get_sam2_auto_generator()

        # Generate masks
        masks = generator.generate_masks(frame)

        # Filter by confidence
        masks = generator.filter_by_confidence(masks, min_confidence)

        # Merge overlapping masks
        masks = generator.merge_overlapping_masks(masks, iou_threshold=0.5)

        # Limit results
        masks = masks[:max_results]

        logger.info(f"[DETECT-SAM2] Generated {len(masks)} masks")

        # Format response (similar to YOLO format for compatibility)
        instruments = []
        for mask_data in masks:
            bbox = mask_data["bbox"]
            instruments.append({
                "id": mask_data["id"],
                "bbox": bbox,
                "confidence": mask_data["confidence"],
                "class_name": "instrument",
                "suggested_name": mask_data["suggested_name"],
                "center": mask_data["center"],
                "area": mask_data["area"],
                "aspect_ratio": mask_data["aspect_ratio"],
                "mask_base64": None  # マスクは必要に応じて生成
            })

        return {
            "video_id": video_id,
            "frame_number": frame_number,
            "instruments": instruments,
            "model_info": {
                "model_type": "sam2_auto_mask",
                "min_confidence": min_confidence,
                "is_mock": generator.is_mock
            }
        }

    except Exception as e:
        logger.error(f"[DETECT-SAM2] Detection failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


