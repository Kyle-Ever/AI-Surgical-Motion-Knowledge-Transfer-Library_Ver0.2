from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime

from app.models import get_db
from app.models.reference import ReferenceModel, ReferenceType
from app.models.comparison import ComparisonResult, ComparisonStatus
from app.models.analysis import AnalysisResult, AnalysisStatus
from app.schemas.scoring import (
    ReferenceModelCreate,
    ReferenceModelResponse,
    ReferenceModelListResponse,
    ComparisonCreate,
    ComparisonResponse,
    ComparisonDetailResponse,
    ComparisonReport
)
from app.services.scoring_service import ScoringService

router = APIRouter()
scoring_service = ScoringService()

@router.post(
    "/reference",
    response_model=ReferenceModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create reference model"
)
async def create_reference_model(
    reference: ReferenceModelCreate,
    db: Session = Depends(get_db)
):
    """基準動作モデルを作成"""
    try:
        # 解析結果の確認（大文字・小文字を無視）
        analysis = db.query(AnalysisResult).filter(
            AnalysisResult.id == reference.analysis_id,
            func.lower(AnalysisResult.status) == 'completed'
        ).first()

        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Completed analysis {reference.analysis_id} not found"
            )

        # 基準モデルを作成
        ref_model = await scoring_service.create_reference_model(
            db=db,
            name=reference.name,
            analysis_id=reference.analysis_id,
            description=reference.description,
            reference_type=reference.reference_type,
            surgeon_name=reference.surgeon_name,
            surgery_type=reference.surgery_type,
            surgery_date=reference.surgery_date,
            weights=reference.weights or scoring_service.weight_defaults
        )

        return ref_model

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reference model: {str(e)}"
        )

@router.get(
    "/references",
    response_model=List[ReferenceModelListResponse],
    summary="Get reference models list"
)
async def get_reference_models(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """基準動作モデルのリストを取得"""
    try:
        references = db.query(ReferenceModel).filter(
            ReferenceModel.is_active == 1
        ).offset(skip).limit(limit).all()

        return references

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch reference models: {str(e)}"
        )

@router.get(
    "/reference/{reference_id}",
    response_model=ReferenceModelResponse,
    summary="Get reference model details"
)
async def get_reference_model(
    reference_id: str,
    db: Session = Depends(get_db)
):
    """基準動作モデルの詳細を取得"""
    reference = db.query(ReferenceModel).filter(
        ReferenceModel.id == reference_id,
        ReferenceModel.is_active == 1
    ).first()

    if not reference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reference model {reference_id} not found"
        )

    return reference

@router.post(
    "/compare",
    response_model=ComparisonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start comparison"
)
async def start_comparison(
    comparison: ComparisonCreate,
    db: Session = Depends(get_db)
):
    """比較評価を開始"""
    try:
        # 基準モデルの確認
        reference = db.query(ReferenceModel).filter(
            ReferenceModel.id == comparison.reference_model_id,
            ReferenceModel.is_active == 1
        ).first()

        if not reference:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reference model {comparison.reference_model_id} not found"
            )

        # 学習者の解析結果の確認
        learner_analysis = db.query(AnalysisResult).filter(
            AnalysisResult.id == comparison.learner_analysis_id,
            func.lower(AnalysisResult.status) == 'completed'
        ).first()

        if not learner_analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Completed analysis {comparison.learner_analysis_id} not found"
            )

        # 比較を開始
        comparison_result = await scoring_service.start_comparison(
            db=db,
            reference_model_id=comparison.reference_model_id,
            learner_analysis_id=comparison.learner_analysis_id
        )

        return comparison_result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start comparison: {str(e)}"
        )

@router.get(
    "/comparison/{comparison_id}",
    response_model=ComparisonDetailResponse,
    summary="Get comparison result"
)
async def get_comparison_result(
    comparison_id: str,
    include_details: bool = False,
    db: Session = Depends(get_db)
):
    """比較結果を取得"""
    comparison = db.query(ComparisonResult).filter(
        ComparisonResult.id == comparison_id
    ).first()

    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found"
        )

    # 詳細データを含める場合
    if include_details:
        # reference_modelの情報も含める
        response = ComparisonDetailResponse(
            id=comparison.id,
            reference_model_id=comparison.reference_model_id,
            learner_analysis_id=comparison.learner_analysis_id,
            status=comparison.status,
            progress=comparison.progress,
            overall_score=comparison.overall_score,
            speed_score=comparison.speed_score,
            smoothness_score=comparison.smoothness_score,
            stability_score=comparison.stability_score,
            efficiency_score=comparison.efficiency_score,
            dtw_distance=comparison.dtw_distance,
            feedback=comparison.feedback,
            metrics_comparison=comparison.metrics_comparison,
            comparison_data=comparison.comparison_data,
            temporal_alignment=comparison.temporal_alignment,
            error_message=comparison.error_message,
            created_at=comparison.created_at,
            completed_at=comparison.completed_at,
            reference_model=comparison.reference_model
        )
    else:
        response = ComparisonResponse(
            id=comparison.id,
            reference_model_id=comparison.reference_model_id,
            learner_analysis_id=comparison.learner_analysis_id,
            status=comparison.status,
            progress=comparison.progress,
            overall_score=comparison.overall_score,
            speed_score=comparison.speed_score,
            smoothness_score=comparison.smoothness_score,
            stability_score=comparison.stability_score,
            efficiency_score=comparison.efficiency_score,
            dtw_distance=comparison.dtw_distance,
            feedback=comparison.feedback,
            metrics_comparison=comparison.metrics_comparison,
            error_message=comparison.error_message,
            created_at=comparison.created_at,
            completed_at=comparison.completed_at
        )

    return response

@router.get(
    "/comparison/{comparison_id}/status",
    summary="Get comparison status"
)
async def get_comparison_status(
    comparison_id: str,
    db: Session = Depends(get_db)
):
    """比較処理のステータスを取得"""
    comparison = db.query(ComparisonResult).filter(
        ComparisonResult.id == comparison_id
    ).first()

    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found"
        )

    return {
        "comparison_id": comparison.id,
        "status": comparison.status,
        "progress": comparison.progress,
        "overall_score": comparison.overall_score,
        "error_message": comparison.error_message
    }

@router.get(
    "/report/{comparison_id}",
    response_model=ComparisonReport,
    summary="Generate comparison report"
)
async def get_comparison_report(
    comparison_id: str,
    db: Session = Depends(get_db)
):
    """比較レポートを生成"""
    try:
        report = await scoring_service.get_comparison_report(
            db=db,
            comparison_id=comparison_id
        )
        return report

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )

@router.get(
    "/comparisons",
    response_model=List[ComparisonResponse],
    summary="Get comparisons list"
)
async def get_comparisons(
    learner_analysis_id: Optional[str] = None,
    reference_model_id: Optional[str] = None,
    status: Optional[ComparisonStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """比較結果のリストを取得"""
    try:
        query = db.query(ComparisonResult)

        if learner_analysis_id:
            query = query.filter(
                ComparisonResult.learner_analysis_id == learner_analysis_id
            )

        if reference_model_id:
            query = query.filter(
                ComparisonResult.reference_model_id == reference_model_id
            )

        if status:
            query = query.filter(ComparisonResult.status == status)

        comparisons = query.order_by(
            ComparisonResult.created_at.desc()
        ).offset(skip).limit(limit).all()

        return comparisons

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch comparisons: {str(e)}"
        )