"""
メトリクス計算モジュール
手の動きに関する各種メトリクスを計算
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """手の動きメトリクス計算クラス"""

    def __init__(self, fps: float = 30.0):
        """
        初期化

        Args:
            fps: 動画のフレームレート
        """
        self.fps = fps
        self.frame_time = 1.0 / fps  # フレーム間の時間（秒）

    def calculate_all_metrics(self, skeleton_data: List[Dict]) -> Dict[str, Any]:
        """
        全メトリクスを計算

        Args:
            skeleton_data: 骨格データのリスト

        Returns:
            計算されたメトリクス
        """
        # フレームごとのデータを整理
        frames_data = self._organize_by_frame(skeleton_data)

        # 各メトリクスを計算
        position_metrics = self._calculate_position_metrics(frames_data)
        velocity_metrics = self._calculate_velocity_metrics(frames_data)
        angle_metrics = self._calculate_angle_metrics(frames_data)
        coordination_metrics = self._calculate_coordination_metrics(frames_data)

        return {
            "position": position_metrics,
            "velocity": velocity_metrics,
            "angles": angle_metrics,
            "coordination": coordination_metrics,
            "summary": self._calculate_summary_metrics(
                position_metrics, velocity_metrics, angle_metrics, coordination_metrics
            )
        }

    def _organize_by_frame(self, skeleton_data: List[Dict]) -> Dict[int, Dict]:
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
            hand_type = data.get("hand_type", "Unknown")

            if frame_num not in frames:
                frames[frame_num] = {
                    "timestamp": data.get("timestamp", 0),
                    "left": None,
                    "right": None
                }

            if hand_type == "Left":
                frames[frame_num]["left"] = data
            elif hand_type == "Right":
                frames[frame_num]["right"] = data

        return frames

    def _calculate_position_metrics(self, frames_data: Dict) -> Dict:
        """
        位置メトリクスを計算

        Args:
            frames_data: フレームごとのデータ

        Returns:
            位置メトリクス
        """
        left_positions = []
        right_positions = []
        timestamps = []

        for frame_num in sorted(frames_data.keys()):
            frame = frames_data[frame_num]
            timestamps.append(frame["timestamp"])

            # 左手の手首位置（point_0）
            if frame["left"] and frame["left"].get("landmarks"):
                wrist = frame["left"]["landmarks"].get("point_0", {})
                left_positions.append({
                    "x": wrist.get("x", 0),
                    "y": wrist.get("y", 0),
                    "z": wrist.get("z", 0)
                })
            else:
                left_positions.append(None)

            # 右手の手首位置
            if frame["right"] and frame["right"].get("landmarks"):
                wrist = frame["right"]["landmarks"].get("point_0", {})
                right_positions.append({
                    "x": wrist.get("x", 0),
                    "y": wrist.get("y", 0),
                    "z": wrist.get("z", 0)
                })
            else:
                right_positions.append(None)

        return {
            "timestamps": timestamps,
            "left_hand": left_positions,
            "right_hand": right_positions
        }

    def _calculate_velocity_metrics(self, frames_data: Dict) -> Dict:
        """
        速度メトリクスを計算

        Args:
            frames_data: フレームごとのデータ

        Returns:
            速度メトリクス
        """
        positions = self._calculate_position_metrics(frames_data)
        left_velocities = []
        right_velocities = []

        for i in range(len(positions["timestamps"])):
            if i == 0:
                left_velocities.append(0)
                right_velocities.append(0)
                continue

            # 左手の速度
            if positions["left_hand"][i] and positions["left_hand"][i-1]:
                dx = positions["left_hand"][i]["x"] - positions["left_hand"][i-1]["x"]
                dy = positions["left_hand"][i]["y"] - positions["left_hand"][i-1]["y"]
                velocity = np.sqrt(dx**2 + dy**2) / self.frame_time
                left_velocities.append(velocity)
            else:
                left_velocities.append(None)

            # 右手の速度
            if positions["right_hand"][i] and positions["right_hand"][i-1]:
                dx = positions["right_hand"][i]["x"] - positions["right_hand"][i-1]["x"]
                dy = positions["right_hand"][i]["y"] - positions["right_hand"][i-1]["y"]
                velocity = np.sqrt(dx**2 + dy**2) / self.frame_time
                right_velocities.append(velocity)
            else:
                right_velocities.append(None)

        return {
            "timestamps": positions["timestamps"],
            "left_hand": left_velocities,
            "right_hand": right_velocities
        }

    def _calculate_angle_metrics(self, frames_data: Dict) -> Dict:
        """
        指の角度メトリクスを計算

        Args:
            frames_data: フレームごとのデータ

        Returns:
            角度メトリクス
        """
        left_angles = []
        right_angles = []
        timestamps = []

        finger_names = ["thumb", "index", "middle", "ring", "pinky"]
        finger_points = {
            "thumb": [0, 1, 2, 3, 4],
            "index": [0, 5, 6, 7, 8],
            "middle": [0, 9, 10, 11, 12],
            "ring": [0, 13, 14, 15, 16],
            "pinky": [0, 17, 18, 19, 20]
        }

        for frame_num in sorted(frames_data.keys()):
            frame = frames_data[frame_num]
            timestamps.append(frame["timestamp"])

            # 左手の角度
            if frame["left"] and frame["left"].get("landmarks"):
                angles = {}
                for finger in finger_names:
                    angle = self._calculate_finger_angle(
                        frame["left"]["landmarks"],
                        finger_points[finger]
                    )
                    angles[finger] = angle
                left_angles.append(angles)
            else:
                left_angles.append(None)

            # 右手の角度
            if frame["right"] and frame["right"].get("landmarks"):
                angles = {}
                for finger in finger_names:
                    angle = self._calculate_finger_angle(
                        frame["right"]["landmarks"],
                        finger_points[finger]
                    )
                    angles[finger] = angle
                right_angles.append(angles)
            else:
                right_angles.append(None)

        return {
            "timestamps": timestamps,
            "left_hand": left_angles,
            "right_hand": right_angles
        }

    def _calculate_finger_angle(self, landmarks: Dict, points: List[int]) -> float:
        """
        指の角度を計算

        Args:
            landmarks: ランドマーク座標
            points: 指のポイントインデックス

        Returns:
            角度（度）
        """
        if len(points) < 3:
            return 0

        # 3点を取得（基部、中間、先端）
        p1 = landmarks.get(f"point_{points[0]}", {})
        p2 = landmarks.get(f"point_{points[2]}", {})
        p3 = landmarks.get(f"point_{points[4]}", {})

        if not all([p1, p2, p3]):
            return 0

        # ベクトルを計算
        v1 = np.array([p2["x"] - p1["x"], p2["y"] - p1["y"]])
        v2 = np.array([p3["x"] - p2["x"], p3["y"] - p2["y"]])

        # 角度を計算
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        angle = np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0)))

        return float(angle)

    def _calculate_coordination_metrics(self, frames_data: Dict) -> Dict:
        """
        両手の協調性メトリクスを計算

        Args:
            frames_data: フレームごとのデータ

        Returns:
            協調性メトリクス
        """
        coordination_scores = []
        timestamps = []
        distances = []

        for frame_num in sorted(frames_data.keys()):
            frame = frames_data[frame_num]
            timestamps.append(frame["timestamp"])

            # 両手が検出されている場合
            if (frame["left"] and frame["left"].get("landmarks") and
                frame["right"] and frame["right"].get("landmarks")):

                left_wrist = frame["left"]["landmarks"].get("point_0", {})
                right_wrist = frame["right"]["landmarks"].get("point_0", {})

                # 両手の距離
                distance = np.sqrt(
                    (left_wrist.get("x", 0) - right_wrist.get("x", 0))**2 +
                    (left_wrist.get("y", 0) - right_wrist.get("y", 0))**2
                )
                distances.append(distance)

                # 協調スコア（仮の計算）
                coordination_scores.append(1.0 - min(distance, 1.0))
            else:
                distances.append(None)
                coordination_scores.append(None)

        return {
            "timestamps": timestamps,
            "coordination_score": coordination_scores,
            "hand_distance": distances
        }

    def _calculate_summary_metrics(
        self,
        position_metrics: Dict,
        velocity_metrics: Dict,
        angle_metrics: Dict,
        coordination_metrics: Dict
    ) -> Dict:
        """
        サマリーメトリクスを計算

        Args:
            各種メトリクス

        Returns:
            サマリーメトリクス
        """
        # 平均速度
        left_velocities = [v for v in velocity_metrics["left_hand"] if v is not None]
        right_velocities = [v for v in velocity_metrics["right_hand"] if v is not None]

        avg_left_velocity = np.mean(left_velocities) if left_velocities else 0
        avg_right_velocity = np.mean(right_velocities) if right_velocities else 0

        # 協調性スコア
        coord_scores = [s for s in coordination_metrics["coordination_score"] if s is not None]
        avg_coordination = np.mean(coord_scores) if coord_scores else 0

        # 検出率
        total_frames = len(position_metrics["timestamps"])
        left_detected = sum(1 for p in position_metrics["left_hand"] if p is not None)
        right_detected = sum(1 for p in position_metrics["right_hand"] if p is not None)

        return {
            "average_velocity": {
                "left": float(avg_left_velocity),
                "right": float(avg_right_velocity)
            },
            "average_coordination": float(avg_coordination),
            "detection_rate": {
                "left": left_detected / total_frames if total_frames > 0 else 0,
                "right": right_detected / total_frames if total_frames > 0 else 0
            },
            "total_frames": total_frames
        }