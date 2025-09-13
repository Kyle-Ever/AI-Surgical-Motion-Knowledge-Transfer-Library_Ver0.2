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

router = APIRouter()

# 処理中のタスクを管理（簡易版）
processing_tasks: Dict[str, Any] = {}

@router.post(
    "/{video_id}/analyze",
    response_model=AnalysisResponse,
    summary="Start analysis",
    responses={
        400: {"description": "Analysis already in progress or invalid input"},
        404: {"description": "Video not found"},
    },
)
async def start_analysis(
    video_id: str,
    analysis_params: AnalysisCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """動画の解析を開始"""
    
    # 動画の存在確認
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # 既に解析中かチェック
    existing = db.query(AnalysisResult).filter(
        AnalysisResult.video_id == video_id,
        AnalysisResult.status.in_([AnalysisStatus.PENDING, AnalysisStatus.PROCESSING])
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Analysis already in progress")
    
    # 解析結果レコードを作成
    analysis_id = str(uuid.uuid4())
    analysis_result = AnalysisResult(
        id=analysis_id,
        video_id=video_id,
        status=AnalysisStatus.PENDING
    )
    
    db.add(analysis_result)
    db.commit()
    db.refresh(analysis_result)
    
    # バックグラウンドで解析を開始
    # 実際の実装では、CeleryやRQなどのタスクキューを使用
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
    responses={404: {"description": "Analysis not found"}},
)
async def get_analysis_status(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """解析の進捗状況を取得"""
    
    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # モックのステップ情報を生成
    steps = []
    
    if analysis.status == AnalysisStatus.COMPLETED:
        steps = [
            ProcessingStep(name="動画読み込み", status="completed", progress=100),
            ProcessingStep(name="骨格検出処理", status="completed", progress=100),
            ProcessingStep(name="器具追跡処理", status="completed", progress=100),
            ProcessingStep(name="データ生成", status="completed", progress=100),
        ]
    elif analysis.status == AnalysisStatus.PROCESSING:
        progress = analysis.progress or 0
        if progress < 25:
            steps = [
                ProcessingStep(name="動画読み込み", status="processing", progress=progress * 4),
                ProcessingStep(name="骨格検出処理", status="pending"),
                ProcessingStep(name="器具追跡処理", status="pending"),
                ProcessingStep(name="データ生成", status="pending"),
            ]
        elif progress < 50:
            steps = [
                ProcessingStep(name="動画読み込み", status="completed", progress=100),
                ProcessingStep(name="骨格検出処理", status="processing", progress=(progress - 25) * 4),
                ProcessingStep(name="器具追跡処理", status="pending"),
                ProcessingStep(name="データ生成", status="pending"),
            ]
        elif progress < 75:
            steps = [
                ProcessingStep(name="動画読み込み", status="completed", progress=100),
                ProcessingStep(name="骨格検出処理", status="completed", progress=100),
                ProcessingStep(name="器具追跡処理", status="processing", progress=(progress - 50) * 4),
                ProcessingStep(name="データ生成", status="pending"),
            ]
        else:
            steps = [
                ProcessingStep(name="動画読み込み", status="completed", progress=100),
                ProcessingStep(name="骨格検出処理", status="completed", progress=100),
                ProcessingStep(name="器具追跡処理", status="completed", progress=100),
                ProcessingStep(name="データ生成", status="processing", progress=(progress - 75) * 4),
            ]
    else:
        steps = [
            ProcessingStep(name="動画読み込み", status="pending"),
            ProcessingStep(name="骨格検出処理", status="pending"),
            ProcessingStep(name="器具追跡処理", status="pending"),
            ProcessingStep(name="データ生成", status="pending"),
        ]
    
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
    responses={404: {"description": "Analysis not found"}},
)
async def get_analysis_result(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """解析結果を取得"""
    
    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return analysis

# バックグラウンドタスク
async def process_video_analysis(
    analysis_id: str,
    video: Video,
    instruments: list,
    sampling_rate: int
):
    """動画解析を実行"""
    from app.models import SessionLocal
    import asyncio
    from pathlib import Path
    
    db = SessionLocal()
    analysis_service = AnalysisService()
    
    try:
        analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
        if not analysis:
            return
        
        # 処理中に更新
        analysis.status = AnalysisStatus.PROCESSING
        analysis.current_step = "動画読み込み"
        db.commit()
        
        # 実際の解析を実行
        video_path = Path(video.file_path)
        if video_path.exists():
            result = await analysis_service.process_video(
                video_id=video.id,
                video_path=str(video_path),
                video_type=video.video_type,
                analysis_id=analysis_id
            )
            
            # 結果から要約データを更新
            analysis.status = AnalysisStatus.COMPLETED
            analysis.progress = 100
            
            # スコアから統計を計算
            if result.get("scores"):
                analysis.avg_velocity = result["scores"].get("speed", 0)
                analysis.max_velocity = result["scores"].get("speed", 0) * 1.5
                analysis.total_distance = result["frame_count"] * 10  # 仮の計算
            
            analysis.total_frames = result.get("frame_count", 0)
            analysis.completed_at = datetime.now()
            
        else:
            # ファイルが見つからない場合はモック処理
            import random
            
            # 進捗をシミュレート
            for progress in range(0, 101, 5):
                await asyncio.sleep(1)
                analysis.progress = progress
                
                if progress < 25:
                    analysis.current_step = "動画読み込み"
                elif progress < 50:
                    analysis.current_step = "骨格検出処理"
                elif progress < 75:
                    analysis.current_step = "器具追跡処理"
                else:
                    analysis.current_step = "データ生成"
                
                db.commit()
            
            # モックデータ
            analysis.status = AnalysisStatus.COMPLETED
            analysis.avg_velocity = random.uniform(10, 20)
            analysis.max_velocity = random.uniform(30, 50)
            analysis.total_distance = random.uniform(1000, 2000)
            analysis.total_frames = random.randint(2000, 4000)
            analysis.completed_at = datetime.now()
            
            # モック座標データ
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
    """完了した解析結果の一覧を取得"""
    analyses = db.query(AnalysisResult).filter(
        AnalysisResult.status == AnalysisStatus.COMPLETED
    ).offset(skip).limit(limit).all()
    
    # 関連する動画情報も含める
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
