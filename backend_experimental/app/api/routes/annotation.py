"""アノテーションAPI"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import json
import uuid
from datetime import datetime

from app.models import get_db
from app.models.video import Video
from app.schemas.common import SuccessResponse, ErrorResponse
from app.core.config import settings
from app.ai_engine.processors.frame_extractor import FrameExtractor
from pydantic import BaseModel

router = APIRouter()


class BoundingBox(BaseModel):
    """バウンディングボックス"""
    x: float
    y: float
    width: float
    height: float
    label: str


class FrameAnnotation(BaseModel):
    """フレームアノテーション"""
    frame_number: int
    annotations: List[BoundingBox]


class AnnotationSaveRequest(BaseModel):
    """アノテーション保存リクエスト"""
    video_id: str
    annotations: List[FrameAnnotation]


class AnnotationResponse(BaseModel):
    """アノテーションレスポンス"""
    id: str
    video_id: str
    created_at: datetime
    frame_count: int
    total_annotations: int


@router.post(
    "/save",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save annotations",
    responses={
        404: {"description": "Video not found", "model": ErrorResponse},
        500: {"description": "Failed to save annotations", "model": ErrorResponse},
    },
)
async def save_annotations(
    request: AnnotationSaveRequest,
    db: Session = Depends(get_db)
):
    """アノテーションを保存"""

    # 動画の存在確認
    video = db.query(Video).filter(Video.id == request.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # アノテーションディレクトリの作成
    annotation_dir = Path(settings.DATA_DIR) / "annotations"
    annotation_dir.mkdir(parents=True, exist_ok=True)

    # アノテーションIDの生成
    annotation_id = str(uuid.uuid4())

    # アノテーションデータの準備
    annotation_data = {
        "id": annotation_id,
        "video_id": request.video_id,
        "video_file": video.filename,
        "created_at": datetime.now().isoformat(),
        "frames": []
    }

    total_annotations = 0

    # フレームごとのアノテーション処理
    for frame_anno in request.annotations:
        frame_data = {
            "frame_number": frame_anno.frame_number,
            "annotations": []
        }

        for box in frame_anno.annotations:
            frame_data["annotations"].append({
                "x": box.x,
                "y": box.y,
                "width": box.width,
                "height": box.height,
                "label": box.label
            })
            total_annotations += 1

        annotation_data["frames"].append(frame_data)

    # JSONファイルとして保存
    annotation_file = annotation_dir / f"{annotation_id}.json"
    try:
        with open(annotation_file, "w", encoding="utf-8") as f:
            json.dump(annotation_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save annotation file: {str(e)}"
        )

    return AnnotationResponse(
        id=annotation_id,
        video_id=request.video_id,
        created_at=datetime.now(),
        frame_count=len(request.annotations),
        total_annotations=total_annotations
    )


@router.get(
    "/{video_id}",
    response_model=dict,
    summary="Get annotations for video",
    responses={
        404: {"description": "Annotations not found", "model": ErrorResponse},
    },
)
async def get_annotations(
    video_id: str,
    db: Session = Depends(get_db)
):
    """動画のアノテーションを取得"""

    # 動画の存在確認
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # アノテーションファイルを探す
    annotation_dir = Path(settings.DATA_DIR) / "annotations"

    # 該当する動画のアノテーションを検索
    annotations = []
    if annotation_dir.exists():
        for annotation_file in annotation_dir.glob("*.json"):
            try:
                with open(annotation_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("video_id") == video_id:
                        annotations.append(data)
            except Exception:
                continue

    if not annotations:
        return {"video_id": video_id, "annotations": []}

    # 最新のアノテーションを返す
    latest_annotation = max(annotations, key=lambda x: x.get("created_at", ""))
    return latest_annotation


@router.get(
    "/{video_id}/frames",
    response_model=dict,
    summary="Get video frames for annotation",
    responses={
        404: {"description": "Video not found", "model": ErrorResponse},
    },
)
async def get_frames(
    video_id: str,
    fps: int = 5,
    max_frames: Optional[int] = 100,
    db: Session = Depends(get_db)
):
    """アノテーション用のフレームを取得"""

    # 動画の存在確認
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(video.file_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    # フレーム抽出
    try:
        with FrameExtractor(str(video_path), target_fps=fps) as extractor:
            video_info = extractor.get_info()

            # フレーム保存ディレクトリ
            frames_dir = Path(settings.DATA_DIR) / "frames" / video_id
            frames_dir.mkdir(parents=True, exist_ok=True)

            frame_urls = []
            frame_count = 0

            for frame_num, frame in extractor.extract_frames_generator():
                if max_frames and frame_count >= max_frames:
                    break

                # フレームを保存
                import cv2
                frame_file = frames_dir / f"frame_{frame_num:06d}.jpg"
                cv2.imwrite(str(frame_file), frame)

                # URLを生成（実際のAPIエンドポイントに合わせて調整）
                frame_urls.append({
                    "frame_number": frame_num,
                    "url": f"/api/v1/frames/{video_id}/{frame_num}"
                })

                frame_count += 1

            return {
                "video_id": video_id,
                "video_info": {
                    "width": video_info.width,
                    "height": video_info.height,
                    "fps": video_info.fps,
                    "duration": video_info.duration,
                    "total_frames": video_info.total_frames
                },
                "frames": frame_urls,
                "extracted_count": frame_count
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract frames: {str(e)}"
        )


@router.delete(
    "/{annotation_id}",
    response_model=SuccessResponse,
    summary="Delete annotation",
    responses={
        404: {"description": "Annotation not found", "model": ErrorResponse},
    },
)
async def delete_annotation(annotation_id: str):
    """アノテーションを削除"""

    annotation_file = Path(settings.DATA_DIR) / "annotations" / f"{annotation_id}.json"

    if not annotation_file.exists():
        raise HTTPException(status_code=404, detail="Annotation not found")

    try:
        annotation_file.unlink()
        return SuccessResponse(
            message="Annotation deleted successfully",
            data={"id": annotation_id}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete annotation: {str(e)}"
        )