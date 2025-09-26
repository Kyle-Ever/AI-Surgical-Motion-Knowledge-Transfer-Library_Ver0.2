"""検出内容の詳細確認 - 何が検出されているか分析"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
import mediapipe as mp

def verify_detection():
    """検出内容を詳細に確認"""

    print("=" * 80)
    print("VERIFYING DETECTION CONTENT")
    print("=" * 80)

    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")

    if not video_path.exists():
        print(f"Error: Video not found")
        return

    # MediaPipe手検出
    mp_hands = mp.solutions.hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.01,
        min_tracking_confidence=0.01,
        model_complexity=1
    )

    mp_drawing = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(str(video_path))

    # 最初の50フレームを分析
    frame_count = 0
    exclude_y = int(720 * 0.3)  # 上部30%の境界

    print(f"Exclude line at Y={exclude_y}")
    print("\nAnalyzing first 50 frames...")
    print("-" * 40)

    detection_locations = {
        'above_line': 0,  # 除外ライン上部
        'below_line': 0,  # 除外ライン下部
        'total': 0
    }

    sample_detections = []

    while frame_count < 50:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]

        # 青い手袋の前処理
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([60, 10, 10])
        upper_blue = np.array([150, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        hsv_copy = hsv.copy()
        hsv_copy[blue_mask > 0, 0] = 18
        hsv_copy[blue_mask > 0, 1] = hsv_copy[blue_mask > 0, 1] * 0.3
        preprocessed = cv2.cvtColor(hsv_copy, cv2.COLOR_HSV2BGR)
        preprocessed = cv2.addWeighted(frame, 0.2, preprocessed, 0.8, 0)

        # 検出
        rgb_frame = cv2.cvtColor(preprocessed, cv2.COLOR_BGR2RGB)
        result = mp_hands.process(rgb_frame)

        if result.multi_hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
                # 各ランドマークの位置を分析
                y_positions = [lm.y * h for lm in hand_landmarks.landmark]
                x_positions = [lm.x * w for lm in hand_landmarks.landmark]

                center_y = sum(y_positions) / 21
                center_x = sum(x_positions) / 21

                # サイズ計算
                hand_width = max(x_positions) - min(x_positions)
                hand_height = max(y_positions) - min(y_positions)
                hand_size = max(hand_width, hand_height)

                detection_locations['total'] += 1

                if center_y < exclude_y:
                    detection_locations['above_line'] += 1
                    location = "ABOVE (excluded)"
                else:
                    detection_locations['below_line'] += 1
                    location = "BELOW (valid)"

                # 詳細情報を保存
                detection_info = {
                    'frame': frame_count,
                    'center': (int(center_x), int(center_y)),
                    'size': int(hand_size),
                    'location': location,
                    'y_ratio': center_y / h * 100,
                    'size_ratio': hand_size / min(w, h) * 100
                }

                sample_detections.append(detection_info)

                # 最初の10個の検出を詳細表示
                if len(sample_detections) <= 10:
                    print(f"Frame {frame_count:3d}: {location}")
                    print(f"  Position: ({int(center_x)}, {int(center_y)}) - Y={detection_info['y_ratio']:.1f}%")
                    print(f"  Size: {int(hand_size)} pixels ({detection_info['size_ratio']:.1f}% of screen)")

                    # 位置から推定
                    if detection_info['y_ratio'] < 20:
                        print("  WARNING: LIKELY Face/Head area")
                    elif detection_info['size_ratio'] > 30:
                        print("  WARNING: LIKELY Face (too large)")
                    else:
                        print("  OK: LIKELY Hand")

                # 最初の検出を画像として保存
                if len(sample_detections) == 1:
                    vis_frame = frame.copy()

                    # 検出を描画
                    mp_drawing.draw_landmarks(
                        vis_frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS
                    )

                    # 除外ラインを描画
                    cv2.line(vis_frame, (0, exclude_y), (w, exclude_y), (0, 255, 255), 2)
                    cv2.putText(vis_frame, "EXCLUDE LINE (30%)",
                               (10, exclude_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                    # 検出位置をマーク
                    cv2.circle(vis_frame, (int(center_x), int(center_y)), 10, (0, 0, 255), -1)
                    cv2.putText(vis_frame, f"{location}",
                               (int(center_x) + 15, int(center_y)),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                    cv2.imwrite("first_detection_analysis.jpg", vis_frame)
                    print("\n>>> First detection saved to 'first_detection_analysis.jpg'")

        frame_count += 1

    cap.release()
    mp_hands.close()

    # 統計サマリー
    print("\n" + "=" * 80)
    print("DETECTION SUMMARY")
    print("=" * 80)

    print(f"Total detections: {detection_locations['total']}")
    print(f"  - Above exclude line (Y<{exclude_y}): {detection_locations['above_line']}")
    print(f"  - Below exclude line (Y>{exclude_y}): {detection_locations['below_line']}")

    if sample_detections:
        # Y位置の分布
        y_ratios = [d['y_ratio'] for d in sample_detections]
        avg_y = np.mean(y_ratios)

        # サイズの分布
        size_ratios = [d['size_ratio'] for d in sample_detections]
        avg_size = np.mean(size_ratios)

        print(f"\nAverage Y position: {avg_y:.1f}% from top")
        print(f"Average size: {avg_size:.1f}% of screen")

        # 領域別カウント
        top_20 = sum(1 for d in sample_detections if d['y_ratio'] < 20)
        middle = sum(1 for d in sample_detections if 20 <= d['y_ratio'] < 80)
        bottom = sum(1 for d in sample_detections if d['y_ratio'] >= 80)

        print(f"\nDistribution by screen region:")
        print(f"  - Top 20% (face area): {top_20}")
        print(f"  - Middle 60%: {middle}")
        print(f"  - Bottom 20%: {bottom}")

        # 大きすぎる検出
        large = sum(1 for d in sample_detections if d['size_ratio'] > 30)
        print(f"\nLarge detections (>30% screen): {large}")

        if top_20 > len(sample_detections) * 0.5:
            print("\nPROBLEM: Most detections are in face area (top 20%)")

        if large > len(sample_detections) * 0.5:
            print("PROBLEM: Most detections are too large (likely faces)")

        print("\nCONCLUSION:")
        if avg_y < 30 and avg_size > 25:
            print("  MediaPipe is detecting FACES as hands!")
        elif detection_locations['below_line'] == 0:
            print("  No actual HANDS detected in surgical area!")
        else:
            print("  Some valid hand detections in surgical area")


if __name__ == "__main__":
    verify_detection()