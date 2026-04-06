"""管理者パネル用Pydanticスキーマ"""

from typing import Optional
from pydantic import BaseModel, field_validator, model_validator


class WeightsUpdate(BaseModel):
    a1: Optional[float] = None
    a2: Optional[float] = None
    a3: Optional[float] = None
    b1: Optional[float] = None
    b2: Optional[float] = None
    b3: Optional[float] = None
    group_a: Optional[float] = None
    group_b: Optional[float] = None


class ThresholdsUpdate(BaseModel):
    idle_velocity_threshold: Optional[float] = None
    idle_velocity_threshold_pixel: Optional[float] = None
    micro_pause_max_sec: Optional[float] = None
    check_pause_max_sec: Optional[float] = None
    movement_velocity_threshold: Optional[float] = None
    movement_velocity_threshold_pixel: Optional[float] = None
    smoothing_window: Optional[int] = None
    hysteresis_ratio: Optional[float] = None
    adaptive_threshold: Optional[bool] = None
    idle_percentile: Optional[int] = None
    movement_percentile: Optional[int] = None


class ScoringUpdate(BaseModel):
    a1_max_path_pixel: Optional[float] = None
    a1_max_path_normalized: Optional[float] = None
    a2_sparc_min: Optional[float] = None
    a2_sparc_max: Optional[float] = None
    a3_both_hands_min_ratio: Optional[float] = None
    a3_correlation_weight: Optional[float] = None
    a3_balance_weight: Optional[float] = None
    b1_max_idle_ratio: Optional[float] = None
    b2_max_movements_per_minute: Optional[float] = None
    b3_max_area_pixel: Optional[float] = None
    b3_max_area_normalized: Optional[float] = None


class SparcUpdate(BaseModel):
    freq_cutoff_hz: Optional[float] = None
    amplitude_threshold: Optional[float] = None


class MetricsConfigUpdate(BaseModel):
    """部分更新用リクエストモデル。指定されたフィールドのみ更新される"""
    weights: Optional[WeightsUpdate] = None
    thresholds: Optional[ThresholdsUpdate] = None
    scoring: Optional[ScoringUpdate] = None
    sparc: Optional[SparcUpdate] = None
