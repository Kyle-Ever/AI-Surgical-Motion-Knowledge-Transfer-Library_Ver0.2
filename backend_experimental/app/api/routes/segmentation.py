"""
器具セグメンテーション・検出エンドポイント

SAM/SAM2/YOLOv8による器具検出・セグメンテーション機能を提供。
URLプレフィックスは /api/v1/videos で登録（フロントエンド互換性維持）。
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pathlib import Path
import cv2
import numpy as np
import base64
import json
import logging

from app.models import get_db
from app.models.video import Video
from app.core.config import settings
from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified as SAMTracker

router = APIRouter()
logger = logging.getLogger(__name__)


# === Global instances (lazy initialization) ===

_sam_tracker = None

def get_sam_tracker():
    """Get or initialize SAM tracker"""
    global _sam_tracker
    if _sam_tracker is None:
        _sam_tracker = SAMTracker(
            model_type="vit_b",
            checkpoint_path=None,
            device="cpu",
            use_mock=True
        )
    return _sam_tracker


_tool_detector = None

def get_tool_detector():
    """Get or initialize Tool Detector"""
    global _tool_detector
    if _tool_detector is None:
        from app.ai_engine.processors.tool_detector import ToolDetector, YOLOModel
        _tool_detector = ToolDetector(
            model_size=YOLOModel.NANO,
            confidence_threshold=0.3,
            force_mock=False
        )
    return _tool_detector


_sam2_auto_generator = None

def get_sam2_auto_generator():
    """Get or initialize SAM2 Auto Mask Generator"""
    global _sam2_auto_generator
    if _sam2_auto_generator is None:
        from app.ai_engine.processors.sam2_auto_mask_generator import SAM2AutoMaskGenerator
        _sam2_auto_generator = SAM2AutoMaskGenerator(min_mask_area=500)
    return _sam2_auto_generator


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


# === Endpoints ===

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

    try:
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=400, detail=f"Failed to extract frame {frame_number}")

        logger.info(f"Frame shape (original): {frame.shape}")

        tracker = get_sam_tracker()
        tracker.set_image(frame)

        if prompt_type == "point":
            if labels is None:
                labels = [1] * len(coordinates)

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

        mask = result["mask"]
        mask_uint8 = (mask * 255).astype(np.uint8)
        _, mask_encoded = cv2.imencode('.png', mask_uint8)
        mask_base64 = base64.b64encode(mask_encoded.tobytes()).decode('utf-8')

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

    instruments = body.get("instruments", [])
    instruments_file = Path(settings.UPLOAD_DIR) / f"{video_id}_instruments.json"

    try:
        instruments_data = []
        for inst in instruments:
            instruments_data.append({
                "name": inst["name"],
                "bbox": inst["bbox"],
                "frame_number": inst.get("frame_number", 0),
                "mask": inst.get("mask", "")
            })

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
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=400, detail=f"Failed to extract frame {frame_number}")

        logger.info(f"[DETECT] Frame extracted: {frame.shape}")

        detector = get_tool_detector()
        detection_result = detector.detect_from_frame(frame)

        logger.info(f"[DETECT] Detected {len(detection_result['instruments'])} instruments")

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
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=400, detail=f"Failed to extract frame {frame_number}")

        tracker = get_sam_tracker()
        tracker.set_image(frame)

        x1, y1, x2, y2 = bbox
        result = tracker.segment_with_box(
            box=(int(x1), int(y1), int(x2), int(y2))
        )

        mask = result["mask"]
        mask_uint8 = (mask * 255).astype(np.uint8)
        _, mask_encoded = cv2.imencode('.png', mask_uint8)
        mask_base64 = base64.b64encode(mask_encoded.tobytes()).decode('utf-8')

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
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=400, detail=f"Failed to extract frame {frame_number}")

        logger.info(f"[DETECT-SAM2] Frame extracted: {frame.shape}")

        generator = get_sam2_auto_generator()
        masks = generator.generate_masks(frame)
        masks = generator.filter_by_confidence(masks, min_confidence)
        masks = generator.merge_overlapping_masks(masks, iou_threshold=0.5)
        masks = masks[:max_results]

        logger.info(f"[DETECT-SAM2] Generated {len(masks)} masks")

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
                "mask_base64": None
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
