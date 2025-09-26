from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models import Base
import uuid
import enum

class ComparisonStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ComparisonResult(Base):
    """比較結果モデル - 学習者の動作と基準動作の比較結果"""
    __tablename__ = "comparison_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # 関連ID
    reference_model_id = Column(String, ForeignKey("reference_models.id"), nullable=False)
    learner_analysis_id = Column(String, ForeignKey("analysis_results.id"), nullable=False)

    # ステータス
    status = Column(Enum(ComparisonStatus), default=ComparisonStatus.PENDING)
    progress = Column(Integer, default=0)

    # 比較スコア（0-100）
    overall_score = Column(Float, nullable=True)  # 総合スコア
    speed_score = Column(Float, nullable=True)     # 速度スコア
    smoothness_score = Column(Float, nullable=True) # 滑らかさスコア
    stability_score = Column(Float, nullable=True)  # 安定性スコア
    efficiency_score = Column(Float, nullable=True) # 効率性スコア

    # 詳細な比較データ
    comparison_data = Column(JSON, nullable=True)  # 詳細な比較結果
    dtw_distance = Column(Float, nullable=True)    # DTW距離（類似度）

    # 時系列の一致度データ
    temporal_alignment = Column(JSON, nullable=True)  # 時間軸での対応関係

    # フィードバック
    feedback = Column(JSON, nullable=True, default={
        "strengths": [],      # 良い点
        "weaknesses": [],     # 改善点
        "suggestions": [],    # 具体的な提案
        "detailed_analysis": {}  # 詳細分析
    })

    # メトリクスの詳細比較
    metrics_comparison = Column(JSON, nullable=True, default={
        "velocity": {
            "learner": {},
            "reference": {},
            "difference": {}
        },
        "trajectory": {
            "learner": {},
            "reference": {},
            "difference": {}
        },
        "stability": {
            "learner": {},
            "reference": {},
            "difference": {}
        },
        "efficiency": {
            "learner": {},
            "reference": {},
            "difference": {}
        }
    })

    # エラー情報
    error_message = Column(Text, nullable=True)

    # タイムスタンプ
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    # リレーション
    reference_model = relationship("ReferenceModel", back_populates="comparisons")
    learner_analysis = relationship("AnalysisResult", foreign_keys=[learner_analysis_id])