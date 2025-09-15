from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
from pathlib import Path
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
        video_id,  # Pass video_id instead of video object
        analysis_params.instruments,
        analysis_params.sampling_rate
    )

    return analysis_result

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
    """Get list of completed analyses with video information"""

    import logging
    logger = logging.getLogger(__name__)
    logger.info("[DEBUG] get_completed_analyses endpoint called")

    analyses = db.query(AnalysisResult).filter(
        AnalysisResult.status == AnalysisStatus.COMPLETED
    ).offset(skip).limit(limit).all()

    logger.info(f"[DEBUG] Found {len(analyses)} completed analyses")

    # Add video information to each analysis
    result = []
    for analysis in analyses:
        # Get associated video
        video = db.query(Video).filter(Video.id == analysis.video_id).first()

        # Convert to dict and add video info
        analysis_dict = {
            "id": analysis.id,
            "video_id": analysis.video_id,
            "status": analysis.status,
            "skeleton_data": analysis.skeleton_data,
            "instrument_data": analysis.instrument_data,
            "motion_analysis": analysis.motion_analysis,
            "scores": analysis.scores,
            "avg_velocity": analysis.avg_velocity,
            "max_velocity": analysis.max_velocity,
            "total_distance": analysis.total_distance,
            "total_frames": analysis.total_frames,
            "created_at": analysis.created_at,
            "completed_at": analysis.completed_at,
            "video": {
                "id": video.id,
                "filename": video.filename,
                "original_filename": video.original_filename,
                "surgery_name": video.surgery_name,
                "surgeon_name": video.surgeon_name,
                "surgery_date": video.surgery_date,
                "video_type": video.video_type,
                "duration": video.duration,
                "created_at": video.created_at
            } if video else None
        }
        result.append(analysis_dict)

    return result


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

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[DEBUG] get_analysis_result called with id: {analysis_id}")

    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        logger.warning(f"[DEBUG] Analysis not found for id: {analysis_id}")
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Get video type from video
    video = db.query(Video).filter(Video.id == analysis.video_id).first()

    try:
        # Create response manually to avoid from_orm issues
        result_dict = {
            "id": analysis.id,
            "video_id": analysis.video_id,
            "video_type": video.video_type.value if video and video.video_type else None,
            "status": analysis.status,
            "skeleton_data": analysis.skeleton_data,
            "instrument_data": analysis.instrument_data,
            "motion_analysis": analysis.motion_analysis,
            "coordinate_data": analysis.coordinate_data,
            "velocity_data": analysis.velocity_data,
            "angle_data": analysis.angle_data,
            "scores": analysis.scores,
            "avg_velocity": analysis.avg_velocity,
            "max_velocity": analysis.max_velocity,
            "total_distance": analysis.total_distance,
            "total_frames": analysis.total_frames,
            "created_at": analysis.created_at,
            "completed_at": analysis.completed_at,
            "video": None
        }

        result = AnalysisResultResponse(**result_dict)
        return result
    except Exception as e:
        logger.error(f"Error creating response for analysis {analysis_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating response: {str(e)}")

# Background task
async def process_video_analysis(
    analysis_id: str,
    video_id: str,
    instruments: list,
    sampling_rate: int
):
    """Process video analysis task"""
    from app.models import SessionLocal
    import asyncio
    from pathlib import Path
    import logging

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    analysis_service = AnalysisService()

    try:
        analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
        if not analysis:
            return

        # Get video from database
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return

        # Update status to processing
        analysis.status = AnalysisStatus.PROCESSING
        analysis.current_step = "Loading video"
        db.commit()

        # Check if we should use real processing or mock
        use_real_processing = False
        video_path = Path(video.file_path) if video.file_path else None

        # Debug: Log the actual path being checked
        logger.info(f"[DEBUG] Video file_path from DB: {video.file_path}")
        logger.info(f"[DEBUG] Resolved video_path: {video_path}")
        logger.info(f"[DEBUG] Path exists: {video_path.exists() if video_path else False}")

        if video_path and video_path.exists():
            logger.info(f"[MediaPipe] Video file found: {video_path}")
            logger.info(f"[MediaPipe] File size: {video_path.stat().st_size / (1024*1024):.2f} MB")

            # Try to use real MediaPipe processing
            try:
                logger.info(f"[MediaPipe] Starting real video processing...")
                # Run MediaPipe processing in executor to avoid blocking
                import asyncio
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    process_with_mediapipe,
                    analysis, video, video_path, instruments, sampling_rate, db
                )
                logger.info(f"[MediaPipe] Real processing completed successfully")
                return  # Exit after successful processing
            except Exception as e:
                import traceback
                logger.error(f"[MediaPipe] Real processing failed: {e}")
                logger.error(f"[MediaPipe] Traceback:\n{traceback.format_exc()}")
                logger.warning(f"[MediaPipe] Falling back to mock processing")
                use_real_processing = False
        else:
            logger.warning(f"[MediaPipe] Video file not found or path is None: {video_path}")
            if video_path:
                logger.warning(f"[MediaPipe] Expected location: {video_path.absolute()}")

        # Fallback to mock processing
        logger.info("[MOCK] Using mock processing")
        await process_with_mock(analysis, instruments, db, video.video_type if video else None)

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = str(e)
        db.commit()
        raise
    finally:
        db.close()


def process_with_mediapipe(
    analysis: AnalysisResult,
    video: Video,
    video_path: Path,
    instruments: list,
    sampling_rate: int,
    db
):
    """Process video with real MediaPipe"""
    import cv2
    from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Initialize processors with settings matching the reference code
        # For external cameras, we need to flip handedness (mirror effect)
        flip_handedness = (video.video_type == 'external')
        # Use same settings as reference code that works with both hands
        skeleton_detector = HandSkeletonDetector(
            static_image_mode=False,         # Use tracking mode like reference
            max_num_hands=2,                # Detect both hands
            min_detection_confidence=0.5,   # Same as reference code
            min_tracking_confidence=0.5,    # Same as reference code
            flip_handedness=flip_handedness # Flip for external cameras
        )
        logger.info(f"[MediaPipe] HandSkeletonDetector initialized with static_mode=False, max_hands=2, confidence=0.5, flip={flip_handedness}")
        # Note: FrameExtractor is not needed here, we use cv2 directly

        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        # Use lower interval for smoother tracking (process more frames)
        # For 30fps video with sampling_rate=5, we want 5 samples per second
        # So interval = fps/sampling_rate = 30/5 = 6 frames
        # But for better tracking, let's process more frames
        frame_interval = max(1, int(fps / (sampling_rate * 2)))  # Double the sampling for smoother tracking

        skeleton_data = []
        instrument_data = []
        frame_count = 0
        processed_frames = 0

        expected_samples = total_frames // frame_interval
        logger.info(f"[MediaPipe] Processing {total_frames} frames at {fps:.2f} fps")
        logger.info(f"[MediaPipe] Sampling every {frame_interval} frames (approx {fps/frame_interval:.1f} samples/sec)")
        logger.info(f"[MediaPipe] Expected samples: {expected_samples}")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Process only sampled frames
            if frame_count % frame_interval == 0:
                timestamp = frame_count / fps

                # Detect hand skeleton
                detection_result = skeleton_detector.detect_from_frame(frame)

                if processed_frames % 10 == 0:  # Log every 10th processed frame
                    logger.info(f"[MediaPipe] Frame {frame_count}: Detected {len(detection_result.get('hands', []))} hands")

                if detection_result["hands"]:
                    for hand_idx, hand in enumerate(detection_result["hands"]):
                        # Convert to our format (normalize coordinates to 0-1 range)
                        landmarks = {}
                        frame_height, frame_width = frame.shape[:2]
                        for i, landmark in enumerate(hand["landmarks"]):
                            # Convert from pixel coordinates to normalized coordinates
                            landmarks[f"point_{i}"] = {
                                "x": landmark["x"] / frame_width,  # Normalize to 0-1
                                "y": landmark["y"] / frame_height,  # Normalize to 0-1
                                "z": landmark.get("z", 0)
                            }

                        skeleton_data.append({
                            "frame_number": frame_count,
                            "timestamp": timestamp,
                            "hand_type": hand.get("handedness", hand.get("label", "Unknown")),
                            "landmarks": landmarks
                        })

                # Simple instrument detection (only for internal camera with registered instruments)
                if instruments and video.video_type == 'internal':
                    # For now, create mock instrument data when instruments are registered
                    # Real YOLO detection would go here
                    instrument_data.append({
                        "frame_number": frame_count,
                        "timestamp": timestamp,
                        "detections": [
                            {
                                "bbox": [100, 100, 200, 200],  # Mock bbox
                                "confidence": 0.9,
                                "class_name": instruments[0].get("name", "Forceps") if instruments else "Unknown",
                                "track_id": 0
                            }
                        ] if instruments else []
                    })

                processed_frames += 1

                # Update progress
                progress = int((frame_count / total_frames) * 100)
                analysis.progress = progress
                analysis.current_step = f"Processing frame {frame_count}/{total_frames}"
                db.commit()

            frame_count += 1

        cap.release()

        # Save results
        logger.info(f"[MediaPipe] Processing complete!")
        logger.info(f"[MediaPipe] Processed frames: {processed_frames}")
        logger.info(f"[MediaPipe] Total hand detections: {len(skeleton_data)}")
        detection_rate = len(skeleton_data) / max(processed_frames, 1) * 100
        logger.info(f"[MediaPipe] Detection rate: {detection_rate:.1f}%")

        # Log summary of hand types detected
        if skeleton_data:
            hand_types = {}
            for data in skeleton_data:
                hand_type = data.get("hand_type", "Unknown")
                hand_types[hand_type] = hand_types.get(hand_type, 0) + 1
            logger.info(f"[MediaPipe] Hand types detected: {hand_types}")

        analysis.skeleton_data = skeleton_data
        analysis.instrument_data = instrument_data if instruments else None
        analysis.total_frames = total_frames
        analysis.status = AnalysisStatus.COMPLETED
        analysis.progress = 100

        from datetime import datetime
        analysis.completed_at = datetime.now()
        db.commit()

    except Exception as e:
        import traceback
        logger.error(f"[MediaPipe] Processing failed: {e}")
        logger.error(f"[MediaPipe] Traceback: {traceback.format_exc()}")
        raise


async def process_with_mock(
    analysis: AnalysisResult,
    instruments: list,
    db,
    video_type: str = None
):
    """Fallback mock processing"""
    import asyncio
    import random
    import math
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"[MOCK] Starting mock processing for video_type: {video_type}")

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

    # Mock skeleton_data (MediaPipe hand landmarks format)
    # Generate 100 frames of hand skeleton data
    analysis.skeleton_data = []
    for i in range(100):
        landmarks = {}
        # Generate 21 hand landmarks (MediaPipe hand model)
        # Center position for the hand (moves in a circular pattern)
        center_x = 0.5 + 0.2 * math.sin(i * 0.05)
        center_y = 0.5 + 0.2 * math.cos(i * 0.05)

        # Define relative positions for hand landmarks (simplified hand structure)
        hand_structure = [
            (0, 0),      # 0: Wrist
            (-0.02, -0.04), # 1: Thumb CMC
            (-0.03, -0.08), # 2: Thumb MCP
            (-0.04, -0.12), # 3: Thumb IP
            (-0.05, -0.15), # 4: Thumb Tip
            (0, -0.05),   # 5: Index MCP
            (0, -0.10),   # 6: Index PIP
            (0, -0.14),   # 7: Index DIP
            (0, -0.17),   # 8: Index Tip
            (0.02, -0.05),  # 9: Middle MCP
            (0.02, -0.10),  # 10: Middle PIP
            (0.02, -0.14),  # 11: Middle DIP
            (0.02, -0.17),  # 12: Middle Tip
            (0.04, -0.05),  # 13: Ring MCP
            (0.04, -0.10),  # 14: Ring PIP
            (0.04, -0.14),  # 15: Ring DIP
            (0.04, -0.17),  # 16: Ring Tip
            (0.06, -0.05),  # 17: Pinky MCP
            (0.06, -0.09),  # 18: Pinky PIP
            (0.06, -0.13),  # 19: Pinky DIP
            (0.06, -0.16),  # 20: Pinky Tip
        ]

        for j, (offset_x, offset_y) in enumerate(hand_structure):
            landmarks[f"point_{j}"] = {
                "x": max(0.1, min(0.9, center_x + offset_x + random.uniform(-0.005, 0.005))),
                "y": max(0.1, min(0.9, center_y + offset_y + random.uniform(-0.005, 0.005))),
                "z": random.uniform(-0.05, 0.05)
            }

        analysis.skeleton_data.append({
            "frame_number": i,
            "timestamp": i * 0.033,  # ~30fps
            "landmarks": landmarks
        })

    # Mock instrument_data (YOLO-style detection format)
    # Only generate if instruments are registered AND video_type is internal
    if instruments and video_type == 'internal':
        logger.info(f"[MOCK] Generating instrument data for {len(instruments)} instruments")
        analysis.instrument_data = []
        # Use registered instrument names
        instrument_names = [inst.get("name", "Unknown") for inst in instruments] if instruments else []
        if not instrument_names:
            instrument_names = ["Forceps", "Scissors", "Needle Holder"]

        for i in range(100):
            detections = []

            # Simulate 1-2 instruments detected
            num_instruments = min(len(instrument_names), random.randint(1, 2))
            for inst_id in range(num_instruments):
                # Create moving bounding box
                center_x = 0.4 + 0.2 * math.sin(i * 0.05 + inst_id * math.pi)
                center_y = 0.5 + 0.1 * math.cos(i * 0.05 + inst_id * math.pi)
                width = 0.1 + random.uniform(-0.02, 0.02)
                height = 0.15 + random.uniform(-0.02, 0.02)

                detections.append({
                    "bbox": [
                        max(0, (center_x - width/2) * 640),  # x1
                        max(0, (center_y - height/2) * 480),  # y1
                        min(640, (center_x + width/2) * 640),  # x2
                        min(480, (center_y + height/2) * 480)   # y2
                    ],
                    "confidence": 0.85 + random.uniform(-0.1, 0.1),
                    "class_name": instrument_names[inst_id % len(instrument_names)],
                    "track_id": inst_id
                })

            analysis.instrument_data.append({
                "frame_number": i,
                "timestamp": i * 0.033,  # ~30fps
                "detections": detections
            })
    else:
        # No instruments registered or external camera, no detection data
        logger.info(f"[MOCK] No instrument data (video_type={video_type}, instruments={len(instruments) if instruments else 0})")
        analysis.instrument_data = None

    # Mock coordinate data (for backward compatibility)
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


@router.get(
    "/{analysis_id}/export",
    summary="Export analysis data as CSV",
    responses={
        404: {"description": "Analysis not found", "model": ErrorResponse},
        200: {"description": "CSV file", "content": {"text/csv": {}}}
    }
)
async def export_analysis(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """Export analysis data as CSV"""
    from fastapi.responses import Response
    import csv
    import io

    # Find the analysis
    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Get associated video
    video = db.query(Video).filter(Video.id == analysis.video_id).first()

    # Create CSV data
    output = io.StringIO()
    writer = csv.writer(output)

    # Write headers and basic info
    writer.writerow(["Analysis Export"])
    writer.writerow(["Analysis ID", analysis.id])
    writer.writerow(["Video ID", analysis.video_id])
    writer.writerow(["Video Name", video.original_filename if video else "Unknown"])
    writer.writerow(["Surgery Name", video.surgery_name if video else ""])
    writer.writerow(["Surgeon Name", video.surgeon_name if video else ""])
    writer.writerow(["Status", analysis.status])
    writer.writerow(["Created At", analysis.created_at])
    writer.writerow(["Completed At", analysis.completed_at])
    writer.writerow([])

    # Write metrics if available
    if analysis.motion_analysis and analysis.motion_analysis.get("metrics"):
        metrics = analysis.motion_analysis["metrics"]
        writer.writerow(["Metrics"])
        if metrics.get("summary"):
            summary = metrics["summary"]
            writer.writerow(["Average Velocity (Left)", summary.get("average_velocity", {}).get("left", "")])
            writer.writerow(["Average Velocity (Right)", summary.get("average_velocity", {}).get("right", "")])
            writer.writerow(["Detection Rate (Left)", summary.get("detection_rate", {}).get("left", "")])
            writer.writerow(["Detection Rate (Right)", summary.get("detection_rate", {}).get("right", "")])
            writer.writerow(["Total Frames", summary.get("total_frames", "")])
        writer.writerow([])

    # Write skeleton data summary
    if analysis.skeleton_data:
        writer.writerow(["Skeleton Data"])
        writer.writerow(["Frame", "Timestamp", "Hand Type", "Detection"])
        for i, frame_data in enumerate(analysis.skeleton_data[:100]):  # Limit to first 100 frames
            writer.writerow([
                frame_data.get("frame_number", i),
                frame_data.get("timestamp", ""),
                frame_data.get("hand_type", ""),
                "Yes" if frame_data.get("landmarks") else "No"
            ])

    # Get CSV content
    csv_content = output.getvalue()
    output.close()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=analysis_{analysis_id}.csv"
        }
    )


@router.delete(
    "/{analysis_id}",
    summary="Delete analysis result",
    responses={
        404: {"description": "Analysis not found", "model": ErrorResponse},
        200: {"description": "Analysis deleted successfully"}
    }
)
async def delete_analysis(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """Delete analysis result and associated data"""

    # Find the analysis
    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Optionally delete associated video file (be careful with this)
    # For now, we'll just delete the analysis record, not the video
    # video_id = analysis.video_id

    # Delete the analysis record
    db.delete(analysis)
    db.commit()

    return {"message": "Analysis deleted successfully", "id": analysis_id}


@router.get(
    "/test/mediapipe",
    summary="Test MediaPipe functionality",
)
async def test_mediapipe():
    """Test if MediaPipe is working correctly"""
    import logging
    logger = logging.getLogger(__name__)

    result = {
        "mediapipe_available": False,
        "hand_detector_available": False,
        "test_detection": None,
        "errors": []
    }

    # Test MediaPipe import
    try:
        import mediapipe as mp
        result["mediapipe_available"] = True
        logger.info("[TEST] MediaPipe import successful")
    except Exception as e:
        result["errors"].append(f"MediaPipe import error: {str(e)}")
        logger.error(f"[TEST] MediaPipe import failed: {e}")
        return result

    # Test HandSkeletonDetector
    try:
        from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
        result["hand_detector_available"] = True
        logger.info("[TEST] HandSkeletonDetector import successful")

        # Create a test detector
        detector = HandSkeletonDetector(
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3
        )
        logger.info("[TEST] HandSkeletonDetector initialized")

        # Create a simple test image (white background with a black square)
        import numpy as np
        test_image = np.ones((480, 640, 3), dtype=np.uint8) * 255
        test_image[100:200, 100:200] = 0  # Black square

        # Try detection
        detection_result = detector.detect_from_frame(test_image)
        result["test_detection"] = {
            "hands_detected": len(detection_result.get("hands", [])),
            "frame_shape": detection_result.get("frame_shape", [])
        }
        logger.info(f"[TEST] Detection result: {result['test_detection']}")

    except Exception as e:
        import traceback
        result["errors"].append(f"HandSkeletonDetector error: {str(e)}")
        logger.error(f"[TEST] HandSkeletonDetector failed: {e}")
        logger.error(f"[TEST] Traceback:\n{traceback.format_exc()}")

    return result
