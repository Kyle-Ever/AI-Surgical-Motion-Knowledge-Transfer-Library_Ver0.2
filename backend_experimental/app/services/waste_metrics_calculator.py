"""
ムダ指標計算モジュール
手術動作の「ムダ」を定量化する3つの指標を計算:
  1. アイドルタイム（停滞時間）
  2. 作業空間（凸包面積）
  3. 動作回数（離散動作数）
"""

import numpy as np
from scipy.spatial import ConvexHull
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class WasteMetricsCalculator:
    """手術動作のムダ指標計算クラス"""

    # --- 閾値定数（実データでチューニング予定） ---
    # アイドル判定: 正規化座標での速度閾値（0-1空間）
    IDLE_VELOCITY_THRESHOLD = 0.005
    # アイドル判定: ピクセル座標での速度閾値
    IDLE_VELOCITY_THRESHOLD_PIXEL = 5.0
    # アイドル判定: 最小持続フレーム数（これ未満は一瞬の停止として無視）
    IDLE_MIN_FRAMES = 5
    # 動作カウント: 速度閾値（これを超えたら「動作中」）
    MOVEMENT_VELOCITY_THRESHOLD = 0.008
    # 動作カウント: ピクセル座標での速度閾値
    MOVEMENT_VELOCITY_THRESHOLD_PIXEL = 8.0
    # 動作カウント: 移動平均のウィンドウサイズ
    SMOOTHING_WINDOW = 5
    # ピクセル座標判定の閾値（x or y > 2.0 ならピクセル座標）
    PIXEL_COORD_THRESHOLD = 2.0

    def __init__(self, fps: float = 30.0):
        self.fps = fps
        self.frame_time = 1.0 / fps

    def calculate_all_waste_metrics(
        self, skeleton_data: List[Dict]
    ) -> Dict[str, Any]:
        """
        全ムダ指標を一括計算

        Args:
            skeleton_data: フロントエンド形式の骨格データ
                [{frame_number, timestamp, hands: [{hand_type, landmarks, ...}]}]

        Returns:
            3指標の計算結果
        """
        if not skeleton_data:
            return self._empty_result()

        # 手首位置を抽出（左右それぞれ + 統合）
        left_positions, right_positions = self._extract_wrist_positions_by_hand(
            skeleton_data
        )
        combined_positions = self._combine_positions(left_positions, right_positions)

        # 座標系を自動検出（ピクセル座標 or 正規化座標）
        self._is_pixel_coords = self._detect_pixel_coords(
            left_positions, right_positions
        )
        if self._is_pixel_coords:
            logger.info("[WASTE_METRICS] Detected pixel coordinates, using pixel thresholds")

        # 速度を計算
        combined_velocities = self._calculate_velocities(combined_positions)
        left_velocities = self._calculate_velocities(left_positions)
        right_velocities = self._calculate_velocities(right_positions)

        # 3つの指標を計算
        idle_time = self._calculate_idle_time(combined_velocities)
        working_volume = self._calculate_working_volume(
            left_positions, right_positions
        )
        movement_count = self._calculate_movement_count(combined_velocities)

        total_duration = len(skeleton_data) * self.frame_time

        result = {
            "idle_time": {
                **idle_time,
                "total_duration_seconds": round(total_duration, 2),
            },
            "working_volume": working_volume,
            "movement_count": {
                **movement_count,
                "total_duration_seconds": round(total_duration, 2),
            },
            "per_hand": {
                "left": {
                    "idle_time": self._calculate_idle_time(left_velocities),
                    "working_volume": self._calculate_working_volume_single(
                        left_positions
                    ),
                    "movement_count": self._calculate_movement_count(left_velocities),
                },
                "right": {
                    "idle_time": self._calculate_idle_time(right_velocities),
                    "working_volume": self._calculate_working_volume_single(
                        right_positions
                    ),
                    "movement_count": self._calculate_movement_count(right_velocities),
                },
            },
        }

        logger.info(
            f"[WASTE_METRICS] idle_ratio={idle_time['idle_time_ratio']:.3f}, "
            f"hull_area={working_volume['convex_hull_area']:.6f}, "
            f"movements={movement_count['movement_count']}, "
            f"movements/min={movement_count['movements_per_minute']:.1f}"
        )

        return result

    # =========================================================================
    # 位置・速度の抽出
    # =========================================================================

    def _extract_wrist_positions_by_hand(
        self, skeleton_data: List[Dict]
    ) -> tuple:
        """
        skeleton_dataから左右の手首位置をそれぞれ抽出

        V1形式（landmarks直接）とV2形式（hands配列）の両方に対応。

        Returns:
            (left_positions, right_positions): 各フレームの{x, y}またはNone
        """
        left_positions: List[Optional[Dict]] = []
        right_positions: List[Optional[Dict]] = []

        for frame_data in skeleton_data:
            hands = frame_data.get("hands", [])
            left_wrist = None
            right_wrist = None

            if hands:
                # V2形式: hands配列にhand_type付きで格納
                for hand in hands:
                    landmarks = hand.get("landmarks", {})
                    wrist = self._get_wrist_from_landmarks(landmarks)
                    if not wrist:
                        continue

                    hand_type = hand.get("hand_type", "")
                    pos = {"x": float(wrist["x"]), "y": float(wrist["y"])}

                    if hand_type == "Left":
                        left_wrist = pos
                    elif hand_type == "Right":
                        right_wrist = pos
                    else:
                        # hand_type不明の場合はrightとして扱う
                        if right_wrist is None:
                            right_wrist = pos
            else:
                # V1形式: landmarksが直接フレームに格納（hand_typeなし）
                landmarks = frame_data.get("landmarks", {})
                wrist = self._get_wrist_from_landmarks(landmarks)
                if wrist:
                    pos = {"x": float(wrist["x"]), "y": float(wrist["y"])}
                    right_wrist = pos  # V1は単一の手として扱う

            left_positions.append(left_wrist)
            right_positions.append(right_wrist)

        return left_positions, right_positions

    @staticmethod
    def _get_wrist_from_landmarks(landmarks) -> Optional[Dict]:
        """landmarksからpoint_0（手首）を取得。dict形式とlist形式の両方に対応。"""
        if isinstance(landmarks, dict):
            wrist = landmarks.get("point_0")
            if wrist and isinstance(wrist, dict) and wrist.get("x") is not None:
                return wrist
        elif isinstance(landmarks, list) and len(landmarks) > 0:
            # list形式: [{x, y, z}, ...] の最初の要素が手首
            wrist = landmarks[0]
            if isinstance(wrist, dict) and wrist.get("x") is not None:
                return wrist
        return None

    def _combine_positions(
        self,
        left: List[Optional[Dict]],
        right: List[Optional[Dict]],
    ) -> List[Optional[Dict]]:
        """左右の手首位置を平均して統合（片手のみの場合はその手を使用）"""
        combined = []
        for l_pos, r_pos in zip(left, right):
            if l_pos and r_pos:
                combined.append({
                    "x": (l_pos["x"] + r_pos["x"]) / 2.0,
                    "y": (l_pos["y"] + r_pos["y"]) / 2.0,
                })
            elif l_pos:
                combined.append(l_pos)
            elif r_pos:
                combined.append(r_pos)
            else:
                combined.append(None)
        return combined

    def _calculate_velocities(
        self, positions: List[Optional[Dict]]
    ) -> List[Optional[float]]:
        """フレーム間の速度を計算（正規化座標空間）"""
        velocities: List[Optional[float]] = []
        for i in range(len(positions)):
            if i == 0:
                velocities.append(None)
                continue
            if positions[i] and positions[i - 1]:
                dx = positions[i]["x"] - positions[i - 1]["x"]
                dy = positions[i]["y"] - positions[i - 1]["y"]
                velocities.append(np.sqrt(dx ** 2 + dy ** 2) / self.frame_time)
            else:
                velocities.append(None)
        return velocities

    # =========================================================================
    # 指標1: アイドルタイム
    # =========================================================================

    def _calculate_idle_time(
        self, velocities: List[Optional[float]]
    ) -> Dict[str, Any]:
        """
        アイドルタイム（手が停滞している時間）を計算

        速度が閾値以下の状態がIDLE_MIN_FRAMES以上続いた区間を「アイドル」とする。
        """
        if not velocities or all(v is None for v in velocities):
            return {
                "idle_time_ratio": 0.0,
                "total_idle_seconds": 0.0,
                "idle_segments": [],
                "idle_frame_count": 0,
            }

        total_frames = len(velocities)
        idle_segments = []
        current_idle_start = None
        threshold = self._idle_threshold

        for i, v in enumerate(velocities):
            is_idle = v is not None and v < threshold

            if is_idle and current_idle_start is None:
                current_idle_start = i
            elif not is_idle and current_idle_start is not None:
                duration_frames = i - current_idle_start
                if duration_frames >= self.IDLE_MIN_FRAMES:
                    idle_segments.append({
                        "start_frame": current_idle_start,
                        "end_frame": i - 1,
                        "duration_seconds": round(
                            duration_frames * self.frame_time, 3
                        ),
                    })
                current_idle_start = None

        # 末尾の処理
        if current_idle_start is not None:
            duration_frames = total_frames - current_idle_start
            if duration_frames >= self.IDLE_MIN_FRAMES:
                idle_segments.append({
                    "start_frame": current_idle_start,
                    "end_frame": total_frames - 1,
                    "duration_seconds": round(
                        duration_frames * self.frame_time, 3
                    ),
                })

        idle_frame_count = sum(
            seg["end_frame"] - seg["start_frame"] + 1 for seg in idle_segments
        )
        valid_frames = sum(1 for v in velocities if v is not None)
        idle_ratio = idle_frame_count / valid_frames if valid_frames > 0 else 0.0

        return {
            "idle_time_ratio": round(idle_ratio, 4),
            "total_idle_seconds": round(idle_frame_count * self.frame_time, 2),
            "idle_segments": idle_segments[:50],  # 上限50区間
            "idle_frame_count": idle_frame_count,
        }

    # =========================================================================
    # 指標2: 作業空間（凸包面積）
    # =========================================================================

    def _calculate_working_volume(
        self,
        left_positions: List[Optional[Dict]],
        right_positions: List[Optional[Dict]],
    ) -> Dict[str, Any]:
        """
        作業空間を計算（左右の手の移動範囲の凸包面積）

        全ての有効な手首座標を使い、凸包面積を求める。
        熟練医は作業空間が小さくコンパクト。
        """
        all_points = []
        for pos in left_positions:
            if pos:
                all_points.append([pos["x"], pos["y"]])
        for pos in right_positions:
            if pos:
                all_points.append([pos["x"], pos["y"]])

        return self._compute_hull_metrics(all_points)

    def _calculate_working_volume_single(
        self, positions: List[Optional[Dict]]
    ) -> Dict[str, Any]:
        """単一の手の作業空間を計算"""
        points = [[p["x"], p["y"]] for p in positions if p]
        return self._compute_hull_metrics(points)

    def _compute_hull_metrics(
        self, points: List[List[float]]
    ) -> Dict[str, Any]:
        """凸包と境界ボックスのメトリクスを計算"""
        if len(points) < 3:
            return {
                "convex_hull_area": 0.0,
                "bounding_box_area": 0.0,
                "hull_vertices": 0,
                "centroid": {"x": 0.0, "y": 0.0},
            }

        points_array = np.array(points)

        # 重複点を除去（ConvexHullがエラーになるため）
        unique_points = np.unique(points_array, axis=0)
        if len(unique_points) < 3:
            return {
                "convex_hull_area": 0.0,
                "bounding_box_area": 0.0,
                "hull_vertices": 0,
                "centroid": {
                    "x": round(float(np.mean(unique_points[:, 0])), 4),
                    "y": round(float(np.mean(unique_points[:, 1])), 4),
                },
            }

        try:
            hull = ConvexHull(unique_points)
            hull_area = float(hull.volume)  # 2Dではvolumeが面積
        except Exception as e:
            logger.warning(f"[WASTE_METRICS] ConvexHull failed: {e}")
            hull_area = 0.0
            hull = None

        # バウンディングボックス
        x_min, y_min = points_array.min(axis=0)
        x_max, y_max = points_array.max(axis=0)
        bbox_area = float((x_max - x_min) * (y_max - y_min))

        # 重心
        centroid_x = float(np.mean(points_array[:, 0]))
        centroid_y = float(np.mean(points_array[:, 1]))

        return {
            "convex_hull_area": round(hull_area, 6),
            "bounding_box_area": round(bbox_area, 6),
            "hull_vertices": len(hull.vertices) if hull else 0,
            "centroid": {
                "x": round(centroid_x, 4),
                "y": round(centroid_y, 4),
            },
        }

    # =========================================================================
    # 指標3: 動作回数
    # =========================================================================

    def _calculate_movement_count(
        self, velocities: List[Optional[float]]
    ) -> Dict[str, Any]:
        """
        離散的な動作回数を計算

        速度を平滑化→閾値との交差を検出→交差回数の半分が動作回数
        （閾値を下から上に超えた回数 = 新しい動作の開始）
        """
        valid_velocities = [v for v in velocities if v is not None]
        if len(valid_velocities) < self.SMOOTHING_WINDOW:
            return {
                "movement_count": 0,
                "movements_per_minute": 0.0,
                "avg_movement_duration_seconds": 0.0,
            }

        # 移動平均で平滑化
        smoothed = self._moving_average(valid_velocities, self.SMOOTHING_WINDOW)

        # 閾値交差を検出（下→上 = 動作開始）
        threshold = self._movement_threshold
        movement_count = 0
        was_below = smoothed[0] < threshold

        for v in smoothed[1:]:
            is_below = v < threshold
            if was_below and not is_below:
                movement_count += 1
            was_below = is_below

        total_duration = len(velocities) * self.frame_time
        movements_per_minute = (
            (movement_count / total_duration) * 60.0 if total_duration > 0 else 0.0
        )
        avg_duration = (
            total_duration / movement_count if movement_count > 0 else 0.0
        )

        return {
            "movement_count": movement_count,
            "movements_per_minute": round(movements_per_minute, 1),
            "avg_movement_duration_seconds": round(avg_duration, 2),
        }

    # =========================================================================
    # ユーティリティ
    # =========================================================================

    def _detect_pixel_coords(
        self,
        left: List[Optional[Dict]],
        right: List[Optional[Dict]],
    ) -> bool:
        """座標がピクセル座標かどうかを自動検出"""
        for positions in [left, right]:
            for pos in positions:
                if pos and (
                    abs(pos["x"]) > self.PIXEL_COORD_THRESHOLD
                    or abs(pos["y"]) > self.PIXEL_COORD_THRESHOLD
                ):
                    return True
        return False

    @property
    def _idle_threshold(self) -> float:
        if getattr(self, '_is_pixel_coords', False):
            return self.IDLE_VELOCITY_THRESHOLD_PIXEL
        return self.IDLE_VELOCITY_THRESHOLD

    @property
    def _movement_threshold(self) -> float:
        if getattr(self, '_is_pixel_coords', False):
            return self.MOVEMENT_VELOCITY_THRESHOLD_PIXEL
        return self.MOVEMENT_VELOCITY_THRESHOLD

    @staticmethod
    def _moving_average(data: List[float], window: int) -> List[float]:
        """移動平均"""
        if len(data) < window:
            return data
        cumsum = np.cumsum(data)
        cumsum = np.insert(cumsum, 0, 0)
        return list(
            (cumsum[window:] - cumsum[:-window]) / window
        )

    def _empty_result(self) -> Dict[str, Any]:
        """空データ用のデフォルト結果"""
        empty_idle = {
            "idle_time_ratio": 0.0,
            "total_idle_seconds": 0.0,
            "idle_segments": [],
            "idle_frame_count": 0,
        }
        empty_volume = {
            "convex_hull_area": 0.0,
            "bounding_box_area": 0.0,
            "hull_vertices": 0,
            "centroid": {"x": 0.0, "y": 0.0},
        }
        empty_count = {
            "movement_count": 0,
            "movements_per_minute": 0.0,
            "avg_movement_duration_seconds": 0.0,
        }
        return {
            "idle_time": {**empty_idle, "total_duration_seconds": 0.0},
            "working_volume": empty_volume,
            "movement_count": {**empty_count, "total_duration_seconds": 0.0},
            "per_hand": {
                "left": {
                    "idle_time": empty_idle,
                    "working_volume": empty_volume,
                    "movement_count": empty_count,
                },
                "right": {
                    "idle_time": empty_idle,
                    "working_volume": empty_volume,
                    "movement_count": empty_count,
                },
            },
        }

    # =========================================================================
    # スコア変換（0-100、低ムダ = 高スコア）
    # =========================================================================

    @staticmethod
    def score_idle_time(idle_time_ratio: float) -> float:
        """
        アイドルタイム比率をスコアに変換
        ratio 0% → 100点、ratio 50%以上 → 0点
        """
        score = max(0.0, (1.0 - idle_time_ratio * 2.0)) * 100.0
        return round(min(score, 100.0), 1)

    @staticmethod
    def score_working_volume(hull_area: float) -> float:
        """
        凸包面積をスコアに変換
        正規化座標(0-1)での面積 or ピクセル座標での面積を自動判定。
        面積 0 → 100点
        """
        # ピクセル座標の場合は面積が大きい（例: 100000以上）
        if hull_area > 100:
            # ピクセル座標: 1920x1080の画面で最大面積≒500000
            max_area = 500000.0
        else:
            # 正規化座標: 最大面積≒0.25（画面の1/4）
            max_area = 0.10
        ratio = min(hull_area / max_area, 1.0) if max_area > 0 else 0.0
        score = (1.0 - ratio) * 100.0
        return round(max(score, 0.0), 1)

    @staticmethod
    def score_movement_count(movements_per_minute: float) -> float:
        """
        動作回数/分をスコアに変換
        少ない動作回数 = 効率的 = 高スコア
        0回/分 → 100点、60回/分以上 → 0点
        """
        max_mpm = 60.0
        ratio = min(movements_per_minute / max_mpm, 1.0)
        score = (1.0 - ratio) * 100.0
        return round(max(score, 0.0), 1)

    def calculate_waste_scores(
        self, waste_metrics: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        ムダ指標からスコアを一括計算

        Returns:
            {waste_score, idle_time_score, working_volume_score, movement_count_score}
        """
        idle_score = self.score_idle_time(
            waste_metrics.get("idle_time", {}).get("idle_time_ratio", 0)
        )
        volume_score = self.score_working_volume(
            waste_metrics.get("working_volume", {}).get("convex_hull_area", 0)
        )
        movement_score = self.score_movement_count(
            waste_metrics.get("movement_count", {}).get("movements_per_minute", 0)
        )

        # 複合スコア（重み付き平均）
        waste_score = round(
            idle_score * 0.4 + volume_score * 0.3 + movement_score * 0.3,
            1,
        )

        return {
            "waste_score": waste_score,
            "idle_time_score": idle_score,
            "working_volume_score": volume_score,
            "movement_count_score": movement_score,
        }
