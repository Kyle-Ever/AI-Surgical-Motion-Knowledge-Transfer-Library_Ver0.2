"""
Review Deck 向けの気づきイベントスキーマ。

解析結果ページの Review Deck タブで、6指標別にタイムライン表示する
「気づきポイント」を表現する。
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class EventSeverity(str, Enum):
    """イベントの重要度表示レベル"""
    normal = "normal"    # タイムラインに点だけ
    notable = "notable"  # 通常のバッジ色
    hot = "hot"          # 強調（赤バッジ）


class EventIndicator(str, Enum):
    """6指標のID（SixMetricsService の metric_id と整合）"""
    A1 = "A1"  # 動作経済性
    A2 = "A2"  # 動作滑らかさ
    A3 = "A3"  # 両手協調性
    B1 = "B1"  # ロスタイム
    B2 = "B2"  # 動作回数効率
    B3 = "B3"  # 作業空間偏差


class EventCategory(str, Enum):
    """指標グループ (SixMetricsService の group と整合)"""
    motion_quality = "motion_quality"      # A系
    waste_detection = "waste_detection"    # B系


class ReviewEvent(BaseModel):
    """
    Review Deck に表示する単一の気づきイベント。

    フロントエンド側 ReviewEvent TypeScript 型と 1:1 対応する。

    実習生向けに、カード UI で 3 段構成 (fact/why/action) のフィードバックとして
    表示することを想定して、coaching_* フィールドを分けて持つ。
    description は後方互換のため残すが、新しい UI では fact/why/action を優先。
    """
    id: str = Field(..., description="安定したイベントID（解析ID + 指標 + 連番）")
    timestamp: float = Field(..., ge=0, description="動画開始からの秒数")
    duration: Optional[float] = Field(
        None, ge=0, description="持続時間を持つイベントの場合の秒数"
    )
    indicator: EventIndicator
    category: EventCategory
    severity: EventSeverity = EventSeverity.notable
    title: str = Field(..., description="Event List 一行表示用の要約（例: 両手停止 8.3秒）")
    description: str = Field(
        default="", description="（旧）Context Panel 用の詳細文。fact で代替可能"
    )
    coaching_fact: str = Field(default="", description="何が起きたか (時間 + 事実)")
    coaching_why: str = Field(default="", description="なぜ問題か (手技学的な意味)")
    coaching_action: str = Field(default="", description="次に意識すること (実習生向けヒント)")
    related_event_ids: List[str] = Field(default_factory=list)


class ReviewEventsResponse(BaseModel):
    """GET /api/v1/analysis/{id}/events レスポンス"""
    analysis_id: str
    has_events: bool = Field(
        ..., description="解析に対して events が生成済かどうか（旧解析互換フラグ）"
    )
    events: List[ReviewEvent] = Field(default_factory=list)
    generated_at: Optional[str] = None
    thresholds_version: Optional[str] = Field(
        None, description="event_detector 設定のバージョン識別子"
    )


class TimelineSample(BaseModel):
    """SixMetricsService.calculate_timeline 1 サンプル分"""
    timestamp: float
    overall: float
    mq: float
    wd: float
    a1: float
    a2: float
    a3: float
    b1: float
    b2: float
    b3: float


class TimelineResponse(BaseModel):
    """GET /api/v1/analysis/{id}/timeline レスポンス"""
    analysis_id: str
    interval_sec: float
    samples: List[TimelineSample] = Field(default_factory=list)
