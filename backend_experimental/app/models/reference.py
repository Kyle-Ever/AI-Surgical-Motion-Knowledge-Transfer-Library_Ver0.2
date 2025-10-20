from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models import Base
import uuid
import enum
from datetime import datetime
import pytz

def get_jst_now():
    """日本時間（JST）の現在時刻を返す（タイムゾーン情報なし）"""
    jst = pytz.timezone('Asia/Tokyo')
    return datetime.now(jst).replace(tzinfo=None)

class ReferenceType(str, enum.Enum):
    EXPERT = "expert"          # エキスパートの手技
    STANDARD = "standard"      # 標準手技
    CUSTOM = "custom"          # カスタム基準

class ReferenceModel(Base):
    """基準動作モデル - 比較の基準となるエキスパートの手技データ"""
    __tablename__ = "reference_models"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)  # 基準モデルの名前
    description = Column(Text, nullable=True)    # 説明

    # 関連する解析結果
    analysis_id = Column(String, ForeignKey("analysis_results.id"), nullable=False)

    # 基準タイプ
    reference_type = Column(Enum(ReferenceType), default=ReferenceType.EXPERT)

    # メタデータ
    surgeon_name = Column(String(100), nullable=True)  # 執刀医名
    surgery_type = Column(String(100), nullable=True)  # 手術タイプ
    surgery_date = Column(DateTime, nullable=True)     # 手術日

    # 評価基準の重み付け（デフォルト値）
    weights = Column(JSON, nullable=True, default={
        "speed": 0.25,
        "smoothness": 0.25,
        "stability": 0.25,
        "efficiency": 0.25
    })

    # 統計情報（キャッシュ）
    avg_speed_score = Column(Float, nullable=True)
    avg_smoothness_score = Column(Float, nullable=True)
    avg_stability_score = Column(Float, nullable=True)
    avg_efficiency_score = Column(Float, nullable=True)

    # タイムスタンプ
    created_at = Column(DateTime, default=get_jst_now)
    updated_at = Column(DateTime, default=get_jst_now, onupdate=get_jst_now)
    is_active = Column(Integer, default=1)  # ソフトデリート用

    # リレーション
    analysis_result = relationship("AnalysisResult", backref="reference_models")
    comparisons = relationship("ComparisonResult", back_populates="reference_model")