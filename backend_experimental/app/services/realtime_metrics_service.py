"""
リアルタイムメトリクス計算サービス
手技の動きの3つのパラメータ（速度・滑らかさ・正確性）を計算
"""
import numpy as np
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class RealtimeMetricsService:
    """リアルタイムメトリクス計算サービス"""

    def __init__(self, fps: float = 30.0):
        """
        初期化

        Args:
            fps: 動画のフレームレート
        """
        self.fps = fps
        self.frame_time = 1.0 / fps

    def calculate_three_parameters(self, skeleton_data: List[Dict]) -> Dict[str, Any]:
        """
        3つのパラメータ（速度・滑らかさ・正確性）を計算

        Args:
            skeleton_data: 骨格データのリスト（フロントエンド形式）

        Returns:
            3パラメータの計算結果（0-100のスコア）
        """
        if not skeleton_data or len(skeleton_data) == 0:
            return {
                "speed_score": 0,
                "smoothness_score": 0,
                "accuracy_score": 0,
                "raw_values": {
                    "average_speed": 0,
                    "smoothness": 0,
                    "path_efficiency": 0
                }
            }

        # フレームごとに整理
        frames_dict = self._organize_by_frame(skeleton_data)

        # 手首の位置を抽出（左右両手）
        positions = self._extract_wrist_positions(frames_dict)

        # 速度を計算
        velocities = self._calculate_velocities(positions)
        avg_velocity = np.mean([v for v in velocities if v is not None and v > 0])

        # 滑らかさを計算（速度の変化の標準偏差の逆数）
        smoothness = self._calculate_smoothness(velocities)

        # 正確性を計算（経路効率：直線距離 / 実際の移動距離）
        path_efficiency = self._calculate_path_efficiency(positions)

        # スコアに変換（0-100）
        speed_score = self._velocity_to_score(avg_velocity)
        smoothness_score = self._smoothness_to_score(smoothness)
        accuracy_score = self._efficiency_to_score(path_efficiency)

        logger.info(f"[REALTIME_METRICS] Calculated: speed={speed_score:.2f}, smoothness={smoothness_score:.2f}, accuracy={accuracy_score:.2f}")

        return {
            "speed_score": float(speed_score),
            "smoothness_score": float(smoothness_score),
            "accuracy_score": float(accuracy_score),
            "raw_values": {
                "average_speed": float(avg_velocity),
                "smoothness": float(smoothness),
                "path_efficiency": float(path_efficiency)
            }
        }

    def _organize_by_frame(self, skeleton_data: List[Dict]) -> Dict[int, List[Dict]]:
        """
        データをフレーム番号でグループ化

        Args:
            skeleton_data: 骨格データのリスト

        Returns:
            フレーム番号でグループ化されたデータ
        """
        frames = {}
        for data in skeleton_data:
            frame_num = data.get("frame_number", 0)
            if frame_num not in frames:
                frames[frame_num] = []
            frames[frame_num].append(data)
        return frames

    def _extract_wrist_positions(self, frames_dict: Dict) -> List[Optional[Dict]]:
        """
        各フレームから手首の位置を抽出（左右両手の平均）

        Args:
            frames_dict: フレームごとのデータ

        Returns:
            手首位置のリスト
        """
        positions = []
        for frame_num in sorted(frames_dict.keys()):
            hands = frames_dict[frame_num]

            # 手首位置を収集
            wrist_positions = []
            for hand in hands:
                if hand.get("landmarks"):
                    wrist = hand["landmarks"].get("point_0", {})
                    if wrist.get("x") is not None and wrist.get("y") is not None:
                        wrist_positions.append({
                            "x": wrist["x"],
                            "y": wrist["y"]
                        })

            # 複数の手がある場合は平均を取る
            if wrist_positions:
                avg_x = np.mean([p["x"] for p in wrist_positions])
                avg_y = np.mean([p["y"] for p in wrist_positions])
                positions.append({"x": avg_x, "y": avg_y})
            else:
                positions.append(None)

        return positions

    def _calculate_velocities(self, positions: List[Optional[Dict]]) -> List[Optional[float]]:
        """
        速度を計算

        Args:
            positions: 位置のリスト

        Returns:
            速度のリスト
        """
        velocities = []
        for i in range(len(positions)):
            if i == 0:
                velocities.append(None)
                continue

            if positions[i] and positions[i-1]:
                dx = positions[i]["x"] - positions[i-1]["x"]
                dy = positions[i]["y"] - positions[i-1]["y"]
                distance = np.sqrt(dx**2 + dy**2)
                velocity = distance / self.frame_time
                velocities.append(velocity)
            else:
                velocities.append(None)

        return velocities

    def _calculate_smoothness(self, velocities: List[Optional[float]]) -> float:
        """
        滑らかさを計算（速度変化の小ささ）

        Args:
            velocities: 速度のリスト

        Returns:
            滑らかさスコア（高いほど滑らか）
        """
        valid_velocities = [v for v in velocities if v is not None]
        if len(valid_velocities) < 2:
            return 0

        # 速度変化（加速度）を計算
        accelerations = []
        for i in range(1, len(valid_velocities)):
            acc = abs(valid_velocities[i] - valid_velocities[i-1])
            accelerations.append(acc)

        if not accelerations:
            return 0

        # 速度変化の標準偏差（小さいほど滑らか）
        std_dev = np.std(accelerations)

        # 滑らかさスコア（標準偏差の逆数を正規化）
        # std_devが小さいほど高スコア
        if std_dev < 0.001:
            return 100
        else:
            # 逆数を取ってスケーリング
            smoothness = 1.0 / (1.0 + std_dev)
            return smoothness

    def _calculate_path_efficiency(self, positions: List[Optional[Dict]]) -> float:
        """
        経路効率を計算（正確性の指標）

        Args:
            positions: 位置のリスト

        Returns:
            経路効率（0-1、1に近いほど効率的）
        """
        valid_positions = [p for p in positions if p is not None]
        if len(valid_positions) < 2:
            return 0

        # 始点から終点までの直線距離
        start = valid_positions[0]
        end = valid_positions[-1]
        straight_distance = np.sqrt(
            (end["x"] - start["x"])**2 + (end["y"] - start["y"])**2
        )

        # 実際の移動距離
        actual_distance = 0
        for i in range(1, len(valid_positions)):
            dx = valid_positions[i]["x"] - valid_positions[i-1]["x"]
            dy = valid_positions[i]["y"] - valid_positions[i-1]["y"]
            actual_distance += np.sqrt(dx**2 + dy**2)

        # 経路効率（直線距離 / 実際の距離）
        if actual_distance < 0.001:
            return 0
        efficiency = straight_distance / actual_distance
        return min(efficiency, 1.0)  # 1を超えないようにクリップ

    def _velocity_to_score(self, velocity: float) -> float:
        """
        速度を0-100のスコアに変換

        Args:
            velocity: 速度（px/s）

        Returns:
            スコア（0-100）
        """
        # 速度の正規化（経験的な範囲）
        # 0-500 px/s を 0-100 にマッピング
        max_velocity = 500.0
        score = (velocity / max_velocity) * 100
        return min(score, 100)

    def _smoothness_to_score(self, smoothness: float) -> float:
        """
        滑らかさを0-100のスコアに変換

        Args:
            smoothness: 滑らかさ（0-1）

        Returns:
            スコア（0-100）
        """
        return smoothness * 100

    def _efficiency_to_score(self, efficiency: float) -> float:
        """
        経路効率を0-100のスコアに変換

        Args:
            efficiency: 経路効率（0-1）

        Returns:
            スコア（0-100）
        """
        return efficiency * 100
