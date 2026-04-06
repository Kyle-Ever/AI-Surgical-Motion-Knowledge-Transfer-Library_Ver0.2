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

# === デフォルト定数（設定未指定時のフォールバック） ===
IDLE_VELOCITY_THRESHOLD = 0.005
IDLE_VELOCITY_THRESHOLD_PIXEL = 5.0
MICRO_PAUSE_MAX_SEC = 1.0
CHECK_PAUSE_MAX_SEC = 3.0
MOVEMENT_VELOCITY_THRESHOLD = 0.008
MOVEMENT_VELOCITY_THRESHOLD_PIXEL = 8.0
SMOOTHING_WINDOW = 5


class WasteDetector:
    """Group B: ムダ検出の3指標を計算"""

    def __init__(self, fps: float = 30.0, config: Dict[str, Any] = None):
        self.fps = fps
        t = config.get("thresholds", {}) if config else {}
        self.idle_vel = t.get("idle_velocity_threshold", IDLE_VELOCITY_THRESHOLD)
        self.idle_vel_px = t.get("idle_velocity_threshold_pixel", IDLE_VELOCITY_THRESHOLD_PIXEL)
        self.micro_max = t.get("micro_pause_max_sec", MICRO_PAUSE_MAX_SEC)
        self.check_max = t.get("check_pause_max_sec", CHECK_PAUSE_MAX_SEC)
        self.move_vel = t.get("movement_velocity_threshold", MOVEMENT_VELOCITY_THRESHOLD)
        self.move_vel_px = t.get("movement_velocity_threshold_pixel", MOVEMENT_VELOCITY_THRESHOLD_PIXEL)
        self.smooth_win = t.get("smoothing_window", SMOOTHING_WINDOW)
        # ヒステリシス係数: 上昇閾値=threshold, 下降閾値=threshold*係数
        self.hysteresis_ratio = t.get("hysteresis_ratio", 0.7)
        # 適応的閾値: 動画ごとの速度分布に基づいて閾値を自動調整
        self.adaptive_threshold = t.get("adaptive_threshold", True)
        self.idle_percentile = t.get("idle_percentile", 15)       # この百分位数以下を停止と判定
        self.movement_percentile = t.get("movement_percentile", 30)  # この百分位数を動作開始閾値に

    # =========================================================================
    # B1: ロスタイム (Lost Time — 3段階停止分類)
    # =========================================================================

    def lost_time(self, data: PreprocessedData) -> Dict[str, Any]:
        """
        B1: 3段階停止分類によるロスタイム検出（両手同時停止ベース）

        D'Angelo et al. (2015) "Idle time: an underdeveloped performance metric
        for assessing surgical skill." Am J Surg 209(4):645-651 に準拠。
        「両手とも停止」している区間のみをidle timeとして検出する。
        片手が保持（静止）で他方が操作中の場合は正常な手技であり、
        idle timeとしてカウントしない。

        停止を3カテゴリに分類:
        - マイクロポーズ (< 1秒): 正常な動作間の微小停止 → カウントしない
        - 確認停止 (1-3秒): 出血確認など臨床的に正当 → 参考情報として記録
        - ロストタイム (> 3秒): 迷い・計画不足 → スコア算出対象
        """
        left_vels = data.left_velocities
        right_vels = data.right_velocities
        n_frames = min(len(left_vels), len(right_vels))
        if n_frames == 0:
            return self._empty_lost_time(0)

        threshold = self._resolve_idle_threshold(data)
        frame_time = 1.0 / data.fps

        # 両手同時停止区間を検出
        # 片手のデータがNone（未検出）の場合はidle判定しない
        idle_segments = []
        current_start = None

        for i in range(n_frames):
            lv = left_vels[i]
            rv = right_vels[i]
            # 両手とも有効データがあり、かつ両方とも閾値以下の場合のみidle
            left_idle = lv is not None and lv < threshold
            right_idle = rv is not None and rv < threshold
            both_idle = left_idle and right_idle
            if both_idle:
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
            duration_sec = (n_frames - current_start) * frame_time
            idle_segments.append({
                "start_frame": current_start,
                "end_frame": n_frames - 1,
                "duration_seconds": round(duration_sec, 3),
                "start_time": round(current_start * frame_time, 3),
            })

        # 3段階分類
        micro = [s for s in idle_segments if s["duration_seconds"] < self.micro_max]
        check = [s for s in idle_segments
                 if self.micro_max <= s["duration_seconds"] <= self.check_max]
        lost = [s for s in idle_segments if s["duration_seconds"] > self.check_max]

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
            "applied_idle_threshold": round(threshold, 2),
        }

    # =========================================================================
    # B2: 動作回数効率 (Movement Count)
    # =========================================================================

    def movement_count(self, data: PreprocessedData) -> Dict[str, Any]:
        """
        B2: 離散的な動作回数（ヒステリシス付き閾値交差）

        ICSADの速度プロファイル閾値交差に基づく (Dosis et al. 2005)。
        チャタリング防止のため、上昇閾値と下降閾値を分離する
        ヒステリシスを適用。
        - 動作開始: 速度が上昇閾値(threshold)を超えた時点
        - 動作終了: 速度が下降閾値(threshold × hysteresis_ratio)を下回った時点
        """
        threshold = self._resolve_movement_threshold(data)
        threshold_low = threshold * self.hysteresis_ratio

        valid = [v for v in data.combined_velocities if v is not None]
        if len(valid) < self.smooth_win:
            return self._empty_movement_count(data.total_duration_seconds)

        # 移動平均で平滑化
        smoothed = self._moving_average(valid, self.smooth_win)

        # ヒステリシス付き閾値交差検出
        count = 0
        in_movement = smoothed[0] >= threshold
        for v in smoothed[1:]:
            if in_movement:
                # 動作中 → 下降閾値を下回ったら動作終了
                if v < threshold_low:
                    in_movement = False
            else:
                # 停止中 → 上昇閾値を超えたら動作開始
                if v >= threshold:
                    count += 1
                    in_movement = True

        duration = data.total_duration_seconds
        mpm = (count / duration) * 60.0 if duration > 0 else 0
        avg_dur = duration / count if count > 0 else 0

        return {
            "movement_count": count,
            "movements_per_minute": round(mpm, 1),
            "avg_movement_duration_seconds": round(avg_dur, 2),
            "total_duration_seconds": duration,
            "applied_movement_threshold": round(threshold, 2),
            "applied_movement_threshold_low": round(threshold_low, 2),
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
    # 適応的閾値
    # =========================================================================

    def _resolve_idle_threshold(self, data: PreprocessedData) -> float:
        """
        停止判定の閾値を解決する。
        adaptive_threshold=True の場合、速度分布の百分位数から自動算出。
        False の場���は固定閾値を使用。
        """
        if not self.adaptive_threshold:
            return self.idle_vel_px if data.is_pixel_coords else self.idle_vel

        # 両手の速度を個別に集めてpooling
        all_vels = []
        for v in data.left_velocities:
            if v is not None:
                all_vels.append(v)
        for v in data.right_velocities:
            if v is not None:
                all_vels.append(v)

        if len(all_vels) < 10:
            return self.idle_vel_px if data.is_pixel_coords else self.idle_vel

        adaptive = float(np.percentile(all_vels, self.idle_percentile))
        # 固定閾値を下限として使用（適応値がゼロに近くなりすぎるのを防止）
        fixed = self.idle_vel_px if data.is_pixel_coords else self.idle_vel
        result = max(adaptive, fixed)
        logger.info(
            f"[WASTE_DETECTOR] Idle threshold: adaptive P{self.idle_percentile}={adaptive:.2f}, "
            f"fixed={fixed:.2f} -> using {result:.2f}"
        )
        return result

    def _resolve_movement_threshold(self, data: PreprocessedData) -> float:
        """
        動作検出の閾値を解決する。
        adaptive_threshold=True の場合、速度分布の百分位数から自動算出。
        """
        if not self.adaptive_threshold:
            return self.move_vel_px if data.is_pixel_coords else self.move_vel

        combined = [v for v in data.combined_velocities if v is not None]
        if len(combined) < 10:
            return self.move_vel_px if data.is_pixel_coords else self.move_vel

        adaptive = float(np.percentile(combined, self.movement_percentile))
        fixed = self.move_vel_px if data.is_pixel_coords else self.move_vel
        result = max(adaptive, fixed)
        logger.info(
            f"[WASTE_DETECTOR] Movement threshold: adaptive P{self.movement_percentile}={adaptive:.2f}, "
            f"fixed={fixed:.2f} -> using {result:.2f}"
        )
        return result

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
