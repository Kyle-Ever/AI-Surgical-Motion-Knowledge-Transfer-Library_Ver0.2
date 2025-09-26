from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
import uuid

from app.models import get_db
from app.models.analysis import AnalysisResult, AnalysisStatus
from app.models.video import Video
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisResponse,
    AnalysisStatusResponse,
    AnalysisResultResponse,
    ProcessingStep
)
from app.services.analysis_service import AnalysisService
from app.schemas.common import ErrorResponse

router = APIRouter()

# Processing tasks management (simple version)
processing_tasks: Dict[str, Any] = {}

@router.post(
    "/{video_id}/analyze",
    response_model=AnalysisResponse,
    summary="Start analysis",
    responses={
        400: {"description": "Analysis already in progress or invalid input", "model": ErrorResponse},
        404: {"description": "Video not found", "model": ErrorResponse},
    },
)
async def start_analysis(
    video_id: str,
    analysis_params: AnalysisCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start video analysis"""

    # Check if video exists
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check if analysis is already in progress
    existing = db.query(AnalysisResult).filter(
        AnalysisResult.video_id == video_id,
        AnalysisResult.status.in_([AnalysisStatus.PENDING, AnalysisStatus.PROCESSING])
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Analysis already in progress")

    # Create analysis result record
    analysis_id = str(uuid.uuid4())
    analysis_result = AnalysisResult(
        id=analysis_id,
        video_id=video_id,
        status=AnalysisStatus.PENDING
    )

    db.add(analysis_result)
    db.commit()
    db.refresh(analysis_result)

    # Start analysis in background
    # In production, use Celery or RQ for task queue
    background_tasks.add_task(
        process_video_analysis,
        analysis_id,
        video,
        analysis_params.instruments,
        analysis_params.sampling_rate
    )

    return analysis_result

@router.get(
    "/{analysis_id}/status",
    response_model=AnalysisStatusResponse,
    summary="Get analysis status",
    responses={404: {"description": "Analysis not found", "model": ErrorResponse}},
)
async def get_analysis_status(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """Get analysis progress status"""

    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Generate mock step information
    steps = []

    if analysis.status == AnalysisStatus.COMPLETED:
        steps = [
            ProcessingStep(name="Video loading", status="completed", progress=100),
            ProcessingStep(name="Skeleton detection", status="completed", progress=100),
            ProcessingStep(name="Instrument tracking", status="completed", progress=100),
            ProcessingStep(name="Data generation", status="completed", progress=100),
        ]
    elif analysis.status == AnalysisStatus.PROCESSING:
        progress = analysis.progress or 0
        if progress < 25:
            steps = [
                ProcessingStep(name="Video loading", status="processing", progress=progress*4),
                ProcessingStep(name="Skeleton detection", status="pending"),
                ProcessingStep(name="Instrument tracking", status="pending"),
                ProcessingStep(name="Data generation", status="pending"),
            ]
        elif progress < 50:
            steps = [
                ProcessingStep(name="Video loading", status="completed", progress=100),
                ProcessingStep(name="Skeleton detection", status="processing", progress=(progress-25)*4),
                ProcessingStep(name="Instrument tracking", status="pending"),
                ProcessingStep(name="Data generation", status="pending"),
            ]
        elif progress < 75:
            steps = [
                ProcessingStep(name="Video loading", status="completed", progress=100),
                ProcessingStep(name="Skeleton detection", status="completed", progress=100),
                ProcessingStep(name="Instrument tracking", status="processing", progress=(progress-50)*4),
                ProcessingStep(name="Data generation", status="pending"),
            ]
        else:
            steps = [
                ProcessingStep(name="Video loading", status="completed", progress=100),
                ProcessingStep(name="Skeleton detection", status="completed", progress=100),
                ProcessingStep(name="Instrument tracking", status="completed", progress=100),
                ProcessingStep(name="Data generation", status="processing", progress=(progress-75)*4),
            ]
    else:
        steps = [
            ProcessingStep(name="Video loading", status="pending"),
            ProcessingStep(name="Skeleton detection", status="pending"),
            ProcessingStep(name="Instrument tracking", status="pending"),
            ProcessingStep(name="Data generation", status="pending"),
        ]

    # --- start unified mapping ---
    try:
        video = db.query(Video).filter(Video.id == analysis.video_id).first()
        video_type = video.video_type if video else 'external'
        LABELS = {
            'preprocessing': 'Preprocessing',
            'video_info': 'Video info',
            'frame_extraction': 'Frame extraction',
            'skeleton_detection': 'Skeleton detection',
            'instrument_detection': 'Instrument tracking',
            'motion_analysis': 'Motion analysis',
            'score_calculation': 'Score calculation',
            'data_saving': 'Data saving',
            'completed': 'Completed',
        }
        steps_order = ['preprocessing', 'video_info', 'frame_extraction']
        steps_order.append('skeleton_detection' if str(video_type) == 'external' else 'instrument_detection')
        steps_order += ['motion_analysis', 'score_calculation', 'data_saving']
        p = analysis.progress or 0
        thresholds = [5,10,30,50,70,85,95]
        idx_cur = 0
        for i, b in enumerate(thresholds):
            if p >= b:
                idx_cur = min(i, len(steps_order)-1)
        steps = []
        for i, key in enumerate(steps_order):
            if analysis.status == AnalysisStatus.COMPLETED:
                steps.append(ProcessingStep(name=LABELS[key], status='completed', progress=100))
            elif analysis.status == AnalysisStatus.PROCESSING:
                if i < idx_cur:
                    steps.append(ProcessingStep(name=LABELS[key], status='completed', progress=100))
                elif i == idx_cur:
                    start = thresholds[i] if i < len(thresholds) else 95
                    end = thresholds[i+1] if i+1 < len(thresholds) else 100
                    local = 0 if end == start else int(max(0, min(100, (p - start) * 100 / max(1, end - start))))
                    steps.append(ProcessingStep(name=LABELS[key], status='processing', progress=local))
                else:
                    steps.append(ProcessingStep(name=LABELS[key], status='pending'))
            else:
                steps.append(ProcessingStep(name=LABELS[key], status='pending'))
    except Exception:
        pass
    # --- end unified mapping ---
    return AnalysisStatusResponse(
        analysis_id=analysis.id,
        video_id=analysis.video_id,
        overall_progress=analysis.progress or 0,
        steps=steps,
        estimated_time_remaining=max(0, 300 - (analysis.progress or 0) * 3) if analysis.status == AnalysisStatus.PROCESSING else None
    )

@router.get(
    "/{analysis_id}",
    response_model=AnalysisResultResponse,
    summary="Get analysis result",
    responses={404: {"description": "Analysis not found", "model": ErrorResponse}},
)
async def get_analysis_result(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """Get analysis result"""

    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return analysis

# Background task
async def process_video_analysis(
    analysis_id: str,
    video: Video,
    instruments: list,
    sampling_rate: int
):
    """Process video analysis task"""
    from app.models import SessionLocal
    import asyncio
    from pathlib import Path

    db = SessionLocal()
    analysis_service = AnalysisService()

    try:
        analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
        if not analysis:
            return

        # Update status to processing
        analysis.status = AnalysisStatus.PROCESSING
        analysis.current_step = "Loading video"
        db.commit()

        # Run actual analysis
        video_path = Path(video.file_path)
        if video_path.exists():
            result = await analysis_service.process_video(
                video_id=video.id,
                video_path=str(video_path),
                video_type=video.video_type,
                analysis_id=analysis_id
            )

            # Update results from analysis
            analysis.status = AnalysisStatus.COMPLETED
            analysis.progress = 100

            # Calculate statistics from scores
            if result.get("scores"):
                analysis.avg_velocity = result["scores"].get("speed", 0)
                analysis.max_velocity = result["scores"].get("speed", 0) * 1.5
                analysis.total_distance = result["frame_count"] * 10  # Temporary calculation

            analysis.total_frames = result.get("frame_count", 0)
            from datetime import datetime
            analysis.completed_at = datetime.now()

        else:
            # File not found - use mock processing
            import random

            # Simulate progress
            for progress in range(0, 101, 5):
                await asyncio.sleep(1)
                analysis.progress = progress

                if progress < 25:
                    analysis.current_step = "Loading video"
                elif progress < 50:
                    analysis.current_step = "Skeleton detection"
                elif progress < 75:
                    analysis.current_step = "Instrument tracking"
                else:
                    analysis.current_step = "Data generation"

                db.commit()

            # Mock data
            analysis.status = AnalysisStatus.COMPLETED
            analysis.avg_velocity = random.uniform(10, 20)
            analysis.max_velocity = random.uniform(30, 50)
            analysis.total_distance = random.uniform(1000, 2000)
            analysis.total_frames = random.randint(2000, 4000)
            from datetime import datetime
            analysis.completed_at = datetime.now()

            # Mock coordinate data
            analysis.coordinate_data = {
                "frames": [
                    {
                        "frame_number": i,
                        "timestamp": i * 0.2,
                        "left_hand": {"x": random.random(), "y": random.random()},
                        "right_hand": {"x": random.random(), "y": random.random()}
                    }
                    for i in range(10)
                ]
            }

            # Mock velocity data
            analysis.velocity_data = {
                "average": random.uniform(10, 20),
                "max": random.uniform(30, 50),
                "data": [random.uniform(5, 25) for _ in range(10)]
            }

            # Mock angle data
            analysis.angle_data = {
                "frames": [
                    {
                        "frame_number": i,
                        "angles": {
                            "thumb": random.uniform(0, 180),
                            "index": random.uniform(0, 180),
                            "middle": random.uniform(0, 180),
                            "ring": random.uniform(0, 180),
                            "pinky": random.uniform(0, 180)
                        }
                    }
                    for i in range(10)
                ]
            }

        db.commit()

    except Exception as e:
        analysis.status = AnalysisStatus.FAILED
        db.commit()
        raise
    finally:
        db.close()

@router.get(
    "/completed",
    response_model=list[AnalysisResultResponse],
    summary="Get completed analyses",
)
async def get_completed_analyses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get list of completed analyses"""

    analyses = db.query(AnalysisResult).filter(
        AnalysisResult.status == AnalysisStatus.COMPLETED
    ).offset(skip).limit(limit).all()

    return analyses