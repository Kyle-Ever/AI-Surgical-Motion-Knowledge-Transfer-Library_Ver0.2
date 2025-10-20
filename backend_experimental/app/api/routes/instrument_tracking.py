"""器具追跡APIエンドポイント"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging

from app.models import get_db
from app.core.websocket import manager
from app.services.instrument_tracking_service import InstrumentTrackingService
from app.models.video import Video
from app.models.analysis import AnalysisResult

logger = logging.getLogger(__name__)
router = APIRouter()

# サービスインスタンス
tracking_service = InstrumentTrackingService()


class InstrumentSelection(BaseModel):
    """器具選択情報"""
    id: Optional[str] = None
    name: Optional[str] = None
    type: str  # 'rectangle', 'polygon', 'mask'
    data: dict  # 選択データ
    color: Optional[List[int]] = None


class TrackingInitRequest(BaseModel):
    """追跡初期化リクエスト"""
    video_id: int
    selections: List[InstrumentSelection]


class TrackingInitResponse(BaseModel):
    """追跡初期化レスポンス"""
    success: bool
    tracking_id: Optional[str] = None
    instruments_count: Optional[int] = None
    total_frames: Optional[int] = None
    error: Optional[str] = None


class TrackingFrameRequest(BaseModel):
    """フレーム追跡リクエスト"""
    tracking_id: str
    frame_number: Optional[int] = None


class TrackingProcessRequest(BaseModel):
    """ビデオ処理リクエスト"""
    tracking_id: str
    output_video: bool = True
    analysis_id: Optional[int] = None


@router.post("/initialize", response_model=TrackingInitResponse)
async def initialize_tracking(
    request: TrackingInitRequest,
    db: Session = Depends(get_db)
):
    """器具追跡の初期化

    ユーザーが選択した器具領域から特徴点を抽出し、追跡を初期化
    """
    try:
        # ビデオ取得
        video = db.query(Video).filter(Video.id == request.video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # 追跡初期化
        result = await tracking_service.initialize_tracking(
            video_path=video.file_path,
            selections=[sel.dict() for sel in request.selections]
        )

        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error'))

        return TrackingInitResponse(**result)

    except Exception as e:
        logger.error(f"Tracking initialization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/track-frame")
async def track_frame(
    request: TrackingFrameRequest
):
    """特定フレームで追跡

    指定されたフレームで器具を追跡
    """
    try:
        result = await tracking_service.track_frame(
            tracking_id=request.tracking_id,
            frame_number=request.frame_number
        )

        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error'))

        return result

    except Exception as e:
        logger.error(f"Frame tracking failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-video")
async def process_video(
    request: TrackingProcessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """ビデオ全体を処理

    バックグラウンドで器具追跡を実行
    """
    try:
        # 分析レコード取得（オプション）
        analysis = None
        if request.analysis_id:
            analysis = db.query(AnalysisResult).filter(AnalysisResult.id == request.analysis_id).first()

        # バックグラウンドタスクとして実行
        background_tasks.add_task(
            process_video_background,
            request.tracking_id,
            request.output_video,
            analysis.id if analysis else None
        )

        return {
            "message": "Processing started",
            "tracking_id": request.tracking_id
        }

    except Exception as e:
        logger.error(f"Video processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_video_background(
    tracking_id: str,
    output_video: bool,
    analysis_id: Optional[int]
):
    """バックグラウンドでビデオ処理"""
    try:
        # 出力パス設定
        output_path = None
        if output_video:
            from pathlib import Path
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(Path(f"data/results/instrument_tracking_{timestamp}.mp4"))

        # 進捗コールバック
        async def progress_callback(data):
            if analysis_id:
                await manager.send_update(analysis_id, {
                    "type": "instrument_tracking",
                    "progress": data['progress'],
                    "frame": data['frame'],
                    "total": data['total'],
                    "active_instruments": data.get('active_instruments', 0)
                })

        # 処理実行
        result = await tracking_service.process_video(
            tracking_id=tracking_id,
            output_path=output_path,
            progress_callback=progress_callback
        )

        # 完了通知
        if analysis_id:
            await manager.send_update(analysis_id, {
                "type": "instrument_tracking_complete",
                "success": result['success'],
                "success_rate": result.get('success_rate'),
                "output_path": result.get('output_path')
            })

    except Exception as e:
        logger.error(f"Background processing failed: {str(e)}")
        if analysis_id:
            await manager.send_update(analysis_id, {
                "type": "instrument_tracking_error",
                "error": str(e)
            })
    finally:
        # クリーンアップ
        tracking_service.cleanup(tracking_id)


@router.get("/tracking/{tracking_id}/status")
async def get_tracking_status(tracking_id: str):
    """追跡ステータス取得"""
    if tracking_id not in tracking_service.tracking_states:
        raise HTTPException(status_code=404, detail="Tracking not found")

    state = tracking_service.tracking_states[tracking_id]

    # アクティブな器具数をカウント
    active_instruments = sum(
        1 for inst in state['instruments'] if not inst['lost']
    )

    return {
        "tracking_id": tracking_id,
        "frame_count": state['frame_count'],
        "total_frames": state['total_frames'],
        "instruments_count": len(state['instruments']),
        "active_instruments": active_instruments,
        "progress": (state['frame_count'] / state['total_frames'] * 100) if state['total_frames'] > 0 else 0
    }


@router.delete("/tracking/{tracking_id}")
async def cleanup_tracking(tracking_id: str):
    """追跡セッションのクリーンアップ"""
    tracking_service.cleanup(tracking_id)
    return {"message": "Tracking session cleaned up"}