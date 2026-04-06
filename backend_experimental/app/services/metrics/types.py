"""6指標メトリクスの型定義"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class MetricResult:
    """単一指標の計算結果"""
    metric_id: str              # "A1", "A2", "A3", "B1", "B2", "B3"
    metric_name: str            # "economy_of_motion", "smoothness", etc.
    metric_label_ja: str        # "動作経済性", "動作滑らかさ", etc.
    group: str                  # "motion_quality" or "waste_detection"
    raw_values: Dict[str, Any]  # 計算された生値
    score: float                # 0-100
    ratio_to_expert: Optional[float] = None
    evaluation_mode: str = "absolute"  # "absolute" or "relative"


@dataclass
class ExpertBaseline:
    """エキスパート基準値"""
    economy_of_motion: Optional[float] = None     # A1: 総移動距離
    sparc: Optional[float] = None                  # A2: SPARC値
    bimanual_coordination: Optional[float] = None  # A3: 協調値
    lost_time_ratio: Optional[float] = None        # B1: ロスタイム比率
    movements_per_minute: Optional[float] = None   # B2: 動作回数/分
    working_volume_area: Optional[float] = None    # B3: 凸包面積


@dataclass
class SixMetricsResult:
    """6指標の統合結果"""
    metrics: List[MetricResult]
    motion_quality_score: float           # Group A 複合スコア (0-100)
    waste_detection_score: float          # Group B 複合スコア (0-100)
    overall_score: float                  # 総合スコア (0-100)
    evaluation_mode: str                  # "absolute" or "relative"
    expert_baseline_used: bool
    applied_config: Optional[Dict[str, Any]] = None  # 計算時の設定スナップショット

    def to_dict(self) -> Dict[str, Any]:
        """APIレスポンス用のdict変換"""
        metrics_by_group = {"motion_quality": {}, "waste_detection": {}}
        for m in self.metrics:
            entry = {
                "metric_id": m.metric_id,
                "metric_label_ja": m.metric_label_ja,
                "score": m.score,
                "ratio_to_expert": m.ratio_to_expert,
                "evaluation_mode": m.evaluation_mode,
                "raw_values": m.raw_values,
            }
            metrics_by_group[m.group][m.metric_name] = entry

        result = {
            "evaluation_mode": self.evaluation_mode,
            "expert_baseline_used": self.expert_baseline_used,
            "overall_score": self.overall_score,
            "motion_quality": {
                "group_score": self.motion_quality_score,
                "metrics": metrics_by_group["motion_quality"],
            },
            "waste_detection": {
                "group_score": self.waste_detection_score,
                "metrics": metrics_by_group["waste_detection"],
            },
        }
        if self.applied_config is not None:
            result["applied_config"] = self.applied_config
        return result


@dataclass
class PreprocessedData:
    """前処理済みデータ（全指標計算の共通入力）"""
    left_positions: List[Optional[Dict[str, float]]]
    right_positions: List[Optional[Dict[str, float]]]
    left_velocities: List[Optional[float]]
    right_velocities: List[Optional[float]]
    combined_velocities: List[Optional[float]]
    fps: float
    is_pixel_coords: bool
    total_frames: int
    total_duration_seconds: float
