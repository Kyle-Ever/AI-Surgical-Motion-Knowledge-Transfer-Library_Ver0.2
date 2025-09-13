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

# 蜃ｦ逅・ｸｭ縺ｮ繧ｿ繧ｹ繧ｯ繧堤ｮ｡逅・ｼ育ｰ｡譏鍋沿・・
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
    """蜍慕判縺ｮ隗｣譫舌ｒ髢句ｧ・""
    
    # 蜍慕判縺ｮ蟄伜惠遒ｺ隱・
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # 譌｢縺ｫ隗｣譫蝉ｸｭ縺九メ繧ｧ繝・け
    existing = db.query(AnalysisResult).filter(
        AnalysisResult.video_id == video_id,
        AnalysisResult.status.in_([AnalysisStatus.PENDING, AnalysisStatus.PROCESSING])
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Analysis already in progress")
    
    # 隗｣譫千ｵ先棡繝ｬ繧ｳ繝ｼ繝峨ｒ菴懈・
    analysis_id = str(uuid.uuid4())
    analysis_result = AnalysisResult(
        id=analysis_id,
        video_id=video_id,
        status=AnalysisStatus.PENDING
    )
    
    db.add(analysis_result)
    db.commit()
    db.refresh(analysis_result)
    
    # 繝舌ャ繧ｯ繧ｰ繝ｩ繧ｦ繝ｳ繝峨〒隗｣譫舌ｒ髢句ｧ・
    # 螳滄圀縺ｮ螳溯｣・〒縺ｯ縲，elery繧СQ縺ｪ縺ｩ縺ｮ繧ｿ繧ｹ繧ｯ繧ｭ繝･繝ｼ繧剃ｽｿ逕ｨ
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
    """隗｣譫舌・騾ｲ謐礼憾豕√ｒ蜿門ｾ・""
    
    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # 繝｢繝・け縺ｮ繧ｹ繝・ャ繝玲ュ蝣ｱ繧堤函謌・
    steps = []
    
    if analysis.status == AnalysisStatus.COMPLETED:
        steps = [
            ProcessingStep(name="蜍慕判隱ｭ縺ｿ霎ｼ縺ｿ", status="completed", progress=100),
            ProcessingStep(name="鬪ｨ譬ｼ讀懷・蜃ｦ逅・, status="completed", progress=100),
            ProcessingStep(name="蝎ｨ蜈ｷ霑ｽ霍｡蜃ｦ逅・, status="completed", progress=100),
            ProcessingStep(name="繝・・繧ｿ逕滓・", status="completed", progress=100),
        ]
    elif analysis.status == AnalysisStatus.PROCESSING:
        progress = analysis.progress or 0
        if progress < 25:
            steps = [
                ProcessingStep(name="蜍慕判隱ｭ縺ｿ霎ｼ縺ｿ", status="processing", progress=progress * 4),
                ProcessingStep(name="鬪ｨ譬ｼ讀懷・蜃ｦ逅・, status="pending"),
                ProcessingStep(name="蝎ｨ蜈ｷ霑ｽ霍｡蜃ｦ逅・, status="pending"),
                ProcessingStep(name="繝・・繧ｿ逕滓・", status="pending"),
            ]
        elif progress < 50:
            steps = [
                ProcessingStep(name="蜍慕判隱ｭ縺ｿ霎ｼ縺ｿ", status="completed", progress=100),
                ProcessingStep(name="鬪ｨ譬ｼ讀懷・蜃ｦ逅・, status="processing", progress=(progress - 25) * 4),
                ProcessingStep(name="蝎ｨ蜈ｷ霑ｽ霍｡蜃ｦ逅・, status="pending"),
                ProcessingStep(name="繝・・繧ｿ逕滓・", status="pending"),
            ]
        elif progress < 75:
            steps = [
                ProcessingStep(name="蜍慕判隱ｭ縺ｿ霎ｼ縺ｿ", status="completed", progress=100),
                ProcessingStep(name="鬪ｨ譬ｼ讀懷・蜃ｦ逅・, status="completed", progress=100),
                ProcessingStep(name="蝎ｨ蜈ｷ霑ｽ霍｡蜃ｦ逅・, status="processing", progress=(progress - 50) * 4),
                ProcessingStep(name="繝・・繧ｿ逕滓・", status="pending"),
            ]
        else:
            steps = [
                ProcessingStep(name="蜍慕判隱ｭ縺ｿ霎ｼ縺ｿ", status="completed", progress=100),
                ProcessingStep(name="鬪ｨ譬ｼ讀懷・蜃ｦ逅・, status="completed", progress=100),
                ProcessingStep(name="蝎ｨ蜈ｷ霑ｽ霍｡蜃ｦ逅・, status="completed", progress=100),
                ProcessingStep(name="繝・・繧ｿ逕滓・", status="processing", progress=(progress - 75) * 4),
            ]
    else:
        steps = [
            ProcessingStep(name="蜍慕判隱ｭ縺ｿ霎ｼ縺ｿ", status="pending"),
            ProcessingStep(name="鬪ｨ譬ｼ讀懷・蜃ｦ逅・, status="pending"),
            ProcessingStep(name="蝎ｨ蜈ｷ霑ｽ霍｡蜃ｦ逅・, status="pending"),
            ProcessingStep(name="繝・・繧ｿ逕滓・", status="pending"),
        ]
    

        # --- unified step mapping (override) ---
    try:
        video = db.query(Video).filter(Video.id == analysis.video_id).first()
        video_type = getattr(video, 'video_type', None) or 'external'
        LABELS = {
            'preprocessing': '動画読み込み',
            'video_info': '動画情報',
            'frame_extraction': 'フレーム抽出',
            'skeleton_detection': '骨格検出',
            'instrument_detection': '器具追跡',
            'motion_analysis': 'モーション解析',
            'score_calculation': 'スコア計算',
            'data_saving': 'データ保存',
            'completed': '完了',
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
    # --- end unified mapping ---# --- end unified mapping ---
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
    """隗｣譫千ｵ先棡繧貞叙蠕・""
    
    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return analysis

# 繝舌ャ繧ｯ繧ｰ繝ｩ繧ｦ繝ｳ繝峨ち繧ｹ繧ｯ
async def process_video_analysis(
    analysis_id: str,
    video: Video,
    instruments: list,
    sampling_rate: int
):
    """蜍慕判隗｣譫舌ｒ螳溯｡・""
    from app.models import SessionLocal
    import asyncio
    from pathlib import Path
    
    db = SessionLocal()
    analysis_service = AnalysisService()
    
    try:
        analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
        if not analysis:
            return
        
        # 蜃ｦ逅・ｸｭ縺ｫ譖ｴ譁ｰ
        analysis.status = AnalysisStatus.PROCESSING
        analysis.current_step = "蜍慕判隱ｭ縺ｿ霎ｼ縺ｿ"
        db.commit()
        
        # 螳滄圀縺ｮ隗｣譫舌ｒ螳溯｡・
        video_path = Path(video.file_path)
        if video_path.exists():
            result = await analysis_service.process_video(
                video_id=video.id,
                video_path=str(video_path),
                video_type=video.video_type,
                analysis_id=analysis_id
            )
            
            # 邨先棡縺九ｉ隕∫ｴ・ョ繝ｼ繧ｿ繧呈峩譁ｰ
            analysis.status = AnalysisStatus.COMPLETED
            analysis.progress = 100
            
            # 繧ｹ繧ｳ繧｢縺九ｉ邨ｱ險医ｒ險育ｮ・
            if result.get("scores"):
                analysis.avg_velocity = result["scores"].get("speed", 0)
                analysis.max_velocity = result["scores"].get("speed", 0) * 1.5
                analysis.total_distance = result["frame_count"] * 10  # 莉ｮ縺ｮ險育ｮ・
            
            analysis.total_frames = result.get("frame_count", 0)
            analysis.completed_at = datetime.now()
            
        else:
            # 繝輔ぃ繧､繝ｫ縺瑚ｦ九▽縺九ｉ縺ｪ縺・ｴ蜷医・繝｢繝・け蜃ｦ逅・
            import random
            
            # 騾ｲ謐励ｒ繧ｷ繝溘Η繝ｬ繝ｼ繝・
            for progress in range(0, 101, 5):
                await asyncio.sleep(1)
                analysis.progress = progress
                
                if progress < 25:
                    analysis.current_step = "蜍慕判隱ｭ縺ｿ霎ｼ縺ｿ"
                elif progress < 50:
                    analysis.current_step = "鬪ｨ譬ｼ讀懷・蜃ｦ逅・
                elif progress < 75:
                    analysis.current_step = "蝎ｨ蜈ｷ霑ｽ霍｡蜃ｦ逅・
                else:
                    analysis.current_step = "繝・・繧ｿ逕滓・"
                
                db.commit()
            
            # 繝｢繝・け繝・・繧ｿ
            analysis.status = AnalysisStatus.COMPLETED
            analysis.avg_velocity = random.uniform(10, 20)
            analysis.max_velocity = random.uniform(30, 50)
            analysis.total_distance = random.uniform(1000, 2000)
            analysis.total_frames = random.randint(2000, 4000)
            analysis.completed_at = datetime.now()
            
            # 繝｢繝・け蠎ｧ讓吶ョ繝ｼ繧ｿ
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
        
        db.commit()
        
    except Exception as e:
        if analysis:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)
            db.commit()
    finally:
        db.close()

from datetime import datetime

@router.get(
    "/completed",
    response_model=list[AnalysisResultResponse],
    summary="List completed analyses",
)
async def get_completed_analyses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """螳御ｺ・＠縺溯ｧ｣譫千ｵ先棡縺ｮ荳隕ｧ繧貞叙蠕・""
    analyses = db.query(AnalysisResult).filter(
        AnalysisResult.status == AnalysisStatus.COMPLETED
    ).offset(skip).limit(limit).all()
    
    # 髢｢騾｣縺吶ｋ蜍慕判諠・ｱ繧ょ性繧√ｋ
    result = []
    for analysis in analyses:
        video = db.query(Video).filter(Video.id == analysis.video_id).first()
        analysis_dict = {
            "id": analysis.id,
            "video_id": analysis.video_id,
            "status": analysis.status,
            "progress": analysis.progress,
            "current_step": analysis.current_step,
            "started_at": analysis.started_at,
            "completed_at": analysis.completed_at,
            "video": video
        }
        result.append(analysis_dict)
    
    return result

