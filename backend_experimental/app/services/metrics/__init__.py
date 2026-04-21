"""
6指標メトリクスパッケージ
手術動作を6つの指標で定量評価する

Group A: 動作品質 (Motion Quality) — どれだけ上手く動けているか
  A1: 動作経済性 (Economy of Motion)
  A2: 動作滑らかさ (Smoothness / SPARC)
  A3: 両手協調性 (Bimanual Coordination)

Group B: ムダ検出 (Waste Detection) — どこで時間を失っているか
  B1: ロスタイム (Lost Time)
  B2: 動作回数効率 (Movement Count)
  B3: 作業空間偏差 (Working Volume Deviation)
"""

from .event_detector import EventDetector
from .six_metrics_service import SixMetricsService
from .types import MetricResult, ExpertBaseline, SixMetricsResult

__all__ = [
    "SixMetricsService",
    "MetricResult",
    "ExpertBaseline",
    "SixMetricsResult",
    "EventDetector",
]
