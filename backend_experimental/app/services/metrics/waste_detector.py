"""
Group B: ムダ検出 (Waste Detection)
  B1: ロスタイム (Lost Time) — 3段階停止分類
  B2: 動作回数効率 (Movement Count) — 閾値交差カウント
  B3: 作業空間偏差 (Working Volume Deviation) — 凸包面積
"""

import numpy as np
from scipy.spatial import ConvexHull
from typing import List, Dict, Any, Optional
import logging

from .types import PreprocessedData

logger = logging.getLogger(__name__)

# === B1: ロスタイム定数 ===
IDLE_VELOCITY_THRESHOLD = 0.005         # 正規化座標
IDLE_VELOCITY_THRESHOLD_PIXEL = 5.0     # ピクセル座標
MICRO_PAUSE_MAX_SEC = 1.0              # マイクロポーズ上限
CHECK_PAUSE_MAX_SEC = 3.0              # 確認停止上限（超えるとロスタイム）

# === B2: 動作回数定数 ===
MOVEMENT_VELOCITY_THRESHOLD = 0.008     # 正規化座標
MOVEMENT_VELOCITY_THRESHOLD_PIXEL = 8.0 # ピクセル座標
SMOOTHING_WINDOW = 5


class WasteDetector:
    """Group B: ムダ検出の3指標を計算"""

    def __init__(self, fps: float = 30.0):
        self.fps = fps

    # =========================================================================
    # B1: ロスタイム (Lost Time — 3段階停止分類)
    # =========================================================================

    def lost_time(self, data: PreprocessedData) -> Dict[str, Any]:
        """
        B1: 3段階停止分類によるロスタイム検出

        停止を3カテゴリに分類:
        - マイクロポーズ (< 1秒): 正常な動作間の微小停止 → カウントしない
        - 確認停止 (1-3秒): 出血確認など臨床的に正当 → 参考情報として記録
        - ロストタイム (> 3秒): 迷い・計画不足 → スコア算出対象
        """
        velocities = data.combined_velocities
        if not velocities:
            return self._empty_lost_time(0)

        threshold = (IDLE_VELOCITY_THRESHOLD_PIXEL
                     if data.is_pixel_coords
                     else IDLE_VELOCITY_THRESHOLD)
        frame_time = 1.0 / data.fps

        # 連続停止区間を検出
        idle_segments = []
        current_start = None

        for i, v in enumerate(velocities):
            is_idle = v is not None and v < threshold
            if is_idle:
                if current_start is None:
                    current_start = i
            else:
                if current_start is not None:
                    duration_sec = (i - current_start) * frame_time
                    idle_segments.append({
                        "start_frame": current_start,
                        "end_frame": i - 1,
                        "duration_seconds": round(duration_sec, 3),
                        "start_time": round(current_start * frame_time, 3),
                    })
                    current_start = None

        # 末尾処理
        if current_start is not None:
            duration_sec = (len(velocities) - current_start) * frame_time
            idle_segments.append({
                "start_frame": current_start,
                "end_frame": len(velocities) - 1,
                "duration_seconds": round(duration_sec, 3),
                "start_time": round(current_start * frame_time, 3),
            })

        # 3段階分類
        micro = [s for s in idle_segments if s["duration_seconds"] < MICRO_PAUSE_MAX_SEC]
        check = [s for s in idle_segments
                 if MICRO_PAUSE_MAX_SEC <= s["duration_seconds"] <= CHECK_PAUSE_MAX_SEC]
        lost = [s for s in idle_segments if s["duration_seconds"] > CHECK_PAUSE_MAX_SEC]

        lost_sec = sum(s["duration_seconds"] for s in lost)
        check_sec = sum(s["duration_seconds"] for s in check)
        total_idle_sec = sum(s["duration_seconds"] for s in idle_segments)
        duration = data.total_duration_seconds

        return {
            "lost_time_ratio": round(lost_sec / duration, 4) if duration > 0 else 0,
            "lost_time_seconds": round(lost_sec, 2),
            "lost_time_segments": lost[:50],
            "check_pause_count": len(check),
            "check_pause_total_seconds": round(check_sec, 2),
            "micro_pause_count": len(micro),
            "total_idle_seconds": round(total_idle_sec, 2),
            "total_idle_ratio": round(total_idle_sec / duration, 4) if duration > 0 else 0,
            "total_duration_seconds": duration,
        }

    # =========================================================================
    # B2: 動作回数効率 (Movement Count)
    # =========================================================================

    def movement_count(self, data: PreprocessedData) -> Dict[str, Any]:
        """
        B2: 離散的な動作回数

        速度プロファイルの閾値交差（停止→動作開始）をカウント。
        JIGSAWS検証済みの手法。
        """
        threshold = (MOVEMENT_VELOCITY_THRESHOLD_PIXEL
                     if data.is_pixel_coords
                     else MOVEMENT_VELOCITY_THRESHOLD)

        valid = [v for v in data.combined_velocities if v is not None]
        if len(valid) < SMOOTHING_WINDOW:
            return self._empty_movement_count(data.total_duration_seconds)

        # 移動平均で平滑化
        smoothed = self._moving_average(valid, SMOOTHING_WINDOW)

        # 閾値交差検出（下→上 = 動作開始）
        count = 0
        was_below = smoothed[0] < threshold
        for v in smoothed[1:]:
            is_below = v < threshold
            if was_below and not is_below:
                count += 1
            was_below = is_below

        duration = data.total_duration_seconds
        mpm = (count / duration) * 60.0 if duration > 0 else 0
        avg_dur = duration / count if count > 0 else 0

        return {
            "movement_count": count,
            "movements_per_minute": round(mpm, 1),
            "avg_movement_duration_seconds": round(avg_dur, 2),
            "total_duration_seconds": duration,
        }

    # =========================================================================
    # B3: 作業空間偏差 (Working Volume Deviation)
    # =========================================================================

    def working_volume(self, data: PreprocessedData) -> Dict[str, Any]:
        """
        B3: 手の移動範囲の凸包面積

        GOALSの空間認識評価軸に対応。
        エキスパートと比較して広すぎ/狭すぎの双方向で評価。
        """
        all_points = []
        for pos in data.left_positions:
            if pos:
                all_points.append([pos["x"], pos["y"]])
        for pos in data.right_positions:
            if pos:
                all_points.append([pos["x"], pos["y"]])

        return self._compute_hull(all_points)

    def _compute_hull(self, points: List[List[float]]) -> Dict[str, Any]:
        if len(points) < 3:
            return {
                "convex_hull_area": 0.0,
                "bounding_box_area": 0.0,
                "hull_vertices": 0,
                "centroid": {"x": 0.0, "y": 0.0},
            }

        arr = np.array(points)
        unique = np.unique(arr, axis=0)
        if len(unique) < 3:
            cx = round(float(np.mean(unique[:, 0])), 4)
            cy = round(float(np.mean(unique[:, 1])), 4)
            return {
                "convex_hull_area": 0.0,
                "bounding_box_area": 0.0,
                "hull_vertices": 0,
                "centroid": {"x": cx, "y": cy},
            }

        try:
            hull = ConvexHull(unique)
            hull_area = float(hull.volume)  # 2Dではvolumeが面積
            hull_verts = len(hull.vertices)
        except Exception as e:
            logger.warning(f"[WASTE_DETECTOR] ConvexHull failed: {e}")
            hull_area = 0.0
            hull_verts = 0

        x_min, y_min = arr.min(axis=0)
        x_max, y_max = arr.max(axis=0)
        bbox = float((x_max - x_min) * (y_max - y_min))

        return {
            "convex_hull_area": round(hull_area, 6),
            "bounding_box_area": round(bbox, 6),
            "hull_vertices": hull_verts,
            "centroid": {
                "x": round(float(np.mean(arr[:, 0])), 4),
                "y": round(float(np.mean(arr[:, 1])), 4),
            },
        }

    # =========================================================================
    # ユーティリティ
    # =========================================================================

    @staticmethod
    def _moving_average(data: List[float], window: int) -> List[float]:
        if len(data) < window:
            return data
        cumsum = np.cumsum(data)
        cumsum = np.insert(cumsum, 0, 0)
        return list((cumsum[window:] - cumsum[:-window]) / window)

    @staticmethod
    def _empty_lost_time(duration: float) -> Dict[str, Any]:
        return {
            "lost_time_ratio": 0.0, "lost_time_seconds": 0.0,
            "lost_time_segments": [], "check_pause_count": 0,
            "check_pause_total_seconds": 0.0, "micro_pause_count": 0,
            "total_idle_seconds": 0.0, "total_idle_ratio": 0.0,
            "total_duration_seconds": duration,
        }

    @staticmethod
    def _empty_movement_count(duration: float) -> Dict[str, Any]:
        return {
            "movement_count": 0, "movements_per_minute": 0.0,
            "avg_movement_duration_seconds": 0.0,
            "total_duration_seconds": duration,
        }
