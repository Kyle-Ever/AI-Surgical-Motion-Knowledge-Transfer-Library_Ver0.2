"""
前処理モジュール — skeleton_dataを全指標計算の共通入力形式に変換

V1形式（landmarks直接）、V2形式（hands配列）、
dict形式landmarks、list形式landmarks、ピクセル座標/正規化座標
のすべてに対応する一元化された前処理。
"""

import numpy as np
from typing import List, Dict, Any, Optional
import logging

from .types import PreprocessedData

logger = logging.getLogger(__name__)

# ピクセル座標判定の閾値
PIXEL_COORD_THRESHOLD = 2.0


def preprocess_skeleton_data(
    skeleton_data: List[Dict], fps: float = 30.0
) -> PreprocessedData:
    """
    skeleton_dataを前処理して全指標計算の共通入力に変換

    対応フォーマット:
    - V2: [{frame_number, timestamp, hands: [{hand_type, landmarks: {"point_0": {x,y}}}]}]
    - V1: [{frame_number, timestamp, landmarks: {"point_0": {x,y}}}]
    - landmarks list形式: [{x, y, z, visibility}, ...]（point_0がindex 0）
    """
    if not skeleton_data:
        return _empty_preprocessed(fps)

    left_positions: List[Optional[Dict[str, float]]] = []
    right_positions: List[Optional[Dict[str, float]]] = []

    for frame_data in skeleton_data:
        hands = frame_data.get("hands", [])
        left_wrist = None
        right_wrist = None

        if hands:
            # V2形式: hands配列
            for hand in hands:
                wrist = _get_wrist(hand.get("landmarks"))
                if not wrist:
                    continue
                hand_type = hand.get("hand_type", "")
                if hand_type == "Left":
                    left_wrist = wrist
                elif hand_type == "Right":
                    right_wrist = wrist
                else:
                    if right_wrist is None:
                        right_wrist = wrist
        else:
            # V1形式: landmarksが直接フレームに格納
            wrist = _get_wrist(frame_data.get("landmarks"))
            if wrist:
                right_wrist = wrist

        left_positions.append(left_wrist)
        right_positions.append(right_wrist)

    # ピクセル座標検出
    is_pixel = _detect_pixel_coords(left_positions, right_positions)
    if is_pixel:
        logger.info("[PREPROCESS] Detected pixel coordinates")

    total_frames = len(skeleton_data)
    frame_time = 1.0 / fps if fps > 0 else 1.0 / 30.0

    # 実際の動画時間: skeleton_dataのタイムスタンプから算出
    first_timestamp = 0.0
    last_timestamp = 0.0
    if skeleton_data:
        first_timestamp = skeleton_data[0].get("timestamp", 0) or 0
        last_timestamp = skeleton_data[-1].get("timestamp", 0) or 0

    if last_timestamp > first_timestamp:
        total_duration = last_timestamp - first_timestamp
        # 実効FPSに更新
        if total_frames > 1:
            fps = (total_frames - 1) / total_duration
            frame_time = 1.0 / fps
    else:
        total_duration = total_frames * frame_time

    # 速度計算（実効FPSベースのframe_timeで計算）
    left_velocities = _calculate_velocities(left_positions, frame_time)
    right_velocities = _calculate_velocities(right_positions, frame_time)
    combined_positions = _combine_positions(left_positions, right_positions)
    combined_velocities = _calculate_velocities(combined_positions, frame_time)

    return PreprocessedData(
        left_positions=left_positions,
        right_positions=right_positions,
        left_velocities=left_velocities,
        right_velocities=right_velocities,
        combined_velocities=combined_velocities,
        fps=fps,
        is_pixel_coords=is_pixel,
        total_frames=total_frames,
        total_duration_seconds=round(total_duration, 2),
    )


def _get_wrist(landmarks) -> Optional[Dict[str, float]]:
    """landmarksから手首(point_0)を取得。dict/list両形式対応。"""
    if not landmarks:
        return None
    wrist = None
    if isinstance(landmarks, dict):
        wrist = landmarks.get("point_0")
    elif isinstance(landmarks, list) and len(landmarks) > 0:
        wrist = landmarks[0]
    if wrist and isinstance(wrist, dict) and wrist.get("x") is not None:
        return {"x": float(wrist["x"]), "y": float(wrist["y"])}
    return None


def _detect_pixel_coords(
    left: List[Optional[Dict]], right: List[Optional[Dict]]
) -> bool:
    """座標がピクセルか正規化かを自動検出"""
    for positions in [left, right]:
        for pos in positions:
            if pos and (
                abs(pos["x"]) > PIXEL_COORD_THRESHOLD
                or abs(pos["y"]) > PIXEL_COORD_THRESHOLD
            ):
                return True
    return False


def _calculate_velocities(
    positions: List[Optional[Dict]], frame_time: float
) -> List[Optional[float]]:
    """フレーム間速度を計算"""
    velocities: List[Optional[float]] = []
    for i in range(len(positions)):
        if i == 0:
            velocities.append(None)
            continue
        if positions[i] and positions[i - 1]:
            dx = positions[i]["x"] - positions[i - 1]["x"]
            dy = positions[i]["y"] - positions[i - 1]["y"]
            velocities.append(np.sqrt(dx ** 2 + dy ** 2) / frame_time)
        else:
            velocities.append(None)
    return velocities


def _combine_positions(
    left: List[Optional[Dict]], right: List[Optional[Dict]]
) -> List[Optional[Dict]]:
    """左右の手首位置を統合"""
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


def _empty_preprocessed(fps: float) -> PreprocessedData:
    return PreprocessedData(
        left_positions=[],
        right_positions=[],
        left_velocities=[],
        right_velocities=[],
        combined_velocities=[],
        fps=fps,
        is_pixel_coords=False,
        total_frames=0,
        total_duration_seconds=0.0,
    )
