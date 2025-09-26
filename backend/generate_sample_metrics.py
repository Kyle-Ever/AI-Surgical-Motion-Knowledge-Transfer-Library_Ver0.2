"""
サンプルメトリクスデータを生成するスクリプト
既存の解析結果にメトリクスデータを追加する
"""

import json
import sqlite3
import numpy as np
from datetime import datetime

def generate_sample_metrics():
    """サンプルメトリクスを生成"""

    # サンプルタイムスタンプ（5秒ごと、10分間）
    timestamps = list(range(0, 600, 5))
    num_points = len(timestamps)

    # 左手の位置データ（ランダムウォーク）
    left_x = np.cumsum(np.random.randn(num_points) * 0.01) + 0.3
    left_y = np.cumsum(np.random.randn(num_points) * 0.01) + 0.5
    left_positions = [{"x": float(x), "y": float(y), "z": 0} for x, y in zip(left_x, left_y)]

    # 右手の位置データ
    right_x = np.cumsum(np.random.randn(num_points) * 0.01) + 0.7
    right_y = np.cumsum(np.random.randn(num_points) * 0.01) + 0.5
    right_positions = [{"x": float(x), "y": float(y), "z": 0} for x, y in zip(right_x, right_y)]

    # 速度データ（位置の差分）
    left_velocities = []
    right_velocities = []
    for i in range(num_points):
        if i == 0:
            left_velocities.append(0)
            right_velocities.append(0)
        else:
            left_v = np.sqrt((left_x[i] - left_x[i-1])**2 + (left_y[i] - left_y[i-1])**2) * 30
            right_v = np.sqrt((right_x[i] - right_x[i-1])**2 + (right_y[i] - right_y[i-1])**2) * 30
            left_velocities.append(float(left_v))
            right_velocities.append(float(right_v))

    # 協調性データ（両手の距離）
    distances = []
    for i in range(num_points):
        dist = np.sqrt((left_x[i] - right_x[i])**2 + (left_y[i] - right_y[i])**2)
        distances.append(float(dist))

    coordination_scores = [1.0 - min(d, 1.0) for d in distances]

    # メトリクス構造
    metrics = {
        "position": {
            "timestamps": timestamps,
            "left_hand": left_positions,
            "right_hand": right_positions
        },
        "velocity": {
            "timestamps": timestamps,
            "left_hand": left_velocities,
            "right_hand": right_velocities
        },
        "angles": {
            "timestamps": timestamps,
            "left_hand": [{"thumb": 45, "index": 30, "middle": 25, "ring": 20, "pinky": 15} for _ in range(num_points)],
            "right_hand": [{"thumb": 45, "index": 30, "middle": 25, "ring": 20, "pinky": 15} for _ in range(num_points)]
        },
        "coordination": {
            "timestamps": timestamps,
            "coordination_score": coordination_scores,
            "hand_distance": distances
        },
        "summary": {
            "average_velocity": {
                "left": float(np.mean(left_velocities)),
                "right": float(np.mean(right_velocities))
            },
            "average_coordination": float(np.mean(coordination_scores)),
            "detection_rate": {
                "left": 0.95,
                "right": 0.92
            },
            "total_frames": 192
        }
    }

    return {"metrics": metrics}

def generate_sample_skeleton_data():
    """サンプル骨格データを生成"""
    skeleton_data = []

    for frame_num in range(0, 192, 2):  # 2フレームごと
        for hand_type in ["Left", "Right"]:
            # 21個のランドマークポイント
            landmarks = {}
            for i in range(21):
                landmarks[f"point_{i}"] = {
                    "x": np.random.random(),
                    "y": np.random.random(),
                    "z": np.random.random() * 0.1
                }

            skeleton_data.append({
                "frame_number": frame_num,
                "timestamp": frame_num / 30.0,  # 30fps想定
                "hand_type": hand_type,
                "landmarks": landmarks,
                "confidence": 0.9 + np.random.random() * 0.1
            })

    return skeleton_data

def update_analysis_data(analysis_id):
    """解析データを更新"""
    conn = sqlite3.connect('aimotion.db')
    cursor = conn.cursor()

    # メトリクスデータを生成
    motion_analysis = generate_sample_metrics()
    skeleton_data = generate_sample_skeleton_data()

    # 更新
    cursor.execute("""
        UPDATE analysis_results
        SET motion_analysis = ?,
            skeleton_data = ?,
            avg_velocity = ?,
            max_velocity = ?,
            total_distance = ?
        WHERE id = ?
    """, (
        json.dumps(motion_analysis),
        json.dumps(skeleton_data),
        motion_analysis["metrics"]["summary"]["average_velocity"]["left"],
        max(motion_analysis["metrics"]["velocity"]["left_hand"]),
        100.5,  # サンプル値
        analysis_id
    ))

    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()

    return rows_affected

if __name__ == "__main__":
    analysis_id = "d934ce94-36f5-49fc-916f-c32a5327e766"

    rows = update_analysis_data(analysis_id)
    if rows > 0:
        print(f"Successfully updated analysis {analysis_id} with sample metrics")
    else:
        print(f"Failed to update analysis {analysis_id} - not found")